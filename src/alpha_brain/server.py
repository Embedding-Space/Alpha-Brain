"""Alpha Brain MCP Server."""

from contextlib import asynccontextmanager

from fastmcp import FastMCP
from structlog import get_logger

from alpha_brain.tools import get_memory, health_check, remember, search

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
    
    Use remember() to store memories as natural language prose.
    Use search() to find memories and knowledge using various search strategies.
    
    This system combines:
    - Diary Brain: Experiential memories with emotional context
    - Encyclopedia Brain: Crystallized knowledge and technical patterns
    """,
    lifespan=lifespan,
)

# Register tools
mcp.tool(health_check)
mcp.tool(remember)
mcp.tool(search)
mcp.tool(get_memory)


if __name__ == "__main__":
    # This is used when running directly, not via Docker
    mcp.run()
