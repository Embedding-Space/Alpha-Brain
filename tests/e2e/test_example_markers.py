"""Example of using test markers for database state."""

import pytest


@pytest.mark.needs_empty_db
@pytest.mark.asyncio
async def test_create_first_memory(mcp_client):
    """Test creating memory in empty database."""
    # This test assumes the database starts empty
    result = await mcp_client.call_tool(
        "remember", 
        {"content": "This is the very first memory"}
    )
    
    prose = result.content[0].text
    # Check for ID which indicates successful storage
    assert "ID:" in prose


@pytest.mark.needs_data
@pytest.mark.asyncio
async def test_search_historical_data(mcp_client):
    """Test searching through pre-populated historical data."""
    # This test assumes the database has the test dataset loaded
    result = await mcp_client.call_tool(
        "search",
        {"query": "Jeffery", "limit": 10}
    )
    
    prose = result.content[0].text
    # Should find multiple memories about Jeffery from the test dataset
    assert "Jeffery" in prose
    # Check for multiple results by looking for numbered entries
    assert "2." in prose and "3." in prose  # At least 3 results


@pytest.mark.needs_data
@pytest.mark.asyncio  
async def test_temporal_search_last_month(mcp_client):
    """Test temporal search on historical data."""
    # Search for memories from June (our test data spans June-July)
    result = await mcp_client.call_tool(
        "search",
        {"interval": "2025-06-01/2025-06-30"}
    )
    
    prose = result.content[0].text
    # Should find the June memories from our test dataset
    # Look for at least one numbered result
    assert "1." in prose
    # Age format might vary, but ID should be present
    assert "ID:" in prose
