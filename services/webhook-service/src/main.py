"""
Webhook Service - Focused on receiving and queuing webhook requests.
Microservice responsible for webhook ingestion and message queuing.
"""

from contextlib import asynccontextmanager
from datetime import datetime

import uvicorn
from config.settings import WebhookConfig
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from models import ProcessingResult, WebhookPayload
from webhook_processor import WebhookProcessor


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown events."""
    logger.info("🚀 Starting Webhook Service")
    yield
    logger.info("🛑 Shutting down Webhook Service")


# Initialize FastAPI app
app = FastAPI(
    title="Webhook Service",
    description="Microservice for webhook ingestion and queuing",
    version="1.0.0",
    lifespan=lifespan,
)

# Load configuration
config = WebhookConfig()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure based on environment
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Initialize webhook processor
webhook_processor = WebhookProcessor(config)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "webhook-service",
        "status": "running",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/health")
async def health_check():
    """Detailed health check endpoint."""
    try:
        health_status = await webhook_processor.health_check()
        return {
            "service": "webhook-service",
            "status": "healthy",
            "queue_status": health_status.get("queue", "unknown"),
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


@app.post("/webhook/forth")
async def forth_webhook(request: Request) -> ProcessingResult:
    """
    Main webhook endpoint for Forth CRM integration.
    Receives webhook data and queues it for document processing.
    """
    try:
        # Parse request data
        content_type = request.headers.get("content-type", "")
        request_data = await _parse_request_data(request, content_type)

        # Create webhook payload
        payload = WebhookPayload.from_webhook_data(request_data)

        # Process webhook
        result = await webhook_processor.process_webhook(payload)

        logger.info(f"✅ Webhook processed: {payload.contact_id}/{payload.doc_id}")
        return result

    except Exception as e:
        logger.error(f"❌ Webhook processing failed: {e}")
        return ProcessingResult(
            success=False, processing_time_ms=0, status="failed", error_message=str(e)
        )


@app.get("/metrics")
async def get_metrics():
    """Get webhook processing metrics."""
    return webhook_processor.get_metrics()


async def _parse_request_data(request: Request, content_type: str) -> dict:
    """Parse webhook request data based on content type."""
    if "application/x-www-form-urlencoded" in content_type:
        form_data = await request.form()
        return dict(form_data)
    else:
        body = await request.body()
        if body:
            import json

            return json.loads(body)
        return {}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=config.host,
        port=config.port,
        reload=config.debug,
        log_level=config.log_level.lower(),
    )
