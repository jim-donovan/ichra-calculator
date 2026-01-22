"""
Contribution Evaluation Module

Refactored modular implementation of the Contribution Evaluation page (Page 3).
Replaces the monolithic page with focused components and services.

Three Operating Modes:
- Non-ALE Standard: <46 employees, standard ICHRA goal
- Non-ALE Subsidy: <46 employees, subsidy-optimized goal
- ALE: ≥46 employees, affordability focus

See the PRD at /docs/Glove_contribution_modeling_PRD.pdf for detailed requirements.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

# ALE threshold: 50 full-time equivalent employees, but we use 46 as buffer
ALE_THRESHOLD = 46


class OperatingMode(Enum):
    """
    Operating modes for contribution evaluation.

    The mode determines:
    - Which strategies are available
    - Which metrics are displayed
    - Whether affordability is the primary concern (ALE) or optional (Non-ALE)
    """
    NON_ALE_STANDARD = "non_ale_standard"     # <46 employees, standard goal
    NON_ALE_SUBSIDY = "non_ale_subsidy"       # <46 employees, subsidy-optimized
    ALE = "ale"                                # ≥46 employees, affordability required


class GoalType(Enum):
    """
    ICHRA goal type selection (Non-ALE only).

    Standard: Minimize employer cost while providing competitive coverage
    Subsidy: Intentionally design for unaffordability so employees can access ACA subsidies
    """
    STANDARD = "standard"
    SUBSIDY_OPTIMIZED = "subsidy_optimized"


class SafeHarborType(Enum):
    """
    IRS Safe Harbor types for ALE affordability determination.

    RATE_OF_PAY: Uses actual employee wages (most accurate, requires income data)
    FPL: Uses Federal Poverty Level (no income data needed, but may be more expensive)
    W2_WAGES: Uses W-2 box 1 (retrospective, not recommended for planning)
    """
    RATE_OF_PAY = "rate_of_pay"
    FPL = "fpl"
    W2_WAGES = "w2_wages"


@dataclass
class CensusContext:
    """
    Census-derived context for contribution evaluation.

    Computed once when entering the page, used throughout for mode detection
    and strategy recommendations.
    """
    employee_count: int
    has_income_data: bool
    has_current_er_spend: bool

    # Demographics
    avg_age: float
    min_age: int
    max_age: int
    age_distribution: Dict[str, int]  # age_band -> count

    # Geography
    states: List[str]
    is_multi_state: bool

    # Family composition
    family_status_distribution: Dict[str, int]  # EE/ES/EC/F -> count

    # Financial (if available)
    total_current_er_monthly: Optional[float] = None
    avg_income: Optional[float] = None

    @property
    def is_ale(self) -> bool:
        """Applicable Large Employer (50+ FTEs, using 46 as buffer)"""
        return self.employee_count >= ALE_THRESHOLD

    def get_operating_mode(self, goal: GoalType = GoalType.STANDARD) -> OperatingMode:
        """Determine operating mode based on employee count and goal selection."""
        if self.is_ale:
            return OperatingMode.ALE
        elif goal == GoalType.SUBSIDY_OPTIMIZED:
            return OperatingMode.NON_ALE_SUBSIDY
        else:
            return OperatingMode.NON_ALE_STANDARD


@dataclass
class StrategyRecommendation:
    """
    AI-generated strategy recommendation.

    Includes the recommended configuration plus explanation for display.
    """
    strategy_type: str
    base_age: int
    base_contribution: float
    safe_harbor: Optional[SafeHarborType] = None

    # For display
    explanation: str = ""
    contribution_basis: str = ""  # Explains how base_contribution was calculated

    # Cost metrics
    total_monthly: float = 0.0
    total_annual: float = 0.0

    # Mode-specific metrics
    affordable_count: Optional[int] = None
    affordable_pct: Optional[float] = None
    subsidy_eligible_count: Optional[int] = None
    vs_current_delta: Optional[float] = None

    @property
    def strategy_display_name(self) -> str:
        """Human-readable strategy name for UI display."""
        names = {
            'flat_amount': 'Flat Amount',
            'base_age_curve': 'ACA 3:1 Contribution Curve',
            'percentage_lcsp': '% of LCSP',
            'fpl_safe_harbor': 'FPL Safe Harbor',
            'rate_of_pay_safe_harbor': 'Rate of Pay Safe Harbor',
            'subsidy_optimized': 'Subsidy-Optimized',
        }
        return names.get(self.strategy_type, self.strategy_type)


# Strategy constraints by mode (from PRD)
# Note: Safe harbor strategies are mode-specific optimization targets
STRATEGY_CONSTRAINTS = {
    OperatingMode.NON_ALE_STANDARD: ['flat_amount', 'base_age_curve', 'percentage_lcsp'],
    OperatingMode.NON_ALE_SUBSIDY: [
        'subsidy_optimized',  # Max contribution that keeps ICHRA unaffordable (requires income)
        'flat_amount',
        'base_age_curve',
    ],  # No %LCSP (would make ICHRA affordable)
    OperatingMode.ALE: [
        'rate_of_pay_safe_harbor',  # Minimum cost (requires income data)
        'fpl_safe_harbor',          # Guaranteed affordable, no income needed
        'base_age_curve',           # Traditional age-scaled
        'percentage_lcsp',          # Percentage of LCSP
    ],
}


def get_available_strategies(mode: OperatingMode) -> List[str]:
    """Get list of strategy types available for the given mode."""
    return STRATEGY_CONSTRAINTS.get(mode, [])
