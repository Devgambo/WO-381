import { useState } from "react";
import FileUpload from "../components/FileUpload";
import ReportDisplay from "../components/ReportDisplay";
import UserInputForm from "../components/UserInputForm";
import { generateInitialReport, generateFinalReport } from "../api";
import { useAuth } from "../context/AuthContext";

const STEPS = [
    { num: 1, label: "Upload" },
    { num: 2, label: "Initial Report" },
    { num: 3, label: "User Input" },
    { num: 4, label: "Final Report" },
];

export default function DashboardPage() {
    const { token } = useAuth();
    const [files, setFiles] = useState([]);
    const [initialReport, setInitialReport] = useState(null);
    const [finalReport, setFinalReport] = useState(null);
    const [userInput, setUserInput] = useState("");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [step, setStep] = useState(1);
    const [reportId, setReportId] = useState(null);

    const handleGenerateInitial = async () => {
        if (files.length === 0) return setError("Please upload at least one file.");
        setLoading(true);
        setError(null);
        try {
            const data = await generateInitialReport(files, token);
            setInitialReport(data.report);
            setReportId(data.report_id);
            setStep(2);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const handleGenerateFinal = async () => {
        if (!userInput.trim())
            return setError("Please provide additional information before generating the final report.");
        setLoading(true);
        setError(null);
        try {
            const data = await generateFinalReport(initialReport, userInput, reportId, token);
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
    };

    const canNavigate = (num) => {
        if (num === 1) return true;
        if (num === 2 && initialReport) return true;
        if (num === 3 && initialReport) return true;
        if (num === 4 && finalReport) return true;
        return false;
    };

    return (
        <>
            {/* Header */}
            <header className="mb-8">
                <h1 className="text-[1.85rem] font-extrabold tracking-tight bg-gradient-to-br from-[var(--color-text-primary)] to-[var(--color-accent-light)] bg-clip-text text-transparent flex items-center gap-2">
                    <span className="text-[1.6rem]">🧑‍🔬</span>
                    Foundation Compliance Check using AI
                </h1>
                <p className="text-[0.95rem] text-[var(--color-text-secondary)] mt-1">
                    Analyze structural drawings for compliance with IS 456:2000 and SP 34
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
                    <h2 className="text-lg font-bold mb-5">📋 Step 2 — Initial Compliance Report</h2>
                    <ReportDisplay report={initialReport} title="Initial Report" filenamePrefix="initial_compliance_report" />
                    <button
                        onClick={() => setStep(3)}
                        className="mt-5 inline-flex items-center gap-1.5 px-6 py-2.5 font-semibold text-sm text-white rounded-lg bg-gradient-to-br from-[var(--color-accent)] to-purple-600 shadow-[0_4px_14px_var(--color-accent-glow)] hover:shadow-[0_6px_22px_var(--color-accent-glow)] hover:-translate-y-0.5 transition-all cursor-pointer"
                    >
                        ✏️ Provide Additional Information →
                    </button>
                </section>
            )}

            {/* Step 3 */}
            {step === 3 && (
                <section className="bg-[var(--color-bg-card)] border border-[var(--color-border-subtle)] rounded-xl p-8 backdrop-blur-md animate-fade-up">
                    <h2 className="text-lg font-bold mb-5">✏️ Step 3 — Provide Additional Information</h2>
                    <UserInputForm userInput={userInput} setUserInput={setUserInput} />
                    <button
                        onClick={handleGenerateFinal}
                        disabled={loading || !userInput.trim()}
                        className="mt-5 inline-flex items-center gap-1.5 px-6 py-2.5 font-semibold text-sm text-white rounded-lg bg-gradient-to-br from-[var(--color-accent)] to-purple-600 shadow-[0_4px_14px_var(--color-accent-glow)] hover:shadow-[0_6px_22px_var(--color-accent-glow)] hover:-translate-y-0.5 transition-all disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                    >
                        {loading ? "Generating…" : "🚀 Generate Final Report"}
                    </button>
                </section>
            )}

            {/* Step 4 */}
            {step === 4 && finalReport && (
                <section className="bg-[var(--color-bg-card)] border border-[var(--color-border-subtle)] rounded-xl p-8 backdrop-blur-md animate-fade-up">
                    <h2 className="text-lg font-bold mb-5">📊 Step 4 — Final Compliance Report</h2>
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
