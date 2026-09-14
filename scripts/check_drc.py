#!/usr/bin/env python3
"""Fail-closed DRC gate for release decisions.

Usage:
  python3 scripts/check_drc.py <drc.json> [--strict-parity]

Exit codes:
  0 = release gate passed
  1 = blocked by errors/unconnected/parity (when strict)
  2 = malformed input
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _error_count(entries: list[dict]) -> int:
    return sum(1 for entry in entries if str(entry.get("severity", "")).lower() == "error")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path, help="KiCad DRC JSON report path")
    parser.add_argument(
        "--strict-parity",
        action="store_true",
        help="Treat schematic_parity entries as blocking (default: informative only)",
    )
    args = parser.parse_args()

    try:
        data = json.loads(args.report.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot read DRC report {args.report}: {exc}")
        return 2

    violations = data.get("violations") or []
    unconnected = data.get("unconnected_items") or []
    parity = data.get("schematic_parity") or []

    error_violations = _error_count(violations)
    error_unconnected = _error_count(unconnected)
    parity_count = len(parity)

    print(
        f"BLOCKED: violations={error_violations} "
        f"unconnected_items={error_unconnected} schematic_parity={parity_count}"
        if (error_violations > 0 or error_unconnected > 0 or (args.strict_parity and parity_count > 0))
        else (
            f"PASS: violations={error_violations} "
            f"unconnected_items={error_unconnected} schematic_parity={parity_count}"
        )
    )

    if error_violations > 0:
        print("REASON: DRC error-severity violations present")
    if error_unconnected > 0:
        print("REASON: unrouted/unconnected items present")
    if args.strict_parity and parity_count > 0:
        print("REASON: schematic/PCB parity differences present in strict mode")

    return 1 if (error_violations > 0 or error_unconnected > 0 or (args.strict_parity and parity_count > 0)) else 0


if __name__ == "__main__":
    raise SystemExit(main())
