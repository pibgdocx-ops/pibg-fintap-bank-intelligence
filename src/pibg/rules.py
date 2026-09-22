from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from .models import Transaction

VAT_RATE = Decimal("0.15")


def _vat_part(amount: Decimal) -> Decimal:
    return (amount * VAT_RATE / (Decimal("1") + VAT_RATE)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


RULES = [
    ("truck repair", "Repairs & Maintenance", "Operating Expense", "STANDARD_RATED", "CLAIMABLE_IF_DOCUMENTATION", "15", "Revenue expenditure", "Tax invoice", "Truck repair appears to be a taxable business service."),
    ("repairs", "Repairs & Maintenance", "Operating Expense", "STANDARD_RATED", "CLAIMABLE_IF_DOCUMENTATION", "15", "Revenue expenditure", "Tax invoice", "Repair appears to be a taxable business expense."),
    ("tyre", "Motor Vehicle Expenses", "Operating Expense", "STANDARD_RATED", "CLAIMABLE_IF_DOCUMENTATION", "15", "Revenue expenditure", "Tax invoice", "Vehicle tyre expense requires a valid tax invoice."),
    ("diesel", "Fuel & Oils", "Operating Expense", "ZERO_RATED", "NOT_APPLICABLE", "2", "Revenue expenditure", "No", "Diesel/petrol fuel-levy goods are treated as zero-rated."),
    ("fuel", "Fuel & Oils", "Operating Expense", "ZERO_RATED", "NOT_APPLICABLE", "2", "Revenue expenditure", "No", "Fuel requires sector and product confirmation; default is zero-rated review."),
    ("accountant", "Accounting Fees", "Operating Expense", "STANDARD_RATED", "CLAIMABLE_IF_DOCUMENTATION", "15", "Revenue expenditure", "Tax invoice", "Professional accounting service requires a tax invoice."),
    ("consult", "Consulting & Professional Fees", "Operating Expense", "STANDARD_RATED", "CLAIMABLE_IF_DOCUMENTATION", "15", "Revenue expenditure", "Tax invoice", "Professional service requires a tax invoice."),
    ("insurance", "Insurance", "Operating Expense", "STANDARD_RATED", "CLAIMABLE_IF_DOCUMENTATION", "15", "Revenue expenditure", "Tax invoice", "Insurance treatment requires the policy invoice."),
    ("outsurance", "Insurance", "Operating Expense", "STANDARD_RATED", "CLAIMABLE_IF_DOCUMENTATION", "15", "Revenue expenditure", "Tax invoice", "Insurance treatment requires the policy invoice."),
    ("electricity", "Utilities", "Operating Expense", "STANDARD_RATED", "CLAIMABLE_IF_DOCUMENTATION", "15", "Revenue expenditure", "Tax invoice", "Utility expense requires supplier tax invoice."),
    ("water", "Utilities", "Operating Expense", "STANDARD_RATED", "CLAIMABLE_IF_DOCUMENTATION", "15", "Revenue expenditure", "Tax invoice", "Utility expense requires supplier tax invoice."),
    ("ppe", "Company Uniforms", "Operating Expense", "STANDARD_RATED", "CLAIMABLE_IF_DOCUMENTATION", "15", "Revenue expenditure", "Tax invoice", "PPE appears to be business uniforms/safety equipment."),
    ("uniform", "Company Uniforms", "Operating Expense", "STANDARD_RATED", "CLAIMABLE_IF_DOCUMENTATION", "15", "Revenue expenditure", "Tax invoice", "Uniform purchase requires a valid tax invoice."),
    ("registration", "Compliance fees ( SARS / Labour & other)", "Operating Expense", "NON_SUPPLY / OUT_OF_SCOPE", "NOT_APPLICABLE", "3", "Revenue expenditure", "No", "Vehicle/permit registration is not assumed to carry claimable VAT."),
    ("permit", "Compliance fees ( SARS / Labour & other)", "Operating Expense", "NON_SUPPLY / OUT_OF_SCOPE", "NOT_APPLICABLE", "3", "Revenue expenditure", "No", "Permit payment is not assumed to carry claimable VAT."),
    ("bank charge", "Bank Charges", "Operating Expense", "STANDARD_RATED", "CLAIMABLE", "15", "Revenue expenditure", "Bank statement", "Bank statement provides the bank-charge evidence."),
    ("monthly fee", "Bank Charges", "Operating Expense", "STANDARD_RATED", "CLAIMABLE", "15", "Revenue expenditure", "Bank statement", "Bank statement provides the bank-charge evidence."),
    ("interest", "Interest & Other income", "Other Income", "EXEMPT", "NOT_APPLICABLE", "3", "Revenue", "No", "Interest is treated as an exempt financial service."),
    ("loan repayment", "Loan Repayments", "Liability", "NON_SUPPLY / OUT_OF_SCOPE", "NOT_APPLICABLE", "3", "Capital", "Loan schedule", "Loan principal is a balance-sheet movement."),
    ("wesbank", "Asset Finance Repayment", "Liability", "NON_SUPPLY / OUT_OF_SCOPE", "NOT_APPLICABLE", "3", "Capital", "Finance statement", "Asset-finance payment must be split between principal, interest and fees."),
    ("asset acquisition", "Asset Acquisition", "Asset", "STANDARD_RATED", "CLAIMABLE_IF_DOCUMENTATION", "14", "Capital", "Tax invoice", "Asset purchase is posted as capital goods/services."),
    ("sars", "Compliance fees ( SARS / Labour & other)", "Tax", "NON_SUPPLY / OUT_OF_SCOPE", "NOT_APPLICABLE", "3", "Revenue expenditure", "SARS assessment", "Tax payment is not an operating expense or revenue."),
]


def classify(*, date: str, bank: str, account: str, description: str, amount: Decimal, direction: str) -> Transaction:
    text = description.lower()
    counterparty = description
    if direction == "Money In":
        return Transaction(date, bank, account, description, amount, direction, counterparty,
            "Revenue", "Income", "UNKNOWN / REVIEW", Decimal("0"), Decimal("0"), True,
            "REVIEW_REQUIRED", "1", "Revenue", "Revenue", "Tax invoice", "Missing", 55, True,
            "Incoming receipt may be revenue, a refund, loan proceeds, or an inter-account transfer.", "AI / review")
    if "interest" in text or "int on debit" in text:
        return Transaction(date, bank, account, description, amount, direction, counterparty,
            "Finance Costs", "Operating Expense", "EXEMPT", Decimal("0"), Decimal("0"), True,
            "NOT_APPLICABLE", "3", "Finance Costs", "Revenue expenditure", "Bank statement", "Available", 80, True,
            "Debit interest is a finance cost; the accountant should confirm the final management-report treatment.", "Narration rule")
    for needle, category, accounting_type, vat, claim, field, capital, document, reason in RULES:
        if needle in text:
            rate = VAT_RATE if vat == "STANDARD_RATED" else Decimal("0")
            review = claim == "CLAIMABLE_IF_DOCUMENTATION" or "fuel" in needle or "wesbank" in needle
            return Transaction(date, bank, account, description, amount, direction, counterparty,
                category, accounting_type, vat, rate, _vat_part(amount) if rate else Decimal("0"), True,
                claim, field, category, capital, document,
                "Missing" if document not in ("No", "Bank statement") else "Available", 88 if not review else 72,
                review, reason, "Vendor / keyword rule")
    return Transaction(date, bank, account, description, amount, direction, counterparty,
        "Unclassified", "Review", "UNKNOWN / REVIEW", Decimal("0"), Decimal("0"), True,
        "REVIEW_REQUIRED", "", "Unclassified", "", "Tax invoice", "Missing", 35, True,
        "No approved PIBG vendor or narration rule matched this payment.", "AI / review")
