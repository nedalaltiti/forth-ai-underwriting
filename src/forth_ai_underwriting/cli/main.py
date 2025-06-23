#!/usr/bin/env python3
"""
CLI interface for the Forth AI Underwriting System.
Clean implementation using service registry and modular commands.
"""

import asyncio
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
import uvicorn
from loguru import logger

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from forth_ai_underwriting.config.settings import settings
from forth_ai_underwriting.core.database import db_manager
from forth_ai_underwriting.services.validation import ValidationService
from forth_ai_underwriting.core.service_registry import (
    initialize_application,
    health_check_application,
    shutdown_application,
    get_service_registry
)

console = Console()


@click.group()
@click.version_option(version=settings.app_version)
def app():
    """Forth AI Underwriting System CLI."""
    pass


@app.group()
def server():
    """Server management commands."""
    pass


@server.command()
@click.option("--host", default="0.0.0.0", help="Host to bind to")
@click.option("--port", default=8000, help="Port to bind to")
@click.option("--reload", is_flag=True, help="Enable auto-reload for development")
@click.option("--workers", default=1, help="Number of worker processes")
def start(host: str, port: int, reload: bool, workers: int):
    """Start the FastAPI server."""
    logger.info("Starting Forth AI Underwriting server")
    
    # Initialize application services
    try:
        initialize_application()
        logger.info("All services initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        raise click.ClickException(f"Service initialization failed: {e}")
    
    # Start the server
    try:
        if reload or workers == 1:
            uvicorn.run(
                "forth_ai_underwriting.api.main:app",
                host=host,
                port=port,
                reload=reload,
                log_level=settings.log_level.lower()
            )
        else:
            uvicorn.run(
                "forth_ai_underwriting.api.main:app",
                host=host,
                port=port,
                workers=workers,
                log_level=settings.log_level.lower()
            )
    finally:
        # Ensure cleanup on shutdown
        shutdown_application()


@app.group()
def services():
    """Service management commands."""
    pass


@services.command()
def list():
    """List all registered services."""
    logger.info("Listing all registered services")
    
    try:
        registry = get_service_registry()
        from forth_ai_underwriting.core.service_registry import register_all_services
        register_all_services()
        
        service_list = registry.list_services()
        
        click.echo("\n🔧 Registered Services:")
        click.echo("=" * 50)
        
        for name, info in service_list.items():
            status = "✅ Initialized" if info["initialized"] else "⏳ Not Initialized"
            deps = ", ".join(info["dependencies"]) if info["dependencies"] else "None"
            health_check = "✅ Available" if info["has_health_check"] else "❌ Not Available"
            
            click.echo(f"\n📦 {name}")
            click.echo(f"   Status: {status}")
            click.echo(f"   Dependencies: {deps}")
            click.echo(f"   Health Check: {health_check}")
        
        click.echo(f"\nTotal Services: {len(service_list)}")
        
    except Exception as e:
        logger.error(f"Failed to list services: {e}")
        raise click.ClickException(f"Service listing failed: {e}")


@services.command()
def init():
    """Initialize all services."""
    logger.info("Initializing all services")
    
    try:
        initialize_application()
        click.echo("✅ All services initialized successfully")
    except Exception as e:
        logger.error(f"Service initialization failed: {e}")
        raise click.ClickException(f"Service initialization failed: {e}")


@services.command()
@click.option("--format", "output_format", default="table", type=click.Choice(["table", "json"]), help="Output format")
def health(output_format: str):
    """Check health of all services."""
    logger.info("Checking health of all services")
    
    async def check_health():
        try:
            # Ensure services are initialized
            initialize_application()
            
            # Run health checks
            health_results = await health_check_application()
            return health_results
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {"overall_status": "failed", "error": str(e)}
    
    # Run async health check
    health_results = asyncio.run(check_health())
    
    if output_format == "json":
        import json
        click.echo(json.dumps(health_results, indent=2))
    else:
        # Table format
        overall = health_results.get("overall_status", "unknown")
        status_icon = "✅" if overall == "healthy" else "❌" if overall == "failed" else "⚠️"
        
        click.echo(f"\n{status_icon} Overall Status: {overall.upper()}")
        click.echo("=" * 50)
        
        services_health = health_results.get("services", {})
        for service_name, service_health in services_health.items():
            service_status = service_health.get("status", "unknown")
            service_icon = "✅" if service_status == "healthy" else "❌"
            
            click.echo(f"{service_icon} {service_name}: {service_status}")
            
            if "error" in service_health:
                click.echo(f"   Error: {service_health['error']}")
            elif "note" in service_health:
                click.echo(f"   Note: {service_health['note']}")
        
        click.echo(f"\nServices: {health_results.get('initialized_count', 0)}/{health_results.get('total_count', 0)} initialized")


@app.group()
def db():
    """Database management commands."""
    pass


@db.command()
@click.option("--force", is_flag=True, help="Force database recreation")
def init(force: bool):
    """Initialize the database."""
    logger.info("Initializing database")
    
    try:
        from forth_ai_underwriting.core.database import DatabaseManager
        
        db_manager = DatabaseManager()
        
        if force:
            click.echo("🗑️  Dropping existing tables...")
            db_manager.drop_tables()
        
        click.echo("🔧 Creating database tables...")
        db_manager.create_tables()
        
        click.echo("✅ Database initialized successfully")
        
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise click.ClickException(f"Database initialization failed: {e}")


@db.command()
def status():
    """Check database status."""
    logger.info("Checking database status")
    
    try:
        from forth_ai_underwriting.core.database import DatabaseManager
        
        db_manager = DatabaseManager()
        
        # Try to connect and get basic info
        with db_manager.get_session() as session:
            # Simple query to test connection
            result = session.execute("SELECT 1").fetchone()
            
            if result:
                click.echo("✅ Database connection successful")
                click.echo(f"🔗 Database URL: {settings.database.url}")
                click.echo(f"📊 Pool size: {settings.database.pool_size}")
            else:
                click.echo("❌ Database connection failed")
                
    except Exception as e:
        logger.error(f"Database status check failed: {e}")
        click.echo(f"❌ Database error: {e}")


@app.group()
def validate():
    """Validation commands."""
    pass


@validate.command()
@click.argument("contact_id")
@click.option("--cache/--no-cache", default=True, help="Use cached results if available")
def contact(contact_id: str, cache: bool):
    """Validate a specific contact."""
    logger.info(f"Validating contact: {contact_id}")
    
    async def run_validation():
        try:
            # Initialize services
            initialize_application()
            
            # Get validation service
            registry = get_service_registry()
            validation_service = registry.get("validation_service")
            
            # Run validation
            results = await validation_service.validate_contact(contact_id)
            
            return results
            
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            return None
    
    # Run validation
    results = asyncio.run(run_validation())
    
    if results:
        click.echo(f"\n📋 Validation Results for Contact: {contact_id}")
        click.echo("=" * 60)
        
        passed = 0
        total = len(results)
        
        for result in results:
            status_icon = "✅" if result.result == "Pass" else "❌"
            click.echo(f"{status_icon} {result.title}")
            click.echo(f"   Result: {result.result}")
            click.echo(f"   Reason: {result.reason}")
            
            if hasattr(result, 'confidence') and result.confidence is not None:
                click.echo(f"   Confidence: {result.confidence:.2f}")
            
            click.echo()  # Add spacing
            
            if result.result == "Pass":
                passed += 1
        
        success_rate = (passed / total) * 100 if total > 0 else 0
        click.echo(f"📊 Summary: {passed}/{total} checks passed ({success_rate:.1f}% success rate)")
        
    else:
        click.echo("❌ Validation failed")


@app.group()
def config():
    """Configuration management commands."""
    pass


@config.command()
def show():
    """Show current configuration."""
    logger.info("Displaying current configuration")
    
    try:
        config_data = {
            "Application": {
                "Name": settings.app_name,
                "Version": settings.app_version,
                "Environment": settings.environment,
                "Debug": settings.debug,
                "Host": settings.app_host,
                "Port": settings.app_port
            },
            "Database": {
                "URL": settings.database.url,
                "Pool Size": settings.database.pool_size
            },
            "AI Services": {
                "Primary LLM": settings.llm.provider,
                "Fallback LLM": settings.llm.fallback_provider,
                "Gemini Model": settings.gemini.model_name,
                "AI Parsing Enabled": settings.document_processing.enable_ai_parsing
            },
            "Features": {
                "Caching": settings.cache.enable_caching,
                "Audit Logging": settings.features.enable_audit_logging,
                "Metrics": settings.features.metrics_enabled,
                "Rate Limiting": settings.features.rate_limit_enabled
            }
        }
        
        click.echo("\n🔧 Current Configuration:")
        click.echo("=" * 50)
        
        for section, items in config_data.items():
            click.echo(f"\n📦 {section}:")
            for key, value in items.items():
                click.echo(f"   {key}: {value}")
                
    except Exception as e:
        logger.error(f"Configuration display failed: {e}")
        raise click.ClickException(f"Configuration error: {e}")


@config.command()
def validate_config():
    """Validate current configuration."""
    logger.info("Validating configuration")
    
    try:
        # Test configuration by attempting to initialize settings
        issues = []
        
        # Check required settings
        if not settings.forth_api.base_url:
            issues.append("❌ FORTH_API_BASE_URL not configured")
        
        if not settings.forth_api.api_key:
            issues.append("❌ FORTH_API_KEY not configured")
        
        if not settings.gemini.api_key:
            issues.append("⚠️  GOOGLE_API_KEY not configured (Gemini features disabled)")
        
        if not settings.security.secret_key:
            issues.append("❌ SECRET_KEY not configured")
        
        # Check database configuration
        if not settings.database.url.startswith("postgresql"):
            issues.append("⚠️  Only PostgreSQL is supported for production deployment")
        
        if issues:
            click.echo("🔍 Configuration Issues Found:")
            click.echo("=" * 40)
            for issue in issues:
                click.echo(f"   {issue}")
        else:
            click.echo("✅ Configuration validation passed")
            
        # Try to initialize services to test configuration
        try:
            initialize_application()
            click.echo("✅ Service initialization test passed")
        except Exception as e:
            click.echo(f"❌ Service initialization test failed: {e}")
            
    except Exception as e:
        logger.error(f"Configuration validation failed: {e}")
        raise click.ClickException(f"Configuration validation failed: {e}")


@app.group()
def monitoring():
    """Monitoring and metrics commands."""
    pass


@monitoring.command()
def health():
    """Comprehensive system health check."""
    logger.info("Running comprehensive health check")
    
    async def run_health_check():
        try:
            # Initialize services
            initialize_application()
            
            # Check all services
            service_health = await health_check_application()
            
            # Check database
            db_health = check_database_health()
            
            # Check external APIs
            api_health = await check_external_apis_health()
            
            return {
                "services": service_health,
                "database": db_health,
                "external_apis": api_health
            }
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {"error": str(e)}
    
    health_results = asyncio.run(run_health_check())
    
    click.echo("\n🏥 System Health Check")
    click.echo("=" * 50)
    
    # Display results
    for component, results in health_results.items():
        if component == "error":
            click.echo(f"❌ Health check failed: {results}")
            continue
            
        click.echo(f"\n📊 {component.title()}:")
        
        if isinstance(results, dict):
            for key, value in results.items():
                if isinstance(value, dict):
                    status = value.get("status", "unknown")
                    icon = "✅" if status == "healthy" else "❌"
                    click.echo(f"   {icon} {key}: {status}")
                else:
                    click.echo(f"   {key}: {value}")


def check_database_health():
    """Check database health."""
    try:
        from forth_ai_underwriting.core.database import DatabaseManager
        
        db_manager = DatabaseManager()
        with db_manager.get_session() as session:
            session.execute("SELECT 1").fetchone()
            
        return {"status": "healthy", "connection": "active"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


async def check_external_apis_health():
    """Check external API health."""
    results = {}
    
    # Check Forth API
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            # Simple health check (adjust URL as needed)
            response = await client.get(f"{settings.forth_api.base_url}/health", timeout=5)
            results["forth_api"] = {"status": "healthy" if response.status_code == 200 else "degraded"}
    except Exception as e:
        results["forth_api"] = {"status": "unhealthy", "error": str(e)}
    
    # Check Gemini API
    try:
        if settings.gemini.api_key:
            from forth_ai_underwriting.services.gemini_service import get_gemini_service
            gemini_service = get_gemini_service()
            health = await gemini_service.health_check()
            results["gemini_api"] = health
        else:
            results["gemini_api"] = {"status": "disabled", "reason": "No API key configured"}
    except Exception as e:
        results["gemini_api"] = {"status": "unhealthy", "error": str(e)}
    
    return results


if __name__ == "__main__":
    app() 