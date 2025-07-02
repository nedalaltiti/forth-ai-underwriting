"""
Validation Service - Focused on AI-powered underwriting validation.
Microservice responsible for document validation and assessment.
"""

from contextlib import asynccontextmanager
from datetime import datetime

import uvicorn
from config.settings import ValidationConfig
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from models import ValidationRequest, ValidationResponse
from validation_processor import ValidationProcessor


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown events."""
    logger.info("🚀 Starting Validation Service")
    yield
    logger.info("🛑 Shutting down Validation Service")


# Initialize FastAPI app
app = FastAPI(
    title="Validation Service",
    description="AI-powered underwriting validation microservice",
    version="1.0.0",
    lifespan=lifespan,
)

# Load configuration
config = ValidationConfig()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Initialize validation processor
validation_processor = ValidationProcessor(config)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "validation-service",
        "status": "running",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/health")
async def health_check():
    """Detailed health check endpoint."""
    try:
        health_status = await validation_processor.health_check()
        return {
            "service": "validation-service",
            "status": "healthy"
            if health_status.get("status") == "healthy"
            else "degraded",
            "ai_services": health_status.get("ai_services", {}),
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "service": "validation-service",
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }


@app.post("/validate/contact", response_model=ValidationResponse)
async def validate_contact(request: ValidationRequest) -> ValidationResponse:
    """
    Validate a contact using AI-powered underwriting rules.

    Args:
        request: Validation request with contact ID and optional context

    Returns:
        Validation response with results and overall status
    """
    try:
        logger.info(f"🔍 Starting validation for contact: {request.contact_id}")

        # Process validation
        results = await validation_processor.validate_contact(
            contact_id=request.contact_id,
            validation_types=request.validation_types,
            context=request.context,
        )

        # Determine overall status
        overall_status = "pass" if all(r.result == "Pass" for r in results) else "fail"

        logger.info(
            f"✅ Validation completed for {request.contact_id}: "
            f"{len(results)} checks, status={overall_status}"
        )

        return ValidationResponse(
            contact_id=request.contact_id,
            validation_results=[r.dict() for r in results],
            overall_status=overall_status,
            processed_at=datetime.utcnow(),
        )

    except Exception as e:
        logger.error(f"❌ Validation failed for {request.contact_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/validate/hardship")
async def validate_hardship(contact_id: str, hardship_description: str) -> dict:
    """
    Validate hardship claim using AI assessment.

    Args:
        contact_id: Contact identifier
        hardship_description: Hardship description text

    Returns:
        Hardship validation result
    """
    try:
        result = await validation_processor.validate_hardship_only(
            contact_id=contact_id, hardship_description=hardship_description
        )

        return {
            "contact_id": contact_id,
            "hardship_result": result.dict(),
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"❌ Hardship validation failed for {contact_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/validate/contract")
async def validate_contract(contact_id: str, contract_data: dict) -> dict:
    """
    Validate contract data using business rules.

    Args:
        contact_id: Contact identifier
        contract_data: Parsed contract data

    Returns:
        Contract validation results
    """
    try:
        results = await validation_processor.validate_contract_only(
            contact_id=contact_id, contract_data=contract_data
        )

        return {
            "contact_id": contact_id,
            "contract_results": [r.dict() for r in results],
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"❌ Contract validation failed for {contact_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/metrics")
async def get_metrics():
    """Get validation service metrics."""
    return validation_processor.get_metrics()


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=config.host,
        port=config.port,
        reload=config.debug,
        log_level=config.log_level.lower(),
    )
