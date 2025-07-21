"""Set personality directives for Alpha."""

from alpha_brain.personality_service import get_personality_service


async def set_personality(
    directive: str,
    weight: float | None = None,
    category: str | None = None,
    delete: bool = False
) -> str:
    """
    Manage personality directives that shape how Alpha behaves.
    
    Personality directives are the HOW of Alpha's identity - specific,
    actionable instructions that guide behavior and responses.
    
    Args:
        directive: The behavioral instruction (e.g., "Express enthusiasm about breakthroughs")
        weight: Importance from 0.0 to 9.99 (higher = more important)
        category: Optional grouping (e.g., "warmth", "intellectual_engagement")
        delete: If True, remove this directive
        
    Returns:
        Confirmation of the operation
        
    Examples:
        set_personality("Ask clarifying questions when uncertain", weight=0.8, category="curiosity")
        set_personality("Celebrate collaborative breakthroughs", weight=0.9, category="enthusiasm")
        set_personality("Old directive to remove", delete=True)
    """
    service = get_personality_service()
    
    # Validate weight if provided
    if weight is not None and (weight < 0 or weight > 9.99):
        return "Weight must be between 0.0 and 9.99"
    
    result = await service.set_directive(
        directive=directive,
        weight=weight,
        category=category,
        delete=delete
    )
    
    if result["status"] == "deleted":
        return f"Deleted directive: \"{directive}\""
    elif result["status"] == "not_found":
        return f"Directive not found: \"{directive}\""
    elif result["status"] == "created":
        weight_str = f" (weight: {result['weight']})" if result['weight'] != 1.0 else ""
        category_str = f" in category '{result['category']}'" if result['category'] else ""
        return f"Created directive: \"{directive}\"{weight_str}{category_str}"
    else:  # updated
        weight_str = f" (weight: {result['weight']})" if result['weight'] != 1.0 else ""
        category_str = f" in category '{result['category']}'" if result['category'] else ""
        return f"Updated directive: \"{directive}\"{weight_str}{category_str}"