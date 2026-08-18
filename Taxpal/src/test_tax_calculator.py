import unittest
from decimal import Decimal

from tax_calculator import (
    calculate_corporate_income_tax,
    calculate_individual_business_income,
    calculate_paye,
    calculate_percentage_tax,
    calculate_rental_income,
    calculate_vat,
    calculate_withholding_tax,
    parse_statutory_tax_request,
    parse_percentage_tax_request,
    parse_vat_request,
)
from tax_rules import available_tax_years, load_tax_rules


class VatCalculatorTests(unittest.TestCase):
    def test_exclusive_standard_rate(self):
        result = calculate_vat("1000000")
        self.assertEqual(result["net_amount"], "1000000.00")
        self.assertEqual(result["vat_amount"], "180000.00")
        self.assertEqual(result["gross_amount"], "1180000.00")

    def test_inclusive_standard_rate(self):
        result = calculate_vat("590000", inclusive=True)
        self.assertEqual(result["net_amount"], "500000.00")
        self.assertEqual(result["vat_amount"], "90000.00")
        self.assertEqual(result["gross_amount"], "590000.00")

    def test_parser_ignores_percentage_as_amount(self):
        result = parse_vat_request("Calculate VAT on UGX 200,000 at 16%")
        self.assertIsNotNone(result)
        self.assertEqual(result["input_amount"], "200000.00")
        self.assertEqual(result["rate"], "16")

    def test_rejects_negative_amount(self):
        with self.assertRaises(ValueError):
            calculate_vat(Decimal("-1"))

    def test_non_calculation_is_not_routed(self):
        self.assertIsNone(parse_vat_request("What does VAT mean?"))

    def test_standard_vat_rate_fact_works_without_retrieval(self):
        result = parse_vat_request("What is the standard VAT rate in Uganda?")
        self.assertEqual(result["kind"], "vat_rate_fact")
        self.assertEqual(result["rate"], "18")
        self.assertEqual(result["tax_year"], "2026/27")

    def test_custom_percentage_calculation(self):
        result = calculate_percentage_tax("500000", "6", "Withholding tax")
        self.assertEqual(result["tax_amount"], "30000.00")
        self.assertNotIn("total_amount", result)
        self.assertEqual(result["source"], "User-specified rate")

    def test_custom_percentage_parser_requires_explicit_rate(self):
        with self.assertRaisesRegex(ValueError, "will not guess"):
            parse_percentage_tax_request(
                "Calculate withholding tax on UGX 500,000"
            )

    def test_custom_percentage_parser(self):
        result = parse_percentage_tax_request(
            "Calculate 6% withholding tax on UGX 500,000"
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["tax_amount"], "30000.00")

    def test_resident_paye_brackets_and_surcharge(self):
        self.assertEqual(calculate_paye("235000")["tax_amount"], "0.00")
        self.assertEqual(calculate_paye("335000")["tax_amount"], "10000.00")
        self.assertEqual(calculate_paye("410000")["tax_amount"], "25000.00")
        self.assertEqual(calculate_paye("11000000")["tax_amount"], "3302000.00")

    def test_non_resident_paye(self):
        self.assertEqual(calculate_paye("335000", resident=False)["tax_amount"], "33500.00")
        self.assertEqual(calculate_paye("410000", resident=False)["tax_amount"], "48500.00")

    def test_individual_business_income_uses_annual_bands(self):
        self.assertEqual(calculate_individual_business_income("2820000")["tax_amount"], "0.00")
        self.assertEqual(calculate_individual_business_income("4920000")["tax_amount"], "300000.00")

    def test_rental_income_variants(self):
        individual = calculate_rental_income("6000000", "resident individual")
        self.assertEqual(individual["tax_amount"], "381600.00")
        company = calculate_rental_income("10000000", "company", "8000000")
        self.assertEqual(company["allowed_expenses"], "5000000.00")
        self.assertEqual(company["tax_amount"], "1500000.00")
        nonresident = calculate_rental_income("10000000", "non-resident individual")
        self.assertEqual(nonresident["tax_amount"], "1500000.00")

    def test_corporate_income_tax(self):
        self.assertEqual(calculate_corporate_income_tax("10000000")["tax_amount"], "3000000.00")

    def test_verified_withholding_categories(self):
        result = calculate_withholding_tax("2000000", "resident goods/services above UGX 1m")
        self.assertEqual(result["tax_amount"], "120000.00")
        self.assertEqual(result["net_amount"], "1880000.00")
        with self.assertRaisesRegex(ValueError, "exceeds"):
            calculate_withholding_tax("1000000", "rent above UGX 1m")

    def test_statutory_prompt_parser(self):
        result = parse_statutory_tax_request(
            "Calculate PAYE for Non-resident on monthly chargeable income UGX 410,000"
        )
        self.assertFalse(result["resident"])
        self.assertEqual(result["tax_amount"], "48500.00")

    def test_rule_packs_are_versioned_and_effective_dated(self):
        self.assertEqual(available_tax_years(), ["2026/27", "2025/26"])
        rules = load_tax_rules("2026/27")
        self.assertEqual(rules["version"], "UG-2026-27-v1")
        self.assertEqual(rules["effective_from"], "2026-07-01")
        self.assertEqual(rules["effective_to"], "2027-06-30")

    def test_calculation_records_rule_provenance(self):
        result = calculate_paye("1000000", tax_year="2025/26")
        self.assertEqual(result["tax_year"], "2025/26")
        self.assertEqual(result["rule_version"], "UG-2025-26-v1")
        self.assertEqual(result["tax_amount"], "202000.00")

    def test_typed_request_selects_tax_year(self):
        result = parse_statutory_tax_request(
            "Calculate PAYE for resident on monthly chargeable income UGX 1,000,000 for tax year 2025/26"
        )
        self.assertEqual(result["tax_year"], "2025/26")

    def test_unsupported_tax_year_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unsupported tax year"):
            calculate_paye("1000000", tax_year="2024/25")


if __name__ == "__main__":
    unittest.main()
