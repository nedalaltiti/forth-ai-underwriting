"""
Validation service for underwriting checks.
Clean, modular implementation using centralized prompt management and reference data.
"""

import asyncio
import json
import httpx
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from loguru import logger
from dateutil.parser import parse as parse_date

from forth_ai_underwriting.config.settings import settings
from forth_ai_underwriting.core.schemas import ValidationResult
from forth_ai_underwriting.services.gemini_service import get_gemini_service
from forth_ai_underwriting.core.exceptions import ValidationError, ExternalAPIError


class ReferenceDataManager:
    """Manages reference data for validation checks."""
    
    def __init__(self):
        self.reference_data = self._load_reference_data()
    
    def _load_reference_data(self) -> Dict[str, Any]:
        """Load reference data from JSON files."""
        try:
            # Load main reference data
            with open("src/forth_ai_underwriting/data/reference_tables.json", "r") as f:
                main_data = json.load(f)
            
            # Load enhanced reference data
            try:
                with open("src/forth_ai_underwriting/data/enhanced_reference_tables.json", "r") as f:
                    enhanced_data = json.load(f)
                    # Merge enhanced data
                    main_data.update(enhanced_data)
            except FileNotFoundError:
                logger.warning("Enhanced reference data not found, using basic reference data")
            
            return main_data
        except Exception as e:
            logger.error(f"Failed to load reference data: {e}")
            return self._get_fallback_reference_data()
    
    def _get_fallback_reference_data(self) -> Dict[str, Any]:
        """Fallback reference data if files are not available."""
        return {
            "state_company_mapping": {"CA": "Faye Caulin"},
            "affiliate_exceptions": {"Credit Care": {"draft_days_min": 2, "draft_days_max": 45}},
            "validation_thresholds": {"minimum_payment": 250.00, "minimum_age": 18}
        }
    
    def get_state_company(self, state: str) -> Optional[str]:
        """Get assigned company for a state."""
        return self.reference_data.get("state_company_mapping", {}).get(state.upper())
    
    def get_affiliate_exceptions(self, affiliate: str) -> Optional[Dict[str, Any]]:
        """Get affiliate-specific exceptions."""
        return self.reference_data.get("affiliate_exceptions", {}).get(affiliate)
    
    def get_threshold(self, threshold_name: str) -> Any:
        """Get validation threshold value."""
        return self.reference_data.get("validation_thresholds", {}).get(threshold_name)


class ForthAPIClient:
    """Client for Forth API interactions."""
    
    def __init__(self):
        self.client = httpx.AsyncClient(
            base_url=settings.forth_api.base_url,
            headers={"Authorization": f"Bearer {settings.forth_api.api_key}"},
            timeout=settings.forth_api.timeout
        )
    
    async def fetch_contact_data(self, contact_id: str) -> Dict[str, Any]:
        """Fetch contact data from Forth API."""
        try:
            response = await self.client.get(f"/contacts/{contact_id}")
            response.raise_for_status()
            return response.json()
        except httpx.RequestError as e:
            logger.error(f"Network error fetching contact {contact_id}: {e}")
            raise ExternalAPIError(f"Failed to fetch contact data: {str(e)}")
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching contact {contact_id}: {e}")
            raise ExternalAPIError(f"API error: {e.response.status_code}")
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()


class ValidationService:
    """
    Clean validation service using modular components.
    Delegates AI validations to specialized services.
    """
    
    def __init__(self):
        self.reference_manager = ReferenceDataManager()
        self.forth_client = ForthAPIClient()
        self.gemini_service = get_gemini_service()
        logger.info("ValidationService initialized with modular components")
    
    async def validate_contact(
        self, 
        contact_id: str, 
        parsed_contract_data: Optional[Dict[str, Any]] = None
    ) -> List[ValidationResult]:
        """
        Main validation method that orchestrates all validation checks.
        
        Args:
            contact_id: The contact ID to validate
            parsed_contract_data: Optional parsed contract data from AI
            
        Returns:
            List of ValidationResult objects
        """
        results = []
        
        try:
            # Fetch contact data from Forth
            async with self.forth_client as client:
                contact_data = await client.fetch_contact_data(contact_id)
            
            # Run all validation checks in parallel for better performance
            validation_tasks = [
                self._validate_hardship(contact_data),
                self._validate_budget_analysis(contact_data),
                self._validate_contract(contact_data, parsed_contract_data),
                self._validate_address(contact_data),
                self._validate_draft(contact_data)
            ]
            
            # Gather results from all validations
            validation_results = await asyncio.gather(*validation_tasks, return_exceptions=True)
            
            # Process results and handle exceptions
            for result in validation_results:
                if isinstance(result, Exception):
                    logger.error(f"Validation error: {result}")
                    results.append(ValidationResult(
                        "Validation Error",
                        "No Pass",
                        f"Validation failed: {str(result)}"
                    ))
                else:
                    results.extend(result)
            
            logger.info(f"Validation completed for contact {contact_id}: {len(results)} checks")
            
        except Exception as e:
            logger.error(f"Validation error for contact {contact_id}: {e}")
            results.append(ValidationResult(
                "System Error",
                "No Pass",
                f"Validation system error: {str(e)}"
            ))
        
        return results
    
    async def _validate_hardship(self, contact_data: Dict[str, Any]) -> List[ValidationResult]:
        """Validate hardship using AI service."""
        results = []
        
        try:
            hardship_description = contact_data.get("custom_fields", {}).get("hardship_description", "")
            
            if not hardship_description or len(hardship_description.strip()) == 0:
                results.append(ValidationResult(
                    "Valid Claim of Hardship",
                    "No Pass",
                    "No hardship description provided"
                ))
                return results
            
            # Use Gemini service for AI-powered assessment
            try:
                assessment = await self.gemini_service.assess_hardship_claim(
                    hardship_description=hardship_description,
                    client_context=self._extract_client_context(contact_data)
                )
                
                result = "Pass" if assessment.is_valid else "No Pass"
                reason = assessment.reason
                confidence = assessment.confidence
                
                # Add keywords found to the reason if available
                if assessment.keywords_found:
                    keywords_str = ", ".join(assessment.keywords_found)
                    reason += f" (Keywords found: {keywords_str})"
                
                results.append(ValidationResult(
                    "Valid Claim of Hardship",
                    result,
                    reason,
                    confidence
                ))
                
            except Exception as ai_error:
                logger.warning(f"AI hardship assessment failed, using fallback: {ai_error}")
                # Simple fallback validation
                result, reason, confidence = self._fallback_hardship_validation(hardship_description)
                results.append(ValidationResult(
                    "Valid Claim of Hardship",
                    result,
                    reason,
                    confidence
                ))
            
        except Exception as e:
            results.append(ValidationResult(
                "Valid Claim of Hardship",
                "No Pass",
                f"Error validating hardship: {str(e)}"
            ))
        
        return results
    
    def _extract_client_context(self, contact_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract relevant client context for AI assessment."""
        return {
            "age": self._calculate_age(contact_data.get("date_of_birth")),
            "family_size": contact_data.get("family_size"),
            "employment_status": contact_data.get("employment_status"),
            "monthly_income": contact_data.get("budget_analysis", {}).get("income"),
            "total_debt": contact_data.get("total_debt")
        }
    
    def _calculate_age(self, date_of_birth: Optional[str]) -> Optional[int]:
        """Calculate age from date of birth."""
        if not date_of_birth:
            return None
        try:
            dob = parse_date(date_of_birth).date()
            today = datetime.now().date()
            return (today - dob).days // 365
        except:
            return None
    
    def _fallback_hardship_validation(self, description: str) -> Tuple[str, str, float]:
        """Fallback hardship validation when AI is unavailable."""
        description_length = len(description.strip())
        
        if description_length < 10:
            return "No Pass", "Hardship description too short or unclear (fallback)", 0.3
        
        # Simple keyword-based validation
        financial_keywords = [
            "job loss", "unemployment", "medical", "illness", "divorce", 
            "income reduction", "disability", "layoff", "financial hardship",
            "unable to pay", "lost job", "reduced hours", "emergency"
        ]
        
        description_lower = description.lower()
        keyword_matches = sum(1 for keyword in financial_keywords if keyword in description_lower)
        
        if keyword_matches > 0:
            return "Pass", f"Valid financial hardship with {keyword_matches} indicators (fallback)", min(0.7 + (keyword_matches * 0.1), 1.0)
        else:
            return "Pass", "Hardship description provided (one-word entries acceptable, fallback)", 0.5
    
    async def _validate_budget_analysis(self, contact_data: Dict[str, Any]) -> List[ValidationResult]:
        """Validate budget analysis for positive surplus."""
        results = []
        
        try:
            budget_data = contact_data.get("budget_analysis", {})
            income = budget_data.get("income", 0)
            expenses = budget_data.get("expenses", 0)
            
            surplus = income - expenses
            
            if surplus > 0:
                result = "Pass"
                reason = f"Positive surplus of ${surplus:.2f} (Income: ${income:.2f}, Expenses: ${expenses:.2f})"
            else:
                result = "No Pass"
                reason = f"Negative surplus of ${surplus:.2f} (Income: ${income:.2f}, Expenses: ${expenses:.2f})"
            
            results.append(ValidationResult(
                "Budget Analysis",
                result,
                reason
            ))
            
        except Exception as e:
            results.append(ValidationResult(
                "Budget Analysis",
                "No Pass",
                f"Error validating budget: {str(e)}"
            ))
        
        return results
    
    async def _validate_contract(
        self, 
        contact_data: Dict[str, Any], 
        parsed_contract_data: Optional[Dict[str, Any]]
    ) -> List[ValidationResult]:
        """Validate contract-related checks using modular validators."""
        results = []
        
        if not parsed_contract_data:
            results.append(ValidationResult(
                "Contract Validation",
                "No Pass",
                "No contract data available for validation"
            ))
            return results
        
        try:
            # Use individual validator methods for modularity
            validators = [
                self._validate_ip_addresses,
                self._validate_mailing_address,
                self._validate_signatures,
                self._validate_bank_details,
                self._validate_ssn_consistency,
                self._validate_dob_consistency
            ]
            
            for validator in validators:
                try:
                    result = validator(contact_data, parsed_contract_data)
                    if result:
                        results.append(result)
                except Exception as e:
                    logger.error(f"Contract validator {validator.__name__} failed: {e}")
                    results.append(ValidationResult(
                        f"Contract - {validator.__name__.replace('_validate_', '').title()}",
                        "No Pass",
                        f"Validation error: {str(e)}"
                    ))
            
        except Exception as e:
            results.append(ValidationResult(
                "Contract Validation",
                "No Pass",
                f"Error validating contract: {str(e)}"
            ))
        
        return results
    
    def _validate_ip_addresses(self, contact_data: Dict[str, Any], parsed_contract_data: Dict[str, Any]) -> ValidationResult:
        """Validate IP addresses in contract."""
        sender_ip = parsed_contract_data.get("sender_ip")
        signer_ip = parsed_contract_data.get("signer_ip")
        
        if sender_ip and signer_ip and sender_ip != signer_ip:
            return ValidationResult(
                "Contract - IP Addresses",
                "Pass",
                f"Sender IP ({sender_ip}) differs from signer IP ({signer_ip})"
            )
        else:
            return ValidationResult(
                "Contract - IP Addresses",
                "No Pass",
                "Sender and signer IP addresses are the same or missing"
            )
    
    def _validate_mailing_address(self, contact_data: Dict[str, Any], parsed_contract_data: Dict[str, Any]) -> ValidationResult:
        """Validate mailing address consistency."""
        forth_address = contact_data.get("address", {})
        contract_address = parsed_contract_data.get("mailing_address", {})
        
        if self._addresses_match(forth_address, contract_address):
            return ValidationResult(
                "Contract - Mailing Address",
                "Pass",
                "Mailing address matches between Forth and contract"
            )
        else:
            return ValidationResult(
                "Contract - Mailing Address",
                "No Pass",
                "Mailing address mismatch between Forth and contract"
            )
    
    def _validate_signatures(self, contact_data: Dict[str, Any], parsed_contract_data: Dict[str, Any]) -> ValidationResult:
        """Validate signature requirements."""
        signatures = parsed_contract_data.get("signatures", {})
        applicant_sig = signatures.get("applicant")
        co_applicant_sig = signatures.get("co_applicant")
        
        issues = []
        
        # Check for dots/dashes in signatures
        if applicant_sig and ("." in applicant_sig or "-" in applicant_sig):
            issues.append("Applicant signature contains dots or dashes")
        
        if co_applicant_sig and ("." in co_applicant_sig or "-" in co_applicant_sig):
            issues.append("Co-applicant signature contains dots or dashes")
        
        # Check if signatures are present
        if not applicant_sig:
            issues.append("Missing applicant signature")
        
        if issues:
            return ValidationResult(
                "Contract - Signatures",
                "No Pass",
                "; ".join(issues)
            )
        else:
            return ValidationResult(
                "Contract - Signatures",
                "Pass",
                "Signatures meet requirements"
            )
    
    def _validate_bank_details(self, contact_data: Dict[str, Any], parsed_contract_data: Dict[str, Any]) -> ValidationResult:
        """Validate bank details consistency."""
        forth_bank = contact_data.get("bank_details", {})
        contract_bank = parsed_contract_data.get("bank_details", {})
        
        if self._bank_details_match(forth_bank, contract_bank):
            return ValidationResult(
                "Contract - Bank Details",
                "Pass",
                "Bank details match between Forth and contract"
            )
        else:
            return ValidationResult(
                "Contract - Bank Details",
                "No Pass",
                "Bank details mismatch between Forth and contract"
            )
    
    def _validate_ssn_consistency(self, contact_data: Dict[str, Any], parsed_contract_data: Dict[str, Any]) -> ValidationResult:
        """Validate SSN consistency across sources."""
        try:
            # Get SSN from different sources
            gateway_ssn_last4 = parsed_contract_data.get("gateway", {}).get("ssn_last4")
            contract_ssn_full = parsed_contract_data.get("agreement", {}).get("ssn")
            legal_plan_ssn = parsed_contract_data.get("legal_plan", {}).get("ssn")
            credit_report_ssn = contact_data.get("credit_report", {}).get("ssn")
            
            # Extract last 4 digits for comparison
            def get_last4(ssn):
                if ssn:
                    return str(ssn).replace("-", "").replace(" ", "")[-4:]
                return None
            
            contract_last4 = get_last4(contract_ssn_full)
            legal_last4 = get_last4(legal_plan_ssn)
            credit_last4 = get_last4(credit_report_ssn)
            
            # Compare all available SSN sources
            ssn_sources = {
                "gateway": gateway_ssn_last4,
                "contract": contract_last4,
                "legal_plan": legal_last4,
                "credit_report": credit_last4
            }
            
            # Filter out None values
            available_ssns = {k: v for k, v in ssn_sources.items() if v}
            
            if len(available_ssns) < 2:
                return ValidationResult(
                    "Contract - SSN Consistency",
                    "No Pass",
                    "Insufficient SSN data for comparison"
                )
            
            # Check if all available SSNs match
            unique_ssns = set(available_ssns.values())
            
            if len(unique_ssns) == 1:
                return ValidationResult(
                    "Contract - SSN Consistency",
                    "Pass",
                    f"SSN consistent across {len(available_ssns)} sources"
                )
            else:
                return ValidationResult(
                    "Contract - SSN Consistency",
                    "No Pass",
                    f"SSN mismatch across sources: {available_ssns}"
                )
                
        except Exception as e:
            return ValidationResult(
                "Contract - SSN Consistency",
                "No Pass",
                f"Error validating SSN consistency: {str(e)}"
            )
    
    def _validate_dob_consistency(self, contact_data: Dict[str, Any], parsed_contract_data: Dict[str, Any]) -> ValidationResult:
        """Validate DOB consistency and age requirement."""
        try:
            forth_dob = contact_data.get("date_of_birth")
            contract_dob = parsed_contract_data.get("agreement", {}).get("date_of_birth")
            credit_dob = contact_data.get("credit_report", {}).get("date_of_birth")
            
            # Parse dates
            dates = {}
            for source, dob in [("forth", forth_dob), ("contract", contract_dob), ("credit", credit_dob)]:
                if dob:
                    try:
                        dates[source] = parse_date(dob).date()
                    except:
                        continue
            
            if len(dates) < 2:
                return ValidationResult(
                    "Contract - DOB Consistency",
                    "No Pass",
                    "Insufficient DOB data for comparison"
                )
            
            # Check consistency
            unique_dates = set(dates.values())
            
            if len(unique_dates) > 1:
                return ValidationResult(
                    "Contract - DOB Consistency",
                    "No Pass",
                    f"DOB mismatch across sources: {dates}"
                )
            
            # Check age requirement (18+)
            dob = list(unique_dates)[0]
            today = datetime.now().date()
            age = (today - dob).days // 365
            
            min_age = self.reference_manager.get_threshold("minimum_age") or 18
            
            if age >= min_age:
                return ValidationResult(
                    "Contract - DOB Consistency",
                    "Pass",
                    f"DOB consistent across sources, client age {age} meets minimum requirement"
                )
            else:
                return ValidationResult(
                    "Contract - DOB Consistency",
                    "No Pass",
                    f"Client age {age} below minimum requirement of {min_age}"
                )
                
        except Exception as e:
            return ValidationResult(
                "Contract - DOB Consistency",
                "No Pass",
                f"Error validating DOB consistency: {str(e)}"
            )
    
    async def _validate_address(self, contact_data: Dict[str, Any]) -> List[ValidationResult]:
        """Validate state address against assigned company."""
        results = []
        
        try:
            client_state = contact_data.get("address", {}).get("state", "").upper()
            assigned_company = contact_data.get("assigned_company", "")
            
            if not client_state:
                results.append(ValidationResult(
                    "Address Validation",
                    "No Pass",
                    "No state information available"
                ))
                return results
            
            expected_company = self.reference_manager.get_state_company(client_state)
            
            if not expected_company:
                results.append(ValidationResult(
                    "Address Validation",
                    "No Pass",
                    f"State '{client_state}' not found in reference table"
                ))
            elif assigned_company == expected_company:
                results.append(ValidationResult(
                    "Address Validation",
                    "Pass",
                    f"State '{client_state}' correctly assigned to '{assigned_company}'"
                ))
            else:
                results.append(ValidationResult(
                    "Address Validation",
                    "No Pass",
                    f"State '{client_state}' should be assigned to '{expected_company}', but assigned to '{assigned_company}'"
                ))
                
        except Exception as e:
            results.append(ValidationResult(
                "Address Validation",
                "No Pass",
                f"Error validating address: {str(e)}"
            ))
        
        return results
    
    async def _validate_draft(self, contact_data: Dict[str, Any]) -> List[ValidationResult]:
        """Validate draft payment requirements."""
        results = []
        
        try:
            contract_data = contact_data.get("contract", {})
            payment_amount = contract_data.get("monthly_payment", 0)
            enrollment_date = contact_data.get("enrollment_date")
            first_draft_date = contact_data.get("first_draft_date")
            affiliate = contact_data.get("affiliate", "")
            
            min_payment = self.reference_manager.get_threshold("minimum_payment") or 250.0
            
            # Validate minimum payment amount
            if payment_amount >= min_payment:
                results.append(ValidationResult(
                    "Draft - Minimum Payment",
                    "Pass",
                    f"Payment amount ${payment_amount:.2f} meets minimum requirement of ${min_payment:.2f}"
                ))
            else:
                results.append(ValidationResult(
                    "Draft - Minimum Payment",
                    "No Pass",
                    f"Payment amount ${payment_amount:.2f} below minimum requirement of ${min_payment:.2f}"
                ))
            
            # Validate draft timing
            if enrollment_date and first_draft_date:
                enrollment_dt = parse_date(enrollment_date)
                first_draft_dt = parse_date(first_draft_date)
                days_diff = (first_draft_dt - enrollment_dt).days
                
                # Get affiliate-specific rules
                affiliate_exceptions = self.reference_manager.get_affiliate_exceptions(affiliate)
                if affiliate_exceptions:
                    min_days = affiliate_exceptions.get("draft_days_min", 2)
                    max_days = affiliate_exceptions.get("draft_days_max", 30)
                else:
                    min_days = 2
                    max_days = 30
                
                if min_days <= days_diff <= max_days:
                    results.append(ValidationResult(
                        "Draft - Timing",
                        "Pass",
                        f"First draft is {days_diff} days after enrollment (within {min_days}-{max_days} day range for {affiliate or 'standard'})"
                    ))
                else:
                    results.append(ValidationResult(
                        "Draft - Timing",
                        "No Pass",
                        f"First draft is {days_diff} days after enrollment (outside {min_days}-{max_days} day range for {affiliate or 'standard'})"
                    ))
            else:
                results.append(ValidationResult(
                    "Draft - Timing",
                    "No Pass",
                    "Missing enrollment date or first draft date"
                ))
                
        except Exception as e:
            results.append(ValidationResult(
                "Draft Validation",
                "No Pass",
                f"Error validating draft: {str(e)}"
            ))
        
        return results
    
    def _addresses_match(self, addr1: Dict[str, Any], addr2: Dict[str, Any]) -> bool:
        """Compare two address dictionaries for matching."""
        if not addr1 or not addr2:
            return False
        
        # Normalize and compare key fields
        fields_to_compare = ["street", "city", "state", "zip_code"]
        
        for field in fields_to_compare:
            val1 = str(addr1.get(field, "")).strip().lower()
            val2 = str(addr2.get(field, "")).strip().lower()
            if val1 != val2:
                return False
        
        return True
    
    def _bank_details_match(self, bank1: Dict[str, Any], bank2: Dict[str, Any]) -> bool:
        """Compare two bank detail dictionaries for matching."""
        if not bank1 or not bank2:
            return False
        
        # Compare account number and routing number
        account1 = str(bank1.get("account_number", "")).strip()
        account2 = str(bank2.get("account_number", "")).strip()
        routing1 = str(bank1.get("routing_number", "")).strip()
        routing2 = str(bank2.get("routing_number", "")).strip()
        
        return account1 == account2 and routing1 == routing2

