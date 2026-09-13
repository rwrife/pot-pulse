// Local store tests: disposable-cache semantics and the explicit
// delete-local-data control (architecture R-09 / privacy).

import { describe, expect, it } from "vitest";
import { LocalStore, type Kv } from "../src/core/store";

function fakeKv(initial?: string): Kv & { snapshot(): string | null } {
  let v: string | null = initial ?? null;
  return {
    get: () => v,
    set: (_k, value) => void (v = value),
    remove: () => void (v = null),
    snapshot: () => v,
  };
}

describe("LocalStore", () => {
  it("round-trips device url + token", () => {
    const s = LocalStore.inMemory();
    s.update({ deviceBaseUrl: "http://d", pairingToken: "tok" });
    expect(s.get()).toEqual({
      deviceBaseUrl: "http://d",
      pairingToken: "tok",
      lastDeviceId: null,
    });
  });

  it("persists updates and re-reads them from storage", () => {
    const kv = fakeKv();
    const a = new LocalStore(kv);
    a.update({ deviceBaseUrl: "http://d", pairingToken: "tok" });
    const b = new LocalStore(kv); // fresh load from same storage
    expect(b.get().pairingToken).toBe("tok");
  });

  it("clear() wipes state and removes the persisted record", () => {
    const kv = fakeKv(
      JSON.stringify({ deviceBaseUrl: "http://d", pairingToken: "tok" }),
    );
    const s = new LocalStore(kv);
    s.clear();
    expect(s.get().deviceBaseUrl).toBe("");
    expect(s.get().pairingToken).toBeNull();
    expect(kv.snapshot()).toBeNull(); // nothing left in storage
  });

  it("falls back to defaults on corrupt persisted JSON", () => {
    const s = new LocalStore(fakeKv("{not json"));
    expect(s.get()).toEqual({
      deviceBaseUrl: "",
      pairingToken: null,
      lastDeviceId: null,
    });
  });

  it("ignores wrong-typed fields in persisted state", () => {
    const s = new LocalStore(
      fakeKv(JSON.stringify({ deviceBaseUrl: 42, pairingToken: {} })),
    );
    expect(s.get().deviceBaseUrl).toBe("");
    expect(s.get().pairingToken).toBeNull();
  });
});
