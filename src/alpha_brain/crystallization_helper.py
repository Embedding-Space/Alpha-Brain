"""Helper model for crystallization analysis using interview-based extraction."""

import json
import os
import time
from pathlib import Path
from typing import List

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.settings import ModelSettings
from structlog import get_logger

from alpha_brain.prompts import render_prompt
from alpha_brain.schema import Memory
from alpha_brain.settings import get_settings

logger = get_logger()


class ClusterAnalysis(BaseModel):
    """Analysis results for a memory cluster."""
    
    title: str = Field(
        default="",
        description="A descriptive title for this knowledge cluster"
    )
    summary: str = Field(
        default="",
        description="A comprehensive summary of what this cluster represents"
    )
    patterns: list[str] = Field(
        default_factory=list,
        description="Recurring patterns or themes identified across memories"
    )
    insights: list[str] = Field(
        default_factory=list,
        description="Key insights and lessons learned"
    )
    technical_knowledge: list[str] = Field(
        default_factory=list,
        description="Technical facts, configurations, or procedures worth documenting"
    )
    relationships: list[str] = Field(
        default_factory=list,
        description="Important relationships between people, projects, or concepts"
    )
    crystallizable: bool = Field(
        default=False,
        description="Whether this cluster contains knowledge worth crystallizing"
    )
    suggested_document_type: str = Field(
        default="",
        description="Type of knowledge document this could become (e.g., 'technical guide', 'project history', 'troubleshooting guide')"
    )


class CrystallizationHelper:
    """Helper model for analyzing memory clusters for crystallization."""
    
    def __init__(self):
        """Initialize with Ollama-compatible endpoint from settings."""
        settings = get_settings()
        
        # Set environment variables for pydantic-ai OpenAI model
        if settings.openai_base_url:
            os.environ["OPENAI_BASE_URL"] = str(settings.openai_base_url)
        if settings.openai_api_key:
            os.environ["OPENAI_API_KEY"] = settings.openai_api_key
            
        # Configure the model with temperature=0 for consistency
        self.model_name = settings.helper_model
        self.model = OpenAIModel(
            settings.helper_model, settings=ModelSettings(temperature=0.0)
        )
        
        # Load questions from JSON file
        input_file = Path(__file__).parent / "model_inputs" / "analysis_input.json"
        try:
            with open(input_file) as f:
                data = json.load(f)
                self.questions = [(q["field"], q["prompt"]) for q in data["questions"]]
                logger.info(
                    "Loaded crystallization questions",
                    question_count=len(self.questions),
                    source=str(input_file)
                )
        except Exception as e:
            logger.error(
                "Failed to load questions from JSON",
                error=str(e),
                file=str(input_file)
            )
            # Fallback to empty questions if file not found
            self.questions = []
        
    def parse_list_response(self, response: str) -> list[str]:
        """Parse a list response from the model."""
        items = []
        lines = response.strip().split("\n")
        
        for line in lines:
            stripped_line = line.strip()
            if not stripped_line:
                continue
                
            # Skip "none" responses
            if stripped_line.lower() in ["none", "no items", "n/a"]:
                continue
                
            # Remove list markers
            import re
            match = re.match(r"^(\d+\.|[-*•])\s*(.+)", stripped_line)
            if match:
                item = match.group(2).strip()
            else:
                item = stripped_line
                
            if item:
                items.append(item)
                
        return items
        
    async def analyze_cluster(
        self, 
        memories: List[Memory], 
        similarity_score: float
    ) -> ClusterAnalysis:
        """
        Analyze a cluster of memories for crystallization potential.
        
        Args:
            memories: List of Memory objects in the cluster
            similarity_score: Average similarity score of the cluster
            
        Returns:
            ClusterAnalysis with insights about the cluster
        """
        try:
            start_time = time.time()
            
            logger.info(
                "Starting cluster analysis",
                memory_count=len(memories),
                similarity=similarity_score,
                model=self.model_name
            )
            
            # Prepare memories for the prompt
            memory_dicts = [
                {
                    "content": m.content,
                    "created_at": m.created_at.isoformat()
                }
                for m in memories
            ]
            
            # Create agent with cluster context
            system_prompt = render_prompt(
                "crystallization_analysis.j2",
                memories=memory_dicts,
                memory_count=len(memories),
                similarity_score=similarity_score
            )
            
            logger.debug("System prompt created", prompt_length=len(system_prompt))
            
            # Log first 500 chars to verify content is there
            logger.debug("System prompt preview", preview=system_prompt[:500])
            
            agent = Agent(self.model, system_prompt=system_prompt, retries=1)
            
            # Initialize analysis
            analysis = ClusterAnalysis()
            
            # Ask each question sequentially
            questions_answered = 0
            print(f"\n{'='*60}")
            print(f"CRYSTALLIZATION ANALYSIS")
            print(f"Model: {self.model_name}")
            print(f"Memories: {len(memories)}")
            print(f"Similarity: {similarity_score:.3f}")
            print(f"{'='*60}\n")
            
            for i, (field_name, question) in enumerate(self.questions, 1):
                try:
                    print(f"[Q{i}] {field_name.upper()}")
                    print(f"     {question}")
                    print(f"     ", end="", flush=True)  # Show we're waiting
                    
                    response = await agent.run(question)
                    
                    # Check if we got a response
                    if not response or not hasattr(response, 'output'):
                        print("[No response]")
                        logger.warning(f"No output from agent for {field_name}")
                        continue
                        
                    answer = response.output.strip()
                    print(f"\n[A{i}] {answer}\n")
                    questions_answered += 1
                    
                    # Parse response based on field type
                    if field_name in ["patterns", "insights", "technical_knowledge", "relationships"]:
                        # List fields
                        parsed_items = self.parse_list_response(answer)
                        setattr(analysis, field_name, parsed_items)
                        if parsed_items:
                            print(f"     (Parsed {len(parsed_items)} items)")
                    elif field_name == "crystallizable":
                        # Boolean field
                        analysis.crystallizable = answer.lower() in ["yes", "true", "1"]
                        print(f"     (Parsed as: {analysis.crystallizable})")
                    else:
                        # String fields
                        setattr(analysis, field_name, answer)
                    
                    print()  # Extra line between Q&A pairs
                        
                except Exception as e:
                    print(f"[ERROR] {type(e).__name__}: {str(e)}\n")
                    logger.warning(
                        f"Failed to get answer for {field_name}",
                        error=str(e),
                        question=question,
                        error_type=type(e).__name__
                    )
                    # Continue with other questions
            
            # If we didn't get any answers, that's a problem
            if questions_answered == 0:
                logger.error("No questions were answered by the agent")
                raise ValueError("Agent failed to answer any questions")
                    
            elapsed = time.time() - start_time
            
            # Print summary
            print(f"\n{'='*60}")
            print(f"ANALYSIS COMPLETE")
            print(f"Time: {elapsed:.2f}s")
            print(f"Questions answered: {questions_answered}/{len(self.questions)}")
            print(f"Crystallizable: {analysis.crystallizable}")
            print(f"{'='*60}\n")
            
            logger.info(
                "cluster_analyzed",
                duration_seconds=elapsed,
                memory_count=len(memories),
                crystallizable=analysis.crystallizable,
                patterns_found=len(analysis.patterns),
                insights_found=len(analysis.insights)
            )
            
            return analysis
            
        except Exception as e:
            logger.error(
                "cluster_analysis_failed", 
                error=str(e), 
                error_type=type(e).__name__
            )
            # Return minimal analysis on failure
            return ClusterAnalysis(
                title=f"Cluster of {len(memories)} memories",
                summary="Analysis failed",
                patterns=[],
                insights=[],
                technical_knowledge=[],
                relationships=[],
                crystallizable=False,
                suggested_document_type=""
            )
            
    async def close(self):
        """Clean up resources."""
        # No cleanup needed with environment variable approach
        pass


# Singleton instance
_crystallization_helper = None


def get_crystallization_helper() -> CrystallizationHelper:
    """Get the crystallization helper singleton."""
    global _crystallization_helper
    if _crystallization_helper is None:
        _crystallization_helper = CrystallizationHelper()
    return _crystallization_helper