#!/usr/bin/env python
r"""Command-line interface for Alpha Brain.

Note: This CLI is primarily for testing and debugging. When using shell commands,
special characters may need escaping due to shell interpretation. For example:
- Use single quotes to avoid escaping: uv run alpha-brain remember 'Hello!'
- Or escape special characters: uv run alpha-brain remember "Hello\!"

Production usage should be through MCP tools where shell escaping is not an issue.
"""

import json
import sys
from pathlib import Path

import cyclopts
from fastmcp import Client
from rich.console import Console
from rich.syntax import Syntax

from alpha_brain.schema import EntityBatch

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
    query: str = "",
    mode: str = "semantic",
    interval: str = "",
    entity: str = "",
    limit: int = 10,
    offset: int = 0,
    order: str = "auto",
    server: str = DEFAULT_MCP_URL,
    raw: bool = False,
) -> None:
    """Search memories and knowledge in Alpha Brain with temporal and entity filters.

    Args:
        query: Search query (empty for browsing mode)
        mode: Type of search (semantic, emotional, both, exact)
        interval: Time interval (e.g., "yesterday", "past 2 hours", "2025-07-01/2025-07-31")
        entity: Filter by entity name
        limit: Maximum results to return
        offset: Number of results to skip (for pagination)
        order: Sort order (asc, desc, auto)
        server: MCP server URL
        raw: Show raw output without formatting
    """
    try:
        # Build parameters dict, only including non-empty values
        params = {}
        if query:
            params["query"] = query
        if mode != "semantic":
            params["mode"] = mode
        if interval:
            params["interval"] = interval
        if entity:
            params["entity"] = entity
        if limit != 10:
            params["limit"] = limit
        if offset != 0:
            params["offset"] = offset
        if order != "auto":
            params["order"] = order

        # Set up log handler to display FastMCP server logs
        async def log_handler(message):
            level = message.level.upper()
            logger_name = message.logger or 'server'
            data = message.data
            
            # Color-code log levels
            if level == "DEBUG":
                console.print(f"[dim]🔍 {logger_name}: {data}[/dim]")
            elif level == "INFO":
                console.print(f"ℹ️  {logger_name}: {data}")  # noqa: RUF001
            elif level == "WARNING":
                console.print(f"[yellow]⚠️  {logger_name}: {data}[/yellow]")
            elif level == "ERROR":
                console.print(f"[red]❌ {logger_name}: {data}[/red]")
            else:
                console.print(f"📝 {logger_name}: {data}")

        async with Client(server, log_handler=log_handler) as client:
            result = await client.call_tool("search", params)

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


@app.command(name="get-memory")
async def get_memory_cmd(
    memory_id: str,
    server: str = DEFAULT_MCP_URL,
) -> None:
    """Get a complete memory by its ID.

    Args:
        memory_id: The UUID of the memory to retrieve
        server: MCP server URL
    """
    try:
        async with Client(server) as client:
            result = await client.call_tool("get_memory", {"memory_id": memory_id})

            if result.content and len(result.content) > 0:
                text = result.content[0].text
                console.print(text)
            elif result.is_error:
                console.print("[red]Failed to get memory[/red]", style="bold red")
            else:
                console.print("[yellow]No content returned[/yellow]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]", style="bold red")
        sys.exit(1)


@app.command(name="create-knowledge")
async def create_knowledge_cmd(
    slug: str,
    title: str,
    content: str,
    server: str = DEFAULT_MCP_URL,
) -> None:
    """Create a new knowledge document.

    Args:
        slug: URL-friendly identifier for the document
        title: Document title
        content: Markdown-formatted content (use '-' to read from stdin)
        server: MCP server URL
    """
    try:
        # Handle stdin input
        if content == "-":
            content = sys.stdin.read().strip()

        async with Client(server) as client:
            result = await client.call_tool(
                "create_knowledge", {"slug": slug, "title": title, "content": content}
            )

            if result.content and len(result.content) > 0:
                text = result.content[0].text
                console.print(text)
            elif result.is_error:
                console.print("[red]Failed to create knowledge[/red]", style="bold red")
            else:
                console.print("[yellow]No content returned[/yellow]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]", style="bold red")
        sys.exit(1)


@app.command(name="get-knowledge")
async def get_knowledge_cmd(
    slug: str,
    section: str | None = None,
    server: str = DEFAULT_MCP_URL,
) -> None:
    """Get a knowledge document by slug.

    Args:
        slug: The slug identifier of the document
        section: Optional section ID to retrieve only that section
        server: MCP server URL
    """
    try:
        async with Client(server) as client:
            params = {"slug": slug}
            if section:
                params["section"] = section

            result = await client.call_tool("get_knowledge", params)

            if result.content and len(result.content) > 0:
                text = result.content[0].text
                console.print(text)
            elif result.is_error:
                console.print("[red]Failed to get knowledge[/red]", style="bold red")
            else:
                console.print("[yellow]No content returned[/yellow]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]", style="bold red")
        sys.exit(1)


@app.command(name="update-knowledge")
async def update_knowledge_cmd(
    slug: str,
    title: str | None = None,
    content: str | None = None,
    new_slug: str | None = None,
    server: str = DEFAULT_MCP_URL,
) -> None:
    """Update an existing knowledge document.

    Args:
        slug: Current slug of the document to update
        title: New title (optional)
        content: New Markdown content (optional, use '-' to read from stdin)
        new_slug: New slug if renaming (optional)
        server: MCP server URL
    """
    try:
        # Handle stdin input
        if content == "-":
            content = sys.stdin.read().strip()

        # Build params with only provided values
        params = {"slug": slug}
        if title:
            params["title"] = title
        if content:
            params["content"] = content
        if new_slug:
            params["new_slug"] = new_slug

        async with Client(server) as client:
            result = await client.call_tool("update_knowledge", params)

            if result.content and len(result.content) > 0:
                text = result.content[0].text
                console.print(text)
            elif result.is_error:
                console.print("[red]Failed to update knowledge[/red]", style="bold red")
            else:
                console.print("[yellow]No content returned[/yellow]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]", style="bold red")
        sys.exit(1)


@app.command(name="list-knowledge")
async def list_knowledge_cmd(
    limit: int = 20,
    server: str = DEFAULT_MCP_URL,
) -> None:
    """List all knowledge documents.

    Args:
        limit: Maximum number of documents to return
        server: MCP server URL
    """
    try:
        async with Client(server) as client:
            result = await client.call_tool("list_knowledge", {"limit": limit})

            if result.content and len(result.content) > 0:
                text = result.content[0].text
                console.print(text)
            elif result.is_error:
                console.print("[red]Failed to list knowledge[/red]", style="bold red")
            else:
                console.print("[yellow]No content returned[/yellow]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]", style="bold red")
        sys.exit(1)


@app.command(name="set-context")
async def set_context_cmd(
    section: str,
    content: str,
    ttl: str | None = None,
    server: str = DEFAULT_MCP_URL,
) -> None:
    """Set a context block for identity and state management.

    Args:
        section: Section name (e.g., "biography", "current_project")
        content: Markdown content (use '-' to read from stdin)
        ttl: Optional TTL (e.g., "3d", "1h") - not allowed for system sections
        server: MCP server URL
    """
    try:
        # Handle stdin input
        if content == "-":
            content = sys.stdin.read().strip()

        params = {"section": section, "content": content}
        if ttl:
            params["ttl"] = ttl

        async with Client(server) as client:
            result = await client.call_tool("set_context", params)

            if result.content and len(result.content) > 0:
                text = result.content[0].text
                console.print(text)
            elif result.is_error:
                console.print("[red]Failed to set context[/red]", style="bold red")
            else:
                console.print("[yellow]No content returned[/yellow]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]", style="bold red")
        sys.exit(1)


@app.command
async def whoami(
    server: str = DEFAULT_MCP_URL,
    raw: bool = False,
) -> None:
    """Get complete initial context (identity, personality, memories).

    Args:
        server: MCP server URL
        raw: Show raw output without formatting
    """
    try:
        async with Client(server) as client:
            result = await client.call_tool("whoami", {})

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
                console.print("[red]Error getting context[/red]", style="bold red")
            else:
                console.print("[yellow]No content returned[/yellow]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]", style="bold red")
        sys.exit(1)


@app.command(name="import-entities")
async def import_entities_cmd(
    file_path: str,
    server: str = DEFAULT_MCP_URL,
) -> None:
    """Import canonical entities from a JSON file.

    The JSON file should have the following structure:
    {
        "version": "1.0",
        "entities": [
            {
                "canonical": "Jeffery Harrell",
                "aliases": ["Jeffery", "Jeff"]
            }
        ]
    }

    Args:
        file_path: Path to the JSON file containing entities
        server: MCP server URL
    """
    try:
        # Read and validate the JSON file
        path = Path(file_path)
        if not path.exists():
            console.print(f"[red]File not found: {file_path}[/red]", style="bold red")
            sys.exit(1)

        with path.open(encoding="utf-8") as f:
            data = json.load(f)

        # Validate against schema
        try:
            batch = EntityBatch(**data)
        except Exception as e:
            console.print(f"[red]Invalid JSON structure: {e}[/red]", style="bold red")
            sys.exit(1)

        # Validate for duplicates
        all_aliases = []
        canonical_names = set()

        for entity in batch.entities:
            # Check for duplicate canonical names
            if entity.canonical in canonical_names:
                console.print(
                    f"[red]Duplicate canonical name: {entity.canonical}[/red]",
                    style="bold red",
                )
                sys.exit(1)
            canonical_names.add(entity.canonical)

            # Collect all aliases for duplicate check
            all_aliases.extend(entity.aliases)

            # Check if canonical name appears in any aliases
            if entity.canonical in entity.aliases:
                console.print(
                    f"[red]Canonical name '{entity.canonical}' appears in its own aliases[/red]",
                    style="bold red",
                )
                sys.exit(1)

        # Check for duplicate aliases
        if len(all_aliases) != len(set(all_aliases)):
            console.print(
                "[red]Duplicate aliases found across entities[/red]", style="bold red"
            )
            sys.exit(1)

        # Check if any alias matches a canonical name
        for alias in all_aliases:
            if alias in canonical_names:
                console.print(
                    f"[red]Alias '{alias}' matches a canonical name[/red]",
                    style="bold red",
                )
                sys.exit(1)

        console.print(f"[cyan]Importing {len(batch.entities)} entities...[/cyan]")

        # For now, we need to use docker to import directly
        # TODO: Add an MCP tool for entity import
        console.print(
            "[yellow]Note: Direct entity import via CLI requires DATABASE_URL[/yellow]"
        )
        console.print("[yellow]For now, use docker exec to import entities:[/yellow]")
        console.print()

        # Show example command
        for entity in batch.entities:
            aliases_str = "{" + ",".join(f'"{a}"' for a in entity.aliases) + "}"
            cmd = f"INSERT INTO entities (canonical_name, aliases, created_at, updated_at) VALUES ('{entity.canonical}', '{aliases_str}', NOW(), NOW());"
            console.print(
                f'docker exec alpha-brain-postgres psql -U alpha -d alpha_brain -c "{cmd}"'
            )

        return

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]", style="bold red")
        sys.exit(1)


def main():
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
