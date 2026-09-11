#!/usr/bin/env python3
"""Dump board inventory: footprints, zones, track/via counts."""
import pcbnew
from pathlib import Path

b = pcbnew.LoadBoard(str(Path(__file__).resolve().parent / "pot-pulse.kicad_pcb"))
print("footprints:")
for fp in b.GetFootprints():
    print(f"  {fp.GetReference():6} {fp.GetValue():20} {fp.GetFPID().GetLibItemName()}")
print("zones:")
for z in b.Zones():
    print(f"  net={z.GetNetname()!r} rule_area={z.GetIsRuleArea()} layer={z.GetLayerName()} filled={z.GetFilledArea()/1e6:.1f}mm2")
tracks = [t for t in b.GetTracks() if t.Type() != pcbnew.PCB_VIA_T]
vias = [t for t in b.GetTracks() if t.Type() == pcbnew.PCB_VIA_T]
print("tracks:", len(tracks), "vias:", len(vias))
print("nets:", b.GetNetCount())
