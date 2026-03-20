# 🏗️ Structural Compliance Check using Multi-Agent AI

> **An intelligent, AI-powered system designed to automatically analyze Reinforced Cement Concrete (RCC) structural drawings (Foundations, Slabs, and Beams) and verify their compliance with Indian Civil Engineering Standards.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![React](https://img.shields.io/badge/React-18+-61DAFB.svg)](https://react.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-009688.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 📋 Overview

This application leverages a sophisticated **Multi-Agent AI Architecture** combined with **RAG (Retrieval-Augmented Generation)** to deeply analyze complex RCC structural engineering drawings. 

It specifically checks designs against:
- **IS 456:2000** — Indian Standard Code of Practice for Plain and Reinforced Concrete
- **SP 34** — Handbook on Concrete Reinforcement and Detailing

By automating the tedious compliance review process, this tool helps structural engineers rapidly identify missing parameters, structural risks, and code violations before construction begins.

### ✨ Key Features

- 📄 **Multi-Element Support** — Effortlessly analyze Foundation, Slab, and Beam structural drawings from a single interface.
- 🤖 **Multi-Agent Orchestration** — An intelligent Orchestrator Agent automatically classifies the uploaded drawing type and dynamically routes it to the correct AI specialist (Foundation, Slab, or Beam Agent).
- ✅ **Interactive Validator Loop** — If crucial data is missing from the drawing, the system prompts the user. A dedicated Validator Agent actively assesses user-supplied answers for engineering plausibility before allowing the report generation to proceed.
- 📚 **RAG-Enhanced Reports** — The final AI report doesn't guess; it uses vector embeddings to retrieve and reference the exact IS code clauses that justify its compliance decisions.
- 💾 **Supabase Integration** — User accounts, session history, and full reports are securely saved to a PostgreSQL database utilizing Row Level Security (RLS).
- 📊 **Professional Exports** — View beautifully formatted reports in the interactive dashboard or download them instantly as PDFs for client delivery.
- 🔄 **Resume Capability** — Started an analysis but didn't finish providing missing data? Seamlessly resume incomplete reports directly from the History dashboard.

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11 or higher
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (blazing fast Python package manager)
- Node.js & npm (for the React frontend)
- [OpenRouter API Key](https://openrouter.ai/) (Provides access to the Gemini 2.5 Flash Vision model)
- [Supabase](https://supabase.com/) Project (Database and Authentication)

### 1. Backend Setup (FastAPI)

```bash
# Navigate to the backend directory
cd server

# Copy environment template
cp .env.example .env

# Edit .env and add your keys:
# OPENROUTER_API_KEY=your_openrouter_api_key_here
# SUPABASE_URL=your_supabase_project_url
# SUPABASE_KEY=your_supabase_service_role_key

# Install all Python dependencies using uv
uv sync

# Initialize and populate the RAG Vector Database (ChromaDB)
uv run python ingest.py

# Start the FastAPI server on port 8000
uv run uvicorn main:app --reload
```

### 2. Frontend Setup (React + Vite)

```bash
# Open a new terminal and navigate to the frontend directory
cd client

# Copy environment template
cp .env.example .env

# Edit .env and add your safe frontend keys:
# VITE_SUPABASE_URL=your_supabase_project_url
# VITE_SUPABASE_ANON_KEY=your_supabase_anon_key
# VITE_API_BASE_URL=http://localhost:8000

# Install Node dependencies
npm install

# Start the Vite development server
npm run dev
```

The frontend application will now be running at `http://localhost:5173`.

---

## 📖 How It Works

The system operates using a state-of-the-art multi-agent workflow:
<img width="1909" height="727" alt="Screenshot 2026-03-19 092558" src="https://github.com/user-attachments/assets/ee7f8098-2857-4f68-8547-d1e5b75ff036" />

### The Multi-Agent Pipeline breakdown:
1. **Orchestrator** — The "manager." It quickly analyzes the visual file to determine if it's a foundation, slab, or beam, ensuring the correct domain logic is applied.
2. **Specialist Extractor** — A vision-enabled agent tailored to the specific structural element. It extracts highly specific engineering parameters (e.g., steel percentage, lap lengths, cover depth) and flags any mandatory data missing from the drawing.
3. **Validator** — The "gatekeeper." If the user manually inputs missing data, the Validator ensures the response is an actual engineering value (and not empty or nonsensical) before advancing the pipeline.
4. **RAG Reporter** — The "auditor." It cross-references the extracted parameters against embedded chunks of the actual IS Code from the Vector DB, generating a definitive compliance verdict (Compliant / Non-Compliant / Warning).

---

## 📁 Project Structure

```
├── client/                     # React / Tailwind Frontend
│   ├── src/
│   │   ├── api.js              # Axios configuration and backend calls
│   │   ├── App.jsx             # React Router setup
│   │   ├── components/         # Reusable UI (Sidebar, FileUpload, ReportDisplay)
│   │   ├── context/            # React Context for Supabase Auth state
│   │   └── pages/              # Views (Dashboard, History, Login)
│   └── package.json            
│
├── server/                     # FastAPI / LangChain Backend
│   ├── main.py                 # Core API endpoints routes
│   ├── llm_handler.py          # Vision AI Specialist agent execution
│   ├── llm_service.py          # Orchestrator, Validator, and RAG Reporter logic
│   ├── prompt.py               # Central registry for all LLM system prompts
│   ├── vector_db.py            # ChromaDB retrieval and querying standard
│   ├── data_loader.py          # Utility for chunking IS Code markdown
│   ├── ingest.py               # Embedding script for the RAG pipeline
│   ├── auth.py                 # Supabase JWT authentication middleware
│   ├── database.py             # Supabase python client init
│   ├── SP34_md/                # Source folder for Raw IS Code markdown files
│   ├── chroma_db/              # Generated vector embeddings output
│   └── pyproject.toml          # uv package dependencies
```

---

## 🛠️ Tech Stack

| Component | Technology Used |
|-----------|-----------------|
| **Frontend UI** | React 18, Vite, Tailwind CSS, React Router |
| **Backend API** | FastAPI, Pydantic, Python 3.11 |
| **AI / LLMs** | Google Gemini 2.5 Flash (Vision & Text) via OpenRouter |
| **Vector Database** | ChromaDB (Local high-performance vector store) |
| **RAG Embeddings** | HuggingFace `sentence-transformers/all-MiniLM-L6-v2` |
| **Auth & Database** | Supabase (PostgreSQL, Row Level Security, JWT) |
| **PDF Generation** | ReportLab (Python PDF creation) |
| **Document Parsing**| PyMuPDF (PDF image extraction) |

---

## 📄 License & Contributing

This project is open-source and available under the MIT License. Contributions are highly encouraged! Feel free to submit a pull request or open an issue if you have suggestions for new features or IS codes to include.
