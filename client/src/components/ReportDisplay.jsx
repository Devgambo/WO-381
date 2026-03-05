import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { downloadPdf } from "../api";
import { useState } from "react";

export default function ReportDisplay({ report, title, filenamePrefix }) {
    const [downloading, setDownloading] = useState(false);

    if (!report) return null;

    const handleDownloadMd = () => {
        const blob = new Blob([report], { type: "text/markdown" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${filenamePrefix}_${Date.now()}.md`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
    };

    const handleDownloadPdf = async () => {
        setDownloading(true);
        try {
            await downloadPdf(report, filenamePrefix);
        } catch (err) {
            alert("PDF download failed: " + err.message);
        } finally {
            setDownloading(false);
        }
    };

    return (
        <div className="mt-2">
            <h3 className="text-base font-semibold text-[var(--color-accent-light)] mb-3">{title}</h3>

            {/* Actions */}
            <div className="flex gap-2.5 flex-wrap mb-5">
                <button
                    onClick={handleDownloadMd}
                    className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-semibold text-[var(--color-text-primary)] bg-[var(--color-bg-glass)] border border-[var(--color-border-subtle)] rounded-lg hover:border-[var(--color-accent)] hover:bg-[var(--color-accent-glow)] transition-all cursor-pointer"
                >
                    📥 Download Markdown
                </button>
                <button
                    onClick={handleDownloadPdf}
                    disabled={downloading}
                    className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-semibold text-[var(--color-text-primary)] bg-[var(--color-bg-glass)] border border-[var(--color-border-subtle)] rounded-lg hover:border-[var(--color-accent)] hover:bg-[var(--color-accent-glow)] transition-all disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                >
                    {downloading ? "⏳ Generating PDF…" : "📄 Download PDF"}
                </button>
            </div>

            {/* Report Content */}
            <div className="bg-[var(--color-bg-glass)] border border-[var(--color-border-subtle)] rounded-lg p-6 max-h-[600px] overflow-y-auto text-sm leading-7 markdown-body">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{report}</ReactMarkdown>
            </div>
        </div>
    );
}
