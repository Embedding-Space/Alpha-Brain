"""Minimal entity flow test - one remember, many assertions."""

import re
from datetime import UTC, datetime

import pytest


@pytest.mark.asyncio
async def test_entity_system_happy_path(mcp_client):
    """Test entity system with minimal API calls."""
    test_id = datetime.now(UTC).isoformat()
    
    # ONE remember call with rich content
    content = f"Test {test_id}: Met with PersonName about ProjectAlpha using ToolBeta"
    result = await mcp_client.call_tool("remember", {"content": content})
    
    # --- ASSERTIONS ABOUT THE REMEMBER RESPONSE ---
    
    # 1. Basic success
    assert not result.is_error, f"Remember failed: {result}"
    assert result.content, "Should have content blocks"
    
    # 2. Response structure
    response_text = result.content[0].text
    assert isinstance(response_text, str), "Response should be text"
    assert len(response_text) > 0, "Response should not be empty"
    
    # 3. Memory ID extraction (we always need this)
    match = re.search(r"ID: ([a-f0-9-]+)", response_text)
    assert match, "Response should contain memory ID"
    memory_id = match.group(1)
    assert len(memory_id) == 36, "Memory ID should be UUID format"
    
    # 4. Response format checks
    assert not response_text.startswith("{"), "Should not be raw JSON"
    assert not response_text.startswith("["), "Should not be raw array"
    
    # --- NOW VERIFY THE MEMORY WAS STORED CORRECTLY ---
    
    # 5. Retrieve the memory to check storage
    get_result = await mcp_client.call_tool("get_memory", {"memory_id": memory_id})
    assert not get_result.is_error, "Should be able to retrieve memory"
    
    memory_text = get_result.content[0].text
    assert content in memory_text, "Original content should be preserved"
    
    # 6. Check that we got back a formatted memory (not just raw data)
    # The template shows: ID, timestamp, content, importance
    assert "Importance:" in memory_text, "Should show importance rating"
    
    # --- VERIFY SEARCH WORKS ---
    
    # 7. ONE search call to verify it's findable
    search_result = await mcp_client.call_tool(
        "search", 
        {"query": test_id, "limit": 5}
    )
    assert not search_result.is_error, "Search should work"
    
    search_text = search_result.content[0].text
    assert memory_id in search_text, "Should find our memory by ID"
    
    print(f"✓ Entity system test passed with memory ID: {memory_id}")