"""
Service classes for webhook processing.
Clean separation of concerns with async support and dependency injection.
"""

import time
import uuid
from typing import Any

from loguru import logger

from ..infrastructure.external_apis import ForthAPIClient
from ..infrastructure.queue import QueueAdapter
from .models import (
    ProcessingResult,
    ProcessingStatus,
    QueueMessage,
    WebhookMetrics,
    WebhookPayload,
)


class DocumentExtractor:
    """Service for extracting document information from external APIs."""

    def __init__(self, forth_client: ForthAPIClient | None = None):
        """Initialize document extractor with optional Forth API client."""
        self.forth_client = forth_client or ForthAPIClient()

    async def get_real_document_id(self, contact_id: str, filename: str) -> str | None:
        """
        Attempt to fetch real document ID from Forth API.

        Args:
            contact_id: Contact identifier
            filename: Document filename to search for

        Returns:
            Document ID if found, None otherwise
        """
        try:
            if not self.forth_client:
                logger.debug("No Forth API client configured")
                return None

            logger.info(
                f"Attempting to fetch document ID for contact {contact_id}, filename: {filename}"
            )

            async with self.forth_client as client:
                doc_id = await client.find_document_url(contact_id, filename)
                if doc_id:
                    logger.info(f"✅ Found document ID: {doc_id}")
                    return doc_id
                else:
                    logger.warning(f"❌ Document not found for filename: {filename}")
                    return None

        except Exception as e:
            logger.error(f"Error fetching document ID: {e}")
            return None


class WebhookProcessor:
    """
    Main webhook processing service with metrics and async queue handling.
    Follows dependency injection pattern for testability.
    """

    def __init__(
        self,
        queue_adapter: QueueAdapter,
        document_extractor: DocumentExtractor | None = None,
    ):
        """
        Initialize webhook processor with dependencies.

        Args:
            queue_adapter: Queue service for message handling
            document_extractor: Service for document ID extraction
        """
        self.queue_adapter = queue_adapter
        self.document_extractor = document_extractor or DocumentExtractor()
        self.metrics = WebhookMetrics()

        logger.info("WebhookProcessor initialized with async queue support")

    async def process_webhook(self, payload: WebhookPayload) -> ProcessingResult:
        """
        Process webhook payload with comprehensive error handling and metrics.

        Args:
            payload: Validated webhook payload

        Returns:
            Processing result with status and metadata
        """
        start_time = time.time()

        try:
            logger.info(
                f"Processing webhook: contact_id={payload.contact_id}, "
                f"doc_type={payload.doc_type}, doc_id={payload.doc_id}"
            )

            # Attempt document ID enhancement if needed
            enhanced_doc_id = await self._enhance_document_id(payload)

            # Create queue message
            message = QueueMessage(
                message_type="contract_download",
                contact_id=payload.contact_id,
                data={
                    "doc_id": enhanced_doc_id or payload.doc_id,
                    "doc_type": payload.doc_type,
                    "doc_name": payload.doc_name,
                    "source": payload.source,
                },
                correlation_id=payload.correlation_id,
                idempotency_key=uuid.uuid4().hex,
            )

            # Send to queue (async)
            message_id = await self._send_to_queue(message)

            # Calculate processing time
            processing_time_ms = int((time.time() - start_time) * 1000)

            # Create successful result
            result = ProcessingResult(
                success=True,
                message_id=message_id,
                processing_time_ms=processing_time_ms,
                status=ProcessingStatus.COMPLETED,
                metadata={
                    "queue_name": self.queue_adapter.queue_name,
                    "enhanced_doc_id": enhanced_doc_id != payload.doc_id
                    if enhanced_doc_id
                    else False,
                },
            )

            # Update metrics
            self.metrics.update_request(
                success=True, processing_time_ms=processing_time_ms, queued=True
            )

            logger.info(f"✅ Webhook processed successfully: {result.model_dump()}")
            return result

        except Exception as e:
            processing_time_ms = int((time.time() - start_time) * 1000)

            logger.error(f"❌ Webhook processing failed: {e}")

            # Update metrics for failure
            self.metrics.update_request(
                success=False, processing_time_ms=processing_time_ms
            )

            return ProcessingResult(
                success=False,
                processing_time_ms=processing_time_ms,
                status=ProcessingStatus.FAILED,
                error_message=str(e),
            )

    async def _enhance_document_id(self, payload: WebhookPayload) -> str | None:
        """
        Attempt to enhance document ID using external APIs.

        Args:
            payload: Webhook payload

        Returns:
            Enhanced document ID or None if enhancement failed
        """
        # Skip enhancement if we already have a good doc_id
        if (
            payload.doc_id
            and not payload.doc_id.startswith("webhook_")
            and payload.doc_id.isdigit()
        ):
            return payload.doc_id

        # Attempt to get real document ID
        if payload.doc_name:
            real_doc_id = await self.document_extractor.get_real_document_id(
                payload.contact_id, payload.doc_name
            )
            if real_doc_id:
                return real_doc_id

        return None

    async def _send_to_queue(self, message: QueueMessage) -> str:
        """
        Send message to queue with proper async handling.

        Args:
            message: Queue message to send

        Returns:
            Message ID from queue system

        Raises:
            Exception: If queue operation fails
        """
        try:
            message_id = await self.queue_adapter.send_message(message)
            logger.info(f"✅ Message sent to queue: {message_id}")
            return message_id
        except Exception as e:
            logger.error(f"❌ Failed to send message to queue: {e}")
            raise

    def get_metrics(self) -> dict[str, Any]:
        """Get current processing metrics."""
        return {
            "total_requests": self.metrics.total_requests,
            "successful_requests": self.metrics.successful_requests,
            "failed_requests": self.metrics.failed_requests,
            "success_rate": self.metrics.success_rate,
            "average_processing_time_ms": self.metrics.average_processing_time_ms,
            "queue_messages_sent": self.metrics.queue_messages_sent,
            "last_request_time": self.metrics.last_request_time.isoformat()
            if self.metrics.last_request_time
            else None,
        }

    async def health_check(self) -> dict[str, Any]:
        """
        Perform health check on all dependencies.

        Returns:
            Health status of processor and dependencies
        """
        health = {
            "status": "healthy",
            "processor": "active",
            "queue": "unknown",
            "document_extractor": "active",
        }

        try:
            # Check queue health
            queue_health = await self.queue_adapter.health_check()
            health["queue"] = (
                "healthy" if queue_health.get("accessible", False) else "unhealthy"
            )

        except Exception as e:
            logger.warning(f"Queue health check failed: {e}")
            health["queue"] = "unhealthy"
            health["status"] = "degraded"

        return health


class WebhookProcessorFactory:
    """Factory for creating webhook processors with proper dependency injection."""

    @staticmethod
    def create_processor(
        queue_name: str,
        forth_api_config: dict[str, str] | None = None,
        use_local_queue: bool = False,
        aws_region: str = "us-west-1",
    ) -> WebhookProcessor:
        """
        Create webhook processor with all dependencies.

        Args:
            queue_name: Name of the queue to use
            forth_api_config: Configuration for Forth API client
            use_local_queue: Whether to use local queue instead of SQS
            aws_region: AWS region for SQS

        Returns:
            Configured WebhookProcessor instance
        """
        # Create queue adapter
        from ..infrastructure.queue import create_queue_adapter

        queue_adapter = create_queue_adapter(
            queue_name=queue_name, use_local=use_local_queue, region=aws_region
        )

        # Create document extractor with API client
        document_extractor = None
        if forth_api_config:
            from ..infrastructure.external_apis import ForthAPIClient

            forth_client = ForthAPIClient(
                base_url=forth_api_config.get("base_url"),
                api_key=forth_api_config.get("api_key"),
                api_key_id=forth_api_config.get("api_key_id"),
            )
            document_extractor = DocumentExtractor(forth_client)

        return WebhookProcessor(
            queue_adapter=queue_adapter, document_extractor=document_extractor
        )
