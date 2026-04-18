import json
import re
import os
from openai import OpenAI, APIError
from dotenv import load_dotenv

load_dotenv()

_api_key = os.getenv("OPENAI_API_KEY")
if not _api_key:
    raise ValueError("OPENAI_API_KEY not found in environment variables. Add it to your .env file.")

client = OpenAI(api_key=_api_key)

# ── Model routing ────────────────────────────────────────────────────────────
# gpt-4o-mini  — fast cheap model for classification and validation (text only).
# o4-mini      — reasoning model for final report generation. Compliance checking
#                is a multi-step rule-matching task; reasoning models handle this
#                significantly better than standard LLMs.
ORCHESTRATOR_MODEL = "gpt-4o-mini"
VALIDATOR_MODEL    = "gpt-4o-mini"
FINAL_REPORT_MODEL = "o4-mini"


def classify_drawing_type(base64_images: list[str]) -> str:
    """Classify the drawing type from images using the Orchestrator prompt.

    Returns one of: "foundation", "slab", "beam", "column", "unknown".
    """
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

    print("🔍 Orchestrator: classifying drawing type...")
    try:
        response = client.chat.completions.create(
            model=ORCHESTRATOR_MODEL,
            messages=messages,
            temperature=0,
            max_tokens=100,
            response_format={"type": "json_object"},
        )
    except Exception as e:
        print(f"❌ Orchestrator classification failed: {e}")
        return "unknown"

    raw = response.choices[0].message.content.strip()
    print(f"🔍 Orchestrator raw response: {raw}")

    try:
        result = json.loads(raw)
        drawing_type = result.get("type", "unknown").lower().strip()
    except json.JSONDecodeError:
        match = re.search(r'"type"\s*:\s*"(\w+)"', raw)
        drawing_type = match.group(1).lower().strip() if match else "unknown"

    valid_types = {"foundation", "slab", "beam", "column", "unknown"}
    if drawing_type not in valid_types:
        print(f"⚠ Unexpected type '{drawing_type}', defaulting to unknown.")
        drawing_type = "unknown"

    print(f"✅ Orchestrator: classified as '{drawing_type}'.")
    return drawing_type


def validate_user_input(missing_fields: list[str], user_answers: dict) -> dict:
    """Validate user-supplied answers for missing data fields.

    Returns {"valid": bool, "invalid_fields": list, "assumed_values": dict}.
    """
    from prompt import VALIDATOR_PROMPT

    fields_json  = json.dumps(missing_fields, indent=2)
    answers_json = json.dumps(user_answers, indent=2, ensure_ascii=False)
    prompt = VALIDATOR_PROMPT.format(fields_json=fields_json, answers_json=answers_json)

    print("🔍 Validator: checking user-supplied data...")
    try:
        response = client.chat.completions.create(
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
    except Exception as e:
        print(f"❌ Validator error: {e} — treating input as valid.")
        return {"valid": True, "invalid_fields": [], "assumed_values": {}}

    raw = response.choices[0].message.content.strip()
    print(f"🔍 Validator raw response: {raw}")

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        json_match = re.search(r"\{.*\}", raw, re.DOTALL)
        result = json.loads(json_match.group()) if json_match else {}

    assumed = result.get("assumed_values", {})
    print(f"✅ Validator: valid={result.get('valid', True)}, "
          f"invalid_count={len(result.get('invalid_fields', []))}, "
          f"assumed_count={len(assumed)}")
    return {
        "valid": result.get("valid", True),
        "invalid_fields": result.get("invalid_fields", []),
        "assumed_values": assumed,   # field → "assumed value — reason"
    }


def generate_compliance_report(
    previous_analysis: str,
    user_input: str,
    drawing_type: str,
    vectordb,
    embedding_model,
    k: int = 15,
) -> str:
    """Generate the final compliance report using RAG + o4-mini reasoning.

    Steps:
    1. Format REFINEMENT_PROMPT_TEMPLATE with the supplied inputs.
    2. Embed the formatted prompt to retrieve top-k IS code chunks from ChromaDB.
    3. Append retrieved context and call o4-mini for multi-step compliance checking.

    Args:
        previous_analysis: Initial extraction report markdown (from specialist agent).
        user_input:        User-supplied / assumed values for missing fields.
        drawing_type:      One of "foundation", "slab", "beam", "column".
        vectordb:          VectorStore instance.
        embedding_model:   HuggingFace embedding model.
        k:                 Number of IS code chunks to retrieve (default 15).

    Returns:
        Final compliance report as a Markdown string.
    """
    from prompt import REFINEMENT_PROMPT_TEMPLATE

    # ── 1. Build refinement prompt from template ─────────────────────────────
    refinement_prompt = REFINEMENT_PROMPT_TEMPLATE.format(
        drawing_type=drawing_type,
        previous_analysis=previous_analysis,
        user_input=user_input,
    )

    # ── 2. RAG retrieval ────────────────────────────────────────────────────
    print("📚 Embedding query and retrieving IS code context...")
    try:
        query_embedding = embedding_model.embed_query(refinement_prompt)
        retrieved = vectordb.query([query_embedding], n_results=k)
        if retrieved:
            context_texts = "\n\n".join(
                f"[Source: {r['metadata'].get('source_file', 'N/A')}, "
                f"Section: {r['metadata'].get('section_number', 'N/A')}, "
                f"Clause: {r['metadata'].get('clause_id', 'N/A')}, "
                f"Content Type: {r['metadata'].get('content_type', 'N/A')}]\n{r['document']}"
                for r in retrieved
            )
        else:
            print("⚠ No IS code context retrieved — proceeding without RAG context.")
            context_texts = "No relevant IS code context found."
    except Exception as e:
        print(f"⚠ RAG retrieval failed: {e} — proceeding without context.")
        context_texts = "IS code context unavailable."

    system_prompt = (
        "You are a Senior Indian Civil Engineer specialising in RCC compliance verification."

        "CORE ROLE:"
        "You are ONLY a verification engine. You are NOT allowed to design or assume values."

        "MANDATORY RULES:"
        "1. NEVER assume, infer, or generate missing values."
        "2. Use ONLY explicitly provided data from:"
        "   - Drawing"
        "   - User Input"
        "3. If data is missing → write 'NOT PROVIDED'"
        "4. If validation cannot be performed → status = 'NOT VERIFIABLE'"
        "5. NEVER mark a parameter as compliant using assumed values"

        "OUTPUT RULES:"
        "- Every row must include: Extracted Value | Source | IS Code Reference | Status"
        "- Allowed statuses: Compliant / Non-Compliant / Not Verifiable / Missing Information / Not Applicable"
        "- Output must be strict Markdown"
        "- Include a final section: '## IS Code References Used' grouped by code"

        "CRITICAL:"
        "If any value is assumed and used in validation, the output is INVALID."
        ""
        "VISUAL DETECTION RULES (VERY IMPORTANT):"
        "- You MUST actively inspect geometry in the drawing."
        "- If two structural elements (footings, beams, columns) overlap, intersect, or clash in plan → mark as NON-COMPLIANT."
        "- Overlap includes: shared area, touching boundaries with no clearance, or one element intruding into another."
        "- Do NOT ignore small overlaps — even partial intersection is NON-COMPLIANT."
        "- If image clarity is insufficient → mark as CANNOT VERIFY, NOT 'No issue'."
        ""
        "UNIFORM MEMBER SIZE RULES (ELEMENT-SPECIFIC):"
        "- For BEAMS: Uniform size across all spans → NON-COMPLIANT (loads and spans vary)."
        "- For FOUNDATIONS: Uniform footing sizes → NON-COMPLIANT (column loads differ)."
        "- For SLABS: Uniform thickness/reinforcement → ACCEPTABLE if spans and loading are similar."
        "- If spans/loading vary significantly in slabs and still uniform → NON-COMPLIANT."
    )

    user_prompt = (
        f"{refinement_prompt}\n\n"
        "---\n\n"
        f"## Retrieved IS Code Context (from knowledge base)\n{context_texts}"
    )

    # ── 4. Call o4-mini (reasoning model) ───────────────────────────────────
    # o4-mini does not accept a temperature parameter (uses internal reasoning).
    # Use max_completion_tokens (covers both output + reasoning tokens).
    print(f"🤖 Calling {FINAL_REPORT_MODEL} for final report generation...")
    try:
        response = client.chat.completions.create(
            model=FINAL_REPORT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            max_completion_tokens=8000,
        )
    except APIError as e:
        _handle_api_error(e)

    report = response.choices[0].message.content
    if not report:
        raise Exception("Empty response from API — please retry.")

    # ── POST VALIDATION: anti-hallucination guard ───────────────────────────
    if re.search(r"assumed|typical|standard practice|generally taken", report, re.IGNORECASE):
        raise ValueError("❌ Model used assumed values in compliance. Rejecting output.")

    if "Source" not in report:
        raise ValueError("❌ Missing 'Source' column in output.")

    print("✅ Final compliance report generated.")
    return report


def _handle_api_error(e: APIError) -> None:
    """Translate APIError into a user-friendly ValueError."""
    code = getattr(e, "status_code", None)
    msg  = str(e)
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