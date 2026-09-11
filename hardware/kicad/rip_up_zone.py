#!/usr/bin/env python3
"""Rip up tracks/vias fully inside a rectangle (surgical re-route zone).

Used to clear congested autorouter lanes (USB-C fanout, sensor cluster) so
the next FreeRouter pass — exported with inner layers stripped — can find a
cleaner local solution. Tracks/vias are removed only when BOTH endpoints
(or the via position) lie inside the rectangle; through-tracks that merely
cross the boundary are also removed because their net will be re-routed.

    python3 rip_up_zone.py X1 Y1 X2 Y2 [X1 Y1 X2 Y2 ...]

Prints counts; saves the board (no zone refill — run fill_zones.py after).
"""
import sys
from pathlib import Path
import pcbnew

NM = 1e6
HERE = Path(__file__).resolve().parent
BOARD = HERE / "pot-pulse.kicad_pcb"


def main() -> int:
    rects = [float(a) for a in sys.argv[1:]]
    if not rects or len(rects) % 4:
        print("usage: rip_up_zone.py X1 Y1 X2 Y2 [more rects]", file=sys.stderr)
        return 2
    rects = [(int(rects[i] * NM), int(rects[i + 1] * NM),
              int(rects[i + 2] * NM), int(rects[i + 3] * NM))
             for i in range(0, len(rects), 4)]

    def inside(x, y):
        return any(x1 <= x <= x2 and y1 <= y <= y2 for (x1, y1, x2, y2) in rects)

    board = pcbnew.LoadBoard(str(BOARD))
    doomed = []
    for tr in list(board.GetTracks()):
        s, e = tr.GetStart(), tr.GetEnd()
        if inside(s.x, s.y) and inside(e.x, e.y):
            doomed.append(tr)
    for tr in doomed:
        board.Remove(tr)
    board.Save(str(BOARD))
    print(f"removed {len(doomed)} tracks/vias in {len(rects)} rect(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
