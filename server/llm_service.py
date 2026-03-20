from typing import List, Dict, Optional
from openai import OpenAI, APIError
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize OpenRouter client
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY not found in environment variables. Please set it in your .env file.")

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

# Model selection for final report generation:
    # 
    # TOP TIER (Best Quality - Recommended for Production):
    # - "anthropic/claude-3.5-sonnet" - Best overall: Excellent reasoning, citations, structured output
    # - "openai/gpt-4o" - Excellent: Great reasoning, fast, good structured output
    # - "anthropic/claude-3-opus" - Excellent: Best reasoning, slower but highest quality
    # - "openai/gpt-4-turbo" - Very Good: Balanced performance and cost
    # 
    # MID TIER (Good Quality - Cost-Effective):
    # - "google/gemini-pro-1.5" - Very Good: Strong technical understanding, good citations
    # - "anthropic/claude-3-sonnet" - Very Good: Good balance of quality and speed
    # - "meta-llama/llama-3.1-70b-instruct" - Good: Open-source, decent technical analysis
    # - "google/gemini-2.0-flash-exp" - Good: Fast, decent quality for structured reports
    # 
    # BUDGET TIER (Fast & Affordable - Good for Testing):
    # - "openai/gpt-4o-mini" - Fast: Good for simple reports, very affordable (RECOMMENDED DEFAULT)
    # - "google/gemini-2.0-flash-exp" - Fast: Quick responses, lower cost, acceptable quality
    # - "meta-llama/llama-3.1-8b-instruct" - Fast: Lightweight, basic technical analysis
    # 
    # Set via environment variable: OPENROUTER_MODEL
    # Default: gpt-4o-mini (reliable, affordable, widely available)
# OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash")

def generate_compliance_report(
    Initial_report: str,
    vectordb,
    embedding_model,
    previous_analysis: str,
    user_input: str,
    k: int = 5
) -> str:
    """
    Generate a compliance report by comparing validated drawing data 
    with IS codes (via RAG) using OpenRouter.
    
    This function:
    1. Retrieves relevant IS code context using RAG
    2. Combines initial report, user input, and IS code context
    3. Generates a comprehensive final compliance report
    
    Args:
        Initial_report: Path to initial report file or raw markdown content
        vectordb: Vector database instance for RAG retrieval
        embedding_model: Embedding model for query encoding
        previous_analysis: The previous analysis report content
        user_input: Additional information provided by the user
        k: Number of relevant chunks to retrieve from vector DB (default: 5)
    
    Returns:
        str: Generated compliance report in markdown format
    
    Raises:
        ValueError: If required parameters are missing
        Exception: If API call fails
    """
    try:
        # Resolve content if a file path is provided, otherwise treat as raw markdown
        if os.path.isfile(Initial_report):
            with open(Initial_report, encoding="utf-8") as f:
                Initial_report = f.read()
        
        if not Initial_report or not previous_analysis:
            raise ValueError("Initial_report and previous_analysis cannot be empty")
        
        # --- 1. Embed query and retrieve relevant IS code context ---
        print("Embedding query and retrieving relevant IS code context...")
        query_embedding = embedding_model.embed_query(Initial_report)
        retrieved = vectordb.query([query_embedding], n_results=k)

        if not retrieved or len(retrieved) == 0:
            print("Warning: No relevant context retrieved from vector database.")
            context_texts = "No relevant IS code context found in the database."
        else:
            context_texts = "\n\n".join(
                [f"[Source: {r['metadata'].get('source_file', 'N/A')}, "
                 f"Clause: {r['metadata'].get('chunk_id', 'N/A')}]\n{r['document']}"
                 for r in retrieved]
            )
        
        # --- 2. Construct prompts ---
        system_prompt = """You are an Indian Senior Civil Engineer with extensive expertise in RCC structural design and code compliance. Your task is to refine a previous analysis of an RCC structural drawing based on new information provided by the user.
            Key Responsibilities:
            - Integrate user input with the previous analysis to create a comprehensive final report
            - Cross-reference all findings with IS 456:2000 and SP 34 provisions
            - Always cite specific IS clause numbers from the provided context
            - Generate a structured, professional compliance report in Markdown format
            - Clearly distinguish between compliant and non-compliant items
            - Update the "Missing or Wrong Information" section based on the integrated analysis

            Output Requirements:
            - Use clear, professional engineering language
            - Structure the report with proper Markdown formatting
            - Include specific clause references for all compliance checks
            - Provide actionable recommendations where non-compliance is identified
            - Be thorough but concise"""

        user_prompt = f"""**PREVIOUS ANALYSIS:**
---
{previous_analysis}
---

**USER'S NEW INPUT:**
---
{user_input}
---

**IS Code Context (Retrieved from Vector Database):**
{context_texts}

---

**Your Tasks:**

1. **Integrate New Information:** 
   - Carefully review the USER'S NEW INPUT
   - Use it to fill gaps and correct information in the PREVIOUS ANALYSIS
   - Merge both sources into a unified understanding

2. **Re-run Compliance Checks:** 
   - With the integrated information, re-evaluate each checklist item
   - Compare against the extracted IS Code contexts (IS 456:2000 and SP 34)
   - Verify compliance with specific clause requirements
   - Cite the exact clause numbers from the provided context

3. **Produce an Updated Report:** 
   - Generate a single, complete, and updated report
   - Maintain the same Markdown checklist format as the original
   - Ensure all sections are properly updated with new information
   - Include a clear summary of changes made

4. **Update Missing Information List:** 
   - The final "**Missing or Wrong Information**" section should only contain items that are *still* missing or non-compliant after incorporating the user's input
   - If all issues are resolved, state this clearly: "All previously identified issues have been resolved based on the provided information."
   - If new issues are discovered, list them clearly

5. **Quality Assurance:**
   - Ensure all technical terms and values are accurate
   - Verify that all IS code references are correctly cited
   - Check that the report is internally consistent

**Important:** Do not ask for more information. Provide the updated report based only on the context provided. If information is still missing after integration, clearly state it in the "Missing or Wrong Information" section.

### Initial Preliminary Report with Additional User Input:
{Initial_report}
---

Please generate the final compliance report now."""

        # --- 3. Call OpenRouter API ---
        print(f"Calling OpenRouter API with model: {OPENROUTER_MODEL}...")
        try:
            response = client.chat.completions.create(
                model=OPENROUTER_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,  # Low temperature for consistent, factual output
                max_tokens=4000,  # Sufficient for detailed reports
            )
        except APIError as api_error:
            error_str = str(api_error)
            error_code = getattr(api_error, 'status_code', None) or getattr(api_error, 'code', None)
            
            # Handle specific error codes
            if error_code == 402 or "402" in error_str or "Insufficient credits" in error_str:
                raise ValueError(
                    "❌ OpenRouter API Error: Insufficient credits.\n\n"
                    "Your OpenRouter account does not have sufficient credits to make this request.\n\n"
                    "To fix this:\n"
                    "1. Visit https://openrouter.ai/settings/credits\n"
                    "2. Purchase credits for your account\n"
                    "3. Ensure your API key is correct and associated with the account that has credits\n\n"
                    f"Technical details: {error_str}"
                ) from api_error
            elif error_code == 401 or "401" in error_str or "Unauthorized" in error_str:
                raise ValueError(
                    "❌ OpenRouter API Error: Invalid API key.\n\n"
                    "Your OPENROUTER_API_KEY is invalid or expired.\n\n"
                    "To fix this:\n"
                    "1. Visit https://openrouter.ai/keys\n"
                    "2. Create a new API key\n"
                    "3. Update your .env file with the new key\n\n"
                    f"Technical details: {error_str}"
                ) from api_error
            elif error_code == 404 or "404" in error_str or "No endpoints found" in error_str or "NotFoundError" in str(type(api_error).__name__):
                raise ValueError(
                    f"❌ Model '{OPENROUTER_MODEL}' is not available on OpenRouter.\n\n"
                    "Please check the model name or use a different model.\n"
                    "Valid options include: 'openai/gpt-4o-mini', 'anthropic/claude-3.5-sonnet', "
                    "'openai/gpt-4o', 'google/gemini-pro-1.5'.\n"
                    "Set OPENROUTER_MODEL environment variable to change the model.\n\n"
                    f"Technical details: {error_str}"
                ) from api_error
            else:
                raise ValueError(
                    f"❌ OpenRouter API Error: {error_str}\n\n"
                    "Please check your API key and account status at https://openrouter.ai/"
                ) from api_error
        except Exception as api_error:
            error_str = str(api_error)
            # Check if it's a model not found error
            if "404" in error_str or "No endpoints found" in error_str or "NotFoundError" in str(type(api_error).__name__):
                raise ValueError(
                    f"❌ Model '{OPENROUTER_MODEL}' is not available on OpenRouter.\n\n"
                    "Please check the model name or use a different model.\n"
                    "Valid options include: 'openai/gpt-4o-mini', 'anthropic/claude-3.5-sonnet', "
                    "'openai/gpt-4o', 'google/gemini-pro-1.5'.\n"
                    "Set OPENROUTER_MODEL environment variable to change the model.\n\n"
                    f"Technical details: {error_str}"
                ) from api_error
            elif "402" in error_str or "Insufficient credits" in error_str:
                raise ValueError(
                    "❌ OpenRouter API Error: Insufficient credits.\n\n"
                    "Your OpenRouter account does not have sufficient credits to make this request.\n\n"
                    "To fix this:\n"
                    "1. Visit https://openrouter.ai/settings/credits\n"
                    "2. Purchase credits for your account\n"
                    "3. Ensure your API key is correct and associated with the account that has credits\n\n"
                    f"Technical details: {error_str}"
                ) from api_error
            else:
                raise ValueError(
                    f"❌ Unexpected error: {error_str}\n\n"
                    "Please check your API key and account status at https://openrouter.ai/"
                ) from api_error

        if not response or not response.choices or len(response.choices) == 0:
            raise Exception("Empty response received from OpenRouter API")

        generated_report = response.choices[0].message.content
        
        if not generated_report:
            raise Exception("Generated report is empty")

        print("✅ Final compliance report generated successfully.")
        return generated_report

    except ValueError as e:
        print(f"❌ Validation error: {e}")
        raise
    except FileNotFoundError as e:
        print(f"❌ File not found: {e}")
        raise
    except Exception as e:
        print(f"❌ Error generating compliance report: {e}")
        raise Exception(f"Failed to generate compliance report: {str(e)}")


def classify_drawing_type(base64_images: list[str]) -> str:
    """
    Classify the drawing type using the Orchestrator prompt.

    Sends the drawing images to the vision model and parses the JSON
    response to determine if the drawing is foundation, slab, or beam.

    Args:
        base64_images: List of base64-encoded PNG image strings.

    Returns:
        str: One of "foundation", "slab", "beam", or "unknown".
    """
    import json
    import re
    from prompt import ORCHESTRATOR_PROMPT

    try:
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": ORCHESTRATOR_PROMPT},
                ] + [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{img}"}
                    } for img in base64_images
                ]
            }
        ]

        print("🔍 Orchestrator: Classifying drawing type...")
        response = client.chat.completions.create(
            model=OPENROUTER_MODEL,
            messages=messages,
            temperature=0,
            max_tokens=100,
        )

        raw_text = response.choices[0].message.content.strip()
        print(f"🔍 Orchestrator raw response: {raw_text}")

        # Try to parse the JSON response
        try:
            result = json.loads(raw_text)
            drawing_type = result.get("type", "unknown").lower().strip()
        except json.JSONDecodeError:
            # Fallback: try to extract with regex
            match = re.search(r'"type"\s*:\s*"(\w+)"', raw_text)
            if match:
                drawing_type = match.group(1).lower().strip()
            else:
                print("⚠ Orchestrator: Could not parse response, defaulting to unknown.")
                drawing_type = "unknown"

        valid_types = {"foundation", "slab", "beam", "unknown"}
        if drawing_type not in valid_types:
            print(f"⚠ Orchestrator: Unexpected type '{drawing_type}', defaulting to unknown.")
            drawing_type = "unknown"

        print(f"✅ Orchestrator: Drawing classified as '{drawing_type}'.")
        return drawing_type

    except Exception as e:
        print(f"❌ Orchestrator classification failed: {e}")
        return "unknown"


def validate_user_input(missing_fields: list[str], user_answers: dict) -> dict:
    """
    Validate user-supplied answers for missing data fields.

    Uses the Validator Agent prompt to check that user-provided values
    are plausible and correctly formatted for civil engineering data.

    Args:
        missing_fields: List of field names that were missing.
        user_answers: Dict mapping field name → user-provided value.

    Returns:
        dict: {"valid": bool, "invalid_fields": list[dict]}
    """
    import json
    import re
    from prompt import VALIDATOR_PROMPT

    try:
        fields_json = json.dumps(missing_fields, indent=2)
        answers_json = json.dumps(user_answers, indent=2, ensure_ascii=False)

        prompt = VALIDATOR_PROMPT.format(
            fields_json=fields_json,
            answers_json=answers_json,
        )

        print("🔍 Validator Agent: Checking user-supplied data...")
        response = client.chat.completions.create(
            model=OPENROUTER_MODEL,
            messages=[
                {"role": "system", "content": "You are a strict data validation agent. Respond ONLY with valid JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            max_tokens=2000,
        )

        raw_text = response.choices[0].message.content.strip()
        print(f"🔍 Validator raw response: {raw_text}")

        # Strip markdown fences if present
        if raw_text.startswith("```"):
            raw_text = re.sub(r'^```(?:json)?\s*', '', raw_text)
            raw_text = re.sub(r'\s*```$', '', raw_text)

        try:
            result = json.loads(raw_text)
        except json.JSONDecodeError:
            # Try to extract JSON from the response
            json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
            else:
                print("⚠ Validator: Could not parse response, assuming valid.")
                return {"valid": True, "invalid_fields": []}

        is_valid = result.get("valid", True)
        invalid_fields = result.get("invalid_fields", [])

        print(f"✅ Validator: valid={is_valid}, invalid_count={len(invalid_fields)}")
        return {
            "valid": is_valid,
            "invalid_fields": invalid_fields,
        }

    except Exception as e:
        print(f"❌ Validator error: {e}")
        # On error, don't block the user — return valid
        return {"valid": True, "invalid_fields": []}









#user_prompt = f"""
    # ### Initial Preliminary Report with additioal user input
    # {Initial_report}

    # ### IS Code Context (Retrieved)
    # {context_texts}

    # ### Task
    # Compare and validate the extracted RCC design data against the provisions of *SP 34*, identifying whether the design parameters meet the code requirements and highlighting any deviations, warnings, or violations.

    # ---

    # ### 📄 *Input Data (Provide or Attach):*

    # Include all or any available RCC design data extracted from the drawing or report, for example:

    # * *Member Type:* (e.g., Beam / Slab / Column / Footing)
    # * *Dimensions:* (b, D, L, cover, etc.)
    # * *Material Grades:* (fck = … MPa, fy = … MPa)
    # * *Load Details:* (DL, LL, factored load, etc.)
    # * *Reinforcement Details:*

    # * Main bars (number, diameter, spacing)
    # * Distribution or secondary steel
    # * Stirrups / Ties (diameter, spacing)
    # * *Support Conditions*
    # * *Design Moments & Shear Values* (if available)
    # * *Location or exposure condition* (for durability checks)
    # * *Concrete cover and effective depth*
    # * *Any special design notes* (development length, anchorage, detailing, etc.)

    # ---

    # ### ⚙ *Task Instructions:*

    # 1. *Step 1 — Validate Design Inputs*

    # * Check if all the necessary parameters for RCC design are available.
    # * Identify missing or inconsistent data (e.g., unspecified cover, bar diameters without spacing, etc.).

    # 2. *Step 2 — IS 456:2000 Compliance*
    # Perform a *clause-by-clause verification* based on IS 456:2000, including but not limited to:

    # * *Clause 5–9:* Material properties (cement, aggregates, reinforcement grades)
    # * *Clause 22:* Design philosophy (limit state method)
    # * *Clause 26:* Requirements for durability, cover, exposure, and quality control
    # * *Clause 36:* Reinforcement detailing and bar curtailment
    # * *Clause 40:* Development length and anchorage
    # * *Clause 41–46:* Serviceability checks (deflection, cracking)
    # * *Annex A/B:* Stress-strain relations, permissible limits
    # * *Member-specific clauses:*

    #     * Beams — flexure, shear, torsion (Clauses 38, 40.1)
    #     * Slabs — one-way/two-way (Clauses 24, 26.5.2)
    #     * Columns — axial load + bending (Clause 39)
    #     * Footings — bearing, punching shear (Clause 34)

    # For each check, include:

    # * Reference clause number
    # * Formula or criterion from IS 456
    # * Computed or given value from design data
    # * Pass/Fail or Compliant/Non-Compliant verdict

    # 3. *Step 3 — SP 34 Comparison*

    # * Use *SP 34* for reinforcement detailing checks (preferred bar spacing, curtailment, anchorage, lap length, etc.)
    # * Verify:

    #     * Bar placement and spacing limits
    #     * Minimum and maximum reinforcement ratios
    #     * Detailing around supports and corners
    #     * Shear reinforcement distribution
    #     * Recommended detailing practices for ductility and crack control
    # * Cite the *SP 34 table/figure reference* and provide a short note comparing the design’s detailing to those guidelines.

    # 4. *Step 4 — Tabular Comparison*
    # Prepare a structured comparison table like:

    # | Check Type    | Parameter            | Design Value | IS 456:2000 Limit/Requirement | SP 34 Guideline | Clause/Ref        | Status (OK/Not OK) | Remarks            |
    # | ------------- | -------------------- | ------------ | ----------------------------- | --------------- | ----------------- | ------------------ | ------------------ |
    # | Flexure       | Mu (kNm)             | 68.5         | < Mu_lim (72.4)               | –               | IS 456 Cl. 38.1   | ✅ OK               | Within capacity    |
    # | Reinforcement | Main bars (mm²)      | 804          | ≥ 804                         | Fig. 7, SP34    | ✅                 | OK                 |                    |
    # | Cover         | Effective cover (mm) | 20           | ≥ 25 (moderate exposure)      | –               | IS 456 Cl. 26.4.2 | ❌                  | Less than required |

    # 5. *Step 5 — Final Output*

    # * Provide a *summary of compliance* (e.g., 85% compliant with IS 456, 90% compliant with SP 34)
    # * Highlight *critical deviations* that could affect safety, serviceability, or code compliance.
    # * Suggest *rectifications or redesign notes* where applicable.

    # ---

    # ### 🧾 *Output Format (Structured Response)*

    # * *Section 1:* Summary of data checked
    # * *Section 2:* IS 456:2000 verification (with clause references)
    # * *Section 3:* SP 34 detailing check (with figure/table references)
    # * *Section 4:* Comparison Table (as shown above)
    # * *Section 5:* Observations and Recommendations

    # ---

    # ### ⚠ *Optional Enhancements*

    # If you want the comparison to be automated or AI-assisted:

    # * Ask the model to highlight non-compliance in red and suggest correction per code.
    # * Ask for *separate summaries per RCC member type* (beam/slab/column/footing).
    # * Request the *percentage deviation from IS code permissible limits* for each parameter.

    # ---

    # ### ✅ *Example Prompt (ready-to-use)*

    # > You are an RCC design auditor.
    # > I will provide RCC design data extracted from construction drawings.
    # > Compare every design parameter against the rules and clauses of *IS 456:2000* and *SP 34*, and create a detailed compliance report.
    # >
    # > For each check:
    # >
    # > * Mention the *IS clause number or SP 34 reference*.
    # > * Show formula or limit used for verification.
    # > * Provide computed value from the extracted data.
    # > * Mark as *Compliant / Non-Compliant / Insufficient Data*.
    # > * Give recommendations for correction if not compliant.
    # >
    # > Output in this structure:
    # >
    # > 1. Data Summary
    # > 2. IS 456:2000 Clause-wise Verification
    # > 3. SP 34 Detailing Check
    # > 4. Comparative Table (as shown above)
    # > 5. Summary and Recommendations

    # """