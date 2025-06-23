"""
Contract parsing prompts for AI document analysis.
Specialized prompts for extracting structured data from debt settlement contracts.
"""

from typing import Dict, Any, List
from .prompt_manager import PromptTemplate, PromptCategory, PromptVersion, get_prompt_manager


class ContractParsingPrompts:
    """Container for all contract-related prompts."""
    
    @staticmethod
    def register_all_prompts():
        """Register all contract parsing prompts with the prompt manager."""
        manager = get_prompt_manager()
        
        # Contract Data Extraction Prompt
        contract_extraction_prompt = PromptTemplate(
            name="contract_extraction",
            category=PromptCategory.CONTRACT_PARSING,
            version=PromptVersion.V2_0,
            system_prompt="""You are an expert legal document analyst specializing in debt settlement contract analysis. Your task is to extract specific structured information from contract documents with extreme accuracy.

CRITICAL EXTRACTION RULES:
1. Only extract information that is explicitly stated in the document
2. Use null for any information that is not clearly present or is ambiguous
3. Pay special attention to IP addresses, signatures, dates, and financial details
4. Distinguish between different document sections (agreement, gateway, legal plan, VLP)
5. Maintain data consistency and format standardization
6. Flag any suspicious or inconsistent data

QUALITY STANDARDS:
- IP addresses must be in valid IPv4 format (x.x.x.x)
- Dates must be in YYYY-MM-DD format
- SSN should be in XXX-XX-XXXX format or last 4 digits only where specified
- Signatures should not contain dots, dashes, or special characters
- Financial amounts should be numeric values""",
            
            user_prompt_template="""Analyze the following contract document and extract the required underwriting information with maximum precision:

DOCUMENT CONTENT:
{document_text}

Extract the following information in strict JSON format:

{{
    "sender_ip": "IP address of document sender (null if not found)",
    "signer_ip": "IP address of document signer (null if not found)",
    "mailing_address": {{
        "street": "complete street address",
        "city": "city name",
        "state": "state abbreviation (2 letters)",
        "zip_code": "zip code"
    }},
    "signatures": {{
        "applicant": "primary applicant signature/name (remove dots/dashes)",
        "co_applicant": "co-applicant signature/name (remove dots/dashes)"
    }},
    "bank_details": {{
        "account_number": "bank account number",
        "routing_number": "bank routing number (9 digits)",
        "bank_name": "name of bank"
    }},
    "agreement": {{
        "ssn": "social security number in XXX-XX-XXXX format",
        "date_of_birth": "date of birth in YYYY-MM-DD format",
        "full_name": "complete legal name as written"
    }},
    "gateway": {{
        "ssn_last4": "last 4 digits of SSN from payment gateway section",
        "payment_amount": "monthly payment amount (numeric)",
        "enrollment_date": "enrollment date in YYYY-MM-DD format",
        "first_draft_date": "first draft date in YYYY-MM-DD format"
    }},
    "legal_plan": {{
        "ssn": "SSN from legal plan section",
        "signed": "true if legal plan section is signed, false otherwise"
    }},
    "vlp_section": {{
        "present": "true if VLP (Voluntary Legal Plan) section exists",
        "signed": "true if VLP section is signed",
        "ssn": "SSN from VLP section",
        "dob": "date of birth from VLP section in YYYY-MM-DD format",
        "name": "full name from VLP section"
    }},
    "document_metadata": {{
        "document_type": "type of document identified",
        "completion_status": "complete/incomplete/partial",
        "pages_processed": "estimated number of pages",
        "extraction_confidence": "high/medium/low confidence in extraction quality"
    }}
}}

VALIDATION REQUIREMENTS:
- All IP addresses must be different and in valid format
- Dates must be realistic and properly formatted
- SSN consistency across all sections
- Signature fields must not contain dots, dashes, or abbreviations
- Financial amounts must be reasonable for debt settlement context

Return ONLY the JSON object with no additional commentary.""",
            
            format_instructions="""Return a valid JSON object with all specified fields. Use null for missing information. Ensure all dates are in YYYY-MM-DD format, IP addresses are valid IPv4, and SSN formats are consistent.""",
            
            required_variables=["document_text"],
            optional_variables=[],
            
            output_schema={
                "sender_ip": (str, None),
                "signer_ip": (str, None),
                "mailing_address": dict,
                "signatures": dict,
                "bank_details": dict,
                "agreement": dict,
                "gateway": dict,
                "legal_plan": dict,
                "vlp_section": dict,
                "document_metadata": dict
            },
            
            examples=[
                {
                    "input": "Sample contract with IP 192.168.1.1 and signature John Doe...",
                    "output": {
                        "sender_ip": "192.168.1.1",
                        "signatures": {"applicant": "John Doe"},
                        "document_metadata": {"extraction_confidence": "high"}
                    }
                }
            ],
            
            metadata={
                "purpose": "Extract structured data from debt settlement contracts",
                "performance_target": "95% accuracy on key fields",
                "last_updated": "2024-01-01"
            }
        )
        
        # Contract Validation Prompt
        contract_validation_prompt = PromptTemplate(
            name="contract_validation",
            category=PromptCategory.CONTRACT_PARSING,
            version=PromptVersion.V2_0,
            system_prompt="""You are a contract validation specialist for debt settlement underwriting. Your role is to identify potential issues, inconsistencies, and compliance violations in extracted contract data.

VALIDATION FOCUS AREAS:
1. Data consistency across document sections
2. Compliance with underwriting requirements
3. Detection of fraudulent or suspicious patterns
4. Verification of required signatures and documentation
5. Financial data validation and reasonableness checks

CRITICAL VALIDATION POINTS:
- IP address differences (sender vs signer)
- SSN consistency across all sections
- Date logic and sequence validation
- Signature completeness and format compliance
- Financial amount reasonableness
- Required documentation presence""",
            
            user_prompt_template="""Validate the extracted contract data for compliance and consistency issues:

EXTRACTED CONTRACT DATA:
{contract_data}

FORTH SYSTEM DATA (for comparison):
{forth_data}

Perform comprehensive validation and return results in JSON format:

{{
    "validation_results": [
        {{
            "check_name": "IP Address Validation",
            "status": "pass/fail/warning",
            "details": "specific findings",
            "severity": "critical/high/medium/low"
        }}
    ],
    "data_consistency": {{
        "ssn_matches": "true/false - SSN consistent across sections",
        "address_consistency": "true/false - addresses match between sources",
        "signature_compliance": "true/false - signatures meet requirements",
        "date_logic": "true/false - dates are logical and sequential"
    }},
    "compliance_status": {{
        "overall_status": "compliant/non_compliant/needs_review",
        "critical_issues": ["list of critical issues"],
        "warnings": ["list of warnings"],
        "recommendations": ["list of recommendations"]
    }},
    "risk_assessment": {{
        "fraud_risk": "low/medium/high",
        "data_quality": "excellent/good/fair/poor",
        "manual_review_required": "true/false",
        "confidence_score": "0.0-1.0"
    }}
}}""",
            
            format_instructions="""Return a comprehensive validation report in JSON format with detailed findings and recommendations.""",
            
            required_variables=["contract_data", "forth_data"],
            optional_variables=[],
            
            metadata={
                "purpose": "Validate extracted contract data for compliance",
                "validation_rules": "Based on underwriting guidelines v2.0"
            }
        )
        
        # Document Quality Assessment Prompt
        document_quality_prompt = PromptTemplate(
            name="document_quality_assessment",
            category=PromptCategory.DOCUMENT_METADATA,
            version=PromptVersion.V1_0,
            system_prompt="""You are a document quality analyst specializing in PDF contract analysis. Assess the quality, completeness, and extractability of contract documents.""",
            
            user_prompt_template="""Assess the quality and completeness of this contract document:

DOCUMENT TEXT SAMPLE:
{document_text}

DOCUMENT METADATA:
- File size: {file_size} bytes
- Estimated pages: {page_count}
- Processing method: {extraction_method}

Provide quality assessment in JSON format:

{{
    "quality_metrics": {{
        "text_clarity": "excellent/good/fair/poor",
        "completeness": "complete/mostly_complete/partial/incomplete",
        "readability": "high/medium/low",
        "extraction_success": "full/partial/failed"
    }},
    "content_analysis": {{
        "has_signatures": "true/false",
        "has_financial_data": "true/false",
        "has_personal_info": "true/false",
        "sections_present": ["list of identified sections"]
    }},
    "recommendations": {{
        "suitable_for_processing": "true/false",
        "requires_manual_review": "true/false",
        "improvement_suggestions": ["list of suggestions"]
    }}
}}""",
            
            required_variables=["document_text", "file_size", "page_count", "extraction_method"],
            optional_variables=[]
        )
        
        # Register all prompts
        manager.register_prompt(contract_extraction_prompt)
        manager.register_prompt(contract_validation_prompt)
        manager.register_prompt(document_quality_prompt)


def get_contract_extraction_prompt(**kwargs) -> Dict[str, str]:
    """Get rendered contract extraction prompt."""
    return get_prompt_manager().render_prompt("contract_extraction", **kwargs)


def get_contract_validation_prompt(**kwargs) -> Dict[str, str]:
    """Get rendered contract validation prompt."""
    return get_prompt_manager().render_prompt("contract_validation", **kwargs)


def get_document_quality_prompt(**kwargs) -> Dict[str, str]:
    """Get rendered document quality assessment prompt."""
    return get_prompt_manager().render_prompt("document_quality_assessment", **kwargs)


# Auto-register prompts when module is imported
# ContractParsingPrompts.register_all_prompts()  # Temporarily disabled for testing 