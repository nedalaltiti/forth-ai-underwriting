"""
Worker service: parse_contract_docs
Reads from S3 events, parses documents using AI, saves to DB, and queues for validation.
"""

import asyncio
from datetime import datetime
from typing import Any

from forth_ai_underwriting.core.database import get_db
from forth_ai_underwriting.core.repositories import (
    DocumentRepository,
)
from forth_ai_underwriting.services.process import get_document_processor
from forth_ai_underwriting.services.queue_service import get_queue_service
from forth_ai_underwriting.services.s3_service import get_s3_service
from loguru import logger


class ParseWorker:
    """Worker that parses documents from S3 using AI."""

    def __init__(self):
        self.queue_service = get_queue_service()
        self.s3_service = get_s3_service()
        self.document_processor = get_document_processor()
        self.running = False
        logger.info("ParseWorker initialized")

    async def start(self):
        """Start the worker to process S3 events."""
        self.running = True
        logger.info("ParseWorker started")

        while self.running:
            try:
                # For S3 events, you would typically use:
                # 1. S3 Event Notifications -> SQS
                # 2. Lambda function triggered by S3
                # 3. Or poll S3 for new files

                # For this implementation, we'll check for new documents periodically
                await self._check_for_new_documents()

                await asyncio.sleep(10)  # Check every 10 seconds

            except Exception as e:
                logger.error(f"Error in parse worker loop: {e}")
                await asyncio.sleep(30)

    async def _check_for_new_documents(self):
        """Check for new documents to parse."""
        # In production, this would be triggered by S3 events
        # For now, we'll check the database for unparsed documents

        with next(get_db()) as db:
            doc_repo = DocumentRepository(db)

            # Get documents that need parsing
            unparsed_docs = (
                db.query(doc_repo.model_class)
                .filter(
                    doc_repo.model_class.processing_status == "uploaded",
                    doc_repo.model_class.parsed_data.is_(None),
                )
                .limit(10)
                .all()
            )

            for doc in unparsed_docs:
                await self._process_document(doc)

    async def process_s3_event(
        self, s3_key: str, bucket: str, event_type: str = "created"
    ):
        """Process a specific S3 event (called by Lambda or S3 notification)."""
        if event_type != "created":
            return

        try:
            # Extract metadata from S3 object
            metadata = await self.s3_service.get_document_metadata(s3_key)

            contact_id = metadata["metadata"].get("contact_id")
            doc_id = metadata["metadata"].get("doc_id")
            correlation_id = metadata["metadata"].get("correlation_id")

            logger.info(
                f"Processing S3 document: {s3_key}, contact_id={contact_id}, doc_id={doc_id}"
            )

            # Download document from S3
            local_path = await self.s3_service.download_document(s3_key)

            try:
                # Process document with AI
                processing_result = await self.document_processor.process_document(
                    document_url=f"file://{local_path}",
                    document_name=metadata["metadata"].get("original_filename"),
                    skip_ai_parsing=False,
                )

                if (
                    processing_result.validation_ready
                    and processing_result.contract_data
                ):
                    # Save to database
                    await self._save_parsed_data(
                        contact_id=contact_id,
                        doc_id=doc_id,
                        s3_key=s3_key,
                        parsed_data=self._contract_data_to_dict(
                            processing_result.contract_data
                        ),
                        processing_result=processing_result,
                    )

                    # Queue for validation
                    await self.queue_service.send_validation_task_message(
                        contact_id=contact_id,
                        doc_id=doc_id,
                        s3_key=s3_key,
                        parsed_data=self._contract_data_to_dict(
                            processing_result.contract_data
                        ),
                        correlation_id=correlation_id,
                    )

                    logger.info(f"Document parsed and queued for validation: {doc_id}")
                else:
                    logger.warning(
                        f"Document parsing incomplete: {processing_result.processing_errors}"
                    )

            finally:
                # Clean up local file
                import os

                try:
                    os.remove(local_path)
                except:
                    pass

        except Exception as e:
            logger.error(f"Failed to process S3 document {s3_key}: {e}")

    async def _process_document(self, doc):
        """Process a document record."""
        try:
            # Update status
            doc.processing_status = "parsing"

            # Get S3 key from document record
            s3_key = doc.parsed_data.get("s3_key") if doc.parsed_data else None

            if not s3_key:
                logger.warning(f"No S3 key found for document {doc.id}")
                return

            # Process the S3 document
            await self.process_s3_event(s3_key, self.s3_service.bucket_name)

        except Exception as e:
            logger.error(f"Failed to process document {doc.id}: {e}")
            doc.processing_status = "failed"

    def _contract_data_to_dict(self, contract_data) -> dict[str, Any]:
        """Convert ContractData object to dictionary."""
        if hasattr(contract_data, "__dict__"):
            result = {}
            for field, value in contract_data.__dict__.items():
                if value is not None:
                    result[field] = value
            return result
        else:
            return contract_data

    async def _save_parsed_data(
        self,
        contact_id: str,
        doc_id: str,
        s3_key: str,
        parsed_data: dict[str, Any],
        processing_result: Any,
    ):
        """Save parsed data to database."""
        with next(get_db()) as db:
            try:
                # Update or create document record
                doc_repo = DocumentRepository(db)

                doc = (
                    db.query(doc_repo.model_class)
                    .filter(
                        doc_repo.model_class.contact_id == contact_id,
                        doc_repo.model_class.document_name == doc_id,
                    )
                    .first()
                )

                if not doc:
                    # Create new document record
                    doc = doc_repo.create_document(
                        contact_id=contact_id,
                        document_url=s3_key,
                        document_name=doc_id,
                        document_type="contract",
                    )

                # Update with parsed data
                doc.parsed_data = {
                    "s3_key": s3_key,
                    "parsed_at": datetime.utcnow().isoformat(),
                    "contract_data": parsed_data,
                    "extraction_metadata": {
                        "method": processing_result.document_info.processing_status
                        if hasattr(processing_result, "document_info")
                        else "unknown",
                        "text_quality": processing_result.document_info.text_quality
                        if hasattr(processing_result, "document_info")
                        else "unknown",
                        "processing_time_ms": processing_result.document_info.processing_time_ms
                        if hasattr(processing_result, "document_info")
                        else None,
                    },
                }
                doc.processing_status = "completed"
                doc.processed = True

                db.commit()
                logger.info(f"Saved parsed data for document {doc_id}")

            except Exception as e:
                db.rollback()
                logger.error(f"Failed to save parsed data: {e}")
                raise

    async def stop(self):
        """Stop the worker."""
        self.running = False
        logger.info("ParseWorker stopping...")


async def main():
    """Main entry point for the parse worker."""
    worker = ParseWorker()

    try:
        await worker.start()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    finally:
        await worker.stop()


if __name__ == "__main__":
    asyncio.run(main())
