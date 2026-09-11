#!/usr/bin/env python3
"""Deterministic final-board pipeline for pot-pulse (issue #5).

Rebuilds the committed board state from reproducible inputs:
  build_pcb.py -> import t1.ses -> fill -> silk hygiene -> U5 silk fix
  -> close_stubs (VBUS bridge; bad pad-center vias are removed next)
  -> targeted stub cleanup -> final fill.

Adjudicate afterwards with:
  kicad-cli pcb drc --severity-error --severity-warning --format json \
      --output reports/drc-final.json pot-pulse.kicad_pcb
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def run(*args: str) -> None:
    print("+", " ".join(args))
    r = subprocess.run(args, cwd=HERE, capture_output=True, text=True)
    out = "\n".join(l for l in (r.stdout + r.stderr).splitlines() if "swig" not in l)
    print(out.strip()[-400:] or "(ok)")
    if r.returncode:
        raise SystemExit(f"step failed: {args}")


run("python3", "build_pcb.py")
run("python3", "reload_probe.py")
run("python3", "check_placement_vs_table.py")
run("python3", "route_driver.py", "import", "reports/routing/t1.ses")
run("python3", "fill_zones.py")
run("python3", "silk_hygiene.py")
run("python3", "fix_u5_silk.py")

# DRC for the closer input (subprocess kicad-cli inside container works via
# full path? No — kicad-cli is a host shim. Caller runs DRC before/after.)
drc = HERE / "reports" / "routing" / "t1c-drc.json"
if not drc.exists():
    raise SystemExit("run host-side: kicad-cli pcb drc ... --output reports/routing/t1c-drc.json first")
run("python3", "close_stubs.py", "--drc", str(drc))
# The closer places off-pad vias at pad centers in two congested spots;
# remove those specific artifacts (see close_stubs LEFT/FIX log).
run("python3", "remove_bad_via.py", "53.5", "29.6", "/I2C_SDA")
run("python3", "drop_track.py", "/I2C_SDA", "B.Cu", "53.5", "29.6")
run("python3", "fill_zones.py")
print("done")
