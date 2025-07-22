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
    similarity_threshold: float = 0.75
) -> str:
    """
    Find clusters of related memories that might contain crystallizable knowledge.
    
    This tool identifies groups of semantically similar memories without deep analysis.
    Use this to discover potential knowledge patterns before deciding which clusters
    deserve deeper investigation.
    
    Args:
        ctx: MCP context
        query: Filter memories by semantic relevance to this query
        interval: Filter memories by time interval (e.g., "last week", "July 2025")
        limit: Maximum number of cluster candidates to return
        algorithm: Clustering algorithm to use (hdbscan, kmeans, dbscan, agglomerative)
        n_clusters: Number of clusters for kmeans (defaults to sqrt(n_memories))
        similarity_threshold: Minimum similarity for clustering (0.75 default, higher = tighter clusters)
        
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
    
    # Sort by interestingness score (most interesting first)
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
        candidates=candidate_dicts,
        current_time=TimeService.format_full(TimeService.now())
    )