from embedding_service import embedding_model
from vector_db import VectorStore
from data_loader import read_md_files_from_folder
import uuid

def ingest_data():
    print("Loading markdown files...")

    #todo: Add More seg files for Embedding
    # Update this path if your markdown files are located elsewhere
    folder_path = "./SP34_md"
    try:
        md_files = read_md_files_from_folder(folder_path)
    except FileNotFoundError:
        print(f"Directory {folder_path} not found. Please ensure your MD files are here.")
        return

    print(f"Loaded {len(md_files)} chunks. Generating embeddings...")
    texts = [f["content"] for f in md_files]
    ids = [str(uuid.uuid4()) for _ in range(len(md_files))]
    metadatas = [{"content_type": f["content_type"], "source": f["file_name"]} for f in md_files]
    
    embeddings = embedding_model.embed_documents(texts)
    
    print("Saving to ChromaDB...")
    db = VectorStore(collection_name="is_codes_docs", folder_path="./chroma_db")
    db.save_documents(documents=texts, ids=ids, embeddings=embeddings, metadatas=metadatas)
    
    print("✅ RAG pipeline ingestion complete!")

if __name__ == "__main__": 
    ingest_data()
