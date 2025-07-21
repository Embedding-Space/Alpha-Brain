"""Service for managing personality directives."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from structlog import get_logger

from alpha_brain.database import get_db
from alpha_brain.schema import PersonalityDirective

logger = get_logger()


class PersonalityService:
    """Service for managing personality directives - the HOW of Alpha's behavior."""
    
    async def set_directive(
        self,
        directive: str,
        weight: float | None = None,
        category: str | None = None,
        delete: bool = False
    ) -> dict:
        """
        Set, update, or delete a personality directive.
        
        Args:
            directive: The behavioral instruction
            weight: Importance weight (0.0 to 9.99)
            category: Optional category for organization
            delete: If True, delete the directive
            
        Returns:
            Operation result
        """
        async with get_db() as db:
            # Check if directive exists
            result = await db.execute(
                select(PersonalityDirective).where(
                    PersonalityDirective.directive == directive
                )
            )
            existing = result.scalar_one_or_none()
            
            if delete:
                if existing:
                    await db.delete(existing)
                    await db.commit()
                    logger.info("Deleted personality directive", directive=directive)
                    return {"status": "deleted", "directive": directive}
                return {"status": "not_found", "directive": directive}
            
            if existing:
                # Update existing directive
                if weight is not None:
                    existing.weight = Decimal(str(weight))
                if category is not None:
                    existing.category = category if category else None
                    
                await db.commit()
                await db.refresh(existing)
                
                logger.info(
                    "Updated personality directive",
                    directive=directive,
                    weight=float(existing.weight),
                    category=existing.category
                )
                
                return {
                    "status": "updated",
                    "directive": directive,
                    "weight": float(existing.weight),
                    "category": existing.category
                }
            # Create new directive
            new_directive = PersonalityDirective(
                directive=directive,
                weight=Decimal(str(weight)) if weight is not None else Decimal("1.0"),
                category=category if category else None
            )

            db.add(new_directive)
            await db.commit()
            await db.refresh(new_directive)

            logger.info(
                "Created personality directive",
                directive=directive,
                weight=float(new_directive.weight),
                category=new_directive.category
            )

            return {
                "status": "created",
                "directive": directive,
                "weight": float(new_directive.weight),
                "category": new_directive.category
            }
    
    async def get_directives(self, category: str | None = None) -> list[PersonalityDirective]:
        """
        Get personality directives, optionally filtered by category.
        
        Args:
            category: Optional category filter
            
        Returns:
            List of PersonalityDirective objects
        """
        async with get_db() as db:
            query = select(PersonalityDirective)
            
            if category:
                query = query.where(PersonalityDirective.category == category)
                
            # Order by category (nulls last) then by weight (highest first)
            query = query.order_by(
                PersonalityDirective.category.nullslast(),
                PersonalityDirective.weight.desc()
            )
            
            result = await db.execute(query)
            return list(result.scalars().all())
    
    async def get_categories(self) -> list[str]:
        """Get all unique categories."""
        async with get_db() as db:
            result = await db.execute(
                select(PersonalityDirective.category)
                .where(PersonalityDirective.category.isnot(None))
                .distinct()
                .order_by(PersonalityDirective.category)
            )
            return [cat for (cat,) in result.all()]


# Module-level singleton
_personality_service: PersonalityService | None = None


def get_personality_service() -> PersonalityService:
    """Get or create the personality service singleton."""
    global _personality_service
    if _personality_service is None:
        _personality_service = PersonalityService()
    return _personality_service
