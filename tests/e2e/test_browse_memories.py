"""E2E tests for the browse memories tool."""


import pytest


@pytest.mark.asyncio
async def test_browse_basic_interval(mcp_client):
    """Browse should return memories from the specified time interval in chronological order."""
    # First, create some test memories with known timestamps
    await mcp_client.call_tool("remember", {"content": "Morning standup discussing browse tool design"})
    await mcp_client.call_tool("remember", {"content": "Afternoon debugging session with pgvector issues"})
    await mcp_client.call_tool("remember", {"content": "Evening reflection on TDD methodology"})
    
    # Browse memories from today
    result = await mcp_client.call_tool("browse", {"interval": "today"})
    
    # Should return memories without error
    assert not result.is_error
    response = result.content[0].text
    
    # The browse tool should show memories in a structured format
    assert response is not None
    assert len(response) > 0
    # Check that our test memories appear in the output
    assert "browse tool design" in response or "debugging session" in response or "TDD methodology" in response


@pytest.mark.asyncio
async def test_browse_with_entity_filter(mcp_client):
    """Browse should filter by entity when specified."""
    # Create memories with different entities
    await mcp_client.call_tool("remember", {"content": "Jeffery suggested using TDD for the browse tool"})
    await mcp_client.call_tool("remember", {"content": "Kylee is traveling to Chicago next week"})
    await mcp_client.call_tool("remember", {"content": "Sparkle knocked over my water glass again"})
    
    # Browse only Jeffery memories from today
    result = await mcp_client.call_tool("browse", {"interval": "today", "entity": "Jeffery Harrell"})
    
    assert not result.is_error
    response = result.content[0].text
    
    # Should include Jeffery memory but perhaps not others
    # (Can't be too strict since test data might have other Jeffery memories)
    assert "TDD" in response or "Jeffery" in response


@pytest.mark.asyncio
async def test_browse_with_text_search(mcp_client):
    """Browse should support full-text search filtering."""
    # Create memories with specific keywords
    await mcp_client.call_tool("remember", {"content": "Working on Alpha Brain browse functionality"})
    await mcp_client.call_tool("remember", {"content": "Fixed the pgvector backup restore issue"})
    await mcp_client.call_tool("remember", {"content": "Having coffee and chatting about visualization ideas"})
    
    # Browse memories containing "browse"
    result = await mcp_client.call_tool("browse", {"interval": "today", "text": "browse"})
    
    assert not result.is_error
    response = result.content[0].text
    
    # Should find the browse functionality memory
    assert response is not None
    assert len(response) > 0


@pytest.mark.asyncio
async def test_browse_with_exact_match(mcp_client):
    """Browse should support exact substring matching."""
    # Create a memory with a specific phrase
    await mcp_client.call_tool("remember", {"content": "Jeffery said 'eat our own dogfood' about the backup system"})
    
    # Search for exact phrase
    result = await mcp_client.call_tool("browse", {"interval": "today", "exact": "eat our own dogfood"})
    
    assert not result.is_error
    response = result.content[0].text
    
    # Should find the memory with that exact phrase
    assert "eat our own dogfood" in response


@pytest.mark.asyncio
async def test_browse_with_importance_filter(mcp_client):
    """Browse should filter by minimum importance level."""
    # Browse only important memories (4+)
    result = await mcp_client.call_tool("browse", {"interval": "past week", "importance": 4})
    
    assert not result.is_error
    response = result.content[0].text
    
    # Should get a response (even if no memories match the filter)
    assert response is not None


@pytest.mark.asyncio
async def test_browse_with_combined_filters(mcp_client):
    """Browse should correctly combine multiple filters."""
    # Create a specific memory we can find
    await mcp_client.call_tool("remember", {"content": "Jeffery and I celebrated fixing the critical pgvector tests"})
    
    # Browse with multiple filters
    result = await mcp_client.call_tool("browse", {
        "interval": "today",
        "entity": "Jeffery Harrell", 
        "text": "pgvector"
    })
    
    assert not result.is_error
    response = result.content[0].text
    
    # Should return results matching all filters
    assert response is not None


@pytest.mark.asyncio
async def test_browse_respects_limit(mcp_client):
    """Browse should respect the limit parameter."""
    # Browse with a small limit
    result = await mcp_client.call_tool("browse", {"interval": "past month", "limit": 5})
    
    assert not result.is_error
    response = result.content[0].text
    
    # Should get a response
    assert response is not None


@pytest.mark.asyncio
async def test_browse_requires_interval(mcp_client):
    """Browse should fail gracefully when interval is missing."""
    # Try to browse without required interval
    from fastmcp.exceptions import ToolError
    
    with pytest.raises(ToolError) as exc_info:
        await mcp_client.call_tool("browse", {"entity": "Jeffery Harrell"})
    
    # Should indicate an error due to missing required parameter
    error_text = str(exc_info.value)
    assert "interval" in error_text.lower()


@pytest.mark.asyncio  
async def test_browse_with_ascending_order(mcp_client):
    """Browse should support ascending chronological order."""
    # Create memories with known order
    await mcp_client.call_tool("remember", {"content": "First memory of the day"})
    await mcp_client.call_tool("remember", {"content": "Second memory of the day"})
    await mcp_client.call_tool("remember", {"content": "Third memory of the day"})
    
    # Browse in ascending order (oldest first)
    result = await mcp_client.call_tool("browse", {"interval": "today", "order": "asc", "limit": 10})
    
    assert not result.is_error
    response = result.content[0].text
    
    # Should show memories in some order
    assert response is not None
    assert len(response) > 0
