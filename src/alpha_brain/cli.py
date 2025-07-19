#!/usr/bin/env python
"""Command-line interface for Alpha Brain."""

import json
import sys

import cyclopts
from fastmcp import Client
from rich.console import Console
from rich.syntax import Syntax

app = cyclopts.App(
    name="alpha-brain",
    help="Command-line interface for Alpha Brain unified memory and knowledge system.",
)
console = Console()

# Default MCP server URL
DEFAULT_MCP_URL = "http://localhost:9100/mcp/"


@app.command
async def remember(
    content: str,
    server: str = DEFAULT_MCP_URL,
    raw: bool = False,
) -> None:
    """Store a memory in Alpha Brain.

    Args:
        content: The content to remember
        server: MCP server URL
        raw: Show raw output without formatting
    """
    try:
        async with Client(server) as client:
            result = await client.call_tool("remember", {"content": content})

            if raw:
                # Show the raw CallToolResult structure
                console.print(f"CallToolResult: {result}")
                console.print(f"- data: {result.data}")
                console.print(f"- content: {result.content}")
                console.print(f"- structured_content: {result.structured_content}")
                console.print(f"- is_error: {result.is_error}")
            # Extract the text content
            elif result.content and len(result.content) > 0:
                text = result.content[0].text
                console.print(text)
            elif result.is_error:
                console.print("[red]Error storing memory[/red]", style="bold red")
            else:
                console.print("[yellow]No content returned[/yellow]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]", style="bold red")
        sys.exit(1)


@app.command
async def search(
    query: str,
    search_type: str = "semantic",
    limit: int = 10,
    server: str = DEFAULT_MCP_URL,
    raw: bool = False,
) -> None:
    """Search memories and knowledge in Alpha Brain.

    Args:
        query: Search query
        search_type: Type of search (semantic, emotional, both)
        limit: Maximum results to return
        server: MCP server URL
        raw: Show raw output without formatting
    """
    try:
        async with Client(server) as client:
            result = await client.call_tool(
                "search", {"query": query, "search_type": search_type, "limit": limit}
            )

            if raw:
                # Show the raw CallToolResult structure
                console.print(f"CallToolResult: {result}")
                console.print(f"- data: {result.data}")
                console.print(f"- content: {result.content}")
                console.print(f"- structured_content: {result.structured_content}")
                console.print(f"- is_error: {result.is_error}")
            # Extract the text content
            elif result.content and len(result.content) > 0:
                text = result.content[0].text
                console.print(text)
            elif result.is_error:
                console.print("[red]Error searching memories[/red]", style="bold red")
            else:
                console.print("[yellow]No results found[/yellow]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]", style="bold red")
        sys.exit(1)


@app.command
async def health(
    server: str = DEFAULT_MCP_URL,
    raw: bool = False,
) -> None:
    """Check health of the Alpha Brain server.

    Args:
        server: MCP server URL
        raw: Show raw output without formatting
    """
    try:
        async with Client(server) as client:
            result = await client.call_tool("health_check", {})

            if raw:
                # Show the raw CallToolResult structure
                console.print(f"CallToolResult: {result}")
                console.print(f"- data: {result.data}")
                console.print(f"- content: {result.content}")
                console.print(f"- structured_content: {result.structured_content}")
                console.print(f"- is_error: {result.is_error}")
            # Extract the text content
            elif result.content and len(result.content) > 0:
                text = result.content[0].text
                # If it's JSON, pretty print it
                try:
                    data = json.loads(text)
                    syntax = Syntax(json.dumps(data, indent=2), "json", theme="monokai")
                    console.print(syntax)
                except json.JSONDecodeError:
                    # Not JSON, just print as text
                    console.print(text)
            elif result.is_error:
                console.print("[red]Server health check failed[/red]", style="bold red")
            else:
                console.print("[green]Server is healthy[/green]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]", style="bold red")
        sys.exit(1)


@app.command
async def tools(
    server: str = DEFAULT_MCP_URL,
) -> None:
    """List available tools on the MCP server.

    Args:
        server: MCP server URL
    """
    try:
        async with Client(server) as client:
            tools = await client.list_tools()

            console.print(f"\n[bold]Available tools on {server}:[/bold]\n")

            for tool in tools:
                console.print(f"[cyan]{tool.name}[/cyan]")
                if tool.description:
                    console.print(f"  {tool.description}")
                if tool.inputSchema:
                    console.print(f"  Schema: {json.dumps(tool.inputSchema, indent=4)}")
                console.print()

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]", style="bold red")
        sys.exit(1)


def main():
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
