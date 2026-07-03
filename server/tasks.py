"""RQ task functions.

Each function is enqueued by a route in `main.py` and executed inside the
`worker.py` process. They are deliberately import-light at module scope — the
heavy ML imports (torch, chromadb, sentence-transformers) happen lazily inside
the function body so importing this module from the web process stays cheap.

Every task mirrors its lifecycle into the Supabase `jobs` row via
`jobs.update_job` so the browser can poll a plain authenticated endpoint.
"""
import logging

from database import get_supabase_admin_client
from extractors import extract_missing_fields, extract_quality_assessment
from jobs import update_job

log = logging.getLogger("compliance.tasks")

MAX_SESSION_NAME_LEN = 200


def _fail(job_id: str, exc: Exception) -> None:
    """Record a job failure. ValueError carries our own safe messages (empty
    model completion, malformed prompt); anything else gets a generic message
    so a raw exception string never reaches the client."""
    if isinstance(exc, ValueError):
        message = str(exc) or "Model returned no usable content"
    else:
        message = "Processing failed — please retry"
    log.exception("Job %s failed", job_id)
    update_job(job_id, status="failed", error=message)


def run_initial_report_job(job_id: str, user_id: str, base64_imgs: list[str], file_names: list[str]) -> None:
    """Classify the drawing, run the specialist vision agent, persist the report row."""
    from llm_handler import run_specialist_agent
    from llm_service import classify_drawing_type

    try:
        update_job(job_id, status="started", progress=15, stage="classifying drawing")
        drawing_type = classify_drawing_type(base64_imgs)

        update_job(job_id, progress=40, stage="reading drawing (vision)")
        initial_report = run_specialist_agent(base64_imgs, drawing_type)

        update_job(job_id, progress=80, stage="extracting fields")
        missing_fields = extract_missing_fields(initial_report)
        quality_assessment = extract_quality_assessment(initial_report)

        session_name = ", ".join(file_names)[:MAX_SESSION_NAME_LEN]
        supabase = get_supabase_admin_client()
        db_result = supabase.table("reports").insert({
            "user_id": user_id,
            "session_name": session_name,
            "initial_report": initial_report,
            "drawing_type": drawing_type,
        }).execute()
        if not db_result.data:
            raise ValueError("Could not persist report")
        report_id = db_result.data[0]["id"]

        result = {
            "report": initial_report,
            "drawing_type": drawing_type,
            "missing_fields": missing_fields,
            "file_names": file_names,
            "report_id": report_id,
            "quality_assessment": quality_assessment,
        }
        update_job(job_id, status="finished", progress=100, stage="done",
                   result=result, report_id=report_id)
    except Exception as exc:  # noqa: BLE001 — recorded then re-raised for RQ
        _fail(job_id, exc)
        raise


def run_final_report_job(
    job_id: str,
    user_id: str,
    initial_report: str,
    combined_user_input: str,
    drawing_type: str,
    report_id: str,
) -> None:
    """Run the multi-stage RAG pipeline + reasoning model, update the report row."""
    from embedding_service import get_embedding_model
    from llm_service import generate_compliance_report
    from vector_db import VectorStore

    try:
        update_job(job_id, status="started", progress=20, stage="retrieving IS-code context")
        vectordb = VectorStore(collection_name="is_codes_docs", folder_path="./chroma_db")
        embedding_model = get_embedding_model()

        update_job(job_id, progress=45, stage="reasoning over clauses")
        final_report, rag_ok, rag_low_confidence = generate_compliance_report(
            initial_report,
            combined_user_input,
            drawing_type,
            vectordb,
            embedding_model,
        )

        update_job(job_id, progress=90, stage="saving verdict")
        if report_id:
            supabase = get_supabase_admin_client()
            upd = supabase.table("reports").update({
                "final_report": final_report,
            }).eq("id", report_id).eq("user_id", user_id).execute()
            if not upd.data:
                raise ValueError("Report not found for update")

        result = {
            "report": final_report,
            "report_id": report_id,
            "rag_context_used": rag_ok,
            "rag_confidence_low": rag_low_confidence,
        }
        update_job(job_id, status="finished", progress=100, stage="done",
                   result=result, report_id=report_id)
    except Exception as exc:  # noqa: BLE001
        _fail(job_id, exc)
        raise
