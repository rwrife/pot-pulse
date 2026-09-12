#!/usr/bin/env python3
"""Compare current footprint positions against build_pcb.py PLACEMENT table."""
import sys
from pathlib import Path
import pcbnew

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_pcb import PLACEMENT  # noqa: E402

board = pcbnew.LoadBoard(str(Path(__file__).resolve().parent / "pot-pulse.kicad_pcb"))
NM = 1e6
diffs = 0
for fp in board.GetFootprints():
    ref = fp.GetReference()
    p = fp.GetPosition()
    rot = fp.GetOrientationDegrees()
    want = PLACEMENT.get(ref)
    if want is None:
        print(f"{ref}: on board but not in PLACEMENT (mounting hole or extra)")
        continue
    x, y, r = want
    rot_mod = rot % 360
    if rot_mod < 0:
        rot_mod += 360
    if abs(p.x / NM - x) > 0.01 or abs(p.y / NM - y) > 0.01 or abs(rot_mod - r % 360) > 0.1:
        print(f"{ref}: board ({p.x/1e6:.2f},{p.y/1e6:.2f},{rot:.0f}) != table ({x},{y},{r})")
        diffs += 1
print("placement mismatches:", diffs)
