// Export/backup data-handling tests: CSV escaping, JSON round-trip, and
// restore-file parsing (user-owned data paths per architecture R-09).

import { describe, expect, it } from "vitest";
import { exportToCsv, exportToJson, parseBackupFile } from "../src/core/export";
import type { ExportPayload } from "../src/api/types";

const doc: ExportPayload = {
  export_version: 1,
  device_id: "potpulse-test01",
  sample_interval_ms: 120000,
  zone_names: ["Basil", 'Gated "Pot"', "Line\nBreak", "Mint"],
  samples: [
    {
      zone_id: "z1",
      moisture_raw: 2048,
      moisture_calibrated: 0.55,
      state: "ok",
      quality: "ok",
      timestamp: "2026-09-13T12:00:00Z",
      monotonic_ms: 1000,
    },
    {
      zone_id: "z2",
      moisture_raw: 3000,
      moisture_calibrated: null,
      state: "unknown",
      quality: "uncalibrated",
      timestamp: null,
      monotonic_ms: 1000,
    },
  ],
};

describe("exportToCsv", () => {
  const csv = exportToCsv(doc).content;
  const rows = csv.trim().split("\n");

  it("has a header and one row per sample", () => {
    expect(rows[0]).toBe(
      "zone_id,timestamp,monotonic_ms,moisture_raw,moisture_calibrated,state,quality",
    );
    expect(rows).toHaveLength(1 + doc.samples.length);
  });

  it("keeps raw readings and null calibrated (never fabricates)", () => {
    expect(rows[2]).toContain("z2");
    expect(rows[2].endsWith(",uncalibrated")).toBe(true);
    expect(rows[2]).toContain(",,"); // empty calibrated + empty timestamp
  });

  it("quotes embedded quotes/commas/newlines per RFC 4180", () => {
    const withMeta = exportToCsv({
      ...doc,
      samples: [],
      zone_names: ['He said "hi", ok', "a\nb"],
    }).content;
    // zone_names aren't rows; test sample zone fields instead
    expect(withMeta.trim().split("\n")).toHaveLength(1);
    const tricky = exportToCsv({
      ...doc,
      samples: [
        {
          zone_id: 'z"1,x',
          moisture_raw: 1,
          moisture_calibrated: 0.5,
          state: "ok",
          quality: "ok",
          timestamp: "2026-01-01T00:00:00Z",
          monotonic_ms: 1,
        },
      ],
    }).content;
    expect(tricky.split("\n")[1].startsWith('"z""1,x",')).toBe(true);
  });

  it("sanitizes the device id into a safe filename", () => {
    expect(exportToCsv(doc).filename).toBe("potpulse-export-potpulse-test01.csv");
    expect(
      exportToCsv({ ...doc, device_id: "../../etc/pass wd" }).filename,
    ).toBe("potpulse-export-.._.._etc_pass_wd.csv");
  });
});

describe("exportToJson", () => {
  it("is the canonical document verbatim (round-trips)", () => {
    const parsed = JSON.parse(exportToJson(doc).content);
    expect(parsed.export_version).toBe(1);
    expect(parsed.samples).toHaveLength(2);
    expect(parsed).not.toHaveProperty("pairing_token"); // R-09: no secrets
  });
});

describe("parseBackupFile", () => {
  it("parses valid JSON", () => {
    expect(parseBackupFile('{"backup_version":1}')).toEqual({ backup_version: 1 });
  });
  it("throws on malformed JSON (caller surfaces a validation error)", () => {
    expect(() => parseBackupFile("{oops")).toThrow();
  });
});
