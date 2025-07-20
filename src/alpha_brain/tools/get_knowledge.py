"""Tool for retrieving knowledge documents."""

from alpha_brain.database import get_db
from alpha_brain.knowledge_service import KnowledgeService
from alpha_brain.markdown_parser import get_table_of_contents


async def get_knowledge(slug: str, section: str | None = None) -> str:
    """Retrieve a knowledge document by its slug.
    
    Args:
        slug: The slug identifier of the document
        section: Optional section ID to retrieve only that section
        
    Returns:
        The document content or section, formatted as Markdown
    """
    async with get_db() as db:
        service = KnowledgeService(db)
        
        knowledge = await service.get_by_slug(slug)
        
        if not knowledge:
            return f"Knowledge document with slug '{slug}' not found."
        
        # If section requested, extract just that section
        if section:
            for sec in knowledge.structure.get("sections", []):
                if sec.get("id") == section:
                    return (
                        f"# {sec['title']}\n\n"
                        f"{sec['content']}\n\n"
                        f"---\n"
                        f"*From: {knowledge.title} ({knowledge.slug})*"
                    )
            
            return f"Section '{section}' not found in document '{slug}'."
        
        # Return full document with metadata
        toc = get_table_of_contents(knowledge.structure)
        toc_text = "\n".join(toc) if toc else "No sections found"
        
        return (
            f"# {knowledge.title}\n\n"
            f"**Slug:** {knowledge.slug}\n"
            f"**Last updated:** {knowledge.updated_at.isoformat()}\n\n"
            f"## Table of Contents\n\n{toc_text}\n\n"
            f"---\n\n"
            f"{knowledge.content}"
        )