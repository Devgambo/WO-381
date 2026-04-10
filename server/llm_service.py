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
# gpt-4o-mini  — fast cheap model for classification and validation (text only,
#                no complex reasoning needed).
# o4-mini      — reasoning model for final report generation. Compliance checking
#                is a multi-step rule-matching task across IS clauses; reasoning
#                models handle this significantly better than standard LLMs.
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

    Returns {"valid": bool, "invalid_fields": list}.
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
        return {"valid": True, "invalid_fields": []}

    raw = response.choices[0].message.content.strip()
    print(f"🔍 Validator raw response: {raw}")

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        json_match = re.search(r"\{.*\}", raw, re.DOTALL)
        result = json.loads(json_match.group()) if json_match else {}

    print(f"✅ Validator: valid={result.get('valid', True)}, "
          f"invalid_count={len(result.get('invalid_fields', []))}")
    return {
        "valid": result.get("valid", True),
        "invalid_fields": result.get("invalid_fields", []),
    }


def generate_compliance_report(
    Initial_report: str,
    vectordb,
    embedding_model,
    previous_analysis: str,
    user_input: str,
    k: int = 15,
) -> str:
    """Generate the final compliance report using RAG + o4-mini reasoning.

    Steps:
    1. Retrieve the top-k most relevant IS code chunks from ChromaDB.
    2. Build a prompt combining initial report, user input, and retrieved context.
    3. Call o4-mini (reasoning model) for multi-step clause-matching compliance.

    Args:
        Initial_report:     Refinement prompt string (pre-formatted by main.py).
        vectordb:           VectorStore instance.
        embedding_model:    HuggingFace embedding model.
        previous_analysis:  Initial extraction report markdown.
        user_input:         User-supplied values for missing fields.
        k:                  Number of IS code chunks to retrieve (default 10).

    Returns:
        Final compliance report as a Markdown string.
    """
    # ── 1. RAG retrieval ────────────────────────────────────────────────────
    print("📚 Embedding query and retrieving IS code context...")
    try:
        query_embedding = embedding_model.embed_query(Initial_report)
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

    # ── 2. Prompts ──────────────────────────────────────────────────────────
    system_prompt = (
        "You are a Senior Indian Civil Engineer specialising in RCC structural design "
        "and code compliance. Your task is to produce a final, professional compliance "
        "report by integrating the initial drawing analysis with the user-supplied data "
        "and the IS code clauses provided below.\n\n"
        "Rules:\n"
        "- Cite specific IS 456:2000 clause numbers and SP 34 references for every finding.\n"
        "- Use clear, professional engineering language.\n"
        "- Output valid Markdown with a structured compliance table.\n"
        "- Be decisive: every checklist item must end with a status of "
        "Compliant / Non-Compliant / Missing Information / Not Applicable.\n"
        "- Do not ask for more information — work with what is provided."
    )

    user_prompt = (
        f"## Previous Analysis\n{previous_analysis}\n\n"
        f"## User-Supplied Data\n{user_input}\n\n"
        f"## Relevant IS Code Clauses (retrieved)\n{context_texts}\n\n"
        "---\n\n"
        "## Task\n"
        "1. Integrate the user-supplied data into the previous analysis.\n"
        "2. Re-evaluate every compliance checklist item with the combined information.\n"
        "3. Cite the exact IS clause number or SP 34 reference for each finding.\n"
        "4. Produce one complete, updated Markdown compliance report.\n"
        "5. In the final 'Missing or Wrong Information' section list only items that "
        "are *still* unresolved after incorporating the user input. "
        "If everything is resolved, state: "
        "'All previously identified issues have been resolved.'\n\n"
        f"## Refinement Directive\n{Initial_report}"
    )

    # ── 3. Call o4-mini (reasoning model) ───────────────────────────────────
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
