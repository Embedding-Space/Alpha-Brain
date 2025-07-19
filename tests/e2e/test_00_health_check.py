"""
Health check test - runs first to ensure stack is up.

Named test_00_ to ensure it runs before other tests.
"""

import pytest


@pytest.mark.asyncio
async def test_server_is_healthy(mcp_client):
    """Test that the server is running and all services are connected."""
    # Call the health_check tool
    result = await mcp_client.call_tool("health_check", {})

    # The result is now prose, wrapped in CallToolResult
    prose_result = result.data
    assert isinstance(prose_result, str)

    # Check the response contains expected content
    assert "Alpha Brain (v1.0.0)" in prose_result
    assert "healthy" in prose_result or "partially operational" in prose_result

    # If everything is healthy, we should see this message
    if "healthy" in prose_result and "partially" not in prose_result:
        assert "All systems operational" in prose_result


@pytest.mark.asyncio
async def test_server_has_expected_tools(mcp_client):
    """Test that the server exposes the expected tools."""
    # Get list of available tools
    tools = await mcp_client.list_tools()

    # Extract tool names
    tool_names = {tool.name for tool in tools}

    # Check expected tools are present
    expected_tools = {"health_check", "remember", "search"}
    assert expected_tools.issubset(tool_names), (
        f"Missing tools: {expected_tools - tool_names}"
    )


@pytest.mark.asyncio
async def test_server_info(mcp_client):
    """Test that we can get server information."""
    # Server info is available in the initialize_result after connection
    assert mcp_client.initialize_result is not None

    # Check server info
    server_info = mcp_client.initialize_result.serverInfo
    assert server_info is not None

    # Check server name
    assert server_info.name == "Alpha Brain"

    # Check it has instructions (optional field)
    if hasattr(server_info, "instructions") and server_info.instructions:
        assert "prose-first memory system" in server_info.instructions.lower()
