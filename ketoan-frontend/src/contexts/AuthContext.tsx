import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api, login as apiLogin, setToken } from "../api/client";
import type { CurrentUser } from "../api/types";

interface AuthContextValue {
  user: CurrentUser | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(true);

  async function refreshUser() {
    try {
      const me = await api.get<CurrentUser>("/auth/me");
      setUser(me);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (localStorage.getItem("access_token")) {
      refreshUser();
    } else {
      setLoading(false);
    }
  }, []);

  async function login(username: string, password: string) {
    const token = await apiLogin(username, password);
    setToken(token);
    await refreshUser();
  }

  function logout() {
    setToken(null);
    setUser(null);
  }

  return <AuthContext.Provider value={{ user, loading, login, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth phải dùng bên trong AuthProvider");
  return ctx;
}
