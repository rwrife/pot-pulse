# Firmware Plan (Scaffold)

## Responsibilities
- Initialize and sample moisture, light, and ambient sensors.
- Apply per-zone calibration transforms.
- Publish current readings and recent history through local API.
- Persist configuration, calibration metadata, and retention settings.
- Provide provisioning/recovery behavior for failed network setup.

## Interfaces
- Sensor drivers (I2C + analog/ADC abstraction)
- Local HTTP/WebSocket telemetry API
- USB serial diagnostics and setup commands

## Provisioning and update approach
- Initial setup via USB serial or temporary AP onboarding flow.
- OTA update path considered only after stable local recovery route exists.
- Recovery mode must support full settings reset without cloud dependency.

## Test strategy
- Unit tests for calibration and threshold-state logic.
- Hardware-abstraction tests for payload schema and sensor status flags.
- Manual bench test checklist for first hardware bring-up (voltage rails, sensor detection, sample cadence).

Current state: planning only; no firmware project created yet.
