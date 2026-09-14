# Pot Pulse Evidence Matrix (Issue #8)

This matrix separates what is currently proven from what is only planned.

## Evidence classes

| Class | Meaning |
|---|---|
| Static analysis | Source/build/tool outputs without physical board execution |
| Simulation | Electrical simulation outputs |
| Bench validation | Measurements and behavior on assembled hardware |
| Field observation | Long-run use in deployment conditions |

## Current matrix (2026-09-14 run)

| Scope | Class | Evidence artifact | Status |
|---|---|---|---|
| Schematic electrical rules | Static analysis | `docs/evidence/2026-09-14/erc.rpt` | PASS (0 errors / 0 warnings) |
| PCB design rules | Static analysis | `docs/evidence/2026-09-14/drc.json` + `scripts/check_drc.py` | BLOCKED (5 unconnected) |
| Schematic↔PCB pad-net mapping | Static analysis | `hardware/kicad/cross_check_pads.py` run log | PASS |
| Firmware portable core tests | Static analysis | `pio test -e native` | PASS (19/19) |
| Firmware target build | Static analysis | `pio run -e esp32c3` | PASS |
| App typecheck/tests/build | Static analysis | `npm run typecheck && npm run test && npm run build` | PASS (47 tests) |
| BOM determinism/properties | Static analysis | `scripts/validate_bom.py` | PASS |
| Fabrication artifact preview | Static analysis | `docs/evidence/2026-09-14/pot-pulse-schematic.pdf`, `.../gerbers/*`, `.../pot-pulse-fabrication-preview.zip` | GENERATED (preview-only) |
| SPICE | Simulation | N/A in this run | NOT RUN |
| Board power-up/calibration | Bench validation | Planned in `docs/bring-up.md` | NOT RUN |
| Shelf deployment behavior | Field observation | N/A | NOT RUN |

## Interpretation

- This run proves reproducible source-level checks and exportability.
- It does **not** prove physical electrical behavior, calibration quality, EMC, thermal margins, or field reliability.
- Production release requires bench and (optionally) simulation evidence in addition to static checks.
