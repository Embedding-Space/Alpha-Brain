"""Search tool for finding memories."""

from alpha_brain.memory_service import get_memory_service


async def search(query: str, search_type: str = "semantic", limit: int = 10) -> str:
    """
    Search memories using various strategies.

    Args:
        query: The search query
        search_type: Type of search - 'semantic', 'emotional', 'both'
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
        similarity_pct = f"{mem.similarity_score * 100:.1f}%"
        results.append(
            f"• {mem.age} (similarity: {similarity_pct}): {mem.content[:200]}"
            + ("..." if len(mem.content) > 200 else "")
        )

    header = f"Found {len(memories)} memor{'ies' if len(memories) != 1 else 'y'} matching '{query}':"
    return header + "\n\n" + "\n\n".join(results)