"""Find clusters of related memories with sophisticated filtering."""

from fastmcp import Context
from sqlalchemy import select, text, and_, func
from structlog import get_logger

from alpha_brain.database import get_db
from alpha_brain.entity_service import get_entity_service
from alpha_brain.interval_parser import parse_interval
from alpha_brain.memory_service import get_memory_service
from alpha_brain.schema import Memory, Entity
from alpha_brain.templates import render_output
from alpha_brain.time_service import TimeService

logger = get_logger()


async def find_clusters(
    ctx: Context,
    # Filtering parameters (all optional, AND'd together)
    query: str | None = None,           # Semantic search to filter memories
    interval: str | None = None,        # Time interval filter
    entities: list[str] | None = None,  # Filter to clusters containing ALL these entities
    min_interestingness: float = 0.0,   # Normalized 0-1 threshold
    
    # Clustering parameters
    algorithm: str = "hdbscan",
    similarity_threshold: float = 0.675,
    min_cluster_size: int = 5,
    
    # Display parameters
    limit: int = 20,
    sort_by: str = "interestingness",   # or "size", "recency"
) -> str:
    """
    Find clusters of related memories that might contain crystallizable knowledge.
    
    This tool identifies groups of semantically similar memories with sophisticated
    filtering. Results are cached for efficient retrieval with get_cluster.
    
    Args:
        ctx: MCP context
        query: Filter memories by semantic relevance to this query
        interval: Filter memories by time interval (e.g., "last week", "July 2025")
        entities: Filter to clusters containing ALL of these entities
        min_interestingness: Minimum interestingness score (0-1 scale)
        algorithm: Clustering algorithm to use (hdbscan, kmeans, dbscan, agglomerative)
        similarity_threshold: Minimum similarity for clustering (0.675 default)
        min_cluster_size: Minimum number of memories required in a cluster (default 5)
        limit: Maximum number of clusters to return
        sort_by: How to sort results - "interestingness" (default), "size", or "recency"
        
    Returns:
        List of memory clusters with statistics and preview content
    """
    # Step 1: Apply filtering logic to get candidate memories
    async with get_db() as session:
        # Get total memory count for context
        total_count = await session.scalar(select(func.count()).select_from(Memory))
        
        # Build base query
        conditions = []
        params = {}
        
        # Time interval filter
        if interval:
            start_time, end_time = parse_interval(interval)
            conditions.append("created_at >= :start_time AND created_at <= :end_time")
            params["start_time"] = start_time
            params["end_time"] = end_time
        
        # Full-text search filter
        if query:
            conditions.append("search_vector @@ plainto_tsquery('english', :query)")
            params["query"] = query
        
        # Construct SQL query
        if conditions:
            where_clause = " WHERE " + " AND ".join(conditions)
        else:
            where_clause = ""
        
        # Add ordering and limit
        if query:
            # Order by relevance for text search
            order_clause = " ORDER BY ts_rank(search_vector, plainto_tsquery('english', :query)) DESC"
        else:
            # Order by recency for browse/explore
            order_clause = " ORDER BY created_at DESC"
        
        sql = f"""
            SELECT id, content, created_at, semantic_embedding, emotional_embedding, marginalia, entity_ids
            FROM memories{where_clause}{order_clause}
            LIMIT 5000
        """
        
        result = await session.execute(text(sql), params)
        rows = result.fetchall()
        
        # Convert rows to Memory objects
        memories = []
        for row in rows:
            memory = Memory(
                id=row.id,
                content=row.content,
                created_at=row.created_at,
                semantic_embedding=row.semantic_embedding,
                emotional_embedding=row.emotional_embedding,
                marginalia=row.marginalia,
                entity_ids=row.entity_ids
            )
            memories.append(memory)
        
        filtered_count = len(memories)
        
        # Step 2: Apply entity filter if specified
        if entities:
            # Get entity IDs for all specified entities
            entity_service = get_entity_service()
            required_entity_ids = set()
            
            for entity_name in entities:
                canonical_name = await entity_service.get_canonical_name(entity_name)
                if canonical_name:
                    # Get the entity to find its ID
                    stmt = select(Entity).where(Entity.canonical_name == canonical_name)
                    entity = await session.scalar(stmt)
                    if entity:
                        required_entity_ids.add(entity.id)
            
            # Filter memories that contain ALL required entities
            if required_entity_ids:
                memories = [
                    m for m in memories 
                    if m.entity_ids and required_entity_ids.issubset(set(m.entity_ids))
                ]
                logger.info(f"Entity filtering: {filtered_count} → {len(memories)} memories")
                filtered_count = len(memories)
    
    # Step 3: Run clustering analysis on filtered memory set
    memory_service = get_memory_service()
    
    # Clear and regenerate cache
    memory_service.clear_cluster_cache()
    
    # Calculate default n_clusters if kmeans and not provided
    if algorithm == "kmeans":
        import math
        n_clusters = max(2, int(math.sqrt(len(memories))))
    else:
        n_clusters = None
    
    candidates = memory_service.cluster_memories(
        memories=memories,
        similarity_threshold=similarity_threshold,
        embedding_type="semantic",
        n_clusters=n_clusters,
        algorithm=algorithm
    )
    
    # Filter by minimum cluster size
    candidates = [c for c in candidates if c.memory_count >= min_cluster_size]
    
    # Filter by minimum interestingness (normalize from 0-10 scale to 0-1)
    if min_interestingness > 0:
        candidates = [
            c for c in candidates 
            if (c.interestingness_score / 10.0) >= min_interestingness
        ]
    
    # Sort by chosen method
    if sort_by == "size":
        candidates.sort(key=lambda c: c.memory_count, reverse=True)
    elif sort_by == "recency":
        candidates.sort(key=lambda c: c.newest, reverse=True)
    else:
        # Default to interestingness
        candidates.sort(key=lambda c: c.interestingness_score, reverse=True)
    
    # Convert candidates to template-friendly format
    candidate_dicts = []
    for candidate in candidates[:limit]:
        # Get centroid memory preview
        centroid_preview = None
        if candidate.centroid_memory:
            centroid_preview = {
                "content": candidate.centroid_memory.content[:200] + "..." 
                          if len(candidate.centroid_memory.content) > 200 else candidate.centroid_memory.content,
                "timestamp": TimeService.format_age(candidate.centroid_memory.created_at)
            }
        
        # Get entity names for this cluster
        all_entity_ids = set()
        for memory in candidate.memories:
            if memory.entity_ids:
                all_entity_ids.update(memory.entity_ids)
        
        entity_names = []
        if all_entity_ids:
            async with get_db() as session:
                stmt = select(Entity).where(Entity.id.in_(list(all_entity_ids)))
                result = await session.execute(stmt)
                entities_found = result.scalars().all()
                entity_names = sorted([e.canonical_name for e in entities_found])
        
        candidate_dict = {
            "cluster_id": candidate.cluster_id,
            "memory_count": candidate.memory_count,
            "similarity": candidate.similarity,
            "interestingness": candidate.interestingness_score / 10.0,  # Normalize to 0-1
            "time_span": TimeService.format_age_difference(candidate.oldest, candidate.newest),
            "age": TimeService.format_age(candidate.newest),
            "centroid_preview": centroid_preview,
            "entities": entity_names[:5],  # Top 5 entities
            "entity_count": len(entity_names)
        }
        candidate_dicts.append(candidate_dict)
    
    # Determine mode for display
    if query and interval:
        mode = "query+interval"
    elif query:
        mode = "query"
    elif interval:
        mode = "interval"
    else:
        mode = "explore"
    
    return render_output(
        "find_clusters",
        mode=mode,
        query=query,
        interval=interval,
        entity_filter=entities,
        filtered_count=filtered_count,
        total_count=total_count,
        cluster_count=len(candidates),
        candidates=candidate_dicts,
        current_time=TimeService.format_full(TimeService.now())
    )