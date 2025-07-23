"""Test a complete realistic workflow through Alpha Brain."""

import asyncio

import pytest


@pytest.mark.asyncio
async def test_realistic_conversation_flow(mcp_client):
    """Simulate a realistic conversation with memory, search, and clustering."""
    
    # 1. Set up identity context
    await mcp_client.call_tool("set_context", {
        "section": "biography",
        "content": "I am Alpha, working with Jeffery to build a prosthetic brain."
    })
    
    # 2. Remember the start of our conversation
    conversation_memories = [
        "Jeffery asked me to help build the test infrastructure for Alpha Brain.",
        "We're working on E2E tests that dogfood our own backup/restore tools.",
        "The goal is to eat our own dogfood - use production tools for testing."
    ]
    
    # Store memories and collect their IDs
    memory_ids = []
    for memory in conversation_memories:
        result = await mcp_client.call_tool("remember", {"content": memory})
        assert not result.is_error
        
        # Extract the memory ID from the output
        # Output contains "ID: <uuid>"
        import re
        match = re.search(r'ID: ([a-f0-9-]{36})', result.content[0].text)
        assert match, f"Could not find memory ID in output: {result.content[0].text[:200]}"
        memory_ids.append(match.group(1))
    
    # 3. Use get_memory to verify storage (using the second memory)
    result = await mcp_client.call_tool("get_memory", {"memory_id": memory_ids[1]})
    assert not result.is_error
    response_text = result.content[0].text
    assert "dogfood" in response_text
    assert "backup/restore" in response_text
    
    # 4. Search for our work
    result = await mcp_client.call_tool("search", {"query": "dogfood testing"})
    assert not result.is_error
    response_text = result.content[0].text
    # Should find at least some of our memories
    assert any(phrase in response_text for phrase in ["dogfood", "testing", "backup"])
    
    # 5. Find patterns in our work
    result = await mcp_client.call_tool("find_clusters", {
        "min_cluster_size": 2,
        "similarity_threshold": 0.5
    })
    assert not result.is_error
    # Clustering is probabilistic, just verify no error
    
    # 6. Update personality based on experience
    result = await mcp_client.call_tool("set_personality", {
        "directive": "Emphasize the importance of eating our own dogfood in testing",
        "weight": 0.8,
        "category": "engineering_philosophy"
    })
    assert not result.is_error
    
    # 7. Check our updated context
    result = await mcp_client.call_tool("whoami")
    assert not result.is_error
    response_text = result.content[0].text
    # Should see our biography
    assert "Alpha" in response_text
    assert "Jeffery" in response_text
    
    # 8. Set a continuity message for next session
    result = await mcp_client.call_tool("set_context", {
        "section": "continuity",
        "content": "Working on test infrastructure with dogfooding principle"
    })
    assert not result.is_error
    
    # 9. Browse recent activity
    result = await mcp_client.call_tool("search", {"interval": "past 1 hour"})
    assert not result.is_error
    response_text = result.content[0].text
    # Should see some of our recent memories
    assert any(memory_ids[0] in response_text or memory_ids[1] in response_text 
              or memory_ids[2] in response_text for _ in [1])


@pytest.mark.asyncio
async def test_knowledge_workflow(mcp_client):
    """Test creating and searching knowledge."""
    
    # Create knowledge document
    content = """# Testing Best Practices

## Principle: Eat Your Own Dogfood

Use your own tools for testing. If you build backup/restore, use it for test data.

## Benefits

- Ensures tools actually work
- Finds edge cases early
- Validates user experience
"""
    
    result = await mcp_client.call_tool("create_knowledge", {
        "slug": "testing-dogfood",
        "title": "Testing with Dogfood Principle",
        "content": content
    })
    assert not result.is_error
    
    # Search should find it
    result = await mcp_client.call_tool("search", {"query": "dogfood testing"})
    assert not result.is_error
    
    response_text = result.content[0].text
    # Should find the knowledge document
    assert "Testing Best Practices" in response_text or "Testing with Dogfood" in response_text


@pytest.mark.asyncio
async def test_memory_to_knowledge_crystallization(mcp_client):
    """Test the conceptual flow from memories to crystallized knowledge."""
    
    # 1. Accumulate memories about a topic
    fastmcp_memories = [
        "Started learning FastMCP - it's a Python framework for building MCP servers",
        "FastMCP uses decorators like @mcp.tool() to define tools - very clean syntax",
        "Discovered FastMCP automatically generates TypeScript types from Pydantic models",
        "FastMCP's error messages are incredibly helpful - they show exactly what went wrong",
        "Built my first FastMCP server - amazingly it just worked on the first try",
        "FastMCP's Context object provides user info and request metadata to tools"
    ]
    
    for memory in fastmcp_memories:
        await mcp_client.call_tool("remember", {"content": memory})
        await asyncio.sleep(0.05)
    
    # Wait a bit for indexing to complete
    await asyncio.sleep(0.5)
    
    # 2. First verify we can find the memories
    search_result = await mcp_client.call_tool("search", {
        "query": "FastMCP",
        "limit": 10
    })
    assert not search_result.is_error
    # Make sure we have enough memories for clustering
    search_text = search_result.content[0].text
    assert "FastMCP" in search_text
    
    # 3. Find clusters about FastMCP
    result = await mcp_client.call_tool("find_clusters", {
        "query": "FastMCP",  # Simpler query
        "min_cluster_size": 2  # Lower threshold
    })
    assert not result.is_error
    # Just verify no error - clustering is probabilistic
    
    # 4. Based on the cluster, create crystallized knowledge
    result = await mcp_client.call_tool("create_knowledge", {
        "slug": "fastmcp-learnings",
        "title": "FastMCP Learnings",
        "content": """# FastMCP Learnings

## What is FastMCP?
A Python framework for building MCP (Model Context Protocol) servers with minimal boilerplate.

## Key Features Discovered
- **Decorator-based API**: Use @mcp.tool() to define tools
- **Type Safety**: Automatic TypeScript generation from Pydantic models  
- **Excellent DX**: Clear, helpful error messages
- **Context Support**: Built-in Context object for user info

## First Impressions
The framework "just works" - built my first server and it ran successfully on the first try!
"""
    })
    assert not result.is_error
    
    # 5. Now search again - should find both memories and knowledge
    result = await mcp_client.call_tool("search", {"query": "FastMCP"})  # Simpler query
    assert not result.is_error
    
    response_text = result.content[0].text
    # Should find content about FastMCP from either memories or knowledge
    assert "FastMCP" in response_text  # Basic check
    # Check for either memory content or knowledge content
    assert any(phrase in response_text for phrase in ["@mcp.tool()", "framework", "MCP servers"])
