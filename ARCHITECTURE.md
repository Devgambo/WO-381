# Architecture & Project Guide

This document explains what this repository does, how the pieces fit together, what each backend file is responsible for, and a roadmap of useful things to add next (observability, evaluation, hardening). It is intentionally backend-heavy; the React frontend is described at the end.

---

## 1. What the project does

The application audits Indian Reinforced Cement Concrete (RCC) structural drawings — foundations, slabs, beams, columns — against IS 456:2000 and SP 34. A user uploads a PDF or images, and the system:

1. Classifies which structural element the drawing depicts.
2. Runs a vision model with a specialised prompt to transcribe the drawing and emit a Phase 1 → Phase 4 report.
3. Pulls out fields that the drawing left missing or unverifiable.
4. Asks the user to fill in the missing fields, with the option to type "assume" and let a validator agent supply standards-compliant defaults.
5. Retrieves the relevant IS code clauses via RAG (vector search over cleaned SP 34 and IS 456 text).
6. Calls a reasoning model to produce a final, citation-backed compliance verdict.
7. Persists the run to Supabase so the user can return later, resume, or download a PDF.

The product is a workflow over multiple LLM calls, glued together by FastAPI on the server side and React on the client side.

---

## 2. High-level architecture

```
                ┌────────────────────────────────────────────┐
                │                  Browser                   │
                │  React 19 + Vite + Tailwind                │
                │  (Login → Dashboard → History)             │
                └───────────────────┬────────────────────────┘
                                    │ HTTPS + Bearer JWT
                                    ▼
                ┌────────────────────────────────────────────┐
                │                FastAPI app                 │
                │                                            │
                │  Routes      → auth, reports, generate-*   │
                │  Agents      → orchestrator/specialist/    │
                │                validator/RAG reporter      │
                │  Services    → vector store, embeddings,   │
                │                PDF rendering               │
                └───┬───────────┬──────────────┬─────────────┘
                    │           │              │
                    ▼           ▼              ▼
              ┌──────────┐ ┌──────────┐  ┌───────────────┐
              │ Supabase │ │ ChromaDB │  │ OpenAI API    │
              │ (auth +  │ │ (vector  │  │ gpt-4o /      │
              │ Postgres)│ │ store)   │  │ gpt-4o-mini / │
              └──────────┘ └──────────┘  │ o4-mini       │
                                         └───────────────┘
```

Two external dependencies do the heavy lifting: OpenAI (vision + reasoning) and Supabase (auth + persistence). The vector store is local on disk (`server/chroma_db/`) — it ships embedded with the backend.

---

## 3. Repository layout

```
WO-381/
├── ARCHITECTURE.md             ← this file
├── README.md                   ← quick start, env vars, API surface
├── .gitignore
├── client/                     ← React 19 SPA
│   └── src/
│       ├── api.js
│       ├── App.jsx
│       ├── components/
│       ├── context/
│       └── pages/
└── server/                     ← FastAPI app + RAG pipeline
    ├── main.py                 ← all HTTP routes
    ├── auth.py                 ← Supabase JWT validation, login/signup/logout
    ├── database.py             ← Supabase client factory (anon + service role)
    ├── openai_client.py        ← shared OpenAI client + model IDs
    ├── llm_handler.py          ← specialist (vision) agent
    ├── llm_service.py          ← orchestrator, validator, RAG reporter
    ├── prompt.py               ← every LLM prompt (per drawing type)
    ├── embedding_service.py    ← lazy BAAI/bge-large embedder
    ├── vector_db.py            ← ChromaDB wrapper
    ├── data_loader.py          ← chunk SP 34 / IS code markdown
    ├── ingest.py               ← one-off: build the RAG index
    ├── clean_docs.py           ← one-off: clean SP 34 OCR markdown
    ├── SP34_md/                ← source IS code markdown
    └── chroma_db/              ← persisted vector index (generated)
```

---

## 4. Backend files in detail

The server is split into thin layers: routing (`main.py`) → agents (`llm_handler.py`, `llm_service.py`) → services (`vector_db.py`, `embedding_service.py`, `database.py`, `openai_client.py`) → prompts (`prompt.py`). Pipeline scripts live next to the app (`ingest.py`, `clean_docs.py`).

### 4.1 `main.py` — HTTP surface and orchestration

This file is the only FastAPI app. It owns CORS, logging, lazy service initialisation, request-size limits, and every route. Important pieces:

- **App setup.** Reads `CORS_ALLOW_ORIGINS`, `LOG_LEVEL`, `MAX_UPLOAD_BYTES`, `HOST`, `PORT`, `RELOAD` from environment. CORS is allow-listed (not wildcard) so credentialed requests work.
- **Lazy loaders.** `get_vectordb()` and `get_embedding_model()` defer the expensive ChromaDB and HuggingFace imports until the first time they are needed, so booting the API doesn't pull a 1.3 GB model into memory.
- **Helpers.**
  - `_safe_filename` — strips header-injection characters from user-supplied download names.
  - `_read_upload` — bounds an upload at `MAX_UPLOAD_BYTES` (default 50 MB).
  - `_open_image_bytes` — opens an image with PIL, normalising to RGB.
  - `markdown_to_pdf` — converts the report markdown into a ReportLab PDF. Handles headings, tables, lists, inline bold/italic/code.
  - `_extract_missing_fields` — parses the Phase-1/Phase-4 markdown returned by the specialist agent and emits a deduplicated list of "this field needs the user to fill it in".
  - `_extract_quality_assessment` — pulls `severity`, `critical_defects_count`, and the `rejection_narrative` block out of the Phase 4 section.
- **Routes** (every authenticated route depends on `get_current_user`):

  | Method | Path | Purpose |
  |--------|------|---------|
  | `POST` | `/api/generate-initial-report` | Upload one or more files. Convert PDFs to pages, run orchestrator → specialist agent, extract missing fields and quality assessment, persist the row in Supabase. |
  | `POST` | `/api/generate-final-report` | Take the initial report plus user-supplied answers, run RAG retrieval, call the reasoning model, persist the final report. Returns `rag_context_used` so the client can warn when RAG silently failed. |
  | `POST` | `/api/validate-input` | Validate the answers the user filled in. Returns invalid fields and a map of assumed values. |
  | `GET`  | `/api/rag/query` | Direct RAG query — debug helper, authenticated. |
  | `POST` | `/api/download-pdf` | Markdown → PDF, streaming response. |
  | `GET`  | `/api/reports` | List the calling user's reports. |
  | `GET`  | `/api/reports/{id}` | Get one report. |
  | `GET`  | `/api/reports/{id}/missing-fields` | Re-derive missing fields server-side on resume (so the client doesn't keep a duplicated parser). |
  | `DELETE` | `/api/reports/{id}` | Delete a report. |

- **PIL lifecycle.** `generate_initial_report` opens images, hands them to the vision agent, then closes every image in a `finally` block.
- **Error handling.** Every route logs via `logging.exception` and returns a short, fixed message to the client — the raw exception string is never echoed back.

### 4.2 `auth.py` — authentication

Three responsibilities:

- `_parse_bearer(authorization)` — strict parser; case-insensitive `bearer`, exactly two whitespace-separated tokens, otherwise 401.
- `get_current_user` — FastAPI dependency. Validates the JWT against Supabase's `auth.get_user(token)` and returns `{id, email, token}`. The token is forwarded so `/logout` can call `supabase.auth.sign_out(token)` and actually invalidate the session.
- Routes: `POST /api/auth/signup`, `/login`, `/logout`. Login/signup return `{access_token, user_id, email}`. The Pydantic model treats `email` as optional because Supabase supports phone-only accounts.

### 4.3 `database.py` — Supabase clients

Two memoised clients:

- `get_supabase_client()` — uses the anon key. Anything user-facing (auth flow) uses this client so RLS is enforced.
- `get_supabase_admin_client()` — uses the service-role key. Anything server-side that needs to bypass RLS (e.g. inserting a report on behalf of the authenticated user) uses this client. Falls back to the anon key if no service key is set.

### 4.4 `openai_client.py` — shared OpenAI client + model IDs

Single source of truth for the OpenAI handle:

- `get_openai_client()` — memoised `OpenAI(api_key=…)`, raises if `OPENAI_API_KEY` is missing.
- Model IDs:
  - `VISION_MODEL` (default `gpt-4o`) — specialist agent.
  - `ORCHESTRATOR_MODEL` (default `gpt-4o-mini`) — classifies drawing type.
  - `VALIDATOR_MODEL` (default `gpt-4o-mini`) — validates user input.
  - `FINAL_REPORT_MODEL` (default `o4-mini`) — reasoning model for the final RAG-backed verdict.

All four are overridable via env vars (`OPENAI_VISION_MODEL`, etc.), so staging/prod can pin different snapshots.

### 4.5 `llm_handler.py` — the specialist (vision) agent

Two utilities and one agent runner:

- `pdf_to_images(pdf_source)` — uses PyMuPDF to rasterise each PDF page at 220 DPI, downscale so the longest side is ≤ 3072 px, and warn when a page approaches OpenAI's 20 MB image limit.
- `pil_to_base64(image)` — encodes a PIL image to base64 PNG.
- `run_specialist_agent(base64_images, drawing_type)` — picks the right prompt from `prompt.PROMPT_REGISTRY`, sends it to `gpt-4o` with `detail: "high"` (so the tile-based vision pipeline can read fine reinforcement annotations), and returns the markdown report.

System message reminds the model that the images are attached and that the response must start with `### Phase 1`. This is a defence against the "I'm unable to view images" preamble that vision models sometimes emit when they haven't processed image tokens yet.

### 4.6 `llm_service.py` — orchestrator, validator, RAG reporter

Three top-level functions:

- `classify_drawing_type(base64_images)` — runs the orchestrator prompt. Uses `response_format=json_object` so the answer is `{"type": "foundation"|"slab"|"beam"|"column"|"unknown"}`. Falls back to a regex if the JSON parse fails, and pins anything unexpected to `"unknown"`.

- `validate_user_input(missing_fields, user_answers)` — runs the validator prompt. Returns `{valid, invalid_fields, assumed_values}`. If the user types "assume" for a field, the validator emits the canonical IS-code default for that field (e.g. concrete grade → M25, cover for footing → 50 mm). The route never tells the model to grade the user — it grades the inputs against engineering plausibility.

- `generate_compliance_report(previous_analysis, user_input, drawing_type, vectordb, embedding_model, k=15)` — the core RAG flow:
  1. Format the refinement prompt with the prior analysis and user input.
  2. Embed the full refinement prompt and pull the top-k chunks from ChromaDB.
  3. Call `o4-mini` (reasoning model) with a strict system prompt that forbids assumed values and requires every row to be tagged `[DRAWING] | [USER-PROVIDED] | [USER-ASSUMED] | [NOT PROVIDED]`.
  4. Post-validate: any row marked `Compliant` that also contains assumption language fails the report (raises `ValueError`, surfaced as HTTP 502). Rows tagged `Conditionally Compliant` are allowed to.
  5. Return `(report_markdown, rag_succeeded)` so the caller can warn the user when RAG silently fell back to no context.

`_handle_api_error` is annotated `NoReturn` so static analysers know it always raises, and so the calling code can be linear.

### 4.7 `prompt.py` — all LLM prompts in one place

Five distinct prompts plus a registry:

- `_EXTRACTION_PREAMBLE` — shared two-phase methodology, Indian RCC drawing convention cheat-sheet (Y-prefix means Fe 500, how to read `Y8-8"`, etc.), and anti-hallucination warnings. This preamble forces the model to transcribe what it sees in Phase 1 before making compliance judgments in Phase 2.
- `INITIAL_EXTRACTION_PROMPT` (foundation), `SLAB_EXTRACTION_PROMPT`, `BEAM_EXTRACTION_PROMPT`, `COLUMN_EXTRACTION_PROMPT` — each builds on the preamble with element-specific checklist rows.
- `ORCHESTRATOR_PROMPT` — three-line classifier.
- `VALIDATOR_PROMPT` — strict validator with a hard-coded standard-defaults table.
- `REFINEMENT_PROMPT_TEMPLATE` — the template used by the RAG reporter. Includes the attribution-rule scaffold that forces the model to tag every row with a source.

`PROMPT_REGISTRY` maps a drawing type to the matching specialist prompt; `llm_handler.py` reads from this map.

### 4.8 `embedding_service.py` — lazy embedder

Exposes `get_embedding_model()`, which on first call constructs a `HuggingFaceEmbeddings(model_name="BAAI/bge-large-en-v1.5", normalize_embeddings=True)`. Lazy initialisation matters: this model is ~1.3 GB on disk and pulls all of `torch` into memory.

`BAAI/bge-large-en-v1.5` is significantly better than `all-MiniLM-L6-v2` on technical text (~64 vs ~57 on MTEB), which matters because IS code passages are dense with engineering terminology and the model has to retrieve clauses by intent, not surface keywords.

### 4.9 `vector_db.py` — ChromaDB wrapper

A thin wrapper around `chromadb.PersistentClient`. Methods:

- `save_documents(documents, ids, embeddings, metadatas)` — bulk insert.
- `query(query_embeddings, n_results, where)` — search by precomputed embedding. Returns a list of `{id, document, metadata, score}` dicts. Metadata is null-safe — if Chroma returns `None` per-document, we coerce to `{}` so downstream code can call `.get()` without guarding.
- `query_by_text(query_text, embedding_model, n_results, where)` — convenience helper that embeds the text first.

### 4.10 `data_loader.py` — markdown chunker

Three specialised splitters used by `ingest.py`:

- `chunk_ocr_file(content, file_name)` — splits an OCR markdown file at heading boundaries, then packs paragraphs into ≤ 1500-character chunks while preserving the section and clause number as metadata.
- `parse_images_tables(content, file_name)` — parser for the cleaned `SP_IMAGES_TABLES.md` file, which has structured `## is_code_chunk_NNN (TABLE|DIAGRAM, Page N)` entries. Lifts the description, page, and any embedded "Symbols & Notation" sub-table into metadata.
- `chunk_guide_file(content, file_name)` — splits the `Reading_RCC_*.md` step-by-step guides at "Step N" or numbered-heading boundaries.

`read_md_files_from_folder` selects the right splitter per filename and returns one flat list of chunks ready to embed.

### 4.11 `ingest.py` — one-time RAG index builder

Loads the markdown chunks, embeds them in batches of 32 (so the model doesn't OOM on a large corpus), wipes the ChromaDB collection, and writes the embeddings back in batches of 500. `--dry-run` prints chunk-type statistics without writing to disk.

You re-run this any time the SP 34 source markdown changes or the embedding model changes (because old vectors are not comparable to new ones).

### 4.12 `clean_docs.py` — one-time SP 34 OCR cleanup

The raw OCR output of SP 34 has noise: repeated "page intentionally left blank" markers, broken LaTeX (`$\mathrm{N}/\mathrm{mm}^2$` → `N/mm²`), duplicated section headers from double-scanned pages, and an enormous pipe-delimited table of images/tables that includes base64-embedded image data.

This script:
- Backs up the source markdown to `SP34_md_backup/` before touching anything.
- Cleans every `SP_34_OCR_*.md` file in place — drops noise, normalises units.
- Rewrites `SP_IMAGES_TABLES.md` into structured `## is_code_chunk_NNN (...)` entries (60–80% size reduction) and drops base64 image content from the text body.

Run once when the source markdown is updated. Then re-run `ingest.py`.

---

## 5. Data model (Supabase)

A single table:

```sql
create table reports (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  session_name text,
  drawing_type text,
  initial_report text,
  final_report text,
  created_at timestamptz default now()
);
alter table reports enable row level security;
create policy "users see own reports" on reports
  for all using (auth.uid() = user_id);
```

Notes:
- `session_name` is the comma-joined filenames, capped at 200 characters server-side.
- `initial_report` and `final_report` are markdown blobs (sizable — easily 30–50 KB each).
- RLS ensures one user cannot read another user's rows even with a valid token. Server-side mutations use the service-role key but always scope by `user_id`.
- `missing_fields` is intentionally not a column. It is re-derived from `initial_report` on demand by `GET /api/reports/{id}/missing-fields`, so the parser can evolve without a migration.

---

## 6. Request lifecycles

### 6.1 First-time analysis

```
Client                    /generate-initial-report               OpenAI / Supabase
  │ POST files                  │
  ├─────────────────────────────► validate JWT (Supabase)
  │                              ├─ open PDF → PIL pages
  │                              ├─ encode pages to base64
  │                              ├─ orchestrator → drawing_type
  │                              ├─ specialist (vision) → markdown report
  │                              ├─ _extract_missing_fields(report)
  │                              ├─ _extract_quality_assessment(report)
  │                              ├─ insert reports row
  ◄──────────────────────────────┤ {report, drawing_type,
                                  │  missing_fields, file_names,
                                  │  report_id, quality_assessment}
```

### 6.2 Filling in missing fields

```
Client                    /validate-input
  │ POST {missing_fields, user_answers}
  ├─────────────────────────────► validate JWT
  │                              ├─ validator agent (gpt-4o-mini)
  ◄──────────────────────────────┤ {valid, invalid_fields, assumed_values}
```

If any field is invalid the client surfaces the error inline and the user fixes it. If everything is valid, the client builds the combined user input (substituting in the assumed values where the user wrote "assume") and posts to `/generate-final-report`.

### 6.3 Final report

```
Client                    /generate-final-report          ChromaDB / OpenAI
  │ POST {initial_report,
  │       user_input,
  │       assumed_values, ...}
  ├─────────────────────────────► validate JWT
  │                              ├─ format REFINEMENT_PROMPT_TEMPLATE
  │                              ├─ embed → ChromaDB.query (top-15 chunks)
  │                              ├─ o4-mini call with system + user prompt
  │                              ├─ post-validate (no Compliant + assumed)
  │                              ├─ update reports.final_report
  ◄──────────────────────────────┤ {report, report_id, rag_context_used}
```

### 6.4 Resume from history

```
Client                    /reports/{id}/missing-fields
  ├─────────────────────────────►
  │                              ├─ fetch initial_report from Supabase
  │                              ├─ _extract_missing_fields(initial_report)
  ◄──────────────────────────────┤ {missing_fields}
  (then proceeds as 6.2)
```

---

## 7. RAG pipeline notes

- **Corpus:** SP 34 (Handbook on Concrete Reinforcement and Detailing) OCR markdown + a curated `Reading_RCC_*.md` guide set + a `SP_IMAGES_TABLES.md` reference of figures and tables.
- **Cleanup:** `clean_docs.py` is mandatory before ingestion — otherwise the corpus drowns the index in OCR junk.
- **Chunking:** section-aware, 1500-char target per chunk, metadata includes `source_file`, `section_number`, `section_title`, `clause_id`, `content_type` (`text|table|image_description`), and `step_number` where applicable.
- **Embeddings:** `BAAI/bge-large-en-v1.5`, normalised. Batch size 32 during ingestion.
- **Retrieval:** the entire refinement prompt is embedded as the query (so user input + prior analysis both contribute). Top-k = 15 by default.
- **Surfacing failures:** when retrieval fails or returns zero hits, the route returns `rag_context_used: false` so the client can warn the user that the verdict is opinion, not citation-backed.

---

## 8. Authentication and security model

- **Tokens.** Supabase issues JWTs. The frontend stores them in `localStorage` (acceptable starting point; XSS-vulnerable in the long term — see §10).
- **Server validation.** Every protected route depends on `get_current_user`, which parses the Bearer token and calls `supabase.auth.get_user(token)`.
- **RLS.** The `reports` table has a "user sees own reports" policy. The service-role key bypasses RLS but the routes always filter by `user_id`.
- **CORS.** Allow-listed origins, no wildcard. Credentials only enabled because the list is finite.
- **Upload limits.** `MAX_UPLOAD_BYTES` rejects anything over 50 MB by default.
- **Filename sanitisation.** `_safe_filename` strips header-injection characters before they touch a `Content-Disposition` header.
- **Logging.** Errors land in the server log via `logging.exception`; the response body never contains the raw exception string.

What is **not** done yet, and should be: rate limiting, request-body size enforcement at the proxy layer, refresh-token rotation, and moving JWTs out of `localStorage`. See §10.

---

## 9. Configuration

All knobs are environment variables. Defaults are designed for local development.

| Variable | Purpose | Default |
|----------|---------|---------|
| `OPENAI_API_KEY` | Required | — |
| `SUPABASE_URL` | Required | — |
| `SUPABASE_KEY` | Anon key, required | — |
| `SUPABASE_SERVICE_ROLE_KEY` | Service-role key, required for inserts | — |
| `CORS_ALLOW_ORIGINS` | Comma-separated allow list | `http://localhost:5173,http://localhost:3000` |
| `LOG_LEVEL` | Python logging level | `INFO` |
| `MAX_UPLOAD_BYTES` | Per-file cap | `52428800` (50 MB) |
| `HOST` / `PORT` / `RELOAD` | uvicorn args when running `python main.py` | `127.0.0.1` / `8000` / `false` |
| `OPENAI_VISION_MODEL` | Specialist agent | `gpt-4o` |
| `OPENAI_ORCHESTRATOR_MODEL` | Classifier | `gpt-4o-mini` |
| `OPENAI_VALIDATOR_MODEL` | Validator | `gpt-4o-mini` |
| `OPENAI_FINAL_REPORT_MODEL` | RAG reporter | `o4-mini` |
| `VITE_API_BASE_URL` | Frontend → backend URL | `http://localhost:8000` |

---

## 10. Frontend overview

React 19 + Vite + Tailwind CSS + React Router. Five real entry points:

- `App.jsx` — Routes (`/login`, `/dashboard`, `/history`, catch-all routes based on auth state).
- `context/AuthContext.jsx` — login/signup/logout, token persistence in `localStorage`, a 401 auto-purge `fetch` wrapper.
- `pages/LoginPage.jsx` — email/password.
- `pages/DashboardPage.jsx` — four-step workflow (upload → initial report → missing data → final report). Drives the API calls; renders the reports.
- `pages/HistoryPage.jsx` — list, view, resume, download, delete.
- `components/FileUpload.jsx` — react-dropzone, restricted to PDF/PNG/JPG.
- `components/ReportDisplay.jsx` — `react-markdown` + GitHub-flavoured markdown plugin + download buttons.
- `components/UserInputForm.jsx` — free-form fallback when no missing fields were detected.
- `components/Sidebar.jsx` — desktop nav and a mobile hamburger toggle.
- `api.js` — every backend call goes through this module. Reads `VITE_API_BASE_URL`. Sends Bearer tokens on every authenticated route.

The frontend has no business logic: it never re-parses the report on the client, never derives missing fields, never assumes a model name. It is purely a presentation layer over the backend's contract.

---

## 11. What to add next

This section is intentionally opinionated. Items are roughly ordered by ROI for a system that runs LLMs in production.

### 11.1 Observability — LangSmith / Helicone / Phoenix

LLM calls happen inside `llm_handler.run_specialist_agent` and `llm_service.generate_compliance_report`. Today, the only record of a call is a log line. That is unworkable once real users are using it.

Three options:

- **[LangSmith](https://docs.smith.langchain.com/)** — first-class tracing, prompt versioning, dataset-driven evals. Integrate by setting `LANGSMITH_TRACING=true`, `LANGSMITH_API_KEY`, and wrapping each agent call with `langsmith.trace`. Works without LangChain — there is a thin `@traceable` decorator for raw OpenAI client calls. Cost: free tier exists; paid tier needed for retention beyond 14 days.

- **[Phoenix (Arize)](https://docs.arize.com/phoenix)** — open-source, OTel-based. Self-hostable. Gives flame-graph traces of agent calls, retrieval, and tool use. Lower lock-in than LangSmith.

- **[Helicone](https://www.helicone.ai/)** — proxy-based; you just point `OPENAI_BASE_URL` at Helicone and it logs every request. Easiest drop-in, but only sees OpenAI calls (no view into RAG, no agent tracing).

**Recommendation:** start with LangSmith for the dev loop (prompt iteration on real traces), add Phoenix later if you need self-hosted retention.

### 11.2 RAG evaluation — RAGAS, TruLens, DeepEval

The retrieval quality is currently not measured. A regression in chunking or embedding model would be invisible.

- **[RAGAS](https://docs.ragas.io/)** — the standard. Define a small dataset of `{question, ground_truth_answer, ground_truth_contexts}` derived from IS 456 / SP 34, then run RAGAS to compute `faithfulness`, `answer_relevancy`, `context_precision`, `context_recall`. Wire into CI so a PR that swaps the embedding model has to prove it didn't regress.
- **[DeepEval](https://docs.confident-ai.com/)** — pytest-style assertions on LLM outputs. Good for "the final report must cite at least one IS clause" type checks.
- **[TruLens](https://www.trulens.org/)** — interactive evaluation UI, less batch-oriented than RAGAS.

**Concrete first step:** build a 50-question evaluation set covering the most common compliance checks (concrete grade, cover, lap length, tie spacing, etc.). Run RAGAS nightly against the live RAG pipeline. Track `context_recall` as the north-star metric — if the IS clause for a question is not in the top-k retrieved chunks, the model has no chance of citing it correctly.

### 11.3 Prompt management — promptfoo, LangSmith Prompts, or a `prompts/` directory

Right now every prompt lives in `prompt.py`. That works at small scale, but you can't A/B prompts or roll them back without a code change.

- **[promptfoo](https://www.promptfoo.dev/)** — declarative prompt evals; integrates with RAGAS.
- **LangSmith Prompts** — versioned prompts hosted externally; fetched at runtime.
- **Local YAML files in `server/prompts/`** — zero-dep, version-controlled, easy to diff. Start here.

### 11.4 Background processing — Celery / RQ / FastAPI BackgroundTasks

`POST /generate-initial-report` blocks for tens of seconds (vision call, especially on multi-page PDFs). The client just spins. Move LLM work to a job queue:

- **[Celery](https://docs.celeryq.dev/) + Redis** — heavy, production-grade.
- **[RQ](https://python-rq.org/)** — lighter, simpler.
- **FastAPI `BackgroundTasks`** — works for fire-and-forget but the client still has to poll for completion.

Pair with a `GET /api/reports/{id}/status` endpoint and Server-Sent Events from the client so the dashboard streams progress.

### 11.5 Caching — semantic and exact

Two layers:

- **Exact-prompt cache.** OpenAI now supports prompt caching natively for prompts ≥ 1024 tokens (the extraction prompts are well above that). It is automatic with `gpt-4o` and the `o-series` models, but you should structure the prompt so the cached prefix is stable: long static preamble first, then volatile user input last. The current preamble layout already does this — but verify with the OpenAI dashboard.

- **Semantic cache for RAG.** [GPTCache](https://gptcache.readthedocs.io/) or your own Redis + embedding-distance check. Many users will ask about the same handful of foundation drawings; caching the orchestrator + extractor by image hash would shave significant cost.

### 11.6 Structured outputs — Pydantic models + `response_format`

The validator and orchestrator already use `response_format=json_object`. The specialist agent does not — its output is free-form markdown. There is value in keeping it markdown (the user reads it), but the extracted fields (`missing_fields`, `quality_assessment`) currently come from regex parsing. Two improvements:

1. Make the model emit a JSON sidecar block alongside the markdown report (`<!--JSON-->{...}<!--/JSON-->`), parsed server-side.
2. Or call a second, cheap model on the markdown to extract the fields with a Pydantic schema.

Option 1 is cheaper; option 2 is more robust if the upstream prompt drifts.

### 11.7 Rate limiting and abuse protection

Add [slowapi](https://slowapi.readthedocs.io/) middleware. Reasonable defaults:

- `/api/auth/login`, `/api/auth/signup`: 5/min per IP.
- `/api/generate-initial-report`, `/api/generate-final-report`: 5/min per user.
- `/api/rag/query`, `/api/download-pdf`: 30/min per user.

### 11.8 Authentication hardening

- Move the JWT out of `localStorage` and into an HTTP-only secure cookie. Requires a token-exchange route on the backend (`POST /api/auth/login` returns a Set-Cookie instead of a body) and CSRF protection on state-changing endpoints.
- Add refresh-token rotation. Supabase issues both — use them.
- Optional: SSO via Supabase's OIDC providers (Google, GitHub) for users who hate passwords.

### 11.9 Persisting derived fields

If you start running evals over historical reports, you'll want `missing_fields`, `quality_assessment.severity`, and the list of cited IS clauses as columns, not regex-derivations. Add a migration:

```sql
alter table reports
  add column missing_fields jsonb default '[]'::jsonb,
  add column severity text,
  add column rejection_narrative text,
  add column rag_chunks jsonb default '[]'::jsonb;
```

Backfill from existing rows by re-running the extractors once.

### 11.10 Multi-page report stitching

A real-world foundation drawing set is 5–20 sheets. Today the agent treats them as one giant batch. Two improvements:

- Per-sheet specialist call, then a "merge" agent that reconciles overlapping schedules.
- Sheet-aware schedule extraction — separate prompts for "title block", "general notes", "column schedule", "footing schedule".

### 11.11 PDF rendering quality

ReportLab is functional but plain. For client deliverables, consider:

- [WeasyPrint](https://weasyprint.org/) — HTML + CSS → PDF. Lets you style the report in CSS, which is much easier than ReportLab's flowable system.
- [Playwright + Chromium](https://playwright.dev/docs/api/class-page#page-pdf) — render the report as a print-stylesheeted HTML page, screenshot to PDF. Highest fidelity, heaviest dependency.

### 11.12 Frontend polish

- Streaming the report into the UI token-by-token (use the OpenAI SDK's stream + Server-Sent Events).
- Storybook for `ReportDisplay`, `FileUpload`, `Sidebar`.
- Playwright end-to-end tests for the happy path: login → upload → validate → final report.

### 11.13 Tests

There are currently no tests. Easy wins:

- **`server/tests/test_extract.py`** — feed canned markdown reports into `_extract_missing_fields` and `_extract_quality_assessment`, assert the output.
- **`server/tests/test_safe_filename.py`** — header-injection unit tests.
- **`server/tests/test_validator.py`** — mock the OpenAI client, assert the validator returns the right `assumed_values` for "assume" inputs.
- **`server/tests/test_rag.py`** — given a synthetic ChromaDB, assert retrieval ranks the right clause first.

`pytest` + `pytest-asyncio` + `respx` for HTTP mocking is the minimum viable stack.

### 11.14 Containerisation and deployment

- Multi-stage `Dockerfile` for the backend: `uv sync --frozen`, then copy the source.
- Separate static-site deploy for the frontend (Vercel, Netlify, Cloudflare Pages, or S3 + CloudFront).
- ChromaDB can run in-process for now; consider [Chroma Cloud](https://www.trychroma.com/cloud) or self-hosted Chroma + Postgres when the corpus grows past a few hundred thousand chunks.

---

## 12. Glossary

- **RCC** — Reinforced Cement Concrete.
- **IS 456:2000** — the Indian Standard for plain and reinforced concrete.
- **SP 34** — the Bureau of Indian Standards handbook for concrete reinforcement and detailing.
- **IS 13920** — ductile detailing for earthquake-resistant design (seismic zones III–V).
- **IS 1786** — the standard for high-strength deformed steel bars and wires.
- **HYSD / TMT** — high-yield strength deformed / thermo-mechanically treated bars (Fe 500 and Fe 550 grades).
- **Lap length** — the overlap distance between two reinforcement bars at a splice (typically ≥ 50× bar diameter).
- **Development length (Ld)** — the length of bar required to transfer stress from steel to concrete.
- **RLS** — Postgres Row-Level Security; Supabase's default authorization mechanism.
- **RAG** — Retrieval-Augmented Generation: embed a query, search a vector store, feed the top-k chunks as context to an LLM.
- **MTEB** — Massive Text Embedding Benchmark; the de facto leaderboard for embedding models.
