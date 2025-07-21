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
from alpha_brain.entity_service import get_entity_service
from alpha_brain.memory_helper import MemoryHelper
from alpha_brain.interval_parser import parse_interval
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
            
            # Get entity IDs for the canonical entities
            entity_service = get_entity_service()
            entity_result = await entity_service.canonicalize_names_with_ids(
                metadata.entities + metadata.unknown_entities
            )

            # Convert to dict for storage
            metadata_dict = {
                "entities": metadata.entities,
                "unknown_entities": metadata.unknown_entities,
                "entity_ids": entity_result["entity_ids"],  # Add entity IDs
                "importance": metadata.importance,
                "keywords": metadata.keywords,
                "summary": metadata.summary,
                "analyzed_at": pendulum.now("UTC").isoformat(),
            }

            logger.info(
                "Memory analyzed",
                entity_count=len(metadata.entities),
                unknown_count=len(metadata.unknown_entities),
                entity_ids=entity_result["entity_ids"],
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
                "entity_ids": [],  # Empty entity IDs on failure
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
                    entity_ids=metadata.get("entity_ids", []),  # Store entity IDs
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
                    "splash_analysis": splash_analysis,
                }

        except Exception as e:
            logger.error("Failed to store memory", error=str(e))
            return {
                "status": "error",
                "error": str(e),
                "message": "Failed to store memory",
            }

    async def search(  # noqa: PLR0912, PLR0915
        self,
        query: str | None = None,
        search_type: str = "semantic",
        limit: int = 10,
        offset: int = 0,
        interval: str | None = None,
        entity: str | None = None,
        order: str = "auto"
    ) -> list[MemoryOutput]:
        """
        Search or browse memories with flexible filtering options.

        First checks for entity matches in marginalia, then performs vector search.
        Entity matches are boosted to the top of results.

        Args:
            query: The search query. If None/empty, browse mode is activated.
            search_type: 'semantic', 'emotional', 'both', or 'exact'
            limit: Maximum results to return
            offset: Number of results to skip for pagination
            interval: Time interval filter (e.g., "yesterday", "past 3 hours")
            entity: Entity name filter (will be canonicalized)
            order: Sort order - 'asc', 'desc', or 'auto'

        Returns:
            List of matching memories with similarity scores
        """
        try:
            async with get_db() as session:
                # Determine if we're in browse mode
                is_browsing = not query or query in ["", "*", "%"]
                
                # Parse temporal interval if provided
                start_dt, end_dt = None, None
                if interval:
                    start_dt, end_dt = parse_interval(interval)
                    logger.info(
                        "Parsed interval",
                        interval=interval,
                        start=start_dt.isoformat(),
                        end=end_dt.isoformat()
                    )
                
                # Canonicalize entity filter if provided
                canonical_entity = None
                if entity:
                    entity_service = get_entity_service()
                    result = await entity_service.canonicalize_names([entity])
                    if result["entities"]:
                        canonical_entity = result["entities"][0]
                    else:
                        # Entity not found, use as-is
                        canonical_entity = entity
                    logger.info(
                        "Canonicalized entity",
                        input=entity,
                        canonical=canonical_entity
                    )
                
                # Determine sort order
                if order == "auto":
                    if is_browsing and interval:
                        # For past intervals (yesterday, last week), use chronological
                        # For now-anchored (past 3 hours), use reverse chronological
                        if any(word in interval.lower() for word in ["past", "ago", "last"]):
                            actual_order = "desc"  # Newest first for recent intervals
                        else:
                            actual_order = "asc"   # Oldest first for past intervals
                    else:
                        actual_order = "desc"  # Default to newest first for search
                else:
                    actual_order = order
                
                # If browsing mode (no query), skip to filtered selection
                if is_browsing:
                    # Build base query for browsing
                    stmt = select(
                        Memory.id,
                        Memory.content,
                        Memory.created_at,
                        Memory.marginalia,
                    )
                    
                    # Apply temporal filter
                    if start_dt and end_dt:
                        stmt = stmt.where(
                            Memory.created_at.between(start_dt, end_dt)
                        )
                    
                    # Apply entity filter
                    if canonical_entity:
                        stmt = stmt.where(
                            Memory.marginalia["entities"].op("@>")(
                                [canonical_entity]
                            )
                        )
                    
                    # Apply ordering
                    if actual_order == "asc":
                        stmt = stmt.order_by(Memory.created_at.asc())
                    else:
                        stmt = stmt.order_by(Memory.created_at.desc())
                    
                    # Apply pagination
                    stmt = stmt.limit(limit).offset(offset)
                    
                    # Execute and convert to MemoryOutput
                    result = await session.execute(stmt)
                    rows = result.fetchall()
                    
                    memories = []
                    for row in rows:
                        age = TimeService.format_age(row.created_at)
                        memory_output = MemoryOutput(
                            id=row.id,
                            content=row.content,
                            created_at=row.created_at,
                            similarity_score=None,  # No similarity in browse mode
                            marginalia=row.marginalia or {},
                            age=age,
                        )
                        memories.append(memory_output)
                    
                    logger.info(
                        "Browse mode results",
                        count=len(memories),
                        interval=interval,
                        entity=entity
                    )
                    
                    return memories
                
                # Search mode - continue with existing logic but add filters
                # First, check for entity matches in marginalia
                entity_matches = []
                if search_type != "exact" and query:
                    # Try to canonicalize the query - it might be an entity alias
                    entity_service = get_entity_service()
                    result = await entity_service.canonicalize_names([query])
                    search_entity = result["entities"][0] if result["entities"] else query
                    
                    logger.info(
                        "Entity search canonicalization",
                        query=query,
                        canonical=search_entity
                    )
                    
                    # Look for the canonicalized entity in entities array
                    # For unknown_entities, still use the original query
                    entity_stmt = (
                        select(
                            Memory.id,
                            Memory.content,
                            Memory.created_at,
                            Memory.marginalia,
                        )
                        .where(
                            # Check if canonicalized name is in entities array
                            # OR original query is in unknown_entities array
                            (Memory.marginalia["entities"].op("@>")([search_entity]))
                            | (Memory.marginalia["unknown_entities"].op("@>")([query]))
                        )
                    )
                    
                    # Apply temporal filter
                    if start_dt and end_dt:
                        entity_stmt = entity_stmt.where(
                            Memory.created_at.between(start_dt, end_dt)
                        )
                    
                    # Apply entity filter (in addition to query match)
                    if canonical_entity and canonical_entity != query:
                        entity_stmt = entity_stmt.where(
                            Memory.marginalia["entities"].op("@>")(
                                [canonical_entity]
                            )
                        )
                    
                    entity_stmt = entity_stmt.order_by(Memory.created_at.desc()).limit(limit)

                    entity_result = await session.execute(entity_stmt)
                    entity_rows = entity_result.fetchall()

                    # Convert entity matches to MemoryOutput with perfect similarity
                    for row in entity_rows:
                        age = TimeService.format_age(row.created_at)
                        memory_output = MemoryOutput(
                            id=row.id,
                            content=row.content,
                            created_at=row.created_at,
                            similarity_score=1.0,  # Perfect score for entity matches
                            marginalia=row.marginalia or {},
                            age=age,
                        )
                        entity_matches.append(memory_output)

                    logger.info(
                        "Entity matches found",
                        query=query,
                        count=len(entity_matches),
                    )
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
                    )
                    
                    # Apply temporal filter
                    if start_dt and end_dt:
                        stmt = stmt.where(
                            Memory.created_at.between(start_dt, end_dt)
                        )
                    
                    # Apply entity filter
                    if canonical_entity:
                        stmt = stmt.where(
                            Memory.marginalia["entities"].op("@>")(
                                [canonical_entity]
                            )
                        )
                    
                    # Apply ordering based on actual_order
                    if actual_order == "asc":
                        stmt = stmt.order_by(Memory.created_at.asc())
                    else:
                        stmt = stmt.order_by(Memory.created_at.desc())
                    
                    # Apply pagination
                    stmt = stmt.limit(limit).offset(offset)

                else:
                    # Vector similarity search - need embeddings
                    # We know query is not None here because we're not in browse mode
                    semantic_emb, emotional_emb = await self.embedding_service.embed(
                        query  # type: ignore
                    )

                    # Collect entity match IDs to exclude from vector search
                    entity_match_ids = [m.id for m in entity_matches]

                    if search_type == "semantic":
                        # Semantic search using SQLAlchemy Vector distance methods
                        # pgvector provides cosine_distance method on Vector columns
                        stmt = select(
                            Memory.id,
                            Memory.content,
                            Memory.created_at,
                            Memory.marginalia,
                            Memory.semantic_embedding.cosine_distance(
                                semantic_emb.tolist()
                            ).label("distance"),
                        ).where(Memory.semantic_embedding.is_not(None))

                        # Exclude entity matches to avoid duplicates
                        if entity_match_ids:
                            stmt = stmt.where(~Memory.id.in_(entity_match_ids))
                        
                        # Apply temporal filter
                        if start_dt and end_dt:
                            stmt = stmt.where(
                                Memory.created_at.between(start_dt, end_dt)
                            )
                        
                        # Apply entity filter
                        if canonical_entity:
                            stmt = stmt.where(
                                Memory.marginalia["entities"].op("@>")(
                                    [canonical_entity]
                                )
                            )

                        stmt = stmt.order_by(
                            Memory.semantic_embedding.cosine_distance(
                                semantic_emb.tolist()
                            )
                        ).limit(
                            limit - len(entity_matches)
                        )  # Adjust limit for entity matches

                    elif search_type == "emotional":
                        # Emotional search using SQLAlchemy Vector distance methods
                        stmt = select(
                            Memory.id,
                            Memory.content,
                            Memory.created_at,
                            Memory.marginalia,
                            Memory.emotional_embedding.cosine_distance(
                                emotional_emb.tolist()
                            ).label("distance"),
                        ).where(Memory.emotional_embedding.is_not(None))

                        # Exclude entity matches to avoid duplicates
                        if entity_match_ids:
                            stmt = stmt.where(~Memory.id.in_(entity_match_ids))
                        
                        # Apply temporal filter
                        if start_dt and end_dt:
                            stmt = stmt.where(
                                Memory.created_at.between(start_dt, end_dt)
                            )
                        
                        # Apply entity filter
                        if canonical_entity:
                            stmt = stmt.where(
                                Memory.marginalia["entities"].op("@>")(
                                    [canonical_entity]
                                )
                            )

                        stmt = stmt.order_by(
                            Memory.emotional_embedding.cosine_distance(
                                emotional_emb.tolist()
                            )
                        ).limit(
                            limit - len(entity_matches)
                        )  # Adjust limit for entity matches

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
                        )

                        # Exclude entity matches to avoid duplicates
                        if entity_match_ids:
                            stmt = stmt.where(~Memory.id.in_(entity_match_ids))
                        
                        # Apply temporal filter
                        if start_dt and end_dt:
                            stmt = stmt.where(
                                Memory.created_at.between(start_dt, end_dt)
                            )
                        
                        # Apply entity filter
                        if canonical_entity:
                            stmt = stmt.where(
                                Memory.marginalia["entities"].op("@>")(
                                    [canonical_entity]
                                )
                            )

                        stmt = stmt.order_by(avg_distance).limit(
                            limit - len(entity_matches)
                        )  # Adjust limit for entity matches

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

                # Combine entity matches (first) with vector search results
                # Entity matches have perfect similarity and should appear first
                combined_results = entity_matches + memories

                logger.info(
                    "Search completed",
                    query=query,
                    search_type=search_type,
                    entity_matches=len(entity_matches),
                    vector_matches=len(memories),
                    total_results=len(combined_results),
                )

                return combined_results[
                    :limit
                ]  # Ensure we don't exceed requested limit

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
                    similarity_score=None,  # Not from a search
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
