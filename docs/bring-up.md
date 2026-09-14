# Pot Pulse Bring-Up Guide (Issue #8)

This guide is the integration handoff for first board power-up and app/firmware validation.

> Evidence boundary: this document defines **procedure and expected checkpoints**. It is not itself bench evidence.

## 1) Pre-flight

- Use SELV USB power only (5 V).
- Do not connect wet probes during first rail checks.
- Required tools: DMM, USB-C cable, USB serial terminal, local browser, optional oscilloscope.

## 2) Wiring and pinout

```text
USB-C host
   |
   v
[J1 USB-C] -> F1 PPTC -> +5V_PROTECTED -> U1 TPS62162 -> +3V3
                                                |
                                     +----------+----------+
                                     |          |          |
                                    U2         U4         I2C sensors
                                  ESP32-C3   ADS1115      U5 SHT40 / U6 VEML7700
                                     |
                    +----------------+----------------+
                    |                |                |
                  J2 zone1         J3 zone2         J4/J5 zone3/4
```

### Zone connectors (J2–J5)

| Pin | Net | Meaning |
|---|---|---|
| 1 | +3V3 | Probe power |
| 2 | GND | Probe return |
| 3 | PROBEn_RAW | Analog moisture signal |

### Debug header (J6)

| Pin | Net |
|---|---|
| 1 | +3V3 |
| 2 | GND |
| 3 | EN |
| 4 | BOOT_GPIO9 |
| 5 | U0RXD |
| 6 | U0TXD |

## 3) First power sequence

1. Connect USB-C with no probes attached.
2. Measure rails at test pads before any functional test:
   - TP1 `VBUS`
   - TP2 `+5V_PROTECTED`
   - TP3 `+3V3`
   - TP4 `GND`
3. Confirm no unexpected heating on U1/U2/U7.
4. Open USB serial console @ 115200 and run `status`.

## 4) Expected electrical checkpoints

| Checkpoint | Expected range/state | Notes |
|---|---|---|
| TP1 VBUS | 4.75–5.25 V | USB source dependent |
| TP2 +5V_PROTECTED | close to TP1 (small PPTC drop) | Large drop indicates overcurrent path |
| TP3 +3V3 | 3.23–3.37 V target band | TPS62162 nominal 3.3 V rail |
| TP5/TP6 I2C lines | Idle HIGH near +3V3 | pull-ups R4/R5 |
| EN / BOOT pins | HIGH at idle | reset/strap sanity |

## 5) Firmware/API telemetry checkpoints

1. Pairing request (LAN): `POST /api/v1/pair/request` -> `202` with `pair_id` and `nonce`.
2. Confirm pairing over USB serial: `pair confirm <pair_id>` -> token printed only on serial.
3. Authenticated status request with `X-PotPulse-Token`:
   - `schema_version=1`
   - `time_quality` present
   - all four zones present (`z1..z4`)
   - uncalibrated zones report `quality=uncalibrated`
4. Calibrate each zone with dry/wet endpoints.
5. Verify history pagination returns bounded samples (`limit` within 1..500).

## 6) Calibration flow

Per zone:
1. Capture dry reference in air/dry medium.
2. Capture wet reference in saturated medium.
3. `POST /api/v1/calibration/zN` with `dry_raw`, `wet_raw`, thresholds.
4. Re-check `/api/v1/status` and ensure zone quality transitions from `uncalibrated` to `ok`.
5. Repeat for z1..z4.

## 7) Troubleshooting quick map

| Symptom | Probable cause | Action |
|---|---|---|
| No +3V3 at TP3 | power-path fault (J1/F1/U1/input passives) | Stop; inspect orientation and shorts |
| I2C stuck low | short or wrong pull-up/population | Isolate U4/U5/U6 branch, inspect R4/R5 |
| Pairing always 401 | missing/invalid token header | re-run pair request + serial confirm |
| Zone always uncalibrated | calibration rejected or not persisted | validate dry/wet values and retry |
| USB not enumerating | data-path/ESD path issue on DM/DP | inspect J1/U7 routing and solder joints |

## 8) Current status from static evidence

- ERC: clean (`0 errors, 0 warnings`) in `docs/evidence/2026-09-14/erc.rpt`.
- DRC: blocked for release (`5 unconnected`, plus parity warnings) in `docs/evidence/2026-09-14/drc.json`.
- Therefore this guide is a **bring-up plan**, not proof of completed bring-up.
