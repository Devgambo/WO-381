"""Thin ChromaDB wrapper.

Notes:
- Collection is created with cosine distance because the embedder
  (BAAI/bge-large-en-v1.5) is normalised at encode time and L2 over
  normalised vectors yields a confusing 0..2 score range.
- `query()` can optionally return per-document embeddings so callers
  can run MMR over them.
"""
from __future__ import annotations

from typing import Any

import chromadb


class VectorStore:
    def __init__(self, collection_name: str, folder_path: str):
        self.client = chromadb.PersistentClient(path=folder_path)
        # `hnsw:space` is the standard Chroma knob for distance metric.
        # Existing collections retain their original metric — call
        # `ingest.py --rebuild` to switch.
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def save_documents(
        self,
        documents: list[str],
        ids: list[str],
        embeddings: list[list[float]] | None = None,
        metadatas: list[dict[str, Any]] | None = None,
    ) -> None:
        if len(documents) != len(ids):
            raise ValueError("documents and ids must have same length")
        self.collection.add(
            documents=documents, ids=ids,
            embeddings=embeddings, metadatas=metadatas,
        )

    def upsert(
        self,
        documents: list[str],
        ids: list[str],
        embeddings: list[list[float]] | None = None,
        metadatas: list[dict[str, Any]] | None = None,
    ) -> None:
        if len(documents) != len(ids):
            raise ValueError("documents and ids must have same length")
        self.collection.upsert(
            documents=documents, ids=ids,
            embeddings=embeddings, metadatas=metadatas,
        )

    def all_ids(self) -> list[str]:
        # Chroma always returns ids; we don't need bodies/embeddings here.
        return list(self.collection.get().get("ids", []) or [])

    def delete(self, ids: list[str]) -> None:
        if ids:
            self.collection.delete(ids=ids)

    def query(
        self,
        query_embeddings: list[list[float]],
        n_results: int = 5,
        where: dict[str, Any] | None = None,
        include_embeddings: bool = False,
    ) -> list[dict[str, Any]]:
        """Query by embeddings, return structured results."""
        include = ["documents", "metadatas", "distances"]
        if include_embeddings:
            include.append("embeddings")

        kwargs: dict[str, Any] = {
            "query_embeddings": query_embeddings,
            "n_results": n_results,
            "include": include,
        }
        if where:
            kwargs["where"] = where

        raw = self.collection.query(**kwargs)

        ids = (raw.get("ids") or [[]])[0]
        documents = (raw.get("documents") or [[]])[0]
        metadatas_outer = raw.get("metadatas") or [[None] * len(ids)]
        metadatas = metadatas_outer[0] if metadatas_outer else [None] * len(ids)
        distances_outer = raw.get("distances") or [[None] * len(ids)]
        distances = distances_outer[0] if distances_outer else [None] * len(ids)
        embeddings = None
        if include_embeddings:
            embeddings_outer = raw.get("embeddings") or [[None] * len(ids)]
            embeddings = embeddings_outer[0] if embeddings_outer else [None] * len(ids)

        results = []
        for i in range(len(ids)):
            meta = metadatas[i] if i < len(metadatas) else None
            if not isinstance(meta, dict):
                meta = {}
            item: dict[str, Any] = {
                "id": ids[i],
                "document": documents[i] if i < len(documents) else "",
                "metadata": meta,
                "score": distances[i] if i < len(distances) else None,
            }
            if include_embeddings and embeddings and i < len(embeddings):
                item["embedding"] = embeddings[i]
            results.append(item)
        return results

    def query_by_text(
        self,
        query_text: str,
        embedding_model,
        n_results: int = 5,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        query_embedding = embedding_model.embed_query(query_text)
        return self.query([query_embedding], n_results=n_results, where=where)
