from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal


@dataclass
class Transaction:
    date: str
    bank: str
    account: str
    description: str
    amount: Decimal
    direction: str
    counterparty: str
    accounting_category: str
    accounting_type: str
    vat_treatment: str
    vat_rate: Decimal
    vat_amount: Decimal
    vat_inclusive: bool
    input_vat_claim_status: str
    vat201_field: str
    management_report_category: str
    capital_or_revenue: str
    supporting_document_required: str
    supporting_document_status: str
    confidence: int
    review_required: bool
    reason: str
    rule_source: str
    accountant_approved: bool = False

    def csv_row(self) -> dict[str, str]:
        values = asdict(self)
        return {
            key: (f"{value:.2f}" if isinstance(value, Decimal) else str(value))
            for key, value in values.items()
        }
