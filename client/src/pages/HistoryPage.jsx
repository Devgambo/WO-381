import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { fetchReports, downloadPdf, deleteReport } from "../api";
import ReportDisplay from "../components/ReportDisplay";

const TYPE_CODE = {
    foundation: "FDN",
    slab: "SLB",
    beam: "BMS",
    column: "COL",
    unknown: "???",
};

const TYPE_COLOR = {
    foundation: "#10b981",
    slab: "#38bdf8",
    beam: "#f59e0b",
    column: "#a855f7",
    unknown: "#6b7280",
};

export default function HistoryPage() {
    const { token } = useAuth();
    const navigate = useNavigate();
    const [reports, setReports] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [selectedReport, setSelectedReport] = useState(null);
    const [viewType, setViewType] = useState("initial");
    const [deletingIds, setDeletingIds] = useState(() => new Set());
    const [filter, setFilter] = useState("all"); // all | initial | final

    useEffect(() => {
        const controller = new AbortController();
        const load = async () => {
            setLoading(true);
            setError(null);
            try {
                const data = await fetchReports(token);
                if (controller.signal.aborted) return;
                setReports(data.reports || []);
            } catch (err) {
                if (!controller.signal.aborted) setError(err.message);
            } finally {
                if (!controller.signal.aborted) setLoading(false);
            }
        };
        load();
        return () => controller.abort();
    }, [token]);

    const handleDownload = async (report, type) => {
        const content = type === "initial" ? report.initial_report : report.final_report;
        if (!content) return;
        const rawSession = (report.session_name || "report").slice(0, 80);
        const safeSession = rawSession.replace(/[^a-zA-Z0-9]/g, "_");
        const filename = `${type}_report_${safeSession}`;
        try {
            await downloadPdf(content, filename, token);
        } catch (err) {
            setError(err.message);
        }
    };

    const handleDelete = async (reportId) => {
        if (!window.confirm("Delete this report? This cannot be undone.")) return;
        setDeletingIds((prev) => {
            const next = new Set(prev);
            next.add(reportId);
            return next;
        });
        try {
            await deleteReport(reportId, token);
            setReports((prev) => prev.filter((r) => r.id !== reportId));
        } catch (err) {
            setError(err.message);
        } finally {
            setDeletingIds((prev) => {
                const next = new Set(prev);
                next.delete(reportId);
                return next;
            });
        }
    };

    const handleResume = (report) => {
        navigate("/dashboard", {
            state: { resumeReport: report },
        });
    };

    const formatDate = (dateStr) => {
        if (!dateStr) return "—";
        const d = new Date(dateStr);
        if (Number.isNaN(d.getTime())) return "—";
        return d.toLocaleDateString("en-US", {
            year: "numeric",
            month: "short",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit",
        });
    };

    const visible = reports.filter((r) => {
        if (filter === "all") return true;
        if (filter === "final") return Boolean(r.final_report);
        if (filter === "initial") return r.initial_report && !r.final_report;
        return true;
    });

    const counts = {
        all: reports.length,
        initial: reports.filter((r) => r.initial_report && !r.final_report).length,
        final: reports.filter((r) => Boolean(r.final_report)).length,
    };

    if (selectedReport) {
        const reportContent = viewType === "initial" ? selectedReport.initial_report : selectedReport.final_report;
        return (
            <>
                <header className="mb-8 pb-6 border-b border-[var(--color-border-subtle)]">
                    <div className="flex items-baseline gap-3 mb-2">
                        <button
                            onClick={() => setSelectedReport(null)}
                            className="bg-transparent border-none cursor-pointer mono text-[10px] tracking-[0.18em] uppercase text-[var(--color-text-secondary)] hover:text-[var(--color-accent-light)] transition-colors"
                        >
                            ← /history
                        </button>
                        <span className="label-mono text-[var(--color-text-faint)]">·</span>
                        <span className="label-mono">{selectedReport.id?.slice(0, 8)}</span>
                    </div>
                    <h1 className="text-2xl font-semibold tracking-tight text-[var(--color-text-primary)] truncate">
                        {selectedReport.session_name || "Untitled report"}
                    </h1>
                    <p className="text-xs text-[var(--color-text-muted)] mt-2 mono">
                        {formatDate(selectedReport.created_at)}
                    </p>
                </header>

                <div className="flex gap-0 mb-6 border border-[var(--color-border-subtle)] w-fit">
                    {selectedReport.initial_report && (
                        <button
                            onClick={() => setViewType("initial")}
                            className={`px-4 py-2 text-xs mono uppercase tracking-wider border-r border-[var(--color-border-subtle)] last:border-r-0 transition-colors cursor-pointer
                                ${viewType === "initial"
                                    ? "bg-[var(--color-accent-glow)] text-[var(--color-accent-light)]"
                                    : "bg-transparent text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-glass)]"
                                }`}
                        >
                            Initial
                        </button>
                    )}
                    {selectedReport.final_report && (
                        <button
                            onClick={() => setViewType("final")}
                            className={`px-4 py-2 text-xs mono uppercase tracking-wider border-r border-[var(--color-border-subtle)] last:border-r-0 transition-colors cursor-pointer
                                ${viewType === "final"
                                    ? "bg-[var(--color-accent-glow)] text-[var(--color-accent-light)]"
                                    : "bg-transparent text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-glass)]"
                                }`}
                        >
                            Final
                        </button>
                    )}
                </div>

                {reportContent ? (
                    <section className="panel p-6 animate-fade-up">
                        <ReportDisplay
                            report={reportContent}
                            title={viewType === "initial" ? "Initial extraction" : "Final verdict"}
                            filenamePrefix={`${viewType}_compliance_report`}
                        />
                    </section>
                ) : (
                    <div className="border border-dashed border-[var(--color-border-subtle)] py-16 text-center">
                        <p className="label-mono">No {viewType} report</p>
                    </div>
                )}
            </>
        );
    }

    return (
        <>
            <header className="mb-8 pb-6 border-b border-[var(--color-border-subtle)]">
                <div className="flex items-baseline gap-3 mb-2">
                    <span className="label-mono">/history</span>
                    <span className="label-mono text-[var(--color-text-faint)]">·</span>
                    <span className="label-mono">{counts.all} records</span>
                </div>
                <div className="flex items-end justify-between gap-4 flex-wrap">
                    <div>
                        <h1 className="text-2xl font-semibold tracking-tight text-[var(--color-text-primary)]">
                            Report history
                        </h1>
                        <p className="text-sm text-[var(--color-text-secondary)] mt-1">
                            Resume incomplete runs, download archives, or delete sessions.
                        </p>
                    </div>
                    <div className="flex gap-0 border border-[var(--color-border-subtle)]">
                        {[
                            { k: "all", label: "All" },
                            { k: "initial", label: "Open" },
                            { k: "final", label: "Closed" },
                        ].map((tab, i, arr) => (
                            <button
                                key={tab.k}
                                onClick={() => setFilter(tab.k)}
                                className={`px-3 py-1.5 mono text-[10px] uppercase tracking-wider transition-colors cursor-pointer
                                    ${i < arr.length - 1 ? "border-r border-[var(--color-border-subtle)]" : ""}
                                    ${filter === tab.k
                                        ? "bg-[var(--color-accent-glow)] text-[var(--color-accent-light)]"
                                        : "bg-transparent text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-glass)]"
                                    }`}
                            >
                                {tab.label} <span className="text-[var(--color-text-muted)] ml-1">{String(counts[tab.k]).padStart(2, "0")}</span>
                            </button>
                        ))}
                    </div>
                </div>
            </header>

            {error && (
                <div className="flex items-start gap-3 px-4 py-3 border border-[rgba(239,68,68,0.4)] bg-[rgba(239,68,68,0.06)] text-[var(--color-danger)] text-xs mb-6 animate-fade-up">
                    <span className="mono pt-0.5">ERR</span>
                    <span className="flex-1">{error}</span>
                </div>
            )}

            {loading ? (
                <div className="border border-[var(--color-border-subtle)] bg-[var(--color-bg-card)] py-12 flex flex-col items-center gap-4 text-center">
                    <div className="w-8 h-8 border-2 border-[var(--color-border-medium)] border-t-[var(--color-accent)] rounded-full animate-spin-slow" />
                    <p className="label-mono">Loading records…</p>
                </div>
            ) : visible.length === 0 ? (
                <div className="border border-dashed border-[var(--color-border-subtle)] py-20 text-center">
                    <p className="mono text-[10px] tracking-[0.18em] uppercase text-[var(--color-text-muted)] mb-2">
                        Empty
                    </p>
                    <p className="text-sm text-[var(--color-text-secondary)]">
                        {filter === "all" ? "No reports yet." : `No ${filter === "initial" ? "open" : "closed"} reports.`}
                    </p>
                </div>
            ) : (
                <div className="border border-[var(--color-border-subtle)] divide-y divide-[var(--color-border-subtle)]">
                    {/* Column header */}
                    <div className="hidden md:grid grid-cols-[80px_1fr_180px_auto] gap-4 px-4 py-2.5 bg-[var(--color-bg-secondary)]">
                        <span className="label-mono">Type</span>
                        <span className="label-mono">Session</span>
                        <span className="label-mono">Created</span>
                        <span className="label-mono text-right">Actions</span>
                    </div>

                    {visible.map((report) => {
                        const isDeleting = deletingIds.has(report.id);
                        const type = report.drawing_type || "unknown";
                        const code = TYPE_CODE[type] || TYPE_CODE.unknown;
                        const color = TYPE_COLOR[type] || TYPE_COLOR.unknown;
                        return (
                            <div
                                key={report.id}
                                className="grid grid-cols-1 md:grid-cols-[80px_1fr_180px_auto] gap-4 px-4 py-4 bg-[var(--color-bg-card)] hover:bg-[var(--color-bg-glass)] transition-colors"
                            >
                                <div className="flex items-start">
                                    <span
                                        className="mono text-[10px] uppercase tracking-wider px-1.5 py-0.5 border"
                                        style={{ borderColor: `${color}66`, color, background: `${color}14` }}
                                    >
                                        {code}
                                    </span>
                                </div>

                                <div className="min-w-0">
                                    <p
                                        className="font-medium text-sm text-[var(--color-text-primary)] truncate cursor-pointer hover:text-[var(--color-accent-light)] transition-colors"
                                        onClick={() => { setSelectedReport(report); setViewType(report.initial_report ? "initial" : "final"); }}
                                    >
                                        {report.session_name || "Untitled report"}
                                    </p>
                                    <div className="flex gap-2 mt-1.5 flex-wrap">
                                        <span className="mono text-[10px] tracking-wider text-[var(--color-text-muted)]">
                                            {report.id?.slice(0, 8)}
                                        </span>
                                        {report.initial_report && (
                                            <span className="mono text-[10px] uppercase tracking-wider text-[var(--color-info)]">
                                                · initial
                                            </span>
                                        )}
                                        {report.final_report ? (
                                            <span className="mono text-[10px] uppercase tracking-wider text-[var(--color-success)]">
                                                · final
                                            </span>
                                        ) : (
                                            <span className="mono text-[10px] uppercase tracking-wider text-[var(--color-warning)]">
                                                · pending
                                            </span>
                                        )}
                                    </div>
                                </div>

                                <p className="text-xs text-[var(--color-text-muted)] mono pt-0.5">
                                    {formatDate(report.created_at)}
                                </p>

                                <div className="flex items-center gap-1.5 justify-end flex-wrap">
                                    <button
                                        onClick={() => { setSelectedReport(report); setViewType(report.initial_report ? "initial" : "final"); }}
                                        className="btn-secondary px-2.5 py-1.5 mono text-[10px] uppercase tracking-wider cursor-pointer"
                                    >
                                        View
                                    </button>
                                    {report.initial_report && !report.final_report && (
                                        <button
                                            onClick={() => handleResume(report)}
                                            className="px-2.5 py-1.5 mono text-[10px] uppercase tracking-wider border border-[rgba(245,158,11,0.4)] text-[var(--color-warning)] hover:bg-[rgba(245,158,11,0.08)] transition-colors cursor-pointer bg-transparent"
                                            title="Resume — provide missing data and generate final report"
                                        >
                                            Resume
                                        </button>
                                    )}
                                    {report.initial_report && (
                                        <button
                                            onClick={() => handleDownload(report, "initial")}
                                            className="px-2.5 py-1.5 mono text-[10px] uppercase tracking-wider border border-[var(--color-border-medium)] text-[var(--color-text-secondary)] hover:text-[var(--color-accent-light)] hover:border-[var(--color-accent)] transition-colors cursor-pointer bg-transparent"
                                        >
                                            ↓ Init
                                        </button>
                                    )}
                                    {report.final_report && (
                                        <button
                                            onClick={() => handleDownload(report, "final")}
                                            className="px-2.5 py-1.5 mono text-[10px] uppercase tracking-wider border border-[rgba(16,185,129,0.4)] text-[var(--color-success)] hover:bg-[rgba(16,185,129,0.08)] transition-colors cursor-pointer bg-transparent"
                                        >
                                            ↓ Final
                                        </button>
                                    )}
                                    <button
                                        onClick={() => handleDelete(report.id)}
                                        disabled={isDeleting}
                                        className="btn-danger px-2.5 py-1.5 mono text-[10px] uppercase tracking-wider cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
                                        title="Delete report"
                                    >
                                        {isDeleting ? "…" : "Delete"}
                                    </button>
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}
        </>
    );
}
