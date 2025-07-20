#!/usr/bin/env python
"""Health check utilities for Alpha Brain MCP server."""

import asyncio
import sys

from fastmcp import Client


async def check_mcp_server(url: str, max_attempts: int = 30) -> bool:
    """
    Check if MCP server is ready by attempting to connect with FastMCP client.

    Args:
        url: MCP server URL (e.g., "http://localhost:9100/mcp/")
        max_attempts: Maximum connection attempts before giving up

    Returns:
        True if server is ready, False otherwise
    """
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


def main(url: str | None = None) -> int:
    """Main entry point for health check."""
    if url is None:
        url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:9100/mcp/"

    print(f"Waiting for MCP server at {url}", end="", flush=True)
    success = asyncio.run(check_mcp_server(url))
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
