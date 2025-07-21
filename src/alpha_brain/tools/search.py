"""Adaptive search that chooses strategy based on query emotional tone."""

import numpy as np
from fastmcp import Context
from scipy.spatial.distance import cosine
from sqlalchemy import select, text

from alpha_brain.database import get_db
from alpha_brain.embeddings import get_embedding_service
from alpha_brain.entity_service import get_entity_service
from alpha_brain.memory_service import get_memory_service
from alpha_brain.schema import Entity, Knowledge, Memory
from alpha_brain.templates import render_output
from alpha_brain.time_service import TimeService


# Pure neutral vector for comparison
# Format: [anger, disgust, fear, joy, neutral, sadness, surprise]
PURE_NEUTRAL = np.array([0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0])

# Threshold for deciding if a query is emotional
EMOTIONAL_THRESHOLD = 0.8  # If neutral similarity < 0.8, include emotional search


async def search(ctx: Context, query: str, limit: int = 10) -> str:
    """
    Adaptive search that analyzes query emotion and chooses appropriate strategy.
    
    - Neutral queries (similarity > 0.8): Semantic search only
    - Emotional queries: Both semantic and emotional search, presented separately
    
    Args:
        ctx: MCP context
        query: The search query
        limit: Maximum number of results per search type
        
    Returns:
        Formatted search results with appropriate sections
    """
    # Wall 1: Check for entity matches (always do this)
    entity_match = None
    entity_service = get_entity_service()
    
    # Try exact match first (canonical name or alias)
    async with get_db() as session:
        # Check canonical name
        stmt = select(Entity).where(Entity.canonical_name == query)
        result = await session.execute(stmt)
        entity = result.scalar_one_or_none()
        
        if not entity:
            # Check aliases using PostgreSQL ANY
            stmt = select(Entity).where(
                text(":query = ANY(aliases)").bindparams(query=query)
            )
            result = await session.execute(stmt)
            entity = result.scalar_one_or_none()
        
        if entity:
            entity_match = {
                "id": entity.id,
                "canonical_name": entity.canonical_name,
                "aliases": entity.aliases,
                "entity_type": entity.entity_type,
                "description": entity.description,
                "first_seen": TimeService.format_for_context(entity.first_seen),
            }
    
    # Wall 2: Check for knowledge matches
    knowledge_match = None
    # TODO: Implement knowledge search when we have the Knowledge model ready
    
    # Wall 3: Full-text search for exact word matches
    fulltext_memories = []
    async with get_db() as session:
        # Use PostgreSQL full-text search with plainto_tsquery
        stmt = text("""
            SELECT id, content, created_at
            FROM memories 
            WHERE search_vector @@ plainto_tsquery('english', :query)
            ORDER BY ts_rank(search_vector, plainto_tsquery('english', :query)) DESC
            LIMIT :limit
        """)
        
        result = await session.execute(stmt, {"query": query, "limit": limit})
        rows = result.fetchall()
        
        for row in rows:
            from alpha_brain.schema import MemoryOutput
            memory = MemoryOutput(
                id=row.id,
                content=row.content,
                created_at=row.created_at,
                similarity_score=None,  # Full-text doesn't have similarity scores
                marginalia={},
                age=TimeService.format_age(row.created_at)
            )
            fulltext_memories.append(memory)
    
    # Wall 4: Analyze query emotion to determine search strategy
    embedding_service = get_embedding_service()
    embeddings = await embedding_service.embed(query)
    # embeddings is a tuple: (semantic_embedding, emotional_embedding)
    _, emotional_emb = embeddings
    emotional_emb = np.array(emotional_emb)
    
    # Calculate similarity to pure neutral
    neutral_similarity = 1 - cosine(emotional_emb, PURE_NEUTRAL)
    
    # Determine dominant emotion for context
    emotion_labels = ["anger", "disgust", "fear", "joy", "neutral", "sadness", "surprise"]
    dominant_idx = np.argmax(emotional_emb)
    dominant_emotion = emotion_labels[dominant_idx]
    dominant_score = emotional_emb[dominant_idx]
    
    # Wall 4: Perform appropriate searches
    memory_service = get_memory_service()
    
    if neutral_similarity > EMOTIONAL_THRESHOLD:
        # Query is neutral - semantic search only
        semantic_memories = await memory_service.search(
            query=query,
            search_type="semantic",
            limit=limit
        )
        emotional_memories = []
        search_mode = "semantic"
    else:
        # Query has emotion - do both searches separately
        semantic_memories = await memory_service.search(
            query=query,
            search_type="semantic",
            limit=limit
        )
        emotional_memories = await memory_service.search(
            query=query,
            search_type="emotional",
            limit=limit
        )
        search_mode = "both"
    
    # Check if we should warn about low similarity
    semantic_warning = None
    if semantic_memories and all(m.similarity_score < 0.3 for m in semantic_memories):
        semantic_warning = "Semantic search returned low-quality results."
    
    emotional_warning = None
    if emotional_memories and all(m.similarity_score < 0.3 for m in emotional_memories):
        emotional_warning = "Emotional search returned low-quality results."
    
    # Format the adaptive results
    return render_output(
        "search",
        query=query,
        entity=entity_match,
        knowledge=knowledge_match,
        fulltext_memories=fulltext_memories,
        semantic_memories=semantic_memories,
        emotional_memories=emotional_memories,
        semantic_warning=semantic_warning,
        emotional_warning=emotional_warning,
        search_mode=search_mode,
        neutral_similarity=neutral_similarity,
        dominant_emotion=dominant_emotion,
        dominant_score=dominant_score,
        current_time=TimeService.format_full(TimeService.now())
    )