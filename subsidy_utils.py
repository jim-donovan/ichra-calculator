"""
Subsidy Utilities - Single Source of Truth

Consolidates all subsidy eligibility logic into one module to ensure
consistent calculations across:
- contribution_strategies.py
- contribution_eval/components/action_bar.py
- contribution_eval/services/subsidy_service.py

Key concepts:
- LCSP (Lowest Cost Silver Plan): Used for IRS ICHRA affordability test
- SLCSP (Second Lowest Cost Silver Plan): Used for ACA subsidy calculation
- FPL (Federal Poverty Level): Determines subsidy amount based on income
- Affordability: ICHRA is "unaffordable" if employee cost > 9.96% of income
- Subsidy Eligibility: Employee can access subsidies if ICHRA is unaffordable AND subsidy > 0
"""

from typing import Dict, Any, Optional

from constants import (
    ACA_AGE_CURVE,
    AFFORDABILITY_THRESHOLD_2026,
    MEDICARE_ELIGIBILITY_AGE,
)


# =============================================================================
# FPL CONSTANTS (2025 Federal Poverty Level for 2026 plan year)
# =============================================================================
# Per ACA rules, 2025 FPL values are used for 2026 coverage year
# Source: HHS 2025 Poverty Guidelines
# https://www.mybenefitadvisor.com/articles/compliance/2025/q1/2025-federal-poverty-guidelines-announced/

FPL_2025_BASE = 15650  # 1 person (48 contiguous states + DC)
FPL_2025_PER_ADDITIONAL = 5500  # per additional person

# Household size mapping by family status
FAMILY_STATUS_HOUSEHOLD_SIZE = {
    'EE': 1,   # Employee only
    'ES': 2,   # Employee + Spouse
    'EC': 2,   # Employee + Child (assumes 1 child)
    'F': 4,    # Family (assumes 2 adults + 2 children)
}

# Buffer for subsidy optimization (90% = 10% safety margin below threshold)
AFFORDABILITY_BUFFER = 0.90


# =============================================================================
# FPL CALCULATION
# =============================================================================

def get_fpl_for_household(household_size: int) -> float:
    """
    Get Federal Poverty Level for a given household size.

    Uses 2025 FPL values (for 2026 plan year per ACA rules).

    Args:
        household_size: Number of people in household (1-8+)

    Returns:
        Annual FPL in dollars
    """
    if household_size < 1:
        household_size = 1
    return FPL_2025_BASE + (household_size - 1) * FPL_2025_PER_ADDITIONAL


def get_household_size(family_status: str) -> int:
    """
    Get household size from family status code.

    Args:
        family_status: EE, ES, EC, or F

    Returns:
        Estimated household size
    """
    return FAMILY_STATUS_HOUSEHOLD_SIZE.get(family_status.upper(), 1)


# =============================================================================
# ACA APPLICABLE PERCENTAGE
# =============================================================================

def get_applicable_percentage(annual_income: float, family_status: str = 'EE') -> float:
    """
    Calculate the ACA applicable percentage based on income as % of FPL.

    This is the percentage of income the person is expected to contribute
    toward health insurance premiums. Lower income = lower percentage.

    Uses 2025 FPL values and ACA sliding scale (with ARP enhancements).

    Args:
        annual_income: Annual household income in dollars
        family_status: EE, ES, EC, or F (determines household size for FPL)

    Returns:
        Applicable percentage as decimal (e.g., 0.04 for 4%)
    """
    if annual_income <= 0:
        return 0.0

    household_size = get_household_size(family_status)
    fpl = get_fpl_for_household(household_size)
    fpl_percentage = (annual_income / fpl) * 100

    # ACA sliding scale with ARP enhancements (2022-2025, likely extended to 2026)
    # These provide more generous subsidies than pre-ARP ACA
    if fpl_percentage <= 100:
        # Below poverty line - no expected contribution
        return 0.0
    elif fpl_percentage <= 150:
        # 100-150% FPL: 0% to 4% (linear interpolation)
        return (fpl_percentage - 100) / 50 * 0.04
    elif fpl_percentage <= 200:
        # 150-200% FPL: 4% to 6.5%
        return 0.04 + (fpl_percentage - 150) / 50 * 0.025
    elif fpl_percentage <= 250:
        # 200-250% FPL: 6.5% to 8.5%
        return 0.065 + (fpl_percentage - 200) / 50 * 0.02
    elif fpl_percentage <= 400:
        # 250-400% FPL: 8.5% cap (ARP enhancement)
        return 0.085
    else:
        # Above 400% FPL: 8.5% cap (ARP removed the cliff)
        # Pre-ARP, these folks would be ineligible for subsidies
        return 0.085


# =============================================================================
# SUBSIDY CALCULATION
# =============================================================================

def calculate_monthly_subsidy(
    slcsp: float,
    monthly_income: float,
    family_status: str = 'EE',
    lcsp: float = None,
) -> float:
    """
    Calculate estimated monthly ACA subsidy using FPL-based sliding scale.

    ACA subsidies are calculated based on SLCSP (Second Lowest Cost Silver Plan),
    not LCSP. The subsidy covers the gap between expected contribution and SLCSP.

    Subsidy = SLCSP - (Annual Income x Applicable Percentage / 12)

    Args:
        slcsp: Second Lowest Cost Silver Plan premium (monthly) - ACA benchmark
        monthly_income: Employee's monthly income
        family_status: EE, ES, EC, or F
        lcsp: Lowest Cost Silver Plan (optional, fallback if SLCSP unavailable)

    Returns:
        Estimated monthly subsidy (0 if negative or ineligible)
    """
    # Use SLCSP as primary benchmark, fall back to LCSP if not available
    benchmark = slcsp if slcsp and slcsp > 0 else lcsp

    if monthly_income <= 0 or not benchmark or benchmark <= 0:
        return 0.0

    # Convert to float in case it's a Decimal from database
    benchmark = float(benchmark)

    annual_income = monthly_income * 12
    applicable_pct = get_applicable_percentage(annual_income, family_status)

    # Expected monthly contribution = annual income x applicable % / 12
    expected_contribution = (annual_income * applicable_pct) / 12

    # Subsidy covers the difference between SLCSP (benchmark) and expected contribution
    return max(0.0, benchmark - expected_contribution)


# =============================================================================
# AGE FACTOR
# =============================================================================

def get_age_factor(age: int) -> float:
    """
    Get the ACA 3:1 age curve factor for a given age.

    Uses the federal default age rating curve.
    Age 21 = 1.0 (base), Age 64 = 3.0 (maximum).

    Args:
        age: Employee age

    Returns:
        Age factor (1.0 to 3.0)
    """
    # Clamp age to valid range (21-64 for adults in ACA curve)
    clamped_age = max(21, min(64, age))
    return ACA_AGE_CURVE.get(clamped_age, 1.0)


# =============================================================================
# EMPLOYEE COST CALCULATION
# =============================================================================

def calculate_employee_cost(lcsp: float, contribution: float) -> float:
    """
    Calculate employee's out-of-pocket cost for LCSP.

    Args:
        lcsp: Lowest Cost Silver Plan premium (monthly)
        contribution: Employer's monthly ICHRA contribution

    Returns:
        Employee's monthly cost (LCSP - contribution, minimum 0)
    """
    return max(0.0, lcsp - contribution)


# =============================================================================
# MAX CONTRIBUTION FOR ELIGIBILITY
# =============================================================================

def calculate_max_contribution_for_eligibility(
    lcsp: float,
    monthly_income: float,
    with_buffer: bool = True,
) -> Optional[float]:
    """
    Calculate maximum contribution that keeps ICHRA "unaffordable".

    For employee to access ACA subsidies, ICHRA must be unaffordable.
    This function calculates the max ER contribution that still keeps
    the ICHRA unaffordable for the employee.

    Formula:
    - Unaffordable if: Employee Cost > 9.96% x Income
    - Employee Cost = LCSP - Contribution
    - Max Contribution = LCSP - (9.96% x Income)
    - With buffer: Max Contribution x 90%

    Args:
        lcsp: Lowest Cost Silver Plan premium (monthly)
        monthly_income: Employee's monthly income
        with_buffer: Apply 10% safety margin (90% of max)

    Returns:
        Maximum contribution for eligibility, or None if already affordable
    """
    if monthly_income <= 0 or lcsp <= 0:
        return None

    threshold_cost = monthly_income * AFFORDABILITY_THRESHOLD_2026
    max_contribution = lcsp - threshold_cost

    if max_contribution < 0:
        # ICHRA is already affordable at any contribution level
        return None

    if with_buffer:
        max_contribution *= AFFORDABILITY_BUFFER

    return max(0.0, max_contribution)


# =============================================================================
# SUBSIDY ELIGIBILITY (UNIFIED)
# =============================================================================

def is_subsidy_eligible(
    monthly_income: float,
    lcsp: float,
    contribution: float,
    age: int,
    slcsp: float = None,
    family_status: str = 'EE',
) -> Dict[str, Any]:
    """
    Determine if an employee is eligible for ACA marketplace subsidies.

    An employee is subsidy-eligible if ALL of the following are true:
    1. Not Medicare-eligible (age < 65)
    2. Has income data
    3. ICHRA is unaffordable (employee cost > 9.96% of income)
    4. Would receive a subsidy (subsidy amount > 0)

    This is the SINGLE SOURCE OF TRUTH for subsidy eligibility.
    All other modules should call this function.

    Args:
        monthly_income: Employee's monthly income (None/0 = no income data)
        lcsp: Lowest Cost Silver Plan premium (monthly)
        contribution: Employer's monthly ICHRA contribution
        age: Employee age
        slcsp: Second Lowest Cost Silver Plan premium (optional, for subsidy calc)
        family_status: EE, ES, EC, or F

    Returns:
        Dict with:
        - eligible: bool (True if can access subsidies)
        - reason: str (explanation)
        - subsidy_amount: float (estimated monthly subsidy, 0 if ineligible)
        - is_medicare: bool (True if age >= 65)
        - is_unaffordable: bool (True if ICHRA is unaffordable)
        - employee_cost: float (LCSP - contribution)
        - affordability_pct: float (employee_cost / income * 100)
        - max_contribution_for_eligibility: float or None
    """
    result = {
        'eligible': False,
        'reason': '',
        'subsidy_amount': 0.0,
        'is_medicare': False,
        'is_unaffordable': False,
        'employee_cost': 0.0,
        'affordability_pct': None,
        'max_contribution_for_eligibility': None,
    }

    # Check Medicare eligibility first
    if age >= MEDICARE_ELIGIBILITY_AGE:
        result['is_medicare'] = True
        result['reason'] = 'Medicare-eligible (65+) - cannot receive ACA subsidies'
        return result

    # Check income data
    if monthly_income is None or monthly_income <= 0:
        result['reason'] = 'No income data - cannot determine eligibility'
        return result

    # Calculate employee cost
    employee_cost = calculate_employee_cost(lcsp, contribution)
    result['employee_cost'] = employee_cost

    # Calculate affordability percentage
    affordability_pct = (employee_cost / monthly_income) * 100 if monthly_income > 0 else 0
    result['affordability_pct'] = affordability_pct

    # Check if ICHRA is unaffordable
    threshold_cost = monthly_income * AFFORDABILITY_THRESHOLD_2026
    is_unaffordable = employee_cost > threshold_cost
    result['is_unaffordable'] = is_unaffordable

    # Calculate max contribution for eligibility (for display purposes)
    max_for_elig = calculate_max_contribution_for_eligibility(lcsp, monthly_income, with_buffer=True)
    result['max_contribution_for_eligibility'] = max_for_elig

    if not is_unaffordable:
        result['reason'] = 'ICHRA is affordable - must accept (cannot access subsidies)'
        return result

    # ICHRA is unaffordable - now check if they'd get a subsidy
    # Use SLCSP for subsidy calculation (ACA benchmark)
    benchmark = slcsp if slcsp and slcsp > 0 else lcsp
    subsidy = calculate_monthly_subsidy(benchmark, monthly_income, family_status, lcsp)

    if subsidy > 0:
        result['eligible'] = True
        result['subsidy_amount'] = subsidy
        result['reason'] = 'ICHRA unaffordable AND qualifies for ACA subsidy'
    else:
        result['reason'] = 'ICHRA unaffordable but income too high for subsidy (above 400% FPL)'

    return result


# =============================================================================
# BATCH ELIGIBILITY CHECK
# =============================================================================

def check_eligibility_for_contribution(
    employee_data: Dict[str, Any],
    contribution: float,
    lcsp: float,
    slcsp: float = None,
) -> Dict[str, Any]:
    """
    Check subsidy eligibility for a single employee at a given contribution level.

    Convenience function that extracts employee data and calls is_subsidy_eligible.

    Args:
        employee_data: Dict with employee fields (age, monthly_income, family_status)
        contribution: Employer's monthly ICHRA contribution
        lcsp: Lowest Cost Silver Plan premium (monthly)
        slcsp: Second Lowest Cost Silver Plan premium (optional)

    Returns:
        Result from is_subsidy_eligible()
    """
    age = int(employee_data.get('age', 30) or 30)
    monthly_income = employee_data.get('monthly_income')
    family_status = str(employee_data.get('family_status', 'EE')).upper()

    # Parse income if it's a string
    if isinstance(monthly_income, str):
        try:
            monthly_income = float(monthly_income.replace('$', '').replace(',', '').strip())
        except (ValueError, TypeError):
            monthly_income = None

    # Convert to float
    if monthly_income is not None:
        try:
            monthly_income = float(monthly_income)
            if monthly_income <= 0:
                monthly_income = None
        except (ValueError, TypeError):
            monthly_income = None

    return is_subsidy_eligible(
        monthly_income=monthly_income,
        lcsp=lcsp,
        contribution=contribution,
        age=age,
        slcsp=slcsp,
        family_status=family_status,
    )
