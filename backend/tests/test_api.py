"""Run: python backend/tests/test_api.py  (uses a temporary database)"""
import os, sys, tempfile, io
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "t.db")
import app as A
c = A.app.test_client()
def login(u, p): return {"Authorization": "Bearer " + c.post("/api/login", json={"username": u, "password": p}).get_json()["token"]}
off, ins = login("official", "Aicte!Verify#2026"), login("greenfield", "Greenfield!FDR#26")
assert c.post("/api/login", json={"username": "x", "password": "y"}).status_code == 401
assert c.get("/api/fdrs").status_code == 401
d = c.get("/api/dashboard", headers=off).get_json(); print("dashboard", {k: d[k] for k in ("active", "expiring", "matured", "pending", "high_risk")})
fl = {f["fdr_number"]: f for f in c.get("/api/fdrs", headers=off).get_json()}
assert all(f["institution"] == "Greenfield Institute of Technology" for f in c.get("/api/fdrs", headers=ins).get_json()), "institution isolation"
assert c.post(f"/api/fdrs/{fl['IB902114']['id']}/verify", headers=ins).status_code == 403
print("mismatch ->", c.post(f"/api/fdrs/{fl['IB902114']['id']}/verify", headers=off).get_json())
print("not found ->", c.post(f"/api/fdrs/{fl['SBI120045']['id']}/verify", headers=off).get_json())
print("good ->", c.post(f"/api/fdrs/{fl['HD330918']['id']}/verify", headers=off).get_json())
r = c.post("/api/fdrs", headers=ins, json={"bank": "SBI", "fdr_number": "SBI999", "amount": 100000, "issue_date": "2026-10-01", "maturity_date": "2027-10-01"}); assert r.status_code == 201, r.data
nid = r.get_json()["id"]; assert c.post("/api/fdrs", headers=ins, json={"bank": "SBI", "fdr_number": "SBI999", "amount": 1, "issue_date": "2026-10-01", "maturity_date": "2027-10-01"}).status_code == 409
assert c.post(f"/api/fdrs/{nid}/upload", headers=ins, data={"file": (io.BytesIO(b"%PDF-1.4\n% demo PDF bytes"), "x.pdf")}, content_type="multipart/form-data").status_code == 201
dup = c.post(f"/api/fdrs/{nid}/upload", headers=ins, data={"file": (io.BytesIO(b"%PDF-1.4\\n% demo PDF bytes"), "copy.pdf")}, content_type="multipart/form-data")
assert dup.status_code == 409, dup.data
assert c.post(f"/api/fdrs/{nid}/upload", headers=ins, data={"file": (io.BytesIO(b"x"), "x.exe")}, content_type="multipart/form-data").status_code == 400
bb = fl["BB440276"]["id"]; print("approve ->", c.post(f"/api/fdrs/{bb}/decide_release", headers=off, json={"approve": True}).get_json())
rq = fl["SBI778201"]["id"]; assert c.post(f"/api/fdrs/{rq}/request_release", headers=ins, json={"reason": "Institutional approval cycle complete"}).status_code == 200
assert c.post(f"/api/fdrs/{rq}/decide_release", headers=off, json={"approve": False, "remark": "need docs"}).status_code == 200
rn = c.post(f"/api/fdrs/{rq}/renew", headers=ins, json={"fdr_number": "SBI-R1", "amount": 500000, "maturity_date": "2028-01-01"}); assert rn.status_code == 201, rn.data
print("time shift ->", c.post("/api/time", headers=off, json={"offset": 120}).get_json())
print("notifications:", len(c.get("/api/notifications", headers=off).get_json()))
assert c.get("/api/reports/upcoming?fmt=csv", headers=off).data.startswith(b"FDR No")
print("audit chain intact:", c.get("/api/audit", headers=off).get_json()["intact"])
print("ALL TESTS PASSED")
ad = login("admin", "Portal!Admin#2026")
assert c.get("/api/institutions", headers=off).status_code == 200 and c.get("/api/institutions", headers=ins).status_code == 403
assert c.post("/api/fdrs", headers=ad, json={"institution_id": 1, "bank": "SBI", "fdr_number": "ADMINADD1", "amount": 1000, "issue_date": "2026-01-01", "maturity_date": "2027-01-01"}).status_code == 403, "admins must not submit FDRs"
assert c.post("/api/institutions", headers=ad, json={"name": "Test College", "aicte_id": "TEST-AICTE-1002", "college_code": "TST1002", "username": "tcol", "password": "Test!College2026"}).status_code == 201
assert c.post("/api/login", json={"username": "tcol", "password": "Test!College2026"}).status_code == 403, "admin-created institutions must remain pending"
assert c.get("/api/registrations", headers=ad).status_code == 403
reg_admin_created = [r for r in c.get("/api/registrations", headers=off).get_json() if r["username"] == "tcol"][0]
assert c.post(f"/api/registrations/{reg_admin_created['id']}/decide", headers=off, json={"approve": True}).status_code == 200
iid = [i for i in c.get("/api/institutions", headers=off).get_json() if i["name"] == "Test College"][0]["id"]
assert c.post("/api/fdrs", headers=off, json={"institution_id": iid, "bank": "SBI", "fdr_number": "OFF1", "amount": 1000, "issue_date": "2026-01-01", "maturity_date": "2027-01-01"}).status_code == 403, "only institutions may submit FDRs"
assert len(c.get("/api/releases", headers=ins).get_json()) >= 1 and "to_verify" in c.get("/api/dashboard", headers=off).get_json()
print("EXTRA TESTS PASSED")

# ---- notifications, outbox, edit, metrics, real SMTP path (fake local mail server) ----
import socketserver, threading
GOT = []
class H(socketserver.StreamRequestHandler):
    def handle(self):
        w = lambda s: (self.wfile.write((s + "\r\n").encode()), self.wfile.flush()); w("220 test ESMTP"); data, buf = False, []
        while True:
            line = self.rfile.readline()
            if not line: break
            l = line.decode(errors="replace").rstrip("\r\n")
            if data:
                if l == ".": GOT.append("\n".join(buf)); data, buf = False, []; w("250 OK")
                else: buf.append(l)
                continue
            u = l.upper()
            if u.startswith(("EHLO", "HELO")): w("250 localhost")
            elif u.startswith("DATA"): data = True; w("354 go")
            elif u.startswith("QUIT"): w("221 bye"); break
            else: w("250 OK")
srv = socketserver.TCPServer(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
assert c.post("/api/time", headers=off, json={"offset": 0}).status_code == 200
ob = c.get("/api/outbox", headers=off).get_json(); assert ob and all(o["status"] in ("sent", "simulated", "failed") for o in ob); assert c.get("/api/outbox", headers=ins).status_code == 200
m = c.get("/api/dashboard", headers=off).get_json()["metrics"]; print("metrics", m); assert m["avg_verify_hours"] and m["messages"] > 0
assert "desk_email" in c.get("/api/notify_settings", headers=off).get_json()["settings"] and c.get("/api/notify_settings", headers=ins).status_code == 403
assert c.post("/api/notify_settings", headers=off, json={"desk_email": "desk@aicte.example"}).status_code == 200
assert c.put(f"/api/fdrs/{nid}", headers=ins, json={"amount": 120000}).status_code == 200
assert c.put(f"/api/fdrs/{fl['SBI664390']['id']}", headers=off, json={"amount": 1}).status_code == 400
sun = [i for i in c.get("/api/institutions", headers=off).get_json() if i["username"] == "sunrise"][0]["id"]
assert c.put(f"/api/institutions/{sun}", headers=ad, json={"email": "registrar@sunrise.test", "phone": ""}).status_code == 200
os.environ.update(SMTP_HOST="127.0.0.1", SMTP_PORT=str(srv.server_address[1]), SMTP_TLS="0")
assert c.post(f"/api/fdrs/{fl['IB902114']['id']}/verify", headers=off).status_code == 200
rows = [o for o in c.get("/api/outbox", headers=off).get_json() if "sunrise.test" in o["recipient"]]
print("live email ->", rows[0]["status"], rows[0]["recipient"]); assert rows and rows[0]["status"] == "sent" and any("IB902114" in g_ for g_ in GOT), (rows, GOT)
t = c.post("/api/notify_test", headers=off, json={"email": "me@college.test"}).get_json(); print("test msg ->", t); assert t["results"][0]["status"] == "sent"
assert c.post("/api/time", headers=off, json={"offset": 90}).status_code == 200
assert c.get("/api/outbox", headers=off).get_json()[0]["status"] == "simulated", "demo date must never send live"
print("NOTIFICATION TESTS PASSED")

# ---- self-registration with approval ----
ok_ = {"name": "Test Reg College", "aicte_id": "TEST-AICTE-1001", "college_code": "REG1001", "email": "reg@testcol.test", "phone": "044-23456789", "username": "regcol", "password": "Reg!College2026", "confirm_password": "Reg!College2026"}
assert c.post("/api/register", json=ok_).status_code == 201
assert c.post("/api/register", json=ok_).status_code == 409
assert c.post("/api/register", json={"name": "Bad", "email": "nope", "username": "x", "password": "1"}).status_code == 400
assert c.post("/api/register", json=dict(ok_, name="Mismatch College", aicte_id="TEST-AICTE-MISMATCH", college_code="MISM1", username="mismatch", confirm_password="Different!Password2026")).status_code == 400, "confirm password must match"
assert c.post("/api/register", json=dict(ok_, name="Weak Password College", aicte_id="TEST-AICTE-WEAK", college_code="WEAK1", username="weakpass", password="password123", confirm_password="password123")).status_code == 400, "weak registration passwords must be rejected"
assert c.post("/api/login", json={"username": "regcol", "password": "Reg!College2026"}).status_code == 403, "pending users must not sign in"
regs = c.get("/api/registrations", headers=off).get_json(); rid = [x["id"] for x in regs if x["username"] == "regcol"][0]
assert c.get("/api/registrations", headers=ins).status_code == 403
assert c.get("/api/registrations", headers=ad).status_code == 403, "only an AICTE official may review registrations"
assert "Test Reg College" not in [i["name"] for i in c.get("/api/institutions", headers=off).get_json()]
assert c.get("/api/dashboard", headers=off).get_json()["reg_pending"] >= 1
assert c.post(f"/api/registrations/{rid}/decide", headers=off, json={"approve": True}).status_code == 200
lg = c.post("/api/login", json={"username": "regcol", "password": "Reg!College2026"}); assert lg.status_code == 200
assert c.get("/api/dashboard", headers={"Authorization": "Bearer " + lg.get_json()["token"]}).get_json()["total"] == 0
assert "Test Reg College" in [i["name"] for i in c.get("/api/institutions", headers=off).get_json()]
assert c.post("/api/register", json=dict(ok_, name="Rejected College", aicte_id="TEST-AICTE-1003", college_code="REG1003", username="rejcol")).status_code == 201
rj = [x["id"] for x in c.get("/api/registrations", headers=off).get_json() if x["username"] == "rejcol"][0]
assert c.post(f"/api/registrations/{rj}/decide", headers=off, json={"approve": False}).status_code == 200
assert c.post("/api/login", json={"username": "rejcol", "password": "Reg!College2026"}).status_code == 401
assert c.get("/api/audit", headers=off).get_json()["intact"]
print("REGISTRATION TESTS PASSED")


# ---- SIH hardening: explainable intelligence + validated CSV import ----
intel = c.get("/api/intelligence", headers=off)
assert intel.status_code == 200, intel.data
ij = intel.get_json()
assert "priority_queue" in ij and "disclaimer" in ij and all("risk_reasons" in r for r in ij["priority_queue"])
assert c.get("/api/intelligence", headers=ins).status_code == 200
csv_data = b"bank,fdr_number,amount,issue_date,maturity_date,institution_id\nSBI,BULKTEST1,100000,2026-01-01,2027-01-01,1\nSBI,BULKTEST2,-1,2026-01-01,2027-01-01,1\nSBI,BULKTEST1,100000,2026-01-01,2027-01-01,1\n"
imp = c.post("/api/import/fdrs", headers=off, data={"file": (io.BytesIO(csv_data), "import.csv")}, content_type="multipart/form-data")
assert imp.status_code == 403, "only institutions may bulk-import their own FDRs"
imp = c.post("/api/import/fdrs", headers=ins, data={"file": (io.BytesIO(csv_data), "import.csv")}, content_type="multipart/form-data")
assert imp.status_code == 200, imp.data
assert imp.get_json()["created"] == 1 and imp.get_json()["rejected"] == 2, imp.get_json()
# Institution imports cannot assign records to a different institution even if a CSV includes an ID.
csv_inst = b"bank,fdr_number,amount,issue_date,maturity_date,institution_id\nSBI,OWNBULK1,100000,2026-01-01,2027-01-01,2\n"
imp2 = c.post("/api/import/fdrs", headers=ins, data={"file": (io.BytesIO(csv_inst), "import.csv")}, content_type="multipart/form-data")
assert imp2.status_code == 200 and imp2.get_json()["created"] == 1, imp2.data
ownrow = c.get("/api/fdrs?q=OWNBULK1", headers=ins).get_json()
assert len(ownrow) == 1 and ownrow[0]["institution_id"] == 1, ownrow
badpng = c.post(f"/api/fdrs/{nid}/upload", headers=ins, data={"file": (io.BytesIO(b"not a png"), "fake.png")}, content_type="multipart/form-data")
assert badpng.status_code == 400, badpng.data
assert c.get("/api/audit", headers=off).get_json()["intact"]
print("SIH INTELLIGENCE / CSV / FILE SIGNATURE TESTS PASSED")
