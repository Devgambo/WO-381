# Project Documentation

## Overview

This project is a **Foundation Compliance Check System** that uses AI to analyze RCC (Reinforced Cement Concrete) structural drawings for compliance with Indian civil engineering standards: **IS 456:2000** and **SP 34**.

---

## Core Application Files

### `final.py`
**Main Streamlit web application.**

- Provides a user-friendly web interface for uploading PDF/image drawings
- Handles the complete workflow: upload → initial analysis → user input → final report
- Generates downloadable compliance reports in Markdown and PDF formats
- Uses `markdown_to_pdf()` for PDF conversion with WeasyPrint or ReportLab fallback

### `FINAL.ipynb`
**Jupyter notebook version of the application.**

- Alternative interface for running the analysis step-by-step
- Useful for debugging, experimentation, and batch processing
- Same functionality as `final.py` but in notebook format

---

## LLM & AI Services

### `llm_handler.py`
**PDF/Image analysis using OpenRouter API.**

| Function | Description |
|----------|-------------|
| `pdf_to_images()` | Converts PDF pages to PIL Image objects using PyMuPDF |
| `pil_to_base64()` | Encodes images to base64 for API transmission |
| `analyze_rcc_drawing()` | Analyzes PDF drawings with vision LLM |
| `analyze_rcc_drawing_from_images()` | Analyzes image files directly |

Uses **Google Gemini 2.5 Flash** model via OpenRouter for vision analysis.

### `llm_service.py`
**Final compliance report generation with RAG (Retrieval-Augmented Generation).**

| Function | Description |
|----------|-------------|
| `generate_compliance_report()` | Combines initial report + user input + IS code context to generate final report |

- Embeds the query and retrieves relevant IS code sections from ChromaDB
- Uses structured prompts for consistent, professional output
- Returns comprehensive Markdown-formatted compliance reports

### `prompt.py`
**System prompts for LLM calls.**

| Prompt | Purpose |
|--------|---------|
| `INITIAL_EXTRACTION_PROMPT` | 22-point checklist for initial drawing analysis |
| `REFINEMENT_PROMPT_TEMPLATE` | Template for integrating user corrections |

Contains detailed instructions for checking:
- Concrete grades, reinforcement bars, lap lengths, clear cover
- Seismic/wind load specifications, development lengths
- Footing types, column ties, steel percentages

---

## Data & Embeddings

### `embedding_service.py`
**HuggingFace embeddings for semantic search.**

- Uses `sentence-transformers/all-MiniLM-L6-v2` model
- Provides `embedding_model` instance for embedding queries
- `get_embedding()` function for single query embedding

### `vector_db.py`
**ChromaDB vector store wrapper.**

| Method | Description |
|--------|-------------|
| `__init__()` | Creates/connects to persistent ChromaDB collection |
| `save_documents()` | Stores documents with embeddings and metadata |
| `query()` | Retrieves similar documents by embedding |

Used for RAG - stores IS code sections and retrieves relevant context during report generation.

### `data_loader.py`
**Markdown file loader utility.**

| Function | Description |
|----------|-------------|
| `read_md_files_from_folder()` | Reads all `.md` files from a folder into a list of dicts |

Used to load IS code documents from `SP34_md/` folder for vector DB indexing.

---

## Utilities

### `pdf_to_image.py`
**PDF to image conversion using ConvertAPI.**

- Alternative to PyMuPDF for high-quality PDF rendering
- Uses ConvertAPI cloud service for conversion
- Outputs to `convertedimages/` folder

### `gemini_vision.py`
**Direct Gemini API integration (optional).**

- Alternative to OpenRouter for vision analysis
- Uses Google's Gemini API directly
- Backup option if OpenRouter is unavailable

---

## Data Directories

| Directory | Contents |
|-----------|----------|
| `SP34_md/` | IS code documents in Markdown format (source for RAG) |
| `chroma_db/` | Persistent ChromaDB vector database |
| `uploads/` | User-uploaded PDF/image files |
| `reports/` | Generated PDF reports |
| `first_extract/` | Initial analysis reports |
| `RESULT/` | Final compliance reports |

---

## Configuration Files

| File | Purpose |
|------|---------|
| `pyproject.toml` | UV project config with all dependencies |
| `.env` | Environment variables (API keys) |
| `.env.example` | Template for required environment variables |
| `uv.lock` | Locked dependency versions |

---

## Data Flow

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│ PDF/Image   │────▶│  llm_handler.py  │────▶│ Initial Report  │
│ Upload      │     │  (Vision LLM)    │     │                 │
└─────────────┘     └──────────────────┘     └────────┬────────┘
                                                      │
                                                      ▼
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│ User Input  │────▶│  llm_service.py  │◀────│ Vector DB (RAG) │
│ Corrections │     │  (Final Report)  │     │ IS Code Context │
└─────────────┘     └──────────────────┘     └─────────────────┘
                            │
                            ▼
                    ┌─────────────────┐
                    │ Final Compliance│
                    │     Report      │
                    └─────────────────┘
```
