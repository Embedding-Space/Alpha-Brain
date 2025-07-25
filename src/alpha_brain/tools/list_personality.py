"""List personality directives."""

from alpha_brain.personality_service import get_personality_service
from alpha_brain.templates import render_output


async def list_personality(category: str | None = None) -> str:
    """
    List all personality directives, optionally filtered by category.
    
    Personality directives are behavioral instructions with weights that
    shape how Alpha responds and behaves. They represent the mutable,
    evolvable aspects of Alpha's personality.
    
    Args:
        category: Optional category filter (e.g., "warmth", "curiosity")
        
    Returns:
        Formatted list of personality directives grouped by category
    """
    service = get_personality_service()
    
    # Get directives
    directives = await service.get_directives(category=category)
    
    if not directives:
        if category:
            return f"No personality directives found in category '{category}'"
        return "No personality directives configured yet"
    
    # Group by category for display
    by_category = {}
    uncategorized = []
    
    for directive in directives:
        # Convert to display format
        item = {
            "id": str(directive.id),
            "text": directive.directive,
            "weight": float(directive.weight),
            "created_at": directive.created_at,
            "updated_at": directive.updated_at
        }
        
        if directive.category:
            if directive.category not in by_category:
                by_category[directive.category] = []
            by_category[directive.category].append(item)
        else:
            uncategorized.append(item)
    
    # Build categories list for template
    categories = []
    for cat_name, items in sorted(by_category.items()):
        categories.append({
            "name": cat_name,
            "directives": items
        })
    
    # Add uncategorized if any
    if uncategorized:
        categories.append({
            "name": "uncategorized",
            "directives": uncategorized
        })
    
    return render_output("list_personality", categories=categories)