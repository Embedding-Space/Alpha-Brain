"""Entity management tool for name aliasing and canonicalization."""

from typing import Literal

from fastmcp import Context
from pydantic import Field
from sqlalchemy import func, select, update
from structlog import get_logger

from alpha_brain.database import get_db
from alpha_brain.schema import NameIndex
from alpha_brain.templates import render_output

logger = get_logger()


async def entity(  # noqa: PLR0911
    ctx: Context,
    operation: Literal["set-alias", "merge", "list", "show"],
    name: str | None = Field(None, description="The name to operate on"),
    canonical: str | None = Field(None, description="The canonical name (for set-alias)"),
    from_canonical: str | None = Field(None, description="Source canonical name (for merge)"),
    to_canonical: str | None = Field(None, description="Target canonical name (for merge)"),
) -> str:
    """
    Manage entity names and their canonical mappings.
    
    Operations:
    - set-alias: Create or update a name -> canonical mapping
    - merge: Change all names with one canonical to another canonical
    - list: Show all canonical names
    - show: Show all aliases for a specific name
    
    Examples:
    - entity --operation set-alias --name "PostgreSQL" --canonical "Postgres"
    - entity --operation merge --from-canonical "Jeffrey Harrell" --to-canonical "Jeffery Harrell"
    - entity --operation list
    - entity --operation show --name "Postgres"
    """
    try:
        if operation == "set-alias":
            if not name or not canonical:
                return render_output(
                    "error",
                    error_type="Missing Parameters",
                    message="set-alias requires both 'name' and 'canonical' parameters",
                )
            return await set_alias(name, canonical)
            
        if operation == "merge":
            if not from_canonical or not to_canonical:
                return render_output(
                    "error",
                    error_type="Missing Parameters", 
                    message="merge requires both 'from_canonical' and 'to_canonical' parameters",
                )
            return await merge_entities(from_canonical, to_canonical)
            
        if operation == "list":
            return await list_entities()
            
        if operation == "show":
            if not name:
                return render_output(
                    "error",
                    error_type="Missing Parameter",
                    message="show requires 'name' parameter",
                )
            return await show_entity(name)
            
        return render_output(
            "error",
            error_type="Invalid Operation",
            message=f"Unknown operation: {operation}",
        )
            
    except Exception as e:
        logger.error("entity_operation_failed", operation=operation, error=str(e))
        return render_output(
            "error",
            error_type="Operation Failed",
            message=f"Entity operation failed: {e!s}",
        )


async def set_alias(name: str, canonical: str) -> str:
    """Create or update a name -> canonical mapping."""
    async with get_db() as session:
        # Check if name already exists
        stmt = select(NameIndex).where(NameIndex.name == name)
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()
        
        if existing:
            # Update existing
            existing.canonical_name = canonical
            await session.commit()
            
            return render_output(
                "entity_alias",
                operation="updated",
                name=name,
                canonical=canonical,
                message=f"Updated '{name}' to map to '{canonical}'",
            )
        # Create new
        entry = NameIndex(name=name, canonical_name=canonical)
        session.add(entry)
        
        # Also ensure canonical points to itself
        if name != canonical:
            # Check if canonical exists
            stmt = select(NameIndex).where(NameIndex.name == canonical)
            result = await session.execute(stmt)
            canonical_entry = result.scalar_one_or_none()
            
            if not canonical_entry:
                # Create self-referential entry
                canonical_entry = NameIndex(name=canonical, canonical_name=canonical)
                session.add(canonical_entry)
        
        await session.commit()
        
        return render_output(
            "entity_alias",
            operation="created",
            name=name,
            canonical=canonical,
            message=f"Created alias '{name}' → '{canonical}'",
        )


async def merge_entities(from_canonical: str, to_canonical: str) -> str:
    """Change all names with from_canonical to use to_canonical."""
    async with get_db() as session:
        # Update all entries
        stmt = (
            update(NameIndex)
            .where(NameIndex.canonical_name == from_canonical)
            .values(canonical_name=to_canonical)
        )
        result = await session.execute(stmt)
        await session.commit()
        
        count = result.rowcount
        
        return render_output(
            "entity_merge", 
            from_canonical=from_canonical,
            to_canonical=to_canonical,
            count=count,
            message=f"Merged {count} names from '{from_canonical}' to '{to_canonical}'",
        )


async def list_entities() -> str:
    """List all canonical names."""
    async with get_db() as session:
        # Get distinct canonical names with counts
        stmt = (
            select(
                NameIndex.canonical_name,
                func.count(NameIndex.id).label("alias_count")
            )
            .group_by(NameIndex.canonical_name)
            .order_by(NameIndex.canonical_name)
        )
        result = await session.execute(stmt)
        entities = result.all()
        
        return render_output(
            "entity_list",
            entities=[
                {
                    "canonical_name": canonical,
                    "alias_count": count
                }
                for canonical, count in entities
            ],
            total=len(entities),
        )


async def show_entity(name: str) -> str:
    """Show all aliases for a specific name."""
    async with get_db() as session:
        # First find what canonical this name maps to
        stmt = select(NameIndex).where(NameIndex.name == name)
        result = await session.execute(stmt)
        entry = result.scalar_one_or_none()
        
        if not entry:
            return render_output(
                "entity_show",
                name=name,
                found=False,
                message=f"No entity found for '{name}'",
            )
        
        canonical = entry.canonical_name
        
        # Now get all names that map to this canonical
        stmt = (
            select(NameIndex.name)
            .where(NameIndex.canonical_name == canonical)
            .order_by(NameIndex.name)
        )
        result = await session.execute(stmt)
        all_names = [row[0] for row in result.all()]
        
        # Separate canonical from aliases
        aliases = [n for n in all_names if n != canonical]
        
        return render_output(
            "entity_show",
            name=name,
            found=True,
            canonical=canonical,
            aliases=aliases,
            is_canonical=(name == canonical),
        )
