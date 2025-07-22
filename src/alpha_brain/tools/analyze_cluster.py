"""Analyze a specific cluster by showing all memories within it."""

from fastmcp import Context
from sqlalchemy import select

from alpha_brain.crystallization_service import get_crystallization_service
from alpha_brain.database import get_db
from alpha_brain.interval_parser import parse_interval
from alpha_brain.schema import Memory
from alpha_brain.templates import render_output
from alpha_brain.time_service import TimeService
from structlog import get_logger

logger = get_logger()


async def analyze_cluster(
    ctx: Context,
    cluster_number: int,
    query: str | None = None,
    interval: str | None = None,
    algorithm: str = "hdbscan",
    n_clusters: int | None = None,
    similarity_threshold: float = 0.55,
    min_cluster_size: int = 5
) -> str:
    """
    Show all memories in a specific cluster for detailed analysis.
    
    This tool uses cached results from the most recent crystallize run when possible.
    If parameters don't match or no cache exists, it re-runs the clustering.
    For consistent results, run crystallize first with your desired parameters.
    
    Args:
        ctx: MCP context
        cluster_number: Which cluster to analyze (1-based, as shown in crystallize output)
        query: Filter memories by semantic relevance (must match crystallize parameters)
        interval: Filter memories by time interval (must match crystallize parameters)
        algorithm: Clustering algorithm (must match crystallize parameters)
        n_clusters: Number of clusters for kmeans (must match crystallize parameters)
        similarity_threshold: Minimum similarity for clustering (must match crystallize parameters)
        min_cluster_size: Minimum number of memories required in a cluster (must match crystallize parameters)
        
    Returns:
        All memories in the specified cluster with full content
    """
    # Step 1: Apply same filtering logic as crystallize to get candidate memories
    async with get_db() as session:
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
            # Query mode: Use full-text search
            from sqlalchemy import text
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
            mode = "query"
        else:
            # Combined mode: Query + interval filtering
            start_time, end_time = parse_interval(interval)
            from sqlalchemy import text
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
            mode = "query+browse"
        
        # Execute query for simple cases
        if mode in ["explore", "browse"]:
            result = await session.execute(stmt)
            memories = result.scalars().all()
    
    # Step 2: Get crystallization service and check for cached results
    crystallization_service = get_crystallization_service(algorithm=algorithm)
    
    # First check if we have cached clusters
    cached_candidates = crystallization_service.get_cached_clusters()
    if cached_candidates is not None:
        # Verify the cache is for the same memories
        cached_memory_ids = set()
        for candidate in cached_candidates:
            cached_memory_ids.update(candidate.memory_ids)
        
        current_memory_ids = {str(m.id) for m in memories}
        
        if cached_memory_ids == current_memory_ids:
            logger.info("Using cached clustering results")
            candidates = cached_candidates
        else:
            logger.info("Cache invalid - memory sets don't match")
            # Run fresh clustering
            if algorithm == "kmeans" and n_clusters is None:
                import math
                n_clusters = max(2, int(math.sqrt(len(memories))))
            
            candidates = crystallization_service.cluster_memories(
                memories=memories,
                similarity_threshold=similarity_threshold,
                embedding_type="semantic",
                n_clusters=n_clusters
            )
    else:
        # No cache, run clustering
        if algorithm == "kmeans" and n_clusters is None:
            import math
            n_clusters = max(2, int(math.sqrt(len(memories))))
        
        candidates = crystallization_service.cluster_memories(
            memories=memories,
            similarity_threshold=similarity_threshold,
            embedding_type="semantic",
            n_clusters=n_clusters
        )
    
    # Filter out small clusters to match crystallize behavior
    candidates = [c for c in candidates if c.memory_count >= min_cluster_size]
    
    # Step 3: Find the requested cluster (1-based index from user)
    if cluster_number < 1 or cluster_number > len(candidates):
        return f"Invalid cluster number. Found {len(candidates)} clusters (with >= {min_cluster_size} memories), but you requested cluster {cluster_number}."
    
    # Get the cluster (convert to 0-based index)
    cluster = candidates[cluster_number - 1]
    
    # Step 4: Format all memories in the cluster
    memory_dicts = []
    for memory in cluster.memories:
        memory_dict = {
            "id": str(memory.id),
            "content": memory.content,
            "created_at": TimeService.format_datetime_scannable(memory.created_at),
            "marginalia": memory.marginalia
        }
        memory_dicts.append(memory_dict)
    
    # Sort by created_at
    memory_dicts.sort(key=lambda m: m["created_at"])
    
    return render_output(
        "analyze_cluster",
        cluster_number=cluster_number,
        total_clusters=len(candidates),
        memory_count=cluster.memory_count,
        similarity=cluster.similarity,
        radius=cluster.radius,
        density_std=cluster.density_std,
        interestingness_score=cluster.interestingness_score,
        oldest=TimeService.format_datetime_scannable(cluster.oldest),
        newest=TimeService.format_datetime_scannable(cluster.newest),
        memories=memory_dicts,
        current_time=TimeService.format_full(TimeService.now())
    )