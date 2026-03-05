import { useCallback } from "react";
import { useDropzone } from "react-dropzone";

const ACCEPTED = {
  "application/pdf": [".pdf"],
  "image/png": [".png"],
  "image/jpeg": [".jpg", ".jpeg"],
  "image/gif": [".gif"],
  "image/bmp": [".bmp"],
  "image/webp": [".webp"],
};

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
      {/* Dropzone */}
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-all
          ${isDragActive
            ? "border-[var(--color-accent)] bg-[var(--color-accent-glow)]"
            : "border-[var(--color-border-subtle)] bg-[var(--color-bg-glass)] hover:border-[var(--color-accent)] hover:bg-[var(--color-accent-glow)]"
          }`}
      >
        <input {...getInputProps()} />
        <span className="text-4xl block mb-2">📁</span>
        {isDragActive ? (
          <p className="text-sm font-medium text-[var(--color-text-primary)]">Drop the files here…</p>
        ) : (
          <>
            <p className="text-sm font-medium text-[var(--color-text-primary)]">
              Drag & drop PDF or image files here
            </p>
            <span className="text-xs text-[var(--color-text-muted)] mt-1 block">
              or click to browse • Supports PDF, PNG, JPG, GIF, BMP, WebP
            </span>
          </>
        )}
      </div>

      {/* File List */}
      {files.length > 0 && (
        <div className="mt-4">
          <h4 className="text-sm font-semibold text-[var(--color-text-secondary)] mb-2">📎 Selected Files</h4>
          {files.map((f, i) => (
            <div
              key={i}
              className="flex items-center gap-2.5 px-3 py-2 rounded-lg bg-[var(--color-bg-glass)] border border-[var(--color-border-subtle)] mb-1.5 hover:border-[var(--color-border-hover)] transition-colors"
            >
              <span className="text-lg">{f.type === "application/pdf" ? "📄" : "🖼️"}</span>
              <span className="flex-1 text-sm font-medium text-[var(--color-text-primary)] truncate">
                {f.name}
              </span>
              <span className="text-xs text-[var(--color-text-muted)]">
                {(f.size / 1024).toFixed(1)} KB
              </span>
              <button
                onClick={() => removeFile(i)}
                title="Remove file"
                className="bg-transparent border-none text-[var(--color-text-muted)] cursor-pointer text-sm px-1.5 py-0.5 rounded hover:text-red-400 hover:bg-red-500/15 transition-colors"
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
