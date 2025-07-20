"""Get a specific memory by ID."""

from uuid import UUID

from alpha_brain.memory_service import get_memory_service


async def get_memory(memory_id: str) -> str:
    """
    Retrieve a complete memory by its ID.

    Args:
        memory_id: The UUID of the memory to retrieve

    Returns:
        Prose description of the memory with all metadata
    """
    service = get_memory_service()

    try:
        # Validate UUID format
        uuid_obj = UUID(memory_id)
    except ValueError:
        return f"Invalid memory ID format: '{memory_id}'. Please provide a valid UUID."

    # Get the memory from the database
    memory = await service.get_by_id(uuid_obj)

    if not memory:
        return f"No memory found with ID: {memory_id}"

    # Build a comprehensive prose response
    result = f"Memory ID: {memory.id}\n"
    result += f"Created: {memory.created_at.isoformat()} ({memory.age})\n"
    result += "\n"
    result += f"Content:\n{memory.content}\n"

    # Include marginalia if available
    if memory.marginalia:
        result += "\n--- Marginalia ---\n"

        # Extract key marginalia fields
        summary = memory.marginalia.get("summary", "")
        if summary:
            result += f"Summary: {summary}\n"

        importance = memory.marginalia.get("importance", None)
        if importance is not None:
            result += f"Importance: {importance}/5\n"

        entities = memory.marginalia.get("entities", [])
        if entities:
            result += f"Entities: {', '.join(entities)}\n"

        unknown_entities = memory.marginalia.get("unknown_entities", [])
        if unknown_entities:
            result += f"Unknown entities: {', '.join(unknown_entities)}\n"

        keywords = memory.marginalia.get("keywords", [])
        if keywords:
            result += f"Keywords: {', '.join(keywords)}\n"

        # Show analyzed_at if available
        analyzed_at = memory.marginalia.get("analyzed_at", "")
        if analyzed_at:
            result += f"\nAnalyzed at: {analyzed_at}\n"

    return result
