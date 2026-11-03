import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import {
  api,
  clearTokens,
  getRefreshToken,
  hasTokens,
  saveTokens,
  setSessionExpiredHandler,
} from "./api";
import type { SignupRequest, SignupResponse, Tokens, User } from "./types";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (payload: SignupRequest) => Promise<void>;
  logout: () => Promise<void>;
  setUser: (user: User) => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(hasTokens());

  useEffect(() => {
    setSessionExpiredHandler(() => setUser(null));
    if (!hasTokens()) return;
    api<User>("/users/me")
      .then(setUser)
      .catch(() => clearTokens())
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const tokens = await api<Tokens>("/auth/login", {
      method: "POST",
      json: { email, password },
      auth: false,
    });
    saveTokens(tokens);
    setUser(await api<User>("/users/me"));
  }, []);

  const signup = useCallback(async (payload: SignupRequest) => {
    const res = await api<SignupResponse>("/auth/signup", {
      method: "POST",
      json: payload,
      auth: false,
    });
    saveTokens(res.tokens);
    setUser(res.user);
  }, []);

  const logout = useCallback(async () => {
    const refreshToken = getRefreshToken();
    if (refreshToken) {
      // Best effort: revoke the refresh token on the server, log out locally regardless.
      await api("/auth/logout", {
        method: "POST",
        json: { refresh_token: refreshToken },
        auth: false,
      }).catch(() => {});
    }
    clearTokens();
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, loading, login, signup, logout, setUser }),
    [user, loading, login, signup, logout],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}

// For pages that only render when logged in (they sit behind RequireAuth).
export function useUser(): User {
  const { user } = useAuth();
  if (!user) throw new Error("useUser called without a logged-in user");
  return user;
}
