# AICTE Security Deposit / FDR Management Portal (SIH 26265)

```
fdr-portal/
├── backend/                 Flask REST API
│   ├── app.py               entry point (app factory)
│   ├── config.py            settings / environment variables
│   ├── database.py          schema + DB helpers
│   ├── security.py          JWT auth + role-based access
│   ├── seed.py              first-run demo data (8 institutions, 22 FDRs)
│   ├── routes/              auth, fdrs, workflow, dashboard, admin
│   ├── services/            fdr_service (rules, risk, scan), notifier (email/SMS), bank_adapter, audit, scanner
│   └── tests/test_api.py    API + SMTP tests
├── frontend/                web UI (no build step)
│   ├── index.html
│   ├── css/style.css
│   └── js/                  core, pages, modals, main
├── docs/                    ARCHITECTURE.md, API.md
├── tests/ui_smoke.js        renders every page for every role (needs server running)
├── requirements.txt · Procfile · .env.example
```

## Run (VS Code terminal, from this folder)
```
python -m venv .venv
.venv\Scripts\activate          (Mac/Linux: source .venv/bin/activate)
pip install -r requirements.txt
python backend/app.py           ->  http://localhost:8000
```
Tests: `python backend/tests/test_api.py` (expects ALL TESTS PASSED).
Reset demo data: stop server, delete `backend/fdr.db`, start again.

## Demo logins (controlled SIH demonstrations only; all institutions and IDs are FICTIONAL)
| Role | Login | Password |
|---|---|---|
| AICTE Regulation Official | `official` | `Aicte!Verify#2026` |
| System Admin | `admin` | `Portal!Admin#2026` |
| Greenfield Institute | `greenfield` | `Greenfield!FDR#26` |
| Riverside College | `riverside` | `Riverside!FDR#26` |
| Lakeview Institute | `lakeview` | `Lakeview!FDR#26` |
| Sunrise Polytechnic | `sunrise` | `Sunrise!FDR#26` |
| Hilltop Institute | `hilltop` | `Hilltop!FDR#26` |
| Northgate Institute | `northgate` | `Northgate!FDR#26` |
| Eastwood College | `eastwood` | `Eastwood!FDR#26` |
| Westbrook College | `westbrook` | `Westbrook!FDR#26` |

These are fictional presentation credentials and are intentionally displayed on the demo sign-in screen. Enable `ENABLE_DEMO_DATA=true` only for a controlled SIH judging/demo environment. Because the credentials are public and predictable, do not enable demo mode for a real deployment or store real financial/institutional data in this demo. For a non-demo production deployment, set `ENABLE_DEMO_DATA=false` and use a separately generated bootstrap administrator password and securely provisioned official account.

## New: registration, themes, OCR
- **Institution registration and approval workflow:** login page > *Request access*. Applicants provide institution name, AICTE Institute ID / Permanent ID, college code, official email, optional landline, username, and a password of 12+ characters with uppercase, lowercase, number and symbol. Password confirmation is checked server-side and password visibility can be toggled. New accounts remain pending and cannot sign in until an authorized Regulation Official independently reviews the supplied details and approves them on **Institutions > Registration requests**. Admin accounts cannot approve or reject requests. Rejection deletes the request so the institution can re-apply. Notifications are simulated until SMTP is configured. This prototype records the ID but does not automatically query an AICTE registry; the official must verify it independently. Email ownership verification and CAPTCHA are not yet implemented (basic per-IP rate limit only).
- **Light / Dark theme:** toggle in the top bar and on the login page; the choice is remembered (defaults to your system setting).
- **Document integrity guard:** uploads are checked against file signatures (not just filename extensions), empty/mismatched files are rejected, and exact duplicate document hashes are flagged to help prevent the same receipt being attached to multiple FDRs. A successful upload returns SHA-256 integrity metadata. This is a duplicate-file safeguard, not proof that a bank issued the document.
- **OCR:** *Institution account > FDR Management > Submit FDR > choose a JPG/PNG/PDF*. Bank, FDR number, amount, issue date and maturity date are read from the document and filled in (verify before submitting). Runs in the browser (Tesseract.js, pdf.js), so it needs internet the first time to download the OCR engine; digital PDFs are read directly, scanned PDFs/photos via OCR. If OCR cannot read the file it falls back to the file name (`FDR_SBI_778299_500000.pdf`). Try `docs/samples/sample_fdr_receipt.png`. Accuracy depends on scan quality; always check the filled values.
- Tests: `node tests/ocr_parse.js` (parser; verified against real Tesseract output), `node tests/ui_smoke.js` (server running).

## Email / SMS alerts
- Triggers: reminders at 90/60/30/7 days before maturity, overdue escalation (Regional Officer, then Chairman after 30 days), new submission (to verification desk), verification mismatch and release decisions (to the institution).
- Recipients: institution contact + verification desk (+ Regional Officer / Chairman on escalation). Edit them on the **Notifications** page.
- **Go live:** copy `.env.example` to `.env`, fill SMTP (and/or Twilio) values, restart. Use **Notifications > Send test message** to check.
- Safety: while the *Demo date* slider is not at today, or for `.example` demo contacts, messages are only *simulated* (logged, never sent). Without credentials everything is simulated, and the delivery log shows exactly what would be sent.
- SMTP code is tested against a local mail server in `backend/tests/test_api.py`; the Twilio call is untested against the real service.

## Expected outcomes covered (PS 26265)
Repository, document management, verification + discrepancy detection, validity/maturity tracking, renewal history, release workflow, alerts + escalation (in-app, email, SMS), dashboard + reports, audit trail + access control, integration-ready bank adapter (`services/bank_adapter.py`). The dashboard also reports measurable impact: verification turnaround, share of bank-verified records, issues flagged automatically, reminders issued, estimated staff time saved (baseline and time-saving figures are stated assumptions; replace with AICTE figures).

## Host (Render.com)
A `render.yaml` Blueprint is included. Push the project to your own GitHub repository and create a Render Blueprint from it. It configures a persistent disk for SQLite and uploads, a generated `SECRET_KEY`, and a one-time production bootstrap administrator. Retrieve the generated `BOOTSTRAP_ADMIN_PASSWORD` from your service environment settings for the first login, then create an official account through your own admin/onboarding process. The persistent disk service may incur hosting charges. Do not use local demo credentials in a public deployment.

## Real vs simulated
Real: auth/roles, workflow, discrepancy rules, scanner, release rules, audit chain, document hashing.
Simulated until configured: bank verification (registry table behind an adapter), OCR (filename: `FDR_SBI_778299_500000.pdf`), email/SMS (live once SMTP/Twilio are set).


## Added in the SIH hardening pass
- **FDR Intelligence** page (`GET /api/intelligence`): deterministic risk factors with human-readable reasons, prioritised review queue, and renewal-chain amount/date checks. Scores are triage support only, not fraud determinations.
- **Bulk CSV import** (`POST /api/import/fdrs`): validates required columns, dates, amounts, duplicate FDR numbers, row-level outcomes, and institution scoping. Only institution accounts can submit or bulk-import FDRs, and records are always assigned to the authenticated institution. Maximum CSV size is 2 MB.
- **Document signature checks** validate PDF/PNG/JPEG magic bytes as well as the filename extension; exact duplicate SHA-256 uploads are rejected. A hash detects byte-identical files but does not prove authenticity.
- **Production safety**: set `APP_ENV=production` and a strong `SECRET_KEY`; the app refuses to start with the built-in demo secret. A fresh production database does not receive demo accounts or synthetic FDR records; it requires `BOOTSTRAP_ADMIN_USERNAME` and a `BOOTSTRAP_ADMIN_PASSWORD` of at least 14 characters.
- Renewal is restricted to bank-verified instruments; release requests require a reason.

### CSV import format
```csv
bank,fdr_number,amount,issue_date,maturity_date
SBI,DEMO001,100000,2026-01-01,2027-01-01
```
Use ISO dates (`YYYY-MM-DD`). Only institution accounts can import CSV files; records are automatically assigned to the signed-in institution, and any supplied `institution_id` column is ignored. Use fictional sample data for demonstrations.

### Deployment reminder
The local SQLite database and local upload folder are suitable for a prototype, not a multi-instance production service. If deployed on Vercel, the platform sets `VERCEL` and the app treats that as production unless `APP_ENV` is explicitly set; configure the production secret and bootstrap admin environment variables or startup intentionally fails closed. For production, configure a persistent database/storage service, restrict CORS if adding cross-origin clients, use HTTPS, rotate secrets, add backups/retention policies, and integrate a bank only through a formally authorised verification API. The bank registry shipped with this prototype is a demo adapter and must not be described as a live bank connection.
