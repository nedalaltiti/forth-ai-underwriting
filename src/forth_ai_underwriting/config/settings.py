import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
import os

from forth_ai_underwriting.utils.environment import (
    get_env_var, get_env_var_bool, get_env_var_int, get_env_var_float, get_env_var_list
)

logger = logging.getLogger("forth_ai_underwriting.config")

@dataclass(frozen=True)
class DatabaseSettings:
    """PostgreSQL database configuration with AWS Secrets Manager integration."""
    name: str
    user: str
    password: str
    host: str
    port: int
    sslmode: str = "disable"
    pool_size: int = 20
    max_overflow: int = 30
    pool_timeout: int = 30
    pool_recycle: int = 3600
    
    @property
    def url(self) -> str:
        """
        Assemble a PostgreSQL SQLAlchemy URL using asyncpg.
        Example: postgresql+asyncpg://user:pass@host:5432/dbname?sslmode=disable
        """
        creds = f"{self.user}:{self.password}" if self.password else self.user
        return (
            f"postgresql+asyncpg://{creds}@{self.host}:{self.port}/{self.name}"
            f"?sslmode={self.sslmode}"
        )

    @property
    def engine_kwargs(self) -> dict:
        """SQLAlchemy engine configuration for PostgreSQL."""
        return {
            "pool_size": self.pool_size,
            "max_overflow": self.max_overflow,
            "pool_timeout": self.pool_timeout,
            "pool_recycle": self.pool_recycle,
            "pool_pre_ping": True,
            "echo_pool": False,
        }
    
    @classmethod
    def from_environment(cls) -> "DatabaseSettings":
        """Load database configuration from AWS Secrets Manager or environment variables."""
        # Check if we should use AWS Secrets Manager
        use_aws_secrets = get_env_var_bool("USE_AWS_SECRETS", False)
        environment = get_env_var("ENVIRONMENT", "development")
        
        logger.info(f"=== DATABASE CONFIGURATION ===")
        logger.info(f"ENVIRONMENT: {environment}")
        logger.info(f"USE_AWS_SECRETS: {use_aws_secrets}")
        
        if use_aws_secrets:
            try:
                from forth_ai_underwriting.utils.secret_manager import get_database_credentials, get_aws_region
                
                # Get AWS configuration
                region = get_aws_region()
                secret_name = get_env_var("AWS_DB_SECRET_NAME")
                
                if not secret_name:
                    raise ValueError("AWS_DB_SECRET_NAME is required when USE_AWS_SECRETS=true")
                
                logger.info(f"Loading database credentials from AWS Secrets Manager: {secret_name}")
                db_creds = get_database_credentials(secret_name, region)
                
                return cls(
                    name=db_creds["database"],
                    user=db_creds["username"],
                    password=db_creds["password"],
                    host=db_creds["host"],
                    port=int(db_creds["port"]),
                    sslmode=db_creds.get("sslmode", "require"),
                    pool_size=get_env_var_int("DB_POOL_SIZE", 20),
                    max_overflow=get_env_var_int("DB_MAX_OVERFLOW", 30),
                    pool_timeout=get_env_var_int("DB_POOL_TIMEOUT", 30),
                    pool_recycle=get_env_var_int("DB_POOL_RECYCLE", 3600),
                )
                
            except Exception as e:
                logger.error(f"Failed to load database credentials from AWS Secrets Manager: {e}")
                
                if environment == "production":
                    raise ValueError("Production environment requires AWS Secrets Manager for database configuration")
                
                logger.info("Falling back to environment variables for database configuration")
        
        # Fallback to environment variables (for development only)
        db_name = get_env_var("DB_NAME")
        db_user = get_env_var("DB_USER") 
        db_password = get_env_var("DB_PASSWORD")
        db_host = get_env_var("DB_HOST")
        
        # Provide development defaults if needed
        if environment == "development":
            db_name = db_name or "forth_underwriting_dev"
            db_user = db_user or "postgres"
            db_password = db_password or "postgres"
            db_host = db_host or "localhost"
        
        if not all([db_name, db_user, db_password, db_host]):
            missing = [name for name, val in [
                ("DB_NAME", db_name), ("DB_USER", db_user), 
                ("DB_PASSWORD", db_password), ("DB_HOST", db_host)
            ] if not val]
            raise ValueError(f"Missing required PostgreSQL environment variables: {missing}")
        
        return cls(
            name=db_name,
            user=db_user,
            password=db_password,
            host=db_host,
            port=get_env_var_int("DB_PORT", 5432),
            sslmode=get_env_var("DB_SSLMODE", "disable" if environment == "development" else "require"),
            pool_size=get_env_var_int("DB_POOL_SIZE", 20),
            max_overflow=get_env_var_int("DB_MAX_OVERFLOW", 30),
            pool_timeout=get_env_var_int("DB_POOL_TIMEOUT", 30),
            pool_recycle=get_env_var_int("DB_POOL_RECYCLE", 3600),
        )

@dataclass(frozen=True)
class SecuritySettings:
    """Security and authentication configuration."""
    secret_key: str
    cors_origins: List[str]
    cors_allow_credentials: bool = True
    cors_allow_methods: List[str] = field(default_factory=lambda: ["GET", "POST", "PUT", "DELETE"])
    cors_allow_headers: List[str] = field(default_factory=lambda: ["*"])
    
    @classmethod
    def from_environment(cls) -> "SecuritySettings":
        """Load security settings with production validation."""
        secret_key = get_env_var("SECRET_KEY")
        environment = get_env_var("ENVIRONMENT", "development")
        
        # Validate secret key
        if not secret_key:
            if environment == "production":
                raise ValueError("SECRET_KEY is required in production")
            secret_key = "dev_secret_key_at_least_32_characters_long_for_development_only"
        
        # Production secret key validation
        weak_secrets = [
            "your_secret_key_here", "change_me", "secret", "password",
            "your_secret_key_here_change_in_production",
            "your_secret_key_here_change_in_production_12345",
            "dev_secret_key_at_least_32_characters_long_for_development_only"
        ]
        
        if secret_key.lower() in [weak.lower() for weak in weak_secrets] and environment == "production":
            raise ValueError("Secret key appears to be a default/placeholder value in production")
        
        if len(secret_key) < 32:
            raise ValueError("Secret key must be at least 32 characters long")
        
        # CORS configuration
        cors_origins_env = get_env_var("CORS_ORIGINS")
        if cors_origins_env:
            cors_origins = [origin.strip() for origin in cors_origins_env.split(",")]
        else:
            if environment == "production":
                # Require explicit CORS origins in production
                cors_origins = []
            else:
                cors_origins = ["http://localhost:3000", "http://localhost:8000"]
        
        # Production CORS validation
        if environment == "production" and "*" in cors_origins:
            raise ValueError("CORS origins cannot include '*' in production")
        
        return cls(
            secret_key=secret_key,
            cors_origins=cors_origins,
            cors_allow_credentials=get_env_var_bool("CORS_ALLOW_CREDENTIALS", True),
            cors_allow_methods=get_env_var_list("CORS_ALLOW_METHODS", cls.cors_allow_methods),
            cors_allow_headers=get_env_var_list("CORS_ALLOW_HEADERS", cls.cors_allow_headers),
        )

@dataclass(frozen=True)
class GeminiSettings:
    """Google Gemini AI configuration."""
    api_key: str
    model_name: str = "gemini-pro"
    temperature: float = 0.7
    max_output_tokens: int = 1024
    use_aws_secrets: bool = False
    credentials_path: Optional[str] = None
    
    @classmethod
    def from_environment(cls) -> "GeminiSettings":
        """Load Gemini settings from environment or AWS Secrets Manager."""
        use_aws_secrets = get_env_var_bool("USE_AWS_SECRETS", False)
        secret_name = get_env_var("AWS_GEMINI_SECRET_NAME")
        
        credentials_path: Optional[str] = None
        api_key: Optional[str] = None
        
        if use_aws_secrets and secret_name:
            try:
                from forth_ai_underwriting.utils.secret_manager import load_gemini_credentials, get_aws_region
                
                region = get_aws_region()
                logger.info(f"Loading Gemini credentials from AWS Secrets Manager: {secret_name}")
                credentials_path = load_gemini_credentials(secret_name, region)
                
                return cls(
                    api_key="",  # Not needed when using service account
                    model_name=get_env_var("GEMINI_MODEL_NAME", "gemini-2.0-flash-001"),
                    temperature=get_env_var_float("GEMINI_TEMPERATURE", 0.0),
                    max_output_tokens=get_env_var_int("GEMINI_MAX_OUTPUT_TOKENS", 1024),
                    use_aws_secrets=True,
                    credentials_path=credentials_path,
                )
                
            except Exception as e:
                logger.error(f"Failed to load Gemini credentials from AWS Secrets Manager: {e}")
                logger.info("Falling back to environment variables for Gemini configuration")
        
        # Use environment variables
        api_key = get_env_var("GEMINI_API_KEY", "")
        
        return cls(
            api_key=api_key,
            model_name=get_env_var("GEMINI_MODEL_NAME", "gemini-2.0-flash-001"),
            temperature=get_env_var_float("GEMINI_TEMPERATURE", 0.0),
            max_output_tokens=get_env_var_int("GEMINI_MAX_OUTPUT_TOKENS", 1024),
            use_aws_secrets=False,
            credentials_path=None,
        )

@dataclass(frozen=True)
class ForthAPISettings:
    """Forth API integration settings."""
    base_url: str
    api_key: str
    timeout: int = 30
    webhook_endpoint: str = "/webhook/forth"
    webhook_secret: Optional[str] = None
    
    @classmethod
    def from_environment(cls) -> "ForthAPISettings":
        """Load Forth API settings from environment."""
        return cls(
            base_url=get_env_var("FORTH_API_BASE_URL", ""),
            api_key=get_env_var("FORTH_API_KEY", ""),
            timeout=get_env_var_int("FORTH_API_TIMEOUT", 30),
            webhook_endpoint=get_env_var("WEBHOOK_ENDPOINT", "/webhook/forth"),
            webhook_secret=get_env_var("FORTH_WEBHOOK_SECRET", None),
        )

@dataclass(frozen=True)
class LLMSettings:
    """LLM service configuration."""
    provider: str = "gemini"
    fallback_provider: Optional[str] = None
    openai_api_key: Optional[str] = None
    
    @classmethod
    def from_environment(cls) -> "LLMSettings":
        """Load LLM settings from environment."""
        return cls(
            provider=get_env_var("LLM_PROVIDER", "gemini"),
            fallback_provider=get_env_var("LLM_FALLBACK_PROVIDER", None),
            openai_api_key=get_env_var("OPENAI_API_KEY", None),
        )

@dataclass(frozen=True)
class DocumentProcessingSettings:
    """Document processing configuration."""
    max_file_size_mb: int = 50
    max_chunk_size: int = 1000
    enable_ai_parsing: bool = True
    processing_timeout: int = 300
    
    @classmethod
    def from_environment(cls) -> "DocumentProcessingSettings":
        """Load document processing settings from environment."""
        return cls(
            max_file_size_mb=get_env_var_int("MAX_FILE_SIZE_MB", 50),
            max_chunk_size=get_env_var_int("MAX_CHUNK_SIZE", 1000),
            enable_ai_parsing=get_env_var_bool("ENABLE_AI_PARSING", True),
            processing_timeout=get_env_var_int("DOCUMENT_PROCESSING_TIMEOUT", 300),
        )

@dataclass(frozen=True)
class AWSSettings:
    """AWS-specific configuration settings."""
    use_secrets_manager: bool = False
    region: str = "us-west-1"
    db_secret_name: Optional[str] = None
    gemini_secret_name: Optional[str] = None
    
    @classmethod
    def from_environment(cls) -> "AWSSettings":
        """Load AWS settings from environment."""
        return cls(
            use_secrets_manager=get_env_var_bool("USE_AWS_SECRETS", False),
            region=get_env_var("AWS_REGION", get_env_var("AWS_DEFAULT_REGION", "us-west-1")),
            db_secret_name=get_env_var("AWS_DB_SECRET_NAME", None),
            gemini_secret_name=get_env_var("AWS_GEMINI_SECRET_NAME", None),
        )

@dataclass(frozen=True)
class CacheSettings:
    """Cache and performance settings."""
    enable_caching: bool = True
    redis_url: Optional[str] = None
    cache_ttl: int = 3600
    
    @classmethod
    def from_environment(cls) -> "CacheSettings":
        """Load cache settings from environment."""
        return cls(
            enable_caching=get_env_var_bool("ENABLE_CACHING", True),
            redis_url=get_env_var("REDIS_URL", None),
            cache_ttl=get_env_var_int("CACHE_TTL", 3600),
        )

@dataclass(frozen=True)
class FeatureFlags:
    """Feature toggle configuration."""
    enable_audit_logging: bool = True
    metrics_enabled: bool = True
    rate_limit_enabled: bool = True
    
    @classmethod
    def from_environment(cls) -> "FeatureFlags":
        """Load feature flags from environment."""
        return cls(
            enable_audit_logging=get_env_var_bool("ENABLE_AUDIT_LOGGING", True),
            metrics_enabled=get_env_var_bool("METRICS_ENABLED", True),
            rate_limit_enabled=get_env_var_bool("RATE_LIMIT_ENABLED", True),
        )

@dataclass(frozen=True)
class AppSettings:
    """Main application settings aggregator."""
    # Application info
    app_name: str = "Forth AI Underwriting"
    app_version: str = "1.0.0"
    environment: str = "development"
    debug: bool = False
    
    # Server config
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"
    
    # Component settings
    database: DatabaseSettings = field(default_factory=DatabaseSettings.from_environment)
    security: SecuritySettings = field(default_factory=SecuritySettings.from_environment)
    gemini: GeminiSettings = field(default_factory=GeminiSettings.from_environment)
    forth_api: ForthAPISettings = field(default_factory=ForthAPISettings.from_environment)
    llm: LLMSettings = field(default_factory=LLMSettings.from_environment)
    document_processing: DocumentProcessingSettings = field(default_factory=DocumentProcessingSettings.from_environment)
    aws: AWSSettings = field(default_factory=AWSSettings.from_environment)
    cache: CacheSettings = field(default_factory=CacheSettings.from_environment)
    features: FeatureFlags = field(default_factory=FeatureFlags.from_environment)
    
    @classmethod
    def from_environment(cls) -> "AppSettings":
        """Load all settings from environment."""
        environment = get_env_var("ENVIRONMENT", "development")
        debug = get_env_var_bool("DEBUG", environment == "development")
        
        return cls(
            app_name=get_env_var("APP_NAME", "Forth AI Underwriting"),
            app_version=get_env_var("APP_VERSION", "1.0.0"),
            environment=environment,
            debug=debug,
            app_host=get_env_var("APP_HOST", "0.0.0.0"),
            app_port=get_env_var_int("APP_PORT", 8000),
            log_level=get_env_var("LOG_LEVEL", "DEBUG" if debug else "INFO"),
        )
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"
    
    def validate_configuration(self) -> dict:
        """Validate configuration for production readiness."""
        environment = self.environment
        errors = []
        warnings = []
        
        # Production-critical checks
        if environment == "production":
            # Security checks
            if len(self.security.secret_key) < 64:
                errors.append("Secret key must be at least 64 characters in production")
            
            if "*" in self.security.cors_origins:
                errors.append("CORS origins cannot include '*' in production")
            
            if self.debug:
                errors.append("Debug mode must be disabled in production")
            
            # AWS checks
            if not self.aws.use_secrets_manager:
                warnings.append("AWS Secrets Manager is recommended for production")
            
            # API checks
            if not self.forth_api.base_url:
                errors.append("FORTH_API_BASE_URL is required")
            
            if not self.forth_api.api_key:
                errors.append("FORTH_API_KEY is required")
            
            if not self.gemini.api_key and not self.gemini.use_aws_secrets:
                errors.append("Gemini API key is required")
        
        # General checks
        if not self.database.url.startswith("postgresql"):
            errors.append("Only PostgreSQL is supported")
        
        # Calculate security score
        security_checks = {
            "strong_secret": len(self.security.secret_key) >= 64,
            "aws_secrets": self.aws.use_secrets_manager,
            "secure_cors": "*" not in self.security.cors_origins,
            "debug_off": not self.debug,
            "postgresql": self.database.url.startswith("postgresql"),
        }
        
        security_score = sum(1 for check in security_checks.values() if check) * 20
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "security_score": security_score,
            "security_checks": security_checks,
            "environment": environment,
        }
    
    def cleanup(self):
        """Clean up temporary resources like credential files."""
        if self.gemini.use_aws_secrets and self.gemini.credentials_path:
            try:
                from forth_ai_underwriting.utils.secret_manager import cleanup_temp_credentials
                cleanup_temp_credentials(self.gemini.credentials_path)
                logger.info("Cleaned up temporary Gemini credentials")
            except Exception as e:
                logger.error(f"Failed to cleanup temporary credentials: {e}")

# Create global settings instance
try:
    settings = AppSettings.from_environment()
    logger.info(f"✅ Configuration loaded successfully for environment: {settings.environment}")
    logger.info(f"✅ Database: PostgreSQL at {settings.database.host}:{settings.database.port}")
    
    # Auto-cleanup on module unload
    import atexit
    atexit.register(settings.cleanup)
    
except Exception as exc:
    logger.critical("❌ Failed to load configuration – exiting", exc_info=exc)
    raise

__all__ = ["settings", "AppSettings"]

