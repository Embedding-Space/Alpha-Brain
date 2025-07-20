"""Shared fixtures for E2E tests."""

import os
import subprocess

import pytest
from fastmcp import Client


@pytest.fixture(scope="session")
def mcp_url():
    """URL for the MCP server."""
    # Use test URL if provided, otherwise default
    return os.environ.get("MCP_TEST_URL", "http://localhost:9100/mcp/")


@pytest.fixture(autouse=True)
def clean_database():
    """Clean the database before each test using docker exec."""
    # Run truncate commands via docker exec
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
            "TRUNCATE TABLE knowledge CASCADE; TRUNCATE TABLE memories CASCADE;",
        ],
        check=False,  # Don't fail if tables don't exist yet
        capture_output=True,
    )


@pytest.fixture
async def mcp_client(mcp_url):
    """Create an MCP client for testing."""
    async with Client(mcp_url) as client:
        yield client
