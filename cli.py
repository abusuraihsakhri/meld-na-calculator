#!/usr/bin/env python3
"""
Command-line interface for the MELD-Na Calculator.

Usage examples:

  Single patient:
    python cli.py calculate --bilirubin 2.5 --inr 1.8 --creatinine 1.5 --sodium 135

  With albumin (MELD 3.0):
    python cli.py calculate --bilirubin 2.5 --inr 1.8 --creatinine 1.5 \
        --sodium 135 --albumin 3.2 --female

  Dialysis patient:
    python cli.py calculate --bilirubin 4.0 --inr 2.5 --creatinine 1.0 \
        --sodium 130 --dialysis

  Batch processing:
    python cli.py batch --input patients.csv --output scored.csv

  Show exception points info:
    python cli.py exceptions

DISCLAIMER: Educational/reference tool only. Not for clinical decision-making.
"""

import argparse
import csv
import json
import sys

from meld_na import (
    full_assessment,
    calculate_meld,
    calculate_meld_na,
    calculate_meld_3,
    estimate_3month_mortality,
    get_allocation_priority,
    get_exception_points_info,
)


def _print_result(result: dict) -> None:
    """Pretty-print a full_assessment result dict."""
    print("=" * 60)
    print("  MELD-Na Calculator Results")
    print("=" * 60)
    print(f"  MELD (original) :  {result['meld']}")
    print(f"  MELD-Na (2016)  :  {result['meld_na']}")
    if result["meld_3"] is not None:
        print(f"  MELD 3.0 (2023) :  {result['meld_3']}")
    else:
        print(f"  MELD 3.0 (2023) :  N/A (requires --albumin)")
    print(f"  3-month mortality:  {result['mortality_3mo'] * 100:.1f}%")
    print(f"  Priority tier   :  {result['priority']}")
    print("-" * 60)
    print("  Inputs (after clamping/adjustment):")
    for k, v in result["inputs"].items():
        print(f"    {k:20s}: {v}")
    print("=" * 60)


def cmd_calculate(args):
    """Handle the 'calculate' subcommand."""
    result = full_assessment(
        bilirubin=args.bilirubin,
        inr=args.inr,
        creatinine=args.creatinine,
        sodium=args.sodium,
        albumin=args.albumin,
        female=args.female,
        dialysis=args.dialysis,
    )
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        _print_result(result)
    return 0


def cmd_batch(args):
    """Handle the 'batch' subcommand — process a CSV of patients."""
    with open(args.input, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    # Map common column name variants to our expected names
    COL_MAP = {
        "bilirubin": "bilirubin",
        "bili": "bilirubin",
        "bilirubin_mgdl": "bilirubin",
        "inr": "inr",
        "creatinine": "creatinine",
        "creat": "creatinine",
        "creatinine_mgdl": "creatinine",
        "sodium": "sodium",
        "na": "sodium",
        "sodium_meql": "sodium",
        "albumin": "albumin",
        "albumin_gdl": "albumin",
        "dialysis": "dialysis",
        "sex": "sex",
        "female": "female",
    }

    def _get(row, key):
        """Get a value from a row, trying column aliases."""
        for col, mapped in COL_MAP.items():
            if mapped == key and col in row and row[col] not in (None, ""):
                return row[col]
        return None

    def _parse_bool(val):
        if val is None:
            return False
        s = str(val).strip().lower()
        return s in ("1", "true", "yes", "y", "f", "female")

    out_fields = list(fieldnames)
    for extra in ["meld", "meld_na", "meld_3", "mortality_3mo", "priority"]:
        if extra not in out_fields:
            out_fields.append(extra)

    out_rows = []
    for row in rows:
        try:
            bili = float(_get(row, "bilirubin") or 1.0)
            inr = float(_get(row, "inr") or 1.0)
            creat = float(_get(row, "creatinine") or 1.0)
            na = float(_get(row, "sodium") or 137.0)
            alb_raw = _get(row, "albumin")
            alb = float(alb_raw) if alb_raw is not None else None
            dialysis = _parse_bool(_get(row, "dialysis"))
            sex_val = str(_get(row, "sex") or "M").strip().upper()
            female = sex_val in ("F", "FEMALE") or _parse_bool(_get(row, "female"))

            result = full_assessment(
                bilirubin=bili,
                inr=inr,
                creatinine=creat,
                sodium=na,
                albumin=alb,
                female=female,
                dialysis=dialysis,
            )
            merged = dict(row)
            merged["meld"] = result["meld"]
            merged["meld_na"] = result["meld_na"]
            merged["meld_3"] = result["meld_3"] if result["meld_3"] is not None else ""
            merged["mortality_3mo"] = f"{result['mortality_3mo'] * 100:.1f}%"
            merged["priority"] = result["priority"]
            out_rows.append(merged)
        except Exception as e:
            merged = dict(row)
            merged["meld"] = "ERROR"
            merged["meld_na"] = "ERROR"
            merged["meld_3"] = "ERROR"
            merged["mortality_3mo"] = "ERROR"
            merged["priority"] = str(e)
            out_rows.append(merged)

    with open(args.output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=out_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(out_rows)

    print(f"Processed {len(out_rows)} patient(s) -> {args.output}")
    return 0


def cmd_exceptions(args):
    """Handle the 'exceptions' subcommand."""
    print(get_exception_points_info())
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="meld-na-calculator",
        description="MELD-Na / MELD 3.0 Calculator — liver transplant scoring",
        epilog="DISCLAIMER: Educational/reference tool only. Not for clinical use.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # --- calculate ---
    p_calc = sub.add_parser(
        "calculate",
        help="Calculate MELD scores for a single patient",
    )
    p_calc.add_argument(
        "--bilirubin", type=float, required=True,
        help="Serum bilirubin (mg/dL)",
    )
    p_calc.add_argument(
        "--inr", type=float, required=True,
        help="International normalized ratio",
    )
    p_calc.add_argument(
        "--creatinine", type=float, required=True,
        help="Serum creatinine (mg/dL)",
    )
    p_calc.add_argument(
        "--sodium", type=float, required=True,
        help="Serum sodium (mEq/L)",
    )
    p_calc.add_argument(
        "--albumin", type=float, default=None,
        help="Serum albumin (g/dL) — enables MELD 3.0 calculation",
    )
    p_calc.add_argument(
        "--female", action="store_true",
        help="Patient is female (for MELD 3.0 sex adjustment)",
    )
    p_calc.add_argument(
        "--dialysis", action="store_true",
        help="Patient received ≥ 2 dialysis sessions in the past week",
    )
    p_calc.add_argument(
        "--json", action="store_true",
        help="Output result as JSON instead of formatted text",
    )

    # --- batch ---
    p_batch = sub.add_parser(
        "batch",
        help="Batch-process a CSV file of patients",
    )
    p_batch.add_argument(
        "--input", "-i", required=True,
        help="Input CSV file path",
    )
    p_batch.add_argument(
        "--output", "-o", default="scored.csv",
        help="Output CSV file path (default: scored.csv)",
    )

    # --- exceptions ---
    sub.add_parser(
        "exceptions",
        help="Show MELD exception point policies",
    )

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "calculate":
        return cmd_calculate(args)
    elif args.command == "batch":
        return cmd_batch(args)
    elif args.command == "exceptions":
        return cmd_exceptions(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
