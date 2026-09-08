#!/usr/bin/env python3
"""Generate the editable Pot Pulse first-pass schematic.

Manufacturer datasheets cited in hardware/component-selection.md are the
pinout/electrical source of truth.  The generated KiCad schematic remains
editable; this script only makes the first capture reproducible.
"""
from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

RES_DS = "https://www.yageo.com/upload/media/product/productsearch/datasheet/rchip/PYu-RC_Group_51_RoHS_L_16.pdf"
CAP_DS = "https://www.murata.com/en-global/products/capacitor/mlcc/overview/lineup"
PRICE_SNAPSHOT_DATE = "2026-09-08"

# Exact source records queried by MPN on PRICE_SNAPSHOT_DATE. USBLC6-2SC6
# and TPD4E05U06DQAR intentionally retain the manufacturer-validated LCSC
# records from the 2026-09-05 component-selection snapshot; newer same-MPN
# search hits did not expose manufacturer identity and are not substitutions.
SOURCING: dict[str, tuple[str, str, str, str, str]] = {
    # MPN: (supplier, supplier PN, source URL, estimated unit cost USD, snapshot date)
    "ADS1115IDGSR": ("LCSC", "C37593", "https://www.lcsc.com/product-detail/C37593.html", "1.5342", PRICE_SNAPSHOT_DATE),
    "ESD5Z5.0T1G": ("LCSC", "C82044", "https://www.lcsc.com/product-detail/C82044.html", "0.0365", PRICE_SNAPSHOT_DATE),
    "ESP32-C3-MINI-1-H4X": ("LCSC", "C41349510", "https://www.lcsc.com/product-detail/C41349510.html", "3.0795", PRICE_SNAPSHOT_DATE),
    "GRM188R71H104KA93D": ("LCSC", "C77055", "https://www.lcsc.com/product-detail/C77055.html", "0.0199", PRICE_SNAPSHOT_DATE),
    "GRM31CR61A106KA01L": ("LCSC", "C97949", "https://www.lcsc.com/product-detail/C97949.html", "0.3352", PRICE_SNAPSHOT_DATE),
    "MF-MSMF050-2": ("LCSC", "C17313", "https://www.lcsc.com/product-detail/C17313.html", "0.0690", PRICE_SNAPSHOT_DATE),
    "RC0603FR-07100KL": ("LCSC", "C14675", "https://www.lcsc.com/product-detail/C14675.html", "0.0022", PRICE_SNAPSHOT_DATE),
    "RC0603FR-0710KL": ("LCSC", "C98220", "https://www.lcsc.com/product-detail/C98220.html", "0.0023", PRICE_SNAPSHOT_DATE),
    "RC0603FR-071KL": ("LCSC", "C22548", "https://www.lcsc.com/product-detail/C22548.html", "0.0021", PRICE_SNAPSHOT_DATE),
    "RC0603FR-074K7L": ("LCSC", "C99782", "https://www.lcsc.com/product-detail/C99782.html", "0.0023", PRICE_SNAPSHOT_DATE),
    "RC0603FR-075K1L": ("LCSC", "C105580", "https://www.lcsc.com/product-detail/C105580.html", "0.0020", PRICE_SNAPSHOT_DATE),
    "S3B-PH-K-S(LF)(SN)": ("LCSC", "C157929", "https://www.lcsc.com/product-detail/C157929.html", "0.0497", PRICE_SNAPSHOT_DATE),
    "SHT40-AD1B-R2": ("LCSC", "C2909890", "https://www.lcsc.com/product-detail/C2909890.html", "2.0288", PRICE_SNAPSHOT_DATE),
    "TPD4E05U06DQAR": ("LCSC", "C138714", "https://www.lcsc.com/product-detail/C138714.html", "0.0819", "2026-09-05"),
    "TPS62162DSGR": ("LCSC", "C40256", "https://www.lcsc.com/product-detail/C40256.html", "0.9697", PRICE_SNAPSHOT_DATE),
    "USB4105-GF-A": ("LCSC", "C3020560", "https://www.lcsc.com/product-detail/C3020560.html", "1.0319", PRICE_SNAPSHOT_DATE),
    "USBLC6-2SC6": ("LCSC", "C7519", "https://www.lcsc.com/product-detail/C7519.html", "0.1639", "2026-09-05"),
    "VEML7700-TR": ("LCSC", "C504893", "https://www.lcsc.com/product-detail/C504893.html", "0.7256", PRICE_SNAPSHOT_DATE),
}


def find_symbol_dir(explicit: str | None) -> Path:
    for candidate in (explicit, os.environ.get("KICAD_SYMBOL_DIR"), "/usr/share/kicad/symbols"):
        if candidate and Path(candidate).is_dir():
            return Path(candidate)
    raise SystemExit("KiCad symbol libraries not found; pass --symbol-dir")


def q(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def custom_symbol(name: str, ref: str, footprint: str, datasheet: str,
                  description: str, pins: list[tuple[str, str, str, str]]) -> str:
    sides = {side: [p for p in pins if p[3] == side] for side in "LRTB"}
    rows = max(len(sides["L"]), len(sides["R"]), 4)
    half_h = max(7.62, (rows + 1) * 1.27)
    half_w = 15.24
    out = [
        f'  (symbol "{q(name)}" (pin_names (offset 1.016)) (in_bom yes) (on_board yes)',
        f'    (property "Reference" "{q(ref)}" (at {-half_w} {half_h + 2.54} 0) (effects (font (size 1.27 1.27)) (justify left bottom)))',
        f'    (property "Value" "{q(name)}" (at {half_w} {-half_h - 2.54} 0) (effects (font (size 1.27 1.27)) (justify right top)))',
        f'    (property "Footprint" "{q(footprint)}" (at 0 {-half_h - 5.08} 0) (effects (font (size 1.27 1.27)) hide))',
        f'    (property "Datasheet" "{q(datasheet)}" (at 0 {-half_h - 7.62} 0) (effects (font (size 1.27 1.27)) hide))',
        f'    (property "ki_description" "{q(description)}" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))',
        f'    (symbol "{q(name)}_0_1" (rectangle (start {-half_w} {half_h}) (end {half_w} {-half_h}) (stroke (width 0.254) (type default)) (fill (type background))))',
        f'    (symbol "{q(name)}_1_1"',
    ]

    def pin_line(pin: tuple[str, str, str, str], idx: int, count: int) -> str:
        number, pname, ptype, side = pin
        if side == "L":
            x, y, angle = -half_w - 5.08, (count - 1 - 2 * idx) * 1.27, 0
        elif side == "R":
            x, y, angle = half_w + 5.08, (count - 1 - 2 * idx) * 1.27, 180
        elif side == "T":
            x, y, angle = (idx - count // 2) * 2.54, half_h + 5.08, 270
        else:
            x, y, angle = (idx - count // 2) * 2.54, -half_h - 5.08, 90
        shape = "inverted" if pname.endswith("_N") else "line"
        return (
            f'      (pin {ptype} {shape} (at {x:.3f} {y:.3f} {angle}) (length 5.08) '
            f'(name "{q(pname)}" (effects (font (size 1.016 1.016)))) '
            f'(number "{q(number)}" (effects (font (size 1.016 1.016)))))'
        )

    for side in "LRTB":
        for idx, pin in enumerate(sides[side]):
            out.append(pin_line(pin, idx, len(sides[side])))
    out += ["    )", "  )"]
    return "\n".join(out)


def write_custom_library(here: Path) -> None:
    lib = here / "lib"
    lib.mkdir(parents=True, exist_ok=True)
    symbols: list[str] = []

    esp_io = {
        5: "GPIO2", 6: "GPIO3", 12: "GPIO0", 13: "GPIO1", 16: "GPIO10",
        18: "GPIO4", 19: "GPIO5", 20: "GPIO6", 21: "GPIO7", 22: "GPIO8",
        23: "GPIO9", 26: "USB_D-", 27: "USB_D+", 30: "U0RXD_GPIO20",
        31: "U0TXD_GPIO21",
    }
    esp_nc = {4, 7, 9, 10, 15, 17, 24, 25, 28, 29, 32, 33, 34, 35}
    esp_gnd = {1, 2, 11, 14, *range(36, 54)}
    esp_pins: list[tuple[str, str, str, str]] = []
    for number in range(1, 54):
        if number == 3:
            esp_pins.append(("3", "3V3", "power_in", "T"))
        elif number == 8:
            esp_pins.append(("8", "EN", "input", "L"))
        elif number in esp_io:
            side = "L" if number <= 19 else "R"
            esp_pins.append((str(number), esp_io[number], "bidirectional", side))
        elif number in esp_nc:
            esp_pins.append((str(number), "NC", "passive", "L"))
        elif number in esp_gnd:
            esp_pins.append((str(number), "GND", "power_in", "B"))
        else:
            raise AssertionError(number)
    symbols.append(custom_symbol(
        "ESP32-C3-MINI-1-H4X", "U", "pot-pulse:ESP32-C3-MINI-1",
        "https://www.espressif.com/sites/default/files/documentation/esp32-c3-mini-1_datasheet_en.pdf",
        "Espressif ESP32-C3-MINI-1 H4X module; 53-pad map from datasheet v2.2 Table 3-1",
        esp_pins,
    ))
    symbols.append(custom_symbol(
        "TPS62162DSGR", "U", "Package_SON:WSON-8-1EP_2x2mm_P0.5mm_EP0.9x1.6mm_ThermalVias",
        "https://www.ti.com/lit/ds/symlink/tps62160.pdf",
        "TI fixed 3.3 V 1 A buck, DSG WSON-8 exposed pad",
        [("1", "PGND", "power_in", "B"), ("2", "VIN", "power_in", "L"),
         ("3", "EN", "input", "L"), ("4", "AGND", "power_in", "B"),
         ("5", "FB", "input", "L"), ("6", "VOS", "input", "R"),
         ("7", "SW", "power_out", "R"), ("8", "PG", "open_collector", "R"),
         ("9", "EP_GND", "power_in", "B")],
    ))
    symbols.append(custom_symbol(
        "ADS1115IDGSR", "U", "Package_SO:VSSOP-10_3x3mm_P0.5mm",
        "https://www.ti.com/lit/ds/symlink/ads1115.pdf",
        "TI ADS1115 16-bit four-channel ADC, DGS VSSOP-10",
        [("1", "ADDR", "input", "L"), ("2", "ALERT/RDY_N", "open_collector", "R"),
         ("3", "GND", "power_in", "B"), ("4", "AIN0", "input", "L"),
         ("5", "AIN1", "input", "L"), ("6", "AIN2", "input", "L"),
         ("7", "AIN3", "input", "L"), ("8", "VDD", "power_in", "T"),
         ("9", "SDA", "bidirectional", "R"), ("10", "SCL", "input", "R")],
    ))
    symbols.append(custom_symbol(
        "SHT40-AD1B-R2", "U", "Sensor_Humidity:Sensirion_DFN-4_1.5x1.5mm_P0.8mm_SHT4x_NoCentralPad",
        "https://sensirion.com/media/documents/33FD6951/6A7C10A0/HT_DS_Datasheet_SHT4x_V7.3.pdf",
        "Sensirion SHT40 temperature/humidity sensor",
        [("1", "SDA", "bidirectional", "L"), ("2", "SCL", "input", "L"),
         ("3", "VDD", "power_in", "T"), ("4", "VSS", "power_in", "B")],
    ))
    symbols.append(custom_symbol(
        "VEML7700-TR", "U", "pot-pulse:VEML7700",
        "https://www.vishay.com/docs/84286/veml7700.pdf",
        "Vishay VEML7700 side-view ambient-light sensor",
        [("1", "SCL", "input", "L"), ("2", "VDD", "power_in", "T"),
         ("3", "GND", "power_in", "B"), ("4", "SDA", "bidirectional", "L")],
    ))
    symbols.append(custom_symbol(
        "TPD4E05U06DQAR", "U", "Package_SON:USON-10_2.5x1.0mm_P0.5mm",
        "https://www.ti.com/lit/ds/symlink/tpd4e05u06.pdf",
        "TI four-channel low-capacitance ESD protector, DQA USON-10",
        [("1", "D1+", "passive", "L"), ("2", "D1-", "passive", "L"),
         ("3", "GND", "power_in", "B"), ("4", "D2+", "passive", "L"),
         ("5", "D2-", "passive", "L"), ("6", "NC", "passive", "R"),
         ("7", "NC", "passive", "R"), ("8", "GND", "power_in", "B"),
         ("9", "NC", "passive", "R"), ("10", "NC", "passive", "R")],
    ))
    symbols.append(custom_symbol(
        "USBLC6-2SC6", "U", "Package_TO_SOT_SMD:SOT-23-6",
        "https://www.st.com/resource/en/datasheet/usblc6-2.pdf",
        "ST USBLC6-2SC6 two-line USB 2.0 ESD protection",
        [("1", "I/O1", "passive", "L"), ("2", "GND", "power_in", "B"),
         ("3", "I/O2", "passive", "L"), ("4", "I/O2", "passive", "R"),
         ("5", "VBUS", "power_in", "T"), ("6", "I/O1", "passive", "R")],
    ))
    (lib / "pot-pulse.kicad_sym").write_text(
        "(kicad_symbol_lib (version 20220914) (generator kicad_symbol_editor)\n"
        + "\n".join(symbols) + "\n)\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol-dir")
    parser.add_argument("--output", default=str(Path(__file__).with_name("pot-pulse.kicad_sch")))
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    write_custom_library(here)
    symbol_dir = find_symbol_dir(args.symbol_dir)
    os.environ["KICAD_SYMBOL_DIR"] = str(symbol_dir)

    from kicad_sch_api import create_schematic, get_symbol_cache
    cache = get_symbol_cache()
    cache.discover_libraries([str(symbol_dir)])
    if not cache.add_library_path(str(here / "lib" / "pot-pulse.kicad_sym")):
        raise SystemExit("Could not load project symbol library")

    sch = create_schematic("Pot Pulse first-pass schematic")
    sch.set_paper_size("A3")
    sch.set_title_block(
        title="Pot Pulse USB/SELV four-zone sensor node",
        date="2026-09-07", rev="A0 schematic",
        company="Open hardware design — rwrife/pot-pulse",
        comments={
            1: "USB 5 V SELV only; indoor informational monitor; no mains or actuators",
            2: "Four SEN0193 probes powered at 3.3 V; calibrate each zone in firmware",
            3: "Static schematic/ERC evidence only; PCB, bench, EMC and field validation pending",
        },
    )

    comps: dict[str, object] = {}
    labels: set[tuple[float, float, str]] = set()
    no_connects: set[tuple[float, float]] = set()

    def add(lib_id: str, ref: str, value: str, pos: tuple[float, float], footprint: str,
            manufacturer: str, mpn: str, datasheet: str, notes: str, *,
            supplier: str = "", supplier_pn: str = "", in_bom: bool = True):
        c = sch.components.add(lib_id, ref, value, position=pos, footprint=footprint)
        source_url = datasheet
        estimated_unit_cost = "TBD - live quote required"
        price_snapshot = PRICE_SNAPSHOT_DATE
        if sourcing := SOURCING.get(mpn):
            supplier, supplier_pn, source_url, estimated_unit_cost, price_snapshot = sourcing
        elif in_bom:
            supplier = supplier or "Unassigned"
        for key, val in {
            "Manufacturer": manufacturer, "MPN": mpn, "Datasheet": datasheet,
            "Supplier": supplier, "Supplier PN": supplier_pn,
            "Source URL": source_url,
            "Estimated Unit Cost USD": estimated_unit_cost,
            "Price Snapshot Date": price_snapshot,
            "BOM Comments": notes,
        }.items():
            c.set_property(key, val)
        c.in_bom = in_bom
        comps[ref] = c
        return c

    def point(ref: str, pin: str):
        from kicad_sch_api.core.types import Point
        c = comps[ref]
        p = c.get_pin(str(pin))
        if p is None:
            raise ValueError(f"{ref} pin {pin} missing")
        return Point(c.position.x + p.position.x, c.position.y - p.position.y)

    def connect(ref: str, pin: str, net: str) -> None:
        p = point(ref, pin)
        key = (round(p.x, 6), round(p.y, 6), net)
        if key not in labels:
            sch.labels.add(net, (p.x, p.y))
            labels.add(key)

    def nc(ref: str, pin: str) -> None:
        p = point(ref, pin)
        key = (round(p.x, 6), round(p.y, 6))
        if key not in no_connects:
            sch.no_connects.add((p.x, p.y))
            no_connects.add(key)

    def resistor(ref: str, value: str, pos: tuple[float, float], mpn: str, notes: str):
        return add("Device:R", ref, value, pos, "Resistor_SMD:R_0603_1608Metric",
                   "Yageo", mpn, RES_DS, notes)

    def capacitor(ref: str, value: str, pos: tuple[float, float], mpn: str, notes: str,
                  footprint: str = "Capacitor_SMD:C_0603_1608Metric"):
        return add("Device:C", ref, value, pos, footprint, "Murata", mpn, CAP_DS, notes)

    # USB-C power/data entry and protected 5 V rail.
    add("Connector:USB_C_Receptacle_USB2.0_16P", "J1", "USB-C POWER + NATIVE USB", (35, 48),
        "Connector_USB:USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal",
        "Global Connector Technology", "USB4105-GF-A", "https://gct.co/files/specs/usb4105-spec.pdf",
        "USB 2.0 sink; CC1/CC2 each use 5.1 kΩ Rd; shield tied to GND.", supplier="LCSC", supplier_pn="C3020560")
    resistor("R1", "5.1k 1%", (62, 35), "RC0603FR-075K1L", "USB-C CC1 Rd to GND.")
    resistor("R2", "5.1k 1%", (75, 35), "RC0603FR-075K1L", "USB-C CC2 Rd to GND.")
    add("Device:Polyfuse", "F1", "500mA hold / 1A trip", (78, 48), "Fuse:Fuse_1812_4532Metric",
        "Bourns", "MF-MSMF050-2", "https://bourns.com/docs/product-datasheets/mf-msmf.pdf",
        "Resettable USB input protection; bench-check radio-burst margin and nuisance trips.", supplier="LCSC", supplier_pn="C17313")
    add("Device:D_TVS", "D1", "ESD5Z5.0T1G", (93, 59), "Diode_SMD:D_SOD-523",
        "onsemi", "ESD5Z5.0T1G", "https://www.onsemi.com/pdf/datasheet/esd5z2.5t1-d.pdf",
        "5 V VBUS transient clamp after PPTC; short ground return.", supplier="LCSC", supplier_pn="C82044")
    add("pot-pulse:USBLC6-2SC6", "U7", "USBLC6-2SC6", (76, 78), "Package_TO_SOT_SMD:SOT-23-6",
        "STMicroelectronics", "USBLC6-2SC6", "https://www.st.com/resource/en/datasheet/usblc6-2.pdf",
        "Native USB D+/D- ESD array at J1; route as a short differential pair.", supplier="LCSC", supplier_pn="C7519")

    # Fixed 3.3 V buck and local rail capacitance.
    add("pot-pulse:TPS62162DSGR", "U1", "TPS62162DSGR 3.3V", (127, 50),
        "Package_SON:WSON-8-1EP_2x2mm_P0.5mm_EP0.9x1.6mm_ThermalVias",
        "Texas Instruments", "TPS62162DSGR", "https://www.ti.com/lit/ds/symlink/tps62160.pdf",
        "Fixed 3.3 V buck; FB and exposed pad to AGND; short SW loop required.", supplier="LCSC", supplier_pn="C40256")
    add("Device:L", "L1", "2.2uH 1.3A", (158, 50), "Inductor_SMD:L_1008_2520Metric",
        "TDK", "VLS252012T-2R2M1R3", "https://product.tdk.com/en/search/inductor/inductor/smd/info?part_no=VLS252012T-2R2M1R3",
        "Datasheet-recommended TPS6216x inductor; verify saturation margin in layout/power review.")
    capacitor("C1", "10uF 10V X5R", (112, 68), "GRM31CR61A106KA01L", "Buck input bulk capacitor.", "Capacitor_SMD:C_1206_3216Metric")
    capacitor("C2", "100nF 50V X7R", (122, 68), "GRM188R71H104KA93D", "Buck high-frequency input bypass.")
    capacitor("C3", "22uF 16V X5R", (171, 63), "GRM31CR61C226ME15L", "Buck output capacitor; 22 µF nominal per TI typical application.", "Capacitor_SMD:C_1206_3216Metric")
    resistor("R3", "100k 1%", (146, 68), "RC0603FR-07100KL", "TPS62162 open-drain PG pull-up.")

    # Controller, reset/boot bias and debug access.
    add("pot-pulse:ESP32-C3-MINI-1-H4X", "U2", "ESP32-C3-MINI-1-H4X", (219, 78), "pot-pulse:ESP32-C3-MINI-1",
        "Espressif Systems", "ESP32-C3-MINI-1-H4X",
        "https://www.espressif.com/sites/default/files/documentation/esp32-c3-mini-1_datasheet_en.pdf",
        "4 MB H4X module; native USB on GPIO18/19; antenna keepout is mandatory.", supplier="LCSC", supplier_pn="C41349510")
    capacitor("C4", "10uF 10V X5R", (190, 27), "GRM31CR61A106KA01L", "ESP32-C3 local rail bulk capacitor.", "Capacitor_SMD:C_1206_3216Metric")
    capacitor("C5", "100nF 50V X7R", (202, 27), "GRM188R71H104KA93D", "ESP32-C3 high-frequency decoupling.")
    resistor("R6", "10k 1%", (215, 27), "RC0603FR-0710KL", "EN pull-up; EN must not float.")
    capacitor("C6", "1uF 16V X7R", (227, 27), "GRM188R71C105KA12D", "EN power-on reset delay capacitor; bench-verify startup timing.")
    resistor("R7", "10k 1%", (239, 27), "RC0603FR-0710KL", "GPIO9 boot-strapping pull-up; debug header can pull low.")
    add("Connector_Generic:Conn_01x06", "J6", "DEBUG / PROGRAM PADS", (286, 45), "Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical",
        "N/A", "PCB_DEBUG_PADS", "~", "Unpopulated labeled pads: 3V3, GND, EN, BOOT, U0RXD and U0TXD.", in_bom=False)

    # Four external probes, connector-boundary ESD and per-channel RC filters.
    add("pot-pulse:TPD4E05U06DQAR", "U3", "TPD4E05U06DQAR", (80, 148), "Package_SON:USON-10_2.5x1.0mm_P0.5mm",
        "Texas Instruments", "TPD4E05U06DQAR", "https://www.ti.com/lit/ds/symlink/tpd4e05u06.pdf",
        "Four low-leakage ESD channels at probe connector boundary.", supplier="LCSC", supplier_pn="C138714")
    for idx, y in enumerate((125, 142, 159, 176), 1):
        add("Connector_Generic:Conn_01x03", f"J{idx+1}", f"ZONE {idx} SEN0193", (36, y),
            "Connector_JST:JST_PH_S3B-PH-K_1x03_P2.00mm_Horizontal",
            "JST", "S3B-PH-K-S(LF)(SN)", "https://www.jst-mfg.com/product/pdf/eng/ePH.pdf",
            f"Zone {idx}: pin 1=3V3, pin 2=GND, pin 3=analog signal; verify mating cable orientation before assembly.",
            supplier="LCSC", supplier_pn="C157929")
        resistor(f"R{8+idx}", "1k 1%", (111, y), "RC0603FR-071KL", f"Zone {idx} ADC series filter resistor after ESD.")
        capacitor(f"C{9+idx}", "100nF 50V X7R", (130, y), "GRM188R71H104KA93D", f"Zone {idx} ADC shunt filter capacitor; settling to be bench characterized.")

    # ADC and shared I2C environmental sensors.
    add("pot-pulse:ADS1115IDGSR", "U4", "ADS1115IDGSR", (173, 150), "Package_SO:VSSOP-10_3x3mm_P0.5mm",
        "Texas Instruments", "ADS1115IDGSR", "https://www.ti.com/lit/ds/symlink/ads1115.pdf",
        "ADDR=GND gives 0x48; four independent single-ended probe channels.", supplier="LCSC", supplier_pn="C37593")
    capacitor("C7", "100nF 50V X7R", (173, 119), "GRM188R71H104KA93D", "ADS1115 local VDD bypass per datasheet.")
    resistor("R8", "10k 1%", (196, 119), "RC0603FR-0710KL", "ADS1115 ALERT/RDY open-drain pull-up.")
    resistor("R4", "4.7k 1%", (225, 126), "RC0603FR-074K7L", "Single assembled I2C SDA pull-up to 3V3.")
    resistor("R5", "4.7k 1%", (238, 126), "RC0603FR-074K7L", "Single assembled I2C SCL pull-up to 3V3.")
    add("pot-pulse:SHT40-AD1B-R2", "U5", "SHT40-AD1B-R2", (226, 158),
        "Sensor_Humidity:Sensirion_DFN-4_1.5x1.5mm_P0.8mm_SHT4x_NoCentralPad",
        "Sensirion", "SHT40-AD1B-R2", "https://sensirion.com/media/documents/33FD6951/6A7C10A0/HT_DS_Datasheet_SHT4x_V7.3.pdf",
        "I2C 0x44; open-cavity sensor; keep away from regulator and heat sources.", supplier="LCSC", supplier_pn="C2909890")
    capacitor("C8", "100nF 50V X7R", (226, 181), "GRM188R71H104KA93D", "SHT40 local supply decoupling.")
    add("pot-pulse:VEML7700-TR", "U6", "VEML7700-TR", (278, 158), "pot-pulse:VEML7700",
        "Vishay", "VEML7700-TR", "https://www.vishay.com/docs/84286/veml7700.pdf",
        "Fixed I2C 0x10; side-view optical aperture must face enclosure opening.", supplier="LCSC", supplier_pn="C504893")
    capacitor("C9", "100nF 50V X7R", (278, 181), "GRM188R71H104KA93D", "VEML7700 local supply decoupling.")

    # Explicit connectivity: USB connector, power tree and USB protection.
    for pin in ("A4", "A9", "B4", "B9"): connect("J1", pin, "VBUS")
    for pin in ("A1", "A12", "B1", "B12", "S1"): connect("J1", pin, "GND")
    connect("J1", "A5", "CC1"); connect("J1", "B5", "CC2")
    for pin in ("A6", "B6"): connect("J1", pin, "USB_CONN_DP")
    for pin in ("A7", "B7"): connect("J1", pin, "USB_CONN_DM")
    for pin in ("A8", "B8"): nc("J1", pin)
    connect("R1", "1", "CC1"); connect("R1", "2", "GND")
    connect("R2", "1", "CC2"); connect("R2", "2", "GND")
    connect("F1", "1", "VBUS"); connect("F1", "2", "+5V_PROTECTED")
    connect("D1", "1", "+5V_PROTECTED"); connect("D1", "2", "GND")
    for pin, net in {"1":"USB_CONN_DM", "6":"USB_DM", "3":"USB_CONN_DP", "4":"USB_DP", "2":"GND", "5":"+5V_PROTECTED"}.items(): connect("U7", pin, net)

    for pin, net in {"1":"GND", "2":"+5V_PROTECTED", "3":"+5V_PROTECTED", "4":"GND", "5":"GND", "6":"+3V3", "7":"SW_NODE", "8":"REG_PG", "9":"GND"}.items(): connect("U1", pin, net)
    connect("L1", "1", "SW_NODE"); connect("L1", "2", "+3V3")
    for ref in ("C1", "C2"): connect(ref, "1", "+5V_PROTECTED"); connect(ref, "2", "GND")
    connect("C3", "1", "+3V3"); connect("C3", "2", "GND")
    connect("R3", "1", "+3V3"); connect("R3", "2", "REG_PG")

    connect("U2", "3", "+3V3")
    connect("U2", "8", "EN")
    gpio_nets = {18:"I2C_SDA", 19:"I2C_SCL", 20:"ADC_ALERT_N", 23:"BOOT_GPIO9",
                 26:"USB_DM", 27:"USB_DP", 30:"U0RXD", 31:"U0TXD"}
    for pin, net in gpio_nets.items(): connect("U2", str(pin), net)
    for pin in (5, 6, 12, 13, 16, 21, 22): nc("U2", str(pin))
    for pin in (1, 2, 11, 14, *range(36, 54)): connect("U2", str(pin), "GND")
    for pin in (4, 7, 9, 10, 15, 17, 24, 25, 28, 29, 32, 33, 34, 35): nc("U2", str(pin))
    for ref in ("C4", "C5"): connect(ref, "1", "+3V3"); connect(ref, "2", "GND")
    connect("R6", "1", "+3V3"); connect("R6", "2", "EN")
    connect("C6", "1", "EN"); connect("C6", "2", "GND")
    connect("R7", "1", "+3V3"); connect("R7", "2", "BOOT_GPIO9")
    for pin, net in {"1":"+3V3", "2":"GND", "3":"EN", "4":"BOOT_GPIO9", "5":"U0RXD", "6":"U0TXD"}.items(): connect("J6", pin, net)

    for idx in range(1, 5):
        j = f"J{idx+1}"; raw = f"PROBE{idx}_RAW"; adc = f"MOISTURE_AIN{idx-1}"
        connect(j, "1", "+3V3"); connect(j, "2", "GND"); connect(j, "3", raw)
        connect("U3", str([1,2,4,5][idx-1]), raw)
        r = f"R{8+idx}"; c = f"C{9+idx}"
        connect(r, "1", raw); connect(r, "2", adc)
        connect(c, "1", adc); connect(c, "2", "GND")
    connect("U3", "3", "GND"); connect("U3", "8", "GND")
    for pin in (6, 7, 9, 10): nc("U3", str(pin))

    for pin, net in {"1":"GND", "2":"ADC_ALERT_N", "3":"GND", "4":"MOISTURE_AIN0", "5":"MOISTURE_AIN1", "6":"MOISTURE_AIN2", "7":"MOISTURE_AIN3", "8":"+3V3", "9":"I2C_SDA", "10":"I2C_SCL"}.items(): connect("U4", pin, net)
    connect("C7", "1", "+3V3"); connect("C7", "2", "GND")
    connect("R8", "1", "+3V3"); connect("R8", "2", "ADC_ALERT_N")
    connect("R4", "1", "+3V3"); connect("R4", "2", "I2C_SDA")
    connect("R5", "1", "+3V3"); connect("R5", "2", "I2C_SCL")
    for pin, net in {"1":"I2C_SDA", "2":"I2C_SCL", "3":"+3V3", "4":"GND"}.items(): connect("U5", pin, net)
    connect("C8", "1", "+3V3"); connect("C8", "2", "GND")
    for pin, net in {"1":"I2C_SCL", "2":"+3V3", "3":"GND", "4":"I2C_SDA"}.items(): connect("U6", pin, net)
    connect("C9", "1", "+3V3"); connect("C9", "2", "GND")

    # ERC source declarations and named test access.
    for idx, (net, pos) in enumerate((("VBUS", (110, 88)), ("+5V_PROTECTED", (128, 88)), ("+3V3", (146, 88)), ("GND", (164, 88))), 1):
        ref = f"#FLG0{idx}"
        add("power:PWR_FLAG", ref, "PWR_FLAG", pos, "", "N/A", "PCB_NET_FLAG", "~",
            "ERC-only source declaration; not a purchased component.", in_bom=False)
        connect(ref, "1", net)
    test_nets = ["VBUS", "+5V_PROTECTED", "+3V3", "GND", "I2C_SDA", "I2C_SCL", "USB_DP", "USB_DM",
                 "REG_PG", "EN", "BOOT_GPIO9", "ADC_ALERT_N", "MOISTURE_AIN0", "MOISTURE_AIN1", "MOISTURE_AIN2", "MOISTURE_AIN3"]
    for idx, net in enumerate(test_nets, 1):
        ref = f"TP{idx}"
        add("Connector:TestPoint", ref, net, (28 + ((idx-1) % 8) * 35, 215 + ((idx-1)//8)*14),
            "TestPoint:TestPoint_Pad_D1.5mm", "N/A", "PCB_TEST_PAD", "~",
            "Unpopulated labeled PCB test pad; electrical limits follow connected net.", in_bom=False)
        connect(ref, "1", net)

    sch.add_text("USB-C 5 V SELV / PPTC / TVS / NATIVE USB ESD", (20, 18), size=1.7, bold=True)
    sch.add_text("TPS62162 FIXED 3.3 V BUCK + ESP32-C3-MINI-1", (98, 18), size=1.7, bold=True)
    sch.add_text("FOUR PROBE INPUTS / LOW-LEAKAGE ESD / RC / ADS1115", (20, 105), size=1.7, bold=True)
    sch.add_text("SHARED I2C: ADS1115 0x48 / SHT40 0x44 / VEML7700 0x10", (158, 105), size=1.7, bold=True)
    sch.add_text("STATIC SCHEMATIC/ERC EVIDENCE ONLY — PCB, SIMULATION, BENCH AND FIELD VALIDATION REMAIN PENDING", (20, 252), size=1.0, bold=True)

    issues = sch.validate()
    errors = [issue for issue in issues if getattr(issue, "severity", "") == "error"]
    if errors:
        raise SystemExit("Schematic API validation failed: " + "; ".join(map(str, errors)))
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    sch.save_as(out)
    print(f"generated {out} with {len(comps)} symbols; api_validation_issues={len(issues)} errors=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
