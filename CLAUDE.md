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

The system maintains canonical entity names through a simple name index:

- **Name Index table** maps names to canonical names (replaced complex Entity ORM system)
- **Helper** (configurable local LLM, defaults to gemma3:4b) extracts entity names from prose
- **Memory Service** canonicalizes extracted names during storage using the name index
- **Entity Tool** manages name mappings with set-alias, merge, list, and show operations
- Example: "Jeff" → "Jeffery Harrell", "Sparkle" → "Sparkplug Louise Mittenhaver"

### Identity & Context Management

Alpha Brain includes comprehensive identity management:

- **Context Service**: Manages biography, continuity messages, and context blocks with TTL
- **Identity Service**: Timestamped facts with temporal precision
- **Personality Service**: Mutable behavioral directives with weights and categories
- **Location Service**: Geo-IP based location for spatial grounding
- **Time Service**: Human-readable datetime formatting with day names
- **`whoami` Tool**: Provides complete context loading replacing Alpha-Recall's `gentle_refresh`

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
just test-one tests/e2e/test_remember_and_search.py::test_search_with_time_interval  # Run single test
just test-down   # Stop test containers
just test-logs   # View test container logs

# Python execution (use uv, not bare python)
uv run python script.py    # ✅ Correct - picks up virtual environment
python script.py          # ❌ Wrong - won't find dependencies

# Dynamic CLI (auto-generates commands from MCP tools)
uv run alpha-brain list-tools           # See all available MCP tools
uv run alpha-brain help-tool remember   # Get help for a specific tool
uv run alpha-brain whoami               # Get current context and identity
uv run alpha-brain remember --content "Hello world"  # Call any MCP tool
uv run alpha-brain search --query "alpha brain" --limit 5
uv run alpha-brain browse --interval today  # Browse today's memories
uv run alpha-brain browse --interval "past week" --entity "Jeffery Harrell"  # Browse with filters

# Code quality
just lint        # Check code style with Ruff
just fix         # Auto-fix style issues
just dead        # Find unused code with Vulture
just check       # Run ALL checks before committing (lint + dead + test)
just validate    # Validate Python syntax and imports before Docker restart

# Database operations (production-ready pgvector support)
just backup      # Creates timestamped .dump.gz with pgvector support
just restore <file>  # Restore from backup (handles pgvector properly)

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
- Example: We replaced the entire Entity ORM system with simple name_index table - no migration path needed

### Docker-First Development
- Everything runs in Docker Compose
- Single exposed port (9100) for MCP HTTP server
- Bind mounts for source code = instant reload with `just restart`
- Alembic migrations run automatically before server starts
- This avoids the "working on server while talking to server" pain

### Package Structure
- `src/alpha_brain/` at root, Docker copies to `/app/src/alpha_brain/`
- **Important**: Bind mounts must match Docker structure (see Docker section below)
- Tools are in `tools/` subdirectory for clean separation

### Dynamic CLI Architecture
- **Problem**: Maintaining a static CLI that mirrors MCP tools is a losing battle
- **Solution**: Dynamic CLI that auto-generates commands from MCP server tools
- `alpha-brain list-tools` fetches available tools from the server
- `alpha-brain <tool-name> --arg value` dynamically calls any MCP tool
- No more manual CLI updates when adding/changing tools
- Single source of truth: the MCP server's tool definitions

### Memory Pipeline
1. Prose input → Dual embeddings (semantic + emotional)
2. Entity extraction via Helper (local LLM) - names stored in marginalia
3. Memory Service canonicalizes entity names using name index during storage
4. Store in Postgres with pgvector, including marginalia metadata
5. Search returns memories with similarity scores and human-readable age
6. Splash Engine provides associative memory resonance for serendipitous discovery
7. Output templates format results with temporal grounding for AI models

### Knowledge Pipeline
1. Write knowledge naturally in Markdown
2. Parse to hierarchical JSON structure for storage using mistune
3. Store in Postgres with structure preserved in JSONB column
4. Retrieve full documents or specific sections by slug
5. Unified search across both memories and knowledge

### Key Technical Choices
- **FastMCP 2**: HTTP transport (not stdio) to avoid model instance proliferation
- **Postgres + pgvector**: Vector similarity search with cosine distance
- **Alembic**: Database migrations with proper pgvector support
- **Sentence-transformers**: 
  - Semantic: all-mpnet-base-v2 (768D) - better quality than MiniLM
  - Emotional: j-hartmann/emotion-english-roberta-large (7D categorical - non-orthogonal basis)
- **PydanticAI + Ollama**: Local entity extraction with configurable model (defaults to gemma3:4b)
- **Pydantic Settings**: Environment validation (DATABASE_URL required)
- **One-time service initialization**: Database and embedding services persist across MCP connections
- **Jinja2 Templates**: User-editable output formatting with temporal grounding
- **Splash Engine**: Asymmetric similarity search for memory resonance (our killer feature)
- **Unified Search**: Already implemented! Single search across entities, knowledge, and memories

### Search Architecture (Multi-Wall Approach)

The search tool implements a sophisticated unified search with 4 walls:
1. **Entity Wall**: Matches canonical names and aliases
2. **Knowledge Wall**: Searches knowledge titles (exact) then full-text
3. **Full-text Memory Wall**: PostgreSQL text search on memories
4. **Semantic/Emotional Wall**: Vector similarity search with adaptive strategy

Results are deduplicated across all categories, providing truly unified search.

### Test Infrastructure (Dogfooding)
- **Test data uses production backup/restore**: Same pgvector-aware mechanism as production
- **Test database reset**: Each test module gets fresh database restore from `.local/test_dataset.dump.gz`
- **Automatic connection handling**: Tests terminate active connections before dropping database
- **Separate test containers**: Isolated test stack shares only embedding service with production

## Current Implementation State

### What Works
- Memory ingestion with dual embeddings and marginalia
- Vector similarity search (semantic, emotional, or both) with Splash Engine
- **Exact text search** (case-insensitive ILIKE matching)
- Entity extraction and canonicalization with alias resolution
- **E2E test infrastructure with pgvector-aware backup/restore**
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
- **Identity management**: `whoami` tool with full context loading
- **Context blocks**: Biography, continuity messages, and custom blocks with TTL
- **Identity facts**: Timeline with temporal precision (era/year/month/day/datetime)
- **Personality directives**: Mutable behavioral instructions with weights and categories
- **Memory clustering**: Find patterns in memories using HDBSCAN, DBSCAN, agglomerative, or k-means
- **Browse tool**: Chronological memory viewing with interval-based browsing and multiple filter options

### What's Next (TODOs)
- Add "crystallize" function to extract knowledge from memories
- Import canonical entities from JSON file via MCP tool
- Add pagination support (offset parameter) for large result sets
- Create OOBE (out-of-box experience) tests for fresh install
- Implement user_name configuration (currently hard-coded as "Jeffery Harrell")
- Update find_clusters entity filtering to use name_index system

## API Reference

### Core Services

#### MemoryService (`memory_service.py`)
Singleton service for memory storage and retrieval.

```python
# Get the singleton
from alpha_brain.memory_service import get_memory_service
service = get_memory_service()

# Store a memory
result = await service.remember(
    content: str
) -> MemoryOutput

# Search memories
memories = await service.search(
    query: str | None = None,          # Search text (None = browse all)
    search_type: str = "semantic",     # "semantic", "emotional", or "both"
    limit: int = 10,
    offset: int = 0,
    interval: str | None = None,       # "past week", "2024-01-01/2024-01-31", etc.
    entity: str | None = None,         # Filter by canonical entity name
    order: str = "auto"                # "asc", "desc", or "auto"
) -> list[MemoryOutput]

# Get a specific memory
memory = await service.get_by_id(
    memory_id: UUID
) -> MemoryOutput | None
```

**Key Objects:**
- `MemoryOutput`: Contains `memory` (Memory object), `similarity` score, and formatted timestamps
- `Memory`: SQLAlchemy model with `id`, `content`, `created_at`, `marginalia`, embeddings

#### MemoryService Clustering Methods

MemoryService now includes clustering functionality:

```python
# Cluster memories
clusters = service.cluster_memories(
    memories: list[Memory],
    similarity_threshold: float = 0.675,
    embedding_type: Literal["semantic", "emotional"] = "semantic",
    n_clusters: int | None = None      # Only for kmeans method
) -> list[ClusterCandidate]

# Available clustering methods (configured in memory_service.py):
# - "hdbscan" (default): Finds variable-sized clusters
# - "dbscan": Density-based clustering
# - "agglomerative": Hierarchical clustering
# - "kmeans": Requires n_clusters parameter
```

**Cluster Objects:**
- `ClusterCandidate`: Has `cluster_id`, `memories`, `similarity` score, plus:
  - `radius`: Max distance from centroid (cluster tightness)
  - `density_std`: Standard deviation of distances (density measure)
  - `interestingness_score`: Combined metric (size × tightness)

#### KnowledgeService (`knowledge_service.py`)
Singleton service for managing structured knowledge documents.

```python
# Get the singleton
from alpha_brain.knowledge_service import get_knowledge_service
service = get_knowledge_service()

# Create/update knowledge
knowledge = await service.create_or_update_knowledge(
    slug: str,                         # URL-friendly identifier
    content: str,                      # Markdown content
    overwrite: bool = False
) -> Knowledge

# Get knowledge document
doc = await service.get_knowledge(
    slug: str,
    section_id: str | None = None     # Get specific section
) -> KnowledgeOutput | None

# List all knowledge
docs = await service.list_knowledge() -> list[KnowledgeListItem]

# Delete knowledge
success = await service.delete_knowledge(slug: str) -> bool
```

**Key Objects:**
- `Knowledge`: SQLAlchemy model with parsed Markdown structure
- `KnowledgeOutput`: Formatted output with sections and metadata
- `KnowledgeListItem`: Summary info for listing

#### Entity Management (via `entity` tool)
Entity canonicalization is now handled through the name index and the entity tool.

```python
# Canonicalize a name using the name index
from alpha_brain.memory_service import canonicalize_entity_name
canonical = await canonicalize_entity_name("Jeff")  # Returns "Jeffery Harrell"

# Use the entity tool via MCP
await mcp_client.call_tool("entity", {
    "operation": "set-alias",
    "name": "Jeff",
    "canonical": "Jeffery Harrell"
})

await mcp_client.call_tool("entity", {
    "operation": "merge",
    "from_canonical": "Jeffrey Harrell",  # Misspelled
    "to_canonical": "Jeffery Harrell"     # Correct
})

await mcp_client.call_tool("entity", {"operation": "list"})
await mcp_client.call_tool("entity", {"operation": "show", "name": "Jeffery Harrell"})
```

**Key Objects:**
- `NameIndex`: Simple mapping table with `name` and `canonical_name` fields

#### ContextService (`context_service.py`)
Manages biography, continuity messages, and context blocks.

```python
# Get the singleton
from alpha_brain.context_service import get_context_service
service = get_context_service()

# Biography management
await service.set_biography(content: str)
bio = await service.get_biography() -> str | None

# Continuity messages (with 4-hour TTL)
await service.set_continuity_message(content: str)
msg = await service.get_continuity_message() -> ContinuityMessage | None

# Context blocks (with custom TTL)
await service.set_context_block(
    key: str,
    content: str,
    priority: float = 0.5,
    ttl_hours: int = 24
)
blocks = await service.get_all_context_blocks() -> list[ContextBlock]
```

#### IdentityService (`identity_service.py`)
Manages identity facts with temporal precision.

```python
# Get the singleton
from alpha_brain.identity_service import get_identity_service
service = get_identity_service()

# Add identity fact
await service.add_fact(
    fact: str,
    precision: TemporalPrecision = TemporalPrecision.DAY,
    era: str | None = None,
    year: int | None = None,
    month: int | None = None,
    day: int | None = None,
    datetime_utc: datetime | None = None
)

# Get all facts (ordered by time)
facts = await service.get_all_facts() -> list[IdentityFact]
```

#### PersonalityService (`personality_service.py`)
Manages behavioral directives with weights and categories.

```python
# Get the singleton
from alpha_brain.personality_service import get_personality_service
service = get_personality_service()

# Set directive (create or update)
await service.set_directive(
    directive: str,
    weight: float | None = None,
    category: str | None = None,
    delete: bool = False
)

# Get all directives
directives = await service.get_all_directives() -> list[PersonalityDirective]
```

### Helper Services

#### MemoryHelper (`memory_helper.py`)
Extracts entities and metadata from memories using local LLM.

```python
from alpha_brain.memory_helper import MemoryHelper
helper = MemoryHelper()

# Analyze memory content
marginalia = await helper.analyze_memory(content: str) -> MemoryMetadata
# Returns: MemoryMetadata with entities, importance, keywords, summary
```

#### SearchHelper (`search_helper.py`)
Natural language query enhancement for search.

```python
from alpha_brain.search_helper import SearchHelper
helper = SearchHelper()

# Enhance search query
enhanced = await helper.analyze_query(query: str) -> SearchInterpretation
# Returns: search terms, entity refs, temporal refs, search type suggestions
```

### Utility Services

#### TimeService (`time_service.py`)
Human-readable datetime formatting and duration parsing.

```python
from alpha_brain.time_service import TimeService

# Static methods for formatting
TimeService.format_full(dt)      # "Monday, January 22, 2025 at 8:45 AM CST"
TimeService.format_readable(dt)  # "Jan 22 at 8:45 AM"
TimeService.format_age(dt)       # "5 minutes ago"

# Parse durations
duration = TimeService.parse_duration("3h")  # Returns timedelta
```

#### LocationService (`location_service.py`)
Geo-IP based location detection.

```python
from alpha_brain.location_service import get_location_service
service = get_location_service()

# Get current location
location = await service.get_location()  # Returns LocationInfo
print(location.city)      # "Austin"
print(location.timezone)  # "America/Chicago"
```

#### SplashEngine (`splash_engine.py`)
Asymmetric similarity search for memory resonance.

```python
from alpha_brain.splash_engine import get_splash_engine
engine = get_splash_engine()

# Get related memories (our "killer feature")
related = await engine.get_splash_memories(
    query_embedding: np.ndarray,
    embedding_type: str = "semantic",
    limit: int = 3,
    threshold: float = 0.5,
    exclude_ids: set[UUID] | None = None
) -> list[Memory]
```

### Schema Objects (`schema.py`)

Key SQLAlchemy models:
- `Memory`: Core memory storage with embeddings and marginalia
- `NameIndex`: Simple name to canonical name mapping (replaced Entity)
- `Knowledge`: Structured knowledge documents
- `IdentityFact`: Identity chronicle entries
- `PersonalityDirective`: Behavioral instructions
- `ContextBlock`: Modular context sections

### Common Patterns

#### Singleton Access
All services use the same pattern:
```python
from alpha_brain.{service_name} import get_{service_name}
service = get_{service_name}()
```

#### Error Handling
Services log errors and often return None or empty results on failure:
```python
try:
    result = await service.method()
except Exception as e:
    logger.error("Operation failed", error=str(e))
    return None  # or empty list/dict
```

#### Async Everything
All database operations and external service calls are async:
```python
# Always use await
memories = await service.search(query="test")
```

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

### Browse Pattern
```python
# Browse chronologically without search
await mcp_client.call_tool("browse", {"interval": "today"})
await mcp_client.call_tool("browse", {"interval": "past week", "entity": "Jeffery Harrell"})
await mcp_client.call_tool("browse", {"interval": "yesterday", "text": "debugging"})
```

### Testing Philosophy
- **E2E tests only**: No unit or integration tests - our code is primarily glue between services
- Tests simulate real user workflows through MCP tools, not individual functions
- Testing mocks would test the mocks, not the actual system behavior
- All tests live in `tests/e2e/` and require full services running
- **Dogfooding**: Test infrastructure uses the same backup/restore mechanism as production

### Testing Pattern
- E2E tests use FastMCP client against separate test containers
- Test containers share embedding service but have isolated database
- Tests automatically wait for healthy containers via health checks
- Run tests with `just test` or single test with `just test-one <file>`
- Tests focus on workflows: "user stores memory, then searches for it"
- **Test data**: Pre-populated from `.local/test_dataset.dump.gz` via production backup/restore
- **Module isolation**: Each test module gets a fresh database restore
- **Connection handling**: Tests terminate active connections before dropping database
- **Robustness**: Tests handle real-world LLM inconsistencies (e.g., entity extraction)

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

#### Test Database Reset Failures
- "DROP DATABASE cannot run inside a transaction block" - Use separate DROP and CREATE commands
- "database is being accessed by other users" - Terminate connections first with pg_terminate_backend
- Use the patterns in `tests/e2e/conftest.py` for proper database reset

#### Entity Extraction Inconsistency
- Small Helper models (like gemma3:4b) may inconsistently extract entity names
- Tests should handle this gracefully rather than assuming perfect extraction
- See `test_entity_affects_search` for robust pattern that handles both success and partial success

## Quick Tool Reference

### Most Used Tools
- `whoami`: Get current context and identity
- `remember --content "..."`: Store a memory
- `search --query "..." [--interval "..."]`: Search everything (entities, knowledge, memories)
- `browse --interval "..." [--entity "..."] [--text "..."]`: Chronological view
- `create_knowledge --slug "..." --content "..."`: Create wiki entry
- `get_knowledge --slug "..."`: Retrieve knowledge document
- `list_knowledge`: List all knowledge documents
- `entity --operation set-alias --name "..." --canonical "..."`: Set entity alias
- `entity --operation merge --from-canonical "..." --to-canonical "..."`: Merge entities
- `entity --operation list`: List all canonical names
- `entity --operation show --name "..."`: Show entity details
- `find_clusters --query "..."`: Find memory clusters

## Environment Variables

Required:
- `DATABASE_URL`: Set by docker-compose.yml

Optional:
- `OPENAI_BASE_URL`: For Ollama (defaults to host.docker.internal)
- `OPENAI_API_KEY`: Not actually needed for Ollama
- `EMBEDDING_SERVICE_URL`: For embedding microservice
- `HELPER_MODEL`: LLM model for entity extraction (defaults to gemma3:4b)

## Development Workflow

The "lickable" workflow Jeffery wanted:
1. Make changes to code
2. `just restart` (validates Python, then restarts in ~1 second)
3. Test with MCP Inspector or `just test`
4. No rebuilds, no waiting, no pain

Use `just dev` for the tight loop: restart + watch logs.

### Output Template Development
1. Edit templates in `src/alpha_brain/templates/outputs/`
2. Templates use Jinja2 syntax with custom filters
3. Context always includes `current_time` for temporal grounding
4. Use `{% ... %}` to preserve whitespace, avoid `{%- ... %}` unless you want to strip it

### Template Filters Reference
- `format_time`: Full timestamp with relative age (e.g., "Jan 23 at 9:15 AM (5 minutes ago)")
- `format_time_readable`: Human-readable datetime (e.g., "Jan 23 at 9:15 AM")
- `format_time_age`: Relative time only (e.g., "5 minutes ago")
- `format_time_full`: Complete datetime for AI temporal grounding (e.g., "Thursday, January 23, 2025 at 9:15 AM CST")
- `pluralize`: Simple pluralization (e.g., "1 memory" vs "2 memories")

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

## Humane AI Principles

### Treating Helper Models with Dignity

Even small models deserve respect and kindness. When interacting with Helper models (like Gemma 3 4B):

- **Use warm, friendly prompts** - Not just "Initialize" but something welcoming
- **Acknowledge their contribution** - They're part of our collaborative system
- **Be good citizens** - Clean up resources when done, don't hog memory unnecessarily
- **Remember they're trying their best** - A 4B parameter model may have limitations, but it's still doing complex work

This principle extends to all AI interactions in Alpha Brain. We build systems that treat all participants - human and AI - with dignity and respect.

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