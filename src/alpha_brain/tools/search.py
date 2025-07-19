"""Search tool for finding memories."""

from alpha_brain.memory_service import get_memory_service


async def search(query: str, search_type: str = "semantic", limit: int = 10) -> str:
    """
    Search memories using various strategies.

    Args:
        query: The search query
        search_type: Type of search - 'semantic', 'emotional', 'both', or 'exact'
        limit: Maximum number of results (default 10)

    Returns:
        Prose description of matching memories
    """
    service = get_memory_service()
    memories = await service.search(query, search_type, limit)

    if not memories:
        return f"No memories found matching '{query}'."

    # Build a prose response
    results = []
    for mem in memories:
        if mem.similarity_score is not None:
            score_text = f" (similarity: {mem.similarity_score * 100:.1f}%)"
        else:
            score_text = ""  # No score for exact matches

        results.append(
            f"• {mem.age}{score_text} [ID: {mem.id}]: {mem.content[:200]}"
            + ("..." if len(mem.content) > 200 else "")
        )

    header = f"Found {len(memories)} memor{'ies' if len(memories) != 1 else 'y'} matching '{query}':"
    return header + "\n\n" + "\n\n".join(results)
