"""FDR repository: list, detail, create, document upload."""
import os, json, csv, io, time, hashlib, datetime as dt
import jwt
from flask import Blueprint, request, jsonify, g, Response
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from config import UP, ALLOWED, SECRET
from database import db, setting, today, D, now
from security import auth, own, getf, nf
from services.audit import audit, chain_ok, hist
from services.fdr_service import lifecycle, flags, risk, fd, notify, scan

from services.fdr_service import announce
bp = Blueprint("fdrs", __name__)

@bp.get("/api/fdrs")
@auth()
def fdrs():
    c, t = db(), today(db()); q = request.args.get("q", "").lower(); st = request.args.get("state", "")
    rows = [fd(c, f, t) for f in c.execute("SELECT * FROM fdrs ORDER BY maturity_date") if own(f)]
    rows = [r for r in rows if (not q or q in (r["fdr_number"] + r["institution"] + r["bank"]).lower()) and (not st or st in (r["state"], r["lifecycle"]))]
    return jsonify(rows)

@bp.get("/api/fdrs/<int:fid>")
@auth()
def fdr_one(fid):
    f = getf(fid); return jsonify(fd(db(), f, today(db()), True)) if f else nf()

@bp.post("/api/fdrs")
@auth("institution")
def fdr_new():
    c, j = db(), request.get_json(silent=True) or {}
    inst = g.u["institution_id"] if g.u["role"] == "institution" else j.get("institution_id")
    if not inst or not c.execute("SELECT 1 FROM institutions WHERE id=?", (inst,)).fetchone(): return jsonify(error="Select an institution"), 400
    try:
        amt = float(j["amount"]); n = j["fdr_number"].strip(); bank = j["bank"].strip(); i, m = j["issue_date"], j["maturity_date"]; D(i); D(m)
        assert amt > 0 and n and bank
    except Exception: return jsonify(error="Fill bank, FDR number, positive amount and valid dates"), 400
    if m <= i: return jsonify(error="Maturity date must be after issue date"), 400
    if c.execute("SELECT 1 FROM fdrs WHERE fdr_number=?", (n,)).fetchone(): return jsonify(error="Duplicate FDR number"), 409
    cur = c.execute("INSERT INTO fdrs(institution_id,bank,fdr_number,amount,issue_date,maturity_date) VALUES(?,?,?,?,?,?)", (inst, bank, n, amt, i, m))
    hist(c, cur.lastrowid, g.u["username"], f"FDR {n} submitted")
    announce(c, c.execute("SELECT * FROM fdrs WHERE id=?", (cur.lastrowid,)).fetchone(), "New FDR submitted and awaiting bank verification", "desk")
    c.commit(); return jsonify(id=cur.lastrowid), 201

@bp.post("/api/import/fdrs")
@auth("institution")
def import_fdrs():
    """Bulk import validated FDR rows from CSV; invalid rows are reported, not silently skipped."""
    c = db(); fl = request.files.get("file")
    if not fl or not fl.filename or not fl.filename.lower().endswith(".csv"):
        return jsonify(error="Upload a .csv file with bank,fdr_number,amount,issue_date,maturity_date columns"), 400
    raw = fl.read(2 * 1024 * 1024 + 1)
    if len(raw) > 2 * 1024 * 1024: return jsonify(error="CSV exceeds the 2 MB import limit"), 413
    try: text = raw.decode("utf-8-sig")
    except UnicodeDecodeError: return jsonify(error="CSV must be UTF-8 encoded"), 400
    reader = csv.DictReader(io.StringIO(text))
    required = {"bank", "fdr_number", "amount", "issue_date", "maturity_date"}
    if not reader.fieldnames or not required.issubset({x.strip() for x in reader.fieldnames if x}):
        return jsonify(error="Missing required CSV columns", required=sorted(required)), 400
    results, created = [], 0
    for line, row in enumerate(reader, start=2):
        try:
            bank = (row.get("bank") or "").strip()[:100]; number = (row.get("fdr_number") or "").strip()[:100]
            amount = float(row.get("amount") or 0); issue = (row.get("issue_date") or "").strip(); maturity = (row.get("maturity_date") or "").strip()
            D(issue); D(maturity)
            if not bank or not number or amount <= 0 or maturity <= issue: raise ValueError("Invalid bank, FDR number, amount, or dates")
            if c.execute("SELECT 1 FROM fdrs WHERE fdr_number=?", (number,)).fetchone(): raise ValueError("Duplicate FDR number")
            inst = g.u["institution_id"]
            cur = c.execute("INSERT INTO fdrs(institution_id,bank,fdr_number,amount,issue_date,maturity_date) VALUES(?,?,?,?,?,?)", (inst, bank, number, amount, issue, maturity))
            hist(c, cur.lastrowid, g.u["username"], f"FDR {number} imported from CSV")
            created += 1; results.append({"line":line,"fdr_number":number,"status":"created","id":cur.lastrowid})
        except Exception as ex:
            results.append({"line":line,"fdr_number":(row.get("fdr_number") or "").strip(),"status":"rejected","error":str(ex)[:180]})
    c.commit()
    return jsonify(created=created, rejected=len(results)-created, results=results), 200

@bp.post("/api/fdrs/<int:fid>/upload")
@auth("institution")
def upload(fid):
    c, f, fl = db(), getf(fid), request.files.get("file")
    if not f: return nf()
    if not fl or not fl.filename or not fl.filename.lower().endswith(ALLOWED):
        return jsonify(error="Upload a PDF, PNG or JPG file (maximum 5 MB)."), 400
    data = fl.read()
    if not data:
        return jsonify(error="The uploaded file is empty."), 400
    # Validate the file signature as well as the extension; extensions alone are not trustworthy.
    ext = os.path.splitext(fl.filename.lower())[1]
    signatures = {
        ".pdf": data.startswith(b"%PDF-"),
        ".png": data.startswith(bytes([137]) + b"PNG\r\n\x1a\n"),
        ".jpg": data.startswith(bytes([255, 216, 255])),
        ".jpeg": data.startswith(bytes([255, 216, 255])),
    }
    if not signatures.get(ext, False):
        return jsonify(error="File content does not match its extension. Upload a valid PDF, PNG or JPG."), 400
    h = hashlib.sha256(data).hexdigest()
    # The same scanned receipt should not silently be attached to multiple instruments.
    duplicate = c.execute("SELECT fdr_id, name FROM docs WHERE sha256=? LIMIT 1", (h,)).fetchone()
    if duplicate:
        return jsonify(error="This exact document has already been uploaded. Check the existing FDR record before retrying.",
                       duplicate_fdr_id=duplicate["fdr_id"]), 409
    name = secure_filename(fl.filename)
    if not name:
        return jsonify(error="Invalid file name."), 400
    p = os.path.join(UP, f"{h[:12]}_{name}")
    with open(p, "wb") as out:
        out.write(data)
    c.execute("INSERT INTO docs(fdr_id,name,sha256,path,at) VALUES(?,?,?,?,?)", (fid, name, h, p, now()))
    hist(c, fid, g.u["username"], f"Document uploaded: {name} (sha256 {h[:12]})")
    c.commit()
    return jsonify(sha256=h, integrity_check="passed", duplicate_check="passed"), 201

@bp.put("/api/fdrs/<int:fid>")
@auth()
def fdr_edit(fid):
    c, f, j = db(), getf(fid), request.get_json(silent=True) or {}
    if not f: return nf()
    if f["state"] not in ("SUBMITTED", "DISCREPANCY"): return jsonify(error="Only unverified FDRs can be edited"), 400
    try:
        bank, n = (j.get("bank") or f["bank"]).strip(), (j.get("fdr_number") or f["fdr_number"]).strip(); amt = float(j.get("amount", f["amount"]))
        i, m = j.get("issue_date") or f["issue_date"], j.get("maturity_date") or f["maturity_date"]; D(i); D(m); assert amt > 0 and n and bank
    except Exception: return jsonify(error="Invalid values"), 400
    if m <= i: return jsonify(error="Maturity date must be after issue date"), 400
    if n != f["fdr_number"] and c.execute("SELECT 1 FROM fdrs WHERE fdr_number=?", (n,)).fetchone(): return jsonify(error="Duplicate FDR number"), 409
    c.execute("UPDATE fdrs SET bank=?,fdr_number=?,amount=?,issue_date=?,maturity_date=?,state='SUBMITTED',bank_status='UNCHECKED',bank_conf=NULL,last_rem=NULL WHERE id=?", (bank, n, amt, i, m, fid))
    hist(c, fid, g.u["username"], "Details edited (bank re-verification required)"); c.commit(); return jsonify(ok=True)
