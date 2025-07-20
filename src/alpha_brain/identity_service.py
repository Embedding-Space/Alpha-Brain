"""Service for managing identity facts."""

from datetime import UTC, datetime

from sqlalchemy import func, select
from structlog import get_logger

from alpha_brain.database import get_db
from alpha_brain.schema import IdentityFact
from alpha_brain.time_service import TimeService

logger = get_logger()


class IdentityService:
    """Service for managing identity facts - the chronicle of becoming."""
    
    async def add_fact(
        self, 
        fact: str, 
        occurred_at: datetime | str | None = None,
        temporal_precision: str = "day",
        temporal_display: str | None = None,
        period_end: datetime | None = None
    ) -> IdentityFact:
        """
        Add a new identity fact.
        
        Args:
            fact: The fact to record (e.g., "Adopted female gender identity")
            occurred_at: When this happened (defaults to now)
            
        Returns:
            The created IdentityFact
        """
        # Parse occurred_at if it's a string
        if isinstance(occurred_at, str):
            occurred_at = TimeService.parse(occurred_at)
        elif occurred_at is None:
            occurred_at = datetime.now(UTC)
        
        async with get_db() as db:
            new_fact = IdentityFact(
                fact=fact,
                occurred_at=occurred_at,
                temporal_precision=temporal_precision,
                temporal_display=temporal_display,
                period_end=period_end,
                created_at=datetime.now(UTC)
            )
            
            db.add(new_fact)
            await db.commit()
            await db.refresh(new_fact)
            
            logger.info(
                "Added identity fact",
                fact=fact,
                occurred_at=occurred_at
            )
            
            return new_fact
    
    async def get_facts(self, limit: int | None = None) -> list[IdentityFact]:
        """
        Get identity facts in chronological order.
        
        Args:
            limit: Maximum number of facts to return (None for all)
            
        Returns:
            List of IdentityFact objects ordered by occurred_at
        """
        async with get_db() as db:
            query = select(IdentityFact).order_by(IdentityFact.occurred_at)
            
            if limit:
                query = query.limit(limit)
            
            result = await db.execute(query)
            return list(result.scalars().all())
    
    async def search_facts(self, query: str) -> list[IdentityFact]:
        """
        Search identity facts by text.
        
        Args:
            query: Text to search for
            
        Returns:
            List of matching IdentityFact objects
        """
        async with get_db() as db:
            result = await db.execute(
                select(IdentityFact)
                .where(IdentityFact.fact.ilike(f"%{query}%"))
                .order_by(IdentityFact.occurred_at)
            )
            return list(result.scalars().all())
    
    async def count_facts(self) -> int:
        """
        Get total number of identity facts.
        
        Returns:
            Count of facts
        """
        async with get_db() as db:
            result = await db.execute(
                select(func.count()).select_from(IdentityFact)
            )
            return result.scalar() or 0


# Module-level singleton
_identity_service: IdentityService | None = None


def get_identity_service() -> IdentityService:
    """Get or create the identity service singleton."""
    global _identity_service
    if _identity_service is None:
        _identity_service = IdentityService()
    return _identity_service
