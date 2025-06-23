from pydantic_settings import BaseSettings
from pydantic import Field, validator
from typing import Optional, List, Union
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Application Configuration
    app_name: str = "Forth AI Underwriting System"
    app_version: str = "0.1.0"
    app_host: str = Field(default="0.0.0.0", env="APP_HOST")
    app_port: int = Field(default=8000, env="APP_PORT")
    debug: bool = Field(default=False, env="DEBUG")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    environment: str = Field(default="development", description="Environment (development, staging, production)")
    
    # Security Configuration
    secret_key: str = Field(..., description="Secret key for encryption")
    cors_origins: List[str] = Field(default=["*"], description="CORS allowed origins")
    cors_allow_credentials: bool = True
    cors_allow_methods: List[str] = Field(default=["*"])
    cors_allow_headers: List[str] = Field(default=["*"])
    
    # Database Configuration
    database_url: str = Field(default="sqlite:///./forth_underwriting.db", description="Database connection URL", validation_alias="DATABASE_URL")
    database_pool_size: int = Field(default=20, description="Database connection pool size")
    database_max_overflow: int = Field(default=30, description="Database max overflow connections")
    database_pool_timeout: int = Field(default=30, description="Database pool timeout in seconds")
    database_pool_recycle: int = Field(default=3600, description="Database pool recycle time in seconds")
    
    # Redis Configuration (for caching and rate limiting)
    redis_url: Optional[str] = Field(default=None, description="Redis connection URL")
    redis_password: Optional[str] = Field(default=None, description="Redis password")
    redis_db: int = Field(default=0, description="Redis database number")
    redis_max_connections: int = Field(default=50, description="Redis max connections")
    cache_ttl_seconds: int = Field(default=3600, description="Default cache TTL in seconds")
    
    # Celery Configuration (for background tasks)
    celery_broker_url: Optional[str] = Field(default=None, description="Celery broker URL")
    celery_result_backend: Optional[str] = Field(default=None, description="Celery result backend URL")
    
    # Forth API Configuration
    forth_api_base_url: str = Field(env="FORTH_API_BASE_URL")
    forth_api_key: str = Field(env="FORTH_API_KEY")
    forth_webhook_secret: Optional[str] = Field(default=None, env="FORTH_WEBHOOK_SECRET")
    forth_api_timeout: int = Field(default=30, description="Forth API timeout in seconds")
    forth_api_retries: int = Field(default=3, description="Forth API retry attempts")
    
    # AWS Configuration
    use_aws_secrets: bool = Field(default=False, env="USE_AWS_SECRETS")
    aws_region: str = Field(default="us-west-1", env="AWS_REGION")
    aws_access_key_id: Optional[str] = Field(default=None, env="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: Optional[str] = Field(default=None, env="AWS_SECRET_ACCESS_KEY")
    aws_db_secret_name: Optional[str] = Field(default=None, env="AWS_DB_SECRET_NAME")
    aws_gemini_secret_name: Optional[str] = Field(default=None, env="AWS_GEMINI_SECRET_NAME")
    
    # Google Cloud Configuration
    google_cloud_location: str = Field(default="us-central1", env="GOOGLE_CLOUD_LOCATION")
    google_cloud_project: str = Field(default="", env="GOOGLE_CLOUD_PROJECT")
    
    # Gemini AI Configuration
    gemini_model_name: str = Field(default="gemini-2.0-flash-001", env="GEMINI_MODEL_NAME")
    gemini_temperature: float = Field(default=0.0, env="GEMINI_TEMPERATURE")
    gemini_max_output_tokens: int = Field(default=1024, env="GEMINI_MAX_OUTPUT_TOKENS")
    gemini_api_key: Optional[str] = Field(default=None, env="GOOGLE_API_KEY")
    
    # OpenAI Configuration (fallback)
    openai_api_key: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4", description="OpenAI model to use")
    openai_max_tokens: int = Field(default=4000, description="OpenAI max tokens")
    openai_temperature: float = Field(default=0.1, description="OpenAI temperature")
    openai_timeout: int = Field(default=60, description="OpenAI API timeout in seconds")
    
    # Embedding Configuration
    embedding_model_name: str = Field(default="text-embedding-005", env="EMBEDDING_MODEL_NAME")
    embedding_dimensions: int = Field(default=768, env="EMBEDDING_DIMENSIONS")
    cache_embeddings: bool = Field(default=True, env="CACHE_EMBEDDINGS")
    cache_ttl_seconds_embeddings: int = Field(default=3600, env="CACHE_TTL_SECONDS")
    min_streaming_length: int = Field(default=50, env="MIN_STREAMING_LENGTH")
    show_ack_threshold: int = Field(default=10, env="SHOW_ACK_THRESHOLD")
    enable_streaming: bool = Field(default=True, env="ENABLE_STREAMING")
    streaming_delay: float = Field(default=1.2, env="STREAMING_DELAY")
    max_chunk_size: int = Field(default=150, env="max_chunk_size")
    
    # Azure Form Recognizer Configuration (optional)
    azure_form_recognizer_endpoint: Optional[str] = Field(default=None, description="Azure Form Recognizer endpoint")
    azure_form_recognizer_key: Optional[str] = Field(default=None, description="Azure Form Recognizer key")
    azure_form_recognizer_model_id: str = Field(default="prebuilt-document", description="Azure Form Recognizer model ID")
    
    # Microsoft Teams Bot Configuration
    microsoft_app_id: str = Field(env="MICROSOFT_APP_ID")
    microsoft_app_password: str = Field(env="MICROSOFT_APP_PASSWORD")
    tenant_id: str = Field(env="TENANT_ID")
    client_id: str = Field(env="CLIENT_ID")
    client_secret: str = Field(env="CLIENT_SECRET")
    teams_webhook_endpoint: str = Field(default="/webhook/teams", description="Teams webhook endpoint")
    
    # Webhook Configuration
    webhook_endpoint: str = Field(default="/webhook/forth-docs", env="WEBHOOK_ENDPOINT")
    webhook_timeout: int = Field(default=30, env="WEBHOOK_TIMEOUT")
    webhook_verify_ssl: bool = Field(default=True, description="Verify SSL for webhook requests")
    
    # Rate Limiting Configuration
    rate_limit_enabled: bool = Field(default=True, description="Enable rate limiting")
    rate_limit_requests_per_minute: int = Field(default=60, description="Default rate limit per minute")
    rate_limit_burst_size: int = Field(default=10, description="Rate limit burst size")
    
    # Monitoring Configuration
    metrics_enabled: bool = Field(default=True, description="Enable metrics collection")
    sentry_dsn: Optional[str] = Field(default=None, description="Sentry DSN for error tracking")
    prometheus_metrics_path: str = Field(default="/metrics", description="Prometheus metrics endpoint")
    
    # Document Processing Configuration
    max_file_size_mb: int = Field(default=50, description="Maximum file size in MB")
    allowed_file_types: List[str] = Field(default=["pdf", "doc", "docx"], description="Allowed file types")
    document_processing_timeout: int = Field(default=300, description="Document processing timeout in seconds")
    
    # LLM Processing Configuration
    llm_provider: str = Field(default="gemini", description="Primary LLM provider (gemini, openai)")
    llm_fallback_provider: str = Field(default="openai", description="Fallback LLM provider")
    llm_max_retries: int = Field(default=3, description="Maximum LLM retry attempts")
    llm_retry_delay: float = Field(default=1.0, description="Delay between LLM retries")
    llm_request_timeout: int = Field(default=60, description="LLM request timeout in seconds")
    
    # Validation Configuration
    validation_cache_enabled: bool = Field(default=True, description="Enable validation result caching")
    validation_cache_ttl_hours: int = Field(default=24, description="Validation cache TTL in hours")
    validation_timeout_seconds: int = Field(default=120, description="Validation timeout in seconds")
    validation_retry_attempts: int = Field(default=2, description="Validation retry attempts")
    
    # Background Task Configuration
    background_task_queue_name: str = Field(default="forth_underwriting_queue", description="Background task queue name")
    background_task_timeout: int = Field(default=600, description="Background task timeout in seconds")
    background_task_retry_delay: int = Field(default=60, description="Background task retry delay in seconds")
    
    # Logging Configuration
    log_format: str = Field(default="json", description="Log format (json, text)")
    log_file_path: Optional[str] = Field(default=None, description="Log file path")
    log_rotation: str = Field(default="1 week", description="Log rotation schedule")
    log_retention: str = Field(default="1 month", description="Log retention period")
    
    # Performance Configuration
    async_pool_size: int = Field(default=100, description="Async pool size")
    request_timeout: int = Field(default=300, description="Request timeout in seconds")
    response_timeout: int = Field(default=300, description="Response timeout in seconds")
    
    # Feature Flags
    enable_ai_parsing: bool = Field(default=True, description="Enable AI parsing of documents")
    enable_azure_form_recognizer: bool = Field(default=False, description="Enable Azure Form Recognizer")
    enable_caching: bool = Field(default=True, description="Enable caching")
    enable_audit_logging: bool = Field(default=True, description="Enable audit logging")
    enable_feedback_collection: bool = Field(default=True, description="Enable feedback collection")
    enable_langchain: bool = Field(default=True, description="Enable LangChain integrations")
    enable_embedding_cache: bool = Field(default=True, description="Enable embedding caching")
    
    @validator("environment")
    def validate_environment(cls, v):
        valid_environments = ["development", "staging", "production"]
        if v not in valid_environments:
            raise ValueError(f"Environment must be one of {valid_environments}")
        return v
    
    @validator("log_level")
    def validate_log_level(cls, v):
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of {valid_levels}")
        return v.upper()
    
    @validator("cors_origins")
    def validate_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
    
    @validator("allowed_file_types")
    def validate_file_types(cls, v):
        if isinstance(v, str):
            return [ft.strip().lower() for ft in v.split(",")]
        return [ft.lower() for ft in v]
    
    @validator("llm_provider")
    def validate_llm_provider(cls, v):
        valid_providers = ["gemini", "openai", "anthropic"]
        if v not in valid_providers:
            raise ValueError(f"LLM provider must be one of {valid_providers}")
        return v
    
    @property
    def is_production(self) -> bool:
        return self.environment == "production"
    
    @property
    def is_development(self) -> bool:
        return self.environment == "development"
    
    @property
    def database_config(self) -> dict:
        """Get database configuration for SQLAlchemy."""
        config = {
            "url": self.database_url,
            "echo": self.debug,
            "future": True,
        }
        
        if self.database_url.startswith("postgresql"):
            config.update({
                "pool_size": self.database_pool_size,
                "max_overflow": self.database_max_overflow,
                "pool_timeout": self.database_pool_timeout,
                "pool_recycle": self.database_pool_recycle,
                "pool_pre_ping": True,
            })
        elif self.database_url.startswith("sqlite"):
            config.update({
                "connect_args": {
                    "check_same_thread": False,
                    "timeout": 20,
                },
                "poolclass": "StaticPool",
            })
        
        return config
    
    @property
    def redis_config(self) -> dict:
        """Get Redis configuration."""
        if not self.redis_url:
            return {}
        
        config = {
            "url": self.redis_url,
            "db": self.redis_db,
            "max_connections": self.redis_max_connections,
            "decode_responses": True,
        }
        
        if self.redis_password:
            config["password"] = self.redis_password
        
        return config
    
    @property
    def gemini_config(self) -> dict:
        """Get Gemini configuration."""
        return {
            "model_name": self.gemini_model_name,
            "temperature": self.gemini_temperature,
            "max_output_tokens": self.gemini_max_output_tokens,
            "google_api_key": self.gemini_api_key,
            "project": self.google_cloud_project,
            "location": self.google_cloud_location,
        }
    
    @property
    def openai_config(self) -> dict:
        """Get OpenAI configuration."""
        return {
            "api_key": self.openai_api_key,
            "model": self.openai_model,
            "temperature": self.openai_temperature,
            "max_tokens": self.openai_max_tokens,
            "timeout": self.openai_timeout,
        }
    
    model_config = {
        "env_file": "configs/.env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "env_prefix": "",  # No prefix since you have specific env var names
        "extra": "ignore",  # Ignore extra fields
    }


# Global settings instance
settings = Settings()


# Development settings override
def get_dev_settings() -> Settings:
    """Get development-specific settings."""
    return Settings(
        environment="development",
        debug=True,
        log_level="DEBUG",
        database_url="sqlite:///./dev_forth_underwriting.db",
        cors_origins=["*"],
        rate_limit_enabled=False,
        cache_ttl_seconds=60,  # Shorter cache for development
        validation_cache_ttl_hours=1,  # Shorter validation cache
    )


# Test settings override
def get_test_settings() -> Settings:
    """Get test-specific settings."""
    return Settings(
        environment="test",
        debug=True,
        log_level="DEBUG",
        database_url="sqlite:///:memory:",
        cors_origins=["*"],
        rate_limit_enabled=False,
        enable_caching=False,
        metrics_enabled=False,
        validation_cache_enabled=False,
    )

