from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from forth_ai_underwriting.infrastructure.ai_parser import AIParserService


@pytest.fixture
def ai_parser_service() -> AIParserService:
    """Create AI parser service with mocked dependencies."""
    with patch(
        "forth_ai_underwriting.infrastructure.ai_parser.get_document_processor"
    ) as mock_doc_processor, patch(
        "forth_ai_underwriting.infrastructure.ai_parser.get_gemini_service"
    ) as mock_gemini_service:
        # Mock document processor
        mock_processor = AsyncMock()
        mock_doc_processor.return_value = mock_processor

        # Mock gemini service
        mock_gemini = AsyncMock()
        mock_gemini_service.return_value = mock_gemini

        service = AIParserService()
        service.document_processor = mock_processor
        service.gemini_service = mock_gemini

        return service


@pytest.mark.asyncio
async def test_parse_contract_success(ai_parser_service: AIParserService) -> None:
    """Test successful contract parsing."""
    document_url = "http://example.com/contract.pdf"

    # Mock processing result
    mock_result = AsyncMock()
    mock_result.validation_ready = True
    mock_result.contract_data = {
        "sender_ip": "192.168.1.1",
        "signer_ip": "192.168.1.2",
        "mailing_address": {"street": "123 Main St", "city": "Anytown"},
    }

    ai_parser_service.document_processor.process_document.return_value = mock_result

    parsed_data = await ai_parser_service.parse_contract(document_url)

    # Verify that document processor was called
    ai_parser_service.document_processor.process_document.assert_called_once_with(
        document_url=document_url, skip_ai_parsing=False
    )

    # Verify that data contains expected fields
    assert "sender_ip" in parsed_data
    assert "signer_ip" in parsed_data
    assert "mailing_address" in parsed_data


@pytest.mark.asyncio
async def test_parse_contract_processor_failure_fallback(
    ai_parser_service: AIParserService,
) -> None:
    """Test fallback when document processor fails."""
    document_url = "http://example.com/contract.pdf"

    # Mock processing result with failure but some extracted text
    mock_result = AsyncMock()
    mock_result.validation_ready = False
    mock_result.contract_data = None
    mock_result.extracted_text = "Sample contract text"
    mock_result.processing_errors = ["OCR failed"]

    ai_parser_service.document_processor.process_document.return_value = mock_result

    # Mock Gemini service fallback
    mock_contract_data = {"sender_ip": "fallback_ip", "signer_ip": "fallback_signer_ip"}
    ai_parser_service.gemini_service.parse_contract_document.return_value = (
        mock_contract_data
    )

    parsed_data = await ai_parser_service.parse_contract(document_url)

    # Verify fallback was called
    ai_parser_service.gemini_service.parse_contract_document.assert_called_once_with(
        document_text="Sample contract text", document_url=document_url
    )

    # Verify that fallback data is present
    assert "sender_ip" in parsed_data
    assert "signer_ip" in parsed_data


@pytest.mark.asyncio
async def test_parse_contract_complete_failure_returns_fallback(
    ai_parser_service: AIParserService,
) -> None:
    """Test that complete parsing failure returns fallback structure."""
    document_url = "http://example.com/contract.pdf"

    # Mock processing result with complete failure
    mock_result = AsyncMock()
    mock_result.validation_ready = False
    mock_result.contract_data = None
    mock_result.extracted_text = None
    mock_result.processing_errors = ["Complete failure"]

    ai_parser_service.document_processor.process_document.return_value = mock_result

    parsed_data = await ai_parser_service.parse_contract(document_url)

    # Verify that fallback structure is returned
    assert parsed_data["_parsing_status"] == "failed"
    assert "_error" in parsed_data
    assert "sender_ip" in parsed_data
    assert "mailing_address" in parsed_data


@pytest.mark.asyncio
async def test_health_check_success(ai_parser_service: AIParserService) -> None:
    """Test health check when all services are healthy."""
    # Mock healthy responses
    ai_parser_service.document_processor.health_check.return_value = {
        "status": "healthy"
    }
    ai_parser_service.gemini_service.health_check.return_value = {"status": "healthy"}

    health = await ai_parser_service.health_check()

    assert health["status"] == "healthy"
    assert health["pipeline_ready"] is True
    assert "document_processor" in health
    assert "gemini_service" in health 