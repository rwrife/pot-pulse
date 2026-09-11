#!/usr/bin/env python3
"""Cross-check schematic netlist pin->net map against PCB pad->net map.

Catches the most expensive class of bug (swapped pins / footprint pad-number
errors) that is invisible to ERC and DRC. Reads reports/pcb-input/netlist.json
(derived from reports/pot-pulse.net by netlist_to_json.py, i.e. from the
schematic) and compares every (component, pin) -> net assignment against the
board's pad nets.

Intentional board-only pads are whitelisted (mounting holes and connector
mechanical/shell/mounting-tab pads).

Exit code 0 only when mismatches == 0, every board-only pad is whitelisted,
and every schematic pin exists on the board.

    python3 cross_check_pads.py
"""
import json
from pathlib import Path

import pcbnew

HERE = Path(__file__).resolve().parent
NETLIST_JSON = HERE / "reports" / "pcb-input" / "netlist.json"
BOARD = HERE / "pot-pulse.kicad_pcb"


def board_only_allowed(ref: str, pad_name: str) -> bool:
    """Mounting holes: all pads. USB-C J1: shield S-pads + empty-name tabs.
    U1 (WSON-8-1EP): the two empty-name pads are paste-only thermal-slug
    apertures from the official library footprint (layers F.Paste only)."""
    if ref.startswith("MK"):
        return True
    if ref == "J1" and (pad_name.startswith("S") or pad_name == ""):
        return True
    if ref == "U1" and pad_name == "":
        return True
    return False


def main() -> int:
    raw = json.loads(NETLIST_JSON.read_text())
    sch_map = {}  # (ref, pin) -> set of net names; netlist.json is net -> [[ref, pin], ...]
    nc_pins = set()  # pins whose only schematic net is an unconnected-(...) pseudo-net
    for net, pins in raw.items():
        norm = net.lstrip("/")
        for ref, pin in pins:
            sch_map.setdefault((ref, str(pin)), set()).add(norm)
            if norm.startswith("unconnected-"):
                nc_pins.add((ref, str(pin)))

    board = pcbnew.LoadBoard(str(BOARD))
    mismatches = []
    board_only = []
    seen = set()
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        for pad in fp.Pads():
            pn = pad.GetPadName() or ""
            net = (pad.GetNetname() or "").lstrip("/")
            key = (ref, pn)
            seen.add(key)
            sch_nets = sch_map.get(key)
            if sch_nets is None:
                if not board_only_allowed(ref, pn):
                    board_only.append(f"{ref}.{pn} net={net} (not in schematic, not whitelisted)")
                continue
            if net not in sch_nets:
                if key in nc_pins and net == "":
                    continue  # schematic NC pin left floating on board: correct
                mismatches.append(
                    f"{ref}.{pn}: PCB net '{net}' != schematic net(s) {sorted(sch_nets)}"
                )
    missing_on_board = [
        f"{r}.{p}: schematic net {sorted(n)} has no PCB pad"
        for (r, p), n in sorted(sch_map.items())
        if (r, p) not in seen
    ]

    for line in mismatches:
        print("MISMATCH:", line)
    for line in board_only:
        print("BOARD-ONLY:", line)
    for line in missing_on_board:
        print("NOT-ON-BOARD:", line)
    print(f"schematic pins: {len(sch_map)} | pcb pads checked: {len(seen)} | "
          f"mismatches: {len(mismatches)} | unwhitelisted board-only: {len(board_only)} | "
          f"missing on board: {len(missing_on_board)}")
    ok = not mismatches and not board_only and not missing_on_board
    print("cross-check:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
