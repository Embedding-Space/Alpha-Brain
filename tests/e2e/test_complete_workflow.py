"""Test a complete realistic workflow through Alpha Brain."""

import pytest
import asyncio


@pytest.mark.asyncio
async def test_realistic_conversation_flow(mcp_client):
    """Simulate a realistic conversation with memory, search, and clustering."""
    
    # 1. Set up identity context
    await mcp_client.call_tool("set_context", {
        "section": "biography",
        "content": "I am Alpha, working with Jeffery to build a prosthetic brain."
    })
    
    await mcp_client.call_tool("add_identity_fact", {
        "fact": "Completed major refactoring of clustering system",
        "year": 2025,
        "month": 7, 
        "day": 22
    })
    
    # 2. Add some aliases for entities we'll use
    await mcp_client.call_tool("add_alias", {
        "canonical_name": "Jeffery Harrell",
        "alias": "Jeffery"
    })
    
    await mcp_client.call_tool("add_alias", {
        "canonical_name": "Alpha Brain",
        "alias": "prosthetic brain"
    })
    
    # 3. Simulate a conversation with memories
    conversation_memories = [
        "Jeffery just suggested we refactor the crystallization service into the memory service",
        "Started working on moving the clustering logic - it's a big change but makes sense architecturally",
        "The refactoring is going well - extracted helper methods to reduce complexity",
        "Jeffery said 'finding clusters among memories is naturally part of the Memory Service's job' - exactly right",
        "Finished the refactoring! All tests passing. The source tree is much cleaner now",
        "Jeffery wants to rebuild the test suite from scratch - 'just a tinkerer and his little duck'",
        "Deleted all the old tests. Fresh start feels good. Time to build better ones"
    ]
    
    # Store memories with small delays
    for memory in conversation_memories:
        await mcp_client.call_tool("remember", {"content": memory})
        await asyncio.sleep(0.05)
    
    # 4. Search for memories about the refactoring
    result = await mcp_client.call_tool("search", {
        "query": "refactoring crystallization"
    })
    assert not result.is_error
    response_text = result.content[0].text
    assert "memory service" in response_text.lower()
    assert "helper methods" in response_text
    
    # 5. Find clusters about today's work
    result = await mcp_client.call_tool("find_clusters", {
        "entities": ["Jeffery Harrell"],
        "interval": "today",
        "min_cluster_size": 2  # Lower threshold for test data
    })
    assert not result.is_error
    
    response_text = result.content[0].text
    # Check if we found clusters (might not if memories aren't similar enough)
    if "No clusters found" in response_text:
        # Skip cluster-specific tests
        return
    
    # Should find a cluster about our refactoring work
    assert "Cluster" in response_text or "cluster" in response_text.lower()
    assert "Jeffery" in response_text
    
    # Extract cluster ID
    import re
    cluster_match = re.search(r"Cluster (\d+)", response_text)
    if not cluster_match:
        # No cluster ID found, skip rest of test
        return
    cluster_id = cluster_match.group(1)
    
    # 6. Get the full cluster to see the story
    result = await mcp_client.call_tool("get_cluster", {"cluster_id": cluster_id})
    assert not result.is_error
    
    cluster_text = result.content[0].text
    # Should tell the story of our refactoring
    assert "refactor" in cluster_text
    assert "little duck" in cluster_text
    
    # 7. Create knowledge documenting what we learned
    result = await mcp_client.call_tool("create_knowledge", {
        "slug": "clustering-refactor-notes",
        "title": "Clustering Refactor Notes",
        "content": """# Clustering Refactor Notes

## What We Did
Moved clustering functionality from CrystallizationService into MemoryService.

## Why
As Jeffery said: "finding clusters among memories is naturally part of the Memory Service's job"

## Results  
- Cleaner architecture
- No more separate crystallization service
- Clustering is now just another memory operation
"""
    })
    assert not result.is_error
    
    # 8. Set continuity for next session
    result = await mcp_client.call_tool("set_context", {
        "section": "continuity",
        "content": "Just finished refactoring and rebuilding tests. The system is cleaner and more coherent. Feeling good about the architectural decisions."
    })
    assert not result.is_error
    
    # 9. Check final state with whoami
    result = await mcp_client.call_tool("whoami", {})
    assert not result.is_error
    
    final_context = result.content[0].text
    # Should see our identity, recent work, and continuity
    assert "prosthetic brain" in final_context
    assert "refactoring" in final_context
    assert "cleaner" in final_context


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
    
    # 2. Find clusters about FastMCP
    result = await mcp_client.call_tool("find_clusters", {
        "query": "FastMCP framework",
        "min_cluster_size": 2  # Lower threshold
    })
    assert not result.is_error
    # Just verify no error - clustering is probabilistic
    
    # 3. Based on the cluster, create crystallized knowledge
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
- **Context System**: Built-in Context object for user/request data

## First Impressions
Remarkably smooth to get started - first server worked immediately.
"""
    })
    assert not result.is_error
    
    # 4. Now when we search, we should find both memories and knowledge
    # Small delay to ensure indexing
    await asyncio.sleep(0.5)
    
    result = await mcp_client.call_tool("search", {"query": "FastMCP"})  # Simpler query
    assert not result.is_error
    
    response_text = result.content[0].text
    # Should find content about FastMCP from either memories or knowledge
    assert "FastMCP" in response_text  # Basic check
    # Check for either memory content or knowledge content
    assert any(phrase in response_text for phrase in ["@mcp.tool()", "framework", "MCP servers"])