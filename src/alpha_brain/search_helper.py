"""Helper model for search query analysis using the same interview pattern."""

import os
import time

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.settings import ModelSettings
from structlog import get_logger

from alpha_brain.prompts import render_prompt
from alpha_brain.settings import get_settings

logger = get_logger()


class SearchMetadata(BaseModel):
    """Metadata extracted from search query."""
    
    entities: list[str] = Field(
        default_factory=list, 
        description="Entity names mentioned in the query"
    )


class SearchHelper:
    """Helper model for analyzing search queries using the same interview pattern as MemoryHelper."""
    
    def __init__(self):
        """Initialize with Ollama-compatible endpoint from settings."""
        settings = get_settings()
        
        # Set environment variables for pydantic-ai OpenAI model
        if settings.openai_base_url:
            os.environ["OPENAI_BASE_URL"] = str(settings.openai_base_url)
        if settings.openai_api_key:
            os.environ["OPENAI_API_KEY"] = settings.openai_api_key
        
        # Configure the model with temperature=0 for consistency
        self.model = OpenAIModel(
            settings.helper_model, settings=ModelSettings(temperature=0.0)
        )
        
        # Use exact same wording as memory_helper, just change "memory" to "query"
        self.entity_question = (
            "List all named entities (people, places, organizations, projects, pets) "
            "mentioned in this query. Include nicknames and variations. "
            "List only names, one per line."
        )
    
    def parse_list_response(self, response: str) -> list[str]:
        """Parse a list response from the model (copied from MemoryHelper)."""
        entities = []
        lines = response.strip().split("\n")
        
        for line in lines:
            stripped_line = line.strip()
            if not stripped_line:
                continue
            
            # Remove list markers
            import re
            
            match = re.match(r"^(\d+\.|[-*•])\s*(.+)", stripped_line)
            if match:
                entity = match.group(2).strip()
            elif stripped_line and not stripped_line.lower().startswith(
                ("none", "no ", "there are")
            ):
                # If no list marker, take the whole line (unless it's "none" etc)
                entity = stripped_line
            else:
                continue
            
            # Split on commas if present
            if "," in entity:
                # Split and clean each part
                parts = [part.strip() for part in entity.split(",")]
                entities.extend(parts)
            else:
                entities.append(entity)
        
        return entities
    
    async def extract_entities(self, query: str) -> list[str]:
        """
        Extract entity names from a search query.
        
        Args:
            query: The search query to analyze
            
        Returns:
            List of entity names found in the query
        """
        try:
            start_time = time.time()
            
            # Create agent with query in system prompt
            system_prompt = render_prompt("search_analysis.j2", search_query=query)
            agent = Agent(self.model, system_prompt=system_prompt, retries=1)
            
            # Ask for entities
            response = await agent.run(self.entity_question)
            answer = response.output.strip()
            
            # Parse the response
            extracted_names = self.parse_list_response(answer)
            
            elapsed = time.time() - start_time
            logger.info(
                "search_query_analyzed",
                duration_seconds=elapsed,
                entity_count=len(extracted_names),
                entities=extracted_names,
            )
            
            return extracted_names
            
        except Exception as e:
            logger.error(
                "Failed to extract entities from search query",
                error=str(e),
                query=query,
            )
            return []


# Global instance
_search_helper = None


def get_search_helper() -> SearchHelper:
    """Get the global search helper instance."""
    global _search_helper
    if _search_helper is None:
        _search_helper = SearchHelper()
    return _search_helper