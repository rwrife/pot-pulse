#!/usr/bin/env python3
"""Validate the issue #2 component-selection handoff.

This is intentionally independent of KiCad because issue #3 creates the first
schematic. It fails closed on incomplete selected-part identity, stale/malformed
snapshot metadata, missing critical classes, and drift from the planning BOM.
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import date
from pathlib import Path


REQUIRED_COLUMNS = {
    "Class",
    "Role",
    "Qty",
    "Manufacturer",
    "MPN",
    "Package_or_Interface",
    "Supply_or_Rating",
    "Operating_Temperature_C",
    "Preferred_Supplier",
    "Supplier_PN",
    "Availability_Status",
    "Stock_Qty",
    "Snapshot_Date",
    "Lifecycle_Status",
    "Datasheet_URL",
    "Product_URL",
    "Selection_Status",
    "Notes",
}

REQUIRED_CLASSES = {
    "mcu",
    "adc",
    "regulator",
    "ambient_sensor",
    "light_sensor",
    "moisture_probe",
    "usb_connector",
    "probe_connector",
    "usb_esd",
    "vbus_tvs",
    "probe_esd",
    "input_fuse",
}

PLACEHOLDERS = {"", "tbd", "unknown", "none", "n/a"}


def load_csv(path: Path) -> tuple[list[dict[str, str]], set[str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return list(reader), set(reader.fieldnames or [])


def validate(selection_path: Path, planning_bom_path: Path) -> list[str]:
    errors: list[str] = []
    rows, columns = load_csv(selection_path)
    missing_columns = sorted(REQUIRED_COLUMNS - columns)
    if missing_columns:
        errors.append(f"selection CSV missing columns: {', '.join(missing_columns)}")
        return errors

    classes = {row["Class"].strip() for row in rows}
    for missing_class in sorted(REQUIRED_CLASSES - classes):
        errors.append(f"missing critical class: {missing_class}")

    seen_mpns: set[str] = set()
    today = date.today()
    for line_number, row in enumerate(rows, start=2):
        prefix = f"selection line {line_number} ({row.get('Class', '')})"
        for field in ("Manufacturer", "MPN", "Package_or_Interface", "Preferred_Supplier", "Supplier_PN"):
            value = row[field].strip()
            if value.lower() in PLACEHOLDERS:
                errors.append(f"{prefix}: {field} is blank or a placeholder")

        mpn = row["MPN"].strip()
        if "," in mpn:
            errors.append(f"{prefix}: MPN contains a comma; one physical part per row is required")
        if mpn in seen_mpns:
            errors.append(f"{prefix}: duplicate MPN {mpn}")
        seen_mpns.add(mpn)

        if row["Selection_Status"].strip() != "selected":
            errors.append(f"{prefix}: Selection_Status must be selected")

        try:
            qty = int(row["Qty"])
            if qty <= 0:
                raise ValueError
        except ValueError:
            errors.append(f"{prefix}: Qty must be a positive integer")

        try:
            snapshot = date.fromisoformat(row["Snapshot_Date"].strip())
            if snapshot > today:
                errors.append(f"{prefix}: Snapshot_Date is in the future")
        except ValueError:
            errors.append(f"{prefix}: Snapshot_Date must be ISO YYYY-MM-DD")

        for field in ("Datasheet_URL", "Product_URL"):
            if not row[field].strip().startswith("https://"):
                errors.append(f"{prefix}: {field} must be an https URL")

        if row["Availability_Status"].strip().lower() in PLACEHOLDERS:
            errors.append(f"{prefix}: availability evidence is missing")
        if row["Lifecycle_Status"].strip().lower() in PLACEHOLDERS:
            errors.append(f"{prefix}: lifecycle evidence is missing")

        stock_text = row["Stock_Qty"].strip()
        if stock_text:
            try:
                if int(stock_text) <= 0:
                    errors.append(f"{prefix}: Stock_Qty must be positive when supplied")
            except ValueError:
                errors.append(f"{prefix}: Stock_Qty must be an integer or blank")
        elif row["Class"] != "moisture_probe":
            errors.append(f"{prefix}: board-mounted selected parts require a stock quantity")

    bom_rows, bom_columns = load_csv(planning_bom_path)
    required_bom_columns = {"Manufacturer", "MPN", "Planning_Status"}
    if required_bom_columns - bom_columns:
        errors.append("planning BOM is missing Manufacturer, MPN, or Planning_Status")
        return errors

    selected_bom_mpns = {
        row["MPN"].strip()
        for row in bom_rows
        if row["Planning_Status"].strip() == "SELECTED_FOR_SCHEMATIC"
    }
    for mpn in sorted(seen_mpns - selected_bom_mpns):
        errors.append(f"planning BOM is missing selected MPN: {mpn}")
    for mpn in sorted(selected_bom_mpns - seen_mpns):
        errors.append(f"planning BOM selected MPN absent from selection manifest: {mpn}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--selection",
        type=Path,
        default=Path("hardware/component-selection.csv"),
    )
    parser.add_argument(
        "--planning-bom",
        type=Path,
        default=Path("bom/preliminary-bom.csv"),
    )
    args = parser.parse_args()

    errors = validate(args.selection, args.planning_bom)
    if errors:
        print(f"FAIL component-selection validation: {len(errors)} error(s)")
        for error in errors:
            print(f"- {error}")
        return 1

    rows, _ = load_csv(args.selection)
    stock_rows = sum(bool(row["Stock_Qty"].strip()) for row in rows)
    print("PASS component-selection validation")
    print(f"selected_parts={len(rows)}")
    print(f"critical_classes={len({row['Class'] for row in rows})}")
    print(f"positive_stock_snapshots={stock_rows}")
    print(f"manufacturer_listing_only={len(rows) - stock_rows}")
    print(f"snapshot_dates={','.join(sorted({row['Snapshot_Date'] for row in rows}))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
