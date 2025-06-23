import pytest
from unittest.mock import AsyncMock, patch
from forth_ai_underwriting.infrastructure.ai_parser import AIParserService

@pytest.fixture
def ai_parser_service():
    with patch("forth_ai_underwriting.infrastructure.ai_parser.httpx.AsyncClient") as MockAsyncClient:
        mock_client = MockAsyncClient.return_value
        mock_client.get.return_value = AsyncMock(status_code=200, json=lambda: {})
        service = AIParserService()
        service.openai_client = mock_client
        service.azure_form_recognizer_client = mock_client # Mock Azure client as well
        return service

@pytest.mark.asyncio
async def test_parse_contract_success(ai_parser_service):
    document_url = "http://example.com/contract.pdf"
    
    # Mock the internal parsing methods to return specific data
    with patch.object(ai_parser_service, 
                      "_parse_with_azure_form_recognizer", 
                      new_callable=AsyncMock) as mock_azure_parser:
        mock_azure_parser.return_value = {"field_azure": "value_azure"}
        
        with patch.object(ai_parser_service, 
                          "_parse_with_openai", 
                          new_callable=AsyncMock) as mock_openai_parser:
            mock_openai_parser.return_value = {"field_openai": "value_openai"}
            
            parsed_data = await ai_parser_service.parse_contract(document_url)
            
            # Verify that both parsing methods were called
            mock_azure_parser.assert_called_once_with(document_url)
            mock_openai_parser.assert_called_once_with(document_url)
            
            # Verify that data from both sources is merged
            assert parsed_data == {"field_azure": "value_azure", "field_openai": "value_openai"}

@pytest.mark.asyncio
async def test_parse_contract_azure_failure_fallback_openai(ai_parser_service):
    document_url = "http://example.com/contract.pdf"
    
    # Mock Azure parser to raise an exception
    with patch.object(ai_parser_service, 
                      "_parse_with_azure_form_recognizer", 
                      new_callable=AsyncMock) as mock_azure_parser:
        mock_azure_parser.side_effect = Exception("Azure error")
        
        with patch.object(ai_parser_service, 
                          "_parse_with_openai", 
                          new_callable=AsyncMock) as mock_openai_parser:
            mock_openai_parser.return_value = {"field_openai_fallback": "value_openai_fallback"}
            
            parsed_data = await ai_parser_service.parse_contract(document_url)
            
            # Verify Azure parser was called and OpenAI parser was still called
            mock_azure_parser.assert_called_once_with(document_url)
            mock_openai_parser.assert_called_once_with(document_url)
            
            # Verify that only OpenAI data is present (as Azure failed)
            assert parsed_data == {"field_openai_fallback": "value_openai_fallback"}

@pytest.mark.asyncio
async def test_parse_with_azure_form_recognizer_dummy_data(ai_parser_service):
    document_url = "http://example.com/contract.pdf"
    parsed_data = await ai_parser_service._parse_with_azure_form_recognizer(document_url)
    
    # Verify that dummy data is returned (as per current placeholder implementation)
    assert "sender_ip" in parsed_data
    assert "signer_ip" in parsed_data
    assert "mailing_address" in parsed_data

@pytest.mark.asyncio
async def test_parse_with_openai_dummy_data(ai_parser_service):
    document_url = "http://example.com/contract.pdf"
    parsed_data = await ai_parser_service._parse_with_openai(document_url)
    
    # Verify that dummy data is returned (as per current placeholder implementation)
    assert "sender_ip" in parsed_data
    assert "signer_ip" in parsed_data
    assert "mailing_address" in parsed_data


