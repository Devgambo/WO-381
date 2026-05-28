from typing import Any, Dict, List, Optional

import chromadb


class VectorStore:
    def __init__(self, collection_name: str, folder_path: str):
        self.client = chromadb.PersistentClient(path=folder_path)
        self.collection = self.client.get_or_create_collection(name=collection_name)

    def save_documents(
        self,
        documents: List[str],
        ids: List[str],
        embeddings: Optional[List[List[float]]] = None,
        metadatas: Optional[List[Dict[str, Any]]] = None,
    ):
        if len(documents) != len(ids):
            raise ValueError("documents and ids must have same length")

        self.collection.add(
            documents=documents,
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
        )

    def query(
        self,
        query_embeddings: List[List[float]],
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Query by embeddings, return structured results."""
        kwargs: Dict[str, Any] = {
            "query_embeddings": query_embeddings,
            "n_results": n_results,
        }
        if where:
            kwargs["where"] = where

        raw = self.collection.query(**kwargs)

        results = []
        ids = raw.get("ids", [[]])[0]
        documents = raw.get("documents", [[]])[0]
        metadatas = raw.get("metadatas") or [[None] * len(ids)]
        distances = raw.get("distances") or [[None] * len(ids)]

        for i in range(len(ids)):
            meta = metadatas[0][i] if metadatas and metadatas[0] else None
            results.append({
                "id": ids[i],
                "document": documents[i],
                "metadata": meta if isinstance(meta, dict) else {},
                "score": distances[0][i] if distances and distances[0] else None,
            })
        return results

    def query_by_text(
        self,
        query_text: str,
        embedding_model,
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Query with raw text — handles embedding internally."""
        query_embedding = embedding_model.embed_query(query_text)
        return self.query([query_embedding], n_results=n_results, where=where)
