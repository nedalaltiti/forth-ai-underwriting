from typing import Any
from unittest.mock import Mock, AsyncMock, patch

import pytest
from forth_ai_underwriting.webhooks.config import WebhookConfig
from forth_ai_underwriting.webhooks.api import create_webhook_app
from forth_ai_underwriting.webhooks.services import WebhookService


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
        with patch.dict("os.environ", {"WEBHOOK_PORT": "9000", "WEBHOOK_HOST": "localhost"}):
            config = WebhookConfig()
            assert config.port == 9000
            assert config.host == "localhost"


class TestWebhookService:
    """Test webhook service functionality."""

    @pytest.fixture
    def webhook_service(self) -> WebhookService:
        """Create webhook service with mocked dependencies."""
        with patch("forth_ai_underwriting.webhooks.services.get_queue_service") as mock_queue_service:
            mock_queue = AsyncMock()
            mock_queue_service.return_value = mock_queue
            service = WebhookService()
            service.queue_service = mock_queue
            return service

    @pytest.mark.asyncio
    async def test_process_webhook_success(self, webhook_service: WebhookService) -> None:
        """Test successful webhook processing."""
        webhook_data = {
            "document_id": "test_doc_123",
            "document_url": "https://example.com/document.pdf",
            "event_type": "document_uploaded"
        }

        # Mock successful queue operation
        webhook_service.queue_service.send_message.return_value = {"MessageId": "msg_123"}

        result = await webhook_service.process_webhook(webhook_data)

        assert result["status"] == "success"
        assert result["message_id"] == "msg_123"
        webhook_service.queue_service.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_webhook_queue_failure(self, webhook_service: WebhookService) -> None:
        """Test webhook processing with queue failure."""
        webhook_data = {
            "document_id": "test_doc_123",
            "document_url": "https://example.com/document.pdf"
        }

        # Mock queue failure
        webhook_service.queue_service.send_message.side_effect = Exception("Queue unavailable")

        result = await webhook_service.process_webhook(webhook_data)

        assert result["status"] == "error"
        assert "Queue unavailable" in result["error"]


class TestWebhookAPI:
    """Test webhook API endpoints."""

    @pytest.fixture
    def app(self):
        """Create FastAPI app for testing."""
        return create_webhook_app()

    def test_create_app(self, app) -> None:
        """Test that the app is created successfully."""
        assert app is not None
        assert hasattr(app, "routes")

    def test_health_endpoint_exists(self, app) -> None:
        """Test that health endpoint is registered."""
        routes = [route.path for route in app.routes]
        assert "/health" in routes 