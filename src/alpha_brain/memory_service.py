"""Memory service for ingestion and retrieval."""

import uuid
from typing import Any

import pendulum
from sqlalchemy import select
from structlog import get_logger

from alpha_brain.database import get_db
from alpha_brain.embeddings import get_embedding_service
from alpha_brain.helper import MemoryHelper
from alpha_brain.schema import Memory, MemoryOutput

logger = get_logger()


class MemoryService:
    """Service for managing memories."""

    def __init__(self, embedding_service=None, memory_helper=None):
        """Initialize the memory service."""
        self.embedding_service = embedding_service or get_embedding_service()
        self.memory_helper = memory_helper or MemoryHelper()

    async def _extract_entities_safe(self, content: str) -> list[str]:
        """Extract entities with error handling, returns empty list on failure."""
        try:
            logger.info("Extracting entities")
            extraction_result = await self.memory_helper.extract_entities(content)
            entities = extraction_result.entities
            logger.info("Extracted entities", entities=entities)
            return entities
        except Exception as e:
            logger.warning("Entity extraction failed", error=str(e))
            return []

    async def remember(
        self, content: str, extra_data: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Store a new memory.

        Args:
            content: The prose content to remember
            extra_data: Optional metadata

        Returns:
            Dict with status and memory details
        """
        try:
            # Generate embeddings first
            logger.info("Generating embeddings", content_preview=content[:100])
            semantic_emb, emotional_emb = await self.embedding_service.embed(content)
            
            # Then extract entities (optional, can fail gracefully)
            entities = await self._extract_entities_safe(content)

            async with get_db() as session:
                memory = Memory(
                    id=uuid.uuid4(),
                    content=content,
                    created_at=pendulum.now("UTC"),
                    semantic_embedding=semantic_emb.tolist(),
                    emotional_embedding=emotional_emb.tolist(),
                    entities=entities,
                    extra_data=extra_data or {},
                )

                session.add(memory)
                await session.commit()

                logger.info("Memory stored", memory_id=str(memory.id))

                return {
                    "status": "stored",
                    "memory_id": str(memory.id),
                    "preview": content[:200] + "..." if len(content) > 200 else content,
                    "entities": entities,
                    "timestamp": memory.created_at.isoformat(),
                }

        except Exception as e:
            logger.error("Failed to store memory", error=str(e))
            return {
                "status": "error",
                "error": str(e),
                "message": "Failed to store memory",
            }

    async def search(
        self, query: str, search_type: str = "semantic", limit: int = 10
    ) -> list[MemoryOutput]:
        """
        Search memories using vector similarity.

        Args:
            query: The search query
            search_type: 'semantic', 'emotional', or 'both'
            limit: Maximum results to return

        Returns:
            List of matching memories with similarity scores
        """
        try:
            # Generate query embeddings
            semantic_emb, emotional_emb = await self.embedding_service.embed(query)

            async with get_db() as session:
                if search_type == "semantic":
                    # Semantic search using SQLAlchemy Vector distance methods
                    # pgvector provides cosine_distance method on Vector columns
                    stmt = (
                        select(
                            Memory.id,
                            Memory.content,
                            Memory.created_at,
                            Memory.extra_data,
                            Memory.semantic_embedding.cosine_distance(
                                semantic_emb.tolist()
                            ).label("distance"),
                        )
                        .where(Memory.semantic_embedding.is_not(None))
                        .order_by(
                            Memory.semantic_embedding.cosine_distance(
                                semantic_emb.tolist()
                            )
                        )
                        .limit(limit)
                    )

                elif search_type == "emotional":
                    # Emotional search using SQLAlchemy Vector distance methods
                    stmt = (
                        select(
                            Memory.id,
                            Memory.content,
                            Memory.created_at,
                            Memory.extra_data,
                            Memory.emotional_embedding.cosine_distance(
                                emotional_emb.tolist()
                            ).label("distance"),
                        )
                        .where(Memory.emotional_embedding.is_not(None))
                        .order_by(
                            Memory.emotional_embedding.cosine_distance(
                                emotional_emb.tolist()
                            )
                        )
                        .limit(limit)
                    )

                else:  # "both" or default
                    # Combined search - average of both distances
                    semantic_dist = Memory.semantic_embedding.cosine_distance(
                        semantic_emb.tolist()
                    )
                    emotional_dist = Memory.emotional_embedding.cosine_distance(
                        emotional_emb.tolist()
                    )
                    avg_distance = (semantic_dist + emotional_dist) / 2

                    stmt = (
                        select(
                            Memory.id,
                            Memory.content,
                            Memory.created_at,
                            Memory.extra_data,
                            avg_distance.label("distance"),
                        )
                        .where(Memory.semantic_embedding.is_not(None))
                        .where(Memory.emotional_embedding.is_not(None))
                        .order_by(avg_distance)
                        .limit(limit)
                    )

                result = await session.execute(stmt)
                rows = result.fetchall()

                # Convert results to MemoryOutput
                memories = []
                for row in rows:
                    # Calculate age
                    created_at = pendulum.instance(row.created_at)
                    age = created_at.diff_for_humans()

                    # Convert distance to similarity (1 - distance for cosine)
                    similarity_score = 1.0 - float(row.distance)

                    memory_output = MemoryOutput(
                        id=row.id,
                        content=row.content,
                        created_at=row.created_at,
                        similarity_score=similarity_score,
                        extra_data=row.extra_data or {},
                        age=age,
                    )

                    memories.append(memory_output)

                logger.info(
                    "Search completed",
                    query=query,
                    search_type=search_type,
                    results_count=len(memories),
                )

                return memories

        except Exception as e:
            logger.error("Search failed", error=str(e))
            return []


# Global instance
_memory_service = None


def get_memory_service() -> MemoryService:
    """Get the global memory service instance."""
    global _memory_service
    if _memory_service is None:
        _memory_service = MemoryService()
    return _memory_service
