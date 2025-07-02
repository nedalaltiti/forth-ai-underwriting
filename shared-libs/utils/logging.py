"""
Shared Logging Utilities - Common logging setup for microservices.
"""

import sys

from loguru import logger


def setup_logging(
    service_name: str,
    log_level: str = "INFO",
    log_format: str | None = None,
    enable_json: bool = False,
):
    """
    Set up standardized logging for microservices.

    Args:
        service_name: Name of the microservice
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_format: Custom log format string
        enable_json: Enable JSON structured logging
    """

    # Remove default logger
    logger.remove()

    # Default format with service name
    if log_format is None:
        if enable_json:
            log_format = (
                '{{"timestamp": "{time:YYYY-MM-DD HH:mm:ss.SSS}", '
                '"service": "' + service_name + '", '
                '"level": "{level}", '
                '"message": "{message}"}}'
            )
        else:
            log_format = (
                "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
                f"{service_name}:{{function}}:{{line}} - {{message}}"
            )

    # Add console handler
    logger.add(
        sys.stdout,
        format=log_format,
        level=log_level.upper(),
        colorize=not enable_json,
        backtrace=True,
        diagnose=True,
    )

    logger.info(f"✅ Logging configured for {service_name} at level: {log_level}")


def get_logger(name: str):
    """Get a logger instance for a specific component."""
    return logger.bind(component=name)
