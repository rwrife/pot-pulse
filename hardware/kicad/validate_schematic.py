#!/usr/bin/env python3
"""Validate issue #3 schematic acceptance criteria and native ERC evidence."""
from __future__ import annotations

import argparse
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCH = ROOT / "hardware/kicad/pot-pulse.kicad_sch"
PRO = ROOT / "hardware/kicad/pot-pulse.kicad_pro"
LIB = ROOT / "hardware/kicad/lib/pot-pulse.kicad_sym"
NOTES = ROOT / "hardware/schematic-notes.md"


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def prop(component, name: str) -> str:
    value = component.get_property(name)
    if isinstance(value, dict):
        value = value.get("value")
    return "" if value is None else str(value)


def rounded(x: float, y: float) -> tuple[float, float]:
    return round(float(x), 3), round(float(y), 3)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--erc", type=Path, required=True)
    args = parser.parse_args()
    for path in (SCH, PRO, LIB, NOTES, args.erc):
        if not path.is_file():
            fail(f"missing required file: {path}")

    os.environ.setdefault("KICAD_SYMBOL_DIR", "/usr/share/kicad/symbols")
    from kicad_sch_api import get_symbol_cache, load_schematic
    cache = get_symbol_cache()
    symbol_dir = Path(os.environ["KICAD_SYMBOL_DIR"])
    if symbol_dir.is_dir():
        cache.discover_libraries([str(symbol_dir)])
    if not cache.add_library_path(str(LIB)):
        fail("could not load project symbol library")
    schematic = load_schematic(SCH)
    components = {c.reference: c for c in schematic.components.all()}
    definitions = {ref: cache.get_symbol(c.lib_id) for ref, c in components.items()}
    if missing := sorted(ref for ref, definition in definitions.items() if definition is None):
        fail(f"symbol definitions did not resolve: {missing}")

    expected_bom_refs = {
        "J1", "F1", "D1", "U1", "U2", "U3", "U4", "U5", "U6", "U7", "L1",
        "R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R9", "R10", "R11", "R12",
        "C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9", "C10", "C11", "C12", "C13",
        "J2", "J3", "J4", "J5",
    }
    bom_refs = {c.reference for c in components.values() if c.in_bom and not c.reference.startswith("#")}
    if bom_refs != expected_bom_refs:
        fail(f"BOM reference set mismatch: missing={sorted(expected_bom_refs-bom_refs)} extra={sorted(bom_refs-expected_bom_refs)}")
    for ref in sorted(bom_refs):
        component = components[ref]
        if not component.footprint:
            fail(f"{ref} has no footprint/package assignment")
        for field in ("Manufacturer", "MPN", "Datasheet", "BOM Comments"):
            if not prop(component, field).strip():
                fail(f"{ref} missing required {field} property")

    expected_pin_names = {
        "U1": {"1":"PGND", "2":"VIN", "3":"EN", "4":"AGND", "5":"FB", "6":"VOS", "7":"SW", "8":"PG", "9":"EP_GND"},
        "U4": {"1":"ADDR", "2":"ALERT/RDY_N", "3":"GND", "4":"AIN0", "5":"AIN1", "6":"AIN2", "7":"AIN3", "8":"VDD", "9":"SDA", "10":"SCL"},
        "U5": {"1":"SDA", "2":"SCL", "3":"VDD", "4":"VSS"},
        "U6": {"1":"SCL", "2":"VDD", "3":"GND", "4":"SDA"},
        "U3": {"1":"D1+", "2":"D1-", "3":"GND", "4":"D2+", "5":"D2-", "8":"GND"},
        "U2": {"3":"3V3", "8":"EN", "18":"GPIO4", "19":"GPIO5", "20":"GPIO6", "23":"GPIO9", "26":"USB_D-", "27":"USB_D+", "30":"U0RXD_GPIO20", "31":"U0TXD_GPIO21"},
    }
    for ref, pin_map in expected_pin_names.items():
        definition = definitions[ref]
        for number, name in pin_map.items():
            pin = definition.get_pin(number)
            if pin is None or pin.name != name:
                fail(f"{ref}.{number}: expected pin name {name!r}, got {getattr(pin, 'name', None)!r}")

    text = SCH.read_text(encoding="utf-8")
    label_pattern = re.compile(r'\(label\s+"([^"]+)"\s*\n\s*\(at\s+([-0-9.]+)\s+([-0-9.]+)')
    labels_at: dict[tuple[float, float], set[str]] = defaultdict(set)
    for net, x, y in label_pattern.findall(text):
        labels_at[rounded(float(x), float(y))].add(net)
    for point, nets in labels_at.items():
        if len(nets) > 1:
            fail(f"conflicting labels at {point}: {sorted(nets)}")

    def pin_point(ref: str, number: str) -> tuple[float, float]:
        component = components[ref]
        pin = definitions[ref].get_pin(number)
        if pin is None:
            fail(f"{ref} missing pin {number}")
        return rounded(component.position.x + pin.position.x, component.position.y - pin.position.y)

    expectations = {
        ("J1", "A4"): "VBUS", ("J1", "A5"): "CC1", ("J1", "B5"): "CC2",
        ("U7", "1"): "USB_CONN_DM", ("U7", "6"): "USB_DM", ("U7", "3"): "USB_CONN_DP", ("U7", "4"): "USB_DP",
        ("U1", "2"): "+5V_PROTECTED", ("U1", "6"): "+3V3", ("U1", "7"): "SW_NODE",
        ("L1", "2"): "+3V3", ("U2", "3"): "+3V3", ("U2", "18"): "I2C_SDA",
        ("U2", "19"): "I2C_SCL", ("U2", "20"): "ADC_ALERT_N", ("U2", "23"): "BOOT_GPIO9",
        ("U2", "26"): "USB_DM", ("U2", "27"): "USB_DP", ("U2", "30"): "U0RXD", ("U2", "31"): "U0TXD",
        ("U4", "1"): "GND", ("U4", "4"): "MOISTURE_AIN0", ("U4", "5"): "MOISTURE_AIN1",
        ("U4", "6"): "MOISTURE_AIN2", ("U4", "7"): "MOISTURE_AIN3", ("U4", "9"): "I2C_SDA", ("U4", "10"): "I2C_SCL",
        ("U5", "1"): "I2C_SDA", ("U5", "2"): "I2C_SCL", ("U6", "1"): "I2C_SCL", ("U6", "4"): "I2C_SDA",
        ("J6", "3"): "EN", ("J6", "4"): "BOOT_GPIO9", ("J6", "5"): "U0RXD", ("J6", "6"): "U0TXD",
    }
    for (ref, pin), net in expectations.items():
        point = pin_point(ref, pin)
        if net not in labels_at.get(point, set()):
            fail(f"{ref}.{pin} at {point}: expected {net}, got {sorted(labels_at.get(point, set()))}")

    required_nets = {
        "VBUS", "+5V_PROTECTED", "+3V3", "GND", "CC1", "CC2", "USB_CONN_DP", "USB_CONN_DM", "USB_DP", "USB_DM",
        "REG_PG", "SW_NODE", "EN", "BOOT_GPIO9", "U0RXD", "U0TXD", "I2C_SDA", "I2C_SCL", "ADC_ALERT_N",
        *{f"PROBE{i}_RAW" for i in range(1, 5)}, *{f"MOISTURE_AIN{i}" for i in range(4)},
    }
    observed_nets = {net for nets in labels_at.values() for net in nets}
    if missing := sorted(required_nets - observed_nets):
        fail(f"missing required named nets: {missing}")

    expected_test_nets = ["VBUS", "+5V_PROTECTED", "+3V3", "GND", "I2C_SDA", "I2C_SCL", "USB_DP", "USB_DM",
                          "REG_PG", "EN", "BOOT_GPIO9", "ADC_ALERT_N", "MOISTURE_AIN0", "MOISTURE_AIN1", "MOISTURE_AIN2", "MOISTURE_AIN3"]
    for index, net in enumerate(expected_test_nets, 1):
        ref = f"TP{index}"
        if ref not in components:
            fail(f"missing {ref} for {net}")
        if net not in labels_at.get(pin_point(ref, "1"), set()):
            fail(f"{ref} is not attached to {net}")

    erc = args.erc.read_text(encoding="utf-8", errors="replace")
    summary = re.search(r"ERC messages:\s*(\d+)\s+Errors\s+(\d+)\s+Warnings\s+(\d+)", erc)
    if not summary:
        fail("native ERC report has no parseable summary")
    messages, errors, warnings = map(int, summary.groups())
    if (errors, warnings) != (0, 0):
        fail(f"native ERC is not clean: messages={messages} errors={errors} warnings={warnings}")

    if "static evidence" not in NOTES.read_text(encoding="utf-8").lower():
        fail("schematic notes do not state the static evidence boundary")

    print(f"PASS: native ERC errors={errors} warnings={warnings} messages={messages}")
    print(f"PASS: {len(bom_refs)} purchased schematic symbols have footprint, Manufacturer, MPN, Datasheet and BOM Comments")
    print(f"PASS: {len(required_nets)} required nets and {len(expectations)} critical pin/net mappings checked")
    print(f"PASS: {len(expected_test_nets)} named test pads include all major rails, I2C, USB, control and four analog channels")
    print("PASS: evidence_class=static_schematic; pcb=not_run bench=not_run field=not_run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
