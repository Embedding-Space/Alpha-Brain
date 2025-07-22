"""Test memory clustering functionality."""

import pytest
import asyncio


@pytest.mark.asyncio
async def test_find_and_get_clusters(mcp_client):
    """Can we find clusters of related memories and retrieve them?"""
    # Create a set of related memories about a specific topic
    cat_memories = [
        "Sparkle caught a mouse this morning and left it by the door",
        "Need to buy more cat food for Sparkle, she's almost out", 
        "Sparkle has been sleeping in the sunny spot all afternoon",
        "The vet said Sparkle is in perfect health at her checkup",
        "Sparkle knocked over my coffee cup while chasing her toy"
    ]
    
    # Store all the memories
    for memory in cat_memories:
        await mcp_client.call_tool("remember", {"content": memory})
        await asyncio.sleep(0.1)  # Small delay to ensure different timestamps
    
    # Find clusters
    result = await mcp_client.call_tool("find_clusters", {
        "limit": 10,
        "min_cluster_size": 3  # At least 3 memories per cluster
    })
    assert not result.is_error
    
    response_text = result.content[0].text
    # Should find at least one cluster
    assert "Cluster" in response_text
    assert "memories" in response_text
    
    # Extract a cluster ID from the response (assuming format "Cluster N")
    import re
    cluster_match = re.search(r"Cluster (\d+)", response_text)
    assert cluster_match, "Should find at least one cluster"
    cluster_id = cluster_match.group(1)
    
    # Get the specific cluster
    result = await mcp_client.call_tool("get_cluster", {"cluster_id": cluster_id})
    assert not result.is_error
    
    response_text = result.content[0].text
    # Should see multiple cat-related memories
    sparkle_mentions = response_text.count("Sparkle")
    assert sparkle_mentions >= 3, "Cluster should contain multiple Sparkle memories"


@pytest.mark.asyncio
async def test_find_clusters_with_filters(mcp_client):
    """Can we filter clusters by entity and time?"""
    # Add an alias for testing
    await mcp_client.call_tool("add_alias", {
        "canonical_name": "Test User 42",
        "alias": "TU42"
    })
    
    # Create memories with the test entity
    test_memories = [
        "Had a meeting with TU42 about the new clustering algorithm",
        "TU42 suggested we improve the interestingness scoring",
        "Implemented the changes TU42 recommended for cluster filtering",
        "TU42 tested the new clustering and found it much better"
    ]
    
    for memory in test_memories:
        await mcp_client.call_tool("remember", {"content": memory})
    
    # Find clusters filtered by entity
    result = await mcp_client.call_tool("find_clusters", {
        "entities": ["TU42"],  # List of entities to filter by
        "limit": 5
    })
    assert not result.is_error
    
    response_text = result.content[0].text
    # Should find clusters containing our test entity
    assert "Test User 42" in response_text or "TU42" in response_text
    assert "clustering" in response_text.lower()


@pytest.mark.asyncio
async def test_find_clusters_with_query(mcp_client):
    """Can we find clusters matching a semantic query?"""
    # Create memories about different topics
    memories = [
        # Cooking memories
        "Made pasta carbonara for dinner, turned out perfectly",
        "Tried a new recipe for homemade pizza dough",
        "The farmers market had amazing fresh tomatoes today",
        # Coding memories  
        "Finally fixed that bug in the memory service",
        "Refactored the clustering algorithm for better performance",
        "Code review went well, team liked the new approach"
    ]
    
    for memory in memories:
        await mcp_client.call_tool("remember", {"content": memory})
    
    # Search for cooking-related clusters
    result = await mcp_client.call_tool("find_clusters", {
        "query": "cooking food recipes",
        "limit": 5,
        "min_cluster_size": 2
    })
    assert not result.is_error
    
    response_text = result.content[0].text
    # Should find cooking-related clusters
    assert any(word in response_text.lower() for word in ["pasta", "pizza", "tomatoes", "recipe"])
    # Probably shouldn't see coding stuff
    assert "bug" not in response_text.lower()


@pytest.mark.asyncio
async def test_cluster_interestingness_scores(mcp_client):
    """Are interestingness scores normalized to 0-1?"""
    # Create a batch of related memories
    memories = [f"Test memory {i} about clustering and scoring" for i in range(10)]
    
    for memory in memories:
        await mcp_client.call_tool("remember", {"content": memory})
    
    # Find clusters
    result = await mcp_client.call_tool("find_clusters", {"limit": 10})
    assert not result.is_error
    
    response_text = result.content[0].text
    
    # Look for interestingness scores in the output
    import re
    # Match patterns like "0.61" or "[... memories, 0.39]"
    score_matches = re.findall(r"\b(0\.\d+)\b", response_text)
    
    assert len(score_matches) > 0, "Should find interestingness scores"
    
    # All scores should be between 0 and 1
    for score_str in score_matches:
        score = float(score_str)
        assert 0.0 <= score <= 1.0, f"Score {score} should be normalized to 0-1"