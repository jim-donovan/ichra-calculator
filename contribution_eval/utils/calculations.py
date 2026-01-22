"""
Calculation utilities for Contribution Evaluation.

Provides helper functions for census analysis, contribution calculations,
and strategy previews.
"""

from typing import Dict, List, Optional, Any, Tuple
import pandas as pd
import numpy as np

from constants import ACA_AGE_CURVE

# Import from parent module
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from contribution_eval import CensusContext
from census_schema import (
    COL_AGE, COL_STATE, COL_FAMILY_STATUS,
    COL_MONTHLY_INCOME, COL_CURRENT_ER,
)


# Age bands for grouping (matches PRD FR-7 requirements)
AGE_BANDS = [
    ('21-29', 21, 29),
    ('30-39', 30, 39),
    ('40-49', 40, 49),
    ('50-59', 50, 59),
    ('60-64', 60, 64),
]


def calculate_age_band(age: int) -> str:
    """
    Get the age band for a given age.

    Args:
        age: Employee age

    Returns:
        Age band string (e.g., "21-29", "30-39")
    """
    for band_name, min_age, max_age in AGE_BANDS:
        if min_age <= age <= max_age:
            return band_name
    if age < 21:
        return "21-29"  # Group with youngest band
    return "60-64"  # Group with oldest band


def build_census_context(census_df: pd.DataFrame) -> CensusContext:
    """
    Build census context from DataFrame for mode detection and analysis.

    This is computed once when entering the page and used throughout
    for mode detection and strategy recommendations.

    Args:
        census_df: Census DataFrame with employee data

    Returns:
        CensusContext with computed demographics and statistics
    """
    if census_df is None or census_df.empty:
        return CensusContext(
            employee_count=0,
            has_income_data=False,
            has_current_er_spend=False,
            avg_age=0,
            min_age=0,
            max_age=0,
            age_distribution={},
            states=[],
            is_multi_state=False,
            family_status_distribution={},
        )

    employee_count = len(census_df)

    # Check for income data (use canonical column name from normalized census)
    income_col = COL_MONTHLY_INCOME if COL_MONTHLY_INCOME in census_df.columns else None

    has_income_data = False
    avg_income = None
    if income_col:
        income_values = census_df[income_col].replace('', np.nan).dropna()
        # Parse currency strings
        if len(income_values) > 0:
            def parse_income(val):
                if pd.isna(val) or val == '':
                    return np.nan
                if isinstance(val, (int, float)):
                    return float(val)
                return float(str(val).replace('$', '').replace(',', '').strip() or np.nan)

            income_values = income_values.apply(parse_income)
            valid_incomes = income_values.dropna()
            if len(valid_incomes) > 0:
                has_income_data = True
                avg_income = valid_incomes.mean()

    # Check for current ER spend (use canonical column name from normalized census)
    er_col = COL_CURRENT_ER if COL_CURRENT_ER in census_df.columns else None

    has_current_er_spend = False
    total_current_er_monthly = None
    if er_col:
        er_values = census_df[er_col].replace('', np.nan).dropna()
        if len(er_values) > 0:
            def parse_currency(val):
                if pd.isna(val) or val == '':
                    return 0
                if isinstance(val, (int, float)):
                    return float(val)
                return float(str(val).replace('$', '').replace(',', '').strip() or 0)

            er_values = er_values.apply(parse_currency)
            total = er_values.sum()
            if total > 0:
                has_current_er_spend = True
                total_current_er_monthly = total

    # Get ages (use canonical column name from normalized census)
    age_col = COL_AGE if COL_AGE in census_df.columns else None

    ages = []
    if age_col:
        ages = census_df[age_col].dropna().astype(int).tolist()

    avg_age = np.mean(ages) if ages else 0
    min_age = min(ages) if ages else 0
    max_age = max(ages) if ages else 0

    # Age distribution by band
    age_distribution = {}
    for age in ages:
        band = calculate_age_band(age)
        age_distribution[band] = age_distribution.get(band, 0) + 1

    # Get states (use canonical column name from normalized census)
    state_col = COL_STATE if COL_STATE in census_df.columns else None

    states = []
    if state_col:
        states = census_df[state_col].dropna().str.upper().unique().tolist()

    is_multi_state = len(states) > 1

    # Family status distribution (use canonical column name from normalized census)
    fs_col = COL_FAMILY_STATUS if COL_FAMILY_STATUS in census_df.columns else None

    family_status_distribution = {}
    if fs_col:
        fs_counts = census_df[fs_col].str.upper().value_counts().to_dict()
        for status in ['EE', 'ES', 'EC', 'F']:
            family_status_distribution[status] = fs_counts.get(status, 0)

    return CensusContext(
        employee_count=employee_count,
        has_income_data=has_income_data,
        has_current_er_spend=has_current_er_spend,
        avg_age=round(avg_age, 1),
        min_age=min_age,
        max_age=max_age,
        age_distribution=age_distribution,
        states=states,
        is_multi_state=is_multi_state,
        family_status_distribution=family_status_distribution,
        total_current_er_monthly=total_current_er_monthly,
        avg_income=avg_income,
    )


def calculate_contribution_preview(
    strategy_type: str,
    base_age: int,
    base_contribution: float,
    preview_ages: List[int] = None
) -> List[Tuple[int, float]]:
    """
    Calculate contribution amounts at specific ages for preview display.

    Used in the Customize panel to show how contributions vary by age
    under the selected strategy.

    Args:
        strategy_type: Strategy type (e.g., 'base_age_curve', 'flat_amount')
        base_age: Base age for age curve strategies
        base_contribution: Base contribution amount
        preview_ages: List of ages to calculate (default: 21, 30, 40, 50, 64)

    Returns:
        List of (age, contribution) tuples
    """
    if preview_ages is None:
        preview_ages = [21, 30, 40, 50, 64]

    if strategy_type == 'flat_amount':
        # Flat amount: same for all ages
        return [(age, base_contribution) for age in preview_ages]

    elif strategy_type == 'base_age_curve':
        # Age curve: scale by ACA 3:1 ratio
        base_ratio = ACA_AGE_CURVE.get(base_age, 1.0)
        results = []
        for age in preview_ages:
            age_ratio = ACA_AGE_CURVE.get(min(age, 64), 1.0)
            contribution = base_contribution * (age_ratio / base_ratio)
            results.append((age, round(contribution, 2)))
        return results

    elif strategy_type == 'percentage_lcsp':
        # Can't preview without actual LCSP data
        # Return placeholder indicating it varies
        return [(age, None) for age in preview_ages]

    else:
        # FPL Safe Harbor or unknown: varies by employee
        return [(age, None) for age in preview_ages]


def calculate_3_1_ratio_check(
    employee_contributions: Dict[str, Dict],
    strategy_type: str
) -> Dict[str, Any]:
    """
    Check if contributions comply with ICHRA 3:1 age ratio rule.

    The 3:1 rule states that the highest contribution (oldest employee)
    cannot exceed 3x the lowest contribution (youngest employee).
    This only applies to age-based strategies.

    Args:
        employee_contributions: Dict of employee_id -> contribution data
        strategy_type: Strategy type being used

    Returns:
        Dict with:
        - compliant: bool
        - min_contribution: float
        - max_contribution: float
        - actual_ratio: float
        - warning: Optional[str]
    """
    # Only check for age-based strategies
    if strategy_type not in ['base_age_curve', 'fixed_age_tiers']:
        return {
            'compliant': True,
            'not_applicable': True,
            'reason': 'No age-based variation in contributions'
        }

    if not employee_contributions:
        return {
            'compliant': True,
            'not_applicable': True,
            'reason': 'No employees to check'
        }

    # Get base contributions (before family multipliers)
    contributions = []
    for emp_id, data in employee_contributions.items():
        base = data.get('base_contribution', data.get('monthly_contribution', 0))
        contributions.append(base)

    if not contributions:
        return {
            'compliant': True,
            'not_applicable': True,
            'reason': 'No contribution data'
        }

    min_contrib = min(contributions)
    max_contrib = max(contributions)

    if min_contrib <= 0:
        return {
            'compliant': False,
            'warning': 'Some employees have zero or negative contributions'
        }

    actual_ratio = max_contrib / min_contrib

    if actual_ratio <= 3.0:
        return {
            'compliant': True,
            'min_contribution': min_contrib,
            'max_contribution': max_contrib,
            'actual_ratio': round(actual_ratio, 2),
        }
    else:
        return {
            'compliant': False,
            'min_contribution': min_contrib,
            'max_contribution': max_contrib,
            'actual_ratio': round(actual_ratio, 2),
            'warning': f'Ratio of {actual_ratio:.2f}:1 exceeds 3:1 limit'
        }


def calculate_affordability_summary(
    employee_contributions: Dict[str, Dict],
    census_df: pd.DataFrame,
    lcsp_data: Dict[str, float]
) -> Dict[str, Any]:
    """
    Calculate affordability summary for ALE mode.

    Determines how many employees meet the IRS affordability test
    under the proposed contribution strategy.

    Args:
        employee_contributions: Dict of employee_id -> contribution data
        census_df: Census DataFrame with income data
        lcsp_data: Dict of employee_id -> LCSP premium

    Returns:
        Dict with affordability metrics
    """
    from constants import AFFORDABILITY_THRESHOLD_2026

    affordable_count = 0
    total_analyzed = 0
    unaffordable_employees = []

    for emp_id, contrib_data in employee_contributions.items():
        contribution = contrib_data.get('monthly_contribution', 0)
        lcsp = lcsp_data.get(emp_id, 0)

        # Get income from census
        emp_row = census_df[
            (census_df.get('employee_id', census_df.get('Employee Number', pd.Series())) == emp_id) |
            (census_df.get('Employee Number', pd.Series()).astype(str) == str(emp_id))
        ]

        if emp_row.empty:
            continue

        emp = emp_row.iloc[0]
        monthly_income = None

        for col in ['monthly_income', 'Monthly Income']:
            if col in emp.index:
                val = emp[col]
                if pd.notna(val) and val != '':
                    if isinstance(val, (int, float)):
                        monthly_income = float(val)
                    else:
                        monthly_income = float(str(val).replace('$', '').replace(',', '').strip() or 0)
                    break

        if monthly_income is None or monthly_income <= 0:
            continue

        total_analyzed += 1

        # Affordability check: (LCSP - ER Contribution) ≤ 9.96% of income
        employee_cost = max(0, lcsp - contribution)
        max_affordable = monthly_income * AFFORDABILITY_THRESHOLD_2026

        if employee_cost <= max_affordable:
            affordable_count += 1
        else:
            gap = employee_cost - max_affordable
            unaffordable_employees.append({
                'employee_id': emp_id,
                'name': contrib_data.get('name', emp_id),
                'gap': round(gap, 2),
                'current_contribution': contribution,
                'min_needed': contribution + gap + 1  # +$1 buffer
            })

    return {
        'affordable_count': affordable_count,
        'total_analyzed': total_analyzed,
        'affordable_pct': (affordable_count / total_analyzed * 100) if total_analyzed > 0 else 0,
        'unaffordable_employees': unaffordable_employees,
        'all_affordable': affordable_count == total_analyzed and total_analyzed > 0,
    }
