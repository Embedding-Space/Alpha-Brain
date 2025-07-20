"""SQLAlchemy models for Alpha Brain."""

from datetime import UTC, datetime

from sqlalchemy import (
    Column,
    DateTime,
    Interval,
    Text,
    func,
    or_,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.hybrid import hybrid_property

Base = declarative_base()


class Context(Base):
    """Context blocks for identity and state management."""
    
    __tablename__ = "context"
    
    section = Column(Text, primary_key=True)
    content = Column(Text, nullable=False)
    ttl = Column(Interval)  # How long this should live
    expires_at = Column(DateTime(timezone=True))  # When it expires
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    @hybrid_property
    def is_active(self):
        """Check if this context block is currently active."""
        if self.expires_at is None:
            return True
        return self.expires_at > datetime.now(UTC)
    
    @is_active.expression
    def is_active(cls):  # noqa: N805
        """SQL expression for filtering active contexts."""
        return or_(cls.expires_at.is_(None), cls.expires_at > func.now())
