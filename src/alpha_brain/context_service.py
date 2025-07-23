"""Service for managing context blocks."""

from datetime import UTC, datetime

from sqlalchemy import select, text
from structlog import get_logger

from alpha_brain.database import get_db
from alpha_brain.schema import Context

logger = get_logger()

# System sections that cannot have TTL and should always exist
SYSTEM_SECTIONS = {"biography", "continuity"}


class ContextService:
    """Service for managing context blocks."""
    
    async def set_context(
        self, 
        section: str, 
        content: str, 
        ttl: str | None = None
    ) -> dict:
        """
        Set or update a context block.
        
        Args:
            section: The section name (e.g., "biography", "current_project")
            content: The markdown content (empty string clears the section)
            ttl: Optional TTL string (e.g., "3d", "1h") - not allowed for system sections
            
        Returns:
            Dict with operation result
            
        Raises:
            ValueError: If trying to set TTL on system section
        """
        # Validate system sections
        if section in SYSTEM_SECTIONS and ttl:
            raise ValueError(f"System section '{section}' cannot have TTL")
        
        # Parse TTL if provided
        expires_at = None
        interval = None
        if ttl:
            # Parse duration string like "3d", "1h", "30m"
            try:
                # Use centralized duration parsing from TimeService
                from alpha_brain.time_service import TimeService
                interval = TimeService.parse_duration(ttl)
                expires_at = datetime.now(UTC) + interval
            except Exception as e:
                raise ValueError(f"Invalid TTL format: {ttl}. Use formats like '3d', '1h', '30m'") from e
        
        async with get_db() as db:
            # Check if section exists
            existing = await db.execute(
                select(Context).where(Context.section == section)
            )
            existing_row = existing.scalar_one_or_none()
            
            if existing_row:
                # Update existing
                existing_row.content = content
                existing_row.ttl = interval
                existing_row.expires_at = expires_at
                existing_row.updated_at = datetime.now(UTC)
                
                await db.commit()
                
                logger.info(
                    "Updated context section",
                    section=section,
                    has_ttl=bool(ttl),
                    expires_at=expires_at
                )
                
                return {
                    "operation": "updated",
                    "section": section,
                    "expires_at": expires_at.isoformat() if expires_at else None
                }
            # Create new
            new_context = Context(
                section=section,
                content=content,
                ttl=interval,
                expires_at=expires_at,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC)
            )

            db.add(new_context)
            await db.commit()

            logger.info(
                "Created context section",
                section=section,
                has_ttl=bool(ttl),
                expires_at=expires_at
            )

            return {
                "operation": "created",
                "section": section,
                "expires_at": expires_at.isoformat() if expires_at else None
            }
    
    async def get_active_contexts(self) -> list[Context]:
        """
        Get all active context blocks (not expired).
        
        Returns:
            List of active Context objects
        """
        async with get_db() as db:
            # Use the view for clean active-only query
            result = await db.execute(
                text("SELECT * FROM active_context ORDER BY section")
            )
            
            # Convert rows to Context objects
            contexts = []
            for row in result:
                context = Context(
                    section=row.section,
                    content=row.content,
                    ttl=row.ttl,
                    expires_at=row.expires_at,
                    created_at=row.created_at,
                    updated_at=row.updated_at
                )
                contexts.append(context)
            
            return contexts
    
    async def get_context(self, section: str) -> Context | None:
        """
        Get a specific context block if active.
        
        Args:
            section: The section name
            
        Returns:
            Context object if found and active, None otherwise
        """
        async with get_db() as db:
            result = await db.execute(
                select(Context)
                .where(Context.section == section)
                .where(Context.is_active)
            )
            
            return result.scalar_one_or_none()


# Module-level singleton
_context_service: ContextService | None = None


def get_context_service() -> ContextService:
    """Get or create the context service singleton."""
    global _context_service
    if _context_service is None:
        _context_service = ContextService()
    return _context_service
