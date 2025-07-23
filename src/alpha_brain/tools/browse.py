"""Browse memories chronologically with flexible filtering."""

from typing import Literal

from fastmcp import Context
from pydantic import Field
from structlog import get_logger

from alpha_brain.memory_service import get_memory_service
from alpha_brain.templates import render_output

logger = get_logger()


async def browse(
    ctx: Context,
    interval: str = Field(..., description="Time interval to browse (e.g., 'today', 'yesterday', 'past week', '2025-07-20')"),
    entity: str | None = Field(None, description="Filter by canonical entity name"),
    text: str | None = Field(None, description="Full-text search within the interval"),
    exact: str | None = Field(None, description="Exact substring match (case-insensitive)"),
    keyword: str | None = Field(None, description="Filter by Helper-extracted keywords"),
    importance: int | None = Field(None, ge=1, le=5, description="Minimum importance level (1-5)"),
    limit: int = Field(20, ge=1, le=100, description="Maximum number of memories to return"),
    order: Literal["asc", "desc"] = Field("desc", description="Sort order: 'asc' for oldest first, 'desc' for newest first"),
) -> str:
    """
    Browse memories chronologically within a time interval.
    
    This tool provides a diary-like view of memories, showing them in chronological
    order within a specified time period. Unlike search which finds similar memories,
    browse lets you see the flow of events over time.
    
    Examples:
    - Browse today's memories: interval="today"
    - Browse last week with entity filter: interval="past week", entity="Jeffery Harrell"
    - Find exact phrases: interval="yesterday", exact="eat our own dogfood"
    - High-importance memories only: interval="past month", importance=4
    """
    try:
        service = get_memory_service()
        
        # For now, we'll use basic search parameters
        # TODO: Add exact_match, keyword, and min_importance support to memory_service
        if exact or keyword or importance:
            logger.warning(
                "browse_unsupported_filters",
                exact=exact,
                keyword=keyword,
                importance=importance,
                message="These filters are not yet implemented in memory service"
            )
        
        # Browse is essentially search without a query, but with interval required
        memories = await service.search(
            query=text,  # Full-text search if provided
            search_type="semantic",  # Not used when query is None
            limit=limit,
            offset=0,
            interval=interval,
            entity=entity,
            order=order,
        )
        
        # Render the output using the browse template
        return render_output(
            "browse",
            memories=memories,
            interval=interval,
            filters={
                "entity": entity,
                "text": text,
                "exact": exact,
                "keyword": keyword,
                "importance": importance,
            },
            limit=limit,
            order=order,
        )
        
    except ValueError as e:
        # Handle invalid interval format
        logger.warning("browse_invalid_interval", interval=interval, error=str(e))
        return render_output(
            "error",
            error_type="Invalid Interval",
            message=f"Could not parse interval '{interval}': {e!s}",
            suggestion="Try formats like 'today', 'yesterday', 'past week', or '2025-07-20'",
        )
    except Exception as e:
        logger.error("browse_failed", error=str(e), error_type=type(e).__name__)
        return render_output(
            "error",
            error_type="Browse Error",
            message=f"Failed to browse memories: {e!s}",
        )
