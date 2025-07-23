"""Test knowledge document management."""

import pytest


@pytest.mark.asyncio
async def test_create_and_retrieve_knowledge(mcp_client):
    """Can we create a knowledge document and get it back?"""
    # Create a knowledge document
    slug = "test-fastmcp-guide"
    content = """# FastMCP Guide

## Overview
FastMCP is a Python framework for building MCP servers.

## Key Features
- Fast and simple
- Type-safe with Pydantic
- Great error messages

## Code Example
```python
from fastmcp import FastMCP

mcp = FastMCP("My Server")

@mcp.tool()
def my_tool(text: str) -> str:
    return f"You said: {text}"
```
"""
    
    result = await mcp_client.call_tool("create_knowledge", {
        "slug": slug,
        "title": "FastMCP Guide",
        "content": content
    })
    assert not result.is_error
    # Check that the document was created - look for slug confirmation
    response_text = result.content[0].text
    assert slug in response_text
    assert "FastMCP Guide" in response_text
    
    # Retrieve the document
    result = await mcp_client.call_tool("get_knowledge", {"slug": slug})
    assert not result.is_error
    
    response_text = result.content[0].text
    # Check the content is there
    assert "FastMCP Guide" in response_text
    assert "Fast and simple" in response_text
    assert "You said:" in response_text
    
    # Check that it parsed the structure
    assert "## Overview" in response_text
    assert "## Key Features" in response_text
    assert "## Code Example" in response_text


@pytest.mark.asyncio
async def test_update_knowledge(mcp_client):
    """Can we update an existing knowledge document?"""
    slug = "test-update-doc"
    
    # Create initial version
    await mcp_client.call_tool("create_knowledge", {
        "slug": slug,
        "title": "Initial Version",
        "content": "# Initial Version\n\nThis is version 1."
    })
    
    # Update it
    result = await mcp_client.call_tool("update_knowledge", {
        "slug": slug,
        "title": "Updated Version",
        "content": "# Updated Version\n\nThis is version 2 with more content!"
    })
    assert not result.is_error
    # Just verify no error - we'll check the actual update worked below
    
    # Verify the update
    result = await mcp_client.call_tool("get_knowledge", {"slug": slug})
    response_text = result.content[0].text
    
    assert "Updated Version" in response_text
    assert "version 2" in response_text
    assert "Initial Version" not in response_text  # Old content is gone


@pytest.mark.asyncio
async def test_get_knowledge_section(mcp_client):
    """Can we retrieve a specific section of a knowledge document?"""
    slug = "test-sections"
    content = """# Document with Sections

## Introduction
This is the intro.

## Main Content
This is the main section with important info.

### Subsection
Details here.

## Conclusion  
Final thoughts.
"""
    
    # Create the document
    await mcp_client.call_tool("create_knowledge", {
        "slug": slug,
        "title": "Document with Sections",
        "content": content
    })
    
    # Get a specific section
    result = await mcp_client.call_tool("get_knowledge", {
        "slug": slug,
        "section": "main-content"  # Sections are slugified
    })
    assert not result.is_error
    
    response_text = result.content[0].text
    # Should have the requested section
    assert "Main Content" in response_text
    assert "important info" in response_text
    
    # Should NOT include other sections (section retrieval is specific)
    assert "Introduction" not in response_text
    assert "Conclusion" not in response_text
    assert "Subsection" not in response_text  # Subsections are separate sections


@pytest.mark.asyncio
async def test_list_knowledge(mcp_client):
    """Can we list all knowledge documents?"""
    # Create a couple of test documents
    await mcp_client.call_tool("create_knowledge", {
        "slug": "test-alpha-guide", 
        "title": "Alpha Guide",
        "content": "# Alpha Guide\n\nHow to work with Alpha."
    })
    
    await mcp_client.call_tool("create_knowledge", {
        "slug": "test-memory-patterns",
        "title": "Memory Patterns",
        "content": "# Memory Patterns\n\nBest practices for memory formation."
    })
    
    # List all documents
    result = await mcp_client.call_tool("list_knowledge", {})
    assert not result.is_error
    
    response_text = result.content[0].text
    # Should see both documents
    assert "test-alpha-guide" in response_text
    assert "test-memory-patterns" in response_text
    assert "Alpha Guide" in response_text
    assert "Memory Patterns" in response_text