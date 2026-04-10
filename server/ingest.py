import argparse
from embedding_service import embedding_model
from vector_db import VectorStore
from data_loader import read_md_files_from_folder
import uuid
import os
import shutil

def ingest_data(dry_run=False):
    print("Loading markdown files...")
    
    folder_path = "./SP34_md"
    try:
        chunks = read_md_files_from_folder(folder_path)
    except FileNotFoundError:
        print(f"Directory {folder_path} not found. Please ensure your MD files are here.")
        return

    print(f"Loaded {len(chunks)} chunks.")
    if dry_run:
        print("Dry run enabled. Exiting before generating embeddings.")
        from collections import Counter
        stats = Counter(c['content_type'] for c in chunks)
        print("Chunk breakdown:", dict(stats))
        return

    print("Generating embeddings (batched)...")
    texts = [f["content"] for f in chunks]
    ids = [str(uuid.uuid4()) for _ in range(len(chunks))]
    
    # Extract metadata by removing 'content' from each chunk dict
    metadatas = []
    for c in chunks:
        m = c.copy()
        del m['content']
        metadatas.append(m)
    
    # Batch embeddings to avoid OOM with BAAI/bge-large-en-v1.5
    EMBED_BATCH = 32
    embeddings = []
    for i in range(0, len(texts), EMBED_BATCH):
        batch = texts[i:i+EMBED_BATCH]
        batch_emb = embedding_model.embed_documents(batch)
        embeddings.extend(batch_emb)
        print(f"  Embedded {min(i+EMBED_BATCH, len(texts))}/{len(texts)} chunks")
    
    print("Rebuilding ChromaDB...")
    db_path = "./chroma_db"
    if os.path.exists(db_path):
        shutil.rmtree(db_path)
        print("Deleted old ChromaDB instance.")
        
    db = VectorStore(collection_name="is_codes_docs", folder_path=db_path)
    
    BATCH_SIZE = 500
    for i in range(0, len(texts), BATCH_SIZE):
        batch_texts = texts[i:i+BATCH_SIZE]
        batch_ids = ids[i:i+BATCH_SIZE]
        batch_embeddings = embeddings[i:i+BATCH_SIZE]
        batch_metadata = metadatas[i:i+BATCH_SIZE]
        
        db.save_documents(
            documents=batch_texts, 
            ids=batch_ids, 
            embeddings=batch_embeddings, 
            metadatas=batch_metadata
        )
        print(f"Inserted batch {i//BATCH_SIZE + 1} ({len(batch_texts)} chunks)")
        
    print("✅ RAG pipeline ingestion complete!")

if __name__ == "__main__": 
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Print chunk stats without saving to DB")
    args = parser.parse_args()
    ingest_data(dry_run=args.dry_run)
