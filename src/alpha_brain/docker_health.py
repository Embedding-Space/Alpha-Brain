#!/usr/bin/env python
"""Docker health check using MCP ping."""

import sys


def main() -> int:
    """
    Docker health check using MCP ping.

    Always uses the MCP ping check - it's clean and doesn't spam logs.
    """
    from alpha_brain.health import main as mcp_health_check

    return mcp_health_check()


if __name__ == "__main__":
    sys.exit(main())
