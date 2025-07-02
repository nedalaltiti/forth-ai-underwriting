"""
Webhook Processor - Core business logic for webhook processing.
Handles webhook validation, queuing, and metrics.
"""

import time
from datetime import datetime
from typing import Any

from loguru import logger
from models import ProcessingResult, QueueMessage, WebhookPayload
from queue_adapter import create_queue_adapter


class WebhookProcessor:
    """
    Core webhook processing business logic.
    Focused solely on webhook ingestion and queuing.
    """

    def __init__(self, config):
        self.config = config
        self.queue_adapter = None
        self.metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "average_processing_time_ms": 0.0,
            "last_request_time": None,
        }

    async def _ensure_queue_adapter(self):
        """Lazy initialization of queue adapter."""
        if self.queue_adapter is None:
            self.queue_adapter = create_queue_adapter(
                queue_name=self.config.queue_name,
                use_local=self.config.use_local_queue,
                region=self.config.aws_region,
                aws_access_key=self.config.aws_access_key_id,
                aws_secret_key=self.config.aws_secret_access_key,
            )

    async def process_webhook(self, payload: WebhookPayload) -> ProcessingResult:
        """
        Process webhook payload and queue for document processing.

        Args:
            payload: Validated webhook payload

        Returns:
            Processing result with success status and metadata
        """
        start_time = time.time()

        try:
            # Ensure queue adapter is initialized
            await self._ensure_queue_adapter()

            # Create queue message
            message = QueueMessage(
                message_type="contract_download",
                contact_id=payload.contact_id,
                data={
                    "contact_id": payload.contact_id,
                    "doc_id": payload.doc_id,
                    "doc_type": payload.doc_type,
                    "doc_name": payload.doc_name,
                    "correlation_id": payload.correlation_id,
                },
                correlation_id=payload.correlation_id,
                timestamp=datetime.utcnow(),
            )

            # Send to queue
            message_id = await self.queue_adapter.send_message(message)

            # Calculate processing time
            processing_time_ms = int((time.time() - start_time) * 1000)

            # Update metrics
            self._update_metrics(success=True, processing_time_ms=processing_time_ms)

            logger.info(
                f"✅ Webhook processed successfully: "
                f"contact_id={payload.contact_id}, doc_id={payload.doc_id}, "
                f"message_id={message_id}, processing_time={processing_time_ms}ms"
            )

            return ProcessingResult(
                success=True,
                message_id=message_id,
                processing_time_ms=processing_time_ms,
                status="completed",
                metadata={
                    "queue_name": self.config.queue_name,
                    "correlation_id": payload.correlation_id,
                },
            )

        except Exception as e:
            processing_time_ms = int((time.time() - start_time) * 1000)
            self._update_metrics(success=False, processing_time_ms=processing_time_ms)

            logger.error(
                f"❌ Webhook processing failed: "
                f"contact_id={payload.contact_id}, doc_id={payload.doc_id}, "
                f"error={str(e)}, processing_time={processing_time_ms}ms"
            )

            return ProcessingResult(
                success=False,
                processing_time_ms=processing_time_ms,
                status="failed",
                error_message=str(e),
            )

    async def health_check(self) -> dict[str, Any]:
        """
        Check health of webhook service dependencies.

        Returns:
            Health status of queue and other dependencies
        """
        try:
            await self._ensure_queue_adapter()

            # Check queue health
            queue_health = await self.queue_adapter.health_check()

            return {
                "service": "webhook-service",
                "status": "healthy"
                if queue_health.get("status") == "healthy"
                else "degraded",
                "queue": queue_health,
                "metrics": self.metrics,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "service": "webhook-service",
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }

    def get_metrics(self) -> dict[str, Any]:
        """Get webhook processing metrics."""
        return {
            **self.metrics,
            "service": "webhook-service",
            "timestamp": datetime.utcnow().isoformat(),
        }

    def _update_metrics(self, success: bool, processing_time_ms: int):
        """Update processing metrics."""
        self.metrics["total_requests"] += 1
        self.metrics["last_request_time"] = datetime.utcnow().isoformat()

        if success:
            self.metrics["successful_requests"] += 1
        else:
            self.metrics["failed_requests"] += 1

        # Update average processing time
        total_time = (
            self.metrics["average_processing_time_ms"]
            * (self.metrics["total_requests"] - 1)
            + processing_time_ms
        )
        self.metrics["average_processing_time_ms"] = (
            total_time / self.metrics["total_requests"]
        )
