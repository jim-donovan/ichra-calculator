"""
Plan Comparison Types
Dataclasses for the Plan Comparison feature (Page 9)
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, List


@dataclass
class CurrentEmployerPlan:
    """
    Represents the employer's current group health plan.
    Used as the baseline for comparing against marketplace alternatives.
    """
    # Plan Overview
    plan_name: str = ""
    carrier: Optional[str] = None
    plan_type: str = "PPO"  # HMO, PPO, EPO, POS
    metal_tier: Optional[str] = None  # Bronze, Silver, Gold, Platinum, or None for group plans
    hsa_eligible: bool = False

    # Monthly Premiums (EE-only, total cost)
    current_premium: Optional[float] = None  # Current EE-only monthly premium
    renewal_premium: Optional[float] = None  # Renewal EE-only monthly premium

    # Deductibles
    individual_deductible: float = 0.0
    family_deductible: Optional[float] = None

    # Out-of-Pocket Maximum
    individual_oop_max: float = 0.0
    family_oop_max: Optional[float] = None

    # Coinsurance (employee pays X% after deductible)
    coinsurance_pct: int = 20

    # Copays - None means "Deductible + Coinsurance" applies instead of flat copay
    pcp_copay: Optional[float] = 25.0
    specialist_copay: Optional[float] = 50.0
    er_copay: Optional[float] = None  # Often Ded + Coinsurance
    urgent_care_copay: Optional[float] = None
    generic_rx_copay: Optional[float] = 10.0
    preferred_rx_copay: Optional[float] = None
    specialty_rx_copay: Optional[float] = None

    def format_copay(self, value: Optional[float]) -> str:
        """Format copay for display. None = Deductible + Coinsurance."""
        if value is None:
            return f"Ded + {self.coinsurance_pct}%"
        elif value == 0:
            return "No charge"
        else:
            return f"${value:,.0f}"

    def is_complete(self) -> bool:
        """Check if required fields are filled in."""
        return bool(
            self.plan_name and
            self.plan_type and
            self.individual_deductible >= 0 and
            self.individual_oop_max >= 0
        )


@dataclass
class MarketplacePlanDetails:
    """
    Enriched marketplace plan data for comparison.
    Includes deductibles, copays, and match score.
    """
    hios_plan_id: str
    plan_name: str
    issuer_name: Optional[str] = None
    metal_level: str = ""
    plan_type: str = ""
    hsa_eligible: bool = False

    # Deductibles
    individual_deductible: float = 0.0
    family_deductible: Optional[float] = None

    # Out-of-Pocket Maximum
    individual_oop_max: float = 0.0
    family_oop_max: Optional[float] = None

    # Coinsurance
    coinsurance_pct: Optional[int] = None

    # Copays (None means coinsurance applies)
    pcp_copay: Optional[float] = None
    specialist_copay: Optional[float] = None
    er_copay: Optional[float] = None
    urgent_care_copay: Optional[float] = None
    generic_rx_copay: Optional[float] = None
    preferred_rx_copay: Optional[float] = None
    specialty_rx_copay: Optional[float] = None

    # Copay descriptions (for display when coinsurance instead of copay)
    pcp_copay_desc: Optional[str] = None
    specialist_copay_desc: Optional[str] = None
    er_copay_desc: Optional[str] = None
    generic_rx_copay_desc: Optional[str] = None

    # Monthly premium for age 21 (base rate)
    age_21_premium: Optional[float] = None

    # Actuarial value (percentage, e.g., 70 for 70%)
    actuarial_value: Optional[float] = None

    # Calculated match score (0-100)
    match_score: float = 0.0

    def format_copay(self, value: Optional[float], coinsurance: Optional[int] = None) -> str:
        """Format copay for display. None = Deductible + Coinsurance."""
        if value is None:
            pct = coinsurance if coinsurance else (self.coinsurance_pct or 20)
            return f"Ded + {pct}%"
        elif value == 0:
            return "No charge"
        else:
            return f"${value:,.0f}"


@dataclass
class ComparisonLocation:
    """Location context for marketplace plan filtering."""
    zip_code: str = ""
    state: str = ""
    county: str = ""
    rating_area_id: Optional[int] = None
    source: str = "manual"  # 'manual' or 'census_employee_{id}'


@dataclass
class ComparisonFilters:
    """Filter settings for marketplace plan selection."""
    metal_levels: List[str] = field(default_factory=lambda: ["Bronze", "Silver", "Gold"])
    plan_types: List[str] = field(default_factory=lambda: ["HMO", "PPO", "EPO", "POS"])
    hsa_only: bool = False
    max_deductible: Optional[float] = None
    max_oop_max: Optional[float] = None


def calculate_match_score(current_plan: CurrentEmployerPlan,
                          marketplace_plan: MarketplacePlanDetails) -> float:
    """
    Calculate similarity score (0-100%) between plans.
    Higher = more similar to current plan.

    Weights:
    - Deductible: 25%
    - OOPM: 25%
    - Plan Type match: 15%
    - HSA match: 10%
    - Copays (PCP/Specialist/Rx): 25%
    """
    score = 100.0

    # Deductible comparison (weight: 25%)
    if current_plan.individual_deductible > 0:
        ded_diff_pct = abs(marketplace_plan.individual_deductible - current_plan.individual_deductible) / current_plan.individual_deductible
        score -= min(25, ded_diff_pct * 25)
    elif marketplace_plan.individual_deductible > 0:
        # Current has $0 deductible, marketplace doesn't
        score -= 15

    # OOPM comparison (weight: 25%)
    if current_plan.individual_oop_max > 0:
        oopm_diff_pct = abs(marketplace_plan.individual_oop_max - current_plan.individual_oop_max) / current_plan.individual_oop_max
        score -= min(25, oopm_diff_pct * 25)
    elif marketplace_plan.individual_oop_max > 0:
        score -= 15

    # Plan type match (weight: 15%)
    if marketplace_plan.plan_type != current_plan.plan_type:
        # Similar types get partial credit
        similar_types = {
            ('PPO', 'POS'): 5,
            ('POS', 'PPO'): 5,
            ('HMO', 'EPO'): 10,
            ('EPO', 'HMO'): 10,
        }
        penalty = similar_types.get((current_plan.plan_type, marketplace_plan.plan_type), 15)
        score -= penalty

    # HSA eligibility match (weight: 10%)
    if marketplace_plan.hsa_eligible != current_plan.hsa_eligible:
        # Only penalize if current has HSA and marketplace doesn't
        if current_plan.hsa_eligible and not marketplace_plan.hsa_eligible:
            score -= 10

    # Copay comparison (weight: 25% split across PCP, Specialist, Generic Rx)
    copay_pairs = [
        (current_plan.pcp_copay, marketplace_plan.pcp_copay, 8.33),
        (current_plan.specialist_copay, marketplace_plan.specialist_copay, 8.33),
        (current_plan.generic_rx_copay, marketplace_plan.generic_rx_copay, 8.34),
    ]

    for current_copay, marketplace_copay, weight in copay_pairs:
        if current_copay and current_copay > 0:
            if marketplace_copay is not None:
                copay_diff_pct = abs(marketplace_copay - current_copay) / current_copay
                score -= min(weight, copay_diff_pct * weight)
            else:
                # Marketplace uses coinsurance instead of copay
                score -= weight * 0.5  # Partial penalty for different structure

    return max(0, round(score, 1))


def compare_benefit(current_value: float, marketplace_value: float,
                    lower_is_better: bool = True) -> str:
    """
    Compare a single benefit value.

    Returns: 'better', 'similar', 'worse'

    - Equivalent (exactly equal) = 'better' (green)
    - Within 5% but not equal = 'similar' (yellow)
    - More than 5% different = 'better' or 'worse'
    """
    # Equivalent values are considered "better" (green)
    if current_value == marketplace_value:
        return 'better'

    if current_value == 0:
        # Current has $0, any non-zero marketplace is worse (for costs)
        return 'worse' if lower_is_better else 'better'

    # Calculate percentage difference
    diff_pct = (marketplace_value - current_value) / current_value * 100

    # Within 5% (but not equal) = similar
    if abs(diff_pct) <= 5:
        return 'similar'

    if lower_is_better:
        return 'better' if diff_pct < 0 else 'worse'
    else:
        return 'better' if diff_pct > 0 else 'worse'


def get_comparison_indicator(comparison_result: str) -> str:
    """Get visual indicator for comparison result."""
    indicators = {
        'better': '🟢',
        'similar': '🟡',
        'worse': '🔴',
    }
    return indicators.get(comparison_result, '')


if __name__ == "__main__":
    # Test the dataclasses
    current = CurrentEmployerPlan(
        plan_name="Acme Corp Gold PPO",
        carrier="Blue Cross Blue Shield",
        plan_type="PPO",
        hsa_eligible=False,
        individual_deductible=1500,
        family_deductible=3000,
        individual_oop_max=6000,
        family_oop_max=12000,
        coinsurance_pct=20,
        pcp_copay=25,
        specialist_copay=50,
        er_copay=250,
        generic_rx_copay=10,
    )

    marketplace = MarketplacePlanDetails(
        hios_plan_id="12345MO0010001",
        plan_name="Blue Shield Silver PPO",
        metal_level="Silver",
        plan_type="PPO",
        hsa_eligible=False,
        individual_deductible=1200,
        family_deductible=2400,
        individual_oop_max=5500,
        family_oop_max=11000,
        pcp_copay=30,
        specialist_copay=60,
        generic_rx_copay=15,
    )

    score = calculate_match_score(current, marketplace)
    print(f"Match Score: {score}%")

    ded_comparison = compare_benefit(
        current.individual_deductible,
        marketplace.individual_deductible,
        lower_is_better=True
    )
    print(f"Deductible comparison: {get_comparison_indicator(ded_comparison)} {ded_comparison}")

    print("\n✓ Plan comparison types loaded successfully!")
