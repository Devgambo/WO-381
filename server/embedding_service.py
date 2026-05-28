_embedding_model = None


def get_embedding_model():
    """Lazy-load the HuggingFace embedding model.

    BAAI/bge-large-en-v1.5 significantly outperforms all-MiniLM-L6-v2 on
    technical domain text (MTEB ~64 vs ~57). Better recall means the RAG
    retrieval returns more relevant IS code clauses for each compliance query.

    NOTE: If migrating from all-MiniLM-L6-v2, re-run ingest.py once so the
    ChromaDB embeddings are rebuilt with this model — old embeddings are
    incompatible with the new vector space.
    """
    global _embedding_model
    if _embedding_model is None:
        from langchain_huggingface import HuggingFaceEmbeddings

        _embedding_model = HuggingFaceEmbeddings(
            model_name="BAAI/bge-large-en-v1.5",
            encode_kwargs={"normalize_embeddings": True},
        )
    return _embedding_model
