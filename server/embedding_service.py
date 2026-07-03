"""Lazy-loaded HuggingFace embedder for BAAI/bge-large-en-v1.5.

BGE models are trained with normalised embeddings + cosine distance and
recommend a query-side instruction prefix to improve retrieval quality on
short queries. Documents are embedded WITHOUT a prefix.

If migrating from a different embedding model, re-run ingest.py once so the
ChromaDB embeddings are rebuilt with this model — old embeddings are
incompatible with the new vector space.
"""
import os

_embedding_model = None

# BGE-recommended instruction prefix — applied to queries only.
# https://huggingface.co/BAAI/bge-large-en-v1.5
BGE_QUERY_INSTRUCTION = os.getenv(
    "BGE_QUERY_INSTRUCTION",
    "Represent this sentence for searching relevant passages: ",
)


def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        from langchain_community.embeddings import HuggingFaceBgeEmbeddings

        _embedding_model = HuggingFaceBgeEmbeddings(
            model_name="BAAI/bge-large-en-v1.5",
            encode_kwargs={"normalize_embeddings": True},
            query_instruction=BGE_QUERY_INSTRUCTION,
            embed_instruction="",
        )
    return _embedding_model
