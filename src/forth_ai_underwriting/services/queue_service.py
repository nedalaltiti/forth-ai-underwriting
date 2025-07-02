"""
Queue service with configurable SQS support and clean architecture.
Uses configuration-driven design with dependency injection.
"""

import uuid
from datetime import datetime
from typing import Any

from forth_ai_underwriting.config.settings import settings
from forth_ai_underwriting.infrastructure.queue import (
    QueueAdapter,
    create_queue_adapter,
)
from forth_ai_underwriting.webhooks.models import (
    MessageType,
    QueueMessage,
)
from loguru import logger


class QueueService:
    """
    Service for managing queues with configurable backends.
    Supports AWS SQS and local development modes based on configuration.
    """

    def __init__(self, queue_adapter: QueueAdapter | None = None):
        """
        Initialize queue service with optional adapter injection.

        Args:
            queue_adapter: Optional pre-configured queue adapter for dependency injection
        """
        self.sqs_config = settings.aws.sqs

        # Use injected adapter or create based on configuration
        if queue_adapter:
            self.main_adapter = queue_adapter
        else:
            self.main_adapter = create_queue_adapter(
                queue_name=self.sqs_config.main_queue,
                use_local=self.sqs_config.use_local_queue,
                region=self.sqs_config.region,
            )

        # Initialize additional adapters for different processing stages
        self._adapters = {
            "main": self.main_adapter,
            "validation": create_queue_adapter(
                queue_name=self.sqs_config.validation_queue,
                use_local=self.sqs_config.use_local_queue,
                region=self.sqs_config.region,
            ),
            "notification": create_queue_adapter(
                queue_name=self.sqs_config.notification_queue,
                use_local=self.sqs_config.use_local_queue,
                region=self.sqs_config.region,
            ),
        }

        # Initialize metrics tracking
        self._metrics = {
            "dlq_messages_sent": 0,
            "send_errors": 0,
            "last_dlq_send": None,
            "messages_processed": 0,
            "errors": 0,
        }

        # Log queue configuration
        logger.info(f"📥 Main queue: {self.sqs_config.main_queue}")
        logger.info(f"💀 DLQ: {self.sqs_config.dead_letter_queue}")
        logger.info(f"✅ Validation queue: {self.sqs_config.validation_queue}")
        logger.info(f"📢 Notification queue: {self.sqs_config.notification_queue}")
        logger.info(f"🌍 Region: {self.sqs_config.region}")
        logger.info(f"🏠 Use local: {self.sqs_config.use_local_queue}")

        logger.info("✅ QueueService initialized with async queue support")

    async def send_contract_download_message(
        self,
        contact_id: str,
        doc_id: str,
        doc_type: str,
        doc_name: str | None = None,
        correlation_id: str | None = None,
        priority: int = 5,
    ) -> str | None:
        """
        Send message to contract download queue (main queue).

        Args:
            contact_id: Contact identifier
            doc_id: Document identifier
            doc_type: Type of document
            doc_name: Optional document name
            correlation_id: Optional correlation ID for tracing
            priority: Message priority (1=highest, 10=lowest)

        Returns:
            Message ID if successful, None otherwise
        """
        try:
            message = QueueMessage(
                message_type=MessageType.CONTRACT_DOWNLOAD,
                contact_id=contact_id,
                data={"doc_id": doc_id, "doc_type": doc_type, "doc_name": doc_name},
                correlation_id=correlation_id or str(uuid.uuid4()),
                priority=priority,
                idempotency_key=f"contract_download_{contact_id}_{doc_id}_{int(datetime.utcnow().timestamp())}",
            )

            message_id = await self._adapters["main"].send_message(message)

            logger.info(f"📨 Contract download message queued: {message_id}")
            logger.debug(
                f"📋 Message details: contact_id={contact_id}, doc_id={doc_id}, doc_type={doc_type}"
            )

            return message_id

        except Exception as e:
            logger.error(f"❌ Failed to send contract download message: {e}")
            return None

    async def send_validation_task_message(
        self,
        contact_id: str,
        doc_id: str,
        s3_key: str,
        parsed_data: dict[str, Any],
        correlation_id: str | None = None,
        priority: int = 5,
    ) -> str | None:
        """
        Send message to validation tasks queue.

        Args:
            contact_id: Contact identifier
            doc_id: Document identifier
            s3_key: S3 object key for the document
            parsed_data: Parsed document data
            correlation_id: Optional correlation ID for tracing
            priority: Message priority (1=highest, 10=lowest)

        Returns:
            Message ID if successful, None otherwise
        """
        try:
            message = QueueMessage(
                message_type=MessageType.VALIDATION_TASK,
                contact_id=contact_id,
                data={"doc_id": doc_id, "s3_key": s3_key, "parsed_data": parsed_data},
                correlation_id=correlation_id or str(uuid.uuid4()),
                priority=priority,
                idempotency_key=f"validation_task_{contact_id}_{doc_id}_{int(datetime.utcnow().timestamp())}",
            )

            message_id = await self._adapters["validation"].send_message(message)

            logger.info(f"🔍 Validation task message queued: {message_id}")
            logger.debug(
                f"📋 Message details: contact_id={contact_id}, doc_id={doc_id}, s3_key={s3_key}"
            )

            return message_id

        except Exception as e:
            logger.error(f"❌ Failed to send validation task message: {e}")
            return None

    async def send_notification_message(
        self,
        contact_id: str,
        notification_type: str,
        data: dict[str, Any],
        correlation_id: str | None = None,
        priority: int = 5,
    ) -> str | None:
        """
        Send message to notification queue.

        Args:
            contact_id: Contact identifier
            notification_type: Type of notification
            data: Notification data
            correlation_id: Optional correlation ID for tracing
            priority: Message priority (1=highest, 10=lowest)

        Returns:
            Message ID if successful, None otherwise
        """
        try:
            message = QueueMessage(
                message_type=MessageType.WEBHOOK_RECEIVED,  # Using generic message type
                contact_id=contact_id,
                data={"notification_type": notification_type, **data},
                correlation_id=correlation_id or str(uuid.uuid4()),
                priority=priority,
                idempotency_key=f"notification_{contact_id}_{notification_type}_{int(datetime.utcnow().timestamp())}",
            )

            message_id = await self._adapters["notification"].send_message(message)

            logger.info(f"📢 Notification message queued: {message_id}")
            logger.debug(
                f"📋 Message details: contact_id={contact_id}, type={notification_type}"
            )

            return message_id

        except Exception as e:
            logger.error(f"❌ Failed to send notification message: {e}")
            return None

    async def receive_messages(
        self, queue_type: str = "main", max_messages: int = 10
    ) -> list[dict[str, Any]]:
        """
        Receive messages from specified queue.

        Args:
            queue_type: Type of queue ('main', 'validation', 'notification')
            max_messages: Maximum number of messages to receive

        Returns:
            List of messages
        """
        try:
            if queue_type not in self._adapters:
                logger.error(f"❌ Unknown queue type: {queue_type}")
                return []

            # Respect configuration limits
            max_messages = min(max_messages, self.sqs_config.max_batch_size)

            messages = await self._adapters[queue_type].receive_messages(max_messages)

            if messages:
                logger.info(
                    f"📥 Received {len(messages)} messages from {queue_type} queue"
                )

            return messages

        except Exception as e:
            logger.error(f"❌ Failed to receive messages from {queue_type} queue: {e}")
            return []

    async def delete_message(self, queue_type: str, receipt_handle: str) -> bool:
        """
        Delete message from specified queue.

        Args:
            queue_type: Type of queue ('main', 'validation', 'notification')
            receipt_handle: Message receipt handle

        Returns:
            True if successful, False otherwise
        """
        try:
            if queue_type not in self._adapters:
                logger.error(f"❌ Unknown queue type: {queue_type}")
                return False

            success = await self._adapters[queue_type].delete_message(receipt_handle)

            if success:
                logger.debug(f"🗑️ Message deleted from {queue_type} queue")

            return success

        except Exception as e:
            logger.error(f"❌ Failed to delete message from {queue_type} queue: {e}")
            return False

    async def send_to_dlq(
        self, queue_type: str, message: QueueMessage, failure_reason: str
    ) -> str | None:
        """
        Send a message to the dead letter queue.

        Args:
            queue_type: Type of queue ('main', 'validation', 'notification')
            message: Message to send to DLQ
            failure_reason: Reason for failure

        Returns:
            Message ID if successful, None if failed
        """
        try:
            adapter = self._adapters.get(queue_type)
            if not adapter:
                logger.error(f"No adapter found for queue type: {queue_type}")
                return None

            message_id = await adapter.send_to_dlq(message, failure_reason)

            # Update metrics safely
            if hasattr(self, "_metrics"):
                self._metrics["dlq_messages_sent"] += 1
                self._metrics["last_dlq_send"] = datetime.utcnow()

            logger.warning(f"📤 Message sent to DLQ: {message_id} - {failure_reason}")
            return message_id

        except Exception as e:
            logger.error(f"❌ Failed to send message to DLQ: {e}")
            if hasattr(self, "_metrics"):
                self._metrics["send_errors"] += 1
            return None

    async def get_queue_attributes(self, queue_type: str = "main") -> dict[str, Any]:
        """
        Get queue attributes and metrics.

        Args:
            queue_type: Type of queue ('main', 'validation', 'notification')

        Returns:
            Dictionary with queue attributes
        """
        try:
            if queue_type not in self._adapters:
                return {"error": f"Unknown queue type: {queue_type}"}

            health_info = await self._adapters[queue_type].health_check()

            return {
                "queue_type": queue_type,
                "configuration": {
                    "use_local_queue": self.sqs_config.use_local_queue,
                    "region": self.sqs_config.region,
                    "max_batch_size": self.sqs_config.max_batch_size,
                    "visibility_timeout": self.sqs_config.visibility_timeout_seconds,
                    "max_receive_count": self.sqs_config.max_receive_count,
                },
                "health": health_info,
            }

        except Exception as e:
            return {"error": str(e)}

    async def health_check(self) -> dict[str, Any]:
        """
        Comprehensive health check for all queue adapters.

        Returns:
            Dictionary with health status for all queues
        """
        health_results = {
            "overall_status": "healthy",
            "configuration": {
                "queue_count": len(self._adapters),
                "use_local_queue": self.sqs_config.use_local_queue,
                "region": self.sqs_config.region,
                "queue_names": {
                    "main": self.sqs_config.main_queue,
                    "validation": self.sqs_config.validation_queue,
                    "notification": self.sqs_config.notification_queue,
                    "dlq": self.sqs_config.dead_letter_queue,
                },
            },
            "adapters": {},
        }

        unhealthy_count = 0

        for queue_type, adapter in self._adapters.items():
            try:
                adapter_health = await adapter.health_check()
                health_results["adapters"][queue_type] = adapter_health

                if not adapter_health.get("accessible", False):
                    unhealthy_count += 1

            except Exception as e:
                health_results["adapters"][queue_type] = {
                    "accessible": False,
                    "error": str(e),
                }
                unhealthy_count += 1

        # Determine overall status
        if unhealthy_count == 0:
            health_results["overall_status"] = "healthy"
        elif unhealthy_count < len(self._adapters):
            health_results["overall_status"] = "degraded"
        else:
            health_results["overall_status"] = "unhealthy"

        return health_results

    def get_metrics(self) -> dict[str, Any]:
        """
        Get service metrics and statistics.

        Returns:
            Dictionary with service metrics
        """
        if hasattr(self, "_metrics"):
            return dict(self._metrics)  # Return a copy
        else:
            return {
                "dlq_messages_sent": 0,
                "send_errors": 0,
                "last_dlq_send": None,
                "messages_processed": 0,
                "errors": 0,
                "note": "Metrics not initialized",
            }


# Global queue service instance with lazy initialization
_queue_service: QueueService | None = None


def get_queue_service(queue_adapter: QueueAdapter | None = None) -> QueueService:
    """
    Get the global queue service instance with optional dependency injection.

    Args:
        queue_adapter: Optional pre-configured queue adapter for testing/DI

    Returns:
        QueueService instance
    """
    global _queue_service
    if _queue_service is None:
        _queue_service = QueueService(queue_adapter)
    return _queue_service


def reset_queue_service():
    """Reset the global queue service instance (useful for testing)."""
    global _queue_service
    _queue_service = None
