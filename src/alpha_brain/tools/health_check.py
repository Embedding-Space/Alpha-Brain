"""Health check tool for Alpha Brain."""

import httpx
import psycopg
from structlog import get_logger

from alpha_brain.settings import get_settings

logger = get_logger()


async def health_check() -> str:
    """Check if the server is running and can connect to services."""
    settings = get_settings()

    checks = {
        "server": True,
        "database": False,
        "ollama": False,
    }

    # Test database connection
    try:
        async with await psycopg.AsyncConnection.connect(
            str(settings.database_url)
        ) as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT 1")
                await cur.fetchone()
        checks["database"] = True
    except Exception as e:
        logger.error("database_health_check_failed", error=str(e))

    # Test Ollama connection
    if settings.openai_base_url:
        try:
            async with httpx.AsyncClient() as client:
                # Try to hit the models endpoint
                response = await client.get(
                    f"{str(settings.openai_base_url).rstrip('/v1')}/api/tags",
                    timeout=5.0,
                )
                if response.status_code == 200:
                    checks["ollama"] = True
        except Exception as e:
            logger.error("ollama_health_check_failed", error=str(e))

    # Build prose response
    status = "healthy" if all(checks.values()) else "partially operational"
    issues = []

    if not checks["database"]:
        issues.append("Database connection failed")
    if not checks["ollama"]:
        issues.append("Ollama is not responding (entity extraction will be disabled)")

    response = f"Alpha Brain (v1.0.0) is {status}."

    if issues:
        response += "\n\nIssues:\n" + "\n".join(f"• {issue}" for issue in issues)
    else:
        response += "\n\nAll systems operational."

    return response
