"""Vector embedding service using sentence-transformers and ChromaDB."""

from __future__ import annotations

import logging
import os

import chromadb
from sentence_transformers import SentenceTransformer

from tirithel.config.settings import get_settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Manages vector embeddings and semantic search via ChromaDB."""

    CONVERSATION_COLLECTION = "conversation_segments"
    NAVIGATION_COLLECTION = "navigation_paths"

    def __init__(self):
        settings = get_settings()
        self._model_name = settings.embedding.model_name
        self._persist_dir = settings.embedding.chroma_persist_dir
        self._model: SentenceTransformer | None = None
        self._chroma_client: chromadb.ClientAPI | None = None

    @property
    def model(self) -> SentenceTransformer:
        if self._model is None:
            logger.info("Loading embedding model: %s", self._model_name)
            self._model = SentenceTransformer(self._model_name)
        return self._model

    @property
    def chroma(self) -> chromadb.ClientAPI:
        if self._chroma_client is None:
            os.makedirs(self._persist_dir, exist_ok=True)
            self._chroma_client = chromadb.PersistentClient(path=self._persist_dir)
        return self._chroma_client

    def embed_text(self, text: str) -> list[float]:
        """Generate embedding vector for a single text."""
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts."""
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        return embeddings.tolist()

    def add_navigation_path(
        self,
        path_id: str,
        issue_summary: str,
        step_descriptions: str,
        metadata: dict | None = None,
    ) -> None:
        """Add a navigation path to the vector store."""
        collection = self.chroma.get_or_create_collection(self.NAVIGATION_COLLECTION)
        document = f"{issue_summary}\n{step_descriptions}"
        embedding = self.embed_text(document)

        collection.upsert(
            ids=[path_id],
            embeddings=[embedding],
            documents=[document],
            metadatas=[metadata or {}],
        )

    def add_conversation_segment(
        self,
        segment_id: str,
        text: str,
        metadata: dict | None = None,
    ) -> None:
        """Add a conversation segment to the vector store."""
        collection = self.chroma.get_or_create_collection(self.CONVERSATION_COLLECTION)
        embedding = self.embed_text(text)

        collection.upsert(
            ids=[segment_id],
            embeddings=[embedding],
            documents=[text],
            metadatas=[metadata or {}],
        )

    def search_navigation_paths(
        self, query: str, top_k: int = 5, profile_id: str | None = None
    ) -> list[dict]:
        """Search for similar navigation paths.

        Returns list of dicts with keys: id, score, document, metadata.
        """
        collection = self.chroma.get_or_create_collection(self.NAVIGATION_COLLECTION)
        query_embedding = self.embed_text(query)

        where_filter = {"profile_id": profile_id} if profile_id else None

        try:
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=where_filter,
            )
        except Exception:
            # If collection is empty or filter fails, return empty
            return []

        matches = []
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                score = 1.0 - (results["distances"][0][i] if results["distances"] else 0)
                matches.append({
                    "id": doc_id,
                    "score": score,
                    "document": results["documents"][0][i] if results["documents"] else "",
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                })

        return matches

    def search_conversation_segments(self, query: str, top_k: int = 5) -> list[dict]:
        """Search for similar conversation segments."""
        collection = self.chroma.get_or_create_collection(self.CONVERSATION_COLLECTION)
        query_embedding = self.embed_text(query)

        try:
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
            )
        except Exception:
            return []

        matches = []
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                score = 1.0 - (results["distances"][0][i] if results["distances"] else 0)
                matches.append({
                    "id": doc_id,
                    "score": score,
                    "document": results["documents"][0][i] if results["documents"] else "",
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                })

        return matches

    def delete_navigation_path(self, path_id: str) -> None:
        """Remove a navigation path from the vector store."""
        collection = self.chroma.get_or_create_collection(self.NAVIGATION_COLLECTION)
        collection.delete(ids=[path_id])
