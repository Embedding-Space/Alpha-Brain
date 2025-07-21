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
    docker compose --profile test up -d --wait
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

# Backup production database
backup:
    @echo "💾 Creating backup..."
    @docker compose exec -T postgres pg_dump -U alpha -d alpha_brain | gzip > "backup-$(date +%Y%m%d-%H%M%S).sql.gz"
    @echo "✅ Backup saved!"

# Restore production database
restore backup_file:
    @echo "⚠️  This will overwrite the production database! Continue? (y/N)"
    @read -r response && [[ "$$response" =~ ^[Yy]$$ ]] || exit 0
    @gunzip -c "{{backup_file}}" | docker compose exec -T postgres psql -U alpha -d alpha_brain
    @echo "✅ Restored from {{backup_file}}"