#!/usr/bin/env python3
"""Generate the project-owned KiCad footprint libraries for Pot Pulse.

Two land patterns have no official KiCad library equivalent and were
explicitly handed from the schematic issue (#3) to the PCB issue (#5):

- ``pot-pulse:VEML7700`` — Vishay VEML7700 ambient light sensor.
  Pad geometry is transcribed from the manufacturer-validated SparkFun
  VEML7700 breakout board files (``SparkFun-Sensor:VEML7700-TT``), which
  follow Vishay's package drawing: 4 pads, 1.27 mm pitch, 0.7 × 1.6 mm,
  pin 1 SCL / 2 VDD / 3 GND / 4 SDA per datasheet 84286 Rev 1.8.
- ``pot-pulse:ESP32-C3-MINI-1`` — copy of Espressif's official
  ``Espressif.pretty/ESP32-C3-MINI-1.kicad_mod`` from the espressif
  kicad-libraries repository (designed against datasheet land pattern
  Figure 11-1), vendored under the project library id used by the
  schematic's Footprint property.

Run with no arguments to regenerate ``lib/pot-pulse.pretty`` in place.
The generator verifies the regenerated pad maps against the schematic
symbol pin sets before writing.
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRETTY = HERE / "lib" / "pot-pulse.pretty"
SYMBOLS = HERE / "lib" / "pot-pulse.kicad_sym"

ESPRESSIF_LIB_URL = "https://github.com/espressif/kicad-libraries/archive/refs/heads/main.zip"

# Transcribed from SparkFun-Sensor:VEML7700-TT (SparkFun Ambient Light
# Sensor - VEML7700 hardware files, CC-BY-SA 4.0), which implements the
# Vishay 84286 package drawing. Positions/sizes in mm, KiCad convention.
VEML7700_PADS = [  # (number, x, y, rotation, w_along_pad, h_across_pad)
    ("1", -1.961, 1.095, 90, 1.6, 0.7),   # SCL
    ("2", -0.691, 1.095, 90, 1.6, 0.7),   # VDD
    ("3", 0.579, 1.095, 90, 1.6, 0.7),    # GND
    ("4", 1.849, 1.095, 90, 1.6, 0.7),    # SDA
]
VEML7700_BODY = (-3.456, -1.305, 3.344, 1.695)      # F.Fab / F.SilkS outline
VEML7700_COURTYARD = (-3.612, -1.456, 3.5, 2.1)     # F.CrtYd

DESCR_VEML = (
    "VEML7700 high accuracy ambient light sensor, I2C, 6.8x2.35x3.0 mm "
    "side-view package. Land pattern transcribed from SparkFun "
    "VEML7700 breakout (Vishay drawing 9.700-5341). Datasheet: "
    "https://www.vishay.com/docs/84286/veml7700.pdf"
)


def s_expr_pad(number: str, x: float, y: float, rot: int, w: float, h: float) -> str:
    return (
        f'  (pad "{number}" smd rect (at {x} {y} {rot}) '
        f'(size {w} {h}) (layers "F.Cu" "F.Paste" "F.Mask"))'
    )


def line(start: tuple[float, float], end: tuple[float, float], width: float, layer: str) -> str:
    return (f'  (fp_line (start {start[0]} {start[1]}) (end {end[0]} {end[1]}) '
            f'(stroke (width {width}) (type solid)) (layer "{layer}"))')


def rect(r: tuple[float, float, float, float], width: float, layer: str) -> list[str]:
    x1, y1, x2, y2 = r
    return [line((x1, y1), (x2, y1), width, layer),
            line((x2, y1), (x2, y2), width, layer),
            line((x2, y2), (x1, y2), width, layer),
            line((x1, y2), (x1, y1), width, layer)]


def veml7700_mod() -> str:
    # Silk follows the SparkFun reference: a full outline on the pad-free
    # long edge and the two short edges, with only outer stubs on the
    # pad side so no silk crosses a pad (KiCad 9 silk-over-pad DRC).
    x1, y1, x2, y2 = VEML7700_BODY          # y2 = pad side
    cx1, cy1, cx2, cy2 = VEML7700_COURTYARD
    pad_min_x = min(px for _, px, _, _, _, _ in VEML7700_PADS) - 0.35   # -2.311
    pad_max_x = max(px for _, px, _, _, _, _ in VEML7700_PADS) + 0.35   # 2.199
    lines = [
        '(footprint "VEML7700" (version 20230121) (generator "pot-pulse")',
        '  (layer "F.Cu")',
        f'  (descr "{DESCR_VEML}")',
        '  (attr smd)',
        '  (fp_text reference "REF**" (at 0 -2.6) (layer "F.SilkS")'
        '    (effects (font (size 1 1) (thickness 0.15))))',
        '  (fp_text value "VEML7700" (at 0 2.8) (layer "F.Fab")'
        '    (effects (font (size 1 1) (thickness 0.15))))',
    ]
    lines += [
        line((x1, y1), (x1, y2), 0.12, "F.SilkS"),
        line((x2, y1), (x2, y2), 0.12, "F.SilkS"),
        line((x1, y1), (x2, y1), 0.12, "F.SilkS"),
        line((x1, y2), (pad_min_x - 0.25, y2), 0.12, "F.SilkS"),
        line((pad_max_x + 0.25, y2), (x2, y2), 0.12, "F.SilkS"),
    ]
    lines += rect(VEML7700_BODY, 0.1, "F.Fab")
    lines += rect(VEML7700_COURTYARD, 0.05, "F.CrtYd")
    # pin-1 marker dot beside pad 1 (matches reference footprint placement)
    lines.append('  (fp_circle (center -2.7 2.2) (end -2.6 2.3) (stroke (width 0.15) (type solid)) (layer "F.SilkS"))')
    for n, px, py, rot, w, h in VEML7700_PADS:
        lines.append(s_expr_pad(n, px, py, rot, w, h))
    lines.append(')')
    return "\n".join(lines) + "\n"


def fetch_espressif_mini1() -> str:
    req = urllib.request.Request(
        ESPRESSIF_LIB_URL, headers={"User-Agent": "pot-pulse-footprint-sync"}
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        zdata = resp.read()
    with zipfile.ZipFile(__import__("io").BytesIO(zdata)) as zf:
        name = next(n for n in zf.namelist() if n.endswith("Espressif.pretty/ESP32-C3-MINI-1.kicad_mod"))
        return zf.read(name).decode("utf-8")


ESP_FALLBACK_URL = (
    "https://raw.githubusercontent.com/espressif/kicad-libraries/main/"
    "footprints/Espressif.pretty/ESP32-C3-MINI-1.kicad_mod"
)


def symbol_pin_numbers(symbol_base: str) -> set[str]:
    txt = SYMBOLS.read_text()
    nums: set[str] = set()
    for m in re.finditer(r'\(symbol "' + re.escape(symbol_base) + r'(?:_\d+_\d+)?"', txt):
        i = m.start(); depth = 0; j = i
        while True:
            if txt[j] == "(":
                depth += 1
            elif txt[j] == ")":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        nums |= set(re.findall(r'\(number "(\d+)"', txt[i:j + 1]))
    return nums


def pad_numbers(mod_text: str) -> set[str]:
    return set(re.findall(r'\(pad "([^"]+)"', mod_text))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--offline-esp-mod", help="local ESP32-C3-MINI-1.kicad_mod to vendor instead of fetching")
    args = ap.parse_args()

    PRETTY.mkdir(parents=True, exist_ok=True)

    if args.offline_esp_mod:
        esp = Path(args.offline_esp_mod).read_text()
    else:
        try:
            esp = fetch_espressif_mini1()
        except Exception as exc:  # noqa: BLE001
            print(f"zip fetch failed ({exc}); trying raw URL", file=sys.stderr)
            with urllib.request.urlopen(urllib.request.Request(
                    ESP_FALLBACK_URL, headers={"User-Agent": "pot-pulse-footprint-sync"}), timeout=120) as resp:
                esp = resp.read().decode("utf-8")

    # Gate 0a: footprint pads must match the schematic symbols exactly.
    esp_nums = pad_numbers(esp)
    esp_sym = symbol_pin_numbers("ESP32-C3-MINI-1-H4X")
    if esp_nums != esp_sym:
        print(f"pad/symbol mismatch ESP32-C3-MINI-1: missing {sorted(esp_sym - esp_nums, key=int)} extra {sorted(esp_nums - esp_sym, key=int)}", file=sys.stderr)
        return 1

    veml = veml7700_mod()
    veml_nums = pad_numbers(veml)
    veml_sym = symbol_pin_numbers("VEML7700-TR")
    if veml_nums != veml_sym:
        print(f"pad/symbol mismatch VEML7700: missing {sorted(veml_sym - veml_nums)} extra {sorted(veml_nums - veml_sym)}", file=sys.stderr)
        return 1

    (PRETTY / "ESP32-C3-MINI-1.kicad_mod").write_text(esp)
    (PRETTY / "VEML7700.kicad_mod").write_text(veml)
    print(f"wrote {PRETTY}/ESP32-C3-MINI-1.kicad_mod ({len(esp_nums)} pads)")
    print(f"wrote {PRETTY}/VEML7700.kicad_mod ({len(veml_nums)} pads)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
