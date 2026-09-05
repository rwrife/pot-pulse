# Pot Pulse MVP Architecture and Risk Baseline

**Status:** Proposed baseline; becomes the accepted MVP baseline when issue #1 is merged.

**Scope:** Issues #2–#8 must conform to this document or update it explicitly in the same pull request.

**Evidence boundary:** This document defines design intent. It is not electrical, simulation, bench, field, or certification evidence.

## 1. Purpose and constraints

Pot Pulse is a local-first, indoor plant-monitoring system. One USB-powered sensor node samples four soil-moisture zones plus device-level illuminance, temperature, and relative humidity. Firmware calibrates and stores readings, then exposes a versioned local API. A browser-based companion app owns setup, visualization, user-initiated export, and local backup/restore workflows.

The MVP is constrained to:

- SELV USB 5 V input and 3.3 V logic/sensors;
- at least four independent capacitive moisture channels;
- one device-level digital ambient sensor and one digital light sensor;
- local operation without a cloud account or cloud relay;
- a normal-mode average-current target of 250 mA or less;
- indoor operation at a nominal 10–35 °C ambient;
- a user-serviceable sensor-node assembly with a target carrier size of 120 mm × 80 mm or less and at least two mounting holes;
- a prototype electronics-plus-enclosure cost target of USD 35–60 and a soft ceiling of USD 75, excluding the host device, tools, shipping, and tax.

This architecture is authoritative for subsystem boundaries, ownership, safety constraints, and non-goals. [`hardware/requirements.md`](../hardware/requirements.md) remains authoritative for measurable hardware acceptance requirements. Any conflict must be resolved by updating both documents in the same pull request; neither silently overrides the other.

Exact components, packages, connector families, and the ADC/multiplexer topology are intentionally deferred to datasheet-backed component selection in issue #2. Those choices may refine this baseline but must preserve its external boundaries and requirements unless the architecture is revised explicitly.

## 2. System context

### 2.1 Context diagram

```text
                              user-owned local environment

  Capacitive probes (×4) ─┐
  Ambient sensor ─────────┼──> [ Pot Pulse sensor node ] <── USB 5 V + setup host
  Light sensor ───────────┘        |        |
                                   |        +── USB serial diagnostics/recovery
                                   |
                                   +── local HTTP / optional WebSocket
                                                |
                                                v
                                      [ Companion web app ]
                                         |             |
                                         v             v
                                  browser cache   CSV/JSON or
                                                  backup files
```

### 2.2 Block narrative

1. **Hardware platform:** accepts only SELV USB 5 V, protects and regulates the supply, connects the ESP32-C3 module to four moisture inputs and shared digital environmental sensors, and exposes programming/debug/test access.
2. **Firmware:** owns hardware initialization, scheduled sampling, quality flags, calibration transforms, bounded on-device history, configuration persistence, pairing authorization, and the versioned device API.
3. **Companion app:** discovers or connects to one device, guides naming and calibration, presents current/history data, manages user-entered metadata and reminders, and performs explicit export, backup, restore, and delete operations through documented APIs.
4. **User-controlled storage:** device flash is authoritative for device configuration, calibration, and bounded readings. Browser storage is a disposable app cache. User-created CSV/JSON and backup files are portable records controlled by the user.
5. **External systems:** the local network and USB host provide transport only. No cloud service is required for setup, normal monitoring, history, or export.

### 2.3 Trust and ownership boundaries

- The **sensor node** is the authority for raw readings, calibration parameters applied to those readings, sensor-health state, sampling cadence, and retained device history.
- The **app** is the authority for presentation state and browser-local cache. It must not silently reinterpret raw values or manufacture missing samples.
- The **user** owns exported data, plant/zone naming, reminder thresholds, and destructive-operation confirmation.
- The **local network is not assumed private enough for configuration writes**. Firmware must require a locally established pairing credential for state-changing API operations. Final authentication mechanics are a firmware/protocol decision, but unauthenticated writes are prohibited.
- Hardware provides electrical connectivity; firmware owns bus transactions. App code must not depend on pin numbers, I2C addresses, ADC channels, or component choices.

## 3. Subsystem responsibilities

### 3.1 Hardware

Hardware owns:

- USB input protection and 5 V-to-3.3 V power integrity;
- ESP32-C3 module, sensor, probe, debug, and test-point connectivity;
- signal conditioning and protection required by selected probes and external connectors;
- four electrically distinct moisture acquisition channels;
- I2C electrical implementation for the ambient and light sensors;
- connector keying/orientation documentation and enclosure mounting constraints.

Hardware does not own calibration policy, threshold meaning, retention policy, UI behavior, or network authorization.

### 3.2 Firmware

Firmware owns:

- deterministic sensor initialization and sample scheduling;
- conversion of hardware observations to typed readings with quality flags;
- dry/wet calibration storage and application per moisture zone;
- timestamps and bounded history retention;
- configuration validation, persistence, reset, and recovery;
- pairing credentials and authorization of state-changing operations;
- the `/api/v1` HTTP contract and optional WebSocket event stream;
- USB serial diagnostics and a recovery path that does not require Wi-Fi or cloud access.

Firmware must preserve raw moisture readings alongside calibrated values so calibration can be audited or replaced.

### 3.3 Companion app

The app owns:

- connection/setup guidance, zone naming, and calibration workflow;
- accessible live status and historical trend presentation;
- local reminder configuration without control of physical actuators;
- explicit CSV/JSON export, backup, restore, and deletion UX; firmware generates and validates canonical device data while the app owns user initiation, transfer, and local file handling;
- validation of user input before sending it to the device;
- clearly distinguishing offline/stale data from current device readings.

The app must consume the versioned protocol and must not directly encode board pinout or sensor-driver assumptions.

## 4. Interface contracts

| ID | Boundary | Producer / owner | Consumer | Inputs | Outputs / contract | Required verification |
|---|---|---|---|---|---|---|
| IF-PWR-01 | USB source → hardware | Hardware | Entire sensor node | SELV USB 5 V only | Protected input and regulated 3.3 V rail; normal-mode average target ≤250 mA | Schematic/ERC review; regulator/protection datasheet checks; bench rail and current measurements |
| IF-MOI-01 | Moisture probes → acquisition hardware | Hardware | Firmware sensor abstraction | Four independent analog probe signals and connector return/reference | Stable per-channel ADC observations plus open/out-of-range detectability where supported | Schematic pinout review; channel-isolation test; dry/wet bench characterization |
| IF-I2C-01 | Ambient/light sensors ↔ MCU | Hardware owns electrical bus; firmware owns transactions | Firmware drivers | 3.3 V I2C, selected addresses, interrupt lines only if documented | Typed temperature °C, relative humidity %RH, illuminance lux, and quality state | Datasheet pin/address validation; bus enumeration and fault-injection tests |
| IF-DBG-01 | USB/debug host ↔ node | Firmware owns command semantics; hardware owns physical path | Setup/diagnostic operator | USB serial or selected native USB path | Provisioning, diagnostics, and recovery/reset without cloud dependency | Repeatable flashing/recovery procedure and failed-Wi-Fi recovery test |
| IF-STO-01 | Firmware services ↔ device flash | Firmware | Firmware API/sampling services | Versioned settings, calibration, zone metadata, bounded readings | Atomic validated records; recoverable defaults after corrupt/incompatible data | Unit tests for migration, bounds, interrupted write, reset, and retention |
| IF-API-01 | Device ↔ companion app | Firmware owns `/api/v1`; app owns client use | Companion app | Pairing credential for writes; bounded query parameters | JSON status/history/config/calibration/export/backup/restore/delete/reset resources defined in [`docs/protocol.md`](protocol.md) | Shared schema/fixture tests plus local integration tests |
| IF-LIVE-01 | Device → companion app | Firmware | Companion app | Optional authenticated WebSocket subscription | Best-effort live events using the same reading schema as HTTP; HTTP remains functional fallback | Disconnect/reconnect, duplicate-event, stale-state, and polling-fallback tests |
| IF-FILE-01 | Companion app ↔ user files | Companion app | User and later app restore flow | Explicit user export/backup/restore action | Versioned UTF-8 CSV/JSON exports and validated backup files; no silent upload | Round-trip tests, malformed-file rejection, accessibility review, explicit-consent UX test |

Interface payload details belong in `docs/protocol.md`. When implementation begins, protocol changes that affect multiple subsystems require coordinated firmware fixtures and app tests in the same change or explicitly sequenced dependent changes.

## 5. End-to-end data flow

1. Firmware wakes or reaches the configured interval (30 seconds to 15 minutes) and requests one sample from each enabled sensor channel.
2. Drivers return a raw value or a typed failure. Firmware records a quality state; it does not replace a failed sample with a plausible number.
3. Firmware applies the stored per-zone dry/wet calibration to moisture observations while retaining the raw observation. Light and ambient values remain in their documented physical units.
4. Firmware assigns a timestamp and appends the sample to a bounded on-device ring buffer according to the active retention policy.
5. `GET /api/v1/status` returns the latest readings and health. Bounded history requests return retained records without exposing unrelated configuration secrets.
6. The app renders live and historical data, labels stale/offline values, and may cache responses for responsiveness. The cache is not a second source of truth.
7. Configuration, calibration, reset, delete, restore, and other writes require a pairing credential plus server-side validation. Destructive operations require explicit user confirmation.
8. Export or backup occurs only after a user action. The resulting file remains local unless the user independently moves or shares it.

### Time behavior

The MVP does not require a battery-backed real-time clock. Firmware must distinguish time that is synchronized from time that is only monotonic/relative. The protocol must expose enough status for the app to label unsynchronized samples rather than presenting them as exact wall-clock observations. The concrete synchronization mechanism is owned by firmware issue #6.

## 6. Failure and recovery behavior

- A missing or invalid sensor produces `sensor_error`/`unknown` quality, not a fabricated normal value.
- Missing calibration produces `uncalibrated`; it must not be displayed as a validated dry/ok/wet assessment.
- Loss of Wi-Fi does not stop sampling or bounded local retention.
- Loss of the optional WebSocket stream falls back to bounded HTTP polling.
- Corrupt or incompatible persisted configuration fails to validated defaults while preserving a documented recovery/reset path.
- USB recovery remains available when network onboarding fails.
- Storage pressure is handled by the documented bounded-retention policy; history must not grow without limit.
- The app marks cached readings stale when freshness cannot be established.

## 7. Security, privacy, and data handling

- No cloud account, cloud relay, remote telemetry service, or third-party analytics is required for MVP operation.
- Pairing establishes a local credential; configuration and destructive writes reject absent or invalid credentials.
- Secrets must not appear in status/history/export payloads, normal logs, or browser-visible error text.
- API inputs are length- and range-checked. History/export requests are bounded to protect memory and responsiveness.
- Device reset, history deletion, and restore are explicit, confirmable operations with deterministic outcomes.
- Browser storage is limited to setup/session state and useful local cache. The app provides user-visible deletion controls.

This is a prototype threat model, not a claim that a hostile LAN is fully defended. Security behavior must be revisited before any remote access, cloud relay, or unattended deployment is proposed.

## 8. Explicit MVP non-goals

The MVP provides informational monitoring only. It explicitly excludes:

- **automatic watering**, irrigation control, pumps, valves, relays, or any other actuator path;
- **mains voltage** input, switching, sensing, wiring, or control;
- cloud accounts, required internet services, remote fleet management, or silent telemetry;
- clinical, medical, life-safety, emergency-monitoring, agricultural, agronomic, yield, diagnosis, or treatment **claims**;
- outdoor/weatherproof deployment;
- guaranteed plant-health outcomes;
- OTA updates until a reliable local recovery route exists;
- multi-user identity federation.

A future proposal that adds an actuator, mains interface, remote access, or regulated-domain claim requires a new architecture and safety review; it is not an incremental MVP feature.

## 9. Risk register

Evidence classes are deliberately separated: static review, automated test/simulation, bench validation, and field observation are not interchangeable.

| ID | Risk | Likelihood / impact | Mitigation in design | Verification evidence | Verification owner |
|---|---|---|---|---|---|
| R-01 | Probe drift, media variation, or corrosion produces misleading moisture state | High / High | Capacitive probes; per-zone dry/wet calibration; retain raw values; quality/uncalibrated states; no watering claims | Calibration unit tests, bench dry/wet/repeatability characterization, later field observation labeled non-generalizable | Firmware lead + integration owner |
| R-02 | Long probe leads couple noise or channels influence each other | Medium / High | Independent channels; defined grounding/conditioning; bounded source impedance; sequential sampling/settling if required by selected ADC | Schematic/layout review, SPICE where applicable, bench cross-channel/noise test | Hardware lead |
| R-03 | USB source, protection, or regulator cannot support peak radio/sensor current | Medium / High | Datasheet-backed power budget, input protection, bulk/decoupling, rail test points, normal-average target | Datasheet calculation, ERC/DRC, static power analysis, bench startup/peak/average current and rail droop | Hardware lead |
| R-04 | I2C address, pull-up, or bus-fault choices make a sensor unavailable or hang sampling | Medium / Medium | Select compatible addresses; calculate pull-ups/capacitance; driver timeouts and bus recovery; health flags | Datasheet review, analyzer checks, unit fault injection, bench disconnect/short recovery | Hardware + firmware leads |
| R-05 | Wi-Fi onboarding fails or credentials are lost | Medium / High | USB provisioning/recovery and deterministic reset independent of cloud; preserve diagnostics | Automated provisioning-state tests and bench failed-network recovery procedure | Firmware lead |
| R-06 | Local API writes are changed by an unauthorized LAN client | Medium / High | Locally established pairing credential, authenticated writes, input validation, no secret leakage | API authorization/negative tests and protocol review | Firmware lead |
| R-07 | Flash wear, corruption, or unbounded retention loses settings/history or destabilizes device | Medium / High | Bounded ring buffer; atomic versioned persistence; validated defaults; controlled write cadence | Persistence, migration, interrupted-write, corruption, and retention-bound tests | Firmware lead |
| R-08 | App shows stale, missing, or uncalibrated values as trustworthy | Medium / High | End-to-end quality states, explicit freshness metadata, offline/stale UI, raw/calibrated distinction | Shared fixture tests, app state tests, accessibility/usability review | App lead |
| R-09 | Export/backup is incomplete, malformed, or leaks secrets | Low / High | Versioned schemas, explicit user action, allowlisted fields, bounded generation, round-trip validation | Golden-file/round-trip tests and inspection proving secret fields absent | App + firmware leads |
| R-10 | Enclosure placement biases light/ambient readings or exposes electronics to moisture | Medium / Medium | Venting and optical placement constraints; leads separate wet area from enclosure; indoor-only labeling | Mechanical review, bench side-by-side sensor comparison, later labeled placement study | Hardware + integration owner |
| R-11 | Scope expands into watering, mains, remote control, or unsupported claims | Medium / High | Non-goals are architecture gates; backlog/PR review rejects actuator and mains paths without a new safety architecture | Architecture trace review on every milestone and release checklist | Project owner |
| R-12 | Component lifecycle or source changes invalidate electrical assumptions | Medium / Medium | Manufacturer+MPN source of truth in KiCad; datasheet/lifecycle checks; documented alternatives; BOM validation | Issue #2 selection record, lifecycle snapshots, schematic-property/BOM consistency checks | Hardware/BOM owner |

## 10. Architecture decisions and downstream gates

| Decision / gate | Baseline | Deferred owner |
|---|---|---|
| Controller family | ESP32-C3 module | Exact module and package: issue #2 |
| Power source | SELV USB 5 V only; regulated 3.3 V logic | Regulator/protection implementation: issues #2–#3 |
| Moisture capacity | Four independent capacitive channels | ADC vs mux and connector choice: issue #2 |
| Environmental sensors | One digital ambient and one digital light sensor per node | Exact MPN/address/package: issue #2 |
| Data authority | Device flash for calibration/config/history; app cache is non-authoritative | Persistence format/limits: issue #6 |
| App boundary | Versioned local HTTP; optional WebSocket; no board assumptions | Concrete schema/fixtures: issues #6–#7 |
| Recovery | USB path works without Wi-Fi/cloud | Concrete command/state flow: issue #6 |
| PCB | Editable KiCad carrier remains the implementation path | Schematic: issue #3; layout: issue #5 |
| BOM | KiCad symbol properties are the source of truth | Selection: issue #2; export pipeline: issue #4 |
| Evidence | Static, simulation, bench, and field evidence reported separately | Integration/release matrix: issue #8 |

## 11. Backlog dependency graph

```text
#1 Architecture baseline
  ├──> #2 Datasheet-backed component selection
  │       └──> #3 Editable schematic + ERC
  │               └──> #4 Schematic-source BOM ──┐
  │                       └──> #5 PCB + DRC ──────┼──> #8 Integration/release
  │                               └──> #6 Firmware MVP ──> #7 App MVP ──┘
  └────────────────────────────────────────────────────────> #7 (architecture contract)
```

The ordering rules are:

1. #2 starts only after this baseline is merged.
2. #3 requires #2 so symbol, footprint, and electrical choices are datasheet-backed.
3. #4 requires a populated schematic from #3; #5 requires both that schematic and its source-of-truth BOM conventions.
4. #6 requires the schematic pin/interface contract and first PCB/testability baseline (#3 and #5).
5. #7 requires this architecture and a testable firmware protocol from #6.
6. #8 requires completed BOM, PCB, firmware, and app work (#4–#7).

Parallel exploratory work may occur, but a dependent issue must not claim acceptance completion before its gates are satisfied.

## 12. Change control

A downstream PR that changes an interface, authority boundary, safety envelope, explicit non-goal, or dependency gate must:

1. update this document and any affected protocol/requirements document;
2. identify affected hardware, firmware, app, BOM, and verification owners;
3. add or update verification evidence appropriate to the risk;
4. avoid presenting static analysis or simulation as bench/field evidence.
