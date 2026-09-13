// Pot Pulse companion app controller (issue #7).
// Wires the accessible HTML shell to the protocol client. The browser is a
// disposable cache (docs/protocol.md): every screen re-reads from the device.

import { DeviceClient } from "./api/client";
import type { StatusPayload, ZoneSample } from "./api/types";
import {
  browserSaveFile,
  exportToCsv,
  exportToJson,
  parseBackupFile,
} from "./core/export";
import {
  environmentDisplay,
  errorText,
  moistureDisplay,
  qualityLabel,
  sparkline,
  timeDisplay,
} from "./core/trend";
import { LocalStore } from "./core/store";
import {
  validateBackupDoc,
  validateCalibration,
  validateHistoryLimit,
  validateSampleInterval,
  validateZoneNames,
} from "./core/validation";

const store = new LocalStore();
let client = new DeviceClient("");
let refreshTimer: number | undefined;

// ---------- DOM helpers ----------

function byId<T extends HTMLElement>(id: string): T {
  const el = document.getElementById(id);
  if (!el) throw new Error(`missing element #${id}`);
  return el as T;
}
function $input(id: string): HTMLInputElement {
  return byId<HTMLInputElement>(id);
}
function $select(id: string): HTMLSelectElement {
  return byId<HTMLSelectElement>(id);
}
function form(id: string): HTMLFormElement {
  return byId<HTMLFormElement>(id);
}

function setStatus(msg: string, isError = false): void {
  const line = byId<HTMLElement>("status-line");
  line.textContent = msg;
  line.classList.toggle("error", isError);
}

// ---------- tabs ----------

const tabIds = ["connect", "dashboard", "setup", "data"] as const;
function selectTab(name: (typeof tabIds)[number]): void {
  for (const t of tabIds) {
    const tab = byId<HTMLButtonElement>("tab-" + t);
    const panel = byId<HTMLElement>("panel-" + t);
    const active = t === name;
    tab.setAttribute("aria-selected", String(active));
    panel.hidden = !active;
  }
}

// ---------- connect / pairing ----------

function connectionLabel(status: StatusPayload | null): string {
  if (!status) return "Not connected.";
  const paired = status.paired ? "paired" : "not paired";
  const id = status.device_id ? ` · ${status.device_id}` : "";
  return `Connected to ${client.baseUrl} (${paired}${id}).`;
}

async function connect(url: string, token: string | null): Promise<void> {
  client = new DeviceClient(url);
  if (token) client.setToken(token);
  const status = await client.getStatus(); // public pre-pairing read
  store.update({
    deviceBaseUrl: url,
    pairingToken: token,
    lastDeviceId: status.device_id || store.get().lastDeviceId,
  });
  byId<HTMLElement>("connection-summary").textContent = connectionLabel(status);
  renderStatus(status);
  populateZoneSelectors(status);
  populateNameFields(status);
  selectTab("dashboard");
  setStatus(token ? "Paired session active." : "Connected read-only; pair to configure.");
  startAutoRefresh();
}

async function startPairing(): Promise<void> {
  if (!client.baseUrl) {
    setStatus("Enter the device address first.", true);
    return;
  }
  try {
    const r = await client.requestPairing();
    byId<HTMLElement>("pair-result").hidden = false;
    byId<HTMLElement>(
      "pair-command",
    ).textContent = `pair confirm ${r.pair_id}`;
    setStatus(
      `Pairing request ${r.pair_id} pending. Confirm over USB serial (${r.confirm_over}), then paste the token.`,
    );
  } catch (err) {
    setStatus(errorText(err), true);
  }
}

// ---------- dashboard ----------

function stateClass(z: ZoneSample): string {
  return "zone-state " + (z.quality === "ok" ? z.state : "unknown");
}

function renderStatus(status: StatusPayload): void {
  const t = timeDisplay(status);
  byId<HTMLElement>("device-time").textContent = `Device time: ${t.text}${t.exact ? "" : " (not shown as exact time)"}`;
  byId<HTMLElement>("environment").textContent = environmentDisplay(status);

  const list = byId<HTMLUListElement>("zone-list");
  list.textContent = "";
  for (const z of status.zones) {
    const li = document.createElement("li");
    li.setAttribute("role", "listitem");
    const name = document.createElement("span");
    name.textContent = `${z.zone_id.toUpperCase()} — ${moistureDisplay(z)}`;
    const badge = document.createElement("span");
    badge.className = stateClass(z);
    badge.textContent =
      z.quality === "ok" ? z.state.toUpperCase() : qualityLabel(z.quality);
    li.append(name, badge);
    list.append(li);
  }
}

function populateZoneSelectors(status: StatusPayload): void {
  for (const id of ["trend-zone", "cal-zone"]) {
    const sel = $select(id);
    const prev = sel.value;
    sel.textContent = "";
    for (const z of status.zones) {
      const opt = document.createElement("option");
      opt.value = z.zone_id;
      opt.textContent = z.zone_id.toUpperCase();
      sel.append(opt);
    }
    if (prev) sel.value = prev;
  }
}

function populateNameFields(status: StatusPayload): void {
  const box = byId<HTMLElement>("zone-name-fields");
  if (box.childElementCount > 0) return; // built once
  status.zones.forEach((z, i) => {
    const label = document.createElement("label");
    label.htmlFor = `zone-name-${i}`;
    label.textContent = `${z.zone_id.toUpperCase()} name`;
    const input = document.createElement("input");
    input.id = `zone-name-${i}`;
    input.type = "text";
    input.maxLength = 32;
    input.value = z.zone_id.toUpperCase();
    box.append(label, input);
  });
}

async function refresh(): Promise<void> {
  if (!client.baseUrl) return;
  try {
    const status = await client.getStatus();
    byId<HTMLElement>("connection-summary").textContent = connectionLabel(status);
    renderStatus(status);
    populateZoneSelectors(status);
  } catch (err) {
    setStatus(errorText(err), true);
    byId<HTMLElement>("connection-summary").textContent =
      "Connection lost — will keep retrying.";
  }
}

function startAutoRefresh(): void {
  if (refreshTimer !== undefined) window.clearInterval(refreshTimer);
  const box = byId<HTMLInputElement>("auto-refresh");
  if (!box.checked) return;
  refreshTimer = window.setInterval(() => void refresh(), 30_000);
}

async function loadTrend(): Promise<void> {
  const zone = $select("trend-zone").value;
  const limit = Number($input("trend-limit").value);
  const vr = validateHistoryLimit(limit);
  if (!vr.ok) {
    setStatus(vr.errors.join(" "), true);
    return;
  }
  try {
    const page = await client.getHistory(zone, { limit });
    const spark = sparkline(page.items);
    const box = byId<HTMLElement>("trend");
    if (!spark.hasData) {
      box.innerHTML = `<p class="empty">No calibrated samples yet for ${zone.toUpperCase()} (${page.count} raw samples returned).</p>`;
      return;
    }
    box.innerHTML = `<svg viewBox="0 0 ${spark.width} ${spark.height}" role="img" aria-label="Calibrated moisture trend for zone ${zone.toUpperCase()}, dry at bottom wet at top"><rect width="${spark.width}" height="${spark.height}" fill="none"/><polyline class="line" points="${spark.points}"/></svg>`;
  } catch (err) {
    setStatus(errorText(err), true);
  }
}

// ---------- setup ----------

async function saveConfig(): Promise<void> {
  const names = Array.from({ length: 4 }, (_, i) =>
    byId<HTMLInputElement>("zone-name-" + i).value,
  );
  const intervalSec = Number($input("sample-interval").value);
  const nameCheck = validateZoneNames(names);
  const intervalCheck = validateSampleInterval(intervalSec * 1000);
  const problems = [...nameCheck.errors, ...intervalCheck.errors];
  if (problems.length) {
    setStatus(problems.join(" "), true);
    return;
  }
  try {
    const r = await client.postConfig({
      zone_names: names,
      sample_interval_ms: intervalSec * 1000,
    });
    setStatus(`Saved (${(r.applied ?? []).join(", ")}).`);
    await refresh();
  } catch (err) {
    setStatus(errorText(err), true);
  }
}

async function storeCalibration(): Promise<void> {
  const zone = $select("cal-zone").value;
  const input = {
    dryRaw: Number($input("cal-dry").value),
    wetRaw: Number($input("cal-wet").value),
    dryThreshold: Number($input("cal-dry-th").value),
    wetThreshold: Number($input("cal-wet-th").value),
  };
  const vr = validateCalibration(input);
  if (!vr.ok) {
    setStatus(vr.errors.join(" "), true);
    return;
  }
  try {
    await client.postCalibration(zone, {
      dry_raw: input.dryRaw,
      wet_raw: input.wetRaw,
      dry_threshold: input.dryThreshold,
      wet_threshold: input.wetThreshold,
    });
    setStatus(`Calibration stored for ${zone.toUpperCase()}.`);
    await refresh();
  } catch (err) {
    setStatus(errorText(err), true);
  }
}

// ---------- data ----------

async function doExport(kind: "csv" | "json"): Promise<void> {
  try {
    const doc = await client.postExport();
    const file = kind === "csv" ? exportToCsv(doc) : exportToJson(doc);
    browserSaveFile(
      file.filename,
      file.content,
      kind === "csv" ? "text/csv" : "application/json",
    );
    setStatus(`Exported ${doc.samples.length} samples to ${file.filename}.`);
  } catch (err) {
    setStatus(errorText(err), true);
  }
}

async function doBackup(): Promise<void> {
  try {
    const doc = await client.postBackup();
    browserSaveFile(
      "potpulse-backup.json",
      JSON.stringify(doc, null, 2) + "\n",
      "application/json",
    );
    setStatus("Backup downloaded (settings, calibration, zone names only).");
  } catch (err) {
    setStatus(errorText(err), true);
  }
}

async function doRestore(): Promise<void> {
  const fileInput = byId<HTMLInputElement>("restore-file");
  const f = fileInput.files?.[0];
  if (!f) {
    setStatus("Choose a backup file first.", true);
    return;
  }
  try {
    const doc = parseBackupFile(await f.text());
    const vr = validateBackupDoc(doc);
    if (!vr.ok) {
      setStatus("Backup file invalid: " + vr.errors.join(" "), true);
      return;
    }
    await client.postRestore(doc);
    setStatus("Restore applied atomically by the device.");
    await refresh();
  } catch (err) {
    setStatus(errorText(err), true);
  }
}

async function doDeleteHistory(): Promise<void> {
  if (
    !window.confirm(
      "Delete ALL retained readings on the device? Settings and calibration are kept. This cannot be undone.",
    )
  ) {
    setStatus("History deletion cancelled.");
    return;
  }
  try {
    const r = await client.deleteHistory();
    setStatus(
      r.complete
        ? `Deleted ${r.deleted ?? 0} retained samples.`
        : "Deletion reported incomplete by the device — retry.",
      !r.complete,
    );
  } catch (err) {
    setStatus(errorText(err), true);
  }
}

function doClearLocal(): void {
  if (
    !window.confirm(
      "Delete this browser's local app data (device address and pairing token)? Device history is not touched.",
    )
  )
    return;
  store.clear();
  client = new DeviceClient("");
  byId<HTMLInputElement>("device-url").value = "";
  byId<HTMLInputElement>("pair-token").value = "";
  byId<HTMLElement>("connection-summary").textContent = "Not connected.";
  setStatus("Local app data deleted.");
  selectTab("connect");
}

// ---------- wiring ----------

function wire(): void {
  for (const t of tabIds) {
    byId<HTMLButtonElement>("tab-" + t).addEventListener("click", () =>
      selectTab(t),
    );
  }

  form("connect-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const url = byId<HTMLInputElement>("device-url").value.trim();
    const token = byId<HTMLInputElement>("pair-token").value.trim() || null;
    connect(url, token).catch((err) => setStatus(errorText(err), true));
  });
  byId<HTMLButtonElement>("btn-pair").addEventListener("click", () =>
    void startPairing(),
  );

  byId<HTMLButtonElement>("btn-refresh").addEventListener("click", () =>
    void refresh(),
  );
  byId<HTMLInputElement>("auto-refresh").addEventListener("change", () =>
    startAutoRefresh(),
  );
  byId<HTMLButtonElement>("btn-trend").addEventListener("click", () =>
    void loadTrend(),
  );

  form("config-form").addEventListener("submit", (e) => {
    e.preventDefault();
    void saveConfig();
  });
  form("cal-form").addEventListener("submit", (e) => {
    e.preventDefault();
    void storeCalibration();
  });

  byId<HTMLButtonElement>("btn-export-csv").addEventListener("click", () =>
    void doExport("csv"),
  );
  byId<HTMLButtonElement>("btn-export-json").addEventListener("click", () =>
    void doExport("json"),
  );
  byId<HTMLButtonElement>("btn-backup").addEventListener("click", () =>
    void doBackup(),
  );
  byId<HTMLButtonElement>("btn-restore").addEventListener("click", () =>
    void doRestore(),
  );
  byId<HTMLButtonElement>("btn-delete-history").addEventListener("click", () =>
    void doDeleteHistory(),
  );
  byId<HTMLButtonElement>("btn-clear-local").addEventListener("click", () =>
    doClearLocal(),
  );
}

function boot(): void {
  wire();
  const saved = store.get();
  if (saved.deviceBaseUrl) {
    byId<HTMLInputElement>("device-url").value = saved.deviceBaseUrl;
    connect(saved.deviceBaseUrl, saved.pairingToken).catch((err) => {
      setStatus(errorText(err), true);
      selectTab("connect");
    });
  } else {
    selectTab("connect");
  }
}

boot();
