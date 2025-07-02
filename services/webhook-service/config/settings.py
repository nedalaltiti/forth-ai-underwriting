"""
Webhook Service Configuration - Focused only on webhook-related settings.
Follows microservices principle of service-specific configuration.
"""

import os

from pydantic import Field
from pydantic_settings import BaseSettings


class WebhookConfig(BaseSettings):
    """
    Webhook service configuration.
    Each microservice manages its own configuration scope.
    """

    # === Server Configuration ===
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port")
    debug: bool = Field(default=False, description="Debug mode")
    log_level: str = Field(default="INFO", description="Logging level")

    # === Queue Configuration ===
    queue_name: str = Field(
        default="uw-contracts-parser-dev-sqs",
        description="SQS queue name for document processing",
    )
    aws_region: str = Field(default="us-west-1", description="AWS region")
    use_local_queue: bool = Field(
        default=False, description="Use local queue for development"
    )

    # === AWS Configuration ===
    aws_access_key_id: str = Field(default="", description="AWS access key")
    aws_secret_access_key: str = Field(default="", description="AWS secret key")

    # === Forth API Configuration (for document enhancement) ===
    forth_api_base_url: str = Field(default="", description="Forth API base URL")
    forth_api_key: str = Field(default="", description="Forth API key")
    forth_api_timeout: int = Field(default=30, description="API timeout seconds")

    # === Security ===
    cors_origins: list[str] = Field(default=["*"], description="CORS allowed origins")

    # === Metrics ===
    enable_metrics: bool = Field(default=True, description="Enable metrics collection")

    class Config:
        env_prefix = "WEBHOOK_"
        env_file = ".env"
        case_sensitive = False

    def __init__(self, **kwargs):
        # Load from environment variables with fallbacks
        super().__init__(**kwargs)

        # Override with environment variables if present
        if os.getenv("AWS_REGION"):
            self.aws_region = os.getenv("AWS_REGION")
        if os.getenv("AWS_ACCESS_KEY_ID"):
            self.aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
        if os.getenv("AWS_SECRET_ACCESS_KEY"):
            self.aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        if os.getenv("QUEUE_NAME"):
            self.queue_name = os.getenv("QUEUE_NAME")

    def validate_config(self) -> dict:
        """Validate webhook service configuration."""
        errors = []
        warnings = []

        # Validate required fields
        if not self.queue_name:
            errors.append("Queue name is required")

        if not self.aws_region:
            errors.append("AWS region is required")

        # Check credentials for AWS mode
        if not self.use_local_queue:
            if not self.aws_access_key_id or not self.aws_secret_access_key:
                warnings.append("AWS credentials not configured - may use IAM roles")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "service": "webhook-service",
        }
