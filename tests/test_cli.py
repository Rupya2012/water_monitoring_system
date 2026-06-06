import csv
import tempfile
import unittest
from pathlib import Path

from water_monitor.__main__ import main


class CliTests(unittest.TestCase):
    def test_generate_sample_then_detect_writes_expected_columns(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            baseline = temp_path / "baseline_clean.csv"
            input_file = temp_path / "input_sensor_data.csv"
            output = temp_path / "detection_results.csv"
            pdf_output = temp_path / "detection_report.pdf"

            main(
                [
                    "generate-sample",
                    "--baseline",
                    str(baseline),
                    "--input",
                    str(input_file),
                    "--baseline-rows",
                    "20",
                    "--input-rows",
                    "50",
                ]
            )
            main(
                [
                    "detect",
                    "--baseline",
                    str(baseline),
                    "--input",
                    str(input_file),
                    "--output",
                    str(output),
                    "--pdf-output",
                    str(pdf_output),
                ]
            )

            with output.open("r", encoding="utf-8", newline="") as csv_file:
                reader = csv.DictReader(csv_file)
                rows = list(reader)

            self.assertEqual(len(rows), 50)
            for column in (
                "n_turbidity",
                "n_orp",
                "n_ph",
                "n_conductivity",
                "vda_distance",
                "vda_alarm",
                "paa_area_ratio",
                "paa_alarm",
                "final_alarm",
                "alert_status",
                "reason",
                "alert_message",
            ):
                self.assertIn(column, reader.fieldnames)
            self.assertGreater(
                sum(row["final_alarm"] == "true" for row in rows),
                0,
            )
            self.assertIn("ALERT", {row["alert_status"] for row in rows})
            self.assertTrue(pdf_output.exists())
            self.assertGreater(pdf_output.stat().st_size, 1000)


if __name__ == "__main__":
    unittest.main()
