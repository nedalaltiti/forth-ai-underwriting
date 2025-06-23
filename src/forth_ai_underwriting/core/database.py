"""
Database configuration and connection management.
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from contextlib import contextmanager
from typing import Generator
import logging

from forth_ai_underwriting.config.settings import settings
from forth_ai_underwriting.core.models import Base

# Configure SQLAlchemy logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

class DatabaseManager:
    """Manages database connections and sessions."""
    
    def __init__(self):
        self.engine = None
        self.SessionLocal = None
        self._initialize_engine()
    
    def _initialize_engine(self):
        """Initialize the database engine with appropriate configuration."""
        
        # Configure engine based on database type
        if settings.database_url.startswith("sqlite"):
            self.engine = create_engine(
                settings.database_url,
                poolclass=StaticPool,
                connect_args={
                    "check_same_thread": False,
                    "timeout": 20,
                },
                echo=settings.debug,
                future=True
            )
        elif settings.database_url.startswith("postgresql"):
            self.engine = create_engine(
                settings.database_url,
                pool_size=20,
                max_overflow=30,
                pool_pre_ping=True,
                pool_recycle=300,
                echo=settings.debug,
                future=True
            )
        else:
            # Default configuration
            self.engine = create_engine(
                settings.database_url,
                echo=settings.debug,
                future=True
            )
        
        # Add connection event listeners
        self._add_event_listeners()
        
        # Create session factory
        self.SessionLocal = sessionmaker(
            bind=self.engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False
        )
    
    def _add_event_listeners(self):
        """Add database event listeners for monitoring and optimization."""
        
        @event.listens_for(self.engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            """Set SQLite pragmas for better performance."""
            if settings.database_url.startswith("sqlite"):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA cache_size=10000")
                cursor.execute("PRAGMA temp_store=MEMORY")
                cursor.close()
    
    def create_tables(self):
        """Create all database tables."""
        Base.metadata.create_all(bind=self.engine)
    
    def drop_tables(self):
        """Drop all database tables."""
        Base.metadata.drop_all(bind=self.engine)
    
    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """Get a database session with automatic cleanup."""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def get_session_direct(self) -> Session:
        """Get a database session for dependency injection."""
        return self.SessionLocal()


# Global database manager instance
db_manager = DatabaseManager()

# Dependency function for FastAPI
def get_db() -> Generator[Session, None, None]:
    """Dependency function to get database session in FastAPI endpoints."""
    with db_manager.get_session() as session:
        yield session 