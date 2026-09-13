// Pure client-side validation mirroring the firmware's frozen bounds
// (docs/protocol.md). The server always re-validates; failing fast here
// gives the UI inline errors before a doomed round-trip.

import { LIMITS } from "../api/types";

export interface ValidationResult {
  ok: boolean;
  errors: string[];
}

function ok(errors: string[]): ValidationResult {
  return { ok: errors.length === 0, errors };
}

export function validateZoneName(name: string): ValidationResult {
  const errors: string[] = [];
  if (name.trim().length === 0) errors.push("Zone name must not be empty.");
  if (name.length > LIMITS.maxZoneNameLen)
    errors.push(`Zone name must be at most ${LIMITS.maxZoneNameLen} characters.`);
  return ok(errors);
}

export function validateZoneNames(names: string[]): ValidationResult {
  const errors: string[] = [];
  if (names.length !== LIMITS.zoneCount)
    errors.push(`Exactly ${LIMITS.zoneCount} zone names are required.`);
  names.forEach((n, i) => {
    const r = validateZoneName(n);
    if (!r.ok) errors.push(`Zone ${i + 1}: ${r.errors.join(" ")}`);
  });
  return ok(errors);
}

export function validateSampleInterval(ms: number): ValidationResult {
  const errors: string[] = [];
  if (!Number.isFinite(ms)) errors.push("Interval must be a number.");
  else if (ms < LIMITS.minSampleIntervalMs || ms > LIMITS.maxSampleIntervalMs)
    errors.push(
      `Interval must be between ${LIMITS.minSampleIntervalMs / 1000} s and ${LIMITS.maxSampleIntervalMs / 60000} min.`,
    );
  return ok(errors);
}

export function validateCalibration(input: {
  dryRaw: number;
  wetRaw: number;
  dryThreshold: number;
  wetThreshold: number;
}): ValidationResult {
  const errors: string[] = [];
  const { dryRaw, wetRaw, dryThreshold, wetThreshold } = input;
  if (!Number.isInteger(dryRaw) || !Number.isInteger(wetRaw))
    errors.push("Raw calibration endpoints must be integers.");
  else if (dryRaw === wetRaw)
    errors.push("Dry and wet endpoints must differ (avoids divide-by-zero).");
  if (!(dryThreshold >= 0 && dryThreshold < wetThreshold && wetThreshold <= 1))
    errors.push("Thresholds must satisfy 0 ≤ dry < wet ≤ 1.");
  return ok(errors);
}

export function validateHistoryLimit(limit: number): ValidationResult {
  const errors: string[] = [];
  if (
    !Number.isInteger(limit) ||
    limit < LIMITS.historyLimitMin ||
    limit > LIMITS.historyLimitMax
  )
    errors.push(
      `History page size must be between ${LIMITS.historyLimitMin} and ${LIMITS.historyLimitMax}.`,
    );
  return ok(errors);
}

export function validateBackupDoc(doc: unknown): ValidationResult {
  const errors: string[] = [];
  if (typeof doc !== "object" || doc === null) {
    return ok(["Backup file must contain a JSON object."]);
  }
  const d = doc as Record<string, unknown>;
  if (d.backup_version !== LIMITS.backupVersion)
    errors.push(`Only backup_version ${LIMITS.backupVersion} is accepted.`);
  if (typeof d.sample_interval_ms !== "number")
    errors.push("Missing sample_interval_ms.");
  else {
    const r = validateSampleInterval(d.sample_interval_ms);
    errors.push(...r.errors);
  }
  if (!Array.isArray(d.zone_names))
    errors.push("Missing zone_names array.");
  else {
    const r = validateZoneNames(d.zone_names.map(String));
    errors.push(...r.errors);
  }
  if (!Array.isArray(d.calibrations)) errors.push("Missing calibrations array.");
  else {
    for (const c of d.calibrations) {
      if (
        typeof c !== "object" ||
        c === null ||
        typeof (c as Record<string, unknown>).dry_raw !== "number" ||
        typeof (c as Record<string, unknown>).wet_raw !== "number"
      ) {
        errors.push("Each calibration needs numeric dry_raw/wet_raw.");
        break;
      }
    }
  }
  return ok(errors);
}
