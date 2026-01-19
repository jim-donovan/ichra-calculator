"""
ACA Premium Tax Credit (Subsidy) Calculator for Unaffordability Analysis

This module calculates potential ACA marketplace subsidies for employees
who may decline ICHRA due to unaffordability. Used to determine if employees
would be better off with marketplace subsidies vs ICHRA contributions.

Key concepts:
- LCSP (Lowest Cost Silver Plan): Used for IRS ICHRA affordability test
- SLCSP (Second Lowest Cost Silver Plan): Used for ACA subsidy calculation
- FPL (Federal Poverty Level): Determines subsidy amount based on income
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import pandas as pd

from constants import (
    FPL_2026_BY_HOUSEHOLD_SIZE,
    FPL_2026_PER_ADDITIONAL_PERSON,
    FPL_2026_ALASKA,
    FPL_2026_ALASKA_PER_ADDITIONAL,
    FPL_2026_HAWAII,
    FPL_2026_HAWAII_PER_ADDITIONAL,
    ACA_APPLICABLE_PERCENTAGE_2026,
    ACA_SUBSIDY_FPL_CAP,
    MEDICARE_ELIGIBILITY_AGE,
    AFFORDABILITY_THRESHOLD_2026,
)


@dataclass
class SubsidyAnalysisResult:
    """Result of subsidy analysis for a single employee."""
    employee_id: str
    employee_name: str
    age: int
    state: str
    family_status: str
    annual_income: float
    monthly_income: float
    household_size: int

    # ICHRA analysis
    lcsp_premium: float
    er_contribution: float
    ee_cost_with_ichra: float
    max_affordable_ee_cost: float
    is_affordable: bool

    # Subsidy analysis (only if under 65)
    slcsp_premium: Optional[float] = None
    fpl_percentage: Optional[float] = None
    applicable_percentage: Optional[float] = None
    expected_contribution: Optional[float] = None
    subsidy_value: Optional[float] = None

    # Medicare flag
    is_medicare_eligible: bool = False

    # Recommendation
    recommendation: str = 'ICHRA'  # 'ICHRA' or 'Subsidy'
    net_benefit: float = 0.0

    # Notes
    notes: str = ''


def get_fpl_for_household(household_size: int, state: str = None) -> float:
    """
    Get Federal Poverty Level for a given household size.

    Args:
        household_size: Number of people in household (1-8+)
        state: Optional state code for Alaska/Hawaii adjustments

    Returns:
        Annual FPL in dollars
    """
    # Select appropriate FPL table
    if state == 'AK':
        fpl_table = FPL_2026_ALASKA
        per_additional = FPL_2026_ALASKA_PER_ADDITIONAL
    elif state == 'HI':
        fpl_table = FPL_2026_HAWAII
        per_additional = FPL_2026_HAWAII_PER_ADDITIONAL
    else:
        fpl_table = FPL_2026_BY_HOUSEHOLD_SIZE
        per_additional = FPL_2026_PER_ADDITIONAL_PERSON

    # Cap at 8 for direct lookup, add per-person for larger households
    if household_size <= 8:
        return fpl_table.get(household_size, fpl_table[1])
    else:
        base = fpl_table[8]
        additional_people = household_size - 8
        return base + (additional_people * per_additional)


def get_applicable_percentage(fpl_percentage: float) -> Optional[float]:
    """
    Get the applicable percentage of income for ACA subsidy calculation.

    Uses linear interpolation within FPL brackets per 2026 ACA rules.

    Args:
        fpl_percentage: Household income as percentage of FPL (e.g., 200 for 200% FPL)

    Returns:
        Applicable percentage (0-9.96%), or None if above 400% FPL
    """
    if fpl_percentage < 100:
        # Below 100% FPL - typically Medicaid eligible, but use lowest bracket
        return 2.10

    if fpl_percentage > ACA_SUBSIDY_FPL_CAP:
        # Above 400% FPL - no subsidy
        return None

    # Find the appropriate bracket and interpolate
    for lower_fpl, upper_fpl, lower_pct, upper_pct in ACA_APPLICABLE_PERCENTAGE_2026:
        if lower_fpl <= fpl_percentage <= upper_fpl:
            # Linear interpolation
            if upper_fpl == lower_fpl:
                return lower_pct

            ratio = (fpl_percentage - lower_fpl) / (upper_fpl - lower_fpl)
            return lower_pct + (upper_pct - lower_pct) * ratio

    # Shouldn't reach here, but default to highest bracket
    return 9.96


def calculate_monthly_subsidy(
    annual_income: float,
    slcsp_premium: float,
    household_size: int = 1,
    state: str = None
) -> Dict[str, Any]:
    """
    Calculate ACA premium tax credit (monthly subsidy).

    Args:
        annual_income: Annual household income in dollars
        slcsp_premium: Monthly Second Lowest Cost Silver Plan premium
        household_size: Number of people in household
        state: State code (for Alaska/Hawaii FPL adjustments)

    Returns:
        Dict with calculation details:
        - subsidy: Monthly subsidy amount
        - fpl_percentage: Income as % of FPL
        - applicable_percentage: % of income expected as contribution
        - expected_contribution: Monthly expected contribution
        - eligible: Whether eligible for subsidy
    """
    fpl = get_fpl_for_household(household_size, state)
    fpl_percentage = (annual_income / fpl) * 100

    # Check eligibility (above 400% FPL = no subsidy)
    if fpl_percentage > ACA_SUBSIDY_FPL_CAP:
        return {
            'subsidy': 0.0,
            'fpl_percentage': fpl_percentage,
            'applicable_percentage': None,
            'expected_contribution': slcsp_premium,  # Pay full premium
            'eligible': False,
            'reason': f'Income exceeds {ACA_SUBSIDY_FPL_CAP}% FPL'
        }

    applicable_pct = get_applicable_percentage(fpl_percentage)

    if applicable_pct is None:
        return {
            'subsidy': 0.0,
            'fpl_percentage': fpl_percentage,
            'applicable_percentage': None,
            'expected_contribution': slcsp_premium,
            'eligible': False,
            'reason': 'No applicable percentage for this FPL level'
        }

    # Calculate expected contribution (what employee is expected to pay)
    annual_expected = annual_income * (applicable_pct / 100)
    monthly_expected = annual_expected / 12

    # Subsidy = SLCSP premium - expected contribution (but not negative)
    subsidy = max(0, slcsp_premium - monthly_expected)

    return {
        'subsidy': round(subsidy, 2),
        'fpl_percentage': round(fpl_percentage, 1),
        'applicable_percentage': round(applicable_pct, 2),
        'expected_contribution': round(monthly_expected, 2),
        'eligible': subsidy > 0,
        'reason': None
    }


def analyze_employee_unaffordability(
    employee: Dict[str, Any],
    er_contribution: float,
    lcsp_premium: float,
    slcsp_premium: Optional[float] = None,
    household_size: int = 1
) -> SubsidyAnalysisResult:
    """
    Analyze whether an employee is better off with ICHRA or marketplace subsidy.

    Args:
        employee: Dict with employee data (age, income, state, etc.)
        er_contribution: Employer's monthly ICHRA contribution
        lcsp_premium: Monthly Lowest Cost Silver Plan premium (for affordability test)
        slcsp_premium: Monthly Second Lowest Cost Silver Plan premium (for subsidy calc)
        household_size: Household size for FPL calculation

    Returns:
        SubsidyAnalysisResult with full analysis
    """
    # Extract employee info
    employee_id = str(employee.get('employee_id') or
                      employee.get('Employee Number') or
                      employee.get('employee_number', ''))

    first_name = str(employee.get('first_name') or
                     employee.get('First Name', '')).strip()
    last_name = str(employee.get('last_name') or
                    employee.get('Last Name', '')).strip()
    employee_name = f"{first_name} {last_name}".strip() or employee_id

    age = int(employee.get('age') or employee.get('ee_age') or
              employee.get('Age', 30))

    state = str(employee.get('state') or
                employee.get('Home State', '')).upper()

    family_status = str(employee.get('family_status') or
                        employee.get('Family Status', 'EE')).upper()

    # Get income
    monthly_income = employee.get('monthly_income', 0)
    if pd.isna(monthly_income) or monthly_income is None:
        monthly_income = 0
    if isinstance(monthly_income, str):
        monthly_income = float(str(monthly_income).replace('$', '').replace(',', '').strip() or 0)
    monthly_income = float(monthly_income)
    annual_income = monthly_income * 12

    # Check Medicare eligibility
    is_medicare = age >= MEDICARE_ELIGIBILITY_AGE

    # Calculate ICHRA affordability (uses LCSP)
    max_affordable_ee_cost = monthly_income * AFFORDABILITY_THRESHOLD_2026
    ee_cost_with_ichra = lcsp_premium - er_contribution
    is_affordable = ee_cost_with_ichra <= max_affordable_ee_cost

    # Build result
    result = SubsidyAnalysisResult(
        employee_id=employee_id,
        employee_name=employee_name,
        age=age,
        state=state,
        family_status=family_status,
        annual_income=annual_income,
        monthly_income=monthly_income,
        household_size=household_size,
        lcsp_premium=lcsp_premium,
        er_contribution=er_contribution,
        ee_cost_with_ichra=ee_cost_with_ichra,
        max_affordable_ee_cost=max_affordable_ee_cost,
        is_affordable=is_affordable,
        is_medicare_eligible=is_medicare,
    )

    # Medicare employees - ICHRA only, no subsidy comparison
    if is_medicare:
        result.recommendation = 'ICHRA'
        result.net_benefit = er_contribution
        result.notes = 'Medicare-eligible - not eligible for ACA marketplace subsidies'
        return result

    # If no income data, can't calculate subsidy
    if monthly_income <= 0:
        result.recommendation = 'ICHRA'
        result.net_benefit = er_contribution
        result.notes = 'No income data - cannot calculate subsidy eligibility'
        return result

    # If no SLCSP data, can't calculate subsidy
    if slcsp_premium is None or slcsp_premium <= 0:
        result.recommendation = 'ICHRA'
        result.net_benefit = er_contribution
        result.notes = 'No SLCSP data available'
        return result

    # Calculate potential subsidy (uses SLCSP)
    subsidy_calc = calculate_monthly_subsidy(
        annual_income=annual_income,
        slcsp_premium=slcsp_premium,
        household_size=household_size,
        state=state
    )

    result.slcsp_premium = slcsp_premium
    result.fpl_percentage = subsidy_calc['fpl_percentage']
    result.applicable_percentage = subsidy_calc['applicable_percentage']
    result.expected_contribution = subsidy_calc['expected_contribution']
    result.subsidy_value = subsidy_calc['subsidy'] if not is_affordable else 0

    # Determine recommendation
    if is_affordable:
        # If ICHRA is affordable, employee cannot decline and get subsidy
        result.recommendation = 'ICHRA'
        result.net_benefit = er_contribution
        result.notes = 'ICHRA is affordable - employee must use ICHRA (subsidy not available)'
    else:
        # ICHRA is unaffordable - employee can decline and potentially get subsidy
        subsidy = subsidy_calc['subsidy']

        if subsidy > er_contribution:
            result.recommendation = 'Subsidy'
            result.net_benefit = subsidy
            result.notes = f'Better off with subsidy (${subsidy:,.0f}) than ICHRA (${er_contribution:,.0f})'
        else:
            result.recommendation = 'ICHRA'
            result.net_benefit = er_contribution
            result.notes = f'ICHRA contribution (${er_contribution:,.0f}) exceeds potential subsidy (${subsidy:,.0f})'

    return result


def analyze_workforce_unaffordability(
    census_df: pd.DataFrame,
    employee_contributions: Dict[str, Dict],
    lcsp_data: Dict[str, Dict],
    slcsp_data: Dict[str, Dict],
    household_size: int = 1
) -> Dict[str, Any]:
    """
    Analyze unaffordability for entire workforce.

    Args:
        census_df: Employee census DataFrame
        employee_contributions: Dict of employee_id -> {monthly_contribution, ...}
        lcsp_data: Dict of employee_id -> {lcsp_premium, ...}
        slcsp_data: Dict of employee_id -> {slcsp_premium, ...}
        household_size: Default household size for FPL calculation

    Returns:
        Dict with:
        - summary: Aggregate statistics
        - under_65: List of SubsidyAnalysisResult for non-Medicare employees
        - medicare: List of SubsidyAnalysisResult for Medicare employees
        - recommendations: Summary of recommendations
    """
    under_65_results: List[SubsidyAnalysisResult] = []
    medicare_results: List[SubsidyAnalysisResult] = []

    for _, employee in census_df.iterrows():
        emp_id = str(employee.get('employee_id') or
                     employee.get('Employee Number') or
                     employee.get('employee_number', ''))

        # Get contribution
        contrib_data = employee_contributions.get(emp_id, {})
        er_contribution = contrib_data.get('monthly_contribution', 0)

        # Get LCSP
        lcsp_info = lcsp_data.get(emp_id, {})
        lcsp_premium = lcsp_info.get('lcsp_premium', 0) or lcsp_info.get('lcsp_ee_rate', 0)

        # Get SLCSP
        slcsp_info = slcsp_data.get(emp_id, {})
        slcsp_premium = slcsp_info.get('slcsp_premium', 0)

        # Skip if no LCSP data
        if not lcsp_premium or lcsp_premium <= 0:
            continue

        # Analyze employee
        result = analyze_employee_unaffordability(
            employee=employee.to_dict(),
            er_contribution=er_contribution,
            lcsp_premium=lcsp_premium,
            slcsp_premium=slcsp_premium,
            household_size=household_size
        )

        if result.is_medicare_eligible:
            medicare_results.append(result)
        else:
            under_65_results.append(result)

    # Calculate summary statistics
    total_under_65 = len(under_65_results)
    affordable_count = sum(1 for r in under_65_results if r.is_affordable)
    unaffordable_count = total_under_65 - affordable_count

    subsidy_recommended = sum(1 for r in under_65_results
                               if r.recommendation == 'Subsidy')

    total_er_ichra = sum(r.er_contribution for r in under_65_results)
    total_er_ichra_affordable = sum(r.er_contribution for r in under_65_results
                                     if r.is_affordable)
    total_subsidies = sum(r.subsidy_value or 0 for r in under_65_results
                          if not r.is_affordable and r.subsidy_value)

    # Net benefit calculation for unaffordable employees
    net_employee_benefit = 0
    for r in under_65_results:
        if not r.is_affordable and r.subsidy_value:
            # Benefit = subsidy they get - ICHRA they forgo
            net_employee_benefit += max(0, r.subsidy_value - r.er_contribution)

    summary = {
        'total_employees': total_under_65 + len(medicare_results),
        'under_65_count': total_under_65,
        'medicare_count': len(medicare_results),
        'affordable_count': affordable_count,
        'unaffordable_count': unaffordable_count,
        'subsidy_recommended_count': subsidy_recommended,
        'total_er_ichra_monthly': total_er_ichra,
        'total_er_ichra_affordable_monthly': total_er_ichra_affordable,
        'total_potential_subsidies_monthly': total_subsidies,
        'net_employee_benefit_monthly': net_employee_benefit,
    }

    return {
        'summary': summary,
        'under_65': under_65_results,
        'medicare': medicare_results,
    }


def can_use_unaffordability_strategy(strategy_type: str) -> bool:
    """
    Check if the unaffordability strategy applies to this contribution strategy.

    FPL Safe Harbor guarantees affordability by definition, so unaffordability
    analysis doesn't apply.

    Args:
        strategy_type: The contribution strategy type

    Returns:
        True if unaffordability analysis is applicable
    """
    # FPL Safe Harbor cannot use unaffordability strategy
    incompatible_strategies = ['fpl_safe_harbor']
    return strategy_type.lower() not in incompatible_strategies
