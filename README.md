# 🏗️ Foundation Compliance Check using AI

> AI-powered analysis of RCC structural drawings for compliance with Indian civil engineering standards

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-FF4B4B.svg)](https://streamlit.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 📋 Overview

This application uses **Vision AI** and **RAG (Retrieval-Augmented Generation)** to analyze Reinforced Cement Concrete (RCC) structural drawings for compliance with:

- **IS 456:2000** — Indian Standard for Plain and Reinforced Concrete
- **SP 34** — Handbook on Concrete Reinforcement and Detailing

### ✨ Key Features

- 📄 **PDF & Image Support** — Upload structural drawings in PDF or image format
- 🤖 **AI-Powered Analysis** — Extracts 22+ compliance parameters using Vision LLM
- 📚 **RAG-Enhanced Reports** — References actual IS code clauses for accurate compliance checking
- 📊 **Professional Reports** — Downloadable in Markdown and PDF formats
- 🔄 **Interactive Workflow** — Review initial findings, provide corrections, generate final reports

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11 or higher
- [uv](https://docs.astral.sh/uv/getting-started/installation/) package manager
- OpenRouter API key ([get one here](https://openrouter.ai/))

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/foundation-compliance-ai.git
cd foundation-compliance-ai

# Copy environment template and add your API key
cp .env.example .env
# Edit .env and add: OPENROUTER_API_KEY=your_key_here

# Install dependencies
uv sync
```

### Running the Application

```bash
uv run python -m streamlit run main.py
```

Then open http://localhost:8501 in your browser.

---

## 📁 Project Structure

```
├── main.py                 # Streamlit web application
├── llm_handler.py          # Vision LLM for PDF/image analysis
├── llm_service.py          # RAG-based compliance report generation
├── prompt.py               # System prompts for LLM calls
├── embedding_service.py    # HuggingFace embeddings
├── vector_db.py            # ChromaDB vector store wrapper
├── data_loader.py          # Markdown file loader utility
│
├── SP34_md/                # IS code documents (markdown)
├── chroma_db/              # Vector database (pre-built)
│
├── pyproject.toml          # Project dependencies
├── .env.example            # Environment variables template
└── README.md
```

---

## 🔧 Configuration

| Environment Variable | Description | Required |
|---------------------|-------------|----------|
| `OPENROUTER_API_KEY` | Your OpenRouter API key | ✅ Yes |
| `OPENROUTER_MODEL` | Model to use (default: `google/gemini-2.5-flash`) | No |
| `GEMINI_API_KEY` | Direct Gemini API key (optional fallback) | No |

---

## 📖 How It Works

```
┌──────────────┐     ┌───────────────────┐     ┌──────────────────┐
│  PDF/Image   │────▶│   Vision LLM      │────▶│  Initial Report  │
│   Upload     │     │  (Gemini Flash)   │     │  (22-point check)│
└──────────────┘     └───────────────────┘     └────────┬─────────┘
                                                        │
                                                        ▼
┌──────────────┐     ┌───────────────────┐     ┌──────────────────┐
│  User Input  │────▶│   RAG Pipeline    │◀────│   Vector DB      │
│ (Corrections)│     │ (Final Analysis)  │     │ (IS Code Refs)   │
└──────────────┘     └───────────────────┘     └──────────────────┘
                              │
                              ▼
                     ┌──────────────────┐
                     │  Final Report    │
                     │  (MD/PDF Export) │
                     └──────────────────┘
```

### Workflow

1. **Upload** — Submit PDF or image of RCC structural drawing
2. **Initial Analysis** — AI extracts key parameters (concrete grade, bar sizes, cover, etc.)
3. **Review & Correct** — Provide missing information or corrections
4. **Final Report** — Generate comprehensive compliance report with IS code references

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|------------|
| Web Framework | Streamlit |
| Vision LLM | Google Gemini 2.5 Flash (via OpenRouter) |
| Embeddings | sentence-transformers/all-MiniLM-L6-v2 |
| Vector DB | ChromaDB |
| PDF Processing | PyMuPDF |
| PDF Generation | ReportLab |

---

## 📄 License

This project is licensed under the MIT License.

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

---

<p align="center">
  Made with ❤️ for structural engineers
</p>
