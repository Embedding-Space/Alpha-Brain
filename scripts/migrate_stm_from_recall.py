#!/usr/bin/env python3
"""
Migrate short-term memories from Alpha-Recall Redis to Alpha-Brain.

This script fetches STMs from the Alpha-Recall Redis instance and 
loads them into Alpha-Brain via the CLI for testing the Splash Engine
with real data.
"""

import asyncio
import json
import subprocess
import sys
from datetime import datetime

import pendulum


async def get_stms_from_recall(limit: int = 200) -> list[dict]:
    """Fetch short-term memories from Alpha-Recall Redis."""
    # Use Docker exec to access Redis in container
    import subprocess
    
    # Get memory IDs from Redis
    result = subprocess.run(
        ["docker", "exec", "redis", "redis-cli", "ZREVRANGE", "memory_index", "0", str(limit-1)],
        capture_output=True,
        text=True,
        check=True
    )
    
    memory_ids = result.stdout.strip().split('\n') if result.stdout.strip() else []
    memories = []
    
    for memory_id in memory_ids:
        if not memory_id:
            continue
            
        # Get content
        content_result = subprocess.run(
            ["docker", "exec", "redis", "redis-cli", "HGET", f"memory:{memory_id}", "content"],
            capture_output=True,
            text=True,
            check=True
        )
        
        # Get created_at
        created_result = subprocess.run(
            ["docker", "exec", "redis", "redis-cli", "HGET", f"memory:{memory_id}", "created_at"],
            capture_output=True,
            text=True,
            check=True
        )
        
        content = content_result.stdout.strip()
        created_at = created_result.stdout.strip()
        
        if content and created_at:
            memory = {
                "id": memory_id,
                "content": content,
                "created_at": created_at,
                "key": f"memory:{memory_id}"
            }
            memories.append(memory)
    
    print(f"Found {len(memories)} STMs in Alpha-Recall Redis")
    return memories



def load_memory_to_brain(content: str, created_at: str) -> bool:
    """Load a single memory into Alpha-Brain via CLI."""
    # Escape quotes in content for shell
    escaped_content = content.replace('"', '\\"').replace("'", "\\'")
    
    # Build the CLI command
    cmd = [
        "uv", "run", "python", "-m", "alpha_brain.cli", 
        "remember", content
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        
        # Check if successful
        if "Stored memory:" in result.stdout:
            return True
        else:
            print(f"Failed to store memory: {result.stdout}")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"Error storing memory: {e.stderr}")
        return False


async def main():
    """Main migration function."""
    print("🧠 Alpha-Recall → Alpha-Brain STM Migration")
    print("=" * 50)
    
    # Get memories from Alpha-Recall
    memories = await get_stms_from_recall(limit=200)
    
    if not memories:
        print("No memories found to migrate!")
        return
    
    # Sort by created_at to maintain chronological order
    memories.sort(key=lambda m: m["created_at"])
    
    print(f"\nMigrating {len(memories)} memories...")
    print("(Loading in chronological order)")
    
    success_count = 0
    failed_count = 0
    
    for i, memory in enumerate(memories, 1):
        content = memory["content"]
        created_at = memory["created_at"]
        
        # Parse and format the timestamp
        dt = pendulum.parse(created_at)
        age = dt.diff_for_humans()
        
        print(f"\n[{i}/{len(memories)}] Memory from {age}:")
        print(f"  Preview: {content[:80]}...")
        
        # Load into Alpha-Brain
        if load_memory_to_brain(content, created_at):
            success_count += 1
            print("  ✓ Loaded successfully")
        else:
            failed_count += 1
            print("  ✗ Failed to load")
        
        # Small delay to avoid overwhelming the service
        await asyncio.sleep(0.5)
    
    print("\n" + "=" * 50)
    print(f"Migration complete!")
    print(f"  ✓ Success: {success_count}")
    print(f"  ✗ Failed: {failed_count}")
    print(f"  Total: {len(memories)}")


if __name__ == "__main__":
    asyncio.run(main())