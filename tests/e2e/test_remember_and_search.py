"""Test the core memory workflow: remember something, then find it."""

import asyncio

import pytest


@pytest.mark.asyncio
async def test_remember_and_search_basic(mcp_client):
    """Can we remember something and find it again?"""
    # Remember something unique
    unique_content = "The little duck helped Jeffery build a prosthetic brain on Tuesday afternoon"
    
    # Store the memory
    result = await mcp_client.call_tool("remember", {"content": unique_content})
    assert not result.is_error
    # Check that we got a memory ID back (indicates successful storage)
    response_text = result.content[0].text
    assert "ID:" in response_text  # Memory ID is always shown
    
    # Search for it by a key phrase
    result = await mcp_client.call_tool("search", {"query": "prosthetic brain"})
    assert not result.is_error
    
    # Check that we found it
    response_text = result.content[0].text
    assert unique_content in response_text
    assert "Jeffery" in response_text  # Entity should be recognized


@pytest.mark.asyncio
async def test_remember_with_entity_then_search(mcp_client):
    """Can we find memories by entity name?"""
    # First, establish an entity with an alias
    # Note: Sparkle is the canonical name, not Sparkplug Louise Mittenhaver
    await mcp_client.call_tool("entity", {
        "operation": "set-alias",
        "name": "Sparkle the cat",
        "canonical": "Sparkle"
    })
    
    # Remember something about Sparkle
    memory1 = "Sparkle caught a mouse and brought it to the door as a gift"
    memory2 = "Fed Sparkle her favorite salmon treats this morning"
    
    result1 = await mcp_client.call_tool("remember", {"content": memory1})
    assert not result1.is_error
    
    result2 = await mcp_client.call_tool("remember", {"content": memory2})
    assert not result2.is_error
    
    # Search by the alias
    result = await mcp_client.call_tool("search", {"query": "Sparkle"})
    assert not result.is_error
    
    response_text = result.content[0].text
    # Both memories should be found because entity search
    assert "mouse" in response_text
    assert "salmon treats" in response_text


@pytest.mark.asyncio 
async def test_search_with_time_interval(mcp_client):
    """Can we filter searches by time?"""
    # Remember something unique to this test run
    import uuid
    unique_id = str(uuid.uuid4())[:8]
    test_memory = f"Test run {unique_id}: Just ran the test suite and everything is green!"
    result = await mcp_client.call_tool("remember", {"content": test_memory})
    assert not result.is_error
    
    # Small delay to ensure full-text indexing
    await asyncio.sleep(0.5)
    
    # Search for recent memories with our unique ID
    result = await mcp_client.call_tool("search", {
        "query": f"Test run {unique_id}",
        "interval": "past 1 hour"
    })
    assert not result.is_error
    
    response_text = result.content[0].text
    assert test_memory in response_text
    
    # Search for memories from yesterday with our unique ID (should find nothing)
    result = await mcp_client.call_tool("search", {
        "query": f"Test run {unique_id}", 
        "interval": "yesterday"
    })
    assert not result.is_error
    
    response_text = result.content[0].text
    # Our unique test memory should NOT be in yesterday's results
    # Check for "No results found" instead of unique_id absence since the query echoes the ID
    assert ("No results found" in response_text or "0 memories found" in response_text or test_memory not in response_text)


@pytest.mark.asyncio
async def test_browse_memories_without_query(mcp_client):
    """Can we browse memories without a search query?"""
    # Add a memory first
    test_memory = "Browsing test: this memory was added during E2E testing"
    await mcp_client.call_tool("remember", {"content": test_memory})
    
    # Browse recent memories (no query, just time interval)
    result = await mcp_client.call_tool("search", {
        "interval": "past 2 hours"
    })
    assert not result.is_error
    
    response_text = result.content[0].text
    # Should see our recent memory
    assert test_memory in response_text
    # Should indicate browse mode - check for the interval we searched
    assert "past 2 hours" in response_text.lower() or "browse past 2 hours" in response_text.lower()
