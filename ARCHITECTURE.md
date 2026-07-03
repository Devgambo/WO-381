# Architecture & Project Guide

This document explains what this repository does, how the pieces fit together, what each backend file is responsible for, and a roadmap of useful things to add next (observability, evaluation, hardening). It is intentionally backend-heavy; the React frontend is described at the end.

---

## 1. What the project does

The application audits Indian Reinforced Cement Concrete (RCC) structural drawings — foundations, slabs, beams, columns — against IS 456:2000 and SP 34. A user uploads a PDF or images, and the system:

1. Classifies which structural element the drawing depicts.
2. Runs a vision model with a specialised prompt to transcribe the drawing and emit a Phase 1 → Phase 4 report.
3. Pulls out fields that the drawing left missing or unverifiable.
4. Asks the user to fill in the missing fields, with the option to type "assume" and let a validator agent supply standards-compliant defaults.
5. Retrieves the relevant IS code clauses via a multi-stage RAG pipeline (dense retrieval → cross-encoder rerank → MMR diversification).
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
                │  Retrieval   → embed → vector → rerank →   │
                │                MMR → context               │
                │  Services    → vector store, embeddings,   │
                │                reranker, PDF rendering     │
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

Two external dependencies do the heavy lifting: OpenAI (vision + reasoning) and Supabase (auth + persistence). The vector store is local on disk (`server/chroma_db/`) — it ships embedded with the backend. The cross-encoder reranker (`BAAI/bge-reranker-base`) and the BGE embedder run in-process.

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
    ├── auth.py                 ← Supabase JWT validation, login/signup/logout, TTL cache
    ├── database.py             ← Supabase client factory (anon + service role)
    ├── openai_client.py        ← shared OpenAI client + model IDs
    ├── llm_handler.py          ← specialist (vision) agent + PDF rasteriser
    ├── llm_service.py          ← orchestrator, validator, RAG reporter
    ├── reranker.py             ← cross-encoder rerank + MMR diversification
    ├── prompt.py               ← every LLM prompt (per drawing type)
    ├── embedding_service.py    ← lazy BAAI/bge-large embedder (with query instruction)
    ├── vector_db.py            ← ChromaDB wrapper (cosine, upsert/delete, MMR-aware)
    ├── data_loader.py          ← chunk SP 34 / IS code markdown (recursive splitter)
    ├── ingest.py               ← idempotent RAG index builder (upsert + prune)
    ├── clean_docs.py           ← one-off: clean SP 34 OCR markdown
    ├── SP34_md/                ← source IS code markdown
    └── chroma_db/              ← persisted vector index (generated)
```

---

## 4. Backend files in detail

The server is split into thin layers: routing (`main.py`) → agents (`llm_handler.py`, `llm_service.py`) → retrieval (`reranker.py`, `vector_db.py`, `embedding_service.py`) → infrastructure (`database.py`, `openai_client.py`, `auth.py`) → prompts (`prompt.py`). Pipeline scripts live next to the app (`ingest.py`, `clean_docs.py`).

### 4.1 `main.py` — HTTP surface and orchestration

This file is the only FastAPI app. It owns CORS, logging, lazy service initialisation, request-size limits, async wrapping, and every route. Important pieces:

- **App setup.** Reads `CORS_ALLOW_ORIGINS`, `LOG_LEVEL`, `MAX_UPLOAD_BYTES`, `MAX_TOTAL_UPLOAD_BYTES`, `MAX_PAGES_PER_PDF`, `HOST`, `PORT`, `RELOAD` from environment. CORS is allow-listed (not wildcard) so credentialed requests work.
- **Lazy loaders.** `get_vectordb()` and `get_embedding_model()` defer the expensive ChromaDB and HuggingFace imports until the first time they are needed, so booting the API doesn't pull a 1.3 GB embedding model and a 280 MB reranker into memory.
- **Async wrapping.** Every blocking CPU/IO/OpenAI call inside an `async def` route runs through `await asyncio.to_thread(...)` (PIL/PyMuPDF rasterisation, base64 encoding, OpenAI client calls, ReportLab PDF generation, Chroma queries). Multi-page PDFs no longer stall the event loop.
- **Helpers.**
  - `_safe_filename` — strips header-injection characters from user-supplied download names.
  - `_content_disposition` — emits an RFC 5987 `Content-Disposition` with both ASCII fallback (`filename="..."`) and UTF-8 form (`filename*=UTF-8''...`) so non-ASCII names display correctly across browsers.
  - `_is_uuid` — rejects malformed `report_id` values at the route boundary (otherwise Supabase raises a 500 on garbage UUIDs).
  - `_read_upload_streaming` — reads the upload in 64 KB chunks and rejects early on overflow against both the per-file `MAX_UPLOAD_BYTES` and the aggregate `MAX_TOTAL_UPLOAD_BYTES` budget — a 200 MB upload no longer eats 200 MB of memory before being rejected.
  - `_open_image_bytes` — opens an image with PIL, forces `.load()` so the decoder buffer can be released, normalises to RGB.
  - `markdown_to_pdf` — converts the report markdown into a ReportLab PDF. Handles headings, tables, lists, inline bold/italic/code. Errors are caught and a fixed message returned — never the raw exception string.
  - `_norm_status` — lowercases, strips bold (`**`) and emoji from a markdown cell so the missing-field extractor matches `"Missing Information ⚠️"` the same as `"missing information"`.
  - `_extract_missing_fields` — parses the Phase-1/Phase-4 markdown returned by the specialist agent and emits a deduplicated list of "this field needs the user to fill it in".
  - `_extract_quality_assessment` — pulls `severity`, `critical_defects_count`, and the `rejection_narrative` block out of the Phase 4 section.
- **Routes** (every authenticated route depends on `get_current_user`):

  | Method | Path | Purpose |
  |--------|------|---------|
  | `POST` | `/api/generate-initial-report` | Upload one or more files. Stream-read with size enforcement, convert PDFs to pages (with a per-PDF page cap), run orchestrator → specialist agent, extract missing fields and quality assessment, persist the row in Supabase. |
  | `POST` | `/api/generate-final-report` | Take the initial report plus user-supplied answers, run the multi-stage RAG pipeline, call the reasoning model, verify the Supabase update touched a row. Returns `rag_context_used` **and** `rag_confidence_low` so the client can warn when retrieval failed or returned only weak hits. |
  | `POST` | `/api/validate-input` | Validate the answers the user filled in. Returns invalid fields and a map of assumed values. Infrastructure errors (OpenAI down) now propagate as 502 instead of being silently treated as `valid=true`. |
  | `GET`  | `/api/rag/query` | Direct RAG query — debug helper, authenticated. Supports `content_type` (`text|table|image_description|procedural_guide`) and `element_type` (`foundation|slab|beam|column|general`) filters. |
  | `POST` | `/api/download-pdf` | Markdown → PDF, returned with an RFC 5987 `Content-Disposition`. |
  | `GET`  | `/api/reports` | List the calling user's reports. |
  | `GET`  | `/api/reports/{id}` | Get one report. |
  | `GET`  | `/api/reports/{id}/missing-fields` | Re-derive missing fields server-side on resume (so the client doesn't keep a duplicated parser). |
  | `DELETE` | `/api/reports/{id}` | Delete a report. |

- **PIL lifecycle.** `generate_initial_report` opens images, hands them to the vision agent, then closes every image in a `finally` block.
- **DB write verification.** Both inserts and updates check `result.data` — a missing row now raises 404 (update) or 500 (insert) instead of returning a 200 with nothing persisted.
- **Error handling.** Every route logs via `logging.exception` and returns a short, fixed message to the client — the raw exception string is never echoed back. `ValueError` from agents (model returned empty content, prompt malformed, post-validation failed) maps to HTTP 502.

### 4.2 `auth.py` — authentication

Four responsibilities:

- `_parse_bearer(authorization)` — strict parser; case-insensitive `bearer`, exactly two whitespace-separated tokens, otherwise 401.
- **In-process TTL cache.** `_USER_CACHE` keeps `{token → (timestamp, user_payload)}` for `SUPABASE_USER_CACHE_TTL` seconds (default 60). Every authenticated request used to round-trip to Supabase auth API; now hot tokens skip that call. The cache is bounded to 1024 entries and self-prunes when full. Logout invalidates the token's cache entry.
- `get_current_user` — FastAPI dependency. Checks the cache, falls back to `supabase.auth.get_user(token)`, returns `{id, email, token}`. The token is forwarded so `/logout` can call `supabase.auth.sign_out(token)` and actually invalidate the session.
- Routes: `POST /api/auth/signup`, `/login`, `/logout`. Login/signup return `{access_token, user_id, email}`. The Pydantic model treats `email` as optional because Supabase supports phone-only accounts.

### 4.3 `database.py` — Supabase clients

Two memoised clients:

- `get_supabase_client()` — uses the anon key. Anything user-facing (auth flow) uses this client so RLS is enforced.
- `get_supabase_admin_client()` — uses the service-role key. Anything server-side that needs to bypass RLS uses this client. **Hard-fails on startup if `SUPABASE_SERVICE_ROLE_KEY` is missing** — previously it silently fell back to the anon key, which left RLS enforced for code that *expected* to bypass it and produced empty-result bugs at runtime.

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

- `pdf_to_images(pdf_source, max_pages=None)` — uses PyMuPDF to rasterise each PDF page at 220 DPI, downscales so the longest side is ≤ 3072 px, and warns when a page approaches OpenAI's 20 MB image limit. Raises `PdfTooLargeError` when the document exceeds `MAX_PAGES_PER_PDF` (default 30), which the route translates to HTTP 413.
- `pil_to_base64(image)` — encodes a PIL image to base64 PNG.
- `run_specialist_agent(base64_images, drawing_type)` — picks the right prompt from `prompt.PROMPT_REGISTRY`, sends it to `gpt-4o` with `detail: "high"` (so the tile-based vision pipeline can read fine reinforcement annotations), and returns the markdown report. **Empty completions are caught and re-raised as `ValueError`** so the missing-field extractor never tries to `.splitlines()` a `None`.

System message reminds the model that the images are attached and that the response must start with `### Phase 1`. This is a defence against the "I'm unable to view images" preamble that vision models sometimes emit when they haven't processed image tokens yet.

### 4.6 `llm_service.py` — orchestrator, validator, RAG reporter

Three top-level functions plus retrieval helpers.

- `classify_drawing_type(base64_images)` — runs the orchestrator prompt. Uses `response_format=json_object` so the answer is `{"type": "foundation"|"slab"|"beam"|"column"|"unknown"}`. Falls back to a regex if the JSON parse fails, and pins anything unexpected to `"unknown"`.

- `validate_user_input(missing_fields, user_answers)` — runs the validator prompt. Returns `{valid, invalid_fields, assumed_values}`. **Infrastructure errors (APIError) are re-raised** — a downed OpenAI no longer silently passes invalid data into the final report. Only JSON parse failures fall through with `valid=true`.

- `generate_compliance_report(previous_analysis, user_input, drawing_type, vectordb, embedding_model)` — the core RAG flow. Returns a **3-tuple `(report_markdown, rag_succeeded, rag_confidence_low)`** so the caller can warn the user when RAG silently fell back, *or* when the top-ranked passages were below the confidence threshold:
  1. Build the refinement prompt by `str.replace`-ing sentinels (`<<DRAWING_TYPE>>`, `<<PREVIOUS_ANALYSIS>>`, `<<USER_INPUT>>`) — no more `.format()` crashes on stray `{` / `}` in the model's prior output.
  2. Run `_retrieve_with_context` (see below).
  3. Call `o4-mini` (reasoning model) with a strict system prompt that forbids assumed values and requires every row to be tagged `[DRAWING] | [USER-PROVIDED] | [USER-ASSUMED] | [NOT PROVIDED]`.
  4. Detect empty completions (`o4-mini` can spend its budget on reasoning tokens and return nothing) and surface a specific retry message.
  5. Post-validate: any row whose **rightmost cell only** is bare `Compliant` AND that contains assumption language fails the report. `Conditionally Compliant` rows are exempt. The check no longer false-positives on rows that merely mention the word "compliant" in an IS clause reference.
  6. Confirm at least one markdown table header has a `Source` column.

- `_retrieve_with_context` is where most of the v2 RAG work lives:
  - Builds a `where={"element_type": {"$in": [drawing_type, "general"]}}` filter so beam queries don't get crowded by column clauses (and vice versa).
  - Parses compliance-row labels from `previous_analysis`. If between 1 and `RAG_MAX_SUBQUERIES` rows are recoverable, runs **one short embedding query per row** at `RAG_PER_QUERY_K` hits each — a far cleaner signal than embedding the whole multi-thousand-token refinement prompt (which previously dominated the embedding with template boilerplate and silently truncated past BGE's 512-token cap).
  - Falls back to a focused single query (drawing_type + topics + first 500 chars of user_input) when row parsing returns nothing or too many rows.
  - Deduplicates the candidate union by chunk ID, keeping the best per-query score.
  - Runs the candidates through `cross_encoder_rerank` (top-N, default 40) and then `mmr_select` (top-K, default 10). Either stage can be disabled via env.
  - Flags `rag_confidence_low = true` when the max rerank score falls below `RAG_MIN_SCORE`.

`_handle_api_error` is annotated `NoReturn` so static analysers know it always raises, and so the calling code can be linear.

### 4.7 `reranker.py` — cross-encoder rerank + MMR

New in v2. Two-stage diversity / quality filter that runs after dense retrieval:

- `get_reranker()` — lazy `sentence_transformers.CrossEncoder(BAAI/bge-reranker-base)`. Honours `RERANK_ENABLED`; returns `None` (no-op) when disabled or the model fails to load.
- `cross_encoder_rerank(query, results, top_k)` — scores every (query, document) pair, stamps `rerank_score` onto each candidate, returns the top-K by that score. Falls back to original order on model failure.
- `mmr_select(query_embedding, results, top_k, lambda=MMR_LAMBDA)` — Maximal Marginal Relevance over candidates that carry an `embedding` field. Picks the most-relevant document first, then trades off relevance against pairwise novelty (λ=0.7 default), so the top-K context the LLM sees isn't ten paraphrases of the same clause. Honours `MMR_ENABLED`.

### 4.8 `prompt.py` — all LLM prompts in one place

Five distinct prompts plus a registry:

- `_EXTRACTION_PREAMBLE` — shared two-phase methodology, Indian RCC drawing convention cheat-sheet (Y-prefix means Fe 500, how to read `Y8-8"`, etc.), and anti-hallucination warnings. This preamble forces the model to transcribe what it sees in Phase 1 before making compliance judgments in Phase 2.
- `INITIAL_EXTRACTION_PROMPT` (foundation), `SLAB_EXTRACTION_PROMPT`, `BEAM_EXTRACTION_PROMPT`, `COLUMN_EXTRACTION_PROMPT` — each builds on the preamble with element-specific checklist rows.
- `ORCHESTRATOR_PROMPT` — three-line classifier.
- `VALIDATOR_PROMPT` — strict validator with a hard-coded standard-defaults table. Still uses Python `str.format` because it has no user-content slots that can carry braces.
- `REFINEMENT_PROMPT_TEMPLATE` — used by the RAG reporter. Uses **sentinel tokens** (`<<DRAWING_TYPE>>`, `<<PREVIOUS_ANALYSIS>>`, `<<USER_INPUT>>`) so `str.replace` can substitute arbitrary content without escaping braces.

`PROMPT_REGISTRY` maps a drawing type to the matching specialist prompt; `llm_handler.py` reads from this map.

### 4.9 `embedding_service.py` — lazy embedder

Exposes `get_embedding_model()`, which on first call constructs a `HuggingFaceEmbeddings(model_name="BAAI/bge-large-en-v1.5", normalize_embeddings=True, query_instruction=BGE_QUERY_INSTRUCTION)`. Lazy initialisation matters: this model is ~1.3 GB on disk and pulls all of `torch` into memory.

The `query_instruction` prefix (`"Represent this sentence for searching relevant passages: "` by default — override via `BGE_QUERY_INSTRUCTION`) is applied to queries only, never to documents — that asymmetry is how BGE was trained and it tangibly improves retrieval recall on short queries.

`BAAI/bge-large-en-v1.5` significantly outperforms `all-MiniLM-L6-v2` on technical text (~64 vs ~57 on MTEB), which matters because IS code passages are dense with engineering terminology.

### 4.10 `vector_db.py` — ChromaDB wrapper

A thin wrapper around `chromadb.PersistentClient`. Methods:

- Collection is created with `hnsw:space=cosine` so distance scores land in `[0, 1]` instead of the confusing 0–2 range that L2-over-normalised-vectors produces. Existing collections retain their original metric — run `ingest.py --rebuild` once to switch.
- `save_documents` / `upsert` — bulk add / bulk overwrite. The reingest pipeline uses `upsert` so re-runs don't produce duplicate vectors.
- `all_ids` / `delete` — used by `ingest.py` to prune chunks that no longer exist in the source corpus.
- `query(query_embeddings, n_results, where, include_embeddings=False)` — search by precomputed embedding. Returns `{id, document, metadata, score}` dicts, optionally with `embedding` when MMR needs it. Metadata is null-safe — if Chroma returns `None` per-document, we coerce to `{}` so downstream code can call `.get()` without guarding.
- `query_by_text` — convenience helper that embeds first.

### 4.11 `data_loader.py` — markdown chunker

Three specialised splitters used by `ingest.py`, all routed through a recursive character splitter (`chunk_size=900`, `chunk_overlap=200`):

- `chunk_ocr_file(content, file_name)` — splits an OCR markdown file at heading boundaries (`#`–`####`), tracks `(section_number, section_title, clause_id)` across the file, then runs each paragraph block through the recursive splitter so no chunk exceeds BGE's effective context.
- `parse_images_tables(content, file_name)` — parser for the cleaned `SP_IMAGES_TABLES.md` file, which has structured `## is_code_chunk_NNN (TABLE|DIAGRAM, Page N)` entries. Lifts the description, page, and any embedded "Symbols & Notation" sub-table into metadata.
- `chunk_guide_file(content, file_name)` — splits the `Reading_RCC_*.md` step-by-step guides at "Step N" or numbered-heading boundaries.

Every chunk's `content` field now starts with a **parent-section prefix** (`[§5.3 Cl. 26.4.2.1 — Clear Cover]`) so even a tiny chunk has lexical anchoring for the embedder. Every chunk carries `element_type ∈ {foundation, slab, beam, column, general}` — filename first, then a keyword fallback on the body — which is what the runtime `where` filter keys on. IDs are deterministic sha1s over `(source_file, clause_id, chunk_index, content[:200])` so re-ingests are idempotent.

`read_md_files_from_folder` selects the right splitter per filename and returns one flat list of chunks ready to embed.

### 4.12 `ingest.py` — RAG index builder

Loads the markdown chunks, embeds them in batches of 32 (so the model doesn't OOM), and **upserts** into ChromaDB in batches of 500. Stable chunk IDs mean a re-run only touches chunks whose content actually changed. Chunks that disappear from the source corpus are pruned by ID.

`--rebuild` wipes the DB and starts from a clean collection — required when the embedding model, chunking strategy, or distance metric changes (because old vectors are not comparable to new ones).
`--dry-run` prints chunk-type statistics without writing to disk.

### 4.13 `clean_docs.py` — one-time SP 34 OCR cleanup

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
  ├─────────────────────────────► validate JWT (cached, 60s TTL)
  │                              ├─ stream-read each file (per-file + aggregate cap)
  │                              ├─ open PDF → PIL pages (asyncio.to_thread, ≤ MAX_PAGES_PER_PDF)
  │                              ├─ encode pages to base64 (asyncio.to_thread)
  │                              ├─ orchestrator → drawing_type (asyncio.to_thread)
  │                              ├─ specialist (vision) → markdown report (asyncio.to_thread)
  │                              ├─ _extract_missing_fields(report)
  │                              ├─ _extract_quality_assessment(report)
  │                              ├─ insert reports row (verify result.data)
  ◄──────────────────────────────┤ {report, drawing_type,
                                  │  missing_fields, file_names,
                                  │  report_id, quality_assessment}
```

### 6.2 Filling in missing fields

```
Client                    /validate-input
  │ POST {missing_fields, user_answers}
  ├─────────────────────────────► validate JWT
  │                              ├─ validator agent (gpt-4o-mini, asyncio.to_thread)
  ◄──────────────────────────────┤ {valid, invalid_fields, assumed_values}
```

If any field is invalid the client surfaces the error inline and the user fixes it. If everything is valid, the client builds the combined user input (substituting in the assumed values where the user wrote "assume") and posts to `/generate-final-report`.

### 6.3 Final report (multi-stage RAG)

```
Client                    /generate-final-report          ChromaDB / Reranker / OpenAI
  │ POST {initial_report, user_input, assumed_values, ...}
  ├─────────────────────────────► validate JWT + UUID check on report_id
  │                              ├─ sentinel-replace refinement template
  │                              ├─ parse compliance-row sub-queries from initial_report
  │                              ├─ for each sub-query (≤ RAG_MAX_SUBQUERIES):
  │                              │     embed (BGE, with query instruction)
  │                              │     ChromaDB.query(top RAG_PER_QUERY_K,
  │                              │                    where=element_type ∈ {drawing_type, general},
  │                              │                    include_embeddings=mmr_on)
  │                              ├─ dedupe candidates by ID (keep best score)
  │                              ├─ cross-encoder rerank (top RAG_TOP_N → RAG_TOP_N)
  │                              ├─ MMR diversify → top RAG_TOP_K
  │                              ├─ low_confidence = max(rerank) < RAG_MIN_SCORE
  │                              ├─ o4-mini call with system + user prompt
  │                              ├─ detect empty completion → 502 retry
  │                              ├─ post-validate (status-cell-only Compliant check + Source column)
  │                              ├─ update reports.final_report (verify result.data)
  ◄──────────────────────────────┤ {report, report_id,
                                  │  rag_context_used, rag_confidence_low}
```

### 6.4 Resume from history

```
Client                    /reports/{id}/missing-fields
  ├─────────────────────────────► UUID + JWT
  │                              ├─ fetch initial_report from Supabase
  │                              ├─ _extract_missing_fields(initial_report)
  ◄──────────────────────────────┤ {missing_fields}
  (then proceeds as 6.2)
```

The Dashboard pre-fills missing-field answers from the sessionStorage draft keyed by `reportId`, so a page refresh mid-flow doesn't lose typed input.

---

## 7. RAG pipeline notes

- **Corpus:** SP 34 (Handbook on Concrete Reinforcement and Detailing) OCR markdown + a curated `Reading_RCC_*.md` guide set + a `SP_IMAGES_TABLES.md` reference of figures and tables.
- **Cleanup:** `clean_docs.py` is mandatory before ingestion — otherwise the corpus drowns the index in OCR junk.
- **Chunking:** recursive character splitter, `chunk_size=900`, `chunk_overlap=200`. Each chunk is prefixed with its parent section / clause heading. Metadata includes `source_file`, `section_number`, `section_title`, `clause_id`, `content_type` (`text|table|image_description|procedural_guide`), `element_type`, and `step_number` where applicable. Deterministic sha1 IDs.
- **Embeddings:** `BAAI/bge-large-en-v1.5`, normalised, with the BGE query-instruction prefix on queries only. Batch size 32 during ingestion.
- **Distance metric:** cosine (Chroma `hnsw:space=cosine`). Run `python ingest.py --rebuild` once when migrating an older index.
- **Query construction:** *focused*. Never the full multi-thousand-token refinement prompt. When the prior analysis is parseable, we issue one short embedded query per compliance row (≤ `RAG_MAX_SUBQUERIES`). Otherwise a single focused query of drawing type + topic labels + the first 500 chars of user input.
- **Metadata filter:** `element_type ∈ {drawing_type, general}` is applied at query time so beam queries don't compete with column or slab clauses.
- **Reranker:** cross-encoder `BAAI/bge-reranker-base`. Top-N=40 candidates → top-N reranked. Toggleable via `RERANK_ENABLED`.
- **Diversification:** MMR (`λ=0.7` default, env-tunable) trims to top-K=10. Keeps the LLM context from being ten paraphrases of the same clause.
- **Surfacing failures:**
  - `rag_context_used=false` when retrieval blew up or returned zero hits.
  - `rag_confidence_low=true` when the best rerank score is below `RAG_MIN_SCORE`. The Dashboard renders an amber banner in both cases.

---

## 8. Authentication and security model

- **Tokens.** Supabase issues JWTs. The frontend stores them in `localStorage` (acceptable starting point; XSS-vulnerable in the long term — see §11.8).
- **Server validation.** Every protected route depends on `get_current_user`, which parses the Bearer token, hits an in-process TTL cache, and falls back to `supabase.auth.get_user(token)` on miss. Logout invalidates the cached entry and calls `sign_out`.
- **RLS.** The `reports` table has a "user sees own reports" policy. The service-role key bypasses RLS but the routes always filter by `user_id`. Missing service-role key fails at startup, not at first write.
- **CORS.** Allow-listed origins, no wildcard. Credentials only enabled because the list is finite.
- **Upload limits.** Per-file (`MAX_UPLOAD_BYTES`, default 50 MB) and aggregate (`MAX_TOTAL_UPLOAD_BYTES`, default 150 MB) enforced via streaming read. PDFs over `MAX_PAGES_PER_PDF` (default 30) get a 413 before any vision call is made.
- **Filename sanitisation.** `_safe_filename` strips header-injection characters and `_content_disposition` emits RFC 5987 ASCII fallback + UTF-8 form so non-ASCII names render correctly and can't smuggle CRLF.
- **UUID validation.** Every route that takes `report_id` rejects malformed UUIDs at the boundary (400) — Supabase doesn't have to defend itself against garbage input.
- **Markdown rendering.** `react-markdown@10` escapes raw HTML by default and `rehype-raw` is deliberately not wired in, so model-generated `<img onerror=...>` renders as literal text. Comment in `ReportDisplay.jsx` calls this out.
- **Logging.** Errors land in the server log via `logging.exception`; the response body never contains the raw exception string.

What is **not** done yet, and should be: rate limiting, request-body size enforcement at the proxy layer, refresh-token rotation, and moving JWTs out of `localStorage`. See §11.

---

## 9. Configuration

All knobs are environment variables. Defaults are designed for local development.

| Variable | Purpose | Default |
|----------|---------|---------|
| `OPENAI_API_KEY` | Required | — |
| `SUPABASE_URL` | Required | — |
| `SUPABASE_KEY` | Anon key, required | — |
| `SUPABASE_SERVICE_ROLE_KEY` | Service-role key, required (hard-fail if missing) | — |
| `CORS_ALLOW_ORIGINS` | Comma-separated allow list | `http://localhost:5173,http://localhost:3000` |
| `LOG_LEVEL` | Python logging level | `INFO` |
| `MAX_UPLOAD_BYTES` | Per-file cap | `52428800` (50 MB) |
| `MAX_TOTAL_UPLOAD_BYTES` | Aggregate per-request cap | `157286400` (150 MB) |
| `MAX_PAGES_PER_PDF` | Per-document page cap | `30` |
| `HOST` / `PORT` / `RELOAD` | uvicorn args when running `python main.py` | `127.0.0.1` / `8000` / `false` |
| `OPENAI_VISION_MODEL` | Specialist agent | `gpt-4o` |
| `OPENAI_ORCHESTRATOR_MODEL` | Classifier | `gpt-4o-mini` |
| `OPENAI_VALIDATOR_MODEL` | Validator | `gpt-4o-mini` |
| `OPENAI_FINAL_REPORT_MODEL` | RAG reporter | `o4-mini` |
| `BGE_QUERY_INSTRUCTION` | BGE query-side prefix | `"Represent this sentence for searching relevant passages: "` |
| `RERANK_ENABLED` | Toggle cross-encoder rerank | `true` |
| `RERANK_MODEL` | Reranker checkpoint | `BAAI/bge-reranker-base` |
| `MMR_ENABLED` | Toggle MMR diversification | `true` |
| `MMR_LAMBDA` | MMR relevance↔diversity trade-off (1.0 = pure relevance) | `0.7` |
| `RAG_TOP_N` | Candidates retrieved before rerank | `40` |
| `RAG_TOP_K` | Final chunks passed to the reasoning model | `10` |
| `RAG_PER_QUERY_K` | Hits per sub-query in multi-query mode | `5` |
| `RAG_MAX_SUBQUERIES` | Hard cap on sub-queries per request | `8` |
| `RAG_MIN_SCORE` | Below this max rerank score → `rag_confidence_low=true` | `0.0` |
| `SUPABASE_USER_CACHE_TTL` | Auth cache duration (seconds) | `60` |
| `VITE_API_BASE_URL` | Frontend → backend URL | `http://localhost:8000` |

---

## 10. Frontend overview

React 19 + Vite + Tailwind CSS + React Router.

- `App.jsx` — Routes (`/login`, `/dashboard`, `/history`, catch-all routes based on auth state).
- `context/AuthContext.jsx` — login/signup/logout, token persistence in `localStorage`, a 401 auto-purge `fetch` wrapper that is **idempotent under React StrictMode** (guarded by `Symbol.for('__auth_fetch_wrapped__')`) and a cross-tab `storage` listener so logging out in one tab logs out the others.
- `pages/LoginPage.jsx` — email/password. `autoComplete` + `htmlFor`/`id` labels for password-manager and accessibility wins.
- `pages/DashboardPage.jsx` — four-step workflow (upload → initial report → missing data → final report). Highlights:
  - `useRef` in-flight guard prevents duplicate `reports` inserts when the user clicks generate twice in 50 ms.
  - File de-dup by `name|size|lastModified` so the same drawing doesn't get processed twice.
  - Resume effect fires exactly once per `location.key`; cleared `location.state` no longer retriggers it.
  - Missing-field inputs live inside an actual `<form onSubmit>` with `htmlFor`/`id` pairings so Enter submits and screen-readers announce labels.
  - `sessionStorage` draft persistence keyed by `reportId` — a mid-flow page refresh restores the typed answers.
  - Renders an amber banner whenever the server reports `rag_context_used=false` or `rag_confidence_low=true`.
- `pages/HistoryPage.jsx` — list, view, resume, download, delete. `deletingIds: Set<string>` so concurrent deletes show their own spinners; `AbortController` cancels in-flight loads on unmount.
- `components/FileUpload.jsx` — react-dropzone, restricted to PDF/PNG/JPG.
- `components/ReportDisplay.jsx` — `react-markdown` + GitHub-flavoured markdown plugin + download buttons. Defers `URL.revokeObjectURL` 1 s so Safari finishes the download.
- `components/UserInputForm.jsx` — `<label htmlFor>` + real-newline backtick placeholder.
- `components/Sidebar.jsx` — desktop nav and a mobile hamburger toggle.
- `api.js` — every backend call goes through this module. Reads `VITE_API_BASE_URL`. Sends Bearer tokens on every authenticated route. Defers `URL.revokeObjectURL` after PDF downloads.

The frontend has no business logic: it never re-parses the report on the client, never derives missing fields, never assumes a model name. It is purely a presentation layer over the backend's contract.

---

## 11. What to add next

This section is intentionally opinionated. Items are roughly ordered by ROI for a system that runs LLMs in production. Items marked **(done)** were shipped in v2; the rest remain open.

### 11.1 Observability — LangSmith / Helicone / Phoenix

LLM calls happen inside `llm_handler.run_specialist_agent` and `llm_service.generate_compliance_report`. Today, the only record of a call is a log line. That is unworkable once real users are using it.

Three options:

- **[LangSmith](https://docs.smith.langchain.com/)** — first-class tracing, prompt versioning, dataset-driven evals. Integrate by setting `LANGSMITH_TRACING=true`, `LANGSMITH_API_KEY`, and wrapping each agent call with `langsmith.trace`. Works without LangChain — there is a thin `@traceable` decorator for raw OpenAI client calls. Cost: free tier exists; paid tier needed for retention beyond 14 days.

- **[Phoenix (Arize)](https://docs.arize.com/phoenix)** — open-source, OTel-based. Self-hostable. Gives flame-graph traces of agent calls, retrieval, and tool use. Lower lock-in than LangSmith.

- **[Helicone](https://www.helicone.ai/)** — proxy-based; you just point `OPENAI_BASE_URL` at Helicone and it logs every request. Easiest drop-in, but only sees OpenAI calls (no view into RAG, no agent tracing).

**Recommendation:** start with LangSmith for the dev loop (prompt iteration on real traces), add Phoenix later if you need self-hosted retention.

### 11.2 RAG evaluation — RAGAS, TruLens, DeepEval

Retrieval quality is now better instrumented (rerank scores, `rag_confidence_low`) but still not *measured* against a golden set. A regression in chunking or embedding model would still be invisible.

- **[RAGAS](https://docs.ragas.io/)** — the standard. Define a small dataset of `{question, ground_truth_answer, ground_truth_contexts}` derived from IS 456 / SP 34, then run RAGAS to compute `faithfulness`, `answer_relevancy`, `context_precision`, `context_recall`. Wire into CI so a PR that swaps the embedding model has to prove it didn't regress.
- **[DeepEval](https://docs.confident-ai.com/)** — pytest-style assertions on LLM outputs. Good for "the final report must cite at least one IS clause" type checks.
- **[TruLens](https://www.trulens.org/)** — interactive evaluation UI, less batch-oriented than RAGAS.

**Concrete first step:** build a 50-question evaluation set covering the most common compliance checks (concrete grade, cover, lap length, tie spacing, etc.). Run RAGAS nightly against the live RAG pipeline. Track `context_recall` as the north-star metric — if the IS clause for a question is not in the top-K retrieved chunks, the model has no chance of citing it correctly. The reranker score is already available per-chunk to feed in as a feature.

### 11.3 Prompt management — promptfoo, LangSmith Prompts, or a `prompts/` directory

Right now every prompt lives in `prompt.py`. That works at small scale, but you can't A/B prompts or roll them back without a code change.

- **[promptfoo](https://www.promptfoo.dev/)** — declarative prompt evals; integrates with RAGAS.
- **LangSmith Prompts** — versioned prompts hosted externally; fetched at runtime.
- **Local YAML files in `server/prompts/`** — zero-dep, version-controlled, easy to diff. Start here.

### 11.4 Background processing — Celery / RQ / FastAPI BackgroundTasks

`POST /generate-initial-report` and `/generate-final-report` are now `asyncio.to_thread`-wrapped so they no longer block the event loop, but the client request still hangs for tens of seconds. Move LLM work to a job queue:

- **[Celery](https://docs.celeryq.dev/) + Redis** — heavy, production-grade.
- **[RQ](https://python-rq.org/)** — lighter, simpler.
- **FastAPI `BackgroundTasks`** — works for fire-and-forget but the client still has to poll for completion.

Pair with a `GET /api/reports/{id}/status` endpoint and Server-Sent Events from the client so the dashboard streams progress.

### 11.5 Caching — semantic and exact

Two layers, partly addressed:

- **Auth cache. (done)** `auth.py` keeps a 60 s in-process TTL cache on `get_user`. Hot paths skip Supabase round-trips.
- **Exact-prompt cache.** OpenAI now supports prompt caching natively for prompts ≥ 1024 tokens (the extraction prompts are well above that). It is automatic with `gpt-4o` and the `o-series` models, but you should structure the prompt so the cached prefix is stable: long static preamble first, then volatile user input last. The current preamble layout already does this — verify with the OpenAI dashboard.
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

Aggregate upload caps now protect against single-shot abuse; rate limiting is the next gap.

### 11.8 Authentication hardening

- Move the JWT out of `localStorage` and into an HTTP-only secure cookie. Requires a token-exchange route on the backend (`POST /api/auth/login` returns a Set-Cookie instead of a body) and CSRF protection on state-changing endpoints.
- Add refresh-token rotation. Supabase issues both — use them.
- Optional: SSO via Supabase's OIDC providers (Google, GitHub) for users who hate passwords.

### 11.9 Persisting derived fields

If you start running evals over historical reports, you'll want `missing_fields`, `quality_assessment.severity`, the list of cited IS clauses, *and the reranked RAG chunks* as columns, not regex-derivations. Add a migration:

```sql
alter table reports
  add column missing_fields jsonb default '[]'::jsonb,
  add column severity text,
  add column rejection_narrative text,
  add column rag_chunks jsonb default '[]'::jsonb,
  add column rag_confidence_low boolean default false;
```

Backfill from existing rows by re-running the extractors once.

### 11.10 Multi-page report stitching

A real-world foundation drawing set is 5–20 sheets. Today the agent treats them as one giant batch capped at `MAX_PAGES_PER_PDF`. Two improvements:

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
- **`server/tests/test_safe_filename.py`** — header-injection + UTF-8 Content-Disposition unit tests.
- **`server/tests/test_validator.py`** — mock the OpenAI client, assert the validator returns the right `assumed_values` for "assume" inputs.
- **`server/tests/test_rag.py`** — given a synthetic ChromaDB, assert retrieval ranks the right clause first and that the reranker reorders correctly.
- **`server/tests/test_data_loader.py`** — golden chunking output for a known SP 34 section.

`pytest` + `pytest-asyncio` + `respx` for HTTP mocking is the minimum viable stack.

### 11.14 Containerisation and deployment

- Multi-stage `Dockerfile` for the backend: `uv sync --frozen`, then copy the source.
- Separate static-site deploy for the frontend (Vercel, Netlify, Cloudflare Pages, or S3 + CloudFront).
- ChromaDB can run in-process for now; consider [Chroma Cloud](https://www.trychroma.com/cloud) or self-hosted Chroma + Postgres when the corpus grows past a few hundred thousand chunks.

### 11.15 Hybrid retrieval (BM25 + dense) and HyDE

Skipped in v2 (Moderate scope). The current pipeline is dense-only — reranked and diversified, but dense. Two additions for hard cases:

- **Hybrid BM25 + dense fusion** (Reciprocal Rank Fusion). Catches exact-match queries that miss the embedder ("IS 456 Cl. 26.4.2.1").
- **HyDE / query expansion.** Use a cheap LLM to draft a hypothetical answer, embed *that*, retrieve against it. Lifts recall on under-specified questions.

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
- **RAG** — Retrieval-Augmented Generation: embed a query, search a vector store, feed the top-K chunks as context to an LLM.
- **Cross-encoder reranker** — a model that takes (query, document) pairs and outputs a relevance score; far more accurate than dense similarity at the cost of one model call per candidate. We use `BAAI/bge-reranker-base`.
- **MMR** — Maximal Marginal Relevance. Picks each next document to maximise relevance to the query while penalising similarity to already-picked documents.
- **MTEB** — Massive Text Embedding Benchmark; the de facto leaderboard for embedding models.
