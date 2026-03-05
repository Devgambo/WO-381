import { useState, useEffect } from "react";
import { useAuth } from "../context/AuthContext";
import { fetchReports, downloadPdf } from "../api";
import ReportDisplay from "../components/ReportDisplay";

export default function HistoryPage() {
    const { token } = useAuth();
    const [reports, setReports] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [selectedReport, setSelectedReport] = useState(null);
    const [viewType, setViewType] = useState("initial");

    useEffect(() => {
        loadReports();
    }, []);

    const loadReports = async () => {
        setLoading(true);
        setError(null);
        try {
            const data = await fetchReports(token);
            setReports(data.reports || []);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const handleDownload = async (report, type) => {
        const content = type === "initial" ? report.initial_report : report.final_report;
        if (!content) return;
        const filename = `${type}_report_${report.session_name.replace(/[^a-zA-Z0-9]/g, "_")}`;
        await downloadPdf(content, filename);
    };

    const formatDate = (dateStr) => {
        return new Date(dateStr).toLocaleDateString("en-US", {
            year: "numeric",
            month: "short",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit",
        });
    };

    if (selectedReport) {
        const reportContent = viewType === "initial" ? selectedReport.initial_report : selectedReport.final_report;
        return (
            <>
                <div className="flex items-center gap-3 mb-6">
                    <button
                        onClick={() => setSelectedReport(null)}
                        className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-[var(--color-text-secondary)] border border-[var(--color-border-subtle)] rounded-lg bg-transparent hover:border-[var(--color-border-hover)] hover:text-[var(--color-text-primary)] transition-all cursor-pointer"
                    >
                        ← Back to History
                    </button>
                    <h2 className="text-lg font-bold text-[var(--color-text-primary)]">
                        {selectedReport.session_name}
                    </h2>
                </div>

                <div className="flex gap-2 mb-6">
                    {selectedReport.initial_report && (
                        <button
                            onClick={() => setViewType("initial")}
                            className={`px-4 py-2 rounded-full border text-sm font-medium transition-all cursor-pointer
                ${viewType === "initial"
                                    ? "border-[var(--color-accent)] bg-[var(--color-accent-glow)] text-[var(--color-text-primary)]"
                                    : "border-[var(--color-border-subtle)] bg-[var(--color-bg-glass)] text-[var(--color-text-secondary)]"
                                } hover:border-[var(--color-border-hover)]`}
                        >
                            📋 Initial Report
                        </button>
                    )}
                    {selectedReport.final_report && (
                        <button
                            onClick={() => setViewType("final")}
                            className={`px-4 py-2 rounded-full border text-sm font-medium transition-all cursor-pointer
                ${viewType === "final"
                                    ? "border-[var(--color-accent)] bg-[var(--color-accent-glow)] text-[var(--color-text-primary)]"
                                    : "border-[var(--color-border-subtle)] bg-[var(--color-bg-glass)] text-[var(--color-text-secondary)]"
                                } hover:border-[var(--color-border-hover)]`}
                        >
                            📊 Final Report
                        </button>
                    )}
                </div>

                {reportContent ? (
                    <section className="bg-[var(--color-bg-card)] border border-[var(--color-border-subtle)] rounded-xl p-8 backdrop-blur-md animate-fade-up">
                        <ReportDisplay
                            report={reportContent}
                            title={viewType === "initial" ? "Initial Report" : "Final Report"}
                            filenamePrefix={`${viewType}_compliance_report`}
                        />
                    </section>
                ) : (
                    <div className="text-center py-12 text-[var(--color-text-muted)] text-sm">
                        No {viewType} report available for this session.
                    </div>
                )}
            </>
        );
    }

    return (
        <>
            <header className="mb-8">
                <h1 className="text-[1.85rem] font-extrabold tracking-tight bg-gradient-to-br from-[var(--color-text-primary)] to-[var(--color-accent-light)] bg-clip-text text-transparent flex items-center gap-2">
                    <span className="text-[1.6rem]">📜</span>
                    Report History
                </h1>
                <p className="text-[0.95rem] text-[var(--color-text-secondary)] mt-1">
                    View and download all your past compliance reports
                </p>
            </header>

            {error && (
                <div className="flex items-center gap-2 px-4 py-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-300 text-sm mb-6">
                    <span>❌</span> {error}
                </div>
            )}

            {loading ? (
                <div className="flex flex-col items-center gap-4 py-12 text-center">
                    <div className="w-10 h-10 border-3 border-[var(--color-border-subtle)] border-t-[var(--color-accent)] rounded-full animate-spin-slow" />
                    <p className="text-sm text-[var(--color-text-secondary)]">Loading reports…</p>
                </div>
            ) : reports.length === 0 ? (
                <div className="text-center py-16">
                    <p className="text-4xl mb-3">📭</p>
                    <p className="text-[var(--color-text-secondary)] text-sm">No reports yet. Generate your first compliance report!</p>
                </div>
            ) : (
                <div className="flex flex-col gap-3">
                    {reports.map((report) => (
                        <div
                            key={report.id}
                            className="bg-[var(--color-bg-card)] border border-[var(--color-border-subtle)] rounded-xl p-5 backdrop-blur-md hover:border-[var(--color-border-hover)] transition-all"
                        >
                            <div className="flex items-start justify-between gap-4">
                                <div className="flex-1 min-w-0">
                                    <h3
                                        className="font-semibold text-[var(--color-text-primary)] text-sm truncate cursor-pointer hover:text-[var(--color-accent-light)] transition-colors"
                                        onClick={() => { setSelectedReport(report); setViewType(report.initial_report ? "initial" : "final"); }}
                                    >
                                        📄 {report.session_name}
                                    </h3>
                                    <p className="text-xs text-[var(--color-text-muted)] mt-1">{formatDate(report.created_at)}</p>
                                    <div className="flex gap-2 mt-2">
                                        {report.initial_report && (
                                            <span className="text-xs px-2 py-0.5 rounded-full bg-blue-500/15 text-blue-300 border border-blue-500/25">
                                                Initial ✓
                                            </span>
                                        )}
                                        {report.final_report && (
                                            <span className="text-xs px-2 py-0.5 rounded-full bg-green-500/15 text-green-300 border border-green-500/25">
                                                Final ✓
                                            </span>
                                        )}
                                    </div>
                                </div>
                                <div className="flex gap-2 shrink-0">
                                    <button
                                        onClick={() => { setSelectedReport(report); setViewType(report.initial_report ? "initial" : "final"); }}
                                        className="px-3 py-1.5 text-xs font-medium text-[var(--color-text-secondary)] border border-[var(--color-border-subtle)] rounded-lg bg-transparent hover:border-[var(--color-border-hover)] hover:text-[var(--color-text-primary)] transition-all cursor-pointer"
                                    >
                                        👁️ View
                                    </button>
                                    {report.initial_report && (
                                        <button
                                            onClick={() => handleDownload(report, "initial")}
                                            className="px-3 py-1.5 text-xs font-medium text-[var(--color-accent-light)] border border-[var(--color-accent)]/30 rounded-lg bg-transparent hover:bg-[var(--color-accent-glow)] transition-all cursor-pointer"
                                            title="Download Initial Report PDF"
                                        >
                                            ⬇️ Initial
                                        </button>
                                    )}
                                    {report.final_report && (
                                        <button
                                            onClick={() => handleDownload(report, "final")}
                                            className="px-3 py-1.5 text-xs font-medium text-green-300 border border-green-500/30 rounded-lg bg-transparent hover:bg-green-500/10 transition-all cursor-pointer"
                                            title="Download Final Report PDF"
                                        >
                                            ⬇️ Final
                                        </button>
                                    )}
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </>
    );
}
