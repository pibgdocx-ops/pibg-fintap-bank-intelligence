from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

from pypdf import PdfReader

from .rules import classify


def detect_bank(text: str) -> str:
    upper = text.upper()
    for marker, bank in [("FNB", "FNB"), ("CAPITEC", "Capitec"), ("NEDBANK", "Nedbank"), ("STANDARD BANK", "Standard Bank"), ("ABSA", "ABSA")]:
        if marker in upper:
            return bank
    return "Unknown"


def _amount(value: str) -> Decimal:
    return Decimal(value.replace(",", ""))


def extract_text(path: Path) -> str:
    return "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)


def _account(text: str) -> str:
    match = re.search(r"(?:Account\s*:\s*[^\n]*?)(\d{8,})", text, re.I)
    if not match:
        match = re.search(r"Account Number\s+\w+\s+(\d{8,})", text, re.I)
    return match.group(1) if match else ""


def parse_fnb(text: str) -> list:
    """Parse the transaction row layout seen in PIBG's FNB samples."""
    account = _account(text)
    transactions = []
    row = re.compile(
        r"(?m)^(\d{2}\s+[A-Z][a-z]{2})\s+(.+?)\s+([\d,]+\.\d{2})(Cr)?\s+([\d,]+\.\d{2})"
    )
    for match in row.finditer(text):
        date, description, amount, credit, _balance = match.groups()
        if description.lower().startswith(("opening balance", "closing balance")):
            continue
        # FNB prints charge-only values in the same visual columns as transactions.
        # A genuine transaction narration must contain at least one letter.
        if not re.search(r"[A-Za-z]", description):
            continue
        direction = "Money In" if credit else "Money Out"
        transactions.append(classify(date=date, bank="FNB", account=account, description=description.strip(), amount=_amount(amount), direction=direction))
    return transactions


def parse_statement(path: Path) -> tuple[str, list]:
    text = extract_text(path)
    bank = detect_bank(text)
    if bank == "FNB":
        return bank, parse_fnb(text)
    return bank, []
