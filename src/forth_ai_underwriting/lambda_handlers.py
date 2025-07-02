"""
AWS Lambda handlers for the underwriting workflow.
"""

import json
from typing import Any

from loguru import logger


# Lambda handlers need to import inside functions to avoid cold start issues
def parse_s3_document_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Lambda handler for S3 events to trigger document parsing.
    This is triggered when a new document is uploaded to S3.
    """
    try:
        # Import inside handler for Lambda
        import asyncio

        from forth_ai_underwriting.workers.parse_worker import ParseWorker

        # Process S3 events
        for record in event.get("Records", []):
            if record["eventName"].startswith("ObjectCreated:"):
                bucket = record["s3"]["bucket"]["name"]
                key = record["s3"]["object"]["key"]

                logger.info(f"S3 event: New object in {bucket}: {key}")

                # Initialize parser
                parser = ParseWorker()

                # Process the document
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                try:
                    loop.run_until_complete(
                        parser.process_s3_event(key, bucket, "created")
                    )
                    logger.info(f"Successfully processed document: {key}")
                except Exception as e:
                    logger.error(f"Failed to process document {key}: {e}")
                    raise
                finally:
                    loop.close()

        return {
            "statusCode": 200,
            "body": json.dumps({"message": "Documents processed successfully"}),
        }

    except Exception as e:
        logger.error(f"Lambda handler error: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}


def webhook_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Lambda handler for Forth webhook events.
    Queues documents for processing.
    """
    try:
        # Import inside handler for Lambda
        import asyncio
        import uuid
        from datetime import datetime

        from forth_ai_underwriting.services.queue_service import get_queue_service

        # Parse the webhook payload
        body = json.loads(event.get("body", "{}"))

        # Extract fields
        contact_id = body.get("contact_id")
        doc_id = body.get("doc_id")
        doc_type = body.get("doc_type", "Contract / Agreement")
        doc_name = body.get("doc_name")

        if not contact_id:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Missing required field: contact_id"}),
            }

        if not doc_id:
            doc_id = (
                f"webhook_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{contact_id}"
            )

        # Queue the document
        queue_service = get_queue_service()
        correlation_id = str(uuid.uuid4())

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            message_id = loop.run_until_complete(
                queue_service.send_contract_download_message(
                    contact_id=contact_id,
                    doc_id=doc_id,
                    doc_type=doc_type,
                    doc_name=doc_name,
                    correlation_id=correlation_id,
                )
            )

            logger.info(f"Queued document: {doc_id} for contact: {contact_id}")

            return {
                "statusCode": 200,
                "body": json.dumps(
                    {
                        "message": "Document queued for processing",
                        "contact_id": contact_id,
                        "doc_id": doc_id,
                        "correlation_id": correlation_id,
                        "message_id": message_id,
                    }
                ),
            }

        finally:
            loop.close()

    except Exception as e:
        logger.error(f"Webhook handler error: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}


def sqs_worker_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Lambda handler for processing SQS messages.
    Can be used instead of long-running workers.
    """
    try:
        # Import inside handler for Lambda
        import asyncio

        # Determine which queue this is for based on event source
        event_source_arn = event["Records"][0]["eventSourceARN"]

        if "contract-downloads" in event_source_arn:
            from forth_ai_underwriting.workers.download_worker import DownloadWorker

            worker = DownloadWorker()
        elif "validation-tasks" in event_source_arn:
            from forth_ai_underwriting.workers.validation_worker import ValidationWorker

            worker = ValidationWorker()
        else:
            logger.error(f"Unknown queue: {event_source_arn}")
            return {"statusCode": 400, "body": json.dumps({"error": "Unknown queue"})}

        # Process messages
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            for record in event["Records"]:
                message = {
                    "receipt_handle": record["receiptHandle"],
                    "message_id": record["messageId"],
                    "body": json.loads(record["body"]),
                    "attributes": record.get("messageAttributes", {}),
                }

                loop.run_until_complete(worker._process_message(message))

            return {
                "statusCode": 200,
                "body": json.dumps({"message": "Messages processed successfully"}),
            }

        finally:
            loop.close()

    except Exception as e:
        logger.error(f"SQS worker handler error: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
