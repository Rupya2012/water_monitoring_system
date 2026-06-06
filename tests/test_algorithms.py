import unittest

from water_monitor.algorithms import (
    calibrate,
    detect_row,
    normalize_row,
    polygon_area_ratio,
)


class AlgorithmTests(unittest.TestCase):
    def test_normalize_row_uses_absolute_distance_from_baseline(self):
        row = {"turbidity": 3.0, "orp": 90.0, "ph": 7.5, "conductivity": 120.0}
        means = {"turbidity": 1.0, "orp": 100.0, "ph": 7.0, "conductivity": 100.0}
        stds = {"turbidity": 2.0, "orp": 5.0, "ph": 0.5, "conductivity": 10.0}

        normalized = normalize_row(row, means, stds)

        self.assertEqual(normalized["turbidity"], 1.0)
        self.assertEqual(normalized["orp"], 2.0)
        self.assertEqual(normalized["ph"], 1.0)
        self.assertEqual(normalized["conductivity"], 2.0)

    def test_polygon_area_ratio_for_unit_vector_is_one(self):
        normalized = {
            "turbidity": 1.0,
            "orp": 1.0,
            "ph": 1.0,
            "conductivity": 1.0,
        }

        self.assertEqual(polygon_area_ratio(normalized), 1.0)

    def test_vda_stays_quiet_on_clean_data_and_flags_large_change(self):
        baseline = [
            {"turbidity": 0.45, "orp": 650.0, "ph": 7.20, "conductivity": 400.0},
            {"turbidity": 0.50, "orp": 653.0, "ph": 7.24, "conductivity": 405.0},
            {"turbidity": 0.40, "orp": 647.0, "ph": 7.18, "conductivity": 395.0},
            {"turbidity": 0.46, "orp": 651.0, "ph": 7.21, "conductivity": 402.0},
        ]
        calibration = calibrate(baseline)

        clean_result = detect_row(
            {"turbidity": 0.47, "orp": 652.0, "ph": 7.22, "conductivity": 403.0},
            calibration,
        )
        contaminated_result = detect_row(
            {"turbidity": 1.60, "orp": 610.0, "ph": 7.02, "conductivity": 500.0},
            calibration,
        )

        self.assertFalse(clean_result.final_alarm)
        self.assertTrue(contaminated_result.vda_alarm)
        self.assertTrue(contaminated_result.final_alarm)


if __name__ == "__main__":
    unittest.main()
