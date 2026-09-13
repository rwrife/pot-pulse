// Validation mirrors the firmware's frozen bounds — these values must match
// firmware/src/pp (config.cpp / calibration.cpp) and docs/protocol.md.

import { describe, expect, it } from "vitest";
import {
  validateBackupDoc,
  validateCalibration,
  validateHistoryLimit,
  validateSampleInterval,
  validateZoneName,
  validateZoneNames,
} from "../src/core/validation";

describe("validateZoneName", () => {
  it("accepts a normal name", () =>
    expect(validateZoneName("Basil").ok).toBe(true));
  it("rejects empty/whitespace", () =>
    expect(validateZoneName("   ").ok).toBe(false));
  it("rejects > 32 chars (frozen limit)", () =>
    expect(validateZoneName("x".repeat(33)).ok).toBe(false));
  it("accepts exactly 32 chars", () =>
    expect(validateZoneName("x".repeat(32)).ok).toBe(true));
});

describe("validateZoneNames", () => {
  it("requires exactly 4 names (z1..z4 zones)", () => {
    expect(validateZoneNames(["a", "b", "c"]).ok).toBe(false);
    expect(validateZoneNames(["a", "b", "c", "d"]).ok).toBe(true);
  });
});

describe("validateSampleInterval", () => {
  it("accepts the frozen range 30 s..15 min", () => {
    expect(validateSampleInterval(30_000).ok).toBe(true);
    expect(validateSampleInterval(900_000).ok).toBe(true);
    expect(validateSampleInterval(120_000).ok).toBe(true);
  });
  it("rejects out-of-range values", () => {
    expect(validateSampleInterval(29_999).ok).toBe(false);
    expect(validateSampleInterval(900_001).ok).toBe(false);
    expect(validateSampleInterval(NaN).ok).toBe(false);
  });
});

describe("validateCalibration", () => {
  it("matches firmware rule dry_raw != wet_raw", () => {
    expect(
      validateCalibration({ dryRaw: 100, wetRaw: 100, dryThreshold: 0.3, wetThreshold: 0.7 })
        .ok,
    ).toBe(false);
    expect(
      validateCalibration({ dryRaw: 100, wetRaw: 3000, dryThreshold: 0.3, wetThreshold: 0.7 })
        .ok,
    ).toBe(true);
  });
  it("allows reversed polarity (wet_raw < dry_raw)", () => {
    expect(
      validateCalibration({ dryRaw: 3000, wetRaw: 100, dryThreshold: 0.3, wetThreshold: 0.7 })
        .ok,
    ).toBe(true);
  });
  it("enforces 0 <= dry_threshold < wet_threshold <= 1", () => {
    expect(
      validateCalibration({ dryRaw: 1, wetRaw: 2, dryThreshold: 0.7, wetThreshold: 0.3 })
        .ok,
    ).toBe(false);
    expect(
      validateCalibration({ dryRaw: 1, wetRaw: 2, dryThreshold: -0.1, wetThreshold: 0.5 })
        .ok,
    ).toBe(false);
    expect(
      validateCalibration({ dryRaw: 1, wetRaw: 2, dryThreshold: 0.5, wetThreshold: 1.1 })
        .ok,
    ).toBe(false);
  });
  it("rejects non-integer raw endpoints", () => {
    expect(
      validateCalibration({ dryRaw: 1.5, wetRaw: 2, dryThreshold: 0.3, wetThreshold: 0.7 })
        .ok,
    ).toBe(false);
  });
});

describe("validateHistoryLimit", () => {
  it("enforces 1..500 integer", () => {
    expect(validateHistoryLimit(100).ok).toBe(true);
    expect(validateHistoryLimit(0).ok).toBe(false);
    expect(validateHistoryLimit(501).ok).toBe(false);
    expect(validateHistoryLimit(1.5).ok).toBe(false);
  });
});

describe("validateBackupDoc", () => {
  const good = {
    backup_version: 1,
    sample_interval_ms: 120000,
    zone_names: ["a", "b", "c", "d"],
    calibrations: [
      { zone_id: "z1", dry_raw: 100, wet_raw: 3000, dry_threshold: 0.3, wet_threshold: 0.7 },
    ],
  };
  it("accepts a v1 backup shaped like firmware POST /api/v1/backup", () =>
    expect(validateBackupDoc(good).ok).toBe(true));
  it("rejects incompatible backup_version (firmware answers 422)", () =>
    expect(validateBackupDoc({ ...good, backup_version: 2 }).ok).toBe(false));
  it("rejects non-objects and missing arrays", () => {
    expect(validateBackupDoc(null).ok).toBe(false);
    expect(validateBackupDoc({ ...good, zone_names: undefined }).ok).toBe(false);
    expect(validateBackupDoc({ ...good, calibrations: "no" }).ok).toBe(false);
  });
});
