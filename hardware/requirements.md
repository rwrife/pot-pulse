# Pot Pulse Hardware Requirements (Initial)

## Electrical
1. Input power: USB 5V SELV only.
2. Logic rail: regulated 3.3V for MCU and sensors.
3. Average current budget target: <= 250 mA in normal sampling mode.
4. Support at least 4 independent moisture sensing zones in MVP.
5. Sensor sampling interval configurable from 30 s to 15 min.

## Measurement and sensing
1. Report temperature and relative humidity from one digital ambient sensor.
2. Report illuminance from one digital light sensor per device.
3. Report per-zone calibrated moisture state using capacitive sensing channels.
4. Store timestamped readings with clear quality/status flags.

## Mechanical
1. Device footprint target: <= 120 mm x 80 mm custom carrier or equivalent module stack.
2. At least two mounting holes for enclosure integration.
3. User-serviceable sensor connectors (no permanent potted assembly).

## Connectivity and UX
1. Local setup path must work without cloud account.
2. Companion app must support live status + history export.
3. USB provisioning/recovery path required when Wi‑Fi onboarding fails.

## Environmental and safety
1. Indoor use only, nominal 10–35°C ambient.
2. No mains voltage exposure.
3. No medical, life-safety, or emergency-monitoring use.

## Cost target
- Prototype electronics + enclosure target range: **USD 35–60**
- Soft ceiling: **USD 75** (excluding phone/computer, tools, shipping, and tax)
- Per-line pricing remains TBD until live distributor sourcing.

## Verification requirements (later milestones)
- KiCad ERC pass (or documented exceptions)
- KiCad DRC pass (or documented exceptions)
- Datasheet-backed pinout and ratings validation
- Firmware build + test logs
- Companion app build + test logs
- Bring-up checklist with expected voltage/telemetry observations
