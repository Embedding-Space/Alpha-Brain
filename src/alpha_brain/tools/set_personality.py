"""Set personality directives for Alpha."""

from typing import Union
from alpha_brain.personality_service import get_personality_service


async def set_personality(
    directive: str,
    weight: Union[float, str, None] = None,
    category: str | None = None,
    delete: bool = False
) -> str:
    """
    Manage personality directives that shape how Alpha behaves.
    
    Personality directives are the HOW of Alpha's identity - specific,
    actionable instructions that guide behavior and responses.
    
    Args:
        directive: The behavioral instruction (e.g., "Express enthusiasm about breakthroughs")
        weight: Importance from -1.0 to 1.0 (negative = avoid, positive = embrace). Can be string or float.
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
    
    # Convert weight to float if it's a string
    if weight is not None:
        try:
            weight = float(weight)
        except (ValueError, TypeError):
            return f"Invalid weight value: {weight}. Must be a number between -1.0 and 1.0"
    
    # Validate weight if provided
    if weight is not None and (weight < -1.0 or weight > 1.0):
        return "Weight must be between -1.0 and 1.0"
    
    result = await service.set_directive(
        directive=directive,
        weight=weight,
        category=category,
        delete=delete
    )
    
    if result["status"] == "deleted":
        return f"Deleted directive: \"{directive}\""
    if result["status"] == "not_found":
        return f"Directive not found: \"{directive}\""
    if result["status"] == "created":
        weight_str = f" (weight: {result['weight']:.2f})"
        category_str = f" in category '{result['category']}'" if result['category'] else ""
        return f"Created directive: \"{directive}\"{weight_str}{category_str}"
    # updated
    weight_str = f" (weight: {result['weight']})" if result['weight'] != 1.0 else ""
    category_str = f" in category '{result['category']}'" if result['category'] else ""
    return f"Updated directive: \"{directive}\"{weight_str}{category_str}"
