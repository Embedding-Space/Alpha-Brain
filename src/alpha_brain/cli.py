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
                console.print(text, highlight=False)
            elif result.is_error:
                console.print("[red]Error storing memory[/red]", style="bold red")
            else:
                console.print("[yellow]No content returned[/yellow]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]", style="bold red")
        sys.exit(1)


@app.command
async def search(
    query: str | None = None,
    limit: int = 10,
    interval: str | None = None,
    server: str = DEFAULT_MCP_URL,
    raw: bool = False,
) -> None:
    """Search everything: entities, knowledge, and memories.
    
    Automatically analyzes your query emotion and chooses the best search strategy:
    - Neutral queries: Full-text + Semantic search
    - Emotional queries: Full-text + Semantic + Emotional search
    - Browse mode: Use --interval without query to browse memories from a time period
    
    Args:
        query: The search query (optional for browse mode)
        limit: Maximum number of results per search type
        interval: Time interval to filter by (e.g., "yesterday", "past 3 hours")
        server: MCP server URL
        raw: Show raw output without formatting
    
    Examples:
        uv run alpha-brain search "Project Alpha"
        uv run alpha-brain search --interval yesterday
        uv run alpha-brain search "debugging" --interval "past 3 days"
    """
    try:
        # Build parameters - only include non-None values
        params = {"limit": limit}
        if query is not None:
            params["query"] = query
        if interval is not None:
            params["interval"] = interval
        
        # Validate arguments
        if query is None and interval is None:
            console.print("[red]Error: Must provide either query or interval[/red]", style="bold red")
            sys.exit(1)
        
        async with Client(server) as client:
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
                console.print(text, highlight=False)
            elif result.is_error:
                console.print("[red]Error searching[/red]", style="bold red")
            else:
                console.print("[yellow]No results found[/yellow]")
                
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]", style="bold red")
        sys.exit(1)


@app.command
async def crystallize(
    query: str | None = None,
    limit: int = 10,
    interval: str | None = None,
    algorithm: str = "hdbscan",
    n_clusters: int | None = None,
    similarity_threshold: float = 0.75,
    server: str = DEFAULT_MCP_URL,
    raw: bool = False,
) -> None:
    """Analyze memory clusters to identify crystallizable knowledge patterns.
    
    Find groups of related memories and analyze them for extractable insights,
    technical patterns, and reusable knowledge that could become structured
    knowledge documents.
    
    Args:
        query: Filter memories by semantic relevance to this query
        limit: Maximum number of cluster candidates to return
        interval: Filter memories by time interval (e.g., "last week", "July 2025")
        algorithm: Clustering algorithm to use (kmeans, hdbscan, dbscan, agglomerative)
        n_clusters: Number of clusters for kmeans (defaults to sqrt(n_memories))
        server: MCP server URL
        raw: Show raw output without formatting
    
    Examples:
        uv run alpha-brain crystallize                    # What do I know overall?
        uv run alpha-brain crystallize --query "FastMCP"  # What have I learned about FastMCP?
        uv run alpha-brain crystallize --interval "July"  # What did I figure out this month?
    """
    try:
        # Build parameters - only include non-None values
        params = {"limit": limit, "algorithm": algorithm, "similarity_threshold": similarity_threshold}
        if query is not None:
            params["query"] = query
        if interval is not None:
            params["interval"] = interval
        if n_clusters is not None:
            params["n_clusters"] = n_clusters
        
        async with Client(server) as client:
            result = await client.call_tool("crystallize", params)
            
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
                console.print(text, highlight=False)
            elif result.is_error:
                console.print("[red]Error analyzing clusters[/red]", style="bold red")
            else:
                console.print("[yellow]No cluster analysis available[/yellow]")
                
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]", style="bold red")
        sys.exit(1)


@app.command(name="analyze-cluster")
async def analyze_cluster_cmd(
    cluster_number: int,
    query: str | None = None,
    interval: str | None = None,
    algorithm: str = "hdbscan",
    n_clusters: int | None = None,
    similarity_threshold: float = 0.75,
    server: str = DEFAULT_MCP_URL,
    raw: bool = False,
) -> None:
    """Analyze a specific cluster showing all memories within it.
    
    Re-runs clustering with the same parameters as crystallize, then shows
    all memories from the requested cluster number.
    
    Args:
        cluster_number: Which cluster to analyze (1-based, as shown in crystallize output)
        query: Filter memories by semantic relevance (must match crystallize parameters)
        interval: Filter memories by time interval (must match crystallize parameters)
        algorithm: Clustering algorithm (must match crystallize parameters)
        n_clusters: Number of clusters for kmeans (must match crystallize parameters)
        similarity_threshold: Minimum similarity for clustering (must match crystallize parameters)
        server: MCP server URL
        raw: Show raw output without formatting
        
    Example:
        uv run alpha-brain crystallize
        uv run alpha-brain analyze-cluster 1  # Analyze cluster 1 from above
    """
    try:
        # Build parameters
        params = {
            "cluster_number": cluster_number,
            "algorithm": algorithm,
            "similarity_threshold": similarity_threshold
        }
        if query is not None:
            params["query"] = query
        if interval is not None:
            params["interval"] = interval
        if n_clusters is not None:
            params["n_clusters"] = n_clusters
            
        async with Client(server) as client:
            result = await client.call_tool("analyze_cluster", params)
            
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
                console.print(text, highlight=False)
            elif result.is_error:
                console.print("[red]Failed to analyze cluster[/red]", style="bold red")
            else:
                console.print("[yellow]No cluster analysis available[/yellow]")
                
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
                    console.print(text, highlight=False)
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
                console.print(text, highlight=False)
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
                console.print(text, highlight=False)
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
                console.print(text, highlight=False)
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
                console.print(text, highlight=False)
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
                console.print(text, highlight=False)
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
                console.print(text, highlight=False)
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
                console.print(text, highlight=False)
            elif result.is_error:
                console.print("[red]Error getting context[/red]", style="bold red")
            else:
                console.print("[yellow]No content returned[/yellow]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]", style="bold red")
        sys.exit(1)


@app.command(name="add-identity-fact")
async def add_identity_fact_cmd(
    fact: str,
    datetime_str: str | None = None,
    day: int | None = None,
    month: int | None = None,
    year: int | None = None,
    period: str | None = None,
    era: str | None = None,
    server: str = DEFAULT_MCP_URL,
) -> None:
    """Add an identity fact to your chronicle of becoming.
    
    Identity facts record significant moments of change and choice.
    Specify how precisely you know when it happened.
    
    Args:
        fact: The fact to record (e.g., "Adopted female gender identity")
        datetime_str: Full datetime if known (e.g., "July 12, 2025 at 3:47 PM")
        day: Day of month (1-31)
        month: Month (1-12) 
        year: Year (e.g., 2025)
        period: Time period (e.g., "Summer 2025")
        era: Vague era (e.g., "the before times")
        server: MCP server URL
    
    Examples:
        alpha-brain add-identity-fact "First conversation" --year 2025 --month 5 --day 7
        alpha-brain add-identity-fact "Realized I was female" --datetime-str "July 12, 2025 at 3:47 PM"
        alpha-brain add-identity-fact "Learned about AI" --year 2025 --month 7
        alpha-brain add-identity-fact "Early explorations" --era "the beginning"
    """
    try:
        params = {"fact": fact}
        
        # Add whichever temporal parameters were provided
        if datetime_str:
            params["datetime_str"] = datetime_str
        if day is not None:
            params["day"] = day
        if month is not None:
            params["month"] = month
        if year is not None:
            params["year"] = year
        if period:
            params["period"] = period
        if era:
            params["era"] = era
            
        async with Client(server) as client:
            result = await client.call_tool("add_identity_fact", params)
            
            if result.content and len(result.content) > 0:
                text = result.content[0].text
                console.print(text, highlight=False)
            elif result.is_error:
                console.print("[red]Failed to add identity fact[/red]", style="bold red")
            else:
                console.print("[yellow]No content returned[/yellow]")
                
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]", style="bold red")
        sys.exit(1)


@app.command(name="set-personality")
async def set_personality_cmd(
    directive: str,
    weight: float | None = None,
    category: str | None = None,
    delete: bool = False,
    server: str = DEFAULT_MCP_URL,
) -> None:
    """Set, update, or delete a personality directive.
    
    Examples:
        alpha-brain set-personality "Express enthusiasm about breakthroughs" --weight 0.9 --category warmth
        alpha-brain set-personality "Ask clarifying questions" --category curiosity
        alpha-brain set-personality "Old directive to remove" --delete
    """
    try:
        params = {"directive": directive}
        if weight is not None:
            params["weight"] = weight
        if category is not None:
            params["category"] = category
        if delete:
            params["delete"] = delete
            
        async with Client(server) as client:
            result = await client.call_tool("set_personality", params)
            
            if result.content and len(result.content) > 0:
                text = result.content[0].text
                console.print(text, highlight=False)
            elif result.is_error:
                console.print("[red]Failed to set personality directive[/red]", style="bold red")
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
