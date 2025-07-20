"""Get a specific memory by ID."""

from uuid import UUID

from alpha_brain.memory_service import get_memory_service
from alpha_brain.templates import render_output


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

    # Use template to render output
    return render_output("get_memory", memory=memory)
