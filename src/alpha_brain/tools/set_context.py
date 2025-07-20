"""Set context blocks for identity and state management."""

from alpha_brain.context_service import get_context_service


async def set_context(
    section: str,
    content: str,
    ttl: str | None = None
) -> str:
    """
    Set or update a context block.
    
    System sections (biography, continuity) cannot have TTL and persist forever.
    Other sections can have optional TTL like "3d", "1h", "30m".
    
    Args:
        section: Section name (e.g., "biography", "current_project", "experiment_x")
        content: Markdown content (empty string clears the section)
        ttl: Optional time-to-live (e.g., "3d", "1h") - not allowed for system sections
        
    Returns:
        Confirmation of the operation
    """
    service = get_context_service()
    
    try:
        result = await service.set_context(section, content, ttl)
        
        if result["operation"] == "created":
            if result["expires_at"]:
                return f"Created context section '{section}' (expires {result['expires_at']})"
            return f"Created context section '{section}'"
        if result["expires_at"]:
            return f"Updated context section '{section}' (expires {result['expires_at']})"
        return f"Updated context section '{section}'"
                
    except ValueError as e:
        return f"Error: {e}"
