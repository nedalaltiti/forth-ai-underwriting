"""
Hardship assessment models with comprehensive Pydantic validation.
Models for AI-powered hardship evaluation and validation.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, validator, model_validator

from .base_models import TimestampedModel, ValidationStatus, ConfidenceLevel


class HardshipCategory(str, Enum):
    """Categories of financial hardship."""
    JOB_LOSS = "job_loss"
    MEDICAL = "medical"
    DIVORCE = "divorce"
    INCOME_REDUCTION = "income_reduction"
    EMERGENCY = "emergency"
    DISABILITY = "disability"
    FAMILY_CHANGE = "family_change"
    ECONOMIC_DOWNTURN = "economic_downturn"
    OTHER = "other"


class SeverityLevel(str, Enum):
    """Severity levels for hardship impact."""
    MILD = "mild"
    MODERATE = "moderate"
    SEVERE = "severe"
    CRITICAL = "critical"


class FinancialImpact(str, Enum):
    """Financial impact levels."""
    MINIMAL = "minimal"
    MODERATE = "moderate"
    SIGNIFICANT = "significant"
    DEVASTATING = "devastating"


class TimeframeCategory(str, Enum):
    """Timeframe categories for hardship."""
    RECENT = "recent"
    ONGOING = "ongoing"
    CHRONIC = "chronic"
    TEMPORARY = "temporary"


class DescriptionQuality(BaseModel):
    """Quality assessment of hardship description."""
    length_category: str = Field(..., description="Length category of description")
    specificity: str = Field(..., description="Level of specificity")
    emotional_authenticity: str = Field(..., description="Emotional authenticity level")
    clarity: str = Field(..., description="Clarity of description")
    
    @validator('length_category')
    def validate_length(cls, v):
        valid_lengths = ['empty', 'minimal', 'brief', 'adequate', 'detailed']
        if v not in valid_lengths:
            raise ValueError(f"Length category must be one of: {valid_lengths}")
        return v
    
    @validator('specificity')
    def validate_specificity(cls, v):
        valid_levels = ['vague', 'general', 'specific', 'very_specific']
        if v not in valid_levels:
            raise ValueError(f"Specificity must be one of: {valid_levels}")
        return v
    
    @validator('emotional_authenticity')
    def validate_authenticity(cls, v):
        valid_levels = ['low', 'medium', 'high']
        if v not in valid_levels:
            raise ValueError(f"Emotional authenticity must be one of: {valid_levels}")
        return v
    
    @validator('clarity')
    def validate_clarity(cls, v):
        valid_levels = ['unclear', 'somewhat_clear', 'clear', 'very_clear']
        if v not in valid_levels:
            raise ValueError(f"Clarity must be one of: {valid_levels}")
        return v


class HardshipAnalysis(BaseModel):
    """Detailed analysis of hardship characteristics."""
    primary_category: HardshipCategory = Field(..., description="Primary hardship category")
    severity_level: SeverityLevel = Field(..., description="Severity of hardship")
    financial_impact: FinancialImpact = Field(..., description="Financial impact level")
    timeframe: TimeframeCategory = Field(..., description="Timeframe category")
    legitimacy_indicators: List[str] = Field(default_factory=list, description="Indicators of legitimacy")
    secondary_categories: List[HardshipCategory] = Field(default_factory=list, description="Additional hardship categories")
    
    @validator('legitimacy_indicators')
    def validate_indicators(cls, v):
        if not v:
            return []
        # Ensure indicators are meaningful
        return [indicator.strip() for indicator in v if indicator.strip()]


class AssessmentResult(BaseModel):
    """Core assessment result."""
    is_valid: bool = Field(..., description="Whether hardship is valid")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    overall_score: int = Field(..., ge=0, le=100, description="Overall assessment score")
    recommendation: str = Field(..., description="Assessment recommendation")
    
    @validator('recommendation')
    def validate_recommendation(cls, v):
        valid_recommendations = ['approve', 'review', 'decline', 'conditional_approve']
        if v not in valid_recommendations:
            raise ValueError(f"Recommendation must be one of: {valid_recommendations}")
        return v
    
    @model_validator(mode='before')
    @classmethod
    def validate_consistency(cls, values):
        is_valid = values.get('is_valid')
        confidence = values.get('confidence', 0)
        recommendation = values.get('recommendation')
        
        # Ensure consistency between validity and recommendation
        if is_valid and recommendation == 'decline':
            raise ValueError("Cannot recommend decline for valid hardship")
        
        if not is_valid and recommendation == 'approve':
            raise ValueError("Cannot recommend approve for invalid hardship")
        
        # Low confidence should not result in approve
        if confidence < 0.5 and recommendation == 'approve':
            raise ValueError("Cannot recommend approve with low confidence")
        
        return values


class HardshipRecommendations(BaseModel):
    """Recommendations based on hardship assessment."""
    program_eligibility: str = Field(..., description="Program eligibility status")
    additional_documentation: List[str] = Field(default_factory=list, description="Additional docs needed")
    follow_up_questions: List[str] = Field(default_factory=list, description="Clarification questions")
    special_considerations: List[str] = Field(default_factory=list, description="Special circumstances")
    
    @validator('program_eligibility')
    def validate_eligibility(cls, v):
        valid_statuses = ['qualified', 'conditionally_qualified', 'not_qualified']
        if v not in valid_statuses:
            raise ValueError(f"Program eligibility must be one of: {valid_statuses}")
        return v


class HardshipAssessment(TimestampedModel):
    """Complete hardship assessment with AI analysis."""
    
    # Input data
    hardship_description: str = Field(..., min_length=1, description="Original hardship description")
    client_context: Optional[Dict[str, Any]] = Field(None, description="Additional client context")
    
    # Assessment results
    assessment_result: AssessmentResult = Field(..., description="Core assessment result")
    hardship_analysis: HardshipAnalysis = Field(..., description="Detailed hardship analysis")
    description_quality: DescriptionQuality = Field(..., description="Quality of description")
    
    # Detailed findings
    keywords_found: List[str] = Field(default_factory=list, description="Relevant keywords identified")
    detailed_reasoning: str = Field(..., description="Comprehensive reasoning")
    risk_factors: List[str] = Field(default_factory=list, description="Risk factors identified")
    strengths: List[str] = Field(default_factory=list, description="Positive factors")
    recommendations: HardshipRecommendations = Field(..., description="Recommendations")
    
    # Processing metadata
    ai_model_version: Optional[str] = Field(None, description="AI model version used")
    processing_time_ms: Optional[int] = Field(None, ge=0, description="Processing time")
    validation_flags: List[str] = Field(default_factory=list, description="Validation flags")
    
    @validator('hardship_description')
    def validate_description(cls, v):
        if not v or not v.strip():
            raise ValueError("Hardship description cannot be empty")
        return v.strip()
    
    @validator('detailed_reasoning')
    def validate_reasoning(cls, v):
        if len(v.strip()) < 20:
            raise ValueError("Detailed reasoning must be at least 20 characters")
        return v.strip()
    
    @model_validator(mode='before')
    @classmethod
    def validate_assessment_consistency(cls, values):
        """Validate consistency across all assessment components."""
        assessment_result = values.get('assessment_result')
        hardship_analysis = values.get('hardship_analysis')
        
        if not assessment_result or not hardship_analysis:
            return values
        
        # Check if severe hardship with low validity makes sense
        if (hardship_analysis.severity_level in [SeverityLevel.SEVERE, SeverityLevel.CRITICAL] and
            not assessment_result.is_valid):
            # This might be inconsistent, add to validation flags
            if 'validation_flags' not in values:
                values['validation_flags'] = []
            values['validation_flags'].append("severe_hardship_marked_invalid")
        
        # Check confidence consistency with assessment
        if assessment_result.confidence > 0.8 and not assessment_result.is_valid:
            if 'validation_flags' not in values:
                values['validation_flags'] = []
            values['validation_flags'].append("high_confidence_invalid_assessment")
        
        return values
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a concise summary of the assessment."""
        return {
            "is_valid": self.assessment_result.is_valid,
            "confidence": self.assessment_result.confidence,
            "category": self.hardship_analysis.primary_category.value,
            "severity": self.hardship_analysis.severity_level.value,
            "recommendation": self.assessment_result.recommendation,
            "program_eligible": self.recommendations.program_eligibility,
            "key_strengths": self.strengths[:3],  # Top 3 strengths
            "main_concerns": self.risk_factors[:3],  # Top 3 concerns
            "processing_time": self.processing_time_ms
        }
    
    def requires_human_review(self) -> bool:
        """Determine if this assessment requires human review."""
        # Low confidence assessments need review
        if self.assessment_result.confidence < 0.6:
            return True
        
        # Assessments with validation flags need review
        if self.validation_flags:
            return True
        
        # Critical severity hardships marked as invalid need review
        if (self.hardship_analysis.severity_level == SeverityLevel.CRITICAL and 
            not self.assessment_result.is_valid):
            return True
        
        # Conditional approvals need review
        if self.assessment_result.recommendation in ['review', 'conditional_approve']:
            return True
        
        return False


class HardshipValidationHistory(BaseModel):
    """Historical record of hardship validations."""
    client_id: str = Field(..., description="Client identifier")
    assessments: List[HardshipAssessment] = Field(default_factory=list, description="Historical assessments")
    last_assessment_date: Optional[datetime] = Field(None, description="Date of last assessment")
    total_assessments: int = Field(default=0, ge=0, description="Total number of assessments")
    
    def add_assessment(self, assessment: HardshipAssessment):
        """Add a new assessment to the history."""
        self.assessments.append(assessment)
        self.last_assessment_date = assessment.created_at
        self.total_assessments = len(self.assessments)
    
    def get_latest_assessment(self) -> Optional[HardshipAssessment]:
        """Get the most recent assessment."""
        if not self.assessments:
            return None
        return max(self.assessments, key=lambda a: a.created_at)
    
    def get_assessment_trend(self) -> Dict[str, Any]:
        """Analyze trends in assessments over time."""
        if len(self.assessments) < 2:
            return {"trend": "insufficient_data"}
        
        recent = self.assessments[-3:]  # Last 3 assessments
        improving = all(
            recent[i].assessment_result.confidence >= recent[i-1].assessment_result.confidence
            for i in range(1, len(recent))
        )
        
        return {
            "trend": "improving" if improving else "declining",
            "latest_confidence": recent[-1].assessment_result.confidence,
            "average_confidence": sum(a.assessment_result.confidence for a in recent) / len(recent),
            "consistency": len(set(a.assessment_result.is_valid for a in recent)) == 1
        } 