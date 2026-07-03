"""One-time / re-run RAG index builder.

Stable chunk IDs let us upsert in place rather than destructively wiping
the index — concurrent readers no longer crash, and a re-ingest only
embeds chunks whose content actually changed.

Run with `--rebuild` to drop the collection and re-create it from scratch
(needed if changing the embedding model or distance metric).
"""
from __future__ import annotations

import argparse
import os
import shutil
from collections import Counter

from data_loader import read_md_files_from_folder
from embedding_service import get_embedding_model
from vector_db import VectorStore

DB_PATH = "./chroma_db"
COLLECTION = "is_codes_docs"
EMBED_BATCH = 32
SAVE_BATCH = 500


def _metadata(chunk: dict) -> dict:
    return {k: v for k, v in chunk.items() if k != "content"}


def ingest_data(dry_run: bool = False, rebuild: bool = False) -> None:
    print("Loading markdown files...")
    folder_path = "./SP34_md"
    try:
        chunks = read_md_files_from_folder(folder_path)
    except FileNotFoundError:
        print(f"Directory {folder_path} not found. Please ensure your MD files are here.")
        return

    print(f"Loaded {len(chunks)} chunks.")
    if dry_run:
        stats = Counter(c["content_type"] for c in chunks)
        element_stats = Counter(c.get("element_type", "general") for c in chunks)
        print("Content-type breakdown:", dict(stats))
        print("Element-type breakdown:", dict(element_stats))
        return

    if rebuild and os.path.exists(DB_PATH):
        print("--rebuild: deleting old ChromaDB instance.")
        shutil.rmtree(DB_PATH)

    print("Generating embeddings (batched)...")
    texts = [c["content"] for c in chunks]
    ids = [c["chunk_id"] for c in chunks]
    metadatas = [_metadata(c) for c in chunks]

    embedding_model = get_embedding_model()
    embeddings: list[list[float]] = []
    for i in range(0, len(texts), EMBED_BATCH):
        batch = texts[i:i + EMBED_BATCH]
        batch_emb = embedding_model.embed_documents(batch)
        embeddings.extend(batch_emb)
        print(f"  Embedded {min(i + EMBED_BATCH, len(texts))}/{len(texts)} chunks")

    print("Upserting into ChromaDB...")
    db = VectorStore(collection_name=COLLECTION, folder_path=DB_PATH)

    pre_count = db.collection.count()

    for i in range(0, len(texts), SAVE_BATCH):
        sl = slice(i, i + SAVE_BATCH)
        db.upsert(
            documents=texts[sl],
            ids=ids[sl],
            embeddings=embeddings[sl],
            metadatas=metadatas[sl],
        )
        print(f"Upserted batch {i // SAVE_BATCH + 1} ({len(texts[sl])} chunks)")

    # Prune chunks that disappeared from the source corpus (stale IDs).
    if not rebuild:
        existing_ids = set(db.all_ids())
        kept_ids = set(ids)
        stale = existing_ids - kept_ids
        if stale:
            print(f"Removing {len(stale)} stale chunks (no longer in source corpus).")
            db.delete(list(stale))

    post_count = db.collection.count()
    print(f"[OK] Ingest complete. Collection now holds {post_count} chunks (was {pre_count}).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Print chunk stats without saving to DB")
    parser.add_argument("--rebuild", action="store_true",
                        help="Wipe DB before ingest (needed when embedding model or metric changes)")
    args = parser.parse_args()
    ingest_data(dry_run=args.dry_run, rebuild=args.rebuild)
