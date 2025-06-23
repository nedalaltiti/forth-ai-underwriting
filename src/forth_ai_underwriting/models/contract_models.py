"""
Contract data models with comprehensive Pydantic validation.
Models for contract parsing and validation results.
"""

from typing import Optional, Dict, Any, List
from datetime import date, datetime
from decimal import Decimal
from ipaddress import IPv4Address
from pydantic import BaseModel, Field, validator, model_validator
import re

from .base_models import (
    TimestampedModel, 
    AddressModel, 
    FinancialAmount, 
    PersonName, 
    SSN, 
    ValidationStatus,
    ProcessingStatus
)


class MailingAddress(AddressModel):
    """Mailing address model with enhanced validation."""
    
    @validator('street')
    def validate_street_required(cls, v):
        if not v or not v.strip():
            raise ValueError("Street address is required")
        return v.strip()
    
    @validator('city')
    def validate_city_required(cls, v):
        if not v or not v.strip():
            raise ValueError("City is required")
        return v.strip().title()


class Signatures(BaseModel):
    """Signature validation model."""
    applicant: Optional[str] = Field(None, description="Primary applicant signature")
    co_applicant: Optional[str] = Field(None, description="Co-applicant signature")
    
    @validator('applicant', 'co_applicant')
    def validate_signature_format(cls, v):
        if v:
            # Remove dots and dashes as per requirements
            cleaned = re.sub(r'[.-]', '', v.strip())
            if not cleaned:
                raise ValueError("Signature cannot be empty after cleaning")
            return cleaned
        return v
    
    @model_validator(mode='before')
    @classmethod
    def validate_at_least_one_signature(cls, values):
        applicant = values.get('applicant')
        co_applicant = values.get('co_applicant')
        
        if not applicant and not co_applicant:
            raise ValueError("At least one signature is required")
        
        return values


class BankDetails(BaseModel):
    """Bank account information with validation."""
    account_number: Optional[str] = Field(None, description="Bank account number")
    routing_number: Optional[str] = Field(None, description="Bank routing number")
    bank_name: Optional[str] = Field(None, description="Name of the bank")
    account_type: Optional[str] = Field(None, description="Type of account (checking, savings)")
    
    @validator('account_number')
    def validate_account_number(cls, v):
        if v:
            # Remove any non-digit characters
            digits = re.sub(r'\D', '', v)
            if len(digits) < 4 or len(digits) > 20:
                raise ValueError("Account number must be 4-20 digits")
            return digits
        return v
    
    @validator('routing_number')
    def validate_routing_number(cls, v):
        if v:
            # Remove any non-digit characters
            digits = re.sub(r'\D', '', v)
            if len(digits) != 9:
                raise ValueError("Routing number must be exactly 9 digits")
            return digits
        return v
    
    @validator('bank_name')
    def validate_bank_name(cls, v):
        if v:
            return v.strip().title()
        return v


class Agreement(BaseModel):
    """Agreement section data."""
    ssn: Optional[SSN] = Field(None, description="Social Security Number")
    date_of_birth: Optional[date] = Field(None, description="Date of birth")
    full_name: Optional[PersonName] = Field(None, description="Full legal name")
    
    @validator('date_of_birth')
    def validate_age(cls, v):
        if v:
            today = date.today()
            age = today.year - v.year - ((today.month, today.day) < (v.month, v.day))
            if age < 18:
                raise ValueError("Applicant must be at least 18 years old")
            if age > 120:
                raise ValueError("Invalid date of birth - age too high")
        return v


class Gateway(BaseModel):
    """Payment gateway section data."""
    ssn_last4: Optional[str] = Field(None, description="Last 4 digits of SSN")
    payment_amount: Optional[FinancialAmount] = Field(None, description="Monthly payment amount")
    enrollment_date: Optional[date] = Field(None, description="Program enrollment date")
    first_draft_date: Optional[date] = Field(None, description="First payment draft date")
    
    @validator('ssn_last4')
    def validate_ssn_last4(cls, v):
        if v:
            digits = re.sub(r'\D', '', v)
            if len(digits) != 4:
                raise ValueError("SSN last 4 must be exactly 4 digits")
            return digits
        return v
    
    @validator('payment_amount')
    def validate_payment_amount(cls, v):
        if v and v.amount < 250:
            raise ValueError("Payment amount must be at least $250")
        return v
    
    @model_validator(mode='before')
    @classmethod
    def validate_date_sequence(cls, values):
        enrollment_date = values.get('enrollment_date')
        first_draft_date = values.get('first_draft_date')
        
        if enrollment_date and first_draft_date:
            days_diff = (first_draft_date - enrollment_date).days
            if days_diff < 2:
                raise ValueError("First draft date must be at least 2 days after enrollment")
            if days_diff > 45:  # Maximum for any affiliate
                raise ValueError("First draft date cannot be more than 45 days after enrollment")
        
        return values


class LegalPlan(BaseModel):
    """Legal plan section data."""
    ssn: Optional[SSN] = Field(None, description="SSN from legal plan")
    signed: Optional[bool] = Field(None, description="Whether legal plan is signed")
    plan_type: Optional[str] = Field(None, description="Type of legal plan")
    
    @validator('signed')
    def validate_signed_status(cls, v):
        # If we have legal plan data, it should be signed
        return v


class VLPSection(BaseModel):
    """Voluntary Legal Plan section data."""
    present: Optional[bool] = Field(None, description="Whether VLP section exists")
    signed: Optional[bool] = Field(None, description="Whether VLP section is signed")
    ssn: Optional[SSN] = Field(None, description="SSN from VLP section")
    dob: Optional[date] = Field(None, description="DOB from VLP section")
    name: Optional[PersonName] = Field(None, description="Name from VLP section")
    
    @model_validator(mode='before')
    @classmethod
    def validate_vlp_consistency(cls, values):
        present = values.get('present', False)
        signed = values.get('signed')
        
        if present and signed is None:
            raise ValueError("If VLP section is present, signed status must be specified")
        
        return values


class DocumentMetadata(BaseModel):
    """Document processing metadata."""
    document_type: Optional[str] = Field(None, description="Type of document")
    completion_status: ProcessingStatus = Field(default=ProcessingStatus.PENDING, description="Processing status")
    pages_processed: Optional[int] = Field(None, ge=0, description="Number of pages processed")
    extraction_confidence: Optional[str] = Field(None, description="Confidence in extraction quality")
    extraction_method: Optional[str] = Field(None, description="Method used for extraction")
    processing_errors: List[str] = Field(default_factory=list, description="List of processing errors")
    
    @validator('extraction_confidence')
    def validate_confidence(cls, v):
        if v:
            valid_levels = ['low', 'medium', 'high']
            if v.lower() not in valid_levels:
                raise ValueError(f"Confidence must be one of: {valid_levels}")
            return v.lower()
        return v


class ContractData(TimestampedModel):
    """Complete contract data model with validation."""
    
    # Network information
    sender_ip: Optional[IPv4Address] = Field(None, description="IP address of document sender")
    signer_ip: Optional[IPv4Address] = Field(None, description="IP address of document signer")
    
    # Address and personal info
    mailing_address: Optional[MailingAddress] = Field(None, description="Mailing address")
    signatures: Optional[Signatures] = Field(None, description="Document signatures")
    
    # Financial information
    bank_details: Optional[BankDetails] = Field(None, description="Bank account details")
    
    # Document sections
    agreement: Optional[Agreement] = Field(None, description="Agreement section data")
    gateway: Optional[Gateway] = Field(None, description="Payment gateway section data")
    legal_plan: Optional[LegalPlan] = Field(None, description="Legal plan section data")
    vlp_section: Optional[VLPSection] = Field(None, description="VLP section data")
    
    # Metadata
    document_metadata: Optional[DocumentMetadata] = Field(None, description="Document processing metadata")
    extraction_source: str = Field(default="ai_parsing", description="Source of data extraction")
    validation_status: ValidationStatus = Field(default=ValidationStatus.PENDING, description="Validation status")
    
    @model_validator(mode='before')
    @classmethod
    def validate_ip_addresses(cls, values):
        sender_ip = values.get('sender_ip')
        signer_ip = values.get('signer_ip')
        
        if sender_ip and signer_ip and sender_ip == signer_ip:
            raise ValueError("Sender IP and signer IP must be different")
        
        return values
    
    @model_validator(mode='before')
    @classmethod
    def validate_ssn_consistency(cls, values):
        """Validate SSN consistency across all sections."""
        ssn_sources = []
        
        # Collect SSNs from different sections
        if values.get('agreement') and values['agreement'].ssn:
            ssn_sources.append(('agreement', values['agreement'].ssn.last_four))
        
        if values.get('gateway') and values['gateway'].ssn_last4:
            ssn_sources.append(('gateway', values['gateway'].ssn_last4))
        
        if values.get('legal_plan') and values['legal_plan'].ssn:
            ssn_sources.append(('legal_plan', values['legal_plan'].ssn.last_four))
        
        if values.get('vlp_section') and values['vlp_section'].ssn:
            ssn_sources.append(('vlp_section', values['vlp_section'].ssn.last_four))
        
        # Check consistency if we have multiple sources
        if len(ssn_sources) > 1:
            first_ssn = ssn_sources[0][1]
            for source, ssn in ssn_sources[1:]:
                if ssn != first_ssn:
                    raise ValueError(f"SSN mismatch between sections: {ssn_sources}")
        
        return values
    
    def get_validation_summary(self) -> Dict[str, Any]:
        """Get a summary of validation status."""
        return {
            "has_ip_addresses": bool(self.sender_ip and self.signer_ip),
            "ip_addresses_different": bool(
                self.sender_ip and self.signer_ip and self.sender_ip != self.signer_ip
            ),
            "has_signatures": bool(self.signatures and 
                                 (self.signatures.applicant or self.signatures.co_applicant)),
            "has_bank_details": bool(self.bank_details and 
                                   self.bank_details.account_number and 
                                   self.bank_details.routing_number),
            "has_mailing_address": bool(self.mailing_address and 
                                      self.mailing_address.street and 
                                      self.mailing_address.city),
            "validation_status": self.validation_status.value,
            "extraction_confidence": (
                self.document_metadata.extraction_confidence 
                if self.document_metadata else None
            )
        }


class ContractValidationResult(BaseModel):
    """Result of contract validation."""
    contract_id: Optional[str] = Field(None, description="Contract identifier")
    validation_checks: List[Dict[str, Any]] = Field(default_factory=list, description="Individual validation results")
    overall_status: ValidationStatus = Field(..., description="Overall validation status")
    confidence_score: Optional[float] = Field(None, ge=0, le=1, description="Overall confidence score")
    issues_found: List[str] = Field(default_factory=list, description="List of issues identified")
    recommendations: List[str] = Field(default_factory=list, description="Recommendations for improvement")
    validated_at: datetime = Field(default_factory=datetime.utcnow, description="Validation timestamp")
    
    def add_check_result(self, check_name: str, status: ValidationStatus, details: str, confidence: Optional[float] = None):
        """Add a validation check result."""
        self.validation_checks.append({
            "check_name": check_name,
            "status": status.value,
            "details": details,
            "confidence": confidence
        })
    
    @property
    def success_rate(self) -> float:
        """Calculate the success rate of validation checks."""
        if not self.validation_checks:
            return 0.0
        
        passed_checks = sum(1 for check in self.validation_checks if check["status"] == "pass")
        return (passed_checks / len(self.validation_checks)) * 100 