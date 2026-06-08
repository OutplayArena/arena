import { describe, it, expect } from "vitest";
import { renderHook } from "@testing-library/react";
import { AppProvider } from "../state";
import { useApp } from "../hooks/useApp";
import { useAuth } from "../hooks/useAuth";
import type { ReactNode } from "react";

describe("useApp", () => {
  it("throws when used outside AppProvider", () => {
    expect(() => {
      renderHook(() => useApp());
    }).toThrow("useApp must be used within AppProvider");
  });

  it("returns context when used within AppProvider", () => {
    const wrapper = ({ children }: { children: ReactNode }) => (
      <AppProvider>{children}</AppProvider>
    );
    const { result } = renderHook(() => useApp(), { wrapper });
    expect(result.current.state).toBeDefined();
    expect(result.current.setMatch).toBeDefined();
    expect(result.current.startGame).toBeDefined();
    expect(result.current.clearMatch).toBeDefined();
  });
});

describe("useAuth", () => {
  it("throws when used outside AuthProvider", () => {
    expect(() => {
      renderHook(() => useAuth());
    }).toThrow("useAuth must be used within AuthProvider");
  });
});
