#!/usr/bin/env python3
"""Dump J1 + U5 pad geometry (pos, size, layer, attribute) for fanout analysis."""
from pathlib import Path
import pcbnew

b = pcbnew.LoadBoard(str(Path(__file__).resolve().parent / "pot-pulse.kicad_pcb"))
NM = 1e6
for fp in b.GetFootprints():
    if fp.GetReference() not in ("J1", "U5"):
        continue
    print(f"--- {fp.GetReference()} @ ({fp.GetPosition().x/NM:.2f},{fp.GetPosition().y/NM:.2f}) rot={fp.GetOrientationDegrees():.0f}")
    for pad in fp.Pads():
        p = pad.GetPosition()
        s = pad.GetSize()
        print(f"  pad {pad.GetPadName():4} net={pad.GetNetname():15} pos=({p.x/NM:.2f},{p.y/NM:.2f}) "
              f"size=({s.x/NM:.2f}x{s.y/NM:.2f}) attr={pad.GetAttribute()} layers={pad.GetLayerName()} shape={pad.GetShape()}")
