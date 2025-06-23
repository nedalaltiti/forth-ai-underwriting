"""
Validation models for budget analysis and debt validation.
Comprehensive Pydantic models for underwriting validation processes.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from decimal import Decimal
from enum import Enum
from pydantic import BaseModel, Field, validator, model_validator

from .base_models import TimestampedModel, ValidationStatus, FinancialAmount


class ValidationRequest(BaseModel):
    """Request model for validation operations."""
    contact_id: str = Field(..., description="Contact identifier")
    validation_types: List[str] = Field(..., description="Types of validation to perform")
    priority: str = Field(default="normal", description="Validation priority")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")


class ValidationResponse(BaseModel):
    """Response model for validation operations."""
    contact_id: str = Field(..., description="Contact identifier")
    validation_results: List[Dict[str, Any]] = Field(..., description="Validation results")
    overall_status: ValidationStatus = Field(..., description="Overall validation status")
    processed_at: datetime = Field(default_factory=datetime.utcnow)


class ValidationCheck(BaseModel):
    """Individual validation check result."""
    check_name: str = Field(..., description="Name of the validation check")
    status: ValidationStatus = Field(..., description="Check status")
    details: str = Field(..., description="Check details")
    confidence: Optional[float] = Field(None, ge=0, le=1, description="Confidence score")


class BudgetAnalysis(BaseModel):
    """Budget analysis validation model."""
    income_analysis: Dict[str, Any] = Field(..., description="Income analysis results")
    expense_analysis: Dict[str, Any] = Field(..., description="Expense analysis results")
    debt_analysis: Dict[str, Any] = Field(..., description="Debt analysis results")
    surplus_analysis: Dict[str, Any] = Field(..., description="Surplus analysis results")


class DebtValidation(BaseModel):
    """Debt validation model."""
    portfolio_summary: Dict[str, Any] = Field(..., description="Portfolio summary")
    debt_composition: Dict[str, Any] = Field(..., description="Debt composition analysis")
    creditor_analysis: Dict[str, Any] = Field(..., description="Creditor analysis")
    compliance_check: Dict[str, Any] = Field(..., description="Compliance check results")


class FinancialProfile(BaseModel):
    """Financial profile analysis model."""
    overall_assessment: Dict[str, Any] = Field(..., description="Overall assessment")
    financial_capacity: Dict[str, Any] = Field(..., description="Financial capacity analysis")
    risk_factors: Dict[str, Any] = Field(..., description="Risk factor analysis")
    recommendations: Dict[str, Any] = Field(..., description="Recommendations") 