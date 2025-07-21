"""Entity service for canonical name resolution."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select, text
from structlog import get_logger

from alpha_brain.database import get_db
from alpha_brain.schema import Entity

logger = get_logger()


class EntityService:
    """Service for managing canonical entities and their aliases."""

    async def get_canonical_name(self, name: str) -> str | None:
        """
        Look up the canonical name for a given name or alias.

        Args:
            name: The name to canonicalize

        Returns:
            The canonical name if found, None otherwise
        """
        async with get_db() as session:
            # First check if it's already a canonical name
            stmt = select(Entity.canonical_name).where(Entity.canonical_name == name)
            result = await session.execute(stmt)
            if result.scalar_one_or_none():
                return name

            # Then check if it's an alias using PostgreSQL ANY operator
            stmt = select(Entity.canonical_name).where(
                text(":name = ANY(aliases)").bindparams(name=name)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def canonicalize_names(self, names: list[str]) -> dict[str, Any]:
        """
        Canonicalize a list of names, returning canonical forms and unknowns.

        Args:
            names: List of names to canonicalize

        Returns:
            Dict with 'canonical' list and 'unknown' list
        """
        canonical_names = []
        unknown_names = []

        for name in names:
            canonical = await self.get_canonical_name(name)
            if canonical:
                canonical_names.append(canonical)
            else:
                unknown_names.append(name)

        # Deduplicate canonical names
        canonical_names = list(set(canonical_names))

        return {"entities": canonical_names, "unknown_entities": unknown_names}
    
    async def canonicalize_names_with_ids(self, names: list[str]) -> dict[str, Any]:
        """
        Canonicalize a list of names, returning canonical forms with IDs and unknowns.

        Args:
            names: List of names to canonicalize

        Returns:
            Dict with 'entities' list (containing dicts with 'id' and 'name'), 
            'entity_ids' list, and 'unknown_entities' list
        """
        entities = []
        entity_ids = []
        unknown_names = []
        seen_ids = set()  # Track seen IDs to avoid duplicates

        async with get_db() as session:
            for name in names:
                # First check if it's already a canonical name
                stmt = select(Entity.id, Entity.canonical_name).where(
                    Entity.canonical_name == name
                )
                result = await session.execute(stmt)
                row = result.fetchone()
                
                if not row:
                    # Then check if it's an alias
                    stmt = select(Entity.id, Entity.canonical_name).where(
                        text(":name = ANY(aliases)").bindparams(name=name)
                    )
                    result = await session.execute(stmt)
                    row = result.fetchone()
                
                if row and row.id not in seen_ids:
                    entities.append({"id": row.id, "name": row.canonical_name})
                    entity_ids.append(row.id)
                    seen_ids.add(row.id)
                elif not row:
                    unknown_names.append(name)

        return {
            "entities": entities, 
            "entity_ids": entity_ids,
            "unknown_entities": unknown_names
        }

    async def add_entity(self, canonical_name: str, aliases: list[str]) -> None:
        """
        Add a new entity with its aliases.

        Args:
            canonical_name: The canonical form of the entity
            aliases: List of aliases that map to this canonical name
        """
        async with get_db() as session:
            entity = Entity(canonical_name=canonical_name, aliases=aliases)
            session.add(entity)
            await session.commit()

            logger.info(
                "Entity added", canonical=canonical_name, alias_count=len(aliases)
            )

    async def add_alias_to_entity(self, canonical_name: str, alias: str) -> None:
        """
        Add an alias to an existing entity.
        
        Args:
            canonical_name: The canonical form of the entity
            alias: The new alias to add
        """
        async with get_db() as session:
            # Fetch the entity
            stmt = select(Entity).where(Entity.canonical_name == canonical_name)
            result = await session.execute(stmt)
            entity = result.scalar_one_or_none()
            
            if not entity:
                raise ValueError(f"Entity '{canonical_name}' not found")
            
            # Add alias if not already present
            if alias not in entity.aliases:
                entity.aliases = [*entity.aliases, alias]
                await session.commit()
                
                logger.info(
                    "Alias added", 
                    canonical=canonical_name, 
                    alias=alias,
                    total_aliases=len(entity.aliases)
                )
            else:
                logger.info(
                    "Alias already exists", 
                    canonical=canonical_name, 
                    alias=alias
                )
    
    async def import_entities(self, entities: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Import multiple entities from a batch.

        Args:
            entities: List of entity dicts with 'canonical' and 'aliases'

        Returns:
            Import results with counts
        """
        imported = 0
        skipped = 0
        errors = []

        for entity_data in entities:
            try:
                canonical = entity_data["canonical"]
                aliases = entity_data.get("aliases", [])

                # Check if entity already exists
                existing = await self.get_canonical_name(canonical)
                if existing:
                    skipped += 1
                    logger.info("Entity already exists", canonical=canonical)
                    continue

                await self.add_entity(canonical, aliases)
                imported += 1

            except Exception as e:
                errors.append(f"Failed to import {entity_data}: {e!s}")
                logger.error("Entity import failed", entity=entity_data, error=str(e))

        return {"imported": imported, "skipped": skipped, "errors": errors}


# Global instance
_entity_service = None


def get_entity_service() -> EntityService:
    """Get the global entity service instance."""
    global _entity_service
    if _entity_service is None:
        _entity_service = EntityService()
    return _entity_service
