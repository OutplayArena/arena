import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, beforeAll, afterAll, vi } from "vitest";
import { server } from "./mocks/server";
import { __resetGameNamesCache } from "./hooks/useGameNames";
import type {} from "vitest/jsdom";

// Node 26's native storage globals shadow jsdom's. Bind the browser storage
// before test modules load, including code that reads storage during import.
for (const name of ["localStorage", "sessionStorage"] as const) {
  Object.defineProperty(globalThis, name, {
    value: jsdom.window[name],
    configurable: true,
    writable: true,
  });
}

beforeAll(() => {
  server.listen({ onUnhandledRequest: "error" });

  vi.stubGlobal("matchMedia", vi.fn((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })));

  Object.defineProperty(navigator, "clipboard", {
    value: {
      writeText: vi.fn().mockResolvedValue(undefined),
    },
    writable: true,
    configurable: true,
  });
});

afterEach(() => {
  cleanup();
  server.resetHandlers();
  localStorage.clear();
  sessionStorage.clear();
  __resetGameNamesCache();
});

afterAll(() => {
  server.close();
  vi.unstubAllGlobals();
});
