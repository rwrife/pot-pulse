#!/usr/bin/env python3
"""Convert the KiCad schematic netlist export into build_pcb.py inputs.

    kicad-cli sch export netlist -o reports/pot-pulse.net pot-pulse.kicad_sch
    python3 netlist_to_json.py        # writes reports/pcb-input/*.json

Writes:
- reports/pcb-input/netlist.json     net name -> [[ref, pad], ...]
- reports/pcb-input/components.json  ref -> "Library:Footprint"
"""
from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
NET_FILE = HERE / "reports" / "pot-pulse.net"
OUT_DIR = HERE / "reports" / "pcb-input"


def parse_netlist(text: str) -> tuple[dict[str, list[list[str]]], dict[str, str]]:
    nets: dict[str, list[list[str]]] = {}
    body = text[text.index("(nets"):]
    for chunk in body.split("(net (code ")[1:]:
        m = re.match(r'"(\d+)"\) \(name "([^"]*)"\)', chunk)
        if not m:
            continue
        name = m.group(2)
        nodes = re.findall(r'\(node \(ref "([^"]+)"\) \(pin "([^"]*)"\)', chunk)
        nets[name] = [list(n) for n in nodes]
    comps = {ref: fp for ref, _value, fp in re.findall(
        r'\(comp \(ref "([^"]+)"\)\s*\(value "([^"]*)"\)\s*\(footprint "([^"]*)"\)', text)}
    return nets, comps


def main() -> int:
    text = NET_FILE.read_text()
    nets, comps = parse_netlist(text)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "netlist.json").write_text(json.dumps(nets, indent=1, sort_keys=True))
    (OUT_DIR / "components.json").write_text(json.dumps(comps, indent=1, sort_keys=True))
    real = {k: v for k, v in nets.items() if not k.startswith("unconnected-")}
    print(f"{len(real)} real nets, {len(comps)} components -> {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
