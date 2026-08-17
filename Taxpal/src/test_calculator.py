import unittest

from calculator import (
    calculate_percentage,
    calculate_total_with_percentage,
)


class CalculatorTests(unittest.TestCase):

    def test_percentage(self):
        result = calculate_percentage(
            1_000_000,
            18,
        )

        self.assertEqual(
            result,
            180_000,
        )

    def test_total_with_percentage(self):
        percentage_amount, total = calculate_total_with_percentage(
            1_000_000,
            18,
        )

        self.assertEqual(
            percentage_amount,
            180_000,
        )

        self.assertEqual(
            total,
            1_180_000,
        )

    def test_zero_percentage(self):
        result = calculate_percentage(
            1_000_000,
            0,
        )

        self.assertEqual(
            result,
            0,
        )

    def test_negative_amount_rejected(self):
        with self.assertRaises(ValueError):
            calculate_percentage(
                -1_000_000,
                18,
            )

    def test_negative_percentage_rejected(self):
        with self.assertRaises(ValueError):
            calculate_percentage(
                1_000_000,
                -18,
            )


if __name__ == "__main__":
    unittest.main()