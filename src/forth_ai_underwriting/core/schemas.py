from pydantic import BaseModel
from typing import Optional


class ValidationResult(BaseModel):
    """Represents the result of a single validation check."""
    title: str
    result: str  # e.g., "Pass", "No Pass"
    reason: str
    confidence: Optional[float] = None  # Confidence score for AI-driven validations


