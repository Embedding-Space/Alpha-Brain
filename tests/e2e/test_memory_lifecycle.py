"""E2E test for the complete memory lifecycle."""

from datetime import UTC, datetime

import pytest


@pytest.mark.asyncio
async def test_full_memory_lifecycle(mcp_client):
    """The one test that matters: can we remember and recall?"""
    # 1. Remember something unique
    test_id = datetime.now(UTC).isoformat()
    content = (
        f"Test memory at {test_id}: The quick brown fox jumps over the lazy dog 🦊"
    )

    remember_result = await mcp_client.call_tool("remember", {"content": content})

    # FastMCP client returns CallToolResult with content blocks
    # The prose is in the text content
    assert hasattr(remember_result, "content")
    assert len(remember_result.content) > 0

    # Get the prose text from the content blocks
    prose_result = remember_result.content[0].text
    assert isinstance(prose_result, str)
    # Check for essential data: ID only (we don't echo content back)
    assert "ID:" in prose_result  # Memory ID should be present

    # 2. Small delay to ensure indexing
    import asyncio

    await asyncio.sleep(0.5)

    # Search for it (semantic search, not exact)
    search_result = await mcp_client.call_tool(
        "search", {"query": "quick brown fox", "limit": 5}
    )

    # Tools now return prose wrapped in CallToolResult
    prose_result = search_result.content[0].text
    assert isinstance(prose_result, str)
    # Check that our memory was found
    assert test_id in prose_result  # Our unique timestamp should be in results

    # 3. Search semantically (partial match)
    semantic_result = await mcp_client.call_tool(
        "search", {"query": "fox jumping", "limit": 5}
    )

    # Should find our memory in results
    prose_result = semantic_result.content[0].text
    assert isinstance(prose_result, str)
    assert test_id in prose_result

    # 4. Test Unicode handling
    emoji_content = "I'm feeling great today! 😊🎉🌟 Unicode test: café, naïve, 你好"
    emoji_result = await mcp_client.call_tool("remember", {"content": emoji_content})

    prose_result = emoji_result.content[0].text
    assert isinstance(prose_result, str)
    # Check for essential data
    assert "ID:" in prose_result  # Memory ID should be present
    # We don't echo content back, so no emoji check needed

    # 5. Test nonsense search (should not crash, returns low similarity results)
    empty_result = await mcp_client.call_tool(
        "search", {"query": "xyzzy12345notfound", "limit": 1}
    )

    prose_result = empty_result.content[0].text
    assert isinstance(prose_result, str)
    # Should return something (either results or no results message)
    # Just check it didn't crash and returned text
    assert len(prose_result) > 0


@pytest.mark.asyncio
async def test_memory_edge_cases(mcp_client):
    """Test edge cases and potential failure modes."""
    # Empty content (service handles gracefully, stores empty memory)
    empty_result = await mcp_client.call_tool("remember", {"content": ""})
    prose_result = empty_result.content[0].text
    assert isinstance(prose_result, str)
    # Should either store it (with ID) or return an error message
    assert (
        "ID:" in prose_result
        or "Failed to store" in prose_result
        or "error" in prose_result.lower()
    )

    # Search with different types
    for search_type in ["semantic", "emotional"]:
        typed_result = await mcp_client.call_tool(
            "search", {"query": "test", "search_type": search_type, "limit": 1}
        )
        prose_result = typed_result.content[0].text
        assert isinstance(prose_result, str)
        # Should return something (results or no results)
        assert len(prose_result) > 0
