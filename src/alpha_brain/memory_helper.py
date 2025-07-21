"""Helper model for memory analysis using interview-based extraction."""

import os
import time

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.settings import ModelSettings
from structlog import get_logger

from alpha_brain.entity_service import get_entity_service
from alpha_brain.prompts import render_prompt
from alpha_brain.settings import get_settings

logger = get_logger()


class MemoryMetadata(BaseModel):
    """Rich metadata extracted from memory through sequential questions."""

    # Canonical entities found in the memory
    entities: list[str] = Field(
        default_factory=list, description="Canonicalized entity names"
    )
    unknown_entities: list[str] = Field(
        default_factory=list, description="Entity names that couldn't be canonicalized"
    )

    # Other metadata
    importance: int = Field(
        default=3, ge=1, le=5, description="Importance rating from 1-5"
    )
    keywords: list[str] = Field(
        default_factory=list,
        description="Key search terms for finding this memory later",
    )
    summary: str = Field(
        default="", description="Brief one-sentence summary of the memory"
    )


class MemoryHelper:
    """Helper model for analyzing memories using sequential questions."""

    def __init__(self, entity_service=None):
        """Initialize with Ollama-compatible endpoint from settings."""
        settings = get_settings()
        self.entity_service = entity_service or get_entity_service()

        # Set environment variables for pydantic-ai OpenAI model
        if settings.openai_base_url:
            os.environ["OPENAI_BASE_URL"] = str(settings.openai_base_url)
        if settings.openai_api_key:
            os.environ["OPENAI_API_KEY"] = settings.openai_api_key

        # Configure the model with temperature=0 for consistency
        self.model = OpenAIModel(
            settings.helper_model, settings=ModelSettings(temperature=0.0)
        )

        # Define our interview questions
        self.questions = [
            (
                "names",
                "List all named entities (people, places, organizations, projects, pets) mentioned in this memory. Include nicknames and variations. List only names, one per line.",
            ),
            ("importance", "Rate the importance from 1-5. Output only the number."),
            (
                "keywords",
                "What are 3-5 keywords that would help find this memory later? List only the keywords.",
            ),
            ("summary", "Summarize this memory in one sentence."),
        ]

    def parse_list_response(self, response: str) -> list[str]:
        """Parse a list response from the model."""
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

    async def analyze_memory(self, content: str) -> MemoryMetadata:
        """
        Analyze memory content through sequential questions.

        Args:
            content: The prose memory to analyze

        Returns:
            MemoryMetadata with rich information about the memory
        """
        try:
            start_time = time.time()

            # Create agent with memory in system prompt
            system_prompt = render_prompt("memory_analysis.j2", memory_content=content)
            agent = Agent(self.model, system_prompt=system_prompt, retries=1)

            # Initialize metadata
            metadata = MemoryMetadata()
            extracted_names = []

            # Ask each question sequentially
            for field_name, question in self.questions:
                try:
                    response = await agent.run(question)
                    answer = response.output.strip()

                    # Parse response based on field type
                    if field_name == "names":
                        # Extract all named entities
                        extracted_names = self.parse_list_response(answer)
                    elif field_name == "keywords":
                        # List fields
                        setattr(metadata, field_name, self.parse_list_response(answer))
                    elif field_name == "importance":
                        # Integer field
                        try:
                            importance = int(answer.strip())
                            metadata.importance = max(
                                1, min(5, importance)
                            )  # Clamp to 1-5
                        except ValueError:
                            logger.warning(f"Could not parse importance: {answer}")
                            metadata.importance = 3
                    else:
                        # String fields (emotional_tone, summary)
                        setattr(metadata, field_name, answer)

                except Exception as e:
                    logger.warning(
                        f"Failed to get answer for {field_name}",
                        error=str(e),
                        question=question,
                    )
                    # Continue with other questions

            # Canonicalize the extracted names
            logger.info(
                "Names extraction result",
                extracted_names=extracted_names,
                count=len(extracted_names) if extracted_names else 0,
            )

            if extracted_names:
                canonicalization_result = await self.entity_service.canonicalize_names(
                    extracted_names
                )
                metadata.entities = canonicalization_result["entities"]
                metadata.unknown_entities = canonicalization_result["unknown_entities"]

                logger.info(
                    "CANONICALIZATION COMPLETE",
                    extracted=len(extracted_names),
                    canonical=len(metadata.entities),
                    unknown_count=len(metadata.unknown_entities),
                    entities=metadata.entities,
                    unknown_entities=metadata.unknown_entities,
                )

            elapsed = time.time() - start_time
            logger.info(
                "memory_analyzed",
                duration_seconds=elapsed,
                entity_count=len(metadata.entities),
                unknown_count=len(metadata.unknown_entities),
                importance=metadata.importance,
            )

            return metadata

        except Exception as e:
            logger.error(
                "memory_analysis_failed", error=str(e), error_type=type(e).__name__
            )
            # Return minimal metadata on failure
            return MemoryMetadata(summary=content[:100] + "...")

    async def close(self):
        """Clean up resources."""
        # No cleanup needed with environment variable approach


# Quick test function (only when run directly)
if __name__ == "__main__":
    import asyncio

    async def test_analysis():
        """Test the memory analysis with a sample."""
        helper = MemoryHelper()

        test_content = """
        Jeffery and I had coffee this morning. We talked about Project Alpha 
        and how Kylee is traveling to Chicago for her Junior League meeting. 
        David Hannah called to discuss the new Tagline features. I'm feeling
        really excited about the progress we're making!
        """

        try:
            result = await helper.analyze_memory(test_content)
            print(f"Canonical entities: {result.entities}")
            print(f"Unknown entities: {result.unknown_entities}")
            print(f"Importance: {result.importance}")
            print(f"Keywords: {result.keywords}")
            print(f"Summary: {result.summary}")
        finally:
            await helper.close()

    asyncio.run(test_analysis())
