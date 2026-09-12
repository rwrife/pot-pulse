# Firmware (Pot Pulse sensor node)

ESP32-C3 firmware MVP for the pot-pulse carrier (issue #5 board). Local-first:
HTTP JSON API on the LAN plus USB-serial provisioning/recovery; no cloud.

## Layout

- `src/pp/` — portable core (C++17, no Arduino includes): sensor drivers,
  calibration, bounded history, config/pairing store, JSON renderers.
  Compiled in both targets and unit-tested natively.
- `src/main.cpp` — ESP32 device layer: pin map, WebServer endpoints, USB
  serial console, flash persistence (Preferences + LittleFS).
- `test/test_core/` — Unity tests (native env) with fake I2C/clock/KV HALs.

## Toolchain (pinned, AC 1)

| Component | Version |
|---|---|
| PlatformIO Core | 6.1.18 |
| platform-espressif32 | 6.10.0 |
| Arduino core (framework-arduinoespressif32) | 2.0.17 |
| ArduinoJson | 7.4.2 |
| Unity | 2.6.1 |
| Host compiler | g++ `-std=gnu++17` |

Pins live in `platformio.ini` (`espressif32@6.10.0`, `native@1.2.1`,
`ArduinoJson@7.4.2`). Any bump must re-run both commands below and refresh
this file.

## Repeatable build/test commands

```sh
cd firmware
pio test -e native      # portable-core unit tests (19 cases)
pio run  -e esp32c3     # device firmware binary (ESP32-C3)
```

Verified on 2026-09-12 (issue #6 implementing PR):
- `pio test -e native` → `19 test cases: 19 succeeded`
- `pio run -e esp32c3` → `SUCCESS`, RAM 12.2% (40,100/327,680 B),
  Flash 68.0% (891,772/1,310,720 B)

## Flashing (bench, once hardware is available)

```sh
pio run -t upload --upload-port /dev/ttyACM0
pio device monitor
```

## USB serial console (IF-DBG-01 — recovery without Wi-Fi/cloud)

Native USB CDC at 115200. Commands:
`status` · `pair list` · `pair confirm <pair_id>` · `wifi <ssid> <pass>` ·
`reset wifi` · `reset full-firmware` · `help`

Pairing: the app POSTs `/api/v1/pair/request`, then the user runs
`pair confirm <pair_id>` on this console; the 128-bit token is printed ONLY
on the local serial console (out-of-band confirmation, architecture §7).

## Reset levels (protocol `POST /api/v1/reset`)

- `full-firmware` (requires `confirm:"confirm"` + pairing): erases pairing
  tokens, settings, zone metadata, calibration, retained history. Wi-Fi
  credentials are RETAINED so the device stays reachable on the LAN.
- Serial `reset wifi` erases only network credentials.
- A `factory` level erasing Wi-Fi too is deferred until a bench procedure
  exists (needs physical access anyway).

## Evidence boundary (issue #6)

- **Static / automated:** datasheet-transcribed drivers with citations
  (SHT4x DS v6.4, VEML7700 Rev 1.8 + AN 84323, ADS1115 2024 datasheet);
  19 native unit tests; successful ESP32-C3 compile+link.
- **Not claimed:** no bench run on real silicon/sensors, no RF/network
  integration test, no EMC/thermal/field evidence. End-to-end pairing +
  API behavior on hardware is bench work owned by issue #8.
- The HTTP request-handling paths (WebServer glue) are compile-verified only;
  their JSON payloads and state machines ARE unit-tested at the core level.
