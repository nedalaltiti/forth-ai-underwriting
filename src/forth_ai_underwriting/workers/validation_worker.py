"""
Worker service: uw_validation
Reads from SQS, runs 5 validation checks, and writes results to DB.
"""

import asyncio
from datetime import datetime
from typing import Any

from forth_ai_underwriting.core.database import get_db
from forth_ai_underwriting.core.repositories import (
    DocumentRepository,
    ValidationRunRepository,
)
from forth_ai_underwriting.core.schemas import ValidationResult
from forth_ai_underwriting.services.queue_service import QueueService, get_queue_service
from forth_ai_underwriting.services.validation import ValidationService
from loguru import logger


class ValidationWorker:
    """Worker that runs underwriting validations."""

    def __init__(self):
        self.queue_service = get_queue_service()
        self.validation_service = ValidationService()
        self.running = False
        logger.info("ValidationWorker initialized")

    async def start(self):
        """Start the worker to process validation queue."""
        self.running = True
        logger.info("ValidationWorker started")

        while self.running:
            try:
                # Poll for messages
                messages = await self.queue_service.receive_messages(
                    QueueService.VALIDATION_TASKS_QUEUE,
                    max_messages=5,  # Process fewer at a time for validations
                )

                if not messages:
                    # No messages, wait a bit
                    await asyncio.sleep(5)
                    continue

                # Process messages
                for message in messages:
                    await self._process_message(message)

            except Exception as e:
                logger.error(f"Error in validation worker loop: {e}")
                await asyncio.sleep(10)

    async def _process_message(self, message: dict[str, Any]):
        """Process a single validation message."""
        receipt_handle = message["receipt_handle"]
        body = message["body"]

        try:
            contact_id = body["contact_id"]
            doc_id = body["data"]["doc_id"]
            s3_key = body["data"]["s3_key"]
            parsed_data = body["data"]["parsed_data"]
            correlation_id = body.get("correlation_id")

            logger.info(
                f"Processing validation: contact_id={contact_id}, doc_id={doc_id}, correlation_id={correlation_id}"
            )

            # Run validations
            validation_results = await self._run_validations(contact_id, parsed_data)

            # Save results to database
            await self._save_validation_results(
                contact_id=contact_id,
                doc_id=doc_id,
                s3_key=s3_key,
                validation_results=validation_results,
                correlation_id=correlation_id,
            )

            logger.info(
                f"Validation completed for contact {contact_id}: {len(validation_results)} checks"
            )

            # Delete message from queue
            await self.queue_service.delete_message(
                QueueService.VALIDATION_TASKS_QUEUE, receipt_handle
            )

        except Exception as e:
            logger.error(f"Failed to process validation message: {e}")
            # Message will become visible again after visibility timeout

    async def _run_validations(
        self, contact_id: str, parsed_data: dict[str, Any]
    ) -> list[ValidationResult]:
        """Run all 5 validation checks."""
        try:
            # Run validations with parsed contract data
            validation_results = await self.validation_service.validate_contact(
                contact_id=contact_id, parsed_contract_data=parsed_data
            )

            return validation_results

        except Exception as e:
            logger.error(f"Validation error for contact {contact_id}: {e}")
            # Return error result
            return [
                ValidationResult(
                    title="System Error",
                    result="No Pass",
                    reason=f"Validation system error: {str(e)}",
                )
            ]

    async def _save_validation_results(
        self,
        contact_id: str,
        doc_id: str,
        s3_key: str,
        validation_results: list[ValidationResult],
        correlation_id: str,
    ):
        """Save validation results to database."""
        with next(get_db()) as db:
            try:
                # Create validation run
                run_repo = ValidationRunRepository(db)

                validation_run = run_repo.create_run(
                    contact_id=contact_id,
                    triggered_by="queue_worker",
                    user_id=f"worker_{correlation_id}",
                )

                # Calculate processing time (mock for now)
                processing_time_ms = 1000

                # Complete the run with results
                run_repo.complete_run(
                    run_id=validation_run.id,
                    results=validation_results,
                    processing_time_ms=processing_time_ms,
                )

                # Update document status
                doc_repo = DocumentRepository(db)
                doc = (
                    db.query(doc_repo.model_class)
                    .filter(
                        doc_repo.model_class.contact_id == contact_id,
                        doc_repo.model_class.document_name == doc_id,
                    )
                    .first()
                )

                if doc:
                    # Add validation info to parsed data
                    if not doc.parsed_data:
                        doc.parsed_data = {}

                    doc.parsed_data["validation"] = {
                        "run_id": validation_run.id,
                        "completed_at": datetime.utcnow().isoformat(),
                        "success_rate": validation_run.success_rate,
                        "correlation_id": correlation_id,
                    }

                    # Update processing status
                    doc.processing_status = "validated"

                db.commit()

                # Log validation summary
                passed = sum(1 for r in validation_results if r.result == "Pass")
                failed = sum(1 for r in validation_results if r.result == "No Pass")

                logger.info(
                    f"Saved validation results for {contact_id}: {passed} passed, {failed} failed"
                )

                # Check if we need to send notifications
                if failed > 0:
                    await self._send_failure_notification(
                        contact_id, validation_results
                    )

            except Exception as e:
                db.rollback()
                logger.error(f"Failed to save validation results: {e}")
                raise

    async def _send_failure_notification(
        self, contact_id: str, results: list[ValidationResult]
    ):
        """Send notification for validation failures."""
        failed_checks = [r for r in results if r.result == "No Pass"]

        if failed_checks:
            logger.warning(
                f"Contact {contact_id} failed {len(failed_checks)} validation checks:"
            )
            for check in failed_checks:
                logger.warning(f"  - {check.title}: {check.reason}")

            # TODO: Implement notification service (Teams, email, etc.)
            # For now, just log the failures

    async def stop(self):
        """Stop the worker."""
        self.running = False
        logger.info("ValidationWorker stopping...")


async def main():
    """Main entry point for the validation worker."""
    worker = ValidationWorker()

    try:
        await worker.start()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    finally:
        await worker.stop()


if __name__ == "__main__":
    asyncio.run(main())
