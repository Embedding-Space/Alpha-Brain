"""Embedding service for semantic and emotional vectors."""

import numpy as np
from structlog import get_logger

from .embeddings_client import get_embedding_client

logger = get_logger()


class EmbeddingService:
    """Service for generating semantic and emotional embeddings."""

    def __init__(self):
        """Initialize embedding service."""
        # Always use the embedding client
        self.client = get_embedding_client()
        logger.info("Using embedding service")

    async def embed(self, text: str) -> tuple[np.ndarray, np.ndarray]:
        """
        Generate both semantic and emotional embeddings for text.

        Args:
            text: The text to embed

        Returns:
            Tuple of (semantic_embedding, emotional_embedding)
        """
        return await self.client.embed(text)

    async def embed_batch(self, texts: list[str]) -> tuple[np.ndarray, np.ndarray]:
        """
        Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed

        Returns:
            Tuple of (semantic_embeddings, emotional_embeddings) arrays
        """
        if not texts:
            return np.array([]), np.array([])

        return await self.client.embed_batch(texts)


# Global instance
_embedding_service = None


def get_embedding_service() -> EmbeddingService:
    """Get the global embedding service instance."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service