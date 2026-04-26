import { createContext, useContext, useState, useEffect, useCallback } from "react";
import { getStoredToken, getStoredUser, storeAuth, clearAuth, exchangeCode, getMe, logoutSession, logoutAllSessions } from "./api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(getStoredUser());
  const [loading, setLoading] = useState(false);

  // Handle OAuth callback code in URL.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const code = params.get("code");
    const state = params.get("state");
    if (code && state) {
      setLoading(true);
      exchangeCode(code, state)
        .then((data) => {
          storeAuth(data.token, data.user);
          setUser(data.user);
          // Clean URL.
          window.history.replaceState({}, "", window.location.pathname);
        })
        .catch((err) => {
          console.error("OAuth callback failed:", err);
        })
        .finally(() => setLoading(false));
    } else if (code) {
      console.error("OAuth callback missing state");
      window.history.replaceState({}, "", window.location.pathname);
    }
  }, []);

  // Validate stored token on mount.
  useEffect(() => {
    const token = getStoredToken();
    if (token && !loading) {
      getMe()
        .then((u) => setUser(u))
        .catch(() => {
          clearAuth();
          setUser(null);
        });
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const logout = useCallback(() => {
    // Fire-and-forget server-side revoke; don't block UI on network.
    logoutSession().catch(() => {});
    clearAuth();
    setUser(null);
  }, []);

  const logoutEverywhere = useCallback(async () => {
    try {
      await logoutAllSessions();
    } catch (err) {
      console.error("logout-all failed:", err);
    }
    clearAuth();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, logout, logoutEverywhere }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be inside AuthProvider");
  return ctx;
}
