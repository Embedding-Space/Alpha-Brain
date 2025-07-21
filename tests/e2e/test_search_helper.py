"""Test SearchHelper entity extraction with realistic query types."""

import pytest

from alpha_brain.search_helper import get_search_helper


@pytest.mark.asyncio
async def test_single_entity_queries():
    """Test queries looking for context about a single entity."""
    helper = get_search_helper()
    
    test_cases = [
        ("David", ["David"]),
        ("Sparkle", ["Sparkle"]),
        ("Tagline", ["Tagline"]),
        ("Alpha Brain", ["Alpha Brain"]),
        ("Project Alpha", ["Project Alpha"]),
    ]
    
    for query, expected in test_cases:
        entities = await helper.extract_entities(query)
        assert entities == expected, f"Query '{query}' extracted {entities}, expected {expected}"


@pytest.mark.asyncio
async def test_multi_entity_queries():
    """Test queries mentioning multiple entities."""
    helper = get_search_helper()
    
    test_cases = [
        ("Jeffery and Kylee", ["Jeffery", "Kylee"]),
        ("David Hannah Michigan", ["David Hannah", "Michigan"]),
        ("Alpha Brain Docker", ["Alpha Brain", "Docker"]),
        ("Sparkle, Jeffery, and David", ["Sparkle", "Jeffery", "David"]),
        ("meeting with David about Tagline", ["David", "Tagline"]),
    ]
    
    for query, expected in test_cases:
        entities = await helper.extract_entities(query)
        # Order doesn't matter, so we compare sets
        assert set(entities) == set(expected), f"Query '{query}' extracted {entities}, expected {expected}"


@pytest.mark.asyncio
async def test_possessive_queries():
    """Test queries with possessive forms."""
    helper = get_search_helper()
    
    test_cases = [
        ("Jeffery's partner", ["Jeffery"]),  # Note: "partner" not extracted as entity
        ("David's company", ["David"]),
        ("Sparkle's food preferences", ["Sparkle"]),
        ("Alpha's memory architecture", ["Alpha"]),
        ("Kylee's Vegas trip", ["Kylee", "Vegas"]),
    ]
    
    for query, expected in test_cases:
        entities = await helper.extract_entities(query)
        assert set(entities) == set(expected), f"Query '{query}' extracted {entities}, expected {expected}"


@pytest.mark.asyncio
async def test_nickname_alias_queries():
    """Test queries using nicknames or aliases."""
    helper = get_search_helper()
    
    test_cases = [
        ("lil duck", ["lil duck"]),  # Should extract as-is
        ("THAT GODDAMN CAT", ["THAT GODDAMN CAT"]),  # Preserve exact form
        ("Jeff", ["Jeff"]),  # Common nickname
        ("little duck called me", ["little duck"]),
        ("Alph and I discussed", ["Alph"]),
    ]
    
    for query, expected in test_cases:
        entities = await helper.extract_entities(query)
        assert entities == expected, f"Query '{query}' extracted {entities}, expected {expected}"


@pytest.mark.asyncio
async def test_event_story_queries():
    """Test queries describing events or stories."""
    helper = get_search_helper()
    
    test_cases = [
        ("that time Jeffery called me lil duck", ["Jeffery", "lil duck"]),
        ("when we fixed the Docker bug", ["Docker"]),  # "we" not extracted
        ("Kylee's Backstreet Boys concert", ["Kylee", "Backstreet Boys"]),
        ("David visiting from Michigan", ["David", "Michigan"]),
        ("Sparkle knocking over coffee", ["Sparkle"]),
    ]
    
    for query, expected in test_cases:
        entities = await helper.extract_entities(query)
        assert set(entities) == set(expected), f"Query '{query}' extracted {entities}, expected {expected}"


@pytest.mark.asyncio
async def test_mixed_entity_semantic_queries():
    """Test queries mixing entities with semantic content."""
    helper = get_search_helper()
    
    test_cases = [
        ("David's new job excitement", ["David"]),
        ("Sparkle being annoying", ["Sparkle"]),
        ("Jeffery stressed about deadlines", ["Jeffery"]),
        ("Kylee happy about promotion", ["Kylee"]),
        ("Alpha confused about Docker", ["Alpha", "Docker"]),
    ]
    
    for query, expected in test_cases:
        entities = await helper.extract_entities(query)
        assert set(entities) == set(expected), f"Query '{query}' extracted {entities}, expected {expected}"


@pytest.mark.asyncio
async def test_pure_semantic_queries():
    """Test queries with no entities (pure semantic search)."""
    helper = get_search_helper()
    
    test_cases = [
        ("memory architecture design", []),  # No entities
        ("frustrated debugging session", []),
        ("breakthrough moment", []),
        ("feeling overwhelmed", []),
        ("excited about progress", []),
    ]
    
    for query, expected in test_cases:
        entities = await helper.extract_entities(query)
        assert entities == expected, f"Query '{query}' extracted {entities}, expected {expected}"


@pytest.mark.asyncio
async def test_edge_cases():
    """Test edge cases and tricky queries."""
    helper = get_search_helper()
    
    test_cases = [
        # Empty query
        ("", []),
        
        # Single word that could be name or adjective
        ("Rich", ["Rich"]),  # Should extract as potential name
        
        # Common words that are also names
        ("Will Smith", ["Will Smith"]),
        ("Grace period", []),  # "Grace" here is not a name
        
        # Multiple forms of same entity
        ("Jeff and Jeffery", ["Jeff", "Jeffery"]),  # Both extracted
        
        # Implicit entities
        ("my partner", []),  # Can't resolve "my partner" without context
        ("the cat", []),  # Generic reference
        
        # Mixed case
        ("JEFFERY AND SPARKLE", ["JEFFERY", "SPARKLE"]),
        
        # Special characters
        ("David's \"big idea\"", ["David"]),
        ("Jeffery (my user)", ["Jeffery"]),
    ]
    
    for query, expected in test_cases:
        entities = await helper.extract_entities(query)
        assert set(entities) == set(expected), f"Query '{query}' extracted {entities}, expected {expected}"


@pytest.mark.asyncio
async def test_performance():
    """Test that entity extraction is reasonably fast."""
    import time
    helper = get_search_helper()
    
    # Complex query with multiple entities
    query = "Jeffery, David, and Kylee discussed Project Alpha and Tagline while Sparkle slept"
    
    start = time.time()
    entities = await helper.extract_entities(query)
    elapsed = time.time() - start
    
    # Should complete in under 2 seconds even with network call to Ollama
    assert elapsed < 2.0, f"Entity extraction took {elapsed:.2f}s, should be under 2s"
    
    # Should find all the entities
    expected_entities = {"Jeffery", "David", "Kylee", "Project Alpha", "Tagline", "Sparkle"}
    assert set(entities) == expected_entities
