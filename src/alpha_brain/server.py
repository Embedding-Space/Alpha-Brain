"""Alpha Brain MCP Server."""

from contextlib import asynccontextmanager

from fastmcp import FastMCP
from structlog import get_logger

from alpha_brain.tools import (
    create_knowledge,
    get_knowledge,
    get_memory,
    health_check,
    list_knowledge,
    remember,
    search,
    update_knowledge,
)

logger = get_logger()


@asynccontextmanager
async def lifespan(app):
    """Manage server lifecycle."""
    # Startup
    print("LIFESPAN: Starting up...")
    from alpha_brain.database import init_db
    from alpha_brain.embeddings import get_embedding_service

    await init_db()

    # Initialize embedding service
    logger.info("Initializing embedding service...")
    embedding_service = get_embedding_service()

    # Wait for embedding service to be ready
    logger.info("Waiting for embedding service to be ready...")
    await embedding_service.client.wait_until_ready()

    # Warm up the embedding models with a test embedding
    logger.info("Warming up embedding models...")
    try:
        await embedding_service.embed("warmup")
        logger.info("Embedding models warmed up successfully")
    except Exception as e:
        logger.warning("Failed to warm up embedding models", error=str(e))

    logger.info("Server ready!")

    yield

    # Shutdown
    from alpha_brain.database import close_db

    await close_db()
    logger.info("Server stopped")


# Create the MCP server
mcp = FastMCP(
    name="Alpha Brain",
    instructions="""
    A unified memory and knowledge system for AI agents.
    
    Memory Tools:
    - remember() to store memories as natural language prose
    - search() to find memories using semantic/emotional search
    - get_memory() to retrieve a specific memory by ID
    
    Knowledge Tools:
    - create_knowledge() to create structured documents from Markdown
    - get_knowledge() to retrieve documents by slug
    - update_knowledge() to modify existing documents
    - list_knowledge() to see all available documents
    
    This system combines:
    - Diary Brain: Experiential memories with emotional context
    - Encyclopedia Brain: Structured knowledge documents with sections
    """,
    lifespan=lifespan,
)

# Register tools
mcp.tool(health_check)
mcp.tool(remember)
mcp.tool(search)
mcp.tool(get_memory)
mcp.tool(create_knowledge)
mcp.tool(get_knowledge)
mcp.tool(update_knowledge)
mcp.tool(list_knowledge)


if __name__ == "__main__":
    # This is used when running directly, not via Docker
    mcp.run()
