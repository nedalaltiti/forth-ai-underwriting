"""
Webhook API router with configurable queue support.
Uses dependency injection and configuration-driven design.
"""

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from loguru import logger

from ..config.settings import settings
from ..core.error_handling import handle_expected_errors, handle_json_errors
from ..core.observability import increment_counter, trace_function, trace_span
from .models import HealthStatus, WebhookPayload
from .services import WebhookProcessor, WebhookProcessorFactory


def create_webhook_router(
    queue_name: str | None = None,
    forth_api_config: dict[str, str] | None = None,
    use_local_queue: bool | None = None,
    aws_region: str | None = None,
) -> APIRouter:
    """
    Create webhook router with configurable dependencies.
    Uses settings from configuration if parameters not provided.

    Args:
        queue_name: Queue name (defaults to settings.aws.sqs.main_queue)
        forth_api_config: Forth API configuration (defaults to settings.forth_api)
        use_local_queue: Use local queue (defaults to settings.aws.sqs.use_local_queue)
        aws_region: AWS region (defaults to settings.aws.sqs.region)

    Returns:
        Configured FastAPI router
    """
    router = APIRouter(prefix="/webhook", tags=["webhooks"])

    # Use configuration from settings if not provided
    queue_name = queue_name or settings.aws.sqs.main_queue
    use_local_queue = (
        use_local_queue
        if use_local_queue is not None
        else settings.aws.sqs.use_local_queue
    )
    aws_region = aws_region or settings.aws.sqs.region

    # Configure Forth API if not provided
    if forth_api_config is None:
        forth_api_config = (
            {
                "base_url": settings.forth_api.base_url,
                "api_key": settings.forth_api.api_key,
                "timeout": settings.forth_api.timeout,
            }
            if settings.forth_api.base_url and settings.forth_api.api_key
            else None
        )

    logger.info("✅ Webhook router configured:")
    logger.info(f"📋 Queue: {queue_name}")
    logger.info(f"🏠 Local queue: {use_local_queue}")
    logger.info(f"🌍 Region: {aws_region}")
    logger.info(f"🔗 Forth API: {'Configured' if forth_api_config else 'Disabled'}")

    def get_webhook_processor() -> WebhookProcessor:
        """Dependency injection for webhook processor."""
        return WebhookProcessorFactory.create_processor(
            queue_name=queue_name,
            forth_api_config=forth_api_config,
            use_local_queue=use_local_queue,
            aws_region=aws_region,
        )

    @router.post("/forth")
    @handle_expected_errors("webhook_processing", "webhook_api")
    @trace_function("webhook.handle_forth_webhook")
    async def handle_forth_webhook(
        request: Request,
        webhook_processor: WebhookProcessor = Depends(get_webhook_processor),
    ) -> JSONResponse:
        """
        Handle Forth CRM webhook with comprehensive processing.

        Supports both JSON and form-encoded payloads with automatic parsing.
        Includes document ID enhancement and queue messaging.
        """
        with trace_span("webhook.process_request") as span:
            try:
                # Parse request data
                content_type = request.headers.get("content-type", "")
                request_data = await _parse_request_data(request, content_type)

                if span:
                    span.set_attribute("request.content_type", content_type)
                    span.set_attribute("request.data_keys", list(request_data.keys()))

                # Create and validate webhook payload
                payload = WebhookPayload.from_webhook_data(request_data)

                if span:
                    span.set_attribute("webhook.contact_id", payload.contact_id)
                    span.set_attribute("webhook.doc_type", payload.doc_type)
                    span.set_attribute("webhook.doc_id", payload.doc_id)

                logger.info(
                    f"📨 Processing webhook: contact_id={payload.contact_id}, "
                    f"doc_id={payload.doc_id}, doc_type={payload.doc_type}"
                )

                # Process webhook
                result = await webhook_processor.process_webhook(payload)

                # Update metrics
                increment_counter(
                    "webhook_requests_total",
                    {
                        "status": "success" if result.success else "error",
                        "doc_type": payload.doc_type,
                    },
                )

                if result.success:
                    logger.info(
                        f"✅ Webhook processed successfully: {result.message_id}"
                    )

                    return JSONResponse(
                        status_code=200,
                        content={
                            "status": "success",
                            "message": "Webhook processed successfully",
                            "data": {
                                "contact_id": payload.contact_id,
                                "doc_id": payload.doc_id,
                                "doc_type": payload.doc_type,
                                "message_id": result.message_id,
                                "processing_time_ms": result.processing_time_ms,
                                "correlation_id": payload.correlation_id,
                            },
                        },
                    )
                else:
                    logger.error(f"❌ Webhook processing failed: {result.error_message}")

                    return JSONResponse(
                        status_code=500,
                        content={
                            "status": "error",
                            "message": "Webhook processing failed",
                            "error": result.error_message,
                            "processing_time_ms": result.processing_time_ms,
                        },
                    )

            except ValueError as e:
                # Validation errors
                logger.error(f"❌ Webhook validation error: {e}")
                increment_counter("webhook_errors_total", {"error_type": "validation"})

                return JSONResponse(
                    status_code=400,
                    content={
                        "status": "error",
                        "message": "Invalid webhook payload",
                        "error": str(e),
                    },
                )

            except Exception as e:
                # Unexpected errors
                logger.error(f"❌ Unexpected webhook error: {e}")
                increment_counter("webhook_errors_total", {"error_type": "unexpected"})

                if span:
                    span.set_attribute("error.message", str(e))

                return JSONResponse(
                    status_code=500,
                    content={
                        "status": "error",
                        "message": "Internal server error",
                        "error": str(e),
                    },
                )

    @router.get("/health")
    async def webhook_health_check(
        webhook_processor: WebhookProcessor = Depends(get_webhook_processor),
    ) -> HealthStatus:
        """
        Comprehensive health check for webhook service.

        Returns:
            Health status including all dependencies
        """
        try:
            health_data = await webhook_processor.health_check()

            return HealthStatus(
                status=health_data.get("status", "unknown"),
                services={
                    "processor": health_data.get("processor", "unknown"),
                    "queue": health_data.get("queue", "unknown"),
                    "document_extractor": health_data.get(
                        "document_extractor", "unknown"
                    ),
                },
                metrics=webhook_processor.get_metrics(),
            )

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return HealthStatus(status="unhealthy", services={"error": str(e)})

    @router.get("/metrics")
    async def webhook_metrics(
        webhook_processor: WebhookProcessor = Depends(get_webhook_processor),
    ) -> dict[str, Any]:
        """Get webhook processing metrics."""
        return webhook_processor.get_metrics()

    @router.post("/test")
    async def test_webhook(
        test_data: dict[str, Any],
        webhook_processor: WebhookProcessor = Depends(get_webhook_processor),
    ) -> JSONResponse:
        """
        Test endpoint for webhook processing.

        Args:
            test_data: Test webhook data

        Returns:
            Processing result
        """
        try:
            # Create test payload
            payload = WebhookPayload.from_webhook_data(test_data)

            # Process webhook
            result = await webhook_processor.process_webhook(payload)

            return JSONResponse(
                status_code=200 if result.success else 500,
                content={
                    "status": "success" if result.success else "error",
                    "message": "Test webhook processed",
                    "result": {
                        "success": result.success,
                        "message_id": result.message_id,
                        "processing_time_ms": result.processing_time_ms,
                        "error_message": result.error_message,
                    },
                },
            )

        except Exception as e:
            logger.error(f"Test webhook failed: {e}")
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "message": "Test webhook failed",
                    "error": str(e),
                },
            )

    return router


@handle_json_errors("parse_webhook_request", "webhook_parser")
async def _parse_request_data(request: Request, content_type: str) -> dict[str, Any]:
    """
    Parse webhook request data based on content type.

    Args:
        request: FastAPI request object
        content_type: Request content type

    Returns:
        Parsed request data as dictionary
    """
    if "application/x-www-form-urlencoded" in content_type:
        # Handle form-encoded data
        form_data = await request.form()

        logger.debug(f"📝 Form data received: {dict(form_data)}")

        return {
            "contact_id": form_data.get("contact_id"),
            "doc_id": form_data.get("doc_id") or form_data.get("{DOC_ID}"),
            "doc_type": form_data.get("doc_type") or form_data.get("{DOC_TYPE}"),
            "doc_name": form_data.get("doc_name") or form_data.get("{FILENAME}"),
            "copydocs": form_data.get("copydocs"),
        }
    else:
        # Handle JSON data
        body = await request.body()
        if not body:
            return {}

        json_data = json.loads(body)
        logger.debug(f"📝 JSON data received: {json_data}")

        return json_data


def create_standalone_app(
    queue_name: str | None = None,
    forth_api_config: dict[str, str] | None = None,
    use_local_queue: bool | None = None,
    aws_region: str | None = None,
) -> FastAPI:
    """
    Create standalone FastAPI app for webhook service.
    Uses configuration from settings if parameters not provided.

    Args:
        queue_name: Queue name (defaults to settings)
        forth_api_config: Forth API configuration (defaults to settings)
        use_local_queue: Use local queue (defaults to settings)
        aws_region: AWS region (defaults to settings)

    Returns:
        Configured FastAPI application
    """
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware

    # Use defaults from settings if not provided
    queue_name = queue_name or settings.aws.sqs.main_queue
    use_local_queue = (
        use_local_queue
        if use_local_queue is not None
        else settings.aws.sqs.use_local_queue
    )
    aws_region = aws_region or settings.aws.sqs.region

    app = FastAPI(
        title="Forth AI Underwriting - Webhook Service",
        description="Webhook processing service with configurable SQS support",
        version=settings.app_version,
        docs_url="/docs" if not settings.is_production else None,
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.security.cors_origins,
        allow_credentials=settings.security.cors_allow_credentials,
        allow_methods=settings.security.cors_allow_methods,
        allow_headers=settings.security.cors_allow_headers,
    )

    # Include webhook router
    webhook_router = create_webhook_router(
        queue_name=queue_name,
        forth_api_config=forth_api_config,
        use_local_queue=use_local_queue,
        aws_region=aws_region,
    )
    app.include_router(webhook_router)

    @app.get("/")
    async def root():
        """Root endpoint with service information."""
        return {
            "service": "Forth AI Underwriting - Webhook Service",
            "version": settings.app_version,
            "environment": settings.environment,
            "configuration": {
                "queue_name": queue_name,
                "use_local_queue": use_local_queue,
                "aws_region": aws_region,
                "forth_api_configured": bool(forth_api_config),
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

    return app
