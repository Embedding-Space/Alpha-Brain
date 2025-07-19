#!/usr/bin/env python
"""Wait for MCP server to be ready."""

import asyncio
import sys

from fastmcp import Client


async def check_server(url: str, max_attempts: int = 30):
    """Try to connect to MCP server."""
    for _attempt in range(max_attempts):
        try:
            async with Client(url) as client:
                # If we can connect and get server info, it's ready
                if client.initialize_result and client.initialize_result.serverInfo:
                    print(
                        f"\n✓ Connected to {client.initialize_result.serverInfo.name}!"
                    )
                    return True
        except Exception:
            # Server not ready yet
            print(".", end="", flush=True)
            await asyncio.sleep(1)

    print("\n❌ Server failed to become ready")
    return False


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:9101/mcp/"
    print(f"Waiting for MCP server at {url}", end="", flush=True)

    success = asyncio.run(check_server(url))
    sys.exit(0 if success else 1)
