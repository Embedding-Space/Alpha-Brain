# Alpha Brain Development Commands

# Default command - show help
default:
    @just --list

# Build Docker images
build:
    docker compose build

# Start the stack
up:
    docker compose up -d --wait

# Stop the stack
down: test-down
    docker compose down

# Restart MCP server (picks up code changes)
restart:
    docker compose restart alpha-brain-mcp

# Take the whole stack down and bring it back up
bounce:
    just down
    just up

# Show MCP server logs (use -f to follow)
logs *args:
    docker compose logs alpha-brain-mcp {{args}}

# Clean up test stack (in case tests failed and it's still running)
test-clean:
    docker compose -f docker-compose.test.yml down -v

# Start test containers (uses existing embedding service)
test-up:
    @echo "🚀 Starting test containers..."
    docker compose --profile test up -d --wait test-postgres test-mcp
    @echo "✅ Test containers ready at http://localhost:9101/mcp/"

# Run tests against test containers
test: test-up
    #!/usr/bin/env bash
    set -euo pipefail
    
    echo "🏃 Running tests against test containers..."
    
    # Run tests - test-up with --wait ensures server is ready
    if env MCP_TEST_URL="http://localhost:9101/mcp/" uv run pytest tests/e2e/ -v -s; then
        echo "✅ Tests passed!"
    else
        echo "❌ Tests failed!"
        exit 1
    fi

# Show test container logs
test-logs *args:
    docker compose logs test-mcp {{args}}

# Stop and remove test containers
test-down:
    @echo "🧹 Stopping test containers..."
    docker compose --profile test down
    @echo "✅ Test containers removed"

# Run E2E tests with fully isolated test stack (slow)
test-isolated:
    #!/usr/bin/env bash
    set -euo pipefail
    
    echo "🧪 Starting test environment..."
    
    # Clean up any existing test stack
    docker compose -f docker-compose.test.yml down -v 2>/dev/null || true
    
    # Start test stack (--remove-orphans to clean up the warning)
    docker compose -f docker-compose.test.yml up -d --wait --remove-orphans
    
    # Wait for server to be ready by trying to connect
    echo "⏳ Waiting for server to be ready..."
    if ! uv run python tests/wait_for_mcp.py http://localhost:9101/mcp/; then
        echo "Server failed to become ready"
        docker compose -f docker-compose.test.yml logs test-mcp
        exit 1
    fi
    
    echo "🏃 Running tests..."
    echo "Test URL will be: http://localhost:9101/mcp/"
    
    # Run tests and capture exit code (pass environment variable directly)
    if env MCP_TEST_URL="http://localhost:9101/mcp/" uv run pytest tests/e2e/ -v -s; then
        TEST_EXIT_CODE=0
        echo "✅ Tests passed!"
    else
        TEST_EXIT_CODE=$?
        echo "❌ Tests failed! Test stack preserved for debugging."
        echo ""
        echo "To view test logs:"
        echo "  docker compose -f docker-compose.test.yml logs"
        echo ""
        echo "To clean up test stack:"
        echo "  docker compose -f docker-compose.test.yml down -v"
        exit $TEST_EXIT_CODE
    fi
    
    # Only tear down if tests passed
    echo "🧹 Cleaning up test environment..."
    docker compose -f docker-compose.test.yml down -v
    
    echo "✨ Test run complete!"

# Run tests with coverage report
# Note: E2E tests don't show coverage since code runs in Docker container
coverage:
    uv run pytest tests/ --cov=alpha_brain --cov-report=term-missing -v

# Remove containers and volumes
clean:
    docker compose down -v

# Clean Python cache files (useful when code changes aren't being picked up)
clean-cache:
    @echo "🧹 Cleaning Python cache files..."
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true
    find . -type f -name "*.pyo" -delete 2>/dev/null || true
    docker compose exec alpha-brain-mcp find /app -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    docker compose exec alpha-brain-mcp find /app -type f -name "*.pyc" -delete 2>/dev/null || true
    @echo "✅ Cache cleaned"

# Quick development cycle - restart and follow logs
dev: restart
    just logs -f

# Connect to Postgres for debugging
psql:
    docker compose exec postgres psql -U alpha -d alpha_brain

# Run a specific test file or individual test
# Usage: just test-one test_memory_lifecycle.py
#        just test-one test_memory_lifecycle.py::test_full_memory_lifecycle
#        just test-one tests/e2e/test_00_health_check.py::test_server_is_healthy
test-one test_path:
    #!/usr/bin/env bash
    set -euo pipefail
    
    # Ensure test containers are up - test-up with --wait ensures server is ready
    just test-up
    
    echo "🏃 Running specific test: {{test_path}}"
    
    # Run the specific test
    if env MCP_TEST_URL="http://localhost:9101/mcp/" uv run pytest {{test_path}} -v -s; then
        echo "✅ Test passed!"
    else
        echo "❌ Test failed!"
        exit 1
    fi

# Run linting and formatting checks
lint:
    uv run ruff check src/ tests/
    uv run ruff format --check src/ tests/

# Fix linting and formatting issues
fix:
    uv run ruff check --fix src/ tests/
    uv run ruff format src/ tests/

# Find dead code
dead:
    uv run vulture src/ .vulture_whitelist.py --min-confidence 80

# Run all checks before committing
check:
    @echo "🔍 Running linting checks..."
    @just lint
    @echo ""
    @echo "🧹 Checking for dead code..."
    @just dead
    @echo ""
    @echo "🧪 Running tests..."
    @just test
    @echo ""
    @echo "✅ All checks passed! Ready to commit."

# Create a backup of all databases
backup:
    #!/usr/bin/env bash
    set -euo pipefail
    
    # Generate timestamp
    TIMESTAMP=$(date +%Y-%m-%d-%H%M%S)
    BACKUP_NAME="alpha-brain-backup-${TIMESTAMP}"
    BACKUP_DIR="/tmp/${BACKUP_NAME}"
    
    echo "Creating backup: ${BACKUP_NAME}.tar.gz"
    
    # Create backup directory
    mkdir -p "${BACKUP_DIR}/postgres"
    
    # Dump Postgres database
    echo "Backing up Postgres database..."
    docker compose exec -T postgres pg_dump -U alpha -d alpha_brain | gzip > "${BACKUP_DIR}/postgres/alpha_brain.sql.gz"
    
    # Create metadata file
    cat > "${BACKUP_DIR}/metadata.json" << EOF
    {
        "version": "1.0.0",
        "timestamp": "${TIMESTAMP}",
        "databases": ["postgres"]
    }
    EOF
    
    # Create tarball
    tar -czf "${BACKUP_NAME}.tar.gz" -C /tmp "${BACKUP_NAME}"
    rm -rf "${BACKUP_DIR}"
    
    echo "Backup complete: ${BACKUP_NAME}.tar.gz"
    echo "Size: $(du -h ${BACKUP_NAME}.tar.gz | cut -f1)"

# Restore databases from backup
restore backup_file:
    #!/usr/bin/env bash
    set -euo pipefail
    
    if [ ! -f "{{backup_file}}" ]; then
        echo "Error: Backup file '{{backup_file}}' not found"
        exit 1
    fi
    
    echo "Restoring from: {{backup_file}}"
    
    # Extract backup
    TEMP_DIR=$(mktemp -d)
    tar -xzf "{{backup_file}}" -C "${TEMP_DIR}"
    
    # Find the backup directory (should be the only directory in TEMP_DIR)
    BACKUP_DIR=$(find "${TEMP_DIR}" -mindepth 1 -maxdepth 1 -type d | head -1)
    
    if [ ! -f "${BACKUP_DIR}/metadata.json" ]; then
        echo "Error: Invalid backup file (missing metadata.json)"
        rm -rf "${TEMP_DIR}"
        exit 1
    fi
    
    # Stop the stack
    echo "Stopping services..."
    docker compose down
    
    # Start only Postgres
    echo "Starting Postgres..."
    docker compose up -d postgres
    docker compose exec postgres sh -c 'until pg_isready -U alpha; do sleep 1; done'
    
    # Drop and recreate database
    echo "Recreating database..."
    docker compose exec postgres psql -U alpha -d postgres -c "DROP DATABASE IF EXISTS alpha_brain;"
    docker compose exec postgres psql -U alpha -d postgres -c "CREATE DATABASE alpha_brain;"
    
    # Restore Postgres
    if [ -f "${BACKUP_DIR}/postgres/alpha_brain.sql.gz" ]; then
        echo "Restoring Postgres database..."
        gunzip -c "${BACKUP_DIR}/postgres/alpha_brain.sql.gz" | docker compose exec -T postgres psql -U alpha -d alpha_brain
    fi
    
    # Clean up
    rm -rf "${TEMP_DIR}"
    
    # Start the full stack
    echo "Starting all services..."
    docker compose up -d
    
    echo "Restore complete!"