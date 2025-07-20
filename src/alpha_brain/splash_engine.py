"""The Splash Engine - Identity reinforcement through associative recollection.

Context reinforcement and contradiction detection through asymmetric similarity search.
When you store a memory, discover what you already know about similar topics AND
surface potential contradictions for reconciliation.

This is our killer feature - nobody else is doing this.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from uuid import UUID

import numpy as np
from sqlalchemy import select
from structlog import get_logger

from alpha_brain.database import get_db
from alpha_brain.embeddings import get_embedding_service
from alpha_brain.schema import Memory
from alpha_brain.time_service import TimeService

logger = get_logger()


@dataclass
class SplashResult:
    """A single splash result with rich metadata."""

    memory_id: UUID
    content: str
    preview: str  # First 100 chars or so
    similarity_score: float
    relationship_type: str  # "similar", "contrasting", "evolving"
    age: str
    created_at: str


@dataclass
class SplashAnalysis:
    """Complete splash analysis for a memory."""

    most_similar: list[SplashResult]
    least_similar: list[SplashResult]
    total_analyzed: int
    analysis_time_ms: float
    mode: str = "semantic"  # Track which mode was used


class SplashEngine:
    """The Splash Engine - our killer feature for memory analysis.

    Provides asymmetric similarity search that surfaces both reinforcing
    and contradicting memories to help with identity formation and
    contradiction resolution.
    """

    def __init__(self, embedding_service=None):
        """Initialize the Splash Engine."""
        self.embedding_service = embedding_service or get_embedding_service()

    async def generate_splash(
        self,
        query_semantic_embedding: np.ndarray,
        query_emotional_embedding: np.ndarray | None = None,
        exclude_memory_id: UUID | None = None,
        count: int = 5,
        mode: str = "semantic",  # "semantic" or "emotional"
    ) -> SplashAnalysis:
        """
        Generate splash analysis showing highest and lowest similarities.

        Args:
            query_semantic_embedding: The semantic embedding to search against
            query_emotional_embedding: The emotional embedding (required if mode="emotional")
            exclude_memory_id: Memory ID to exclude (usually the one just stored)
            count: Number of most similar and least similar memories to return
            mode: "semantic" for topic similarity or "emotional" for emotional resonance

        Returns:
            Splash analysis with most and least similar memories
        """
        start_time = asyncio.get_event_loop().time()

        async with get_db() as session:
            # Choose which embedding to query based on mode
            if mode == "emotional":
                if query_emotional_embedding is None:
                    raise ValueError("Emotional embedding required for emotional mode")

                stmt = select(
                    Memory.id,
                    Memory.content,
                    Memory.created_at,
                    Memory.emotional_embedding,
                ).where(Memory.emotional_embedding.is_not(None))
            else:
                # Default to semantic
                stmt = select(
                    Memory.id,
                    Memory.content,
                    Memory.created_at,
                    Memory.semantic_embedding,
                ).where(Memory.semantic_embedding.is_not(None))

            if exclude_memory_id:
                stmt = stmt.where(Memory.id != exclude_memory_id)

            result = await session.execute(stmt)
            rows = result.fetchall()

            if not rows:
                logger.info("No memories found for splash analysis")
                return SplashAnalysis(
                    most_similar=[],
                    least_similar=[],
                    total_analyzed=0,
                    analysis_time_ms=0.0,
                )

            # Calculate similarities for all memories
            memory_data = []
            for row in rows:
                if mode == "emotional":
                    embedding = np.array(row.emotional_embedding)
                    similarity = self._cosine_similarity(
                        query_emotional_embedding, embedding
                    )
                else:
                    embedding = np.array(row.semantic_embedding)
                    similarity = self._cosine_similarity(
                        query_semantic_embedding, embedding
                    )

                memory_data.append(
                    {
                        "memory_id": row.id,
                        "content": row.content,
                        "created_at": row.created_at,
                        "similarity": similarity,
                    }
                )

            # Sort by similarity (highest first)
            memory_data.sort(key=lambda x: x["similarity"], reverse=True)

            # Get most similar (highest scores)
            most_similar = []
            for item in memory_data[:count]:
                splash_result = self._create_splash_result(
                    item, "most_similar", item["similarity"]
                )
                most_similar.append(splash_result)

            # Get least similar (lowest scores)
            least_similar = []
            for item in memory_data[-count:]:
                splash_result = self._create_splash_result(
                    item, "least_similar", item["similarity"]
                )
                least_similar.append(splash_result)

            # Sort least similar by ascending similarity (least similar first)
            least_similar.sort(key=lambda x: x.similarity_score)

            end_time = asyncio.get_event_loop().time()
            analysis_time_ms = (end_time - start_time) * 1000

            logger.info(
                "Simplified splash analysis complete",
                total_memories=len(rows),
                most_similar_count=len(most_similar),
                least_similar_count=len(least_similar),
                analysis_time_ms=analysis_time_ms,
            )

            return SplashAnalysis(
                most_similar=most_similar,
                least_similar=least_similar,
                total_analyzed=len(rows),
                analysis_time_ms=analysis_time_ms,
                mode=mode,
            )

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors."""
        # Ensure vectors are normalized
        a_norm = a / np.linalg.norm(a)
        b_norm = b / np.linalg.norm(b)

        # Cosine similarity
        return float(np.dot(a_norm, b_norm))

    def _create_splash_result(
        self, item: dict, relationship_type: str, similarity_score: float
    ) -> SplashResult:
        """Create a SplashResult from memory data."""
        content = item["content"]
        preview = content[:100] + "..." if len(content) > 100 else content

        return SplashResult(
            memory_id=item["memory_id"],
            content=content,
            preview=preview,
            similarity_score=similarity_score,
            relationship_type=relationship_type,
            age=TimeService.format_age(item["created_at"]),
            created_at=TimeService.format_readable(item["created_at"]),
        )

    def format_splash_output(self, analysis: SplashAnalysis) -> str:
        """Format simplified splash analysis into beautiful markdown output."""
        total_memories = len(analysis.most_similar) + len(analysis.least_similar)

        if total_memories == 0:
            return "\n🌊 **Splash Analysis**: No related memories found (first memory?)"

        # Use the mode from the analysis
        mode_display = (
            "Emotional resonance"
            if analysis.mode == "emotional"
            else "Semantic similarity"
        )
        lines = [f"\n🌊 **Splash Analysis** - {mode_display} distribution"]

        if analysis.most_similar:
            lines.append(f"\n🔗 **{len(analysis.most_similar)} Most Similar**")
            for memory in analysis.most_similar:
                similarity_pct = int(memory.similarity_score * 100)
                lines.append(
                    f"• `{str(memory.memory_id)[:8]}` | {memory.age} | "
                    f"{similarity_pct}% similar\n"
                    f'  "{memory.preview}"'
                )

        if analysis.least_similar:
            lines.append(f"\n⚡ **{len(analysis.least_similar)} Least Similar**")
            for memory in analysis.least_similar:
                similarity_pct = int(memory.similarity_score * 100)
                # Handle negative similarities gracefully
                if similarity_pct < 0:
                    lines.append(
                        f"• `{str(memory.memory_id)[:8]}` | {memory.age} | "
                        f"{similarity_pct}% similar (negative)\n"
                        f'  "{memory.preview}"'
                    )
                else:
                    lines.append(
                        f"• `{str(memory.memory_id)[:8]}` | {memory.age} | "
                        f"{similarity_pct}% similar\n"
                        f'  "{memory.preview}"'
                    )

        # Performance footer
        lines.append(
            f"\n📊 Analyzed {analysis.total_analyzed} memories in "
            f"{analysis.analysis_time_ms:.1f}ms"
        )

        return "\n".join(lines)


# Global instance
_splash_engine = None


def get_splash_engine() -> SplashEngine:
    """Get the global splash engine instance."""
    global _splash_engine
    if _splash_engine is None:
        _splash_engine = SplashEngine()
    return _splash_engine
