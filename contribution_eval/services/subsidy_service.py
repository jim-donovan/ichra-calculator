"""
Subsidy Service for Contribution Evaluation.

Provides subsidy eligibility calculations for the Subsidy-optimized mode.
Uses subsidy_utils for unified eligibility logic.
"""

from typing import Dict, Optional, Any
import pandas as pd
import logging

from subsidy_utils import is_subsidy_eligible

logger = logging.getLogger(__name__)


class SubsidyService:
    """
    Service for analyzing subsidy eligibility and recommendations.

    Used in Subsidy-optimized mode to help employers design strategies
    that allow lower-income employees to access ACA marketplace subsidies.
    """

    def __init__(self, db, census_df: pd.DataFrame):
        """
        Initialize the subsidy service.

        Args:
            db: Database connection
            census_df: Census DataFrame with employee data
        """
        self.db = db
        self.census_df = census_df

    def analyze_workforce_subsidy_potential(
        self,
        strategy_result: Dict[str, Any],
        lcsp_data: Dict[str, float],
        slcsp_data: Dict[str, float],
    ) -> Dict[str, Any]:
        """
        Analyze subsidy eligibility for entire workforce under a strategy.

        Uses subsidy_utils.is_subsidy_eligible for unified eligibility logic.

        Args:
            strategy_result: Output from StrategyService.calculate_strategy()
            lcsp_data: Dict of employee_id -> LCSP premium
            slcsp_data: Dict of employee_id -> SLCSP premium

        Returns:
            Dict with:
            - eligible_count: Number of employees eligible for subsidies
            - ineligible_count: Number of employees ineligible for subsidies
            - medicare_count: Number of Medicare-eligible employees (65+)
            - total_analyzed: Total employees analyzed
            - has_income_data: Whether census has income data (census-level flag)
            - total_monthly_subsidy: Sum of potential subsidies
            - by_employee: List of per-employee subsidy details
        """
        employee_contributions = strategy_result.get('employee_contributions', {})
        results = []
        medicare_count = 0

        # Census-level check: does the census have income data?
        has_income_data = self._census_has_income_data()

        for emp_id, contrib in employee_contributions.items():
            contribution = contrib.get('monthly_contribution', 0)
            lcsp = lcsp_data.get(emp_id, contrib.get('lcsp_ee_rate', 0))
            # Use actual SLCSP from data - don't estimate
            slcsp = slcsp_data.get(emp_id, contrib.get('slcsp_ee_rate', 0))

            # Get employee data
            emp_data = self._get_employee_data(emp_id)
            if emp_data is None:
                continue

            # Get age - prefer from contrib (already calculated by strategy), fall back to census
            age = contrib.get('age')
            if age is None:
                age = emp_data.get('age') or emp_data.get('ee_age') or 30
            age = int(age)

            family_status = str(emp_data.get('family_status') or emp_data.get('Family Status') or 'EE').upper()

            # Get income (may be None) - check multiple column names
            monthly_income = self._parse_income(
                emp_data.get('monthly_income') or emp_data.get('Monthly Income')
            )

            # Use unified eligibility check from subsidy_utils
            eligibility = is_subsidy_eligible(
                monthly_income=monthly_income,
                lcsp=lcsp,
                contribution=contribution,
                age=age,
                slcsp=slcsp,
                family_status=family_status,
            )

            # Track Medicare count
            if eligibility.get('is_medicare', False):
                medicare_count += 1

            # Build result record
            result = {
                'employee_id': emp_id,
                'name': contrib.get('name', emp_id),
                'eligible': eligibility.get('eligible', False),
                'reason': eligibility.get('reason', ''),
                'subsidy': eligibility.get('subsidy_amount', 0),
                'is_medicare': eligibility.get('is_medicare', False),
            }

            # Add additional fields for eligible employees
            if eligibility.get('eligible', False):
                subsidy = eligibility.get('subsidy_amount', 0)
                better_option = 'Subsidy' if subsidy > contribution else 'ICHRA'
                result.update({
                    'ichra_contribution': contribution,
                    'better_option': better_option,
                    'net_benefit': round(max(subsidy, contribution), 2),
                })

            # Add ICHRA cost for affordable employees
            if not eligibility.get('is_unaffordable', True) and not eligibility.get('is_medicare', False):
                result['ichra_cost'] = eligibility.get('employee_cost', 0)

            results.append(result)

        # Recalculate counts from results list for consistency
        eligible_count = sum(1 for e in results if e.get('eligible') is True)
        ineligible_count = sum(1 for e in results if e.get('eligible') is False)
        total_subsidy = sum(e.get('subsidy', 0) for e in results if e.get('subsidy'))

        return {
            'eligible_count': eligible_count,
            'ineligible_count': ineligible_count,
            'medicare_count': medicare_count,
            'total_analyzed': len(results),
            'has_income_data': has_income_data,
            'total_monthly_subsidy': round(total_subsidy, 2),
            'total_annual_subsidy': round(total_subsidy * 12, 2),
            'by_employee': results,
        }

    def get_subsidy_optimization_summary(
        self,
        subsidy_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Summarize subsidy optimization results for display.

        Args:
            subsidy_analysis: Output from analyze_workforce_subsidy_potential()

        Returns:
            Summary dict for UI display
        """
        by_employee = subsidy_analysis.get('by_employee', [])
        has_income_data = subsidy_analysis.get('has_income_data', False)

        # Count by outcome (binary: eligible or ineligible)
        eligible = sum(1 for e in by_employee if e.get('eligible') is True)
        ineligible = sum(1 for e in by_employee if e.get('eligible') is False)
        medicare = sum(1 for e in by_employee if e.get('is_medicare', False))

        # Sum benefits
        total_subsidy = sum(e.get('subsidy', 0) for e in by_employee if e.get('subsidy'))
        total_ichra = sum(e.get('ichra_contribution', 0) for e in by_employee if e.get('ichra_contribution'))

        # Employees better off with subsidy
        subsidy_better = sum(1 for e in by_employee if e.get('better_option') == 'Subsidy')

        return {
            'eligible_count': eligible,
            'ineligible_count': ineligible,
            'medicare_count': medicare,
            'has_income_data': has_income_data,
            'total_monthly_subsidy': round(total_subsidy, 2),
            'total_monthly_ichra': round(total_ichra, 2),
            'employees_better_with_subsidy': subsidy_better,
            'summary_text': self._build_summary_text(eligible, ineligible, medicare, subsidy_better, has_income_data),
        }

    def _census_has_income_data(self) -> bool:
        """Check if census has income data column with any valid values."""
        income_cols = ['monthly_income', 'Monthly Income', 'monthly_salary', 'Monthly Salary']
        for col in income_cols:
            if col in self.census_df.columns:
                # Check if any non-null, positive values exist
                for val in self.census_df[col]:
                    parsed = self._parse_income(val)
                    if parsed is not None and parsed > 0:
                        return True
        return False

    def _get_employee_data(self, employee_id: str) -> Optional[Dict]:
        """Get employee data from census by ID."""
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

    def _build_summary_text(
        self,
        eligible: int,
        ineligible: int,
        medicare: int,
        subsidy_better: int,
        has_income_data: bool
    ) -> str:
        """Build human-readable summary of subsidy analysis."""
        total = eligible + ineligible

        if not has_income_data:
            return "Income data required for subsidy eligibility analysis. Upload a census with Monthly Income column."

        if eligible == 0:
            msg = "No employees eligible for subsidies under this strategy."
            if medicare > 0:
                msg += f" ({medicare} Medicare-eligible employees excluded.)"
            return msg

        parts = []
        parts.append(f"{eligible} of {total} employees ({eligible/total*100:.0f}%) could access ACA subsidies.")

        if subsidy_better > 0:
            parts.append(f"{subsidy_better} would receive more value from subsidies than ICHRA contributions.")

        if medicare > 0:
            parts.append(f"({medicare} Medicare-eligible employees excluded.)")

        return " ".join(parts)
