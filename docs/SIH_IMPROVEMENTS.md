# SIH 26265 improvement and validation notes

## Added in this pass

- FDR Intelligence API and workspace page with deterministic, explainable risk factors and a prioritized human-review queue.
- Renewal-chain review notes for amount changes and date continuity.
- CSV bulk import with row-by-row acceptance/rejection results, required-column checks, ISO date validation, positive amount checks, duplicate-number checks, and institution scoping.
- File-signature validation for PDF/PNG/JPEG uploads and exact SHA-256 duplicate detection.
- Production startup guard for the signing secret, no demo-data seeding on a fresh production database, and one-time bootstrap admin environment variables.
- Persistent upload directory configuration, health endpoint, Render Blueprint, and Dockerfile.
- Renewal restriction to bank-verified FDRs and required release-request reason.

## Existing capabilities retained

Institution-scoped records, role-based access, OCR-assisted entry, bank-registry adapter, discrepancy review, maturity reminders, escalation, renewal lineage, release/refund approvals, email/SMS outbox, CSV reports, dashboard metrics, and hash-chained audit log.

## Competitor review approach

Use the 30 repository URLs supplied by the team as a feature-review checklist. Compare actual runnable behavior, tests, and source code—not README promises or screenshots alone. Common feature areas worth benchmarking are OCR/data extraction, source-of-truth verification, risk explainability, renewal lineage, workflow queues, auditability, bulk migration, and deployment readiness. Do not copy another team's code without checking its license and attribution requirements. This document does not claim that all 30 repositories were fully cloned or tested.

## Validation status in the authoring environment

- JavaScript syntax checks: passed.
- Python source parsing/bytecode compilation: passed.
- OCR parser tests (`node tests/ocr_parse.js`): passed.
- Full Flask API test suite: not executed here because Flask/PyJWT dependencies were not installed and package downloads were unavailable in the authoring environment. Run the full suite locally after installing requirements.
- Browser/UI smoke and end-to-end tests: require a running server; not claimed as passed here.

## Before public deployment

1. Set `APP_ENV=production`, a unique `SECRET_KEY`, and bootstrap administrator credentials.
2. Use a persistent database and upload storage. The included Render Blueprint configures a persistent disk and may incur hosting charges.
3. Change the bootstrap password after first login and create official accounts through controlled onboarding.
4. Replace the demo bank registry with a formally authorized bank verification API before describing results as bank-confirmed.
5. Configure SMTP/SMS only with approved credentials and recipients; keep demo date mode enabled for presentations using synthetic records.
6. Back up the database and uploads, restrict access, and run the full tests before using real institutional or financial records.
