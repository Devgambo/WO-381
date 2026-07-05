import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { downloadPdf } from "../api";
import { useAuth } from "../context/AuthContext";
import { DownloadIcon, FileTextIcon } from "./Icons";

// react-markdown@10 escapes raw HTML by default — we never enable
// rehype-raw, so model output like `<img onerror=...>` renders as
// literal text. No XSS surface here; do not add rehype-raw without
// also wiring rehype-sanitize.
export default function ReportDisplay({ report, title, filenamePrefix, onError }) {
    const { token } = useAuth();
    const [downloading, setDownloading] = useState(false);

    if (!report) return null;

    const safePrefix = filenamePrefix || "report";

    const handleDownloadMd = () => {
        const blob = new Blob([report], { type: "text/markdown" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${safePrefix}.md`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
    };

    const handleDownloadPdf = async () => {
        setDownloading(true);
        try {
            await downloadPdf(report, safePrefix, token);
        } catch (err) {
            if (onError) onError(err.message);
            else console.error("PDF download failed:", err);
        } finally {
            setDownloading(false);
        }
    };

    return (
        <div>
            <div className="flex items-center justify-between mb-4 pb-3 border-b border-[var(--color-border-subtle)]">
                <div>
                    <span className="label-mono">Output</span>
                    <h3 className="text-sm font-semibold text-[var(--color-text-primary)] mt-0.5">{title}</h3>
                </div>
                <div className="flex gap-2">
                    <button
                        onClick={handleDownloadMd}
                        className="btn-secondary px-3 py-1.5 text-xs cursor-pointer mono uppercase tracking-wider inline-flex items-center gap-1.5"
                    >
                        <FileTextIcon size={12} />
                        <span>.md</span>
                    </button>
                    <button
                        onClick={handleDownloadPdf}
                        disabled={downloading}
                        className="btn-secondary px-3 py-1.5 text-xs cursor-pointer mono uppercase tracking-wider disabled:opacity-50 disabled:cursor-not-allowed inline-flex items-center gap-1.5"
                    >
                        <DownloadIcon size={12} />
                        <span>{downloading ? "…" : ".pdf"}</span>
                    </button>
                </div>
            </div>

            <div className="bg-[var(--color-bg-input)] border border-[var(--color-border-subtle)] p-6 max-h-[600px] overflow-y-auto markdown-body">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{report}</ReactMarkdown>
            </div>
        </div>
    );
}
