import { type ReactElement, type ReactNode } from "react";
import { render, type RenderOptions } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AppProvider } from "./state";
import { AuthContext } from "./context/AuthContext";
import { ThemeContext } from "./context/ThemeContext";
import { SiteConfigContext } from "./context/SiteConfigContext";
import type { AuthState } from "./context/AuthContext";
import type { SiteConfig } from "./types";

/* eslint-disable react-refresh/only-export-components */

function createMockAuth(overrides: Partial<AuthState> = {}): AuthState {
  return {
    user: { id: "test-user", email: "test@test.com", name: "Test User", avatar_url: null, privacy_accepted: true },
    token: "mock-token",
    loading: false,
    hasProviders: true,
    providers: { github: true, google: false },
    sessionExpired: false,
    login: vi.fn(),
    logout: vi.fn(),
    refreshUser: vi.fn().mockResolvedValue(undefined),
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

const mockTheme = { theme: "light" as const, toggle: vi.fn() };
const mockSiteConfig: SiteConfig = {
  github_url: "",
  docs_url: "",
  privacy_notice_url: "",
  about_text: "",
  footer: { copyright: "", tagline: "" },
};

interface CustomRenderOptions extends Omit<RenderOptions, "wrapper"> {
  auth?: AuthState;
  initialRoute?: string;
}

function AllProviders({ children, auth, initialRoute = "/" }: { children: ReactNode; auth: AuthState; initialRoute: string }) {
  return (
    <ThemeContext.Provider value={mockTheme}>
      <SiteConfigContext.Provider value={mockSiteConfig}>
        <AuthContext.Provider value={auth}>
          <MemoryRouter initialEntries={[initialRoute]}>
            <AppProvider>
              {children}
            </AppProvider>
          </MemoryRouter>
        </AuthContext.Provider>
      </SiteConfigContext.Provider>
    </ThemeContext.Provider>
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
