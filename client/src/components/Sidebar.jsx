import { useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function Sidebar() {
    const { user, logout } = useAuth();
    const navigate = useNavigate();
    const [open, setOpen] = useState(false);

    const handleLogout = async () => {
        await logout();
        navigate("/login");
    };

    const linkClass = ({ isActive }) =>
        `flex items-center gap-2.5 px-4 py-2.5 rounded-lg text-sm font-medium transition-all ${isActive
            ? "bg-[var(--color-accent-glow)] text-[var(--color-text-primary)] border border-[var(--color-accent)]/30"
            : "text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-bg-glass)] border border-transparent"
        }`;

    const close = () => setOpen(false);

    return (
        <>
            {/* Mobile menu toggle */}
            <button
                type="button"
                onClick={() => setOpen((v) => !v)}
                aria-label={open ? "Close menu" : "Open menu"}
                className="md:hidden fixed top-4 left-4 z-30 w-10 h-10 grid place-items-center rounded-lg bg-[var(--color-bg-secondary)] border border-[var(--color-border-subtle)] text-lg cursor-pointer"
            >
                {open ? "✕" : "☰"}
            </button>

            {open && (
                <div
                    onClick={close}
                    className="md:hidden fixed inset-0 bg-black/50 z-10"
                />
            )}

            <aside
                className={`w-[280px] bg-[var(--color-bg-secondary)] border-r border-[var(--color-border-subtle)] fixed top-0 left-0 bottom-0 overflow-y-auto flex flex-col p-8 z-20 transition-transform
                    ${open ? "translate-x-0" : "max-md:-translate-x-full"}`}
            >
                {user && (
                    <div className="pb-5 mb-5 border-b border-[var(--color-border-subtle)]">
                        <p className="text-xs font-bold uppercase tracking-wider text-[var(--color-text-muted)] mb-1">Signed in as</p>
                        <p className="text-sm text-[var(--color-text-primary)] font-medium truncate">{user.email}</p>
                    </div>
                )}

                <nav className="flex flex-col gap-1.5 mb-6">
                    <NavLink to="/dashboard" className={linkClass} onClick={close}>
                        🧑‍🔬 New Report
                    </NavLink>
                    <NavLink to="/history" className={linkClass} onClick={close}>
                        📜 History
                    </NavLink>
                </nav>

                <div className="pb-5 mb-5 border-b border-[var(--color-border-subtle)]">
                    <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--color-text-secondary)] mb-2">ℹ️ About</h3>
                    <p className="text-sm text-[var(--color-text-secondary)] leading-relaxed">
                        This tool analyzes RCC structural drawings for compliance with:
                    </p>
                    <ul className="list-disc pl-5 mt-1 text-sm text-[var(--color-text-secondary)] leading-relaxed">
                        <li><strong className="text-[var(--color-text-primary)]">IS 456:2000</strong> — Plain & Reinforced Concrete</li>
                        <li><strong className="text-[var(--color-text-primary)]">SP 34</strong> — Handbook on Concrete Reinforcement Detailing</li>
                    </ul>
                </div>

                <div className="pb-5 border-b border-[var(--color-border-subtle)]">
                    <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--color-text-secondary)] mb-2">📝 Instructions</h3>
                    <ol className="list-decimal pl-5 text-sm text-[var(--color-text-secondary)] leading-relaxed space-y-0.5">
                        <li>Upload your PDF or Image drawing</li>
                        <li>Generate initial report</li>
                        <li>Review missing information</li>
                        <li>Provide additional details</li>
                        <li>Generate final report</li>
                        <li>Download the report</li>
                    </ol>
                </div>

                <div className="flex-1" />

                <button
                    onClick={handleLogout}
                    className="flex items-center gap-2 w-full px-4 py-2.5 text-sm font-medium text-red-400 rounded-lg border border-transparent hover:border-red-500/30 hover:bg-red-500/10 transition-all cursor-pointer bg-transparent"
                >
                    🚪 Logout
                </button>
            </aside>
        </>
    );
}
