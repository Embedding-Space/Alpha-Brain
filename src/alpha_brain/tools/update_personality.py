"""Update personality directive by ID."""

from uuid import UUID

from alpha_brain.database import get_db
from alpha_brain.schema import PersonalityDirective


async def update_personality(
    id: str,
    directive: str | None = None,
    weight: float | None = None,
    category: str | None = None
) -> str:
    """
    Update an existing personality directive by its ID.
    
    This allows iterative refinement of directive wording without having
    to delete and recreate. Find the ID using list_personality.
    
    Args:
        id: The UUID of the directive to update
        directive: New wording for the directive (optional)
        weight: New weight from -1.0 to 1.0 (optional)
        category: New category (optional)
        
    Returns:
        Confirmation of the update
        
    Example:
        update_personality("uuid-here", directive="Make puns at most once per day")
    """
    # Validate UUID
    try:
        directive_id = UUID(id)
    except ValueError:
        return f"Invalid UUID format: {id}"
    
    # Validate weight if provided
    if weight is not None and (weight < -1.0 or weight > 1.0):
        return "Weight must be between -1.0 and 1.0"
    
    # Get the directive by ID
    async with get_db() as db:
        existing = await db.get(PersonalityDirective, directive_id)
        
        if not existing:
            return f"Directive not found with ID: {id}"
        
        # Store old values for comparison
        old_text = existing.directive
        old_weight = float(existing.weight)
        old_category = existing.category
        
        # Update fields if provided
        if directive is not None:
            existing.directive = directive
        if weight is not None:
            existing.weight = float(weight)
        if category is not None:
            existing.category = category if category else None
            
        await db.commit()
        await db.refresh(existing)
        
        # Build response showing what changed
        changes = []
        if directive and directive != old_text:
            changes.append(f"text: \"{old_text}\" → \"{directive}\"")
        if weight is not None and weight != old_weight:
            changes.append(f"weight: {old_weight:.2f} → {weight:.2f}")
        # Compare actual final category values, not the parameter
        if existing.category != old_category:
            if old_category and existing.category:
                changes.append(f"category: {old_category} → {existing.category}")
            elif old_category:
                changes.append(f"category: {old_category} → uncategorized")
            else:
                changes.append(f"category: uncategorized → {existing.category}")
                
        if changes:
            return f"Updated directive {id}: {', '.join(changes)}"
        else:
            return f"No changes made to directive {id}"