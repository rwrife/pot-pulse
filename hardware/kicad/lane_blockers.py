#!/usr/bin/env python3
"""Per-gap blocker dump: for each DRC unconnected pair, report every foreign
copper item colliding with the straight-segment capsule (and L corners),
so congested lanes can be diagnosed and fixed by targeted ripp-up."""
import json
import re
import sys
from math import hypot
from pathlib import Path

import pcbnew

BOARD = Path(__file__).resolve().parent / "pot-pulse.kicad_pcb"
NM = 1e6
WIDTH = int(0.2 * NM)
TOL = int(0.005 * NM)
LAYER_BY_NAME = {"F.Cu": pcbnew.F_Cu, "B.Cu": pcbnew.B_Cu}


def capsule(x1, y1, x2, y2, r):
    dx, dy = x2 - x1, y2 - y1
    ln = hypot(dx, dy) or 1
    px, py = -dy / ln * r, dx / ln * r
    ch = pcbnew.SHAPE_LINE_CHAIN()
    for q in ((x1 + px, y1 + py), (x2 + px, y2 + py), (x2 - px, y2 - py), (x1 - px, y1 - py)):
        ch.Append(int(round(q[0])), int(round(q[1])))
    ch.Append(int(round(x1 + px)), int(round(y1 + py)))
    ch.SetClosed(True)
    return pcbnew.SHAPE_POLY_SET(ch)


def what(item):
    if item.Type() == pcbnew.PCB_VIA_T:
        return f"via net={item.GetNetname()}"
    if item.Type() == pcbnew.PCB_TRACE_T:
        s, e = item.GetStart(), item.GetEnd()
        return (f"track net={item.GetNetname()} ({s.x/1e6:.2f},{s.y/1e6:.2f})->"
                f"({e.x/1e6:.2f},{e.y/1e6:.2f}) w={item.GetWidth()/1e6:.2f}")
    return None


def main():
    drc = json.loads(Path(sys.argv[1]).read_text())
    board = pcbnew.LoadBoard(str(BOARD))
    obstacles = {pcbnew.F_Cu: [], pcbnew.B_Cu: [], pcbnew.In1_Cu: [], pcbnew.In2_Cu: []}
    for tr in board.GetTracks():
        if tr.Type() == pcbnew.PCB_VIA_T:
            obstacles[pcbnew.F_Cu].append(tr)
            obstacles[pcbnew.B_Cu].append(tr)
        else:
            obstacles[tr.GetLayer()].append(tr)
    pads = []
    pad_owner = {}
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            pad_owner[id(pad)] = fp.GetReference()
            pads.append(pad)
            obs_layers = [pcbnew.F_Cu, pcbnew.B_Cu] if int(pad.GetAttribute()) in (0, 2) else [pad.GetLayer()]
            for ly in obs_layers:
                obstacles[ly].append(pad)

    ns = board.GetDesignSettings().m_NetSettings

    def clearance(net_name):
        ni = board.FindNet(net_name)
        if ni is None:
            return int(0.2 * NM)
        nc = ns.GetNetClassByName(ni.GetNetClassName())
        return int(nc.GetClearance())

    def describe(pos_items):
        out = []
        for i in pos_items:
            out.append(i["description"])
        return out

    for pair in drc.get("unconnected_items", []):
        items = pair["items"]
        net = re.search(r"\[(.*?)\]", items[0]["description"]).group(1)
        pts = []
        kinds = []
        for i in items:
            x, y = int(round(i["pos"]["x"] * NM)), int(round(i["pos"]["y"] * NM))
            m = re.match(r"Pad (\S+) \[", i["description"])
            kind = "pad" if m else ("track" if "Track" in i["description"] else "via")
            # snap pads to real geometry center
            if m:
                best = None
                for p in pads:
                    pp = p.GetPosition()
                    if p.GetPadName() == m.group(1) and p.GetNetname() == net:
                        d = hypot(pp.x - x, pp.y - y)
                        if d < int(0.6 * NM) and (best is None or d < best[0]):
                            best = (d, pp.x, pp.y)
                if best:
                    x, y = best[1], best[2]
            if kind == "track":
                # snap to nearest same-net track endpoint
                best = None
                for tr in board.GetTracks():
                    if tr.GetNetname() != net or tr.Type() == pcbnew.PCB_VIA_T:
                        continue
                    for p in (tr.GetStart(), tr.GetEnd()):
                        d = hypot(p.x - x, p.y - y)
                        if best is None or d < best[0]:
                            best = (d, p.x, p.y)
                if best and best[0] < int(8 * NM):
                    x, y = best[1], best[2]
            pts.append((x, y))
            kinds.append(kind)
        clr = clearance(net)
        r = WIDTH / 2 + clr
        print(f"=== {net}  {describe(items)}")
        print(f"    gap {pts[0][0]/1e6:.2f},{pts[0][1]/1e6:.2f} -> {pts[1][0]/1e6:.2f},{pts[1][1]/1e6:.2f} "
              f"len={hypot(pts[1][0]-pts[0][0], pts[1][1]-pts[0][1])/1e6:.2f}mm clr={clr/1e6:.2f}")
        # try pads near the midpoint on either layer (who owns the corridor?)
        mid = ((pts[0][0] + pts[1][0]) // 2, (pts[0][1] + pts[1][1]) // 2)
        cap = capsule(pts[0][0], pts[0][1], pts[1][0], pts[1][1], r)
        # which layer to test? segment straight: test F.Cu corridor
        blockers = {}
        for ly in (pcbnew.F_Cu, pcbnew.B_Cu):
            for ob in obstacles[ly]:
                if ob.GetNetname() == net:
                    continue
                if cap.Collide(ob.GetEffectiveShape(ly), 0):
                    key = what(ob) or f"pad {ob.GetPadName()} net={ob.GetNetname()} of {pad_owner.get(id(ob),'?')}"
                    blockers.setdefault(ly, []).append(key)
        for ly, bl in blockers.items():
            print(f"    [{ly}] blocked by {len(bl)} foreign items:")
            for k in sorted(set(bl))[:8]:
                print(f"       - {k}")
        if not blockers:
            print("    NOT blocked straight — closer failure must be rule/edge/via_ok related")
        # pad near midpoint?
        near = []
        for p in pads:
            pp = p.GetPosition()
            if hypot(pp.x - mid[0], pp.y - mid[1]) < int(2.5 * NM):
                near.append(f"{pad_owner.get(id(p),'?')}.{p.GetPadName()}({p.GetNetname()})")
        if near:
            print(f"    pads within 2.5mm of midpoint: {', '.join(sorted(set(near)))}")


if __name__ == "__main__":
    main()
