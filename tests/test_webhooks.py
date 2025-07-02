from unittest.mock import patch

import pytest
from forth_ai_underwriting.webhooks.api import create_standalone_app
from forth_ai_underwriting.webhooks.config import WebhookConfig


class TestWebhookConfig:
    """Test webhook configuration."""

    def test_defaults(self) -> None:
        """Test default configuration values."""
        config = WebhookConfig()
        assert config.host == "0.0.0.0"
        assert config.port == 8000
        assert config.queue_name == "uw-contracts-parser-dev-sqs"
        assert config.aws_region == "us-west-1"

    def test_environment_override(self) -> None:
        """Test configuration can be overridden by environment variables."""
        with patch.dict(
            "os.environ", {"WEBHOOK_PORT": "9000", "WEBHOOK_HOST": "localhost"}
        ):
            config = WebhookConfig()
            assert config.port == 9000
            assert config.host == "localhost"


class TestWebhookAPI:
    """Test webhook API endpoints."""

    @pytest.fixture
    def app(self):
        """Create FastAPI app for testing."""
        return create_standalone_app()

    def test_create_app(self, app) -> None:
        """Test that the app is created successfully."""
        assert app is not None
        assert hasattr(app, "routes")

    def test_health_endpoint_exists(self, app) -> None:
        """Test that health endpoint is registered."""
        routes = [route.path for route in app.routes]
        assert "/health" in routes
