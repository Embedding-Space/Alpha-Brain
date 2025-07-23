"""Database connection and session management."""

from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from structlog import get_logger

from alpha_brain.settings import get_settings

logger = get_logger()

# Global engine and session factory
_engine: AsyncEngine | None = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Get or create the database engine."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.async_database_url,
            echo=False,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )
        logger.info("Database engine created", url=settings.async_database_url)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get or create the session factory."""
    global _async_session_factory
    if _async_session_factory is None:
        engine = get_engine()
        _async_session_factory = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
        logger.info("Session factory created")
    return _async_session_factory


@asynccontextmanager
async def get_db():
    """Get a database session."""
    session_factory = get_session_factory()

    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initialize database tables."""
    # Import models to register them
    from alpha_brain.schema import Base

    engine = get_engine()

    async with engine.begin() as conn:
        # Create pgvector extension
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

        # Create tables
        await conn.run_sync(Base.metadata.create_all)

        # Create GIN index for entity aliases (for fast array lookups)
        await conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_entity_aliases ON entities USING GIN (aliases)"
            )
        )
        
        # Create view for active context blocks
        await conn.execute(
            text("""
                CREATE OR REPLACE VIEW active_context AS
                SELECT * FROM context 
                WHERE expires_at IS NULL OR expires_at > NOW()
            """)
        )
        
        # Create index on expires_at for efficient filtering
        await conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_context_expires ON context(expires_at) WHERE expires_at IS NOT NULL"
            )
        )
        
        # Add full-text search infrastructure
        logger.info("Setting up full-text search...")
        
        # Add search_vector to memories table
        await conn.execute(text("""
            ALTER TABLE memories ADD COLUMN IF NOT EXISTS search_vector tsvector;
        """))
        
        # Create GIN index for fast full-text search on memories
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_memories_search_vector 
            ON memories USING GIN (search_vector);
        """))
        
        # Create trigger function to automatically update search_vector
        await conn.execute(text("""
            CREATE OR REPLACE FUNCTION update_memories_search_vector()
            RETURNS trigger AS $$
            BEGIN
                NEW.search_vector := to_tsvector('english', NEW.content);
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
        """))
        
        # Create trigger to update search_vector on insert/update
        await conn.execute(text("""
            DROP TRIGGER IF EXISTS memories_search_vector_trigger ON memories;
            CREATE TRIGGER memories_search_vector_trigger
            BEFORE INSERT OR UPDATE OF content ON memories
            FOR EACH ROW
            EXECUTE FUNCTION update_memories_search_vector();
        """))
        
        # Add search_vector to knowledge table
        await conn.execute(text("""
            ALTER TABLE knowledge ADD COLUMN IF NOT EXISTS search_vector tsvector;
        """))
        
        # Create GIN index for fast full-text search on knowledge
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_knowledge_search_vector 
            ON knowledge USING GIN (search_vector);
        """))
        
        # Create trigger function for knowledge
        await conn.execute(text("""
            CREATE OR REPLACE FUNCTION update_knowledge_search_vector()
            RETURNS trigger AS $$
            BEGIN
                NEW.search_vector := to_tsvector('english', 
                    COALESCE(NEW.title, '') || ' ' || COALESCE(NEW.content, '')
                );
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
        """))
        
        # Create trigger for knowledge
        await conn.execute(text("""
            DROP TRIGGER IF EXISTS knowledge_search_vector_trigger ON knowledge;
            CREATE TRIGGER knowledge_search_vector_trigger
            BEFORE INSERT OR UPDATE OF title, content ON knowledge
            FOR EACH ROW
            EXECUTE FUNCTION update_knowledge_search_vector();
        """))

    logger.info("Database initialized with full-text search support")


async def close_db():
    """Close database connections."""
    global _engine
    if _engine:
        await _engine.dispose()
        _engine = None
        logger.info("Database connections closed")
