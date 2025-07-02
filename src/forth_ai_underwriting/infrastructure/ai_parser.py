"""
AI Parser service for orchestrating document processing and parsing.
Serves as the main entry point for document analysis, delegating to specialized services.
"""

from typing import Any

from loguru import logger

from forth_ai_underwriting.core.exceptions import AIParsingError
from forth_ai_underwriting.services.gemini_service import get_gemini_service
from forth_ai_underwriting.services.process import get_document_processor


class AIParserService:
    """
    Orchestrates the complete document parsing pipeline.
    Delegates to specialized services for actual processing.
    """

    def __init__(self):
        self.document_processor = get_document_processor()
        self.gemini_service = get_gemini_service()
        logger.info("AIParserService initialized - document processing pipeline ready")

    async def parse_contract(self, document_url: str) -> dict[str, Any]:
        """
        Main entry point for contract parsing using the complete processing pipeline.

        Args:
            document_url: URL of the document to parse

        Returns:
            Structured contract data dictionary
        """
        logger.info(f"Starting contract parsing for: {document_url}")

        try:
            # Use the comprehensive document processing pipeline
            processing_result = await self.document_processor.process_document(
                document_url=document_url, skip_ai_parsing=False
            )

            if not processing_result.validation_ready:
                logger.warning(
                    f"Document processing completed with issues: {processing_result.processing_errors}"
                )

                # If we have contract data despite issues, use it
                if processing_result.contract_data:
                    return self._contract_data_to_dict(processing_result.contract_data)

                # Fall back to basic parsing if no contract data
                if processing_result.extracted_text:
                    logger.info("Attempting direct parsing with extracted text")
                    contract_data = await self.gemini_service.parse_contract_document(
                        document_text=processing_result.extracted_text,
                        document_url=document_url,
                    )
                    return self._contract_data_to_dict(contract_data)

                # Return fallback structure
                logger.warning("Returning fallback data structure")
                return self._get_fallback_data()

            # Process completed successfully
            if processing_result.contract_data:
                logger.info("Contract parsing completed successfully")
                return self._contract_data_to_dict(processing_result.contract_data)
            else:
                logger.warning(
                    "No contract data extracted despite successful processing"
                )
                return self._get_fallback_data()

        except Exception as e:
            logger.error(f"Contract parsing failed for {document_url}: {e}")
            raise AIParsingError(f"Failed to parse contract: {str(e)}")

    def _contract_data_to_dict(self, contract_data) -> dict[str, Any]:
        """
        Convert ContractData object to dictionary format for compatibility.

        Args:
            contract_data: ContractData object from processing pipeline

        Returns:
            Dictionary representation of contract data
        """
        if hasattr(contract_data, "__dict__"):
            # DataClass object
            result = {}
            for field, value in contract_data.__dict__.items():
                if value is not None:
                    result[field] = value
            return self._ensure_structure(result)
        else:
            # Already a dictionary
            return self._ensure_structure(contract_data)

    def _ensure_structure(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Ensure the contract data has the expected structure.

        Args:
            data: Raw contract data dictionary

        Returns:
            Properly structured contract data
        """
        # Define expected structure with defaults
        expected_structure = {
            "sender_ip": None,
            "signer_ip": None,
            "mailing_address": {
                "street": None,
                "city": None,
                "state": None,
                "zip_code": None,
            },
            "signatures": {"applicant": None, "co_applicant": None},
            "bank_details": {
                "account_number": None,
                "routing_number": None,
                "bank_name": None,
            },
            "agreement": {"ssn": None, "date_of_birth": None, "full_name": None},
            "gateway": {
                "ssn_last4": None,
                "payment_amount": None,
                "enrollment_date": None,
                "first_draft_date": None,
            },
            "legal_plan": {"ssn": None, "signed": None},
            "vlp_section": {
                "present": None,
                "signed": None,
                "ssn": None,
                "dob": None,
                "name": None,
            },
        }

        # Merge data with expected structure
        result = {}
        for key, default_value in expected_structure.items():
            if key in data and data[key] is not None:
                if isinstance(default_value, dict) and isinstance(data[key], dict):
                    # Merge nested dictionaries
                    result[key] = {**default_value, **data[key]}
                else:
                    result[key] = data[key]
            else:
                result[key] = default_value

        return result

    def _get_fallback_data(self) -> dict[str, Any]:
        """
        Return fallback data structure when parsing fails.

        Returns:
            Fallback contract data structure
        """
        return {
            "sender_ip": None,
            "signer_ip": None,
            "mailing_address": {
                "street": None,
                "city": None,
                "state": None,
                "zip_code": None,
            },
            "signatures": {"applicant": None, "co_applicant": None},
            "bank_details": {
                "account_number": None,
                "routing_number": None,
                "bank_name": None,
            },
            "agreement": {"ssn": None, "date_of_birth": None, "full_name": None},
            "gateway": {
                "ssn_last4": None,
                "payment_amount": None,
                "enrollment_date": None,
                "first_draft_date": None,
            },
            "legal_plan": {"ssn": None, "signed": None},
            "vlp_section": {
                "present": None,
                "signed": None,
                "ssn": None,
                "dob": None,
                "name": None,
            },
            "_parsing_status": "failed",
            "_error": "Document parsing failed, using fallback structure",
        }

    async def health_check(self) -> dict[str, Any]:
        """
        Check the health of the AI parsing pipeline.

        Returns:
            Health status of all components
        """
        try:
            processor_health = await self.document_processor.health_check()
            gemini_health = await self.gemini_service.health_check()

            return {
                "status": "healthy"
                if processor_health["status"] == "healthy"
                and gemini_health["status"] == "healthy"
                else "degraded",
                "document_processor": processor_health,
                "gemini_service": gemini_health,
                "pipeline_ready": True,
            }

        except Exception as e:
            return {"status": "unhealthy", "error": str(e), "pipeline_ready": False}


# Global AI parser service instance
_ai_parser_service: AIParserService | None = None


def get_ai_parser_service() -> AIParserService:
    """Get the global AI parser service instance."""
    global _ai_parser_service
    if _ai_parser_service is None:
        _ai_parser_service = AIParserService()
    return _ai_parser_service
