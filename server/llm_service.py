import json
import logging
import re
from typing import NoReturn

from openai import APIError

from openai_client import (
    FINAL_REPORT_MODEL,
    ORCHESTRATOR_MODEL,
    VALIDATOR_MODEL,
    get_openai_client,
)

log = logging.getLogger(__name__)


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
    """Validate user-supplied answers. Returns {valid, invalid_fields, assumed_values}."""
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
    except Exception:
        log.exception("Validator error — treating input as valid.")
        return {"valid": True, "invalid_fields": [], "assumed_values": {}}

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


def generate_compliance_report(
    previous_analysis: str,
    user_input: str,
    drawing_type: str,
    vectordb,
    embedding_model,
    k: int = 15,
) -> tuple[str, bool]:
    """Generate the final compliance report using RAG + reasoning model.

    Returns:
        (report_markdown, rag_succeeded). When rag_succeeded is False the caller
        can warn the user that the verdict was produced without IS-code context.
    """
    from prompt import REFINEMENT_PROMPT_TEMPLATE

    refinement_prompt = REFINEMENT_PROMPT_TEMPLATE.format(
        drawing_type=drawing_type,
        previous_analysis=previous_analysis,
        user_input=user_input,
    )

    log.info("Embedding query and retrieving IS code context")
    rag_succeeded = False
    try:
        query_embedding = embedding_model.embed_query(refinement_prompt)
        retrieved = vectordb.query([query_embedding], n_results=k)
        if retrieved:
            context_texts = "\n\n".join(
                f"[Source: {(r.get('metadata') or {}).get('source_file', 'N/A')}, "
                f"Section: {(r.get('metadata') or {}).get('section_number', 'N/A')}, "
                f"Clause: {(r.get('metadata') or {}).get('clause_id', 'N/A')}, "
                f"Content Type: {(r.get('metadata') or {}).get('content_type', 'N/A')}]\n{r.get('document', '')}"
                for r in retrieved
            )
            rag_succeeded = True
        else:
            log.warning("No IS code context retrieved — proceeding without RAG context.")
            context_texts = "No relevant IS code context found."
    except Exception:
        log.exception("RAG retrieval failed — proceeding without context.")
        context_texts = "IS code context unavailable."

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

    report = response.choices[0].message.content
    if not report:
        raise ValueError("Empty response from compliance model — please retry.")

    # Post validation: a row marked "Compliant" must not also rely on assumption
    # language. Conditionally-Compliant rows are allowed to.
    bad_rows = []
    for line in report.splitlines():
        if not line.startswith("|"):
            continue
        if "Conditionally" in line:
            continue
        if not re.search(r"\bCompliant\b", line):
            continue
        if re.search(r"\b(assumed|generally taken)\b", line, re.IGNORECASE):
            bad_rows.append(line)
    if bad_rows:
        raise ValueError(
            f"Model marked {len(bad_rows)} row(s) Compliant using assumption language. "
            f"First offender: {bad_rows[0][:120]}…"
        )

    if not re.search(r"^\|[^\n]*\bSource\b[^\n]*\|", report, re.MULTILINE):
        raise ValueError("Output has no Markdown table with a 'Source' column.")

    log.info("Final compliance report generated.")
    return report, rag_succeeded


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
