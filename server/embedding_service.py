from langchain_huggingface import HuggingFaceEmbeddings

# BAAI/bge-large-en-v1.5 significantly outperforms all-MiniLM-L6-v2 on technical
# domain text (MTEB benchmark: ~64 vs ~57). Better recall means the RAG retrieval
# returns more relevant IS code clauses for each compliance query.
# NOTE: If you are migrating from all-MiniLM-L6-v2, re-run ingest.py once to
# rebuild the ChromaDB embeddings with this new model — old embeddings are
# incompatible with the new vector space.
embedding_model = HuggingFaceEmbeddings(
    model_name="BAAI/bge-large-en-v1.5",
    encode_kwargs={"normalize_embeddings": True},
)
