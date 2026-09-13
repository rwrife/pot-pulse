// User-owned data operations: canonical export -> downloadable files,
// local-file backup download, and restore-file parsing. All transfers are
// triggered by explicit user actions; nothing here auto-uploads anywhere.

import type { ExportPayload, ZoneSample } from "../api/types";

export interface CsvDoc {
  filename: string;
  content: string;
}

function csvEscape(v: string | number | null): string {
  const s = v === null ? "" : String(v);
  if (/[",\n]/.test(s)) return '"' + s.replace(/"/g, '""') + '"';
  return s;
}

// Deterministic history CSV derived from the canonical export document.
export function exportToCsv(doc: ExportPayload): CsvDoc {
  const header = [
    "zone_id",
    "timestamp",
    "monotonic_ms",
    "moisture_raw",
    "moisture_calibrated",
    "state",
    "quality",
  ];
  const lines = [header.join(",")];
  for (const s of doc.samples) {
    lines.push(
      [
        csvEscape(s.zone_id),
        csvEscape(s.timestamp),
        csvEscape(s.monotonic_ms),
        csvEscape(s.moisture_raw),
        csvEscape(s.moisture_calibrated),
        csvEscape(s.state),
        csvEscape(s.quality),
      ].join(","),
    );
  }
  const stamp = (doc.device_id || "potpulse").replace(/[^A-Za-z0-9._-]/g, "_");
  return { filename: `potpulse-export-${stamp}.csv`, content: lines.join("\n") + "\n" };
}

export function exportToJson(doc: ExportPayload): CsvDoc {
  const stamp = (doc.device_id || "potpulse").replace(/[^A-Za-z0-9._-]/g, "_");
  return {
    filename: `potpulse-export-${stamp}.json`,
    content: JSON.stringify(doc, null, 2) + "\n",
  };
}

// Parse a user-selected restore file BEFORE posting it (client-side guard;
// the device still validates atomically).
export function parseBackupFile(text: string): unknown {
  return JSON.parse(text);
}

// File-download abstraction, injectable for tests.
export type SaveFileFn = (filename: string, content: string, mime: string) => void;

export const browserSaveFile: SaveFileFn = (filename, content, mime) => {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
};

// Sort helper for trend rendering: chronological by (timestamp ?? monotonic).
export function chronological(samples: ZoneSample[]): ZoneSample[] {
  return [...samples].sort((a, b) => {
    const ta = a.timestamp ? Date.parse(a.timestamp) : a.monotonic_ms;
    const tb = b.timestamp ? Date.parse(b.timestamp) : b.monotonic_ms;
    return ta - tb;
  });
}
