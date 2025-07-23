#!/bin/bash
# Run alembic commands against the Docker database

set -e

# Export environment variables
export DATABASE_URL="postgresql://alpha:alphapass@localhost:5432/alpha_brain"
export HELPER_MODEL="gemma3:4b"
export EMBEDDING_SERVICE_URL="http://localhost:8001"

# Run alembic command with all arguments passed through
uv run alembic "$@"