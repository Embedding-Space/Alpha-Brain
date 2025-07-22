"""Memory crystallization tool - extract structured knowledge from memory clusters."""

from fastmcp import Context
from sqlalchemy import select, text

from alpha_brain.crystallization_service import get_crystallization_service
from alpha_brain.database import get_db
from alpha_brain.embeddings import get_embedding_service
from alpha_brain.interval_parser import parse_interval
from alpha_brain.schema import Memory
from alpha_brain.templates import render_output
from alpha_brain.time_service import TimeService
from structlog import get_logger

logger = get_logger()


async def crystallize(
    ctx: Context, 
    query: str | None = None, 
    interval: str | None = None,
    limit: int = 10,
    algorithm: str = "hdbscan",
    n_clusters: int | None = None,
    similarity_threshold: float = 0.55,
    sort_by: str = "interestingness",
    min_cluster_size: int = 5,
    refresh: bool = False
) -> str:
    """
    Find clusters of related memories that might contain crystallizable knowledge.
    
    This tool identifies groups of semantically similar memories without deep analysis.
    Use this to discover potential knowledge patterns before deciding which clusters
    deserve deeper investigation.
    
    Results are cached so that analyze_cluster can reliably examine the same clusters.
    Run with refresh=True to force new clustering.
    
    Args:
        ctx: MCP context
        query: Filter memories by semantic relevance to this query
        interval: Filter memories by time interval (e.g., "last week", "July 2025")
        limit: Maximum number of cluster candidates to return
        algorithm: Clustering algorithm to use (hdbscan, kmeans, dbscan, agglomerative)
        n_clusters: Number of clusters for kmeans (defaults to sqrt(n_memories))
        similarity_threshold: Minimum similarity for clustering (0.55 default, range 0.4-0.8)
            - 0.75-0.8: Very tight clusters (often just 2-3 highly similar memories)
            - 0.65-0.75: Balanced clusters (recommended default)
            - 0.5-0.65: Looser topical groupings
            - 0.4-0.5: Very broad themes (may be too noisy)
        sort_by: How to sort results - "interestingness" (default) or "size"
        min_cluster_size: Minimum number of memories required in a cluster (default 5)
        refresh: Force fresh clustering instead of using cached results (default False)
        
    Returns:
        List of memory clusters with basic statistics and preview content
    """
    # Step 1: Apply filtering logic to get candidate memories
    async with get_db() as session:
        # Get total memory count for context
        total_stmt = select(Memory)
        total_result = await session.execute(total_stmt)
        total_count = len(total_result.scalars().all())
        
        if not query and not interval:
            # Explore mode: Most recent 5000 memories
            stmt = select(Memory).order_by(Memory.created_at.desc()).limit(5000)
            mode = "explore"
        elif interval and not query:
            # Browse mode: Filter by time interval
            start_time, end_time = parse_interval(interval)
            stmt = select(Memory).where(
                Memory.created_at >= start_time,
                Memory.created_at <= end_time
            ).order_by(Memory.created_at.desc()).limit(5000)
            mode = "browse"
        elif query and not interval:
            # Query mode: Filter by semantic relevance using full-text search
            # Use PostgreSQL full-text search like in the search tool
            stmt = text("""
                SELECT id, content, created_at, semantic_embedding, emotional_embedding, marginalia, entity_ids
                FROM memories 
                WHERE search_vector @@ plainto_tsquery('english', :query)
                ORDER BY ts_rank(search_vector, plainto_tsquery('english', :query)) DESC
                LIMIT 5000
            """)
            result = await session.execute(stmt, {"query": query})
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
            mode = "query"
        else:
            # Combined mode: Query + interval filtering
            start_time, end_time = parse_interval(interval)
            stmt = text("""
                SELECT id, content, created_at, semantic_embedding, emotional_embedding, marginalia, entity_ids
                FROM memories 
                WHERE search_vector @@ plainto_tsquery('english', :query)
                AND created_at >= :start_time AND created_at <= :end_time
                ORDER BY ts_rank(search_vector, plainto_tsquery('english', :query)) DESC
                LIMIT 5000
            """)
            result = await session.execute(stmt, {
                "query": query, 
                "start_time": start_time, 
                "end_time": end_time
            })
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
            mode = "query+browse"
        
        # Execute query for simple cases (explore, browse)
        if mode in ["explore", "browse"]:
            result = await session.execute(stmt)
            memories = result.scalars().all()
            filtered_count = len(memories)
    
    # Step 2: Run clustering analysis on filtered memory set
    crystallization_service = get_crystallization_service(algorithm=algorithm)
    
    # Clear cache if refresh requested
    if refresh:
        crystallization_service.clear_cache()
        logger.info("Cleared cluster cache - running fresh clustering")
    
    # Calculate default n_clusters if not provided
    if algorithm == "kmeans" and n_clusters is None:
        import math
        n_clusters = max(2, int(math.sqrt(len(memories))))
        logger.info(f"Using sqrt(n) heuristic: {len(memories)} memories → {n_clusters} clusters")
    
    candidates = crystallization_service.cluster_memories(
        memories=memories,
        similarity_threshold=similarity_threshold,
        embedding_type="semantic",
        n_clusters=n_clusters
    )
    
    # Filter out small clusters
    total_clusters_found = len(candidates)
    candidates = [c for c in candidates if c.memory_count >= min_cluster_size]
    filtered_clusters = total_clusters_found - len(candidates)
    
    # Sort by chosen method
    if sort_by == "size":
        candidates.sort(key=lambda c: c.memory_count, reverse=True)
    else:
        # Default to interestingness
        candidates.sort(key=lambda c: c.interestingness_score, reverse=True)
    
    # Convert candidates to template-friendly format (no Helper analysis)
    candidate_dicts = []
    for i, candidate in enumerate(candidates[:limit]):
        # Get centroid memory if available
        centroid_data = None
        if candidate.centroid_memory:
            memory = candidate.centroid_memory
            # Format timestamp using TimeService
            timestamp = TimeService.format_datetime_scannable(memory.created_at)
            
            centroid_data = {
                "timestamp": timestamp,
                "content": memory.content,
                "distance": candidate.centroid_distance
            }
        
        # Extract entities mentioned across all memories in cluster
        all_entity_ids = set()
        for memory in candidate.memories:
            if memory.entity_ids:
                all_entity_ids.update(memory.entity_ids)
        
        # Get entity names from database
        entity_names = []
        if all_entity_ids:
            async with get_db() as session:
                from alpha_brain.schema import Entity
                stmt = select(Entity).where(Entity.id.in_(list(all_entity_ids)))
                result = await session.execute(stmt)
                entities = result.scalars().all()
                entity_names = [e.canonical_name for e in entities]
        
        # Format timestamps for oldest/newest using TimeService
        oldest_formatted = TimeService.format_datetime_scannable(candidate.oldest)
        newest_formatted = TimeService.format_datetime_scannable(candidate.newest)
        
        candidate_dict = {
            "cluster_id": candidate.cluster_id,
            "memory_count": candidate.memory_count,
            "similarity": candidate.similarity,
            "radius": candidate.radius,
            "density_std": candidate.density_std,
            "interestingness_score": candidate.interestingness_score,
            "interestingness_vector": candidate.interestingness_vector.tolist() if hasattr(candidate, 'interestingness_vector') else None,
            "time_span_days": candidate.time_span_days if hasattr(candidate, 'time_span_days') else 0,
            "oldest": oldest_formatted,
            "newest": newest_formatted,
            "centroid": centroid_data,
            "memory_ids": candidate.memory_ids  # All IDs for potential analysis
        }
        candidate_dicts.append(candidate_dict)
    
    return render_output(
        "crystallize",
        mode=mode,
        query=query or "recent memories",
        interval=interval,
        filtered_count=filtered_count,
        total_count=total_count,
        cluster_count=len(candidates),
        total_clusters_found=total_clusters_found,
        filtered_clusters=filtered_clusters,
        min_cluster_size=min_cluster_size,
        candidates=candidate_dicts,
        current_time=TimeService.format_full(TimeService.now())
    )