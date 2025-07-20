"""Search tool for finding memories."""

from fastmcp import Context

from alpha_brain.memory_service import get_memory_service
from alpha_brain.templates import render_output


async def search(
    ctx: Context,
    query: str | None = None,
    mode: str = "semantic", 
    interval: str | None = None,
    entity: str | None = None,
    order: str = "auto",
    limit: int = 10,
    offset: int = 0
) -> str:
    """
    Search or browse memories with flexible filtering options.

    Args:
        query: Search query text. If omitted or empty, browse mode is activated.
        mode: Search mode - 'semantic', 'emotional', 'both', or 'exact' (ignored in browse mode)
        interval: Time interval to filter by (e.g., "yesterday", "past 3 hours", "2024-01-01/2024-01-31")
        entity: Filter by entity name (will be canonicalized)
        order: Sort order - 'asc' (oldest first), 'desc' (newest first), 'auto' (smart default)
        limit: Maximum results to return (default 10)
        offset: Number of results to skip for pagination (default 0)

    Returns:
        Prose description of matching memories
    """
    await ctx.debug(f"Search parameters: query={query!r}, mode={mode}, interval={interval!r}, entity={entity!r}, order={order}, limit={limit}, offset={offset}")
    
    service = get_memory_service()
    
    # Determine if we're in browse mode
    is_browsing = not query or query in ["", "*", "%"]
    await ctx.debug(f"Browse mode: {is_browsing}")
    
    if interval:
        try:
            from alpha_brain.interval_parser import parse_interval
            start_dt, end_dt = parse_interval(interval)
            await ctx.info(f"Parsed interval '{interval}' → {start_dt.format('MM/DD HH:mm')} to {end_dt.format('MM/DD HH:mm')} (local time boundaries)")
        except Exception as e:
            await ctx.error(f"Failed to parse interval '{interval}': {e}")
            # Pass through the detailed error message from the interval parser
            return str(e)
    
    if is_browsing and not interval:
        await ctx.warning("Browse mode requires a time interval")
        return "Please specify a time interval when browsing memories."
    
    # Call the updated search method
    await ctx.debug("Calling memory service search...")
    try:
        memories = await service.search(
            query=query,
            search_type=mode,  # Tool uses 'mode', service expects 'search_type'
            limit=limit,
            offset=offset,
            interval=interval,
            entity=entity,
            order=order
        )
        await ctx.info(f"Found {len(memories)} memories")
    except Exception as e:
        await ctx.error(f"Search failed: {e}")
        raise
    
    if not memories:
        if is_browsing:
            return render_output(
                "search", 
                query=None, 
                search_type=None, 
                memories=[],
                is_browsing=True,
                interval=interval
            )
        return f"No memories found matching '{query}'."

    return render_output(
        "search", 
        query=query, 
        search_type=mode, 
        memories=memories,
        is_browsing=is_browsing,
        interval=interval,
        entity=entity,
        order=order,
        offset=offset,
        limit=limit
    )
