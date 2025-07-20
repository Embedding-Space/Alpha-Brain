"""Remember tool for storing memories."""

from alpha_brain.memory_service import get_memory_service
from alpha_brain.templates import render_output


async def remember(content: str) -> str:
    """Remember a piece of information as prose."""
    import structlog

    logger = structlog.get_logger()

    service = get_memory_service()
    result = await service.remember(content)
    logger.info("remember_tool_got_result", result=result)

    if result["status"] == "stored":
        preview = result["preview"]
        if len(preview) > 100:
            preview = preview[:100] + "..."

        # Build context for template
        metadata = result.get("metadata", {})
        context = {
            "preview": preview,
            "timestamp": result["timestamp"],
            "memory_id": result["memory_id"],
            "summary": metadata.get("summary", ""),
            "splash": result.get("splash", ""),
            "splash_analysis": result.get(
                "splash_analysis"
            ),  # Pass the raw analysis object
        }

        prose_result = render_output("remember", **context)
        logger.info("remember_tool_returning_prose", prose=prose_result)
        return prose_result

    error_result = f"Failed to store memory: {result.get('message', 'Unknown error')}"
    logger.info("remember_tool_returning_error", prose=error_result)
    return error_result
