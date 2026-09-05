# Pot Pulse

USB-powered ESP32-C3 plant-shelf monitor for home growers to track soil moisture, light, and microclimate trends in a local dashboard without cloud accounts or automatic watering.

## Motivation
Houseplant care is mostly guesswork between watering days. People often overwater because they cannot see trend data (light, moisture, humidity) across multiple pots in one place.

## Target users
- Home plant hobbyists with 1–20 potted indoor plants
- Small office/shared-space plant caretakers
- Makers who want a safe, low-voltage, locally controlled monitoring tool

## Concrete use cases
1. Compare morning/evening light exposure per shelf position.
2. Track soil moisture drop rate after watering to tune intervals.
3. Spot dry microclimates near windows/vents before plants decline.
4. Export a local history snapshot for seasonal care adjustments.

## Intended end-to-end workflow
1. Assemble device (SELV USB only) and connect sensors for each monitored pot zone.
2. Join device to local network (or direct USB setup mode).
3. Name shelves/zones in the companion app.
4. Calibrate moisture probes with dry/wet reference points.
5. Review live status + trend charts; set local reminder thresholds.
6. Export CSV/JSON snapshots for personal records.

## MVP features
- ESP32-C3 firmware with periodic sampling (moisture, light, temp/humidity)
- Local-first companion web app (mobile + desktop browsers)
- Per-zone calibration profiles and health-state bands (informational only)
- On-device ring buffer with timestamped readings
- Local network API for status/history/export
- USB recovery/provisioning flow
- Versioned backup/restore of settings and zone metadata

## Non-goals (MVP)
- Automatic watering, relays, or pumps
- Any mains-voltage control path
- Cloud account requirement or remote telemetry service
- Plant diagnosis/treatment claims
- Outdoor/weatherproof deployment

## Privacy, permissions, and data ownership
- Local-first by default: data stored on device and exported by user action.
- No required cloud service.
- Companion app only requests local-network/browser storage permissions needed for setup, caching, and export.
- User can delete local history and reset device from settings.

## Safety limits
- Prototype scope is **SELV USB power only (5V)**.
- Monitoring only; no high-power actuators.
- Not a life-safety, agricultural compliance, or medical system.

## Planned source tree and artifact policy
This repository is scaffold-first. Hardware implementation must be delivered as editable KiCad source files (not image-only schematics):

- `hardware/kicad/pot-pulse.kicad_pro` (planned)
- `hardware/kicad/pot-pulse.kicad_sch` (planned)
- `hardware/kicad/pot-pulse.kicad_pcb` (planned, if custom PCB is retained)

These files are **not created yet** in this initial scaffold.

Final BOM source of truth will live in KiCad schematic symbol properties and be exported to tracked `bom/bom.csv`.

## Current status
- ✅ Repository scaffold and execution backlog created
- 🚧 Documentation/backlog phase only (no firmware/app/KiCad implementation yet)

## Milestones
1. Requirements + architecture freeze
2. Datasheet-backed component selection
3. KiCad schematic and ERC
4. PCB layout and DRC
5. Firmware bring-up + simulated/bench validation
6. Companion app MVP + local export
7. Integration docs + fabrication-ready package

## Development quickstart (planned)
### Firmware
- Toolchain: PlatformIO (ESP-IDF framework)
- Target: ESP32-C3 dev module + custom carrier pin map

### Companion app
- TypeScript + Vite + local-first PWA behavior
- Connect to device over local HTTP/WebSocket

### Hardware
- KiCad 9 project under `hardware/kicad/`
- BOM exported to `bom/bom.csv`

(Implementation workspace will be added by backlog issues.)
