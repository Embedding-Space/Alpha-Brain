"""Get a specific cluster from the cache."""

from fastmcp import Context
from structlog import get_logger

from alpha_brain.memory_service import get_memory_service
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
    # Get memory service and check for cached results
    memory_service = get_memory_service()
    
    cached_candidates = memory_service.get_cached_clusters()
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
    
    # Sort memories chronologically first
    sorted_memories = sorted(cluster.memories, key=lambda m: m.created_at)
    
    # Get the first memory's time as baseline
    baseline_time = sorted_memories[0].created_at if sorted_memories else None
    
    # Format all memories in the cluster
    memory_dicts = []
    for memory in sorted_memories:
        # Calculate relative time from first memory
        if baseline_time:
            time_diff = memory.created_at - baseline_time
            minutes_diff = int(time_diff.total_seconds() / 60)
            if minutes_diff == 0:
                relative_time = ""
            else:
                relative_time = f" +{minutes_diff} min"
        else:
            relative_time = ""
        
        memory_dict = {
            "id": str(memory.id),
            "content": memory.content,
            "timestamp": TimeService.format_datetime_scannable(memory.created_at),
            "relative_time": relative_time,
            "marginalia": memory.marginalia
        }
        memory_dicts.append(memory_dict)
    
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
