#!/usr/bin/env python3
"""
Database initialization script for Forth AI Underwriting System.
Creates PostgreSQL database, tables, and initial data.
PostgreSQL only - SQLite removed for production readiness.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sqlalchemy import text, create_engine
from loguru import logger

from forth_ai_underwriting.core.database import db_manager
from forth_ai_underwriting.core.models import Base
from forth_ai_underwriting.config.settings import settings


async def create_database():
    """Create PostgreSQL database if it doesn't exist."""
    try:
        logger.info(f"Checking PostgreSQL database: {settings.database.name}")
        
        # Connect to postgres database to create the target database
        postgres_url = settings.database.url.replace(f"/{settings.database.name}", "/postgres")
        
        engine = create_engine(postgres_url)
        
        with engine.connect() as conn:
            # Set autocommit mode for database creation
            conn.execute(text("COMMIT"))
            
            # Check if database exists
            result = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :db_name"),
                {"db_name": settings.database.name}
            )
            
            if not result.fetchone():
                logger.info(f"Creating PostgreSQL database: {settings.database.name}")
                conn.execute(text(f'CREATE DATABASE "{settings.database.name}"'))
                logger.info(f"✅ Database {settings.database.name} created successfully")
            else:
                logger.info(f"✅ Database {settings.database.name} already exists")
        
        engine.dispose()
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to create PostgreSQL database: {e}")
        logger.error(f"Database URL: {settings.database.url}")
        logger.error("Please ensure PostgreSQL is running and credentials are correct")
        return False


def create_tables():
    """Create all database tables."""
    try:
        logger.info("Creating database tables...")
        db_manager.create_tables()
        logger.info("✅ Database tables created successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to create tables: {e}")
        return False


def create_extensions():
    """Create PostgreSQL extensions if needed."""
    try:
        logger.info("Creating PostgreSQL extensions...")
        
        with db_manager.get_session() as session:
            # Enable UUID extension for generating UUIDs
            try:
                session.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
                logger.info("✅ UUID extension enabled")
            except Exception as e:
                logger.warning(f"UUID extension not created (might already exist): {e}")
            
            # Enable pg_stat_statements for query performance monitoring
            try:
                session.execute(text('CREATE EXTENSION IF NOT EXISTS "pg_stat_statements"'))
                logger.info("✅ pg_stat_statements extension enabled")
            except Exception as e:
                logger.warning(f"pg_stat_statements extension not created: {e}")
            
            session.commit()
        
        return True
        
    except Exception as e:
        logger.warning(f"Extension creation had issues (not critical): {e}")
        return True  # Extensions are nice-to-have, not critical


def insert_initial_data():
    """Insert initial reference data."""
    try:
        logger.info("Inserting initial data...")
        
        with db_manager.get_session() as session:
            # Check if we already have data
            from forth_ai_underwriting.core.models import SystemMetrics
            existing_data = session.query(SystemMetrics).first()
            
            if existing_data:
                logger.info("Initial data already exists, skipping...")
                return True
            
            # Insert initial system metrics
            metrics = [
                SystemMetrics(
                    metric_name="system_initialized",
                    metric_value=1.0,
                    metric_type="gauge",
                    labels={"version": settings.app_version, "database": "postgresql"}
                ),
                SystemMetrics(
                    metric_name="database_tables_created",
                    metric_value=1.0,
                    metric_type="counter",
                    labels={
                        "environment": settings.environment,
                        "database_host": settings.database.host,
                        "database_name": settings.database.name
                    }
                ),
                SystemMetrics(
                    metric_name="aws_secrets_enabled",
                    metric_value=1.0 if settings.aws.use_secrets_manager else 0.0,
                    metric_type="gauge",
                    labels={"region": settings.aws.region}
                )
            ]
            
            for metric in metrics:
                session.add(metric)
            
            session.commit()
            logger.info("✅ Initial data inserted successfully")
            
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to insert initial data: {e}")
        return False


def verify_database():
    """Verify database setup by running basic queries."""
    try:
        logger.info("Verifying database setup...")
        
        # Test database manager health check
        health_status = db_manager.health_check()
        logger.info(f"Database health check: {health_status['status']}")
        
        if health_status['status'] != 'healthy':
            logger.error(f"Database health check failed: {health_status}")
            return False
        
        with db_manager.get_session() as session:
            # Test basic table access
            from forth_ai_underwriting.core.models import (
                Contact, ValidationRun, ValidationResult, 
                Document, UserFeedback, AuditLog, 
                ValidationCache, SystemMetrics
            )
            
            tables_to_test = [
                Contact, ValidationRun, ValidationResult,
                Document, UserFeedback, AuditLog,
                ValidationCache, SystemMetrics
            ]
            
            for table in tables_to_test:
                count = session.query(table).count()
                logger.info(f"✅ Table {table.__tablename__}: {count} records")
            
            # Test a simple query
            result = session.execute(text("SELECT version()"))
            postgres_version = result.fetchone()[0]
            logger.info(f"✅ PostgreSQL version: {postgres_version}")
            
            logger.info("✅ Database verification completed successfully")
            return True
            
    except Exception as e:
        logger.error(f"❌ Database verification failed: {e}")
        return False


def display_configuration():
    """Display current database configuration."""
    logger.info("=== DATABASE CONFIGURATION ===")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Database Type: PostgreSQL")
    logger.info(f"Host: {settings.database.host}")
    logger.info(f"Port: {settings.database.port}")
    logger.info(f"Database: {settings.database.name}")
    logger.info(f"User: {settings.database.user}")
    logger.info(f"SSL Mode: {settings.database.sslmode}")
    logger.info(f"Pool Size: {settings.database.pool_size}")
    logger.info(f"Max Overflow: {settings.database.max_overflow}")
    logger.info(f"AWS Secrets: {'Enabled' if settings.aws.use_secrets_manager else 'Disabled'}")
    logger.info("================================")


def main():
    """Main initialization function."""
    logger.info("🚀 Starting PostgreSQL database initialization...")
    
    # Verify we're using PostgreSQL
    if not settings.database.url.startswith("postgresql"):
        logger.error(f"❌ Only PostgreSQL is supported. Current URL: {settings.database.url}")
        logger.error("Please configure PostgreSQL database connection")
        return False
    
    # Display configuration
    display_configuration()
    
    # Create database
    if not asyncio.run(create_database()):
        logger.error("❌ Database creation failed")
        return False
    
    # Create extensions
    if not create_extensions():
        logger.warning("⚠️  Extension creation had issues (proceeding anyway)")
    
    # Create tables
    if not create_tables():
        logger.error("❌ Table creation failed")
        return False
    
    # Insert initial data
    if not insert_initial_data():
        logger.error("❌ Initial data insertion failed")
        return False
    
    # Verify setup
    if not verify_database():
        logger.error("❌ Database verification failed")
        return False
    
    logger.info("🎉 Database initialization completed successfully!")
    logger.info("📊 Database is ready for the Forth AI Underwriting System")
    return True


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("Database initialization cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error during database initialization: {e}")
        sys.exit(1) 