"""Schema for the unified memory and knowledge system."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from pydantic import BaseModel, Field
from sqlalchemy import JSON, Column, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
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
        Vector(1024)
    )  # ng3owb/sentiment-embedding-model dimensions

    # Extra data - flexible JSON field for future expansion
    extra_data = Column(JSON, default={})

    # Optional: extracted entities (can be None if we skip extraction)
    entities = Column(JSON)  # List of entity names mentioned

    # For future TTL support if we want ephemeral memories
    expires_at = Column(DateTime, nullable=True)


class MemoryInput(BaseModel):
    """Input model for creating a memory."""

    content: str = Field(..., description="The prose content to remember")
    extra_data: dict[str, Any] = Field(
        default_factory=dict, description="Optional extra data about this memory"
    )


class MemoryOutput(BaseModel):
    """Output model for retrieved memories."""

    id: UUID
    content: str
    created_at: datetime
    similarity_score: float | None = Field(
        None, description="Similarity score if from a search"
    )
    extra_data: dict[str, Any] = {}

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
