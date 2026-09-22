"""Production-oriented Fintap bank-statement review web app.

For a first hosted pilot this uses FastAPI + SQLAlchemy. PostgreSQL is used when
DATABASE_URL is supplied; SQLite is supported for local development.
"""
from __future__ import annotations

import base64
import csv
import html
import io
import json
import os
import secrets
import uuid
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path
from typing import Generator

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy import Boolean, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from .models import Transaction
from .parser import parse_statement
from .reporting import write_management_report, write_vat_schedule

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/fintap.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    client: Mapped[str] = mapped_column(String(255))
    bank: Mapped[str] = mapped_column(String(64))
    transaction_json: Mapped[str] = mapped_column(Text)
    statement_filename: Mapped[str] = mapped_column(String(255))


class AppUser(Base):
    __tablename__ = "app_users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(128), unique=True)
    password_hash: Mapped[str] = mapped_column(String(128))


Base.metadata.create_all(engine)
Path("data/jobs").mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Fintap Bank Intelligence", version="0.1.0")
security = HTTPBasic(auto_error=False)


def db() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def auth(credentials: HTTPBasicCredentials | None = Depends(security)) -> str:
    username = os.getenv("APP_USERNAME")
    password = os.getenv("APP_PASSWORD")
    if not username or not password:
        return "local-pilot"
    if not credentials or not (
        secrets.compare_digest(credentials.username, username)
        and secrets.compare_digest(credentials.password, password)
    ):
        raise HTTPException(status_code=401, detail="Authentication required", headers={"WWW-Authenticate": "Basic"})
    return credentials.username


def tx_from_json(item: dict) -> Transaction:
    item = dict(item)
    for key in ("amount", "vat_rate", "vat_amount"):
        item[key] = Decimal(str(item[key]))
    return Transaction(**item)


def txs(job: Job) -> list[Transaction]:
    return [tx_from_json(x) for x in json.loads(job.transaction_json)]


def page(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)} | Fintap</title>
<style>body{{font-family:Arial,sans-serif;margin:0;background:#f5f9f8;color:#16383d}}header{{background:#fff;padding:20px 7%;border-bottom:4px solid #00a99d}}.brand{{font-size:32px;font-weight:800;color:#008f87;letter-spacing:2px}}.tag{{color:#08756f;font-size:13px}}main{{max-width:1180px;margin:35px auto;padding:0 22px}}.card{{background:white;border-radius:10px;padding:25px;margin:20px 0;box-shadow:0 1px 7px #dbe6e5}}input,button{{padding:10px;margin:6px 0;border:1px solid #b9d4d0;border-radius:5px}}button{{background:#008f87;color:white;border:0;font-weight:700;cursor:pointer}}table{{width:100%;border-collapse:collapse;font-size:13px}}th,td{{padding:9px;border-bottom:1px solid #e2edeb;text-align:left;vertical-align:top}}th{{background:#e9f7f5}}.review{{color:#a35c00;font-weight:700}}.ok{{color:#08756f;font-weight:700}}a{{color:#007d76}}</style></head><body><header><div class="brand">FINTAP</div><div class="tag">Building financially intelligent businesses</div></header><main>{body}</main></body></html>''')


@app.get("/health", response_class=PlainTextResponse)
def health() -> str:
    return "ok"


@app.get("/", response_class=HTMLResponse)
def home(_: str = Depends(auth)) -> HTMLResponse:
    return page("Bank statement review", '''<div class="card"><h1>Bank statement review</h1><p>Upload a PDF statement to create a VAT-inclusive draft ledger and accountant review queue.</p>
<form enctype="multipart/form-data" method="post" action="/upload"><label>Client name<br><input name="client" required placeholder="Yanga Environmental Services (Pty) Ltd" size="48"></label><br><label>PDF statement<br><input name="statement" type="file" accept="application/pdf" required></label><br><button>Process statement</button></form></div>
<div class="card"><h2>Workflow</h2><p>Upload → bank detection → classification → accountant review → VAT schedule → management report.</p><p><strong>Hosted pilot:</strong> transactions persist in the configured database.</p></div>''')


@app.post("/upload")
async def upload(client: str = Form(...), statement: UploadFile = File(...), _: str = Depends(auth), session: Session = Depends(db)) -> RedirectResponse:
    if statement.content_type not in ("application/pdf", "application/octet-stream") and not (statement.filename or "").lower().endswith(".pdf"):
        raise HTTPException(400, "Please upload a PDF bank statement")
    content = await statement.read()
    if len(content) > int(os.getenv("MAX_UPLOAD_MB", "25")) * 1024 * 1024:
        raise HTTPException(413, "Statement is larger than the configured upload limit")
    job_id = uuid.uuid4().hex[:12]
    job_dir = Path("data/jobs") / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = job_dir / "statement.pdf"
    pdf_path.write_bytes(content)
    bank, transactions = parse_statement(pdf_path)
    (job_dir / "statement.pdf").chmod(0o600)
    job = Job(id=job_id, client=client, bank=bank, transaction_json=json.dumps([asdict(x) for x in transactions], default=str), statement_filename=statement.filename or "statement.pdf")
    session.add(job); session.commit()
    return RedirectResponse(f"/jobs/{job_id}/review", status_code=303)


@app.get("/jobs/{job_id}/review", response_class=HTMLResponse)
def review(job_id: str, _: str = Depends(auth), session: Session = Depends(db)) -> HTMLResponse:
    job = session.get(Job, job_id)
    if not job: raise HTTPException(404, "Job not found")
    rows = []
    for index, row in enumerate(txs(job)):
        status = "Approved" if row.accountant_approved else ("Review required" if row.review_required else "Auto-classified")
        action = "" if row.accountant_approved else f'<form method="post" action="/jobs/{job_id}/approve/{index}"><button>Approve</button></form>'
        rows.append(f"<tr><td>{html.escape(row.date)}</td><td>{html.escape(row.description)}</td><td>R {row.amount:,.2f}</td><td>{html.escape(row.accounting_category)}</td><td>{html.escape(row.vat_treatment)}</td><td class=\"{'review' if row.review_required else 'ok'}\">{status}</td><td>{action}</td></tr>")
    links = f'<p><a href="/jobs/{job_id}/download/transactions.csv">Transactions CSV</a> · <a href="/jobs/{job_id}/download/review_queue.csv">Review queue CSV</a> · <a href="/jobs/{job_id}/download/vat_schedule.csv">VAT schedule CSV</a> · <a href="/jobs/{job_id}/download/management_report.html">Management report</a></p>'
    content = f'<div class="card"><h1>{html.escape(job.client)}</h1><p>Detected bank: <strong>{html.escape(job.bank)}</strong> | {len(txs(job))} transactions.</p>{links}</div><div class="card"><h2>Accountant review queue</h2><table><tr><th>Date</th><th>Bank narration</th><th>Amount</th><th>Category</th><th>VAT treatment</th><th>Status</th><th>Action</th></tr>{"".join(rows) or "<tr><td colspan=7>No line-level parser is available for this bank yet.</td></tr>"}</table></div>'
    return page("Accountant review", content)


@app.post("/jobs/{job_id}/approve/{index}")
def approve(job_id: str, index: int, _: str = Depends(auth), session: Session = Depends(db)) -> RedirectResponse:
    job = session.get(Job, job_id)
    if not job: raise HTTPException(404, "Job not found")
    rows = txs(job)
    if index < 0 or index >= len(rows): raise HTTPException(404, "Transaction not found")
    rows[index].accountant_approved = True; rows[index].review_required = False; rows[index].rule_source = "Accountant approval"
    job.transaction_json = json.dumps([asdict(x) for x in rows], default=str)
    session.commit()
    return RedirectResponse(f"/jobs/{job_id}/review", status_code=303)


def csv_bytes(rows: list[Transaction]) -> bytes:
    output = io.StringIO(); fields = list(rows[0].csv_row()) if rows else list(Transaction.__annotations__)
    writer = csv.DictWriter(output, fieldnames=fields); writer.writeheader(); writer.writerows(row.csv_row() for row in rows)
    return output.getvalue().encode()


@app.get("/jobs/{job_id}/download/{filename}")
def download(job_id: str, filename: str, _: str = Depends(auth), session: Session = Depends(db)) -> Response:
    job = session.get(Job, job_id)
    if not job: raise HTTPException(404, "Job not found")
    rows = txs(job); job_dir = Path("data/jobs") / job_id; job_dir.mkdir(parents=True, exist_ok=True)
    if filename == "transactions.csv": return Response(csv_bytes(rows), media_type="text/csv", headers={"Content-Disposition":"attachment; filename=transactions.csv"})
    if filename == "review_queue.csv": return Response(csv_bytes([r for r in rows if r.review_required]), media_type="text/csv", headers={"Content-Disposition":"attachment; filename=review_queue.csv"})
    if filename == "vat_schedule.csv":
        target = job_dir / filename; write_vat_schedule(target, rows); return Response(target.read_bytes(), media_type="text/csv", headers={"Content-Disposition":"attachment; filename=vat_schedule.csv"})
    if filename == "management_report.html":
        target = job_dir / filename; write_management_report(target, job.client, rows); return Response(target.read_bytes(), media_type="text/html", headers={"Content-Disposition":"attachment; filename=management_report.html"})
    raise HTTPException(404, "File not found")


@app.get("/api/jobs/{job_id}")
def api_job(job_id: str, _: str = Depends(auth), session: Session = Depends(db)) -> dict:
    job = session.get(Job, job_id)
    if not job: raise HTTPException(404, "Job not found")
    return {"id":job.id,"client":job.client,"bank":job.bank,"transaction_count":len(txs(job)),"transactions":[asdict(x) for x in txs(job)]}


def main() -> None:
    import uvicorn
    uvicorn.run("pibg.web:app", host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", "8000")), reload=False)


if __name__ == "__main__": main()
