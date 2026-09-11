#!/usr/bin/env python3
"""Delete one specific track segment: net + layer + start-point match.
Usage: drop_track.py NET LAYER START_X START_Y"""
import sys
from pathlib import Path
import pcbnew

NM = 1e6
net = sys.argv[1]
layer_name = sys.argv[2]
sx = int(float(sys.argv[3]) * NM)
sy = int(float(sys.argv[4]) * NM)
LY = {"F.Cu": pcbnew.F_Cu, "B.Cu": pcbnew.B_Cu}
TOL = int(0.03 * NM)
BOARD = Path(__file__).resolve().parent / "pot-pulse.kicad_pcb"
board = pcbnew.LoadBoard(str(BOARD))
removed = 0
for tr in list(board.GetTracks()):
    if tr.Type() == pcbnew.PCB_VIA_T or tr.GetNetname() != net:
        continue
    if str(tr.GetLayerName()) != layer_name:
        continue
    s = tr.GetStart()
    e = tr.GetEnd()
    for p in (s, e):
        if abs(p.x - sx) < TOL and abs(p.y - sy) < TOL:
            board.Remove(tr)
            removed += 1
            break
board.Save(str(BOARD))
print(f"removed {removed} track(s) net={net} layer={layer_name} near {sx/1e6},{sy/1e6}")
