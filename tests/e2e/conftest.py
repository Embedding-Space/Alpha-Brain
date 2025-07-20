"""Shared fixtures for E2E tests."""

import os
import subprocess

import pytest
from fastmcp import Client


@pytest.fixture(scope="session")
def mcp_url():
    """URL for the MCP server."""
    # Use test URL if provided, otherwise default
    return os.environ.get("MCP_TEST_URL", "http://localhost:9101/mcp/")


@pytest.fixture(scope="module", autouse=True)
def reset_test_database():
    """Reset the database to known state at the start of each test module."""
    # Reload the test dataset from the dump file
    dump_file = "/docker-entrypoint-initdb.d/10-test-data.sql"
    
    # First truncate existing data
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
            "TRUNCATE TABLE knowledge CASCADE; TRUNCATE TABLE memories CASCADE; TRUNCATE TABLE entities CASCADE;",
        ],
        check=False,
        capture_output=True,
    )
    
    # Then reload from dump (which now contains clean INSERT statements)
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
            "-f",
            dump_file,
        ],
        check=False,
        capture_output=True,
    )
    
    yield  # Run the tests in the module
    
    # No cleanup needed - next module will reset


@pytest.fixture
async def mcp_client(mcp_url):
    """Create an MCP client for testing."""
    async with Client(mcp_url) as client:
        yield client
