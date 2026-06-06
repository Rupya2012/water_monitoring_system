"""Small dependency-free PDF report writer."""

from __future__ import annotations

from pathlib import Path
from textwrap import wrap

from .algorithms import Calibration, DetectionResult, SENSOR_COLUMNS

PAGE_WIDTH = 612
PAGE_HEIGHT = 792
LEFT_MARGIN = 48
TOP_Y = 746
LINE_HEIGHT = 14
MAX_LINE_CHARS = 95


def write_pdf_report(
    path: Path,
    *,
    baseline_path: Path,
    input_path: Path,
    output_path: Path,
    original_rows: list[dict[str, str]],
    results: list[DetectionResult],
    calibration: Calibration,
    max_alert_rows: int = 50,
) -> None:
    """Write a plain PDF report explaining columns and alert rows."""

    if max_alert_rows < 1:
        raise ValueError("max_alert_rows must be at least 1")

    lines = _build_report_lines(
        baseline_path=baseline_path,
        input_path=input_path,
        output_path=output_path,
        original_rows=original_rows,
        results=results,
        calibration=calibration,
        max_alert_rows=max_alert_rows,
    )
    _write_basic_pdf(path, lines)


def _build_report_lines(
    *,
    baseline_path: Path,
    input_path: Path,
    output_path: Path,
    original_rows: list[dict[str, str]],
    results: list[DetectionResult],
    calibration: Calibration,
    max_alert_rows: int,
) -> list[str]:
    alert_count = sum(result.final_alarm for result in results)
    vda_count = sum(result.vda_alarm for result in results)
    paa_count = sum(result.paa_alarm for result in results)

    lines = [
        "Water Contamination Detection Report",
        "",
        "Files",
        f"Baseline clean-water CSV: {baseline_path}",
        f"Input sensor CSV: {input_path}",
        f"Result CSV: {output_path}",
        "",
        "Input Columns",
        "timestamp: time of the sensor reading",
        "turbidity: cloudiness of water; sudden rise can indicate particles or microbes",
        "orp: oxidation-reduction potential; sudden change can indicate chemical/biological activity",
        "ph: acidity/alkalinity of water",
        "conductivity: dissolved-ion level; sudden rise can indicate dissolved contaminants",
        "temperature, label, notes: optional columns preserved if present",
        "",
        "Clean-Water Calibration",
    ]

    for sensor in SENSOR_COLUMNS:
        lines.append(
            f"{sensor}: mean={calibration.means[sensor]:.6f}, "
            f"std_dev={calibration.std_devs[sensor]:.6f}"
        )

    lines.extend(
        [
            f"VDA learned warning threshold: {calibration.vda_threshold:.6f}",
            "PAA warning threshold: area_ratio > 1.000000",
            "",
            "Summary",
            f"Rows analyzed: {len(results)}",
            f"Rows with ALERT: {alert_count}",
            f"Rows with NO_ALERT: {len(results) - alert_count}",
            f"VDA alerts: {vda_count}",
            f"PAA alerts: {paa_count}",
            "",
            "How To Read One Warning",
            "ALERT means at least one algorithm found the row unusual compared with clean water.",
            "VDA warning: combined normalized distance is above the learned threshold.",
            "PAA warning: radar/polygon area ratio is above 1.",
            "",
            f"Alert Rows (showing up to {max_alert_rows})",
        ]
    )

    alert_rows = [
        (index, row, result)
        for index, (row, result) in enumerate(zip(original_rows, results), start=1)
        if result.final_alarm
    ]

    if not alert_rows:
        lines.append("No alert rows found.")
        return lines

    for index, row, result in alert_rows[:max_alert_rows]:
        lines.extend(
            [
                "",
                f"Row {index} at {row.get('timestamp', '')}: ALERT ({result.reason})",
                (
                    "Values: "
                    f"turbidity={row.get('turbidity', '')}, "
                    f"orp={row.get('orp', '')}, "
                    f"ph={row.get('ph', '')}, "
                    f"conductivity={row.get('conductivity', '')}"
                ),
                (
                    "Normalized: "
                    f"turbidity={result.normalized['turbidity']:.3f}, "
                    f"orp={result.normalized['orp']:.3f}, "
                    f"ph={result.normalized['ph']:.3f}, "
                    f"conductivity={result.normalized['conductivity']:.3f}"
                ),
                (
                    f"Decision: VDA distance={result.vda_distance:.3f} "
                    f"(threshold={calibration.vda_threshold:.3f}, alarm={result.vda_alarm}); "
                    f"PAA area ratio={result.paa_area_ratio:.3f} "
                    f"(threshold=1.000, alarm={result.paa_alarm})"
                ),
            ]
        )

    hidden_count = len(alert_rows) - max_alert_rows
    if hidden_count > 0:
        lines.extend(["", f"{hidden_count} more alert rows are in the CSV output."])

    return lines


def _write_basic_pdf(path: Path, lines: list[str]) -> None:
    pages = _paginate(lines)
    objects: list[bytes] = []

    catalog_id = 1
    pages_id = 2
    font_id = 3
    page_ids: list[int] = []
    content_ids: list[int] = []
    next_id = 4

    for page_lines in pages:
        page_ids.append(next_id)
        content_ids.append(next_id + 1)
        next_id += 2

    objects.append(f"{catalog_id} 0 obj\n<< /Type /Catalog /Pages {pages_id} 0 R >>\nendobj\n".encode("ascii"))
    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    objects.append(
        f"{pages_id} 0 obj\n<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>\nendobj\n".encode("ascii")
    )
    objects.append(f"{font_id} 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n".encode("ascii"))

    for page_id, content_id, page_lines in zip(page_ids, content_ids, pages):
        stream = _page_stream(page_lines)
        objects.append(
            (
                f"{page_id} 0 obj\n"
                f"<< /Type /Page /Parent {pages_id} 0 R "
                f"/MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
                f"/Resources << /Font << /F1 {font_id} 0 R >> >> "
                f"/Contents {content_id} 0 R >>\n"
                "endobj\n"
            ).encode("ascii")
        )
        objects.append(
            (
                f"{content_id} 0 obj\n"
                f"<< /Length {len(stream)} >>\n"
                "stream\n"
            ).encode("ascii")
            + stream
            + b"\nendstream\nendobj\n"
        )

    content = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(content))
        content.extend(obj)

    xref_offset = len(content)
    content.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    content.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        content.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    content.extend(
        (
            "trailer\n"
            f"<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\n"
            "startxref\n"
            f"{xref_offset}\n"
            "%%EOF\n"
        ).encode("ascii")
    )

    path.write_bytes(bytes(content))


def _paginate(lines: list[str]) -> list[list[str]]:
    wrapped_lines: list[str] = []
    for line in lines:
        if not line:
            wrapped_lines.append("")
            continue
        wrapped_lines.extend(wrap(line, width=MAX_LINE_CHARS) or [""])

    lines_per_page = int((TOP_Y - 48) / LINE_HEIGHT)
    return [
        wrapped_lines[index : index + lines_per_page]
        for index in range(0, len(wrapped_lines), lines_per_page)
    ] or [[""]]


def _page_stream(lines: list[str]) -> bytes:
    commands = ["BT", "/F1 10 Tf", f"{LEFT_MARGIN} {TOP_Y} Td"]
    for index, line in enumerate(lines):
        if index > 0:
            commands.append(f"0 -{LINE_HEIGHT} Td")
        commands.append(f"({_escape_pdf_text(line)}) Tj")
    commands.append("ET")
    return "\n".join(commands).encode("latin-1", errors="replace")


def _escape_pdf_text(text: str) -> str:
    safe_text = text.encode("latin-1", errors="replace").decode("latin-1")
    return safe_text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
