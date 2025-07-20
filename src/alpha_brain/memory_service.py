"""Memory service for ingestion and retrieval."""

from __future__ import annotations

import uuid
from typing import Any
from uuid import UUID

import pendulum
from sqlalchemy import select
from structlog import get_logger

from alpha_brain.database import get_db
from alpha_brain.embeddings import get_embedding_service
from alpha_brain.helper import MemoryHelper
from alpha_brain.schema import Memory, MemoryOutput
from alpha_brain.splash_engine import get_splash_engine
from alpha_brain.time_service import TimeService

logger = get_logger()


class MemoryService:
    """Service for managing memories."""

    def __init__(self, embedding_service=None, memory_helper=None, splash_engine=None):
        """Initialize the memory service."""
        self.embedding_service = embedding_service or get_embedding_service()
        self.memory_helper = memory_helper or MemoryHelper()
        self.splash_engine = splash_engine or get_splash_engine()

    async def _analyze_memory_safe(self, content: str) -> dict[str, Any]:
        """Analyze memory with error handling, returns minimal metadata on failure."""
        try:
            logger.info("Analyzing memory")
            metadata = await self.memory_helper.analyze_memory(content)

            # Convert to dict for storage
            metadata_dict = {
                "entities": metadata.entities,
                "unknown_entities": metadata.unknown_entities,
                "importance": metadata.importance,
                "keywords": metadata.keywords,
                "summary": metadata.summary,
                "analyzed_at": pendulum.now("UTC").isoformat(),
            }

            logger.info(
                "Memory analyzed",
                entity_count=len(metadata.entities),
                unknown_count=len(metadata.unknown_entities),
                importance=metadata.importance,
            )
            return metadata_dict
        except Exception as e:
            logger.warning("Memory analysis failed", error=str(e))
            # Return minimal metadata
            return {
                "summary": content[:100] + "..." if len(content) > 100 else content,
                "importance": 3,
                "analyzed_at": pendulum.now("UTC").isoformat(),
            }

    async def remember(
        self, content: str, marginalia: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Store a new memory.

        Args:
            content: The prose content to remember
            marginalia: Optional annotations and glosses

        Returns:
            Dict with status and memory details
        """
        try:
            # Generate embeddings first
            logger.info("Generating embeddings", content_preview=content[:100])
            semantic_emb, emotional_emb = await self.embedding_service.embed(content)

            # Then analyze the memory (optional, can fail gracefully)
            metadata = await self._analyze_memory_safe(content)

            # Merge provided marginalia with our metadata
            combined_marginalia = {**(marginalia or {}), **metadata}

            async with get_db() as session:
                memory = Memory(
                    id=uuid.uuid4(),
                    content=content,
                    created_at=pendulum.now("UTC"),
                    semantic_embedding=semantic_emb.tolist(),
                    emotional_embedding=emotional_emb.tolist(),
                    marginalia=combined_marginalia,
                )

                session.add(memory)
                await session.commit()

                logger.info("Memory stored", memory_id=str(memory.id))

                # Generate splash analysis for this memory
                # TEMPORARY: Always use emotional mode for testing
                splash_mode = "emotional"  # was: os.getenv("SPLASH_MODE", "semantic")

                logger.info(f"Generating {splash_mode} splash analysis")
                splash_analysis = await self.splash_engine.generate_splash(
                    query_semantic_embedding=semantic_emb,
                    query_emotional_embedding=emotional_emb,
                    exclude_memory_id=memory.id,
                    mode=splash_mode,
                )
                splash_output = self.splash_engine.format_splash_output(splash_analysis)

                return {
                    "status": "stored",
                    "memory_id": str(memory.id),
                    "preview": content[:200] + "..." if len(content) > 200 else content,
                    "timestamp": memory.created_at.isoformat(),
                    "metadata": {
                        "summary": metadata.get("summary", ""),
                        "importance": metadata.get("importance", 3),
                        "keywords": metadata.get("keywords", []),
                    },
                    "splash": splash_output,
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
        Search memories using vector similarity or exact text match.

        Args:
            query: The search query
            search_type: 'semantic', 'emotional', 'both', or 'exact'
            limit: Maximum results to return

        Returns:
            List of matching memories with similarity scores
        """
        try:
            async with get_db() as session:
                if search_type == "exact":
                    # Exact text search using ILIKE
                    stmt = (
                        select(
                            Memory.id,
                            Memory.content,
                            Memory.created_at,
                            Memory.marginalia,
                        )
                        .where(Memory.content.ilike(f"%{query}%"))
                        .order_by(Memory.created_at.desc())
                        .limit(limit)
                    )

                else:
                    # Vector similarity search - need embeddings
                    semantic_emb, emotional_emb = await self.embedding_service.embed(
                        query
                    )

                    if search_type == "semantic":
                        # Semantic search using SQLAlchemy Vector distance methods
                        # pgvector provides cosine_distance method on Vector columns
                        stmt = (
                            select(
                                Memory.id,
                                Memory.content,
                                Memory.created_at,
                                Memory.marginalia,
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
                                Memory.marginalia,
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
                                Memory.marginalia,
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
                    age = TimeService.format_age(row.created_at)

                    # Calculate similarity score
                    if search_type == "exact":
                        # For exact search, we don't have a distance/similarity score
                        similarity_score = None
                    else:
                        # Convert distance to similarity (1 - distance for cosine)
                        similarity_score = 1.0 - float(row.distance)

                    memory_output = MemoryOutput(
                        id=row.id,
                        content=row.content,
                        created_at=row.created_at,
                        similarity_score=similarity_score,
                        marginalia=row.marginalia or {},
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

    async def get_by_id(self, memory_id: UUID) -> MemoryOutput | None:
        """
        Get a specific memory by its ID.

        Args:
            memory_id: The UUID of the memory

        Returns:
            MemoryOutput if found, None otherwise
        """
        try:
            async with get_db() as session:
                stmt = select(
                    Memory.id,
                    Memory.content,
                    Memory.created_at,
                    Memory.marginalia,
                ).where(Memory.id == memory_id)

                result = await session.execute(stmt)
                row = result.fetchone()

                if not row:
                    return None

                # Calculate age
                created_at = pendulum.instance(row.created_at)
                age = created_at.diff_for_humans()

                return MemoryOutput(
                    id=row.id,
                    content=row.content,
                    created_at=row.created_at,
                    marginalia=row.marginalia or {},
                    age=age,
                )

        except Exception as e:
            logger.error(
                "Failed to get memory by ID", memory_id=str(memory_id), error=str(e)
            )
            return None


# Global instance
_memory_service = None


def get_memory_service() -> MemoryService:
    """Get the global memory service instance."""
    global _memory_service
    if _memory_service is None:
        _memory_service = MemoryService()
    return _memory_service
