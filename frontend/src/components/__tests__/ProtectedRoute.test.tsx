import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { ProtectedRoute } from "../ProtectedRoute";
import {
  renderWithProviders,
  createMockAuth,
  createMockAuthLoading,
  createMockAuthNoProviders,
  createMockAuthNoUser,
} from "../../test-utils";

describe("ProtectedRoute", () => {
  it("renders children when user is authenticated", () => {
    renderWithProviders(
      <ProtectedRoute>
        <div>Secret content</div>
      </ProtectedRoute>,
      { auth: createMockAuth() },
    );
    expect(screen.getByText("Secret content")).toBeInTheDocument();
  });

  it("redirects to /login when no user", () => {
    renderWithProviders(
      <ProtectedRoute>
        <div>Secret content</div>
      </ProtectedRoute>,
      { auth: createMockAuthNoUser() },
    );
    expect(screen.queryByText("Secret content")).not.toBeInTheDocument();
  });

  it("shows loading spinner when loading", () => {
    renderWithProviders(
      <ProtectedRoute>
        <div>Secret content</div>
      </ProtectedRoute>,
      { auth: createMockAuthLoading() },
    );
    expect(screen.queryByText("Secret content")).not.toBeInTheDocument();
  });

  it("renders children when no auth providers (local mode)", () => {
    renderWithProviders(
      <ProtectedRoute>
        <div>Local content</div>
      </ProtectedRoute>,
      { auth: createMockAuthNoProviders() },
    );
    expect(screen.getByText("Local content")).toBeInTheDocument();
  });
});
