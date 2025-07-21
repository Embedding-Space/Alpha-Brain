"""Test entity ID system with known and unknown entities."""

import re
from datetime import UTC, datetime

import pytest


@pytest.mark.asyncio
async def test_entity_ids_with_known_entities(mcp_client):
    """Test that known entities get proper IDs while unknowns are tracked."""
    # First, add test entities so we have something to find
    # Use add_alias tool to create entities with their aliases
    await mcp_client.call_tool("add_alias", {
        "canonical_name": "Test Person",
        "alias": "Test Person"  # Create the entity
    })
    await mcp_client.call_tool("add_alias", {
        "canonical_name": "Test Person", 
        "alias": "TP"
    })
    await mcp_client.call_tool("add_alias", {
        "canonical_name": "Test Person",
        "alias": "TestP"
    })
    
    await mcp_client.call_tool("add_alias", {
        "canonical_name": "Test Project",
        "alias": "Test Project"  # Create the entity
    })
    await mcp_client.call_tool("add_alias", {
        "canonical_name": "Test Project",
        "alias": "TestProj"
    })
    
    # Now remember something with both known and unknown entities
    test_id = datetime.now(UTC).isoformat()
    content = f"Test {test_id}: Test Person and UnknownPerson discussed Test Project and UnknownProject"
    
    result = await mcp_client.call_tool("remember", {"content": content})
    assert not result.is_error
    
    # Extract memory ID
    response_text = result.content[0].text
    match = re.search(r"ID: ([a-f0-9-]+)", response_text)
    memory_id = match.group(1)
    
    # Get the memory to check entity processing
    get_result = await mcp_client.call_tool("get_memory", {"memory_id": memory_id})
    memory_text = get_result.content[0].text
    
    # Extract marginalia
    marginalia_match = re.search(r"Full marginalia: ({.*})", memory_text)
    assert marginalia_match, "Should find marginalia"
    
    # Parse the marginalia (it's a Python dict repr)
    import ast
    marginalia = ast.literal_eval(marginalia_match.group(1))
    
    # Check entity processing
    assert "entity_ids" in marginalia, "Should have entity_ids field"
    assert len(marginalia["entity_ids"]) == 2, "Should have 2 entity IDs for known entities"
    assert all(isinstance(entity_id, int) for entity_id in marginalia["entity_ids"]), "Entity IDs should be integers"
    
    # Known entities should be canonicalized
    assert "Test Person" in marginalia["entities"], "Should have canonicalized Test Person"
    assert "Test Project" in marginalia["entities"], "Should have canonicalized Test Project"
    
    # Unknown entities should be tracked
    assert "UnknownPerson" in marginalia["unknown_entities"], "Should track UnknownPerson"
    assert "UnknownProject" in marginalia["unknown_entities"], "Should track UnknownProject"
    
    # Now test search by entity - should find our memory
    search_result = await mcp_client.call_tool("search", {
        "query": "Test Person",  # Search by entity name
        "limit": 5
    })
    
    assert not search_result.is_error
    search_text = search_result.content[0].text
    assert memory_id in search_text, "Should find memory by entity name"
    
    # Test alias resolution - search by alias should also work
    alias_search = await mcp_client.call_tool("search", {
        "query": "TP",  # Search by alias
        "limit": 5
    })
    
    assert not alias_search.is_error
    alias_text = alias_search.content[0].text
    assert memory_id in alias_text, "Should find memory by entity alias"
    
    print(f"✓ Entity ID system test passed - known entities got IDs: {marginalia['entity_ids']}")


@pytest.mark.asyncio 
async def test_retroactive_alias_resolution(mcp_client):
    """Test that adding aliases retroactively makes old memories searchable."""
    # Create a memory with an unknown entity
    test_id = datetime.now(UTC).isoformat()
    content = f"Test {test_id}: DaveSmith is working on the new feature"
    
    result = await mcp_client.call_tool("remember", {"content": content})
    response_text = result.content[0].text
    match = re.search(r"ID: ([a-f0-9-]+)", response_text)
    memory_id = match.group(1)
    
    # Verify DaveSmith is unknown
    get_result = await mcp_client.call_tool("get_memory", {"memory_id": memory_id})
    memory_text = get_result.content[0].text
    assert "DaveSmith" in memory_text, "Should contain DaveSmith"
    
    marginalia_match = re.search(r"Full marginalia: ({.*})", memory_text)
    import ast
    marginalia = ast.literal_eval(marginalia_match.group(1))
    assert "DaveSmith" in marginalia["unknown_entities"], "DaveSmith should be unknown"
    assert len(marginalia["entity_ids"]) == 0, "Should have no entity IDs yet"
    
    # Search for DaveSmith - should not find it via entity search
    # search_before = await mcp_client.call_tool("search", {
    #     "query": "David Smith",
    #     "limit": 5
    # })
# search_text_before = search_before.content[0].text
    # It might find it via text search, but not as an entity match
    
    # Now add David Smith as an entity with DaveSmith as an alias
    await mcp_client.call_tool("add_alias", {
        "canonical_name": "David Smith",
        "alias": "David Smith"  # Create the entity
    })
    await mcp_client.call_tool("add_alias", {
        "canonical_name": "David Smith",
        "alias": "Dave"
    })
    await mcp_client.call_tool("add_alias", {
        "canonical_name": "David Smith",
        "alias": "DaveSmith"
    })
    await mcp_client.call_tool("add_alias", {
        "canonical_name": "David Smith",
        "alias": "D.Smith"
    })
    
    # Search again - now it should find our memory via entity/alias match
    search_after = await mcp_client.call_tool("search", {
        "query": "David Smith",
        "limit": 5
    })
    search_text_after = search_after.content[0].text
    
    # The memory should be found and potentially ranked higher due to entity match
    # Note: We can't update the historical entity_ids without re-processing,
    # but the search should still work via alias resolution
    assert memory_id in search_text_after, "Should find memory via canonicalized entity"
    
    # Also test searching by the original alias
    alias_search = await mcp_client.call_tool("search", {
        "query": "DaveSmith",
        "limit": 5
    })
    alias_text = alias_search.content[0].text
    assert memory_id in alias_text, "Should still find by original text"
    
    print("✓ Retroactive alias resolution test passed - old memories are now findable!")
