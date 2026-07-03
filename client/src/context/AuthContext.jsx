import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { loginUser, logoutUser, refreshSession, signupUser } from "../api";

const AuthContext = createContext(null);

// F4 marker so the fetch wrap stays idempotent under React StrictMode
// double-mount.
const FETCH_WRAPPED = Symbol.for("__auth_fetch_wrapped__");

// Refresh this many ms before the access token's stated expiry.
const REFRESH_SKEW_MS = 60 * 1000;

function readStored() {
    const token = localStorage.getItem("token");
    const userRaw = localStorage.getItem("user");
    if (!token || !userRaw) return { token: null, user: null, refreshToken: null, expiresAt: null };
    try {
        return {
            token,
            user: JSON.parse(userRaw),
            refreshToken: localStorage.getItem("refresh_token"),
            expiresAt: Number(localStorage.getItem("expires_at")) || null,
        };
    } catch {
        return { token: null, user: null, refreshToken: null, expiresAt: null };
    }
}

export function AuthProvider({ children }) {
    const initial = readStored();
    const [user, setUser] = useState(initial.user);
    const [token, setToken] = useState(initial.token);
    const [loading] = useState(false);

    // Refresh-token state lives in refs so the process-wide fetch wrapper can
    // read the latest value without being re-created on every render.
    const refreshTokenRef = useRef(initial.refreshToken);
    const expiresAtRef = useRef(initial.expiresAt);
    const refreshTimerRef = useRef(null);
    const refreshingRef = useRef(null); // de-dupes concurrent refresh attempts

    const persist = useCallback((nextToken, nextUser, nextRefresh, nextExpiresAt) => {
        if (nextToken && nextUser) {
            localStorage.setItem("token", nextToken);
            localStorage.setItem("user", JSON.stringify(nextUser));
            if (nextRefresh) localStorage.setItem("refresh_token", nextRefresh);
            if (nextExpiresAt) localStorage.setItem("expires_at", String(nextExpiresAt));
        } else {
            localStorage.removeItem("token");
            localStorage.removeItem("user");
            localStorage.removeItem("refresh_token");
            localStorage.removeItem("expires_at");
        }
        refreshTokenRef.current = nextRefresh ?? null;
        expiresAtRef.current = nextExpiresAt ?? null;
        setToken(nextToken);
        setUser(nextUser);
    }, []);

    // Exchange the refresh token for a fresh access token. De-duped: many
    // simultaneous 401s share one in-flight refresh.
    const doRefresh = useCallback(async () => {
        const rt = refreshTokenRef.current;
        if (!rt) return null;
        if (refreshingRef.current) return refreshingRef.current;

        refreshingRef.current = (async () => {
            try {
                const data = await refreshSession(rt);
                persist(
                    data.access_token,
                    { id: data.user_id, email: data.email },
                    data.refresh_token,
                    data.expires_at,
                );
                return data.access_token;
            } catch {
                persist(null, null);
                return null;
            } finally {
                refreshingRef.current = null;
            }
        })();
        return refreshingRef.current;
    }, [persist]);

    const login = useCallback(async (email, password) => {
        const data = await loginUser(email, password);
        persist(
            data.access_token,
            { id: data.user_id, email: data.email },
            data.refresh_token,
            data.expires_at,
        );
        return data;
    }, [persist]);

    const signup = useCallback(async (email, password) => {
        const data = await signupUser(email, password);
        if (data.access_token) {
            persist(
                data.access_token,
                { id: data.user_id, email: data.email },
                data.refresh_token,
                data.expires_at,
            );
        }
        return data;
    }, [persist]);

    const logout = useCallback(async () => {
        const currentToken = token;
        persist(null, null);
        if (currentToken) {
            try { await logoutUser(currentToken); } catch { /* ignore */ }
        }
    }, [token, persist]);

    // Proactive silent refresh: schedule one a minute before expiry.
    useEffect(() => {
        if (refreshTimerRef.current) {
            clearTimeout(refreshTimerRef.current);
            refreshTimerRef.current = null;
        }
        const expiresAt = expiresAtRef.current;
        if (!token || !expiresAt) return;
        const msUntil = expiresAt * 1000 - Date.now() - REFRESH_SKEW_MS;
        refreshTimerRef.current = setTimeout(() => { doRefresh(); }, Math.max(msUntil, 0));
        return () => {
            if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
        };
    }, [token, doRefresh]);

    // Reactive refresh: on a 401, try one refresh + replay before giving up.
    // Wrap exactly once even under StrictMode double-mount.
    useEffect(() => {
        if (!window.fetch[FETCH_WRAPPED]) {
            const original = window.fetch;
            const wrapped = async (...args) => {
                const res = await original(...args);
                if (res.status !== 401) return res;

                // Don't try to refresh the auth endpoints themselves.
                const url = typeof args[0] === "string" ? args[0] : args[0]?.url || "";
                if (url.includes("/api/auth/")) {
                    if (localStorage.getItem("token")) persist(null, null);
                    return res;
                }

                const newToken = await doRefresh();
                if (!newToken) {
                    if (localStorage.getItem("token")) persist(null, null);
                    return res;
                }
                // Replay the original request with the fresh token.
                const [input, init = {}] = args;
                const headers = new Headers(init.headers || {});
                headers.set("Authorization", `Bearer ${newToken}`);
                return original(input, { ...init, headers });
            };
            wrapped[FETCH_WRAPPED] = true;
            wrapped.__original = original;
            window.fetch = wrapped;
        }
    }, [doRefresh, persist]);

    // Cross-tab sync: log out everywhere when one tab clears the token.
    useEffect(() => {
        const onStorage = (e) => {
            if (e.key === "token" && !e.newValue) {
                setToken(null);
                setUser(null);
                refreshTokenRef.current = null;
                expiresAtRef.current = null;
            }
        };
        window.addEventListener("storage", onStorage);
        return () => window.removeEventListener("storage", onStorage);
    }, []);

    return (
        <AuthContext.Provider value={{ user, token, loading, login, signup, logout, isAuthenticated: !!token }}>
            {children}
        </AuthContext.Provider>
    );
}

export function useAuth() {
    const ctx = useContext(AuthContext);
    if (!ctx) throw new Error("useAuth must be used within AuthProvider");
    return ctx;
}
