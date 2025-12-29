"""
Contribution Strategy Calculator for ICHRA

Supports multiple contribution strategy types:
1. Base Age + ACA 3:1 Curve - Scale contributions by age using federal age curve
2. Percentage of LCSP - X% of per-employee LCSP
3. Fixed Age Tiers - Fixed amounts per age tier
4. Custom - Manual dollar amounts per class

All strategies support optional family status multipliers.
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
    CUSTOM = "custom"                        # Manual dollar amounts per class


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

    # BASE_AGE_CURVE specific
    base_age: int = 21                      # Default base age
    base_contribution: float = 0.0          # Dollar amount for base age

    # PERCENTAGE_LCSP specific
    lcsp_percentage: float = 100.0          # e.g., 75.0 for 75%

    # FIXED_AGE_TIERS specific
    tier_amounts: Dict[str, float] = field(default_factory=dict)  # {"21": 300, "18-25": 320, ...}

    # CUSTOM specific
    custom_classes: List[Dict] = field(default_factory=list)  # Manual class definitions

    def __post_init__(self):
        """Generate default name if not provided"""
        if not self.name:
            if self.strategy_type == StrategyType.BASE_AGE_CURVE:
                self.name = f"Base Age {self.base_age} + ACA 3:1 Curve"
            elif self.strategy_type == StrategyType.PERCENTAGE_LCSP:
                self.name = f"{self.lcsp_percentage:.0f}% of Per-Employee LCSP"
            elif self.strategy_type == StrategyType.FIXED_AGE_TIERS:
                self.name = "Fixed Age Tiers"
            elif self.strategy_type == StrategyType.CUSTOM:
                self.name = "Custom Contribution Classes"


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
            return self._calculate_base_age_curve(config)
        elif config.strategy_type == StrategyType.PERCENTAGE_LCSP:
            return self._calculate_percentage_lcsp(config)
        elif config.strategy_type == StrategyType.FIXED_AGE_TIERS:
            return self._calculate_fixed_age_tiers(config)
        elif config.strategy_type == StrategyType.CUSTOM:
            return self._calculate_custom(config)
        else:
            raise ValueError(f"Unknown strategy type: {config.strategy_type}")

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
        """
        tier_amounts = config.tier_amounts or {}
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

            # Get tier for this employee's age
            age_tier = self._get_age_tier(emp_age)
            base_amount = tier_amounts.get(age_tier, 0)

            # Get age ratio from ACA curve for reference
            emp_age_clamped = min(max(emp_age, 0), 64)
            emp_ratio = ACA_AGE_CURVE.get(emp_age_clamped, 1.0)

            # Apply family multiplier
            final_amount = base_amount * multipliers.get(family_status, 1.0)

            lcsp_data = employee_lcsps.get(emp_id, {})

            employee_contributions[emp_id] = {
                'age': emp_age,
                'state': state,
                'family_status': family_status,
                'age_ratio': emp_ratio,
                'age_tier': age_tier,
                'base_contribution': round(base_amount, 2),
                'family_multiplier': multipliers.get(family_status, 1.0),
                'monthly_contribution': round(final_amount, 2),
                'annual_contribution': round(final_amount * 12, 2),
                'lcsp_ee_rate': lcsp_data.get('lcsp_ee_rate', 0),
                'rating_area': lcsp_data.get('rating_area', ''),
            }
            total_monthly += final_amount

            # Aggregate by age tier
            if age_tier not in by_age_tier:
                by_age_tier[age_tier] = {'count': 0, 'total_monthly': 0.0, 'tier_amount': base_amount}
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
                'tier_amounts': tier_amounts,
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

    def _calculate_custom(self, config: StrategyConfig) -> Dict[str, Any]:
        """
        Custom Strategy.

        User defines custom classes with specific dollar amounts.
        Each class has criteria (age range, state, family status) and a contribution amount.
        """
        custom_classes = config.custom_classes or []
        multipliers = config.family_multipliers if config.apply_family_multipliers else {'EE': 1.0, 'ES': 1.0, 'EC': 1.0, 'F': 1.0}

        employee_lcsps = self._get_employee_lcsps()

        employee_contributions = {}
        total_monthly = 0.0
        by_age_tier = {}
        by_family_status = {}

        def match_employee_to_class(emp_age: int, emp_state: str, emp_family_status: str) -> Optional[Dict]:
            """Find the first matching custom class for an employee"""
            for cls in custom_classes:
                criteria = cls.get('criteria', {})
                # Check age range if specified
                if 'age_min' in criteria and emp_age < criteria['age_min']:
                    continue
                if 'age_max' in criteria and emp_age > criteria['age_max']:
                    continue
                # Check state if specified
                if 'state' in criteria and criteria['state'] != emp_state:
                    continue
                # Check family status if specified
                if 'family_status' in criteria and criteria['family_status'] != emp_family_status:
                    continue
                return cls
            return None

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

            # Find matching class
            matched_class = match_employee_to_class(emp_age, state, family_status)
            if matched_class:
                base_amount = matched_class.get('contribution', 0)
                class_name = matched_class.get('name', 'Custom')
            else:
                base_amount = 0
                class_name = 'Unmatched'

            # Apply family multiplier
            final_amount = base_amount * multipliers.get(family_status, 1.0)

            lcsp_data = employee_lcsps.get(emp_id, {})

            employee_contributions[emp_id] = {
                'age': emp_age,
                'state': state,
                'family_status': family_status,
                'class_name': class_name,
                'base_contribution': round(base_amount, 2),
                'family_multiplier': multipliers.get(family_status, 1.0),
                'monthly_contribution': round(final_amount, 2),
                'annual_contribution': round(final_amount * 12, 2),
                'lcsp_ee_rate': lcsp_data.get('lcsp_ee_rate', 0),
                'rating_area': lcsp_data.get('rating_area', ''),
            }
            total_monthly += final_amount

            # Aggregate by age tier (for reference)
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
                'custom_classes': custom_classes,
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
