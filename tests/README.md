# Alpha Brain Test Suite

This directory contains workflow-based end-to-end tests for the Alpha Brain system.

## Test Philosophy

Alpha Brain is primarily glue code between PydanticAI, FastMCP, PostgreSQL, and other services. Instead of unit or integration tests that would mostly test mocks, we focus exclusively on **workflow-simulating E2E tests** that validate actual functionality with real (or plausible) user workflows.

## Test Organization

```
tests/
├── conftest.py          # Shared pytest configuration and fixtures
├── wait_for_mcp.py      # Utility to wait for MCP server readiness
└── e2e/                 # End-to-end tests using the full system
    ├── conftest.py      # E2E-specific fixtures (FastMCP client, etc.)
    ├── test_00_health_check.py    # Basic connectivity tests
    ├── test_memory_lifecycle.py   # Memory CRUD operations
    ├── test_exact_search.py       # Exact text search functionality
    ├── test_knowledge_e2e.py      # Knowledge system E2E tests
    └── test_knowledge_tools.py    # Knowledge MCP tools tests
```

## End-to-End Tests (`e2e/`)

Our E2E tests simulate real user workflows:
- Store memories and retrieve them later
- Create knowledge documents and update them
- Search for information across different contexts
- Handle edge cases users might encounter

These tests require all services running (database, embedding service, MCP server) and validate the complete system working together.

## Running Tests

### Run all tests:
```bash
uv run pytest
```

### Run with verbose output:
```bash
uv run pytest -xvs
```

### Run specific test file:
```bash
uv run pytest tests/e2e/test_memory_lifecycle.py -xvs
```

### Run with coverage:
```bash
uv run pytest --cov=alpha_brain --cov-report=html
```

## Test Dependencies

E2E tests require the following services running:
- PostgreSQL database
- Embedding service  
- MCP server

Use `docker compose up` to start all required services.

## Writing New Tests

When adding new E2E tests:

1. **Think in workflows**: What would a user actually do?
2. **Test through MCP tools**: Use the same interface users will use
3. **Validate outcomes**: Check that the system state matches expectations
4. **Test error cases**: What happens when things go wrong?

Example workflow test structure:
```python
@pytest.mark.asyncio
async def test_user_workflow(mcp_client):
    """Test a complete user workflow."""
    # 1. User creates initial state
    result = await mcp_client.call_tool("remember", {...})
    
    # 2. User performs operations
    search_result = await mcp_client.call_tool("search", {...})
    
    # 3. Validate the outcome matches user expectations
    assert "expected content" in search_result.content[0].text
```

## No Unit Tests

We intentionally don't have unit or integration tests because:
- Most of our code is coordinating between external services
- Testing individual functions would mostly test mocks, not real behavior
- E2E tests catch actual bugs users would experience
- The overhead of maintaining mocks doesn't provide value for glue code