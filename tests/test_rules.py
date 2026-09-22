import unittest
from decimal import Decimal

from pibg.rules import classify


class ClassificationTests(unittest.TestCase):
    def test_truck_repair_is_vat_inclusive_review_item(self):
        row = classify(date="17 Jun", bank="FNB", account="123", description="FNB App Payment To Truck Repairs Yanga", amount=Decimal("1200.00"), direction="Money Out")
        self.assertEqual(row.accounting_category, "Repairs & Maintenance")
        self.assertEqual(row.vat_amount, Decimal("156.52"))
        self.assertTrue(row.vat_inclusive)
        self.assertTrue(row.review_required)

    def test_income_is_not_automatically_final_revenue(self):
        row = classify(date="17 Jun", bank="FNB", account="123", description="Payment From customer", amount=Decimal("5000"), direction="Money In")
        self.assertEqual(row.accounting_category, "Revenue")
        self.assertTrue(row.review_required)

    def test_debit_interest_is_not_income(self):
        row = classify(date="06 Aug", bank="FNB", account="123", description="Int On Debit Balance", amount=Decimal("3235.84"), direction="Money Out")
        self.assertEqual(row.accounting_category, "Finance Costs")
        self.assertNotEqual(row.accounting_type, "Income")


if __name__ == "__main__":
    unittest.main()
