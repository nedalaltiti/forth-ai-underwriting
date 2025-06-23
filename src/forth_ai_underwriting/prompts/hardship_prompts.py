"""
Hardship assessment prompts for AI-powered validation.
Specialized prompts for evaluating financial hardship claims in debt settlement.
"""

from typing import Dict, Any, List
from .prompt_manager import PromptTemplate, PromptCategory, PromptVersion, get_prompt_manager


class HardshipAssessmentPrompts:
    """Container for all hardship assessment prompts."""
    
    @staticmethod
    def register_all_prompts():
        """Register all hardship assessment prompts with the prompt manager."""
        manager = get_prompt_manager()
        
        # Primary Hardship Assessment Prompt
        hardship_assessment_prompt = PromptTemplate(
            name="hardship_assessment",
            category=PromptCategory.HARDSHIP_ASSESSMENT,
            version=PromptVersion.V2_0,
            system_prompt="""You are an expert financial hardship analyst specializing in debt settlement program qualification. Your role is to evaluate hardship claims for legitimacy, severity, and program eligibility.

HARDSHIP EVALUATION FRAMEWORK:
1. Legitimacy Assessment - Is this a genuine financial hardship?
2. Severity Analysis - How significantly does this impact financial capacity?
3. Relevance Check - Is this hardship related to debt settlement needs?
4. Documentation Quality - How well is the hardship described?
5. Program Eligibility - Does this qualify for debt settlement assistance?

ACCEPTABLE HARDSHIP CATEGORIES:
- Employment Issues: job loss, unemployment, reduced hours, layoffs, business closure
- Medical/Health: illness, medical bills, disability, injury, chronic conditions
- Family Changes: divorce, separation, death of income provider, dependent care
- Income Reduction: salary cuts, commission loss, retirement, benefit reduction
- Emergency Expenses: home repairs, vehicle breakdown, unexpected major costs
- Economic Factors: inflation impact, cost of living increases, economic downturn

ASSESSMENT CRITERIA:
- Even single-word entries can be valid if they indicate legitimate hardship
- Brief descriptions are acceptable if they clearly communicate hardship
- Look for emotional authenticity and specific details
- Consider cumulative impact of multiple factors
- Evaluate timeframe and ongoing nature of hardship

QUALITY INDICATORS:
- Specific details and circumstances
- Emotional authenticity in description
- Clear connection to financial impact
- Reasonable timeline and context
- Consistency with debt settlement needs""",
            
            user_prompt_template="""Analyze the following hardship description for debt settlement program qualification:

HARDSHIP DESCRIPTION:
"{hardship_description}"

ADDITIONAL CONTEXT (if available):
- Client Age: {client_age}
- Family Size: {family_size}
- Employment Status: {employment_status}
- Monthly Income: {monthly_income}
- Total Debt: {total_debt}

Provide comprehensive assessment in JSON format:

{{
    "assessment_result": {{
        "is_valid": true/false,
        "confidence": 0.0-1.0,
        "overall_score": 0-100,
        "recommendation": "approve/review/decline"
    }},
    "hardship_analysis": {{
        "primary_category": "job_loss/medical/divorce/income_reduction/emergency/other",
        "severity_level": "mild/moderate/severe/critical",
        "financial_impact": "minimal/moderate/significant/devastating",
        "timeframe": "recent/ongoing/chronic/temporary",
        "legitimacy_indicators": ["list of legitimacy factors found"]
    }},
    "description_quality": {{
        "length_category": "empty/minimal/brief/adequate/detailed",
        "specificity": "vague/general/specific/very_specific",
        "emotional_authenticity": "low/medium/high",
        "clarity": "unclear/somewhat_clear/clear/very_clear"
    }},
    "keywords_found": ["list", "of", "relevant", "hardship", "keywords"],
    "detailed_reasoning": "Comprehensive explanation of assessment decision",
    "risk_factors": ["any concerns or red flags identified"],
    "strengths": ["positive factors supporting validity"],
    "recommendations": {{
        "program_eligibility": "qualified/conditionally_qualified/not_qualified",
        "additional_documentation": ["list if additional info needed"],
        "follow_up_questions": ["suggested clarification questions"],
        "special_considerations": ["any special circumstances to note"]
    }}
}}

ASSESSMENT GUIDELINES:
1. Empty descriptions automatically fail
2. Single valid hardship words (unemployment, medical, divorce) can pass with moderate confidence
3. Brief but clear descriptions should pass with good confidence
4. Detailed, specific hardships receive highest confidence scores
5. Multiple hardship factors increase severity and confidence
6. Consider context and proportionality to client situation
7. Flag any suspicious or inconsistent patterns""",
            
            format_instructions="""Return a comprehensive JSON assessment with all required fields. Confidence scores should be decimal values between 0.0 and 1.0. Overall scores should be integers between 0-100.""",
            
            required_variables=["hardship_description"],
            optional_variables=["client_age", "family_size", "employment_status", "monthly_income", "total_debt"],
            
            output_schema={
                "assessment_result": dict,
                "hardship_analysis": dict,
                "description_quality": dict,
                "keywords_found": list,
                "detailed_reasoning": str,
                "risk_factors": list,
                "strengths": list,
                "recommendations": dict
            },
            
            examples=[
                {
                    "input_description": "Lost my job due to company downsizing in March 2024",
                    "expected_result": {
                        "is_valid": True,
                        "confidence": 0.85,
                        "primary_category": "job_loss",
                        "severity_level": "severe"
                    }
                },
                {
                    "input_description": "Unemployment",
                    "expected_result": {
                        "is_valid": True,
                        "confidence": 0.65,
                        "primary_category": "job_loss",
                        "severity_level": "moderate"
                    }
                }
            ],
            
            metadata={
                "purpose": "Comprehensive hardship assessment for debt settlement qualification",
                "accuracy_target": "90% correlation with human underwriter decisions",
                "sensitivity": "High - err on side of client assistance when borderline"
            }
        )
        
        # Hardship Validation Prompt (for secondary review)
        hardship_validation_prompt = PromptTemplate(
            name="hardship_validation",
            category=PromptCategory.HARDSHIP_ASSESSMENT,
            version=PromptVersion.V1_0,
            system_prompt="""You are a senior underwriting reviewer specializing in hardship validation. Your role is to perform secondary validation of hardship assessments and flag cases requiring manual review.""",
            
            user_prompt_template="""Review this hardship assessment for accuracy and completeness:

ORIGINAL HARDSHIP DESCRIPTION:
"{hardship_description}"

INITIAL AI ASSESSMENT:
{initial_assessment}

CLIENT FINANCIAL PROFILE:
- Monthly Income: ${monthly_income}
- Total Debt: ${total_debt}
- DTI Ratio: {dti_ratio}%
- Credit Score: {credit_score}

Provide validation review in JSON format:

{{
    "validation_result": {{
        "assessment_confirmed": true/false,
        "confidence_in_assessment": 0.0-1.0,
        "requires_human_review": true/false,
        "validation_score": 0-100
    }},
    "consistency_check": {{
        "hardship_matches_profile": true/false,
        "severity_appropriate": true/false,
        "timeline_reasonable": true/false,
        "documentation_sufficient": true/false
    }},
    "red_flags": ["any concerning patterns or inconsistencies"],
    "validation_notes": "Detailed notes on assessment quality",
    "final_recommendation": "approve/conditional_approve/manual_review/decline"
}}""",
            
            required_variables=["hardship_description", "initial_assessment", "monthly_income", "total_debt", "dti_ratio", "credit_score"],
            optional_variables=[]
        )
        
        # Hardship Keywords Extraction Prompt
        hardship_keywords_prompt = PromptTemplate(
            name="hardship_keywords_extraction",
            category=PromptCategory.HARDSHIP_ASSESSMENT,
            version=PromptVersion.V1_0,
            system_prompt="""You are a text analysis specialist focusing on financial hardship keyword extraction. Identify and categorize hardship-related terms and phrases.""",
            
            user_prompt_template="""Extract and categorize hardship-related keywords from this description:

HARDSHIP DESCRIPTION:
"{hardship_description}"

Extract keywords in JSON format:

{{
    "employment_keywords": ["job-related terms found"],
    "medical_keywords": ["health/medical terms found"],
    "family_keywords": ["family change terms found"],
    "financial_keywords": ["money/finance terms found"],
    "emergency_keywords": ["emergency/unexpected terms found"],
    "emotional_indicators": ["emotional expressions found"],
    "temporal_indicators": ["time-related phrases"],
    "severity_indicators": ["terms indicating severity level"],
    "impact_keywords": ["terms showing financial impact"],
    "overall_sentiment": "positive/neutral/negative/distressed"
}}""",
            
            required_variables=["hardship_description"],
            optional_variables=[]
        )
        
        # Register all prompts
        manager.register_prompt(hardship_assessment_prompt)
        manager.register_prompt(hardship_validation_prompt)
        manager.register_prompt(hardship_keywords_prompt)


def get_hardship_assessment_prompt(**kwargs) -> Dict[str, str]:
    """Get rendered hardship assessment prompt."""
    return get_prompt_manager().render_prompt("hardship_assessment", **kwargs)


def get_hardship_validation_prompt(**kwargs) -> Dict[str, str]:
    """Get rendered hardship validation prompt."""
    return get_prompt_manager().render_prompt("hardship_validation", **kwargs)


def get_hardship_keywords_prompt(**kwargs) -> Dict[str, str]:
    """Get rendered hardship keywords extraction prompt."""
    return get_prompt_manager().render_prompt("hardship_keywords_extraction", **kwargs)


# Auto-register prompts when module is imported
# HardshipAssessmentPrompts.register_all_prompts()  # Temporarily disabled for testing 