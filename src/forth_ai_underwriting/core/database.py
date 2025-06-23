"""
Database configuration and connection management.
PostgreSQL only - SQLite removed for production readiness.
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from typing import Generator
import logging

from forth_ai_underwriting.config.settings import database, settings
from forth_ai_underwriting.core.models import Base

# Configure SQLAlchemy logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

class DatabaseManager:
    """Manages PostgreSQL database connections and sessions."""
    
    def __init__(self):
        self.engine = None
        self.SessionLocal = None
        self._initialize_engine()
    
    def _initialize_engine(self):
        """Initialize the PostgreSQL database engine."""
        
        # Verify we're using PostgreSQL
        if not database.url.startswith("postgresql"):
            raise ValueError(f"Only PostgreSQL is supported. Current URL: {database.url}")
        
        logger = logging.getLogger(__name__)
        logger.info(f"Initializing PostgreSQL connection to {database.host}:{database.port}")
        
        # Create PostgreSQL engine with optimal configuration
        self.engine = create_engine(
            database.url,
            **database.engine_kwargs,
            echo=settings.debug,
            future=True
        )
        
        # Add connection event listeners for PostgreSQL optimization
        self._add_event_listeners()
        
        # Create session factory
        self.SessionLocal = sessionmaker(
            bind=self.engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False
        )
        
        logger.info("✅ PostgreSQL database engine initialized successfully")
    
    def _add_event_listeners(self):
        """Add PostgreSQL-specific event listeners for monitoring and optimization."""
        
        @event.listens_for(self.engine, "connect")
        def set_postgresql_settings(dbapi_connection, connection_record):
            """Set PostgreSQL session settings for optimal performance."""
            with dbapi_connection.cursor() as cursor:
                # Set timezone
                cursor.execute("SET timezone TO 'UTC'")
                
                # Optimize for application workload
                cursor.execute("SET statement_timeout = '300s'")  # 5 minute timeout
                cursor.execute("SET lock_timeout = '30s'")        # 30 second lock timeout
                cursor.execute("SET idle_in_transaction_session_timeout = '60s'")  # 1 minute idle timeout
                
                # Connection logging for monitoring
                connection_record.info['connected_at'] = dbapi_connection.get_backend_pid()
        
        @event.listens_for(self.engine, "checkout")
        def receive_checkout(dbapi_connection, connection_record, connection_proxy):
            """Log when a connection is checked out from the pool."""
            logger = logging.getLogger(__name__)
            if settings.debug:
                logger.debug(f"Database connection checked out: PID {connection_record.info.get('connected_at')}")
        
        @event.listens_for(self.engine, "checkin")  
        def receive_checkin(dbapi_connection, connection_record):
            """Log when a connection is returned to the pool."""
            logger = logging.getLogger(__name__)
            if settings.debug:
                logger.debug(f"Database connection checked in: PID {connection_record.info.get('connected_at')}")
    
    def create_tables(self):
        """Create all database tables."""
        logger = logging.getLogger(__name__)
        logger.info("Creating database tables...")
        Base.metadata.create_all(bind=self.engine)
        logger.info("✅ Database tables created successfully")
    
    def drop_tables(self):
        """Drop all database tables."""
        logger = logging.getLogger(__name__)
        logger.warning("Dropping all database tables...")
        Base.metadata.drop_all(bind=self.engine)
        logger.info("✅ Database tables dropped")
    
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
    
    def health_check(self) -> dict:
        """Perform a health check on the database connection."""
        try:
            with self.get_session() as session:
                # Simple query to test connection
                result = session.execute("SELECT 1 as health_check")
                row = result.fetchone()
                
                # Get connection pool stats
                pool = self.engine.pool
                pool_status = {
                    "size": pool.size(),
                    "checked_in": pool.checkedin(),
                    "checked_out": pool.checkedout(),
                    "invalidated": pool.invalidated(),
                    "overflow": pool.overflow(),
                }
                
                return {
                    "status": "healthy",
                    "database_type": "postgresql",
                    "connection_test": "passed" if row[0] == 1 else "failed",
                    "pool_status": pool_status,
                    "url_host": database.host,
                    "url_port": database.port,
                    "url_database": database.name,
                }
                
        except Exception as e:
            return {
                "status": "unhealthy",
                "database_type": "postgresql", 
                "error": str(e),
                "url_host": database.host,
                "url_port": database.port,
                "url_database": database.name,
            }


# Global database manager instance
db_manager = DatabaseManager()

# Dependency function for FastAPI
def get_db() -> Generator[Session, None, None]:
    """Dependency function to get database session in FastAPI endpoints."""
    with db_manager.get_session() as session:
        yield session 