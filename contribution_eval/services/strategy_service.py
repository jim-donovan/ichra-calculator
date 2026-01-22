"""
Strategy Service for Contribution Evaluation.

Wraps ContributionStrategyCalculator with additional logic for:
- Mode-based strategy filtering
- Affordability calculations
- Session state compatibility
"""

from typing import Dict, List, Optional, Any
import pandas as pd
import logging

from contribution_strategies import (
    ContributionStrategyCalculator,
    StrategyConfig,
    StrategyType,
)
from contribution_eval import (
    OperatingMode,
    SafeHarborType,
    STRATEGY_CONSTRAINTS,
)
from constants import (
    AFFORDABILITY_THRESHOLD_2026,
    ACA_AGE_CURVE,
)

logger = logging.getLogger(__name__)


class StrategyService:
    """
    Service for calculating and managing contribution strategies.

    Provides a higher-level interface over ContributionStrategyCalculator
    with mode-aware filtering and session state compatibility.
    """

    def __init__(self, db, census_df: pd.DataFrame, lcsp_cache: Dict[str, Any] = None):
        """
        Initialize the strategy service.

        Args:
            db: Database connection
            census_df: Census DataFrame with employee data
            lcsp_cache: Optional pre-computed LCSP cache to avoid repeated queries
        """
        self.db = db
        self.census_df = census_df
        self._calculator = ContributionStrategyCalculator(db, census_df, lcsp_cache)
        self._lcsp_cache = lcsp_cache

    def get_lcsp_cache(self) -> Dict[str, Any]:
        """Get the LCSP cache for storage in session state."""
        return self._calculator.get_lcsp_cache()

    def get_available_strategies(self, mode: OperatingMode) -> List[Dict[str, str]]:
        """
        Get list of strategies available for the given operating mode.

        Args:
            mode: Current operating mode

        Returns:
            List of dicts with 'value' and 'label' for each strategy
        """
        available = STRATEGY_CONSTRAINTS.get(mode, [])

        strategy_labels = {
            'flat_amount': 'Flat Amount',
            'base_age_curve': 'ACA 3:1 Contribution Curve',
            'percentage_lcsp': '% of LCSP',
            'fpl_safe_harbor': 'FPL Safe Harbor (Guaranteed Affordable)',
            'rate_of_pay_safe_harbor': 'Rate of Pay Safe Harbor (Minimum Cost)',
            'subsidy_optimized': 'Subsidy-Optimized (Maximize Eligibility)',
        }

        return [
            {'value': s, 'label': strategy_labels.get(s, s)}
            for s in available
        ]

    def calculate_strategy(
        self,
        strategy_type: str,
        base_age: int = 21,
        base_contribution: float = 0,
        lcsp_percentage: float = 100,
        apply_family_multipliers: bool = True,
        apply_location_adjustment: bool = False,
        location_adjustments: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """
        Calculate contributions for all employees under specified strategy.

        Args:
            strategy_type: One of 'flat_amount', 'base_age_curve', 'percentage_lcsp', 'fpl_safe_harbor'
            base_age: Base age for age curve (default 21)
            base_contribution: Base contribution amount for flat/age curve
            lcsp_percentage: Percentage of LCSP for percentage strategy
            apply_family_multipliers: Whether to apply family status multipliers
            apply_location_adjustment: Whether to apply location adjustments
            location_adjustments: Dict of state -> adjustment amount

        Returns:
            Strategy result with employee contributions and summary metrics
        """
        # Map string to StrategyType enum
        type_map = {
            'flat_amount': StrategyType.FLAT_AMOUNT,
            'base_age_curve': StrategyType.BASE_AGE_CURVE,
            'percentage_lcsp': StrategyType.PERCENTAGE_LCSP,
            'fpl_safe_harbor': StrategyType.FPL_SAFE_HARBOR,
            'rate_of_pay_safe_harbor': StrategyType.RATE_OF_PAY_SAFE_HARBOR,
            'subsidy_optimized': StrategyType.SUBSIDY_OPTIMIZED,
        }

        st_type = type_map.get(strategy_type)
        if st_type is None:
            raise ValueError(f"Unknown strategy type: {strategy_type}")

        # Build config
        config = StrategyConfig(
            strategy_type=st_type,
            base_age=base_age,
            base_contribution=base_contribution,
            flat_amount=base_contribution if st_type == StrategyType.FLAT_AMOUNT else 0,
            lcsp_percentage=lcsp_percentage,
            apply_family_multipliers=apply_family_multipliers,
            apply_location_adjustment=apply_location_adjustment,
            location_adjustments=location_adjustments or {},
        )

        # Calculate
        result = self._calculator.calculate_strategy(config)

        return result

    def calculate_multiple_strategies(
        self,
        mode: OperatingMode,
        base_contribution: float = 400,
        lcsp_percentage: float = 100,
        safe_harbor: SafeHarborType = SafeHarborType.FPL,
        use_optimized_ale: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Calculate all available strategies for comparison.

        Args:
            mode: Operating mode to determine available strategies
            base_contribution: Base contribution for flat/age strategies
            lcsp_percentage: Percentage for LCSP strategy
            safe_harbor: Safe harbor method for ALE affordability calculations
            use_optimized_ale: If True and ALE mode, calculate optimized strategies
                              for 100% affordability. If False, use provided params.

        Returns:
            List of strategy results with summary metrics
        """
        # For ALE mode with optimization requested (initial recommendation)
        if mode == OperatingMode.ALE and use_optimized_ale:
            return self._calculate_ale_strategies(safe_harbor)

        # Standard calculation for all modes (including ALE with custom params)
        available = STRATEGY_CONSTRAINTS.get(mode, [])
        results = []

        for strategy_type in available:
            try:
                result = self.calculate_strategy(
                    strategy_type=strategy_type,
                    base_age=21,
                    base_contribution=base_contribution,
                    lcsp_percentage=lcsp_percentage,
                )
                result['strategy_type'] = strategy_type

                # For ALE mode, add affordability analysis (shows gaps if not 100%)
                if mode == OperatingMode.ALE:
                    result = self.calculate_with_affordability(result, safe_harbor)

                results.append(result)
            except Exception as e:
                logger.error(f"Error calculating {strategy_type}: {e}")

        return results

    def _calculate_ale_strategies(
        self,
        safe_harbor: SafeHarborType,
    ) -> List[Dict[str, Any]]:
        """
        Calculate ALE strategies optimized for 100% affordability.

        For ALE employers, the goal is 100% affordability (legal requirement).
        Cost is the OUTPUT - we find the minimum cost to achieve compliance.

        Args:
            safe_harbor: Safe harbor method for income determination

        Returns:
            List of strategy results, each achieving 100% affordability
        """
        from constants import FPL_MONTHLY_2026

        results = []

        # Step 1: Calculate a baseline strategy to get LCSP values for all employees
        # This ensures we use the same employee IDs and LCSP values as the final calculation
        baseline_result = self.calculate_strategy(
            strategy_type='base_age_curve',
            base_age=21,
            base_contribution=100,  # Arbitrary starting point
        )

        # Step 2: Calculate minimum contribution needed for each employee
        base_age = 21
        base_ratio = ACA_AGE_CURVE.get(base_age, 1.0)
        required_bases = []

        employee_contributions = baseline_result.get('employee_contributions', {})

        for emp_id, contrib in employee_contributions.items():
            lcsp = contrib.get('lcsp_ee_rate', 0)
            emp_age = contrib.get('age', 30)
            emp_age = min(max(int(emp_age), 0), 64)
            emp_ratio = ACA_AGE_CURVE.get(emp_age, 1.0)

            # Get income based on safe harbor
            if safe_harbor == SafeHarborType.FPL:
                monthly_income = FPL_MONTHLY_2026
            else:
                # Rate of Pay - get from census
                emp_row = self._get_employee_row(emp_id)
                if emp_row is not None:
                    monthly_income = self._parse_income(emp_row.get('monthly_income'))
                else:
                    monthly_income = None

                if monthly_income is None or monthly_income <= 0:
                    # Fall back to FPL for employees without income data
                    monthly_income = FPL_MONTHLY_2026

            # Calculate minimum contribution for affordability
            # Affordability: LCSP - Contribution <= 9.96% × Income
            # So: Contribution >= LCSP - (9.96% × Income)
            max_employee_cost = monthly_income * AFFORDABILITY_THRESHOLD_2026
            min_contribution = max(0, lcsp - max_employee_cost)

            # Reverse the age curve to find required base
            # Contribution = base_contribution × (emp_ratio / base_ratio)
            # So: base_contribution = min_contribution × (base_ratio / emp_ratio)
            if emp_ratio > 0:
                required_base = min_contribution * (base_ratio / emp_ratio)
                required_bases.append(required_base)

        # Step 3: Use the MAX of all required bases to ensure everyone is covered
        optimal_base = max(required_bases) if required_bases else 0
        # Round UP to next dollar to ensure we meet the threshold
        optimal_base = float(int(optimal_base) + 1)

        # Step 4: Calculate strategy with optimal base and verify affordability
        age_curve_result = self.calculate_strategy(
            strategy_type='base_age_curve',
            base_age=base_age,
            base_contribution=optimal_base,
        )
        age_curve_result['strategy_type'] = 'base_age_curve'
        age_curve_result = self.calculate_with_affordability(age_curve_result, safe_harbor)

        # Step 5: If not 100% affordable, iterate to fix (handles edge cases)
        max_iterations = 10
        iteration = 0
        while iteration < max_iterations:
            affordability = age_curve_result.get('affordability', {})
            if affordability.get('all_affordable', False):
                break

            # Find the largest gap and increase base accordingly
            unaffordable = affordability.get('unaffordable_employees', [])
            if not unaffordable:
                break

            max_gap = max(emp.get('gap', 0) for emp in unaffordable)
            # Increase base by the gap (scaled for youngest employee ratio)
            optimal_base += max_gap + 1

            age_curve_result = self.calculate_strategy(
                strategy_type='base_age_curve',
                base_age=base_age,
                base_contribution=optimal_base,
            )
            age_curve_result['strategy_type'] = 'base_age_curve'
            age_curve_result = self.calculate_with_affordability(age_curve_result, safe_harbor)
            iteration += 1

        results.append(age_curve_result)

        # Strategy 2: Percentage of LCSP (100%) - always 100% affordable
        lcsp_result = self.calculate_strategy(
            strategy_type='percentage_lcsp',
            lcsp_percentage=100,
        )
        lcsp_result['strategy_type'] = 'percentage_lcsp'
        lcsp_result = self.calculate_with_affordability(lcsp_result, safe_harbor)
        results.append(lcsp_result)

        # Strategy 3: FPL Safe Harbor - guaranteed affordable using FPL threshold
        fpl_result = self.calculate_strategy(
            strategy_type='fpl_safe_harbor',
        )
        fpl_result['strategy_type'] = 'fpl_safe_harbor'
        fpl_result = self.calculate_with_affordability(fpl_result, SafeHarborType.FPL)
        results.append(fpl_result)

        # Strategy 4: Rate of Pay Safe Harbor - minimum cost using actual income
        # Only include if census has income data
        if self._has_income_data():
            rop_result = self.calculate_strategy(
                strategy_type='rate_of_pay_safe_harbor',
            )
            rop_result['strategy_type'] = 'rate_of_pay_safe_harbor'
            rop_result = self.calculate_with_affordability(rop_result, SafeHarborType.RATE_OF_PAY)
            # Insert at beginning since it's likely the lowest cost option
            results.insert(0, rop_result)

        return results

    def calculate_with_affordability(
        self,
        strategy_result: Dict[str, Any],
        safe_harbor: SafeHarborType = SafeHarborType.FPL,
    ) -> Dict[str, Any]:
        """
        Add affordability analysis to strategy result.

        For ALE employers, determines how many employees meet the IRS
        affordability test under the proposed strategy.

        Args:
            strategy_result: Output from calculate_strategy()
            safe_harbor: Safe harbor method for income determination

        Returns:
            Strategy result enriched with affordability metrics
        """
        employee_contributions = strategy_result.get('employee_contributions', {})

        # Get LCSP data
        lcsp_by_employee = {}
        for emp_id, contrib in employee_contributions.items():
            lcsp_by_employee[emp_id] = contrib.get('lcsp_ee_rate', 0)

        # Calculate affordability for each employee
        affordable_count = 0
        total_with_income = 0
        unaffordable = []
        skipped_employees = []  # Employees skipped due to missing income data (Rate of Pay only)
        employee_affordability = {}  # Per-employee affordability data for CSV export

        for emp_id, contrib in employee_contributions.items():
            contribution = contrib.get('monthly_contribution', 0)
            lcsp = contrib.get('lcsp_ee_rate', 0)

            # Get income based on safe harbor method
            if safe_harbor == SafeHarborType.FPL:
                # Use FPL as income proxy (most conservative)
                from constants import FPL_MONTHLY_2026
                monthly_income = FPL_MONTHLY_2026
                total_with_income += 1
            else:
                # Rate of Pay: need actual income from census
                emp_row = self._get_employee_row(emp_id)
                if emp_row is None:
                    skipped_employees.append({
                        'employee_id': emp_id,
                        'name': contrib.get('name', emp_id),
                        'reason': 'Employee not found in census',
                    })
                    continue

                monthly_income = self._parse_income(emp_row.get('monthly_income'))
                if monthly_income is None or monthly_income <= 0:
                    skipped_employees.append({
                        'employee_id': emp_id,
                        'name': contrib.get('name', emp_id),
                        'reason': 'No income data',
                    })
                    continue
                total_with_income += 1

            # Affordability check
            employee_cost = max(0, lcsp - contribution)
            max_affordable = monthly_income * AFFORDABILITY_THRESHOLD_2026

            # Calculate affordability percentage (employee's cost as % of income)
            # Threshold is 9.96% - lower is better (more affordable)
            affordability_pct = (employee_cost / monthly_income * 100) if monthly_income > 0 else 0
            margin_to_threshold = AFFORDABILITY_THRESHOLD_2026 * 100 - affordability_pct  # Positive = affordable, negative = gap

            is_affordable = employee_cost <= max_affordable
            gap = 0 if is_affordable else employee_cost - max_affordable

            # Store per-employee affordability data
            employee_affordability[emp_id] = {
                'is_affordable': is_affordable,
                'affordability_pct': round(affordability_pct, 2),
                'threshold_pct': round(AFFORDABILITY_THRESHOLD_2026 * 100, 2),
                'margin_to_threshold': round(margin_to_threshold, 2),
                'income_measure': round(monthly_income, 2),
                'employee_cost': round(employee_cost, 2),
                'gap': round(gap, 2),
            }

            if is_affordable:
                affordable_count += 1
            else:
                unaffordable.append({
                    'employee_id': emp_id,
                    'name': contrib.get('name', emp_id),
                    'current_contribution': contribution,
                    'gap': round(gap, 2),
                    'min_needed': round(contribution + gap + 1, 2),
                })

        # Recalculate counts from the collected data for consistency
        # This ensures counts always match the actual analysis results
        total_employees = len(employee_contributions)
        skipped_count = len(skipped_employees)

        # Add affordability metrics to result
        strategy_result['affordability'] = {
            'safe_harbor': safe_harbor.value,
            'affordable_count': affordable_count,
            'total_analyzed': total_with_income,
            'total_employees': total_employees,  # Total employees in strategy
            'skipped_count': skipped_count,  # Employees skipped (no income data)
            'affordable_pct': (affordable_count / total_with_income * 100) if total_with_income > 0 else 0,
            'all_affordable': affordable_count == total_with_income and total_with_income > 0,
            'unaffordable_employees': unaffordable,
            'skipped_employees': skipped_employees,  # Details of skipped employees
            'employee_affordability': employee_affordability,  # Per-employee data for CSV
        }

        return strategy_result

    def calculate_safe_harbor_comparison(self) -> Dict[str, Dict[str, Any]]:
        """
        Compare costs for Rate of Pay vs FPL safe harbors.

        Used by ALE employers to choose the most cost-effective safe harbor.

        Returns:
            Dict with 'rate_of_pay' and 'fpl' keys, each containing:
            - min_cost: Minimum employer cost to achieve 100% affordability
            - has_data: Whether required data is available
            - employees_covered: Number of employees
        """
        # Check for income data availability
        has_income = any(
            self._parse_income(row.get('monthly_income')) is not None
            for _, row in self.census_df.iterrows()
        )

        results = {}

        # FPL Safe Harbor (always available)
        fpl_result = self.calculate_strategy(
            strategy_type='fpl_safe_harbor',
            apply_family_multipliers=True,
        )
        results['fpl'] = {
            'min_cost': fpl_result.get('total_monthly', 0),
            'annual_cost': fpl_result.get('total_annual', 0),
            'has_data': True,
            'employees_covered': fpl_result.get('employees_covered', 0),
            'description': 'Uses Federal Poverty Level - no income data needed',
        }

        # Rate of Pay (requires income data)
        if has_income:
            # For Rate of Pay, we need to calculate the minimum contribution
            # that makes each employee affordable based on their actual income
            rop_contributions = {}
            total_monthly = 0

            for emp_id, contrib in fpl_result.get('employee_contributions', {}).items():
                emp_row = self._get_employee_row(emp_id)
                if emp_row is None:
                    # Fallback to FPL amount for this employee
                    rop_contributions[emp_id] = contrib.get('monthly_contribution', 0)
                    total_monthly += rop_contributions[emp_id]
                    continue

                monthly_income = self._parse_income(emp_row.get('monthly_income'))
                if monthly_income is None or monthly_income <= 0:
                    # No income data - use FPL fallback
                    rop_contributions[emp_id] = contrib.get('monthly_contribution', 0)
                    total_monthly += rop_contributions[emp_id]
                    continue

                lcsp = contrib.get('lcsp_ee_rate', 0)
                max_ee_cost = monthly_income * AFFORDABILITY_THRESHOLD_2026

                # Minimum contribution for affordability
                min_contrib = max(0, lcsp - max_ee_cost) + 1  # +$1 buffer
                rop_contributions[emp_id] = min_contrib
                total_monthly += min_contrib

            results['rate_of_pay'] = {
                'min_cost': round(total_monthly, 2),
                'annual_cost': round(total_monthly * 12, 2),
                'has_data': True,
                'employees_covered': len(rop_contributions),
                'description': 'Uses actual employee wages - typically lower cost',
            }
        else:
            results['rate_of_pay'] = {
                'min_cost': None,
                'annual_cost': None,
                'has_data': False,
                'employees_covered': 0,
                'description': 'Requires income data in census (Monthly Income column)',
            }

        # W-2 Wages (disabled per PRD)
        results['w2_wages'] = {
            'min_cost': None,
            'annual_cost': None,
            'has_data': False,
            'employees_covered': 0,
            'description': 'Not recommended for planning (retrospective)',
            'disabled': True,
        }

        return results

    def to_session_state_format(
        self,
        strategy_result: Dict[str, Any],
        strategy_type: str,
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Convert strategy result to session state format for Page 5 compatibility.

        Ensures the output matches what the Employer Summary page expects.

        Args:
            strategy_result: Raw result from calculate_strategy()
            strategy_type: Strategy type string
            config: Strategy configuration parameters

        Returns:
            Dict formatted for st.session_state.contribution_settings
        """
        return {
            'strategy_type': strategy_type,
            'strategy_name': strategy_result.get('strategy_name', ''),
            'config': config,
            'contribution_type': 'class_based',  # For compatibility
            'employee_assignments': {
                emp_id: {
                    'monthly_contribution': data.get('monthly_contribution', 0),
                    'annual_contribution': data.get('annual_contribution', 0),
                }
                for emp_id, data in strategy_result.get('employee_contributions', {}).items()
            },
            'total_monthly': strategy_result.get('total_monthly', 0),
            'total_annual': strategy_result.get('total_annual', 0),
            'employees_covered': strategy_result.get('employees_covered', 0),
        }

    def _get_employee_row(self, employee_id: str) -> Optional[Dict]:
        """Get employee row from census by ID."""
        for col in ['employee_id', 'Employee Number', 'employee_number']:
            if col in self.census_df.columns:
                matches = self.census_df[self.census_df[col].astype(str) == str(employee_id)]
                if not matches.empty:
                    return matches.iloc[0].to_dict()
        return None

    def _parse_income(self, value) -> Optional[float]:
        """Parse income value from various formats."""
        if pd.isna(value) or value == '' or value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(str(value).replace('$', '').replace(',', '').strip())
        except (ValueError, TypeError):
            return None

    def _has_income_data(self) -> bool:
        """Check if census has income data for at least some employees."""
        income_cols = ['monthly_income', 'Monthly Income', 'monthly_salary', 'Monthly Salary']
        for col in income_cols:
            if col in self.census_df.columns:
                # Check if any non-null values exist
                values = self.census_df[col].dropna()
                if len(values) > 0:
                    return True
        return False
