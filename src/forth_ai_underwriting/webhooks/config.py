"""
Webhook service configuration with multiple secret providers.
Supports environment variables, AWS Parameter Store, and AWS Secrets Manager.
"""

import json
import logging
import os
from enum import Enum
from typing import Any

from pydantic import ConfigDict, Field, field_validator
from pydantic_settings import BaseSettings


class SecretProvider(str, Enum):
    """Supported secret providers."""

    ENV_VAR = "env_var"
    AWS_PARAMETER_STORE = "aws_parameter_store"
    AWS_SECRETS_MANAGER = "aws_secrets_manager"
    HASHICORP_VAULT = "hashicorp_vault"


class WebhookConfig(BaseSettings):
    """
    Webhook service configuration with multiple provider support.

    Priority order:
    1. Environment variables
    2. AWS Parameter Store (if enabled)
    3. AWS Secrets Manager (if enabled)
    4. Default values
    """

    # === Server Configuration ===
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port")
    log_level: str = Field(default="INFO", description="Logging level")
    debug: bool = Field(default=False, description="Debug mode")

    # === Queue Configuration ===
    queue_name: str = Field(
        default="uw-contracts-parser-dev-sqs",  # Default queue name
        description="SQS queue name",
    )
    aws_region: str = Field(
        default="us-west-1", description="AWS region"  # Default region with fallback
    )
    use_local_queue: bool = Field(
        default=False,  # Default to AWS SQS
        description="Use local queue instead of SQS",
    )

    # === Forth API Configuration ===
    forth_api_base_url: str | None = Field(
        default=None, description="Forth API base URL"
    )
    forth_api_key: str | None = Field(default=None, description="Forth API key")
    forth_api_key_id: str | None = Field(default=None, description="Forth API key ID")
    forth_api_timeout: int = Field(
        default=30, description="Forth API request timeout in seconds"
    )

    # === Metrics Configuration ===
    metrics_port: int = Field(
        default=9090, description="Port for Prometheus metrics endpoint"
    )

    # === Feature Flags ===
    enable_document_enhancement: bool = Field(
        default=True, description="Enable document enhancement via Forth API"
    )
    enable_metrics: bool = Field(default=True, description="Enable metrics collection")
    enable_health_checks: bool = Field(
        default=True, description="Enable health check endpoints"
    )

    # === Secret Management ===
    secret_provider: SecretProvider = Field(
        default=SecretProvider.ENV_VAR, description="Secret provider to use"
    )
    aws_parameter_prefix: str = Field(
        default="/forth-underwriting/webhooks/",
        description="AWS Parameter Store prefix",
    )
    aws_secrets_name: str | None = Field(
        default=None, description="AWS Secrets Manager secret name"
    )

    # === Security ===
    cors_origins: list[str] = Field(default=["*"], description="CORS allowed origins")
    webhook_secret: str | None = Field(
        default=None, description="Webhook signature verification secret"
    )

    def __init__(self, **kwargs):
        # Handle AWS region from multiple environment variable sources
        if "aws_region" not in kwargs:
            aws_region = (
                os.getenv("WEBHOOK_AWS_REGION")
                or os.getenv("AWS_REGION")
                or os.getenv("AWS_DEFAULT_REGION")
                or "us-west-1"
            )
            kwargs["aws_region"] = aws_region

        # Handle queue name from multiple sources
        if "queue_name" not in kwargs:
            queue_name = (
                os.getenv("WEBHOOK_QUEUE_NAME")
                or os.getenv("SQS_MAIN_QUEUE")
                or "uw-contracts-parser-dev-sqs"
            )
            kwargs["queue_name"] = queue_name

        # Handle use_local_queue from multiple sources
        if "use_local_queue" not in kwargs:
            use_local_str = (
                os.getenv("WEBHOOK_USE_LOCAL_QUEUE")
                or os.getenv("USE_LOCAL_QUEUE")
                or "false"
            )
            kwargs["use_local_queue"] = use_local_str.lower() in (
                "true",
                "1",
                "yes",
                "on",
            )

        super().__init__(**kwargs)

    model_config = ConfigDict(
        env_prefix="WEBHOOK_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        # Custom field aliases for environment variables
        fields={
            "aws_region": {
                "env": ["WEBHOOK_AWS_REGION", "AWS_REGION", "AWS_DEFAULT_REGION"]
            },
            "queue_name": {"env": ["WEBHOOK_QUEUE_NAME", "SQS_MAIN_QUEUE"]},
            "use_local_queue": {"env": ["WEBHOOK_USE_LOCAL_QUEUE", "USE_LOCAL_QUEUE"]},
        },
    )

    # Support for AWS Parameter Store and Secrets Manager
    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        return (
            init_settings,
            env_settings,
            lambda: aws_parameter_store_settings(settings_cls),
            lambda: aws_secrets_manager_settings(settings_cls),
            dotenv_settings,
            file_secret_settings,
        )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v):
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of: {valid_levels}")
        return v.upper()

    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins(cls, v):
        """Validate CORS origins."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    def get_forth_api_config(self) -> dict[str, Any]:
        """Get Forth API configuration with secrets loaded."""
        return {
            "base_url": self.forth_api_base_url,
            "api_key": self._get_secret("forth_api_key", self.forth_api_key),
            "api_key_id": self.forth_api_key_id,
            "timeout": self.forth_api_timeout,
        }

    def _get_secret(
        self, secret_name: str, default_value: str | None = None
    ) -> str | None:
        """Get secret from configured provider."""
        if self.secret_provider == SecretProvider.ENV_VAR:
            return default_value

        elif self.secret_provider == SecretProvider.AWS_PARAMETER_STORE:
            return self._get_from_parameter_store(secret_name, default_value)

        elif self.secret_provider == SecretProvider.AWS_SECRETS_MANAGER:
            return self._get_from_secrets_manager(secret_name, default_value)

        else:
            logging.warning(f"Unsupported secret provider: {self.secret_provider}")
            return default_value

    def _get_from_parameter_store(
        self, secret_name: str, default_value: str | None
    ) -> str | None:
        """Get secret from AWS Parameter Store."""
        try:
            import boto3

            ssm = boto3.client("ssm", region_name=self.aws_region)
            parameter_name = f"{self.aws_parameter_prefix}{secret_name}"

            response = ssm.get_parameter(Name=parameter_name, WithDecryption=True)

            value = response["Parameter"]["Value"]
            logging.info(f"✅ Loaded secret {secret_name} from Parameter Store")
            return value

        except Exception as e:
            logging.warning(f"Failed to load {secret_name} from Parameter Store: {e}")
            return default_value

    def _get_from_secrets_manager(
        self, secret_name: str, default_value: str | None
    ) -> str | None:
        """Get secret from AWS Secrets Manager."""
        try:
            import boto3

            secrets_client = boto3.client("secretsmanager", region_name=self.aws_region)

            if self.aws_secrets_name:
                # Get from named secret
                response = secrets_client.get_secret_value(
                    SecretId=self.aws_secrets_name
                )
                secret_data = json.loads(response["SecretString"])
                value = secret_data.get(secret_name)

                if value:
                    logging.info(f"✅ Loaded secret {secret_name} from Secrets Manager")
                    return value
                else:
                    logging.warning(
                        f"Secret {secret_name} not found in {self.aws_secrets_name}"
                    )

            return default_value

        except Exception as e:
            logging.warning(f"Failed to load {secret_name} from Secrets Manager: {e}")
            return default_value

    def log_configuration(self):
        """Log configuration (without sensitive data)."""
        logging.info("=== WEBHOOK SERVICE CONFIGURATION ===")
        logging.info(f"Server: {self.host}:{self.port}")
        logging.info(f"Log Level: {self.log_level}")
        logging.info(f"Queue: {self.queue_name}")
        logging.info(f"AWS Region: {self.aws_region}")
        logging.info(f"Local Queue: {self.use_local_queue}")
        logging.info(f"Forth API URL: {self.forth_api_base_url or 'Not configured'}")
        logging.info(
            f"Forth API Key: {'Configured' if self.forth_api_key else 'Not configured'}"
        )
        logging.info(f"Document Enhancement: {self.enable_document_enhancement}")
        logging.info(f"Metrics: {self.enable_metrics}")
        logging.info(f"Health Checks: {self.enable_health_checks}")
        logging.info("=====================================")

    def validate(self) -> dict[str, Any]:
        """Validate configuration and return validation result."""
        errors = []
        warnings = []

        # Validate required fields
        if not self.queue_name:
            errors.append("Queue name is required")

        if not self.host:
            errors.append("Server host is required")

        if self.port < 1 or self.port > 65535:
            errors.append("Server port must be between 1 and 65535")

        # Validate Forth API configuration
        if self.enable_document_enhancement:
            if not self.forth_api_base_url:
                warnings.append(
                    "Forth API base URL not configured - document enhancement disabled"
                )

            if not self.forth_api_key:
                warnings.append(
                    "Forth API key not configured - document enhancement may fail"
                )

        # Validate AWS configuration
        if not self.use_local_queue:
            if not self.aws_region:
                errors.append("AWS region is required when using SQS")

        # Validate security settings
        if "*" in self.cors_origins and len(self.cors_origins) > 1:
            warnings.append(
                "CORS origins includes '*' with other origins - this may be insecure"
            )

        # Calculate security score
        security_checks = {
            "specific_cors": "*" not in self.cors_origins,
            "webhook_secret": bool(self.webhook_secret),
            "forth_api_configured": bool(
                self.forth_api_base_url and self.forth_api_key
            ),
            "proper_log_level": self.log_level in ["INFO", "WARNING", "ERROR"],
            "debug_disabled": not self.debug,
        }

        security_score = sum(1 for check in security_checks.values() if check) * 20

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "security_score": security_score,
            "security_checks": security_checks,
        }


def aws_parameter_store_settings(settings: BaseSettings) -> dict[str, Any]:
    """Load settings from AWS Parameter Store."""
    if (
        not hasattr(settings, "secret_provider")
        or settings.secret_provider != SecretProvider.AWS_PARAMETER_STORE
    ):
        return {}

    try:
        import boto3

        ssm = boto3.client(
            "ssm", region_name=getattr(settings, "aws_region", "us-west-1")
        )
        prefix = getattr(
            settings, "aws_parameter_prefix", "/forth-underwriting/webhooks/"
        )

        # Get all parameters with the prefix
        paginator = ssm.get_paginator("get_parameters_by_path")

        parameters = {}
        for page in paginator.paginate(
            Path=prefix, Recursive=True, WithDecryption=True
        ):
            for param in page["Parameters"]:
                # Convert parameter name to config key
                key = param["Name"].replace(prefix, "").replace("/", "_").lower()
                parameters[key] = param["Value"]

        logging.info(f"✅ Loaded {len(parameters)} parameters from Parameter Store")
        return parameters

    except Exception as e:
        logging.warning(f"Failed to load from Parameter Store: {e}")
        return {}


def aws_secrets_manager_settings(settings: BaseSettings) -> dict[str, Any]:
    """Load settings from AWS Secrets Manager."""
    if (
        not hasattr(settings, "secret_provider")
        or settings.secret_provider != SecretProvider.AWS_SECRETS_MANAGER
    ):
        return {}

    if not hasattr(settings, "aws_secrets_name") or not settings.aws_secrets_name:
        return {}

    try:
        import boto3

        secrets_client = boto3.client(
            "secretsmanager", region_name=getattr(settings, "aws_region", "us-west-1")
        )

        response = secrets_client.get_secret_value(SecretId=settings.aws_secrets_name)
        secret_data = json.loads(response["SecretString"])

        # Convert secret keys to config format
        parameters = {}
        for key, value in secret_data.items():
            config_key = key.replace("-", "_").lower()
            parameters[config_key] = value

        logging.info(f"✅ Loaded {len(parameters)} secrets from Secrets Manager")
        return parameters

    except Exception as e:
        logging.warning(f"Failed to load from Secrets Manager: {e}")
        return {}


def setup_logging(level: str = "INFO"):
    """Setup logging configuration."""
    import logging

    # Configure logging format
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Set third-party loggers to WARNING to reduce noise
    for logger_name in ["boto3", "botocore", "urllib3", "aioboto3"]:
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    logging.info(f"Logging configured at level: {level}")


def get_config() -> WebhookConfig:
    """Get webhook configuration with proper secret loading."""
    return WebhookConfig()


# Export for convenience
config = get_config()
