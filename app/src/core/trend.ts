// Trend + presentation helpers. Kept pure so unit tests can assert the
// exact protocol-rendering rules (uncalibrated never looks valid, relative
// time is never shown as wall-clock).

import type { StatusPayload, ZoneSample } from "../api/types";
import { chronological } from "./export";

export interface Sparkline {
  points: string; // svg polyline points
  width: number;
  height: number;
  hasData: boolean;
}

// Build an SVG polyline from calibrated moisture values (0..1) in the
// 0..width x 0..height box. Samples without a valid calibration are skipped.
export function sparkline(
  samples: ZoneSample[],
  width = 280,
  height = 60,
): Sparkline {
  const ordered = chronological(samples).filter(
    (s) => s.quality === "ok" && s.moisture_calibrated !== null,
  );
  if (ordered.length < 2) return { points: "", width, height, hasData: false };
  const n = ordered.length;
  const pts = ordered.map((s, i) => {
    const x = (i / (n - 1)) * width;
    const y = height - (s.moisture_calibrated as number) * height;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  return { points: pts.join(" "), width, height, hasData: true };
}

export function moistureDisplay(zone: ZoneSample): string {
  if (zone.quality === "uncalibrated") return "uncalibrated";
  if (zone.quality === "sensor_error") return "sensor error";
  if (zone.quality === "stale") return "stale";
  if (zone.moisture_calibrated === null) return "no data";
  return `${Math.round(zone.moisture_calibrated * 100)}% · ${zone.state}`;
}

export function qualityLabel(q: string): string {
  switch (q) {
    case "ok":
      return "OK";
    case "sensor_error":
      return "sensor error";
    case "uncalibrated":
      return "uncalibrated";
    case "stale":
      return "stale";
    default:
      return q;
  }
}

// Protocol rule: unsynchronized time must never be rendered as exact
// wall-clock. Returns a human label plus a flag for styling.
export function timeDisplay(status: StatusPayload): {
  text: string;
  exact: boolean;
} {
  if (status.time_quality === "synchronized" && status.timestamp) {
    return { text: status.timestamp.replace("T", " "), exact: true };
  }
  if (status.time_quality === "relative") {
    return { text: "device clock not synchronized", exact: false };
  }
  return { text: "time unknown", exact: false };
}

export function environmentDisplay(status: StatusPayload): string {
  const e = status.environment;
  const parts: string[] = [];
  if (e.light_quality === "ok" && e.light_lux !== null && e.light_lux !== undefined)
    parts.push(`${e.light_lux.toFixed(0)} lux`);
  else parts.push("light: " + qualityLabel(e.light_quality));
  if (
    e.ambient_quality === "ok" &&
    e.temperature_c !== null &&
    e.temperature_c !== undefined
  ) {
    parts.push(`${e.temperature_c.toFixed(1)} °C`);
    if (e.humidity_rh !== null && e.humidity_rh !== undefined)
      parts.push(`${e.humidity_rh.toFixed(0)} %RH`);
  } else parts.push("ambient: " + qualityLabel(e.ambient_quality));
  return parts.join(" · ");
}

// Human summary of an ApiError-ish failure for role=status announcements.
export function errorText(err: unknown): string {
  if (err instanceof Error) {
    if (err.message.startsWith("unauthorized"))
      return "Not paired (or pairing token invalid). Open Pair and confirm on the device's USB serial console.";
    return err.message;
  }
  return "Unknown error talking to the device.";
}
