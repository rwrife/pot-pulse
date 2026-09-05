# Pot Pulse Device/App Protocol (MVP Contract)

**Status:** Proposed contract; implementation is owned by firmware issue #6 and consumer verification by app issue #7.

This protocol refines the subsystem boundary in [`architecture.md`](architecture.md). The architecture owns safety, trust, and data-authority rules; this document owns transport resources and payload semantics. A change that affects both must update both documents together.

## Transport and availability

- Primary transport: local HTTP with JSON payloads over the LAN.
- Optional transport: an authenticated WebSocket stream for best-effort live updates.
- Setup/recovery transport: USB serial commands for provisioning, diagnostics, and reset.
- HTTP remains the functional fallback when WebSocket delivery is unavailable.
- No cloud relay, cloud account, or internet connection is required.

## Security boundary

The local network is a transport boundary, **not a trusted authorization boundary**.

- Firmware must require a locally established pairing credential for configuration, calibration, export, backup, restore, history deletion, reset, and other state-changing or user-data operations.
- An absent, invalid, or expired credential must fail closed without changing device state.
- A minimal read-only first-run status response may be exposed before pairing only if it contains no credentials, network secrets, retained history, user metadata, or stable tracking identifier.
- Pairing and credential-storage mechanics are finalized in issue #6, but unauthenticated configuration writes are prohibited by the architecture baseline.
- Secrets must not be returned by status/history/export/backup resources or written to normal diagnostic logs.

## Resource contract

All resources are rooted at `/api/v1`. Firmware owns server behavior and canonical device data. The app owns client validation, user consent, transfer, local file handling, and presentation.

### Read and observation resources

- `GET /api/v1/status`
  - Returns device health, time quality, device-level environmental observations, and the latest moisture observation for every configured zone.
  - Must distinguish current, stale, sensor-error, and uncalibrated states.
- `GET /api/v1/history?zone=<id>&from=<ts>&to=<ts>&limit=<n>`
  - Returns a bounded page of retained samples.
  - Firmware validates the zone, time range, and maximum page size.
- Authenticated WebSocket subscription (optional)
  - Emits the same reading schema used by status/history.
  - Delivery is best effort; reconnecting clients recover through bounded HTTP history rather than assuming exactly-once events.

### State-changing and user-data resources

Each resource below requires a valid pairing credential and server-side schema/range validation.

- `POST /api/v1/calibration/<zone_id>`
  - Stores validated dry/wet reference points and calibration metadata for one moisture zone.
- `POST /api/v1/config`
  - Updates allowed settings such as sampling interval, thresholds, zone metadata, and retention policy.
- `POST /api/v1/export`
  - Generates a canonical, versioned CSV or JSON history export after explicit user action.
  - Firmware owns export content; the app owns download and user-selected file storage.
- `POST /api/v1/backup`
  - Generates a versioned backup of restorable settings, calibration, and zone metadata.
  - Credentials, network secrets, and transient samples are excluded unless a later version documents and secures them explicitly.
- `POST /api/v1/restore`
  - Accepts a bounded versioned backup, validates the complete payload before mutation, and applies it atomically or not at all.
  - Incompatible versions and malformed data are rejected without changing current settings.
- `DELETE /api/v1/history`
  - Deletes retained readings only after an explicit confirmation value in the request.
  - The response states whether deletion completed; partial success is not reported as complete.
- `POST /api/v1/reset`
  - Performs the documented reset level only after an explicit confirmation value.
  - Reset semantics must state whether configuration, calibration, history, pairing, and network settings are retained or erased.

The concrete pairing resource, headers, status codes, size limits, pagination shape, and confirmation-value format must be frozen with shared fixtures in issue #6 before issue #7 claims integration completion.

## Status payload sketch

Illuminance, temperature, and humidity are **device-level** observations because the MVP has one light sensor and one ambient sensor per node. Only moisture is per-zone.

```json
{
  "schema_version": 1,
  "device_id": "string",
  "timestamp": "ISO-8601-or-null",
  "time_quality": "synchronized|relative|unknown",
  "environment": {
    "light_lux": 0.0,
    "light_quality": "ok|sensor_error|stale",
    "temperature_c": 0.0,
    "humidity_rh": 0.0,
    "ambient_quality": "ok|sensor_error|stale"
  },
  "zones": [
    {
      "zone_id": "string",
      "moisture_raw": 0,
      "moisture_calibrated": 0.0,
      "state": "dry|ok|wet|unknown",
      "quality": "ok|sensor_error|uncalibrated|stale"
    }
  ]
}
```

Normative payload rules:

- `moisture_raw` is retained so calibration can be audited or replaced.
- `moisture_calibrated` and `state` must not imply a valid calibration when quality is `uncalibrated`.
- Unsynchronized time is represented explicitly; the app must not render it as exact wall-clock time.
- Missing or failed sensor readings are represented by quality state and nullable/omitted measurement fields in the final schema, never by fabricated normal values.
- Unknown additive fields are ignored by clients; incompatible breaking changes require a new API/schema version.

## Ownership and failure behavior

- Device flash is authoritative for device configuration, calibration, zone metadata, and bounded history.
- Browser storage is a disposable cache and may contain app presentation state. It is not authoritative device history.
- Loss of Wi-Fi does not stop scheduled sampling or bounded retention.
- Loss of WebSocket delivery falls back to HTTP status/history.
- The app labels cached or unsynchronized readings and does not silently manufacture missing samples.
- Export and backup occur only after user action. Files stay local unless the user independently moves or shares them.
- Restore, delete, and reset are deterministic, confirmable operations with all-or-nothing outcomes where device state is mutated.

## Out of scope for MVP

- Third-party cloud API contracts or cloud relay
- Multi-user identity federation
- Remote device fleet management
- Remote actuator control or watering automation
- Mains-powered or mains-connected interfaces
