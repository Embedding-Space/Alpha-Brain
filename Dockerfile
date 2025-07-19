# Development Dockerfile - uses bind mounts for code
FROM python:3.13-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set up working directory
WORKDIR /app

# Copy everything we need
COPY pyproject.toml uv.lock README.md ./
COPY src ./src

# Install in editable mode so bind mounts work properly
RUN uv pip install --system --no-cache -e .

# Expose MCP HTTP port
EXPOSE 9100

# Use exec form to ensure signals are handled properly
ENTRYPOINT ["fastmcp", "run", "src/alpha_brain/server.py", "--transport", "http", "--host", "0.0.0.0", "--port", "9100"]