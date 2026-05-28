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
| **PDF** | ReportLab |
| **PDF parsing** | PyMuPDF (fitz) |

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (or pip)
- Node.js 20+ / npm
- OpenAI API key
- Supabase project (URL + anon key + service-role key)

### 1. Backend

```bash
cd server

# Configure environment
cat > .env <<'ENV'
OPENAI_API_KEY=sk-...
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_KEY=<anon-key>
SUPABASE_SERVICE_ROLE_KEY=<service-role-key>

# Optional overrides
# CORS_ALLOW_ORIGINS=http://localhost:5173
# HOST=127.0.0.1
# PORT=8000
# RELOAD=true
# LOG_LEVEL=INFO
# MAX_UPLOAD_BYTES=52428800
# OPENAI_VISION_MODEL=gpt-4o
# OPENAI_ORCHESTRATOR_MODEL=gpt-4o-mini
# OPENAI_VALIDATOR_MODEL=gpt-4o-mini
# OPENAI_FINAL_REPORT_MODEL=o4-mini
ENV

# Install
uv sync

# One-time: clean source markdown and build the RAG index
uv run python clean_docs.py
uv run python ingest.py

# Run
uv run uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

Supabase schema:

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

### 2. Frontend

```bash
cd client

cat > .env <<'ENV'
VITE_API_BASE_URL=http://localhost:8000
ENV

npm install
npm run dev
```

App runs at `http://localhost:5173`.

---

## 📁 Project Structure

```
├── client/                     # React 19 frontend (Vite + Tailwind)
│   └── src/
│       ├── api.js              # API client (uses VITE_API_BASE_URL)
│       ├── App.jsx             # Routes
│       ├── components/         # FileUpload, ReportDisplay, Sidebar, UserInputForm
│       ├── context/            # AuthContext (Supabase JWT)
│       └── pages/              # Login, Dashboard, History
│
└── server/                     # FastAPI backend
    ├── main.py                 # Routes
    ├── auth.py                 # Supabase JWT validation
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
    ├── SP34_md/                # Source IS code markdown
    └── chroma_db/              # Persisted vector index
```

---

## 🔌 API Surface

All `/api/*` routes (except `/`, `/api/auth/*`) require `Authorization: Bearer <token>`.

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/auth/signup` | Create user |
| POST | `/api/auth/login` | Email/password login |
| POST | `/api/auth/logout` | Invalidate Supabase session |
| POST | `/api/generate-initial-report` | Upload drawing → classify → extract |
| POST | `/api/generate-final-report` | RAG-backed final verdict |
| POST | `/api/validate-input` | Validate user-supplied missing fields |
| GET  | `/api/reports` | List user's reports |
| GET  | `/api/reports/{id}` | Get a single report |
| GET  | `/api/reports/{id}/missing-fields` | Re-derive missing fields (resume) |
| DELETE | `/api/reports/{id}` | Delete a report |
| GET  | `/api/rag/query` | Direct RAG query (`q`, `k`, `content_type`) |
| POST | `/api/download-pdf` | Markdown → PDF |

---

## 📄 License

MIT.
