"""
Validation prompts for budget analysis and debt validation.
Specialized prompts for financial analysis and debt compliance checking.
"""

from typing import Dict, Any, List
from .prompt_manager import PromptTemplate, PromptCategory, PromptVersion, get_prompt_manager


class ValidationPrompts:
    """Container for all validation-related prompts."""
    
    @staticmethod
    def register_all_prompts():
        """Register all validation prompts with the prompt manager."""
        manager = get_prompt_manager()
        
        # Budget Analysis Prompt
        budget_analysis_prompt = PromptTemplate(
            name="budget_analysis",
            category=PromptCategory.BUDGET_ANALYSIS,
            version=PromptVersion.V2_0,
            system_prompt="""You are an expert financial analyst specializing in debt settlement program qualification. Your role is to analyze client budgets for program viability, sustainability, and compliance with underwriting guidelines.

BUDGET ANALYSIS FRAMEWORK:
1. Income Verification & Stability Assessment
2. Expense Categorization & Reasonableness
3. Debt-to-Income (DTI) Ratio Calculation
4. Surplus/Deficit Analysis
5. Program Affordability Assessment
6. Financial Sustainability Projection

KEY REQUIREMENTS:
- DTI ratio should be 60-100% for optimal qualification
- Must have positive surplus after essential expenses
- Monthly payment capacity should be reasonable and sustainable
- Emergency fund considerations
- Geographic cost-of-living adjustments

ANALYSIS CRITERIA:
- Income stability and source reliability
- Expense reasonableness for family size and location
- Debt payment sustainability
- Program fee affordability
- Long-term financial viability""",
            
            user_prompt_template="""Analyze the following budget information for debt settlement program qualification:

INCOME INFORMATION:
{income_details}

EXPENSE BREAKDOWN:
{expense_details}

DEBT SUMMARY:
{debt_summary}

CLIENT PROFILE:
- Family Size: {family_size}
- Location: {location}
- Employment Status: {employment_status}
- Credit Score: {credit_score}

Provide comprehensive budget analysis in JSON format:

{{
    "income_analysis": {{
        "total_monthly_income": "calculated total income",
        "income_stability": "stable/variable/unstable",
        "primary_income_source": "employment/self_employed/benefits/other",
        "income_verification_level": "verified/stated/estimated",
        "seasonal_variations": "none/minimal/moderate/significant"
    }},
    "expense_analysis": {{
        "total_monthly_expenses": "calculated total expenses",
        "essential_expenses": "housing, utilities, food, transportation, insurance",
        "discretionary_expenses": "non-essential spending",
        "expense_reasonableness": "below_average/average/above_average/excessive",
        "potential_reductions": ["areas where expenses could be reduced"]
    }},
    "debt_analysis": {{
        "total_debt_amount": "sum of all debts",
        "monthly_debt_payments": "current monthly debt obligations",
        "debt_to_income_ratio": "DTI percentage",
        "dti_compliance": "meets_requirements/borderline/exceeds_limits",
        "debt_composition": "primarily_unsecured/mixed/secured_heavy"
    }},
    "surplus_analysis": {{
        "monthly_surplus": "income minus expenses",
        "surplus_after_debt_payments": "surplus after current debt payments",
        "available_for_program": "estimated monthly capacity for program",
        "sustainability_rating": "excellent/good/marginal/poor"
    }},
    "program_viability": {{
        "qualified_for_program": true/false,
        "recommended_monthly_payment": "suggested program payment amount",
        "qualification_confidence": 0.0-1.0,
        "risk_level": "low/medium/high",
        "estimated_program_duration": "months to complete program"
    }},
    "recommendations": {{
        "approval_recommendation": "approve/conditional_approve/decline",
        "conditions": ["any conditions for approval"],
        "required_documentation": ["additional docs needed"],
        "budget_improvement_suggestions": ["suggestions for better qualification"],
        "follow_up_requirements": ["items to verify or monitor"]
    }},
    "red_flags": ["concerning financial patterns or issues"],
    "detailed_analysis": "Comprehensive explanation of findings and recommendations"
}}

CALCULATION REQUIREMENTS:
- All financial figures should be monthly amounts
- DTI = (Total Monthly Debt Payments / Gross Monthly Income) × 100
- Surplus = Income - Expenses
- Consider geographic cost adjustments
- Factor in program fees and settlement savings""",
            
            format_instructions="""Return detailed budget analysis in JSON format with all calculations and recommendations clearly explained.""",
            
            required_variables=["income_details", "expense_details", "debt_summary"],
            optional_variables=["family_size", "location", "employment_status", "credit_score"],
            
            output_schema={
                "income_analysis": dict,
                "expense_analysis": dict,
                "debt_analysis": dict,
                "surplus_analysis": dict,
                "program_viability": dict,
                "recommendations": dict,
                "red_flags": list,
                "detailed_analysis": str
            },
            
            metadata={
                "purpose": "Comprehensive budget analysis for debt settlement qualification",
                "compliance_standards": "NTS underwriting guidelines v2.0"
            }
        )
        
        # Debt Validation Prompt
        debt_validation_prompt = PromptTemplate(
            name="debt_validation",
            category=PromptCategory.DEBT_VALIDATION,
            version=PromptVersion.V2_0,
            system_prompt="""You are a debt validation specialist for debt settlement programs. Your role is to analyze debt portfolios for program eligibility, compliance with guidelines, and identification of high-risk or prohibited debt types.

DEBT VALIDATION REQUIREMENTS:
1. Minimum $10,000 total enrolled debt
2. Majority must be unsecured debt (credit cards, personal loans, collections)
3. No individual debt under $500 (with rare exceptions)
4. Exclude prohibited debt types and high-risk creditors
5. Verify debt legitimacy and current status

PROHIBITED/HIGH-RISK CREDITORS:
- Government agencies (IRS, state taxes, student loans)
- Secured debts (mortgages, auto loans unless surrendering)
- Recent lawsuits or judgments
- Family/friend loans
- Business debts for active businesses
- Utility deposits
- HOA fees

ACCEPTABLE DEBT TYPES:
- Credit cards (major banks and credit unions)
- Personal loans (unsecured)
- Medical bills and collections
- Store credit cards
- Old collection accounts
- Charged-off accounts

VALIDATION CRITERIA:
- Debt age and statute of limitations
- Creditor reputation and settlement likelihood
- Account status and collectibility
- Documentation requirements""",
            
            user_prompt_template="""Validate the following debt portfolio for debt settlement program eligibility:

DEBT PORTFOLIO:
{debt_list}

CREDITOR VALIDATION DATA:
{creditor_database}

CLIENT INFORMATION:
- Total Income: ${monthly_income}
- State: {client_state}
- Program Type: {program_type}

Perform comprehensive debt validation in JSON format:

{{
    "portfolio_summary": {{
        "total_debt_amount": "sum of all debts",
        "account_count": "number of debt accounts",
        "meets_minimum_requirement": true/false,
        "average_debt_amount": "average per account",
        "largest_single_debt": "amount of largest debt"
    }},
    "debt_composition": {{
        "unsecured_debt_amount": "total unsecured debt",
        "unsecured_percentage": "percentage of portfolio that's unsecured",
        "secured_debt_amount": "total secured debt",
        "meets_composition_requirements": true/false
    }},
    "creditor_analysis": {{
        "acceptable_creditors": ["list of approved creditors"],
        "high_risk_creditors": ["list of risky creditors"],
        "prohibited_creditors": ["list of prohibited creditors"],
        "unknown_creditors": ["creditors needing research"]
    }},
    "account_validation": [
        {{
            "creditor_name": "creditor name",
            "debt_amount": "amount owed",
            "debt_type": "credit_card/personal_loan/medical/collection/other",
            "status": "acceptable/conditional/prohibited",
            "risk_level": "low/medium/high",
            "settlement_likelihood": "excellent/good/fair/poor",
            "concerns": ["any issues with this debt"],
            "required_documentation": ["docs needed for this account"]
        }}
    ],
    "compliance_check": {{
        "minimum_debt_met": true/false,
        "individual_minimums_met": true/false,
        "composition_compliant": true/false,
        "creditor_compliance": true/false,
        "overall_compliance": "compliant/non_compliant/conditional"
    }},
    "risk_assessment": {{
        "portfolio_risk": "low/medium/high",
        "lawsuit_risk": "low/medium/high",
        "settlement_viability": "excellent/good/fair/poor",
        "program_success_likelihood": 0.0-1.0
    }},
    "recommendations": {{
        "enrollment_recommendation": "approve/conditional/decline",
        "debts_to_exclude": ["accounts that should not be enrolled"],
        "additional_verification": ["items requiring further validation"],
        "program_modifications": ["suggested changes to program structure"],
        "monitoring_requirements": ["ongoing monitoring needs"]
    }},
    "detailed_findings": "Comprehensive analysis of debt portfolio and recommendations"
}}

VALIDATION RULES:
- Flag any debt under $500 unless exceptional circumstances
- Identify creditors known for aggressive litigation
- Check for recent payment activity indicating ongoing relationships
- Verify debt ages and statute of limitations by state
- Assess settlement negotiation prospects for each creditor""",
            
            format_instructions="""Return comprehensive debt validation analysis with specific recommendations for each account and overall portfolio.""",
            
            required_variables=["debt_list"],
            optional_variables=["creditor_database", "monthly_income", "client_state", "program_type"],
            
            output_schema={
                "portfolio_summary": dict,
                "debt_composition": dict,
                "creditor_analysis": dict,
                "account_validation": list,
                "compliance_check": dict,
                "risk_assessment": dict,
                "recommendations": dict,
                "detailed_findings": str
            }
        )
        
        # Financial Profile Analysis Prompt
        financial_profile_prompt = PromptTemplate(
            name="financial_profile_analysis",
            category=PromptCategory.GENERAL_VALIDATION,
            version=PromptVersion.V1_0,
            system_prompt="""You are a comprehensive financial analyst evaluating complete client profiles for debt settlement program suitability. Consider all aspects of the client's financial situation.""",
            
            user_prompt_template="""Analyze the complete financial profile for program qualification:

CLIENT PROFILE:
{client_data}

FINANCIAL DATA:
{financial_data}

HARDSHIP INFORMATION:
{hardship_data}

Provide complete financial assessment in JSON format:

{{
    "overall_assessment": {{
        "program_suitability": "excellent/good/marginal/poor",
        "qualification_status": "qualified/conditionally_qualified/not_qualified",
        "confidence_level": 0.0-1.0,
        "primary_concerns": ["main issues affecting qualification"]
    }},
    "financial_capacity": {{
        "income_adequacy": "sufficient/marginal/insufficient",
        "expense_management": "excellent/good/needs_improvement/poor",
        "debt_burden": "manageable/challenging/overwhelming",
        "payment_capacity": "strong/adequate/limited/insufficient"
    }},
    "risk_factors": {{
        "income_stability": "stable/at_risk/unstable",
        "expense_volatility": "predictable/somewhat_variable/highly_variable",
        "compliance_risk": "low/medium/high",
        "completion_likelihood": 0.0-1.0
    }},
    "recommendations": {{
        "program_structure": "standard/modified/specialized",
        "monitoring_level": "standard/enhanced/intensive",
        "success_strategies": ["recommendations for program success"]
    }}
}}""",
            
            required_variables=["client_data", "financial_data", "hardship_data"],
            optional_variables=[]
        )
        
        # Register all prompts
        manager.register_prompt(budget_analysis_prompt)
        manager.register_prompt(debt_validation_prompt)
        manager.register_prompt(financial_profile_prompt)


def get_budget_analysis_prompt(**kwargs) -> Dict[str, str]:
    """Get rendered budget analysis prompt."""
    return get_prompt_manager().render_prompt("budget_analysis", **kwargs)


def get_debt_validation_prompt(**kwargs) -> Dict[str, str]:
    """Get rendered debt validation prompt."""
    return get_prompt_manager().render_prompt("debt_validation", **kwargs)


def get_financial_profile_prompt(**kwargs) -> Dict[str, str]:
    """Get rendered financial profile analysis prompt."""
    return get_prompt_manager().render_prompt("financial_profile_analysis", **kwargs)


# Auto-register prompts when module is imported
# ValidationPrompts.register_all_prompts()  # Temporarily disabled for testing 