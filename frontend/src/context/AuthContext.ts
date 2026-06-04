import { createContext } from "react";
import type { ProvidersResponse, UserInfo } from "../types";

export interface AuthState {
  user: UserInfo | null;
  token: string | null;
  loading: boolean;
  hasProviders: boolean;
  providers: ProvidersResponse;
  sessionExpired: boolean;
  login: () => void;
  logout: () => void;
}

export const AuthContext = createContext<AuthState | null>(null);
