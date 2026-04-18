# Task: Fix three bugs in the RCC compliance pipeline

I've already updated `prompt.py` with a new two-phase extraction methodology.
The other files need three specific fixes to match. Do NOT modify `prompt.py`.

---

## File 1: `llm_service.py`

### Bug A — Post-validation regex is too broad

**Location:** inside `generate_compliance_report()`, near the end of the function,
the block marked `# ── POST VALIDATION: anti-hallucination guard ──`.

**Current code:**
```python
if re.search(r"assumed|typical|standard practice|generally taken", report, re.IGNORECASE):
    raise ValueError("❌ Model used assumed values in compliance. Rejecting output.")
```

**Why it's broken:** The word `assumed` appears legitimately in the section
heading `"User-Supplied / Assumed Values"` (which the refinement prompt itself
asks the model to produce) and in any row tagged `[USER-ASSUMED]`. The current
regex rejects valid reports.

**Replace with:** a structural check that only fires when assumption-language
appears inside a Markdown table row that is ALSO marked `Compliant`. Rows
marked `Missing Information`, `Cannot Verify`, `Conditionally Compliant`, or
`Not Applicable` are allowed to reference assumed values.

```python
# Only reject if a row is marked "Compliant" AND contains assumption language.
# "Conditionally Compliant" rows are explicitly allowed for [USER-ASSUMED] values.
bad_rows = re.findall(
    r"^\|(?![^\n|]*Conditionally)[^\n]*\b(?:assumed|typical|standard practice|generally taken)\b[^\n]*\|[^\n]*\bCompliant\b[^\n]*\|",
    report,
    re.IGNORECASE | re.MULTILINE,
)
if bad_rows:
    raise ValueError(
        f"❌ Model marked {len(bad_rows)} row(s) Compliant using assumption language. "
        f"First offender: {bad_rows[0][:120]}…"
    )
```

### Bug B — `system_prompt` string concatenation has no whitespace

**Location:** inside `generate_compliance_report()`, the variable `system_prompt`
built with `system_prompt = ( "..." "..." "..." )`.

**Why it's broken:** Python concatenates adjacent string literals with NO
separator. The current code produces a run-together blob like
`...verification.CORE ROLE:You are ONLY a verification engine...MANDATORY RULES:1. NEVER...`
which the model has to work hard to parse.

**Fix:** rewrite the entire `system_prompt` assignment using a single triple-quoted
string so whitespace and newlines are preserved exactly as authored. Replace the
current `system_prompt = ( ... )` block with:

```python
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
```

### Bug C — The `"Source" not in report` guard is too naive

**Location:** immediately after the new regex check.

**Current code:**
```python
if "Source" not in report:
    raise ValueError("❌ Missing 'Source' column in output.")
```

**Why it's fragile:** the literal word "Source" may appear in prose even when
the table itself has no Source column. Tighten to check for it inside a
Markdown table header row.

**Replace with:**
```python
# Confirm at least one table header contains the Source column.
if not re.search(r"^\|[^\n]*\bSource\b[^\n]*\|", report, re.MULTILINE):
    raise ValueError("❌ Output has no Markdown table with a 'Source' column.")
```

---

## File 2: `llm_handler.py`

### Bug D — 150 DPI / 2048 px cap loses small schedule text on A1 drawings

**Location:** top of the file, the `_MAX_DIM` constant and the `get_pixmap(dpi=150)`
call inside `pdf_to_images()`.

**Why it's broken:** Indian structural drawings are typically A1 (594 × 841 mm).
At 150 DPI they render to ~3500–5000 px, then get downscaled to 2048 px, at
which point schedule text (often 1.5–2 mm tall on the sheet) collapses below
the size needed for reliable OCR-style extraction. This is a root cause of
missed extractions in the column schedule.

**Fix:** bump DPI to 220 and raise the cap to 3072 px. Keep the resize logic
identical — only the constants change.

```python
# Old:
_MAX_DIM = 2048
# ...
pix = page.get_pixmap(dpi=150)

# New:
_MAX_DIM = 3072       # was 2048 — A1 sheets need more pixels for schedule text
_RENDER_DPI = 220     # was 150 — small reinforcement annotations were mushy at 150
# ...
pix = page.get_pixmap(dpi=_RENDER_DPI)
```

Also add a file-size sanity check right before the `images.append(img)` line so
we fail loudly if a page exceeds OpenAI's ~20 MB image limit instead of having
the image silently dropped:

```python
buf = io.BytesIO()
img.save(buf, format="PNG")
size_mb = len(buf.getvalue()) / (1024 * 1024)
if size_mb > 18:
    print(f"⚠ Page {page_num + 1} rendered to {size_mb:.1f} MB — approaching OpenAI cap. "
          f"Consider lowering _RENDER_DPI.")
images.append(img)
```

---

## Acceptance criteria

Before declaring done:

1. `python -c "import llm_service; import llm_handler"` must succeed with no
   syntax errors.
2. `grep -n '"assumed|typical' llm_service.py` must return no results (old
   regex is gone).
3. `grep -n 'system_prompt = """' llm_service.py` must return exactly one
   match (new triple-quoted prompt is in place).
4. `grep -n '_MAX_DIM = 3072' llm_handler.py` must return one match.
5. `grep -n 'dpi=150' llm_handler.py` must return zero matches.
6. Do NOT modify `prompt.py`. Do NOT rename functions. Do NOT change function
   signatures. Imports must remain identical.

After edits, show me a unified diff of both files.