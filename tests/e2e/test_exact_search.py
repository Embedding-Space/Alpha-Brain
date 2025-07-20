"""Test exact text search functionality."""

import asyncio
from datetime import UTC, datetime

import pytest


@pytest.mark.asyncio
async def test_exact_search(mcp_client):
    """Test that exact search finds specific text."""
    # Store some test memories with unique phrases
    test_id = datetime.now(UTC).isoformat()

    memories = [
        f"Test {test_id}: The quick brown fox jumps over the lazy dog",
        f"Test {test_id}: Premature optimization is the root of all evil",
        f"Test {test_id}: Alpha Brain is working great with exact search",
    ]

    # Store all memories
    for content in memories:
        await mcp_client.call_tool("remember", {"content": content})

    # Small delay to ensure indexing
    await asyncio.sleep(0.5)

    # Test 1: Search for exact phrase
    result = await mcp_client.call_tool(
        "search",
        {"query": "premature optimization", "search_type": "exact", "limit": 5},
    )

    prose_result = result.content[0].text
    # Should find the memory content
    assert "Premature optimization" in prose_result
    assert test_id in prose_result

    # Test 2: Case insensitive search
    result = await mcp_client.call_tool(
        "search", {"query": "ALPHA BRAIN", "search_type": "exact", "limit": 5}
    )

    prose_result = result.content[0].text
    # Should find the memory content (case insensitive)
    assert "Alpha Brain" in prose_result

    # Test 3: Partial word match
    result = await mcp_client.call_tool(
        "search", {"query": "optim", "search_type": "exact", "limit": 5}
    )

    prose_result = result.content[0].text
    # Should find the memory with partial match
    assert "optimization" in prose_result

    # Test 4: No similarity scores in exact search (check the last result)
    # Since we don't have similarity scores for exact search, they shouldn't appear
    # (Note: The template shows them only if not none)

    # Test 5: Search returns nothing for non-existent text
    result = await mcp_client.call_tool(
        "search",
        {"query": "xyzzy_nonexistent_text_12345", "search_type": "exact", "limit": 5},
    )

    prose_result = result.content[0].text
    # Should indicate no results found (empty or message)
    assert "No memories found" in prose_result or (
        prose_result.strip() == "" or not prose_result.strip()
    )


@pytest.mark.asyncio
async def test_exact_vs_semantic_search(mcp_client):
    """Compare exact search with semantic search."""
    # Store a memory about optimization
    test_id = datetime.now(UTC).isoformat()
    content = f"Test {test_id}: We should avoid premature optimization in our code"

    await mcp_client.call_tool("remember", {"content": content})
    await asyncio.sleep(0.5)

    # Exact search for "optimize" (won't find "optimization")
    exact_result = await mcp_client.call_tool(
        "search", {"query": "optimize", "search_type": "exact", "limit": 1}
    )

    # Semantic search for "optimize" (should find "optimization")
    semantic_result = await mcp_client.call_tool(
        "search", {"query": "optimize", "search_type": "semantic", "limit": 1}
    )

    # Exact search is literal - won't find variations
    exact_text = exact_result.content[0].text
    # Either finds nothing or finds memories containing "optimize"
    assert "No memories found" in exact_text or "optimize" in exact_text

    # Semantic search understands meaning - finds related terms
    semantic_text = semantic_result.content[0].text
    assert "optimization" in semantic_text
    assert "similarity:" in semantic_text  # Has similarity score
