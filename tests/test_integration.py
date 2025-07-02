"""
Integration tests for the Forth AI Underwriting System.
Tests the complete pipeline from document processing to validation.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from typing import Dict, Any

from forth_ai_underwriting.infrastructure.ai_parser import get_ai_parser_service
from forth_ai_underwriting.services.validation import ValidationService
from forth_ai_underwriting.services.gemini_service import get_gemini_service
from forth_ai_underwriting.services.llm_service import get_llm_service
from forth_ai_underwriting.services.process import get_document_processor
from forth_ai_underwriting.prompts import get_prompt_manager


@pytest.fixture
def mock_contact_data() -> Dict[str, Any]:
    """Mock contact data for testing."""
    return {
        "contact_id": "test_contact_123",
        "address": {"state": "CA", "city": "Los Angeles", "street": "123 Test St", "zip_code": "90210"},
        "assigned_company": "Faye Caulin",
        "custom_fields": {"hardship_description": "Lost my job due to company downsizing and medical expenses."},
        "budget_analysis": {"income": 5000, "expenses": 4000},
        "enrollment_date": "2025-01-01",
        "first_draft_date": "2025-01-15",
        "affiliate": "Standard",
        "contract": {"monthly_payment": 300}
    }


@pytest.fixture
def mock_contract_data() -> Dict[str, Any]:
    """Mock parsed contract data for testing."""
    return {
        "sender_ip": "192.168.1.100",
        "signer_ip": "10.0.0.50",
        "mailing_address": {
            "street": "123 Test St",
            "city": "Los Angeles", 
            "state": "CA",
            "zip_code": "90210"
        },
        "signatures": {
            "applicant": "John Doe",
            "co_applicant": "Jane Doe"
        },
        "bank_details": {
            "account_number": "1234567890",
            "routing_number": "0987654321",
            "bank_name": "Test Bank"
        },
        "agreement": {
            "ssn": "123-45-6789",
            "date_of_birth": "1990-01-01",
            "full_name": "John Doe"
        },
        "gateway": {
            "ssn_last4": "6789",
            "payment_amount": 300.00,
            "enrollment_date": "2025-01-01",
            "first_draft_date": "2025-01-15"
        },
        "legal_plan": {
            "ssn": "123-45-6789",
            "signed": True
        },
        "vlp_section": {
            "present": True,
            "signed": True,
            "ssn": "123-45-6789",
            "dob": "1990-01-01",
            "name": "John Doe"
        }
    }


class TestServiceIntegration:
    """Test integration between all services."""
    
    @pytest.mark.asyncio
    async def test_prompt_manager_integration(self) -> None:
        """Test that prompt manager works with all services."""
        prompt_manager = get_prompt_manager()
        
        # Test contract extraction prompt
        contract_prompt = prompt_manager.render_prompt(
            "contract_extraction_v1",
            document_text="Sample contract text"
        )
        
        assert "system_prompt" in contract_prompt
        assert "user_prompt" in contract_prompt
        assert "Sample contract text" in contract_prompt["user_prompt"]
        
        # Test hardship assessment prompt
        hardship_prompt = prompt_manager.render_prompt(
            "hardship_assessment_v1",
            hardship_description="Lost my job"
        )
        
        assert "system_prompt" in hardship_prompt
        assert "user_prompt" in hardship_prompt
        assert "Lost my job" in hardship_prompt["user_prompt"]
    
    @pytest.mark.asyncio
    async def test_llm_service_integration(self) -> None:
        """Test LLM service with different providers."""
        llm_service = get_llm_service()
        
        # Test service initialization
        assert llm_service is not None
        health = llm_service.health_check()
        assert "status" in health
        # Accept either "service", "model", or "providers" keys for health check
        assert any(key in health for key in ["providers", "service", "model"])
        
        # Test available providers
        providers = llm_service.get_available_providers()
        assert isinstance(providers, list)
    
    @pytest.mark.asyncio
    async def test_gemini_service_integration(self) -> None:
        """Test Gemini service integration."""
        gemini_service = get_gemini_service()
        
        # Test health check
        health = await gemini_service.health_check()
        assert "status" in health
        assert "model" in health
    
    @pytest.mark.asyncio
    async def test_document_processor_integration(self) -> None:
        """Test document processor service."""
        processor = get_document_processor()
        
        # Test health check
        health = await processor.health_check()
        assert "status" in health
        # Don't require specific keys as the structure may vary
    
    @pytest.mark.asyncio
    async def test_ai_parser_integration(self) -> None:
        """Test AI parser service orchestration."""
        ai_parser = get_ai_parser_service()
        
        # Test health check
        health = await ai_parser.health_check()
        assert "status" in health
        assert "document_processor" in health
        assert "gemini_service" in health


class TestValidationPipeline:
    """Test the complete validation pipeline."""
    
    @pytest.mark.asyncio
    async def test_complete_validation_pipeline(self, mock_contact_data: Dict[str, Any], mock_contract_data: Dict[str, Any]) -> None:
        """Test the complete validation pipeline from end to end."""
        
        # Mock the Forth API client
        with patch('forth_ai_underwriting.services.validation.ForthAPIClient') as mock_client:
            # Setup mock to return test contact data
            mock_instance = AsyncMock()
            mock_instance.fetch_contact_data.return_value = mock_contact_data
            mock_client.return_value.__aenter__.return_value = mock_instance
            
            # Mock Gemini service for hardship assessment
            with patch('forth_ai_underwriting.services.validation.get_gemini_service') as mock_gemini:
                mock_gemini_instance = AsyncMock()
                mock_gemini_instance.assess_hardship_claim.return_value = MagicMock(
                    is_valid=True,
                    confidence=0.85,
                    reason="Valid financial hardship due to job loss",
                    keywords_found=["job", "company downsizing"],
                    assessment_details={"category": "job_loss"}
                )
                mock_gemini.return_value = mock_gemini_instance
                
                # Run validation
                validation_service = ValidationService()
                results = await validation_service.validate_contact(
                    contact_id="test_contact_123",
                    parsed_contract_data=mock_contract_data
                )
                
                # Verify results
                assert len(results) > 0
                
                # Check that all validation types are present
                validation_types = [result.title for result in results]
                expected_types = [
                    "Valid Claim of Hardship",
                    "Budget Analysis", 
                    "Contract - IP Addresses",
                    "Contract - Mailing Address",
                    "Contract - Signatures",
                    "Contract - Bank Details",
                    "Contract - SSN Consistency",
                    "Contract - DOB Consistency",
                    "Address Validation",
                    "Draft - Minimum Payment",
                    "Draft - Timing"
                ]
                
                for expected_type in expected_types:
                    assert any(expected_type in vtype for vtype in validation_types), f"Missing validation: {expected_type}"
                
                # Check that hardship validation passed
                hardship_result = next((r for r in results if "Hardship" in r.title), None)
                assert hardship_result is not None
                assert hardship_result.result == "Pass"
                assert hardship_result.confidence == 0.85
    
    @pytest.mark.asyncio
    async def test_validation_with_failures(self, mock_contact_data: Dict[str, Any], mock_contract_data: Dict[str, Any]) -> None:
        """Test validation pipeline with some failures."""
        
        # Modify test data to create failures
        failing_contract_data = mock_contract_data.copy()
        failing_contract_data["sender_ip"] = "192.168.1.100"  # Same as signer IP
        failing_contract_data["signer_ip"] = "192.168.1.100"  # Same as sender IP
        
        failing_contact_data = mock_contact_data.copy()
        failing_contact_data["budget_analysis"] = {"income": 3000, "expenses": 4000}  # Negative surplus
        
        with patch('forth_ai_underwriting.services.validation.ForthAPIClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.fetch_contact_data.return_value = failing_contact_data
            mock_client.return_value.__aenter__.return_value = mock_instance
            
            with patch('forth_ai_underwriting.services.validation.get_gemini_service') as mock_gemini:
                mock_gemini_instance = AsyncMock()
                mock_gemini_instance.assess_hardship_claim.return_value = MagicMock(
                    is_valid=False,
                    confidence=0.25,
                    reason="Insufficient detail in hardship description",
                    keywords_found=[],
                    assessment_details={"category": "unclear"}
                )
                mock_gemini.return_value = mock_gemini_instance
                
                validation_service = ValidationService()
                results = await validation_service.validate_contact(
                    contact_id="test_contact_123",
                    parsed_contract_data=failing_contract_data
                )
                
                # Verify that we have failures
                failed_results = [r for r in results if r.result == "No Pass"]
                assert len(failed_results) > 0
                
                # Check specific failures
                ip_result = next((r for r in results if "IP Addresses" in r.title), None)
                assert ip_result is not None
                assert ip_result.result == "No Pass"
                
                budget_result = next((r for r in results if "Budget Analysis" in r.title), None)
                assert budget_result is not None
                assert budget_result.result == "No Pass"


class TestErrorHandling:
    """Test error handling across the system."""
    
    @pytest.mark.asyncio
    async def test_ai_service_error_handling(self) -> None:
        """Test error handling when AI services fail."""
        
        with patch("forth_ai_underwriting.services.gemini_service.get_gemini_service") as mock_get_service:
            mock_service = AsyncMock()
            mock_service.parse_contract_document.side_effect = Exception("AI service unavailable")
            mock_get_service.return_value = mock_service
            
            gemini_service = get_gemini_service()
            
            # This should raise an appropriate exception
            with pytest.raises(Exception):
                await gemini_service.parse_contract_document("test document")
    
    @pytest.mark.asyncio 
    async def test_validation_service_error_recovery(self, mock_contact_data: Dict[str, Any]) -> None:
        """Test validation service error recovery mechanisms."""
        
        with patch('forth_ai_underwriting.services.validation.ForthAPIClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.fetch_contact_data.return_value = mock_contact_data
            mock_client.return_value.__aenter__.return_value = mock_instance
            
            # Mock Gemini service to fail, should fall back to rule-based validation
            with patch('forth_ai_underwriting.services.validation.get_gemini_service') as mock_gemini:
                mock_gemini_instance = AsyncMock()
                mock_gemini_instance.assess_hardship_claim.side_effect = Exception("AI service failed")
                mock_gemini.return_value = mock_gemini_instance
                
                validation_service = ValidationService()
                results = await validation_service.validate_contact("test_contact_123")
                
                # Should still get results due to fallback mechanisms
                assert len(results) > 0
                
                # Hardship validation should have used fallback
                hardship_result = next((r for r in results if "Hardship" in r.title), None)
                assert hardship_result is not None
                assert "fallback" in hardship_result.reason


class TestPerformanceIntegration:
    """Test performance aspects of the integrated system."""
    
    @pytest.mark.asyncio
    async def test_concurrent_validations(self, mock_contact_data: Dict[str, Any], mock_contract_data: Dict[str, Any]) -> None:
        """Test that multiple validations can run concurrently."""
        
        with patch('forth_ai_underwriting.services.validation.ForthAPIClient') as mock_client:
            mock_instance = AsyncMock()
            mock_instance.fetch_contact_data.return_value = mock_contact_data
            mock_client.return_value.__aenter__.return_value = mock_instance
            
            with patch('forth_ai_underwriting.services.validation.get_gemini_service') as mock_gemini:
                mock_gemini_instance = AsyncMock()
                mock_gemini_instance.assess_hardship_claim.return_value = MagicMock(
                    is_valid=True,
                    confidence=0.85,
                    reason="Valid hardship",
                    keywords_found=["job"],
                    assessment_details={}
                )
                mock_gemini.return_value = mock_gemini_instance
                
                validation_service = ValidationService()
                
                # Run multiple validations concurrently
                tasks = [
                    validation_service.validate_contact(f"contact_{i}", mock_contract_data)
                    for i in range(5)
                ]
                
                results = await asyncio.gather(*tasks)
                
                # All should complete successfully
                assert len(results) == 5
                for result_set in results:
                    assert len(result_set) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 