"""Helper model for entity extraction and other memory processing tasks."""

import os

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from structlog import get_logger

from alpha_brain.prompts import DEFAULT_CANONICAL_MAPPINGS, render_prompt
from alpha_brain.settings import get_settings

logger = get_logger()


class ExtractedEntities(BaseModel):
    """Entities extracted from prose."""

    entities: list[str] = Field(
        default_factory=list,
        description="List of proper nouns/entities found in the text",
    )
    canonical_mappings: dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of found names to canonical forms (e.g., 'Jeffery' -> 'Jeffery Harrell')",
    )


class MemoryHelper:
    """Helper model for processing memories using a small local LLM."""

    def __init__(self):
        """Initialize with Ollama-compatible endpoint from settings."""
        settings = get_settings()

        # Set environment variables for pydantic-ai OpenAI model
        if settings.openai_base_url:
            os.environ["OPENAI_BASE_URL"] = str(settings.openai_base_url)
        if settings.openai_api_key:
            os.environ["OPENAI_API_KEY"] = settings.openai_api_key

        # Configure the model - using Ollama's OpenAI compatibility
        self.model = OpenAIModel(settings.ollama_model)

        # Create agent for entity extraction with retries
        system_prompt = render_prompt(
            "entity_extraction.j2",
            examples=DEFAULT_CANONICAL_MAPPINGS,
            strict_json=True,
            model_specific_hints="For Llama models: Focus on returning clean JSON without markdown formatting.",
        )

        self.entity_agent = Agent(
            self.model,
            output_type=ExtractedEntities,
            retries=1,  # Reduced retries for faster failures
            system_prompt=system_prompt,
        )

    async def extract_entities(self, content: str) -> ExtractedEntities:
        """
        Extract entities from prose content.

        Args:
            content: The prose to analyze

        Returns:
            ExtractedEntities with found entities and canonical mappings
        """
        try:
            result = await self.entity_agent.run(content)
            logger.info(
                "entities_extracted",
                entity_count=len(result.output.entities),
                mapping_count=len(result.output.canonical_mappings),
            )
            return result.output

        except Exception as e:
            logger.error(
                "entity_extraction_failed", error=str(e), error_type=type(e).__name__
            )
            # Return empty result on failure - prose is still valuable
            return ExtractedEntities()

    async def close(self):
        """Clean up resources."""
        # No cleanup needed with environment variable approach


# Quick test function (only when run directly)
if __name__ == "__main__":
    import asyncio

    async def test_extraction():
        """Test the entity extraction with a sample."""
        # Need to import here to avoid circular imports
        from alpha_brain.helper import MemoryHelper

        helper = MemoryHelper()

        test_content = """
        Jeffery and I had coffee this morning. We talked about Project Alpha 
        and how Kylee is traveling to Chicago for her Junior League meeting. 
        David Hannah called to discuss the new Tagline features.
        """

        try:
            result = await helper.extract_entities(test_content)
            print(f"Entities: {result.entities}")
            print(f"Mappings: {result.canonical_mappings}")
        finally:
            await helper.close()

    asyncio.run(test_extraction())
