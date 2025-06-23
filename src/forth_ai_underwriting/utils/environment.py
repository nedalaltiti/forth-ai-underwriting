"""
Environment variable handling with validation and type conversion for Forth AI Underwriting.

This module provides functions for retrieving environment variables with
proper typing, validation, and default values using a fail-safe approach.
"""

import os
import logging
from typing import Any, Callable, Dict, Optional, TypeVar, Union, cast

try:
    from dotenv import load_dotenv
    load_dotenv()
    DOTENV_LOADED = True
except ImportError:
    DOTENV_LOADED = False

# Configure logging
logger = logging.getLogger("forth_ai_underwriting.config")

# Type variable for generic type hints
T = TypeVar('T')

# Type converter registry for environment variables
TYPE_CONVERTERS: Dict[type, Callable[[str], Any]] = {
    str: str,
    int: int,
    float: float,
    bool: lambda v: v.lower() in ('true', 'yes', 'y', '1', 'on'),
    list: lambda v: [item.strip() for item in v.split(',') if item.strip()],
}


def get_env_var(name: str, default: Optional[T] = None, var_type: Optional[type] = None) -> Any:
    """
    Get environment variable with validation and type conversion.
    
    Args:
        name: The name of the environment variable
        default: Default value if not set
        var_type: Type to convert the value to (inferred from default if not provided)
    
    Returns:
        The value of the environment variable converted to the appropriate type
    
    Examples:
        >>> get_env_var("APP_PORT", 8000, int)  # Returns PORT as int with default 8000
        >>> get_env_var("DEBUG", False)         # Infers bool type from default value
    """
    # Get the raw value from environment
    value = os.environ.get(name)
    
    # If no value and no default, return None
    if value is None and default is None:
        return None
    
    # If we have a value, try to convert it
    if value is not None:
        # Determine the target type
        target_type = var_type or (type(default) if default is not None else str)
        
        # Get the appropriate converter
        converter = TYPE_CONVERTERS.get(target_type, str)
        
        try:
            return converter(value)
        except (ValueError, TypeError) as e:
            # Log the error and fall back to default
            logger.warning(
                f"Failed to convert environment variable '{name}' value '{value}' "
                f"to type {target_type.__name__}: {str(e)}. Using default value."
            )
    
    # If conversion failed or no value, return default
    return default


def get_env_var_bool(name: str, default: bool = False) -> bool:
    """
    Get boolean environment variable with validation.
    
    Args:
        name: The name of the environment variable
        default: Default value if not set
    
    Returns:
        The boolean value of the environment variable
    """
    return cast(bool, get_env_var(name, default, bool))


def get_env_var_list(name: str, default: Optional[list] = None) -> list:
    """
    Get a list from a comma-separated environment variable.
    
    Args:
        name: The name of the environment variable
        default: Default value if not set
    
    Returns:
        A list parsed from the comma-separated environment variable
    """
    if default is None:
        default = []
    return cast(list, get_env_var(name, default, list))


def get_env_var_int(name: str, default: int) -> int:
    """Get integer environment variable with validation."""
    return cast(int, get_env_var(name, default, int))


def get_env_var_float(name: str, default: float) -> float:
    """Get float environment variable with validation."""
    return cast(float, get_env_var(name, default, float))


def is_dotenv_loaded() -> bool:
    """Check if .env file was successfully loaded."""
    return DOTENV_LOADED


def is_aws_secrets_enabled() -> bool:
    """
    Check if AWS Secrets Manager integration is enabled.
    
    Returns:
        True if AWS secrets should be used, False otherwise
    """
    return get_env_var_bool("USE_AWS_SECRETS", False)


def get_aws_region() -> str:
    """
    Get AWS region from environment or use default.
    
    Returns:
        AWS region string
    """
    return get_env_var("AWS_REGION", "us-west-1")


def validate_required_env_vars() -> None:
    """
    Validate that all required environment variables are set.
    
    Raises:
        ValueError: If required environment variables are missing
    """
    required_vars = []
    
    # Check AWS configuration if secrets are enabled
    if is_aws_secrets_enabled():
        aws_required = ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION"]
        for var in aws_required:
            if not get_env_var(var):
                required_vars.append(var)
    
    # Check Teams configuration
    teams_required = ["MICROSOFT_APP_ID", "MICROSOFT_APP_PASSWORD", "TENANT_ID", "CLIENT_ID", "CLIENT_SECRET"]
    for var in teams_required:
        if not get_env_var(var):
            required_vars.append(var)
    
    if required_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(required_vars)}")


def get_environment_info() -> Dict[str, Any]:
    """
    Get information about the current environment configuration.
    
    Returns:
        Dictionary with environment information
    """
    return {
        "dotenv_loaded": is_dotenv_loaded(),
        "aws_secrets_enabled": is_aws_secrets_enabled(),
        "environment": get_env_var("ENVIRONMENT", "development"),
        "debug": get_env_var_bool("DEBUG", False),
        "aws_region": get_aws_region() if is_aws_secrets_enabled() else None,
        "google_cloud_project": get_env_var("GOOGLE_CLOUD_PROJECT"),
        "google_cloud_location": get_env_var("GOOGLE_CLOUD_LOCATION", "us-central1"),
    } 