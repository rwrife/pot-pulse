#!/usr/bin/env python3
"""Remove a specific bad via (and any zero-length track stubs at its
position) that close_stubs.py misplaced. Usage: remove_bad_via.py X Y NET"""
import sys
from pathlib import Path
import pcbnew

NM = 1e6
x = int(float(sys.argv[1]) * NM)
y = int(float(sys.argv[2]) * NM)
net = sys.argv[3]
TOL = int(0.02 * NM)
BOARD = Path(__file__).resolve().parent / "pot-pulse.kicad_pcb"
board = pcbnew.LoadBoard(str(BOARD))
removed = 0
for tr in list(board.GetTracks()):
    s = tr.GetStart()
    if tr.GetNetname() == net and abs(s.x - x) < TOL and abs(s.y - y) < TOL:
        if tr.Type() == pcbnew.PCB_VIA_T:
            board.Remove(tr)
            removed += 1
        else:
            e = tr.GetEnd()
            # only stubs whose far end is also within 0.8mm (the closer's stub)
            if abs(e.x - x) < int(0.9 * NM) and abs(e.y - y) < int(0.9 * NM):
                board.Remove(tr)
                removed += 1
board.Save(str(BOARD))
print(f"removed {removed} items at {x/1e6},{y/1e6} net={net}")
