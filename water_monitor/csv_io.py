"""CSV loading and writing helpers for the water monitor CLI."""

from __future__ import annotations

import csv
from pathlib import Path

from .algorithms import DetectionResult, SENSOR_COLUMNS

REQUIRED_COLUMNS = ("timestamp", *SENSOR_COLUMNS)
OPTIONAL_COLUMNS = ("temperature", "label", "notes")
RESULT_COLUMNS = (
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
)


def read_sensor_csv(path: Path) -> tuple[list[dict[str, str]], list[dict[str, float]]]:
    """Read a CSV and return original rows plus numeric sensor-only rows."""

    with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        if reader.fieldnames is None:
            raise ValueError(f"{path} is empty or missing a header row")

        missing = [column for column in REQUIRED_COLUMNS if column not in reader.fieldnames]
        if missing:
            raise ValueError(
                f"{path} is missing required column(s): {', '.join(missing)}"
            )

        original_rows: list[dict[str, str]] = []
        numeric_rows: list[dict[str, float]] = []
        for line_number, row in enumerate(reader, start=2):
            original_rows.append(dict(row))
            numeric_rows.append(_parse_sensor_values(row, path, line_number))

    if not original_rows:
        raise ValueError(f"{path} must contain at least one data row")

    return original_rows, numeric_rows


def write_detection_csv(
    path: Path,
    original_rows: list[dict[str, str]],
    results: list[DetectionResult],
) -> None:
    """Write original input columns plus detection result columns."""

    if len(original_rows) != len(results):
        raise ValueError("original row count and result count differ")

    input_columns = list(original_rows[0].keys()) if original_rows else list(REQUIRED_COLUMNS)
    fieldnames = [*input_columns, *RESULT_COLUMNS]

    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()

        for original, result in zip(original_rows, results):
            output = dict(original)
            output.update(
                {
                    "n_turbidity": _format_number(result.normalized["turbidity"]),
                    "n_orp": _format_number(result.normalized["orp"]),
                    "n_ph": _format_number(result.normalized["ph"]),
                    "n_conductivity": _format_number(result.normalized["conductivity"]),
                    "vda_distance": _format_number(result.vda_distance),
                    "vda_alarm": str(result.vda_alarm).lower(),
                    "paa_area_ratio": _format_number(result.paa_area_ratio),
                    "paa_alarm": str(result.paa_alarm).lower(),
                    "final_alarm": str(result.final_alarm).lower(),
                    "alert_status": "ALERT" if result.final_alarm else "NO_ALERT",
                    "reason": result.reason,
                    "alert_message": _alert_message(original, result),
                }
            )
            writer.writerow(output)


def _parse_sensor_values(
    row: dict[str, str],
    path: Path,
    line_number: int,
) -> dict[str, float]:
    parsed: dict[str, float] = {}
    for sensor in SENSOR_COLUMNS:
        raw_value = row.get(sensor, "")
        try:
            parsed[sensor] = float(raw_value)
        except ValueError as exc:
            raise ValueError(
                f"{path}:{line_number} has invalid numeric value "
                f"for {sensor!r}: {raw_value!r}"
            ) from exc
    return parsed


def _format_number(value: float) -> str:
    return f"{value:.6f}"


def _alert_message(original: dict[str, str], result: DetectionResult) -> str:
    if not result.final_alarm:
        return "NO_ALERT: readings are within learned clean-water limits"

    sensor_values = ", ".join(
        f"{sensor}={original.get(sensor, '')}" for sensor in SENSOR_COLUMNS
    )
    return f"ALERT: {result.reason} warning; {sensor_values}"
