import { useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import {
    CompassIcon,
    HistoryIcon,
    LogOutIcon,
    MenuIcon,
    PlusIcon,
    XIcon,
} from "./Icons";

const NAV_ITEMS = [
    { to: "/dashboard", label: "New Report", Icon: PlusIcon },
    { to: "/history", label: "History", Icon: HistoryIcon },
    { to: "/about", label: "How it works", Icon: CompassIcon },
];

export default function Sidebar() {
    const { user, logout } = useAuth();
    const navigate = useNavigate();
    const [open, setOpen] = useState(false);

    const handleLogout = async () => {
        await logout();
        navigate("/login");
    };

    const linkClass = ({ isActive }) =>
        `relative flex items-center gap-3 px-4 py-2.5 text-sm font-medium transition-colors border-l-2
        ${isActive
            ? "border-[var(--color-accent)] text-[var(--color-text-primary)] bg-[var(--color-bg-glass)]"
            : "border-transparent text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-bg-glass)]"
        }`;

    const close = () => setOpen(false);

    return (
        <>
            <button
                type="button"
                onClick={() => setOpen((v) => !v)}
                aria-label={open ? "Close menu" : "Open menu"}
                className="md:hidden fixed top-4 left-4 z-30 w-10 h-10 grid place-items-center bg-[var(--color-bg-secondary)] border border-[var(--color-border-medium)] text-[var(--color-text-primary)] cursor-pointer rounded-[3px]"
            >
                {open ? <XIcon size={16} /> : <MenuIcon size={16} />}
            </button>

            {open && (
                <div
                    onClick={close}
                    className="md:hidden fixed inset-0 bg-black/60 z-10"
                />
            )}

            <aside
                className={`w-[260px] bg-[var(--color-bg-secondary)] border-r border-[var(--color-border-subtle)] fixed top-0 left-0 bottom-0 overflow-y-auto flex flex-col z-20 transition-transform
                    ${open ? "translate-x-0" : "max-md:-translate-x-full"}`}
            >
                {/* Brand */}
                <div className="px-5 py-5 border-b border-[var(--color-border-subtle)]">
                    <div className="flex items-baseline gap-2">
                        <span className="text-[10px] font-mono uppercase tracking-[0.18em] text-[var(--color-accent)]">RCC</span>
                        <span className="label-mono">v2.1</span>
                    </div>
                    <h1 className="text-base font-semibold text-[var(--color-text-primary)] mt-1 leading-tight">
                        Compliance Engine
                    </h1>
                    <p className="text-[11px] text-[var(--color-text-muted)] mt-1 leading-relaxed">
                        IS 456:2000 · SP 34 · multi-agent verification
                    </p>
                </div>

                {/* User */}
                {user && (
                    <div className="px-5 py-4 border-b border-[var(--color-border-subtle)]">
                        <p className="label-mono mb-1.5">Signed in</p>
                        <p className="text-xs text-[var(--color-text-primary)] truncate mono">{user.email}</p>
                    </div>
                )}

                {/* Nav */}
                <nav className="flex flex-col py-3">
                    {NAV_ITEMS.map((item) => (
                        <NavLink key={item.to} to={item.to} className={linkClass} onClick={close}>
                            <item.Icon size={15} className="shrink-0 opacity-70" />
                            <span>{item.label}</span>
                        </NavLink>
                    ))}
                </nav>

                {/* Codes covered */}
                <div className="px-5 py-4 border-t border-[var(--color-border-subtle)]">
                    <p className="label-mono mb-2">Codes covered</p>
                    <ul className="space-y-1 text-xs text-[var(--color-text-secondary)] leading-relaxed">
                        <li className="flex gap-2">
                            <span className="mono text-[var(--color-text-muted)] shrink-0">456</span>
                            <span>Plain & reinforced concrete</span>
                        </li>
                        <li className="flex gap-2">
                            <span className="mono text-[var(--color-text-muted)] shrink-0">SP 34</span>
                            <span>Reinforcement detailing</span>
                        </li>
                        <li className="flex gap-2">
                            <span className="mono text-[var(--color-text-muted)] shrink-0">13920</span>
                            <span>Ductile seismic detailing</span>
                        </li>
                        <li className="flex gap-2">
                            <span className="mono text-[var(--color-text-muted)] shrink-0">1786</span>
                            <span>HYSD / TMT steel</span>
                        </li>
                    </ul>
                </div>

                {/* Workflow */}
                <div className="px-5 py-4 border-t border-[var(--color-border-subtle)]">
                    <p className="label-mono mb-2">Workflow</p>
                    <ol className="space-y-1.5 text-[11px] text-[var(--color-text-secondary)] leading-relaxed">
                        {[
                            "Upload drawing",
                            "Vision extract",
                            "Resolve missing data",
                            "RAG verdict",
                            "Download",
                        ].map((step, i) => (
                            <li key={step} className="flex gap-2.5 items-baseline">
                                <span className="mono text-[var(--color-text-muted)] shrink-0">
                                    {String(i + 1).padStart(2, "0")}
                                </span>
                                <span>{step}</span>
                            </li>
                        ))}
                    </ol>
                </div>

                <div className="flex-1" />

                {/* Logout */}
                <div className="px-5 py-4 border-t border-[var(--color-border-subtle)]">
                    <button
                        onClick={handleLogout}
                        className="btn-danger w-full px-3 py-2 text-xs mono uppercase tracking-wider cursor-pointer inline-flex items-center justify-center gap-2"
                    >
                        <LogOutIcon size={13} />
                        <span>Sign out</span>
                    </button>
                </div>
            </aside>
        </>
    );
}
