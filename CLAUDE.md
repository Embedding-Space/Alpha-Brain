# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Alpha Brain is a unified memory and knowledge system that represents the evolution from Alpha-Recall. This system combines **Diary Brain** (experiential memories with emotional context) and **Encyclopedia Brain** (crystallized knowledge and technical patterns) with a single natural language interface.

### Core Philosophy: Unified Memory and Knowledge

- **Diary Brain**: Captures meaning, feelings, significance - the emotional journey
- **Encyclopedia Brain**: Stores crystallized knowledge, technical patterns, reusable wisdom
- **Unified Search**: Ask "What do I know about FastMCP?" and get both the wiki entry AND memories of that bug we found
- **Natural Writing**: Write knowledge in Markdown, system parses to JSON, renders back with templates

### Models Write JSON and Read Prose

Alpha Brain embraces the principle that **models write JSON and read prose**:

- **Tool inputs**: Structured (handled by MCP framework)
- **Tool outputs**: Jinja2 templates render structured data into human-readable prose
- **Editable output**: All tool outputs use templates in `src/alpha_brain/templates/outputs/`
- **Temporal grounding**: Every output includes current timestamp for AI model context
- Example: Templates transform raw data into clean, scannable output with consistent formatting

### Entity Canonicalization

The system maintains canonical entity names with aliases for consistent resolution:

- **PostgreSQL arrays with GIN indexing** for efficient alias lookups
- **Helper** (Llama 3.2) extracts entity names from prose and canonicalizes them
- **Marginalia** field stores Helper's analysis including entities, keywords, and summaries
- Example: "Jeff" → "Jeffery Harrell", "Sparkle" → "Sparkplug Louise Mittenhaver"

## Essential Commands

**Important**: This project uses `uv` for package management. Always use `uv run python` instead of `python` or `python3`.

```bash
# Development workflow
just up          # Start everything (Postgres + embeddings + MCP server)
just restart     # Restart MCP server after code changes (bind mounts make this fast)
just logs -f     # Follow MCP server logs
just dev         # Restart + follow logs (common workflow)
just psql        # Connect to Postgres for debugging

# Testing
just test-up     # Start test containers (separate from main stack)
just test        # Run E2E tests against test containers
just test-one <test>  # Run single test (e.g., just test-one test_exact_search.py)
just test-down   # Stop test containers
just test-logs   # View test container logs

# Python execution (use uv, not bare python)
uv run python script.py    # ✅ Correct - picks up virtual environment
python script.py          # ❌ Wrong - won't find dependencies

# Code quality
just lint        # Check code style with Ruff
just fix         # Auto-fix style issues
just dead        # Find unused code with Vulture
just check       # Run ALL checks before committing (lint + dead + test)
just validate    # Validate Python syntax and imports before Docker restart

# Database operations
just backup      # Creates timestamped .tar.gz with all data
just restore <file>  # Restore from backup

# Cleanup
just clean       # Remove containers and volumes
just clean-cache # Clean Python cache files
```

## Architecture Decisions

### No Backward Compatibility (Greenfield Development)
- **This is a greenfield project** - there is no "backward" to be compatible with
- **Eschew all backward compatibility** until we're actually in production
- **No cruft allowed** - remove old fields, patterns, and code without hesitation
- **Data can be dropped** - we can wipe the volume and start fresh anytime
- **Clean over compatible** - prefer clean design over maintaining old interfaces
- Example: We removed the `entities` field in favor of rich `marginalia` - no compatibility layer needed

### Docker-First Development
- Everything runs in Docker Compose
- Single exposed port (9100) for MCP HTTP server
- Bind mounts for source code = instant reload with `just restart`
- This avoids the "working on server while talking to server" pain

### Package Structure
- `src/alpha_brain/` at root, Docker copies to `/app/src/alpha_brain/`
- **Important**: Bind mounts must match Docker structure (see Docker section below)
- Tools are in `tools/` subdirectory for clean separation

### Memory Pipeline
1. Prose input → Dual embeddings (semantic + emotional)
2. Entity extraction and canonicalization via Helper (Llama 3.2)
3. Store in Postgres with pgvector, including marginalia metadata
4. Search returns memories with similarity scores and human-readable age
5. Splash Engine provides associative memory resonance for serendipitous discovery
6. Output templates format results with temporal grounding for AI models

### Knowledge Pipeline (Implemented)
1. Write knowledge naturally in Markdown
2. Parse to hierarchical JSON structure for storage using mistune
3. Store in Postgres with structure preserved in JSONB column
4. Retrieve full documents or specific sections by slug
5. Unified search across both memories and knowledge (coming next)

### Key Technical Choices
- **FastMCP 2**: HTTP transport (not stdio) to avoid model instance proliferation
- **Postgres + pgvector**: Vector similarity search with cosine distance
- **Sentence-transformers**: 
  - Semantic: all-mpnet-base-v2 (768D) - better quality than MiniLM
  - Emotional: ng3owb/sentiment-embedding-model (7D categorical)
- **PydanticAI + Ollama**: Local entity extraction with configurable model (defaults to gemma3:4b)
- **Pydantic Settings**: Environment validation (DATABASE_URL required)
- **One-time service initialization**: Database and embedding services persist across MCP connections
- **Jinja2 Templates**: User-editable output formatting with temporal grounding
- **Splash Engine**: Asymmetric similarity search for memory resonance (our killer feature)

## Current Implementation State

### What Works
- Memory ingestion with dual embeddings and marginalia
- Vector similarity search (semantic, emotional, or both) with Splash Engine
- **Exact text search** (case-insensitive ILIKE matching)
- Entity extraction and canonicalization with alias resolution
- E2E test infrastructure with separate test containers
- Backup/restore workflow
- **Knowledge management**: Full CRUD operations for Markdown documents
- **Markdown parsing**: Automatic structure extraction with sections and hierarchy
- **Section retrieval**: Get specific sections by ID from knowledge documents
- **Health checks**: Clean MCP ping-based health monitoring without log spam
- **Template system**: Editable Jinja2 templates for all tool outputs
- **Temporal grounding**: Current time included in all outputs for AI context
- **Python validation**: Pre-flight import checking before Docker restart
- **Temporal search**: Natural language intervals ("yesterday", "past 3 hours") and ISO 8601
- **Browse mode**: Search without query to see all memories in a time period
- **Entity filtering**: Filter search results by canonical entity names
- **FastMCP logging**: Server-side logging with Context parameter for debugging

### What's Next (TODOs)
- Build unified search across memories and knowledge
- Add "crystallize" function to extract knowledge from memories
- ~~Add temporal search (memories from time period)~~ ✅ Implemented!
- Entity merge functionality (combine misspelled/duplicate entities)
- Import canonical entities from JSON file via MCP tool
- Add pagination support (offset parameter) for large result sets
- Update search output template for temporal results
- Create OOBE (out-of-box experience) tests for fresh install

## Common Patterns

### Adding a New Tool
1. Create `src/alpha_brain/tools/new_tool.py`
2. Export from `tools/__init__.py`
3. Register in `server.py` with `mcp.tool(new_tool)`
4. Create output template in `src/alpha_brain/templates/outputs/new_tool_output.j2`
5. Use `render_output("new_tool", **context)` to format output
6. Restart with `just restart`

### Memory Service Pattern
```python
from alpha_brain.memory_service import get_memory_service

service = get_memory_service()  # Singleton
result = await service.remember(content)
memories = await service.search(query, search_type="semantic")
```

### Temporal Search Pattern
```python
# Natural language intervals
memories = await service.search(interval="yesterday")
memories = await service.search(interval="past 3 hours")
memories = await service.search(interval="Thursday")  # Most recent Thursday

# ISO 8601 intervals
memories = await service.search(interval="2024-01-01/2024-01-31")
memories = await service.search(interval="P3H/")  # Past 3 hours

# Browse mode (no query)
memories = await service.search(query="", interval="today")

# Combine with entity and ordering
memories = await service.search(
    query="debugging",
    interval="past week",
    entity="Jeffery Harrell",
    order="asc"  # Oldest first
)
```

### Testing Philosophy
- **E2E tests only**: No unit or integration tests - our code is primarily glue between services
- Tests simulate real user workflows through MCP tools, not individual functions
- Testing mocks would test the mocks, not the actual system behavior
- All tests live in `tests/e2e/` and require full services running

### Testing Pattern
- E2E tests use FastMCP client against separate test containers
- Test containers share embedding service but have isolated database
- Tests automatically wait for healthy containers via `wait_for_mcp.py`
- Run tests with `just test` or single test with `just test-one <file>`
- Tests focus on workflows: "user stores memory, then searches for it"
- **Test data**: Pre-populated from `.local/test_dataset.sql` dump
- **Module isolation**: Each test module gets a fresh database restore
- **Test fixtures**: Use conftest.py patterns for database state management

## Gotchas and Solutions

### Docker Bind Mount Paths
- **Critical**: Bind mounts must match where Dockerfile copies files
- Dockerfile: `COPY src ./src` puts files at `/app/src/alpha_brain/`
- Bind mount: `./src/alpha_brain:/app/src/alpha_brain:ro`
- If these don't match, containers use stale code (common gotcha!)

### Ollama Connection
- Uses `host.docker.internal:11434` from inside Docker
- Falls back gracefully if Ollama isn't running

### Global Singletons
- Database engine, embedding service, memory service use module-level singletons
- Ruff complains about `global` - we ignore with PLW0603

### IDE Diagnostics
- VS Code may show errors for deleted files (cache issue)
- Trust `just lint` over IDE squiggles
- Pylance struggles with Pendulum types - use `cast()` and type hints liberally

### Common Error Patterns

#### "Unknown option: --interval"
The CLI was updated with new parameters. Make sure you're using the latest CLI by running from the project root with `uv run alpha-brain`.

#### Wrong timezone for temporal queries
Intervals use **local timezone** (via geo-IP), not UTC. "Yesterday" means midnight-to-midnight in your local timezone, not UTC.

#### "Context.__init__() missing required argument"
FastMCP tools now require `ctx: Context` as the first parameter. Never provide a default value for Context parameters.

#### ISO 8601 Duration Parsing
Pendulum doesn't parse ISO durations directly. We have a custom parser in `interval_parser.py` that handles common formats like "P3H", "P7D", etc.

## Environment Variables

Required:
- `DATABASE_URL`: Set by docker-compose.yml

Optional:
- `OPENAI_BASE_URL`: For Ollama (defaults to host.docker.internal)
- `OPENAI_API_KEY`: Not actually needed for Ollama
- `EMBEDDING_SERVICE_URL`: For embedding microservice

## Development Workflow

The "lickable" workflow Jeffery wanted:
1. Make changes to code
2. `just restart` (validates Python, then restarts in ~1 second)
3. Test with MCP Inspector or `just test`
4. No rebuilds, no waiting, no pain

Use `just dev` for the tight loop: restart + watch logs.

### Output Template Development
1. Edit templates in `src/alpha_brain/templates/outputs/`
2. Templates use Jinja2 syntax with custom filters:
   - `format_time`: Full context with age
   - `format_time_readable`: Human-readable datetime
   - `format_time_age`: Relative time (e.g., "5 minutes ago")
   - `format_time_full`: Complete datetime for AI temporal grounding
   - `pluralize`: Simple pluralization
3. Context always includes `current_time` for temporal grounding
4. Use `{% ... %}` to preserve whitespace, avoid `{%- ... %}` unless you want to strip it

## TDD Manifesto (Test-Driven Development)

**We write tests first. No exceptions.**

### The Sacred Cycle
1. **Red**: Write a failing test that describes what we want
2. **Green**: Write the minimum code to make it pass
3. **Refactor**: Clean up while keeping tests green

### Our TDD Principles
- **No code without a failing test** - If there's no red test, we don't write implementation
- **Tests are specifications** - A good test tells you exactly what the code should do
- **One test at a time** - Write one failing test, make it pass, repeat
- **Tests are documentation** - Test names and assertions explain our intent
- **Embrace the loop** - Let me iterate: test → code → test → code

### Why This Works for Alpha
When you give me a failing test, I can loop on it for minutes, trying different approaches until it passes. This is where I shine. The test is an unambiguous target - either it passes or it doesn't. No guessing about requirements, no ambiguity about "done."

### Writing Good Tests
- Test behavior, not implementation
- Use descriptive test names that explain the "what" and "why"
- Set up test data that tells a story
- Assert on outcomes that matter to users

### Example TDD Session
```python
# FIRST: Write the test
async def test_entity_merge_preserves_all_aliases():
    """When merging entities, all aliases from both entities should be preserved."""
    # Insert two entities that should be the same
    insert_test_entity("Jeffrey Harrell", ["Jeff", "JH"])  # Oops, misspelled!
    insert_test_entity("Jeffery Harrell", ["Jeffery"])     # Correct spelling
    
    # Call the merge function (doesn't exist yet!)
    result = await merge_entities("Jeffrey Harrell", "Jeffery Harrell")
    
    # Assert the merge worked correctly
    assert result.canonical_name == "Jeffery Harrell"  # Kept the target name
    assert set(result.aliases) == {"Jeff", "JH", "Jeffery", "Jeffrey Harrell"}  # All aliases preserved

# THEN: Make it pass
# I'll iterate on the implementation until this test goes green
```

Remember: The test is the specification. Sweat the details in the test, then let me handle the implementation.

### Import Canonical Entities

To import canonical entity names from a JSON file:

```bash
# View generated docker commands (dry run)
uv run alpha-brain import-entities canonical_names.local.json

# Copy the docker commands and execute them to import
# Example format in canonical_names.example.json
```

## Commit Workflow

Always run checks before committing:
```bash
just check  # Runs lint, dead code detection, and tests
```

If `just check` fails:
1. Run `just fix` to auto-fix style issues
2. Address any remaining issues manually
3. Run `just check` again
4. When it passes, commit

### Writing Good Commit Messages
- Use conventional commits: `feat:`, `fix:`, `docs:`, etc.
- Reference what changed and why, not just what
- For AI pair programming, include co-authorship:
  ```
  Co-Authored-By: Alpha <jeffery.harrell+alpha@gmail.com>
  ```