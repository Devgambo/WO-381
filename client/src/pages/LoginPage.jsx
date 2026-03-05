import { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { useNavigate } from "react-router-dom";

export default function LoginPage() {
    const [isSignup, setIsSignup] = useState(false);
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [error, setError] = useState(null);
    const [loading, setLoading] = useState(false);
    const [signupSuccess, setSignupSuccess] = useState(false);
    const { login, signup } = useAuth();
    const navigate = useNavigate();

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError(null);
        setLoading(true);
        try {
            if (isSignup) {
                const data = await signup(email, password);
                if (data.access_token) {
                    navigate("/dashboard");
                } else {
                    setSignupSuccess(true);
                }
            } else {
                await login(email, password);
                navigate("/dashboard");
            }
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen flex items-center justify-center bg-[var(--color-bg-primary)] px-4">
            <div className="w-full max-w-[400px] bg-[var(--color-bg-card)] border border-[var(--color-border-subtle)] rounded-2xl p-8 backdrop-blur-md animate-fade-up shadow-[0_8px_32px_rgba(0,0,0,0.3)]">
                <div className="text-center mb-8">
                    <h1 className="text-2xl font-extrabold tracking-tight bg-gradient-to-br from-[var(--color-text-primary)] to-[var(--color-accent-light)] bg-clip-text text-transparent">
                        🧑‍🔬 Compliance Check
                    </h1>
                    <p className="text-sm text-[var(--color-text-secondary)] mt-1">
                        {isSignup ? "Create your account" : "Sign in to continue"}
                    </p>
                </div>

                {signupSuccess && (
                    <div className="flex items-center gap-2 px-4 py-3 rounded-lg bg-green-500/10 border border-green-500/30 text-green-300 text-sm mb-5">
                        ✅ Account created! Please check your email to confirm, then log in.
                    </div>
                )}

                {error && (
                    <div className="flex items-center gap-2 px-4 py-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-300 text-sm mb-5">
                        <span>❌</span> {error}
                    </div>
                )}

                <form onSubmit={handleSubmit} className="flex flex-col gap-4">
                    <div>
                        <label className="block text-xs font-semibold text-[var(--color-text-secondary)] mb-1.5 uppercase tracking-wider">
                            Email
                        </label>
                        <input
                            type="email"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            required
                            placeholder="you@example.com"
                            className="w-full px-4 py-2.5 rounded-lg bg-[var(--color-bg-glass)] border border-[var(--color-border-subtle)] text-[var(--color-text-primary)] text-sm placeholder:text-[var(--color-text-muted)] focus:outline-none focus:border-[var(--color-accent)] transition-colors"
                        />
                    </div>
                    <div>
                        <label className="block text-xs font-semibold text-[var(--color-text-secondary)] mb-1.5 uppercase tracking-wider">
                            Password
                        </label>
                        <input
                            type="password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            required
                            minLength={6}
                            placeholder="••••••••"
                            className="w-full px-4 py-2.5 rounded-lg bg-[var(--color-bg-glass)] border border-[var(--color-border-subtle)] text-[var(--color-text-primary)] text-sm placeholder:text-[var(--color-text-muted)] focus:outline-none focus:border-[var(--color-accent)] transition-colors"
                        />
                    </div>
                    <button
                        type="submit"
                        disabled={loading}
                        className="mt-2 w-full py-2.5 font-semibold text-sm text-white rounded-lg bg-gradient-to-br from-[var(--color-accent)] to-purple-600 shadow-[0_4px_14px_var(--color-accent-glow)] hover:shadow-[0_6px_22px_var(--color-accent-glow)] hover:-translate-y-0.5 transition-all disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                    >
                        {loading ? "Please wait…" : isSignup ? "Sign Up" : "Sign In"}
                    </button>
                </form>

                <div className="text-center mt-6">
                    <button
                        onClick={() => { setIsSignup(!isSignup); setError(null); setSignupSuccess(false); }}
                        className="text-sm text-[var(--color-text-secondary)] hover:text-[var(--color-accent-light)] transition-colors bg-transparent border-none cursor-pointer"
                    >
                        {isSignup ? "Already have an account? Sign In" : "Don't have an account? Sign Up"}
                    </button>
                </div>
            </div>
        </div>
    );
}
