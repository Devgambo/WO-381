# 🏗️ Structural Drawing Compliance Checker

> **Upload an RCC structural drawing → get a detailed IS 456 / SP 34 compliance report in seconds.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![React 19](https://img.shields.io/badge/React-19-61DAFB.svg)](https://react.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An AI-powered system that reads Indian RCC structural drawings (foundations, slabs, beams, columns), extracts engineering parameters using GPT-4o vision, validates them against **IS 456:2000** and **SP 34**, and produces a clause-by-clause compliance verdict — all through a modern web interface with real-time progress tracking.

---

## ✨ Key Features

- **Multi-drawing support** — Foundations, Slabs, Beams, and Columns
- **AI vision extraction** — GPT-4o reads dimensions, rebar schedules, and spacing directly from the drawing
- **RAG-powered verdicts** — Final reports cite specific IS code clauses retrieved from a local vector store
- **Multi-agent pipeline** — Orchestrator → Specialist → Validator → RAG Reporter, each with a focused role
- **Smart validation** — The Validator agent catches implausible values and supplies IS-code defaults when the user says "assume"
- **Background processing** — Long AI workflows run as queued jobs with a live progress bar
- **Report history** — Save, resume, and download reports as Markdown or PDF
- **Auth & security** — Supabase auth with refresh-token rotation, RLS, rate limiting, and security headers

---

## 🔄 How It Works

```
  ┌─────────────┐
  │  Upload PDF  │
  │  (drawing)   │
  └──────┬───────┘
         ▼
  ┌─────────────────────┐
  │  1. Classify         │  ← GPT-4o-mini identifies drawing type
  │  2. Vision Extract   │  ← GPT-4o reads engineering params from image
  └──────┬───────────────┘
         ▼
  ┌─────────────────────┐
  │  3. User fills gaps  │  ← Missing fields shown in UI; Validator
  │     + Validate       │    checks plausibility & applies IS defaults
  └──────┬───────────────┘
         ▼
  ┌─────────────────────┐
  │  4. RAG Retrieval    │  ← Relevant IS 456 / SP 34 clauses fetched
  │     (ChromaDB +      │    from local vector store (BGE embeddings
  │      reranker)       │    + cross-encoder reranking + MMR)
  └──────┬───────────────┘
         ▼
  ┌─────────────────────┐
  │  5. Final Report     │  ← o4-mini reasoning model produces a
  │     (compliance      │    clause-by-clause compliance verdict
  │      verdict)        │
  └──────┬───────────────┘
         ▼
    ✅ / ❌ / ⚠️
    Per-check verdict
    with IS code citations
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | React 19 · Vite · Tailwind CSS · React Router · Storybook 9 |
| **Backend** | FastAPI · Python 3.11 · honcho (process manager) |
| **AI / LLM** | GPT-4o (vision) · GPT-4o-mini (orchestrator/validator) · o4-mini (reasoning) |
| **RAG** | ChromaDB · BAAI/bge-large-en-v1.5 · cross-encoder reranker · MMR |
| **Auth & DB** | Supabase (PostgreSQL + Row Level Security) |
| **Jobs** | Redis + RQ (gracefully degrades to in-process for local dev) |
| **PDF** | PyMuPDF (parsing) · ReportLab (generation) |

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+ with [uv](https://docs.astral.sh/uv/)
- Node.js 20+
- OpenAI API key
- Supabase project (free tier works)

### Backend

```bash
cd server
cp .env.example .env          # fill in API keys and Supabase creds

uv sync                       # install dependencies
uv run python clean_docs.py   # one-time: clean source markdown
uv run python ingest.py       # one-time: build the RAG vector index

uv run honcho start            # starts API (port 8000) + worker together
```

> **No Redis?** Leave `REDIS_URL` empty — jobs run in-process automatically.
> **Windows?** Set `RQ_SIMPLE_WORKER=1` in `.env`.

### Frontend

```bash
cd client
npm install
npm run dev                    # → http://localhost:5173
```

### Database

Run these in your Supabase SQL editor:

```sql
-- Reports table
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

-- Jobs table (see server/db/migrations.sql for full DDL)
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

---

## 📁 Project Structure

```
client/                          # React SPA
├── src/
│   ├── api.js                   # API client with job polling & token refresh
│   ├── context/AuthContext.jsx   # JWT auth + silent refresh
│   ├── pages/                   # Login, Dashboard, History
│   └── components/              # FileUpload, ReportDisplay, Sidebar (+stories)
│
server/                          # FastAPI backend
├── main.py                      # Routes, security headers, rate limits
├── tasks.py                     # Worker job functions
├── jobs.py                      # RQ queue + Supabase job-state helpers
├── llm_service.py               # Orchestrator, Validator, RAG Reporter agents
├── llm_handler.py               # Vision extraction (Specialist agent)
├── vector_db.py                 # ChromaDB wrapper (search + MMR + reranking)
├── prompt.py                    # All LLM prompts (per drawing type)
├── Dockerfile + Procfile        # Production container (API + worker)
└── SP34_md/                     # IS code source documents for RAG
```

---

## 🔌 API Reference

Generate routes are **asynchronous** — they return `202 { job_id }` and the client polls for progress.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/auth/signup` | Create account |
| `POST` | `/api/auth/login` | Login (returns access + refresh token) |
| `POST` | `/api/auth/refresh` | Rotate tokens |
| `POST` | `/api/generate-initial-report` | Upload drawing → enqueue extraction → `202` |
| `POST` | `/api/generate-final-report` | Enqueue RAG compliance verdict → `202` |
| `GET` | `/api/jobs/{id}` | Poll job status / progress / result |
| `POST` | `/api/validate-input` | Validate user-supplied fields |
| `GET` | `/api/reports` | List reports |
| `GET` | `/api/reports/{id}` | Get report |
| `DELETE` | `/api/reports/{id}` | Delete report |
| `GET` | `/api/rag/query` | Direct RAG query |
| `POST` | `/api/download-pdf` | Export report as PDF |

**Rate limits:** auth `5/min` · generate `5/min` · query/PDF `30/min` · job polling `120/min`

---

## 🏗️ Indian Standards Covered

| Code | Title |
|------|-------|
| **IS 456:2000** | Plain and Reinforced Concrete — Code of Practice |
| **SP 34** | Handbook on Concrete Reinforcement and Detailing |
| **IS 1786** | High Strength Deformed Steel Bars and Wires |
| **IS 13920** | Ductile Design and Detailing of RC Structures |
| **IS 1893** | Earthquake Resistant Design |
| **IS 875** | Design Loads |

---

## 📄 License

MIT
