// API client tests against a scripted fake of the frozen firmware behavior
// (docs/protocol.md "Frozen mechanics"). No network access.

import { describe, expect, it } from "vitest";
import { ApiError, DeviceClient } from "../src/api/client";
import type { StatusPayload } from "../src/api/types";

interface Recorded {
  url: string;
  method: string;
  headers: Record<string, string>;
  body?: string;
}

const STATUS: StatusPayload = {
  schema_version: 1,
  timestamp: "2026-09-13T12:00:00Z",
  time_quality: "synchronized",
  paired: true,
  device_id: "potpulse-test01",
  environment: {
    light_lux: 320.5,
    light_quality: "ok",
    temperature_c: 21.5,
    humidity_rh: 48.2,
    ambient_quality: "ok",
  },
  zones: [
    {
      zone_id: "z1",
      moisture_raw: 2048,
      moisture_calibrated: 0.55,
      state: "ok",
      quality: "ok",
      timestamp: "2026-09-13T12:00:00Z",
      monotonic_ms: 12345,
    },
    {
      zone_id: "z2",
      moisture_raw: 3000,
      moisture_calibrated: null,
      state: "unknown",
      quality: "uncalibrated",
      timestamp: null,
      monotonic_ms: 12345,
    },
  ],
};

function fakeFetch(
  handler: (req: Recorded) => { status: number; body: unknown },
) {
  const calls: Recorded[] = [];
  const fetchImpl = async (input: string, init?: RequestInit) => {
    const rec: Recorded = {
      url: input,
      method: init?.method ?? "GET",
      headers: (init?.headers as Record<string, string>) ?? {},
      body: typeof init?.body === "string" ? init.body : undefined,
    };
    calls.push(rec);
    const { status, body } = handler(rec);
    return new Response(typeof body === "string" ? body : JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    });
  };
  return { fetchImpl, calls };
}

describe("DeviceClient", () => {
  it("GETs status without a token (pre-pairing is allowed)", async () => {
    const { fetchImpl, calls } = fakeFetch(() => ({ status: 200, body: STATUS }));
    const c = new DeviceClient("http://potpulse.local/", { fetchImpl });
    const s = await c.getStatus();
    expect(s.schema_version).toBe(1);
    expect(calls[0].url).toBe("http://potpulse.local/api/v1/status");
    expect(calls[0].headers["X-PotPulse-Token"]).toBeUndefined();
  });

  it("sends X-PotPulse-Token once paired", async () => {
    const { fetchImpl, calls } = fakeFetch(() => ({
      status: 200,
      body: { schema_version: 1, zone_id: "z1", items: [], count: 0 },
    }));
    const c = new DeviceClient("http://d", { fetchImpl });
    c.setToken("abc123");
    await c.getHistory("z1", { limit: 50, from: 10, to: 20 });
    expect(calls[0].headers["X-PotPulse-Token"]).toBe("abc123");
    expect(calls[0].url).toBe(
      "http://d/api/v1/history?zone=z1&from=10&to=20&limit=50",
    );
  });

  it("maps 401 fail-closed responses to ApiError('unauthorized')", async () => {
    const { fetchImpl } = fakeFetch(() => ({
      status: 401,
      body: { error: "unauthorized", message: "token required" },
    }));
    const c = new DeviceClient("http://d", { fetchImpl });
    await expect(c.postConfig({ sample_interval_ms: 60000 })).rejects.toMatchObject(
      { status: 401, code: "unauthorized" },
    );
  });

  it("requests pairing and parses the 202 payload", async () => {
    const { fetchImpl } = fakeFetch(() => ({
      status: 202,
      body: { pair_id: "a1b2c3d4", nonce: "0123456789ab", confirm_over: "usb-serial" },
    }));
    const c = new DeviceClient("http://d", { fetchImpl });
    const r = await c.requestPairing();
    expect(r.pair_id).toBe("a1b2c3d4");
    expect(r.confirm_over).toBe("usb-serial");
  });

  it("surfaces 409 while a pairing request is active", async () => {
    const { fetchImpl } = fakeFetch(() => ({
      status: 409,
      body: { error: "request_active", message: "one active pairing request" },
    }));
    const c = new DeviceClient("http://d", { fetchImpl });
    const err = await c.requestPairing().catch((e) => e as ApiError);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).code).toBe("request_active");
  });

  it("posts calibration to the per-zone path", async () => {
    const { fetchImpl, calls } = fakeFetch(() => ({
      status: 200,
      body: { ok: "calibration_stored" },
    }));
    const c = new DeviceClient("http://d", { fetchImpl });
    c.setToken("t");
    await c.postCalibration("z2", { dry_raw: 100, wet_raw: 3000 });
    expect(calls[0].url).toBe("http://d/api/v1/calibration/z2");
    expect(JSON.parse(calls[0].body!)).toEqual({ dry_raw: 100, wet_raw: 3000 });
  });

  it("deleteHistory appends the frozen confirmation word", async () => {
    const { fetchImpl, calls } = fakeFetch(() => ({
      status: 200,
      body: { ok: true, deleted: 42, complete: true },
    }));
    const c = new DeviceClient("http://d", { fetchImpl });
    c.setToken("t");
    const r = await c.deleteHistory();
    expect(calls[0].method).toBe("DELETE");
    expect(calls[0].url).toBe("http://d/api/v1/history?confirm=confirm");
    expect(r.complete).toBe(true);
  });

  it("maps 428 confirmation-required without failing silently", async () => {
    const { fetchImpl } = fakeFetch(() => ({
      status: 428,
      body: { error: "confirmation_required", message: "append ?confirm=confirm" },
    }));
    const c = new DeviceClient("http://d", { fetchImpl });
    c.setToken("t");
    // deleteHistory always sends the word; simulate a stricter future server:
    const err = await c
      .postRestore({ backup_version: 99 })
      .then(() => null)
      .catch((e) => e as ApiError);
    expect(err?.code).toBe("confirmation_required");
    expect(err?.status).toBe(428);
  });

  it("reset sends level + confirm exactly as frozen", async () => {
    const { fetchImpl, calls } = fakeFetch(() => ({
      status: 200,
      body: { ok: "factory_reset" },
    }));
    const c = new DeviceClient("http://d", { fetchImpl });
    c.setToken("t");
    await c.resetFirmware();
    expect(JSON.parse(calls[0].body!)).toEqual({
      level: "full-firmware",
      confirm: "confirm",
    });
  });

  it("tolerates unknown additive fields (protocol forward-compat rule)", async () => {
    const { fetchImpl } = fakeFetch(() => ({
      status: 200,
      body: { ...STATUS, future_field: { nested: true } },
    }));
    const c = new DeviceClient("http://d", { fetchImpl });
    const s = await c.getStatus();
    expect(s.zones[0].zone_id).toBe("z1");
  });
});
