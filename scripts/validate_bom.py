#!/usr/bin/env python3
"""Validate the schematic-owned BOM export and procurement tracking files."""
from __future__ import annotations

import argparse
import csv
import tempfile
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import NoReturn

import export_bom

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_NON_SCHEMATIC = ROOT / "bom/non-schematic-items.csv"
REQUIRED_PROPERTIES = (
    "Manufacturer",
    "MPN",
    "Supplier",
    "Source URL",
    "Estimated Unit Cost USD",
    "Price Snapshot Date",
    "Datasheet",
    "BOM Comments",
)
NON_SCHEMATIC_FIELDS = [
    "Item",
    "Quantity",
    "Manufacturer",
    "MPN",
    "Supplier",
    "Source URL",
    "Estimated Unit Cost USD",
    "Status",
    "Dependency",
    "Notes",
]


def fail(message: str) -> NoReturn:
    raise SystemExit(f"ERROR: {message}")


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def validate_component_properties(schematic: Path) -> tuple[int, int]:
    components = export_bom.purchased_components(schematic)
    if not components:
        fail("schematic contains no purchased BOM components")
    quote_required = 0
    for component in components:
        ref = component.reference
        if not str(component.footprint).strip():
            fail(f"{ref} has no footprint")
        values = {name: export_bom.prop(component, name) for name in REQUIRED_PROPERTIES}
        missing = [name for name, value in values.items() if not value]
        if missing:
            fail(f"{ref} missing properties: {', '.join(missing)}")
        try:
            date.fromisoformat(values["Price Snapshot Date"])
        except ValueError:
            fail(f"{ref} has invalid Price Snapshot Date: {values['Price Snapshot Date']!r}")
        cost = values["Estimated Unit Cost USD"]
        try:
            numeric = Decimal(cost)
        except InvalidOperation:
            if not cost.startswith("TBD"):
                fail(f"{ref} cost must be numeric or explicit TBD: {cost!r}")
            quote_required += 1
        else:
            if numeric < 0:
                fail(f"{ref} has negative unit cost")
            if values["Supplier"] == "Unassigned" or not export_bom.prop(component, "Supplier PN"):
                fail(f"{ref} has numeric cost without assigned supplier and supplier PN")
    return len(components), quote_required


def validate_export(schematic: Path, committed_bom: Path) -> tuple[list[dict[str, str]], Decimal]:
    if not committed_bom.is_file():
        fail(f"missing committed BOM: {committed_bom}")
    fields, rows = read_csv(committed_bom)
    if fields != export_bom.FIELDS:
        fail(f"BOM header mismatch: expected {export_bom.FIELDS}, got {fields}")
    with tempfile.TemporaryDirectory() as tmp:
        generated = Path(tmp) / "bom.csv"
        export_bom.write_bom(schematic, generated)
        if generated.read_bytes() != committed_bom.read_bytes():
            fail("committed bom/bom.csv is stale; run scripts/export_bom.py")

    refs: list[str] = []
    subtotal = Decimal("0")
    for row_number, row in enumerate(rows, 2):
        allowed_empty = {"Supplier PN"} if row.get("Supplier") == "Unassigned" else set()
        missing = [field for field in export_bom.FIELDS if field not in allowed_empty and not row.get(field, "").strip()]
        if missing:
            fail(f"BOM row {row_number} has empty fields: {', '.join(missing)}")
        if row["Supplier"] != "Unassigned" and not row["Supplier PN"].strip():
            fail(f"BOM row {row_number} has assigned supplier without Supplier PN")
        row_refs = [ref.strip() for ref in row["References"].split(",")]
        if int(row["Quantity"]) != len(row_refs):
            fail(f"BOM row {row_number} quantity does not match references")
        refs.extend(row_refs)
        if row["Pricing Status"].startswith("Dated"):
            expected = Decimal(row["Estimated Unit Cost USD"]) * int(row["Quantity"])
            actual = Decimal(row["Extended Estimate USD"])
            if expected != actual:
                fail(f"BOM row {row_number} extended estimate mismatch")
            subtotal += actual
        elif row["Extended Estimate USD"] != "TBD":
            fail(f"BOM row {row_number} quote-required extended estimate must be TBD")
    if len(refs) != len(set(refs)):
        fail("a schematic reference appears on more than one BOM row")
    source_refs = {component.reference for component in export_bom.purchased_components(schematic)}
    if set(refs) != source_refs:
        fail(f"BOM references differ from schematic: missing={sorted(source_refs-set(refs))} extra={sorted(set(refs)-source_refs)}")
    return rows, subtotal


def validate_non_schematic(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        fail(f"missing non-schematic procurement list: {path}")
    fields, rows = read_csv(path)
    if fields != NON_SCHEMATIC_FIELDS:
        fail(f"non-schematic header mismatch: expected {NON_SCHEMATIC_FIELDS}, got {fields}")
    for row_number, row in enumerate(rows, 2):
        required = [field for field in NON_SCHEMATIC_FIELDS if field != "Dependency"]
        missing = [field for field in required if not row.get(field, "").strip()]
        if missing:
            fail(f"non-schematic row {row_number} has empty fields: {', '.join(missing)}")
        try:
            quantity = int(row["Quantity"])
        except ValueError:
            fail(f"non-schematic row {row_number} quantity is not an integer")
        if quantity < 1:
            fail(f"non-schematic row {row_number} quantity must be positive")
    item_text = " ".join(row["Item"].lower() for row in rows)
    for category in ("probe", "cable", "enclosure", "fastener", "debug adapter"):
        if category not in item_text:
            fail(f"non-schematic procurement list lacks {category}")
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schematic", type=Path, default=export_bom.DEFAULT_SCHEMATIC)
    parser.add_argument("--bom", type=Path, default=export_bom.DEFAULT_OUTPUT)
    parser.add_argument("--non-schematic", type=Path, default=DEFAULT_NON_SCHEMATIC)
    args = parser.parse_args()

    component_count, quote_component_count = validate_component_properties(args.schematic)
    rows, subtotal = validate_export(args.schematic, args.bom)
    non_schematic = validate_non_schematic(args.non_schematic)
    priced_lines = sum(row["Pricing Status"].startswith("Dated") for row in rows)

    print(f"PASS: {component_count} purchased schematic symbols have complete BOM properties")
    print(f"PASS: {len(rows)} grouped BOM lines reproduce byte-for-byte from KiCad source; quantity={sum(int(row['Quantity']) for row in rows)}")
    print(f"PASS: pricing coverage={priced_lines}/{len(rows)} lines; quote_required_components={quote_component_count}; partial_estimate_usd={subtotal:.4f}")
    print(f"PASS: {len(non_schematic)} non-schematic procurement rows cover probes, cable, enclosure, fasteners, and debug adapter")
    print("PASS: evidence_class=static_bom; stock=not_verified_for_order; physical_procurement=not_run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
