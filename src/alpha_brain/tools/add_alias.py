"""Add alias tool for entity management."""

from alpha_brain.entity_service import get_entity_service
from alpha_brain.templates import render_output


async def add_alias(canonical_name: str, alias: str) -> str:
    """
    Add an alias to an entity, creating the entity if it doesn't exist.
    
    Args:
        canonical_name: The canonical form of the entity name
        alias: The alias to add (can be the same as canonical_name)
    
    Returns:
        Prose description of the operation result
    """
    entity_service = get_entity_service()
    
    # First check if the canonical name already exists
    existing = await entity_service.get_canonical_name(canonical_name)
    
    if existing:
        # Entity exists, need to add the alias
        # For now, we'll need to add an update method to EntityService
        # Let's check if the alias is already there
        if await entity_service.get_canonical_name(alias) == canonical_name:
            # Alias already points to this canonical name
            return render_output(
                "add_alias",
                canonical_name=canonical_name,
                alias=alias,
                status="already_exists",
                message=f"'{alias}' is already an alias for '{canonical_name}'"
            )
        
        # Need to update the entity with new alias
        # We'll need to implement this in EntityService
        await entity_service.add_alias_to_entity(canonical_name, alias)
        
        return render_output(
            "add_alias",
            canonical_name=canonical_name,
            alias=alias,
            status="alias_added",
            message=f"Added '{alias}' as an alias for '{canonical_name}'"
        )
    # Entity doesn't exist, create it with the alias
    aliases = [alias] if alias != canonical_name else []
    await entity_service.add_entity(canonical_name, aliases)
    
    return render_output(
        "add_alias",
        canonical_name=canonical_name,
        alias=alias,
        status="entity_created",
        message=f"Created entity '{canonical_name}'" + (f" with alias '{alias}'" if aliases else "")
    )
