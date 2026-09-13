// Browser-local app state. Protocol ownership rule: browser storage is a
// disposable cache, NOT authoritative device history. We persist only the
// device base URL, the pairing token (so refreshes don't re-pair), and
// presentation preferences. Device readings are re-fetched on demand.

export interface AppState {
  deviceBaseUrl: string;
  pairingToken: string | null;
  lastDeviceId: string | null; // presentation hint only; never a tracker we sell/keep
}

const STORAGE_KEY = "potpu…e-v1";

export interface Kv {
  get(key: string): string | null;
  set(key: string, value: string): void;
  remove(key: string): void;
}

const localKv: Kv = {
  get: (k) => localStorage.getItem(k),
  set: (k, v) => localStorage.setItem(k, v),
  remove: (k) => localStorage.removeItem(k),
};

const memoryKv = (): Kv => {
  const m = new Map<string, string>();
  return {
    get: (k) => m.get(k) ?? null,
    set: (k, v) => void m.set(k, v),
    remove: (k) => void m.delete(k),
  };
};

export class LocalStore {
  private state: AppState;
  constructor(private kv: Kv = localKv) {
    this.state = this.load();
  }

  static inMemory(seed?: Partial<AppState>): LocalStore {
    const store = new LocalStore(memoryKv());
    if (seed) store.update(seed);
    return store;
  }

  private load(): AppState {
    const fallback: AppState = {
      deviceBaseUrl: "",
      pairingToken: null,
      lastDeviceId: null,
    };
    const raw = this.kv.get(STORAGE_KEY);
    if (!raw) return fallback;
    try {
      const parsed = JSON.parse(raw) as Partial<AppState>;
      return {
        deviceBaseUrl:
          typeof parsed.deviceBaseUrl === "string"
            ? parsed.deviceBaseUrl
            : "",
        pairingToken:
          typeof parsed.pairingToken === "string" ? parsed.pairingToken : null,
        lastDeviceId:
          typeof parsed.lastDeviceId === "string"
            ? parsed.lastDeviceId
            : null,
      };
    } catch {
      // Corrupt cache: fall back to defaults (cache is disposable).
      return fallback;
    }
  }

  get(): Readonly<AppState> {
    return { ...this.state };
  }

  update(patch: Partial<AppState>): void {
    this.state = { ...this.state, ...patch };
    this.kv.set(STORAGE_KEY, JSON.stringify(this.state));
  }

  // Explicit user-facing "delete my local data" control.
  clear(): void {
    this.state = { deviceBaseUrl: "", pairingToken: null, lastDeviceId: null };
    this.kv.remove(STORAGE_KEY);
  }
}
