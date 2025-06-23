"""
Main FastAPI application for Forth AI Underwriting System.
Clean implementation using modular services and proper error handling.
"""

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
import json
import uvicorn
from loguru import logger
from datetime import datetime

from forth_ai_underwriting.config.settings import settings
from forth_ai_underwriting.services.validation import ValidationService
from forth_ai_underwriting.infrastructure.ai_parser import get_ai_parser_service
from forth_ai_underwriting.services.teams_bot import TeamsBot
from forth_ai_underwriting.core.middleware import (
    RequestLoggingMiddleware,
    SecurityHeadersMiddleware,
    ExceptionHandlingMiddleware
)
from forth_ai_underwriting.core.exceptions import ValidationError, AIParsingError
from forth_ai_underwriting.models.base_models import BaseResponse, SuccessResponse, ErrorResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown events."""
    # Startup
    logger.info("Starting Forth AI Underwriting System")
    
    # Pre-initialize services for better performance
    get_validation_service()
    get_ai_parser_service()
    get_teams_bot()
    
    logger.info("All services initialized successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Forth AI Underwriting System")


# Initialize FastAPI app with lifespan
app = FastAPI(
    title="Forth AI Underwriting System",
    description="AI-powered underwriting validation system for Forth Debt Resolution",
    version=settings.app_version,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
    lifespan=lifespan
)

# Add middleware in correct order
app.add_middleware(ExceptionHandlingMiddleware)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.security.cors_origins,
    allow_credentials=settings.security.cors_allow_credentials,
    allow_methods=settings.security.cors_allow_methods,
    allow_headers=settings.security.cors_allow_headers,
)


# Service instances (initialized on first request)
_validation_service: Optional[ValidationService] = None
_ai_parser_service = None
_teams_bot: Optional[TeamsBot] = None


def get_validation_service() -> ValidationService:
    """Get or create validation service instance."""
    global _validation_service
    if _validation_service is None:
        _validation_service = ValidationService()
    return _validation_service


def get_teams_bot() -> TeamsBot:
    """Get or create Teams bot instance."""
    global _teams_bot
    if _teams_bot is None:
        _teams_bot = TeamsBot()
    return _teams_bot


# Request/Response models
class WebhookPayload(BaseModel):
    """Webhook payload from Forth Debt Resolution."""
    contact_id: str = Field(..., description="Contact identifier")
    document_type: str = Field(..., description="Type of document")
    document_url: str = Field(..., description="URL of the document")
    document_name: str = Field(..., description="Name of the document")
    created_by: str = Field(..., description="User who created the document")
    timestamp: str = Field(..., description="Creation timestamp")
    additional_data: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class TeamsRequest(BaseModel):
    """Teams bot request payload."""
    contact_id: str = Field(..., description="Contact identifier")
    user_id: str = Field(..., description="Teams user identifier")
    conversation_id: str = Field(..., description="Teams conversation identifier")


class FeedbackRequest(BaseModel):
    """User feedback request."""
    contact_id: str = Field(..., description="Contact identifier")
    rating: int = Field(..., ge=1, le=5, description="Rating from 1-5 stars")
    feedback: str = Field(..., description="Feedback description")
    user_id: str = Field(..., description="User identifier")


# API Routes
@app.get("/", response_model=SuccessResponse)
async def root():
    """Health check endpoint."""
    return SuccessResponse(
        message="Forth AI Underwriting System is running",
        data={
            "version": settings.app_version,
            "environment": settings.environment,
            "timestamp": datetime.utcnow().isoformat()
        }
    )


@app.get("/health", response_model=SuccessResponse)
async def health_check():
    """Detailed health check endpoint."""
    try:
        # Check service health
        validation_service = get_validation_service()
        ai_parser_service = get_ai_parser_service()
        
        # Run health checks
        ai_health = await ai_parser_service.health_check()
        
        health_data = {
            "status": "healthy",
            "version": settings.app_version,
            "environment": settings.environment,
            "services": {
                "validation": "active",
                "ai_parser": ai_health["status"],
                "teams_bot": "active"
            },
            "ai_pipeline": ai_health
        }
        
        return SuccessResponse(
            message="System health check completed",
            data=health_data
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return ErrorResponse(
            message="Health check failed",
            error_code="HEALTH_CHECK_FAILED",
            error_details={"error": str(e)}
        )


@app.post(settings.forth_api.webhook_endpoint, response_model=SuccessResponse)
async def forth_webhook(
    payload: WebhookPayload,
    background_tasks: BackgroundTasks,
    request: Request
):
    """
    Webhook endpoint for Forth Debt Resolution.
    Triggered when a contract PDF is uploaded with contract_id type 'agreement'.
    """
    try:
        logger.info(f"Received webhook for contact_id: {payload.contact_id}")
        
        # Validate webhook (optional signature verification)
        if settings.forth_api.webhook_secret:
            # Add webhook signature validation here if needed
            pass
        
        # Process the document in background
        background_tasks.add_task(
            process_contract_document,
            payload.contact_id,
            payload.document_url,
            payload.document_name
        )
        
        return SuccessResponse(
            message="Document processing initiated",
            data={
                "contact_id": payload.contact_id,
                "document_name": payload.document_name,
                "status": "accepted"
            }
        )
        
    except Exception as e:
        logger.error(f"Webhook processing error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/teams/validate", response_model=SuccessResponse)
async def teams_validate_contact(
    request: TeamsRequest,
    validation_service: ValidationService = Depends(get_validation_service),
    teams_bot: TeamsBot = Depends(get_teams_bot)
):
    """
    Teams bot endpoint for manual validation requests.
    Takes a contact_id and returns validation results.
    """
    try:
        logger.info(f"Teams validation request for contact_id: {request.contact_id}")
        
        # Get validation results
        validation_results = await validation_service.validate_contact(request.contact_id)
        
        # Format results for Teams
        formatted_results = teams_bot.format_validation_results(validation_results)
        
        return SuccessResponse(
            message="Validation completed successfully",
            data={
                "contact_id": request.contact_id,
                "user_id": request.user_id,
                "results": formatted_results,
                "validation_count": len(validation_results)
            }
        )
        
    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Teams validation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/teams/feedback", response_model=SuccessResponse)
async def teams_feedback(feedback_request: FeedbackRequest):
    """
    Endpoint to collect user feedback from Teams bot.
    """
    try:
        # Log feedback for future enhancements
        feedback_data = {
            "contact_id": feedback_request.contact_id,
            "rating": feedback_request.rating,
            "feedback": feedback_request.feedback,
            "user_id": feedback_request.user_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        logger.info(f"Feedback received: {feedback_data}")
        
        # Store feedback (implement storage logic as needed)
        await store_feedback(feedback_data)
        
        return SuccessResponse(
            message="Feedback recorded successfully",
            data={
                "contact_id": feedback_request.contact_id,
                "rating": feedback_request.rating
            }
        )
        
    except Exception as e:
        logger.error(f"Feedback processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Background tasks
async def process_contract_document(contact_id: str, document_url: str, document_name: str):
    """
    Background task to process uploaded contract documents.
    """
    try:
        logger.info(f"Processing document {document_name} for contact {contact_id}")
        
        # Parse document using AI parser service
        ai_parser_service = get_ai_parser_service()
        parsed_data = await ai_parser_service.parse_contract(document_url)
        
        # Run validation checks
        validation_service = get_validation_service()
        validation_results = await validation_service.validate_contact(
            contact_id, 
            parsed_contract_data=parsed_data
        )
        
        # Store results or send notification
        await store_validation_results(contact_id, validation_results)
        
        logger.info(f"Document processing completed for contact {contact_id}")
        
    except AIParsingError as e:
        logger.error(f"AI parsing error for {contact_id}: {e}")
        # Could send notification about parsing failure
    except ValidationError as e:
        logger.error(f"Validation error for {contact_id}: {e}")
        # Could send notification about validation failure
    except Exception as e:
        logger.error(f"Document processing error for {contact_id}: {e}")


# Helper functions
async def store_feedback(feedback_data: Dict[str, Any]):
    """Store user feedback for future analysis."""
    # TODO: Implement feedback storage logic
    # This could be a database, file, or external service
    logger.info(f"Storing feedback: {feedback_data}")


async def store_validation_results(contact_id: str, results: List[Any]):
    """Store validation results."""
    # TODO: Implement results storage logic
    # This could update the Forth system or store in a database
    logger.info(f"Storing validation results for {contact_id}: {len(results)} results")


# Event handlers are now managed by the lifespan context manager above


if __name__ == "__main__":
    uvicorn.run(
        "forth_ai_underwriting.api.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )

