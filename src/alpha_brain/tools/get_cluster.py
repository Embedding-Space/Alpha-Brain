"""Get a specific cluster from the cache."""

from fastmcp import Context
from structlog import get_logger

from alpha_brain.crystallization_service import get_crystallization_service
from alpha_brain.templates import render_output
from alpha_brain.time_service import TimeService

logger = get_logger()


async def get_cluster(
    ctx: Context,
    cluster_id: str
) -> str:
    """
    Retrieve a specific cluster from the cache.
    
    This tool shows all memories in a cluster that was found by find_clusters.
    You must run find_clusters first to populate the cache.
    
    Args:
        ctx: MCP context
        cluster_id: The cluster ID from find_clusters output
        
    Returns:
        All memories in the specified cluster with full content
    """
    # Get crystallization service and check for cached results
    crystallization_service = get_crystallization_service()
    
    cached_candidates = crystallization_service.get_cached_clusters()
    if cached_candidates is None:
        return render_output(
            "get_cluster_error",
            error="No clusters in cache. Please run find_clusters first.",
            current_time=TimeService.format_full(TimeService.now())
        )
    
    # Find the requested cluster
    try:
        cluster_id_int = int(cluster_id)
    except ValueError:
        return render_output(
            "get_cluster_error",
            error=f"Invalid cluster ID: {cluster_id}. Must be a number.",
            current_time=TimeService.format_full(TimeService.now())
        )
    
    cluster = None
    for candidate in cached_candidates:
        if candidate.cluster_id == cluster_id_int:
            cluster = candidate
            break
    
    if cluster is None:
        return render_output(
            "get_cluster_error",
            error=f"Cluster {cluster_id} not found in cache. Available cluster IDs: {[c.cluster_id for c in cached_candidates]}",
            current_time=TimeService.format_full(TimeService.now())
        )
    
    # Format all memories in the cluster
    memory_dicts = []
    for memory in cluster.memories:
        memory_dict = {
            "id": str(memory.id),
            "content": memory.content,
            "created_at": TimeService.format_datetime_scannable(memory.created_at),
            "age": TimeService.format_age(memory.created_at),
            "marginalia": memory.marginalia
        }
        memory_dicts.append(memory_dict)
    
    # Sort by created_at (oldest first for reading chronologically)
    memory_dicts.sort(key=lambda m: m["created_at"])
    
    # Calculate normalized interestingness
    normalized_interestingness = cluster.interestingness_score / 10.0
    
    return render_output(
        "get_cluster",
        cluster_id=cluster_id,
        memory_count=cluster.memory_count,
        similarity=cluster.similarity,
        interestingness=normalized_interestingness,
        time_span=TimeService.format_age_difference(cluster.oldest, cluster.newest),
        memories=memory_dicts,
        current_time=TimeService.format_full(TimeService.now())
    )