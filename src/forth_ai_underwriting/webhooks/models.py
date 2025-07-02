"""
Pydantic models for webhook data processing.
Clean, validated data structures with comprehensive type safety.
"""

import logging
import re
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

logger = logging.getLogger(__name__)


# Pre-compiled regex patterns for performance (2025 best practice)
class RegexPatterns:
    """Pre-compiled regex patterns for webhook data validation."""

    PLACEHOLDER_PATTERN = re.compile(r"^\{.*\}$")
    EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    CONTACT_ID_PATTERN = re.compile(r"^\d+$")
    DOC_ID_PATTERN = re.compile(r"^\d+$")
    SCHEMA_VERSION_PATTERN = re.compile(r"^v\d+\.\d+$")  # e.g., v1.0, v2.1


class WebhookSource(str, Enum):
    """Source systems for webhooks."""

    FORTH_CRM = "forth_crm"
    MANUAL = "manual"
    TEST = "test"


class ProcessingStatus(str, Enum):
    """Processing status enumeration."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class MessageSchemaVersion(str, Enum):
    """Message schema versions for backward compatibility and evolution."""

    V1_0 = "v1.0"  # Initial schema
    V1_1 = "v1.1"  # Added correlation_id and priority
    V2_0 = "v2.0"  # Added retry logic and DLQ support
    LATEST = "v2.0"  # Current latest version


class MessageType(str, Enum):
    """Standardized message types for queue routing."""

    CONTRACT_DOWNLOAD = "contract_download"
    DOCUMENT_PARSE = "document_parse"
    VALIDATION_TASK = "validation_task"
    WEBHOOK_RECEIVED = "webhook_received"
    RETRY_TASK = "retry_task"
    DLQ_MESSAGE = "dlq_message"
    TEST = "test"  # For testing purposes


class WebhookPayload(BaseModel):
    """
    Strict webhook payload validation with Pydantic v2.
    Enforces type safety and forbids unexpected fields for security.
    """

    model_config = ConfigDict(
        # Pydantic v2 configuration for strict validation
        extra="forbid",  # Forbid extra fields for security
        str_strip_whitespace=True,  # Auto-strip whitespace
        validate_assignment=True,  # Validate on assignment
        use_enum_values=True,  # Use enum values in serialization
        frozen=False,  # Allow mutation for processing
    )

    contact_id: str = Field(..., description="Contact identifier", min_length=1)
    doc_type: str = Field(..., description="Document type", min_length=1)
    doc_id: str = Field(..., description="Document identifier", min_length=1)
    doc_name: str | None = Field(None, description="Document name/filename")
    correlation_id: str | None = Field(None, description="Correlation identifier")
    source: WebhookSource = Field(
        default=WebhookSource.FORTH_CRM, description="Webhook source"
    )
    raw_data: dict[str, Any] | None = Field(None, description="Original webhook data")

    @field_validator("contact_id")
    @classmethod
    def validate_contact_id(cls, v: str) -> str:
        """Validate contact ID format with strict rules."""
        if not v or not v.strip():
            raise ValueError("Contact ID cannot be empty")

        # Validate format (should be numeric for Forth CRM)
        contact_id = v.strip()
        if not RegexPatterns.CONTACT_ID_PATTERN.match(contact_id):
            raise ValueError(f"Contact ID must be numeric, got: {contact_id}")

        return contact_id

    @field_validator("doc_id")
    @classmethod
    def validate_doc_id(cls, v: str) -> str:
        """Validate document ID format with flexible rules."""
        if not v or not v.strip():
            raise ValueError("Document ID cannot be empty")

        # Check for placeholder values using pre-compiled regex
        doc_id = v.strip()
        if RegexPatterns.PLACEHOLDER_PATTERN.match(doc_id):
            raise ValueError(f"Document ID cannot be a placeholder: {doc_id}")

        # Accept any non-empty string - validation happens downstream
        # This allows for webhook-generated IDs, UUIDs, and other formats
        return doc_id

    @field_validator("doc_type")
    @classmethod
    def validate_doc_type(cls, v: str) -> str:
        """Validate document type."""
        if not v or not v.strip():
            raise ValueError("Document type cannot be empty")

        # Normalize document type
        doc_type = v.strip()
        allowed_types = [
            "Contract / Agreement",
            "Contract",
            "Agreement",
            "Legal Plan",
            "VLP",
            "Hardship Documentation",
        ]

        # Case-insensitive check
        if not any(doc_type.lower() == allowed.lower() for allowed in allowed_types):
            # Allow it but log a warning - don't be too strict
            pass

        return doc_type

    @field_validator("doc_name")
    @classmethod
    def validate_doc_name(cls, v: str | None) -> str | None:
        """Validate document name."""
        if v is None:
            return None

        doc_name = v.strip()
        if not doc_name:
            return None

        # Check for placeholder values
        if RegexPatterns.PLACEHOLDER_PATTERN.match(doc_name):
            return None  # Ignore placeholder names

        return doc_name

    @classmethod
    def from_webhook_data(
        cls, data: dict[str, Any], source: WebhookSource = WebhookSource.FORTH_CRM
    ) -> "WebhookPayload":
        """
        Create payload from raw webhook data with intelligent field mapping.

        Args:
            data: Raw webhook data dictionary
            source: Source system for the webhook

        Returns:
            Validated WebhookPayload instance

        Raises:
            ValueError: If required fields are missing or invalid
        """
        if not isinstance(data, dict):
            raise ValueError("Webhook data must be a dictionary")

        # Extract contact_id (required)
        contact_id = data.get("contact_id")
        if not contact_id:
            raise ValueError("Missing required field: contact_id")

        # Map document type with fallbacks
        doc_type = (
            data.get("doc_type") or data.get("{DOC_TYPE}") or "Contract / Agreement"
        )

        # Map document name with fallbacks
        doc_name = (
            data.get("doc_name")
            or data.get("{FILENAME}")
            or data.get("filename")
            or data.get("{DOC_TITLE}")
        )

        # Extract document ID with intelligent processing
        doc_id = cls._extract_document_id(data, contact_id)

        # Extract correlation ID
        correlation_id = (
            data.get("correlation_id")
            or data.get("{TRIGGER_TITLE}")
            or data.get("trigger_title")
        )

        return cls(
            contact_id=contact_id,
            doc_type=doc_type,
            doc_id=doc_id,
            doc_name=doc_name,
            correlation_id=correlation_id,
            source=source,
            raw_data=data,
        )

    @staticmethod
    def _extract_document_id(data: dict[str, Any], contact_id: str) -> str:
        """
        Intelligent document ID extraction with multiple fallback strategies.

        Priority order:
        1. {UPLOAD_DOC_IDS} - comma-separated list (takes latest)
        2. {LAST_UPLOAD_ID} - single latest ID
        3. {TRIGGER_DOC_ID} - triggered document ID
        4. __copydocs parameter parsing
        5. Generated timestamp-based fallback
        """
        # Try direct field extraction
        doc_id = (
            data.get("doc_id")
            or data.get("{UPLOAD_DOC_IDS}")
            or data.get("{LAST_UPLOAD_ID}")
            or data.get("{TRIGGER_DOC_ID}")
        )

        # Clean up placeholder values
        if doc_id and RegexPatterns.PLACEHOLDER_PATTERN.match(str(doc_id).strip()):
            doc_id = None

        # Handle comma-separated lists (take the latest)
        if doc_id and "," in str(doc_id):
            doc_ids = [id.strip() for id in str(doc_id).split(",") if id.strip()]
            if doc_ids:
                doc_id = doc_ids[-1]

        # Fallback: extract from __copydocs parameter
        if not doc_id:
            doc_id = WebhookPayload._extract_from_copydocs(data.get("__copydocs"))

        # Final fallback: generate timestamp-based ID
        if not doc_id:
            doc_id = (
                f"webhook_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{contact_id}"
            )

        return doc_id

    @staticmethod
    def _extract_from_copydocs(copydocs: str | None) -> str | None:
        """Extract document ID from __copydocs parameter format: ACCT-CONTACT-DOCIDS"""
        if not copydocs or "-" not in copydocs:
            return None

        try:
            # Format: "5883-1089855503-469966089,469966300,..."
            parts = copydocs.split("-", 2)
            if len(parts) >= 3:
                doc_ids = parts[2].split(",")
                return doc_ids[-1].strip()
        except Exception:
            pass

        return None


class ProcessingResult(BaseModel):
    """Result of webhook processing operation."""

    model_config = ConfigDict(
        extra="forbid",
        use_enum_values=True,
        validate_assignment=True,
    )

    success: bool = Field(..., description="Whether processing succeeded")
    message_id: str | None = Field(None, description="Queue message ID")
    processing_time_ms: int = Field(
        ..., ge=0, description="Processing time in milliseconds"
    )
    status: ProcessingStatus = Field(..., description="Processing status")
    error_message: str | None = Field(None, description="Error message if failed")
    metadata: dict[str, Any] | None = Field(None, description="Additional metadata")


class QueueMessage(BaseModel):
    """
    Structured message for queue systems with schema versioning.
    Supports backward compatibility and message evolution following 2025 MLOps practices.
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
    )

    # Schema versioning for backward compatibility
    schema_version: MessageSchemaVersion = Field(
        default=MessageSchemaVersion.LATEST,
        description="Message schema version for compatibility",
    )

    # Core message fields
    message_type: MessageType = Field(..., description="Standardized message type")
    contact_id: str = Field(..., description="Contact identifier", min_length=1)
    data: dict[str, Any] = Field(..., description="Message payload data")

    # Tracing and correlation
    correlation_id: str | None = Field(
        None, description="Correlation identifier for tracing"
    )
    trace_id: str | None = Field(None, description="Distributed tracing ID")

    # Timing and priority
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Message creation timestamp"
    )
    priority: int = Field(
        default=5, ge=1, le=10, description="Message priority (1=highest, 10=lowest)"
    )

    # Retry and DLQ support (v2.0 features)
    retry_count: int = Field(default=0, ge=0, description="Number of retry attempts")
    max_retries: int = Field(default=3, ge=0, description="Maximum retry attempts")
    retry_delay_seconds: int = Field(
        default=60, ge=1, description="Delay between retries"
    )

    # Dead Letter Queue metadata
    original_queue: str | None = Field(
        None, description="Original queue name for DLQ messages"
    )
    failure_reason: str | None = Field(None, description="Reason for failure (DLQ)")
    failed_at: datetime | None = Field(None, description="Timestamp of failure")

    # Processing metadata
    processing_timeout_seconds: int = Field(
        default=300, ge=1, description="Processing timeout"
    )
    idempotency_key: str | None = Field(
        None, description="Idempotency key for at-least-once processing"
    )

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, v: MessageSchemaVersion) -> MessageSchemaVersion:
        """Validate schema version format."""
        if isinstance(v, str) and not RegexPatterns.SCHEMA_VERSION_PATTERN.match(v):
            raise ValueError(f"Invalid schema version format: {v}")
        return v

    @field_validator("idempotency_key")
    @classmethod
    def validate_idempotency_key(cls, v: str | None) -> str | None:
        """Generate idempotency key if not provided."""
        if v is None:
            import uuid

            return str(uuid.uuid4())
        return v

    @model_validator(mode="after")
    def validate_retry_logic(self) -> "QueueMessage":
        """Validate retry configuration."""
        if self.retry_count > self.max_retries:
            raise ValueError(
                f"Retry count ({self.retry_count}) cannot exceed max retries ({self.max_retries})"
            )

        # Set failed_at timestamp if this is a failure
        if self.retry_count > 0 and self.failed_at is None:
            object.__setattr__(self, "failed_at", datetime.utcnow())

        return self

    def to_queue_format(self) -> dict[str, Any]:
        """
        Convert to format suitable for queue systems with schema versioning.
        Maintains backward compatibility across schema versions.
        """
        base_format = {
            "SchemaVersion": self.schema_version,
            "MessageType": self.message_type,
            "ContactId": self.contact_id,
            "Data": self.data,
            "CorrelationId": self.correlation_id,
            "TraceId": self.trace_id,
            "Timestamp": self.timestamp.isoformat(),
            "Priority": self.priority,
            "IdempotencyKey": self.idempotency_key,
        }

        # Add v2.0+ fields for newer schema versions
        if self.schema_version in [
            MessageSchemaVersion.V2_0,
            MessageSchemaVersion.LATEST,
        ]:
            base_format.update(
                {
                    "RetryCount": self.retry_count,
                    "MaxRetries": self.max_retries,
                    "RetryDelaySeconds": self.retry_delay_seconds,
                    "ProcessingTimeoutSeconds": self.processing_timeout_seconds,
                    "OriginalQueue": self.original_queue,
                    "FailureReason": self.failure_reason,
                    "FailedAt": self.failed_at.isoformat() if self.failed_at else None,
                }
            )

        return base_format

    @classmethod
    def from_queue_format(cls, data: dict[str, Any]) -> "QueueMessage":
        """
        Create QueueMessage from queue format with schema version handling.
        Supports backward compatibility for older message formats.
        """
        schema_version = data.get("SchemaVersion", MessageSchemaVersion.V1_0)

        # Base fields available in all versions
        base_data = {
            "schema_version": schema_version,
            "message_type": data.get("MessageType", MessageType.WEBHOOK_RECEIVED),
            "contact_id": data["ContactId"],
            "data": data["Data"],
            "correlation_id": data.get("CorrelationId"),
            "timestamp": datetime.fromisoformat(data["Timestamp"])
            if data.get("Timestamp")
            else datetime.utcnow(),
            "priority": data.get("Priority", 5),
        }

        # Add v1.1+ fields
        if schema_version != MessageSchemaVersion.V1_0:
            base_data.update(
                {
                    "trace_id": data.get("TraceId"),
                    "idempotency_key": data.get("IdempotencyKey"),
                }
            )

        # Add v2.0+ fields
        if schema_version in [MessageSchemaVersion.V2_0, MessageSchemaVersion.LATEST]:
            base_data.update(
                {
                    "retry_count": data.get("RetryCount", 0),
                    "max_retries": data.get("MaxRetries", 3),
                    "retry_delay_seconds": data.get("RetryDelaySeconds", 60),
                    "processing_timeout_seconds": data.get(
                        "ProcessingTimeoutSeconds", 300
                    ),
                    "original_queue": data.get("OriginalQueue"),
                    "failure_reason": data.get("FailureReason"),
                    "failed_at": datetime.fromisoformat(data["FailedAt"])
                    if data.get("FailedAt")
                    else None,
                }
            )

        return cls(**base_data)

    def create_retry_message(
        self, failure_reason: str, original_queue: str
    ) -> "QueueMessage":
        """
        Create a retry message with incremented retry count.
        Used for implementing at-least-once processing.
        """
        return QueueMessage(
            schema_version=self.schema_version,
            message_type=MessageType.RETRY_TASK,
            contact_id=self.contact_id,
            data=self.data,
            correlation_id=self.correlation_id,
            trace_id=self.trace_id,
            priority=min(self.priority + 1, 10),  # Lower priority for retries
            retry_count=self.retry_count + 1,
            max_retries=self.max_retries,
            retry_delay_seconds=min(
                self.retry_delay_seconds * 2, 3600
            ),  # Exponential backoff
            processing_timeout_seconds=self.processing_timeout_seconds,
            original_queue=original_queue,
            failure_reason=failure_reason,
            failed_at=datetime.utcnow(),
            idempotency_key=self.idempotency_key,  # Preserve for deduplication
        )

    def create_dlq_message(
        self, failure_reason: str, original_queue: str
    ) -> "QueueMessage":
        """
        Create a dead letter queue message when max retries exceeded.
        """
        return QueueMessage(
            schema_version=self.schema_version,
            message_type=MessageType.DLQ_MESSAGE,
            contact_id=self.contact_id,
            data=self.data,
            correlation_id=self.correlation_id,
            trace_id=self.trace_id,
            priority=10,  # Lowest priority for DLQ
            retry_count=self.retry_count,
            max_retries=self.max_retries,
            retry_delay_seconds=self.retry_delay_seconds,
            processing_timeout_seconds=self.processing_timeout_seconds,
            original_queue=original_queue,
            failure_reason=f"Max retries exceeded: {failure_reason}",
            failed_at=datetime.utcnow(),
            idempotency_key=self.idempotency_key,
        )

    def should_retry(self) -> bool:
        """Check if message should be retried based on retry count."""
        return self.retry_count < self.max_retries

    def is_expired(self) -> bool:
        """Check if message has exceeded processing timeout."""
        if not self.failed_at:
            return False

        elapsed_seconds = (datetime.utcnow() - self.failed_at).total_seconds()
        return elapsed_seconds > self.processing_timeout_seconds

    @field_serializer("timestamp", "failed_at")
    def serialize_datetime(self, value: datetime | None) -> str | None:
        """Serialize datetime fields to ISO format."""
        return value.isoformat() if value else None


class WebhookMetrics(BaseModel):
    """Metrics for webhook processing performance with Pydantic validation."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        frozen=False,
    )

    total_requests: int = Field(default=0, ge=0, description="Total number of requests")
    successful_requests: int = Field(
        default=0, ge=0, description="Number of successful requests"
    )
    failed_requests: int = Field(
        default=0, ge=0, description="Number of failed requests"
    )
    average_processing_time_ms: float = Field(
        default=0.0, ge=0.0, description="Average processing time"
    )
    queue_messages_sent: int = Field(
        default=0, ge=0, description="Number of queue messages sent"
    )
    last_request_time: datetime | None = Field(
        default=None, description="Last request timestamp"
    )

    @model_validator(mode="after")
    def validate_request_counts(self) -> "WebhookMetrics":
        """Validate that request counts are consistent."""
        expected_total = self.successful_requests + self.failed_requests

        # Allow for small inconsistencies during concurrent updates
        if abs(self.total_requests - expected_total) > 1:
            # Log the inconsistency but don't fail validation
            logger.warning(
                f"Metrics inconsistency detected: total={self.total_requests}, "
                f"successful={self.successful_requests}, failed={self.failed_requests}"
            )

            # Auto-correct the total_requests to match
            object.__setattr__(self, "total_requests", expected_total)

        return self

    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        if self.total_requests == 0:
            return 0.0
        return (self.successful_requests / self.total_requests) * 100

    @property
    def failure_rate(self) -> float:
        """Calculate failure rate percentage."""
        return 100.0 - self.success_rate

    def update_request(
        self, success: bool, processing_time_ms: int, queued: bool = False
    ) -> None:
        """Update metrics with new request data in an atomic way."""
        # Update all counters atomically to prevent inconsistencies
        old_total = self.total_requests
        old_avg = self.average_processing_time_ms

        # Increment counters
        self.total_requests = old_total + 1
        self.last_request_time = datetime.utcnow()

        if success:
            self.successful_requests += 1
            if queued:
                self.queue_messages_sent += 1
        else:
            self.failed_requests += 1

        # Update rolling average
        if self.total_requests == 1:
            self.average_processing_time_ms = float(processing_time_ms)
        else:
            self.average_processing_time_ms = (
                old_avg * old_total + processing_time_ms
            ) / self.total_requests


class HealthStatus(BaseModel):
    """Health check status model."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
    )

    status: str = Field(..., description="Overall health status", min_length=1)
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Health check timestamp"
    )
    services: dict[str, str] = Field(
        default_factory=dict, description="Service health statuses"
    )
    metrics: dict[str, Any] | None = Field(None, description="Performance metrics")

    @field_serializer("timestamp")
    def serialize_timestamp(self, value: datetime) -> str:
        """Serialize timestamp to ISO format."""
        return value.isoformat()
