"""Core water contamination detection algorithms.

The algorithms are based on the VDA and PAA sensor-fusion methods described
in Lambrou et al., IEEE Sensors Journal, 2014.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from statistics import fmean, pstdev

SENSOR_COLUMNS = ("turbidity", "orp", "ph", "conductivity")
EPSILON = 1e-12


@dataclass(frozen=True)
class Calibration:
    """Clean-water calibration values learned from a baseline CSV."""

    means: dict[str, float]
    std_devs: dict[str, float]
    clean_vector: dict[str, float]
    vda_threshold: float
    vda_margin: float


@dataclass(frozen=True)
class DetectionResult:
    """Algorithm outputs for a single sensor reading."""

    normalized: dict[str, float]
    vda_distance: float
    vda_alarm: bool
    paa_area_ratio: float
    paa_alarm: bool
    final_alarm: bool
    reason: str


def calibrate(
    baseline_rows: list[dict[str, float]],
    *,
    vda_margin: float = 0.10,
    vda_threshold: float | None = None,
) -> Calibration:
    """Learn clean-water means, standard deviations, N0, and VDA threshold."""

    if not baseline_rows:
        raise ValueError("baseline CSV must contain at least one data row")
    if vda_margin < 0:
        raise ValueError("vda_margin must be zero or positive")

    means: dict[str, float] = {}
    std_devs: dict[str, float] = {}

    for sensor in SENSOR_COLUMNS:
        values = [row[sensor] for row in baseline_rows]
        means[sensor] = fmean(values)
        std = pstdev(values)
        std_devs[sensor] = std if std > EPSILON else EPSILON

    baseline_normalized = [normalize_row(row, means, std_devs) for row in baseline_rows]
    clean_vector = {
        sensor: fmean(row[sensor] for row in baseline_normalized)
        for sensor in SENSOR_COLUMNS
    }
    baseline_distances = [
        euclidean_distance(row, clean_vector) for row in baseline_normalized
    ]

    if vda_threshold is None:
        learned_threshold = max(baseline_distances, default=0.0) * (1.0 + vda_margin)
        if learned_threshold <= EPSILON:
            learned_threshold = EPSILON
    else:
        if vda_threshold <= 0:
            raise ValueError("vda_threshold must be greater than zero")
        learned_threshold = vda_threshold

    return Calibration(
        means=means,
        std_devs=std_devs,
        clean_vector=clean_vector,
        vda_threshold=learned_threshold,
        vda_margin=vda_margin,
    )


def normalize_row(
    row: dict[str, float],
    means: dict[str, float],
    std_devs: dict[str, float],
) -> dict[str, float]:
    """Normalize one row using N_i = abs(S_i - mean_i) / std_i."""

    return {
        sensor: abs(row[sensor] - means[sensor]) / std_devs[sensor]
        for sensor in SENSOR_COLUMNS
    }


def euclidean_distance(
    vector: dict[str, float],
    reference: dict[str, float],
) -> float:
    """Return Euclidean distance between two sensor vectors."""

    return sqrt(
        sum((vector[sensor] - reference[sensor]) ** 2 for sensor in SENSOR_COLUMNS)
    )


def polygon_area_ratio(normalized: dict[str, float]) -> float:
    """Return PAA area ratio A_N / A_1 for four equally spaced radar axes."""

    values = [normalized[sensor] for sensor in SENSOR_COLUMNS]
    adjacent_products = sum(
        values[index] * values[(index + 1) % len(values)]
        for index in range(len(values))
    )
    return adjacent_products / len(values)


def detect_row(row: dict[str, float], calibration: Calibration) -> DetectionResult:
    """Run VDA and PAA on one input reading."""

    normalized = normalize_row(row, calibration.means, calibration.std_devs)
    vda_distance = euclidean_distance(normalized, calibration.clean_vector)
    vda_alarm = vda_distance > calibration.vda_threshold
    paa_area = polygon_area_ratio(normalized)
    paa_alarm = paa_area > 1.0
    final_alarm = vda_alarm or paa_alarm

    reasons: list[str] = []
    if vda_alarm:
        reasons.append("VDA")
    if paa_alarm:
        reasons.append("PAA")

    return DetectionResult(
        normalized=normalized,
        vda_distance=vda_distance,
        vda_alarm=vda_alarm,
        paa_area_ratio=paa_area,
        paa_alarm=paa_alarm,
        final_alarm=final_alarm,
        reason="+".join(reasons) if reasons else "none",
    )
