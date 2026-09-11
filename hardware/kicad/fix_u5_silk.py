#!/usr/bin/env python3
"""Move U5's Reference field above the part (its below-part position collides
with U6's silkscreen pin-1 circle and clips solder-mask copper)."""
from pathlib import Path
import pcbnew

BOARD = Path(__file__).resolve().parent / "pot-pulse.kicad_pcb"
NM = 1e6
board = pcbnew.LoadBoard(str(BOARD))
for fp in board.GetFootprints():
    if fp.GetReference() != "U5":
        continue
    for field in fp.GetFields():
        if field.GetName() != "Reference":
            continue
        field.SetTextPos(pcbnew.VECTOR2I(0, int(2.8 * NM)))  # below part, away from U6 silk
        field.SetTextSize(pcbnew.VECTOR2I(int(0.8 * NM), int(0.8 * NM)))
        field.SetTextThickness(int(0.15 * NM))
        print("moved U5 Reference to (0, -2.6)")
board.Save(str(BOARD))
