#!/usr/bin/env python3
"""Deterministically close short leftover gaps after autorouting
pot-pulse.kicad_pcb (FreeRouter cannot thread the last few stubs).

Method (verified pattern from the kicad-headless-pcb-pipeline skill):
parse `kicad-cli pcb drc --format json` unconnected_items pairs, build
candidate paths (straight / L-route, F.Cu or B.Cu, with optional
layer-change vias), accept a candidate only when its clearance capsule
collides with no same-layer foreign-net copper, then commit, refill zones,
and let native DRC adjudicate.

    python3 close_stubs.py --drc reports/routing/passN-drc.json [--dry]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from math import hypot
from pathlib import Path

import pcbnew

HERE = Path(__file__).resolve().parent
BOARD = HERE / "pot-pulse.kicad_pcb"
NM = 1e6
CLEAR = int(0.2 * NM)    # default clearance
EDGE = int(0.5 * NM)     # copper edge clearance
VIA_D, VIA_DRILL = int(0.6 * NM), int(0.3 * NM)
WIDTH = int(0.2 * NM)
TOL = int(0.005 * NM)

LAYER_BY_NAME = {"F.Cu": pcbnew.F_Cu, "In1.Cu": pcbnew.In1_Cu,
                 "In2.Cu": pcbnew.In2_Cu, "B.Cu": pcbnew.B_Cu}


def parse_item(desc: str, pos: dict):
    """Return (kind, net, layer|None, x_nm, y_nm) from a DRC item description."""
    x, y = int(round(pos["x"] * NM)), int(round(pos["y"] * NM))
    m = re.match(r"Pad (\S+) \[(.*)\] of (\S+) on (\S+)", desc)
    if m:
        return ("pad", m.group(2), LAYER_BY_NAME.get(m.group(4)), m.group(3), m.group(1), x, y)
    m = re.match(r"PTH pad (\S+) \[(.*)\] of (\S+) on (\S+)", desc)
    if m:
        return ("pad", m.group(2), LAYER_BY_NAME.get(m.group(4)), m.group(3), m.group(1), x, y)
    m = re.match(r"Track \[(.*)\] on (\S+?)(?:,|$)", desc)
    if m:
        return ("track", m.group(1), LAYER_BY_NAME.get(m.group(2)), None, None, x, y)
    m = re.match(r"(?:Blind/Buried )?Via \[(.*)\] on (\S+)(?: - \S+)?(?:,.*)?$", desc)
    if m:
        return ("via", m.group(1), None, None, None, x, y)
    return None


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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--drc", required=True)
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    drc = json.loads(Path(args.drc).read_text())
    board = pcbnew.LoadBoard(str(BOARD))
    net_ids = {}
    for entry in board.GetNetsByName():
        name = str(entry)
        ni = board.FindNet(name)
        if ni is not None:
            net_ids[name] = ni.GetNetCode()

    # obstacle index: same-layer foreign-net fixed copper
    obstacles = {ly: [] for ly in LAYER_BY_NAME.values()}
    for tr in board.GetTracks():
        if tr.Type() == pcbnew.PCB_VIA_T:
            obstacles[pcbnew.F_Cu].append(tr)
            obstacles[pcbnew.B_Cu].append(tr)
        else:
            obstacles[tr.GetLayer()].append(tr)
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            # SMD pads block their own layer; PTH(0)/CONN(2) block both faces
            obs_layers = [pcbnew.F_Cu, pcbnew.B_Cu] if int(pad.GetAttribute()) in (0, 2) else [pad.GetLayer()]
            for ly in obs_layers:
                obstacles[ly].append(pad)

    all_layers = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]

    # rule areas (RF keepout): candidate copper may not enter them
    rule_bbs = []
    for z in board.Zones():
        if z.GetIsRuleArea():
            bb = z.GetBoundingBox()
            rule_bbs.append((bb.GetX(), bb.GetY(), bb.GetRight(), bb.GetBottom()))

    def in_rule(pts):
        for (x, y) in pts:
            for (rx1, ry1, rx2, ry2) in rule_bbs:
                if rx1 <= x <= rx2 and ry1 <= y <= ry2:
                    return True
        # segments may cross a rule area without endpoints inside
        return False

    def net_clearance(net_name):
        ni = board.FindNet(net_name)
        if ni is not None:
            ns = board.GetDesignSettings().m_NetSettings
            nc = ns.GetNetClassByName(ni.GetNetClassName())
            try:
                return int(nc.GetClearance())
            except Exception:
                return CLEAR
        return CLEAR

    def blocked(pts, net_name, layer):
        """capsule chain collision vs foreign copper + board edge."""
        net_id = net_ids.get(net_name, 0)
        clr = net_clearance(net_name)
        for i in range(len(pts) - 1):
            x1, y1 = pts[i]
            x2, y2 = pts[i + 1]
            cap = capsule(x1, y1, x2, y2, WIDTH / 2 + clr)
            if in_rule([(x1, y1), (x2, y2)]):
                return "rule"
            for x, y in ((x1, y1), (x2, y2)):
                if x < EDGE or y < EDGE or x > 70 * NM - EDGE or y > 50 * NM - EDGE:
                    return "edge"
            for ob in obstacles[layer]:
                if ob.GetNetCode() == net_id:
                    continue
                if cap.Collide(ob.GetEffectiveShape(layer), 0):
                    return "copper"
        return None

    def via_ok(x, y, net_name):
        """A via barrel passes F/In1/In2/B copper and drills a hole.

        Check: (a) annular capsule vs foreign copper on EVERY layer,
        (b) drill-edge capsule vs foreign holes (PTH/NPTH) — hole clearance.
        """
        net_id = net_ids.get(net_name, 0)
        clr = net_clearance(net_name)
        if x < EDGE or y < EDGE or x > 70 * NM - EDGE or y > 50 * NM - EDGE:
            return False
        if in_rule([(x, y)]):
            return False
        ann = capsule(x, y, x + 1, y, VIA_D / 2 + clr)
        hole = capsule(x, y, x + 1, y, VIA_DRILL / 2 + int(0.25 * NM))
        for ly in all_layers:
            for ob in obstacles[ly]:
                if ob.GetNetCode() == net_id:
                    continue
                if ann.Collide(ob.GetEffectiveShape(ly), 0):
                    return False
        # a via may not sit on SMD pad copper even when the net matches
        # (via-in-SMD-pad is a process violation here: no tenting/planarization)
        for fp in board.GetFootprints():
            for pad in fp.Pads():
                if int(pad.GetAttribute()) != 1:  # 1 = SMD
                    continue
                cap = capsule(x, y, x + 1, y, VIA_D / 2)
                if cap.Collide(pad.GetEffectiveShape(pcbnew.F_Cu), 0):
                    return False
        # a via must stay clear of plane pour clearances on inner layers:
        # approximate by rejecting positions inside any foreign-net pad's
        # zone-relief ring? Too deep — DRC adjudicates; instead reject if the
        # annulus touches same-net inner-layer TRACKS is fine, planes are
        # handled by the next DRC pass, and a plane-connected via is DESIRED.
        # drill-to-drill: via hole edge vs every foreign pad hole (NPTH
        # mounting tabs are invisible to copper-shape checks)
        for fp in board.GetFootprints():
            for pad in fp.Pads():
                if pad.GetNetCode() == net_id:
                    continue
                dsize = pad.GetDrillSize()
                if not dsize or max(dsize.x, dsize.y) <= 0:
                    continue
                pp = pad.GetPosition()
                # approximate pad hole as circle r=drill/2; require edge gap
                r_other = max(dsize.x, dsize.y) / 2
                need = r_other + VIA_DRILL / 2 + int(0.25 * NM)
                if hypot(pp.x - x, pp.y - y) < need:
                    return False
        return True

    def pad_at(x, y):
        for fp in board.GetFootprints():
            for pad in fp.Pads():
                p = pad.GetPosition()
                if hypot(p.x - x, p.y - y) < TOL:
                    return pad
        return None

    added = []
    for pair in drc.get("unconnected_items", []):
        items = [parse_item(i["description"], i["pos"]) for i in pair["items"]]
        if any(it is None for it in items):
            print("SKIP unparsed:", [i["description"] for i in pair["items"]])
            continue
        (k1, net1, ly1, ref1, pn1, x1, y1), (k2, net2, ly2, ref2, pn2, x2, y2) = items
        if net1 != net2:
            print("SKIP net mismatch", net1, net2)
            continue
        net = net1
        # pad positions may report bbox centers; snap to pad geometry centers
        if k1 == "pad":
            p = pad_at(x1, y1)
            if p:
                x1, y1 = p.GetPosition().x, p.GetPosition().y
        if k2 == "pad":
            p = pad_at(x2, y2)
            if p:
                x2, y2 = p.GetPosition().x, p.GetPosition().y
        if k1 == "pad" and k2 == "pad" and ref1 == ref2:
            # Same-footprint same-net pad pairs (USB-C VBUS A4/A9 etc.) ARE
            # real ratsnest connections the footprint does not make for us.
            pass

        # DRC 'pos' for a track points at its ratsnest-anchored endpoint.
        # Find the track of this net whose midpoint-or-endpoint matches pos,
        # then use the endpoint closest to pos.
        def snap_track(x, y, net_name, other_x, other_y):
            best = None
            nid = net_ids.get(net_name, 0)
            for tr in board.GetTracks():
                if tr.GetNetCode() != nid or tr.Type() == pcbnew.PCB_VIA_T:
                    continue
                s, e = tr.GetStart(), tr.GetEnd()
                for p in (s, e):
                    d = hypot(p.x - x, p.y - y)
                    if d < int(0.35 * NM) and (best is None or d < best[0]):
                        best = (d, p.x, p.y)
                mx, my = (s.x + e.x) / 2, (s.y + e.y) / 2
                if hypot(mx - x, my - y) < int(0.35 * NM):
                    for p in (s, e):
                        d2 = hypot(p.x - x, p.y - y)
                        if best is None or d2 < best[0]:
                            best = (d2, p.x, p.y)
            return (best[1], best[2]) if best else (x, y)

        if k1 == "track":
            x1, y1 = snap_track(x1, y1, net, x2, y2)
        if k2 == "track":
            x2, y2 = snap_track(x2, y2, net, x1, y1)
        if k1 == "via" or k2 == "via":
            pass  # via pos is exact

        candidates = []
        # straight/L segments on F.Cu are electrically valid only when both
        # items carry copper on F.Cu: F.Cu pads, through pads, vias (barrel),
        # or F.Cu track ends. An inner-layer track end needs a via.
        def on_fcopper(kind, ly, x, y):
            if kind == "via":
                return True
            if kind == "track":
                return ly == pcbnew.F_Cu
            p = pad_at(x, y)
            # PTH(0)/CONN(2) pads reach both copper faces
            return p is not None and (p.GetLayer() == pcbnew.F_Cu or int(p.GetAttribute()) in (0, 2))
        if on_fcopper(k1, ly1, x1, y1) and on_fcopper(k2, ly2, x2, y2):
            layer = pcbnew.F_Cu
            if blocked([(x1, y1), (x2, y2)], net, layer) is None:
                candidates.append(("straight", layer, [(x1, y1), (x2, y2)], []))
            for corner in ((x1, y2), (x2, y1)):
                if blocked([(x1, y1), corner, (x2, y2)], net, layer) is None:
                    candidates.append(("L", layer, [(x1, y1), corner, (x2, y2)], []))
            # Z-detour lanes (same-face): route out to an offset lane, along, back
            if k1 == "pad" and k2 == "pad":
                lanes = []
                for k in [int(s * NM) for s in (0.45, 0.55, 0.65, 0.8, 0.95, 1.15, 1.35, 1.6, 1.9, 2.3)]:
                    lanes += [(min(x1, x2) - k), (max(x1, x2) + k)]
                    lanes += [ (max(y1, y2) + k), (min(y1, y2) - k)]
                for lx in sorted(set(lanes)):
                    if abs(lx - min(x1, x2)) < 30 * NM or abs(lx - max(x1, x2)) < 30 * NM:
                        pass
                    if lx < EDGE or lx > 70 * NM - EDGE:
                        continue
                    if blocked([(x1, y1), (lx, y1), (lx, y2), (x2, y2)], net, layer) is None:
                        candidates.append((f"Z-lane x={lx/1e6:.2f}", layer,
                                           [(x1, y1), (lx, y1), (lx, y2), (x2, y2)], []))
                        break
                if not candidates:
                    for ly in sorted(set([min(y1, y2) - int(0.45 * NM), max(y1, y2) + int(0.45 * NM),
                                          min(y1, y2) - int(0.6 * NM), max(y1, y2) + int(0.6 * NM),
                                          min(y1, y2) - int(0.8 * NM), max(y1, y2) + int(0.8 * NM),
                                          min(y1, y2) - int(1.1 * NM), max(y1, y2) + int(1.1 * NM)])):
                        if ly < EDGE or ly > 50 * NM - EDGE:
                            continue
                        if blocked([(x1, y1), (x1, ly), (x2, ly), (x2, y2)], net, layer) is None:
                            candidates.append((f"Z-lane y={ly/1e6:.2f}", layer,
                                               [(x1, y1), (x1, ly), (x2, ly), (x2, y2)], []))
                            break
        # via+straight on B.Cu: via1 near p1, via2 near p2
        for off1 in [(0, 0), (0.7 * NM, 0), (0, 0.7 * NM), (0, -0.7 * NM), (0.7*NM, 0.7*NM), (-0.7*NM, 0.7*NM), (0.7*NM, -0.7*NM), (-0.7*NM, -0.7*NM)]:
            v1 = (x1 + off1[0], y1 + off1[1])
            if not via_ok(*v1, net):
                continue
            if off1 != (0, 0):
                p1pad = pad_at(x1, y1)
                if k1 == "pad" and (p1pad is None or p1pad.GetNetname() != net):
                    continue
                if blocked([(x1, y1), v1], net, pcbnew.F_Cu):
                    continue
            for off2 in [(0, 0), (0.7 * NM, 0), (0, 0.7 * NM), (0, -0.7 * NM), (0.7*NM, 0.7*NM), (-0.7*NM, 0.7*NM), (0.7*NM, -0.7*NM), (-0.7*NM, -0.7*NM)]:
                v2 = (x2 + off2[0], y2 + off2[1])
                if not via_ok(*v2, net):
                    continue
                if off2 != (0, 0):
                    p2pad = pad_at(x2, y2)
                    if k2 == "pad" and (p2pad is None or p2pad.GetNetname() != net):
                        continue
                    if blocked([(x2, y2), v2], net, pcbnew.F_Cu):
                        continue
                if blocked([v1, v2], net, pcbnew.B_Cu):
                    continue
                stubs = []
                if off1 != (0, 0):
                    stubs.append((x1, y1, *v1))
                if off2 != (0, 0):
                    stubs.append((x2, y2, *v2))
                candidates.append((f"BCu-via off1={off1} off2={off2}", pcbnew.B_Cu, [v1, v2],
                                   [(s[0], s[1], s[2], s[3], pcbnew.F_Cu) for s in stubs]))
                break  # first viable offset pair wins
            if candidates:
                break

        if not candidates:
            if os.environ.get("DEBUG_PAIR") in (net.strip("/"), "1"):
                print(f"DEBUG pair [{net}] k1={k1}/{ly1} k2={k2}/{ly2} "
                      f"fc1={on_fcopper(k1, ly1, x1, y1)} fc2={on_fcopper(k2, ly2, x2, y2)} "
                      f"fblocked={blocked([(x1,y1),(x2,y2)], net, pcbnew.F_Cu)}")
            print(f"LEFT [{net}] {pair['items'][0]['description']} <-> {pair['items'][1]['description']}")
            continue
        kind, layer, pts, stubs = candidates[0]
        print(f"FIX [{net}] {pair['items'][0]['description']} <-> {pair['items'][1]['description']}: {kind}")
        if args.dry:
            continue
        for i in range(len(pts) - 1):
            tr = pcbnew.PCB_TRACK(board)
            tr.SetStart(pcbnew.VECTOR2I(int(pts[i][0]), int(pts[i][1])))
            tr.SetEnd(pcbnew.VECTOR2I(int(pts[i+1][0]), int(pts[i+1][1])))
            tr.SetWidth(int(WIDTH))
            tr.SetLayer(layer)
            tr.SetNetCode(net_ids[net])
            board.Add(tr)
            obstacles[layer].append(tr)
        for (sx, sy, ex, ey, ly) in stubs:
            tr = pcbnew.PCB_TRACK(board)
            tr.SetStart(pcbnew.VECTOR2I(int(sx), int(sy)))
            tr.SetEnd(pcbnew.VECTOR2I(int(ex), int(ey)))
            tr.SetWidth(int(WIDTH))
            tr.SetLayer(ly)
            tr.SetNetCode(net_ids[net])
            board.Add(tr)
            obstacles[ly].append(tr)
        via_pts = []
        if kind.startswith("BCu"):
            via_pts = [pts[0], pts[-1]]
        for (vx, vy) in via_pts:
            v = pcbnew.PCB_VIA(board)
            v.SetPosition(pcbnew.VECTOR2I(int(vx), int(vy)))
            v.SetWidth(int(VIA_D))
            v.SetDrill(int(VIA_DRILL))
            v.SetNetCode(net_ids[net])
            board.Add(v)
            obstacles[pcbnew.F_Cu].append(v)
            obstacles[pcbnew.B_Cu].append(v)
        added.append(net)

    print(f"fixed {len(added)} pairs")
    if args.dry or not added:
        return 0
    board.Save(str(BOARD))
    print("saved; refill zones + re-run DRC to adjudicate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
