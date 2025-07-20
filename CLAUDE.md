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
- **Tool outputs**: Prose wrapped in JSON for human readability
- Instead of `{"memory_id": "...", "similarity": 0.46}`, return narrative descriptions
- Example: `"Found memory from 23 minutes ago (similarity: 0.46): 'The cat sat on the mat.'"`
- This aligns with the prose-first philosophy and makes tools more conversational

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
2. Optional entity extraction with Llama 3.2 (can fail gracefully)
3. Store in Postgres with pgvector
4. Search returns memories with similarity scores and human-readable age

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
  - Emotional: ng3owb/sentiment-embedding-model (1024D)
- **PydanticAI + Ollama**: Local entity extraction with Llama 3.2
- **Pydantic Settings**: Environment validation (DATABASE_URL required)

## Current Implementation State

### What Works
- Memory ingestion with dual embeddings
- Vector similarity search (semantic, emotional, or both)
- **Exact text search** (case-insensitive ILIKE matching)
- Entity extraction via local Llama 3.2
- E2E test infrastructure with separate test containers
- Backup/restore workflow
- **Knowledge management**: Full CRUD operations for Markdown documents
- **Markdown parsing**: Automatic structure extraction with sections and hierarchy
- **Section retrieval**: Get specific sections by ID from knowledge documents

### What's Next (TODOs)
- Build unified search across memories and knowledge
- Add "crystallize" function to extract knowledge from memories
- Add temporal search (memories from time period)
- Add entity-based search (all memories about X)
- CLI tool for dogfooding (`uv run alpha-brain remember`)

## Common Patterns

### Adding a New Tool
1. Create `src/alpha_brain/tools/new_tool.py`
2. Export from `tools/__init__.py`
3. Register in `server.py` with `mcp.tool(new_tool)`
4. Restart with `just restart`

### Memory Service Pattern
```python
from alpha_brain.memory_service import get_memory_service

service = get_memory_service()  # Singleton
result = await service.remember(content)
memories = await service.search(query, search_type="semantic")
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
2. `just restart` (1 second)
3. Test with MCP Inspector or `just test`
4. No rebuilds, no waiting, no pain

Use `just dev` for the tight loop: restart + watch logs.

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