import { useState, useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import FileUpload from "../components/FileUpload";
import ReportDisplay from "../components/ReportDisplay";
import UserInputForm from "../components/UserInputForm";
import { generateInitialReport, generateFinalReport, validateInput } from "../api";
import { useAuth } from "../context/AuthContext";

const STEPS = [
    { num: 1, label: "Upload" },
    { num: 2, label: "Initial Report" },
    { num: 3, label: "Missing Data" },
    { num: 4, label: "Final Report" },
];

const DRAWING_TYPE_LABELS = {
    foundation: { emoji: "🏗️", label: "Foundation", color: "#22c55e" },
    slab: { emoji: "🧱", label: "Slab", color: "#3b82f6" },
    beam: { emoji: "📐", label: "Beam", color: "#f59e0b" },
    unknown: { emoji: "❓", label: "Unknown", color: "#6b7280" },
};

export default function DashboardPage() {
    const { token } = useAuth();
    const location = useLocation();
    const navigate = useNavigate();
    const [files, setFiles] = useState([]);
    const [initialReport, setInitialReport] = useState(null);
    const [finalReport, setFinalReport] = useState(null);
    const [userInput, setUserInput] = useState("");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [step, setStep] = useState(1);
    const [reportId, setReportId] = useState(null);
    const [drawingType, setDrawingType] = useState(null);
    const [missingFields, setMissingFields] = useState([]);
    const [missingAnswers, setMissingAnswers] = useState({});
    const [validationErrors, setValidationErrors] = useState([]);
    const [validating, setValidating] = useState(false);

    // Resume from history: pre-fill state if navigated with resumeReport
    useEffect(() => {
        const resumeData = location.state?.resumeReport;
        if (resumeData) {
            setInitialReport(resumeData.initial_report);
            setReportId(resumeData.id);
            setDrawingType(resumeData.drawing_type || "unknown");

            // Re-extract missing fields from the initial report
            const fields = extractMissingFieldsClient(resumeData.initial_report);
            setMissingFields(fields);
            const answers = {};
            fields.forEach((f) => { answers[f] = ""; });
            setMissingAnswers(answers);
            setStep(3);

            // Clear the navigation state so refresh doesn't re-trigger
            navigate(location.pathname, { replace: true, state: {} });
        }
    }, []);

    // Client-side missing field extractor (mirrors backend logic)
    function extractMissingFieldsClient(report) {
        if (!report) return [];
        const lines = report.split("\n");
        const missing = [];
        let inSection = false;
        for (const line of lines) {
            const stripped = line.trim();
            if (/missing.*(?:wrong|information)/i.test(stripped)) {
                inSection = true;
                continue;
            }
            if (inSection && stripped.startsWith("#")) break;
            if (!inSection || !stripped || stripped.startsWith("|") || /^---+$|^===+$|^\*\*\*+$/.test(stripped)) continue;
            let clean = stripped.replace(/^\d+\.\s*|^[-*+]\s*/, "").trim();
            if (clean && !["none", "n/a", "nil"].includes(clean.toLowerCase())) {
                if (clean.includes(":")) clean = clean.split(":")[0].trim();
                missing.push(clean);
            }
        }
        return missing;
    }

    const handleGenerateInitial = async () => {
        if (files.length === 0) return setError("Please upload at least one file.");
        setLoading(true);
        setError(null);
        try {
            const data = await generateInitialReport(files, token);
            setInitialReport(data.report);
            setReportId(data.report_id);
            setDrawingType(data.drawing_type || "unknown");
            setMissingFields(data.missing_fields || []);
            // Pre-fill answer slots
            const answers = {};
            (data.missing_fields || []).forEach((f) => { answers[f] = ""; });
            setMissingAnswers(answers);
            setStep(2);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const handleValidateAndProceed = async () => {
        // If there are no missing fields, go straight to final
        if (missingFields.length === 0) {
            handleGenerateFinal();
            return;
        }
        setValidating(true);
        setError(null);
        setValidationErrors([]);
        try {
            const result = await validateInput(missingFields, missingAnswers, token);
            if (result.valid) {
                // Build user input string from the answers
                const inputText = Object.entries(missingAnswers)
                    .filter(([, v]) => v.trim())
                    .map(([k, v]) => `${k}: ${v}`)
                    .join("\n");
                setUserInput(inputText);
                handleGenerateFinal(inputText);
            } else {
                setValidationErrors(result.invalid_fields || []);
                setError("Some answers are invalid. Please correct them and try again.");
            }
        } catch (err) {
            setError(err.message);
        } finally {
            setValidating(false);
        }
    };

    const handleGenerateFinal = async (overrideInput) => {
        const input = overrideInput || userInput;
        if (!input.trim())
            return setError("Please provide additional information before generating the final report.");
        setLoading(true);
        setError(null);
        try {
            const data = await generateFinalReport(initialReport, input, drawingType, reportId, token);
            setFinalReport(data.report);
            setStep(4);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const handleReset = () => {
        setFiles([]);
        setInitialReport(null);
        setFinalReport(null);
        setUserInput("");
        setError(null);
        setStep(1);
        setReportId(null);
        setDrawingType(null);
        setMissingFields([]);
        setMissingAnswers({});
        setValidationErrors([]);
    };

    const canNavigate = (num) => {
        if (num === 1) return true;
        if (num === 2 && initialReport) return true;
        if (num === 3 && initialReport) return true;
        if (num === 4 && finalReport) return true;
        return false;
    };

    const dtInfo = DRAWING_TYPE_LABELS[drawingType] || DRAWING_TYPE_LABELS.unknown;

    return (
        <>
            {/* Header */}
            <header className="mb-8">
                <h1 className="text-[1.85rem] font-extrabold tracking-tight bg-gradient-to-br from-[var(--color-text-primary)] to-[var(--color-accent-light)] bg-clip-text text-transparent flex items-center gap-2">
                    <span className="text-[1.6rem]">🧑‍🔬</span>
                    RCC Structural Compliance Check
                </h1>
                <p className="text-[0.95rem] text-[var(--color-text-secondary)] mt-1">
                    Analyze structural drawings (Foundations, Slabs, Beams) for compliance with IS 456:2000 and SP 34
                </p>
            </header>

            {/* Stepper */}
            <div className="flex gap-2 mb-8 flex-wrap">
                {STEPS.map(({ num, label }) => (
                    <button
                        key={num}
                        onClick={() => canNavigate(num) && setStep(num)}
                        className={`flex items-center gap-2 px-4 py-2 rounded-full border transition-all cursor-pointer select-none text-sm
              ${step >= num
                                ? "border-[var(--color-accent)] bg-[var(--color-accent-glow)]"
                                : "border-[var(--color-border-subtle)] bg-[var(--color-bg-glass)]"
                            }
              ${step === num ? "shadow-[0_0_16px_var(--color-accent-glow)]" : ""}
              hover:border-[var(--color-border-hover)]`}
                    >
                        <span
                            className={`w-6 h-6 rounded-full grid place-items-center text-xs font-bold transition-all
                ${step >= num ? "bg-[var(--color-accent)] text-white" : "bg-[var(--color-bg-secondary)] text-[var(--color-text-muted)]"}`}
                        >
                            {num}
                        </span>
                        <span className={`font-medium ${step >= num ? "text-[var(--color-text-primary)]" : "text-[var(--color-text-secondary)]"}`}>
                            {label}
                        </span>
                    </button>
                ))}
            </div>

            {/* Error */}
            {error && (
                <div className="flex items-center gap-2 px-4 py-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-300 text-sm mb-6 animate-fade-up">
                    <span>❌</span> {error}
                    <button onClick={() => setError(null)} className="ml-auto bg-transparent border-none text-red-300 cursor-pointer text-base px-1">✕</button>
                </div>
            )}

            {/* Loading */}
            {loading && (
                <div className="flex flex-col items-center gap-4 py-12 text-center">
                    <div className="w-10 h-10 border-3 border-[var(--color-border-subtle)] border-t-[var(--color-accent)] rounded-full animate-spin-slow" />
                    <p className="text-sm text-[var(--color-text-secondary)]">Analyzing… This may take a minute.</p>
                </div>
            )}

            {/* Step 1 */}
            {step === 1 && (
                <section className="bg-[var(--color-bg-card)] border border-[var(--color-border-subtle)] rounded-xl p-8 backdrop-blur-md animate-fade-up">
                    <h2 className="text-lg font-bold mb-5">📄 Step 1 — Upload PDF or Image</h2>
                    <FileUpload files={files} setFiles={setFiles} />
                    <button
                        onClick={handleGenerateInitial}
                        disabled={loading || files.length === 0}
                        className="mt-5 inline-flex items-center gap-1.5 px-6 py-2.5 font-semibold text-sm text-white rounded-lg bg-gradient-to-br from-[var(--color-accent)] to-purple-600 shadow-[0_4px_14px_var(--color-accent-glow)] hover:shadow-[0_6px_22px_var(--color-accent-glow)] hover:-translate-y-0.5 transition-all disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                    >
                        {loading ? "Analyzing…" : "🔍 Generate Initial Report"}
                    </button>
                </section>
            )}

            {/* Step 2 */}
            {step === 2 && initialReport && (
                <section className="bg-[var(--color-bg-card)] border border-[var(--color-border-subtle)] rounded-xl p-8 backdrop-blur-md animate-fade-up">
                    <div className="flex items-center gap-3 mb-5">
                        <h2 className="text-lg font-bold">📋 Step 2 — Initial Compliance Report</h2>
                        {drawingType && (
                            <span
                                className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider"
                                style={{
                                    background: `${dtInfo.color}20`,
                                    border: `1px solid ${dtInfo.color}60`,
                                    color: dtInfo.color,
                                }}
                            >
                                {dtInfo.emoji} {dtInfo.label}
                            </span>
                        )}
                    </div>
                    <ReportDisplay report={initialReport} title="Initial Report" filenamePrefix="initial_compliance_report" />
                    <button
                        onClick={() => setStep(3)}
                        className="mt-5 inline-flex items-center gap-1.5 px-6 py-2.5 font-semibold text-sm text-white rounded-lg bg-gradient-to-br from-[var(--color-accent)] to-purple-600 shadow-[0_4px_14px_var(--color-accent-glow)] hover:shadow-[0_6px_22px_var(--color-accent-glow)] hover:-translate-y-0.5 transition-all cursor-pointer"
                    >
                        ✏️ Provide Missing Data →
                    </button>
                </section>
            )}

            {/* Step 3 — Missing Data & Validation */}
            {step === 3 && (
                <section className="bg-[var(--color-bg-card)] border border-[var(--color-border-subtle)] rounded-xl p-8 backdrop-blur-md animate-fade-up">
                    <h2 className="text-lg font-bold mb-5">✏️ Step 3 — Provide Missing Information</h2>

                    {missingFields.length > 0 ? (
                        <>
                            <p className="text-sm text-[var(--color-text-secondary)] mb-4">
                                The following fields are missing or need correction. Please fill them in:
                            </p>
                            <div className="space-y-4">
                                {missingFields.map((field) => {
                                    const fieldError = validationErrors.find((e) => e.field === field);
                                    return (
                                        <div key={field}>
                                            <label className="block text-sm font-medium text-[var(--color-text-primary)] mb-1">
                                                {field}
                                            </label>
                                            <input
                                                type="text"
                                                value={missingAnswers[field] || ""}
                                                onChange={(e) =>
                                                    setMissingAnswers((prev) => ({
                                                        ...prev,
                                                        [field]: e.target.value,
                                                    }))
                                                }
                                                placeholder={`Enter ${field}`}
                                                className={`w-full px-4 py-2.5 text-sm text-[var(--color-text-primary)] bg-[var(--color-bg-glass)] border rounded-lg focus:outline-none focus:shadow-[0_0_0_3px_var(--color-accent-glow)] transition-all font-[inherit] ${
                                                    fieldError
                                                        ? "border-red-500 focus:border-red-500"
                                                        : "border-[var(--color-border-subtle)] focus:border-[var(--color-accent)]"
                                                }`}
                                            />
                                            {fieldError && (
                                                <p className="text-xs text-red-400 mt-1">
                                                    ⚠️ {fieldError.reason}
                                                    {fieldError.expected && (
                                                        <span className="text-[var(--color-text-muted)]"> — Expected: {fieldError.expected}</span>
                                                    )}
                                                </p>
                                            )}
                                        </div>
                                    );
                                })}
                            </div>
                        </>
                    ) : (
                        <>
                            <p className="text-sm text-[var(--color-text-secondary)] mb-3">
                                No missing fields detected. You can provide any additional corrections or notes below:
                            </p>
                            <UserInputForm userInput={userInput} setUserInput={setUserInput} />
                        </>
                    )}

                    <button
                        onClick={missingFields.length > 0 ? handleValidateAndProceed : () => handleGenerateFinal()}
                        disabled={loading || validating}
                        className="mt-5 inline-flex items-center gap-1.5 px-6 py-2.5 font-semibold text-sm text-white rounded-lg bg-gradient-to-br from-[var(--color-accent)] to-purple-600 shadow-[0_4px_14px_var(--color-accent-glow)] hover:shadow-[0_6px_22px_var(--color-accent-glow)] hover:-translate-y-0.5 transition-all disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                    >
                        {validating ? "Validating…" : loading ? "Generating…" : "🚀 Validate & Generate Final Report"}
                    </button>
                </section>
            )}

            {/* Step 4 */}
            {step === 4 && finalReport && (
                <section className="bg-[var(--color-bg-card)] border border-[var(--color-border-subtle)] rounded-xl p-8 backdrop-blur-md animate-fade-up">
                    <div className="flex items-center gap-3 mb-5">
                        <h2 className="text-lg font-bold">📊 Step 4 — Final Compliance Report</h2>
                        {drawingType && (
                            <span
                                className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider"
                                style={{
                                    background: `${dtInfo.color}20`,
                                    border: `1px solid ${dtInfo.color}60`,
                                    color: dtInfo.color,
                                }}
                            >
                                {dtInfo.emoji} {dtInfo.label}
                            </span>
                        )}
                    </div>
                    <ReportDisplay report={finalReport} title="Final Report" filenamePrefix="final_compliance_report" />
                </section>
            )}

            {/* Reset */}
            {(initialReport || finalReport) && (
                <button
                    onClick={handleReset}
                    className="mt-8 inline-flex items-center gap-1.5 px-5 py-2 text-sm font-medium text-[var(--color-text-secondary)] border border-[var(--color-border-subtle)] rounded-lg bg-transparent hover:border-[var(--color-border-hover)] hover:text-[var(--color-text-primary)] transition-all cursor-pointer"
                >
                    🔄 Start New Analysis
                </button>
            )}
        </>
    );
}
