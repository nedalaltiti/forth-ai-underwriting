"""
Async queue infrastructure with AWS SQS and local fallback.
Uses aioboto3 for proper async AWS integration.
"""

import json
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from loguru import logger

try:
    import aioboto3

    HAS_AIOBOTO3 = True
except ImportError:
    aioboto3 = None
    HAS_AIOBOTO3 = False

from ..config.settings import settings
from ..webhooks.models import QueueMessage


class QueueAdapter(ABC):
    """Abstract base class for queue adapters with DLQ support only."""

    def __init__(self, queue_name: str):
        self.queue_name = queue_name
        # Use configuration-driven DLQ naming
        self.dlq_name = self._get_dlq_name(queue_name)
        self._processed_messages = set()  # For idempotency tracking

    def _get_dlq_name(self, queue_name: str) -> str:
        """Get DLQ name from configuration or generate based on queue name."""
        # Use a simple naming pattern to generate DLQ name
        if queue_name.endswith("-dev-sqs"):
            base_name = queue_name.replace("-dev-sqs", "")
            return f"{base_name}-dl-dev-sqs"
        elif queue_name.endswith("-prod-sqs"):
            base_name = queue_name.replace("-prod-sqs", "")
            return f"{base_name}-dl-prod-sqs"
        elif queue_name.endswith("-staging-sqs"):
            base_name = queue_name.replace("-staging-sqs", "")
            return f"{base_name}-dl-staging-sqs"
        elif queue_name.endswith("-sqs"):
            base_name = queue_name.replace("-sqs", "")
            return f"{base_name}-dl-sqs"
        else:
            # Generic fallback
            return f"{queue_name}-dlq"

    @abstractmethod
    async def send_message(self, message: QueueMessage) -> str:
        """Send a message to the queue."""
        pass

    @abstractmethod
    async def receive_messages(self, max_messages: int = 10) -> list[dict[str, Any]]:
        """Receive messages from the queue."""
        pass

    @abstractmethod
    async def delete_message(self, receipt_handle: str) -> bool:
        """Delete a message from the queue."""
        pass

    @abstractmethod
    async def send_to_dlq(self, message: QueueMessage, failure_reason: str) -> str:
        """Send a message to the dead letter queue."""
        pass

    @abstractmethod
    async def health_check(self) -> dict[str, Any]:
        """Check the health of the queue."""
        pass

    def is_duplicate_message(self, idempotency_key: str) -> bool:
        """Check if message has already been processed."""
        return idempotency_key in self._processed_messages

    def mark_message_processed(self, idempotency_key: str) -> None:
        """Mark message as processed for idempotency."""
        self._processed_messages.add(idempotency_key)

        # Clean up old entries to prevent memory leaks
        if len(self._processed_messages) > 10000:
            # Remove oldest 1000 entries (simple FIFO cleanup)
            to_remove = list(self._processed_messages)[:1000]
            for key in to_remove:
                self._processed_messages.discard(key)


@dataclass
class LocalMessage:
    """Local queue message representation."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    body: str = ""
    receipt_handle: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    receive_count: int = 0


class LocalQueueAdapter(QueueAdapter):
    """Local in-memory queue adapter with DLQ support."""

    def __init__(self, queue_name: str):
        super().__init__(queue_name)
        self._queues: dict[str, list[LocalMessage]] = {}
        self._dlq: list[LocalMessage] = []
        self._ensure_queue(queue_name)
        logger.info(f"✅ Local queue adapter initialized with DLQ: {queue_name}")

    def _ensure_queue(self, queue_name: str):
        """Ensure queue exists."""
        if queue_name not in self._queues:
            self._queues[queue_name] = []

    async def send_message(self, message: QueueMessage) -> str:
        """Send message to local queue with idempotency check."""
        try:
            # Check for duplicate messages
            if message.idempotency_key and self.is_duplicate_message(
                message.idempotency_key
            ):
                logger.info(
                    f"⚠️ Duplicate message detected, skipping: {message.idempotency_key}"
                )
                return f"duplicate_{message.idempotency_key}"

            local_message = LocalMessage(
                body=json.dumps(message.to_queue_format()), timestamp=datetime.utcnow()
            )

            self._queues[self.queue_name].append(local_message)

            # Mark as processed for idempotency
            if message.idempotency_key:
                self.mark_message_processed(message.idempotency_key)

            logger.info(f"✅ Local message queued: {local_message.id}")
            return local_message.id

        except Exception as e:
            logger.error(f"❌ Failed to send local message: {e}")
            raise

    async def receive_messages(self, max_messages: int = 10) -> list[dict[str, Any]]:
        """Receive messages from local queue."""
        messages = []

        # Get messages from main queue
        queue = self._queues.get(self.queue_name, [])

        for _ in range(min(max_messages, len(queue))):
            if queue:
                local_message = queue.pop(0)
                local_message.receive_count += 1

                messages.append(
                    {
                        "MessageId": local_message.id,
                        "Body": local_message.body,
                        "ReceiptHandle": local_message.receipt_handle,
                        "ReceiveCount": local_message.receive_count,
                    }
                )

        return messages

    async def delete_message(self, receipt_handle: str) -> bool:
        """Delete message from local queue."""
        return True

    async def send_to_dlq(self, message: QueueMessage, failure_reason: str) -> str:
        """Send message to local dead letter queue."""
        try:
            dlq_message = message.create_dlq_message(failure_reason, self.queue_name)

            local_message = LocalMessage(
                body=json.dumps(dlq_message.to_queue_format()),
                timestamp=datetime.utcnow(),
            )

            self._dlq.append(local_message)
            logger.warning(f"⚠️ Message sent to DLQ: {failure_reason}")
            return local_message.id

        except Exception as e:
            logger.error(f"❌ Failed to send to DLQ: {e}")
            raise

    async def health_check(self) -> dict[str, Any]:
        """Check local queue health with DLQ metrics."""
        return {
            "type": "local",
            "accessible": True,
            "queue_name": self.queue_name,
            "message_count": len(self._queues.get(self.queue_name, [])),
            "dlq_count": len(self._dlq),
            "processed_messages_count": len(self._processed_messages),
            "queues": list(self._queues.keys()),
        }


class SQSAdapter(QueueAdapter):
    """AWS SQS queue adapter with DLQ support."""

    def __init__(self, queue_name: str, region: str = "us-west-1"):
        super().__init__(queue_name)
        self.region = region
        self.queue_url = None
        self.dlq_url = None
        self._session = None
        self._initialized = False

        if not HAS_AIOBOTO3:
            raise ImportError("aioboto3 is required for SQS adapter")

        logger.info(f"✅ SQS adapter initialized with DLQ support: {queue_name}")

    async def _ensure_initialized(self):
        """Ensure SQS client and queues are initialized."""
        if self._initialized:
            return

        self._session = aioboto3.Session()

        # Initialize main queue and DLQ
        self.queue_url = await self._get_or_create_queue_url(self.queue_name)
        self.dlq_url = await self._get_or_create_queue_url(self.dlq_name)

        # Configure DLQ redrive policy for main queue
        await self._configure_dlq_policy()

        self._initialized = True

    async def _get_or_create_queue_url(self, queue_name: str) -> str:
        """Get existing queue URL or create new queue with DLQ configuration."""
        try:
            async with self._session.client("sqs", region_name=self.region) as client:
                try:
                    response = await client.get_queue_url(QueueName=queue_name)
                    queue_url = response["QueueUrl"]
                    logger.info(f"✅ Found existing SQS queue: {queue_name}")
                    return queue_url

                except client.exceptions.QueueDoesNotExist:
                    logger.warning(f"Queue {queue_name} does not exist, creating...")

                    # Create queue with appropriate attributes
                    attributes = {
                        "MessageRetentionPeriod": "1209600",  # 14 days
                        "VisibilityTimeoutSeconds": "300",  # 5 minutes
                        "ReceiveMessageWaitTimeSeconds": "20",  # Long polling
                    }

                    # Special configuration for DLQ
                    if queue_name.endswith("-dlq"):
                        attributes.update(
                            {
                                "MessageRetentionPeriod": "1209600",  # Keep DLQ messages for 14 days
                                "VisibilityTimeoutSeconds": "60",  # Shorter timeout for DLQ
                            }
                        )

                    response = await client.create_queue(
                        QueueName=queue_name, Attributes=attributes
                    )
                    queue_url = response["QueueUrl"]
                    logger.info(f"✅ Created new SQS queue: {queue_name}")
                    return queue_url

        except Exception as e:
            logger.error(f"❌ Error accessing SQS queue: {e}")
            raise

    async def _configure_dlq_policy(self):
        """Configure dead letter queue redrive policy for main queue."""
        try:
            if not self.dlq_url:
                return

            async with self._session.client("sqs", region_name=self.region) as client:
                # Get DLQ ARN
                dlq_attributes = await client.get_queue_attributes(
                    QueueUrl=self.dlq_url, AttributeNames=["QueueArn"]
                )
                dlq_arn = dlq_attributes["Attributes"]["QueueArn"]

                # Set redrive policy on main queue
                redrive_policy = {
                    "deadLetterTargetArn": dlq_arn,
                    "maxReceiveCount": 3,  # After 3 failed attempts, send to DLQ
                }

                await client.set_queue_attributes(
                    QueueUrl=self.queue_url,
                    Attributes={"RedrivePolicy": json.dumps(redrive_policy)},
                )

                logger.info(f"✅ Configured DLQ redrive policy for {self.queue_name}")

        except Exception as e:
            logger.warning(f"⚠️ Failed to configure DLQ policy: {e}")

    async def send_message(self, message: QueueMessage) -> str:
        """Send message to SQS queue with idempotency check."""
        try:
            await self._ensure_initialized()

            # Check for duplicate messages
            if message.idempotency_key and self.is_duplicate_message(
                message.idempotency_key
            ):
                logger.info(
                    f"⚠️ Duplicate message detected, skipping: {message.idempotency_key}"
                )
                return f"duplicate_{message.idempotency_key}"

            message_body = json.dumps(message.to_queue_format())

            # Build message attributes (only include non-None values)
            message_attributes = {
                "SchemaVersion": {
                    "StringValue": str(message.schema_version),
                    "DataType": "String",
                },
                "MessageType": {
                    "StringValue": str(message.message_type),
                    "DataType": "String",
                },
                "ContactId": {
                    "StringValue": str(message.contact_id),
                    "DataType": "String",
                },
            }

            # Only add IdempotencyKey if it's not None
            if message.idempotency_key:
                message_attributes["IdempotencyKey"] = {
                    "StringValue": str(message.idempotency_key),
                    "DataType": "String",
                }

            # Prepare send_message parameters
            send_params = {
                "QueueUrl": self.queue_url,
                "MessageBody": message_body,
                "MessageAttributes": message_attributes,
            }

            # Check if this is a FIFO queue (ends with .fifo)
            is_fifo_queue = self.queue_name.endswith(".fifo")

            if is_fifo_queue:
                # FIFO queues require MessageDeduplicationId and MessageGroupId
                deduplication_id = (
                    message.idempotency_key
                    or f"{message.contact_id}_{message.timestamp.isoformat()}"
                )
                send_params.update(
                    {
                        "MessageDeduplicationId": deduplication_id,
                        "MessageGroupId": message.contact_id,  # Group by contact for ordering
                    }
                )

            # Use context manager for client operations
            async with self._session.client("sqs", region_name=self.region) as client:
                response = await client.send_message(**send_params)

            message_id = response["MessageId"]

            # Mark as processed for idempotency
            if message.idempotency_key:
                self.mark_message_processed(message.idempotency_key)

            logger.info(f"✅ SQS message sent: {message_id} (FIFO: {is_fifo_queue})")
            return message_id

        except Exception as e:
            logger.error(f"❌ Failed to send SQS message: {e}")
            raise

    async def receive_messages(self, max_messages: int = 10) -> list[dict[str, Any]]:
        """Receive messages from SQS queue."""
        try:
            await self._ensure_initialized()

            async with self._session.client("sqs", region_name=self.region) as client:
                response = await client.receive_message(
                    QueueUrl=self.queue_url,
                    MaxNumberOfMessages=min(max_messages, 10),
                    WaitTimeSeconds=20,  # Long polling
                    MessageAttributeNames=["All"],
                    AttributeNames=["All"],
                )

            messages = response.get("Messages", [])
            logger.debug(f"Received {len(messages)} messages from SQS")
            return messages

        except Exception as e:
            logger.error(f"❌ Failed to receive SQS messages: {e}")
            raise

    async def delete_message(self, receipt_handle: str) -> bool:
        """Delete message from SQS queue."""
        try:
            await self._ensure_initialized()

            async with self._session.client("sqs", region_name=self.region) as client:
                await client.delete_message(
                    QueueUrl=self.queue_url, ReceiptHandle=receipt_handle
                )

            logger.debug("✅ SQS message deleted")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to delete SQS message: {e}")
            return False

    async def send_to_dlq(self, message: QueueMessage, failure_reason: str) -> str:
        """Send message to SQS dead letter queue."""
        try:
            await self._ensure_initialized()
            dlq_message = message.create_dlq_message(failure_reason, self.queue_name)

            message_body = json.dumps(dlq_message.to_queue_format())

            # Build message attributes (only include non-None values)
            message_attributes = {
                "MessageType": {
                    "StringValue": str(dlq_message.message_type),
                    "DataType": "String",
                },
                "ContactId": {
                    "StringValue": str(dlq_message.contact_id),
                    "DataType": "String",
                },
                "FailureReason": {
                    "StringValue": str(failure_reason),
                    "DataType": "String",
                },
                "OriginalQueue": {
                    "StringValue": str(self.queue_name),
                    "DataType": "String",
                },
            }

            # Prepare send_message parameters
            send_params = {
                "QueueUrl": self.dlq_url,
                "MessageBody": message_body,
                "MessageAttributes": message_attributes,
            }

            # Check if DLQ is a FIFO queue (ends with .fifo)
            is_fifo_queue = self.dlq_name.endswith(".fifo")

            if is_fifo_queue:
                # FIFO queues require MessageDeduplicationId and MessageGroupId
                deduplication_id = (
                    dlq_message.idempotency_key
                    or f"{dlq_message.contact_id}_{dlq_message.timestamp.isoformat()}"
                )
                send_params.update(
                    {
                        "MessageDeduplicationId": deduplication_id,
                        "MessageGroupId": dlq_message.contact_id,
                    }
                )

            async with self._session.client("sqs", region_name=self.region) as client:
                response = await client.send_message(**send_params)

            message_id = response["MessageId"]
            logger.warning(
                f"⚠️ SQS message sent to DLQ: {message_id} - {failure_reason} (FIFO: {is_fifo_queue})"
            )
            return message_id

        except Exception as e:
            logger.error(f"❌ Failed to send to SQS DLQ: {e}")
            raise

    async def health_check(self) -> dict[str, Any]:
        """Check SQS queue health with DLQ metrics."""
        try:
            await self._ensure_initialized()

            async with self._session.client("sqs", region_name=self.region) as client:
                # Get main queue attributes
                main_response = await client.get_queue_attributes(
                    QueueUrl=self.queue_url,
                    AttributeNames=["ApproximateNumberOfMessages", "CreatedTimestamp"],
                )

                # Get DLQ attributes
                dlq_response = await client.get_queue_attributes(
                    QueueUrl=self.dlq_url,
                    AttributeNames=["ApproximateNumberOfMessages"],
                )

            main_attributes = main_response.get("Attributes", {})
            dlq_attributes = dlq_response.get("Attributes", {})

            return {
                "type": "sqs",
                "accessible": True,
                "queue_name": self.queue_name,
                "queue_url": self.queue_url,
                "region": self.region,
                "message_count": int(
                    main_attributes.get("ApproximateNumberOfMessages", 0)
                ),
                "dlq_message_count": int(
                    dlq_attributes.get("ApproximateNumberOfMessages", 0)
                ),
                "created_timestamp": main_attributes.get("CreatedTimestamp"),
                "dlq_url": self.dlq_url,
                "processed_messages_count": len(self._processed_messages),
            }

        except Exception as e:
            logger.error(f"❌ SQS health check failed: {e}")
            return {"type": "sqs", "accessible": False, "error": str(e)}

    async def __aenter__(self):
        """Async context manager entry."""
        await self._ensure_initialized()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._session:
            await self._session.close()


def create_queue_adapter(
    queue_name: str, use_local: bool | None = None, region: str = "us-west-1"
) -> QueueAdapter:
    """
    Factory function to create appropriate queue adapter.

    Args:
        queue_name: Name of the queue
        use_local: Force local queue (None = auto-detect from settings)
        region: AWS region for SQS

    Returns:
        QueueAdapter instance (Local or SQS)
    """
    # Determine whether to use local queue
    if use_local is None:
        use_local = settings.aws.sqs.use_local_queue

    if use_local:
        logger.info("Creating local queue adapter")
        return LocalQueueAdapter(queue_name)
    else:
        logger.info("Creating AWS SQS adapter")
        return SQSAdapter(queue_name, region)


async def get_queue_service(queue_name: str) -> QueueAdapter:
    """
    Get queue service instance with proper initialization.

    Args:
        queue_name: Name of the queue

    Returns:
        Initialized QueueAdapter instance
    """
    adapter = create_queue_adapter(queue_name)

    # Ensure initialization for SQS adapters
    if isinstance(adapter, SQSAdapter):
        await adapter._ensure_initialized()

    return adapter
