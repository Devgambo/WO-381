# 🏗️ Structural Compliance Check using Multi-Agent AI

> **AI-powered analysis of Indian RCC structural drawings (Foundations, Slabs, Beams, Columns) against IS 456:2000 and SP 34.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![React 19](https://img.shields.io/badge/React-19-61DAFB.svg)](https://react.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 📋 Overview

Multi-agent + RAG pipeline that classifies an uploaded structural drawing, extracts engineering parameters, validates user-supplied missing fields, and produces a compliance verdict citing IS code clauses.

Codes covered:
- **IS 456:2000** — Plain & Reinforced Concrete
- **SP 34** — Handbook on Concrete Reinforcement & Detailing
- **IS 1786, IS 13920, IS 1893, IS 875** — referenced in checklists

### Features

- 📄 Foundation / Slab / Beam / Column drawing support
- 🤖 Multi-agent orchestration (Orchestrator → Specialist → Validator → RAG Reporter)
- ✅ Validator agent enforces engineering-plausible answers and supplies IS-code defaults when the user says "assume"
- 📚 RAG over cleaned SP 34 + IS code markdown chunks, embedded with `BAAI/bge-large-en-v1.5`
- 💾 Supabase auth + report history with RLS
- 📊 Markdown and PDF (ReportLab) download
- 🔄 Resume incomplete reports from history
- ⚙️ **Background processing (Redis + RQ)** — long LLM workflows run as jobs; the UI shows a live progress bar and polls for the result
- 🚦 **Rate limiting (slowapi)** on auth, generate, query and download routes
- 🔐 **Auth hardening** — refresh-token rotation, silent + on-401 token refresh, security headers
- 📕 **Storybook** stories for the core UI components

> 📌 New in this release: see [`IMPLEMENTATION.md`](./IMPLEMENTATION.md) for what
> was added and full local-run steps, and [`DEPLOYMENT.md`](./DEPLOYMENT.md) for
> a free-first deploy guide.

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|-----------|
| **Frontend** | React 19, Vite, Tailwind CSS, React Router |
| **Backend** | FastAPI, Pydantic, Python 3.11 |
| **Vision LLM** | OpenAI `gpt-4o` (configurable via `OPENAI_VISION_MODEL`) |
| **Reasoning LLM** | OpenAI `o4-mini` for the final report (configurable via `OPENAI_FINAL_REPORT_MODEL`) |
| **Orchestrator / Validator** | OpenAI `gpt-4o-mini` |
| **Vector store** | ChromaDB (local, persisted at `server/chroma_db/`) |
| **Embeddings** | HuggingFace `BAAI/bge-large-en-v1.5` |
| **Auth & DB** | Supabase (PostgreSQL + RLS) |
| **Background jobs** | Redis + RQ (job state persisted in Supabase) |
| **Rate limiting** | slowapi (Redis- or memory-backed) |
| **Process manager** | honcho (runs API + worker together) |
| **PDF** | ReportLab |
| **PDF parsing** | PyMuPDF (fitz) |
| **Component dev** | Storybook 9 |

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (or pip)
- Node.js 20+ / npm
- OpenAI API key
- Supabase project (URL + anon key + service-role key)
- **Optional:** Docker, for Redis. Without it, background jobs run in-process.

### 1. Backend

```bash
cd server

# Configure environment — every variable is documented in .env.example
cp .env.example .env
#   then fill in OPENAI_API_KEY, SUPABASE_URL, SUPABASE_KEY,
#   SUPABASE_SERVICE_ROLE_KEY. Leave REDIS_URL pointing at localhost if you
#   start Redis below, or comment it out to run jobs in-process.

# (Optional) Redis broker for background jobs + shared rate-limit counters
docker run -d -p 6379:6379 redis:7-alpine

# Install
uv sync

# One-time: clean source markdown and build the RAG index.
# Use --rebuild whenever the embedding model, chunking strategy, or distance
# metric changes; ordinary re-runs upsert in place via stable chunk IDs.
uv run python clean_docs.py
uv run python ingest.py --rebuild

# Run the API + RQ worker together (honcho reads the Procfile)
uv run honcho start

#  …or run them separately:
#  uv run uvicorn main:app --reload --port 8000
#  uv run python worker.py        # only needed when REDIS_URL is set
```

> On Windows, set `RQ_SIMPLE_WORKER=1` in `.env` (the worker can't fork).

Supabase schema — the `reports` table **and** the new `jobs` table
(`server/db/migrations.sql`):

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

-- Background-job tracking (full DDL in server/db/migrations.sql)
create table jobs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  type text not null,
  status text not null default 'queued',
  progress int not null default 0,
  stage text,
  result jsonb,
  error text,
  report_id uuid,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
alter table jobs enable row level security;
create policy "users see own jobs" on jobs
  for all using (auth.uid() = user_id);
```

### 2. Frontend

```bash
cd client

cat > .env <<'ENV'
VITE_API_BASE_URL=http://localhost:8000
ENV

npm install
npm run dev               # app at http://localhost:5173
npm run storybook         # component workshop at http://localhost:6006
```

App runs at `http://localhost:5173`.

---

## 📁 Project Structure

```
├── client/                     # React 19 frontend (Vite + Tailwind)
│   ├── .storybook/             # Storybook 9 config
│   └── src/
│       ├── api.js              # API client: job submit/poll, token refresh
│       ├── App.jsx             # Routes
│       ├── components/         # FileUpload, ReportDisplay, Sidebar, UserInputForm (+ *.stories.jsx)
│       ├── context/            # AuthContext (JWT + silent/on-401 refresh)
│       ├── stories/            # Storybook decorators
│       └── pages/              # Login, Dashboard (job progress), History
│
└── server/                     # FastAPI backend
    ├── main.py                 # Routes (enqueue jobs, security headers, rate limits)
    ├── auth.py                 # JWT validation + refresh-token rotation
    ├── rate_limit.py           # slowapi limiter + limits
    ├── jobs.py                 # RQ queue + Supabase jobs-table helpers
    ├── tasks.py                # Worker job functions (initial / final report)
    ├── worker.py               # RQ worker entrypoint
    ├── extractors.py           # Report parsers (shared by API + worker)
    ├── database.py             # Supabase client init (anon + service role)
    ├── openai_client.py        # Shared OpenAI client + model IDs
    ├── llm_handler.py          # Specialist (vision) agent
    ├── llm_service.py          # Orchestrator, Validator, RAG Reporter
    ├── prompt.py               # All LLM prompts (per drawing type)
    ├── embedding_service.py    # Lazy BAAI/bge-large embedder
    ├── vector_db.py            # ChromaDB wrapper
    ├── data_loader.py          # SP 34 markdown chunking
    ├── ingest.py               # One-time RAG index builder
    ├── clean_docs.py           # One-time SP 34 OCR cleanup
    ├── Dockerfile / Procfile   # API + worker container (honcho)
    ├── .env.example            # All env vars, documented
    ├── db/migrations.sql       # jobs table DDL
    ├── SP34_md/                # Source IS code markdown
    └── chroma_db/              # Persisted vector index
```

---

## 🔌 API Surface

All `/api/*` routes (except `/`, `/api/auth/*`) require `Authorization: Bearer <token>`.

Both generate routes are **asynchronous**: they return `202 { job_id }` and the
client polls `GET /api/jobs/{id}` for progress and the final result.

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/auth/signup` | Create user (returns access + refresh token) |
| POST | `/api/auth/login` | Email/password login (returns access + refresh token) |
| POST | `/api/auth/refresh` | Rotate tokens via refresh token |
| POST | `/api/auth/logout` | Invalidate Supabase session |
| POST | `/api/generate-initial-report` | Upload drawing → **enqueue** classify/extract → `202 { job_id }` |
| POST | `/api/generate-final-report` | **Enqueue** RAG-backed final verdict → `202 { job_id }` |
| GET  | `/api/jobs/{id}` | Poll background job status / progress / result |
| POST | `/api/validate-input` | Validate user-supplied missing fields |
| GET  | `/api/reports` | List user's reports |
| GET  | `/api/reports/{id}` | Get a single report |
| GET  | `/api/reports/{id}/missing-fields` | Re-derive missing fields (resume) |
| DELETE | `/api/reports/{id}` | Delete a report |
| GET  | `/api/rag/query` | Direct RAG query (`q`, `k`, `content_type`) |
| POST | `/api/download-pdf` | Markdown → PDF |

Rate limits apply per token/IP (429 on exceed): auth `5/min`, generate `5/min`,
query & PDF `30/min`, job polling `120/min`.

---

## 📄 License

MIT.
