# Pot Pulse first-pass schematic

This directory contains the editable KiCad 9 project for the USB-powered Pot Pulse four-zone sensor node.

## Files

- `pot-pulse.kicad_pro` — KiCad project settings.
- `pot-pulse.kicad_sch` — editable schematic source of truth.
- `lib/pot-pulse.kicad_sym` — project symbols whose pin maps were transcribed from the manufacturer documents cited in `../component-selection.md`.
- `generate_schematic.py` — reproducible first-capture generator; the generated schematic remains editable in KiCad.
- `validate_schematic.py` — static acceptance checks for required parts, properties, nets, pin mappings, test access, and the native ERC summary.
- `reports/erc.rpt` — native KiCad 9 electrical-rules report.
- `reports/schematic-analysis.txt` — supplemental static analyzer output.

## Reproduce and verify

The host needs KiCad 9 symbol libraries and Python 3.11+:

```sh
python3 -m venv /tmp/pot-pulse-kicad-venv
/tmp/pot-pulse-kicad-venv/bin/pip install -r hardware/kicad/requirements.txt
KICAD_SYMBOL_DIR=/usr/share/kicad/symbols \
  /tmp/pot-pulse-kicad-venv/bin/python hardware/kicad/generate_schematic.py
kicad-cli sch erc -o hardware/kicad/reports/erc.rpt hardware/kicad/pot-pulse.kicad_sch
KICAD_SYMBOL_DIR=/usr/share/kicad/symbols \
  /tmp/pot-pulse-kicad-venv/bin/python hardware/kicad/validate_schematic.py \
  --erc hardware/kicad/reports/erc.rpt
```

The repository's headless `kicad-cli` wrapper runs KiCad 9 in a container. The committed report is generated from the editable schematic, not hand-authored.

## Evidence boundary

These files provide **static schematic and native ERC evidence only**. They do not provide PCB layout/DRC, simulation, assembled-board, EMC, environmental, field, or calibration evidence. PCB land patterns for the project-specific ESP32-C3-MINI-1 and VEML7700 packages are intentionally owned by issue #5; their schematic footprint identifiers preserve that handoff.
