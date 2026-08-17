import unittest

from calculation_parser import parse_calculation_request


class CalculationParserTests(unittest.TestCase):

    def test_vat_request(self):
        result = parse_calculation_request(
            "Calculate 18% VAT on UGX 1,000,000"
        )

        self.assertEqual(result.amount, 1_000_000)
        self.assertEqual(result.percentage, 18)
        self.assertEqual(result.tax_type, "vat")

    def test_percentage_without_currency(self):
        result = parse_calculation_request(
            "Calculate 10% tax on 500000"
        )

        self.assertEqual(result.amount, 500_000)
        self.assertEqual(result.percentage, 10)

    def test_no_percentage(self):
        result = parse_calculation_request(
            "Calculate VAT on UGX 1,000,000"
        )

        self.assertEqual(result.amount, 1_000_000)
        self.assertIsNone(result.percentage)
        self.assertEqual(result.tax_type, "vat")

    def test_rental_tax(self):
        result = parse_calculation_request(
            "Calculate rental income tax on 2,000,000"
        )

        self.assertEqual(result.amount, 2_000_000)
        self.assertEqual(result.tax_type, "rental_income")


if __name__ == "__main__":
    unittest.main()