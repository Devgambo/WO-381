import { useState } from "react";
import { useAuth } from "../context/AuthContext";
import { useNavigate } from "react-router-dom";
import { AlertTriangleIcon, ArrowRightIcon, CheckIcon } from "../components/Icons";

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
        <div className="min-h-screen flex bg-[var(--color-bg-primary)]">
            {/* Left brand panel */}
            <div className="hidden md:flex flex-col justify-between w-[45%] bg-[var(--color-bg-secondary)] border-r border-[var(--color-border-subtle)] p-12 relative overflow-hidden">
                <div
                    aria-hidden
                    className="absolute inset-0 opacity-[0.06]"
                    style={{
                        backgroundImage:
                            "linear-gradient(var(--color-text-primary) 1px, transparent 1px), linear-gradient(90deg, var(--color-text-primary) 1px, transparent 1px)",
                        backgroundSize: "32px 32px",
                    }}
                />
                <div className="relative">
                    <div className="flex items-baseline gap-2">
                        <span className="mono text-[10px] tracking-[0.2em] uppercase text-[var(--color-accent)]">RCC</span>
                        <span className="label-mono">Engine v2.1</span>
                    </div>
                    <h1 className="text-3xl font-semibold text-[var(--color-text-primary)] tracking-tight mt-3 leading-tight">
                        Structural compliance,<br />verified by code.
                    </h1>
                    <p className="text-sm text-[var(--color-text-secondary)] mt-4 leading-relaxed max-w-md">
                        Multi-agent vision + RAG over IS 456:2000 and SP 34. Upload a foundation,
                        slab, beam, or column drawing — receive a citation-backed verdict.
                    </p>
                </div>

                <div className="relative grid grid-cols-2 gap-4 max-w-sm">
                    {[
                        { k: "IS 456", v: "Concrete code" },
                        { k: "SP 34", v: "Detailing handbook" },
                        { k: "IS 13920", v: "Seismic ductility" },
                        { k: "IS 1786", v: "HYSD steel" },
                    ].map((c) => (
                        <div key={c.k} className="border border-[var(--color-border-subtle)] p-3">
                            <p className="mono text-[10px] uppercase tracking-wider text-[var(--color-accent-light)]">
                                {c.k}
                            </p>
                            <p className="text-xs text-[var(--color-text-secondary)] mt-1">{c.v}</p>
                        </div>
                    ))}
                </div>

                <p className="relative label-mono">
                    © Compliance Engine · for review, not a substitute for a licensed engineer
                </p>
            </div>

            {/* Right form panel */}
            <div className="flex-1 flex items-center justify-center px-6">
                <div className="w-full max-w-[420px]">
                    <div className="md:hidden mb-8">
                        <span className="mono text-[10px] tracking-[0.2em] uppercase text-[var(--color-accent)]">RCC</span>
                        <h1 className="text-2xl font-semibold tracking-tight mt-1">Compliance Engine</h1>
                    </div>

                    <div className="mb-7">
                        <span className="label-mono">
                            {isSignup ? "Create account" : "Authenticate"}
                        </span>
                        <h2 className="text-xl font-semibold tracking-tight text-[var(--color-text-primary)] mt-1">
                            {isSignup ? "Get started" : "Welcome back"}
                        </h2>
                    </div>

                    {signupSuccess && (
                        <div className="rounded-[3px] border border-[rgba(16,185,129,0.35)] bg-[rgba(16,185,129,0.07)] text-[var(--color-success)] px-4 py-3 text-xs mb-5 flex items-start gap-2">
                            <CheckIcon size={14} className="shrink-0 mt-0.5" />
                            <span>Account created. Check your email to confirm, then sign in.</span>
                        </div>
                    )}

                    {error && (
                        <div className="rounded-[3px] border border-[rgba(239,68,68,0.35)] bg-[rgba(239,68,68,0.07)] text-[var(--color-danger)] px-4 py-3 text-xs mb-5 flex items-start gap-2">
                            <AlertTriangleIcon size={14} className="shrink-0 mt-0.5" />
                            <span>{error}</span>
                        </div>
                    )}

                    <form onSubmit={handleSubmit} className="flex flex-col gap-5">
                        <div>
                            <label
                                htmlFor="login-email"
                                className="block label-mono mb-1.5"
                            >
                                Email
                            </label>
                            <input
                                id="login-email"
                                name="email"
                                type="email"
                                autoComplete="email"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                required
                                placeholder="you@example.com"
                                className="input-base w-full px-3.5 py-2.5 text-sm placeholder:text-[var(--color-text-faint)]"
                            />
                        </div>
                        <div>
                            <label
                                htmlFor="login-password"
                                className="block label-mono mb-1.5"
                            >
                                Password
                            </label>
                            <input
                                id="login-password"
                                name="password"
                                type="password"
                                autoComplete={isSignup ? "new-password" : "current-password"}
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                required
                                minLength={6}
                                placeholder="• • • • • • • •"
                                className="input-base w-full px-3.5 py-2.5 text-sm placeholder:text-[var(--color-text-faint)] mono tracking-[0.2em]"
                            />
                        </div>
                        <button
                            type="submit"
                            disabled={loading}
                            className="btn-primary py-2.5 px-4 text-sm cursor-pointer mt-1 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                        >
                            {loading ? (
                                <>
                                    <span className="w-3 h-3 border border-white/40 border-t-white animate-spin-slow rounded-full" />
                                    <span>Authenticating…</span>
                                </>
                            ) : (
                                <>
                                    <span>{isSignup ? "Create account" : "Sign in"}</span>
                                    <ArrowRightIcon size={14} />
                                </>
                            )}
                        </button>
                    </form>

                    <div className="mt-8 pt-5 border-t border-[var(--color-border-subtle)] flex items-center justify-between">
                        <span className="label-mono">
                            {isSignup ? "Have an account?" : "No account?"}
                        </span>
                        <button
                            onClick={() => { setIsSignup(!isSignup); setError(null); setSignupSuccess(false); }}
                            className="text-xs text-[var(--color-accent-light)] hover:text-[var(--color-accent)] transition-colors bg-transparent border-none cursor-pointer mono uppercase tracking-wider inline-flex items-center gap-1.5"
                        >
                            <span>{isSignup ? "Sign in" : "Sign up"}</span>
                            <ArrowRightIcon size={12} />
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
