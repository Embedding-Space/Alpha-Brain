"""Test that tool outputs use Jinja2 templates."""

import re

import pytest
from fastmcp import Client


@pytest.mark.asyncio
async def test_remember_uses_template(mcp_client: Client):
    """Test that remember tool uses a Jinja2 template for output."""
    # Store a simple memory
    content = "Testing template output formatting"
    result = await mcp_client.call_tool("remember", {"content": content})

    assert not result.is_error
    output = result.content[0].text

    # The output should contain key elements we expect from a template
    # We don't care about exact formatting, just that the data is there
    assert "ID:" in output or "id:" in output, "Output should contain memory ID"
    # We intentionally don't echo back the content - the user already knows what they sent

    # Verify we can extract the memory ID
    match = re.search(r"[Ii][Dd]:\s*([a-f0-9-]+)", output)
    assert match, "Should be able to extract memory ID from output"

    # The timestamp is included via 'Current time:' at the top
    assert "Current time:" in output  # Always present due to temporal grounding


@pytest.mark.asyncio
async def test_get_memory_uses_template(mcp_client: Client):
    """Test that get_memory tool uses a Jinja2 template for output."""
    # First store a memory with marginalia
    content = "Jeffery and Alpha discussed template systems for tool outputs"
    result = await mcp_client.call_tool("remember", {"content": content})
    assert not result.is_error

    # Extract memory ID
    match = re.search(r"[Ii][Dd]:\s*([a-f0-9-]+)", result.content[0].text)
    memory_id = match.group(1)

    # Get the memory back
    result = await mcp_client.call_tool("get_memory", {"memory_id": memory_id})
    assert not result.is_error
    output = result.content[0].text

    # Check that template included the expected sections
    assert memory_id in output, "Output should contain memory ID"
    assert content in output, "Output should contain content"

    # Should show some analysis data - either entities or importance
    # The template conditionally shows these based on what's in marginalia
    assert (
        "Entities:" in output
        or "entities:" in output
        or "Importance:" in output
        or "importance:" in output
    ), "Should show some marginalia data"

    # The template shows entities in the 'Entities:' line if found
    # But we can't guarantee which entities will be found, so just check the content is there


@pytest.mark.asyncio
async def test_template_files_exist():
    """Test that required output templates exist in the codebase."""
    from pathlib import Path

    # Check that template directory exists
    template_dir = (
        Path(__file__).parent.parent.parent / "src/alpha_brain/templates/outputs"
    )
    assert template_dir.exists(), f"Template directory should exist at {template_dir}"

    # Check for required templates
    required_templates = [
        "remember_output.j2",
        "get_memory_output.j2",
        "search_output.j2",
    ]

    for template_name in required_templates:
        template_path = template_dir / template_name
        assert template_path.exists(), f"Required template {template_name} not found"
