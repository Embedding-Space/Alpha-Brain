"""Test entity-aware search functionality."""

import pytest


@pytest.mark.asyncio
async def test_entity_search_prioritizes_exact_matches(mcp_client):
    """Entity matches should appear first with perfect similarity scores."""
    # Create a unique test entity
    test_entity = "TestEntityAware42"
    result = await mcp_client.call_tool(
        "add_alias", 
        {"canonical_name": test_entity, "alias": test_entity}
    )
    assert not result.is_error
    
    # Store a memory with this entity
    memory_with_entity = f"Had lunch with {test_entity} at the new cafe downtown"
    result = await mcp_client.call_tool("remember", {"content": memory_with_entity})
    assert not result.is_error

    # Store a related memory without the entity
    related_memory = "The cafe downtown has excellent coffee and pastries"
    result = await mcp_client.call_tool("remember", {"content": related_memory})
    assert not result.is_error

    # Search for the entity
    result = await mcp_client.call_tool("search", {"query": test_entity})
    assert not result.is_error

    output = result.content[0].text

    # The entity match should appear first
    assert memory_with_entity in output
    assert "similarity: 1.00" in output  # Perfect score for entity match

    # Related memory might appear but with lower score
    if related_memory in output:
        # Find the similarity scores
        lines = output.split("\n")
        entity_line_idx = None
        related_line_idx = None

        for i, line in enumerate(lines):
            if memory_with_entity in line:
                # Look backwards for the similarity score
                for j in range(i, -1, -1):
                    if "similarity:" in lines[j]:
                        entity_line_idx = j
                        break
            elif related_memory in line:
                # Look backwards for the similarity score
                for j in range(i, -1, -1):
                    if "similarity:" in lines[j]:
                        related_line_idx = j
                        break

        # Entity match should come before related match
        assert entity_line_idx is not None
        if related_line_idx is not None:
            assert entity_line_idx < related_line_idx


@pytest.mark.asyncio
async def test_entity_search_works_with_unknown_entities(mcp_client):
    """Search should find entities even when they're not canonicalized."""
    # Store memory with an unknown entity
    content = "Meeting with Dr. Zhivago about the new research project"
    result = await mcp_client.call_tool("remember", {"content": content})
    assert not result.is_error

    # Search for the unknown entity
    result = await mcp_client.call_tool("search", {"query": "Dr. Zhivago"})
    assert not result.is_error

    output = result.content[0].text
    assert content in output
    assert "similarity: 1.00" in output  # Should still get perfect score


@pytest.mark.asyncio
async def test_entity_search_combines_with_semantic_search(mcp_client):
    """Entity search should combine with regular semantic search."""
    # Store several memories
    memories = [
        "Alpha is working on improving the search algorithm",
        "The search algorithm needs to handle entity names better",
        "Testing the new entity-aware features in the system",
    ]

    for memory in memories:
        result = await mcp_client.call_tool("remember", {"content": memory})
        assert not result.is_error

    # Search for "Alpha" - should find entity match plus semantic matches
    result = await mcp_client.call_tool("search", {"query": "Alpha", "limit": 10})
    assert not result.is_error

    output = result.content[0].text

    # First memory should have perfect score (entity match)
    assert memories[0] in output
    assert "similarity: 1.00" in output

    # Other memories might appear with lower semantic similarity
    # But we should see multiple results
    assert "---" in output  # Multiple results separator
