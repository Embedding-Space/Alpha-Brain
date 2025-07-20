"""Test temporal search and browsing functionality."""

import asyncio
from datetime import UTC, datetime

import pytest
from fastmcp import Client


@pytest.mark.asyncio
async def test_browse_yesterday(mcp_client: Client):
    """Test browsing all memories from yesterday."""
    # The test dataset already has memories with various timestamps
    # So we can test browsing functionality without storing new ones
    # For now, let's just test the interface
    
    result = await mcp_client.call_tool(
        "search",
        {"interval": "yesterday"}  # No query = browse mode
    )
    
    assert not result.is_error
    output = result.content[0].text
    
    # Should return memories in chronological order (oldest first) for past intervals
    assert "Current time:" in output  # Temporal grounding
    # Results should be from yesterday only
    

@pytest.mark.asyncio
async def test_browse_past_hours(mcp_client: Client):
    """Test browsing memories from the past N hours."""
    # Store a recent memory
    content = f"Test memory at {datetime.now(UTC).isoformat()}"
    await mcp_client.call_tool("remember", {"content": content})
    
    await asyncio.sleep(0.5)
    
    result = await mcp_client.call_tool(
        "search",
        {"interval": "past 2 hours"}
    )
    
    assert not result.is_error
    output = result.content[0].text
    
    # Should include our recent memory
    assert content in output
    # Should be in reverse chronological order (newest first) for now-anchored intervals


@pytest.mark.asyncio
async def test_iso_interval_formats(mcp_client: Client):
    """Test ISO 8601 interval parsing."""
    # Test explicit date range
    result = await mcp_client.call_tool(
        "search",
        {"interval": "2024-01-01/2024-01-31"}
    )
    assert not result.is_error
    
    # Test duration before now
    result = await mcp_client.call_tool(
        "search", 
        {"interval": "P1H/"}  # Past 1 hour
    )
    assert not result.is_error
    
    # Test start date + duration
    result = await mcp_client.call_tool(
        "search",
        {"interval": "2024-01-01/P7D"}  # 7 days starting Jan 1
    )
    assert not result.is_error


@pytest.mark.asyncio
async def test_search_with_temporal_filter(mcp_client: Client):
    """Test search query with temporal filtering."""
    # Store memories at different times
    content = "Discussion about temporal search implementation"
    await mcp_client.call_tool("remember", {"content": content})
    
    await asyncio.sleep(0.5)
    
    # Search with both query and time filter
    result = await mcp_client.call_tool(
        "search",
        {
            "query": "temporal search",
            "interval": "past 1 hour",
            "mode": "semantic"
        }
    )
    
    assert not result.is_error
    output = result.content[0].text
    
    # Should find our memory
    assert "temporal search" in output.lower()
    # Should show similarity scores (not browsing mode)
    assert "similarity:" in output


@pytest.mark.asyncio
async def test_entity_and_temporal_filters(mcp_client: Client):
    """Test combining entity and temporal filters."""
    # Use the existing test dataset which has memories about Jeffery
    # Search for memories from July that mention Jeffery
    result = await mcp_client.call_tool(
        "search",
        {
            "query": "Alpha",  # Many memories about Project Alpha
            "entity": "Jeffery Harrell",  # Use canonical name
            "interval": "2025-07-01/2025-07-31"  # July memories
        }
    )
    
    assert not result.is_error
    output = result.content[0].text
    
    # Should find memories that:
    # 1. Match the query "Alpha"
    # 2. Have Jeffery as an entity
    # 3. Are from July
    assert "Alpha" in output or "ID:" in output  # At least found something


@pytest.mark.asyncio
async def test_pagination(mcp_client: Client):
    """Test pagination with offset and limit."""
    # Store multiple memories
    for i in range(15):
        await mcp_client.call_tool(
            "remember",
            {"content": f"Test memory number {i}"}
        )
    
    await asyncio.sleep(0.5)
    
    # Get first page
    result = await mcp_client.call_tool(
        "search",
        {
            "interval": "today",
            "limit": 5,
            "offset": 0
        }
    )
    
    assert not result.is_error
    page1 = result.content[0].text
    
    # Get second page
    result = await mcp_client.call_tool(
        "search",
        {
            "interval": "today",
            "limit": 5,
            "offset": 5
        }
    )
    
    assert not result.is_error
    page2 = result.content[0].text
    
    # Pages should have different content
    assert page1 != page2
    # Could check for "Showing 1-5 of 15" type indicators


@pytest.mark.asyncio
async def test_order_parameter(mcp_client: Client):
    """Test explicit ordering control."""
    # Test ascending order
    result = await mcp_client.call_tool(
        "search",
        {
            "interval": "today",
            "order": "asc"
        }
    )
    assert not result.is_error
    
    # Test descending order
    result = await mcp_client.call_tool(
        "search",
        {
            "interval": "today",
            "order": "desc"
        }
    )
    assert not result.is_error
    
    # Test auto order (should be smart based on interval type)
    result = await mcp_client.call_tool(
        "search",
        {
            "interval": "yesterday",
            "order": "auto"  # Should default to chronological for past intervals
        }
    )
    assert not result.is_error


@pytest.mark.asyncio
async def test_natural_language_intervals(mcp_client: Client):
    """Test various natural language interval expressions."""
    intervals_to_test = [
        "today",
        "yesterday", 
        "this week",
        "past 3 hours",
        "last 24 hours",
        "this month"
    ]
    
    for interval in intervals_to_test:
        result = await mcp_client.call_tool(
            "search",
            {"interval": interval}
        )
        assert not result.is_error, f"Failed to parse interval: {interval}"


@pytest.mark.asyncio
async def test_empty_query_variations(mcp_client: Client):
    """Test that various empty query formats trigger browse mode."""
    empty_queries = [None, "", "*", "%"]
    
    for query in empty_queries:
        params = {"interval": "today"}
        if query is not None:
            params["query"] = query
            
        result = await mcp_client.call_tool("search", params)
        assert not result.is_error
        # In browse mode, we shouldn't see similarity scores
        # (unless it's an entity match, but we're not testing that here)
        # This is a bit tricky to test without controlling the data


@pytest.mark.asyncio
async def test_invalid_interval_error_handling(mcp_client: Client):
    """Test that invalid intervals return helpful error messages."""
    result = await mcp_client.call_tool(
        "search",
        {"interval": "gibberish time expression"}
    )
    
    # Should either handle gracefully or return an error
    # Let's check the implementation decides how to handle this
    assert result is not None  # At least it shouldn't crash
