# Pot Pulse — Implementation Plan

## Scope and architecture
Pot Pulse is a low-voltage sensing node plus local-first companion app. The normative MVP subsystem boundaries, interfaces, safety constraints, non-goals, and risk ownership are defined in [`docs/architecture.md`](docs/architecture.md). Downstream changes that alter those boundaries must update the architecture in the same pull request.

### Subsystems
1. **Sensor node (ESP32-C3 firmware)**
   - Samples soil moisture channels, ambient light, and temp/humidity.
   - Stores short local history and serves local API.
2. **Hardware platform (KiCad project)**
   - USB-powered sensing carrier with protection, connectors, and test points.
   - Supports common capacitive probe modules and I2C sensors.
3. **Companion app (local web app)**
   - Setup, zone naming, calibration, status/trends, export, and backup/restore.

## Technology choices (and rationale)
- **ESP32-C3**: low-cost Wi‑Fi + USB support, broad maker ecosystem.
- **KiCad**: editable open hardware source and reproducible outputs.
- **PlatformIO + ESP-IDF**: reproducible firmware builds and testable configuration.
- **TypeScript + Vite PWA**: fast cross-device local UI without app-store dependency.
- **CSV/JSON exports**: transparent, user-owned data portability.

## Milestones and dependency order

| Milestone | GitHub issue | Depends on | Exit gate |
|---|---:|---|---|
| Architecture and risk baseline | #1 | None | System context, interface ownership, non-goals, risk mitigations, and verification owners are agreed |
| Datasheet-backed component selection | #2 | #1 | Critical parts have manufacturer/MPN, electrical/package validation, lifecycle/availability snapshot, and KiCad field conventions |
| Editable schematic and ERC | #3 | #1, #2 | KiCad source captures the architecture interfaces and passes ERC or documents every exception |
| Schematic-source BOM | #4 | #2, #3 | `bom/bom.csv` is reproducibly exported from populated KiCad properties and non-schematic items are tracked separately |
| PCB layout and DRC | #5 | #3, #4 | Editable layout implements mechanical/testability constraints and passes DRC or documents every exception |
| Firmware MVP | #6 | #3, #5 | Pinned build, sampling/calibration/persistence/recovery implementation, `/api/v1` fixtures, and automated tests are reproducible |
| Companion app MVP | #7 | #1, #6 | Setup, status/history, accessible UX, export/backup/restore/delete flows build and test against the firmware contract |
| Integration and release package | #8 | #4, #5, #6, #7 | Bring-up/assembly docs and mature fabrication/release artifacts carry an explicit static/simulation/bench/field evidence matrix |

Dependency policy:

- A dependent milestone may be explored early, but it cannot claim acceptance completion until all listed gates have landed.
- Component and electrical decisions flow from manufacturer datasheets into KiCad properties and then into the exported BOM; the preliminary planning CSV is not a source of truth.
- Firmware owns physical sensor behavior and the device API; the app consumes the versioned protocol and does not encode board-level assumptions.
- Issue #8 is the only release/fabrication gate and must not promote placeholders or static checks as physical validation.

## Testing strategy
- **Static checks**: lint/format for firmware and app.
- **Firmware tests**: unit tests for calibration math and payload encoding; hardware-abstraction tests where practical.
- **App tests**: unit tests for state/store logic; integration tests for setup + export workflows.
- **Hardware verification**: ERC/DRC evidence, pinout checks, and measurement checklist in bring-up docs.
- **Boundary reporting**: explicitly separate static analysis, simulation, bench tests, and field usage.

## Packaging/distribution plan
- Firmware release artifacts: tagged binaries + flashing instructions.
- Companion app: local web bundle served from device or local host with offline fallback.
- Hardware: KiCad sources, PDF schematic, Gerbers/drills, BOM/CPL when applicable.

## Risks
The authoritative risk register is [`docs/architecture.md`](docs/architecture.md#9-risk-register). It assigns mitigations, evidence types, and verification owners for probe drift/corrosion, analog noise, power integrity, I2C faults, onboarding/recovery, API authorization, flash persistence, stale UI data, export privacy, enclosure bias/moisture exposure, scope creep, and component lifecycle.

Risk status must be updated where the evidence is produced. Static review, automated test/simulation, bench validation, and field observation remain distinct evidence classes.

## Explicit non-goals
- Autonomous irrigation or actuator control.
- Mains-powered designs.
- Agricultural certification/guarantees.
- Clinical or biological diagnosis.
- Cloud-first data architecture.
