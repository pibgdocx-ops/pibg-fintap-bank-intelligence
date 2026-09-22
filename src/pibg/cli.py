from __future__ import annotations

import argparse
from pathlib import Path

from .parser import parse_statement
from .reporting import write_csv, write_management_report, write_vat_schedule


def pdfs(items: list[str]) -> list[Path]:
    files: list[Path] = []
    for item in items:
        path = Path(item)
        files.extend(sorted(path.glob("*.pdf")) if path.is_dir() else [path])
    return [file for file in files if file.suffix.lower() == ".pdf"]


def main() -> None:
    parser = argparse.ArgumentParser(description="PIBG bank statement classifier MVP")
    parser.add_argument("--input", nargs="+", required=True, help="PDF file(s) or folder(s)")
    parser.add_argument("--client", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output); output.mkdir(parents=True, exist_ok=True)
    transactions = []
    unsupported = []
    for path in pdfs(args.input):
        bank, parsed = parse_statement(path)
        if not parsed:
            unsupported.append(f"{path.name} ({bank})")
        transactions.extend(parsed)
    write_csv(output / "transactions.csv", transactions)
    write_csv(output / "review_queue.csv", [row for row in transactions if row.review_required])
    write_vat_schedule(output / "vat_schedule.csv", transactions)
    write_management_report(output / "management_report.html", args.client, transactions)
    print(f"Created {len(transactions)} transactions in {output}")
    if unsupported:
        print("Detected but awaiting line-level parser: " + ", ".join(unsupported))


if __name__ == "__main__":
    main()
