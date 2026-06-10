import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, clearToken, getToken, type UserPreferencesApi } from "../api/client";

export interface AuthUser {
  sys_id: string;
  user_name: string;
  permissions: string[];
  group_ids: string[];
  preferences: UserPreferencesApi;
}

interface AuthContextValue {
  user: AuthUser | null;
  loading: boolean;
  refresh: () => Promise<void>;
  hasPermission: (permission: string) => boolean;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function permissionMatch(permissions: string[], required: string): boolean {
  if (permissions.includes(required)) return true;
  if (required.startsWith("records.") && permissions.includes("records.*.write")) {
    return required.endsWith(".write") || required.endsWith(".delete");
  }
  if (required.endsWith(".read") && permissions.includes("records.*.read")) {
    return required.startsWith("records.");
  }
  return false;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(!!getToken());

  const refresh = useCallback(async () => {
    if (!getToken()) {
      setUser(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const me = await api.me();
      setUser(me);
    } catch {
      clearToken();
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const hasPermission = useCallback(
    (permission: string) => (user ? permissionMatch(user.permissions, permission) : false),
    [user]
  );

  const logout = useCallback(() => {
    clearToken();
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, loading, refresh, hasPermission, logout }),
    [user, loading, refresh, hasPermission, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
