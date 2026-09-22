# Fintap Bank Intelligence — deployment-ready pilot

This project is a deployment foundation for the Fintap bank-statement workflow. It accepts PDF bank statements, detects supported banks, classifies transactions, creates an accountant review queue, and produces draft VAT and management reports.

## Current supported parser status
- FNB: line-level parser implemented for the supplied FNB layout.
- Standard Bank, Capitec, Absa, Nedbank: bank detection is present, but line-level extraction still requires labelled statements for each layout. The system deliberately returns zero extracted transactions rather than inventing financial data.

## Hosted pilot architecture
- FastAPI web application
- PostgreSQL when `DATABASE_URL` is supplied; SQLite for local development
- Persistent job records
- Basic authentication for the hosted pilot
- Docker deployment
- Render deployment manifest
- Health endpoint: `/health`

## Local run
```bash
python3 -m pip install -r requirements.txt
python3 -m pip install -e .
cp .env.example .env
set -a; . ./.env; set +a
pibg-web
```
Open `http://127.0.0.1:8000`.

## Docker
```bash
docker build -t fintap-bank-intelligence .
docker run --rm -p 8000:8000 -e APP_USERNAME=admin -e APP_PASSWORD=change-me fintap-bank-intelligence
```

## Render
The included `render.yaml` provisions the web service and PostgreSQL database. Set `APP_USERNAME` and `APP_PASSWORD` as secrets in Render. For a real production rollout, move uploaded statements to S3/Cloudflare R2 and add proper per-user authentication and audit logging before opening the service broadly.

## Important accounting control
The bank statement is an extraction source, not automatic proof of input VAT. Transactions requiring tax invoices/support are kept in the review queue. Incoming money is not automatically treated as final revenue.

## Next engineering phase
1. Add labelled Standard Bank, Capitec, Absa and Nedbank parser fixtures.
2. Add client/business/user tables and role-based access.
3. Add S3/R2 document storage.
4. Add GL posting engine and chart of accounts.
5. Add VAT201 mapping and reconciliation controls.
6. Expand the management-report engine to the agreed PIBG report structure.
7. Add AI-assisted classification only for low-confidence transactions, with accountant approval and audit trail.
