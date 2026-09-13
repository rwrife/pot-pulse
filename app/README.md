# Pot Pulse Companion App

Local-first companion app (issue #7): setup, live status + trends, and
user-owned export/backup/restore/delete — no cloud, no accounts. Consumes the
frozen `/api/v1` contract from [`docs/protocol.md`](../docs/protocol.md) as
implemented by firmware issue #6.

## Stack (pinned)

| Component | Version |
|---|---|
| Node.js (CI + local) | 22.x |
| TypeScript | 5.6.3 |
| Vite | 5.4.11 |
| Vitest | 2.1.8 |

Vanilla DOM + TypeScript (no framework) keeps the bundle ~15 kB and the
dependency surface minimal.

## Commands

```sh
cd app
npm ci            # pinned install from package-lock.json
npm run typecheck # tsc --noEmit
npm run test      # vitest run (47 unit tests)
npm run build     # production bundle -> app/dist/
npm run dev       # dev server (point it at a device on the LAN)
```

## How it talks to the device

- `src/api/client.ts` — typed client for every frozen resource:
  status, history, pair/request, calibration, config, export, backup,
  restore, history delete (`?confirm=confirm`), reset
  (`{level:"full-firmware",confirm:"confirm"}`). Sends `X-PotPulse-Token`
  once paired; maps `401/409/422/428` to typed errors; tolerates unknown
  additive fields (protocol forward-compat rule).
- `src/core/validation.ts` — mirrors the firmware's frozen bounds client-side
  (zone name ≤ 32, interval 30 s–15 min, `dry_raw != wet_raw`,
  `0 ≤ dry < wet ≤ 1`, history limit 1–500, `backup_version == 1`).
  The device always re-validates.

## Data ownership

- Device flash is authoritative; browser storage (`src/core/store.ts`) holds
  ONLY the device address, pairing token, and a presentation hint — never
  readings. Corrupt cache falls back to defaults.
- Export (CSV/JSON) and backup download happen only on explicit user action;
  the restore file is parsed + validated before posting, and the device
  applies it atomically-or-not-at-all.
- Two separate destructive controls: **Delete device history** (requires the
  frozen confirmation word; settings/calibration kept) and **Delete local app
  data** (wipes this browser's cache only).

## Accessibility basics (issue #7 AC 4)

- Landmarks + skip link; tablist with `aria-selected` and labelled panels.
- `role="status" aria-live="polite"` announcement line for every action result.
- Every input has a real `<label>`; token field is `type="password"`.
- ≥44 px touch targets, visible focus outlines, dark-mode tokens,
  `clamp()`/rem text that scales, WCAG-AA-matched palette, trend chart has a
  text `aria-label`, destructive actions confirm before firing.

## Evidence boundary (issue #7)

- **Static / automated:** `tsc --noEmit` clean; 47 vitest unit tests against a
  scripted fake of the frozen protocol (auth fail-closed, 409 pairing, 428
  confirmation, CSV escaping, uncalibrated-never-valid rendering);
  production Vite build; GitHub Actions `app` workflow.
- **Not claimed:** no end-to-end run against physical ESP32-C3 hardware and
  no screen-reader manual audit — both are bench/field work owned by issue #8.
