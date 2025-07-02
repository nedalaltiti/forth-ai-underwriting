"""
Worker service: download_contact_docs
Reads from SQS, calls Forth API to get document URL, downloads document directly to S3.
Enhanced with streaming upload, better error handling, retry logic, and configuration support.
"""

import asyncio
from datetime import datetime
from io import BytesIO
from typing import Any

import boto3
import httpx
from forth_ai_underwriting.config.settings import settings
from forth_ai_underwriting.infrastructure.external_apis import ForthAPIClient
from forth_ai_underwriting.services.queue_service import get_queue_service
from forth_ai_underwriting.services.s3_service import get_s3_service
from loguru import logger


class DownloadWorker:
    """
    Worker that downloads documents from Forth API and uploads directly to S3.

    Workflow:
    1. Read messages from SQS download queue
    2. Call Forth API to get document URL
    3. Stream download document directly to S3 (no local storage)
    4. Delete message from queue on success
    5. Queue for parsing (next step in pipeline)
    """

    def __init__(self):
        self.queue_service = get_queue_service()
        self.s3_service = get_s3_service()

        # Initialize Forth API client with credentials from settings
        self.forth_client = ForthAPIClient(
            base_url=settings.forth_api.base_url,
            api_key=settings.forth_api.api_key,
            timeout=settings.forth_api.timeout,
        )

        # Initialize direct S3 client for streaming uploads
        self.s3_client = boto3.client(
            "s3",
            region_name=settings.aws.region,
            aws_access_key_id=settings.aws.access_key_id,
            aws_secret_access_key=settings.aws.secret_access_key,
        )

        # Use production bucket
        self.bucket_name = "contact-contracts-dev-s3-us-west-1"
        logger.info(f"DownloadWorker initialized with S3 bucket: {self.bucket_name}")

        self.running = False

        # Statistics
        self.processed_count = 0
        self.failed_count = 0
        self.start_time = datetime.utcnow()

    async def start(self, poll_interval: int = 5):
        """
        Start the worker to process download queue.

        Args:
            poll_interval: Seconds between queue polls when no messages
        """
        self.running = True
        logger.info("🚀 DownloadWorker started - polling for document download tasks")

        while self.running:
            try:
                # Poll for messages from main queue
                messages = await self.queue_service.receive_messages(
                    queue_type="main", max_messages=10
                )

                if not messages:
                    # No messages, wait before next poll
                    await asyncio.sleep(poll_interval)
                    continue

                logger.info(f"📥 Received {len(messages)} download messages")

                # Process messages concurrently
                tasks = [self._process_message(message) for message in messages]
                await asyncio.gather(*tasks, return_exceptions=True)

            except Exception as e:
                logger.error(f"❌ Error in download worker loop: {e}")
                await asyncio.sleep(10)  # Wait longer on error

    async def _process_message(self, message: dict[str, Any]):
        """Process a single download message."""
        receipt_handle = message.get("ReceiptHandle", message.get("receipt_handle"))
        message_id = message.get("MessageId", message.get("message_id", "unknown"))

        try:
            # Parse message body
            if isinstance(message.get("Body"), str):
                import json

                body = json.loads(message["Body"])
            else:
                body = message.get("body", message)

            # Extract message data from QueueMessage format
            # The QueueMessage.to_queue_format() returns fields like:
            # ContactId, Data, CorrelationId, etc.
            contact_id = body.get("ContactId")
            data = body.get("Data", {})
            doc_id = data.get("doc_id")
            doc_type = data.get("doc_type", "Contract")
            doc_name = data.get("doc_name")
            correlation_id = body.get("CorrelationId")

            if not contact_id or not doc_id:
                logger.error("❌ Invalid message format: missing contact_id or doc_id")
                logger.error(f"📋 Message body: {body}")
                # Delete invalid message
                await self.queue_service.delete_message("main", receipt_handle)
                return

            logger.info(
                f"📄 Processing download: contact_id={contact_id}, doc_id={doc_id}, correlation_id={correlation_id}"
            )

            # Download document directly to S3
            download_result = await self._download_document_to_s3(
                contact_id=contact_id,
                doc_id=doc_id,
                doc_name=doc_name,
                doc_type=doc_type,
                correlation_id=correlation_id,
            )

            if download_result["success"]:
                logger.info(f"✅ Document uploaded to S3: {download_result['s3_key']}")

                # Queue for parsing (next step in pipeline)
                await self._queue_for_parsing(
                    contact_id=contact_id,
                    doc_id=doc_id,
                    s3_key=download_result["s3_key"],
                    correlation_id=correlation_id,
                )

                # Delete message from queue (success)
                await self.queue_service.delete_message("main", receipt_handle)
                self.processed_count += 1

                logger.info(f"🎉 Download task completed successfully: {doc_id}")
            else:
                logger.error(f"❌ Document download failed: {download_result['error']}")
                self.failed_count += 1
                # Don't delete message - let it retry

        except Exception as e:
            logger.error(f"❌ Failed to process download message {message_id}: {e}")
            self.failed_count += 1
            # Message will become visible again after visibility timeout

    async def _download_document_to_s3(
        self,
        contact_id: str,
        doc_id: str,
        doc_name: str | None,
        doc_type: str,
        correlation_id: str | None,
    ) -> dict[str, Any]:
        """
        Download document from Forth API and stream directly to S3.

        Returns:
            Dict with success status, s3_key if successful, or error message
        """
        try:
            async with self.forth_client as client:
                # Get document URL from Forth API
                document_url = await self._get_document_url(
                    client, contact_id, doc_id, doc_name
                )

                if not document_url:
                    return {
                        "success": False,
                        "error": f"Document URL not found for doc_id={doc_id}, doc_name={doc_name}",
                    }

                # Stream download and upload to S3
                s3_result = await self._stream_to_s3(
                    url=document_url,
                    contact_id=contact_id,
                    doc_id=doc_id,
                    doc_name=doc_name,
                    doc_type=doc_type,
                    correlation_id=correlation_id,
                )

                return s3_result

        except Exception as e:
            logger.error(f"❌ Error downloading document to S3: {e}")
            return {"success": False, "error": str(e)}

    async def _get_document_url(
        self,
        client: ForthAPIClient,
        contact_id: str,
        doc_id: str,
        doc_name: str | None,
    ) -> str | None:
        """Get document URL from Forth API."""
        try:
            # First, try to get document URL by ID
            try:
                # Call Forth API to get document details directly
                response = await client._client.get(
                    f"/contacts/{contact_id}/documents/{doc_id}/uploaded"
                )
                response.raise_for_status()
                doc_data = response.json()

                # Extract file URL from response
                if "response" in doc_data and doc_data["response"].get("file_content"):
                    document_url = doc_data["response"]["file_content"]
                    logger.info(f"📍 Found document URL by ID: {doc_id}")
                    return document_url

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    logger.warning(
                        f"⚠️ Document {doc_id} not found by ID, trying by name..."
                    )
                else:
                    logger.error(f"❌ API error getting document {doc_id}: {e}")

            # If direct lookup failed, try to find by filename
            if doc_name:
                document_url = await client.find_document_url(contact_id, doc_name)
                if document_url:
                    logger.info(f"📍 Found document URL by name: {doc_name}")
                    return document_url

            return None

        except Exception as e:
            logger.error(f"❌ Error getting document URL: {e}")
            return None

    async def _stream_to_s3(
        self,
        url: str,
        contact_id: str,
        doc_id: str,
        doc_name: str | None,
        doc_type: str,
        correlation_id: str | None,
    ) -> dict[str, Any]:
        """
        Stream download content directly to S3.

        Returns:
            Dict with success status and S3 key or error
        """
        try:
            # Generate S3 key and filename
            if doc_name:
                # Sanitize filename
                safe_name = "".join(c for c in doc_name if c.isalnum() or c in "._-")
                filename = f"{doc_id}_{safe_name}"
            else:
                # Default to PDF if no name provided
                filename = f"{doc_id}.pdf"

            s3_key = f"contacts/{contact_id}/documents/{doc_id}/{filename}"

            logger.info(f"⬇️ Streaming document from Forth API to S3: {url[:100]}...")

            # Create metadata
            metadata = {
                "contact_id": contact_id,
                "doc_id": doc_id,
                "doc_type": doc_type,
                "upload_timestamp": datetime.utcnow().isoformat(),
                "correlation_id": correlation_id or "",
                "source": "download_worker_stream",
                "original_url": url[:200],  # Truncate URL for metadata
            }

            # Stream download and upload
            async with httpx.AsyncClient(timeout=300.0) as http_client:
                async with http_client.stream(
                    "GET", url, follow_redirects=True
                ) as response:
                    response.raise_for_status()

                    # Get content type from response
                    content_type = response.headers.get(
                        "content-type", "application/pdf"
                    )

                    # Read content into memory (for small files) or use multipart upload for large files
                    content_length = response.headers.get("content-length")

                    if (
                        content_length and int(content_length) > 100 * 1024 * 1024
                    ):  # 100MB
                        # Use multipart upload for large files
                        await self._multipart_upload_to_s3(
                            response=response,
                            s3_key=s3_key,
                            content_type=content_type,
                            metadata=metadata,
                        )
                    else:
                        # Stream to memory and upload normally
                        content = BytesIO()
                        file_size = 0

                        async for chunk in response.aiter_bytes(chunk_size=8192):
                            content.write(chunk)
                            file_size += len(chunk)

                        if file_size == 0:
                            return {
                                "success": False,
                                "error": "Downloaded file is empty",
                            }

                        # Upload to S3
                        content.seek(0)

                        self.s3_client.upload_fileobj(
                            content,
                            self.bucket_name,
                            s3_key,
                            ExtraArgs={
                                "ServerSideEncryption": "AES256",
                                "ContentType": content_type,
                                "Metadata": metadata,
                            },
                        )

                    logger.info(
                        f"✅ Streamed document to S3: s3://{self.bucket_name}/{s3_key} ({file_size:,} bytes)"
                    )

                    return {
                        "success": True,
                        "s3_key": s3_key,
                        "bucket": self.bucket_name,
                        "file_size": file_size,
                        "content_type": content_type,
                    }

        except httpx.HTTPStatusError as e:
            logger.error(
                f"❌ HTTP error downloading file: {e.response.status_code} - {e}"
            )
            return {
                "success": False,
                "error": f"HTTP {e.response.status_code}: {str(e)}",
            }
        except Exception as e:
            logger.error(f"❌ Failed to stream file to S3: {e}")
            return {"success": False, "error": str(e)}

    async def _multipart_upload_to_s3(
        self, response, s3_key: str, content_type: str, metadata: dict[str, str]
    ):
        """Handle multipart upload for large files."""
        try:
            # Initiate multipart upload
            multipart_response = self.s3_client.create_multipart_upload(
                Bucket=self.bucket_name,
                Key=s3_key,
                ServerSideEncryption="AES256",
                ContentType=content_type,
                Metadata=metadata,
            )

            upload_id = multipart_response["UploadId"]
            parts = []
            part_number = 1

            # Upload parts
            async for chunk in response.aiter_bytes(
                chunk_size=5 * 1024 * 1024
            ):  # 5MB chunks
                upload_response = self.s3_client.upload_part(
                    Bucket=self.bucket_name,
                    Key=s3_key,
                    PartNumber=part_number,
                    UploadId=upload_id,
                    Body=chunk,
                )

                parts.append(
                    {"ETag": upload_response["ETag"], "PartNumber": part_number}
                )

                part_number += 1

            # Complete multipart upload
            self.s3_client.complete_multipart_upload(
                Bucket=self.bucket_name,
                Key=s3_key,
                UploadId=upload_id,
                MultipartUpload={"Parts": parts},
            )

            logger.info(f"✅ Completed multipart upload: {s3_key}")

        except Exception as e:
            # Abort multipart upload on error
            try:
                self.s3_client.abort_multipart_upload(
                    Bucket=self.bucket_name, Key=s3_key, UploadId=upload_id
                )
            except:
                pass
            raise e

    async def _queue_for_parsing(
        self, contact_id: str, doc_id: str, s3_key: str, correlation_id: str | None
    ):
        """Queue document for parsing (next step in pipeline)."""
        try:
            # Send message to parsing queue (could be validation queue)
            await self.queue_service.send_validation_task_message(
                contact_id=contact_id,
                doc_id=doc_id,
                s3_key=s3_key,
                parsed_data={},  # Will be filled by parser
                correlation_id=correlation_id,
            )

            logger.info(f"📤 Queued for parsing: {s3_key}")

        except Exception as e:
            logger.error(f"❌ Failed to queue for parsing: {e}")
            # This is not critical - parsing can be triggered other ways

    async def stop(self):
        """Stop the worker and clean up resources."""
        self.running = False
        logger.info("🛑 DownloadWorker stopping...")

        # Log statistics
        runtime = (datetime.utcnow() - self.start_time).total_seconds()
        logger.info(
            f"📊 Worker statistics: {self.processed_count} processed, "
            f"{self.failed_count} failed, {runtime:.1f}s runtime"
        )

    def get_stats(self) -> dict[str, Any]:
        """Get worker statistics."""
        runtime = (datetime.utcnow() - self.start_time).total_seconds()
        return {
            "processed_count": self.processed_count,
            "failed_count": self.failed_count,
            "runtime_seconds": runtime,
            "success_rate": self.processed_count
            / max(1, self.processed_count + self.failed_count),
            "bucket_name": self.bucket_name,
            "running": self.running,
        }


async def main():
    """Main entry point for the download worker."""
    worker = DownloadWorker()

    try:
        logger.info("🚀 Starting Forth AI Underwriting - Download Worker (Direct S3)")
        await worker.start()
    except KeyboardInterrupt:
        logger.info("⚠️ Received interrupt signal")
    finally:
        await worker.stop()


if __name__ == "__main__":
    asyncio.run(main())
