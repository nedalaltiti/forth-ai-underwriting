"""
Custom exception classes for the Forth AI Underwriting System.
"""

from typing import Any, Dict, Optional
from fastapi import HTTPException
from starlette.status import (
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
    HTTP_409_CONFLICT,
    HTTP_422_UNPROCESSABLE_ENTITY,
    HTTP_429_TOO_MANY_REQUESTS,
    HTTP_500_INTERNAL_SERVER_ERROR,
    HTTP_503_SERVICE_UNAVAILABLE
)


class BaseUnderwritingException(Exception):
    """Base exception for all underwriting system errors."""
    
    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)


class ValidationError(BaseUnderwritingException):
    """Raised when validation fails."""
    pass


class ContactNotFoundError(BaseUnderwritingException):
    """Raised when a contact is not found."""
    pass


class DocumentProcessingError(BaseUnderwritingException):
    """Raised when document processing fails."""
    pass


class AIParsingError(BaseUnderwritingException):
    """Raised when AI parsing fails."""
    pass


class AIProviderError(BaseUnderwritingException):
    """Raised when AI provider operations fail."""
    pass


class CacheError(BaseUnderwritingException):
    """Raised when cache operations fail."""
    pass


class DatabaseError(BaseUnderwritingException):
    """Raised when database operations fail."""
    pass


class AuthenticationError(BaseUnderwritingException):
    """Raised when authentication fails."""
    pass


class AuthorizationError(BaseUnderwritingException):
    """Raised when authorization fails."""
    pass


class RateLimitError(BaseUnderwritingException):
    """Raised when rate limit is exceeded."""
    pass


class ExternalAPIError(BaseUnderwritingException):
    """Raised when external API calls fail."""
    pass


class ConfigurationError(BaseUnderwritingException):
    """Raised when configuration is invalid."""
    pass


# HTTP Exception mapping
class HTTPExceptionHandler:
    """Handles conversion of custom exceptions to HTTP exceptions."""
    
    EXCEPTION_MAP = {
        ValidationError: HTTP_400_BAD_REQUEST,
        ContactNotFoundError: HTTP_404_NOT_FOUND,
        DocumentProcessingError: HTTP_422_UNPROCESSABLE_ENTITY,
        AIParsingError: HTTP_422_UNPROCESSABLE_ENTITY,
        AIProviderError: HTTP_503_SERVICE_UNAVAILABLE,
        CacheError: HTTP_500_INTERNAL_SERVER_ERROR,
        DatabaseError: HTTP_500_INTERNAL_SERVER_ERROR,
        AuthenticationError: HTTP_401_UNAUTHORIZED,
        AuthorizationError: HTTP_403_FORBIDDEN,
        RateLimitError: HTTP_429_TOO_MANY_REQUESTS,
        ExternalAPIError: HTTP_503_SERVICE_UNAVAILABLE,
        ConfigurationError: HTTP_500_INTERNAL_SERVER_ERROR,
    }
    
    @classmethod
    def to_http_exception(cls, exc: BaseUnderwritingException) -> HTTPException:
        """Convert custom exception to HTTP exception."""
        status_code = cls.EXCEPTION_MAP.get(type(exc), HTTP_500_INTERNAL_SERVER_ERROR)
        
        detail = {
            "error_code": exc.error_code or type(exc).__name__,
            "message": exc.message,
            "details": exc.details
        }
        
        return HTTPException(status_code=status_code, detail=detail)


# Specific error factory functions
def create_validation_error(message: str, contact_id: str = None, check_type: str = None) -> ValidationError:
    """Create a validation error with context."""
    details = {}
    if contact_id:
        details["contact_id"] = contact_id
    if check_type:
        details["check_type"] = check_type
    
    return ValidationError(
        message=message,
        error_code="VALIDATION_FAILED",
        details=details
    )


def create_contact_not_found_error(contact_id: str) -> ContactNotFoundError:
    """Create a contact not found error."""
    return ContactNotFoundError(
        message=f"Contact with ID '{contact_id}' not found",
        error_code="CONTACT_NOT_FOUND",
        details={"contact_id": contact_id}
    )


def create_document_processing_error(document_id: str, reason: str) -> DocumentProcessingError:
    """Create a document processing error."""
    return DocumentProcessingError(
        message=f"Failed to process document: {reason}",
        error_code="DOCUMENT_PROCESSING_FAILED",
        details={"document_id": document_id, "reason": reason}
    )


def create_ai_parsing_error(document_url: str, provider: str, reason: str) -> AIParsingError:
    """Create an AI parsing error."""
    return AIParsingError(
        message=f"AI parsing failed for document: {reason}",
        error_code="AI_PARSING_FAILED",
        details={"document_url": document_url, "provider": provider, "reason": reason}
    )


def create_rate_limit_error(limit: int, window: int, identifier: str) -> RateLimitError:
    """Create a rate limit error."""
    return RateLimitError(
        message=f"Rate limit exceeded: {limit} requests per {window} seconds",
        error_code="RATE_LIMIT_EXCEEDED",
        details={"limit": limit, "window": window, "identifier": identifier}
    )


def create_external_api_error(api_name: str, status_code: int, reason: str) -> ExternalAPIError:
    """Create an external API error."""
    return ExternalAPIError(
        message=f"External API '{api_name}' failed: {reason}",
        error_code="EXTERNAL_API_FAILED",
        details={"api_name": api_name, "status_code": status_code, "reason": reason}
    ) 