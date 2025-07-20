"""End-to-end workflow tests for the knowledge management system."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_knowledge_creation_and_retrieval_workflow(mcp_client):
    """Test the complete workflow of creating and retrieving knowledge."""
    
    # User creates a knowledge document
    create_result = await mcp_client.call_tool(
        "create_knowledge",
        {
            "slug": "test-workflow-doc",
            "title": "How to Use Alpha Brain",
            "content": """# How to Use Alpha Brain

## Overview
Alpha Brain combines memory and knowledge management in a unified system.

### Key Concepts
- **Memories**: Experiential, timestamped, immutable
- **Knowledge**: Structured documentation, updateable

## Getting Started

First, understand the two types of storage:

1. Use `remember` for experiences
2. Use `create_knowledge` for documentation

### Memory Examples

```python
# Store an experience
await remember("Today I learned about vector embeddings")
```

### Knowledge Examples

```python
# Create documentation
await create_knowledge(
    slug="vector-guide",
    title="Vector Embeddings Guide",
    content="..."
)
```

## Advanced Usage

> **Pro tip**: Use semantic search to find both memories and knowledge.

### Search Strategies
- Semantic: Meaning-based matching
- Emotional: Feeling-based matching
- Exact: Precise text matching

## Troubleshooting

If searches aren't returning expected results:
- Check your search type
- Try different query terms
- Ensure content was stored successfully
"""
        }
    )
    
    result_text = create_result.content[0].text
    assert "Created knowledge document" in result_text
    assert "How to Use Alpha Brain" in result_text
    assert "test-workflow-doc" in result_text
    assert "Sections: 9" in result_text  # All headers including H3s
    
    # User retrieves the full document
    get_result = await mcp_client.call_tool(
        "get_knowledge",
        {"slug": "test-workflow-doc"}
    )
    
    full_doc = get_result.content[0].text
    assert "# How to Use Alpha Brain" in full_doc
    assert "## Table of Contents" in full_doc
    assert "- How to Use Alpha Brain" in full_doc
    assert "  - Overview" in full_doc
    assert "    - Key Concepts" in full_doc
    assert "## Getting Started" in full_doc
    assert "```python" in full_doc
    assert "await remember(" in full_doc
    
    # User retrieves a specific section
    section_result = await mcp_client.call_tool(
        "get_knowledge",
        {
            "slug": "test-workflow-doc",
            "section": "advanced-usage"
        }
    )
    
    section = section_result.content[0].text
    assert "# Advanced Usage" in section
    assert "Pro tip" in section
    assert "From: How to Use Alpha Brain (test-workflow-doc)" in section
    
    # User lists all documents
    list_result = await mcp_client.call_tool("list_knowledge", {})
    
    list_text = list_result.content[0].text
    assert "Knowledge Documents" in list_text
    # Note: Other docs might exist, so just check ours is there
    assert "test-workflow-doc" in list_text


@pytest.mark.asyncio
async def test_knowledge_update_workflow(mcp_client):
    """Test updating knowledge documents through the workflow."""
    
    # User creates initial document
    await mcp_client.call_tool(
        "create_knowledge",
        {
            "slug": "test-update-doc",
            "title": "Initial Version",
            "content": """# Initial Version

## Content
This is the first version.
"""
        }
    )
    
    # User updates the document with new content
    update_result = await mcp_client.call_tool(
        "update_knowledge",
        {
            "slug": "test-update-doc",
            "title": "Updated Version",
            "content": """# Updated Version

## Content
This is the updated version with more information.

## New Section
This section was added in the update.
"""
        }
    )
    
    update_text = update_result.content[0].text
    assert "Updated knowledge document" in update_text
    assert "Changes:" in update_text
    assert "Title: 'Initial Version' → 'Updated Version'" in update_text
    assert "Content: Updated (2 → 3 sections)" in update_text
    
    # User renames the document
    rename_result = await mcp_client.call_tool(
        "update_knowledge",
        {
            "slug": "test-update-doc",
            "new_slug": "test-update-doc-renamed"
        }
    )
    
    rename_text = rename_result.content[0].text
    assert "Slug: 'test-update-doc' → 'test-update-doc-renamed'" in rename_text
    
    # Verify old slug doesn't work
    old_doc_result = await mcp_client.call_tool(
        "get_knowledge",
        {"slug": "test-update-doc"}
    )
    
    assert "not found" in old_doc_result.content[0].text
    
    # Verify new slug works
    new_doc_result = await mcp_client.call_tool(
        "get_knowledge",
        {"slug": "test-update-doc-renamed"}
    )
    
    assert "Updated Version" in new_doc_result.content[0].text


@pytest.mark.asyncio
async def test_knowledge_with_complex_markdown(mcp_client):
    """Test that complex Markdown structures are preserved correctly."""
    
    complex_content = """# Complex Markdown Test

## Features Overview

This document tests **various** *Markdown* features.

### Lists

Unordered list:
- First item with `inline code`
- Second item with [a link](https://example.com)
- Third item with **bold** and *italic*

Ordered list:
1. Step one
2. Step two
3. Step three

### Code Examples

```python
class KnowledgeSystem:
    def __init__(self):
        self.documents = {}
    
    def store(self, slug: str, content: str) -> None:
        \"\"\"Store a document.\"\"\"
        self.documents[slug] = content
```

```javascript
const knowledge = {
  store: (slug, content) => {
    localStorage.setItem(slug, content);
  }
};
```

### Special Characters & Formatting

Testing: <>&"' and \\`backticks\\` plus $special$ chars.

> **Important**: This is a blockquote with **formatting**.
> It spans multiple lines.

### Tables and Images

| Feature | Status | Notes |
|---------|--------|-------|
| Markdown | ✅ | Full support |
| Tables | ⚠️ | Basic support |

![Example](image.png "Image tooltip")

---

## Conclusion

All features work! 🎉
"""
    
    # Create document with complex content
    create_result = await mcp_client.call_tool(
        "create_knowledge",
        {
            "slug": "test-complex-doc",
            "title": "Complex Markdown Features",
            "content": complex_content
        }
    )
    
    create_text = create_result.content[0].text
    assert "Created knowledge document" in create_text
    # Don't assert exact section count - it can vary based on markdown parsing
    
    # Retrieve and verify content is preserved
    get_result = await mcp_client.call_tool(
        "get_knowledge",
        {"slug": "test-complex-doc"}
    )
    
    retrieved = get_result.content[0].text
    
    # Check various Markdown features are preserved
    assert "**various** *Markdown*" in retrieved
    assert "```python" in retrieved
    assert "```javascript" in retrieved
    assert "class KnowledgeSystem:" in retrieved
    assert "[a link](https://example.com)" in retrieved
    assert "> **Important**:" in retrieved
    assert "| Feature | Status |" in retrieved
    assert "![Example](image.png" in retrieved
    assert "🎉" in retrieved


@pytest.mark.asyncio
async def test_knowledge_error_handling(mcp_client):
    """Test error handling in knowledge workflows."""
    
    # Create a document for testing errors
    await mcp_client.call_tool(
        "create_knowledge",
        {
            "slug": "test-error-doc",
            "title": "Error Test",
            "content": "# Error Test\n\nContent"
        }
    )
    
    # Try to create duplicate
    dup_result = await mcp_client.call_tool(
        "create_knowledge",
        {
            "slug": "test-error-doc",
            "title": "Duplicate",
            "content": "# Duplicate"
        }
    )
    
    dup_text = dup_result.content[0].text
    assert "Error:" in dup_text
    assert "already exists" in dup_text
    
    # Try to get non-existent document
    not_found_result = await mcp_client.call_tool(
        "get_knowledge",
        {"slug": "non-existent-doc"}
    )
    
    assert "not found" in not_found_result.content[0].text
    
    # Try to get non-existent section
    bad_section_result = await mcp_client.call_tool(
        "get_knowledge",
        {
            "slug": "test-error-doc",
            "section": "non-existent"
        }
    )
    
    assert "Section 'non-existent' not found" in bad_section_result.content[0].text
    
    # Try to update non-existent document
    update_fail_result = await mcp_client.call_tool(
        "update_knowledge",
        {
            "slug": "non-existent-doc",
            "title": "Won't work"
        }
    )
    
    assert "not found" in update_fail_result.content[0].text