# Pot Pulse Device/App Protocol (Initial Draft)

## Transport assumptions
- Primary: local HTTP (JSON) over LAN
- Optional: WebSocket stream for live updates
- Fallback/setup: USB serial commands for provisioning and diagnostics

## Security assumptions (MVP)
- Local network is the trust boundary for initial prototype.
- Device should require a local pairing token before allowing configuration writes.
- Read-only status endpoints may be optionally exposed unauthenticated on first-run only.
- No cloud relay in MVP.

## Proposed resources
- `GET /api/v1/status`
  - Returns current per-zone moisture/light/ambient values plus sensor health flags.
- `GET /api/v1/history?zone=<id>&from=<ts>&to=<ts>`
  - Returns bounded historical samples.
- `POST /api/v1/calibration/<zone_id>`
  - Stores calibration points and metadata.
- `POST /api/v1/config`
  - Updates sampling interval, thresholds, retention policy.
- `POST /api/v1/export`
  - Produces user-initiated CSV/JSON payload.
- `POST /api/v1/reset`
  - Controlled reset with explicit confirmation token.

## Data model sketch
```json
{
  "device_id": "string",
  "timestamp": "ISO-8601",
  "zones": [
    {
      "zone_id": "string",
      "moisture_raw": 0,
      "moisture_calibrated": 0.0,
      "light_lux": 0.0,
      "state": "dry|ok|wet|unknown",
      "quality": "ok|sensor_error|uncalibrated"
    }
  ],
  "ambient": {"temperature_c": 0.0, "humidity_rh": 0.0, "quality": "ok|sensor_error"}
}
```

## Out of scope for MVP
- Third-party cloud API contracts
- Multi-user auth federation
- Remote device fleet management
