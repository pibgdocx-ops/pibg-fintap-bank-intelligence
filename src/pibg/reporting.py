from __future__ import annotations

import csv
from collections import defaultdict
from decimal import Decimal
from html import escape
from pathlib import Path

from .models import Transaction


def money(value: Decimal) -> str:
    return f"R {value:,.2f}"


def write_csv(path: Path, rows: list[Transaction]) -> None:
    fields = list(rows[0].csv_row()) if rows else list(Transaction.__annotations__)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(row.csv_row() for row in rows)


def write_vat_schedule(path: Path, rows: list[Transaction]) -> None:
    groups: dict[tuple[str, str], list[Decimal]] = defaultdict(lambda: [Decimal("0"), Decimal("0")])
    for row in rows:
        kind = "Output VAT" if row.direction == "Money In" else "Input VAT"
        groups[(kind, row.vat201_field or "Review")][0] += row.amount
        if row.input_vat_claim_status in ("CLAIMABLE", "CLAIMABLE_IF_DOCUMENTATION") and row.vat_treatment == "STANDARD_RATED":
            groups[(kind, row.vat201_field or "Review")][1] += row.vat_amount
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["Schedule", "VAT201 field", "VAT-inclusive amount", "Preliminary VAT", "Status"])
        for (kind, field), (inclusive, vat) in sorted(groups.items()):
            writer.writerow([kind, field, f"{inclusive:.2f}", f"{vat:.2f}", "Accountant review required where documentation is missing"])


def write_management_report(path: Path, client: str, rows: list[Transaction]) -> None:
    income = sum((r.amount for r in rows if r.accounting_type == "Income"), Decimal("0"))
    cogs = sum((r.amount for r in rows if r.accounting_category == "Cost Of Sales"), Decimal("0"))
    expenses: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for row in rows:
        if row.accounting_type == "Operating Expense":
            expenses[row.management_report_category] += row.amount
    total_expenses = sum(expenses.values(), Decimal("0"))
    net_profit = income - cogs - total_expenses
    lines = "".join(f"<tr><td>{escape(name)}</td><td>{money(value)}</td></tr>" for name, value in sorted(expenses.items()))
    path.write_text(f'''<!doctype html><html><head><meta charset="utf-8"><title>PIBG Management Report</title><style>
body{{font-family:Arial,sans-serif;margin:48px;color:#14333a}}header{{border-bottom:5px solid #00a99d;padding-bottom:16px}}.brand{{color:#008f87;font-size:36px;font-weight:800}}.tag{{color:#08756f}}table{{width:100%;border-collapse:collapse;margin-top:22px}}td,th{{padding:10px;border-bottom:1px solid #dbe6e5;text-align:left}}td:last-child{{text-align:right}}.total{{font-weight:700;background:#e9f7f5}}.notice{{background:#fff7dc;padding:14px;margin-top:25px}}</style></head><body>
<header><div class="brand">PIBG</div><div class="tag">Building financially intelligent businesses</div><h1>Management Report</h1><p>{escape(client)} | Values are VAT-inclusive</p></header>
<table><tr><th>Income statement</th><th>Amount</th></tr><tr><td>Revenue</td><td>{money(income)}</td></tr><tr><td>Cost of sales</td><td>{money(cogs)}</td></tr><tr><td>Operating expenses</td><td>{money(total_expenses)}</td></tr><tr class="total"><td>Net profit before tax</td><td>{money(net_profit)}</td></tr></table>
<h2>Operating expenses</h2><table><tr><th>Category</th><th>VAT-inclusive amount</th></tr>{lines}</table>
<p class="notice">Draft report. Transactions flagged for review must be approved by the accountant before finalisation.</p></body></html>''', encoding="utf-8")
