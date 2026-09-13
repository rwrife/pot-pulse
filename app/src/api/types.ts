// Payload types mirroring docs/protocol.md (MVP contract, schema_version 1).
// Unknown additive fields are ignored by clients per the protocol; these
// interfaces therefore only declare the fields the app consumes.

export type Quality = "ok" | "sensor_error" | "uncalibrated" | "stale";
export type ZoneState = "dry" | "ok" | "wet" | "unknown";
export type TimeQuality = "synchronized" | "relative" | "unknown";

export interface Environment {
  light_lux?: number | null;
  light_quality: Quality;
  temperature_c?: number | null;
  humidity_rh?: number | null;
  ambient_quality: Quality;
}

export interface ZoneSample {
  zone_id: string;
  moisture_raw: number;
  moisture_calibrated: number | null;
  state: ZoneState;
  quality: Quality;
  timestamp: string | null;
  monotonic_ms: number;
}

export interface StatusPayload {
  schema_version: number;
  device_id?: string; // absent/empty pre-pairing (no stable tracking id)
  timestamp: string | null;
  time_quality: TimeQuality;
  paired: boolean;
  environment: Environment;
  zones: ZoneSample[];
}

export interface HistoryPage {
  schema_version: number;
  zone_id: string;
  items: ZoneSample[];
  count: number;
}

export interface PairRequestPayload {
  pair_id: string;
  nonce: string;
  confirm_over: string;
}

export interface CalibrationPayload {
  dry_raw: number;
  wet_raw: number;
  dry_threshold?: number;
  wet_threshold?: number;
}

export interface ConfigPayload {
  sample_interval_ms?: number;
  zone_names?: string[];
}

export interface OkPayload {
  ok: string;
  applied?: string[];
  deleted?: number;
  complete?: boolean;
}

// POST /api/v1/export canonical document.
export interface ExportPayload {
  export_version: number;
  device_id: string;
  sample_interval_ms: number;
  zone_names: string[];
  samples: ZoneSample[];
}

// POST /api/v1/backup canonical document (no credentials, no samples).
export interface BackupCalibration {
  zone_id: string | number;
  dry_raw: number;
  wet_raw: number;
  dry_threshold?: number;
  wet_threshold?: number;
}

export interface BackupPayload {
  backup_version: number;
  sample_interval_ms: number;
  zone_names: string[];
  calibrations: BackupCalibration[];
}

export interface ErrorPayload {
  error: string;
  message: string;
}

// Protocol-frozen bounds (docs/protocol.md "Frozen mechanics").
export const LIMITS = {
  minSampleIntervalMs: 30_000,
  maxSampleIntervalMs: 900_000,
  maxZoneNameLen: 32,
  zoneCount: 4,
  historyLimitMin: 1,
  historyLimitMax: 500,
  historyLimitDefault: 100,
  confirmWord: "confirm",
  backupVersion: 1,
} as const;
