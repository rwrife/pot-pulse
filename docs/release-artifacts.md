# Fabrication/Release Artifact Workflow (Issue #8)

This document defines how to produce a mature release bundle and when to block it.

## Gate policy

A **mature** fabrication bundle requires:
1. ERC clean.
2. DRC gate clean (`scripts/check_drc.py` reports PASS).
3. BOM validation/export reproducible from schematic source of truth.

If DRC gate is blocked, any exported Gerbers/ZIP are **preview-only** artifacts.

## Commands

```sh
# 1) Static electrical checks
kicad-cli sch erc --severity-all --exit-code-violations \
  --output docs/evidence/<date>/erc.rpt hardware/kicad/pot-pulse.kicad_sch
kicad-cli pcb drc --schematic-parity --severity-all --exit-code-violations \
  --format json --output docs/evidence/<date>/drc.json hardware/kicad/pot-pulse.kicad_pcb
python3 scripts/check_drc.py docs/evidence/<date>/drc.json

# 2) BOM from schematic symbol properties
/tmp/pot-pulse-kicad-venv/bin/python scripts/validate_bom.py
/tmp/pot-pulse-kicad-venv/bin/python scripts/export_bom.py --output docs/evidence/<date>/bom.csv

# 3) Output artifacts (run only when gate is PASS for mature release)
kicad-cli sch export pdf --output docs/evidence/<date>/pot-pulse-schematic.pdf hardware/kicad/pot-pulse.kicad_sch
kicad-cli pcb export gerbers --layers F.Cu,B.Cu,F.Mask,B.Mask,F.SilkS,B.SilkS,Edge.Cuts \
  --output docs/evidence/<date>/gerbers hardware/kicad/pot-pulse.kicad_pcb
kicad-cli pcb export drill --format excellon --excellon-units mm --generate-map --map-format pdf \
  --generate-report --report-path docs/evidence/<date>/gerbers/drill-report.txt \
  --output docs/evidence/<date>/gerbers hardware/kicad/pot-pulse.kicad_pcb
(cd docs/evidence/<date> && zip -r pot-pulse-fabrication-release.zip bom.csv pot-pulse-schematic.pdf gerbers)
```

## 2026-09-14 execution result

- `scripts/check_drc.py docs/evidence/2026-09-14/drc.json` ->
  `BLOCKED: violations=0 unconnected_items=5 schematic_parity=145`
- A preview bundle was still exported for integration handoff:
  `docs/evidence/2026-09-14/pot-pulse-fabrication-preview.zip`
- Do not treat preview bundle as production-ready release output.
