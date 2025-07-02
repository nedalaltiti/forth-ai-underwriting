from pydantic import BaseModel
from typing import Optional


class ValidationResult(BaseModel):
    """Represents the result of a single validation check."""
    title: str
    result: str  # e.g., "Pass", "No Pass"
    reason: str
    confidence: Optional[float] = None  # Confidence score for AI-driven validations

    def __init__(self, title_or_kwargs=None, result=None, reason=None, confidence=None, **kwargs):
        """Initialize ValidationResult with positional or keyword arguments."""
        if isinstance(title_or_kwargs, str) and result is not None and reason is not None:
            # Called with positional arguments
            super().__init__(title=title_or_kwargs, result=result, reason=reason, confidence=confidence)
        elif isinstance(title_or_kwargs, dict):
            # Called with a dict
            super().__init__(**title_or_kwargs)
        else:
            # Called with keyword arguments
            super().__init__(title=title_or_kwargs, result=result, reason=reason, confidence=confidence, **kwargs)


