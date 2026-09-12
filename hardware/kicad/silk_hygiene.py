#!/usr/bin/env python3
"""Post-route silkscreen hygiene for pot-pulse.kicad_pcb.

Policy (from the verified workflow):
- Dense passives (R*/C*/L*/F*/D*): hide the Reference field entirely — they
  are 0603/1206 parts in dense lanes and their silk collides with neighbours.
  Values stay visible on F.Fab; the BOM carries designator-to-place data.
- Test points (TP*) and user-facing parts: KEEP references visible (test
  point identity is part of testability) but shrink to 0.8 mm / 0.15 mm
  stroke to collapse silk_over_copper / silk_overlap warnings.
- Standalone board gr_text labels: ensure >= 0.15 mm stroke (a (size .8 .15)
  label with no explicit thickness renders at ~0.019 mm and trips
  text_thickness DRC).

Run AFTER the final route import (route geometry shifts make pre-route
cleanup moot). Re-run DRC afterwards.

    python3 silk_hygiene.py
"""
import re
from pathlib import Path

import pcbnew

HERE = Path(__file__).resolve().parent
BOARD = HERE / "pot-pulse.kicad_pcb"
NM = 1e6

DENSE_RE = re.compile(r"^[RCLFDM]\d+$")  # R1 C12 L1 F1 D1 MK1? keep MK — no: MK handled below


def main() -> int:
    board = pcbnew.LoadBoard(str(BOARD))
    hidden = shrunk = text_fixed = 0
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        want_hide = bool(re.fullmatch(r"[RCLFD]\d+", ref))
        want_shrink = bool(re.fullmatch(r"TP\d+|MK\d+|J\d+|U\d+", ref))
        for field in fp.GetFields():
            try:
                name = field.GetName()
            except Exception:
                continue
            if name != "Reference":
                continue
            if want_hide:
                field.SetVisible(False)
                hidden += 1
            elif want_shrink:
                field.SetVisible(True)
                field.SetTextSize(pcbnew.VECTOR2I(int(0.8 * NM), int(0.8 * NM)))
                field.SetTextThickness(int(0.15 * NM))
                shrunk += 1
    for item in board.GetDrawings():
        cls = type(item).__name__
        if cls in ("PCB_TEXT", "PCB_TEXT_T"):
            try:
                if item.GetTextThickness() < int(0.15 * NM):
                    item.SetTextThickness(int(0.15 * NM))
                    text_fixed += 1
            except Exception:
                pass
    board.Save(str(BOARD))
    print(f"hidden refs={hidden} shrunk refs={shrunk} board texts fixed={text_fixed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
