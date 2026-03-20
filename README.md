# Compliance Report Generation using AI

> AI-powered analysis of RCC structural drawings for compliance with Indian civil engineering standards

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18+-61DAFB?logo=react&logoColor=black)](https://react.dev/)
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

## Quick Start

### Prerequisites

- Python 3.11 or higher
- [uv](https://docs.astral.sh/uv/getting-started/installation/) package manager
- OpenRouter API key ([get one here](https://openrouter.ai/))

### Installation

```bash
# Clone the repository
git clone https://github.com/Devgambo/WO-381.git
cd server
# Install dependencies
uv sync
# Edit .env and add: OPENROUTER_API_KEY=your_key_here
uv run uvicorn main:app --reload

cd client
npm i
npm run dev
```

---

## 📖 How It Works
<img width="1909" height="727" alt="Screenshot 2026-03-19 092558" src="https://github.com/user-attachments/assets/097edfbc-aff0-4eaf-89d6-68d0cd63f12f" />

### Workflow

1. **Upload** — Submit PDF or image of RCC structural drawing
2. **Initial Analysis** — AI extracts key parameters (concrete grade, bar sizes, cover, etc.)
3. **Review & Correct** — Provide missing information or corrections
4. **Final Report** — Generate comprehensive compliance report with IS code references

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|------------|
| Web Framework | React |
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
