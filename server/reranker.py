"""Cross-encoder reranker + MMR diversity for RAG retrieval.

Two-stage pipeline:
  1. Dense retrieval returns top-N candidates from ChromaDB.
  2. CrossEncoder (BAAI/bge-reranker-base by default) re-scores each
     (query, document) pair — far more accurate than cosine on the dense
     vectors alone, especially for short queries with technical jargon.
  3. MMR optionally trims the reranked list to top-K while penalising
     near-duplicate passages so the LLM sees diverse evidence.

Both stages are env-toggleable so we can A/B against the baseline.
"""
from __future__ import annotations

import logging
import os
from typing import Any

log = logging.getLogger(__name__)

_RERANK_MODEL_NAME = os.getenv("RERANK_MODEL", "BAAI/bge-reranker-base")
_RERANK_ENABLED = os.getenv("RERANK_ENABLED", "true").lower() == "true"
_MMR_ENABLED = os.getenv("MMR_ENABLED", "true").lower() == "true"
_MMR_LAMBDA = float(os.getenv("MMR_LAMBDA", "0.7"))

_reranker = None


def is_rerank_enabled() -> bool:
    return _RERANK_ENABLED


def is_mmr_enabled() -> bool:
    return _MMR_ENABLED


def get_reranker():
    """Lazy-load the CrossEncoder. Returns None if disabled or load fails."""
    global _reranker
    if not _RERANK_ENABLED:
        return None
    if _reranker is None:
        try:
            from sentence_transformers import CrossEncoder

            log.info("Loading reranker model: %s", _RERANK_MODEL_NAME)
            _reranker = CrossEncoder(_RERANK_MODEL_NAME)
        except Exception:
            log.exception("Reranker load failed — falling back to no rerank")
            _reranker = None
    return _reranker


def cross_encoder_rerank(
    query: str,
    results: list[dict[str, Any]],
    top_k: int,
) -> list[dict[str, Any]]:
    """Re-score each (query, document) pair, sort by rerank_score desc, take top_k.

    Each returned dict has an added `rerank_score` field. On failure the
    original ordering is preserved (truncated to top_k).
    """
    if not results:
        return []
    model = get_reranker()
    if model is None or len(results) == 1:
        return results[:top_k]

    pairs = [(query, r.get("document", "") or "") for r in results]
    try:
        scores = model.predict(pairs).tolist()
    except Exception:
        log.exception("Reranker predict failed — returning original order")
        return results[:top_k]

    for r, s in zip(results, scores):
        r["rerank_score"] = float(s)
    results.sort(key=lambda r: r.get("rerank_score", float("-inf")), reverse=True)
    return results[:top_k]


def mmr_select(
    query_embedding: list[float],
    results: list[dict[str, Any]],
    top_k: int,
    lambda_param: float | None = None,
) -> list[dict[str, Any]]:
    """Maximal Marginal Relevance over results that carry an `embedding` field.

    If results have no `embedding`, returns first top_k unchanged.
    lambda_param ∈ [0, 1]: 1 → pure relevance; 0 → pure diversity.
    """
    if not results or top_k <= 0:
        return []
    if not _MMR_ENABLED:
        return results[:top_k]
    if any(r.get("embedding") is None for r in results):
        return results[:top_k]

    import numpy as np

    lam = _MMR_LAMBDA if lambda_param is None else lambda_param
    q = np.array(query_embedding, dtype=np.float32)
    docs = np.array([r["embedding"] for r in results], dtype=np.float32)

    q_norm = q / (np.linalg.norm(q) + 1e-12)
    d_norms = docs / (np.linalg.norm(docs, axis=1, keepdims=True) + 1e-12)
    rel = d_norms @ q_norm  # cosine similarity to query, shape (N,)

    selected: list[int] = []
    remaining = set(range(len(results)))
    pairwise = d_norms @ d_norms.T  # shape (N, N)

    while remaining and len(selected) < top_k:
        if not selected:
            idx = int(max(remaining, key=lambda i: rel[i]))
        else:
            def score(i: int) -> float:
                max_sim = max(pairwise[i, j] for j in selected)
                return lam * rel[i] - (1 - lam) * float(max_sim)

            idx = int(max(remaining, key=score))
        selected.append(idx)
        remaining.discard(idx)

    return [results[i] for i in selected]
