# Hardware Overview (Scaffold)

## System block description
Pot Pulse hardware is a USB-powered sensing platform centered on an ESP32-C3 module. It connects low-voltage sensors for:
- ambient temperature/humidity,
- shelf light level,
- multiple soil-moisture channels.

A planned custom carrier provides protection, connectors, debug access, and mounting points.

## Controller choice
- **Primary controller:** Espressif `ESP32-C3-MINI-1-H4X` module (Wi‑Fi + native USB, 4 MB flash).
- Rationale: enough I/O/peripherals for multi-sensor polling and local API hosting.

The datasheet-backed selections for the first schematic pass are recorded in
[`component-selection.md`](component-selection.md), with machine-readable MPN,
supplier, availability, and lifecycle evidence in
[`component-selection.csv`](component-selection.csv). The CSV is an issue #3
handoff only; once the schematic exists, KiCad symbol properties become the BOM
source of truth.

## Interfaces
- USB-C or USB-micro for power + provisioning/debug
- I2C bus for temp/humidity + light sensors
- Analog inputs (direct or via external ADC/mux) for capacitive moisture channels
- UART/JTAG pads for debug/programming

## Power plan
- SELV **USB 5V only** input.
- Onboard 3.3V regulation for logic and sensors.
- Reverse-polarity/overcurrent protections documented in schematic milestone.

## Enclosure/assembly concept
- Small desktop/shelf enclosure with vent slots.
- Detachable sensor leads to each pot zone.
- Standard standoffs/fasteners for at-home assembly.

## Safety limits
- No mains wiring.
- No pump/relay/high-power load control in MVP.
- Indoor hobby monitoring only.

## Expected KiCad deliverables
Planned editable source files:
- `hardware/kicad/pot-pulse.kicad_pro`
- `hardware/kicad/pot-pulse.kicad_sch`
- `hardware/kicad/pot-pulse.kicad_pcb` (if custom PCB remains in scope)

Expected evidence artifacts (later milestones):
- ERC and DRC outputs
- schematic PDF
- Gerbers/drill files
- BOM export from schematic properties (`bom/bom.csv`)

Current state: critical parts selected; no KiCad project committed yet.

Validate the selection handoff from the repository root:

```sh
python3 scripts/validate_component_selection.py
```
