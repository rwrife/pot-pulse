# Companion App Plan (Scaffold)

## Responsibilities
- Device discovery/onboarding on local network.
- Zone naming, calibration workflow, and threshold configuration.
- Live status dashboard and historical trend views.
- Local export (CSV/JSON) and backup/restore operations.

## Setup flow
1. Connect to device (USB-assisted or local network).
2. Name zones and assign plant/context metadata.
3. Run dry/wet calibration for each moisture channel.
4. Configure reminder thresholds and sampling profile.

## Data ownership and privacy
- User-owned local data by default.
- No required cloud account.
- Explicit export/delete controls.
- Any optional remote sync must be opt-in and out-of-scope for MVP.

## Protocol boundary
The app consumes documented local endpoints from `docs/protocol.md` and should avoid direct hardware assumptions.

Current state: planning only; no app code created yet.
