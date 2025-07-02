from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from forth_ai_underwriting.services.gemini_service import GeminiProvider


@pytest.fixture
def gemini_provider() -> GeminiProvider:
    """Create a mock Gemini provider for testing."""
    with patch("forth_ai_underwriting.services.gemini_service.genai") as mock_genai:
        provider = GeminiProvider()
        provider.model = AsyncMock()
        return provider


@pytest.mark.asyncio
async def test_health_check_success(gemini_provider: GeminiProvider) -> None:
    """Test successful health check."""
    # Mock a successful generation
    mock_response = AsyncMock()
    mock_response.text = "test response"
    gemini_provider.model.generate_content_async.return_value = mock_response

    result = await gemini_provider.health_check()

    assert result["status"] == "healthy"
    assert result["model_available"] is True
    assert "response_time_ms" in result


@pytest.mark.asyncio  
async def test_health_check_exception_handling(gemini_provider: GeminiProvider) -> None:
    """Test health check with exception handling."""
    # Mock an exception during generation
    gemini_provider.model.generate_content_async.side_effect = Exception("API Error")

    result = await gemini_provider.health_check()

    # Check the nested structure for initialization status
    assert result["checks"]["initialization"]["status"] == "unhealthy"
    assert "error" in result["checks"]["initialization"] 