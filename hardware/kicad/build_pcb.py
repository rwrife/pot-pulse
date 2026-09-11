#!/usr/bin/env python3
"""Generate the first-pass Pot Pulse PCB (hardware/kicad/pot-pulse.kicad_pcb).

The board is built entirely through the KiCad 9 ``pcbnew`` Python API so the
result is editable in PCBNEW and reproducible from a clean clone:

    python3 netlist_to_json.py          # refresh reports/pcb-input JSONs
    python3 build_pcb.py                # build pot-pulse.kicad_pcb

Design intent (documented in ../pcb-design-notes.md):
- 70 x 50 mm, 4 layers: F.Cu signal / In1.Cu solid GND / In2.Cu +3V3 /
  B.Cu signal. Solid ground grounding strategy; no plane splits.
- USB-C enters at the left edge; protection + 3.3 V buck cluster sit between
  the USB connector and the MCU.
- ESP32-C3-MINI-1 (U2) is rotated 180 deg so its PCB antenna points at the
  bottom board edge; a copper/via/reflow-free RF keepout band runs from the
  module antenna edge to the bottom edge, matching the datasheet keepout
  figure (exact RF performance requires bench verification).
- ADS1115 (U4) + probe conditioning + 4 JST zone connectors live on the right
  side; probe cables exit the right edge; analog runs keep away from the buck
  switch node and the antenna band.
- 6-pin debug/programming header (J6) on the top edge next to the MCU.
- 16 test points in two rows at the bottom-left/bottom-right, outside the RF
  keepout.
- 4 x M3 mounting holes in the corners.

Netlist + placement data:
- reports/pcb-input/netlist.json + components.json (from netlist_to_json.py)
- PLACEMENT table below (courtyard-checked; build_pcb.py asserts no courtyard
  overlaps and no edge violations before saving).

Routing: run reports/pcb-input through Specctra (pcbnew.ExportSpecctraDSN),
FreeRouter, then pcbnew.ImportSpecctraSES. See ../pcb-design-notes.md.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

try:
    import pcbnew
except ImportError as exc:  # pragma: no cover
    raise SystemExit("pcbnew python bindings required (run inside the KiCad container)") from exc

HERE = Path(__file__).resolve().parent
INPUT = HERE / "reports" / "pcb-input"
BOARD_W, BOARD_H = 70.0, 50.0

# ---------------------------------------------------------------------------
# Placement table: ref -> (x_mm, y_mm, rotation_deg)
# Coordinates are footprint origins. check_placement() verifies every pair of
# courtyards for overlap and every courtyard against the board edge using the
# real courtyard geometry of the loaded footprints, so these numbers are
# evidence-checked, not eyeballed.
PLACEMENT: dict[str, tuple[float, float, float]] = {
    # ---- USB entry + input protection + buck (left/top band) ----
    "J1":  (5.0,  25.0, 90.0),      # USB-C, mouth ~0.2 mm inside left edge
    "U7":  (12.0, 29.5, 90.0),      # USBLC6 between connector and MCU
    "R1":  (8.5,  36.0, 0.0),
    "R2":  (8.5,  33.0, 0.0),
    "F1":  (12.5, 41.0, 0.0),
    "D1":  (17.0, 41.0, 0.0),
    "C1":  (21.5, 41.0, 0.0),
    "C2":  (21.5, 37.8, 0.0),
    "U1":  (26.5, 41.0, 0.0),      # TPS62162 buck
    "L1":  (31.3, 40.9, 0.0),
    "C3":  (36.0, 41.0, 0.0),
    "C4":  (41.0, 41.0, 0.0),
    "C5":  (40.0, 37.8, 0.0),
    "R3":  (30.0, 37.0, 0.0),      # REG_PG divider
    # ---- MCU (antenna toward bottom edge, keepout in front of it) ----
    "U2":  (35.0, 26.0, 180.0),
    "C6":  (26.0, 33.5, 0.0),      # EN cap
    "R6":  (26.0, 36.2, 0.0),      # EN pull-up
    "R7":  (45.0, 36.2, 0.0),      # BOOT pull-up
    "C7":  (45.0, 33.5, 0.0),
    "C8":  (22.0, 19.5, 0.0),      # MCU decoupling, above RF keepout
    "C9":  (46.5, 19.5, 0.0),
    "J6":  (55.0, 47.5, 180.0),    # debug/programming header, top edge
    # ---- environment sensors (top-right; VEML aperture faces up) ----
    # U5 (SHT40) sits right of U2's courtyard in the open pocket below U6's
    # row; the earlier slot at (50.5,26) was ringed by the ADC/zone-filter
    # fanout and FreeRouter could not finish its pads (4 stranded stubs).
    "U5":  (54.2, 30.0, 0.0),      # SHT40
    "U6":  (56.5, 26.0, 0.0),      # VEML7700
    "R4":  (49.3, 22.0, 0.0),      # I2C pull-ups (row above ADC)
    "R5":  (52.32, 22.0, 0.0),
    "R8":  (55.35, 22.0, 0.0),      # ALERT pull-up
    "U3":  (58.4, 22.0, 0.0),      # TPD4E05 probe ESD array
    # ---- ADC + probe conditioning (right middle) ----
    "U4":  (52.5, 18.0, 0.0),      # ADS1115
    # zone filter grid (right, clear of RF keepout x<=46 and connectors)
    "C10": (48.0, 9.5, 0.0), "C11": (51.5, 9.5, 0.0),
    "C12": (55.0, 9.5, 0.0), "C13": (58.02, 9.5, 0.0),
    "R9":  (48.0, 6.5, 0.0), "R10": (51.5, 6.5, 0.0),
    "R11": (55.0, 6.5, 0.0), "R12": (58.02, 6.5, 0.0),
    # Zone connectors, cables exit right. Whole bank shifted +0.55mm from the
    # original 9.2mm pitch so J5's courtyard (asymmetric under 270deg rot,
    # bottom edge y=7.27) clears MK3's mounting-hole courtyard (top y=7.08);
    # intra-bank gaps stay at the original 0.24mm.
    "J2":  (66.9, 37.35, 270.0),
    "J3":  (66.9, 28.15, 270.0),
    "J4":  (66.9, 18.95, 270.0),
    "J5":  (66.9, 9.75, 270.0),
    # ---- test points (left block + bottom-right row, all outside RF band) ----
    "TP1":  (8.45, 6.0, 0.0),      # VBUS (clears MK1 courtyard x<=7.08)
    "TP2":  (12.0, 6.0, 0.0),      # +5V_PROTECTED
    "TP3":  (8.0,  10.0, 0.0),     # +3V3
    "TP4":  (12.0, 10.0, 0.0),     # GND
    "TP5":  (16.0, 6.0, 0.0),      # I2C_SDA
    "TP6":  (16.0, 10.0, 0.0),     # I2C_SCL
    "TP7":  (20.0, 6.0, 0.0),      # USB_DP
    "TP8":  (20.0, 10.0, 0.0),     # USB_DM
    "TP15": (8.0,  14.5, 0.0),     # MOISTURE_AIN2
    "TP16": (12.0, 14.5, 0.0),     # MOISTURE_AIN3
    "TP9":  (49.0, 12.5, 0.0),     # REG_PG
    "TP10": (52.5, 12.5, 0.0),     # EN
    "TP11": (48.0, 3.5, 0.0),      # BOOT_GPIO9
    "TP12": (51.5, 3.5, 0.0),      # ADC_ALERT_N
    # TP13/TP14 clear the RF keepout (right edge x=46), R12/C13 above, and
    # MK3's courtyard (left edge x=60.02).
    "TP13": (56.0, 3.5, 0.0),      # MOISTURE_AIN0
    "TP14": (58.6, 3.5, 0.0),      # MOISTURE_AIN1
}

# Three M3 mounting holes. The top-right corner is occupied by the JST zone
# connector bank (courtyards would collide); hardware/requirements.md needs
# "at least two mounting holes" and three provide stable enclosure mounting.
MOUNT_HOLES = [(3.6, 3.6), (3.6, 46.4), (63.5, 3.6)]

# Test-point / mounting-hole / board-edge components: silk reference fields
# collide with each other or the edge at these densities, so their reference
# text lives on F.Fab only (positions are documented in pcb-design-notes.md).
NO_SILK_REF = {f"TP{i}" for i in range(1, 17)} | {"MK1", "MK2", "MK3", "J1", "J6"}

# RF keepout (all layers, copper+vias+zones+tracks disallowed):
# bottom band in front of the U2 antenna. U2 origin (35,26) rot 180 deg ->
# module body y 17.7..34.3 with antenna end at y=17.7; courtyard spans
# y 17.475..34.525. Keepout rect (x1,y1,x2,y2) spans x 24..46, y from below
# edge to 17.4 so it stops clear of U2's courtyard (rule areas that graze a
# footprint courtyard flag the whole footprint as an items_not_allowed error).
RF_KEEPOUT = (24.0, -2.0, 46.0, 17.4)

NET_CLASS_DEFS = {
    "Power":  dict(width=0.5,  clearance=0.20, via_d=0.7,  via_drill=0.35),
    # USB: the GCT USB4105 staggered 0.5 mm pitch pads (0.3 x 1.15 mm) need
    # 0.15 mm fanout tracks — 0.2 mm leaves no corridor and the autorouter
    # strands the A-row hops. Impedance is not controlled on this first pass
    # (documented gap in pcb-design-notes.md).
    "USB":    dict(width=0.15, clearance=0.15, via_d=0.6,  via_drill=0.3),
    "Analog": dict(width=0.20, clearance=0.25, via_d=0.6,  via_drill=0.3),
}
NET_CLASS_MEMBERS = {
    "Power":  ["/VBUS", "/+5V_PROTECTED", "/SW_NODE", "/+3V3", "/GND"],
    "USB":    ["/USB_DP", "/USB_DM", "/USB_CONN_DP", "/USB_CONN_DM"],
    "Analog": ["/MOISTURE_AIN0", "/MOISTURE_AIN1", "/MOISTURE_AIN2", "/MOISTURE_AIN3",
               "/PROBE1_RAW", "/PROBE2_RAW", "/PROBE3_RAW", "/PROBE4_RAW"],
}

TUNING_NOTE = ""  # kept empty; Specctra tuning is written by routing step


def mm(v: float) -> int:
    return int(round(v * 1e6))


def rect_chain(x1: float, y1: float, x2: float, y2: float) -> "pcbnew.SHAPE_LINE_CHAIN":
    lc = pcbnew.SHAPE_LINE_CHAIN()
    for px, py in [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]:
        lc.Append(mm(px), mm(py))
    lc.SetClosed(True)
    return lc


def load_inputs() -> tuple[dict, dict]:
    nets = json.loads((INPUT / "netlist.json").read_text())
    comps = json.loads((INPUT / "components.json").read_text())
    return nets, comps


def pad_net_map(nets: dict) -> dict[str, dict[str, str]]:
    m: dict[str, dict[str, str]] = {}
    for net, nodes in nets.items():
        if net.startswith("unconnected-"):
            continue
        for ref, pin in nodes:
            m.setdefault(ref, {})[pin] = net
    return m


def fp_load(fpid: str) -> "pcbnew.FOOTPRINT":
    lib, name = fpid.split(":")
    search = HERE / "lib" / "pot-pulse.pretty" if lib == "pot-pulse" else Path("/usr/share/kicad/footprints") / f"{lib}.pretty"
    fp = pcbnew.FootprintLoad(str(search), name)
    if fp is None:
        raise SystemExit(f"footprint {fpid} not found under {search}")
    return fp


def courtyard_bounds(fp: "pcbnew.FOOTPRINT") -> tuple[float, float, float, float]:
    """Axis-aligned courtyard bbox in mm.

    Works both on a freshly loaded footprint (local coords) and on one
    already added to the board (absolute coords) — in both cases the
    returned bbox is in the same frame as the item coordinates.
    """
    xs, ys = [], []
    for item in fp.GraphicalItems():
        if item.GetLayer() == pcbnew.F_CrtYd:
            ib = item.GetBoundingBox()
            xs += [ib.GetX(), ib.GetRight()]
            ys += [ib.GetY(), ib.GetBottom()]
    if not xs:
        # no courtyard drawn: union of pads
        px, py = [], []
        for pad in fp.Pads():
            pb = pad.GetBoundingBox()
            px += [pb.GetX(), pb.GetRight()]
            py += [pb.GetY(), pb.GetBottom()]
        return (min(px) / 1e6, min(py) / 1e6, max(px) / 1e6, max(py) / 1e6)
    return min(xs) / 1e6, min(ys) / 1e6, max(xs) / 1e6, max(ys) / 1e6


def check_placement(footprints: list["pcbnew.FOOTPRINT"]) -> list[str]:
    problems = []
    boxes = {fp.GetReference(): courtyard_bounds(fp) for fp in footprints}
    for ref, (x1, y1, x2, y2) in boxes.items():
        if x1 < -0.01 or y1 < -0.01 or x2 > BOARD_W + 0.01 or y2 > BOARD_H + 0.01:
            problems.append(f"{ref} courtyard outside board: {x1:.2f},{y1:.2f}..{x2:.2f},{y2:.2f}")
    refs = sorted(boxes)
    for i in range(len(refs)):
        for j in range(i + 1, len(refs)):
            a, b = boxes[refs[i]], boxes[refs[j]]
            ox = min(a[2], b[2]) - max(a[0], b[0])
            oy = min(a[3], b[3]) - max(a[1], b[1])
            if ox > 0.0 and oy > 0.0:
                problems.append(f"courtyard overlap {refs[i]}/{refs[j]}: {ox:.2f}x{oy:.2f}mm")
    return problems


def build(out_path: Path, check_only: bool = False) -> int:
    nets, comps = load_inputs()
    pmap = pad_net_map(nets)

    board = pcbnew.NewBoard(str(out_path))
    board.SetCopperLayerCount(4)

    # design rules
    ds = board.GetDesignSettings()
    ds.m_minClearance = mm(0.2)
    ds.m_minTrackWidth = mm(0.15)
    ds.m_minViaDia = mm(0.6)
    ds.m_minViaDrill = mm(0.3)
    # The WSON-8 ThermalVias land pattern for U1 carries 0.25 mm EP thermal
    # vias (datasheet-recommended stitching); allow them rather than widening
    # drills the footprint cannot use.
    ds.m_MinThroughDrill = mm(0.2)
    ds.m_CopperEdgeClearance = mm(0.5)

    ns = ds.m_NetSettings
    default = ns.GetDefaultNetclass()
    default.SetClearance(mm(0.2))
    default.SetTrackWidth(mm(0.2))
    default.SetViaDiameter(mm(0.6))
    default.SetViaDrill(mm(0.3))
    for cname, spec in NET_CLASS_DEFS.items():
        nc = pcbnew.NETCLASS(cname)
        nc.SetTrackWidth(mm(spec["width"]))
        nc.SetClearance(mm(spec["clearance"]))
        nc.SetViaDiameter(mm(spec["via_d"]))
        nc.SetViaDrill(mm(spec["via_drill"]))
        ns.SetNetclass(cname, nc)

    # board outline
    for i, (sx, sy) in enumerate([(0, 0), (BOARD_W, 0), (BOARD_W, BOARD_H), (0, BOARD_H)]):
        ex, ey = [(BOARD_W, 0), (BOARD_W, BOARD_H), (0, BOARD_H), (0, 0)][i]
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(pcbnew.VECTOR2I(mm(sx), mm(sy)))
        s.SetEnd(pcbnew.VECTOR2I(mm(ex), mm(ey)))
        s.SetWidth(mm(0.1))
        s.SetLayer(pcbnew.Edge_Cuts)
        board.Add(s)

    # nets — keep board-owned refs alive until save (GC trap)
    netmap: dict[str, object] = {}
    for name in nets:
        if name.startswith("unconnected-"):
            continue
        board.Add(pcbnew.NETINFO_ITEM(board, name))
        ni = board.FindNet(name)
        assert ni is not None, f"net {name} vanished after Add"
        netmap[name] = ni
    for cname, members in NET_CLASS_MEMBERS.items():
        shared = ns.GetNetClassByName(cname)
        for m in members:
            if m in netmap:
                netmap[m].SetNetClass(shared)

    # footprints
    placed: list["pcbnew.FOOTPRINT"] = []
    for ref, (x, y, rot) in PLACEMENT.items():
        fp = fp_load(comps[ref])
        fp.SetReference(ref)
        fp.SetLayer(pcbnew.F_Cu)
        fp.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
        fp.SetOrientationDegrees(rot)
        board.Add(fp)
        if ref in NO_SILK_REF:
            # Move the reference field off silk (to F.Fab) — dense TP grid /
            # edge-adjacent parts otherwise create silk DRC violations.
            # (KiCad 9 API: reference/value live on FOOTPRINT fields, not
            # fp.Texts(); field objects expose SetLayer directly.)
            for fld in fp.GetFields():
                if fld.GetLayer() == pcbnew.F_SilkS:
                    fld.SetLayer(pcbnew.F_Fab)
        # Net binding MUST happen after board.Add: pads cloned into the
        # board before binding serialize as net 0 (verified on KiCad 9.0.9
        # — see hardware/pcb-design-notes.md).
        nets_for_ref = pmap.get(ref, {})
        for pad in fp.Pads():
            net = nets_for_ref.get(pad.GetPadName(), "")
            if net:
                pad.SetNet(netmap[net])
        placed.append(fp)

    missing = sorted(set(pmap) - set(PLACEMENT))
    extra = sorted(set(PLACEMENT) - set(pmap))
    if missing or extra:
        print(f"ERROR placement/netlist mismatch: missing={missing} extra={extra}", file=sys.stderr)
        return 2

    # mounting holes
    for idx, (hx, hy) in enumerate(MOUNT_HOLES, start=1):
        fp = fp_load("MountingHole:MountingHole_3.2mm_M3")
        fp.SetReference(f"MK{idx}")
        fp.SetLayer(pcbnew.F_Cu)
        fp.SetPosition(pcbnew.VECTOR2I(mm(hx), mm(hy)))
        board.Add(fp)
        for fld in fp.GetFields():
            if fld.GetLayer() == pcbnew.F_SilkS:
                fld.SetLayer(pcbnew.F_Fab)
        placed.append(fp)

    # copper pours (star ground: solid GND; +3V3 on In2)
    # GND planes connect THT pads SOLID (no thermal relief): FreeRouter
    # routed some signal nets across In1.Cu, and the resulting cleared
    # slots starved the relief spokes on the zone-edge JST GND pads to a
    # single spoke (starved_thermal DRC errors). Solid GND THT connections
    # are standard for plane nets used as return paths; all fine-pitch
    # parts are SMD and sit on F.Cu (no F.Cu pour). The +3V3 plane keeps
    # thermal relief.
    def pour(netname: str, layer: int, solid: bool = False) -> None:
        z = pcbnew.ZONE(board)
        z.AddPolygon(rect_chain(0.5, 0.5, BOARD_W - 0.5, BOARD_H - 0.5))
        z.SetNetCode(netmap[netname].GetNetCode())
        z.SetLayer(layer)
        z.SetPadConnection(
            pcbnew.ZONE_CONNECTION_FULL if solid
            else pcbnew.ZONE_CONNECTION_THERMAL
        )
        z.SetLocalClearance(mm(0.25))
        board.Add(z)

    pour("/GND", pcbnew.In1_Cu, solid=True)
    pour("/GND", pcbnew.B_Cu, solid=True)
    pour("/+3V3", pcbnew.In2_Cu)

    # RF keepout: rule area on every layer (no copper, no vias, no tracks,
    # no footprints/pads) in front of the U2 antenna. It ends at y=17.4,
    # just below U2's courtyard (y=17.475) so no footprint is flagged inside.
    for layer in (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu):
        kz = pcbnew.ZONE(board)
        kz.AddPolygon(rect_chain(*RF_KEEPOUT))
        kz.SetIsRuleArea(True)
        kz.SetDoNotAllowCopperPour(True)
        kz.SetDoNotAllowVias(True)
        kz.SetDoNotAllowTracks(True)
        kz.SetDoNotAllowPads(True)
        kz.SetDoNotAllowFootprints(True)
        kz.SetLayer(layer)
        board.Add(kz)

    # silkscreen legend
    t = pcbnew.PCB_TEXT(board)
    t.SetText("Pot Pulse A0")
    t.SetPosition(pcbnew.VECTOR2I(mm(30.0), mm(45.5)))
    t.SetLayer(pcbnew.F_SilkS)
    t.SetVisible(True)
    t.SetTextSize(pcbnew.VECTOR2I(mm(1.0), mm(1.0)))
    # NOTE: SetTextWidth() in the KiCad 9 bindings also rewrites the glyph
    # height ((size 1 0.15) serializes); stroke thickness is SetTextThickness.
    t.SetTextThickness(mm(0.15))
    board.Add(t)

    problems = check_placement(placed)
    if problems:
        print("PLACEMENT PROBLEMS:", file=sys.stderr)
        for p in problems:
            print("  " + p, file=sys.stderr)
        return 3
    if check_only:
        print(f"placement OK: {len(placed)} footprints")
        return 0

    board.SetFileName(str(out_path))
    board.Save(str(out_path))
    print(f"saved {out_path}: {len(placed)} footprints, {len(netmap)} nets")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(HERE / "pot-pulse.kicad_pcb"))
    ap.add_argument("--check-only", action="store_true")
    args = ap.parse_args()
    raise SystemExit(build(Path(args.out), args.check_only))
