import { useCallback, useEffect, useState } from "react";
import type { ProvidersResponse, UserInfo } from "../types";
import { AuthContext } from "./AuthContext";
import { request } from "../api";

const TOKEN_KEY = "nasharena_token";

function parseToken() {
  const params = new URLSearchParams(window.location.search);
  const token = params.get("token");
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
    window.history.replaceState({}, "", window.location.pathname);
  }
  return localStorage.getItem(TOKEN_KEY);
}

const EMPTY_PROVIDERS: ProvidersResponse = { github: false, google: false };

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token] = useState<string | null>(parseToken);
  const [user, setUser] = useState<UserInfo | null>(null);
  const [loading, setLoading] = useState(!!token);
  const [providers, setProviders] = useState<ProvidersResponse>(EMPTY_PROVIDERS);
  const hasProviders = providers.github || providers.google;

  useEffect(() => {
    request<ProvidersResponse>("/api/auth/providers")
      .then((p) => setProviders(p))
      .catch(() => setProviders(EMPTY_PROVIDERS));
  }, []);

  useEffect(() => {
    if (!token) return;
    request<UserInfo>("/api/auth/me")
      .then((u) => {
        setUser(u);
        setLoading(false);
      })
      .catch(() => {
        localStorage.removeItem(TOKEN_KEY);
        setLoading(false);
      });
  }, [token]);

  const login = useCallback(() => {
    setLoading(true);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, token, loading, hasProviders, providers, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
