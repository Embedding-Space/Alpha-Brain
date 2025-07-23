"""Adaptive search that chooses strategy based on query emotional tone."""

import numpy as np
from fastmcp import Context
from scipy.spatial.distance import cosine
from sqlalchemy import select, text

from alpha_brain.database import get_db
from alpha_brain.embeddings import get_embedding_service
from alpha_brain.memory_service import get_memory_service
from alpha_brain.schema import Entity, Knowledge, Memory, MemoryOutput
from alpha_brain.templates import render_output
from alpha_brain.time_service import TimeService


def extract_first_paragraph(content: str) -> str:
    """Extract the first paragraph from markdown content.
    
    Skips headers and returns the first actual paragraph of text.
    """
    lines = content.strip().split('\n')
    
    # Find the first non-header, non-empty line
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped and not stripped.startswith('#'):
            # Found start of first paragraph
            paragraph_lines = [stripped]
            
            # Continue collecting lines until we hit a blank line or end
            for j in range(i + 1, len(lines)):
                next_line = lines[j].strip()
                if not next_line:  # Blank line = end of paragraph
                    break
                if next_line.startswith('#'):  # Header = end of paragraph
                    break
                if next_line.startswith(('-', '*')):  # Bullet list = end of paragraph
                    break
                if next_line.startswith(('1.', '2.')):  # Numbered list = end
                    break
                paragraph_lines.append(next_line)
            
            return ' '.join(paragraph_lines)
    
    # Fallback if no paragraph found
    return content[:300] + "..." if len(content) > 300 else content


# Pure neutral vector for comparison
# Format: [anger, disgust, fear, joy, neutral, sadness, surprise]
PURE_NEUTRAL = np.array([0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0])

# Threshold for deciding if a query is emotional
EMOTIONAL_THRESHOLD = 0.8  # If neutral similarity < 0.8, include emotional search


async def search(ctx: Context, query: str | None = None, limit: int = 10, interval: str | None = None) -> str:
    """
    Adaptive search that analyzes query emotion and chooses appropriate strategy.
    
    - Neutral queries (similarity > 0.8): Semantic search only  
    - Emotional queries: Both semantic and emotional search, presented separately
    - No query (browse mode): Returns memories from specified interval
    
    Args:
        ctx: MCP context
        query: The search query (optional for browse mode)
        limit: Maximum number of results per search type
        interval: Time interval to filter by (e.g., "yesterday", "past 3 hours")
        
    Returns:
        Formatted search results with appropriate sections
    """
    # Handle browse mode (no query, just interval) 
    if not query and interval:
        # Browse mode - get memories directly from database without embeddings
        from alpha_brain.interval_parser import parse_interval
        
        try:
            start_time, end_time = parse_interval(interval)
            
            async with get_db() as session:
                stmt = select(Memory).where(
                    Memory.created_at >= start_time,
                    Memory.created_at <= end_time
                ).order_by(Memory.created_at.desc()).limit(limit)
                
                result = await session.execute(stmt)
                raw_memories = result.scalars().all()
                
                # Convert to MemoryOutput format
                memories = []
                for memory in raw_memories:
                    memories.append(MemoryOutput(
                        id=memory.id,
                        content=memory.content,
                        created_at=memory.created_at,
                        similarity_score=None,
                        marginalia=memory.marginalia,
                        age=TimeService.format_age(memory.created_at)
                    ))
            
            # Return simple browse results
            return render_output(
                "search", 
                query=f"Browse {interval}",
                entity=None,
                knowledge_title_match=None,
                knowledge_fulltext_matches=[],
                fulltext_memories=[],
                semantic_memories=memories,
                emotional_memories=[],
                semantic_warning=None,
                emotional_warning=None,
                search_mode="browse",
                neutral_similarity=None,
                dominant_emotion=None, 
                dominant_score=None,
                current_time=TimeService.format_full(TimeService.now())
            )
        except Exception as e:
            return f"Browse mode error: {e!s}"
    
    # Require query for all other modes
    if not query:
        raise ValueError("Query parameter is required unless using browse mode with interval")

    # Wall 1: Check for entity matches (only if we have a query)
    entity_match = None
    
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
            }
    
    # Wall 2: Check for knowledge matches (title first, then full-text)
    knowledge_title_match = None
    knowledge_fulltext_matches = []
    
    async with get_db() as session:
        # First check for exact title match (case-insensitive)
        stmt = select(Knowledge).where(
            Knowledge.title.ilike(query)
        )
        result = await session.execute(stmt)
        knowledge = result.scalar_one_or_none()
        
        if knowledge:
            knowledge_title_match = {
                "id": knowledge.id,
                "slug": knowledge.slug,
                "title": knowledge.title,
                "first_paragraph": extract_first_paragraph(knowledge.content),
                "created_at": TimeService.format_for_context(knowledge.created_at),
            }
        
        # Also do full-text search on knowledge
        if not knowledge_title_match:  # Only if we didn't get exact title match
            stmt = text("""
                SELECT id, slug, title, content, created_at,
                       ts_headline('english', content, plainto_tsquery('english', :query), 
                                  'MaxFragments=2, FragmentDelimiter=…, MaxWords=40, MinWords=10') as headline
                FROM knowledge
                WHERE search_vector @@ plainto_tsquery('english', :query)
                ORDER BY ts_rank_cd(search_vector, plainto_tsquery('english', :query)) DESC
                LIMIT :limit
            """)
            
            result = await session.execute(stmt, {"query": query, "limit": limit})
            rows = result.fetchall()
            
            for row in rows:
                knowledge_fulltext_matches.append({
                    "id": row.id,
                    "slug": row.slug,
                    "title": row.title,
                    "headline": row.headline,
                    "created_at": TimeService.format_for_context(row.created_at),
                })
    
    # Wall 3: Full-text search for exact word matches
    fulltext_memories = []
    
    # Parse interval if provided for full-text search
    if interval:
        from alpha_brain.interval_parser import parse_interval
        start_time, end_time = parse_interval(interval)
    
    async with get_db() as session:
        # Build query with optional time filter
        if interval:
            stmt = text("""
                SELECT id, content, created_at
                FROM memories 
                WHERE search_vector @@ plainto_tsquery('english', :query)
                  AND created_at >= :start_time
                  AND created_at <= :end_time
                ORDER BY ts_rank(search_vector, plainto_tsquery('english', :query)) DESC
                LIMIT :limit
            """)
            params = {"query": query, "limit": limit, "start_time": start_time, "end_time": end_time}
        else:
            stmt = text("""
                SELECT id, content, created_at
                FROM memories 
                WHERE search_vector @@ plainto_tsquery('english', :query)
                ORDER BY ts_rank(search_vector, plainto_tsquery('english', :query)) DESC
                LIMIT :limit
            """)
            params = {"query": query, "limit": limit}
        
        result = await session.execute(stmt, params)
        rows = result.fetchall()
        
        for row in rows:
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
            limit=limit,
            interval=interval
        )
        emotional_memories = []
        search_mode = "semantic"
    else:
        # Query has emotion - do both searches separately
        semantic_memories = await memory_service.search(
            query=query,
            search_type="semantic",
            limit=limit,
            interval=interval
        )
        emotional_memories = await memory_service.search(
            query=query,
            search_type="emotional",
            limit=limit,
            interval=interval
        )
        search_mode = "both"
    
    # Check if we should warn about low similarity
    semantic_warning = None
    if semantic_memories and all(m.similarity_score < 0.3 for m in semantic_memories):
        semantic_warning = "Semantic search returned low-quality results."
    
    emotional_warning = None
    if emotional_memories and all(m.similarity_score < 0.3 for m in emotional_memories):
        emotional_warning = "Emotional search returned low-quality results."
    
    # Deduplicate memories across sections
    # Priority: entity > knowledge > full-text > semantic > emotional
    seen_ids = set()
    
    # Full-text memories get first pass (after entity/knowledge)
    deduped_fulltext = []
    for memory in fulltext_memories:
        if memory.id not in seen_ids:
            seen_ids.add(memory.id)
            deduped_fulltext.append(memory)
    
    # Semantic memories exclude anything already shown
    deduped_semantic = []
    for memory in semantic_memories:
        if memory.id not in seen_ids:
            seen_ids.add(memory.id)
            deduped_semantic.append(memory)
    
    # Emotional memories exclude anything already shown
    deduped_emotional = []
    for memory in emotional_memories:
        if memory.id not in seen_ids:
            seen_ids.add(memory.id)
            deduped_emotional.append(memory)
    
    # Format the adaptive results
    return render_output(
        "search",
        query=query,
        entity=entity_match,
        knowledge_title_match=knowledge_title_match,
        knowledge_fulltext_matches=knowledge_fulltext_matches,
        fulltext_memories=deduped_fulltext,
        semantic_memories=deduped_semantic,
        emotional_memories=deduped_emotional,
        semantic_warning=semantic_warning,
        emotional_warning=emotional_warning,
        search_mode=search_mode,
        neutral_similarity=neutral_similarity,
        dominant_emotion=dominant_emotion,
        dominant_score=dominant_score,
        current_time=TimeService.format_full(TimeService.now())
    )
