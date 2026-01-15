from langchain_huggingface import HuggingFaceEmbeddings

# Initialize once (global / in __init__)
embedding_model = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2",
    encode_kwargs={'normalize_embeddings': True}
)

def get_embedding(query: str):
    """Generate embedding vector for a given query string."""
    try:
        embedding = embedding_model.embed_query(query)
        print(
            f"✅ Successfully generated embedding for query: '{query[:15]}...' "
            f"using model: '{embedding_model.model_name}'"
        )
        return embedding
    except Exception as e:
        print(
            f"❌ Error generating embedding for query: '{query[:15]}...' "
            f"with model: '{embedding_model.model_name}'"
        )
        raise e
