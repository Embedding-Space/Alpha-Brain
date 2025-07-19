"""Client for embedding service."""

import asyncio
import os

import httpx
import numpy as np
from structlog import get_logger

logger = get_logger()

# Get embedding service URL from environment
EMBEDDING_SERVICE_URL = os.getenv("EMBEDDING_SERVICE_URL", "http://localhost:8001")


class EmbeddingServiceClient:
    """Client for the embedding microservice."""

    def __init__(self, base_url: str | None = None):
        """Initialize embedding service client."""
        self.base_url = base_url or EMBEDDING_SERVICE_URL
        logger.info("Embedding service client initialized", base_url=self.base_url)

    async def health_check(self) -> dict:
        """Check if embedding service is healthy."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/health")
            response.raise_for_status()
            return response.json()

    async def embed(self, text: str) -> tuple[np.ndarray, np.ndarray]:
        """
        Generate both semantic and emotional embeddings for text.

        Args:
            text: The text to embed

        Returns:
            Tuple of (semantic_embedding, emotional_embedding)
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/embed",
                json={"text": text, "model_type": "both"},
                timeout=30.0,
            )
            response.raise_for_status()
            
            data = response.json()
            semantic = np.array(data["semantic"])
            emotional = np.array(data["emotional"])
            
            return semantic, emotional

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

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/embed_batch",
                json=texts,
                params={"model_type": "both"},
                timeout=60.0,  # Longer timeout for batch
            )
            response.raise_for_status()
            
            data = response.json()
            semantic = np.array(data["semantic"])
            emotional = np.array(data["emotional"])
            
            return semantic, emotional

    async def wait_until_ready(self, max_attempts: int = 30):
        """Wait for embedding service to be ready."""
        for attempt in range(max_attempts):
            try:
                health = await self.health_check()
                if health.get("models_loaded"):
                    logger.info("Embedding service is ready", health=health)
                    return
            except Exception:
                pass
            
            if attempt < max_attempts - 1:
                await asyncio.sleep(1)
        
        raise RuntimeError("Embedding service failed to become ready")


# Global instance
_embedding_client = None


def get_embedding_client() -> EmbeddingServiceClient:
    """Get the global embedding client instance."""
    global _embedding_client
    if _embedding_client is None:
        _embedding_client = EmbeddingServiceClient()
    return _embedding_client