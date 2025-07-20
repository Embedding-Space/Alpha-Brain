"""Service for managing knowledge documents."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from alpha_brain.markdown_parser import parse_markdown_to_structure
from alpha_brain.schema import Knowledge, KnowledgeInput, KnowledgeOutput

logger = structlog.get_logger()


class KnowledgeService:
    """Service for managing structured knowledge documents."""

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def create(self, knowledge_input: KnowledgeInput) -> KnowledgeOutput:
        """Create a new knowledge document.

        Args:
            knowledge_input: The knowledge data to store

        Returns:
            The created knowledge document

        Raises:
            ValueError: If slug already exists
        """
        # Check if slug already exists
        existing = await self.get_by_slug(knowledge_input.slug)
        if existing:
            raise ValueError(
                f"Knowledge document with slug '{knowledge_input.slug}' already exists"
            )

        # Parse the Markdown content into structure
        structure = parse_markdown_to_structure(knowledge_input.content)

        # Create knowledge record
        knowledge = Knowledge(
            slug=knowledge_input.slug,
            title=knowledge_input.title,
            content=knowledge_input.content,
            structure=structure,
            created_at=datetime.now(tz=UTC),
            updated_at=datetime.now(tz=UTC),
        )

        self.db.add(knowledge)
        await self.db.commit()
        await self.db.refresh(knowledge)

        logger.info(
            "knowledge_created",
            knowledge_id=str(knowledge.id),
            slug=knowledge.slug,
            sections=len(structure.get("sections", [])),
        )

        return KnowledgeOutput(
            id=knowledge.id,
            slug=knowledge.slug,
            title=knowledge.title,
            content=knowledge.content,
            structure=knowledge.structure,
            created_at=knowledge.created_at,
            updated_at=knowledge.updated_at,
        )

    async def get_by_id(self, knowledge_id: UUID) -> KnowledgeOutput | None:
        """Get a knowledge document by ID.

        Args:
            knowledge_id: The UUID of the knowledge document

        Returns:
            The knowledge document if found, None otherwise
        """
        result = await self.db.execute(
            select(Knowledge).where(Knowledge.id == knowledge_id)
        )
        knowledge = result.scalar_one_or_none()

        if not knowledge:
            return None

        return KnowledgeOutput(
            id=knowledge.id,
            slug=knowledge.slug,
            title=knowledge.title,
            content=knowledge.content,
            structure=knowledge.structure,
            created_at=knowledge.created_at,
            updated_at=knowledge.updated_at,
        )

    async def get_by_slug(self, slug: str) -> KnowledgeOutput | None:
        """Get a knowledge document by slug.

        Args:
            slug: The slug identifier

        Returns:
            The knowledge document if found, None otherwise
        """
        result = await self.db.execute(select(Knowledge).where(Knowledge.slug == slug))
        knowledge = result.scalar_one_or_none()

        if not knowledge:
            return None

        return KnowledgeOutput(
            id=knowledge.id,
            slug=knowledge.slug,
            title=knowledge.title,
            content=knowledge.content,
            structure=knowledge.structure,
            created_at=knowledge.created_at,
            updated_at=knowledge.updated_at,
        )

    async def update(
        self, slug: str, knowledge_input: KnowledgeInput
    ) -> KnowledgeOutput | None:
        """Update an existing knowledge document.

        Args:
            slug: The slug of the document to update
            knowledge_input: The new knowledge data

        Returns:
            The updated knowledge document if found, None otherwise
        """
        # Get existing document
        result = await self.db.execute(select(Knowledge).where(Knowledge.slug == slug))
        knowledge = result.scalar_one_or_none()

        if not knowledge:
            return None

        # Parse new structure
        structure = parse_markdown_to_structure(knowledge_input.content)

        # Update fields
        knowledge.title = knowledge_input.title
        knowledge.content = knowledge_input.content
        knowledge.structure = structure
        knowledge.updated_at = datetime.now(tz=UTC)

        # If slug is changing, check it doesn't already exist
        if knowledge_input.slug != slug:
            existing = await self.get_by_slug(knowledge_input.slug)
            if existing:
                raise ValueError(
                    f"Knowledge document with slug '{knowledge_input.slug}' already exists"
                )
            knowledge.slug = knowledge_input.slug

        await self.db.commit()
        await self.db.refresh(knowledge)

        logger.info(
            "knowledge_updated",
            knowledge_id=str(knowledge.id),
            slug=knowledge.slug,
            old_slug=slug if slug != knowledge.slug else None,
        )

        return KnowledgeOutput(
            id=knowledge.id,
            slug=knowledge.slug,
            title=knowledge.title,
            content=knowledge.content,
            structure=knowledge.structure,
            created_at=knowledge.created_at,
            updated_at=knowledge.updated_at,
        )

    async def delete(self, slug: str) -> bool:
        """Delete a knowledge document.

        Args:
            slug: The slug of the document to delete

        Returns:
            True if deleted, False if not found
        """
        result = await self.db.execute(select(Knowledge).where(Knowledge.slug == slug))
        knowledge = result.scalar_one_or_none()

        if not knowledge:
            return False

        await self.db.delete(knowledge)
        await self.db.commit()

        logger.info("knowledge_deleted", knowledge_id=str(knowledge.id), slug=slug)

        return True

    async def list_all(
        self, limit: int = 100, offset: int = 0
    ) -> list[KnowledgeOutput]:
        """List all knowledge documents.

        Args:
            limit: Maximum number of documents to return
            offset: Number of documents to skip

        Returns:
            List of knowledge documents
        """
        result = await self.db.execute(
            select(Knowledge)
            .order_by(Knowledge.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        knowledge_list = result.scalars().all()

        return [
            KnowledgeOutput(
                id=k.id,
                slug=k.slug,
                title=k.title,
                content=k.content,
                structure=k.structure,
                created_at=k.created_at,
                updated_at=k.updated_at,
            )
            for k in knowledge_list
        ]
