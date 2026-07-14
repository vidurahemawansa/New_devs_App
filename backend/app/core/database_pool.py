import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
import logging
from ..config import settings

logger = logging.getLogger(__name__)

class DatabasePool:
    def __init__(self):
        self.engine = None
        self.session_factory = None
        
    async def initialize(self):
        """Initialize database connection pool"""
        try:
            if self.session_factory is not None:
                # Already initialized (e.g. by a previous caller) - reuse it.
                return

            # Build the async engine URL from the same DATABASE_URL used by the
            # rest of the app (see docker-compose.yml / config.py), just swapping
            # in the asyncpg driver. Previously this referenced settings attributes
            # (supabase_db_user/host/port/name) that don't exist on Settings, which
            # made initialization always raise and silently fall back to mock data.
            database_url = settings.database_url
            if database_url.startswith("postgresql+asyncpg://"):
                pass
            elif database_url.startswith("postgresql://"):
                database_url = "postgresql+asyncpg://" + database_url[len("postgresql://"):]
            elif database_url.startswith("postgres://"):
                database_url = "postgresql+asyncpg://" + database_url[len("postgres://"):]

            self.engine = create_async_engine(
                database_url,
                pool_size=20,  # Number of connections to maintain
                max_overflow=30,  # Additional connections when needed
                pool_pre_ping=True,  # Validate connections
                pool_recycle=3600,  # Recycle connections every hour
                echo=False  # Set to True for SQL debugging
            )
            
            self.session_factory = async_sessionmaker(
                bind=self.engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            logger.info("✅ Database connection pool initialized")
            
        except Exception as e:
            logger.error(f"❌ Database pool initialization failed: {e}")
            self.engine = None
            self.session_factory = None
    
    async def close(self):
        """Close database connections"""
        if self.engine:
            await self.engine.dispose()
    
    def get_session(self) -> AsyncSession:
        """Get a new database session from the pool.

        Returns the AsyncSession itself (not a coroutine) so callers can use it
        directly as an async context manager, e.g. `async with db_pool.get_session() as session:`.
        Previously this was an `async def`, which meant `async with db_pool.get_session()`
        tried to enter a coroutine object as a context manager and always raised
        `AttributeError: __aenter__`, silently breaking every real DB query.
        """
        if not self.session_factory:
            raise Exception("Database pool not initialized")
        return self.session_factory()

# Global database pool instance
db_pool = DatabasePool()

async def get_db_session() -> AsyncSession:
    """Dependency to get database session"""
    async with db_pool.get_session() as session:
        yield session
