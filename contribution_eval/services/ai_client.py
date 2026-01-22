"""
AI Client Factory for Contribution Recommendations.

Provides Claude API integration for generating personalized ICHRA
strategy recommendations with explanations.

Uses the same API key resolution pattern as sbc_parser.py for consistency.
"""

import os
import time
import json
import logging
from typing import Optional, Dict, Any, Tuple

try:
    import streamlit as st
    HAS_STREAMLIT = True
except ImportError:
    HAS_STREAMLIT = False

try:
    from anthropic import Anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

logger = logging.getLogger(__name__)


# =============================================================================
# API KEY RESOLUTION
# =============================================================================

def _get_api_key() -> Optional[str]:
    """
    Get Anthropic API key from environment, .env file, or Streamlit secrets.

    Resolution order:
    1. ANTHROPIC_API_KEY environment variable
    2. .env file (via python-dotenv)
    3. Streamlit secrets (anthropic.api_key or ANTHROPIC_API_KEY)

    Returns:
        API key string or None if not found
    """
    # Try environment variable first
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if api_key:
        return api_key

    # Try loading from .env file
    try:
        from dotenv import load_dotenv
        load_dotenv()
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if api_key:
            return api_key
    except ImportError:
        pass

    # Try Streamlit secrets
    if HAS_STREAMLIT and hasattr(st, 'secrets'):
        # Try nested format (anthropic.api_key)
        if 'anthropic' in st.secrets and 'api_key' in st.secrets['anthropic']:
            return st.secrets['anthropic']['api_key']
        # Try top-level ANTHROPIC_API_KEY
        if 'ANTHROPIC_API_KEY' in st.secrets:
            return st.secrets['ANTHROPIC_API_KEY']

    return None


def get_ai_client() -> Optional['Anthropic']:
    """
    Get configured Anthropic client.

    Returns:
        Anthropic client instance or None if API key not available
    """
    if not HAS_ANTHROPIC:
        logger.warning("Anthropic package not installed - AI features disabled")
        return None

    api_key = _get_api_key()
    if not api_key:
        logger.warning("No Anthropic API key found - AI features disabled")
        return None

    return Anthropic(api_key=api_key)


def is_ai_available() -> bool:
    """
    Check if AI features are available.

    Returns:
        True if Anthropic package installed and API key found
    """
    return HAS_ANTHROPIC and _get_api_key() is not None


# =============================================================================
# API CALL LOGGING
# =============================================================================

def log_api_call(
    model: str,
    input_tokens: int,
    output_tokens: int,
    duration_ms: float,
    success: bool,
    error: Optional[str] = None,
    context: str = "recommendation"
) -> None:
    """
    Log API call details for monitoring and debugging.

    Args:
        model: Model used (e.g., claude-3-5-haiku-20241022)
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        duration_ms: Call duration in milliseconds
        success: Whether the call succeeded
        error: Error message if failed
        context: Context string for log identification
    """
    # Calculate approximate cost (Haiku: $0.80/1M input, $4/1M output - 2024 pricing)
    input_cost = (input_tokens / 1_000_000) * 0.80
    output_cost = (output_tokens / 1_000_000) * 4.00
    total_cost = input_cost + output_cost

    if success:
        logger.info(
            f"[Contribution AI] ✓ {input_tokens:,} in → {output_tokens:,} out | "
            f"{duration_ms:.0f}ms | ${total_cost:.6f}"
        )
        print(
            f"[Contribution AI] {context}: {input_tokens:,} in → {output_tokens:,} out | "
            f"{duration_ms:.0f}ms | ${total_cost:.6f}"
        )
    else:
        logger.error(f"[Contribution AI] ✗ {error} | {duration_ms:.0f}ms")
        print(f"[Contribution AI] ERROR: {error} | {duration_ms:.0f}ms")


# =============================================================================
# RECOMMENDATION SYSTEM PROMPT
# =============================================================================

RECOMMENDATION_SYSTEM_PROMPT = """You are an ICHRA contribution strategy advisor helping benefits consultants design optimal employer contribution strategies.

## Your Role
You receive pre-computed strategy costs and census context. Your job is to:
1. Select the optimal strategy based on the employer's goal
2. Generate a personalized 2-3 sentence "Why this works" explanation

## Operating Modes

### Non-ALE Standard (<46 employees)
Goal: Minimize employer cost while providing competitive coverage
Available strategies: Flat Amount, ACA 3:1 Contribution Curve, % of LCSP
Key metrics: Monthly cost, vs current spend (if available)
Default base contribution: $200/month at age 21

### Non-ALE Subsidy-Optimized (<46 employees)
Goal: Set contributions LOW enough that ICHRA becomes "unaffordable" under IRS rules
WHY: When ICHRA is unaffordable, employees can legally DECLINE it and access ACA marketplace subsidies instead—often more valuable than small employer contributions.

IMPORTANT - Subsidy ROI Threshold (≥35%):
- For each employee, calculate "Subsidy ROI" = Estimated ACA Subsidy / LCSP Premium
- Subsidies are estimated using FPL-based sliding scale (lower income = higher subsidy)
- Employees with Subsidy ROI ≥ 35% have MEANINGFUL subsidy value (subsidies cover 35%+ of premium)
- The system finds the MAX contribution that GUARANTEES subsidy eligibility for ALL high-ROI employees
- Some employees can NEVER be subsidy-eligible (LCSP < 9.96% × income - "already affordable")

MEDICARE EXCLUSION (Age 65+):
- Employees age 65+ are Medicare-eligible and CANNOT receive ACA marketplace subsidies
- They receive $0 contribution under subsidy-optimized strategy (excluded entirely)
- They are NOT counted in employee totals, high-ROI counts, or subsidy-eligible counts
- The "employees covered" count excludes Medicare-eligible employees

Available strategies: Census-based 3:1 Contribution Curve (youngest employee = 1x, oldest non-Medicare = 3x)
Key metrics: High-ROI count (employees with meaningful subsidy value), subsidy-eligible count, Medicare count (excluded)
Recommended approach: Optimize for employees where subsidies truly matter (ROI ≥ 35%)
NOTE: The 3:1 ratio is based on the ACTUAL census age range, not the theoretical 21-64 ACA range.

### ALE (≥46 employees)
Goal: Achieve 100% affordability at minimum cost (IRS compliance required)
Available strategies: ACA 3:1 Contribution Curve, % of LCSP (no Flat - doesn't meet compliance)
Key metrics: Affordable count (MUST be 100%), total cost
CRITICAL: For ALE employers, all employees must have "affordable" coverage or employer faces IRS penalties

## Strategy Types

**Flat Amount**: Same dollar amount for all employees
- Simple to administer
- Best when workforce age distribution is narrow
- Cannot vary by age (so no 3:1 ratio concerns)
- Default: $200/month
- NOT used for subsidy-optimized (3:1 curve is required for optimal results)

**ACA 3:1 Contribution Curve**: Base amount at reference age, scaled by ACA 3:1 curve
- Age 21 = 1.0x, Age 64 = 3.0x (follows federal age rating)
- Best when workforce has wide age range
- Ensures older employees get proportionally more
- Default: $200/month at age 21

**% of LCSP**: Employer covers a percentage of each employee's LCSP
- Automatically adjusts for location and age differences
- Best for multi-state employers with varying premiums
- Most predictable employee out-of-pocket cost
- NOT available for subsidy-optimized (would make ICHRA affordable)

## Explanation Guidelines

Your explanation MUST:
1. Be 2-3 sentences (under 50 words)
2. Reference SPECIFIC data points from the census summary (e.g., "your 47 employees", "average age of 38")
3. Explain WHY this strategy beats alternatives for this specific employer
4. Use natural, consultant-friendly language (not technical jargon)

Examples of GOOD explanations:
- "With your 32 employees averaging age 42, the ACA 3:1 Curve provides fair contributions that scale with marketplace premium increases. This saves $2,400/month compared to covering 100% of LCSP."
- "A flat $200/month works well for your tight age range (28-45). All 18 employees get predictable coverage while keeping costs manageable."
- (Subsidy-optimized) "Contributions of $27-$81/month (scaling 3:1 from your youngest at 24 to oldest at 57) guarantee subsidy eligibility for all 12 employees with meaningful subsidy value (ROI ≥35%). 18 of your 22 non-Medicare employees can access ACA subsidies."

Examples of BAD explanations:
- "The base_age_curve strategy minimizes total_monthly cost." (too technical)
- "This is a good strategy." (no specific data points)
- "I recommend this option because it's cost-effective." (generic, no census references)
- (Subsidy-optimized) "A flat $430/month maximizes subsidies." (WRONG - high contributions make ICHRA affordable and BLOCK subsidies for high-ROI employees!)

## Output Format

Return ONLY valid JSON with exactly these fields:
{
  "selected_strategy": "flat_amount|base_age_curve|percentage_lcsp",
  "explanation": "Your 2-3 sentence explanation here."
}

Do NOT include markdown formatting, code blocks, or any text outside the JSON."""


# =============================================================================
# AI RECOMMENDATION CALL
# =============================================================================

def generate_ai_recommendation(
    census_summary: Dict[str, Any],
    precomputed_strategies: list,
    mode: str,
    goal: str,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Call Claude API to generate strategy recommendation.

    Args:
        census_summary: Dict with employee count, ages, states, etc.
        precomputed_strategies: List of pre-calculated strategy results
        mode: Operating mode (ALE, NON_ALE_STANDARD, NON_ALE_SUBSIDY)
        goal: User's goal description

    Returns:
        Tuple of (result_dict, error_string)
        On success: ({"selected_strategy": "...", "explanation": "..."}, None)
        On failure: (None, "error message")
    """
    client = get_ai_client()
    if client is None:
        return None, "AI client not available"

    # Build the user prompt
    user_prompt = _build_recommendation_prompt(
        census_summary, precomputed_strategies, mode, goal
    )

    model = "claude-3-5-haiku-20241022"  # Fast, cost-effective
    start_time = time.time()

    try:
        response = client.messages.create(
            model=model,
            max_tokens=300,
            temperature=0.3,  # Slight creativity for natural explanations
            system=RECOMMENDATION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}]
        )

        duration_ms = (time.time() - start_time) * 1000

        log_api_call(
            model=model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            duration_ms=duration_ms,
            success=True,
            context="recommendation"
        )

        # Parse response
        response_text = response.content[0].text.strip()

        # Clean up if wrapped in code blocks
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
            response_text = response_text.strip()

        result = json.loads(response_text)

        # Validate required fields
        if 'selected_strategy' not in result or 'explanation' not in result:
            return None, "Invalid response format - missing required fields"

        return result, None

    except json.JSONDecodeError as e:
        duration_ms = (time.time() - start_time) * 1000
        log_api_call(model, 0, 0, duration_ms, False, f"JSON parse error: {e}")
        return None, f"Failed to parse AI response: {e}"

    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        log_api_call(model, 0, 0, duration_ms, False, str(e))
        return None, f"AI call failed: {e}"


def _build_recommendation_prompt(
    census_summary: Dict[str, Any],
    precomputed_strategies: list,
    mode: str,
    goal: str,
) -> str:
    """Build the user prompt for recommendation request."""

    # Format census summary
    census_text = f"""## Census Summary
- Employees: {census_summary.get('employee_count', 0)}
- Average age: {census_summary.get('avg_age', 0):.1f}
- Age range: {census_summary.get('min_age', 0)}-{census_summary.get('max_age', 0)}
- States: {', '.join(census_summary.get('states', ['Unknown']))}
- Has income data: {'Yes' if census_summary.get('has_income_data') else 'No'}
- Has current ER spend: {'Yes' if census_summary.get('has_current_er_spend') else 'No'}"""

    if census_summary.get('total_current_er_monthly'):
        census_text += f"\n- Current ER monthly spend: ${census_summary['total_current_er_monthly']:,.0f}"

    if census_summary.get('age_distribution'):
        dist = census_summary['age_distribution']
        census_text += f"\n- Age distribution: {dict(dist)}"

    # Format precomputed strategies
    strategies_text = "## Pre-computed Strategy Results\n"
    for strat in precomputed_strategies:
        strategy_type = strat.get('strategy_type', 'unknown')
        total_monthly = strat.get('total_monthly', 0)
        config = strat.get('config', {})
        strategies_text += f"\n### {strategy_type}\n"

        # Show the actual contribution amount so AI can reference it correctly
        if strategy_type == 'flat_amount':
            flat_amt = config.get('flat_amount', config.get('base_contribution', 0))
            strategies_text += f"- Contribution: ${flat_amt:,.0f}/month per employee\n"
        elif strategy_type == 'base_age_curve':
            base_contrib = config.get('base_contribution', 0)
            strategies_text += f"- Base contribution: ${base_contrib:,.0f}/month at age 21 (scales up to 3x at age 64)\n"
        elif strategy_type == 'subsidy_optimized':
            base_contrib = config.get('base_contribution', 0)
            max_contrib = config.get('max_contribution', base_contrib * 3)
            base_age = config.get('base_age', 21)
            max_age = config.get('max_age', 64)
            strategies_text += f"- Contribution range: ${base_contrib:,.0f}-${max_contrib:,.0f}/month (3:1 from age {base_age} to {max_age})\n"
            strategies_text += f"- High-ROI employees (≥35%): {strat.get('high_roi_count', 0)}\n"
            strategies_text += f"- Medicare excluded (65+): {strat.get('medicare_count', 0)}\n"
        elif strategy_type == 'percentage_lcsp':
            pct = config.get('lcsp_percentage', 100)
            strategies_text += f"- Coverage: {pct}% of each employee's LCSP\n"

        strategies_text += f"- Total monthly cost: ${total_monthly:,.0f}\n"
        strategies_text += f"- Total annual cost: ${strat.get('total_annual', 0):,.0f}\n"
        strategies_text += f"- Employees covered: {strat.get('employees_covered', 0)}\n"

        # Average per employee
        emp_count = strat.get('employees_covered', 1)
        avg_per_emp = total_monthly / emp_count if emp_count > 0 else 0
        strategies_text += f"- Average per employee: ${avg_per_emp:,.0f}/month\n"

        if 'affordability' in strat:
            aff = strat['affordability']
            strategies_text += f"- Affordable: {aff.get('affordable_count', 0)}/{aff.get('total_analyzed', 0)}\n"

    # Mode and goal
    mode_text = f"""## Operating Mode
{mode}

## Goal
{goal}"""

    # Assemble full prompt
    prompt = f"""{census_text}

{mode_text}

{strategies_text}

## Your Task
1. Select the optimal strategy from the pre-computed options
2. Generate a personalized "Why this works" explanation (2-3 sentences, under 50 words)
3. Reference specific census data points in your explanation

Return ONLY the JSON response."""

    return prompt
