"""
Base Pydantic models for the underwriting system.
Provides common models and validation patterns used throughout the application.
"""

from typing import Any, Dict, List, Optional, Generic, TypeVar, Union, Literal
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from pydantic import BaseModel, Field, validator, model_validator
import re

T = TypeVar('T')


class ValidationStatus(str, Enum):
    """Status values for validation results."""
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"
    PENDING = "pending"
    ERROR = "error"


class ProcessingStatus(str, Enum):
    """Status values for processing operations."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ConfidenceLevel(str, Enum):
    """Confidence levels for AI assessments."""
    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


class TimestampedModel(BaseModel):
    """Base model with automatic timestamp fields."""
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    
    def update_timestamp(self):
        """Update the updated_at timestamp."""
        self.updated_at = datetime.utcnow()


class BaseResponse(BaseModel):
    """Base response model for API responses."""
    success: bool = Field(..., description="Whether the operation was successful")
    message: Optional[str] = Field(None, description="Human-readable message")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")
    request_id: Optional[str] = Field(None, description="Unique request identifier")
    
    class Config:
        extra = "forbid"
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat(),
            Decimal: lambda v: float(v)
        }


class SuccessResponse(BaseResponse):
    """Success response model."""
    success: Literal[True] = Field(default=True, description="Always True for success responses")
    data: Optional[Any] = Field(None, description="Response data")


class ErrorResponse(BaseResponse):
    """Error response model."""
    success: Literal[False] = Field(default=False, description="Always False for error responses")
    error_code: Optional[str] = Field(None, description="Machine-readable error code")
    error_details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    
    @validator('message')
    def validate_error_message(cls, v):
        if not v:
            return "An error occurred"
        return v


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response model."""
    items: List[T] = Field(..., description="List of items")
    total_count: int = Field(..., ge=0, description="Total number of items")
    page: int = Field(..., ge=1, description="Current page number")
    page_size: int = Field(..., ge=1, le=1000, description="Number of items per page")
    total_pages: int = Field(..., ge=0, description="Total number of pages")
    has_next: bool = Field(..., description="Whether there are more pages")
    has_previous: bool = Field(..., description="Whether there are previous pages")
    
    @model_validator(mode='before')
    @classmethod
    def validate_pagination(cls, values):
        total_count = values.get('total_count', 0)
        page_size = values.get('page_size', 1)
        page = values.get('page', 1)
        
        # Calculate total pages
        total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 0
        values['total_pages'] = total_pages
        
        # Calculate has_next and has_previous
        values['has_next'] = page < total_pages
        values['has_previous'] = page > 1
        
        return values


class AddressModel(BaseModel):
    """Base address model with validation."""
    street: Optional[str] = Field(None, max_length=255, description="Street address")
    city: Optional[str] = Field(None, max_length=100, description="City name")
    state: Optional[str] = Field(None, min_length=2, max_length=2, description="State abbreviation")
    zip_code: Optional[str] = Field(None, description="ZIP code")
    country: str = Field(default="US", description="Country code")
    
    @validator('state')
    def validate_state(cls, v):
        if v:
            return v.upper()
        return v
    
    @validator('zip_code')
    def validate_zip_code(cls, v):
        if v:
            # Remove any non-digit characters and validate format
            clean_zip = re.sub(r'\D', '', v)
            if len(clean_zip) not in [5, 9]:
                raise ValueError("ZIP code must be 5 or 9 digits")
            # Format as XXXXX or XXXXX-XXXX
            if len(clean_zip) == 9:
                return f"{clean_zip[:5]}-{clean_zip[5:]}"
            return clean_zip
        return v


class FinancialAmount(BaseModel):
    """Model for financial amounts with validation."""
    amount: Decimal = Field(..., ge=0, decimal_places=2, description="Monetary amount")
    currency: str = Field(default="USD", description="Currency code")
    
    @validator('amount', pre=True)
    def validate_amount(cls, v):
        if isinstance(v, (int, float)):
            return Decimal(str(v))
        elif isinstance(v, str):
            # Remove currency symbols and commas
            clean_amount = re.sub(r'[^\d.]', '', v)
            return Decimal(clean_amount) if clean_amount else Decimal('0')
        return v
    
    def __str__(self):
        return f"{self.currency} {self.amount:.2f}"


class PersonName(BaseModel):
    """Model for person names with validation."""
    first_name: str = Field(..., min_length=1, max_length=50, description="First name")
    middle_name: Optional[str] = Field(None, max_length=50, description="Middle name")
    last_name: str = Field(..., min_length=1, max_length=50, description="Last name")
    suffix: Optional[str] = Field(None, max_length=10, description="Name suffix (Jr, Sr, etc)")
    
    @validator('first_name', 'last_name', 'middle_name', 'suffix')
    def validate_name_parts(cls, v):
        if v:
            # Remove extra whitespace and validate characters
            cleaned = re.sub(r'\s+', ' ', v.strip())
            if not re.match(r'^[a-zA-Z\s\'-]+$', cleaned):
                raise ValueError("Name can only contain letters, spaces, hyphens, and apostrophes")
            return cleaned.title()
        return v
    
    @property
    def full_name(self) -> str:
        """Get formatted full name."""
        parts = [self.first_name]
        if self.middle_name:
            parts.append(self.middle_name)
        parts.append(self.last_name)
        if self.suffix:
            parts.append(self.suffix)
        return " ".join(parts)


class SSN(BaseModel):
    """Model for Social Security Number with validation."""
    value: str = Field(..., description="SSN value")
    masked: bool = Field(default=True, description="Whether SSN should be masked in output")
    
    @validator('value')
    def validate_ssn(cls, v):
        if not v:
            raise ValueError("SSN cannot be empty")
        
        # Remove any non-digit characters
        digits = re.sub(r'\D', '', v)
        
        # Validate length
        if len(digits) not in [4, 9]:
            raise ValueError("SSN must be 4 digits (last 4) or 9 digits (full)")
        
        # Format appropriately
        if len(digits) == 9:
            return f"{digits[:3]}-{digits[3:5]}-{digits[5:]}"
        else:
            return digits  # Last 4 digits only
    
    @property
    def last_four(self) -> str:
        """Get last 4 digits of SSN."""
        digits = re.sub(r'\D', '', self.value)
        return digits[-4:] if len(digits) >= 4 else digits
    
    @property
    def masked_value(self) -> str:
        """Get masked SSN for display."""
        if len(self.value) == 4:
            return f"XXX-XX-{self.value}"
        else:
            return f"XXX-XX-{self.last_four}"
    
    def __str__(self):
        return self.masked_value if self.masked else self.value


class PhoneNumber(BaseModel):
    """Model for phone numbers with validation."""
    number: str = Field(..., description="Phone number")
    type: Optional[str] = Field(None, description="Phone type (mobile, home, work)")
    
    @validator('number')
    def validate_phone(cls, v):
        if not v:
            raise ValueError("Phone number cannot be empty")
        
        # Remove all non-digit characters
        digits = re.sub(r'\D', '', v)
        
        # Validate US phone number
        if len(digits) == 10:
            return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
        elif len(digits) == 11 and digits[0] == '1':
            return f"1-({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
        else:
            raise ValueError("Invalid phone number format")
    
    @property
    def digits_only(self) -> str:
        """Get phone number as digits only."""
        return re.sub(r'\D', '', self.number)


class EmailAddress(BaseModel):
    """Model for email addresses with validation."""
    email: str = Field(..., description="Email address")
    verified: bool = Field(default=False, description="Whether email is verified")
    
    @validator('email')
    def validate_email(cls, v):
        if not v:
            raise ValueError("Email cannot be empty")
        
        # Basic email validation
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, v.lower()):
            raise ValueError("Invalid email format")
        
        return v.lower()


class ValidationMetrics(BaseModel):
    """Model for validation performance metrics."""
    total_checks: int = Field(..., ge=0, description="Total number of validation checks")
    passed_checks: int = Field(..., ge=0, description="Number of passed checks")
    failed_checks: int = Field(..., ge=0, description="Number of failed checks")
    warning_checks: int = Field(..., ge=0, description="Number of warning checks")
    processing_time_ms: Optional[int] = Field(None, ge=0, description="Processing time in milliseconds")
    
    @model_validator(mode='before')
    @classmethod
    def validate_check_counts(cls, values):
        total = values.get('total_checks', 0)
        passed = values.get('passed_checks', 0)
        failed = values.get('failed_checks', 0)
        warnings = values.get('warning_checks', 0)
        
        if passed + failed + warnings != total:
            raise ValueError("Sum of individual check counts must equal total checks")
        
        return values
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_checks == 0:
            return 0.0
        return (self.passed_checks / self.total_checks) * 100
    
    @property
    def failure_rate(self) -> float:
        """Calculate failure rate as percentage."""
        if self.total_checks == 0:
            return 0.0
        return (self.failed_checks / self.total_checks) * 100 