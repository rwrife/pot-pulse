#!/usr/bin/env python3
"""Rip up stranded track fragments (dangling ends) from pot-pulse.kicad_pcb.

After a FreeRouter import, abandoned routing attempts can leave track
segments with one end anchored and the other end floating in space
("track_dangling"/stuck ratsnest). The next router pass treats these as
real copper and tends to strand MORE. This script deletes every track whose
endpoints do not both touch same-net copper (pad, via, or anchored track
end), iterating until stable, then drops vias that no longer connect
anything on either copper face. Save + refill zones + re-export the DSN
afterwards so the router sees a clean connectivity state.

    python3 rip_up_dangling.py
"""
from collections import defaultdict
from math import hypot
from pathlib import Path

import pcbnew

HERE = Path(__file__).resolve().parent
BOARD = HERE / "pot-pulse.kicad_pcb"
NM = 1e6
TOL = int(0.02 * NM)   # copper-touch tolerance


def anchors(board):
    """net -> layer -> list of anchored points (pads, vias)."""
    pts = defaultdict(lambda: defaultdict(list))
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.GetNetCode() == 0:
                continue
            p = pad.GetPosition()
            attr = int(pad.GetAttribute())
            if attr in (0, 2):  # PTH / connector: both faces
                pts[pad.GetNetCode()][pcbnew.F_Cu].append(p)
                pts[pad.GetNetCode()][pcbnew.B_Cu].append(p)
            else:
                pts[pad.GetNetCode()][pad.GetLayer()].append(p)
    for tr in board.GetTracks():
        if tr.Type() == pcbnew.PCB_VIA_T:
            p = tr.GetStart()
            pts[tr.GetNetCode()][pcbnew.F_Cu].append(p)
            pts[tr.GetNetCode()][pcbnew.B_Cu].append(p)
    return pts


def anchored(pts, net, layer, p):
    for q in pts[net][layer]:
        if hypot(p.x - q.x, p.y - q.y) <= TOL:
            return True
    return False


def main() -> int:
    board = pcbnew.LoadBoard(str(BOARD))
    removed_tracks = 0
    while True:
        pts = anchors(board)
        # union-find-ish: mark anchored tracks by fixed-point iteration
        anchored_ids = set()
        changed = True
        while changed:
            changed = False
            for tr in board.GetTracks():
                if tr.Type() == pcbnew.PCB_VIA_T or id(tr) in anchored_ids:
                    continue
                net, ly = tr.GetNetCode(), tr.GetLayer()
                s_ok = anchored(pts, net, ly, tr.GetStart())
                e_ok = anchored(pts, net, ly, tr.GetEnd())
                if s_ok or e_ok:
                    # anchored if one end touches real copper and the other
                    # touches another already-anchored track end
                    if s_ok and e_ok:
                        anchored_ids.add(id(tr)); changed = True; continue
                    ok_end = tr.GetStart() if s_ok else tr.GetEnd()
                    for o in board.GetTracks():
                        if o is tr or o.Type() == pcbnew.PCB_VIA_T:
                            continue
                        if o.GetNetCode() != net or o.GetLayer() != ly:
                            continue
                        if id(o) not in anchored_ids:
                            continue
                        for q in (o.GetStart(), o.GetEnd()):
                            if hypot(q.x - ok_end.x, q.y - ok_end.y) <= TOL:
                                anchored_ids.add(id(tr)); changed = True
                                break
                        else:
                            continue
                        break
        to_delete = [tr for tr in board.GetTracks()
                     if tr.Type() != pcbnew.PCB_VIA_T and id(tr) not in anchored_ids]
        if not to_delete:
            break
        for tr in to_delete:
            board.Remove(tr)
            removed_tracks += 1

    # vias that now connect nothing: no anchored same-net track/pad on both faces
    pts = anchors(board)
    removed_vias = 0
    for tr in list(board.GetTracks()):
        if tr.Type() != pcbnew.PCB_VIA_T:
            continue
        net = tr.GetNetCode()
        p = tr.GetStart()
        f = anchored(pts, net, pcbnew.F_Cu, p)
        b = anchored(pts, net, pcbnew.B_Cu, p)
        if not (f and b):
            board.Remove(tr)
            removed_vias += 1

    board.Save(str(BOARD))
    b2 = pcbnew.LoadBoard(str(BOARD))
    print(f"removed {removed_tracks} stranded track segs, {removed_vias} dead vias; "
          f"tracks/vias after reload: {len(b2.GetTracks())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
