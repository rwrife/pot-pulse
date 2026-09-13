// Rendering-rule tests for protocol norms: uncalibrated never displays as a
// valid value, relative time never displays as wall-clock, trends skip
// invalid samples.

import { describe, expect, it } from "vitest";
import type { StatusPayload, ZoneSample } from "../src/api/types";
import {
  environmentDisplay,
  moistureDisplay,
  sparkline,
  timeDisplay,
} from "../src/core/trend";

const base = (o: Partial<ZoneSample>): ZoneSample => ({
  zone_id: "z1",
  moisture_raw: 2048,
  moisture_calibrated: 0.5,
  state: "ok",
  quality: "ok",
  timestamp: null,
  monotonic_ms: 1000,
  ...o,
});

describe("moistureDisplay", () => {
  it("shows percent + state when calibrated", () =>
    expect(moistureDisplay(base({}))).toBe("50% · ok"));
  it("never implies a valid calibration", () =>
    expect(moistureDisplay(base({ quality: "uncalibrated", moisture_calibrated: 0.42 })))
      .toBe("uncalibrated"));
  it("surfaces sensor errors and staleness", () => {
    expect(moistureDisplay(base({ quality: "sensor_error" }))).toBe("sensor error");
    expect(moistureDisplay(base({ quality: "stale" }))).toBe("stale");
  });
});

const statusBase = (o: Partial<StatusPayload>): StatusPayload => ({
  schema_version: 1,
  timestamp: null,
  time_quality: "unknown",
  paired: false,
  environment: {
    light_lux: null,
    light_quality: "ok",
    temperature_c: null,
    humidity_rh: null,
    ambient_quality: "ok",
  },
  zones: [],
  ...o,
});

describe("timeDisplay", () => {
  it("shows exact time only when synchronized", () => {
    const t = timeDisplay(statusBase({
      time_quality: "synchronized",
      timestamp: "2026-09-13T12:00:00Z",
    }));
    expect(t.exact).toBe(true);
    expect(t.text).toContain("2026-09-13");
  });
  it("labels relative time as not exact (protocol rule)", () => {
    const t = timeDisplay(statusBase({
      time_quality: "relative",
      timestamp: "2026-09-13T12:00:00Z", // even if a stale stamp is present
    }));
    expect(t.exact).toBe(false);
    expect(t.text).toContain("not synchronized");
  });
});

describe("environmentDisplay", () => {
  it("renders measurements when quality ok", () => {
    const s = statusBase({
      environment: {
        light_lux: 320.4,
        light_quality: "ok",
        temperature_c: 21.55,
        humidity_rh: 48.2,
        ambient_quality: "ok",
      },
    });
    expect(environmentDisplay(s)).toBe("320 lux · 21.6 °C · 48 %RH");
  });
  it("renders quality labels instead of fabricated numbers", () => {
    const s = statusBase({
      environment: {
        light_lux: null,
        light_quality: "sensor_error",
        temperature_c: 25, // present but ambient not ok -> must not render
        humidity_rh: 50,
        ambient_quality: "stale",
      },
    });
    expect(environmentDisplay(s)).toBe("light: sensor error · ambient: stale");
  });
});

describe("sparkline", () => {
  it("needs >= 2 valid points", () => {
    expect(sparkline([base({})]).hasData).toBe(false);
  });
  it("orders chronologically and clamps to the box", () => {
    const spark = sparkline([
      base({ monotonic_ms: 3000, moisture_calibrated: 1.0, timestamp: null }),
      base({ monotonic_ms: 1000, moisture_calibrated: 0.0, timestamp: null }),
      base({ monotonic_ms: 2000, moisture_calibrated: 0.5, timestamp: null }),
    ]);
    expect(spark.hasData).toBe(true);
    const pts = spark.points.split(" ");
    expect(pts).toHaveLength(3);
    // first (oldest, dry) is bottom-left; last (newest, wet) top-right
    expect(pts[0]).toBe("0.0,60.0");
    expect(pts[2]).toBe("280.0,0.0");
  });
  it("skips uncalibrated/sensor-error samples entirely", () => {
    const spark = sparkline([
      base({ monotonic_ms: 1000 }),
      base({ monotonic_ms: 2000, quality: "uncalibrated", moisture_calibrated: null }),
      base({ monotonic_ms: 3000, quality: "sensor_error", moisture_calibrated: null }),
      base({ monotonic_ms: 4000, moisture_calibrated: 0.25 }),
    ]);
    expect(spark.points.split(" ")).toHaveLength(2);
  });
});
