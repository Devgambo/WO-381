import chromadb
from typing import List, Dict, Optional, Callable, Any


class VectorStore:
    def __init__(
        self,
        collection_name: str,
        folder_path: str,
        # embedding_fn: Optional[Callable] = None
    ):
        self.client = chromadb.PersistentClient(path=folder_path)
        self.collection = self.client.get_or_create_collection(
            name=collection_name
            # embedding_function=embedding_fn
        )

    def save_documents(
        self,
        documents: List[str],
        ids: List[str],
        embeddings: Optional[List[List[float]]] = None,
        metadatas: Optional[List[Dict[str, Any]]] = None
    ):
        if len(documents) != len(ids):
            raise ValueError("❌ documents and ids must have same length")

        self.collection.add(
            documents=documents,
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas
        )

    def query(
        self,
        query_embeddings: List[List[float]],
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Query by embeddings, return structured results.
        
        Args:
            query_embeddings: List of embedding vectors to query with.
            n_results: Number of results to return.
            where: Optional metadata filter dict for ChromaDB (e.g., {"content_type": "text"}).
        """
        query_kwargs = {
            "query_embeddings": query_embeddings,
            "n_results": n_results,
        }
        if where:
            query_kwargs["where"] = where

        raw = self.collection.query(**query_kwargs)

        results = []
        for i in range(len(raw["ids"][0])):  # Chroma nests everything under index 0
            results.append({
                "id": raw["ids"][0][i],
                "document": raw["documents"][0][i],
                "metadata": raw["metadatas"][0][i] if raw["metadatas"] else {},
                "score": raw["distances"][0][i] if "distances" in raw else None
            })
        return results

    def query_by_text(
        self,
        query_text: str,
        embedding_model,
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Query with raw text — handles embedding internally.

        Args:
            query_text: The text query to search for.
            embedding_model: An embedding model with an embed_query(str) method.
            n_results: Number of results to return.
            where: Optional metadata filter dict.
        """
        query_embedding = embedding_model.embed_query(query_text)
        return self.query([query_embedding], n_results=n_results, where=where)












#################################################






# import chromadb
# from typing import List, Dict, Optional, Union


# class VectorStore:
#     def __init__(self, collection_name: str, folder_path: str):
#         self.client = chromadb.PersistentClient(path=folder_path)
#         self.collection = self.client.get_or_create_collection(name=collection_name)

#     def save_documents(
#             self,
#             documents: List[str],
#             ids: List[str],
#             embeddings: Optional[List[List[float]]] = None
#     ):
#         """Save documents to ChromaDB.

#         Args:
#             documents: List of document texts.
#             ids: List of document IDs.
#             embeddings: Optional precomputed embeddings (from EmbeddingService).
#         """
#         if embeddings is None:
#             self.collection.add(documents=documents, ids=ids)
#         else:
#             self.collection.add(
#                 documents=documents,
#                 ids=ids,
#                 embeddings=embeddings
#             )


#     def query(
#             self,
#             query_embeddings: List[List[float]],
#             n_results: int = 5,
#     ) -> Dict:
#         return self.collection.query(
#             query_embeddings=query_embeddings,
#             n_results=n_results,
#         )

#     # def get_all(self, where: Optional[Dict] = None) -> Dict:
#     #     return self.collection.get(where=where)
