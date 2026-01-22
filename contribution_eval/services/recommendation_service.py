"""
AI Recommendation Service for Contribution Evaluation.

Replaces the interactive AI chat with proactive recommendations.
Uses a hybrid approach:
1. Rule-based calculations: Pre-compute all strategy costs deterministically
2. AI-powered selection: Claude analyzes results and generates personalized explanation
3. Fallback: Rule-based selection if AI unavailable

See the PRD at /docs/Glove_contribution_modeling_PRD.pdf for detailed requirements.
"""

from typing import Dict, List, Optional, Any
import pandas as pd
import numpy as np
import logging

from contribution_eval import (
    OperatingMode,
    GoalType,
    SafeHarborType,
    CensusContext,
    StrategyRecommendation,
    STRATEGY_CONSTRAINTS,
)
from contribution_eval.services.strategy_service import StrategyService
from contribution_eval.services.ai_client import (
    generate_ai_recommendation,
    is_ai_available,
)
from constants import (
    ACA_AGE_CURVE,
    AFFORDABILITY_THRESHOLD_2026,
    FPL_SAFE_HARBOR_THRESHOLD_2026,
)

logger = logging.getLogger(__name__)


class RecommendationService:
    """
    Service for generating proactive AI strategy recommendations.

    Implements a hybrid approach:
    - Deterministic cost calculations for compliance/auditability
    - AI-powered strategy selection and explanation generation
    - Automatic fallback to rule-based when AI unavailable
    """

    def __init__(
        self,
        db,
        census_df: pd.DataFrame,
        context: CensusContext,
        lcsp_cache: Dict[str, Any] = None,
    ):
        """
        Initialize the recommendation service.

        Args:
            db: Database connection
            census_df: Census DataFrame
            context: Pre-computed census context
            lcsp_cache: Optional pre-computed LCSP cache to avoid repeated queries
        """
        self.db = db
        self.census_df = census_df
        self.context = context
        self._strategy_service = StrategyService(db, census_df, lcsp_cache)

    def generate_recommendation(
        self,
        mode: OperatingMode,
        goal: GoalType = GoalType.STANDARD,
    ) -> StrategyRecommendation:
        """
        Generate the optimal strategy recommendation for the given mode.

        This is the main entry point called on page load and when
        the user changes the goal selection.

        For NON_ALE_SUBSIDY mode: Directly uses subsidy_optimized strategy
        (no comparison needed - the goal IS the strategy).

        For other modes, uses a hybrid approach:
        1. Pre-compute all available strategies with costs
        2. Call Claude to select optimal strategy and generate explanation
        3. Fall back to rule-based if AI unavailable

        Args:
            mode: Current operating mode (ALE, Non-ALE Standard, Non-ALE Subsidy)
            goal: User's goal (Standard or Subsidy-optimized)

        Returns:
            StrategyRecommendation with optimal strategy and explanation
        """
        # NON_ALE_SUBSIDY: The goal IS the strategy - no comparison needed
        if mode == OperatingMode.NON_ALE_SUBSIDY:
            return self._generate_subsidy_optimized_recommendation()

        # Step 1: Pre-compute all strategy costs
        precomputed = self._precompute_strategies(mode)

        if not precomputed:
            logger.warning("No strategies could be calculated, returning default")
            return self._default_recommendation()

        # Step 2: Build census summary for AI
        census_summary = self._build_census_summary()

        # Step 3: Try AI-powered recommendation
        if is_ai_available():
            ai_result = self._get_ai_recommendation(
                census_summary, precomputed, mode, goal
            )
            if ai_result:
                return self._build_recommendation_from_ai(ai_result, precomputed, mode)

        # Step 4: Fall back to rule-based selection
        logger.info("Using rule-based recommendation (AI unavailable or failed)")
        return self._fallback_recommendation(mode, goal, precomputed)

    def _precompute_strategies(self, mode: OperatingMode) -> List[Dict[str, Any]]:
        """
        Pre-compute all available strategies for the mode.

        For ALE mode: Uses affordability-optimized calculation with the
        appropriate safe harbor (Rate of Pay if income data available, else FPL).

        Returns list of strategy results with costs and employee breakdowns.
        """
        # For ALE mode, use the affordability-optimized calculation
        if mode == OperatingMode.ALE:
            # Choose safe harbor based on income data availability
            safe_harbor = SafeHarborType.RATE_OF_PAY if self.context.has_income_data else SafeHarborType.FPL
            harbor_label = "Rate of Pay" if safe_harbor == SafeHarborType.RATE_OF_PAY else "FPL Safe Harbor"
            self._contribution_basis = f"Optimized for 100% affordability using {harbor_label}"
            self._estimated_base_contribution = 400  # Fallback, actual is calculated per safe harbor

            return self._strategy_service.calculate_multiple_strategies(
                mode=mode,
                safe_harbor=safe_harbor,
                use_optimized_ale=True,  # Use optimization for initial recommendation
            )

        # For Non-ALE modes, use standard calculation
        available = STRATEGY_CONSTRAINTS.get(mode, [])
        results = []

        # Estimate base contribution based on mode
        if mode == OperatingMode.NON_ALE_SUBSIDY:
            # For subsidy-optimized: LOW contributions maximize subsidy eligibility
            base_contrib = 50
            self._contribution_basis = "Optimized for subsidy eligibility"
        else:
            base_contrib, self._contribution_basis = self._estimate_base_contribution()

        # Store estimated contribution for use by AI recommendation builder
        self._estimated_base_contribution = base_contrib

        for strategy_type in available:
            try:
                if strategy_type == 'percentage_lcsp':
                    result = self._strategy_service.calculate_strategy(
                        strategy_type=strategy_type,
                        lcsp_percentage=100,
                    )
                elif strategy_type in ['fpl_safe_harbor', 'rate_of_pay_safe_harbor', 'subsidy_optimized']:
                    # Safe harbor and subsidy strategies calculate per-employee contributions automatically
                    result = self._strategy_service.calculate_strategy(
                        strategy_type=strategy_type,
                        apply_family_multipliers=True,
                    )
                else:
                    result = self._strategy_service.calculate_strategy(
                        strategy_type=strategy_type,
                        base_age=21,
                        base_contribution=base_contrib,
                    )

                result['strategy_type'] = strategy_type
                results.append(result)

            except Exception as e:
                logger.warning(f"Error calculating {strategy_type}: {e}")
                continue

        return results

    def _build_census_summary(self) -> Dict[str, Any]:
        """
        Build census summary dictionary for AI prompt.
        """
        return {
            'employee_count': self.context.employee_count,
            'avg_age': self.context.avg_age,
            'min_age': self.context.min_age,
            'max_age': self.context.max_age,
            'age_distribution': self.context.age_distribution,
            'states': self.context.states,
            'is_multi_state': self.context.is_multi_state,
            'has_income_data': self.context.has_income_data,
            'has_current_er_spend': self.context.has_current_er_spend,
            'total_current_er_monthly': self.context.total_current_er_monthly,
            'avg_income': self.context.avg_income,
            'family_status_distribution': self.context.family_status_distribution,
        }

    def _get_ai_recommendation(
        self,
        census_summary: Dict[str, Any],
        precomputed: List[Dict[str, Any]],
        mode: OperatingMode,
        goal: GoalType,
    ) -> Optional[Dict[str, Any]]:
        """
        Call Claude API for strategy selection and explanation.

        Returns dict with 'selected_strategy' and 'explanation' or None if failed.
        """
        # Build mode and goal descriptions
        mode_desc = {
            OperatingMode.NON_ALE_STANDARD: "Non-ALE Standard (under 46 employees, minimize cost)",
            OperatingMode.NON_ALE_SUBSIDY: "Non-ALE Subsidy-Optimized (under 46 employees, maximize subsidy eligibility)",
            OperatingMode.ALE: "ALE (46+ employees, must achieve 100% IRS affordability compliance)",
        }.get(mode, str(mode))

        goal_desc = {
            GoalType.STANDARD: "Minimize employer cost while providing competitive marketplace coverage",
            GoalType.SUBSIDY_OPTIMIZED: "Design contributions so employees can decline ICHRA and access ACA subsidies",
        }.get(goal, str(goal))

        # Call AI
        result, error = generate_ai_recommendation(
            census_summary=census_summary,
            precomputed_strategies=precomputed,
            mode=mode_desc,
            goal=goal_desc,
        )

        if error:
            logger.warning(f"AI recommendation failed: {error}")
            return None

        return result

    def _build_recommendation_from_ai(
        self,
        ai_result: Dict[str, Any],
        precomputed: List[Dict[str, Any]],
        mode: OperatingMode,
    ) -> StrategyRecommendation:
        """
        Build StrategyRecommendation from AI result and precomputed data.
        """
        selected_type = ai_result.get('selected_strategy', 'base_age_curve')
        explanation = ai_result.get('explanation', '')

        # Find the matching precomputed result
        matching_result = None
        for result in precomputed:
            if result.get('strategy_type') == selected_type:
                matching_result = result
                break

        # If AI selected an invalid strategy, fall back to first available
        if matching_result is None:
            logger.warning(f"AI selected invalid strategy {selected_type}, using first available")
            matching_result = precomputed[0] if precomputed else {}
            selected_type = matching_result.get('strategy_type', 'base_age_curve')

        # Extract cost metrics
        total_monthly = matching_result.get('total_monthly', 0)
        total_annual = matching_result.get('total_annual', 0)

        # Calculate vs current delta
        vs_current = None
        if self.context.has_current_er_spend and self.context.total_current_er_monthly:
            vs_current = total_monthly - self.context.total_current_er_monthly

        # Get affordability metrics for ALE
        affordable_count = None
        affordable_pct = None
        if mode == OperatingMode.ALE:
            affordability = matching_result.get('affordability', {})
            affordable_count = affordability.get('affordable_count', 0)
            affordable_pct = affordability.get('affordable_pct', 0)

        # Determine safe harbor for ALE
        safe_harbor = None
        if mode == OperatingMode.ALE:
            safe_harbor = SafeHarborType.RATE_OF_PAY if self.context.has_income_data else SafeHarborType.FPL

        # Get base contribution (uses estimated value for strategies that don't have it)
        base_contribution = self._get_base_contribution_from_result(matching_result, selected_type)

        return StrategyRecommendation(
            strategy_type=selected_type,
            base_age=21,
            base_contribution=base_contribution,
            safe_harbor=safe_harbor,
            explanation=explanation,
            contribution_basis=getattr(self, '_contribution_basis', ''),
            total_monthly=total_monthly,
            total_annual=total_annual,
            affordable_count=affordable_count,
            affordable_pct=affordable_pct,
            vs_current_delta=vs_current,
        )

    def _generate_subsidy_optimized_recommendation(self) -> StrategyRecommendation:
        """
        Generate subsidy-optimized recommendation directly.

        For NON_ALE_SUBSIDY mode, the goal IS the strategy - no comparison needed.
        Uses Subsidy ROI threshold: finds the maximum contribution that guarantees
        subsidy eligibility for all employees with Subsidy ROI >= 40% (meaningful
        subsidy value), while providing a competitive ICHRA contribution to all.
        """
        try:
            result = self._strategy_service.calculate_strategy(
                strategy_type='subsidy_optimized',
                apply_family_multipliers=True,
            )
            result['strategy_type'] = 'subsidy_optimized'
        except Exception as e:
            logger.error(f"Error calculating subsidy_optimized strategy: {e}")
            return self._default_recommendation()

        # Extract metrics
        total_monthly = result.get('total_monthly', 0)
        total_annual = result.get('total_annual', 0)
        config = result.get('config', {})

        # Get flat contribution (new flat rate approach)
        flat_contribution = config.get('flat_contribution', 0)

        # Get subsidy eligibility metrics
        eligible_count = result.get('subsidy_eligible_count', 0)
        high_roi_count = result.get('high_roi_count', 0)
        medicare_count = result.get('medicare_count', 0)
        employees_eligible_at_optimal = result.get('employees_eligible_at_optimal', 0)
        constraining_employee = result.get('constraining_employee')
        total = self.context.employee_count

        # Build explanation with flat rate context
        eligible_pct = (eligible_count / total * 100) if total > 0 else 0

        # Build dynamic explanation
        explanation_parts = []

        if high_roi_count > 0 and flat_contribution > 0:
            explanation_parts.append(
                f"A flat contribution of ${flat_contribution:.0f}/month keeps all {employees_eligible_at_optimal} "
                f"high-ROI employees (≥35% subsidy value) eligible for ACA subsidies."
            )
            if constraining_employee:
                explanation_parts.append(
                    f"This rate is set by {constraining_employee.get('name', 'an employee')} "
                    f"(age {constraining_employee.get('age', '?')})."
                )
        elif flat_contribution > 0:
            explanation_parts.append(
                f"Flat contribution of ${flat_contribution:.0f}/month for all employees. "
                f"No employees have subsidies covering ≥35% of their premium."
            )
        else:
            explanation_parts.append(
                "Unable to calculate optimal contribution. Check income data availability."
            )

        explanation_parts.append(
            f"{eligible_count} of {total} employees ({eligible_pct:.0f}%) can access ACA subsidies."
        )

        if medicare_count > 0:
            explanation_parts.append(f"{medicare_count} Medicare-eligible employee(s) excluded from subsidy calculations.")

        if not self.context.has_income_data:
            explanation_parts.append("Note: Without income data, subsidy eligibility is estimated.")

        explanation = " ".join(explanation_parts)

        return StrategyRecommendation(
            strategy_type='subsidy_optimized',
            base_age=21,
            base_contribution=flat_contribution,  # Use flat contribution
            explanation=explanation,
            contribution_basis=f"Flat rate optimized for 100% subsidy eligibility",
            total_monthly=total_monthly,
            total_annual=total_annual,
            subsidy_eligible_count=eligible_count,
        )

    def _fallback_recommendation(
        self,
        mode: OperatingMode,
        goal: GoalType,
        precomputed: List[Dict[str, Any]],
    ) -> StrategyRecommendation:
        """
        Generate rule-based recommendation when AI is unavailable.
        """
        if mode == OperatingMode.ALE:
            return self._fallback_for_ale(precomputed)
        elif mode == OperatingMode.NON_ALE_SUBSIDY:
            # This shouldn't be reached anymore since we handle subsidy mode directly
            return self._fallback_for_subsidy(precomputed)
        else:
            return self._fallback_for_standard(precomputed)

    def _fallback_for_standard(self, precomputed: List[Dict[str, Any]]) -> StrategyRecommendation:
        """
        Rule-based recommendation for Non-ALE Standard mode.
        Goal: Minimize employer cost.
        """
        # Pick lowest cost strategy
        best_result = min(precomputed, key=lambda x: x.get('total_monthly', float('inf')))
        strategy_type = best_result.get('strategy_type', 'base_age_curve')

        # Build template explanation
        total_monthly = best_result.get('total_monthly', 0)
        employee_count = best_result.get('employees_covered', self.context.employee_count)

        explanation = self._build_standard_explanation(strategy_type, best_result)

        # Calculate vs current
        vs_current = None
        if self.context.has_current_er_spend and self.context.total_current_er_monthly:
            vs_current = total_monthly - self.context.total_current_er_monthly

        base_contribution = self._get_base_contribution_from_result(best_result, strategy_type)

        return StrategyRecommendation(
            strategy_type=strategy_type,
            base_age=21,
            base_contribution=base_contribution,
            explanation=explanation,
            contribution_basis=getattr(self, '_contribution_basis', ''),
            total_monthly=total_monthly,
            total_annual=best_result.get('total_annual', 0),
            vs_current_delta=vs_current,
        )

    def _fallback_for_subsidy(self, precomputed: List[Dict[str, Any]]) -> StrategyRecommendation:
        """
        Rule-based recommendation for Non-ALE Subsidy-optimized mode.
        Goal: Maximize employees who can access ACA subsidies.
        """
        # For subsidy optimization, lower contributions = more employees declining ICHRA
        # Start with lowest cost strategy
        best_result = min(precomputed, key=lambda x: x.get('total_monthly', float('inf')))
        strategy_type = best_result.get('strategy_type', 'flat_amount')

        # Count subsidy-eligible employees
        eligible_count = self._count_subsidy_eligible(best_result)
        total = self.context.employee_count

        explanation = self._build_subsidy_explanation(
            strategy_type, best_result, eligible_count, total
        )

        base_contribution = self._get_base_contribution_from_result(best_result, strategy_type)

        return StrategyRecommendation(
            strategy_type=strategy_type,
            base_age=21,
            base_contribution=base_contribution,
            explanation=explanation,
            contribution_basis=getattr(self, '_contribution_basis', ''),
            total_monthly=best_result.get('total_monthly', 0),
            total_annual=best_result.get('total_annual', 0),
            subsidy_eligible_count=eligible_count,
        )

    def _fallback_for_ale(self, precomputed: List[Dict[str, Any]]) -> StrategyRecommendation:
        """
        Rule-based recommendation for ALE mode.
        Goal: Achieve 100% affordability at minimum cost.
        """
        # For ALE, prefer strategies that achieve 100% affordability
        affordable_strategies = [
            s for s in precomputed
            if s.get('affordability', {}).get('affordable_pct', 0) >= 100
        ]

        if affordable_strategies:
            # Pick lowest cost among 100% affordable
            best_result = min(affordable_strategies, key=lambda x: x.get('total_monthly', float('inf')))
        else:
            # None achieve 100%, pick highest affordability %
            best_result = max(precomputed, key=lambda x: x.get('affordability', {}).get('affordable_pct', 0))

        strategy_type = best_result.get('strategy_type', 'base_age_curve')
        affordability = best_result.get('affordability', {})

        # Determine safe harbor
        safe_harbor = SafeHarborType.RATE_OF_PAY if self.context.has_income_data else SafeHarborType.FPL

        # Get safe harbor comparison for explanation
        harbor_comparison = self._strategy_service.calculate_safe_harbor_comparison()

        explanation = self._build_ale_explanation(
            safe_harbor, best_result, harbor_comparison, self.context.has_income_data
        )

        base_contribution = self._get_base_contribution_from_result(best_result, strategy_type)

        return StrategyRecommendation(
            strategy_type=strategy_type,
            base_age=21,
            base_contribution=base_contribution,
            safe_harbor=safe_harbor,
            explanation=explanation,
            contribution_basis=getattr(self, '_contribution_basis', ''),
            total_monthly=best_result.get('total_monthly', 0),
            total_annual=best_result.get('total_annual', 0),
            affordable_count=affordability.get('affordable_count', 0),
            affordable_pct=affordability.get('affordable_pct', 0),
        )

    def _get_base_contribution_from_result(
        self, result: Dict[str, Any], strategy_type: str
    ) -> float:
        """
        Extract base_contribution from result config.

        For strategies that don't use base_contribution (percentage_lcsp, safe harbors),
        returns the estimated value instead for use in comparison calculations.
        """
        config = result.get('config', {})

        # Check for flat_contribution first (subsidy_optimized uses this)
        base_contribution = config.get('flat_contribution') or config.get('base_contribution') or config.get('flat_amount', 0)

        # If strategy doesn't have base_contribution, use our estimate
        if base_contribution == 0 and strategy_type in ['percentage_lcsp', 'fpl_safe_harbor', 'rate_of_pay_safe_harbor']:
            base_contribution = getattr(self, '_estimated_base_contribution', 400)

        return base_contribution

    def _estimate_base_contribution(self) -> tuple[float, str]:
        """
        Estimate a reasonable base contribution based on census demographics.
        Uses average LCSP if available, otherwise age-based default.

        Returns:
            Tuple of (contribution_amount, explanation_string)
        """
        # Try to get average LCSP
        try:
            avg_lcsp = self._strategy_service._calculator.get_workforce_summary().get('avg_lcsp', 0)
            if avg_lcsp > 0:
                # Start at 75% of average LCSP
                contribution = round(avg_lcsp * 0.75, -1)  # Round to nearest $10
                basis = f"75% of avg LCSP (${avg_lcsp:,.0f})"
                return contribution, basis
        except Exception:
            pass

        # Default based on average age
        if self.context.avg_age > 50:
            return 600, f"Age-based default (avg age {self.context.avg_age:.0f})"
        elif self.context.avg_age > 40:
            return 500, f"Age-based default (avg age {self.context.avg_age:.0f})"
        else:
            return 400, f"Age-based default (avg age {self.context.avg_age:.0f})"

    def _count_subsidy_eligible(self, strategy_result: Dict[str, Any]) -> int:
        """
        Count employees who would be subsidy-eligible under this strategy.

        An employee is subsidy-eligible if the ICHRA is "unaffordable" for them,
        meaning their cost for LCSP exceeds 9.96% of their income.
        """
        eligible = 0
        employee_contributions = strategy_result.get('employee_contributions', {})

        for emp_id, contrib in employee_contributions.items():
            contribution = contrib.get('monthly_contribution', 0)
            lcsp = contrib.get('lcsp_ee_rate', 0)

            # Get employee income
            emp_row = self._strategy_service._get_employee_row(emp_id)
            if emp_row is None:
                continue

            monthly_income = self._strategy_service._parse_income(
                emp_row.get('monthly_income') or emp_row.get('Monthly Income')
            )
            if monthly_income is None or monthly_income <= 0:
                continue

            # Check if unaffordable (employee cost > 9.96% of income)
            employee_cost = max(0, lcsp - contribution)
            max_affordable = monthly_income * AFFORDABILITY_THRESHOLD_2026

            if employee_cost > max_affordable:
                eligible += 1

        return eligible

    # =========================================================================
    # TEMPLATE-BASED EXPLANATIONS (Fallback)
    # =========================================================================

    def _build_standard_explanation(
        self,
        strategy: str,
        result: Dict[str, Any],
    ) -> str:
        """Build explanation for Standard mode recommendation with specific data points."""
        total_monthly = result.get('total_monthly', 0)
        employee_count = result.get('employees_covered', 0)
        avg_contribution = total_monthly / employee_count if employee_count > 0 else 0

        # Get LCSP coverage info
        employee_contributions = result.get('employee_contributions', {})
        lcsp_coverage_pcts = []
        for emp_id, data in employee_contributions.items():
            lcsp = data.get('lcsp_ee_rate', 0)
            contrib = data.get('monthly_contribution', 0)
            if lcsp > 0:
                lcsp_coverage_pcts.append((contrib / lcsp) * 100)

        avg_lcsp_coverage = sum(lcsp_coverage_pcts) / len(lcsp_coverage_pcts) if lcsp_coverage_pcts else 0

        parts = []

        if strategy == 'flat_amount':
            flat_amount = result.get('config', {}).get('flat_amount', avg_contribution)
            parts.append(
                f"At ${flat_amount:,.0f}/month, this covers an average of {avg_lcsp_coverage:.0f}% of each employee's LCSP."
            )
            if self.context.is_multi_state:
                parts.append(
                    f"Your {employee_count} employees across {len(self.context.states)} states "
                    f"benefit from predictable, uniform contributions."
                )

        elif strategy == 'base_age_curve':
            base_contrib = result.get('config', {}).get('base_contribution', 0)
            parts.append(
                f"Starting at ${base_contrib:,.0f} for age 21 and scaling with the ACA 3:1 curve mirrors marketplace premium increases."
            )
            parts.append(
                f"This covers ~{avg_lcsp_coverage:.0f}% of LCSP for your {employee_count} employees (avg age {self.context.avg_age:.0f})."
            )

        elif strategy == 'percentage_lcsp':
            pct = result.get('config', {}).get('lcsp_percentage', 100)
            parts.append(
                f"Covering {pct:.0f}% of each employee's LCSP ensures everyone can afford the most affordable Silver plan."
            )
            if self.context.is_multi_state:
                parts.append(
                    f"This automatically adjusts for premium differences across your {len(self.context.states)} states."
                )

        # Add vs current spend if available
        if self.context.has_current_er_spend and self.context.total_current_er_monthly:
            delta = total_monthly - self.context.total_current_er_monthly
            if delta < 0:
                parts.append(f"This saves ${abs(delta):,.0f}/month vs. your current spend.")
            elif delta > 0:
                parts.append(f"This is ${delta:,.0f}/month more than current, but ensures comprehensive coverage.")

        return " ".join(parts)

    def _build_subsidy_explanation(
        self,
        strategy: str,
        result: Dict[str, Any],
        eligible_count: int,
        total: int
    ) -> str:
        """Build explanation for Subsidy-optimized mode recommendation."""
        pct = (eligible_count / total * 100) if total > 0 else 0

        parts = []
        parts.append(
            f"This strategy makes ICHRA unaffordable for {eligible_count} of {total} employees ({pct:.0f}%), "
            f"allowing them to access ACA marketplace subsidies."
        )

        if eligible_count > 0:
            parts.append("Employees who decline ICHRA can often get significant federal subsidies based on their income.")

        if not self.context.has_income_data:
            parts.append("Note: Income data would help identify exactly which employees qualify for subsidies.")

        return " ".join(parts)

    def _build_ale_explanation(
        self,
        safe_harbor: SafeHarborType,
        result: Dict[str, Any],
        harbor_comparison: Dict[str, Dict],
        has_income: bool
    ) -> str:
        """Build explanation for ALE mode recommendation."""
        parts = []

        affordability = result.get('affordability', {})
        affordable_pct = affordability.get('affordable_pct', 0)

        if safe_harbor == SafeHarborType.RATE_OF_PAY:
            parts.append("Using Rate of Pay safe harbor based on your income data.")
            fpl_cost = harbor_comparison.get('fpl', {}).get('min_cost', 0)
            rop_cost = harbor_comparison.get('rate_of_pay', {}).get('min_cost', 0)
            if fpl_cost and rop_cost and rop_cost < fpl_cost:
                savings = fpl_cost - rop_cost
                parts.append(f"This saves ${savings:,.0f}/month compared to FPL safe harbor.")
        else:
            parts.append("Using FPL safe harbor, which guarantees affordability without requiring income data.")
            if has_income:
                rop_cost = harbor_comparison.get('rate_of_pay', {}).get('min_cost', 0)
                fpl_cost = harbor_comparison.get('fpl', {}).get('min_cost', 0)
                if rop_cost and fpl_cost and rop_cost < fpl_cost:
                    savings = fpl_cost - rop_cost
                    parts.append(f"With your income data, Rate of Pay could save ${savings:,.0f}/month.")

        if affordable_pct >= 100:
            parts.append("All employees meet the IRS affordability test.")
        else:
            unaffordable = affordability.get('unaffordable_employees', [])
            parts.append(f"{len(unaffordable)} employees need additional contributions for affordability.")

        return " ".join(parts)

    def _default_recommendation(self) -> StrategyRecommendation:
        """Return a default recommendation when calculation fails."""
        return StrategyRecommendation(
            strategy_type='base_age_curve',
            base_age=21,
            base_contribution=400,
            explanation="Default recommendation: Age + 3:1 Curve starting at $400/month for age 21. Adjust based on your budget and workforce needs.",
            contribution_basis="Default starting point",
            total_monthly=0,
            total_annual=0,
        )
