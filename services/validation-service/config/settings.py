"""
Validation Service Configuration - Focused on AI validation settings.
"""

import os

from pydantic import Field
from pydantic_settings import BaseSettings


class ValidationConfig(BaseSettings):
    """
    Validation service configuration.
    Manages AI services, validation rules, and business logic settings.
    """

    # === Server Configuration ===
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8001, description="Server port")
    debug: bool = Field(default=False, description="Debug mode")
    log_level: str = Field(default="INFO", description="Logging level")

    # === AI Configuration ===
    gemini_api_key: str = Field(default="", description="Google Gemini API key")
    gemini_model_name: str = Field(
        default="gemini-2.0-flash-001", description="Gemini model"
    )
    gemini_temperature: float = Field(default=0.0, description="AI temperature setting")

    # === Forth API Configuration ===
    forth_api_base_url: str = Field(default="", description="Forth API base URL")
    forth_api_key: str = Field(default="", description="Forth API key")
    forth_api_timeout: int = Field(default=30, description="API timeout seconds")

    # === Validation Rules ===
    minimum_payment_amount: float = Field(
        default=250.0, description="Minimum payment validation"
    )
    minimum_age: int = Field(default=18, description="Minimum age requirement")

    # === Reference Data ===
    reference_data_path: str = Field(
        default="./data/reference_tables.json",
        description="Path to validation reference data",
    )

    # === Caching ===
    enable_caching: bool = Field(
        default=True, description="Enable validation result caching"
    )
    cache_ttl_hours: int = Field(default=24, description="Cache TTL in hours")

    # === Metrics ===
    enable_metrics: bool = Field(default=True, description="Enable metrics collection")

    class Config:
        env_prefix = "VALIDATION_"
        env_file = ".env"
        case_sensitive = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Override with environment variables if present
        if os.getenv("GEMINI_API_KEY"):
            self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        if os.getenv("FORTH_API_BASE_URL"):
            self.forth_api_base_url = os.getenv("FORTH_API_BASE_URL")
        if os.getenv("FORTH_API_KEY"):
            self.forth_api_key = os.getenv("FORTH_API_KEY")

    def validate_config(self) -> dict:
        """Validate validation service configuration."""
        errors = []
        warnings = []

        # AI configuration
        if not self.gemini_api_key:
            errors.append("Gemini API key is required for AI validation")

        # API configuration
        if not self.forth_api_base_url:
            warnings.append("Forth API URL not configured")
        if not self.forth_api_key:
            warnings.append("Forth API key not configured")

        # Validation rules
        if self.minimum_payment_amount <= 0:
            errors.append("Minimum payment amount must be positive")
        if self.minimum_age < 0:
            errors.append("Minimum age must be non-negative")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "service": "validation-service",
        }
