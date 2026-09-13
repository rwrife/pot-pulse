// Typed client for the frozen /api/v1 contract (docs/protocol.md).
// All state-changing/user-data calls carry X-PotPulse-Token when paired.
// The client never logs token material and never sends more than the
// protocol's 8 KiB request bodies (payloads built here stay well under).

import type {
  BackupPayload,
  CalibrationPayload,
  ConfigPayload,
  ExportPayload,
  HistoryPage,
  OkPayload,
  PairRequestPayload,
  StatusPayload,
  ZoneSample,
} from "./types";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  constructor(status: number, code: string, message: string) {
    super(`${code}: ${message}`);
    this.status = status;
    this.code = code;
  }
}

export interface FetchLike {
  (input: string, init?: RequestInit): Promise<Response>;
}

interface ClientDeps {
  fetchImpl?: FetchLike;
  // Injectable clock so tests can freeze polling timestamps.
  now?: () => number;
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function httpError(status: number, body: unknown): ApiError {
  if (isRecord(body) && typeof body.error === "string") {
    const msg = typeof body.message === "string" ? body.message : "";
    return new ApiError(status, body.error, msg);
  }
  return new ApiError(status, "http_" + status, "unexpected response");
}

export class DeviceClient {
  readonly baseUrl: string;
  private token: string | null = null;
  private readonly fetchImpl: FetchLike;

  constructor(baseUrl: string, deps: ClientDeps = {}) {
    this.baseUrl = baseUrl.replace(/\/+$/, "");
    this.fetchImpl = deps.fetchImpl ?? ((i, init) => fetch(i, init));
  }

  setToken(token: string | null): void {
    this.token = token;
  }

  hasToken(): boolean {
    return this.token !== null;
  }

  private async request<T>(
    method: string,
    path: string,
    body?: unknown,
    query?: Record<string, string>,
  ): Promise<T> {
    let url = this.baseUrl + path;
    if (query && Object.keys(query).length > 0) {
      url +=
        "?" +
        Object.entries(query)
          .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
          .join("&");
    }
    const headers: Record<string, string> = {};
    if (body !== undefined) headers["Content-Type"] = "application/json";
    if (this.token) headers["X-PotPulse-Token"] = this.token;

    const res = await this.fetchImpl(url, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });

    const text = await res.text();
    let parsed: unknown = null;
    if (text.length > 0) {
      try {
        parsed = JSON.parse(text);
      } catch {
        throw httpError(res.status, null);
      }
    }
    if (!res.ok) throw httpError(res.status, parsed);
    return parsed as T;
  }

  // ---- read resources ----

  getStatus(): Promise<StatusPayload> {
    return this.request<StatusPayload>("GET", "/api/v1/status");
  }

  getHistory(
    zone: string,
    opts: { from?: number; to?: number; limit?: number } = {},
  ): Promise<HistoryPage> {
    const query: Record<string, string> = { zone };
    if (opts.from !== undefined) query["from"] = String(opts.from);
    if (opts.to !== undefined) query["to"] = String(opts.to);
    if (opts.limit !== undefined) query["limit"] = String(opts.limit);
    return this.request<HistoryPage>("GET", "/api/v1/history", undefined, query);
  }

  // ---- pairing ----

  requestPairing(): Promise<PairRequestPayload> {
    return this.request<PairRequestPayload>("POST", "/api/v1/pair/request");
  }

  // ---- state-changing resources (token required; fail closed w/ 401) ----

  postCalibration(
    zoneId: string,
    cal: CalibrationPayload,
  ): Promise<OkPayload> {
    return this.request<OkPayload>(
      "POST",
      `/api/v1/calibration/${encodeURIComponent(zoneId)}`,
      cal,
    );
  }

  postConfig(cfg: ConfigPayload): Promise<OkPayload> {
    return this.request<OkPayload>("POST", "/api/v1/config", cfg);
  }

  postExport(): Promise<ExportPayload> {
    return this.request<ExportPayload>("POST", "/api/v1/export");
  }

  postBackup(): Promise<BackupPayload> {
    return this.request<BackupPayload>("POST", "/api/v1/backup");
  }

  postRestore(backup: unknown): Promise<OkPayload> {
    return this.request<OkPayload>("POST", "/api/v1/restore", backup);
  }

  deleteHistory(): Promise<OkPayload> {
    return this.request<OkPayload>(
      "DELETE",
      "/api/v1/history",
      undefined,
      { confirm: "confirm" },
    );
  }

  resetFirmware(): Promise<OkPayload> {
    return this.request<OkPayload>("POST", "/api/v1/reset", {
      level: "full-firmware",
      confirm: "confirm",
    });
  }
}

// Re-export for consumers that validate history items before rendering.
export function isZoneSample(v: unknown): v is ZoneSample {
  return (
    isRecord(v) &&
    typeof v.zone_id === "string" &&
    typeof v.moisture_raw === "number" &&
    typeof v.quality === "string" &&
    typeof v.monotonic_ms === "number"
  );
}
