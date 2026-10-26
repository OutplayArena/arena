import { beforeEach, describe, expect, it } from "vitest";

// Reading storage during module evaluation must work as well as inside tests.
const storages = { localStorage, sessionStorage };

beforeEach(() => {
  expect(localStorage.length).toBe(0);
  expect(sessionStorage.length).toBe(0);
});

describe.each(["localStorage", "sessionStorage"] as const)("%s", (name) => {
  it("provides browser Storage before test modules load", () => {
    expect(storages[name]).toBe(window[name]);
    expect(storages[name]).toBeInstanceOf(Storage);
  });

  it("supports storage operations without leaking into the next test", () => {
    const storage = storages[name];
    storage.setItem("token", "test-token");
    expect(storage.getItem("token")).toBe("test-token");
    expect(storage.key(0)).toBe("token");
    expect(storage.length).toBe(1);
    storage.removeItem("token");
    expect(storage.getItem("token")).toBeNull();
    // The shared cleanup must remove entries from both storage areas.
    localStorage.setItem("cleanup", "local");
    sessionStorage.setItem("cleanup", "session");
  });
});

it("keeps local and session storage separate", () => {
  localStorage.setItem("token", "local-token");
  sessionStorage.setItem("token", "session-token");
  expect(localStorage.getItem("token")).toBe("local-token");
  expect(sessionStorage.getItem("token")).toBe("session-token");
});
