"""
Shared Models - Common data structures used across microservices.
Minimal shared models following microservices best practices.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ServiceStatus(str, Enum):
    """Standard service status enumeration."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class ProcessingStatus(str, Enum):
    """Processing status enumeration."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ValidationStatus(str, Enum):
    """Validation result status."""

    PASS = "Pass"
    NO_PASS = "No Pass"
    PENDING = "Pending"


class WebhookPayload(BaseModel):
    """Webhook payload model shared between services."""

    contact_id: str = Field(..., description="Contact identifier")
    doc_id: str = Field(..., description="Document identifier")
    doc_type: str = Field(..., description="Document type")
    doc_name: str | None = Field(None, description="Document filename")
    correlation_id: str | None = Field(None, description="Correlation ID for tracing")

    @classmethod
    def from_webhook_data(cls, data: dict[str, Any]) -> "WebhookPayload":
        """Create payload from raw webhook data."""
        return cls(
            contact_id=str(data.get("contact_id", "")),
            doc_id=str(data.get("doc_id", "")),
            doc_type=str(data.get("doc_type", "Contract")),
            doc_name=data.get("doc_name"),
            correlation_id=data.get("correlation_id"),
        )


class QueueMessage(BaseModel):
    """Standard queue message format."""

    message_type: str = Field(..., description="Message type identifier")
    contact_id: str = Field(..., description="Contact identifier")
    data: dict[str, Any] = Field(..., description="Message payload")
    correlation_id: str | None = Field(None, description="Correlation ID")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Message timestamp"
    )
    retry_count: int = Field(default=0, description="Retry attempt count")


class ProcessingResult(BaseModel):
    """Standard processing result."""

    success: bool = Field(..., description="Whether processing succeeded")
    message_id: str | None = Field(None, description="Queue message ID")
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")
    status: ProcessingStatus = Field(..., description="Processing status")
    error_message: str | None = Field(None, description="Error message if failed")
    metadata: dict[str, Any] | None = Field(None, description="Additional metadata")


class ValidationResult(BaseModel):
    """Individual validation check result."""

    title: str = Field(..., description="Validation check title")
    result: ValidationStatus = Field(..., description="Validation result")
    reason: str = Field(..., description="Validation reasoning")
    confidence: float | None = Field(None, description="Confidence score")


class ValidationRequest(BaseModel):
    """Validation service request."""

    contact_id: str = Field(..., description="Contact identifier")
    validation_types: list[str] = Field(
        default=["all"], description="Types of validation to perform"
    )
    context: dict[str, Any] | None = Field(None, description="Additional context")


class ValidationResponse(BaseModel):
    """Validation service response."""

    contact_id: str = Field(..., description="Contact identifier")
    validation_results: list[dict[str, Any]] = Field(
        ..., description="Validation results"
    )
    overall_status: str = Field(..., description="Overall validation status")
    processed_at: datetime = Field(
        default_factory=datetime.utcnow, description="Processing timestamp"
    )


class HealthStatus(BaseModel):
    """Standard health check response."""

    service: str = Field(..., description="Service name")
    status: ServiceStatus = Field(..., description="Service status")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Health check timestamp"
    )
    details: dict[str, Any] | None = Field(
        None, description="Additional health details"
    )
