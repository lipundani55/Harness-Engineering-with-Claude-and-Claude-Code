import math
import unittest

from demosrc.bmi import bmi_category, calculate_bmi


class BmiTests(unittest.TestCase):
    def test_calculates_bmi(self):
        self.assertAlmostEqual(calculate_bmi(70, 1.75), 22.857142857)

    def test_rejects_invalid_measurements(self):
        for value in (0, -1, math.inf, -math.inf, math.nan):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    calculate_bmi(value, 1.75)
                with self.assertRaises(ValueError):
                    calculate_bmi(70, value)

    def test_rejects_out_of_range_result(self):
        with self.assertRaises(ValueError):
            calculate_bmi(70, 1e-320)

    def test_categories_at_boundaries(self):
        cases = (
            (18.49, "Underweight"),
            (18.5, "Healthy weight"),
            (24.99, "Healthy weight"),
            (25, "Overweight"),
            (29.99, "Overweight"),
            (30, "Obesity"),
        )
        for bmi, expected in cases:
            with self.subTest(bmi=bmi):
                self.assertEqual(bmi_category(bmi), expected)

    def test_rejects_invalid_bmi(self):
        for bmi in (0, -1, math.inf, math.nan):
            with self.subTest(bmi=bmi):
                with self.assertRaises(ValueError):
                    bmi_category(bmi)


if __name__ == "__main__":
    unittest.main()