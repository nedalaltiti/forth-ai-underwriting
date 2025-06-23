"""
Gemini-specific service for document parsing and validation using Google's Gemini models.
Clean service using the centralized prompt management system.
"""

import asyncio
import json
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
from loguru import logger

from forth_ai_underwriting.services.llm_service import get_llm_service
from forth_ai_underwriting.config.settings import settings
from forth_ai_underwriting.core.exceptions import create_ai_parsing_error
from forth_ai_underwriting.prompts import (
    get_hardship_assessment_prompt,
    get_contract_extraction_prompt,
    get_budget_analysis_prompt,
    get_debt_validation_prompt
)
from forth_ai_underwriting.models.hardship_models import (
    HardshipAssessment as HardshipAssessmentModel,
    HardshipAnalysis,
    AssessmentResult,
    DescriptionQuality,
    HardshipRecommendations
)
from forth_ai_underwriting.models.contract_models import ContractData as ContractDataModel


@dataclass
class ContractData:
    """Structured contract data extracted from documents."""
    sender_ip: Optional[str] = None
    signer_ip: Optional[str] = None
    mailing_address: Optional[Dict[str, str]] = None
    signatures: Optional[Dict[str, str]] = None
    bank_details: Optional[Dict[str, str]] = None
    agreement: Optional[Dict[str, Any]] = None
    gateway: Optional[Dict[str, Any]] = None
    legal_plan: Optional[Dict[str, Any]] = None
    vlp_section: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class HardshipAssessment:
    """Hardship assessment result."""
    is_valid: bool
    confidence: float
    reason: str
    keywords_found: List[str]
    assessment_details: Dict[str, Any]


class GeminiService:
    """
    Clean Gemini service using centralized prompt management.
    Focuses only on Gemini-specific optimizations and integrations.
    """
    
    def __init__(self):
        self.llm_service = get_llm_service()
        self.model_name = settings.gemini.model_name
        logger.info(f"GeminiService initialized with model: {self.model_name}")
    
    async def parse_contract_document(self, document_text: str, document_url: str = "N/A") -> ContractData:
        """
        Parse contract document using centralized prompt management.
        
        Args:
            document_text: The full text content of the document
            document_url: URL or identifier of the document
            
        Returns:
            ContractData object with extracted information
        """
        try:
            # Use centralized prompt management
            prompt_data = get_contract_extraction_prompt(document_text=document_text)
            
            result = await self.llm_service.generate_json(
                prompt=prompt_data["user_prompt"],
                system_prompt=prompt_data["system_prompt"]
            )
            
            if not result.success:
                logger.error(f"Contract parsing failed: {result.error}")
                raise create_ai_parsing_error(
                    document_url=document_url,
                    provider="gemini",
                    reason=f"Contract parsing failed: {result.error}"
                )
            
            # Convert to ContractData object
            data = result.data or {}
            return ContractData(
                sender_ip=data.get("sender_ip"),
                signer_ip=data.get("signer_ip"),
                mailing_address=data.get("mailing_address"),
                signatures=data.get("signatures"),
                bank_details=data.get("bank_details"),
                agreement=data.get("agreement"),
                gateway=data.get("gateway"),
                legal_plan=data.get("legal_plan"),
                vlp_section=data.get("vlp_section"),
                metadata=data.get("document_metadata")
            )
            
        except Exception as e:
            logger.error(f"Contract parsing failed for document {document_url}: {e}")
            raise create_ai_parsing_error(
                document_url=document_url,
                provider="gemini",
                reason=f"Contract parsing failed: {str(e)}"
            )
    
    async def assess_hardship_claim(
        self, 
        hardship_description: str, 
        client_context: Optional[Dict[str, Any]] = None
    ) -> HardshipAssessment:
        """
        Assess hardship using centralized prompt management.
        
        Args:
            hardship_description: The client's hardship description
            client_context: Additional client context
            
        Returns:
            HardshipAssessment with validation results
        """
        try:
            # Use centralized prompt management
            prompt_data = get_hardship_assessment_prompt(
                hardship_description=hardship_description,
                client_age=client_context.get("age") if client_context else None,
                family_size=client_context.get("family_size") if client_context else None,
                employment_status=client_context.get("employment_status") if client_context else None,
                monthly_income=client_context.get("monthly_income") if client_context else None,
                total_debt=client_context.get("total_debt") if client_context else None
            )
            
            result = await self.llm_service.generate_json(
                prompt=prompt_data["user_prompt"],
                system_prompt=prompt_data["system_prompt"]
            )
            
            if not result.success:
                logger.error(f"Hardship assessment failed: {result.error}")
                return HardshipAssessment(
                    is_valid=False,
                    confidence=0.0,
                    reason=f"Assessment failed: {result.error}",
                    keywords_found=[],
                    assessment_details={}
                )
            
            # Return legacy format for compatibility
            data = result.data or {}
            return HardshipAssessment(
                is_valid=data.get("assessment_result", {}).get("is_valid", False),
                confidence=data.get("assessment_result", {}).get("confidence", 0.0),
                reason=data.get("detailed_reasoning", "No reasoning provided"),
                keywords_found=data.get("keywords_found", []),
                assessment_details=data.get("hardship_analysis", {})
            )
            
        except Exception as e:
            logger.error(f"Hardship assessment failed: {e}")
            raise create_ai_parsing_error(
                document_url="N/A",
                provider="gemini", 
                reason=f"Hardship assessment failed: {str(e)}"
            )
    
    async def analyze_budget_data(self, budget_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze budget data using centralized prompt management.
        """
        try:
            prompt_data = get_budget_analysis_prompt(
                income_details=json.dumps(budget_info.get("income", {}), indent=2),
                expense_details=json.dumps(budget_info.get("expenses", {}), indent=2),
                debt_summary=json.dumps(budget_info.get("debts", {}), indent=2),
                family_size=budget_info.get("family_size"),
                location=budget_info.get("location"),
                employment_status=budget_info.get("employment_status"),
                credit_score=budget_info.get("credit_score")
            )
            
            result = await self.llm_service.generate_json(
                prompt=prompt_data["user_prompt"],
                system_prompt=prompt_data["system_prompt"]
            )
            
            if not result.success:
                logger.error(f"Budget analysis failed: {result.error}")
                return {"error": f"Analysis failed: {result.error}"}
            
            return result.data or {}
            
        except Exception as e:
            logger.error(f"Budget analysis failed: {e}")
            raise create_ai_parsing_error(
                document_url="N/A",
                provider="gemini",
                reason=f"Budget analysis failed: {str(e)}"
            )
    
    async def validate_debt_information(self, debt_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validate debt information using centralized prompt management.
        """
        try:
            prompt_data = get_debt_validation_prompt(
                debt_list=json.dumps(debt_list, indent=2),
                creditor_database="{}",  # Would be loaded from reference data
                monthly_income="N/A",
                client_state="N/A",
                program_type="standard"
            )
            
            result = await self.llm_service.generate_json(
                prompt=prompt_data["user_prompt"],
                system_prompt=prompt_data["system_prompt"]
            )
            
            if not result.success:
                logger.error(f"Debt validation failed: {result.error}")
                return {"error": f"Validation failed: {result.error}"}
            
            return result.data or {}
            
        except Exception as e:
            logger.error(f"Debt validation failed: {e}")
            raise create_ai_parsing_error(
                document_url="N/A",
                provider="gemini",
                reason=f"Debt validation failed: {str(e)}"
            )
    
    async def health_check(self) -> Dict[str, Any]:
        """Check the health of the Gemini service."""
        try:
            test_response = await self.llm_service.test_connection()
            
            return {
                "status": "healthy" if test_response else "unhealthy",
                "model": self.model_name,
                "llm_service": "connected" if test_response else "disconnected"
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "model": self.model_name
            }


# Global Gemini service instance
_gemini_service: Optional[GeminiService] = None


def get_gemini_service() -> GeminiService:
    """Get the global Gemini service instance."""
    global _gemini_service
    if _gemini_service is None:
        _gemini_service = GeminiService()
    return _gemini_service 