"""
Feature Flags System for Forth AI Underwriting
Supports external providers (Unleash, Flagsmith) and local configuration.
"""

import asyncio
import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

try:
    import httpx

    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False


class FeatureFlagProvider(str, Enum):
    """Supported feature flag providers."""

    LOCAL = "local"
    UNLEASH = "unleash"
    FLAGSMITH = "flagsmith"
    LAUNCHDARKLY = "launchdarkly"
    ENVIRONMENT = "environment"


class FeatureFlagType(str, Enum):
    """Types of feature flags."""

    BOOLEAN = "boolean"
    STRING = "string"
    NUMBER = "number"
    JSON = "json"
    PERCENTAGE = "percentage"


class FeatureFlagContext(BaseModel):
    """Context for feature flag evaluation."""

    model_config = ConfigDict(extra="allow")

    user_id: str | None = None
    contact_id: str | None = None
    environment: str = Field(default="development")
    version: str | None = None
    session_id: str | None = None
    custom_properties: dict[str, Any] = Field(default_factory=dict)


@dataclass
class FeatureFlag:
    """Feature flag definition with metadata."""

    name: str
    description: str
    flag_type: FeatureFlagType
    default_value: Any
    enabled: bool = True
    environments: list[str] = field(
        default_factory=lambda: ["development", "staging", "production"]
    )
    rollout_percentage: float = 100.0  # 0-100
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    tags: list[str] = field(default_factory=list)

    def is_enabled_for_environment(self, environment: str) -> bool:
        """Check if flag is enabled for specific environment."""
        return self.enabled and environment in self.environments


class FeatureFlagProvider(ABC):
    """Abstract base class for feature flag providers."""

    @abstractmethod
    async def get_flag(self, flag_name: str, context: FeatureFlagContext) -> Any:
        """Get feature flag value."""
        pass

    @abstractmethod
    async def is_enabled(self, flag_name: str, context: FeatureFlagContext) -> bool:
        """Check if feature flag is enabled."""
        pass

    @abstractmethod
    async def get_all_flags(self, context: FeatureFlagContext) -> dict[str, Any]:
        """Get all feature flags."""
        pass

    @abstractmethod
    async def health_check(self) -> dict[str, Any]:
        """Check provider health."""
        pass


class LocalFeatureFlagProvider(FeatureFlagProvider):
    """Local file-based feature flag provider for development and testing."""

    def __init__(self, config_file: str = "feature_flags.json"):
        self.config_file = config_file
        self.flags: dict[str, FeatureFlag] = {}
        self._last_reload = datetime.utcnow()
        self._reload_interval = timedelta(minutes=5)
        self._load_flags()

    def _load_flags(self):
        """Load feature flags from configuration file."""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file) as f:
                    config = json.load(f)

                for flag_name, flag_data in config.get("flags", {}).items():
                    self.flags[flag_name] = FeatureFlag(
                        name=flag_name,
                        description=flag_data.get("description", ""),
                        flag_type=FeatureFlagType(flag_data.get("type", "boolean")),
                        default_value=flag_data.get("default_value", False),
                        enabled=flag_data.get("enabled", True),
                        environments=flag_data.get(
                            "environments", ["development", "staging", "production"]
                        ),
                        rollout_percentage=flag_data.get("rollout_percentage", 100.0),
                        tags=flag_data.get("tags", []),
                    )

                logger.info(
                    f"✅ Loaded {len(self.flags)} feature flags from {self.config_file}"
                )
            else:
                logger.warning(f"⚠️ Feature flags file not found: {self.config_file}")
                self._create_default_config()

        except Exception as e:
            logger.error(f"❌ Failed to load feature flags: {e}")
            self._create_default_flags()

    def _create_default_config(self):
        """Create default feature flags configuration."""
        default_config = {
            "flags": {
                "ai_parsing_enabled": {
                    "description": "Enable AI-powered document parsing",
                    "type": "boolean",
                    "default_value": True,
                    "enabled": True,
                    "environments": ["development", "staging", "production"],
                    "rollout_percentage": 100.0,
                    "tags": ["ai", "parsing", "core"],
                },
                "experimental_gemini_parser": {
                    "description": "Use experimental Gemini parser for contracts",
                    "type": "boolean",
                    "default_value": False,
                    "enabled": True,
                    "environments": ["development", "staging"],
                    "rollout_percentage": 25.0,
                    "tags": ["experimental", "gemini", "parser"],
                },
                "enhanced_validation": {
                    "description": "Enable enhanced validation checks",
                    "type": "boolean",
                    "default_value": False,
                    "enabled": True,
                    "environments": ["development", "staging", "production"],
                    "rollout_percentage": 50.0,
                    "tags": ["validation", "enhancement"],
                },
                "retry_max_attempts": {
                    "description": "Maximum retry attempts for failed operations",
                    "type": "number",
                    "default_value": 3,
                    "enabled": True,
                    "environments": ["development", "staging", "production"],
                    "rollout_percentage": 100.0,
                    "tags": ["retry", "reliability"],
                },
                "llm_provider": {
                    "description": "Primary LLM provider to use",
                    "type": "string",
                    "default_value": "gemini",
                    "enabled": True,
                    "environments": ["development", "staging", "production"],
                    "rollout_percentage": 100.0,
                    "tags": ["llm", "provider"],
                },
            }
        }

        try:
            with open(self.config_file, "w") as f:
                json.dump(default_config, f, indent=2)
            logger.info(f"✅ Created default feature flags config: {self.config_file}")
            self._load_flags()
        except Exception as e:
            logger.error(f"❌ Failed to create default config: {e}")

    def _create_default_flags(self):
        """Create default feature flags in memory."""
        self.flags = {
            "ai_parsing_enabled": FeatureFlag(
                name="ai_parsing_enabled",
                description="Enable AI-powered document parsing",
                flag_type=FeatureFlagType.BOOLEAN,
                default_value=True,
                tags=["ai", "parsing", "core"],
            ),
            "experimental_gemini_parser": FeatureFlag(
                name="experimental_gemini_parser",
                description="Use experimental Gemini parser for contracts",
                flag_type=FeatureFlagType.BOOLEAN,
                default_value=False,
                rollout_percentage=25.0,
                tags=["experimental", "gemini", "parser"],
            ),
        }

    def _should_reload(self) -> bool:
        """Check if flags should be reloaded."""
        return datetime.utcnow() - self._last_reload > self._reload_interval

    async def get_flag(self, flag_name: str, context: FeatureFlagContext) -> Any:
        """Get feature flag value with context evaluation."""
        if self._should_reload():
            self._load_flags()
            self._last_reload = datetime.utcnow()

        flag = self.flags.get(flag_name)
        if not flag:
            logger.warning(f"⚠️ Feature flag not found: {flag_name}")
            return None

        # Check environment
        if not flag.is_enabled_for_environment(context.environment):
            return flag.default_value

        # Check rollout percentage
        if flag.rollout_percentage < 100.0:
            # Simple hash-based rollout
            import hashlib

            hash_input = (
                f"{flag_name}:{context.user_id or context.contact_id or 'anonymous'}"
            )
            hash_value = int(hashlib.md5(hash_input.encode()).hexdigest()[:8], 16)
            percentage = (hash_value % 100) + 1

            if percentage > flag.rollout_percentage:
                return flag.default_value

        return flag.default_value

    async def is_enabled(self, flag_name: str, context: FeatureFlagContext) -> bool:
        """Check if feature flag is enabled."""
        value = await self.get_flag(flag_name, context)
        if isinstance(value, bool):
            return value
        return bool(value)

    async def get_all_flags(self, context: FeatureFlagContext) -> dict[str, Any]:
        """Get all feature flags for context."""
        result = {}
        for flag_name in self.flags.keys():
            result[flag_name] = await self.get_flag(flag_name, context)
        return result

    async def health_check(self) -> dict[str, Any]:
        """Check provider health."""
        return {
            "provider": "local",
            "healthy": True,
            "flags_count": len(self.flags),
            "config_file": self.config_file,
            "last_reload": self._last_reload.isoformat(),
        }


class UnleashFeatureFlagProvider(FeatureFlagProvider):
    """Unleash feature flag provider for production environments."""

    def __init__(
        self, api_url: str, api_token: str, app_name: str = "forth-ai-underwriting"
    ):
        if not HAS_HTTPX:
            raise ImportError("httpx is required for Unleash provider")

        self.api_url = api_url.rstrip("/")
        self.api_token = api_token
        self.app_name = app_name
        self.client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json",
            },
            timeout=10.0,
        )
        self._cache: dict[str, Any] = {}
        self._cache_ttl = timedelta(minutes=5)
        self._last_cache_update = datetime.utcnow()

    async def _refresh_cache(self):
        """Refresh feature flags cache from Unleash."""
        try:
            response = await self.client.get(f"{self.api_url}/api/client/features")
            response.raise_for_status()

            data = response.json()
            self._cache = {
                feature["name"]: feature for feature in data.get("features", [])
            }
            self._last_cache_update = datetime.utcnow()

            logger.info(f"✅ Refreshed Unleash cache: {len(self._cache)} flags")

        except Exception as e:
            logger.error(f"❌ Failed to refresh Unleash cache: {e}")

    async def _ensure_cache_fresh(self):
        """Ensure cache is fresh."""
        if datetime.utcnow() - self._last_cache_update > self._cache_ttl:
            await self._refresh_cache()

    async def get_flag(self, flag_name: str, context: FeatureFlagContext) -> Any:
        """Get feature flag value from Unleash."""
        await self._ensure_cache_fresh()

        feature = self._cache.get(flag_name)
        if not feature:
            logger.warning(f"⚠️ Unleash feature flag not found: {flag_name}")
            return None

        # Evaluate feature flag based on Unleash strategies
        if not feature.get("enabled", False):
            return False

        # Simple evaluation - in production, use Unleash SDK for full strategy support
        return True

    async def is_enabled(self, flag_name: str, context: FeatureFlagContext) -> bool:
        """Check if feature flag is enabled in Unleash."""
        value = await self.get_flag(flag_name, context)
        return bool(value)

    async def get_all_flags(self, context: FeatureFlagContext) -> dict[str, Any]:
        """Get all feature flags from Unleash."""
        await self._ensure_cache_fresh()
        result = {}

        for flag_name in self._cache.keys():
            result[flag_name] = await self.get_flag(flag_name, context)

        return result

    async def health_check(self) -> dict[str, Any]:
        """Check Unleash provider health."""
        try:
            response = await self.client.get(f"{self.api_url}/health")
            response.raise_for_status()

            return {
                "provider": "unleash",
                "healthy": True,
                "api_url": self.api_url,
                "flags_count": len(self._cache),
                "last_cache_update": self._last_cache_update.isoformat(),
            }

        except Exception as e:
            return {"provider": "unleash", "healthy": False, "error": str(e)}


class EnvironmentFeatureFlagProvider(FeatureFlagProvider):
    """Environment variable-based feature flag provider."""

    def __init__(self, prefix: str = "FEATURE_FLAG_"):
        self.prefix = prefix

    async def get_flag(self, flag_name: str, context: FeatureFlagContext) -> Any:
        """Get feature flag value from environment variables."""
        env_var = f"{self.prefix}{flag_name.upper()}"
        value = os.getenv(env_var)

        if value is None:
            return None

        # Try to parse as JSON first, then boolean, then number, then string
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            if value.lower() in ("true", "false"):
                return value.lower() == "true"
            try:
                return int(value)
            except ValueError:
                try:
                    return float(value)
                except ValueError:
                    return value

    async def is_enabled(self, flag_name: str, context: FeatureFlagContext) -> bool:
        """Check if feature flag is enabled."""
        value = await self.get_flag(flag_name, context)
        return bool(value)

    async def get_all_flags(self, context: FeatureFlagContext) -> dict[str, Any]:
        """Get all feature flags from environment."""
        result = {}

        for key, _value in os.environ.items():
            if key.startswith(self.prefix):
                flag_name = key[len(self.prefix) :].lower()
                result[flag_name] = await self.get_flag(flag_name, context)

        return result

    async def health_check(self) -> dict[str, Any]:
        """Check environment provider health."""
        flags_count = sum(1 for key in os.environ.keys() if key.startswith(self.prefix))

        return {
            "provider": "environment",
            "healthy": True,
            "prefix": self.prefix,
            "flags_count": flags_count,
        }


class FeatureFlagManager:
    """
    Central feature flag manager with multiple provider support.
    Implements fallback strategy and caching for reliability.
    """

    def __init__(
        self,
        primary_provider: FeatureFlagProvider,
        fallback_provider: FeatureFlagProvider | None = None,
    ):
        self.primary_provider = primary_provider
        self.fallback_provider = fallback_provider or LocalFeatureFlagProvider()
        self._cache: dict[str, Any] = {}
        self._cache_ttl = timedelta(minutes=1)
        self._last_cache_update: dict[str, datetime] = {}

    async def is_enabled(
        self, flag_name: str, context: FeatureFlagContext | None = None
    ) -> bool:
        """Check if feature flag is enabled with fallback support."""
        if context is None:
            context = FeatureFlagContext()

        try:
            # Try primary provider first
            result = await self.primary_provider.is_enabled(flag_name, context)
            self._update_cache(flag_name, result)
            return result

        except Exception as e:
            logger.warning(f"⚠️ Primary provider failed for {flag_name}: {e}")

            # Try fallback provider
            try:
                result = await self.fallback_provider.is_enabled(flag_name, context)
                logger.info(f"✅ Fallback provider used for {flag_name}: {result}")
                return result

            except Exception as fallback_error:
                logger.error(
                    f"❌ Fallback provider failed for {flag_name}: {fallback_error}"
                )

                # Use cached value if available
                cached_value = self._get_cached_value(flag_name)
                if cached_value is not None:
                    logger.info(f"📦 Using cached value for {flag_name}: {cached_value}")
                    return cached_value

                # Final fallback - return False for safety
                logger.warning(
                    f"⚠️ All providers failed for {flag_name}, returning False"
                )
                return False

    async def get_flag(
        self, flag_name: str, context: FeatureFlagContext | None = None
    ) -> Any:
        """Get feature flag value with fallback support."""
        if context is None:
            context = FeatureFlagContext()

        try:
            result = await self.primary_provider.get_flag(flag_name, context)
            self._update_cache(flag_name, result)
            return result

        except Exception as e:
            logger.warning(f"⚠️ Primary provider failed for {flag_name}: {e}")

            try:
                result = await self.fallback_provider.get_flag(flag_name, context)
                return result

            except Exception:
                cached_value = self._get_cached_value(flag_name)
                return cached_value

    def _update_cache(self, flag_name: str, value: Any):
        """Update cache with new value."""
        self._cache[flag_name] = value
        self._last_cache_update[flag_name] = datetime.utcnow()

    def _get_cached_value(self, flag_name: str) -> Any:
        """Get cached value if still valid."""
        if flag_name not in self._cache:
            return None

        last_update = self._last_cache_update.get(flag_name)
        if last_update and datetime.utcnow() - last_update < self._cache_ttl:
            return self._cache[flag_name]

        return None

    async def get_all_flags(
        self, context: FeatureFlagContext | None = None
    ) -> dict[str, Any]:
        """Get all feature flags."""
        if context is None:
            context = FeatureFlagContext()

        try:
            return await self.primary_provider.get_all_flags(context)
        except Exception:
            return await self.fallback_provider.get_all_flags(context)

    async def health_check(self) -> dict[str, Any]:
        """Check health of all providers."""
        primary_health = await self.primary_provider.health_check()
        fallback_health = await self.fallback_provider.health_check()

        return {
            "primary_provider": primary_health,
            "fallback_provider": fallback_health,
            "cache_size": len(self._cache),
        }


# Global feature flag manager instance
_feature_flag_manager: FeatureFlagManager | None = None


def get_feature_flag_manager() -> FeatureFlagManager:
    """Get global feature flag manager instance."""
    global _feature_flag_manager

    if _feature_flag_manager is None:
        # Initialize based on environment configuration
        provider_type = os.getenv("FEATURE_FLAG_PROVIDER", "local")

        if provider_type == "unleash":
            api_url = os.getenv("UNLEASH_API_URL")
            api_token = os.getenv("UNLEASH_API_TOKEN")

            if api_url and api_token:
                primary_provider = UnleashFeatureFlagProvider(api_url, api_token)
            else:
                logger.warning(
                    "⚠️ Unleash configuration missing, falling back to local provider"
                )
                primary_provider = LocalFeatureFlagProvider()
        elif provider_type == "environment":
            primary_provider = EnvironmentFeatureFlagProvider()
        else:
            primary_provider = LocalFeatureFlagProvider()

        fallback_provider = LocalFeatureFlagProvider()
        _feature_flag_manager = FeatureFlagManager(primary_provider, fallback_provider)

        logger.info(f"✅ Feature flag manager initialized with {provider_type} provider")

    return _feature_flag_manager


# Convenience functions
async def is_feature_enabled(
    flag_name: str, context: FeatureFlagContext | None = None
) -> bool:
    """Check if feature flag is enabled."""
    manager = get_feature_flag_manager()
    return await manager.is_enabled(flag_name, context)


async def get_feature_flag(
    flag_name: str, context: FeatureFlagContext | None = None
) -> Any:
    """Get feature flag value."""
    manager = get_feature_flag_manager()
    return await manager.get_flag(flag_name, context)


# Decorator for feature flag gating
def feature_flag(flag_name: str, fallback_result: Any = None):
    """Decorator to gate function execution behind feature flag."""

    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            context = FeatureFlagContext()

            # Extract context from kwargs if provided
            if "feature_context" in kwargs:
                context = kwargs.pop("feature_context")

            if await is_feature_enabled(flag_name, context):
                return await func(*args, **kwargs)
            else:
                logger.info(f"🚫 Feature {flag_name} disabled, returning fallback")
                return fallback_result

        def sync_wrapper(*args, **kwargs):
            # For sync functions, we need to handle async feature flag check
            import asyncio

            async def check_and_run():
                context = FeatureFlagContext()
                if "feature_context" in kwargs:
                    context = kwargs.pop("feature_context")

                if await is_feature_enabled(flag_name, context):
                    return func(*args, **kwargs)
                else:
                    logger.info(f"🚫 Feature {flag_name} disabled, returning fallback")
                    return fallback_result

            return asyncio.run(check_and_run())

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator
