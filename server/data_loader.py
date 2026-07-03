"""Markdown → RAG chunk converter for SP 34 / IS 456 source corpus.

Design notes:
- Recursive character splitter with chunk_size=900 / overlap=200. BGE has a
  512-token cap (~2k chars) but smaller chunks give the cross-encoder a
  cleaner signal and let MMR diversify across true sub-topics.
- Every chunk gets a *parent-section prefix* embedded into the text:
  `[SP 34 §<section>.<clause>] — <section_title>` — gives the embedder
  lexical anchoring even when the body is short.
- Every chunk carries `element_type` ∈ {foundation, slab, beam, column,
  general} so RAG queries can filter to drawing-type-relevant chunks.
- Stable IDs (sha1) make ingest idempotent — re-runs upsert in place
  instead of producing duplicates.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

CHUNK_SIZE = 900
CHUNK_OVERLAP = 200


def _stable_id(source_file: str, clause_id: str, chunk_index: int, content: str) -> str:
    """16-char sha1 over the chunk fingerprint. Deterministic across runs."""
    fingerprint = f"{source_file}|{clause_id}|{chunk_index}|{content[:200]}"
    return hashlib.sha1(fingerprint.encode("utf-8")).hexdigest()[:16]


def _classify_element_type(file_name: str, content: str = "") -> str:
    """Heuristic: filename first, then a keyword fallback over the body."""
    fn = file_name.lower()
    if "beam" in fn:
        return "beam"
    if "column" in fn:
        return "column"
    if "slab" in fn:
        return "slab"
    if "foundation" in fn or "footing" in fn:
        return "foundation"

    text = content.lower()
    keyword_hits = {
        "beam": text.count(" beam") + text.count("beams "),
        "column": text.count(" column") + text.count("columns "),
        "slab": text.count(" slab") + text.count("slabs "),
        "foundation": text.count(" footing") + text.count("foundation"),
    }
    best = max(keyword_hits.items(), key=lambda kv: kv[1])
    return best[0] if best[1] >= 2 else "general"


def _splitter():
    """RecursiveCharacterTextSplitter from langchain (transitive dep)."""
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    return RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )


def _parent_prefix(section_number: str, clause_id: str, section_title: str) -> str:
    parts = []
    if section_number:
        parts.append(f"§{section_number}")
        if clause_id:
            parts.append(f"Cl. {clause_id}")
    elif clause_id:
        parts.append(f"Cl. {clause_id}")
    head = " ".join(parts) if parts else "SP 34"
    title = (section_title or "").strip()
    return f"[{head}{' — ' + title if title else ''}]\n\n"


def chunk_ocr_file(content: str, file_name: str) -> list[dict]:
    """Section-aware splitter for SP 34 OCR files."""
    sections = re.split(r"(?m)^(#{1,4}\s+.*$)", content)

    splitter = _splitter()
    chunks: list[dict] = []
    current_title = ""
    current_section = ""
    clause_id = ""

    def emit(body: str, header: str) -> None:
        if not body.strip():
            return
        element_type = _classify_element_type(file_name, body)
        for piece in splitter.split_text(body):
            piece = piece.strip()
            if not piece:
                continue
            prefix = _parent_prefix(current_section, clause_id, current_title)
            text = f"{prefix}{piece}"
            chunks.append({
                "source_file": file_name,
                "section_number": current_section,
                "section_title": current_title,
                "clause_id": clause_id,
                "content_type": "text",
                "element_type": element_type,
                "header": header,
                "content": text,
            })

    # Preamble before any heading.
    if sections and sections[0].strip():
        current_title = "Preliminary"
        current_section = "Prelim"
        emit(sections[0], "")

    for i in range(1, len(sections), 2):
        heading = sections[i]
        text_block = sections[i + 1] if i + 1 < len(sections) else ""
        heading_clean = heading.strip("#").strip()

        sec_match = re.search(r"SECTION\s+(\d+)", heading_clean, re.IGNORECASE)
        if sec_match:
            current_section = sec_match.group(1)
            current_title = heading_clean
            clause_id = ""
        else:
            clause_match = re.match(r"^([\d\.]+)\s+(.*)", heading_clean)
            if clause_match:
                clause_id = clause_match.group(1)
                current_title = clause_match.group(2)
            else:
                clause_id = ""
                current_title = heading_clean

        emit(text_block, heading.strip())

    return chunks


def parse_images_tables(content: str, file_name: str) -> list[dict]:
    """Parser for the cleaned SP_IMAGES_TABLES.md (markdown section format)."""
    chunks: list[dict] = []
    sections = re.split(r"(?m)^##\s+(is_code_chunk_\d+)\s*\(([^)]*)\)", content)

    for i in range(1, len(sections), 3):
        if i + 2 >= len(sections):
            break
        chunk_id = sections[i].strip()
        header_info = sections[i + 1].strip()
        body = sections[i + 2].strip()

        header_parts = [p.strip() for p in header_info.split(",")]
        data_type = header_parts[0] if header_parts else "UNKNOWN"
        page = ""
        for hp in header_parts:
            if hp.startswith("Page"):
                page = hp.replace("Page", "").strip()

        data_type_upper = data_type.upper()
        if "TABLE" in data_type_upper:
            c_type = "table"
        elif "DIAGRAM" in data_type_upper:
            c_type = "image_description"
        else:
            c_type = "text"

        symbols: list[str] = []
        sym_match = re.search(
            r"\*\*Symbols & Notation:\*\*\s*\n\|[^\n]+\n\|[-|]+\n((?:\|[^\n]+\n)*)",
            body,
        )
        if sym_match:
            for row in sym_match.group(1).strip().splitlines():
                cols = [c.strip() for c in row.split("|") if c.strip()]
                if len(cols) >= 2:
                    symbols.append(f"{cols[0]} ({cols[1]}, {cols[2] if len(cols) > 2 else ''})")

        prefix = f"[SP 34 Page {page or '—'} — {data_type}]\n\n"
        text = prefix + body
        chunks.append({
            "chunk_id": chunk_id,
            "source_file": file_name,
            "data_type": data_type,
            "content_type": c_type,
            "element_type": _classify_element_type(file_name, body),
            "page": page,
            "symbols": ", ".join(symbols),
            "content": text,
        })

    return chunks


def chunk_guide_file(content: str, file_name: str) -> list[dict]:
    """Step-based splitter for RCC reading guides."""
    element_type = _classify_element_type(file_name)

    sections = re.split(r"(?m)^(##?\s+(?:Step|STEP|\d+\.).*$)", content)
    splitter = _splitter()
    chunks: list[dict] = []

    def emit(body: str, step_idx: str, heading: str) -> None:
        if not body.strip():
            return
        for piece in splitter.split_text(body):
            piece = piece.strip()
            if not piece:
                continue
            prefix = f"[Guide — {element_type} — Step {step_idx or '?'}]\n\n"
            text = prefix + (heading + "\n\n" if heading else "") + piece
            chunks.append({
                "source_file": file_name,
                "content_type": "procedural_guide",
                "element_type": element_type,
                "step_number": step_idx,
                "header": heading,
                "content": text,
            })

    if sections and sections[0].strip():
        emit(sections[0].strip(), "Prelim", "")

    for i in range(1, len(sections), 2):
        heading = sections[i]
        text_block = sections[i + 1].strip() if i + 1 < len(sections) else ""
        step_match = re.search(r"(?:Step|STEP|\d+\.)\s*(\d*)", heading)
        step_idx = step_match.group(1) if step_match and step_match.group(1) else "?"
        emit(text_block, step_idx, heading.strip())

    return chunks


def _assign_ids(chunks: list[dict]) -> list[dict]:
    """Assign deterministic chunk_id when absent."""
    for i, c in enumerate(chunks):
        if c.get("chunk_id"):
            continue
        c["chunk_id"] = _stable_id(
            c.get("source_file", ""),
            c.get("clause_id", "") or c.get("step_number", "") or "",
            i,
            c.get("content", ""),
        )
    return chunks


def read_md_files_from_folder(folder_path: str) -> list[dict]:
    """Reads and chunks all .md files using specialized parsers."""
    directory = Path(folder_path)
    if not directory.is_dir():
        raise FileNotFoundError(f"Directory not found at: {directory}")

    all_chunks: list[dict] = []

    for file_path in sorted(directory.glob("*.md")):
        try:
            content = file_path.read_text(encoding="utf-8")
            file_name = file_path.name

            if file_name.startswith("SP_34_OCR_"):
                file_chunks = chunk_ocr_file(content, file_name)
            elif file_name == "SP_IMAGES_TABLES.md":
                file_chunks = parse_images_tables(content, file_name)
            elif file_name.startswith("Reading_RCC_"):
                file_chunks = chunk_guide_file(content, file_name)
            else:
                file_chunks = [{
                    "source_file": file_name,
                    "content_type": "text",
                    "element_type": _classify_element_type(file_name, content),
                    "content": content,
                }]

            all_chunks.extend(file_chunks)
        except Exception as e:
            print(f"Error reading file {file_path.name}: {e}")
            continue

    if not all_chunks:
        raise ValueError(f"No valid chunks parsed from '{directory}'")

    return _assign_ids(all_chunks)
