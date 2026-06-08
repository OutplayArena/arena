import { type ReactElement, type ReactNode } from "react";
import { render, type RenderOptions } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AppProvider } from "./state";
import { AuthContext } from "./context/AuthContext";
import type { AuthState } from "./context/AuthContext";

function createMockAuth(overrides: Partial<AuthState> = {}): AuthState {
  return {
    user: { id: "test-user", email: "test@test.com", name: "Test User", avatar_url: null },
    token: "mock-token",
    loading: false,
    hasProviders: true,
    providers: { github: true, google: false },
    sessionExpired: false,
    login: vi.fn(),
    logout: vi.fn(),
    ...overrides,
  };
}

function createMockAuthNoProviders(overrides: Partial<AuthState> = {}): AuthState {
  return createMockAuth({ hasProviders: false, ...overrides });
}

function createMockAuthLoading(overrides: Partial<AuthState> = {}): AuthState {
  return createMockAuth({ loading: true, ...overrides });
}

function createMockAuthNoUser(overrides: Partial<AuthState> = {}): AuthState {
  return createMockAuth({ user: null, ...overrides });
}

import { vi } from "vitest";

interface CustomRenderOptions extends Omit<RenderOptions, "wrapper"> {
  auth?: AuthState;
  initialRoute?: string;
}

function AllProviders({ children, auth, initialRoute = "/" }: { children: ReactNode; auth: AuthState; initialRoute: string }) {
  return (
    <AuthContext.Provider value={auth}>
      <MemoryRouter initialEntries={[initialRoute]}>
        <AppProvider>
          {children}
        </AppProvider>
      </MemoryRouter>
    </AuthContext.Provider>
  );
}

function renderWithProviders(
  ui: ReactElement,
  options: CustomRenderOptions = {},
) {
  const { auth = createMockAuth(), initialRoute = "/", ...renderOptions } = options;
  return render(ui, {
    wrapper: ({ children }) => (
      <AllProviders auth={auth} initialRoute={initialRoute}>
        {children}
      </AllProviders>
    ),
    ...renderOptions,
  });
}

export {
  renderWithProviders,
  createMockAuth,
  createMockAuthNoProviders,
  createMockAuthLoading,
  createMockAuthNoUser,
};
