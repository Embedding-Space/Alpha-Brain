"""Remember tool for storing memories."""

from alpha_brain.memory_service import get_memory_service


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

        # Build a more informative response using metadata
        metadata = result.get("metadata", {})
        summary = metadata.get("summary", "")

        prose_result = (
            f'Stored memory: "{preview}"\n\n'
            f"Created at {result['timestamp']} (ID: {result['memory_id']})."
        )

        if summary:
            prose_result += f"\n\nSummary: {summary}"

        logger.info("remember_tool_returning_prose", prose=prose_result)
        return prose_result

    error_result = f"Failed to store memory: {result.get('message', 'Unknown error')}"
    logger.info("remember_tool_returning_error", prose=error_result)
    return error_result
