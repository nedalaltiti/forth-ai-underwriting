#!/usr/bin/env python3
"""
Forth AI Webhook Service - Clean Modular Implementation

A production-ready webhook service following 2025 AI and software engineering best practices:
- Clean separation of concerns
- Dependency injection
- Async/await throughout
- Comprehensive error handling
- Metrics and health monitoring
- Proper configuration management with multiple secret providers

Usage:
    python webhook_service.py --port 8000
    python webhook_service.py --queue-name my-queue --log-level DEBUG

Environment Variables:
    WEBHOOK_QUEUE_NAME=my-queue
    WEBHOOK_FORTH_API_BASE_URL=https://api.forthcrm.com/v1
    WEBHOOK_FORTH_API_KEY=your-api-key
    WEBHOOK_SECRET_PROVIDER=aws_secrets_manager  # or env_var, aws_parameter_store
    WEBHOOK_AWS_SECRETS_NAME=forth-underwriting-secrets
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Add src to Python path for imports
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

import uvicorn
from forth_ai_underwriting.core.error_handling import handle_expected_errors
from forth_ai_underwriting.core.observability import observability
from forth_ai_underwriting.webhooks.api import create_standalone_app

# Import our clean modular components
from forth_ai_underwriting.webhooks.config import WebhookConfig
from loguru import logger


@handle_expected_errors("service_startup", "webhook_service")
def setup_logging(log_level: str = "INFO") -> None:
    """Configure structured logging with proper formatting."""
    # Remove default loguru handler and add custom one
    logger.remove()

    # Add console handler with structured format
    logger.add(
        sys.stdout,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True,
        backtrace=True,
        diagnose=True,
    )

    # Add file handler for production
    if os.getenv("ENVIRONMENT", "development") == "production":
        logger.add(
            "logs/webhook_service.log",
            level=log_level,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            rotation="10 MB",
            retention="10 days",
            compression="gz",
        )

    logger.info("Logging configured at level: {}", log_level)


def log_configuration(config: WebhookConfig) -> None:
    """Log service configuration for debugging."""
    logger.info("=== WEBHOOK SERVICE CONFIGURATION ===")
    logger.info("Server: {}:{}", config.host, config.port)
    logger.info("Log Level: {}", config.log_level)
    logger.info("Queue: {}", config.queue_name)
    logger.info("AWS Region: {}", config.aws_region)
    logger.info("Local Queue: {}", config.use_local_queue)
    logger.info("Forth API URL: {}", config.forth_api_base_url or "Not configured")
    logger.info(
        "Forth API Key: {}", "Configured" if config.forth_api_key else "Not configured"
    )
    logger.info("Document Enhancement: {}", config.enable_document_enhancement)
    logger.info("Metrics: {}", config.enable_metrics)
    logger.info("Health Checks: {}", config.enable_health_checks)
    logger.info("=====================================")


@handle_expected_errors("detect_environment", "webhook_service")
def detect_environment() -> dict:
    """Detect and validate the runtime environment."""
    environment_info = {
        "aws_credentials": bool(
            os.getenv("AWS_ACCESS_KEY_ID") or os.getenv("AWS_PROFILE")
        ),
        "aws_region": os.getenv(
            "AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-west-1")
        ),
        "has_forth_config": bool(os.getenv("WEBHOOK_FORTH_API_BASE_URL")),
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "environment": os.getenv("ENVIRONMENT", "development"),
    }

    return environment_info


@handle_expected_errors("create_application", "webhook_service")
def create_application(config: WebhookConfig):
    """Create and configure the FastAPI application."""
    # Prepare Forth API configuration
    forth_api_config = None
    if config.forth_api_base_url and config.forth_api_key:
        forth_api_config = {
            "base_url": config.forth_api_base_url,
            "api_key": config.forth_api_key,
            "timeout": config.forth_api_timeout,
        }

    # Create application
    app = create_standalone_app(
        queue_name=config.queue_name,
        forth_api_config=forth_api_config,
        use_local_queue=config.use_local_queue,
        aws_region=config.aws_region,
    )

    # Initialize observability if enabled
    if config.enable_metrics:
        observability.instrument_app(app)
        logger.info("✅ Observability instrumentation enabled")

    return app


@handle_expected_errors("run_server", "webhook_service")
async def run_server(app, config: WebhookConfig) -> None:
    """Run the webhook service with proper configuration."""
    server_config = uvicorn.Config(
        app,
        host=config.host,
        port=config.port,
        log_level=config.log_level.lower(),
        access_log=True,
        reload=config.debug,
        workers=1,  # Single worker for webhook service
        loop="asyncio",
    )

    server = uvicorn.Server(server_config)

    logger.info("🚀 Starting Forth AI Webhook Service")
    logger.info("📡 Server: {}:{}", config.host, config.port)
    logger.info("📨 Queue: {}", config.queue_name)
    logger.info("🔧 Log Level: {}", config.log_level)
    logger.info("🌐 API Docs: http://{}:{}/docs", config.host, config.port)

    try:
        await server.serve()
    except KeyboardInterrupt:
        logger.info("🛑 Service stopped by user")
    except Exception as e:
        logger.error("❌ Server error: {}", e)
        raise


def main():
    """Main entry point for the webhook service."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Forth AI Webhook Service",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with default settings
  python webhook_service.py

  # Run on specific port with debug logging
  python webhook_service.py --port 8080 --log-level DEBUG

  # Check configuration only
  python webhook_service.py --check-config

  # Use local queue for development
  python webhook_service.py --local-queue
        """,
    )

    parser.add_argument("--port", type=int, help="Server port (default: from config)")
    parser.add_argument("--host", type=str, help="Server host (default: from config)")
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: from config)",
    )
    parser.add_argument(
        "--local-queue", action="store_true", help="Use local queue instead of SQS"
    )
    parser.add_argument(
        "--check-config", action="store_true", help="Check configuration and exit"
    )
    parser.add_argument(
        "--metrics-port", type=int, help="Port for Prometheus metrics endpoint"
    )

    args = parser.parse_args()

    try:
        # Load configuration
        config = WebhookConfig()

        # Override with command line arguments
        if args.port:
            config.port = args.port
        if args.host:
            config.host = args.host
        if args.log_level:
            config.log_level = args.log_level
        if args.local_queue:
            config.use_local_queue = True
        if args.metrics_port:
            config.metrics_port = args.metrics_port

        # Setup logging first
        setup_logging(config.log_level)

        # Log configuration
        log_configuration(config)

        # Detect environment
        env_info = detect_environment()
        logger.info("Environment detected: {}", env_info)

        # Validate configuration
        validation_result = config.validate()
        if not validation_result["valid"]:
            logger.error("❌ Configuration validation failed:")
            for error in validation_result["errors"]:
                logger.error("  - {}", error)

            for warning in validation_result["warnings"]:
                logger.warning("  - {}", warning)

            if validation_result["errors"]:
                sys.exit(1)

        logger.info("✅ Configuration validated successfully")

        # Check configuration and exit if requested
        if args.check_config:
            logger.info("✅ Configuration check completed")
            logger.info("Security score: {}/100", validation_result["security_score"])
            sys.exit(0)

        # Create application
        app = create_application(config)

        # Run server
        asyncio.run(run_server(app, config))

    except KeyboardInterrupt:
        logger.info("🛑 Service interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error("❌ Service startup failed: {}", e)
        logger.error("Stack trace:", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
