"""Command-line interface for water contamination detection."""

from __future__ import annotations

import argparse
from pathlib import Path

from .algorithms import calibrate, detect_row
from .csv_io import read_sensor_csv, write_detection_csv
from .report import write_pdf_report
from .sample_data import generate_sample_files


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except ValueError as exc:
        parser.exit(2, f"error: {exc}\n")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m water_monitor",
        description="Detect possible water contamination from sensor CSV files.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    detect_parser = subparsers.add_parser(
        "detect",
        help="read baseline/input CSV files and write detection results",
    )
    detect_parser.add_argument("--baseline", required=True, type=Path)
    detect_parser.add_argument("--input", required=True, type=Path)
    detect_parser.add_argument("--output", required=True, type=Path)
    detect_parser.add_argument(
        "--pdf-output",
        type=Path,
        default=None,
        help="optional PDF report path explaining input columns and alert rows",
    )
    detect_parser.add_argument(
        "--max-pdf-alerts",
        type=int,
        default=50,
        help="maximum number of alert rows to include in the PDF report",
    )
    detect_parser.add_argument(
        "--vda-margin",
        type=float,
        default=0.10,
        help="fraction added to the largest clean-baseline VDA distance",
    )
    detect_parser.add_argument(
        "--vda-threshold",
        type=float,
        default=None,
        help="manual VDA threshold; overrides threshold learned from baseline",
    )
    detect_parser.set_defaults(func=_run_detect)

    sample_parser = subparsers.add_parser(
        "generate-sample",
        help="create example baseline and input CSV files",
    )
    sample_parser.add_argument("--baseline", required=True, type=Path)
    sample_parser.add_argument("--input", required=True, type=Path)
    sample_parser.add_argument("--seed", type=int, default=7)
    sample_parser.add_argument("--baseline-rows", type=int, default=60)
    sample_parser.add_argument("--input-rows", type=int, default=120)
    sample_parser.set_defaults(func=_run_generate_sample)

    return parser


def _run_detect(args: argparse.Namespace) -> None:
    _, baseline_numeric_rows = read_sensor_csv(args.baseline)
    input_original_rows, input_numeric_rows = read_sensor_csv(args.input)

    calibration = calibrate(
        baseline_numeric_rows,
        vda_margin=args.vda_margin,
        vda_threshold=args.vda_threshold,
    )
    results = [detect_row(row, calibration) for row in input_numeric_rows]
    write_detection_csv(args.output, input_original_rows, results)
    if args.pdf_output is not None:
        write_pdf_report(
            args.pdf_output,
            baseline_path=args.baseline,
            input_path=args.input,
            output_path=args.output,
            original_rows=input_original_rows,
            results=results,
            calibration=calibration,
            max_alert_rows=args.max_pdf_alerts,
        )

    alarm_count = sum(result.final_alarm for result in results)
    print(f"Wrote {args.output}")
    if args.pdf_output is not None:
        print(f"Wrote {args.pdf_output}")
    print(f"Rows analyzed: {len(results)}")
    print(f"Rows with alarms: {alarm_count}")
    print(f"VDA threshold: {calibration.vda_threshold:.6f}")


def _run_generate_sample(args: argparse.Namespace) -> None:
    generate_sample_files(
        args.baseline,
        args.input,
        seed=args.seed,
        baseline_rows=args.baseline_rows,
        input_rows=args.input_rows,
    )
    print(f"Wrote {args.baseline}")
    print(f"Wrote {args.input}")


if __name__ == "__main__":
    raise SystemExit(main())
