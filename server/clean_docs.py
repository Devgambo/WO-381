"""
One-time cleanup script for SP34_md source documents.
Run from the server/ directory:  python clean_docs.py
Creates cleaned files IN-PLACE (overwrites originals).
Backs up originals to SP34_md_backup/ first.
"""
import re
import shutil
from pathlib import Path

SRC = Path("./SP34_md")
BACKUP = Path("./SP34_md_backup")


def backup():
    if BACKUP.exists():
        print(f"Backup already exists at {BACKUP}, skipping backup.")
        return
    shutil.copytree(SRC, BACKUP)
    print(f"Backed up originals to {BACKUP}")


# ─── SP_IMAGES_TABLES.md ───────────────────────────────────────────────────────

def clean_images_tables():
    """
    Converts the massive pipe-delimited table into clean, readable markdown
    chunks. Removes:
      - raw_markdown column (contains base64 image data)
      - image_path column (local paths)
      - context_before / context_after (empty columns)
    Keeps:
      - chunk_id, data_type, page, content description, symbols
    """
    fp = SRC / "SP_IMAGES_TABLES.md"
    raw = fp.read_text(encoding="utf-8")
    lines = raw.splitlines()

    chunks = []
    current = None

    for line in lines:
        if not line.strip().startswith("|"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 12:
            continue

        chunk_id = parts[1]

        if chunk_id.startswith("is_code_chunk_"):
            # Save previous chunk
            if current:
                chunks.append(current)

            data_type = parts[8] if len(parts) > 8 else "UNKNOWN"
            page = parts[4] if len(parts) > 4 else ""
            content_desc = parts[6] if len(parts) > 6 else ""

            # Clean content: strip [Figure, Page X]: prefix if present
            content_desc = re.sub(r'^\[(?:Figure|Table),?\s*Page\s*\d+\]:\s*', '', content_desc)
            # Remove any remaining base64 fragments
            content_desc = re.sub(r'<img\s+src="data:image/[^"]*"[^>]*>', '[image]', content_desc)
            # Clean up escaped HTML entities
            content_desc = content_desc.replace("&nbsp;", " ").replace("&amp;", "&")

            current = {
                "id": chunk_id,
                "data_type": data_type,
                "page": page,
                "content": content_desc.strip(),
                "symbols": [],
            }

            # First symbol row inline
            if len(parts) > 10 and parts[9]:
                sym = parts[9].strip()
                meaning = parts[10].strip() if len(parts) > 10 else ""
                unit = parts[11].strip() if len(parts) > 11 else ""
                if sym:
                    current["symbols"].append((sym, meaning, unit))

        elif not chunk_id and current:
            # Continuation row (symbol data only)
            if len(parts) > 10 and parts[9]:
                sym = parts[9].strip()
                meaning = parts[10].strip() if len(parts) > 10 else ""
                unit = parts[11].strip() if len(parts) > 11 else ""
                if sym:
                    current["symbols"].append((sym, meaning, unit))

    if current:
        chunks.append(current)

    # Build clean markdown
    out_lines = [
        "# SP 34 — Images & Tables Reference\n",
        "Cleaned reference document for RAG ingestion. Each entry is one figure or table from SP 34:1987.\n",
        "---\n",
    ]

    for c in chunks:
        out_lines.append(f"## {c['id']} ({c['data_type']}, Page {c['page']})\n")
        out_lines.append(f"{c['content']}\n")

        if c["symbols"]:
            out_lines.append("\n**Symbols & Notation:**\n")
            out_lines.append("| Symbol | Meaning | Unit |")
            out_lines.append("|---|---|---|")
            for sym, meaning, unit in c["symbols"]:
                out_lines.append(f"| {sym} | {meaning} | {unit} |")
            out_lines.append("")

        out_lines.append("---\n")

    cleaned = "\n".join(out_lines)
    fp.write_text(cleaned, encoding="utf-8")
    original_size = len(raw)
    new_size = len(cleaned)
    print(f"  SP_IMAGES_TABLES.md: {original_size:,} -> {new_size:,} bytes "
          f"({100 - new_size*100//original_size}% reduction, {len(chunks)} entries)")


# ─── OCR files ──────────────────────────────────────────────────────────────────

def clean_ocr_file(fp: Path):
    """
    Cleans an OCR markdown file:
    - Remove "As in the Original Standard, this Page is Intentionally Left Blank"
    - Remove "HANDBOOK ON CONCRETE REINFORCEMENT AND DETAINING" header noise
    - Normalize duplicate section headers (e.g., SECTION 1 appearing twice)
    - Clean broken LaTeX: $\\mathrm{...}$ → plain text for common patterns
    - Remove excessive blank lines
    - Remove page-break artifacts
    """
    content = fp.read_text(encoding="utf-8")
    original_size = len(content)

    # Remove "intentionally left blank" pages
    content = re.sub(
        r'As in the Original Standard,?\s*this Page is Intentionally Left Blank\s*',
        '', content, flags=re.IGNORECASE
    )

    # Remove handbook title noise repeated across pages
    content = re.sub(
        r'HANDBOOK ON CONCRETE REINFORCEMENT AND DETA[IL]+ING\s*',
        '', content, flags=re.IGNORECASE
    )

    # Remove "SP 34 : 1987" standalone references (page headers)
    content = re.sub(r'^SP\s*34\s*:\s*1987\s*$', '', content, flags=re.MULTILINE)

    # Remove "SECTION · XX" noise (OCR artifact with dot separators)
    content = re.sub(r'#\s*SECTION\s*[·\.\-]\s*\w+\s*\n', '', content)

    # Clean common LaTeX fragments to plain text
    latex_replacements = [
        (r'\$\\mathrm\{N\}\s*/\s*\\mathrm\{mm\}\^\{?2\}?\$', 'N/mm²'),
        (r'\$\\mathrm\{mm\}\^\{?2\}?\$', 'mm²'),
        (r'\$\\mathrm\{N\}\\?\$', 'N'),
        (r'\$\\mathrm\{mm\}\\?\$', 'mm'),
        (r'\$\\mathrm\{Fe\s*(\d+)\}\\?\$', r'Fe\1'),
        (r'\$\\mathrm\{~([^}]+)\}\\?\$', r'\1'),
        (r'\$\\pm\s*', '±'),
        (r'\\pm\s*', '±'),
        (r'\$\s*$', '', re.MULTILINE),  # trailing lone $
    ]
    for pattern, repl, *flags in latex_replacements:
        f = flags[0] if flags else 0
        content = re.sub(pattern, repl, content, flags=f)

    # Remove duplicate consecutive section headers (OCR double-scans)
    content = re.sub(
        r'(#\s+SECTION\s+\d+\s*\n(?:.*\n){0,3})\1',
        r'\1', content
    )

    # Collapse 3+ blank lines to 2
    content = re.sub(r'\n{3,}', '\n\n', content)

    # Strip trailing whitespace per line
    content = re.sub(r'[ \t]+$', '', content, flags=re.MULTILINE)

    new_size = len(content)
    fp.write_text(content, encoding="utf-8")
    print(f"  {fp.name}: {original_size:,} -> {new_size:,} bytes "
          f"({100 - new_size*100//original_size}% reduction)")


# ─── Main ───────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("SP34 Document Cleaner")
    print("=" * 60)

    backup()

    print("\nCleaning SP_IMAGES_TABLES.md...")
    clean_images_tables()

    print("\nCleaning OCR files...")
    for fp in sorted(SRC.glob("SP_34_OCR_*.md")):
        clean_ocr_file(fp)

    print("\nSkipping Reading_RCC_*.md (already clean)")
    print("\n[DONE] All documents cleaned. Originals backed up to SP34_md_backup/")
    print("   Now re-run: python ingest.py")


if __name__ == "__main__":
    main()
