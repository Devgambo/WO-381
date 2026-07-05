import { useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { UploadIcon, XIcon } from "./Icons";

const ACCEPTED = {
  "application/pdf": [".pdf"],
  "image/png": [".png"],
  "image/jpeg": [".jpg", ".jpeg"],
};

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export default function FileUpload({ files, setFiles }) {
  const onDrop = useCallback(
    (accepted) => setFiles((prev) => [...prev, ...accepted]),
    [setFiles]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED,
    multiple: true,
  });

  const removeFile = (index) => setFiles((prev) => prev.filter((_, i) => i !== index));

  return (
    <div>
      <div
        {...getRootProps()}
        className={`relative border-2 border-dashed p-10 text-center cursor-pointer transition-colors
          ${isDragActive
            ? "border-[var(--color-accent)] bg-[var(--color-accent-glow)]"
            : "border-[var(--color-border-medium)] bg-[var(--color-bg-input)] hover:border-[var(--color-border-hover)] hover:bg-[var(--color-bg-glass)]"
          }`}
      >
        <input {...getInputProps()} />
        <div className="flex flex-col items-center gap-2">
          <div className={`w-11 h-11 grid place-items-center border rounded-[3px] transition-colors
            ${isDragActive
              ? "border-[var(--color-accent)] text-[var(--color-accent-light)]"
              : "border-[var(--color-border-medium)] text-[var(--color-text-secondary)]"
            }`}
          >
            <UploadIcon size={18} />
          </div>
          {isDragActive ? (
            <p className="text-sm font-medium text-[var(--color-text-primary)]">
              Release to drop files
            </p>
          ) : (
            <>
              <p className="text-sm font-medium text-[var(--color-text-primary)]">
                Drag & drop drawings here
              </p>
              <span className="label-mono">
                or click to browse · pdf, png, jpg
              </span>
            </>
          )}
        </div>
      </div>

      {files.length > 0 && (
        <div className="mt-5">
          <div className="flex items-center justify-between mb-2">
            <span className="label-mono">Queued files</span>
            <span className="label-mono">{files.length.toString().padStart(2, "0")}</span>
          </div>
          <div className="border border-[var(--color-border-subtle)] divide-y divide-[var(--color-border-subtle)]">
            {files.map((f, i) => (
              <div
                key={`${f.name}-${i}`}
                className="flex items-center gap-3 px-3 py-2 bg-[var(--color-bg-card)] hover:bg-[var(--color-bg-glass)] transition-colors"
              >
                <span className="mono text-[10px] uppercase tracking-wider text-[var(--color-accent-light)] border border-[var(--color-border-medium)] px-1.5 py-0.5">
                  {f.type === "application/pdf" ? "PDF" : "IMG"}
                </span>
                <span className="flex-1 text-sm text-[var(--color-text-primary)] truncate">
                  {f.name}
                </span>
                <span className="mono text-xs text-[var(--color-text-muted)]">
                  {formatSize(f.size)}
                </span>
                <button
                  onClick={() => removeFile(i)}
                  title="Remove file"
                  aria-label={`Remove ${f.name}`}
                  className="w-6 h-6 grid place-items-center rounded-[3px] text-[var(--color-text-muted)] hover:text-[var(--color-danger)] hover:bg-[rgba(239,68,68,0.08)] transition-colors cursor-pointer bg-transparent border-none"
                >
                  <XIcon size={13} />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
