#!/usr/bin/env python3
"""
Database initialization script for Forth AI Underwriting System.
Creates tables, runs migrations, and sets up initial data.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sqlalchemy import text
from loguru import logger

from forth_ai_underwriting.core.database import db_manager
from forth_ai_underwriting.core.models import Base
from forth_ai_underwriting.config.settings import settings


async def create_database():
    """Create database if it doesn't exist (for PostgreSQL)."""
    if settings.database_url.startswith("postgresql"):
        try:
            # Extract database name from URL
            db_name = settings.database_url.split("/")[-1].split("?")[0]
            
            # Connect to postgres database to create the target database
            postgres_url = settings.database_url.replace(f"/{db_name}", "/postgres")
            
            from sqlalchemy import create_engine
            engine = create_engine(postgres_url)
            
            with engine.connect() as conn:
                # Set autocommit mode
                conn.execute(text("COMMIT"))
                
                # Check if database exists
                result = conn.execute(
                    text("SELECT 1 FROM pg_database WHERE datname = :db_name"),
                    {"db_name": db_name}
                )
                
                if not result.fetchone():
                    logger.info(f"Creating database: {db_name}")
                    conn.execute(text(f"CREATE DATABASE {db_name}"))
                    logger.info(f"Database {db_name} created successfully")
                else:
                    logger.info(f"Database {db_name} already exists")
            
            engine.dispose()
            
        except Exception as e:
            logger.error(f"Failed to create database: {e}")
            return False
    
    return True


def create_tables():
    """Create all database tables."""
    try:
        logger.info("Creating database tables...")
        db_manager.create_tables()
        logger.info("Database tables created successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to create tables: {e}")
        return False


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
                    labels={"version": settings.app_version}
                ),
                SystemMetrics(
                    metric_name="database_tables_created",
                    metric_value=1.0,
                    metric_type="counter",
                    labels={"environment": settings.environment}
                )
            ]
            
            for metric in metrics:
                session.add(metric)
            
            session.commit()
            logger.info("Initial data inserted successfully")
            
        return True
        
    except Exception as e:
        logger.error(f"Failed to insert initial data: {e}")
        return False


def verify_database():
    """Verify database setup by running basic queries."""
    try:
        logger.info("Verifying database setup...")
        
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
                logger.info(f"Table {table.__tablename__}: {count} records")
            
            logger.info("Database verification completed successfully")
            return True
            
    except Exception as e:
        logger.error(f"Database verification failed: {e}")
        return False


def main():
    """Main initialization function."""
    logger.info("Starting database initialization...")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Database URL: {settings.database_url}")
    
    # Create database (if PostgreSQL)
    if not asyncio.run(create_database()):
        logger.error("Database creation failed")
        return False
    
    # Create tables
    if not create_tables():
        logger.error("Table creation failed")
        return False
    
    # Insert initial data
    if not insert_initial_data():
        logger.error("Initial data insertion failed")
        return False
    
    # Verify setup
    if not verify_database():
        logger.error("Database verification failed")
        return False
    
    logger.info("Database initialization completed successfully!")
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 