"""Test basic server health and tool availability."""

import pytest


@pytest.mark.asyncio
async def test_server_health(mcp_client):
    """Is the server healthy?"""
    result = await mcp_client.call_tool("health_check", {})
    assert not result.is_error
    
    # Should indicate healthy status
    response = result.content[0].text.lower()
    assert "healthy" in response or "ok" in response or "running" in response


@pytest.mark.asyncio
async def test_expected_tools_available(mcp_client):
    """Are all our expected tools available?"""
    # Get list of available tools
    tools = await mcp_client.list_tools()
    tool_names = {tool.name for tool in tools}
    
    # Core memory tools
    assert "remember" in tool_names
    assert "search" in tool_names
    assert "get_memory" in tool_names
    
    # Knowledge tools
    assert "create_knowledge" in tool_names
    assert "get_knowledge" in tool_names
    assert "update_knowledge" in tool_names
    assert "list_knowledge" in tool_names
    
    # Entity tools
    assert "add_alias" in tool_names
    
    # Clustering tools
    assert "find_clusters" in tool_names
    assert "get_cluster" in tool_names
    
    # Identity/context tools
    assert "whoami" in tool_names
    assert "set_context" in tool_names
    assert "add_identity_fact" in tool_names
    assert "set_personality" in tool_names
    
    # Health check
    assert "health_check" in tool_names
    
    # Should have at least 15 tools
    assert len(tool_names) >= 15