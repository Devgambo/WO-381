# ── Structural Compliance Checker — backend (API + RQ worker) ────────────────
# Single image that runs both the FastAPI app and the RQ worker via honcho.
# Suitable for a one-box free deploy (e.g. a Hugging Face Docker Space, which
# gives ~16 GB RAM free — enough for the local BGE embedder + reranker).
#
# For a paid split deploy, run this same image twice with different commands:
#   web:    uvicorn main:app --host 0.0.0.0 --port $PORT
#   worker: python worker.py
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/.hf-cache \
    PORT=7860

WORKDIR /app

# System libs PyMuPDF / Pillow / reportlab occasionally need.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install the CPU-only torch first so we don't pull the multi-GB CUDA build,
# then the rest of the dependencies.
COPY pyproject.toml ./
RUN pip install --index-url https://download.pytorch.org/whl/cpu "torch>=2.1.0" \
    && pip install \
        "fastapi>=0.115.0" "uvicorn[standard]>=0.30.0" "python-multipart>=0.0.9" \
        "slowapi>=0.1.9" "redis>=5.0.0" "rq>=1.16.0" "honcho>=1.1.0" \
        numpy python-dotenv PyMuPDF \
        "langchain>=0.2.0" "langchain-community>=0.2.0" "langchain-huggingface>=0.0.3" \
        "langchain-text-splitters>=0.0.1" "chromadb>=0.5.0" "sentence-transformers>=2.2.2" \
        "openai>=1.30.0" Pillow "markdown>=3.4.0" reportlab "supabase>=2.0.0" \
        "PyJWT>=2.8.0" "email-validator>=2.0.0"

COPY . .

# Build the vector index into the image so the container boots query-ready.
# This also warms the BGE model into HF_HOME so the worker doesn't download it
# on first job. Comment out if you prefer to ship a prebuilt ./chroma_db.
RUN python ingest.py || echo "WARN: ingest failed at build — run it at runtime"

EXPOSE 7860
CMD ["honcho", "start"]
