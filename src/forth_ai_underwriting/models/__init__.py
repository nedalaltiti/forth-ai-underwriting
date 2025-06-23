"""
Pydantic models for data validation and serialization.
Comprehensive data models for all aspects of the underwriting system.
"""

from .contract_models import (
    ContractData,
    MailingAddress,
    Signatures,
    BankDetails,
    Agreement,
    Gateway,
    LegalPlan,
    VLPSection,
    DocumentMetadata
)

from .hardship_models import (
    HardshipAssessment,
    HardshipAnalysis,
    DescriptionQuality,
    AssessmentResult,
    HardshipRecommendations
)

from .validation_models import (
    ValidationRequest,
    ValidationResponse,
    ValidationCheck,
    BudgetAnalysis,
    DebtValidation,
    FinancialProfile
)

from .base_models import (
    BaseResponse,
    ErrorResponse,
    SuccessResponse,
    PaginatedResponse,
    TimestampedModel
)

from .client_models import (
    ClientProfile,
    ContactInformation,
    FinancialInformation,
    DebtAccount,
    IncomeSource,
    ExpenseCategory
)

__all__ = [
    # Contract models
    "ContractData",
    "MailingAddress", 
    "Signatures",
    "BankDetails",
    "Agreement",
    "Gateway",
    "LegalPlan",
    "VLPSection",
    "DocumentMetadata",
    
    # Hardship models
    "HardshipAssessment",
    "HardshipAnalysis",
    "DescriptionQuality",
    "AssessmentResult",
    "HardshipRecommendations",
    
    # Validation models
    "ValidationRequest",
    "ValidationResponse",
    "ValidationCheck",
    "BudgetAnalysis",
    "DebtValidation",
    "FinancialProfile",
    
    # Base models
    "BaseResponse",
    "ErrorResponse",
    "SuccessResponse",
    "PaginatedResponse",
    "TimestampedModel",
    
    # Client models
    "ClientProfile",
    "ContactInformation",
    "FinancialInformation",
    "DebtAccount",
    "IncomeSource",
    "ExpenseCategory"
] 