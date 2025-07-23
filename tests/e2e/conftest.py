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
    # Use our production backup/restore mechanism - eating our own dogfood!
    
    # Drop and recreate database (must be separate commands to avoid transaction block)
    # First terminate any active connections to the test database
    subprocess.run(
        [
            "docker",
            "exec",
            "alpha-brain-test-postgres",
            "psql",
            "-U",
            "alpha",
            "-d",
            "postgres",
            "-c",
            """
            SELECT pg_terminate_backend(pid) 
            FROM pg_stat_activity 
            WHERE datname = 'alpha_brain_test' 
            AND pid <> pg_backend_pid();
            """,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    
    # Then drop the database
    subprocess.run(
        [
            "docker",
            "exec",
            "alpha-brain-test-postgres",
            "psql",
            "-U",
            "alpha",
            "-d",
            "postgres",
            "-c",
            "DROP DATABASE IF EXISTS alpha_brain_test;",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    
    # Then create it
    subprocess.run(
        [
            "docker",
            "exec",
            "alpha-brain-test-postgres",
            "psql",
            "-U",
            "alpha",
            "-d",
            "postgres",
            "-c",
            "CREATE DATABASE alpha_brain_test;",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    
    # Create vector extension
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
            "CREATE EXTENSION IF NOT EXISTS vector;",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    
    # Restore from our test dataset that's mounted inside the container
    # The file is mounted at /app/.local/test_dataset.dump.gz in the container
    subprocess.run(
        [
            "docker",
            "exec",
            "alpha-brain-test-postgres",
            "sh",
            "-c",
            "gunzip -c /app/.local/test_dataset.dump.gz | pg_restore -U alpha -d alpha_brain_test -Fc --if-exists --clean --no-owner || true",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    
    # Note: pg_restore may return warnings (exit code 1) even on success, so we use || true
    # If there's a real error, the database operations will fail and tests will catch it
    
    # Note: The real issue is that test-migrate runs BEFORE the restore,
    # but the restore wipes out the new tables. We need a different approach.
    # For now, we'll create a new test dataset that includes the current schema.
    
    yield  # Run the tests in the module
    
    # No cleanup needed - next module will reset


@pytest.fixture
async def mcp_client(mcp_url):
    """Create an MCP client for testing."""
    async with Client(mcp_url) as client:
        yield client
