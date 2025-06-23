"""
Client and contact models with comprehensive Pydantic validation.
Models for client profiles, contact information, and financial data.
"""

from typing import Dict, Any, List, Optional
from datetime import date
from decimal import Decimal
from enum import Enum
from pydantic import BaseModel, Field, validator

from .base_models import (
    TimestampedModel, 
    AddressModel, 
    FinancialAmount, 
    PersonName, 
    SSN, 
    PhoneNumber, 
    EmailAddress
)


class ContactInformation(BaseModel):
    """Contact information model."""
    name: PersonName = Field(..., description="Person's name")
    email: Optional[EmailAddress] = Field(None, description="Email address")
    phone: Optional[PhoneNumber] = Field(None, description="Phone number")
    address: Optional[AddressModel] = Field(None, description="Mailing address")


class FinancialInformation(BaseModel):
    """Financial information model."""
    monthly_income: Optional[FinancialAmount] = Field(None, description="Monthly income")
    monthly_expenses: Optional[FinancialAmount] = Field(None, description="Monthly expenses")
    credit_score: Optional[int] = Field(None, ge=300, le=850, description="Credit score")
    debt_to_income_ratio: Optional[float] = Field(None, ge=0, le=200, description="DTI ratio as percentage")


class DebtAccount(BaseModel):
    """Individual debt account model."""
    creditor_name: str = Field(..., description="Name of creditor")
    debt_amount: FinancialAmount = Field(..., description="Outstanding debt amount")
    debt_type: str = Field(..., description="Type of debt")
    account_status: str = Field(..., description="Current account status")


class IncomeSource(BaseModel):
    """Income source model."""
    source_type: str = Field(..., description="Type of income source")
    amount: FinancialAmount = Field(..., description="Income amount")
    frequency: str = Field(..., description="Payment frequency")


class ExpenseCategory(BaseModel):
    """Expense category model."""
    category: str = Field(..., description="Expense category")
    amount: FinancialAmount = Field(..., description="Expense amount")
    is_essential: bool = Field(..., description="Whether expense is essential")


class ClientProfile(TimestampedModel):
    """Complete client profile model."""
    client_id: str = Field(..., description="Client identifier")
    contact_info: ContactInformation = Field(..., description="Contact information")
    financial_info: Optional[FinancialInformation] = Field(None, description="Financial information")
    debt_accounts: List[DebtAccount] = Field(default_factory=list, description="Debt accounts")
    income_sources: List[IncomeSource] = Field(default_factory=list, description="Income sources")
    expense_categories: List[ExpenseCategory] = Field(default_factory=list, description="Expense categories") 