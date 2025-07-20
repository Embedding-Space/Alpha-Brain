"""Tool for listing knowledge documents."""

from alpha_brain.database import get_db
from alpha_brain.knowledge_service import KnowledgeService
from alpha_brain.time_service import TimeService


async def list_knowledge(limit: int = 20) -> str:
    """List all knowledge documents.
    
    Args:
        limit: Maximum number of documents to return (default 20)
        
    Returns:
        Formatted list of knowledge documents
    """
    async with get_db() as db:
        service = KnowledgeService(db)
        
        documents = await service.list_all(limit=limit)
        
        if not documents:
            return "No knowledge documents found."
        
        # Format the list
        lines = [f"**Knowledge Documents** ({len(documents)} found):\n"]
        
        for doc in documents:
            section_count = len(doc.structure.get("sections", []))
            # Calculate rough size
            size_kb = len(doc.content) / 1024
            
            lines.append(
                f"• **{doc.title}** (`{doc.slug}`)\n"
                f"  Sections: {section_count} | "
                f"Size: {size_kb:.1f}KB | "
                f"Updated: {TimeService.format_age(doc.updated_at)}"
            )
        
        if len(documents) == limit:
            lines.append(f"\n*Showing first {limit} documents. Use a higher limit to see more.*")
        
        return "\n".join(lines)
