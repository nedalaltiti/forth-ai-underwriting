"""
Document Service Configuration - Focused on document processing settings.
"""

import os

from pydantic import Field
from pydantic_settings import BaseSettings


class DocumentConfig(BaseSettings):
    """
    Document service configuration.
    Manages document downloading, processing, and storage settings.
    """

    # === Service Configuration ===
    service_name: str = Field(
        default="document-service", description="Service identifier"
    )
    poll_interval_seconds: int = Field(default=5, description="Queue polling interval")
    max_concurrent_downloads: int = Field(
        default=3, description="Max concurrent downloads"
    )

    # === Queue Configuration ===
    queue_name: str = Field(
        default="uw-contracts-parser-dev-sqs",
        description="SQS queue name for incoming download requests",
    )
    aws_region: str = Field(default="us-west-1", description="AWS region")

    # === AWS Configuration ===
    aws_access_key_id: str = Field(default="", description="AWS access key")
    aws_secret_access_key: str = Field(default="", description="AWS secret key")

    # === S3 Configuration ===
    s3_bucket_name: str = Field(
        default="contact-contracts-dev-s3-us-west-1",
        description="S3 bucket for document storage",
    )

    # === Forth API Configuration ===
    forth_api_base_url: str = Field(default="", description="Forth API base URL")
    forth_api_key: str = Field(default="", description="Forth API key")
    forth_api_timeout: int = Field(default=30, description="API timeout seconds")

    # === Document Processing ===
    max_file_size_mb: int = Field(default=50, description="Maximum file size in MB")
    temp_dir: str = Field(
        default="./temp_downloads", description="Temporary download directory"
    )

    # === Logging ===
    log_level: str = Field(default="INFO", description="Logging level")

    class Config:
        env_prefix = "DOCUMENT_"
        env_file = ".env"
        case_sensitive = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Override with environment variables if present
        if os.getenv("AWS_REGION"):
            self.aws_region = os.getenv("AWS_REGION")
        if os.getenv("AWS_ACCESS_KEY_ID"):
            self.aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
        if os.getenv("AWS_SECRET_ACCESS_KEY"):
            self.aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        if os.getenv("AWS_S3_BUCKET_NAME"):
            self.s3_bucket_name = os.getenv("AWS_S3_BUCKET_NAME")
        if os.getenv("SQS_MAIN_QUEUE"):
            self.queue_name = os.getenv("SQS_MAIN_QUEUE")
        if os.getenv("FORTH_API_BASE_URL"):
            self.forth_api_base_url = os.getenv("FORTH_API_BASE_URL")
        if os.getenv("FORTH_API_KEY"):
            self.forth_api_key = os.getenv("FORTH_API_KEY")

    def validate_config(self) -> dict:
        """Validate document service configuration."""
        errors = []
        warnings = []

        # Required fields
        if not self.queue_name:
            errors.append("Queue name is required")
        if not self.s3_bucket_name:
            errors.append("S3 bucket name is required")
        if not self.aws_region:
            errors.append("AWS region is required")

        # API configuration
        if not self.forth_api_base_url:
            warnings.append("Forth API URL not configured")
        if not self.forth_api_key:
            warnings.append("Forth API key not configured")

        # AWS credentials
        if not self.aws_access_key_id or not self.aws_secret_access_key:
            warnings.append("AWS credentials not configured - may use IAM roles")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "service": "document-service",
        }
