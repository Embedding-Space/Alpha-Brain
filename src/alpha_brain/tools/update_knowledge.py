"""Tool for updating knowledge documents."""

from alpha_brain.database import get_db
from alpha_brain.knowledge_service import KnowledgeService
from alpha_brain.schema import KnowledgeInput


async def update_knowledge(slug: str, title: str | None = None, content: str | None = None, new_slug: str | None = None) -> str:
    """Update an existing knowledge document.
    
    Args:
        slug: Current slug of the document to update
        title: New title (optional, keeps existing if not provided)
        content: New Markdown content (optional, keeps existing if not provided)
        new_slug: New slug if renaming (optional)
        
    Returns:
        Confirmation message with update details
    """
    async with get_db() as db:
        service = KnowledgeService(db)
        
        # Get existing document first
        existing = await service.get_by_slug(slug)
        if not existing:
            return f"Knowledge document with slug '{slug}' not found."
        
        try:
            # Use existing values for any not provided
            knowledge_input = KnowledgeInput(
                slug=new_slug or existing.slug,
                title=title or existing.title,
                content=content or existing.content
            )
            
            result = await service.update(slug, knowledge_input)
            
            if not result:
                return f"Failed to update knowledge document '{slug}'."
            
            # Build update summary
            updates = []
            if title and title != existing.title:
                updates.append(f"Title: '{existing.title}' → '{title}'")
            if new_slug and new_slug != existing.slug:
                updates.append(f"Slug: '{existing.slug}' → '{new_slug}'")
            if content and content != existing.content:
                old_sections = len(existing.structure.get("sections", []))
                new_sections = len(result.structure.get("sections", []))
                updates.append(f"Content: Updated ({old_sections} → {new_sections} sections)")
            
            update_summary = "\n".join(updates) if updates else "No changes detected"
            
            return (
                f'Updated knowledge document "{result.title}".\n\n'
                f"Changes:\n{update_summary}\n\n"
                f"Updated at: {result.updated_at.isoformat()}"
            )
            
        except ValueError as e:
            return f"Error: {str(e)}"
        except Exception as e:
            return f"Failed to update knowledge document: {str(e)}"