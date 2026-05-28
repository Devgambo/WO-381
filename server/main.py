import io
import logging
import os
import re
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
from pydantic import BaseModel

from auth import get_current_user, router as auth_router
from database import get_supabase_admin_client

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
)
log = logging.getLogger("compliance")


# --- Lazy-loaded services (heavy imports) ---
_vectordb = None


def get_vectordb():
    global _vectordb
    if _vectordb is None:
        from vector_db import VectorStore
        _vectordb = VectorStore(collection_name="is_codes_docs", folder_path="./chroma_db")
    return _vectordb


def get_embedding_model():
    from embedding_service import get_embedding_model as _factory
    return _factory()


# --- Limits ---
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(50 * 1024 * 1024)))  # 50 MB default
MAX_RAG_RESULTS = 20
MAX_SESSION_NAME_LEN = 200
ALLOWED_IMAGE_EXTS = {".png", ".jpg", ".jpeg"}
ALLOWED_PDF_EXTS = {".pdf"}

# --- FastAPI App ---
app = FastAPI(
    title="Structural Compliance Checker",
    description="AI-powered multi-agent RCC structural drawing compliance analysis",
    version="2.0.0",
)

_origins_env = os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:5173,http://localhost:3000")
_allow_origins = [o.strip() for o in _origins_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth_router)


def _safe_filename(name: str, default: str = "report") -> str:
    """Strip header-injection chars; keep alphanumerics, underscore, dash, dot."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", (name or "").strip())
    cleaned = cleaned.lstrip(".") or default
    return cleaned[:100]


# ---------- PDF generator ----------
def markdown_to_pdf(markdown_text: str, output) -> tuple[bool, Optional[str]]:
    """Render markdown to a PDF written to `output` (path or file-like)."""
    try:
        import html as html_mod

        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import (
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )

        doc = SimpleDocTemplate(
            output, pagesize=letter,
            rightMargin=72, leftMargin=72,
            topMargin=72, bottomMargin=18,
        )
        styles = getSampleStyleSheet()
        story = []

        h1_style = ParagraphStyle("H1", parent=styles["Heading1"], fontSize=12,
                                  textColor=colors.HexColor("#1a1a1a"), spaceAfter=6, spaceBefore=6)
        h2_style = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=10,
                                  textColor=colors.HexColor("#2a2a2a"), spaceAfter=5, spaceBefore=5)
        h3_style = ParagraphStyle("H3", parent=styles["Heading3"], fontSize=9,
                                  textColor=colors.HexColor("#3a3a3a"), spaceAfter=4, spaceBefore=4)
        normal_style = ParagraphStyle("Normal2", parent=styles["Normal"], fontSize=8, leading=10, spaceAfter=3)

        def convert_inline(text):
            text = html_mod.escape(text)
            text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
            text = re.sub(r'__(.+?)__', r'<b>\1</b>', text)
            text = re.sub(r'`(.+?)`', r'<font name="Courier" color="darkblue">\1</font>', text)
            text = re.sub(r'(?<!\*)\*([^*]+?)\*(?!\*)', r'<i>\1</i>', text)
            return text

        def parse_table(lines, start_idx):
            i = start_idx
            if i >= len(lines) or not lines[i].strip().startswith("|"):
                return None, start_idx
            header_line = lines[i].strip()
            if not header_line.startswith("|") or not header_line.endswith("|"):
                return None, start_idx
            headers = [cell.strip() for cell in header_line.split("|")[1:-1]]
            i += 1
            if i < len(lines) and re.match(r'^\|[\s\-:]+$', lines[i].strip()):
                i += 1
            table_data = []
            while i < len(lines):
                row_line = lines[i].strip()
                if not row_line.startswith("|"):
                    break
                cells = [cell.strip() for cell in row_line.split("|")[1:-1]]
                if len(cells) == len(headers):
                    table_data.append(cells)
                i += 1
            if table_data:
                return [headers] + table_data, i
            return None, start_idx

        lines = markdown_text.split("\n")
        i = 0
        in_list = False
        list_items = []

        def flush_list():
            nonlocal in_list, list_items
            if in_list and list_items:
                for item in list_items:
                    story.append(Paragraph(f"• {convert_inline(item)}", normal_style))
            list_items = []
            in_list = False

        while i < len(lines):
            line = lines[i].rstrip()

            if not line.strip():
                flush_list()
                story.append(Spacer(1, 0.1 * inch))
                i += 1
                continue

            if line.strip().startswith("|") and "|" in line[1:]:
                table_data, new_idx = parse_table(lines, i)
                if table_data:
                    tbl_style = TableStyle([
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f0f0")),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 7),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 4),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ])
                    available_width = letter[0] - 144
                    col_widths = [available_width / len(table_data[0])] * len(table_data[0])
                    formatted = [[Paragraph(convert_inline(c), normal_style) for c in row] for row in table_data]
                    pdf_table = Table(formatted, colWidths=col_widths)
                    pdf_table.setStyle(tbl_style)
                    story.append(pdf_table)
                    story.append(Spacer(1, 0.15 * inch))
                    i = new_idx
                    continue

            if line.startswith("#"):
                flush_list()
                if line.startswith("###"):
                    story.append(Paragraph(convert_inline(line[3:].strip()), h3_style))
                elif line.startswith("##"):
                    story.append(Paragraph(convert_inline(line[2:].strip()), h2_style))
                else:
                    story.append(Paragraph(convert_inline(line[1:].strip()), h1_style))
                i += 1
                continue

            if re.match(r'^---+$|^===+$|^\*\*\*+$', line):
                story.append(Spacer(1, 0.15 * inch))
                i += 1
                continue

            if re.match(r'^[-*+]\s+', line):
                in_list = True
                list_items.append(re.sub(r'^[-*+]\s+', '', line))
                i += 1
                continue

            if re.match(r'^\d+\.\s+', line):
                flush_list()
                story.append(Paragraph(convert_inline(re.sub(r'^\d+\.\s+', '', line)), normal_style))
                i += 1
                continue

            flush_list()
            story.append(Paragraph(convert_inline(line), normal_style))
            i += 1

        flush_list()
        doc.build(story)
        return True, None
    except Exception as e:
        log.exception("PDF conversion failed")
        return False, f"PDF conversion failed: {e}"


# ---------- Missing-field extractor ----------
_FLAG_STATUSES = {'missing information', 'cannot verify', 'non-compliant'}
_CATEGORY_HEADINGS = {
    'missing information', 'cannot verify', 'non-compliant',
    'wrong information', 'document type', 'not applicable',
}
_SKIP_LABELS = {'criteria', 'criterion', 'check', 'none', 'n/a', 'nil', '---', '#'}


def _normalise(s: str) -> str:
    return re.sub(r'[^a-z0-9]', '', s.lower())


def _extract_missing_fields(report: str) -> list[str]:
    """Extract missing/non-compliant fields from compliance table + Phase-4 / Step-5 section."""
    missing_from_table: list[str] = []
    missing_from_step5: list[str] = []

    in_section = False
    location_seen = False

    for line in report.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        # Table row scan
        if stripped.startswith('|'):
            cells = [c.strip() for c in stripped.split('|') if c.strip()]
            if len(cells) >= 4:
                status_cell = cells[-1].replace('**', '').strip().lower()
                if status_cell in _FLAG_STATUSES:
                    criteria_idx = 0
                    if cells[0].replace('**', '').strip().isdigit() and len(cells) >= 5:
                        criteria_idx = 1
                    criteria = re.sub(r'^\d+\.\s*', '', cells[criteria_idx].replace('**', '').strip()).strip()
                    if criteria and not criteria.isdigit() and criteria.lower() not in _SKIP_LABELS:
                        missing_from_table.append(criteria)
                        if 'location' in criteria.lower():
                            location_seen = True
            continue

        # Section header detection
        if stripped.startswith('#'):
            if re.search(
                r'(step\s*5|phase\s*4|4\.1\b|missing.*(?:wrong|information|unverifiable))',
                stripped, re.IGNORECASE,
            ):
                in_section = True
                continue
            if in_section:
                if re.search(r'(4\.2\b|4\.3\b|summary|quality|severity)', stripped, re.IGNORECASE):
                    in_section = False
                    continue
                heading_level = len(stripped) - len(stripped.lstrip('#'))
                if heading_level <= 3:
                    in_section = False
                    continue

        # Site location flag from Step 0
        if not location_seen and re.search(r'0\.2', stripped) and re.search(
            r'(?i)missing|not\s+(mentioned|found|specified|provided|available)', stripped,
        ):
            if re.search(r'(?i)(site\s*)?location', stripped):
                missing_from_step5.append('Site Location')
                location_seen = True
                continue

        if not in_section or stripped.startswith('|') or re.match(r'^---+$|^===+$|^\*\*\*+$', stripped):
            continue

        clean = re.sub(r'^\d+\.\s*|^[-*+]\s*', '', stripped).replace('**', '').strip()
        if not clean or clean.lower() in ('none', 'n/a', 'nil'):
            continue

        if ':' in clean:
            prefix, _, detail = clean.partition(':')
            prefix = prefix.strip()
            detail = detail.strip()
            if prefix.lower() in _CATEGORY_HEADINGS:
                if not detail:
                    continue
                items = [item.strip().rstrip('.') for item in re.split(r',\s*(?![^()]*\))', detail)]
                for item in items:
                    item = re.sub(r'(?i)\s*due to lack of explicit data\s*', '', item).strip()
                    item = re.sub(r'\s*\(.*?\)\s*$', '', item).strip()
                    if item.lower().startswith('and '):
                        item = item[4:].strip()
                    if re.search(r'(?i)notes?\s*section|no\s+dedicated', item):
                        continue
                    if item and item.lower() not in ('none', 'n/a', 'nil'):
                        missing_from_step5.append(item)
            else:
                if not re.search(r'(?i)notes?\s*section|no\s+dedicated', prefix):
                    missing_from_step5.append(prefix)
        else:
            if not re.search(r'(?i)notes?\s*section|no\s+dedicated', clean):
                missing_from_step5.append(clean)

    seen: set[str] = set()
    merged: list[str] = []
    for item in missing_from_step5:
        key = _normalise(item)
        if key and key not in seen:
            seen.add(key)
            merged.append(item)
    for item in missing_from_table:
        key = _normalise(item)
        if not key or key in seen:
            continue
        if any(key in existing or existing in key for existing in seen):
            continue
        seen.add(key)
        merged.append(item)

    log.debug("Missing fields merged: %s", merged)
    return merged


def _extract_quality_assessment(report: str) -> dict:
    """Parse the '### Drawing Quality Assessment' / Phase-4 block."""
    severity = "UNKNOWN"
    critical_defects = 0
    rejection_narrative = "N/A"

    in_section = False
    in_summary_section = False
    narrative_lines: list[str] = []
    collecting_narrative = False

    for line in report.splitlines():
        stripped = line.strip()

        if stripped.startswith("#") and re.search(
            r"drawing\s+quality\s+assessment|summary.*compliance|phase\s*4",
            stripped, re.IGNORECASE,
        ):
            if re.search(r"drawing\s+quality", stripped, re.IGNORECASE):
                in_section = True
            else:
                in_summary_section = True
            continue

        if (in_section or in_summary_section) and stripped.startswith("#"):
            if re.search(r"drawing\s+quality\s+assessment", stripped, re.IGNORECASE):
                in_section = True
                in_summary_section = False
                continue
            heading_level = len(stripped) - len(stripped.lstrip('#'))
            if heading_level <= 3:
                break

        if not in_section and not in_summary_section:
            continue

        sev_match = re.search(r"\*{0,2}severity\*{0,2}\s*:\s*([A-Z_]+)", stripped, re.IGNORECASE)
        if sev_match:
            raw_sev = sev_match.group(1).upper().strip()
            if raw_sev in {"ACCEPTABLE", "REQUIRES_REVISION", "REJECTED"}:
                severity = raw_sev
            continue

        verdict_match = re.search(r"\*{0,2}overall\s+verdict\*{0,2}\s*:\s*(.+)", stripped, re.IGNORECASE)
        if verdict_match and severity == "UNKNOWN":
            verdict_text = verdict_match.group(1).upper()
            if "FAIL" in verdict_text or "REJECT" in verdict_text:
                severity = "REJECTED"
            elif "CONDITIONAL" in verdict_text or "REVISION" in verdict_text:
                severity = "REQUIRES_REVISION"
            elif "PASS" in verdict_text or "ACCEPT" in verdict_text:
                severity = "ACCEPTABLE"
            continue

        defect_match = re.search(r"critical\s+defects?\s+count\s*:\s*(\d+)", stripped, re.IGNORECASE)
        if defect_match:
            try:
                critical_defects = int(defect_match.group(1))
            except ValueError:
                pass
            continue

        narr_match = re.search(r"\*{0,2}rejection\s+narrative\*{0,2}\s*:", stripped, re.IGNORECASE)
        if narr_match:
            collecting_narrative = True
            after_colon = stripped[narr_match.end():].strip()
            if after_colon and after_colon.lower() not in ("n/a", "na", ""):
                narrative_lines.append(after_colon)
            continue

        if collecting_narrative and stripped:
            narrative_lines.append(stripped)

    if narrative_lines:
        candidate = " ".join(narrative_lines).strip()
        if candidate.lower() not in ("n/a", "na"):
            rejection_narrative = candidate

    log.debug(
        "Quality: severity=%s defects=%d narrative_len=%d",
        severity, critical_defects, len(rejection_narrative),
    )
    return {
        "severity": severity,
        "critical_defects": critical_defects,
        "rejection_narrative": rejection_narrative,
    }


# -------- Routes --------
@app.get("/")
async def root():
    return {"message": "Foundation Compliance Check API", "status": "running"}


async def _read_upload(upload: UploadFile) -> bytes:
    data = await upload.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File '{upload.filename}' exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit",
        )
    return data


def _open_image_bytes(name: str, data: bytes) -> Image.Image:
    try:
        img = Image.open(io.BytesIO(data))
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        return img
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not open '{name}' as image: {e}")


@app.post("/api/generate-initial-report")
async def generate_initial_report(
    files: list[UploadFile] = File(...),
    current_user: dict = Depends(get_current_user),
):
    """Upload PDFs or images. Classify, run specialist agent, extract missing fields."""
    from llm_handler import pdf_to_images, pil_to_base64, run_specialist_agent
    from llm_service import classify_drawing_type

    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    pil_images: list[Image.Image] = []
    file_names: list[str] = []

    try:
        for upload in files:
            ext = os.path.splitext(upload.filename or "")[1].lower()
            data = await _read_upload(upload)
            if ext in ALLOWED_PDF_EXTS:
                pdf_pages = pdf_to_images(data)
                pil_images.extend(pdf_pages)
                file_names.append(upload.filename or "upload.pdf")
            elif ext in ALLOWED_IMAGE_EXTS:
                pil_images.append(_open_image_bytes(upload.filename or "image", data))
                file_names.append(upload.filename or "upload.png")
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported file type '{ext}' — accept PDF, PNG, JPG only",
                )

        base64_imgs = [pil_to_base64(img) for img in pil_images]
        drawing_type = classify_drawing_type(base64_imgs)
        initial_report = run_specialist_agent(base64_imgs, drawing_type)
        missing_fields = _extract_missing_fields(initial_report)

        session_name = ", ".join(file_names)[:MAX_SESSION_NAME_LEN]
        supabase = get_supabase_admin_client()
        db_result = supabase.table("reports").insert({
            "user_id": current_user["id"],
            "session_name": session_name,
            "initial_report": initial_report,
            "drawing_type": drawing_type,
        }).execute()
        report_id = db_result.data[0]["id"] if db_result.data else None

        quality_assessment = _extract_quality_assessment(initial_report)

        return {
            "report": initial_report,
            "drawing_type": drawing_type,
            "missing_fields": missing_fields,
            "file_names": file_names,
            "report_id": report_id,
            "quality_assessment": quality_assessment,
        }

    except HTTPException:
        raise
    except Exception:
        log.exception("generate_initial_report failed")
        raise HTTPException(status_code=500, detail="Initial report generation failed")
    finally:
        for img in pil_images:
            try:
                img.close()
            except Exception:
                pass


@app.post("/api/generate-final-report")
async def generate_final_report(
    initial_report: str = Form(...),
    user_input: str = Form(...),
    drawing_type: str = Form("foundation"),
    report_id: str = Form(""),
    assumed_values: str = Form(""),
    current_user: dict = Depends(get_current_user),
):
    """Generate the final compliance report using RAG."""
    import json as _json

    from llm_service import generate_compliance_report

    if not initial_report.strip() or not user_input.strip():
        raise HTTPException(
            status_code=400,
            detail="Both initial_report and user_input are required",
        )

    combined_user_input = user_input
    if assumed_values.strip():
        try:
            assumed_dict = _json.loads(assumed_values)
            if assumed_dict:
                assumed_lines = "\n".join(
                    f"- {field}: {value} (ASSUMED — use as given)"
                    for field, value in assumed_dict.items()
                )
                combined_user_input = (
                    f"{user_input}\n\n"
                    f"**Assumed values (treat as provided data):**\n{assumed_lines}"
                )
        except _json.JSONDecodeError:
            log.warning("assumed_values not valid JSON — ignoring")

    try:
        vectordb = get_vectordb()
        embedding_model = get_embedding_model()
        final_report, rag_ok = generate_compliance_report(
            previous_analysis=initial_report,
            user_input=combined_user_input,
            drawing_type=drawing_type,
            vectordb=vectordb,
            embedding_model=embedding_model,
        )

        if report_id:
            supabase = get_supabase_admin_client()
            supabase.table("reports").update({
                "final_report": final_report,
            }).eq("id", report_id).eq("user_id", current_user["id"]).execute()

        return {
            "report": final_report,
            "report_id": report_id,
            "rag_context_used": rag_ok,
        }

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception:
        log.exception("generate_final_report failed")
        raise HTTPException(status_code=500, detail="Final report generation failed")


# ─── Validator Agent API ────────────────────────────────────────────────────

class ValidateInputRequest(BaseModel):
    missing_fields: list[str]
    user_answers: dict[str, str]
    report_id: str = ""


@app.post("/api/validate-input")
async def validate_input(
    body: ValidateInputRequest,
    current_user: dict = Depends(get_current_user),
):
    from llm_service import validate_user_input as do_validate

    if not body.missing_fields or not body.user_answers:
        raise HTTPException(
            status_code=400,
            detail="Both missing_fields and user_answers are required",
        )

    try:
        return do_validate(body.missing_fields, body.user_answers)
    except Exception:
        log.exception("validate_input failed")
        raise HTTPException(status_code=500, detail="Validation failed")


# ─── RAG Query API (authenticated) ──────────────────────────────────────────

@app.get("/api/rag/query")
async def rag_query(
    q: str,
    k: int = 5,
    content_type: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query string 'q' is required")

    try:
        vectordb = get_vectordb()
        embedding_model = get_embedding_model()

        where = None
        if content_type and content_type in ("text", "table", "image_description"):
            where = {"content_type": content_type}

        effective_k = min(k, MAX_RAG_RESULTS)
        results = vectordb.query_by_text(
            query_text=q,
            embedding_model=embedding_model,
            n_results=effective_k,
            where=where,
        )

        return {
            "query": q,
            "count": len(results),
            "k_requested": k,
            "k_returned": effective_k,
            "max_k": MAX_RAG_RESULTS,
            "results": results,
        }
    except Exception:
        log.exception("rag_query failed")
        raise HTTPException(status_code=500, detail="RAG query failed")


@app.post("/api/download-pdf")
async def download_pdf(
    markdown_content: str = Form(...),
    filename: str = Form("compliance_report"),
    current_user: dict = Depends(get_current_user),
):
    """Convert markdown report to PDF and stream as download (no disk write)."""
    safe = _safe_filename(filename, default="compliance_report")
    pdf_filename = f"{safe}.pdf"

    buffer = io.BytesIO()
    success, error_msg = markdown_to_pdf(markdown_content, buffer)
    if not success:
        raise HTTPException(status_code=500, detail=error_msg or "PDF conversion failed")

    return Response(
        content=buffer.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{pdf_filename}"'},
    )


# ─── Reports API ────────────────────────────────────────────────────────────

@app.get("/api/reports")
async def list_reports(current_user: dict = Depends(get_current_user)):
    try:
        supabase = get_supabase_admin_client()
        result = supabase.table("reports") \
            .select("id, session_name, drawing_type, initial_report, final_report, created_at") \
            .eq("user_id", current_user["id"]) \
            .order("created_at", desc=True) \
            .execute()
        return {"reports": result.data}
    except Exception:
        log.exception("list_reports failed")
        raise HTTPException(status_code=500, detail="Could not list reports")


@app.get("/api/reports/{report_id}")
async def get_report(report_id: str, current_user: dict = Depends(get_current_user)):
    try:
        supabase = get_supabase_admin_client()
        result = supabase.table("reports") \
            .select("*") \
            .eq("id", report_id) \
            .eq("user_id", current_user["id"]) \
            .single() \
            .execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Report not found")
        return {"report": result.data}
    except HTTPException:
        raise
    except Exception:
        log.exception("get_report failed")
        raise HTTPException(status_code=500, detail="Could not fetch report")


@app.get("/api/reports/{report_id}/missing-fields")
async def get_report_missing_fields(
    report_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Re-derive missing fields for a stored report (resume flow)."""
    try:
        supabase = get_supabase_admin_client()
        result = supabase.table("reports") \
            .select("initial_report") \
            .eq("id", report_id) \
            .eq("user_id", current_user["id"]) \
            .single() \
            .execute()
        if not result.data or not result.data.get("initial_report"):
            raise HTTPException(status_code=404, detail="Report not found")
        return {"missing_fields": _extract_missing_fields(result.data["initial_report"])}
    except HTTPException:
        raise
    except Exception:
        log.exception("get_report_missing_fields failed")
        raise HTTPException(status_code=500, detail="Could not derive missing fields")


@app.delete("/api/reports/{report_id}")
async def delete_report(report_id: str, current_user: dict = Depends(get_current_user)):
    try:
        supabase = get_supabase_admin_client()
        result = supabase.table("reports") \
            .delete() \
            .eq("id", report_id) \
            .eq("user_id", current_user["id"]) \
            .execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Report not found")
        return {"deleted": True}
    except HTTPException:
        raise
    except Exception:
        log.exception("delete_report failed")
        raise HTTPException(status_code=500, detail="Could not delete report")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("RELOAD", "false").lower() == "true",
    )
