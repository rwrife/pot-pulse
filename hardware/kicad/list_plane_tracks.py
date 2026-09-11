#!/usr/bin/env python3
"""List signal tracks sitting on the internal plane layers (In1.Cu/In2.Cu).

The stackup intent is In1.Cu = solid GND plane and In2.Cu = solid +3V3
plane. Any signal TRACK on those layers is an autorouter artifact from an
early 4-layer pass; it competes with the pours (spokes instead of solid
planes) and blocked the deterministic stub closer. Prints each offender so
rip_up_lane_blockers.py can remove them plus known stranded stubs.

    python3 list_plane_tracks.py
"""
from pathlib import Path
import pcbnew

board = pcbnew.LoadBoard(str(Path(__file__).resolve().parent / "pot-pulse.kicad_pcb"))
n = 0
for tr in board.GetTracks():
    if tr.Type() == pcbnew.PCB_VIA_T:
        continue
    ly = tr.GetLayerName()
    if str(ly) in ("In1.Cu", "In2.Cu"):
        s, e = tr.GetStart(), tr.GetEnd()
        print(f"plane-layer track: net={tr.GetNetname()} layer={ly} "
              f"({s.x/1e6:.2f},{s.y/1e6:.2f})->({e.x/1e6:.2f},{e.y/1e6:.2f}) w={tr.GetWidth()/1e6:.2f}")
        n += 1
print("total plane-layer signal tracks:", n)
