#!/usr/bin/env python3
"""Export the Pot Pulse BOM from authoritative KiCad symbol properties."""
from __future__ import annotations

import argparse
import csv
import importlib
import re
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMATIC = ROOT / "hardware/kicad/pot-pulse.kicad_sch"
DEFAULT_OUTPUT = ROOT / "bom/bom.csv"
FIELDS = [
    "References",
    "Quantity",
    "Value",
    "Footprint",
    "Manufacturer",
    "MPN",
    "Supplier",
    "Supplier PN",
    "Source URL",
    "Estimated Unit Cost USD",
    "Price Snapshot Date",
    "Extended Estimate USD",
    "Pricing Status",
    "Datasheet",
    "Notes",
]


def natural_key(value: str) -> list[object]:
    return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", value)]


def prop(component: Any, name: str) -> str:
    value = component.get_property(name)
    if isinstance(value, dict):
        value = value.get("value")
    return "" if value is None else str(value).strip()


def purchased_components(schematic_path: Path) -> list[Any]:
    load_schematic = importlib.import_module("kicad_sch_api").load_schematic

    schematic = load_schematic(schematic_path)
    return sorted(
        (
            component
            for component in schematic.components.all()
            if component.in_bom and not component.reference.startswith("#")
        ),
        key=lambda component: natural_key(component.reference),
    )


def build_rows(schematic_path: Path) -> list[dict[str, str]]:
    groups: dict[tuple[str, ...], list[Any]] = defaultdict(list)
    for component in purchased_components(schematic_path):
        key = (
            str(component.value).strip(),
            str(component.footprint).strip(),
            prop(component, "Manufacturer"),
            prop(component, "MPN"),
            prop(component, "Supplier"),
            prop(component, "Supplier PN"),
            prop(component, "Source URL"),
            prop(component, "Estimated Unit Cost USD"),
            prop(component, "Price Snapshot Date"),
            prop(component, "Datasheet"),
        )
        groups[key].append(component)

    rows: list[dict[str, str]] = []
    for key, components in groups.items():
        value, footprint, manufacturer, mpn, supplier, supplier_pn, source_url, unit_cost, snapshot, datasheet = key
        references = sorted((component.reference for component in components), key=natural_key)
        notes = sorted({prop(component, "BOM Comments") for component in components if prop(component, "BOM Comments")})
        try:
            numeric_cost = Decimal(unit_cost)
        except (InvalidOperation, ValueError):
            extended = "TBD"
            pricing_status = "Quote required"
        else:
            extended = f"{numeric_cost * len(components):.4f}"
            pricing_status = "Dated estimate - recheck before order"
        rows.append(
            {
                "References": ", ".join(references),
                "Quantity": str(len(components)),
                "Value": value,
                "Footprint": footprint,
                "Manufacturer": manufacturer,
                "MPN": mpn,
                "Supplier": supplier,
                "Supplier PN": supplier_pn,
                "Source URL": source_url,
                "Estimated Unit Cost USD": unit_cost,
                "Price Snapshot Date": snapshot,
                "Extended Estimate USD": extended,
                "Pricing Status": pricing_status,
                "Datasheet": datasheet,
                "Notes": " | ".join(notes),
            }
        )
    return sorted(rows, key=lambda row: natural_key(row["References"].split(",", 1)[0]))


def write_bom(schematic_path: Path, output_path: Path) -> list[dict[str, str]]:
    rows = build_rows(schematic_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schematic", type=Path, default=DEFAULT_SCHEMATIC)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    rows = write_bom(args.schematic, args.output)
    quantity = sum(int(row["Quantity"]) for row in rows)
    priced = sum(row["Pricing Status"].startswith("Dated") for row in rows)
    print(f"exported {len(rows)} BOM lines / {quantity} schematic parts to {args.output}")
    print(f"pricing: {priced} dated estimates; {len(rows) - priced} quote-required lines")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
