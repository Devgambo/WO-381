import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import FileUpload from "../components/FileUpload";
import ReportDisplay from "../components/ReportDisplay";
import UserInputForm from "../components/UserInputForm";
import {
    fetchReportMissingFields,
    generateFinalReport,
    generateInitialReport,
    pollJob,
    validateInput,
} from "../api";
import { useAuth } from "../context/AuthContext";

const STEPS = [
    { num: 1, label: "Upload", aux: "Drawing intake" },
    { num: 2, label: "Extract", aux: "Vision agent" },
    { num: 3, label: "Resolve", aux: "Missing fields" },
    { num: 4, label: "Verdict", aux: "RAG report" },
];

const DRAWING_TYPE_LABELS = {
    foundation: { code: "FDN", label: "Foundation", color: "#10b981" },
    slab: { code: "SLB", label: "Slab", color: "#38bdf8" },
    beam: { code: "BMS", label: "Beam", color: "#f59e0b" },
    column: { code: "COL", label: "Column", color: "#a855f7" },
    unknown: { code: "???", label: "Unknown", color: "#6b7280" },
};

const ASSUME_RE = /\b(assume|assume yourself|use standard|use default|use typical|any value|as per IS code|standard value|you decide|pick one|common value)\b/i;

const DRAFT_KEY_PREFIX = "compliance-draft:";

function loadDraft(key) {
    if (!key) return null;
    try {
        const raw = sessionStorage.getItem(DRAFT_KEY_PREFIX + key);
        return raw ? JSON.parse(raw) : null;
    } catch {
        return null;
    }
}

function saveDraft(key, value) {
    if (!key) return;
    try {
        sessionStorage.setItem(DRAFT_KEY_PREFIX + key, JSON.stringify(value));
    } catch {
        /* quota — ignore */
    }
}

function clearDraft(key) {
    if (!key) return;
    try { sessionStorage.removeItem(DRAFT_KEY_PREFIX + key); } catch { /* ignore */ }
}

const fileKey = (f) => `${f.name}|${f.size}|${f.lastModified}`;

function DrawingTypeBadge({ type }) {
    const info = DRAWING_TYPE_LABELS[type] || DRAWING_TYPE_LABELS.unknown;
    return (
        <span
            className="inline-flex items-center gap-2 px-2.5 py-1 border mono text-[10px] uppercase tracking-wider"
            style={{
                borderColor: `${info.color}66`,
                color: info.color,
                background: `${info.color}12`,
            }}
        >
            <span className="font-semibold">{info.code}</span>
            <span className="text-[var(--color-text-secondary)]">{info.label}</span>
        </span>
    );
}

function StepIndicator({ step, canNavigate, onJump }) {
    return (
        <div className="grid grid-cols-4 border border-[var(--color-border-subtle)] mb-8">
            {STEPS.map(({ num, label, aux }) => {
                const active = step === num;
                const reached = step >= num;
                const clickable = canNavigate(num);
                return (
                    <button
                        key={num}
                        onClick={() => clickable && onJump(num)}
                        disabled={!clickable}
                        className={`text-left p-4 border-r last:border-r-0 border-[var(--color-border-subtle)] transition-colors
                            ${active
                                ? "bg-[var(--color-bg-glass)]"
                                : "hover:bg-[var(--color-bg-glass)]"
                            }
                            ${clickable ? "cursor-pointer" : "cursor-not-allowed opacity-50"}`}
                    >
                        <div className="flex items-center gap-3">
                            <span
                                className={`w-7 h-7 grid place-items-center mono text-xs border
                                    ${reached
                                        ? "border-[var(--color-accent)] text-[var(--color-accent-light)] bg-[var(--color-accent-glow)]"
                                        : "border-[var(--color-border-medium)] text-[var(--color-text-muted)]"
                                    }`}
                            >
                                {String(num).padStart(2, "0")}
                            </span>
                            <div>
                                <p className={`text-sm font-medium ${reached ? "text-[var(--color-text-primary)]" : "text-[var(--color-text-muted)]"}`}>
                                    {label}
                                </p>
                                <p className="label-mono mt-0.5">{aux}</p>
                            </div>
                        </div>
                        <div className={`h-0.5 mt-3 ${reached ? "bg-[var(--color-accent)]" : "bg-[var(--color-border-subtle)]"}`} />
                    </button>
                );
            })}
        </div>
    );
}

function SeverityChip({ severity }) {
    if (!severity || severity === "UNKNOWN") return null;
    const colors = {
        ACCEPTABLE: { fg: "var(--color-success)", label: "Acceptable" },
        REQUIRES_REVISION: { fg: "var(--color-warning)", label: "Revisions required" },
        REJECTED: { fg: "var(--color-danger)", label: "Rejected" },
    };
    const c = colors[severity] || { fg: "var(--color-text-muted)", label: severity };
    return (
        <span
            className="inline-flex items-center gap-2 px-2.5 py-1 border mono text-[10px] uppercase tracking-wider"
            style={{ borderColor: c.fg, color: c.fg, background: "transparent" }}
        >
            <span className="w-1.5 h-1.5" style={{ background: c.fg }} />
            <span>{c.label}</span>
        </span>
    );
}

export default function DashboardPage() {
    const { token } = useAuth();
    const location = useLocation();
    const navigate = useNavigate();
    const [files, setFilesRaw] = useState([]);
    const [initialReport, setInitialReport] = useState(null);
    const [finalReport, setFinalReport] = useState(null);
    const [userInput, setUserInput] = useState("");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [warning, setWarning] = useState(null);
    const [step, setStep] = useState(1);
    const [reportId, setReportId] = useState(null);
    const [drawingType, setDrawingType] = useState(null);
    const [missingFields, setMissingFields] = useState([]);
    const [missingAnswers, setMissingAnswers] = useState({});
    const [validationErrors, setValidationErrors] = useState([]);
    const [validating, setValidating] = useState(false);
    const [reportTimestamp, setReportTimestamp] = useState(null);
    const [quality, setQuality] = useState(null);
    const [jobProgress, setJobProgress] = useState(null); // { percent, stage }

    const inFlightRef = useRef(false);
    const lastResumeKeyRef = useRef(null);

    const setFiles = (updater) => {
        setFilesRaw((prev) => {
            const next = typeof updater === "function" ? updater(prev) : updater;
            const seen = new Set();
            const deduped = [];
            for (const f of next) {
                const k = fileKey(f);
                if (seen.has(k)) continue;
                seen.add(k);
                deduped.push(f);
            }
            return deduped;
        });
    };

    useEffect(() => {
        const resumeData = location.state?.resumeReport;
        if (!resumeData) return;
        if (lastResumeKeyRef.current === location.key) return;
        lastResumeKeyRef.current = location.key;

        setInitialReport(resumeData.initial_report);
        setReportId(resumeData.id);
        setDrawingType(resumeData.drawing_type || "unknown");
        setStep(3);

        (async () => {
            try {
                const { missing_fields } = await fetchReportMissingFields(resumeData.id, token);
                setMissingFields(missing_fields || []);
                const draft = loadDraft(resumeData.id);
                const answers = {};
                (missing_fields || []).forEach((f) => { answers[f] = draft?.missingAnswers?.[f] || ""; });
                setMissingAnswers(answers);
                if (draft?.userInput) setUserInput(draft.userInput);
            } catch (err) {
                setError(err.message);
            }
        })();

        navigate(location.pathname, { replace: true, state: {} });
    }, [location.key, location.pathname, location.state, navigate, token]);

    useEffect(() => {
        if (!reportId) return;
        if (step < 3) return;
        saveDraft(reportId, {
            userInput,
            missingAnswers,
            drawingType,
            step,
            savedAt: Date.now(),
        });
    }, [reportId, step, userInput, missingAnswers, drawingType]);

    const handleGenerateInitial = async () => {
        if (files.length === 0) {
            setError("Add at least one file.");
            return;
        }
        if (inFlightRef.current) return;
        inFlightRef.current = true;
        setLoading(true);
        setError(null);
        setWarning(null);
        setJobProgress({ percent: 0, stage: "queued" });
        try {
            const { job_id } = await generateInitialReport(files, token);
            const data = await pollJob(job_id, token, (job) =>
                setJobProgress({ percent: job.progress || 0, stage: job.stage || job.status })
            );
            setInitialReport(data.report);
            setReportId(data.report_id);
            setDrawingType(data.drawing_type || "unknown");
            setMissingFields(data.missing_fields || []);
            setReportTimestamp(Date.now());
            setQuality(data.quality_assessment || null);
            const answers = {};
            (data.missing_fields || []).forEach((f) => { answers[f] = ""; });
            setMissingAnswers(answers);
            setStep(2);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
            setJobProgress(null);
            inFlightRef.current = false;
        }
    };

    const handleValidateAndProceed = async (e) => {
        if (e && e.preventDefault) e.preventDefault();
        if (missingFields.length === 0) {
            handleGenerateFinal();
            return;
        }
        if (inFlightRef.current) return;
        inFlightRef.current = true;
        setValidating(true);
        setError(null);
        setWarning(null);
        setValidationErrors([]);
        try {
            const result = await validateInput(missingFields, missingAnswers, token);
            if (result.valid) {
                const assumed = result.assumed_values || {};
                const inputText = Object.entries(missingAnswers)
                    .filter(([, v]) => v.trim())
                    .map(([k, v]) => {
                        const isAssume = ASSUME_RE.test(v);
                        return isAssume && assumed[k]
                            ? `${k}: ${assumed[k]}`
                            : `${k}: ${v}`;
                    })
                    .join("\n");
                setUserInput(inputText);
                inFlightRef.current = false;
                await handleGenerateFinal(inputText, assumed);
            } else {
                setValidationErrors(result.invalid_fields || []);
                setError("Some answers need correction.");
                inFlightRef.current = false;
            }
        } catch (err) {
            setError(err.message);
            inFlightRef.current = false;
        } finally {
            setValidating(false);
        }
    };

    const handleGenerateFinal = async (overrideInput, overrideAssumed = {}) => {
        const input = overrideInput || userInput;
        if (!input.trim()) {
            setError("Provide notes or assumed values before generating the final report.");
            return;
        }
        if (inFlightRef.current) return;
        inFlightRef.current = true;
        setLoading(true);
        setError(null);
        setWarning(null);
        setJobProgress({ percent: 0, stage: "queued" });
        try {
            const { job_id } = await generateFinalReport(initialReport, input, drawingType, reportId, token, overrideAssumed);
            const data = await pollJob(job_id, token, (job) =>
                setJobProgress({ percent: job.progress || 0, stage: job.stage || job.status })
            );
            setFinalReport(data.report);
            setStep(4);
            if (data.rag_context_used === false) {
                setWarning("Final report generated without IS-code context — verdicts may be incomplete.");
            } else if (data.rag_confidence_low) {
                setWarning("RAG retrieval was low-confidence — verdict may be incomplete.");
            }
            clearDraft(reportId);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
            setJobProgress(null);
            inFlightRef.current = false;
        }
    };

    const handleReset = () => {
        if (reportId) clearDraft(reportId);
        setFilesRaw([]);
        setInitialReport(null);
        setFinalReport(null);
        setUserInput("");
        setError(null);
        setWarning(null);
        setStep(1);
        setReportId(null);
        setDrawingType(null);
        setMissingFields([]);
        setMissingAnswers({});
        setValidationErrors([]);
        setReportTimestamp(null);
        setQuality(null);
        setJobProgress(null);
        inFlightRef.current = false;
    };

    const canNavigate = (num) => {
        if (num === 1) return true;
        if (num === 2 && initialReport) return true;
        if (num === 3 && initialReport) return true;
        if (num === 4 && finalReport) return true;
        return false;
    };

    const missingPending = Object.entries(missingAnswers).filter(([, v]) => !v.trim()).length;

    return (
        <>
            {/* Header */}
            <header className="mb-8 pb-6 border-b border-[var(--color-border-subtle)]">
                <div className="flex items-baseline gap-3 mb-2">
                    <span className="label-mono">/dashboard</span>
                    <span className="label-mono text-[var(--color-text-faint)]">·</span>
                    <span className="label-mono">analysis</span>
                </div>
                <div className="flex items-end justify-between gap-4 flex-wrap">
                    <div>
                        <h1 className="text-2xl font-semibold tracking-tight text-[var(--color-text-primary)]">
                            New compliance analysis
                        </h1>
                        <p className="text-sm text-[var(--color-text-secondary)] mt-1 max-w-2xl">
                            Foundation · slab · beam · column. Audited against IS 456:2000 and SP 34
                            with multi-agent vision + RAG retrieval.
                        </p>
                    </div>
                    <div className="flex items-center gap-2 flex-wrap">
                        {drawingType && <DrawingTypeBadge type={drawingType} />}
                        {quality && <SeverityChip severity={quality.severity} />}
                        {reportId && (
                            <span className="mono text-[10px] tracking-wider text-[var(--color-text-muted)] border border-[var(--color-border-subtle)] px-2 py-1">
                                ID · {reportId.slice(0, 8)}
                            </span>
                        )}
                    </div>
                </div>
            </header>

            <StepIndicator step={step} canNavigate={canNavigate} onJump={setStep} />

            {error && (
                <div className="flex items-start gap-3 px-4 py-3 border border-[rgba(239,68,68,0.4)] bg-[rgba(239,68,68,0.06)] text-[var(--color-danger)] text-xs mb-6 animate-fade-up">
                    <span className="mono pt-0.5">ERR</span>
                    <span className="flex-1">{error}</span>
                    <button onClick={() => setError(null)} className="bg-transparent border-none text-[var(--color-danger)] cursor-pointer mono text-xs">×</button>
                </div>
            )}

            {warning && (
                <div className="flex items-start gap-3 px-4 py-3 border border-[rgba(245,158,11,0.4)] bg-[rgba(245,158,11,0.06)] text-[var(--color-warning)] text-xs mb-6 animate-fade-up">
                    <span className="mono pt-0.5">WRN</span>
                    <span className="flex-1">{warning}</span>
                    <button onClick={() => setWarning(null)} className="bg-transparent border-none text-[var(--color-warning)] cursor-pointer mono text-xs">×</button>
                </div>
            )}

            {loading && (
                <div className="border border-[var(--color-border-subtle)] bg-[var(--color-bg-card)] p-8 mb-6 flex flex-col items-center gap-4 text-center">
                    <div className="w-10 h-10 border-2 border-[var(--color-border-medium)] border-t-[var(--color-accent)] rounded-full animate-spin-slow" />
                    <div>
                        <p className="text-sm font-medium text-[var(--color-text-primary)]">
                            {jobProgress?.stage
                                ? jobProgress.stage.charAt(0).toUpperCase() + jobProgress.stage.slice(1)
                                : "Working…"}
                        </p>
                        <p className="label-mono mt-1">
                            Background job · vision + reasoning model · this may take a minute
                        </p>
                    </div>
                    {jobProgress ? (
                        <div className="w-full max-w-xs">
                            <div className="h-1.5 bg-[var(--color-border-subtle)] overflow-hidden">
                                <div
                                    className="h-full bg-[var(--color-accent)] transition-all duration-500 ease-out"
                                    style={{ width: `${Math.max(jobProgress.percent, 4)}%` }}
                                />
                            </div>
                            <p className="label-mono mt-2 text-right">{jobProgress.percent || 0}%</p>
                        </div>
                    ) : (
                        <div className="w-full max-w-xs h-1 progress-stripe" />
                    )}
                </div>
            )}

            {step === 1 && (
                <section className="panel p-6 animate-fade-up">
                    <SectionHeader index="01" title="Drawing intake" hint="Upload one or more sheets" />
                    <FileUpload files={files} setFiles={setFiles} />
                    <div className="mt-6 flex items-center justify-between flex-wrap gap-3">
                        <span className="label-mono">
                            {files.length === 0 ? "Awaiting upload" : `${files.length} file${files.length > 1 ? "s" : ""} ready`}
                        </span>
                        <button
                            onClick={handleGenerateInitial}
                            disabled={loading || files.length === 0}
                            className="btn-primary px-5 py-2.5 text-sm cursor-pointer disabled:cursor-not-allowed inline-flex items-center gap-2"
                        >
                            <span>{loading ? "Analysing…" : "Run extraction"}</span>
                            <span className="mono">→</span>
                        </button>
                    </div>
                </section>
            )}

            {step === 2 && initialReport && (
                <section className="panel p-6 animate-fade-up">
                    <SectionHeader index="02" title="Initial extraction" hint="Phase 1–4 transcription" />
                    <ReportDisplay
                        report={initialReport}
                        title="Phase 1 → Phase 4 report"
                        filenamePrefix={`${drawingType || "unknown"}_init_${reportTimestamp || ""}`}
                        onError={(msg) => setError(msg)}
                    />
                    <div className="mt-6 flex items-center justify-between flex-wrap gap-3 pt-4 border-t border-[var(--color-border-subtle)]">
                        <div className="flex items-center gap-3">
                            <span className="label-mono">Missing fields detected</span>
                            <span className="mono text-base font-semibold text-[var(--color-accent-light)]">
                                {String(missingFields.length).padStart(2, "0")}
                            </span>
                        </div>
                        <button
                            onClick={() => setStep(3)}
                            className="btn-primary px-5 py-2.5 text-sm cursor-pointer inline-flex items-center gap-2"
                        >
                            <span>Resolve gaps</span>
                            <span className="mono">→</span>
                        </button>
                    </div>
                </section>
            )}

            {step === 3 && (
                <section className="panel p-6 animate-fade-up">
                    <SectionHeader
                        index="03"
                        title="Resolve missing data"
                        hint={missingFields.length > 0 ? `${missingPending} of ${missingFields.length} pending` : "Free-form notes"}
                    />

                    {missingFields.length > 0 ? (
                        <form onSubmit={handleValidateAndProceed}>
                            <p className="text-xs text-[var(--color-text-secondary)] mb-5 leading-relaxed">
                                Type <span className="mono text-[var(--color-accent-light)]">assume</span> to let
                                the validator supply IS-code defaults.
                            </p>
                            <div className="border border-[var(--color-border-subtle)] divide-y divide-[var(--color-border-subtle)]">
                                {missingFields.map((field, idx) => {
                                    const fieldError = validationErrors.find((e) => e.field === field);
                                    const inputId = `missing-field-${idx}`;
                                    const filled = (missingAnswers[field] || "").trim().length > 0;
                                    return (
                                        <div key={`${field}-${idx}`} className="grid grid-cols-[36px_1fr] gap-0 p-4">
                                            <span className={`mono text-[10px] tracking-wider pt-2 ${filled ? "text-[var(--color-accent-light)]" : "text-[var(--color-text-muted)]"}`}>
                                                {String(idx + 1).padStart(2, "0")}
                                            </span>
                                            <div>
                                                <label htmlFor={inputId} className="block text-sm font-medium text-[var(--color-text-primary)] mb-1.5">
                                                    {field}
                                                </label>
                                                <input
                                                    id={inputId}
                                                    type="text"
                                                    value={missingAnswers[field] || ""}
                                                    onChange={(e) =>
                                                        setMissingAnswers((prev) => ({
                                                            ...prev,
                                                            [field]: e.target.value,
                                                        }))
                                                    }
                                                    placeholder={`Enter ${field.toLowerCase()}`}
                                                    className={`input-base w-full px-3 py-2 text-sm placeholder:text-[var(--color-text-faint)]
                                                        ${fieldError ? "border-[var(--color-danger)] focus:border-[var(--color-danger)]" : ""}`}
                                                />
                                                {fieldError && (
                                                    <p className="text-xs text-[var(--color-danger)] mt-1.5 mono">
                                                        <span className="opacity-60">! </span>
                                                        {fieldError.reason}
                                                        {fieldError.expected && (
                                                            <span className="text-[var(--color-text-muted)]"> · expected: {fieldError.expected}</span>
                                                        )}
                                                    </p>
                                                )}
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                            <div className="mt-6 flex items-center justify-between flex-wrap gap-3">
                                <span className="label-mono">
                                    {missingPending === 0 ? "All fields answered" : `${missingPending} remaining`}
                                </span>
                                <button
                                    type="submit"
                                    disabled={loading || validating}
                                    className="btn-primary px-5 py-2.5 text-sm cursor-pointer disabled:cursor-not-allowed inline-flex items-center gap-2"
                                >
                                    <span>{validating ? "Validating…" : loading ? "Generating…" : "Validate & generate"}</span>
                                    <span className="mono">→</span>
                                </button>
                            </div>
                        </form>
                    ) : (
                        <>
                            <p className="text-xs text-[var(--color-text-secondary)] mb-4">
                                No missing fields detected. Add any clarifications below.
                            </p>
                            <UserInputForm userInput={userInput} setUserInput={setUserInput} />
                            <div className="mt-6 flex items-center justify-end">
                                <button
                                    onClick={() => handleGenerateFinal()}
                                    disabled={loading || validating}
                                    className="btn-primary px-5 py-2.5 text-sm cursor-pointer disabled:cursor-not-allowed inline-flex items-center gap-2"
                                >
                                    <span>{loading ? "Generating…" : "Generate final report"}</span>
                                    <span className="mono">→</span>
                                </button>
                            </div>
                        </>
                    )}
                </section>
            )}

            {step === 4 && finalReport && (
                <section className="panel p-6 animate-fade-up">
                    <SectionHeader index="04" title="Final compliance verdict" hint="RAG-backed citation report" />
                    <ReportDisplay
                        report={finalReport}
                        title="Compliance verdict"
                        filenamePrefix={`${drawingType || "unknown"}_final_${reportTimestamp || ""}`}
                        onError={(msg) => setError(msg)}
                    />
                </section>
            )}

            {(initialReport || finalReport) && (
                <div className="mt-8 flex items-center gap-3">
                    <button
                        onClick={handleReset}
                        className="btn-secondary px-4 py-2 text-xs cursor-pointer mono uppercase tracking-wider"
                    >
                        Start new analysis
                    </button>
                </div>
            )}
        </>
    );
}

function SectionHeader({ index, title, hint }) {
    return (
        <div className="mb-6 pb-4 border-b border-[var(--color-border-subtle)]">
            <div className="flex items-baseline justify-between gap-4 flex-wrap">
                <div className="flex items-baseline gap-3">
                    <span className="mono text-[10px] tracking-[0.18em] uppercase text-[var(--color-accent)]">
                        STEP / {index}
                    </span>
                    <h2 className="text-base font-semibold tracking-tight text-[var(--color-text-primary)]">
                        {title}
                    </h2>
                </div>
                {hint && <span className="label-mono">{hint}</span>}
            </div>
        </div>
    );
}
