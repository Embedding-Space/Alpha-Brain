"""Test entity canonicalization lifecycle."""

import re
import subprocess

import pytest
from fastmcp import Client

from alpha_brain.schema import EntityBatch


def check_table_structure():
    """Check entity table structure using docker exec."""
    # Check if table exists
    result = subprocess.run(
        [
            "docker",
            "exec",
            "alpha-brain-test-postgres",
            "psql",
            "-U",
            "alpha",
            "-d",
            "alpha_brain_test",
            "-t",
            "-c",
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'entities');",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    exists = result.stdout.strip() == "t"

    # Check GIN index
    if exists:
        result = subprocess.run(
            [
                "docker",
                "exec",
                "alpha-brain-test-postgres",
                "psql",
                "-U",
                "alpha",
                "-d",
                "alpha_brain_test",
                "-t",
                "-c",
                "SELECT EXISTS (SELECT 1 FROM pg_indexes WHERE tablename = 'entities' AND indexname = 'idx_entity_aliases');",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        has_index = result.stdout.strip() == "t"
        return exists and has_index

    return False


def insert_test_entity(canonical_name: str, aliases: list[str]):
    """Insert a test entity directly via psql."""
    # Escape single quotes in names
    canonical_name = canonical_name.replace("'", "''")
    aliases = [a.replace("'", "''") for a in aliases]

    aliases_str = "{" + ",".join(f'"{a}"' for a in aliases) + "}"
    cmd = f"INSERT INTO entities (canonical_name, aliases, created_at, updated_at) VALUES ('{canonical_name}', '{aliases_str}', NOW(), NOW()) ON CONFLICT DO NOTHING;"

    subprocess.run(
        [
            "docker",
            "exec",
            "alpha-brain-test-postgres",
            "psql",
            "-U",
            "alpha",
            "-d",
            "alpha_brain_test",
            "-c",
            cmd,
        ],
        capture_output=True,
        check=True,
    )


@pytest.mark.asyncio
async def test_entity_table_exists():
    """Test that the entities table is created with proper structure."""
    # Wait a moment for database init
    import asyncio

    await asyncio.sleep(1.0)

    assert check_table_structure(), "Entity table or GIN index not found"


@pytest.mark.asyncio
async def test_entity_operations_via_mcp(mcp_client: Client):
    """Test entity operations through memory storage."""
    # First, manually insert some test entities
    insert_test_entity("Test Person E2E", ["TPE2E", "Test P"])
    insert_test_entity("Test Project Alpha", ["TPA", "TestProj"])

    # Store a memory mentioning these entities
    content = "Had a meeting with TPE2E about Test Project Alpha. Also mentioned Unknown Corp."

    result = await mcp_client.call_tool("remember", {"content": content})
    assert not result.is_error

    # Extract memory ID from response
    response_text = result.content[0].text
    match = re.search(r"ID: ([a-f0-9-]+)", response_text)
    assert match
    memory_id = match.group(1)

    # Get the memory to check marginalia
    result = await mcp_client.call_tool("get_memory", {"memory_id": memory_id})
    assert not result.is_error

    memory_text = result.content[0].text

    # Check that entities were canonicalized (order doesn't matter)
    assert "Test Person E2E" in memory_text
    assert "Test Project Alpha" in memory_text
    assert "Entities:" in memory_text
    # Unknown entities might not be shown if empty
    assert (
        "Unknown entities: Unknown Corp" in memory_text
        or "Unknown entities:" not in memory_text
    )


@pytest.mark.asyncio
async def test_memory_with_all_unknown_entities(mcp_client: Client):
    """Test memory with entities that can't be canonicalized."""
    # Store a memory with all unknown entities
    content = "RandomPerson discussed UnknownProject using MysteryTech."

    result = await mcp_client.call_tool("remember", {"content": content})
    assert not result.is_error

    # Extract memory ID
    response_text = result.content[0].text
    match = re.search(r"ID: ([a-f0-9-]+)", response_text)
    assert match
    memory_id = match.group(1)

    # Get the memory
    result = await mcp_client.call_tool("get_memory", {"memory_id": memory_id})
    assert not result.is_error

    memory_text = result.content[0].text

    # Should show unknown entities
    assert "Unknown entities:" in memory_text
    # Check for at least some of the entities
    assert (
        "RandomPerson" in memory_text
        or "UnknownProject" in memory_text
        or "MysteryTech" in memory_text
    )


@pytest.mark.asyncio
async def test_canonicalization_with_aliases(mcp_client: Client):
    """Test that aliases properly resolve to canonical names."""
    # Insert entity with multiple aliases
    insert_test_entity("Sparkplug Louise Mittenhaver", ["Sparkle", "Sparks"])

    # Store memories using different aliases
    memories = [
        "Sparkle knocked over my coffee again.",
        "Sparks seems unusually well-behaved today.",
    ]

    memory_ids = []
    for content in memories:
        result = await mcp_client.call_tool("remember", {"content": content})
        assert not result.is_error

        # Extract memory ID
        match = re.search(r"ID: ([a-f0-9-]+)", result.content[0].text)
        assert match
        memory_ids.append(match.group(1))

    # Check that all memories canonicalized to the same entity
    for memory_id in memory_ids:
        result = await mcp_client.call_tool("get_memory", {"memory_id": memory_id})
        assert not result.is_error

        memory_text = result.content[0].text
        assert "Entities: Sparkplug Louise Mittenhaver" in memory_text


@pytest.mark.asyncio
async def test_entity_batch_validation():
    """Test EntityBatch schema validation."""
    # Valid batch
    valid_data = {
        "version": "1.0",
        "entities": [{"canonical": "Valid Entity", "aliases": ["VE", "Valid"]}],
    }
    batch = EntityBatch(**valid_data)
    assert len(batch.entities) == 1

    # Test various invalid scenarios
    with pytest.raises(ValueError):
        # Missing version
        EntityBatch(entities=[{"canonical": "Test", "aliases": []}])

    with pytest.raises(ValueError):
        # Invalid entity structure
        EntityBatch(version="1.0", entities=[{"name": "Wrong Field"}])


@pytest.mark.asyncio
async def test_search_with_canonicalized_entities(mcp_client: Client):
    """Test that search works with canonicalized entities."""
    # Insert a known entity
    insert_test_entity("Jeffery Harrell", ["Jeffery", "Jeff"])

    # Store a memory
    content = "Jeff and I discussed the new architecture for Alpha Brain."
    result = await mcp_client.call_tool("remember", {"content": content})
    assert not result.is_error

    # Search for the canonical name
    result = await mcp_client.call_tool(
        "search", {"query": "Jeffery Harrell architecture", "search_type": "semantic"}
    )
    assert not result.is_error

    search_text = result.content[0].text
    assert "Jeff and I discussed" in search_text
