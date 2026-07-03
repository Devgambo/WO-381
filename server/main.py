import asyncio
import io
import logging
import os
import re
from typing import Optional
from urllib.parse import quote
from uuid import UUID

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
from pydantic import BaseModel
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from auth import get_current_user, router as auth_router
from database import get_supabase_admin_client
from extractors import extract_missing_fields
from jobs import background_enabled, create_job, get_job, get_queue
from rate_limit import LIMIT_GENERATE, LIMIT_JOBS, LIMIT_QUERY, limiter

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
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(50 * 1024 * 1024)))           # 50 MB / file
MAX_TOTAL_UPLOAD_BYTES = int(os.getenv("MAX_TOTAL_UPLOAD_BYTES", str(150 * 1024 * 1024)))  # 150 MB aggregate
MAX_PAGES_PER_PDF = int(os.getenv("MAX_PAGES_PER_PDF", "30"))
MAX_RAG_RESULTS = 20
MAX_SESSION_NAME_LEN = 200
ALLOWED_IMAGE_EXTS = {".png", ".jpg", ".jpeg"}
ALLOWED_PDF_EXTS = {".pdf"}
ALLOWED_RAG_CONTENT_TYPES = {"text", "table", "image_description", "procedural_guide"}
_UPLOAD_CHUNK = 64 * 1024  # 64 KB

# --- FastAPI App ---
app = FastAPI(
    title="Structural Compliance Checker",
    description="AI-powered multi-agent RCC structural drawing compliance analysis",
    version="2.1.0",
)

_origins_env = os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:5173,http://localhost:3000")
_allow_origins = [o.strip() for o in _origins_env.split(",") if o.strip()]

# Rate limiting (slowapi) — register the limiter and the 429 handler.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["Content-Disposition", "Retry-After", "X-RateLimit-Limit", "X-RateLimit-Remaining"],
)

# Whether to advertise HSTS — only when served over TLS (set ENABLE_HSTS=true in prod).
_ENABLE_HSTS = os.getenv("ENABLE_HSTS", "false").lower() == "true"


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """Defence-in-depth response headers. The API serves JSON/PDF, never HTML
    that loads third-party script, so a tight CSP is safe."""
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
    if _ENABLE_HSTS:
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
        )
    return response


app.include_router(auth_router)


def _safe_filename(name: str, default: str = "report") -> str:
    """Strip header-injection chars; keep alphanumerics, underscore, dash, dot."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", (name or "").strip())
    cleaned = cleaned.lstrip(".") or default
    return cleaned[:100]


def _is_uuid(s: str) -> bool:
    if not s:
        return False
    try:
        UUID(s)
        return True
    except (ValueError, TypeError):
        return False


def _content_disposition(filename: str) -> str:
    """RFC 5987 Content-Disposition with ASCII fallback + UTF-8 form.

    Browsers that don't understand the `filename*=` form fall back to the
    ASCII `filename=` value.
    """
    ascii_safe = re.sub(r"[^\x20-\x7E]", "_", filename).replace('"', "_") or "report"
    encoded = quote(filename, safe="")
    return f'attachment; filename="{ascii_safe}"; filename*=UTF-8\'\'{encoded}'


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
    except Exception:
        log.exception("PDF conversion failed")
        return False, "PDF conversion failed."


# -------- Routes --------
@app.get("/")
async def root():
    return {"message": "Foundation Compliance Check API", "status": "running"}


async def _read_upload_streaming(upload: UploadFile, remaining_budget: int) -> bytes:
    """Stream-read with early rejection if oversize.

    Caller passes the remaining aggregate budget so the request fails the
    moment cumulative bytes exceed MAX_TOTAL_UPLOAD_BYTES.
    """
    chunks: list[bytes] = []
    total = 0
    file_cap = min(MAX_UPLOAD_BYTES, remaining_budget) + 1
    while True:
        chunk = await upload.read(_UPLOAD_CHUNK)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File '{upload.filename}' exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)} MB single-file limit",
            )
        if total > remaining_budget:
            raise HTTPException(
                status_code=413,
                detail=f"Total upload exceeds {MAX_TOTAL_UPLOAD_BYTES // (1024 * 1024)} MB aggregate limit",
            )
        if total > file_cap:
            # Defence-in-depth: should be unreachable because of the two checks above.
            raise HTTPException(status_code=413, detail="Upload too large")
        chunks.append(chunk)
    return b"".join(chunks)


def _open_image_bytes(name: str, data: bytes) -> Image.Image:
    try:
        img = Image.open(io.BytesIO(data))
        img.load()  # force decode so the underlying buffer can be released
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        return img
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not open '{name}' as image: {e}")


def _dispatch(task_func, *args) -> None:
    """Run a task on the RQ queue, or — when no Redis is configured (local dev /
    single-process free tier) — fire-and-forget in the thread pool. Either way
    the API contract is identical: the route returns a job_id and the client
    polls `GET /api/jobs/{id}` for progress and the final result."""
    if background_enabled():
        get_queue().enqueue(task_func, *args)
    else:
        asyncio.create_task(asyncio.to_thread(task_func, *args))


@app.post("/api/generate-initial-report", status_code=202)
@limiter.limit(LIMIT_GENERATE)
async def generate_initial_report(
    request: Request,
    files: list[UploadFile] = File(...),
    current_user: dict = Depends(get_current_user),
):
    """Upload PDFs or images. Rasterise here, then enqueue the vision pipeline
    as a background job. Returns a job_id immediately (202)."""
    from llm_handler import PdfTooLargeError, pdf_to_images, pil_to_base64
    from tasks import run_initial_report_job

    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    pil_images: list[Image.Image] = []
    file_names: list[str] = []
    total_bytes = 0

    try:
        for upload in files:
            ext = os.path.splitext(upload.filename or "")[1].lower()
            remaining = MAX_TOTAL_UPLOAD_BYTES - total_bytes
            if remaining <= 0:
                raise HTTPException(
                    status_code=413,
                    detail=f"Total upload exceeds {MAX_TOTAL_UPLOAD_BYTES // (1024 * 1024)} MB aggregate limit",
                )
            data = await _read_upload_streaming(upload, remaining)
            total_bytes += len(data)

            if ext in ALLOWED_PDF_EXTS:
                try:
                    # N5: PyMuPDF + PIL are blocking — off-load to a thread.
                    pdf_pages = await asyncio.to_thread(pdf_to_images, data)
                except PdfTooLargeError as e:
                    raise HTTPException(status_code=413, detail=str(e))
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

        if not pil_images:
            raise HTTPException(status_code=400, detail="No usable pages extracted from upload")

        # Encode to base64 here (cheap relative to the LLM call) so the job
        # payload that travels through Redis is the image data the model needs,
        # not the raw multi-MB upload.
        base64_imgs = await asyncio.to_thread(lambda: [pil_to_base64(img) for img in pil_images])

        job_id = create_job(current_user["id"], "initial_report")
        _dispatch(run_initial_report_job, job_id, current_user["id"], base64_imgs, file_names)
        return {"job_id": job_id, "status": "queued"}

    except HTTPException:
        raise
    except Exception:
        log.exception("generate_initial_report enqueue failed")
        raise HTTPException(status_code=500, detail="Could not start initial report job")
    finally:
        for img in pil_images:
            try:
                img.close()
            except Exception:
                pass


@app.post("/api/generate-final-report", status_code=202)
@limiter.limit(LIMIT_GENERATE)
async def generate_final_report(
    request: Request,
    initial_report: str = Form(...),
    user_input: str = Form(...),
    drawing_type: str = Form("foundation"),
    report_id: str = Form(""),
    assumed_values: str = Form(""),
    current_user: dict = Depends(get_current_user),
):
    """Enqueue the multi-stage RAG + reasoning pipeline. Returns a job_id (202)."""
    import json as _json

    from tasks import run_final_report_job

    if not initial_report.strip() or not user_input.strip():
        raise HTTPException(
            status_code=400,
            detail="Both initial_report and user_input are required",
        )

    if report_id and not _is_uuid(report_id):
        raise HTTPException(status_code=400, detail="report_id must be a valid UUID")

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
        job_id = create_job(current_user["id"], "final_report", report_id=report_id or None)
        _dispatch(
            run_final_report_job,
            job_id,
            current_user["id"],
            initial_report,
            combined_user_input,
            drawing_type,
            report_id,
        )
        return {"job_id": job_id, "status": "queued"}
    except HTTPException:
        raise
    except Exception:
        log.exception("generate_final_report enqueue failed")
        raise HTTPException(status_code=500, detail="Could not start final report job")


@app.get("/api/jobs/{job_id}")
@limiter.limit(LIMIT_JOBS)
async def get_job_status(
    request: Request,
    job_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Poll a background job. Returns status (queued|started|finished|failed),
    progress (0-100), a human stage label, and — when finished — the result."""
    if not _is_uuid(job_id):
        raise HTTPException(status_code=400, detail="job_id must be a valid UUID")
    try:
        job = get_job(job_id, current_user["id"])
    except Exception:
        log.exception("get_job_status failed")
        raise HTTPException(status_code=500, detail="Could not fetch job")
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job": job}


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
        return await asyncio.to_thread(do_validate, body.missing_fields, body.user_answers)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception:
        log.exception("validate_input failed")
        raise HTTPException(status_code=500, detail="Validation failed")


# ─── RAG Query API (authenticated) ──────────────────────────────────────────

@app.get("/api/rag/query")
@limiter.limit(LIMIT_QUERY)
async def rag_query(
    request: Request,
    q: str,
    k: int = 5,
    content_type: Optional[str] = None,
    element_type: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query string 'q' is required")

    try:
        vectordb = get_vectordb()
        embedding_model = get_embedding_model()

        where: dict[str, str] = {}
        if content_type and content_type in ALLOWED_RAG_CONTENT_TYPES:
            where["content_type"] = content_type
        if element_type and element_type in {"foundation", "slab", "beam", "column", "general"}:
            where["element_type"] = element_type

        effective_k = min(k, MAX_RAG_RESULTS)
        results = await asyncio.to_thread(
            vectordb.query_by_text,
            q,
            embedding_model,
            effective_k,
            where or None,
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
@limiter.limit(LIMIT_QUERY)
async def download_pdf(
    request: Request,
    markdown_content: str = Form(...),
    filename: str = Form("compliance_report"),
    current_user: dict = Depends(get_current_user),
):
    """Convert markdown report to PDF and stream as download (no disk write)."""
    safe = _safe_filename(filename, default="compliance_report")
    pdf_filename = f"{safe}.pdf"

    buffer = io.BytesIO()
    success, error_msg = await asyncio.to_thread(markdown_to_pdf, markdown_content, buffer)
    if not success:
        raise HTTPException(status_code=500, detail=error_msg or "PDF conversion failed")

    return Response(
        content=buffer.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": _content_disposition(pdf_filename)},
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
    if not _is_uuid(report_id):
        raise HTTPException(status_code=400, detail="report_id must be a valid UUID")
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
    if not _is_uuid(report_id):
        raise HTTPException(status_code=400, detail="report_id must be a valid UUID")
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
        return {"missing_fields": extract_missing_fields(result.data["initial_report"])}
    except HTTPException:
        raise
    except Exception:
        log.exception("get_report_missing_fields failed")
        raise HTTPException(status_code=500, detail="Could not derive missing fields")


@app.delete("/api/reports/{report_id}")
async def delete_report(report_id: str, current_user: dict = Depends(get_current_user)):
    if not _is_uuid(report_id):
        raise HTTPException(status_code=400, detail="report_id must be a valid UUID")
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
