"""Orchestrator, Validator, and final-report RAG agents.

Major design points (see plan v2 for full rationale):
- Embedding queries are *focused* — never the full refinement prompt. BGE
  truncates at 512 tokens, so embedding a 4 000-token report makes the
  embedding meaningless (everyone's query reduces to the same template
  header).
- Multi-query retrieval: one sub-query per compliance row when we can
  parse them out of the previous report. Falls back to a single focused
  query when row parsing fails.
- Drawing-type metadata filter restricts retrieval to chunks tagged with
  the relevant element_type (+ general SP 34 / IS 456 chunks).
- Cross-encoder reranker (see reranker.py) re-scores the merged candidate
  set; MMR optionally diversifies before truncating to top-K.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, NoReturn

from openai import APIError

from openai_client import (
    FINAL_REPORT_MODEL,
    ORCHESTRATOR_MODEL,
    VALIDATOR_MODEL,
    get_openai_client,
)
from reranker import cross_encoder_rerank, is_mmr_enabled, mmr_select

log = logging.getLogger(__name__)

RAG_TOP_N = int(os.getenv("RAG_TOP_N", "40"))
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "10"))
RAG_PER_QUERY_K = int(os.getenv("RAG_PER_QUERY_K", "5"))
RAG_MAX_SUBQUERIES = int(os.getenv("RAG_MAX_SUBQUERIES", "8"))
RAG_MIN_SCORE = float(os.getenv("RAG_MIN_SCORE", "0.0"))


def classify_drawing_type(base64_images: list[str]) -> str:
    """Classify the drawing type from images. Returns 'foundation' | 'slab' | 'beam' | 'column' | 'unknown'."""
    from prompt import ORCHESTRATOR_PROMPT

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": ORCHESTRATOR_PROMPT},
            ] + [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{img}", "detail": "low"},
                }
                for img in base64_images
            ],
        }
    ]

    log.info("Orchestrator: classifying drawing type")
    try:
        response = get_openai_client().chat.completions.create(
            model=ORCHESTRATOR_MODEL,
            messages=messages,
            temperature=0,
            max_tokens=100,
            response_format={"type": "json_object"},
        )
    except Exception:
        log.exception("Orchestrator classification failed")
        return "unknown"

    raw = (response.choices[0].message.content or "").strip()
    log.debug("Orchestrator raw response: %s", raw)

    drawing_type = "unknown"
    try:
        result = json.loads(raw)
        drawing_type = str(result.get("type", "unknown")).lower().strip()
    except json.JSONDecodeError:
        match = re.search(r'"type"\s*:\s*"(\w+)"', raw)
        drawing_type = match.group(1).lower().strip() if match else "unknown"

    valid_types = {"foundation", "slab", "beam", "column", "unknown"}
    if drawing_type not in valid_types:
        log.warning("Unexpected drawing type '%s', defaulting to unknown.", drawing_type)
        drawing_type = "unknown"

    log.info("Orchestrator: classified as '%s'", drawing_type)
    return drawing_type


def validate_user_input(missing_fields: list[str], user_answers: dict) -> dict:
    """Validate user-supplied answers. Returns {valid, invalid_fields, assumed_values}.

    Infrastructure errors (APIError, network) are re-raised so the caller
    returns a 5xx rather than silently passing invalid data downstream.
    Only JSON-parse problems fall through with valid=True.
    """
    from prompt import VALIDATOR_PROMPT

    fields_json = json.dumps(missing_fields, indent=2)
    answers_json = json.dumps(user_answers, indent=2, ensure_ascii=False)
    prompt = VALIDATOR_PROMPT.format(fields_json=fields_json, answers_json=answers_json)

    log.info("Validator: checking user-supplied data")
    try:
        response = get_openai_client().chat.completions.create(
            model=VALIDATOR_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are a strict data validation agent. Respond ONLY with valid JSON.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            max_tokens=1024,
            response_format={"type": "json_object"},
        )
    except APIError as e:
        _handle_api_error(e)

    raw = (response.choices[0].message.content or "").strip()
    log.debug("Validator raw response: %s", raw)

    result: dict = {}
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        json_match = re.search(r"\{.*\}", raw, re.DOTALL)
        if json_match:
            try:
                result = json.loads(json_match.group())
            except json.JSONDecodeError:
                log.warning("Validator output not parseable JSON — treating input as valid.")
                result = {}

    assumed = result.get("assumed_values", {})
    log.info(
        "Validator: valid=%s invalid=%d assumed=%d",
        result.get("valid", True),
        len(result.get("invalid_fields", [])),
        len(assumed),
    )
    return {
        "valid": result.get("valid", True),
        "invalid_fields": result.get("invalid_fields", []),
        "assumed_values": assumed,
    }


# ─── Retrieval helpers ────────────────────────────────────────────────────────

_ROW_RE = re.compile(r"^\|(.*)\|\s*$")


def _extract_compliance_rows(previous_analysis: str) -> list[str]:
    """Pull human-readable criterion strings out of the Phase-2 / Phase-3 tables.

    A row like
        | 5 | Clear Cover — Column | IS 456 Cl. 26.4 | ... | Compliant |
    yields the sub-query string `"Clear Cover — Column IS 456 Cl. 26.4"`.
    """
    subqueries: list[str] = []
    seen: set[str] = set()
    for raw_line in previous_analysis.splitlines():
        line = raw_line.strip()
        m = _ROW_RE.match(line)
        if not m:
            continue
        cells = [c.strip().replace("**", "") for c in m.group(1).split("|")]
        cells = [c for c in cells if c]
        if len(cells) < 3:
            continue
        # Skip header / separator rows.
        joined = " ".join(cells).lower()
        if all(re.fullmatch(r"[-: ]+", c) for c in cells):
            continue
        if "criterion" in joined and "status" in joined:
            continue

        # First non-numeric cell = criterion; locate an IS clause if present.
        criterion = next(
            (c for c in cells if not c.isdigit() and not re.fullmatch(r"P\d+\.?", c)),
            "",
        )
        if not criterion or len(criterion) > 120:
            continue
        is_ref = next(
            (c for c in cells if re.search(r"IS\s*\d+|SP\s*\d+|Cl\.\s*\d", c)),
            "",
        )
        sub = f"{criterion} {is_ref}".strip()
        key = sub.lower()
        if key not in seen:
            seen.add(key)
            subqueries.append(sub)
    return subqueries


def _build_focused_query(
    drawing_type: str,
    user_input: str,
    fallback_topics: list[str],
) -> str:
    """Single short query used when multi-query is not viable."""
    topics = ", ".join(fallback_topics[:10]) if fallback_topics else ""
    head = (user_input or "").strip()[:500]
    return (
        f"{drawing_type} RCC compliance "
        f"{topics} {head}".strip()
    )


def _retrieve_with_context(
    *,
    vectordb,
    embedding_model,
    drawing_type: str,
    previous_analysis: str,
    user_input: str,
) -> tuple[list[dict[str, Any]], bool, bool]:
    """Run the full retrieval pipeline. Returns (results, rag_succeeded, low_confidence)."""
    where = None
    if drawing_type and drawing_type != "unknown":
        where = {"element_type": {"$in": [drawing_type, "general"]}}

    subqueries = _extract_compliance_rows(previous_analysis)
    use_multi = 0 < len(subqueries) <= RAG_MAX_SUBQUERIES

    candidate_map: dict[str, dict[str, Any]] = {}
    primary_query_embedding: list[float] | None = None

    try:
        if use_multi:
            log.info("RAG: multi-query over %d compliance rows", len(subqueries))
            for sq in subqueries[:RAG_MAX_SUBQUERIES]:
                emb = embedding_model.embed_query(f"{drawing_type} {sq}")
                primary_query_embedding = primary_query_embedding or emb
                hits = vectordb.query(
                    [emb],
                    n_results=RAG_PER_QUERY_K,
                    where=where,
                    include_embeddings=is_mmr_enabled(),
                )
                for h in hits:
                    h_id = h["id"]
                    if h_id not in candidate_map or h.get("score", 1e9) < candidate_map[h_id].get("score", 1e9):
                        candidate_map[h_id] = h
        else:
            log.info("RAG: focused single-query (multi-query unavailable, sub=%d)", len(subqueries))
            query = _build_focused_query(drawing_type, user_input, subqueries)
            log.debug("Focused query: %s", query[:200])
            emb = embedding_model.embed_query(query)
            primary_query_embedding = emb
            for h in vectordb.query(
                [emb],
                n_results=RAG_TOP_N,
                where=where,
                include_embeddings=is_mmr_enabled(),
            ):
                candidate_map[h["id"]] = h

        candidates = list(candidate_map.values())
        if not candidates:
            log.warning("RAG: no candidates retrieved.")
            return [], False, True

        # Cross-encoder rerank against a single representative query string.
        rerank_query = _build_focused_query(drawing_type, user_input, subqueries)
        reranked = cross_encoder_rerank(rerank_query, candidates, top_k=RAG_TOP_N)

        # Diversify and truncate to RAG_TOP_K.
        if primary_query_embedding is not None:
            final = mmr_select(primary_query_embedding, reranked, top_k=RAG_TOP_K)
        else:
            final = reranked[:RAG_TOP_K]

        # Low-confidence detection — uses rerank_score when present.
        scored = [r.get("rerank_score") for r in final if r.get("rerank_score") is not None]
        low_confidence = bool(scored) and max(scored) < RAG_MIN_SCORE
        log.info(
            "RAG: candidates=%d reranked=%d final=%d low_confidence=%s",
            len(candidates), len(reranked), len(final), low_confidence,
        )
        return final, True, low_confidence

    except Exception:
        log.exception("RAG retrieval failed — proceeding without context")
        return [], False, True


def _format_context(results: list[dict[str, Any]]) -> str:
    if not results:
        return "No relevant IS code context found."
    return "\n\n".join(
        f"[Source: {(r.get('metadata') or {}).get('source_file', 'N/A')}, "
        f"Section: {(r.get('metadata') or {}).get('section_number', 'N/A')}, "
        f"Clause: {(r.get('metadata') or {}).get('clause_id', 'N/A')}, "
        f"Element: {(r.get('metadata') or {}).get('element_type', 'general')}]\n"
        f"{r.get('document', '')}"
        for r in results
    )


# ─── Status-cell-only "Compliant uses assumption" check ───────────────────────


def _row_is_compliant_with_assumption(row: str) -> bool:
    """True if a markdown table row's STATUS cell is bare-Compliant AND
    any earlier cell references assumption language."""
    cells = [c.strip() for c in row.split("|") if c.strip()]
    if len(cells) < 2:
        return False
    status_raw = cells[-1].replace("**", "")
    status_norm = re.sub(r"[^A-Za-z ]", "", status_raw).lower().strip()
    if "conditionally" in status_norm:
        return False
    if "non" in status_norm or "not" in status_norm:
        return False
    if "compliant" not in status_norm:
        return False
    body = " | ".join(cells[:-1])
    return bool(re.search(r"\b(assumed|generally taken)\b", body, re.IGNORECASE))


def generate_compliance_report(
    previous_analysis: str,
    user_input: str,
    drawing_type: str,
    vectordb,
    embedding_model,
    k: int = 15,  # kept for backward-compat; new pipeline uses RAG_TOP_N/RAG_TOP_K
) -> tuple[str, bool, bool]:
    """Generate the final compliance report using RAG + reasoning model.

    Returns:
        (report_markdown, rag_succeeded, rag_confidence_low).
    """
    from prompt import REFINEMENT_PROMPT_TEMPLATE

    # N2 fix: switch from str.format to str.replace so `{` / `}` in the
    # source content (LaTeX, JSON examples, etc.) can no longer crash us.
    refinement_prompt = (
        REFINEMENT_PROMPT_TEMPLATE
        .replace("<<DRAWING_TYPE>>", drawing_type or "unknown")
        .replace("<<PREVIOUS_ANALYSIS>>", previous_analysis)
        .replace("<<USER_INPUT>>", user_input)
    )

    final_results, rag_ok, low_confidence = _retrieve_with_context(
        vectordb=vectordb,
        embedding_model=embedding_model,
        drawing_type=drawing_type,
        previous_analysis=previous_analysis,
        user_input=user_input,
    )
    context_texts = _format_context(final_results)

    system_prompt = """\
You are a Senior Indian Civil Engineer specialising in RCC compliance verification.

CORE ROLE:
You are ONLY a verification engine. You are NOT allowed to design or assume values.

MANDATORY RULES:
1. NEVER assume, infer, or generate missing values.
2. Use ONLY explicitly provided data from:
   - Drawing
   - User Input
3. If data is missing → write 'NOT PROVIDED'.
4. If validation cannot be performed → status = 'Not Verifiable'.
5. NEVER mark a parameter as Compliant using assumed values. Rows backed by
   [USER-ASSUMED] values must be marked 'Conditionally Compliant'.

OUTPUT RULES:
- Every compliance row must include: Extracted Value | Source | IS Code Reference | Status
- Source column tags: [DRAWING] | [USER-PROVIDED] | [USER-ASSUMED] | [NOT PROVIDED]
- Allowed statuses: Compliant | Conditionally Compliant | Non-Compliant | Not Verifiable | Missing Information | Not Applicable
- Output must be strict Markdown.
- Include a final section '## IS Code References Used' grouped by code.

CRITICAL:
If any value is assumed and used to justify a 'Compliant' verdict, the output is INVALID.

VISUAL DETECTION RULES:
- Actively inspect geometry in the drawing.
- If two structural elements (footings, beams, columns) overlap, intersect, or
  clash in plan → mark as Non-Compliant.
- Overlap includes shared area, touching boundaries with no clearance, or one
  element intruding into another.
- Do not ignore small overlaps — partial intersection is Non-Compliant.
- If image clarity is insufficient → mark as Not Verifiable, never 'No issue'.

UNIFORM MEMBER SIZE RULES:
- BEAMS: uniform size across all spans → Non-Compliant (loads/spans vary).
- FOUNDATIONS: uniform footing sizes → Non-Compliant (column loads differ).
- SLABS: uniform thickness/reinforcement → Acceptable if spans and loading are
  similar; Non-Compliant if spans/loading vary significantly and reinforcement
  is still uniform.
"""

    user_prompt = (
        f"{refinement_prompt}\n\n"
        "---\n\n"
        f"## Retrieved IS Code Context (from knowledge base)\n{context_texts}"
    )

    log.info("Calling %s for final report generation", FINAL_REPORT_MODEL)
    try:
        response = get_openai_client().chat.completions.create(
            model=FINAL_REPORT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_completion_tokens=8000,
        )
    except APIError as e:
        _handle_api_error(e)

    # N13: o4-mini can return empty content when reasoning_tokens consume
    # the budget — surface that specifically rather than as a generic 500.
    choice = response.choices[0]
    report = choice.message.content
    if not report or not report.strip():
        finish = getattr(choice, "finish_reason", "?")
        raise ValueError(
            f"Reasoning model returned no content (finish_reason={finish}). "
            "Likely ran out of completion tokens — please retry."
        )

    # N4: status cell ONLY — bare "Compliant" + assumption language = bad.
    bad_rows = [
        line for line in report.splitlines()
        if line.startswith("|") and _row_is_compliant_with_assumption(line)
    ]
    if bad_rows:
        raise ValueError(
            f"Model marked {len(bad_rows)} row(s) Compliant using assumption language. "
            f"First offender: {bad_rows[0][:120]}…"
        )

    if not re.search(r"^\|[^\n]*\bSource\b[^\n]*\|", report, re.MULTILINE):
        raise ValueError("Output has no Markdown table with a 'Source' column.")

    log.info("Final compliance report generated.")
    return report, rag_ok, low_confidence


def _handle_api_error(e: APIError) -> NoReturn:
    """Translate APIError into a user-friendly ValueError."""
    code = getattr(e, "status_code", None)
    msg = str(e)
    if code == 401 or "401" in msg or "Unauthorized" in msg:
        raise ValueError(
            "Invalid OpenAI API key. Check OPENAI_API_KEY in your .env file."
        ) from e
    if code == 429 or "429" in msg or "quota" in msg.lower():
        raise ValueError(
            "OpenAI rate limit or quota exceeded. Check your usage at platform.openai.com."
        ) from e
    if code == 404 or "404" in msg:
        raise ValueError(
            f"Model not found: '{FINAL_REPORT_MODEL}'. Check the model ID is correct."
        ) from e
    raise ValueError(f"OpenAI API error: {msg}") from e
