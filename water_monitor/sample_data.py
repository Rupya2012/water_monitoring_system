"""Generate deterministic sample CSV files for demos and tests."""

from __future__ import annotations

import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

HEADER = ("timestamp", "turbidity", "orp", "ph", "conductivity", "label", "notes")


def generate_sample_files(
    baseline_path: Path,
    input_path: Path,
    *,
    seed: int = 7,
    baseline_rows: int = 60,
    input_rows: int = 120,
) -> None:
    """Create clean baseline data and mixed clean/contaminated input data."""

    if baseline_rows < 5:
        raise ValueError("baseline_rows must be at least 5")
    if input_rows < 20:
        raise ValueError("input_rows must be at least 20")

    random_generator = random.Random(seed)
    start = datetime(2026, 1, 1, 9, 0, 0)

    with baseline_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=HEADER)
        writer.writeheader()
        for index in range(baseline_rows):
            writer.writerow(
                _clean_row(
                    random_generator,
                    start + timedelta(seconds=5 * index),
                    label="clean",
                    notes="baseline clean water",
                )
            )

    with input_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=HEADER)
        writer.writeheader()
        for index in range(input_rows):
            timestamp = start + timedelta(minutes=10, seconds=5 * index)
            if input_rows // 3 <= index < input_rows // 3 + 15:
                writer.writerow(_bacteria_like_row(random_generator, timestamp))
            elif (2 * input_rows) // 3 <= index < (2 * input_rows) // 3 + 15:
                writer.writerow(_arsenic_like_row(random_generator, timestamp))
            else:
                writer.writerow(
                    _clean_row(
                        random_generator,
                        timestamp,
                        label="clean",
                        notes="normal operation",
                        noise_scale=0.45,
                    )
                )


def _clean_row(
    random_generator: random.Random,
    timestamp: datetime,
    *,
    label: str,
    notes: str,
    noise_scale: float = 1.0,
) -> dict[str, str]:
    return _format_row(
        timestamp=timestamp,
        turbidity=random_generator.gauss(0.45, 0.04 * noise_scale),
        orp=random_generator.gauss(655, 8 * noise_scale),
        ph=random_generator.gauss(7.25, 0.04 * noise_scale),
        conductivity=random_generator.gauss(410, 9 * noise_scale),
        label=label,
        notes=notes,
    )


def _bacteria_like_row(
    random_generator: random.Random,
    timestamp: datetime,
) -> dict[str, str]:
    return _format_row(
        timestamp=timestamp,
        turbidity=random_generator.gauss(1.4, 0.12),
        orp=random_generator.gauss(615, 10),
        ph=random_generator.gauss(7.16, 0.05),
        conductivity=random_generator.gauss(470, 14),
        label="contaminated",
        notes="simulated microbiological event",
    )


def _arsenic_like_row(
    random_generator: random.Random,
    timestamp: datetime,
) -> dict[str, str]:
    return _format_row(
        timestamp=timestamp,
        turbidity=random_generator.gauss(0.75, 0.08),
        orp=random_generator.gauss(585, 14),
        ph=random_generator.gauss(7.05, 0.05),
        conductivity=random_generator.gauss(540, 20),
        label="contaminated",
        notes="simulated heavy-metal event",
    )


def _format_row(
    *,
    timestamp: datetime,
    turbidity: float,
    orp: float,
    ph: float,
    conductivity: float,
    label: str,
    notes: str,
) -> dict[str, str]:
    return {
        "timestamp": timestamp.isoformat(),
        "turbidity": f"{max(turbidity, 0.0):.3f}",
        "orp": f"{orp:.3f}",
        "ph": f"{ph:.3f}",
        "conductivity": f"{max(conductivity, 0.0):.3f}",
        "label": label,
        "notes": notes,
    }
