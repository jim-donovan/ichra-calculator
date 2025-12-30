"""
Contribution Strategy Calculator for ICHRA

Supports multiple contribution strategy types:
1. Base Age + ACA 3:1 Curve - Scale contributions by age using federal age curve
2. Percentage of LCSP - X% of per-employee LCSP
3. Fixed Age Tiers - Fixed amounts per age tier

All strategies support:
- Optional family status multipliers (EE, ES, EC, F)
- Optional location adjustments (flat $ add-on by state)
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import pandas as pd
import numpy as np

from database import DatabaseConnection
from constants import ACA_AGE_CURVE, DEFAULT_FAMILY_MULTIPLIERS


class StrategyType(Enum):
    """Contribution strategy types"""
    BASE_AGE_CURVE = "base_age_curve"      # Base age + ACA 3:1 curve
    PERCENTAGE_LCSP = "percentage_lcsp"     # X% of per-employee LCSP
    FIXED_AGE_TIERS = "fixed_age_tiers"     # Fixed amounts per age tier


# Fixed age tiers for FIXED_AGE_TIERS strategy
FIXED_AGE_TIERS = [
    {'age_range': '21', 'age_min': 21, 'age_max': 21},
    {'age_range': '18-25', 'age_min': 18, 'age_max': 25},
    {'age_range': '26-35', 'age_min': 26, 'age_max': 35},
    {'age_range': '36-45', 'age_min': 36, 'age_max': 45},
    {'age_range': '46-55', 'age_min': 46, 'age_max': 55},
    {'age_range': '56-63', 'age_min': 56, 'age_max': 63},
    {'age_range': '64+', 'age_min': 64, 'age_max': 99},
]


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

    # BASE_AGE_CURVE specific
    base_age: int = 21                      # Default base age
    base_contribution: float = 0.0          # Dollar amount for base age

    # PERCENTAGE_LCSP specific
    lcsp_percentage: float = 100.0          # e.g., 75.0 for 75%

    # FIXED_AGE_TIERS specific
    tier_amounts: Dict[str, float] = field(default_factory=dict)  # {"21": 300, "18-25": 320, ...}

    def __post_init__(self):
        """Generate default name if not provided"""
        if not self.name:
            if self.strategy_type == StrategyType.BASE_AGE_CURVE:
                self.name = f"Base Age {self.base_age} + ACA 3:1 Curve"
            elif self.strategy_type == StrategyType.PERCENTAGE_LCSP:
                self.name = f"{self.lcsp_percentage:.0f}% of Per-Employee LCSP"
            elif self.strategy_type == StrategyType.FIXED_AGE_TIERS:
                self.name = "Fixed Age Tiers"


class ContributionStrategyCalculator:
    """
    Calculate contributions for different strategy types.

    Uses per-employee LCSP (based on their actual rating area/age) as the data source,
    then applies the selected strategy to determine contributions.
    """

    def __init__(self, db: DatabaseConnection, census_df: pd.DataFrame):
        self.db = db
        self.census_df = census_df
        self._lcsp_cache = None  # Cache per-employee LCSP

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
        if config.strategy_type == StrategyType.BASE_AGE_CURVE:
            result = self._calculate_base_age_curve(config)
        elif config.strategy_type == StrategyType.PERCENTAGE_LCSP:
            result = self._calculate_percentage_lcsp(config)
        elif config.strategy_type == StrategyType.FIXED_AGE_TIERS:
            result = self._calculate_fixed_age_tiers(config)
        else:
            raise ValueError(f"Unknown strategy type: {config.strategy_type}")

        # Apply location adjustments if enabled
        if config.apply_location_adjustment and config.location_adjustments:
            result = self._apply_location_adjustments(result, config.location_adjustments)

        return result

    def _get_employee_lcsps(self) -> Dict[str, Dict]:
        """
        Get LCSP for each employee using their actual rating area.
        Uses batch query for efficiency. Results cached.

        Returns:
            Dict[employee_id, {lcsp_ee_rate, state, rating_area, family_status, ee_age, ...}]
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
                'lcsp_tier_premium': emp_detail.get('estimated_tier_premium', 0),  # Full family LCSP
                'lcsp_plan_name': emp_detail.get('lcsp_plan_name'),
                'state': emp_detail.get('state'),
                'rating_area': emp_detail.get('rating_area'),
                'family_status': emp_detail.get('family_status', 'EE'),
                'ee_age': emp_detail.get('ee_age'),
            }

        return self._lcsp_cache

    def _get_age_tier(self, age: int) -> str:
        """Get the age tier for a given age"""
        # Check for exact age 21 first
        if age == 21:
            return '21'
        # Then check other tiers
        for tier in FIXED_AGE_TIERS:
            if tier['age_range'] == '21':
                continue  # Skip standalone 21 tier
            if tier['age_min'] <= age <= tier['age_max']:
                return tier['age_range']
        # Fallback for ages under 18
        return '18-25'

    def _calculate_base_age_curve(self, config: StrategyConfig) -> Dict[str, Any]:
        """
        Base Age + ACA 3:1 Curve Strategy.

        User specifies:
        - base_age (e.g., 21)
        - base_contribution (e.g., $400/month)

        System calculates contribution for each employee:
        - contribution = base_contribution * (age_curve[employee_age] / age_curve[base_age])
        """
        base_age = config.base_age
        base_contribution = config.base_contribution
        base_ratio = ACA_AGE_CURVE.get(base_age, 1.0)

        multipliers = config.family_multipliers if config.apply_family_multipliers else {'EE': 1.0, 'ES': 1.0, 'EC': 1.0, 'F': 1.0}

        employee_contributions = {}
        total_monthly = 0.0
        by_age_tier = {}
        by_family_status = {}

        # Get employee LCSPs for reference (even though not used for calculation)
        employee_lcsps = self._get_employee_lcsps()

        for _, emp in self.census_df.iterrows():
            emp_id = str(emp.get('employee_id') or emp.get('Employee Number', ''))
            emp_age = emp.get('age') or emp.get('ee_age')
            if emp_age is None or pd.isna(emp_age):
                emp_age = 30  # Default
            emp_age = int(emp_age)

            family_status = str(emp.get('family_status') or emp.get('Family Status', 'EE')).upper()
            if family_status not in multipliers:
                family_status = 'EE'

            state = str(emp.get('state') or emp.get('Home State', '')).upper()

            # Get age ratio from curve (clamp to 0-64 range)
            emp_age_clamped = min(max(emp_age, 0), 64)
            emp_ratio = ACA_AGE_CURVE.get(emp_age_clamped, 1.0)

            # Scale contribution based on age curve
            base_amount = base_contribution * (emp_ratio / base_ratio)

            # Apply family multiplier
            final_amount = base_amount * multipliers.get(family_status, 1.0)

            # Get LCSP data for reference
            lcsp_data = employee_lcsps.get(emp_id, {})

            employee_contributions[emp_id] = {
                'age': emp_age,
                'state': state,
                'family_status': family_status,
                'age_ratio': emp_ratio,
                'base_contribution': round(base_amount, 2),
                'family_multiplier': multipliers.get(family_status, 1.0),
                'monthly_contribution': round(final_amount, 2),
                'annual_contribution': round(final_amount * 12, 2),
                'lcsp_ee_rate': lcsp_data.get('lcsp_ee_rate', 0),
                'lcsp_tier_premium': lcsp_data.get('lcsp_tier_premium', 0),  # Full family LCSP
                'rating_area': lcsp_data.get('rating_area', ''),
            }
            total_monthly += final_amount

            # Aggregate by age tier
            age_tier = self._get_age_tier(emp_age)
            if age_tier not in by_age_tier:
                by_age_tier[age_tier] = {'count': 0, 'total_monthly': 0.0}
            by_age_tier[age_tier]['count'] += 1
            by_age_tier[age_tier]['total_monthly'] += final_amount

            # Aggregate by family status
            if family_status not in by_family_status:
                by_family_status[family_status] = {'count': 0, 'total_monthly': 0.0}
            by_family_status[family_status]['count'] += 1
            by_family_status[family_status]['total_monthly'] += final_amount

        return {
            'strategy_type': config.strategy_type.value,
            'strategy_name': config.name,
            'config': {
                'base_age': base_age,
                'base_contribution': base_contribution,
                'apply_family_multipliers': config.apply_family_multipliers,
                'family_multipliers': multipliers,
            },
            'employee_contributions': employee_contributions,
            'total_monthly': round(total_monthly, 2),
            'total_annual': round(total_monthly * 12, 2),
            'employees_covered': len(employee_contributions),
            'by_age_tier': by_age_tier,
            'by_family_status': by_family_status,
        }

    def _calculate_percentage_lcsp(self, config: StrategyConfig) -> Dict[str, Any]:
        """
        Percentage of LCSP Strategy.

        Each employee gets X% of their individual LCSP.
        Uses per-employee LCSP based on their actual rating area/age.
        """
        pct = config.lcsp_percentage / 100.0
        multipliers = config.family_multipliers if config.apply_family_multipliers else {'EE': 1.0, 'ES': 1.0, 'EC': 1.0, 'F': 1.0}

        employee_lcsps = self._get_employee_lcsps()

        employee_contributions = {}
        total_monthly = 0.0
        by_age_tier = {}
        by_family_status = {}

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
            lcsp_ee_rate = lcsp_data.get('lcsp_ee_rate', 0) or 0

            # Get age ratio from ACA curve for reference
            emp_age_clamped = min(max(emp_age, 0), 64)
            emp_ratio = ACA_AGE_CURVE.get(emp_age_clamped, 1.0)

            # Contribution = percentage of LCSP
            base_amount = lcsp_ee_rate * pct

            # Apply family multiplier
            final_amount = base_amount * multipliers.get(family_status, 1.0)

            employee_contributions[emp_id] = {
                'age': emp_age,
                'state': state,
                'family_status': family_status,
                'age_ratio': emp_ratio,
                'lcsp_ee_rate': lcsp_ee_rate,
                'lcsp_tier_premium': lcsp_data.get('lcsp_tier_premium', 0),  # Full family LCSP
                'lcsp_percentage': config.lcsp_percentage,
                'base_contribution': round(base_amount, 2),
                'family_multiplier': multipliers.get(family_status, 1.0),
                'monthly_contribution': round(final_amount, 2),
                'annual_contribution': round(final_amount * 12, 2),
                'rating_area': lcsp_data.get('rating_area', ''),
            }
            total_monthly += final_amount

            # Aggregate by age tier
            age_tier = self._get_age_tier(emp_age)
            if age_tier not in by_age_tier:
                by_age_tier[age_tier] = {'count': 0, 'total_monthly': 0.0}
            by_age_tier[age_tier]['count'] += 1
            by_age_tier[age_tier]['total_monthly'] += final_amount

            # Aggregate by family status
            if family_status not in by_family_status:
                by_family_status[family_status] = {'count': 0, 'total_monthly': 0.0}
            by_family_status[family_status]['count'] += 1
            by_family_status[family_status]['total_monthly'] += final_amount

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
            'by_age_tier': by_age_tier,
            'by_family_status': by_family_status,
        }

    def _calculate_fixed_age_tiers(self, config: StrategyConfig) -> Dict[str, Any]:
        """
        Fixed Age Tiers Strategy.

        User specifies dollar amounts for each age tier.
        Tiers: 21, 18-25, 26-35, 36-45, 46-55, 56-63, 64+

        Auto-affordability: If employee has income data, contribution is automatically
        bumped to min_affordable if tier_amount would be unaffordable (9.96% threshold).
        """
        from constants import AFFORDABILITY_THRESHOLD_2026
        from utils import parse_currency

        tier_amounts = config.tier_amounts or {}
        multipliers = config.family_multipliers if config.apply_family_multipliers else {'EE': 1.0, 'ES': 1.0, 'EC': 1.0, 'F': 1.0}

        employee_lcsps = self._get_employee_lcsps()

        employee_contributions = {}
        total_monthly = 0.0
        by_age_tier = {}
        by_family_status = {}
        employees_affordability_adjusted = 0

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

            # Get LCSP data first (needed for affordability calc)
            lcsp_data = employee_lcsps.get(emp_id, {})
            lcsp_ee_rate = lcsp_data.get('lcsp_ee_rate', 0) or 0

            # Get tier for this employee's age
            age_tier = self._get_age_tier(emp_age)
            tier_amount = tier_amounts.get(age_tier, 0)

            # Check for income data to calculate min_affordable
            monthly_income_raw = emp.get('monthly_income') or emp.get('Monthly Income')
            monthly_income = None
            min_affordable = None
            affordability_adjusted = False

            if monthly_income_raw is not None and not pd.isna(monthly_income_raw):
                # Parse income (handle currency strings)
                if isinstance(monthly_income_raw, (int, float)):
                    monthly_income = float(monthly_income_raw)
                else:
                    monthly_income = parse_currency(str(monthly_income_raw))

                if monthly_income and monthly_income > 0 and lcsp_ee_rate > 0:
                    # Calculate min_affordable: LCSP - (income × 9.96%) + $1 buffer
                    max_ee = monthly_income * AFFORDABILITY_THRESHOLD_2026
                    min_affordable_raw = max(0, lcsp_ee_rate - max_ee)
                    min_affordable = min_affordable_raw + 1.0 if min_affordable_raw > 0 else 0

                    # Use higher of tier amount or min_affordable
                    if min_affordable > tier_amount:
                        base_amount = min_affordable
                        affordability_adjusted = True
                        employees_affordability_adjusted += 1
                    else:
                        base_amount = tier_amount
                else:
                    base_amount = tier_amount
            else:
                base_amount = tier_amount

            # Get age ratio from ACA curve for reference
            emp_age_clamped = min(max(emp_age, 0), 64)
            emp_ratio = ACA_AGE_CURVE.get(emp_age_clamped, 1.0)

            # Apply family multiplier
            final_amount = base_amount * multipliers.get(family_status, 1.0)

            employee_contributions[emp_id] = {
                'age': emp_age,
                'state': state,
                'family_status': family_status,
                'age_ratio': emp_ratio,
                'age_tier': age_tier,
                'tier_amount': round(tier_amount, 2),
                'min_affordable': round(min_affordable, 2) if min_affordable is not None else None,
                'affordability_adjusted': affordability_adjusted,
                'base_contribution': round(base_amount, 2),
                'family_multiplier': multipliers.get(family_status, 1.0),
                'monthly_contribution': round(final_amount, 2),
                'annual_contribution': round(final_amount * 12, 2),
                'lcsp_ee_rate': lcsp_ee_rate,
                'lcsp_tier_premium': lcsp_data.get('lcsp_tier_premium', 0),
                'rating_area': lcsp_data.get('rating_area', ''),
            }
            total_monthly += final_amount

            # Aggregate by age tier
            if age_tier not in by_age_tier:
                by_age_tier[age_tier] = {'count': 0, 'total_monthly': 0.0, 'tier_amount': tier_amount, 'adjusted_count': 0}
            by_age_tier[age_tier]['count'] += 1
            by_age_tier[age_tier]['total_monthly'] += final_amount
            if affordability_adjusted:
                by_age_tier[age_tier]['adjusted_count'] += 1

            # Aggregate by family status
            if family_status not in by_family_status:
                by_family_status[family_status] = {'count': 0, 'total_monthly': 0.0}
            by_family_status[family_status]['count'] += 1
            by_family_status[family_status]['total_monthly'] += final_amount

        return {
            'strategy_type': config.strategy_type.value,
            'strategy_name': config.name,
            'config': {
                'tier_amounts': tier_amounts,
                'apply_family_multipliers': config.apply_family_multipliers,
                'family_multipliers': multipliers,
            },
            'employee_contributions': employee_contributions,
            'total_monthly': round(total_monthly, 2),
            'total_annual': round(total_monthly * 12, 2),
            'employees_covered': len(employee_contributions),
            'employees_affordability_adjusted': employees_affordability_adjusted,
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

    # Before metrics (from context)
    before = {
        'affordable_count': current_status.get('affordable_at_current', 0),
        'affordable_pct': 0,
        'annual_spend': current_status.get('current_er_spend_annual', 0),
        'total_gap': current_status.get('total_gap_annual', 0),
    }

    # Calculate after metrics
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

        # Calculate employee's out-of-pocket cost
        employee_cost = max(0, lcsp_premium - monthly_contribution)

        # Max employee should pay (9.96% of income)
        max_employee_contribution = monthly_income * threshold

        # Is it affordable?
        is_affordable = employee_cost <= max_employee_contribution

        # Affordability margin (positive = room to spare, negative = shortfall)
        affordability_margin = max_employee_contribution - employee_cost

        if is_affordable:
            affordable_count += 1
        else:
            # Gap is how much more ER needs to contribute
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
        }

    # Calculate percentages
    before_total = before.get('affordable_count', 0) + current_status.get('needs_increase', 0)
    before['affordable_pct'] = (before['affordable_count'] / before_total * 100) if before_total > 0 else 0

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
    print(f"\nFixed Age Tiers: {[t['age_range'] for t in FIXED_AGE_TIERS]}")
    print(f"\nACA Age Curve (sample):")
    print(f"  Age 21: {ACA_AGE_CURVE[21]}")
    print(f"  Age 40: {ACA_AGE_CURVE[40]}")
    print(f"  Age 64: {ACA_AGE_CURVE[64]}")
    print(f"\nDefault Family Multipliers: {DEFAULT_FAMILY_MULTIPLIERS}")
    print("\n✓ Module loaded successfully!")
