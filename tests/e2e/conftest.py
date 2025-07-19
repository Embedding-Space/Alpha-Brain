"""Shared fixtures for E2E tests."""

import os
import pytest
from fastmcp import Client


@pytest.fixture(scope="session")
def mcp_url():
    """URL for the MCP server."""
    # Use test URL if provided, otherwise default
    return os.environ.get("MCP_TEST_URL", "http://localhost:9100/mcp/")


@pytest.fixture
async def mcp_client(mcp_url):
    """Create an MCP client for testing."""
    async with Client(mcp_url) as client:
        yield client