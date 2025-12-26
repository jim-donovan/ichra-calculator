"""
IRS Affordability Analysis for ICHRA Calculator

Provides functionality to:
- Calculate minimum employer contributions for IRS affordability
- Analyze workforce affordability patterns
- Generate contribution strategy recommendations

IRS Affordability Safe Harbor (2026):
An ICHRA is considered "affordable" if the employee's required contribution
for self-only LCSP coverage ≤ 9.96% of household income.
"""

import pandas as pd
import numpy as np
from typing import List, Tuple, Optional
from database import DatabaseConnection
from queries import PlanQueries
from constants import AFFORDABILITY_THRESHOLD_2026
from utils import parse_currency


class AffordabilityCalculator:
    """Calculate IRS affordability for individual employees"""

    @staticmethod
    def calculate_employee_affordability(
        employee: dict,
        lcsp_premium: float
    ) -> dict:
        """
        Calculate IRS affordability for a single employee.

        Args:
            employee: Employee dict with keys: employee_id, monthly_income, current_er_contribution
            lcsp_premium: Self-only Lowest Cost Silver Plan monthly premium

        Returns:
            Dict with affordability analysis:
            {
                'employee_id': str,
                'monthly_income': float or None,
                'lcsp_premium': float,
                'max_ee_contribution': float,  # 9.96% of income
                'min_er_contribution': float,  # LCSP - max_ee (minimum for affordability)
                'current_er_contribution': float or 0,
                'gap': float,  # Additional ER contribution needed
                'is_affordable_at_current': bool or None,
                'has_income_data': bool
            }

        Logic:
            1. Extract monthly_income from employee (may be None)
            2. If no income: return has_income_data=False, others=None
            3. Calculate max_ee_contribution = monthly_income * 0.0996
            4. Calculate min_er_contribution = max(0, lcsp_premium - max_ee_contribution)
            5. Compare to current_er_contribution from census
            6. Calculate gap = max(0, min_er - current_er)

        Example:
            Employee makes $5000/mo, LCSP is $450/mo, current ER pays $500/mo
            - max_ee_contribution = $498 (9.96% of $5000)
            - min_er_contribution = $0 (since $450 < $498, already affordable with $0 ER)
            - is_affordable_at_current = True
        """
        employee_id = employee.get('employee_id', 'Unknown')

        # Extract and parse monthly income
        monthly_income_raw = employee.get('monthly_income')
        monthly_income = None

        if monthly_income_raw is not None:
            if isinstance(monthly_income_raw, (int, float)):
                monthly_income = float(monthly_income_raw)
            else:
                monthly_income = parse_currency(str(monthly_income_raw))

        # If no income data, return early
        if monthly_income is None or monthly_income <= 0:
            return {
                'employee_id': employee_id,
                'monthly_income': None,
                'lcsp_premium': lcsp_premium,
                'max_ee_contribution': None,
                'min_er_contribution': None,
                'current_er_contribution': None,
                'gap': None,
                'is_affordable_at_current': None,
                'has_income_data': False
            }

        # Calculate affordability threshold (9.96% of income for 2026)
        max_ee_contribution = monthly_income * AFFORDABILITY_THRESHOLD_2026

        # Calculate minimum ER contribution for affordability
        # Employee must pay no more than max_ee_contribution
        # So: LCSP - ER_contribution ≤ max_ee_contribution
        # Therefore: ER_contribution ≥ LCSP - max_ee_contribution
        min_er_contribution = max(0, lcsp_premium - max_ee_contribution)

        # Extract current ER contribution from census
        current_er_raw = employee.get('current_er_contribution') or employee.get('current_er_monthly')
        current_er_contribution = 0

        if current_er_raw is not None:
            if isinstance(current_er_raw, (int, float)):
                current_er_contribution = float(current_er_raw)
            else:
                parsed = parse_currency(str(current_er_raw))
                if parsed is not None:
                    current_er_contribution = parsed

        # Calculate gap (additional contribution needed)
        gap = max(0, min_er_contribution - current_er_contribution)

        # Determine if affordable at current contribution level
        is_affordable_at_current = current_er_contribution >= min_er_contribution

        return {
            'employee_id': employee_id,
            'monthly_income': monthly_income,
            'lcsp_premium': lcsp_premium,
            'max_ee_contribution': max_ee_contribution,
            'min_er_contribution': min_er_contribution,
            'current_er_contribution': current_er_contribution,
            'gap': gap,
            'is_affordable_at_current': is_affordable_at_current,
            'has_income_data': True
        }

    @staticmethod
    def get_age_band(age: int, state: str) -> str:
        """
        Convert age to premium rating age band.

        Args:
            age: Employee age
            state: Two-letter state code

        Returns:
            Age band string for database queries

        Logic:
            - Ages 0-14: "0-14" (single rate)
            - Ages 15-63: exact age as string (e.g., "35")
            - Ages 64+: "64 and over"
            - NY/VT: "Family-Tier Rates" (special rating)
        """
        # Special case for NY and VT
        if state in ['NY', 'VT']:
            return "Family-Tier Rates"

        # Standard age bands
        if age <= 14:
            return "0-14"
        elif age >= 64:
            return "64 and over"
        else:
            return str(age)


class AffordabilityAnalyzer:
    """Analyze affordability across entire workforce"""

    @staticmethod
    def analyze_workforce(
        census_df: pd.DataFrame,
        db: DatabaseConnection
    ) -> dict:
        """
        Comprehensive affordability analysis for entire workforce.

        Args:
            census_df: Employee census DataFrame with columns:
                       employee_id, age, state, rating_area_id, monthly_income, etc.
            db: Database connection

        Returns:
            Dict with complete affordability analysis:
            {
                'summary': {
                    'total_employees': int,
                    'employees_analyzed': int,  # Have income data
                    'affordable_at_current': int,
                    'needs_increase': int,
                    'total_gap_annual': float,
                    'current_er_spend_annual': float,
                    'min_required_spend_annual': float
                },
                'employee_details': List[dict],  # Full affordability per employee
                'age_distribution': dict,  # Stats grouped by age
                'location_distribution': dict,  # Stats by state/rating area
                'flagged_employees': List[dict]  # High-cost outliers (>2× median)
            }

        Process:
            1. Filter employees with income data
            2. Batch fetch LCSP for all employees (efficient single query)
            3. Calculate affordability for each employee
            4. Aggregate statistics
            5. Group by age and location
            6. Flag high-cost employees
        """
        total_employees = len(census_df)

        # Verify required columns exist
        required_cols = ['employee_id', 'state']
        age_col = 'age' if 'age' in census_df.columns else 'employee_age'
        rating_area_col = 'rating_area_id' if 'rating_area_id' in census_df.columns else 'rating_area'

        missing_cols = [col for col in required_cols if col not in census_df.columns]
        if missing_cols:
            return {
                'summary': {
                    'total_employees': total_employees,
                    'employees_analyzed': 0,
                    'affordable_at_current': 0,
                    'needs_increase': 0,
                    'total_gap_annual': 0,
                    'current_er_spend_annual': 0,
                    'min_required_spend_annual': 0
                },
                'employee_details': [],
                'age_distribution': {},
                'location_distribution': {},
                'flagged_employees': [],
                'error': f'Missing required columns: {missing_cols}'
            }

        if age_col not in census_df.columns:
            return {
                'summary': {
                    'total_employees': total_employees,
                    'employees_analyzed': 0,
                    'affordable_at_current': 0,
                    'needs_increase': 0,
                    'total_gap_annual': 0,
                    'current_er_spend_annual': 0,
                    'min_required_spend_annual': 0
                },
                'employee_details': [],
                'age_distribution': {},
                'location_distribution': {},
                'flagged_employees': [],
                'error': f'Age column not found. Expected "age" or "employee_age"'
            }

        # Filter employees with income data
        employees_with_income = census_df[census_df['monthly_income'].notna()].copy()
        employees_analyzed = len(employees_with_income)

        # If no employees have income data, return early
        if employees_analyzed == 0:
            return {
                'summary': {
                    'total_employees': total_employees,
                    'employees_analyzed': 0,
                    'affordable_at_current': 0,
                    'needs_increase': 0,
                    'total_gap_annual': 0,
                    'current_er_spend_annual': 0,
                    'min_required_spend_annual': 0
                },
                'employee_details': [],
                'age_distribution': {},
                'location_distribution': {},
                'flagged_employees': []
            }

        # Build employee_locations list for batch LCSP query
        employee_locations = []
        for _, employee in employees_with_income.iterrows():
            # Access pandas Series columns safely - use .get() with proper defaults
            # Note: For pandas Series, check column existence before access
            try:
                if 'age' in employee.index:
                    age = int(employee['age']) if pd.notna(employee['age']) else 0
                elif 'employee_age' in employee.index:
                    age = int(employee['employee_age']) if pd.notna(employee['employee_age']) else 0
                else:
                    age = 0
            except (ValueError, TypeError):
                age = 0

            try:
                if 'state' in employee.index and pd.notna(employee['state']):
                    state = str(employee['state']).upper()
                else:
                    state = ''
            except (ValueError, TypeError):
                state = ''

            try:
                if 'rating_area_id' in employee.index and pd.notna(employee['rating_area_id']):
                    rating_area_id = employee['rating_area_id']
                elif 'rating_area' in employee.index and pd.notna(employee['rating_area']):
                    rating_area_id = employee['rating_area']
                else:
                    rating_area_id = None
            except (ValueError, TypeError):
                rating_area_id = None

            # Convert age to age band
            age_band = AffordabilityCalculator.get_age_band(age, state)

            employee_locations.append({
                'state_code': state,
                'rating_area_id': rating_area_id,
                'age_band': age_band
            })

        # Batch fetch LCSP for all unique combinations
        try:
            lcsp_df = PlanQueries.get_lcsp_for_employees_batch(db, employee_locations)
        except Exception as e:
            print(f"Error fetching LCSP data: {e}")
            return {
                'summary': {
                    'total_employees': total_employees,
                    'employees_analyzed': 0,
                    'affordable_at_current': 0,
                    'needs_increase': 0,
                    'total_gap_annual': 0,
                    'current_er_spend_annual': 0,
                    'min_required_spend_annual': 0
                },
                'employee_details': [],
                'age_distribution': {},
                'location_distribution': {},
                'flagged_employees': [],
                'error': str(e)
            }

        # Create lookup dict for LCSP premiums
        lcsp_lookup = {}
        for _, lcsp_row in lcsp_df.iterrows():
            # The batch query returns 'age_band' column (or 'age' in some versions)
            age_band_col = 'age_band' if 'age_band' in lcsp_row.index else 'age'
            key = (
                lcsp_row['state_code'],
                int(lcsp_row['rating_area_id']),
                str(lcsp_row[age_band_col])
            )
            lcsp_lookup[key] = float(lcsp_row['premium'])

        # Calculate affordability for each employee
        employee_details = []
        for _, employee in employees_with_income.iterrows():
            # Access pandas Series columns safely
            try:
                age = int(employee['age']) if 'age' in employee.index else int(employee.get('employee_age', 0))
            except (KeyError, ValueError):
                age = 0

            try:
                state = str(employee['state']).upper() if 'state' in employee.index else ''
            except KeyError:
                state = ''

            try:
                rating_area_id = employee['rating_area_id'] if 'rating_area_id' in employee.index else employee.get('rating_area', None)
            except KeyError:
                rating_area_id = None

            age_band = AffordabilityCalculator.get_age_band(age, state)

            # Look up LCSP premium
            lookup_key = (state, int(rating_area_id), age_band)
            lcsp_premium = lcsp_lookup.get(lookup_key)

            if lcsp_premium is None:
                # Skip if no LCSP found
                continue

            # Calculate affordability
            emp_dict = employee.to_dict()
            affordability = AffordabilityCalculator.calculate_employee_affordability(
                emp_dict,
                lcsp_premium
            )

            # Add additional employee context
            affordability['age'] = age
            affordability['state'] = state
            affordability['rating_area_id'] = rating_area_id

            employee_details.append(affordability)

        # Aggregate statistics
        employees_with_data = [e for e in employee_details if e.get('has_income_data')]
        affordable_count = sum(1 for e in employees_with_data if e.get('is_affordable_at_current'))
        needs_increase = len(employees_with_data) - affordable_count

        total_gap = sum(e.get('gap', 0) for e in employees_with_data)
        total_gap_annual = total_gap * 12

        current_er_spend = sum(e.get('current_er_contribution', 0) for e in employees_with_data)
        current_er_spend_annual = current_er_spend * 12

        min_required_spend = sum(e.get('min_er_contribution', 0) for e in employees_with_data)
        min_required_spend_annual = min_required_spend * 12

        summary = {
            'total_employees': total_employees,
            'employees_analyzed': len(employees_with_data),
            'affordable_at_current': affordable_count,
            'needs_increase': needs_increase,
            'total_gap_annual': total_gap_annual,
            'current_er_spend_annual': current_er_spend_annual,
            'min_required_spend_annual': min_required_spend_annual
        }

        # Group by age for distribution analysis
        age_groups = {}
        if employees_with_data:
            age_df = pd.DataFrame(employees_with_data)
            age_df['age_bracket'] = pd.cut(
                age_df['age'],
                bins=[0, 30, 40, 50, 60, 100],
                labels=['Under 30', '30-39', '40-49', '50-59', '60+']
            )

            for age_bracket, group in age_df.groupby('age_bracket', observed=True):
                age_groups[str(age_bracket)] = {
                    'count': len(group),
                    'avg_lcsp': group['lcsp_premium'].mean(),
                    'avg_min_er_contribution': group['min_er_contribution'].mean(),
                    'affordable_pct': (group['is_affordable_at_current'].sum() / len(group) * 100) if len(group) > 0 else 0
                }

        # Group by location (state)
        location_groups = {}
        if employees_with_data:
            loc_df = pd.DataFrame(employees_with_data)
            for state, group in loc_df.groupby('state'):
                location_groups[state] = {
                    'count': len(group),
                    'avg_lcsp': group['lcsp_premium'].mean(),
                    'avg_min_er_contribution': group['min_er_contribution'].mean(),
                    'affordable_pct': (group['is_affordable_at_current'].sum() / len(group) * 100) if len(group) > 0 else 0
                }

        # Flag high-cost employees (>2× median required contribution)
        flagged_employees = []
        if employees_with_data:
            min_er_contributions = [e.get('min_er_contribution', 0) for e in employees_with_data]
            median_contribution = np.median(min_er_contributions)
            threshold = median_contribution * 2

            flagged_employees = [
                e for e in employees_with_data
                if e.get('min_er_contribution', 0) > threshold
            ]

        return {
            'summary': summary,
            'employee_details': employee_details,
            'age_distribution': age_groups,
            'location_distribution': location_groups,
            'flagged_employees': flagged_employees
        }


class ContributionRecommender:
    """Generate contribution strategy recommendations"""

    @staticmethod
    def generate_recommendations(
        analysis_result: dict,
        census_df: pd.DataFrame
    ) -> list:
        """
        Generate 2-3 contribution strategy recommendations.

        Args:
            analysis_result: Output from AffordabilityAnalyzer.analyze_workforce()
            census_df: Employee census DataFrame

        Returns:
            List of recommendation dicts:
            [
                {
                    'strategy_type': 'flat' | 'age_banded' | 'location_based',
                    'name': str,
                    'contribution': float (flat only),
                    'tiers': List[dict] (banded only),
                    'annual_cost': float,
                    'achieves_affordability': str,
                    'savings_vs_current': float,  # Comparison to current ER spend
                    'pros': List[str],
                    'cons': List[str]
                },
                ...
            ]

        Strategy Logic:
            1. Flat (always included): max(min_er_contribution) for all
            2. Age-banded (if CV > 0.15): K-means clustering on LCSP by age
            3. Location-based (if multi-state & >10% variance): By state/rating area
        """
        employee_details = analysis_result['employee_details']
        employees_with_data = [e for e in employee_details if e.get('has_income_data')]

        if not employees_with_data:
            return []

        # Get current ER spend from summary for comparison
        current_er_spend_annual = analysis_result.get('summary', {}).get('current_er_spend_annual', 0)

        recommendations = []

        # ====================
        # Strategy 1: Flat Contribution
        # ====================
        flat_rec = ContributionRecommender._generate_flat_recommendation(
            employees_with_data
        )
        # Calculate savings vs current spend (positive = saves money, negative = costs more)
        flat_rec['savings_vs_current'] = current_er_spend_annual - flat_rec['annual_cost']
        recommendations.append(flat_rec)

        # ====================
        # Strategy 2: Age-Banded (if variance exists)
        # ====================
        age_banded_rec = ContributionRecommender._generate_age_banded_recommendation(
            employees_with_data
        )
        if age_banded_rec:
            age_banded_rec['savings_vs_current'] = current_er_spend_annual - age_banded_rec['annual_cost']
            recommendations.append(age_banded_rec)

        # ====================
        # Strategy 3: Location-Based (if multi-state with variance)
        # ====================
        location_rec = ContributionRecommender._generate_location_recommendation(
            employees_with_data
        )
        if location_rec:
            location_rec['savings_vs_current'] = current_er_spend_annual - location_rec['annual_cost']
            recommendations.append(location_rec)

        return recommendations

    @staticmethod
    def _generate_flat_recommendation(employees: List[dict]) -> dict:
        """
        Generate flat contribution recommendation.

        Contribution = max(min_er_contribution) across all employees
        Ensures 100% affordability.
        """
        max_required = max(e.get('min_er_contribution', 0) for e in employees)
        annual_cost = max_required * len(employees) * 12

        return {
            'strategy_type': 'flat',
            'name': 'Single Flat Contribution',
            'contribution': max_required,
            'annual_cost': annual_cost,
            'achieves_affordability': '100%',
            'pros': [
                'Simplest to administer',
                'Easy to communicate to employees',
                'Ensures affordability for all'
            ],
            'cons': [
                'Over-contributes to younger/lower-cost employees',
                'Highest total employer cost'
            ] if max_required > np.mean([e.get('min_er_contribution', 0) for e in employees]) * 1.3 else []
        }

    @staticmethod
    def _generate_age_banded_recommendation(employees: List[dict]) -> Optional[dict]:
        """
        Generate age-banded contribution recommendation using contiguous age bands.

        Only returns recommendation if coefficient of variation (CV) > 0.15
        (indicates meaningful age-based variance).

        Algorithm:
            1. Calculate CV of min_er_contribution by age
            2. If CV < 0.15: return None (no meaningful variance)
            3. Determine number of bands based on CV:
               - CV < 0.15: Skip (no banding)
               - CV 0.15-0.30: 2 bands
               - CV 0.30-0.50: 3 bands
               - CV > 0.50: 4 bands
            4. Create contiguous age bands using age percentiles
            5. Calculate max contribution needed for each band
            6. Create human-readable age ranges
        """
        if len(employees) < 10:
            # Need reasonable sample size for banding
            return None

        # Calculate coefficient of variation
        contributions_by_age = {}
        for emp in employees:
            age = emp.get('age', None)
            if age is None:
                continue  # Skip employees without age data
            contrib = emp.get('min_er_contribution', 0)
            if age not in contributions_by_age:
                contributions_by_age[age] = []
            contributions_by_age[age].append(contrib)

        # Average contribution per age
        age_avg_contrib = {age: np.mean(contribs) for age, contribs in contributions_by_age.items()}

        if not age_avg_contrib:
            return None

        contributions = list(age_avg_contrib.values())
        mean_contrib = np.mean(contributions)
        std_contrib = np.std(contributions)
        cv = std_contrib / mean_contrib if mean_contrib > 0 else 0

        # Skip if variance is too low
        if cv < 0.15:
            return None

        # Determine number of bands based on CV
        if cv < 0.30:
            n_bands = 2
        elif cv < 0.50:
            n_bands = 3
        else:
            n_bands = 4

        # Get all employee ages and sort them
        employee_ages = [emp.get('age') for emp in employees if emp.get('age') is not None]
        if not employee_ages:
            return None

        # Create contiguous age bands using percentiles
        sorted_ages = sorted(set(employee_ages))
        min_overall_age = min(sorted_ages)
        max_overall_age = max(sorted_ages)

        # Define age band boundaries using percentiles of employee ages
        percentiles = np.linspace(0, 100, n_bands + 1)
        age_boundaries = [int(np.percentile(employee_ages, p)) for p in percentiles]

        # Ensure boundaries are unique and cover full range
        age_boundaries[0] = min_overall_age
        age_boundaries[-1] = max_overall_age + 1  # +1 to include max age

        # Remove duplicate boundaries
        unique_boundaries = []
        for b in age_boundaries:
            if not unique_boundaries or b > unique_boundaries[-1]:
                unique_boundaries.append(b)

        # Need at least 2 bands
        if len(unique_boundaries) < 3:
            # Fall back to simple 2-band split at median
            median_age = int(np.median(employee_ages))
            unique_boundaries = [min_overall_age, median_age, max_overall_age + 1]

        # Build tiers from contiguous age bands
        tiers = []
        for i in range(len(unique_boundaries) - 1):
            band_min = unique_boundaries[i]
            band_max = unique_boundaries[i + 1] - 1  # -1 because upper bound is exclusive

            # Get employees in this age band
            employees_in_band = [
                e for e in employees
                if e.get('age') is not None and band_min <= e.get('age') <= band_max
            ]

            if len(employees_in_band) < 3:
                # Skip very small bands
                continue

            # Calculate max contribution needed in this band (for affordability)
            band_contributions = [e.get('min_er_contribution', 0) for e in employees_in_band]
            tier_contribution = max(band_contributions) if band_contributions else 0

            # Create human-readable age range
            if band_min < 26 and band_max < 30:
                age_range = "Under 30"
            elif i == len(unique_boundaries) - 2:  # Last band
                age_range = f"{band_min}+"
            else:
                age_range = f"{band_min}-{band_max}"

            tiers.append({
                'age_range': age_range,
                'contribution': round(tier_contribution, 2),
                'count': len(employees_in_band),
                'ages': [band_min, band_max]
            })

        if len(tiers) < 2:
            # Need at least 2 tiers for banding to make sense
            return None

        # Calculate annual cost
        annual_cost = sum(tier['contribution'] * tier['count'] * 12 for tier in tiers)

        return {
            'strategy_type': 'age_banded',
            'name': 'Age-Based Contribution Tiers',
            'tiers': tiers,
            'annual_cost': annual_cost,
            'achieves_affordability': '100%',
            'pros': [
                'Mirrors premium age-rating',
                'More cost-efficient than flat',
                'Fair allocation based on cost'
            ],
            'cons': [
                'Slightly more complex to administer',
                'Requires age-based tracking'
            ]
        }

    @staticmethod
    def _generate_location_recommendation(employees: List[dict]) -> Optional[dict]:
        """
        Generate location-based contribution recommendation.

        Only returns if:
        - Multiple states
        - Variance in LCSP premiums > 10% between states

        Groups by state and calculates contribution per location.
        """
        # Group by state
        states = {}
        for emp in employees:
            state = emp.get('state', 'Unknown')
            if state not in states:
                states[state] = []
            states[state].append(emp)

        if len(states) < 2:
            # Single state, no location variance
            return None

        # Calculate average LCSP and required contribution per state
        state_stats = {}
        for state, emps in states.items():
            # Filter to employees with valid data (not None)
            valid_lcsps = [e.get('lcsp_premium', 0) or 0 for e in emps]
            valid_contributions = [e.get('min_er_contribution') for e in emps if e.get('min_er_contribution') is not None]

            avg_lcsp = np.mean(valid_lcsps) if valid_lcsps else 0
            max_required = max(valid_contributions) if valid_contributions else 0

            state_stats[state] = {
                'avg_lcsp': avg_lcsp,
                'max_required': max_required,
                'count': len(emps),
                'with_income_data': len(valid_contributions)
            }

        # Check variance (coefficient of variation)
        lcsps = [stats['avg_lcsp'] for stats in state_stats.values()]
        mean_lcsp = np.mean(lcsps)
        std_lcsp = np.std(lcsps)
        cv = std_lcsp / mean_lcsp if mean_lcsp > 0 else 0

        if cv < 0.10:
            # Less than 10% variance, location-based not worthwhile
            return None

        # Build tiers
        tiers = []
        states_with_zero = []
        for state, stats in state_stats.items():
            tiers.append({
                'location': state,
                'contribution': stats['max_required'],
                'count': stats['count'],
                'with_income_data': stats['with_income_data']
            })
            if stats['max_required'] == 0 and stats['count'] > 0:
                states_with_zero.append(f"{state} ({stats['with_income_data']}/{stats['count']} with income data)")

        # Sort by state
        tiers = sorted(tiers, key=lambda t: t['location'])

        # Calculate annual cost
        annual_cost = sum(tier['contribution'] * tier['count'] * 12 for tier in tiers)

        # Build cons list with warnings if needed
        cons = [
            'May feel inequitable to employees',
            'Requires state-level tracking'
        ]
        if states_with_zero:
            cons.append(f"Warning: $0 contribution for: {', '.join(states_with_zero)}")

        return {
            'strategy_type': 'location_based',
            'name': 'Location-Based Contributions',
            'tiers': tiers,
            'annual_cost': annual_cost,
            'achieves_affordability': '100%',
            'pros': [
                'Addresses geographic premium differences',
                'Cost-efficient for multi-state workforces'
            ],
            'cons': cons
        }


class StrategyApplicator:
    """
    Transform contribution strategy recommendations into executable contribution settings.

    This class takes a strategy recommendation (from ContributionRecommender) and a census,
    then produces a new contribution_settings structure with per-employee class assignments.
    """

    # Family status multipliers (relative to EE base)
    FAMILY_MULTIPLIERS = {
        'EE': 1.0,
        'ES': 1.5,   # Employee + Spouse
        'EC': 1.3,   # Employee + Children
        'F': 1.8     # Family
    }

    @staticmethod
    def apply_strategy(
        strategy: dict,
        census_df: pd.DataFrame,
        apply_family_multipliers: bool = True
    ) -> dict:
        """
        Apply a contribution strategy to generate class-based contribution settings.

        Args:
            strategy: Strategy recommendation dict from ContributionRecommender
            census_df: Employee census DataFrame with columns:
                       employee_id, age, state, rating_area_id, family_status
            apply_family_multipliers: If True, multiply base contribution by family status

        Returns:
            New contribution_settings dict with structure:
            {
                'contribution_type': 'class_based',
                'strategy_applied': 'flat' | 'age_banded' | 'location_based',
                'strategy_name': str,
                'classes': [...],
                'employee_assignments': {...},
                'total_monthly': float,
                'total_annual': float,
                'employees_assigned': int
            }
        """
        strategy_type = strategy.get('strategy_type', 'flat')

        if strategy_type == 'flat':
            return StrategyApplicator._apply_flat(strategy, census_df, apply_family_multipliers)
        elif strategy_type == 'age_banded':
            return StrategyApplicator._apply_age_banded(strategy, census_df, apply_family_multipliers)
        elif strategy_type == 'location_based':
            return StrategyApplicator._apply_location_based(strategy, census_df, apply_family_multipliers)
        else:
            raise ValueError(f"Unknown strategy type: {strategy_type}")

    @staticmethod
    def _apply_flat(
        strategy: dict,
        census_df: pd.DataFrame,
        apply_family_multipliers: bool
    ) -> dict:
        """Apply flat contribution strategy."""
        base_contribution = strategy.get('contribution', 0)

        classes = []
        employee_assignments = {}
        total_monthly = 0.0

        # Create a class for each family status
        for family_status, multiplier in StrategyApplicator.FAMILY_MULTIPLIERS.items():
            if apply_family_multipliers:
                contribution = base_contribution * multiplier
            else:
                contribution = base_contribution

            class_id = f"flat_{family_status}"
            classes.append({
                'class_id': class_id,
                'description': f"Flat Contribution - {family_status}",
                'criteria': {'family_status': family_status},
                'monthly_contribution': round(contribution, 2)
            })

        # Assign employees to classes
        for _, emp in census_df.iterrows():
            # Try multiple column name variations
            employee_id = str(emp.get('employee_id') or emp.get('Employee Number') or emp.get('employee_number', ''))
            family_status = str(emp.get('family_status') or emp.get('Family Status', 'EE')).upper()

            # Normalize family status
            if family_status not in StrategyApplicator.FAMILY_MULTIPLIERS:
                family_status = 'EE'

            if apply_family_multipliers:
                contribution = base_contribution * StrategyApplicator.FAMILY_MULTIPLIERS[family_status]
            else:
                contribution = base_contribution

            class_id = f"flat_{family_status}"

            employee_assignments[employee_id] = {
                'class_id': class_id,
                'monthly_contribution': round(contribution, 2),
                'annual_contribution': round(contribution * 12, 2)
            }
            total_monthly += contribution

        return {
            'contribution_type': 'class_based',
            'strategy_applied': 'flat',
            'strategy_name': strategy.get('name', 'Single Flat Contribution'),
            'base_contribution': base_contribution,
            'apply_family_multipliers': apply_family_multipliers,
            'classes': classes,
            'employee_assignments': employee_assignments,
            'total_monthly': round(total_monthly, 2),
            'total_annual': round(total_monthly * 12, 2),
            'employees_assigned': len(employee_assignments)
        }

    @staticmethod
    def _apply_age_banded(
        strategy: dict,
        census_df: pd.DataFrame,
        apply_family_multipliers: bool
    ) -> dict:
        """Apply age-banded contribution strategy."""
        tiers = strategy.get('tiers', [])

        if not tiers:
            raise ValueError("Age-banded strategy requires tiers")

        # Parse tiers into usable age ranges
        parsed_tiers = []
        for tier in tiers:
            age_range = tier.get('age_range', '')
            ages = tier.get('ages', None)
            contribution = tier.get('contribution', 0)

            if ages and len(ages) >= 2:
                age_min, age_max = ages[0], ages[1]
            else:
                age_min, age_max = StrategyApplicator._parse_age_range(age_range)

            parsed_tiers.append({
                'age_range': age_range,
                'age_min': age_min,
                'age_max': age_max,
                'base_contribution': contribution
            })

        # Sort by age_min for consistent assignment
        parsed_tiers.sort(key=lambda t: t['age_min'])

        # Build classes (one per age tier x family status combination)
        classes = []
        for tier in parsed_tiers:
            for family_status, multiplier in StrategyApplicator.FAMILY_MULTIPLIERS.items():
                if apply_family_multipliers:
                    contribution = tier['base_contribution'] * multiplier
                else:
                    contribution = tier['base_contribution']

                class_id = f"age_{tier['age_min']}_{tier['age_max']}_{family_status}"
                classes.append({
                    'class_id': class_id,
                    'description': f"{tier['age_range']}, {family_status}",
                    'criteria': {
                        'age_min': tier['age_min'],
                        'age_max': tier['age_max'],
                        'family_status': family_status
                    },
                    'monthly_contribution': round(contribution, 2)
                })

        # Assign employees to classes
        employee_assignments = {}
        total_monthly = 0.0

        for _, emp in census_df.iterrows():
            # Try multiple column name variations
            employee_id = str(emp.get('employee_id') or emp.get('Employee Number') or emp.get('employee_number', ''))
            age = emp.get('age') or emp.get('ee_age') or emp.get('Age')
            family_status = str(emp.get('family_status') or emp.get('Family Status', 'EE')).upper()

            # Handle missing age
            if age is None or pd.isna(age):
                age = 30  # Default age
            else:
                age = int(age)

            # Normalize family status
            if family_status not in StrategyApplicator.FAMILY_MULTIPLIERS:
                family_status = 'EE'

            # Find matching tier
            matched_tier = None
            for tier in parsed_tiers:
                if tier['age_min'] <= age <= tier['age_max']:
                    matched_tier = tier
                    break

            # Fallback to last tier if no match (handles edge cases)
            if matched_tier is None:
                matched_tier = parsed_tiers[-1]

            if apply_family_multipliers:
                contribution = matched_tier['base_contribution'] * StrategyApplicator.FAMILY_MULTIPLIERS[family_status]
            else:
                contribution = matched_tier['base_contribution']

            class_id = f"age_{matched_tier['age_min']}_{matched_tier['age_max']}_{family_status}"

            employee_assignments[employee_id] = {
                'class_id': class_id,
                'monthly_contribution': round(contribution, 2),
                'annual_contribution': round(contribution * 12, 2)
            }
            total_monthly += contribution

        return {
            'contribution_type': 'class_based',
            'strategy_applied': 'age_banded',
            'strategy_name': strategy.get('name', 'Age-Based Contribution Tiers'),
            'tiers': tiers,
            'apply_family_multipliers': apply_family_multipliers,
            'classes': classes,
            'employee_assignments': employee_assignments,
            'total_monthly': round(total_monthly, 2),
            'total_annual': round(total_monthly * 12, 2),
            'employees_assigned': len(employee_assignments)
        }

    @staticmethod
    def _apply_location_based(
        strategy: dict,
        census_df: pd.DataFrame,
        apply_family_multipliers: bool
    ) -> dict:
        """Apply location-based contribution strategy."""
        tiers = strategy.get('tiers', [])

        if not tiers:
            raise ValueError("Location-based strategy requires tiers")

        # Build location -> contribution mapping
        location_contributions = {}
        for tier in tiers:
            location = tier.get('location', '').upper()
            contribution = tier.get('contribution', 0)
            location_contributions[location] = contribution

        # Build classes (one per location x family status combination)
        classes = []
        for tier in tiers:
            location = tier.get('location', '').upper()
            base_contribution = tier.get('contribution', 0)

            for family_status, multiplier in StrategyApplicator.FAMILY_MULTIPLIERS.items():
                if apply_family_multipliers:
                    contribution = base_contribution * multiplier
                else:
                    contribution = base_contribution

                class_id = f"loc_{location}_{family_status}"
                classes.append({
                    'class_id': class_id,
                    'description': f"{location}, {family_status}",
                    'criteria': {
                        'state': location,
                        'family_status': family_status
                    },
                    'monthly_contribution': round(contribution, 2)
                })

        # Assign employees to classes
        employee_assignments = {}
        total_monthly = 0.0
        unmatched_employees = []

        for _, emp in census_df.iterrows():
            # Try multiple column name variations
            employee_id = str(emp.get('employee_id') or emp.get('Employee Number') or emp.get('employee_number', ''))
            state = str(emp.get('state') or emp.get('home_state') or emp.get('Home State', '')).upper()
            family_status = str(emp.get('family_status') or emp.get('Family Status', 'EE')).upper()

            # Normalize family status
            if family_status not in StrategyApplicator.FAMILY_MULTIPLIERS:
                family_status = 'EE'

            # Find contribution for this location
            if state in location_contributions:
                base_contribution = location_contributions[state]
                class_id = f"loc_{state}_{family_status}"
            else:
                # Use average contribution for unmatched locations
                unmatched_employees.append(employee_id)
                base_contribution = sum(location_contributions.values()) / len(location_contributions) if location_contributions else 0
                class_id = f"loc_OTHER_{family_status}"

            if apply_family_multipliers:
                contribution = base_contribution * StrategyApplicator.FAMILY_MULTIPLIERS[family_status]
            else:
                contribution = base_contribution

            employee_assignments[employee_id] = {
                'class_id': class_id,
                'monthly_contribution': round(contribution, 2),
                'annual_contribution': round(contribution * 12, 2)
            }
            total_monthly += contribution

        result = {
            'contribution_type': 'class_based',
            'strategy_applied': 'location_based',
            'strategy_name': strategy.get('name', 'Location-Based Contributions'),
            'tiers': tiers,
            'apply_family_multipliers': apply_family_multipliers,
            'classes': classes,
            'employee_assignments': employee_assignments,
            'total_monthly': round(total_monthly, 2),
            'total_annual': round(total_monthly * 12, 2),
            'employees_assigned': len(employee_assignments)
        }

        if unmatched_employees:
            result['warnings'] = {
                'unmatched_locations': unmatched_employees,
                'message': f"{len(unmatched_employees)} employees in states without defined tiers (using average)"
            }

        return result

    @staticmethod
    def _parse_age_range(age_range: str) -> Tuple[int, int]:
        """
        Parse age range string to (min, max) tuple.

        Examples:
            "Under 30" -> (0, 29)
            "30-49" -> (30, 49)
            "50+" -> (50, 99)
            "50-59" -> (50, 59)
            "60+" -> (60, 99)
        """
        age_range = age_range.strip()

        # Handle "Under X"
        if age_range.lower().startswith('under'):
            max_age = int(''.join(filter(str.isdigit, age_range))) - 1
            return (0, max_age)

        # Handle "X+"
        if '+' in age_range:
            min_age = int(''.join(filter(str.isdigit, age_range.replace('+', ''))))
            return (min_age, 99)

        # Handle "X-Y"
        if '-' in age_range:
            parts = age_range.split('-')
            min_age = int(''.join(filter(str.isdigit, parts[0])))
            max_age = int(''.join(filter(str.isdigit, parts[1])))
            return (min_age, max_age)

        # Single age (unlikely but handle it)
        digits = ''.join(filter(str.isdigit, age_range))
        if digits:
            age = int(digits)
            return (age, age)

        # Default fallback
        return (0, 99)
