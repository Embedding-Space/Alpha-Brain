# Alpha Brain Development Commands

# Default command - show help
default:
    @just --list

# === MAIN STACK ===

# Build Docker images
build:
    docker compose build

# Start everything (production + test containers)
up:
    docker compose up -d --wait
    @echo "✅ All services ready!"
    @echo "   Production: http://localhost:9100/mcp/"
    @echo "   Testing:    http://localhost:9101/mcp/"

# Stop everything (test first, then production)
down:
    docker compose --profile test down
    docker compose down

# Restart all services
bounce: down up
    @echo "🔄 All services restarted!"

# Restart MCP server (picks up code changes instantly)
restart:
    docker compose restart alpha-brain-mcp

# Dev mode - restart and watch logs
dev: restart
    just logs -f

# Show logs
logs *args:
    docker compose logs alpha-brain-mcp {{args}}

# Connect to production database (interactive or with command)
psql *args:
    docker compose exec postgres psql -U alpha -d alpha_brain {{args}}

# === TESTING (E2E with populated data) ===

# Start test containers (if not already running)
test-up:
    @docker compose --profile test up -d --wait

# Stop test containers  
test-down:
    @docker compose --profile test down

# Run all E2E tests (assumes populated test database)
test:
    @echo "🧪 Running E2E tests..."
    @env MCP_TEST_URL="http://localhost:9101/mcp/" uv run pytest tests/e2e/ -v -s

# Run specific test
test-one test_path: test-up
    @env MCP_TEST_URL="http://localhost:9101/mcp/" uv run pytest {{test_path}} -v -s

# Show test logs
test-logs *args:
    docker compose logs test-mcp {{args}}

# === FUTURE: OOBE TESTING ===
# TODO: Add out-of-box experience tests
# oobe:
#     @echo "🎁 Testing fresh install experience..."
#     # Test with completely empty database
#     # Verify schema creation, first memory, etc.

# === CODE QUALITY ===

# Lint code
lint:
    @uv run ruff check src/ tests/

# Fix code style  
fix:
    @uv run ruff check --fix src/ tests/
    @uv run ruff format src/ tests/

# Find dead code
dead:
    @uv run vulture src/ .vulture_whitelist.py --min-confidence 80

# Validate Python files compile
validate:
    @uv run python scripts/validate_python.py

# Run all checks before committing
check:
    @just lint
    @just dead
    @just test
    @echo "✅ All checks passed!"

# === UTILITIES ===

# Full cleanup - remove all containers and volumes
clean: down
    docker compose down -v
    rm -rf .local/__pycache__

# Clear Python cache
clean-cache:
    @find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    @find . -type f -name "*.pyc" -delete 2>/dev/null || true

# Backup production database (pgvector-aware)
backup:
    @echo "💾 Creating backup with pgvector support..."
    @docker compose exec -T postgres pg_dump -U alpha -d alpha_brain -Fc -f /tmp/backup.dump
    @docker compose exec -T postgres cat /tmp/backup.dump | gzip > "backup-$(date +%Y%m%d-%H%M%S).dump.gz"
    @docker compose exec -T postgres rm /tmp/backup.dump
    @echo "✅ Backup saved in custom format!"

# Restore production database (pgvector-aware)
restore backup_file:
    @echo "⚠️  This will overwrite the production database! Continue? (y/N)"
    @read -r response && [[ "$$response" =~ ^[Yy]$$ ]] || exit 0
    @echo "🔄 Preparing restore..."
    # Drop and recreate database to ensure clean state
    @docker compose exec -T postgres psql -U alpha -d postgres -c "DROP DATABASE IF EXISTS alpha_brain;"
    @docker compose exec -T postgres psql -U alpha -d postgres -c "CREATE DATABASE alpha_brain;"
    # Create vector extension BEFORE restore
    @docker compose exec -T postgres psql -U alpha -d alpha_brain -c "CREATE EXTENSION IF NOT EXISTS vector;"
    # Restore the data
    @gunzip -c "{{backup_file}}" | docker compose exec -T postgres pg_restore -U alpha -d alpha_brain -Fc --if-exists --clean --no-owner
    @echo "✅ Database restored successfully!"

# Create a clean dump for test data (no memories, just schema + entities)
create-test-dataset:
    @echo "🧪 Creating clean test dataset..."
    # Dump schema and specific tables only (no memories)
    @docker compose exec -T postgres pg_dump -U alpha -d alpha_brain \
        --schema-only \
        --no-owner \
        --no-privileges \
        > .local/test_dataset_schema.sql
    # Append entity data
    @docker compose exec -T postgres pg_dump -U alpha -d alpha_brain \
        --data-only \
        --no-owner \
        --table=entities \
        --table=context \
        --table=identity_facts \
        --table=knowledge \
        >> .local/test_dataset_schema.sql
    @mv .local/test_dataset_schema.sql .local/test_dataset.sql
    @echo "✅ Test dataset created!"