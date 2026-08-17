import unittest

from calculator_intent import is_calculation_request


class CalculatorIntentTests(unittest.TestCase):

    def test_vat_calculation(self):
        self.assertTrue(
            is_calculation_request(
                "Calculate VAT on 1,000,000"
            )
        )

    def test_tax_calculation(self):
        self.assertTrue(
            is_calculation_request(
                "How much tax is payable on 500000?"
            )
        )

    def test_percentage_calculation(self):
        self.assertTrue(
            is_calculation_request(
                "Calculate 18% tax"
            )
        )

    def test_general_tax_question(self):
        self.assertFalse(
            is_calculation_request(
                "What is VAT?"
            )
        )

    def test_general_explanation(self):
        self.assertFalse(
            is_calculation_request(
                "Explain withholding tax"
            )
        )


if __name__ == "__main__":
    unittest.main()