# Pot Pulse Assembly Guide (Issue #8)

## Safety and handling

- SELV-only build: USB 5 V only, no mains-connected circuitry.
- ESD controls required while handling U2/U4/U5/U6/U7.
- Do first power tests without probes inserted into soil/water.

## Required tools

- Fine-tip soldering iron + flux
- Hot-air/rework capability for fine-pitch/QFN parts
- Tweezers, magnification, solder wick
- DMM (required), optional oscilloscope
- USB serial terminal

## Inputs and references

- Board source: `hardware/kicad/pot-pulse.kicad_pcb`
- BOM source of truth: schematic symbol properties (exported to `bom/bom.csv`)
- Non-schematic procurement: `bom/non-schematic-items.csv`

## Suggested population order

1. Small passives around U1/U4/U5/U6/U7
2. U1 buck + L1 + power passives (C1/C2/C3/C4)
3. U7 USB ESD + U3 probe-line ESD
4. U4 ADS1115, U5 SHT40, U6 VEML7700
5. U2 ESP32-C3-MINI-1 module
6. Connectors J1/J2/J3/J4/J5/J6
7. Test points TP1..TP16 and mounting hardware MK1..MK3

## Orientation-critical checks

- J1 USB-C mouth flush to left board edge.
- J2–J5 latch side faces outward board edge.
- J6 notch outward for keyed ribbon orientation.
- D1 polarity band toward buck input path.
- U7 pin-1 marker orientation per footprint dot.
- U1 exposed pad soldered; avoid cold-joint voiding.

## Pre-power inspection checklist

- No solder bridges on U2/U4/U5/U6/U7 fine-pitch pins.
- Continuity check: GND plane references and no VBUS-to-GND short.
- Connector pin-1 orientation matches silk + docs.
- Rail test points TP1/TP2/TP3/TP4 physically accessible.

## First power acceptance (assembly stage)

Pass if all true:
- TP1/TP2/TP3 in expected ranges from `docs/bring-up.md`.
- No component exceeds safe touch temperature in idle state.
- USB serial `status` command responds.

Fail if any are false; do not proceed to probe calibration.

## Known release blocker carried into assembly docs

Current committed PCB DRC still has 5 unconnected items (`docs/evidence/2026-09-14/drc.json`).
This means assembled hardware is not yet fabrication-ready for production release.
The generated fabrication bundle is preview-only until DRC gate is clean.
