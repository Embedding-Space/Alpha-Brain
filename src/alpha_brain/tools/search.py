"""Search tool for finding memories."""

from alpha_brain.memory_service import get_memory_service
from alpha_brain.templates import render_output


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

    return render_output(
        "search", query=query, search_type=search_type, memories=memories
    )
