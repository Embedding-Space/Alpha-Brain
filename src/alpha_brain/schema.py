"""Schema for the unified memory and knowledge system."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from pydantic import BaseModel, Field
from sqlalchemy import ARRAY, Column, DateTime, Interval, String, Text, func, or_
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Memory(Base):
    """A single memory - fundamentally just prose with metadata."""

    __tablename__ = "memories"

    # Core identity
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)

    # The actual memory content - this is the star of the show
    content = Column(Text, nullable=False)

    # Temporal context
    created_at = Column(DateTime, nullable=False)

    # Embeddings for search using pgvector
    semantic_embedding = Column(Vector(768))  # all-mpnet-base-v2 dimensions
    emotional_embedding = Column(
        Vector(7)
    )  # 7D emotion vector: anger, disgust, fear, joy, neutral, sadness, surprise

    # Marginalia - Helper's annotations and glosses added to memories
    marginalia = Column(JSONB, default={})

    # For future TTL support if we want ephemeral memories
    expires_at = Column(DateTime, nullable=True)


class MemoryInput(BaseModel):
    """Input model for creating a memory."""

    content: str = Field(..., description="The prose content to remember")
    marginalia: dict[str, Any] = Field(
        default_factory=dict,
        description="Helper's annotations: entities, categories, and other glosses",
    )


class MemoryOutput(BaseModel):
    """Output model for retrieved memories."""

    id: UUID
    content: str
    created_at: datetime
    similarity_score: float | None = Field(
        None, description="Similarity score if from a search"
    )
    marginalia: dict[str, Any] = {}

    # Human-readable age
    age: str | None = Field(None, description="Human-readable age like '5 minutes ago'")


class NaturalQuery(BaseModel):
    """A natural language query about memories."""

    question: str = Field(
        ..., description="Natural language question like 'Does Jeffery like peas?'"
    )
    search_type: str = Field(
        default="auto", description="Type of search: 'semantic', 'emotional', 'auto'"
    )
    limit: int = Field(default=10, ge=1, le=100)


class NaturalAnswer(BaseModel):
    """A natural language answer synthesized from memories."""

    answer: str = Field(..., description="Natural language answer to the question")
    confidence: float = Field(..., description="Confidence score 0-1")
    supporting_memories: list[MemoryOutput] = Field(
        default_factory=list, description="Memories that informed this answer"
    )
    reasoning: str | None = Field(
        None, description="Optional explanation of how the answer was derived"
    )


class Knowledge(Base):
    """Structured knowledge document stored as parsed Markdown."""

    __tablename__ = "knowledge"

    # Core identity
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    slug = Column(String, nullable=False, unique=True, index=True)

    # Document content
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)  # Raw Markdown
    structure = Column(JSONB, nullable=False)  # Parsed structure

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class KnowledgeInput(BaseModel):
    """Input model for creating/updating knowledge."""

    slug: str = Field(..., description="URL-friendly identifier")
    title: str = Field(..., description="Document title")
    content: str = Field(..., description="Markdown content")


class KnowledgeOutput(BaseModel):
    """Output model for retrieved knowledge."""

    id: UUID
    slug: str
    title: str
    content: str
    structure: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class Entity(Base):
    """Canonical entity names with their aliases for normalization."""

    __tablename__ = "entities"

    # Use canonical name as primary key - it's unique and meaningful
    canonical_name = Column(String, primary_key=True)

    # Array of aliases that resolve to this canonical name
    aliases = Column(ARRAY(String), nullable=False, default=[])

    # Timestamps for tracking
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class EntityInput(BaseModel):
    """Input model for creating/updating entities."""

    canonical: str = Field(..., description="The canonical name")
    aliases: list[str] = Field(
        default_factory=list,
        description="List of aliases that map to this canonical name",
    )


class EntityBatch(BaseModel):
    """Batch of entities for import."""

    version: str = Field(..., description="Schema version")
    entities: list[EntityInput] = Field(..., description="List of entities to import")


class Context(Base):
    """Context blocks for identity and state management."""
    
    __tablename__ = "context"
    
    section = Column(String, primary_key=True)
    content = Column(Text, nullable=False)
    ttl = Column(Interval)  # How long this should live
    expires_at = Column(DateTime, nullable=True)  # When it expires
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    
    @hybrid_property
    def is_active(self):
        """Check if this context block is currently active."""
        if self.expires_at is None:
            return True
        return self.expires_at > datetime.now(UTC)
    
    @is_active.expression
    def is_active(cls):  # noqa: N805
        """SQL expression for filtering active contexts."""
        return or_(cls.expires_at.is_(None), cls.expires_at > func.now())
