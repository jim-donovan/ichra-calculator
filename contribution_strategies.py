"""
Contribution Strategy Calculator for ICHRA

Supports multiple contribution strategy types:
1. Flat Amount - Single dollar amount for all employees
2. Base Age + ACA 3:1 Curve - Scale contributions by age using federal age curve
3. Percentage of LCSP - X% of per-employee LCSP
4. FPL Safe Harbor - Guarantees IRS affordability for all employees

All strategies support:
- Optional family status multipliers (EE, ES, EC, F)
- Optional location adjustments (flat $ add-on by state)
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Any
import pandas as pd
import numpy as np

import logging

from database import DatabaseConnection
from constants import ACA_AGE_CURVE, DEFAULT_FAMILY_MULTIPLIERS, AFFORDABILITY_THRESHOLD_2026, MEDICARE_ELIGIBILITY_AGE
from subsidy_utils import (
    calculate_monthly_subsidy as _estimate_monthly_subsidy,
    is_subsidy_eligible as check_subsidy_eligibility,
    AFFORDABILITY_BUFFER,
)


class StrategyType(Enum):
    """Contribution strategy types"""
    FLAT_AMOUNT = "flat_amount"             # Single flat amount for all employees
    BASE_AGE_CURVE = "base_age_curve"       # Base age + ACA 3:1 curve
    PERCENTAGE_LCSP = "percentage_lcsp"     # X% of per-employee LCSP
    FPL_SAFE_HARBOR = "fpl_safe_harbor"     # FPL-based affordability safe harbor
    RATE_OF_PAY_SAFE_HARBOR = "rate_of_pay_safe_harbor"  # Rate of Pay affordability safe harbor
    SUBSIDY_OPTIMIZED = "subsidy_optimized"  # Max contribution that keeps ICHRA unaffordable for subsidies


# Age tiers for reporting/aggregation purposes
AGE_TIERS = [
    {'age_range': '21', 'age_min': 21, 'age_max': 21},
    {'age_range': '18-25', 'age_min': 18, 'age_max': 25},
    {'age_range': '26-35', 'age_min': 26, 'age_max': 35},
    {'age_range': '36-45', 'age_min': 36, 'age_max': 45},
    {'age_range': '46-55', 'age_min': 46, 'age_max': 55},
    {'age_range': '56-63', 'age_min': 56, 'age_max': 63},
    {'age_range': '64+', 'age_min': 64, 'age_max': 99},
]

# =============================================================================
# SUBSIDY OPTIMIZATION CONSTANTS
# =============================================================================
# FPL constants and subsidy functions are now in subsidy_utils.py

# Subsidy optimization thresholds
SUBSIDY_ROI_THRESHOLD = 0.35  # Employees with ROI >= 35% are considered "high-ROI" for optimization
SUBSIDY_ELIGIBILITY_PERCENTILE = 0  # 0 = use minimum (100% eligible), higher = more aggressive
MEDICARE_AGE = MEDICARE_ELIGIBILITY_AGE  # Alias for backwards compatibility


@dataclass
class StrategyConfig:
    """Configuration for a contribution strategy"""
    strategy_type: StrategyType
    name: str = ""

    # Common options
    apply_family_multipliers: bool = True
    family_multipliers: Dict[str, float] = field(default_factory=lambda: DEFAULT_FAMILY_MULTIPLIERS.copy())

    # Location adjustment (add-on modifier for any strategy)
    apply_location_adjustment: bool = False
    location_adjustments: Dict[str, float] = field(default_factory=dict)  # {"CA": 100, "NY": 100, ...}

    # FLAT_AMOUNT specific
    flat_amount: float = 0.0                # Single dollar amount for all employees

    # BASE_AGE_CURVE specific
    base_age: int = 21                      # Default base age
    base_contribution: float = 0.0          # Dollar amount for base age

    # PERCENTAGE_LCSP specific
    lcsp_percentage: float = 100.0          # e.g., 75.0 for 75%

    # FPL_SAFE_HARBOR specific
    fpl_buffer: float = 5.0  # Additional buffer ($/month) above FPL minimum for safety margin

    def __post_init__(self):
        """Generate default name if not provided"""
        if not self.name:
            if self.strategy_type == StrategyType.FLAT_AMOUNT:
                self.name = f"Flat ${self.flat_amount:,.0f}/mo"
            elif self.strategy_type == StrategyType.BASE_AGE_CURVE:
                self.name = f"Base Age {self.base_age} + ACA 3:1 Curve"
            elif self.strategy_type == StrategyType.PERCENTAGE_LCSP:
                self.name = f"{self.lcsp_percentage:.0f}% of Per-Employee LCSP"
            elif self.strategy_type == StrategyType.FPL_SAFE_HARBOR:
                self.name = "FPL Safe Harbor (Guaranteed Affordable)"
            elif self.strategy_type == StrategyType.RATE_OF_PAY_SAFE_HARBOR:
                self.name = "Rate of Pay Safe Harbor (Minimum Cost)"
            elif self.strategy_type == StrategyType.SUBSIDY_OPTIMIZED:
                self.name = "Subsidy-Optimized (Maximize Subsidy Eligibility)"


class ContributionStrategyCalculator:
    """
    Calculate contributions for different strategy types.

    Uses per-employee LCSP (based on their actual rating area/age) as the data source,
    then applies the selected strategy to determine contributions.
    """

    # ALE threshold (45+ FTEs with buffer for 50-employee ALE rule)
    ALE_THRESHOLD = 45

    def __init__(
        self,
        db: DatabaseConnection,
        census_df: pd.DataFrame,
        lcsp_cache: Dict[str, Dict] = None,
    ):
        self.db = db
        self.census_df = census_df
        self._lcsp_cache = lcsp_cache  # Can be pre-populated to avoid repeated queries
        # Determine ALE status at initialization (used for affordability requirements)
        self.is_ale = self._is_ale_employer()

    def _get_employee_age(self, emp: pd.Series) -> int:
        """
        Get employee age from record, with default fallback.

        Args:
            emp: Employee row from census DataFrame

        Returns:
            Employee age as integer (defaults to 30 if missing)
        """
        emp_age = emp.get('age') or emp.get('ee_age')
        if emp_age is None or pd.isna(emp_age):
            return 30
        return int(emp_age)

    def _is_ale_employer(self) -> bool:
        """
        Determine if employer is ALE (Applicable Large Employer) based on census size.

        Uses 45+ FTEs as threshold (provides buffer for the 50-employee ALE rule).
        Excludes Medicare-eligible employees (65+) from count since they're
        not part of ICHRA affordability calculations.

        Returns:
            True if employer has 45+ non-Medicare employees (ALE)
        """
        non_medicare_count = sum(
            1 for _, emp in self.census_df.iterrows()
            if self._get_employee_age(emp) < MEDICARE_ELIGIBILITY_AGE
        )
        return non_medicare_count >= self.ALE_THRESHOLD

    def _parse_employee_income(self, emp: pd.Series) -> tuple:
        """
        Parse monthly income from employee record.

        Args:
            emp: Employee row from census DataFrame

        Returns:
            Tuple of (monthly_income: float or None, has_income: bool)
        """
        monthly_income = emp.get('monthly_income') or emp.get('Monthly Income')
        if monthly_income is not None and not pd.isna(monthly_income):
            try:
                val = float(monthly_income)
                if val > 0:
                    return val, True
            except (ValueError, TypeError):
                pass
        return None, False

    def _get_employee_name(self, emp: pd.Series, emp_id: str) -> str:
        """
        Get formatted employee name (Last Name, First Name).

        Args:
            emp: Employee row from census DataFrame
            emp_id: Employee ID (fallback if name not available)

        Returns:
            Formatted name string
        """
        first_name = str(emp.get('first_name') or emp.get('First Name') or '').strip()
        last_name = str(emp.get('last_name') or emp.get('Last Name') or '').strip()
        if last_name and first_name:
            return f"{last_name}, {first_name}"
        elif last_name:
            return last_name
        elif first_name:
            return first_name
        return emp_id

    def _validate_3_to_1_ratio(self, employee_contributions: Dict[str, Dict]) -> Dict[str, Any]:
        """
        Validate age-based contributions stay within 3:1 ratio (IRS requirement).

        The 3:1 rule requires that the maximum age-based contribution cannot exceed
        3x the minimum age-based contribution within an employee class. Family
        multipliers are applied uniformly to all ages, so they don't affect this ratio.

        Args:
            employee_contributions: Dict of employee contribution data

        Returns:
            Dict with validation result:
            - valid: bool (True if compliant)
            - ratio: float or None (actual ratio)
            - message: str (compliance status)
        """
        # Extract base contributions (before family multipliers) for non-Medicare employees
        base_contributions = [
            c.get('base_contribution', 0)
            for c in employee_contributions.values()
            if not c.get('is_medicare') and c.get('base_contribution', 0) > 0
        ]

        if len(base_contributions) < 2:
            return {'valid': True, 'ratio': None, 'message': 'Insufficient data for ratio check'}

        min_base = min(base_contributions)
        max_base = max(base_contributions)

        if min_base <= 0:
            return {'valid': True, 'ratio': None, 'message': 'No age variation (base is 0)'}

        ratio = max_base / min_base

        return {
            'valid': ratio <= 3.0,
            'ratio': round(ratio, 2),
            'min_base': round(min_base, 2),
            'max_base': round(max_base, 2),
            'message': 'Compliant' if ratio <= 3.0 else f'VIOLATION: {ratio:.2f}:1 exceeds 3:1 limit'
        }

    def get_lcsp_cache(self) -> Dict[str, Dict]:
        """
        Get the LCSP cache, populating it if needed.

        Use this to extract the cache for storage in session state,
        then pass it back to future calculator instances.
        """
        return self._get_employee_lcsps()

    def calculate_strategy(self, config: StrategyConfig) -> Dict[str, Any]:
        """
        Calculate contributions for all employees based on strategy.

        Args:
            config: StrategyConfig with strategy type and parameters

        Returns:
            Dict with:
            - strategy_type: str
            - strategy_name: str
            - config: dict (strategy configuration)
            - employee_contributions: {emp_id: {...}}
            - total_monthly: float
            - total_annual: float
            - employees_covered: int
            - by_age_tier: dict (summary by age tier)
            - by_family_status: dict (summary by family status)
        """
        if config.strategy_type == StrategyType.FLAT_AMOUNT:
            result = self._calculate_flat_amount(config)
        elif config.strategy_type == StrategyType.BASE_AGE_CURVE:
            result = self._calculate_base_age_curve(config)
        elif config.strategy_type == StrategyType.PERCENTAGE_LCSP:
            result = self._calculate_percentage_lcsp(config)
        elif config.strategy_type == StrategyType.FPL_SAFE_HARBOR:
            result = self._calculate_fpl_safe_harbor(config)
        elif config.strategy_type == StrategyType.RATE_OF_PAY_SAFE_HARBOR:
            result = self._calculate_rate_of_pay_safe_harbor(config)
        elif config.strategy_type == StrategyType.SUBSIDY_OPTIMIZED:
            result = self._calculate_subsidy_optimized(config)
        else:
            raise ValueError(f"Unknown strategy type: {config.strategy_type}")

        # Apply location adjustments if enabled
        if config.apply_location_adjustment and config.location_adjustments:
            result = self._apply_location_adjustments(result, config.location_adjustments)

        return result

    def _get_employee_lcsps(self) -> Dict[str, Dict]:
        """
        Get LCSP and SLCSP for each employee using their actual rating area.
        Uses batch query for efficiency. Results cached.

        Returns:
            Dict[employee_id, {lcsp_ee_rate, slcsp_ee_rate, state, rating_area, family_status, ee_age, ...}]
        """
        if self._lcsp_cache is not None:
            return self._lcsp_cache

        # Use existing calculate_lcsp_scenario from financial_calculator
        from financial_calculator import FinancialSummaryCalculator

        lcsp_result = FinancialSummaryCalculator.calculate_lcsp_scenario(
            census_df=self.census_df,
            db=self.db,
            metal_level='Silver'
        )

        # Build lookup by employee_id
        self._lcsp_cache = {}
        for emp_detail in lcsp_result.get('employee_details', []):
            emp_id = str(emp_detail.get('employee_id', ''))
            self._lcsp_cache[emp_id] = {
                'lcsp_ee_rate': emp_detail.get('lcsp_ee_rate', 0),
                'slcsp_ee_rate': None,  # Will be populated below
                'lcsp_tier_premium': emp_detail.get('estimated_tier_premium', 0),  # Full family LCSP
                'lcsp_plan_name': emp_detail.get('lcsp_plan_name'),
                'state': emp_detail.get('state'),
                'rating_area': emp_detail.get('rating_area'),
                'family_status': emp_detail.get('family_status', 'EE'),
                'ee_age': emp_detail.get('ee_age'),
            }

        # Fetch SLCSP data using batch query
        self._populate_slcsp_data()

        return self._lcsp_cache

    def _populate_slcsp_data(self) -> None:
        """
        Populate SLCSP (Second Lowest Cost Silver Plan) data for subsidy estimation.
        Uses the existing get_lcsp_and_slcsp_batch query.
        """
        if self._lcsp_cache is None:
            return

        from queries import PlanQueries
        from financial_calculator import FinancialSummaryCalculator
        get_age_band = FinancialSummaryCalculator.get_age_band

        # Build employee locations for batch query
        employee_locations = []
        emp_location_map = {}  # Map (state, rating_area, age_band) -> [emp_ids]

        for emp_id, data in self._lcsp_cache.items():
            state = data.get('state')
            rating_area = data.get('rating_area')
            ee_age = data.get('ee_age')

            if not state or not rating_area or ee_age is None:
                continue

            # Convert rating_area to int if it's a string like "Rating Area 1"
            if isinstance(rating_area, str):
                import re
                match = re.search(r'\d+', rating_area)
                rating_area_id = int(match.group()) if match else 1
            else:
                rating_area_id = int(rating_area)

            age_band = get_age_band(int(ee_age))

            location = {
                'state_code': state.upper(),
                'rating_area_id': rating_area_id,
                'age_band': age_band
            }
            employee_locations.append(location)

            # Track which employees map to this location
            key = (state.upper(), rating_area_id, age_band)
            if key not in emp_location_map:
                emp_location_map[key] = []
            emp_location_map[key].append(emp_id)

        if not employee_locations:
            return

        # Batch query for LCSP and SLCSP
        try:
            slcsp_df = PlanQueries.get_lcsp_and_slcsp_batch(self.db, employee_locations)

            if slcsp_df.empty:
                return

            # Build lookup by (state, rating_area, age_band) for plan_rank=2 (SLCSP)
            slcsp_lookup = {}
            for _, row in slcsp_df.iterrows():
                if row.get('plan_rank') == 2:  # SLCSP
                    state = row.get('state_code')
                    rating_area = row.get('rating_area_id')
                    age_band = row.get('age_band')
                    premium = row.get('premium', 0)

                    key = (state, rating_area, age_band)
                    slcsp_lookup[key] = premium

            # Update cache with SLCSP rates
            for key, emp_ids in emp_location_map.items():
                slcsp_rate = slcsp_lookup.get(key)
                for emp_id in emp_ids:
                    if emp_id in self._lcsp_cache:
                        self._lcsp_cache[emp_id]['slcsp_ee_rate'] = slcsp_rate

        except Exception as e:
            import logging
            logging.warning(f"Failed to fetch SLCSP data: {e}")

    def _get_age_tier(self, age: int) -> str:
        """Get the age tier for a given age"""
        # Check for exact age 21 first
        if age == 21:
            return '21'
        # Then check other tiers
        for tier in AGE_TIERS:
            if tier['age_range'] == '21':
                continue  # Skip standalone 21 tier
            if tier['age_min'] <= age <= tier['age_max']:
                return tier['age_range']
        # Fallback for ages under 18
        return '18-25'

    def _recalculate_aggregations(
        self,
        employee_contributions: Dict[str, Dict]
    ) -> tuple:
        """
        Recalculate by_age_tier and by_family_status from deduplicated employee_contributions dict.

        This ensures aggregations match the actual employee count when duplicate employee IDs
        exist in the census (which would be overwritten in the dict but double-counted during
        loop-based accumulation).

        Args:
            employee_contributions: Deduplicated dict of {emp_id: contribution_data}

        Returns:
            Tuple of (by_age_tier, by_family_status) dicts
        """
        by_age_tier = {}
        by_family_status = {}

        for contrib in employee_contributions.values():
            # Skip Medicare-eligible employees (65+) from aggregations
            # They have $0 contribution and would dilute averages
            if contrib.get('is_medicare', False):
                continue

            age = contrib.get('age', 30)
            family_status = contrib.get('family_status', 'EE')
            monthly_contribution = contrib.get('monthly_contribution', 0)

            # Aggregate by age tier
            age_tier = self._get_age_tier(age)
            if age_tier not in by_age_tier:
                by_age_tier[age_tier] = {'count': 0, 'total_monthly': 0.0}
            by_age_tier[age_tier]['count'] += 1
            by_age_tier[age_tier]['total_monthly'] += monthly_contribution

            # Aggregate by family status
            if family_status not in by_family_status:
                by_family_status[family_status] = {'count': 0, 'total_monthly': 0.0}
            by_family_status[family_status]['count'] += 1
            by_family_status[family_status]['total_monthly'] += monthly_contribution

        return by_age_tier, by_family_status

    def _calculate_flat_amount(self, config: StrategyConfig) -> Dict[str, Any]:
        """
        Flat Amount Strategy.

        All employees receive the same base contribution amount.
        Family multipliers are applied on top of the base amount.

        ALE Behavior (45+ employees):
        - Auto-bumps contribution to meet IRS affordability (9.96% threshold)
        - Required to avoid 4980H(b) penalty for unaffordable offers

        Non-ALE Behavior (<45 employees):
        - No auto-adjustment (allows subsidy optimization strategy)
        - Intentional unaffordability may help employees qualify for marketplace subsidies
        """
        flat_amount = config.flat_amount
        multipliers = config.family_multipliers if config.apply_family_multipliers else {'EE': 1.0, 'ES': 1.0, 'EC': 1.0, 'F': 1.0}

        employee_lcsps = self._get_employee_lcsps()

        employee_contributions = {}
        affordability_adjusted_count = 0

        for _, emp in self.census_df.iterrows():
            emp_id = str(emp.get('employee_id') or emp.get('Employee Number', ''))
            emp_age = self._get_employee_age(emp)
            emp_name = self._get_employee_name(emp, emp_id)

            # ===== MEDICARE CHECK (Step 1) =====
            # Medicare-eligible employees (65+) require separate handling
            if emp_age >= MEDICARE_ELIGIBILITY_AGE:
                employee_contributions[emp_id] = {
                    'name': emp_name,
                    'age': emp_age,
                    'is_medicare': True,
                    'excluded_reason': 'Medicare-eligible (65+) - requires separate handling',
                    'monthly_contribution': 0,
                    'annual_contribution': 0,
                    'state': str(emp.get('state') or emp.get('Home State', '')).upper(),
                    'family_status': str(emp.get('family_status') or emp.get('Family Status', 'EE')).upper(),
                }
                continue

            family_status = str(emp.get('family_status') or emp.get('Family Status', 'EE')).upper()
            if family_status not in multipliers:
                family_status = 'EE'

            state = str(emp.get('state') or emp.get('Home State', '')).upper()

            # Get LCSP and SLCSP data
            lcsp_data = employee_lcsps.get(emp_id, {})
            lcsp_ee_rate = lcsp_data.get('lcsp_ee_rate', 0) or 0
            slcsp_ee_rate = lcsp_data.get('slcsp_ee_rate')

            # Log if SLCSP is missing (Step 4 - SLCSP visibility)
            if slcsp_ee_rate is None and lcsp_ee_rate > 0:
                logging.debug(f"SLCSP unavailable for employee {emp_id}, using LCSP for subsidy estimation")

            # Start with flat amount
            base_amount = flat_amount

            # Get age ratio from ACA curve for reference
            emp_age_clamped = min(max(emp_age, 0), 64)
            emp_ratio = ACA_AGE_CURVE.get(emp_age_clamped, 1.0)

            # Apply family multiplier
            final_amount = round(base_amount * multipliers.get(family_status, 1.0), 2)

            # Parse income data using helper
            monthly_income, has_income = self._parse_employee_income(emp)

            # ===== ALE AFFORDABILITY AUTO-ADJUSTMENT (Step 6) =====
            was_bumped = False
            if self.is_ale and has_income and lcsp_ee_rate > 0:
                max_ee_cost = monthly_income * AFFORDABILITY_THRESHOLD_2026
                employee_cost_before_bump = max(0, lcsp_ee_rate - final_amount)
                if employee_cost_before_bump > max_ee_cost:
                    # Unaffordable - ALE must fix to avoid 4980H(b) penalty
                    min_affordable = (lcsp_ee_rate - max_ee_cost) * 1.10  # +10% buffer
                    if min_affordable > final_amount:
                        final_amount = round(min_affordable, 2)
                        was_bumped = True
                        affordability_adjusted_count += 1

            # Calculate employee cost after any adjustments
            employee_cost = max(0, lcsp_ee_rate - final_amount)

            # ===== SUBSIDY ELIGIBILITY (Step 4) - Use unified function =====
            affordability_pct = None
            margin_to_unaffordable = None
            is_subsidy_eligible = None

            if has_income:
                eligibility = check_subsidy_eligibility(
                    monthly_income=monthly_income,
                    lcsp=lcsp_ee_rate,
                    contribution=final_amount,
                    age=emp_age,
                    slcsp=slcsp_ee_rate,
                    family_status=family_status
                )
                is_subsidy_eligible = eligibility.get('eligible', False)
                affordability_pct = eligibility.get('affordability_pct')
                if affordability_pct is not None:
                    threshold_pct = AFFORDABILITY_THRESHOLD_2026 * 100
                    margin_to_unaffordable = affordability_pct - threshold_pct

            employee_contributions[emp_id] = {
                'name': emp_name,
                'age': emp_age,
                'state': state,
                'family_status': family_status,
                'age_ratio': emp_ratio,
                'is_medicare': False,
                'flat_amount': flat_amount,
                'base_contribution': round(base_amount, 2),
                'family_multiplier': multipliers.get(family_status, 1.0),
                'monthly_contribution': round(final_amount, 2),
                'annual_contribution': round(final_amount * 12, 2),
                'lcsp_ee_rate': lcsp_ee_rate,
                'slcsp_ee_rate': slcsp_ee_rate,
                'lcsp_tier_premium': lcsp_data.get('lcsp_tier_premium', 0),
                'rating_area': lcsp_data.get('rating_area', ''),
                'employee_cost': round(employee_cost, 2),
                'monthly_income': round(monthly_income, 2) if has_income else None,
                'affordability_pct': round(affordability_pct, 2) if affordability_pct is not None else None,
                'margin_to_unaffordable': round(margin_to_unaffordable, 2) if margin_to_unaffordable is not None else None,
                'is_subsidy_eligible': is_subsidy_eligible,
                'was_affordability_adjusted': was_bumped,
            }

        # NOTE: No 3:1 ratio check for flat amount strategy.
        # The 3:1 rule applies to age-based variation in contribution design.
        # Flat amount has NO age-based variation (everyone gets the same base).

        # Recalculate totals and aggregations from deduplicated dict
        total_monthly = sum(c['monthly_contribution'] for c in employee_contributions.values())
        by_age_tier, by_family_status = self._recalculate_aggregations(employee_contributions)

        # Count Medicare-excluded employees
        medicare_excluded_count = sum(1 for c in employee_contributions.values() if c.get('is_medicare'))

        return {
            'strategy_type': config.strategy_type.value,
            'strategy_name': config.name,
            'config': {
                'flat_amount': flat_amount,
                'apply_family_multipliers': config.apply_family_multipliers,
                'family_multipliers': multipliers,
            },
            'employee_contributions': employee_contributions,
            'total_monthly': round(total_monthly, 2),
            'total_annual': round(total_monthly * 12, 2),
            'employees_covered': len(employee_contributions),
            'employees_affordability_adjusted': affordability_adjusted_count,
            'medicare_excluded_count': medicare_excluded_count,
            'is_ale': self.is_ale,
            'employees_ratio_adjusted': 0,  # No ratio check for flat amount
            'ratio_adjustment_details': [],  # No ratio check for flat amount
            'by_age_tier': by_age_tier,
            'by_family_status': by_family_status,
        }

    def _calculate_base_age_curve(self, config: StrategyConfig) -> Dict[str, Any]:
        """
        Base Age + ACA 3:1 Curve Strategy.

        User specifies:
        - base_age (e.g., 21)
        - base_contribution (e.g., $400/month)

        System calculates contribution for each employee:
        - contribution = base_contribution * (age_curve[employee_age] / age_curve[base_age])

        ALE Behavior (45+ employees):
        - Auto-bumps contribution to meet IRS affordability (9.96% threshold)
        - Validates 3:1 age ratio compliance

        Non-ALE Behavior (<45 employees):
        - No auto-adjustment (allows subsidy optimization strategy)
        """
        base_age = config.base_age
        base_contribution_input = config.base_contribution
        base_ratio = ACA_AGE_CURVE.get(base_age, 1.0)

        multipliers = config.family_multipliers if config.apply_family_multipliers else {'EE': 1.0, 'ES': 1.0, 'EC': 1.0, 'F': 1.0}

        employee_contributions = {}
        affordability_adjusted_count = 0

        # Get employee LCSPs for reference
        employee_lcsps = self._get_employee_lcsps()

        for _, emp in self.census_df.iterrows():
            emp_id = str(emp.get('employee_id') or emp.get('Employee Number', ''))
            emp_age = self._get_employee_age(emp)
            emp_name = self._get_employee_name(emp, emp_id)

            # ===== MEDICARE CHECK (Step 1) =====
            if emp_age >= MEDICARE_ELIGIBILITY_AGE:
                employee_contributions[emp_id] = {
                    'name': emp_name,
                    'age': emp_age,
                    'is_medicare': True,
                    'excluded_reason': 'Medicare-eligible (65+) - requires separate handling',
                    'monthly_contribution': 0,
                    'annual_contribution': 0,
                    'base_contribution': 0,
                    'state': str(emp.get('state') or emp.get('Home State', '')).upper(),
                    'family_status': str(emp.get('family_status') or emp.get('Family Status', 'EE')).upper(),
                }
                continue

            family_status = str(emp.get('family_status') or emp.get('Family Status', 'EE')).upper()
            if family_status not in multipliers:
                family_status = 'EE'

            state = str(emp.get('state') or emp.get('Home State', '')).upper()

            # Get age ratio from curve (clamp to 0-64 range)
            emp_age_clamped = min(max(emp_age, 0), 64)
            emp_ratio = ACA_AGE_CURVE.get(emp_age_clamped, 1.0)

            # Scale contribution based on age curve
            base_amount = base_contribution_input * (emp_ratio / base_ratio)

            # Apply family multiplier
            final_amount = round(base_amount * multipliers.get(family_status, 1.0), 2)

            # Get LCSP and SLCSP data
            lcsp_data = employee_lcsps.get(emp_id, {})
            lcsp_ee_rate = lcsp_data.get('lcsp_ee_rate', 0) or 0
            slcsp_ee_rate = lcsp_data.get('slcsp_ee_rate')

            # Log if SLCSP is missing
            if slcsp_ee_rate is None and lcsp_ee_rate > 0:
                logging.debug(f"SLCSP unavailable for employee {emp_id}, using LCSP for subsidy estimation")

            # Parse income data
            monthly_income, has_income = self._parse_employee_income(emp)

            # ===== ALE AFFORDABILITY AUTO-ADJUSTMENT (Step 6) =====
            was_bumped = False
            if self.is_ale and has_income and lcsp_ee_rate > 0:
                max_ee_cost = monthly_income * AFFORDABILITY_THRESHOLD_2026
                employee_cost_before_bump = max(0, lcsp_ee_rate - final_amount)
                if employee_cost_before_bump > max_ee_cost:
                    # Unaffordable - ALE must fix
                    min_affordable = (lcsp_ee_rate - max_ee_cost) * 1.10  # +10% buffer
                    if min_affordable > final_amount:
                        final_amount = round(min_affordable, 2)
                        was_bumped = True
                        affordability_adjusted_count += 1

            # Calculate employee cost after any adjustments
            employee_cost = max(0, lcsp_ee_rate - final_amount)

            # ===== SUBSIDY ELIGIBILITY (Step 4) - Use unified function =====
            affordability_pct = None
            margin_to_unaffordable = None
            is_subsidy_eligible = None

            if has_income:
                eligibility = check_subsidy_eligibility(
                    monthly_income=monthly_income,
                    lcsp=lcsp_ee_rate,
                    contribution=final_amount,
                    age=emp_age,
                    slcsp=slcsp_ee_rate,
                    family_status=family_status
                )
                is_subsidy_eligible = eligibility.get('eligible', False)
                affordability_pct = eligibility.get('affordability_pct')
                if affordability_pct is not None:
                    threshold_pct = AFFORDABILITY_THRESHOLD_2026 * 100
                    margin_to_unaffordable = affordability_pct - threshold_pct

            employee_contributions[emp_id] = {
                'name': emp_name,
                'age': emp_age,
                'state': state,
                'family_status': family_status,
                'age_ratio': emp_ratio,
                'is_medicare': False,
                'base_contribution': round(base_amount, 2),
                'family_multiplier': multipliers.get(family_status, 1.0),
                'monthly_contribution': round(final_amount, 2),
                'annual_contribution': round(final_amount * 12, 2),
                'lcsp_ee_rate': lcsp_ee_rate,
                'slcsp_ee_rate': slcsp_ee_rate,
                'lcsp_tier_premium': lcsp_data.get('lcsp_tier_premium', 0),
                'rating_area': lcsp_data.get('rating_area', ''),
                'employee_cost': round(employee_cost, 2),
                'monthly_income': round(monthly_income, 2) if has_income else None,
                'affordability_pct': round(affordability_pct, 2) if affordability_pct is not None else None,
                'margin_to_unaffordable': round(margin_to_unaffordable, 2) if margin_to_unaffordable is not None else None,
                'is_subsidy_eligible': is_subsidy_eligible,
                'was_affordability_adjusted': was_bumped,
            }

        # ===== 3:1 RATIO VALIDATION (Step 5) =====
        ratio_validation = self._validate_3_to_1_ratio(employee_contributions)

        # Recalculate totals and aggregations
        total_monthly = sum(c['monthly_contribution'] for c in employee_contributions.values())
        by_age_tier, by_family_status = self._recalculate_aggregations(employee_contributions)

        # Count Medicare-excluded employees
        medicare_excluded_count = sum(1 for c in employee_contributions.values() if c.get('is_medicare'))

        return {
            'strategy_type': config.strategy_type.value,
            'strategy_name': config.name,
            'config': {
                'base_age': base_age,
                'base_contribution': base_contribution_input,
                'apply_family_multipliers': config.apply_family_multipliers,
                'family_multipliers': multipliers,
            },
            'employee_contributions': employee_contributions,
            'total_monthly': round(total_monthly, 2),
            'total_annual': round(total_monthly * 12, 2),
            'employees_covered': len(employee_contributions),
            'employees_affordability_adjusted': affordability_adjusted_count,
            'medicare_excluded_count': medicare_excluded_count,
            'is_ale': self.is_ale,
            'ratio_validation': ratio_validation,
            'by_age_tier': by_age_tier,
            'by_family_status': by_family_status,
        }

    def _calculate_percentage_lcsp(self, config: StrategyConfig) -> Dict[str, Any]:
        """
        Percentage of LCSP Strategy.

        Each employee gets X% of their individual LCSP.
        Uses per-employee LCSP based on their actual rating area/age.

        Note: No 3:1 ratio check - contributions vary by LCSP, not age directly.
        """
        pct = config.lcsp_percentage / 100.0
        multipliers = config.family_multipliers if config.apply_family_multipliers else {'EE': 1.0, 'ES': 1.0, 'EC': 1.0, 'F': 1.0}

        employee_lcsps = self._get_employee_lcsps()

        employee_contributions = {}

        for _, emp in self.census_df.iterrows():
            emp_id = str(emp.get('employee_id') or emp.get('Employee Number', ''))
            emp_age = self._get_employee_age(emp)
            emp_name = self._get_employee_name(emp, emp_id)

            # ===== MEDICARE CHECK (Step 1) =====
            if emp_age >= MEDICARE_ELIGIBILITY_AGE:
                employee_contributions[emp_id] = {
                    'name': emp_name,
                    'age': emp_age,
                    'is_medicare': True,
                    'excluded_reason': 'Medicare-eligible (65+) - requires separate handling',
                    'monthly_contribution': 0,
                    'annual_contribution': 0,
                    'state': str(emp.get('state') or emp.get('Home State', '')).upper(),
                    'family_status': str(emp.get('family_status') or emp.get('Family Status', 'EE')).upper(),
                }
                continue

            family_status = str(emp.get('family_status') or emp.get('Family Status', 'EE')).upper()
            if family_status not in multipliers:
                family_status = 'EE'

            state = str(emp.get('state') or emp.get('Home State', '')).upper()

            lcsp_data = employee_lcsps.get(emp_id, {})
            lcsp_ee_rate = lcsp_data.get('lcsp_ee_rate', 0) or 0
            slcsp_ee_rate = lcsp_data.get('slcsp_ee_rate')

            # Get age ratio from ACA curve for reference
            emp_age_clamped = min(max(emp_age, 0), 64)
            emp_ratio = ACA_AGE_CURVE.get(emp_age_clamped, 1.0)

            # Contribution = percentage of LCSP
            base_amount = lcsp_ee_rate * pct

            # Apply family multiplier
            final_amount = round(base_amount * multipliers.get(family_status, 1.0), 2)

            # Calculate employee cost
            employee_cost = max(0, lcsp_ee_rate - final_amount)

            # Parse income data
            monthly_income, has_income = self._parse_employee_income(emp)

            # ===== SUBSIDY ELIGIBILITY (Step 4) - Use unified function =====
            affordability_pct = None
            margin_to_unaffordable = None
            is_subsidy_eligible = None

            if has_income:
                eligibility = check_subsidy_eligibility(
                    monthly_income=monthly_income,
                    lcsp=lcsp_ee_rate,
                    contribution=final_amount,
                    age=emp_age,
                    slcsp=slcsp_ee_rate,
                    family_status=family_status
                )
                is_subsidy_eligible = eligibility.get('eligible', False)
                affordability_pct = eligibility.get('affordability_pct')
                if affordability_pct is not None:
                    threshold_pct = AFFORDABILITY_THRESHOLD_2026 * 100
                    margin_to_unaffordable = affordability_pct - threshold_pct

            employee_contributions[emp_id] = {
                'name': emp_name,
                'age': emp_age,
                'state': state,
                'family_status': family_status,
                'age_ratio': emp_ratio,
                'is_medicare': False,
                'lcsp_ee_rate': lcsp_ee_rate,
                'slcsp_ee_rate': slcsp_ee_rate,
                'lcsp_tier_premium': lcsp_data.get('lcsp_tier_premium', 0),
                'lcsp_percentage': config.lcsp_percentage,
                'base_contribution': round(base_amount, 2),
                'family_multiplier': multipliers.get(family_status, 1.0),
                'monthly_contribution': round(final_amount, 2),
                'annual_contribution': round(final_amount * 12, 2),
                'rating_area': lcsp_data.get('rating_area', ''),
                'employee_cost': round(employee_cost, 2),
                'monthly_income': round(monthly_income, 2) if has_income else None,
                'affordability_pct': round(affordability_pct, 2) if affordability_pct is not None else None,
                'margin_to_unaffordable': round(margin_to_unaffordable, 2) if margin_to_unaffordable is not None else None,
                'is_subsidy_eligible': is_subsidy_eligible,
            }

        # Recalculate totals and aggregations
        total_monthly = sum(c['monthly_contribution'] for c in employee_contributions.values())
        by_age_tier, by_family_status = self._recalculate_aggregations(employee_contributions)

        # Count Medicare-excluded employees
        medicare_excluded_count = sum(1 for c in employee_contributions.values() if c.get('is_medicare'))

        return {
            'strategy_type': config.strategy_type.value,
            'strategy_name': config.name,
            'config': {
                'lcsp_percentage': config.lcsp_percentage,
                'apply_family_multipliers': config.apply_family_multipliers,
                'family_multipliers': multipliers,
            },
            'employee_contributions': employee_contributions,
            'total_monthly': round(total_monthly, 2),
            'total_annual': round(total_monthly * 12, 2),
            'employees_covered': len(employee_contributions),
            'medicare_excluded_count': medicare_excluded_count,
            'by_age_tier': by_age_tier,
            'by_family_status': by_family_status,
        }

    def _calculate_fpl_safe_harbor(self, config: StrategyConfig) -> Dict[str, Any]:
        """
        FPL Safe Harbor Strategy.

        This strategy guarantees IRS affordability for ALL employees regardless of income.
        It uses the Federal Poverty Level safe harbor method where an ICHRA is deemed
        affordable if the employee's cost for LCSP ≤ 9.96% of FPL.

        Calculation:
        - FPL monthly (2026) ≈ $1,283
        - 9.96% of FPL ≈ $128/month
        - Required contribution = LCSP - $128 + buffer

        This means every employee's out-of-pocket cost will be ≤ $128/month for LCSP,
        which automatically satisfies the IRS affordability safe harbor.
        """
        from constants import FPL_SAFE_HARBOR_THRESHOLD_2026

        fpl_buffer = config.fpl_buffer  # Additional safety margin
        multipliers = config.family_multipliers if config.apply_family_multipliers else {'EE': 1.0, 'ES': 1.0, 'EC': 1.0, 'F': 1.0}

        employee_lcsps = self._get_employee_lcsps()

        employee_contributions = {}

        # Maximum employee cost under FPL safe harbor (~$128/month for 2026)
        max_ee_cost_fpl = FPL_SAFE_HARBOR_THRESHOLD_2026

        for _, emp in self.census_df.iterrows():
            emp_id = str(emp.get('employee_id') or emp.get('Employee Number', ''))
            emp_age = self._get_employee_age(emp)
            emp_name = self._get_employee_name(emp, emp_id)

            # ===== MEDICARE CHECK (Step 1) =====
            if emp_age >= MEDICARE_ELIGIBILITY_AGE:
                employee_contributions[emp_id] = {
                    'name': emp_name,
                    'age': emp_age,
                    'is_medicare': True,
                    'excluded_reason': 'Medicare-eligible (65+) - requires separate handling',
                    'monthly_contribution': 0,
                    'annual_contribution': 0,
                    'state': str(emp.get('state') or emp.get('Home State', '')).upper(),
                    'family_status': str(emp.get('family_status') or emp.get('Family Status', 'EE')).upper(),
                }
                continue

            family_status = str(emp.get('family_status') or emp.get('Family Status', 'EE')).upper()
            if family_status not in multipliers:
                family_status = 'EE'

            state = str(emp.get('state') or emp.get('Home State', '')).upper()

            # Get LCSP data
            lcsp_data = employee_lcsps.get(emp_id, {})
            lcsp_ee_rate = lcsp_data.get('lcsp_ee_rate', 0) or 0

            # Get age ratio from ACA curve for reference
            emp_age_clamped = min(max(emp_age, 0), 64)
            emp_ratio = ACA_AGE_CURVE.get(emp_age_clamped, 1.0)

            # Calculate minimum contribution for FPL safe harbor
            min_contribution_fpl = max(0, lcsp_ee_rate - max_ee_cost_fpl)

            # Add buffer for safety margin
            base_amount = min_contribution_fpl + fpl_buffer

            # Apply family multiplier
            final_amount = round(base_amount * multipliers.get(family_status, 1.0), 2)

            # Employee's out-of-pocket cost under this strategy
            employee_cost = max(0, lcsp_ee_rate - base_amount)

            employee_contributions[emp_id] = {
                'name': emp_name,
                'age': emp_age,
                'state': state,
                'family_status': family_status,
                'age_ratio': emp_ratio,
                'is_medicare': False,
                'lcsp_ee_rate': lcsp_ee_rate,
                'lcsp_tier_premium': lcsp_data.get('lcsp_tier_premium', 0),
                'fpl_threshold': round(max_ee_cost_fpl, 2),
                'min_contribution_fpl': round(min_contribution_fpl, 2),
                'fpl_buffer': fpl_buffer,
                'base_contribution': round(base_amount, 2),
                'family_multiplier': multipliers.get(family_status, 1.0),
                'monthly_contribution': round(final_amount, 2),
                'annual_contribution': round(final_amount * 12, 2),
                'employee_cost': round(employee_cost, 2),
                'is_fpl_affordable': employee_cost <= max_ee_cost_fpl,
                'rating_area': lcsp_data.get('rating_area', ''),
            }

        # Recalculate totals and aggregations
        total_monthly = sum(c['monthly_contribution'] for c in employee_contributions.values())
        by_age_tier, by_family_status = self._recalculate_aggregations(employee_contributions)

        # Count Medicare-excluded employees
        medicare_excluded_count = sum(1 for c in employee_contributions.values() if c.get('is_medicare'))
        non_medicare_count = len(employee_contributions) - medicare_excluded_count

        return {
            'strategy_type': config.strategy_type.value,
            'strategy_name': config.name,
            'config': {
                'fpl_buffer': fpl_buffer,
                'fpl_threshold': round(max_ee_cost_fpl, 2),
                'apply_family_multipliers': config.apply_family_multipliers,
                'family_multipliers': multipliers,
            },
            'employee_contributions': employee_contributions,
            'total_monthly': round(total_monthly, 2),
            'total_annual': round(total_monthly * 12, 2),
            'employees_covered': len(employee_contributions),
            'medicare_excluded_count': medicare_excluded_count,
            'fpl_affordable_count': non_medicare_count,  # All non-Medicare should be affordable
            'by_age_tier': by_age_tier,
            'by_family_status': by_family_status,
        }

    def _calculate_rate_of_pay_safe_harbor(self, config: StrategyConfig) -> Dict[str, Any]:
        """
        Rate of Pay Safe Harbor Strategy.

        This strategy calculates the MINIMUM contribution needed for each employee
        to achieve IRS affordability based on their actual income (Rate of Pay).
        This is typically the lowest-cost option for ALE employers when income data
        is available, as it targets exactly the affordability threshold.

        Calculation:
        - Employee cost = LCSP - contribution
        - Affordable if: employee cost ≤ 9.96% × monthly income
        - Therefore: contribution ≥ LCSP - (9.96% × monthly income)

        For employees without income data, falls back to FPL safe harbor calculation.
        """
        from constants import FPL_SAFE_HARBOR_THRESHOLD_2026

        fpl_buffer = config.fpl_buffer  # Additional safety margin
        multipliers = config.family_multipliers if config.apply_family_multipliers else {'EE': 1.0, 'ES': 1.0, 'EC': 1.0, 'F': 1.0}

        employee_lcsps = self._get_employee_lcsps()

        employee_contributions = {}

        # FPL threshold for fallback (~$128/month for 2026)
        max_ee_cost_fpl = FPL_SAFE_HARBOR_THRESHOLD_2026

        for _, emp in self.census_df.iterrows():
            emp_id = str(emp.get('employee_id') or emp.get('Employee Number', ''))
            emp_age = self._get_employee_age(emp)
            emp_name = self._get_employee_name(emp, emp_id)

            # ===== MEDICARE CHECK (Step 1) =====
            if emp_age >= MEDICARE_ELIGIBILITY_AGE:
                employee_contributions[emp_id] = {
                    'name': emp_name,
                    'age': emp_age,
                    'is_medicare': True,
                    'excluded_reason': 'Medicare-eligible (65+) - requires separate handling',
                    'monthly_contribution': 0,
                    'annual_contribution': 0,
                    'state': str(emp.get('state') or emp.get('Home State', '')).upper(),
                    'family_status': str(emp.get('family_status') or emp.get('Family Status', 'EE')).upper(),
                    'affordability_method': 'medicare_excluded',
                }
                continue

            family_status = str(emp.get('family_status') or emp.get('Family Status', 'EE')).upper()
            if family_status not in multipliers:
                family_status = 'EE'

            state = str(emp.get('state') or emp.get('Home State', '')).upper()

            # Get LCSP data
            lcsp_data = employee_lcsps.get(emp_id, {})
            lcsp_ee_rate = lcsp_data.get('lcsp_ee_rate', 0) or 0

            # Get age ratio from ACA curve for reference
            emp_age_clamped = min(max(emp_age, 0), 64)
            emp_ratio = ACA_AGE_CURVE.get(emp_age_clamped, 1.0)

            # Parse employee income using helper
            monthly_income, has_income = self._parse_employee_income(emp)

            if has_income:
                # Calculate maximum employee cost at 9.96% affordability threshold
                max_ee_cost = monthly_income * AFFORDABILITY_THRESHOLD_2026

                # Calculate minimum contribution for Rate of Pay affordability
                min_contribution = max(0, lcsp_ee_rate - max_ee_cost)

                # Add buffer for safety margin
                base_amount = min_contribution + fpl_buffer

                # Track affordability details
                income_measure = monthly_income
                affordability_method = 'rate_of_pay'
            else:
                # Fall back to FPL safe harbor if no income data
                min_contribution = max(0, lcsp_ee_rate - max_ee_cost_fpl)
                base_amount = min_contribution + fpl_buffer
                income_measure = None
                affordability_method = 'fpl_fallback'

            # Apply family multiplier
            final_amount = round(base_amount * multipliers.get(family_status, 1.0), 2)

            # Employee's out-of-pocket cost under this strategy
            employee_cost = max(0, lcsp_ee_rate - base_amount)

            employee_contributions[emp_id] = {
                'name': emp_name,
                'age': emp_age,
                'state': state,
                'family_status': family_status,
                'age_ratio': emp_ratio,
                'is_medicare': False,
                'lcsp_ee_rate': lcsp_ee_rate,
                'lcsp_tier_premium': lcsp_data.get('lcsp_tier_premium', 0),
                'monthly_income': income_measure,
                'affordability_method': affordability_method,
                'min_contribution_for_affordability': round(min_contribution, 2),
                'buffer': fpl_buffer,
                'base_contribution': round(base_amount, 2),
                'family_multiplier': multipliers.get(family_status, 1.0),
                'monthly_contribution': round(final_amount, 2),
                'annual_contribution': round(final_amount * 12, 2),
                'employee_cost': round(employee_cost, 2),
                'is_affordable': True,  # Should always be True by design
                'rating_area': lcsp_data.get('rating_area', ''),
            }

        # Recalculate totals and aggregations
        total_monthly = sum(c['monthly_contribution'] for c in employee_contributions.values())
        by_age_tier, by_family_status = self._recalculate_aggregations(employee_contributions)

        # Count employees by method (excluding Medicare)
        employees_with_income = sum(
            1 for c in employee_contributions.values()
            if c.get('affordability_method') == 'rate_of_pay'
        )
        employees_using_fpl_fallback = sum(
            1 for c in employee_contributions.values()
            if c.get('affordability_method') == 'fpl_fallback'
        )
        medicare_excluded_count = sum(
            1 for c in employee_contributions.values()
            if c.get('is_medicare')
        )

        return {
            'strategy_type': config.strategy_type.value,
            'strategy_name': config.name,
            'config': {
                'buffer': fpl_buffer,
                'apply_family_multipliers': config.apply_family_multipliers,
                'family_multipliers': multipliers,
            },
            'employee_contributions': employee_contributions,
            'total_monthly': round(total_monthly, 2),
            'total_annual': round(total_monthly * 12, 2),
            'employees_covered': len(employee_contributions),
            'employees_with_income': employees_with_income,
            'employees_using_fpl_fallback': employees_using_fpl_fallback,
            'medicare_excluded_count': medicare_excluded_count,
            # ===== STEP 7: Fallback visibility flag =====
            'needs_income_data_for_full_compliance': employees_using_fpl_fallback > 0,
            'affordable_count': len(employee_contributions) - medicare_excluded_count,
            'by_age_tier': by_age_tier,
            'by_family_status': by_family_status,
        }

    def _calculate_subsidy_optimized(self, config: StrategyConfig) -> Dict[str, Any]:
        """
        Subsidy-Optimized Strategy for Non-ALE employers.

        Uses a FLAT RATE approach to maximize subsidy eligibility. The flat rate
        is set to the MINIMUM max_contribution across all high-ROI employees,
        ensuring 100% of them remain subsidy-eligible.

        Key Logic:
        1. Calculate Subsidy ROI (Est. Subsidy / LCSP) for each employee
        2. Filter to employees with Subsidy ROI >= 35% (meaningful subsidy value)
        3. Exclude Medicare-eligible employees (age 65+) - they can't get ACA subsidies
        4. Calculate max_contribution for each high-ROI employee that keeps ICHRA unaffordable
        5. Use the MINIMUM of those max_contributions as the flat rate (guarantees 100% eligibility)
        6. Apply that flat rate to ALL non-Medicare employees

        Why Flat Rate over 3:1 Curve:
        - Subsidy eligibility is driven by INCOME, not age
        - A 3:1 curve assumes older employees need higher contributions, but the binding
          constraint is usually a younger, lower-income employee
        - Flat rate avoids accidentally making ICHRA "affordable" for the constraining employee
        - No 3:1 ratio compliance concerns (flat has no age-based variation)

        For ICHRA to be "unaffordable" (employee can decline for subsidies):
        - Employee Cost > 9.96% × Income
        - Employee Cost = LCSP - Contribution
        - Therefore: Contribution < LCSP - (9.96% × Income)
        """
        multipliers = config.family_multipliers if config.apply_family_multipliers else {'EE': 1.0, 'ES': 1.0, 'EC': 1.0, 'F': 1.0}

        employee_lcsps = self._get_employee_lcsps()

        # =====================================================================
        # Step 1: Analyze each employee for subsidy ROI and max contribution
        # =====================================================================
        # For each employee with income data:
        # - Calculate their estimated ACA subsidy using FPL-based sliding scale
        # - Calculate their Subsidy ROI (subsidy / LCSP)
        # - Calculate max contribution that keeps them subsidy-eligible
        # - If ROI >= 35% and non-Medicare, include in optimization
        # =====================================================================
        max_contributions_high_roi = []  # Direct max contributions (not converted to base)
        employee_analysis = {}   # Cache analysis for later
        employees_with_income = 0
        high_roi_count = 0
        medicare_count = 0
        constraining_employee = None  # Track who sets the ceiling
        min_max_contribution = float('inf')

        for _, emp in self.census_df.iterrows():
            emp_id = str(emp.get('employee_id') or emp.get('Employee Number', ''))
            emp_age = emp.get('age') or emp.get('ee_age')
            if emp_age is None or pd.isna(emp_age):
                emp_age = 30
            emp_age = int(emp_age)

            family_status = str(emp.get('family_status') or emp.get('Family Status', 'EE')).upper()
            if family_status not in multipliers:
                family_status = 'EE'

            lcsp_data = employee_lcsps.get(emp_id, {})
            lcsp = lcsp_data.get('lcsp_ee_rate', 0) or 0
            slcsp = lcsp_data.get('slcsp_ee_rate')  # May be None if not available

            # Get employee name for tracking
            first_name = str(emp.get('first_name') or emp.get('First Name') or '').strip()
            last_name = str(emp.get('last_name') or emp.get('Last Name') or '').strip()
            if last_name and first_name:
                emp_name = f"{last_name}, {first_name}"
            elif last_name:
                emp_name = last_name
            elif first_name:
                emp_name = first_name
            else:
                emp_name = emp_id

            # Check Medicare eligibility (65+)
            is_medicare = emp_age >= MEDICARE_AGE
            if is_medicare:
                medicare_count += 1
                employee_analysis[emp_id] = {'is_medicare': True, 'name': emp_name}
                continue

            # Get income
            monthly_income = emp.get('monthly_income') or emp.get('Monthly Income')
            if monthly_income is not None and not pd.isna(monthly_income):
                try:
                    monthly_income = float(monthly_income)
                    if monthly_income > 0 and lcsp > 0:
                        employees_with_income += 1

                        # Calculate estimated subsidy using FPL-based sliding scale
                        estimated_subsidy = _estimate_monthly_subsidy(slcsp, monthly_income, family_status, lcsp)
                        # ROI based on LCSP (what employee would actually pay for cheapest plan)
                        subsidy_roi = estimated_subsidy / lcsp if lcsp > 0 else 0

                        # Max contribution to keep ICHRA unaffordable (with 10% buffer)
                        # Formula: Contribution < LCSP - (9.96% × Income)
                        # With buffer: max_contribution = (LCSP - threshold_cost) × 0.90
                        threshold_cost = monthly_income * AFFORDABILITY_THRESHOLD_2026
                        max_contribution = (lcsp - threshold_cost) * AFFORDABILITY_BUFFER

                        # Cache for later
                        employee_analysis[emp_id] = {
                            'is_medicare': False,
                            'name': emp_name,
                            'age': emp_age,
                            'subsidy_roi': subsidy_roi,
                            'estimated_subsidy': estimated_subsidy,
                            'max_contribution': max_contribution,
                            'monthly_income': monthly_income,
                            'lcsp': lcsp,
                        }

                        # If high ROI (>= 35%) and can be meaningfully made eligible, include in optimization
                        # Require at least $10 headroom to avoid edge cases
                        min_eligibility_headroom = 10.0
                        if subsidy_roi >= SUBSIDY_ROI_THRESHOLD and max_contribution >= min_eligibility_headroom:
                            high_roi_count += 1
                            max_contributions_high_roi.append(max_contribution)

                            # Track the constraining employee (lowest max_contribution)
                            if max_contribution < min_max_contribution:
                                min_max_contribution = max_contribution
                                constraining_employee = {
                                    'employee_id': emp_id,
                                    'name': emp_name,
                                    'age': emp_age,
                                    'monthly_income': monthly_income,
                                    'lcsp': lcsp,
                                    'max_contribution': max_contribution,
                                    'subsidy_roi': subsidy_roi,
                                }
                        else:
                            # Cache that this employee is not high-ROI
                            employee_analysis[emp_id]['is_high_roi'] = False
                except (ValueError, TypeError):
                    pass

        # =====================================================================
        # Step 2: Determine optimal flat contribution
        # =====================================================================
        # Default: Use MINIMUM max_contribution (100% eligibility)
        # Optional: Use percentile for more aggressive approach
        # =====================================================================
        if max_contributions_high_roi:
            sorted_contributions = sorted(max_contributions_high_roi)

            # Use percentile (0 = minimum for 100% eligibility)
            percentile = SUBSIDY_ELIGIBILITY_PERCENTILE
            if percentile == 0:
                # Minimum: guarantees ALL high-ROI employees stay eligible
                optimal_contribution = sorted_contributions[0]
                optimization_method = 'minimum'
                target_eligibility_pct = 100
            else:
                # Percentile approach: accept some becoming affordable for higher contributions
                idx = max(0, int(len(sorted_contributions) * (percentile / 100)) - 1)
                optimal_contribution = sorted_contributions[idx]
                optimization_method = f'percentile_{int(percentile)}'
                target_eligibility_pct = 100 - percentile

            # Floor to nearest dollar, minimum $1
            optimal_contribution = max(1.0, float(int(optimal_contribution)))

            # Count how many will actually be eligible at this contribution level
            employees_eligible_at_optimal = sum(
                1 for mc in max_contributions_high_roi if mc >= optimal_contribution
            )
        else:
            # No high-ROI employees found - default to nominal contribution
            optimal_contribution = 50.0
            optimization_method = 'default'
            target_eligibility_pct = 0
            employees_eligible_at_optimal = 0
            constraining_employee = None

        # =====================================================================
        # Step 3: Calculate contributions for all employees (FLAT RATE)
        # =====================================================================
        # Apply the same flat contribution to all non-Medicare employees
        # Family multipliers still apply on top of the flat base
        # =====================================================================
        employee_contributions = {}

        for _, emp in self.census_df.iterrows():
            emp_id = str(emp.get('employee_id') or emp.get('Employee Number', ''))
            emp_age = emp.get('age') or emp.get('ee_age')
            if emp_age is None or pd.isna(emp_age):
                emp_age = 30
            emp_age = int(emp_age)

            family_status = str(emp.get('family_status') or emp.get('Family Status', 'EE')).upper()
            if family_status not in multipliers:
                family_status = 'EE'

            state = str(emp.get('state') or emp.get('Home State', '')).upper()

            lcsp_data = employee_lcsps.get(emp_id, {})
            lcsp = lcsp_data.get('lcsp_ee_rate', 0) or 0
            slcsp = lcsp_data.get('slcsp_ee_rate', 0) or 0

            # Check if Medicare-eligible
            is_medicare = emp_age >= MEDICARE_AGE
            analysis = employee_analysis.get(emp_id, {})

            # Medicare employees (65+) get $0 contribution - they can't get ACA subsidies
            if is_medicare:
                base_contribution = 0.0
                final_contribution = 0.0
                employee_cost = lcsp
            else:
                # FLAT RATE: same base for everyone (no age curve)
                base_contribution = optimal_contribution
                final_contribution = base_contribution * multipliers.get(family_status, 1.0)
                employee_cost = max(0, lcsp - final_contribution)

            # Get income for eligibility check
            monthly_income = analysis.get('monthly_income')
            has_income = monthly_income is not None and monthly_income > 0
            is_subsidy_eligible = None
            affordability_pct = None
            margin_to_unaffordable = None
            subsidy_roi = analysis.get('subsidy_roi')

            if is_medicare:
                is_subsidy_eligible = False
            elif has_income:
                threshold_cost = monthly_income * AFFORDABILITY_THRESHOLD_2026
                affordability_pct = (employee_cost / monthly_income) * 100
                is_subsidy_eligible = employee_cost > threshold_cost
                margin_to_unaffordable = affordability_pct - (AFFORDABILITY_THRESHOLD_2026 * 100)

            # Get employee name
            emp_name = analysis.get('name', emp_id)
            if not emp_name or emp_name == emp_id:
                first_name = str(emp.get('first_name') or emp.get('First Name') or '').strip()
                last_name = str(emp.get('last_name') or emp.get('Last Name') or '').strip()
                if last_name and first_name:
                    emp_name = f"{last_name}, {first_name}"
                elif last_name:
                    emp_name = last_name
                elif first_name:
                    emp_name = first_name
                else:
                    emp_name = emp_id

            employee_contributions[emp_id] = {
                'name': emp_name,
                'age': emp_age,
                'state': state,
                'family_status': family_status,
                'age_ratio': 1.0,  # Flat rate = no age variation
                'lcsp_ee_rate': lcsp,
                'slcsp_ee_rate': slcsp,
                'lcsp_tier_premium': lcsp_data.get('lcsp_tier_premium', 0),
                'base_contribution': round(base_contribution, 2),
                'family_multiplier': multipliers.get(family_status, 1.0),
                'monthly_contribution': round(final_contribution, 2),
                'annual_contribution': round(final_contribution * 12, 2),
                'employee_cost': round(employee_cost, 2),
                'monthly_income': round(monthly_income, 2) if has_income else None,
                'affordability_pct': round(affordability_pct, 2) if affordability_pct is not None else None,
                'margin_to_unaffordable': round(margin_to_unaffordable, 2) if margin_to_unaffordable is not None else None,
                'is_subsidy_eligible': is_subsidy_eligible,
                'is_medicare': is_medicare,
                'subsidy_roi': round(subsidy_roi, 4) if subsidy_roi is not None else None,
                'rating_area': lcsp_data.get('rating_area', ''),
            }

        # Recalculate totals and aggregations
        total_monthly = sum(c['monthly_contribution'] for c in employee_contributions.values())
        by_age_tier, by_family_status = self._recalculate_aggregations(employee_contributions)

        # Recalculate subsidy counts
        subsidy_eligible_count = sum(
            1 for c in employee_contributions.values()
            if c.get('is_subsidy_eligible') is True
        )
        subsidy_ineligible_count = sum(
            1 for c in employee_contributions.values()
            if c.get('is_subsidy_eligible') is False and not c.get('is_medicare', False)
        )
        no_income_count = sum(
            1 for c in employee_contributions.values()
            if c.get('monthly_income') is None and not c.get('is_medicare', False)
        )
        medicare_count_final = sum(
            1 for c in employee_contributions.values()
            if c.get('is_medicare', False)
        )

        return {
            'strategy_type': config.strategy_type.value,
            'strategy_name': config.name,
            'config': {
                'flat_contribution': round(optimal_contribution, 2),  # The flat rate for all employees
                'apply_family_multipliers': config.apply_family_multipliers,
                'family_multipliers': multipliers,
                'subsidy_roi_threshold': SUBSIDY_ROI_THRESHOLD,
                'optimization_method': optimization_method,
                'eligibility_percentile': SUBSIDY_ELIGIBILITY_PERCENTILE,
                'target_eligibility_pct': target_eligibility_pct,
            },
            'employee_contributions': employee_contributions,
            'total_monthly': round(total_monthly, 2),
            'total_annual': round(total_monthly * 12, 2),
            'employees_covered': len(employee_contributions),
            'employees_with_income': employees_with_income,
            'high_roi_count': high_roi_count,
            'medicare_count': medicare_count_final,
            'subsidy_eligible_count': subsidy_eligible_count,
            'subsidy_ineligible_count': subsidy_ineligible_count,
            'no_income_count': no_income_count,
            'employees_eligible_at_optimal': employees_eligible_at_optimal,
            'constraining_employee': constraining_employee,  # Who sets the ceiling
            'by_age_tier': by_age_tier,
            'by_family_status': by_family_status,
        }

    def _apply_location_adjustments(
        self,
        result: Dict[str, Any],
        location_adjustments: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Apply location-based adjustments to strategy result.

        Location adjustments are flat dollar amounts added on top of the base
        strategy calculation. This allows for geographic cost-of-living adjustments.

        Args:
            result: Strategy result from _calculate_* methods
            location_adjustments: {state_code: adjustment_amount} e.g., {"CA": 100, "NY": 100}

        Returns:
            Modified result with location adjustments applied
        """
        employee_contributions = result.get('employee_contributions', {})
        total_monthly = 0.0
        by_state = {}

        for emp_id, contrib in employee_contributions.items():
            state = contrib.get('state', '')
            adjustment = location_adjustments.get(state, 0)

            # Add location adjustment
            contrib['location_adjustment'] = adjustment
            new_monthly = contrib.get('monthly_contribution', 0) + adjustment
            contrib['monthly_contribution'] = round(new_monthly, 2)
            contrib['annual_contribution'] = round(new_monthly * 12, 2)

            total_monthly += new_monthly

            # Track by state
            if state not in by_state:
                by_state[state] = {'count': 0, 'total_monthly': 0.0, 'adjustment': adjustment}
            by_state[state]['count'] += 1
            by_state[state]['total_monthly'] += new_monthly

        # Update totals
        result['total_monthly'] = round(total_monthly, 2)
        result['total_annual'] = round(total_monthly * 12, 2)
        result['by_state'] = by_state
        result['config']['location_adjustments'] = location_adjustments

        return result

    def get_average_lcsp_by_age(self) -> Dict[int, float]:
        """
        Get average LCSP by age across all employees.
        Useful for showing expected costs at each age.
        """
        employee_lcsps = self._get_employee_lcsps()

        by_age = {}
        for emp_id, data in employee_lcsps.items():
            age = data.get('ee_age')
            if age is None:
                continue
            age = int(age)
            lcsp = data.get('lcsp_ee_rate', 0) or 0

            if age not in by_age:
                by_age[age] = {'total': 0.0, 'count': 0}
            by_age[age]['total'] += lcsp
            by_age[age]['count'] += 1

        return {age: data['total'] / data['count'] if data['count'] > 0 else 0
                for age, data in by_age.items()}

    def get_workforce_summary(self) -> Dict[str, Any]:
        """
        Get summary statistics about the workforce for strategy planning.
        """
        employee_lcsps = self._get_employee_lcsps()

        if not employee_lcsps:
            return {
                'total_employees': 0,
                'avg_age': 0,
                'avg_lcsp': 0,
                'min_lcsp': 0,
                'max_lcsp': 0,
                'by_state': {},
                'by_family_status': {},
            }

        ages = []
        lcsps = []
        by_state = {}
        by_family_status = {}

        for emp_id, data in employee_lcsps.items():
            age = data.get('ee_age')
            lcsp = data.get('lcsp_ee_rate', 0) or 0
            state = data.get('state', 'Unknown')
            fs = data.get('family_status', 'EE')

            if age is not None:
                ages.append(int(age))
            lcsps.append(lcsp)

            if state not in by_state:
                by_state[state] = {'count': 0, 'avg_lcsp': 0, 'total_lcsp': 0}
            by_state[state]['count'] += 1
            by_state[state]['total_lcsp'] += lcsp

            if fs not in by_family_status:
                by_family_status[fs] = {'count': 0}
            by_family_status[fs]['count'] += 1

        # Calculate averages for states
        for state, data in by_state.items():
            data['avg_lcsp'] = data['total_lcsp'] / data['count'] if data['count'] > 0 else 0

        return {
            'total_employees': len(employee_lcsps),
            'avg_age': np.mean(ages) if ages else 0,
            'avg_lcsp': np.mean(lcsps) if lcsps else 0,
            'min_lcsp': min(lcsps) if lcsps else 0,
            'max_lcsp': max(lcsps) if lcsps else 0,
            'by_state': by_state,
            'by_family_status': by_family_status,
        }


def calculate_affordability_impact(
    strategy_result: Dict[str, Any],
    affordability_context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Calculate IRS affordability impact for a proposed contribution strategy.

    An ICHRA is "affordable" if the employee's required contribution for self-only
    LCSP does not exceed 9.96% of their household income (2026 threshold).

    Args:
        strategy_result: Output from ContributionStrategyCalculator.calculate_strategy()
        affordability_context: Dict containing:
            - lcsp_data.by_employee: {emp_id: {lcsp, monthly_income, ...}}
            - current_status: {affordable_at_current, total_gap_annual, current_er_spend_annual}

    Returns:
        Dict with affordability impact metrics:
            - before: {affordable_count, affordable_pct, annual_spend, total_gap}
            - after: {affordable_count, affordable_pct, annual_spend, total_gap}
            - delta: {employees_gained, spend_change, gap_closed}
            - employee_affordability: {emp_id: {is_affordable, employee_cost, affordability_margin}}
    """
    from constants import AFFORDABILITY_THRESHOLD_2026

    threshold = AFFORDABILITY_THRESHOLD_2026  # 0.0996

    employee_contributions = strategy_result.get('employee_contributions', {})
    lcsp_data = affordability_context.get('lcsp_data', {}).get('by_employee', {})
    current_status = affordability_context.get('current_status', {})

    # Calculate BEFORE and AFTER using the SAME population (employees in strategy with income data)
    # This ensures apples-to-apples comparison
    before_affordable_count = 0
    before_total_gap = 0.0
    before_spend = 0.0

    affordable_count = 0
    total_gap = 0.0
    total_proposed_spend = strategy_result.get('total_annual', 0)
    employee_affordability = {}
    employees_analyzed = 0

    for emp_id, contrib in employee_contributions.items():
        emp_lcsp_data = lcsp_data.get(emp_id, {})
        monthly_income = emp_lcsp_data.get('monthly_income', 0)
        lcsp_premium = contrib.get('lcsp_ee_rate', 0) or emp_lcsp_data.get('lcsp', 0)
        monthly_contribution = contrib.get('monthly_contribution', 0)
        # Get current ER contribution from lcsp_data context (original affordability analysis)
        current_er_contribution = emp_lcsp_data.get('current_er_contribution', 0)

        # Skip employees without income data for affordability calculation
        if not monthly_income or monthly_income <= 0:
            employee_affordability[emp_id] = {
                'is_affordable': None,
                'has_income_data': False,
                'employee_cost': None,
                'affordability_margin': None,
            }
            continue

        employees_analyzed += 1

        # Max employee should pay (9.96% of income)
        max_employee_contribution = monthly_income * threshold

        # BEFORE: Calculate affordability with current ER contribution
        before_employee_cost = max(0, lcsp_premium - current_er_contribution)
        before_is_affordable = before_employee_cost <= max_employee_contribution
        if before_is_affordable:
            before_affordable_count += 1
        else:
            before_gap = before_employee_cost - max_employee_contribution
            before_total_gap += before_gap * 12
        before_spend += current_er_contribution * 12

        # AFTER: Calculate affordability with proposed contribution
        employee_cost = max(0, lcsp_premium - monthly_contribution)
        is_affordable = employee_cost <= max_employee_contribution
        affordability_margin = max_employee_contribution - employee_cost

        if is_affordable:
            affordable_count += 1
        else:
            gap = employee_cost - max_employee_contribution
            total_gap += gap * 12  # Annualize

        employee_affordability[emp_id] = {
            'is_affordable': is_affordable,
            'has_income_data': True,
            'employee_cost': round(employee_cost, 2),
            'max_employee_contribution': round(max_employee_contribution, 2),
            'affordability_margin': round(affordability_margin, 2),
            'monthly_contribution': round(monthly_contribution, 2),
            'lcsp_premium': round(lcsp_premium, 2),
            'monthly_income': round(monthly_income, 2),
            'before_is_affordable': before_is_affordable,
        }

    # Before metrics (recalculated for same population)
    before = {
        'affordable_count': before_affordable_count,
        'affordable_pct': (before_affordable_count / employees_analyzed * 100) if employees_analyzed > 0 else 0,
        'annual_spend': before_spend,
        'total_gap': round(before_total_gap, 2),
        'employees_analyzed': employees_analyzed,
    }

    after = {
        'affordable_count': affordable_count,
        'affordable_pct': (affordable_count / employees_analyzed * 100) if employees_analyzed > 0 else 0,
        'annual_spend': total_proposed_spend,
        'total_gap': round(total_gap, 2),
        'employees_analyzed': employees_analyzed,
    }

    # Calculate delta
    delta = {
        'employees_gained': affordable_count - before['affordable_count'],
        'spend_change': total_proposed_spend - before['annual_spend'],
        'gap_closed': before['total_gap'] - total_gap,
    }

    # Build list of unaffordable employees with details for adjustment table
    unaffordable_employees = []
    for emp_id, aff_data in employee_affordability.items():
        if aff_data.get('has_income_data') and not aff_data.get('is_affordable'):
            emp_contrib = employee_contributions.get(emp_id, {})
            monthly_income = aff_data.get('monthly_income', 0)
            lcsp_premium = aff_data.get('lcsp_premium', 0)
            max_ee = aff_data.get('max_employee_contribution', 0)
            current_contribution = aff_data.get('monthly_contribution', 0)

            # Minimum employer contribution needed for affordability
            # min_affordable = LCSP - (income × 9.96%) + $1 buffer for rounding safety
            min_affordable_exact = max(0, lcsp_premium - max_ee)
            min_affordable = min_affordable_exact + 1.0 if min_affordable_exact > 0 else 0

            # Gap = how much more ER needs to contribute beyond current
            gap = max(0, min_affordable - current_contribution)

            unaffordable_employees.append({
                'employee_id': emp_id,
                'name': emp_contrib.get('name', emp_id),
                'age': emp_contrib.get('age', ''),
                'family_status': emp_contrib.get('family_status', 'EE'),
                'monthly_income': round(monthly_income, 2),
                'lcsp_ee_rate': round(lcsp_premium, 2),
                'current_contribution': round(current_contribution, 2),
                'min_affordable': round(min_affordable, 2),
                'gap': round(gap, 2),
                'max_ee_contribution': round(max_ee, 2),
                # Legacy fields for backwards compatibility
                'additional_needed': round(gap, 2),
                'employee_cost': aff_data.get('employee_cost', 0),
            })

    return {
        'before': before,
        'after': after,
        'delta': delta,
        'employee_affordability': employee_affordability,
        'unaffordable_employees': unaffordable_employees,
    }


def get_high_cost_states(
    workforce_summary: Dict[str, Any],
    threshold_pct: float = 15.0
) -> List[str]:
    """
    Identify states with LCSP premiums significantly above average.

    A state is "high-cost" if its average LCSP exceeds the overall workforce
    average by more than the threshold percentage.

    Args:
        workforce_summary: Output from ContributionStrategyCalculator.get_workforce_summary()
        threshold_pct: Percentage above average to qualify as "high-cost" (default 15%)

    Returns:
        List of state codes considered high-cost (e.g., ['CA', 'NY', 'MA'])
    """
    by_state = workforce_summary.get('by_state', {})
    overall_avg = workforce_summary.get('avg_lcsp', 0)

    if not overall_avg or overall_avg <= 0:
        return []

    threshold = overall_avg * (1 + threshold_pct / 100)

    high_cost = []
    for state, data in by_state.items():
        avg_lcsp = data.get('avg_lcsp', 0)
        if avg_lcsp > threshold:
            high_cost.append(state)

    return sorted(high_cost)


if __name__ == "__main__":
    # Test strategy types
    print("Contribution Strategy Calculator")
    print("=" * 50)
    print(f"\nStrategy Types: {[s.value for s in StrategyType]}")
    print(f"\nAge Tiers (for reporting): {[t['age_range'] for t in AGE_TIERS]}")
    print(f"\nACA Age Curve (sample):")
    print(f"  Age 21: {ACA_AGE_CURVE[21]}")
    print(f"  Age 40: {ACA_AGE_CURVE[40]}")
    print(f"  Age 64: {ACA_AGE_CURVE[64]}")
    print(f"\nDefault Family Multipliers: {DEFAULT_FAMILY_MULTIPLIERS}")
    print("\n✓ Module loaded successfully!")
