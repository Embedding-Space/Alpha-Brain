"""Memory service for ingestion and retrieval."""

from __future__ import annotations

import json
import uuid
from typing import Any, Literal
from uuid import UUID

import numpy as np
import pendulum
from sklearn.cluster import DBSCAN, HDBSCAN, AgglomerativeClustering, KMeans
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy import or_, select
from structlog import get_logger

from alpha_brain.database import get_db
from alpha_brain.embeddings import get_embedding_service
from alpha_brain.interval_parser import parse_interval
from alpha_brain.memory_helper import MemoryHelper
from alpha_brain.schema import Memory, MemoryOutput, NameIndex
from alpha_brain.splash_engine import get_splash_engine
from alpha_brain.time_service import TimeService

logger = get_logger()

ClusterAlgorithm = Literal["hdbscan", "dbscan", "agglomerative", "kmeans"]


async def canonicalize_entity_name(name: str) -> str:
    """Canonicalize an entity name using the name index."""
    async with get_db() as session:
        stmt = select(NameIndex.canonical_name).where(NameIndex.name == name)
        result = await session.execute(stmt)
        canonical = result.scalar_one_or_none()
        return canonical or name  # Return original if not found


async def get_all_aliases(canonical_name: str) -> list[str]:
    """Get all aliases for a canonical name, including the canonical name itself."""
    async with get_db() as session:
        # Find all names that map to this canonical name
        stmt = select(NameIndex.name).where(NameIndex.canonical_name == canonical_name)
        result = await session.execute(stmt)
        aliases = [row.name for row in result]
        
        # Always include the canonical name itself
        if canonical_name not in aliases:
            aliases.append(canonical_name)
            
        return aliases


class ClusterCandidate:
    """Represents a cluster of related memories."""
    
    def __init__(self, cluster_id: int, memories: list[Memory], similarity: float, embeddings: np.ndarray | None = None):
        self.cluster_id = cluster_id
        self.memories = memories
        self.similarity = similarity
        self.memory_count = len(memories)
        self.memory_ids = [str(m.id) for m in memories]
        
        # Calculate age range for the cluster first (needed for metrics)
        created_dates = [m.created_at for m in memories]
        self.oldest = min(created_dates)
        self.newest = max(created_dates)
        
        # Calculate cluster metrics if embeddings provided
        self.centroid = None
        self.radius = None
        self.density_std = None
        self.interestingness_score = 0.0
        self.interestingness_vector = np.zeros(4)  # [size, tightness, focus, density]
        
        if embeddings is not None and len(embeddings) > 0:
            self._calculate_metrics(embeddings)
        
        # Default values - will be updated by Helper analysis
        self.title = f"Cluster {cluster_id}"
        self.summary = f"Cluster of {self.memory_count} related memories"
        self.insights: list[str] = []
        self.patterns: list[str] = []
        self.technical_knowledge: list[str] = []
        self.relationships: list[str] = []
        self.crystallizable: bool = False
        self.suggested_document_type: str = ""
        
        # Centroid memory - will be set by crystallization service
        self.centroid_memory: Memory | None = None
        self.centroid_distance: float = 0.0
    
    @property
    def time_span_days(self) -> float:
        """Get time span in days."""
        return (self.newest - self.oldest).total_seconds() / 86400.0
    
    def _calculate_metrics(self, embeddings: np.ndarray):
        """Calculate cluster metrics: centroid, radius, density."""
        # Calculate centroid (mean of all embeddings)
        self.centroid = np.mean(embeddings, axis=0)
        
        # Calculate distances from centroid
        # Using cosine distance: 1 - cosine_similarity
        centroid_norm = self.centroid / np.linalg.norm(self.centroid)
        distances = []
        
        for embedding in embeddings:
            # Normalize embedding
            emb_norm = embedding / np.linalg.norm(embedding)
            # Cosine similarity
            cos_sim = np.dot(centroid_norm, emb_norm)
            # Cosine distance
            distance = 1 - cos_sim
            distances.append(distance)
        
        distances = np.array(distances)
        
        # Radius is the maximum distance
        self.radius = float(np.max(distances))
        
        # Density standard deviation
        self.density_std = float(np.std(distances))
        
        # Calculate time span in days
        time_span_seconds = (self.newest - self.oldest).total_seconds()
        time_span_days = time_span_seconds / 86400.0  # Convert to days
        
        # Calculate interestingness vector components
        # 1. Size score: Aggressive penalty for small clusters
        optimal_size = 25.0
        if self.memory_count < 5:
            # Severe penalty for tiny clusters - exponential decay
            size_score = 0.5 * (self.memory_count / 5.0) ** 2
        elif self.memory_count < 15:
            # Linear ramp up to midpoint
            size_score = 0.5 + 4.5 * (self.memory_count - 5) / 10.0
        elif self.memory_count <= 35:
            # Peak region around 25
            # Gaussian-like peak
            deviation = abs(self.memory_count - optimal_size) / 5.0
            size_score = 10.0 * np.exp(-0.5 * deviation ** 2)
        else:
            # Gentle decline for large clusters
            size_score = 5.0 * np.exp(-((self.memory_count - 35) / 50.0))
        
        # 2. Tightness score: inverse of radius, but scaled to reasonable range
        # Map radius [0, 1] to score [10, 1]
        tightness_score = max(1.0, min(10.0, 1.0 / (self.radius + 0.1)))
        
        # 3. Temporal focus score: inverse log of time span
        # Map days [0, 365] to score [10, 1] roughly
        if time_span_days < 0.04:  # Less than 1 hour
            focus_score = 10.0
        else:
            focus_score = max(1.0, min(10.0, 2.0 / np.log10(time_span_days + 1.1)))
        
        # 4. Density uniformity score: inverse of std dev
        density_score = max(1.0, min(10.0, 1.0 / (self.density_std + 0.1)))
        
        # Store as vector
        self.interestingness_vector = np.array([
            size_score,
            tightness_score,
            focus_score,
            density_score
        ])
        
        # Calculate scalar score as weighted dot product
        # Heavily weight size to avoid tiny clusters dominating
        weights = np.array([0.5, 0.25, 0.15, 0.1])
        self.interestingness_score = float(np.dot(self.interestingness_vector, weights))


class MemoryService:
    """Service for managing memories."""

    def __init__(self, embedding_service=None, memory_helper=None, splash_engine=None):
        """Initialize the memory service."""
        self.embedding_service = embedding_service or get_embedding_service()
        self.memory_helper = memory_helper or MemoryHelper()
        self.splash_engine = splash_engine or get_splash_engine()
        # Clustering cache
        self._cached_clusters: list[ClusterCandidate] | None = None
        self._cache_params: dict[str, Any] | None = None
        self._cache_memory_ids: set[str] | None = None

    async def _analyze_memory_safe(self, content: str) -> dict[str, Any]:
        """Analyze memory with error handling, returns minimal metadata on failure."""
        try:
            logger.info("Analyzing memory")
            metadata = await self.memory_helper.analyze_memory(content)

            # Convert to dict for storage
            metadata_dict = {
                "names": metadata.names,  # Store all names as-is
                "importance": metadata.importance,
                "keywords": metadata.keywords,
                "summary": metadata.summary,
                "analyzed_at": pendulum.now("UTC").isoformat(),
            }

            logger.info(
                "Memory analyzed",
                name_count=len(metadata.names),
                importance=metadata.importance,
            )
            return metadata_dict
        except Exception as e:
            logger.warning("Memory analysis failed", error=str(e))
            # Return minimal metadata
            return {
                "entities": [],
                "unknown_entities": [],
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

            # Canonicalize entity names if any were extracted
            if metadata.get("unknown_entities"):
                canonical_entities = []
                for name in metadata["unknown_entities"]:
                    canonical = await canonicalize_entity_name(name)
                    if canonical not in canonical_entities:
                        canonical_entities.append(canonical)
                
                # Update metadata with canonical entities
                metadata["entities"] = canonical_entities
                logger.info(
                    "Canonicalized entities",
                    unknown=metadata["unknown_entities"],
                    canonical=canonical_entities
                )

            # Merge provided marginalia with our metadata
            combined_marginalia = {**(marginalia or {}), **metadata}

            async with get_db() as session:
                memory = Memory(
                    id=uuid.uuid4(),
                    content=content,
                    created_at=pendulum.now("UTC"),
                    semantic_embedding=semantic_emb.tolist(),
                    emotional_embedding=emotional_emb.tolist(),
                    marginalia=combined_marginalia
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
                
                # Get all aliases for entity filter if provided
                entity_aliases = []
                if entity:
                    canonical_entity = await canonicalize_entity_name(entity)
                    entity_aliases = await get_all_aliases(canonical_entity)
                    logger.info(
                        "Entity filter expanded",
                        input=entity,
                        canonical=canonical_entity,
                        aliases=entity_aliases
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
                    
                    # Apply entity filter - check if any alias is in names
                    if entity_aliases:
                        # Check if the names array contains any of the aliases
                        conditions = []
                        for alias in entity_aliases:
                            conditions.append(
                                Memory.marginalia["names"].op("@>")([alias])
                            )
                        stmt = stmt.where(or_(*conditions))
                    
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
                # First, check for name matches in marginalia
                entity_matches = []
                if search_type != "exact" and query:
                    # Get all aliases for the query
                    query_canonical = await canonicalize_entity_name(query)
                    query_aliases = await get_all_aliases(query_canonical)
                    
                    logger.info(
                        "Name search expansion",
                        query=query,
                        canonical=query_canonical,
                        aliases=query_aliases
                    )
                    
                    # Look for any of the aliases in the names array
                    entity_stmt = (
                        select(
                            Memory.id,
                            Memory.content,
                            Memory.created_at,
                            Memory.marginalia,
                        )
                        .where(
                            # Check if any alias is in the names array
                            or_(*[
                                Memory.marginalia["names"].op("@>")([alias])
                                for alias in query_aliases
                            ])
                        )
                    )
                    
                    # Apply temporal filter
                    if start_dt and end_dt:
                        entity_stmt = entity_stmt.where(
                            Memory.created_at.between(start_dt, end_dt)
                        )
                    
                    # Apply entity filter (in addition to query match)
                    if entity_aliases and query_canonical not in entity_aliases:
                        entity_stmt = entity_stmt.where(
                            or_(*[
                                Memory.marginalia["names"].op("@>")([alias])
                                for alias in entity_aliases
                            ])
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
                    
                    # Apply entity filter - check if any alias is in names
                    if entity_aliases:
                        # Check if the names array contains any of the aliases
                        conditions = []
                        for alias in entity_aliases:
                            conditions.append(
                                Memory.marginalia["names"].op("@>")([alias])
                            )
                        stmt = stmt.where(or_(*conditions))
                    
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
                        
                        # Apply entity filter - check if any alias is in names
                        if entity_aliases:
                            stmt = stmt.where(
                                or_(*[
                                    Memory.marginalia["names"].op("@>")([alias])
                                    for alias in entity_aliases
                                ])
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
                        
                        # Apply entity filter - check if any alias is in names
                        if entity_aliases:
                            stmt = stmt.where(
                                or_(*[
                                    Memory.marginalia["names"].op("@>")([alias])
                                    for alias in entity_aliases
                                ])
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
                        
                        # Apply entity filter - check if any alias is in names
                        if entity_aliases:
                            stmt = stmt.where(
                                or_(*[
                                    Memory.marginalia["names"].op("@>")([alias])
                                    for alias in entity_aliases
                                ])
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

    def _extract_embeddings(
        self,
        memories: list[Memory],
        embedding_type: Literal["semantic", "emotional"]
    ) -> np.ndarray:
        """Extract embeddings from memories as numpy array."""
        if embedding_type == "semantic":
            embeddings = []
            for m in memories:
                if m.semantic_embedding is not None:
                    # Handle string-encoded embeddings
                    if isinstance(m.semantic_embedding, str):
                        emb = json.loads(m.semantic_embedding)
                    else:
                        emb = m.semantic_embedding
                    embeddings.append(np.array(emb))
                else:
                    embeddings.append(np.zeros(768))
            return np.array(embeddings)
        embeddings = []
        for m in memories:
            if m.emotional_embedding is not None:
                # Handle string-encoded embeddings
                if isinstance(m.emotional_embedding, str):
                    emb = json.loads(m.emotional_embedding)
                else:
                    emb = m.emotional_embedding
                embeddings.append(np.array(emb))
            else:
                embeddings.append(np.zeros(7))
        return np.array(embeddings)

    def _apply_clustering_algorithm(
        self,
        embeddings: np.ndarray,
        algorithm: ClusterAlgorithm,
        similarity_threshold: float,
        n_clusters: int | None,
        memory_count: int
    ) -> np.ndarray:
        """Apply the selected clustering algorithm."""
        if algorithm == "hdbscan":
            return self._cluster_hdbscan(embeddings, similarity_threshold)
        if algorithm == "dbscan":
            return self._cluster_dbscan(embeddings, similarity_threshold)
        if algorithm == "agglomerative":
            return self._cluster_agglomerative(embeddings, similarity_threshold)
        if algorithm == "kmeans":
            if n_clusters is None:
                import math
                n_clusters = max(2, int(math.sqrt(memory_count)))
            return self._cluster_kmeans(embeddings, n_clusters)
        raise ValueError(f"Unknown algorithm: {algorithm}")

    def _create_cluster_candidates(
        self,
        labels: np.ndarray,
        memories: list[Memory],
        embeddings: np.ndarray
    ) -> list[ClusterCandidate]:
        """Create ClusterCandidate objects from clustering results."""
        # Group memories by cluster
        clusters: dict[int, list[Memory]] = {}
        for idx, label in enumerate(labels):
            if label == -1:  # Skip noise points
                continue
            if label not in clusters:
                clusters[label] = []
            clusters[label].append(memories[idx])
            
        # Create ClusterCandidate objects
        candidates = []
        for cluster_id, cluster_memories in clusters.items():
            # Calculate average similarity within cluster
            cluster_indices = [i for i, label in enumerate(labels) if label == cluster_id]
            cluster_embeddings = embeddings[cluster_indices]
            
            if len(cluster_memories) > 1:
                similarity_matrix = cosine_similarity(cluster_embeddings)
                # Average of upper triangle (excluding diagonal)
                mask = np.triu(np.ones_like(similarity_matrix, dtype=bool), k=1)
                avg_similarity = similarity_matrix[mask].mean()
            else:
                avg_similarity = 1.0  # Single-memory cluster
                
            candidate = ClusterCandidate(
                cluster_id=cluster_id,
                memories=cluster_memories,
                similarity=avg_similarity,
                embeddings=cluster_embeddings
            )
            
            # Calculate centroid and find closest memory
            if len(cluster_memories) > 0 and cluster_indices and max(cluster_indices) < len(embeddings):
                # Note: centroid is already calculated in ClusterCandidate
                centroid = candidate.centroid if candidate.centroid is not None else cluster_embeddings.mean(axis=0)
                
                # Find memory closest to centroid
                distances = cosine_similarity([centroid], cluster_embeddings)[0]
                closest_idx = np.argmax(distances)
                
                # Map back to the memory - ensure index is valid
                if closest_idx < len(cluster_indices):
                    memory_idx = cluster_indices[closest_idx]
                    if memory_idx < len(memories):
                        candidate.centroid_memory = memories[memory_idx]
                        candidate.centroid_distance = distances[closest_idx]
            
            candidates.append(candidate)
            
        # Sort by cluster size (larger clusters first)
        candidates.sort(key=lambda c: c.memory_count, reverse=True)
        return candidates

    def cluster_memories(
        self, 
        memories: list[Memory], 
        similarity_threshold: float = 0.675,
        embedding_type: Literal["semantic", "emotional"] = "semantic",
        n_clusters: int | None = None,
        algorithm: ClusterAlgorithm = "hdbscan"
    ) -> list[ClusterCandidate]:
        """
        Cluster memories using the specified algorithm.
        
        Args:
            memories: List of Memory objects to cluster
            similarity_threshold: Minimum similarity for clustering (0.675 default)
            embedding_type: Which embeddings to use for clustering
            n_clusters: Number of clusters for kmeans (required for kmeans only)
            algorithm: Clustering algorithm to use
            
        Returns:
            List of ClusterCandidate objects
        """
        if not memories:
            return []
        
        # Check if we can use cached results
        if self._is_cache_valid(memories, similarity_threshold, embedding_type, n_clusters, algorithm):
            logger.info(
                "Using cached clustering results",
                cluster_count=len(self._cached_clusters) if self._cached_clusters else 0
            )
            return self._cached_clusters or []
            
        logger.info(
            "Starting clustering",
            memory_count=len(memories),
            algorithm=algorithm,
            threshold=similarity_threshold
        )
        
        # Extract embeddings
        embeddings = self._extract_embeddings(memories, embedding_type)
            
        # Apply clustering algorithm
        labels = self._apply_clustering_algorithm(
            embeddings, algorithm, similarity_threshold, n_clusters, len(memories)
        )
            
        # Create cluster candidates
        candidates = self._create_cluster_candidates(labels, memories, embeddings)
        
        logger.info(
            "Clustering complete",
            total_memories=len(memories),
            clusters_found=len(candidates),
            noise_points=sum(1 for label in labels if label == -1)
        )
        
        # Cache the results
        self._cached_clusters = candidates
        self._cache_params = {
            "similarity_threshold": similarity_threshold,
            "embedding_type": embedding_type,
            "n_clusters": n_clusters,
            "algorithm": algorithm
        }
        self._cache_memory_ids = {str(m.id) for m in memories}
        
        return candidates
        
    def _cluster_hdbscan(self, embeddings: np.ndarray, threshold: float) -> np.ndarray:
        """HDBSCAN: Density-based clustering that finds clusters of varying densities."""
        # Convert similarity threshold to distance threshold
        # similarity = 1 - distance, so distance = 1 - similarity
        distance_threshold = 1 - threshold
        
        clusterer = HDBSCAN(
            min_cluster_size=2,  # Minimum 2 memories per cluster
            metric='cosine',
            cluster_selection_epsilon=distance_threshold,
            cluster_selection_method='eom'  # Excess of Mass
        )
        return clusterer.fit_predict(embeddings)
        
    def _cluster_dbscan(self, embeddings: np.ndarray, threshold: float) -> np.ndarray:
        """DBSCAN: Original density-based clustering algorithm."""
        distance_threshold = 1 - threshold
        
        clusterer = DBSCAN(
            eps=distance_threshold,
            min_samples=2,
            metric='cosine'
        )
        return clusterer.fit_predict(embeddings)
        
    def _cluster_agglomerative(self, embeddings: np.ndarray, threshold: float) -> np.ndarray:
        """Agglomerative: Hierarchical clustering that merges similar clusters."""
        distance_threshold = 1 - threshold
        
        clusterer = AgglomerativeClustering(
            n_clusters=None,
            distance_threshold=distance_threshold,
            metric='cosine',
            linkage='average'
        )
        return clusterer.fit_predict(embeddings)
        
    def _cluster_kmeans(self, embeddings: np.ndarray, n_clusters: int) -> np.ndarray:
        """K-Means: Classic clustering that partitions into K clusters."""
        # K-means doesn't use similarity threshold, needs number of clusters
        n_clusters = max(2, min(n_clusters, len(embeddings) // 2))
        
        clusterer = KMeans(
            n_clusters=n_clusters,
            random_state=42,
            n_init=10
        )
        return clusterer.fit_predict(embeddings)
    
    def _is_cache_valid(
        self,
        memories: list[Memory],
        similarity_threshold: float,
        embedding_type: Literal["semantic", "emotional"],
        n_clusters: int | None,
        algorithm: ClusterAlgorithm
    ) -> bool:
        """Check if cached clusters are valid for the given parameters."""
        if self._cached_clusters is None or self._cache_params is None:
            return False
        
        # Check if parameters match
        params_match = (
            self._cache_params.get("similarity_threshold") == similarity_threshold and
            self._cache_params.get("embedding_type") == embedding_type and
            self._cache_params.get("n_clusters") == n_clusters and
            self._cache_params.get("algorithm") == algorithm
        )
        
        if not params_match:
            return False
        
        # Check if the same memories are being clustered
        current_memory_ids = {str(m.id) for m in memories}
        return current_memory_ids == self._cache_memory_ids
    
    def get_cached_clusters(self) -> list[ClusterCandidate] | None:
        """Get cached clusters if available."""
        return self._cached_clusters
    
    def clear_cluster_cache(self):
        """Clear the cluster cache."""
        self._cached_clusters = None
        self._cache_params = None
        self._cache_memory_ids = None


# Global instance
_memory_service = None


def get_memory_service() -> MemoryService:
    """Get the global memory service instance."""
    global _memory_service
    if _memory_service is None:
        _memory_service = MemoryService()
    return _memory_service
