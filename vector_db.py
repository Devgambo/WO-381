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
    ) -> List[Dict[str, Any]]:
        """Query by embeddings, return structured results."""
        raw = self.collection.query(
            query_embeddings=query_embeddings,
            n_results=n_results
        )

        results = []
        for i in range(len(raw["ids"][0])):  # Chroma nests everything under index 0
            results.append({
                "id": raw["ids"][0][i],
                "document": raw["documents"][0][i],
                "metadata": raw["metadatas"][0][i] if raw["metadatas"] else {},
                "score": raw["distances"][0][i] if "distances" in raw else None
            })
        return results

    # def query_text(
    #     self,
    #     query_texts: List[str],
    #     embedding_fn,
    #     n_results: int = 5
    # ) -> List[Dict[str, Any]]:
    #     """Query directly with text input."""
    #     query_embeddings = embedding_fn(query_texts)
    #     return self.query(query_embeddings, n_results)
















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
