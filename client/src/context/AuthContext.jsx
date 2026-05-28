import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { loginUser, logoutUser, signupUser } from "../api";

const AuthContext = createContext(null);

function readStored() {
    const token = localStorage.getItem("token");
    const userRaw = localStorage.getItem("user");
    if (!token || !userRaw) return { token: null, user: null };
    try {
        return { token, user: JSON.parse(userRaw) };
    } catch {
        return { token: null, user: null };
    }
}

export function AuthProvider({ children }) {
    const initial = readStored();
    const [user, setUser] = useState(initial.user);
    const [token, setToken] = useState(initial.token);
    const [loading, setLoading] = useState(false);

    const persist = (nextToken, nextUser) => {
        if (nextToken && nextUser) {
            localStorage.setItem("token", nextToken);
            localStorage.setItem("user", JSON.stringify(nextUser));
        } else {
            localStorage.removeItem("token");
            localStorage.removeItem("user");
        }
        setToken(nextToken);
        setUser(nextUser);
    };

    const login = useCallback(async (email, password) => {
        const data = await loginUser(email, password);
        persist(data.access_token, { id: data.user_id, email: data.email });
        return data;
    }, []);

    const signup = useCallback(async (email, password) => {
        const data = await signupUser(email, password);
        if (data.access_token) {
            persist(data.access_token, { id: data.user_id, email: data.email });
        }
        return data;
    }, []);

    const logout = useCallback(async () => {
        const currentToken = token;
        persist(null, null);
        if (currentToken) {
            try { await logoutUser(currentToken); } catch { /* ignore */ }
        }
    }, [token]);

    // Auto-logout on 401 from any fetch.
    useEffect(() => {
        const original = window.fetch;
        const wrapped = async (...args) => {
            const res = await original(...args);
            if (res.status === 401 && token) {
                persist(null, null);
            }
            return res;
        };
        window.fetch = wrapped;
        return () => { window.fetch = original; };
    }, [token]);

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
