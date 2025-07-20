#!/usr/bin/env python3
"""Test the 7D emotion embeddings with splash functionality."""

import asyncio
import numpy as np
from transformers import pipeline


def extract_emotion_vector(emotion_results):
    """Extract 7D emotion vector from classifier results."""
    # Order: anger, disgust, fear, joy, neutral, sadness, surprise
    emotion_order = ['anger', 'disgust', 'fear', 'joy', 'neutral', 'sadness', 'surprise']
    scores = [next(r['score'] for r in emotion_results if r['label'] == emotion) for emotion in emotion_order]
    return np.array(scores)


def cosine_similarity(a, b):
    """Calculate cosine similarity between two vectors."""
    # Ensure vectors are normalized
    a_norm = a / np.linalg.norm(a)
    b_norm = b / np.linalg.norm(b)
    
    # Cosine similarity
    return float(np.dot(a_norm, b_norm))


async def test_7d_splash():
    """Test how 7D emotions work for splash analysis."""
    print("Loading 7D emotion classifier...")
    classifier = pipeline(
        "text-classification", 
        model="j-hartmann/emotion-english-roberta-large",
        return_all_scores=True,
        device=-1  # CPU
    )
    
    # Test memories with clear emotional content
    test_memories = [
        # Very positive
        "YES! The bug is finally fixed! This is amazing!",
        "I'm so proud of what we built together today.",
        "Everything is working perfectly - this feels incredible!",
        
        # Very negative
        "This is so frustrating, nothing is working.",
        "I feel terrible about how this turned out.",
        "Everything is broken and I don't know what to do.",
        
        # Angry
        "This stupid system keeps crashing!",
        "I'm furious that we lost all that work!",
        
        # Fearful
        "I'm worried this won't scale properly.",
        "What if we can't fix this in time?",
        
        # Neutral/technical
        "The embedding service runs on port 8001.",
        "Docker containers use Linux namespaces for isolation.",
        
        # Mixed emotions
        "I'm excited but nervous about deploying this.",
        "This is impressive but I'm concerned about edge cases.",
    ]
    
    # Get embeddings for all memories
    print("\nGenerating emotion embeddings...")
    embeddings = []
    
    for memory in test_memories:
        result = classifier(memory)[0]
        vector = extract_emotion_vector(result)
        embeddings.append(vector)
        
        # Show top emotion
        top_emotion = max(result, key=lambda x: x['score'])
        print(f"\n'{memory[:50]}...'")
        print(f"  Top emotion: {top_emotion['label']} ({top_emotion['score']:.3f})")
        print(f"  Vector: [{', '.join(f'{v:.2f}' for v in vector)}]")
    
    # Test query: "I'm really happy with our progress!"
    query = "I'm really happy with our progress!"
    print(f"\n\nQuery: '{query}'")
    
    query_result = classifier(query)[0]
    query_vector = extract_emotion_vector(query_result)
    
    top_emotion = max(query_result, key=lambda x: x['score'])
    print(f"Query emotion: {top_emotion['label']} ({top_emotion['score']:.3f})")
    print(f"Query vector: [{', '.join(f'{v:.2f}' for v in query_vector)}]")
    
    # Calculate similarities
    print("\n\nSplash Analysis (Emotional Resonance)")
    print("=" * 60)
    
    similarities = []
    for i, (memory, embedding) in enumerate(zip(test_memories, embeddings)):
        sim = cosine_similarity(query_vector, embedding)
        similarities.append((sim, memory))
    
    # Sort by similarity
    similarities.sort(key=lambda x: x[0], reverse=True)
    
    # Show top 5 most similar (emotionally resonant)
    print("\n🔗 Most Emotionally Resonant:")
    for sim, memory in similarities[:5]:
        print(f"  {int(sim * 100)}%: '{memory[:60]}...'")
    
    # Show bottom 5 least similar (emotionally dissonant)
    print("\n⚡ Most Emotionally Dissonant:")
    for sim, memory in similarities[-5:]:
        print(f"  {int(sim * 100)}%: '{memory[:60]}...'")
    
    # Test specific contrasts
    print("\n\nSpecific Emotional Contrasts:")
    print("=" * 60)
    
    # Happy vs Sad
    happy_idx = 0  # "YES! The bug is finally fixed!"
    sad_idx = 4    # "I feel terrible about how this turned out."
    happy_sad_sim = cosine_similarity(embeddings[happy_idx], embeddings[sad_idx])
    print(f"Happy vs Sad: {int(happy_sad_sim * 100)}% similar")
    
    # Angry vs Calm
    angry_idx = 6   # "This stupid system keeps crashing!"
    calm_idx = 10   # "The embedding service runs on port 8001."
    angry_calm_sim = cosine_similarity(embeddings[angry_idx], embeddings[calm_idx])
    print(f"Angry vs Neutral: {int(angry_calm_sim * 100)}% similar")
    
    # Two happy memories
    happy1_idx = 0  # "YES! The bug is finally fixed!"
    happy2_idx = 2  # "Everything is working perfectly..."
    happy_happy_sim = cosine_similarity(embeddings[happy1_idx], embeddings[happy2_idx])
    print(f"Happy vs Happy: {int(happy_happy_sim * 100)}% similar")


if __name__ == "__main__":
    asyncio.run(test_7d_splash())