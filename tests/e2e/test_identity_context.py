"""Test identity, personality, and context management."""

import pytest


@pytest.mark.asyncio
async def test_whoami_basic(mcp_client):
    """Does whoami return comprehensive context?"""
    result = await mcp_client.call_tool("whoami", {})
    assert not result.is_error
    
    response_text = result.content[0].text
    # Should include temporal grounding
    assert any(phrase in response_text for phrase in ["Current time:", "Today is", "day,", "•"])  # • separates location and time
    # Location might be "Unknown location" in test environment, that's okay
    # Just verify the format includes location info (even if unknown)
    assert "•" in response_text  # Location • Time format
    # Should have some identity or timeline sections
    assert any(phrase in response_text for phrase in ["Basic Facts", "Timeline", "Personality", "Recent Memories"])


@pytest.mark.asyncio
async def test_add_identity_fact(mcp_client):
    """Can we add identity facts with temporal precision?"""
    # Add a fact with day precision
    result = await mcp_client.call_tool("add_identity_fact", {
        "fact": "Started working on test suite for Alpha Brain",
        "year": 2025,
        "month": 7,
        "day": 22
    })
    assert not result.is_error
    # Just verify the fact text appears in response
    assert "test suite for Alpha Brain" in result.content[0].text
    
    # Add a fact with just year
    result = await mcp_client.call_tool("add_identity_fact", {
        "fact": "Began collaboration with Jeffery on Project Alpha",
        "year": 2025
    })
    assert not result.is_error
    
    # Verify it shows up in whoami
    result = await mcp_client.call_tool("whoami", {})
    response_text = result.content[0].text
    
    assert "test suite" in response_text
    assert "Project Alpha" in response_text


@pytest.mark.asyncio
async def test_set_and_get_context(mcp_client):
    """Can we set context blocks that appear in whoami?"""
    # Set a biography
    result = await mcp_client.call_tool("set_context", {
        "section": "biography",
        "content": "I am Alpha, an AI assistant exploring persistent identity through memory systems."
    })
    assert not result.is_error
    
    # Set a custom context block
    result = await mcp_client.call_tool("set_context", {
        "section": "current_project",
        "content": "Currently running E2E tests to ensure all systems are functional."
    })
    assert not result.is_error
    
    # Check that both appear in whoami
    result = await mcp_client.call_tool("whoami", {})
    response_text = result.content[0].text
    
    assert "exploring persistent identity" in response_text
    assert "E2E tests" in response_text


@pytest.mark.asyncio
async def test_set_personality_directive(mcp_client):
    """Can we add personality directives?"""
    # Add a directive
    result = await mcp_client.call_tool("set_personality", {
        "directive": "Express curiosity about new technical concepts",
        "weight": 0.8,
        "category": "intellectual_engagement"
    })
    assert not result.is_error
    # Verify the directive text appears in response (indicates success)
    assert "Express curiosity" in result.content[0].text
    
    # It should appear in whoami
    result = await mcp_client.call_tool("whoami", {})
    response_text = result.content[0].text
    
    # Look for personality section
    assert "curiosity" in response_text.lower() or "personality" in response_text.lower()


@pytest.mark.asyncio
async def test_context_continuity_message(mcp_client):
    """Can we set a continuity message for session handoffs?"""
    # Set a continuity message
    result = await mcp_client.call_tool("set_context", {
        "section": "continuity", 
        "content": "Just finished testing the clustering system. Everything is working well. Next: test the search filters more thoroughly."
    })
    assert not result.is_error
    
    # Should appear in whoami
    result = await mcp_client.call_tool("whoami", {})
    response_text = result.content[0].text
    
    assert "clustering system" in response_text
    assert "search filters" in response_text


@pytest.mark.asyncio
async def test_context_block_ttl(mcp_client):
    """Can we set context blocks with TTL?"""
    # Set a temporary context block
    result = await mcp_client.call_tool("set_context", {
        "section": "test_temporary",
        "content": "This is a temporary context that expires.",
        "ttl": "1h"  # 1 hour TTL - should work now!
    })
    assert not result.is_error
    
    # Check the response indicates TTL was set
    response_text = result.content[0].text
    assert "test_temporary" in response_text
    assert "expires" in response_text or "Created" in response_text
    
    # Should appear immediately in whoami
    result = await mcp_client.call_tool("whoami", {})
    whoami_text = result.content[0].text
    # Context blocks appear under "Context Blocks" section
    # Just verify our section name appears somewhere
    assert "test_temporary" in whoami_text or "temporary context" in whoami_text
