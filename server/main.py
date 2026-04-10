import os
import time
import re
import io
import json
import shutil
from typing import Optional
from pydantic import BaseModel

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from auth import router as auth_router, get_current_user
from database import get_supabase_admin_client
from PIL import Image

# Load environment variables
load_dotenv()

# --- Configuration ---
REPORTS_DIR = "reports"
UPLOADS_DIR = "uploads"
FIRST_EXTRACT_DIR = "first_extract"
RESULT_DIR = "RESULT"
os.makedirs(REPORTS_DIR, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(FIRST_EXTRACT_DIR, exist_ok=True)
os.makedirs(RESULT_DIR, exist_ok=True)

# --- Lazy-loaded services (heavy imports) ---
_vectordb = None
_embedding_model = None


def get_vectordb():
    global _vectordb
    if _vectordb is None:
        from vector_db import VectorStore
        _vectordb = VectorStore(collection_name="is_codes_docs", folder_path="./chroma_db")
    return _vectordb


def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        from embedding_service import embedding_model
        _embedding_model = embedding_model
    return _embedding_model


# --- FastAPI App ---
app = FastAPI(
    title="Structural Compliance Checker",
    description="AI-powered multi-agent RCC structural drawing compliance analysis (Foundations, Slabs, Beams)",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)

# ---------- PDF-to-Markdown helper ----------
def markdown_to_pdf(markdown_text: str, output_path: str):
    """
    Converts markdown text to PDF using reportlab.
    Returns (success: bool, error_message: str or None)
    """
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib import colors
        import html as html_mod

        doc = SimpleDocTemplate(
            output_path, pagesize=letter,
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
            table_data = []
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

        while i < len(lines):
            line = lines[i].rstrip()

            if not line.strip():
                if in_list and list_items:
                    for item in list_items:
                        story.append(Paragraph(f"• {convert_inline(item)}", normal_style))
                    list_items = []
                    in_list = False
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
                if in_list and list_items:
                    for item in list_items:
                        story.append(Paragraph(f"• {convert_inline(item)}", normal_style))
                    list_items, in_list = [], False
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
                if in_list and list_items:
                    for item in list_items:
                        story.append(Paragraph(f"• {convert_inline(item)}", normal_style))
                    list_items, in_list = [], False
                story.append(Paragraph(convert_inline(re.sub(r'^\d+\.\s+', '', line)), normal_style))
                i += 1
                continue

            if in_list and list_items:
                for item in list_items:
                    story.append(Paragraph(f"• {convert_inline(item)}", normal_style))
                list_items, in_list = [], False

            story.append(Paragraph(convert_inline(line), normal_style))
            i += 1

        if in_list and list_items:
            for item in list_items:
                story.append(Paragraph(f"• {convert_inline(item)}", normal_style))

        doc.build(story)
        return True, None
    except Exception as e:
        return False, f"PDF conversion failed: {str(e)}"


#--------- missing field extractor----------
def _extract_missing_fields(report: str) -> list[str]:
    """Extract missing/non-compliant fields from both the compliance table AND Step 5.
    
    Uses a dual-extraction approach:
      1. Scan the compliance table (Step 2 & 3) for rows whose Status column
         contains 'Missing Information', 'Cannot Verify', or 'Non-Compliant'.
      2. Parse the 'Step 5: Report Missing or Wrong Information' section.
      3. Merge both sets, deduplicating by normalised name.
    """
    missing_from_table = []
    missing_from_step5 = []

    # ── 1. Extract from the compliance table ──────────────────────
    FLAG_STATUSES = {'missing information', 'cannot verify', 'non-compliant'}
    for line in report.splitlines():
        stripped = line.strip()
        # Table rows look like: | **1. Grade of Concrete** | ... | ... | Missing Information |
        if not stripped.startswith('|'):
            continue
        cells = [c.strip() for c in stripped.split('|')]
        # split('|') gives ['', cell1, cell2, ..., ''] for a well-formed row
        cells = [c for c in cells if c]  # remove empties
        if len(cells) < 4:
            continue
        # Skip the header / separator rows
        status_cell = cells[-1].strip().replace('**', '').strip()
        if status_cell.lower() in FLAG_STATUSES:
            # The criteria name is in the first cell
            criteria = cells[0].strip().replace('**', '').strip()
            # Strip leading number like "1. " or "12. "
            criteria = re.sub(r'^\d+\.\s*', '', criteria).strip()
            if criteria and criteria.lower() not in ('criteria', 'none', 'n/a', 'nil', '---'):
                missing_from_table.append(criteria)

    # ── 2. Extract from Step 5 section ────────────────────────────
    in_section = False
    for line in report.splitlines():
        stripped = line.strip()
        # Detect the section header (Step 5: Report Missing or Wrong Information)
        if stripped.startswith('#') and re.search(r'(step\s*5|missing.*(?:wrong|information))', stripped, re.IGNORECASE):
            in_section = True
            continue
        # Stop at next heading or Summary section
        if in_section and stripped.startswith('#'):
            break
        if not in_section:
            continue
        # Skip empty, table, and separator lines
        if not stripped or stripped.startswith('|') or re.match(r'^---+$|^===+$|^\*\*\*+$', stripped):
            continue
        # Remove list markers (1., 2., -, *)
        clean = re.sub(r'^\d+\.\s*|^[-*+]\s*', '', stripped).strip()
        # Strip markdown bold markers
        clean = clean.replace('**', '')
        if not clean or clean.lower() in ('none', 'n/a', 'nil'):
            continue

        if ':' in clean:
            parts = clean.split(':', 1)
            prefix = parts[0].strip()
            detail = parts[1].strip() if len(parts) > 1 else ''

            category_keywords = (
                'missing information', 'cannot verify', 'non-compliant',
                'missing', 'wrong', 'document type', 'not applicable',
            )
            if prefix.lower() in category_keywords:
                if detail:
                    # Handle comma-separated lists, ignoring commas inside parentheses
                    items = [item.strip().rstrip('.') for item in re.split(r',\s*(?![^()]*\))', detail)]
                    for item in items:
                        item = re.sub(r'(?i)\s*due to lack of explicit data\s*', '', item).strip()
                        # Remove parenthetical suffixes (e.g., "(M20 assumed for design, ...)") 
                        item = re.sub(r'\s*\(.*?\)\s*$', '', item).strip()
                        # Skip artifacts from splitting (e.g., "and specific ...")
                        if item.lower().startswith('and '):
                            item = item[4:].strip()
                        # Skip non-fillable items like "No dedicated NOTES section ..."
                        if re.search(r'(?i)notes?\s*section|no\s+dedicated', item):
                            continue
                        if item and item.lower() not in ('none', 'n/a', 'nil'):
                            missing_from_step5.append(item)
            else:
                # The prefix itself is the field name (e.g., "Clear Cover: Missing")
                # Skip non-fillable items
                if not re.search(r'(?i)notes?\s*section|no\s+dedicated', prefix):
                    missing_from_step5.append(prefix)
        else:
            # Skip non-fillable items
            if not re.search(r'(?i)notes?\s*section|no\s+dedicated', clean):
                missing_from_step5.append(clean)

    # ── 2b. Check Step 0 for missing site location ──────────────
    location_already_listed = any(
        'location' in item.lower() for item in missing_from_step5 + missing_from_table
    )
    if not location_already_listed:
        for line in report.splitlines():
            stripped = line.strip()
            # Look for Step 0.2 lines that flag location as missing
            if re.search(r'0\.2', stripped) and re.search(r'(?i)missing|not\s+(mentioned|found|specified|provided|available)', stripped):
                if re.search(r'(?i)(site\s*)?location', stripped):
                    missing_from_step5.append('Site Location')
                    break

    # ── 3. Merge & deduplicate ────────────────────────────────────
    seen = set()
    merged = []

    def _normalise(s: str) -> str:
        """Lowercase, strip punctuation/spaces for dedup comparison."""
        return re.sub(r'[^a-z0-9]', '', s.lower())

    # Step 5 items first (they tend to have better descriptions)
    for item in missing_from_step5:
        key = _normalise(item)
        if key and key not in seen:
            seen.add(key)
            merged.append(item)

    # Then table items (fill in anything Step 5 missed)
    for item in missing_from_table:
        key = _normalise(item)
        if key and key not in seen:
            # Also check if any existing key contains this one or vice versa
            already_covered = False
            for existing_key in seen:
                if key in existing_key or existing_key in key:
                    already_covered = True
                    break
            if not already_covered:
                seen.add(key)
                merged.append(item)

    print("\n\n[Missing Fields] from table:", missing_from_table)
    print("[Missing Fields] from step5:", missing_from_step5)
    print("[Missing Fields] merged:", merged)
    return merged

# -------- Routes -------- 
@app.get("/")
async def root():
    return {"message": "Foundation Compliance Check API", "status": "running"}


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload a PDF or image file for analysis."""
    allowed_extensions = {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    timestamp = int(time.time())
    safe_name = f"{timestamp}_{file.filename}"
    file_path = os.path.join(UPLOADS_DIR, safe_name)

    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    file_type = "pdf" if ext == ".pdf" else "image"
    return {
        "filename": file.filename,
        "saved_as": safe_name,
        "file_type": file_type,
        "path": file_path,
    }


@app.post("/api/generate-initial-report")
async def generate_initial_report(
    files: list[UploadFile] = File(...),
    current_user: dict = Depends(get_current_user),
):
    """
    Upload one or more files (PDF or images).
    1. Orchestrator classifies the drawing type (foundation/slab/beam).
    2. Specialist agent generates the initial compliance report.
    3. Missing fields are extracted from the report.
    Requires authentication.
    """
    from llm_handler import pdf_to_images, pil_to_base64, run_specialist_agent
    from llm_service import classify_drawing_type

    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    first_ext = os.path.splitext(files[0].filename or "")[1].lower()

    try:
        # --- Step 1: Convert to PIL images ---
        pil_images = []
        file_names = []

        if first_ext == ".pdf":
            pdf_bytes = await files[0].read()
            tmp_path = os.path.join(UPLOADS_DIR, f"{int(time.time())}_{files[0].filename}")
            with open(tmp_path, "wb") as f:
                f.write(pdf_bytes)
            pil_images = pdf_to_images(tmp_path)
            file_names = [files[0].filename]
        else:
            for upload in files:
                img_bytes = await upload.read()
                pil_img = Image.open(io.BytesIO(img_bytes))
                if pil_img.mode in ("RGBA", "LA", "P"):
                    pil_img = pil_img.convert("RGB")
                pil_images.append(pil_img)
                file_names.append(upload.filename)

        # --- Step 2: Orchestrator classifies drawing type ---
        base64_imgs = [pil_to_base64(img) for img in pil_images]
        drawing_type = classify_drawing_type(base64_imgs)

        # --- Step 3: Specialist agent generates initial report ---
        initial_report = run_specialist_agent(pil_images, drawing_type)

        # --- Step 4: Extract missing fields from report ---
        missing_fields = _extract_missing_fields(initial_report)

        # Persist to disk
        timestamp = int(time.time())
        report_filename = f"initial_report_{timestamp}.md"
        report_path = os.path.join(FIRST_EXTRACT_DIR, report_filename)
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(initial_report)

        # Save to Supabase DB (with drawing_type)
        session_name = ", ".join(file_names)
        supabase = get_supabase_admin_client()
        db_result = supabase.table("reports").insert({
            "user_id": current_user["id"],
            "session_name": session_name,
            "initial_report": initial_report,
            "drawing_type": drawing_type,
        }).execute()

        report_id = db_result.data[0]["id"] if db_result.data else None

        return {
            "report": initial_report,
            "drawing_type": drawing_type,
            "missing_fields": missing_fields,
            "file_names": file_names,
            "saved_report": report_filename,
            "report_id": report_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/generate-final-report")
async def generate_final_report(
    initial_report: str = Form(...),
    user_input: str = Form(...),
    drawing_type: str = Form("foundation"),
    report_id: str = Form(""),
    current_user: dict = Depends(get_current_user),
):
    """
    Generate the final compliance report using RAG.
    Expects the initial_report markdown, user_input text, and drawing_type.
    Requires authentication.
    """
    from llm_service import generate_compliance_report
    from prompt import REFINEMENT_PROMPT_TEMPLATE

    if not initial_report.strip() or not user_input.strip():
        raise HTTPException(
            status_code=400,
            detail="Both initial_report and user_input are required",
        )

    try:
        refinement_prompt = REFINEMENT_PROMPT_TEMPLATE.format(
            drawing_type=drawing_type,
            previous_analysis=initial_report,
            user_input=user_input,
        )

        vectordb = get_vectordb()
        embedding_model = get_embedding_model()

        final_report = generate_compliance_report(
            vectordb=vectordb,
            embedding_model=embedding_model,
            Initial_report=refinement_prompt,
            previous_analysis=initial_report,
            user_input=user_input,
        )

        # Persist to disk
        timestamp = int(time.time())
        report_filename = f"final_report_{timestamp}.md"
        report_path = os.path.join(RESULT_DIR, report_filename)
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(final_report)

        # Update Supabase DB with final report
        if report_id:
            supabase = get_supabase_admin_client()
            supabase.table("reports").update({
                "final_report": final_report,
            }).eq("id", report_id).eq("user_id", current_user["id"]).execute()

        return {
            "report": final_report,
            "saved_report": report_filename,
            "report_id": report_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ────────────────────────────────────────────────────────────
# Validator Agent API
# ────────────────────────────────────────────────────────────

class ValidateInputRequest(BaseModel):
    missing_fields: list[str]
    user_answers: dict
    report_id: str = ""

@app.post("/api/validate-input")
async def validate_input(
    body: ValidateInputRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Validate user-supplied answers for missing data fields.
    Returns {valid: bool, invalid_fields: list}.
    Requires authentication.
    """
    from llm_service import validate_user_input as do_validate

    if not body.missing_fields or not body.user_answers:
        raise HTTPException(
            status_code=400,
            detail="Both missing_fields and user_answers are required",
        )

    try:
        result = do_validate(body.missing_fields, body.user_answers)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ────────────────────────────────────────────────────────────
# RAG Query API
# ────────────────────────────────────────────────────────────

@app.get("/api/rag/query")
async def rag_query(
    q: str,
    k: int = 5,
    content_type: Optional[str] = None,
):
    """
    Query the IS codes vector database directly.
    Returns the top-k matching chunks.
    """
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query string 'q' is required")

    try:
        vectordb = get_vectordb()
        embedding_model = get_embedding_model()

        where = None
        if content_type and content_type in ("text", "table", "image_description"):
            where = {"content_type": content_type}

        results = vectordb.query_by_text(
            query_text=q,
            embedding_model=embedding_model,
            n_results=min(k, 20),  # cap at 20
            where=where,
        )

        return {
            "query": q,
            "count": len(results),
            "results": results,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/download-pdf")
async def download_pdf(
    markdown_content: str = Form(...),
    filename: str = Form("compliance_report"),
):
    """Convert markdown report to PDF and return as download."""
    timestamp = int(time.time())
    pdf_filename = f"{filename}_{timestamp}.pdf"
    pdf_path = os.path.join(REPORTS_DIR, pdf_filename)

    success, error_msg = markdown_to_pdf(markdown_content, pdf_path)
    if not success:
        raise HTTPException(status_code=500, detail=error_msg or "PDF conversion failed")

    def iterfile():
        with open(pdf_path, "rb") as f:
            yield from f

    return StreamingResponse(
        iterfile(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{pdf_filename}"'},
    )


# ────────────────────────────────────────────────────────────
# History / Reports API
# ────────────────────────────────────────────────────────────

@app.get("/api/reports")
async def list_reports(current_user: dict = Depends(get_current_user)):
    """Get all reports for the authenticated user, newest first."""
    try:
        supabase = get_supabase_admin_client()
        result = supabase.table("reports") \
            .select("id, session_name, drawing_type, initial_report, final_report, created_at") \
            .eq("user_id", current_user["id"]) \
            .order("created_at", desc=True) \
            .execute()
        return {"reports": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/reports/{report_id}")
async def get_report(report_id: str, current_user: dict = Depends(get_current_user)):
    """Get a single report by ID."""
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
