#!/usr/bin/env python3
"""Dynamic CLI that auto-generates commands from MCP server tools."""

import asyncio
import contextlib
import json
import sys
from typing import Any

from fastmcp import Client
from rich.console import Console
from rich.table import Table

console = Console()

# Global MCP server URL - can be overridden with env var
MCP_URL = "http://localhost:9100/mcp/"


async def get_tools():
    """Get all tools from MCP server."""
    async with Client(MCP_URL) as client:
        tools = await client.list_tools()
        return {tool.name: tool for tool in tools}


async def call_tool(tool_name: str, arguments: dict[str, Any]):
    """Call a tool on the MCP server."""
    async with Client(MCP_URL) as client:
        return await client.call_tool(tool_name, arguments=arguments)


def print_result(result):
    """Pretty print tool result."""
    if isinstance(result.content, list):
        for item in result.content:
            if hasattr(item, "text"):
                console.print(item.text)
            else:
                console.print(item)
    else:
        console.print(result.content)


def main():
    """Main CLI entry point."""
    if len(sys.argv) < 2 or sys.argv[1] in ["--help", "-h", "help"]:
        print_help()
        return
    
    command = sys.argv[1]
    
    if command == "list-tools":
        list_tools_command()
    elif command == "help-tool":
        if len(sys.argv) < 3:
            console.print("[red]Error:[/red] Please specify a tool name")
            sys.exit(1)
        help_tool_command(sys.argv[2])
    else:
        # Try to call it as a tool
        tool_command(command, sys.argv[2:])


def print_help():
    """Print help message."""
    console.print("\n[bold]Alpha Brain Dynamic CLI[/bold]")
    console.print("\nUsage: mcp [COMMAND] [OPTIONS]\n")
    console.print("Commands:")
    console.print("  list-tools              List all available tools")
    console.print("  help-tool TOOL_NAME     Show help for a specific tool")
    console.print("  TOOL_NAME [args...]     Call a tool with arguments\n")
    console.print("Examples:")
    console.print("  mcp list-tools")
    console.print("  mcp help-tool remember")
    console.print("  mcp remember --content 'Hello world'")
    console.print("  mcp search --query 'alpha brain' --limit 5\n")


def list_tools_command():
    """List all available tools."""
    tools = asyncio.run(get_tools())
    
    table = Table(title="Available MCP Tools")
    table.add_column("Tool Name", style="cyan", no_wrap=True)
    table.add_column("Description", style="white")
    
    for name, tool in sorted(tools.items()):
        description = tool.description or ""
        # Truncate long descriptions
        if len(description) > 60:
            description = description[:57] + "..."
        table.add_row(name, description)
    
    console.print(table)
    console.print("\nUse 'mcp help-tool TOOL_NAME' for detailed help on any tool.")


def help_tool_command(tool_name: str):
    """Show help for a specific tool."""
    tools = asyncio.run(get_tools())
    
    if tool_name not in tools:
        console.print(f"[red]Error:[/red] Unknown tool '{tool_name}'")
        console.print("Run 'mcp list-tools' to see available tools.")
        sys.exit(1)
    
    tool = tools[tool_name]
    console.print(f"\n[bold cyan]{tool_name}[/bold cyan]")
    console.print(tool.description or "No description available")
    
    # Parse schema
    schema = tool.inputSchema
    properties = schema.get("properties", {})
    required = schema.get("required", [])
    
    if properties:
        console.print("\n[bold]Arguments:[/bold]")
        for prop_name, prop_def in properties.items():
            # Format argument info
            arg_type = prop_def.get("type", "string")
            is_required = prop_name in required
            description = prop_def.get("description", "")
            default = prop_def.get("default")
            
            # Build argument display
            arg_display = f"  --{prop_name}"
            if is_required:
                arg_display += " [red](required)[/red]"
            arg_display += f" [{arg_type}]"
            if default is not None:
                arg_display += f" (default: {default})"
            
            console.print(arg_display)
            if description:
                console.print(f"      {description}")
    
    console.print("\n[bold]Example:[/bold]")
    console.print(f"  mcp {tool_name}", end="")
    
    # Show example with required args
    for prop_name in required:
        console.print(f" --{prop_name} VALUE", end="")
    console.print()


def tool_command(tool_name: str, args: list[str]):
    """Execute a tool with the given arguments."""
    tools = asyncio.run(get_tools())
    
    if tool_name not in tools:
        console.print(f"[red]Error:[/red] Unknown tool '{tool_name}'")
        console.print("Run 'mcp list-tools' to see available tools.")
        sys.exit(1)
    
    tool = tools[tool_name]
    
    # Parse arguments
    arguments = parse_tool_args(tool, args)
    
    # Call the tool
    try:
        result = asyncio.run(call_tool(tool_name, arguments))
        print_result(result)
    except Exception as e:
        console.print(f"[red]Error calling tool:[/red] {e}")
        sys.exit(1)


def parse_tool_args(tool, args: list[str]) -> dict[str, Any]:
    """Parse command line arguments for a tool."""
    schema = tool.inputSchema
    properties = schema.get("properties", {})
    required = schema.get("required", [])
    
    # Simple argument parser
    parsed = {}
    i = 0
    while i < len(args):
        arg = args[i]
        
        if arg.startswith("--"):
            # It's a named argument
            arg_name = arg[2:]
            
            if arg_name not in properties:
                console.print(f"[red]Error:[/red] Unknown argument '--{arg_name}'")
                sys.exit(1)
            
            # Get the value
            if i + 1 >= len(args):
                console.print(f"[red]Error:[/red] Missing value for '--{arg_name}'")
                sys.exit(1)
            
            value = args[i + 1]
            
            # Type conversion based on schema
            prop_def = properties[arg_name]
            prop_type = prop_def.get("type", "string")
            
            try:
                if prop_type == "integer":
                    value = int(value)
                elif prop_type == "number":
                    value = float(value)
                elif prop_type == "boolean":
                    value = value.lower() in ["true", "yes", "1"]
                elif prop_type == "array":
                    # Try to parse as JSON array
                    value = json.loads(value)
                elif prop_type == "object":
                    # Try to parse as JSON object
                    value = json.loads(value)
                # For anyOf types (e.g., str | None, int | None), try to infer
                elif "anyOf" in prop_def:
                    # Check if one of the types is integer or number
                    types = [t.get("type") for t in prop_def["anyOf"] if "type" in t]
                    if "integer" in types:
                        with contextlib.suppress(ValueError):
                            value = int(value)
                    elif "number" in types:
                        with contextlib.suppress(ValueError):
                            value = float(value)
                # string stays as is
            except (ValueError, json.JSONDecodeError):
                console.print(f"[red]Error:[/red] Invalid value for '--{arg_name}' (expected {prop_type})")
                sys.exit(1)
            
            parsed[arg_name] = value
            i += 2
        else:
            console.print(f"[red]Error:[/red] Unexpected argument '{arg}'")
            console.print("All arguments must be in --name value format")
            sys.exit(1)
    
    # Check required arguments
    for req in required:
        if req not in parsed:
            console.print(f"[red]Error:[/red] Missing required argument '--{req}'")
            sys.exit(1)
    
    return parsed


if __name__ == "__main__":
    main()
