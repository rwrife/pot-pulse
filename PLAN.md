# Pot Pulse — Implementation Plan

## Scope and architecture
Pot Pulse is a low-voltage sensing node plus local-first companion app.

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
1. Finalize measurable requirements and safety envelope.
2. Select candidate components via manufacturer datasheets and lifecycle checks.
3. Create KiCad project + full schematic (power/protection/connectors/debug/test points), run ERC.
4. Export schematic-backed `bom/bom.csv` with manufacturer/MPN/source fields.
5. Create PCB (if retained), run DRC, and document constraints.
6. Implement firmware sampling + calibration + local API + persistent settings.
7. Implement companion app setup/status/history/export flow.
8. Perform integration bring-up and document expected measurements.
9. Publish fabrication/release artifacts once design matures.

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
- Soil moisture probe drift/corrosion and calibration instability.
- Sensor placement variability across different pots and media.
- Wi‑Fi onboarding friction in home networks.
- Scope creep toward automation (watering control) beyond MVP safety bounds.

## Explicit non-goals
- Autonomous irrigation or actuator control.
- Mains-powered designs.
- Agricultural certification/guarantees.
- Clinical or biological diagnosis.
- Cloud-first data architecture.
