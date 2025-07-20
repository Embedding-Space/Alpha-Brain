"""Tool for creating knowledge documents."""

from alpha_brain.database import get_db
from alpha_brain.knowledge_service import KnowledgeService
from alpha_brain.schema import KnowledgeInput


async def create_knowledge(slug: str, title: str, content: str) -> str:
    """Create a new knowledge document from Markdown content.
    
    Args:
        slug: URL-friendly identifier for the document
        title: Document title
        content: Markdown-formatted content
        
    Returns:
        Confirmation message with document details
    """
    async with get_db() as db:
        service = KnowledgeService(db)
        
        try:
            knowledge_input = KnowledgeInput(
                slug=slug,
                title=title,
                content=content
            )
            
            result = await service.create(knowledge_input)
            
            # Get section count from structure
            section_count = len(result.structure.get("sections", []))
            
            return (
                f'Created knowledge document "{result.title}" with slug "{result.slug}".\n\n'
                f"Document ID: {result.id}\n"
                f"Sections: {section_count}\n"
                f"Created at: {result.created_at.isoformat()}"
            )
            
        except ValueError as e:
            return f"Error: {str(e)}"
        except Exception as e:
            return f"Failed to create knowledge document: {str(e)}"