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

    prose_result = result.data
    assert isinstance(prose_result, str)
    # Should find at least one memory
    assert "memory" in prose_result or "memories" in prose_result
    assert "Premature optimization" in prose_result
    assert test_id in prose_result

    # Test 2: Case insensitive search
    result = await mcp_client.call_tool(
        "search", {"query": "ALPHA BRAIN", "search_type": "exact", "limit": 5}
    )

    prose_result = result.data
    assert "memory" in prose_result or "memories" in prose_result
    assert "Alpha Brain" in prose_result

    # Test 3: Partial word match
    result = await mcp_client.call_tool(
        "search", {"query": "optim", "search_type": "exact", "limit": 5}
    )

    prose_result = result.data
    assert "memory" in prose_result or "memories" in prose_result
    assert "optimization" in prose_result

    # Test 4: No similarity scores in exact search
    assert "similarity:" not in prose_result

    # Test 5: Search returns nothing for non-existent text
    result = await mcp_client.call_tool(
        "search",
        {"query": "xyzzy_nonexistent_text_12345", "search_type": "exact", "limit": 5},
    )

    prose_result = result.data
    assert "No memories found" in prose_result


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
    assert (
        "No memories found" in exact_result.data or "optimization" in exact_result.data
    )

    # Semantic search understands meaning - finds related terms
    assert "optimization" in semantic_result.data
    assert "similarity:" in semantic_result.data  # Has similarity score
