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
        entities_text = ""
        if result.get("entities"):
            entities_text = (
                f" I noticed references to: {', '.join(result['entities'])}."
            )

        preview = result["preview"]
        if len(preview) > 100:
            preview = preview[:100] + "..."

        prose_result = (
            f'Stored memory: "{preview}"\n\n'
            f"Created at {result['timestamp']} (ID: {result['memory_id']}).{entities_text}"
        )
        logger.info("remember_tool_returning_prose", prose=prose_result)
        return prose_result
    
    error_result = f"Failed to store memory: {result.get('message', 'Unknown error')}"
    logger.info("remember_tool_returning_error", prose=error_result)
    return error_result