import { createContext, useContext, useState, useEffect } from "react";
import { loginUser, signupUser } from "../api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
    const [user, setUser] = useState(null);
    const [token, setToken] = useState(localStorage.getItem("token"));
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const savedToken = localStorage.getItem("token");
        const savedUser = localStorage.getItem("user");
        if (savedToken && savedUser) {
            setToken(savedToken);
            setUser(JSON.parse(savedUser));
        }
        setLoading(false);
    }, []);

    const login = async (email, password) => {
        const data = await loginUser(email, password);
        localStorage.setItem("token", data.access_token);
        localStorage.setItem("user", JSON.stringify({ id: data.user_id, email: data.email }));
        setToken(data.access_token);
        setUser({ id: data.user_id, email: data.email });
        return data;
    };

    const signup = async (email, password) => {
        const data = await signupUser(email, password);
        if (data.access_token) {
            localStorage.setItem("token", data.access_token);
            localStorage.setItem("user", JSON.stringify({ id: data.user_id, email: data.email }));
            setToken(data.access_token);
            setUser({ id: data.user_id, email: data.email });
        }
        return data;
    };

    const logout = () => {
        localStorage.removeItem("token");
        localStorage.removeItem("user");
        setToken(null);
        setUser(null);
    };

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
