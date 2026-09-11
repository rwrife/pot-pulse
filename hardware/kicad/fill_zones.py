#!/usr/bin/env python3
"""Fill copper zones in pot-pulse.kicad_pcb and save (headless equivalent of
Edit > Fill All Zones). Re-run after each route import: ImportSpecctraSES
invalidates zone fills, and unfilled pours make DRC report every pour-net pad
pair as unconnected plus via_dangling errors on pour-net stitching vias.

    python3 fill_zones.py
"""
from pathlib import Path

import pcbnew

HERE = Path(__file__).resolve().parent
BOARD = HERE / "pot-pulse.kicad_pcb"


def main() -> int:
    board = pcbnew.LoadBoard(str(BOARD))
    zones = [z for z in board.Zones() if not z.GetIsRuleArea()]
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(zones)
    board.Save(str(BOARD))
    b = pcbnew.LoadBoard(str(BOARD))
    pours = [z for z in b.Zones() if not z.GetIsRuleArea()]
    filled = sum(1 for z in pours if getattr(z, "GetIsFilled", z.IsFilled)())
    print(f"zones: {len(pours)} pours (filled={filled}), rule-areas skipped={len(list(b.Zones()))-len(pours)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
