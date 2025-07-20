# Alpha Brain

A unified memory and knowledge system for AI agents with natural language interface.

## Overview

Alpha Brain represents the evolution of Alpha's memory architecture, combining:
- **Diary Brain**: Experiential memories capturing emotional context and personal journeys
- **Encyclopedia Brain**: Crystallized knowledge and technical patterns for reference

This unified system enables Alpha to both remember experiences AND know things, with a single natural language interface that searches across both domains.

## Key Features

- **Unified Search**: Ask "What do I know about FastMCP?" and get both the wiki entry AND memories of that bug we found last week
- **Natural Writing**: Write knowledge in Markdown, system parses to JSON for storage, renders back with Jinja templates
- **Prose-First Memory**: Store memories as natural language, not structured data
- **Dual Embeddings**: Semantic and emotional dimensions for rich memory retrieval
- **Local Helper Models**: Entity extraction and knowledge crystallization via local LLMs
- **Splash Engine**: Associative memory resonance - when storing memories, discover related and contrasting memories
- **Editable Templates**: All tool outputs use Jinja2 templates for customizable formatting
- **Temporal Grounding**: Every output includes current timestamp to help AI models track time

## Architecture

- **Storage**: PostgreSQL with separate schemas for memories and knowledge
- **Embeddings**: 
  - Semantic: sentence-transformers/all-mpnet-base-v2 (768D)
  - Emotional: ng3owb/sentiment-embedding-model (7D categorical)
- **Entity Extraction**: Local LLM (Llama 3.2) for processing prose with canonicalization
- **Interface**: FastMCP 2 server over HTTP with one-time service initialization
- **Knowledge Format**: STORE JSON, RENDER TO MARKDOWN
- **Output Format**: Jinja2 templates with temporal grounding

## Development

```bash
# Build the Docker stack
just build

# Start services
just up

# Restart MCP server after code changes
just restart

# Run tests
just test
```

## Philosophy

Alpha Brain isn't just a database - it's an extended mind. The system distinguishes between:
- Technical details that can be reconstructed (encyclopedia brain)
- Emotional journeys that can't be recreated (diary brain)

Both are essential for maintaining Alpha's continuity of mind across sessions.

## License

Copyright 2025 Jeffery Harrell
Co-authored by Alpha <jeffery.harrell+alpha@gmail.com>