#!/usr/bin/env python
"""Prototype crystallization by finding high-similarity memories and analyzing them with Helper."""

import asyncio
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import asyncpg
import json
from collections import defaultdict
import matplotlib.pyplot as plt
from alpha_brain.memory_helper import MemoryHelper
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.settings import ModelSettings
import os

async def analyze_distribution():
    # Connect to the database
    conn = await asyncpg.connect('postgresql://alpha:brain@localhost/alpha_brain')
    
    # Get all memories with embeddings
    query = """
    SELECT id, content, semantic_embedding, created_at
    FROM memories
    ORDER BY created_at DESC
    """
    
    rows = await conn.fetch(query)
    print(f"Found {len(rows)} memories")
    
    # Extract embeddings
    memories = []
    embeddings = []
    
    for row in rows:
        memories.append({
            'id': row['id'],
            'content': row['content'],
            'created_at': row['created_at']
        })
        # Parse embedding
        emb_str = str(row['semantic_embedding'])
        emb_vec = json.loads(emb_str)
        embeddings.append(np.array(emb_vec))
    
    embeddings = np.array(embeddings)
    
    # Calculate all pairwise similarities
    print("\n=== SIMILARITY DISTRIBUTION ANALYSIS ===")
    similarities = cosine_similarity(embeddings)
    
    # Get upper triangle (avoid counting pairs twice)
    upper_triangle = np.triu(similarities, k=1)
    all_sims = upper_triangle[upper_triangle > 0].flatten()
    
    print(f"Total unique pairs: {len(all_sims)}")
    print(f"Mean similarity: {all_sims.mean():.3f}")
    print(f"Median similarity: {np.median(all_sims):.3f}")
    print(f"Std deviation: {all_sims.std():.3f}")
    print(f"25th percentile: {np.percentile(all_sims, 25):.3f}")
    print(f"75th percentile: {np.percentile(all_sims, 75):.3f}")
    print(f"95th percentile: {np.percentile(all_sims, 95):.3f}")
    
    # Plot histogram
    plt.figure(figsize=(10, 6))
    plt.hist(all_sims, bins=50, alpha=0.7, edgecolor='black')
    plt.axvline(all_sims.mean(), color='red', linestyle='--', label=f'Mean: {all_sims.mean():.3f}')
    plt.axvline(np.median(all_sims), color='green', linestyle='--', label=f'Median: {np.median(all_sims):.3f}')
    plt.xlabel('Cosine Similarity')
    plt.ylabel('Count')
    plt.title('Distribution of Memory Similarities')
    plt.legend()
    plt.savefig('similarity_distribution.png')
    print("\nSaved distribution plot to similarity_distribution.png")
    
    # Try different thresholds to find the sweet spot
    for threshold in [0.675, 0.650, 0.625]:
        print(f"\n=== CLUSTERS WITH THRESHOLD {threshold} ===")
        clusters = defaultdict(list)
        
        # For each memory, find all memories with similarity > threshold
        for i in range(len(memories)):
            high_sim_indices = np.where(similarities[i] > threshold)[0]
            if len(high_sim_indices) > 1:  # More than just itself
                # Use the memory as its own cluster key
                cluster_key = i
                clusters[cluster_key] = high_sim_indices.tolist()
        
        # Merge overlapping clusters
        merged_clusters = []
        processed = set()
        
        for key, indices in clusters.items():
            if key in processed:
                continue
            
            # Find all connected memories
            cluster = set(indices)
            to_check = list(indices)
            
            while to_check:
                idx = to_check.pop()
                if idx in clusters and idx not in processed:
                    new_indices = clusters[idx]
                    for new_idx in new_indices:
                        if new_idx not in cluster:
                            cluster.add(new_idx)
                            to_check.append(new_idx)
                    processed.add(idx)
            
            if len(cluster) >= 3:  # Only keep clusters with 3+ memories
                merged_clusters.append(sorted(list(cluster)))
        
        # Remove duplicate clusters
        unique_clusters = []
        seen = set()
        for cluster in merged_clusters:
            cluster_tuple = tuple(cluster)
            if cluster_tuple not in seen:
                seen.add(cluster_tuple)
                unique_clusters.append(cluster)
        
        print(f"Found {len(unique_clusters)} clusters")
        
        # Analyze the largest cluster at this threshold
        if unique_clusters:
            largest_cluster = max(unique_clusters, key=len)
            print(f"Largest cluster has {len(largest_cluster)} memories")
            
            # Analyze all thresholds
            if True:
                print(f"\nAnalyzing largest cluster at threshold {threshold}...")
                
                # Set up Helper for analysis if not already done
                if threshold == 0.675:  # First threshold
                    os.environ["OPENAI_BASE_URL"] = "http://localhost:11434/v1"
                    os.environ["OPENAI_API_KEY"] = "not-needed"
                    
                    # Create a simple agent for crystallization analysis
                    model = OpenAIModel("gemma3:4b", settings=ModelSettings(temperature=0.3))
                    crystallization_agent = Agent(
                        model=model,
                        system_prompt="You are Helper, an AI assistant analyzing memories to find patterns and extract knowledge."
                    )
                
                # Get the memories
                cluster_memories = [memories[idx] for idx in largest_cluster]
                
                # Show preview
                print(f"\nCluster preview ({len(cluster_memories)} memories):")
                for j, mem in enumerate(cluster_memories[:5]):
                    print(f"  {j+1}. {mem['content'][:80]}...")
                if len(cluster_memories) > 5:
                    print(f"  ... and {len(cluster_memories) - 5} more")
                
                # Calculate average similarity within cluster
                cluster_sims = []
                for j, idx1 in enumerate(largest_cluster):
                    for idx2 in largest_cluster[j+1:]:
                        cluster_sims.append(similarities[idx1, idx2])
                avg_sim = np.mean(cluster_sims) if cluster_sims else 0
                print(f"\nAverage similarity within cluster: {avg_sim:.3f}")
                
                # Prepare memories for Helper
                memory_texts = [f"Memory {j+1}: {mem['content']}" for j, mem in enumerate(cluster_memories[:10])]  # Limit to 10 for context
                prompt = f"""Analyze these {min(len(cluster_memories), 10)} memories from a cluster of {len(cluster_memories)} total memories with average similarity {avg_sim:.3f}.

Note: At this threshold ({threshold}), memories are {"tightly" if threshold >= 0.675 else "moderately" if threshold >= 0.625 else "loosely"} related.

1. What do these memories have in common?
2. Is there a coherent pattern or theme, or are they just loosely related?
3. Would this cluster benefit from being broken into sub-clusters?

Memories:
{chr(10).join(memory_texts)}
"""
                
                try:
                    result = await crystallization_agent.run(prompt)
                    analysis = result.output
                    print(f"\nHelper's Analysis:")
                    print(f"{'-' * 60}")
                    for line in str(analysis).split('\n'):
                        if line.strip():
                            print(f"{line}")
                    print(f"{'-' * 60}")
                except Exception as e:
                    print(f"Error calling Helper: {e}")
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(analyze_distribution())