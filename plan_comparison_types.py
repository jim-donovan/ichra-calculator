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
    # Sentinel values: -1 = N/A, -2 = Not Covered
    # Default to None (unspecified) - user must enter values or import from SBC
    pcp_copay: Optional[float] = None
    specialist_copay: Optional[float] = None
    er_copay: Optional[float] = None
    generic_rx_copay: Optional[float] = None
    preferred_rx_copay: Optional[float] = None
    specialty_rx_copay: Optional[float] = None

    # Per-service coinsurance overrides (None = use default coinsurance_pct)
    pcp_coinsurance: Optional[int] = None
    specialist_coinsurance: Optional[int] = None
    er_coinsurance: Optional[int] = None
    generic_rx_coinsurance: Optional[int] = None
    preferred_rx_coinsurance: Optional[int] = None
    specialty_rx_coinsurance: Optional[int] = None

    # Per-service "after deductible" flags (True = coinsurance applies after deductible is met)
    pcp_after_deductible: bool = False
    specialist_after_deductible: bool = False
    er_after_deductible: bool = False
    generic_rx_after_deductible: bool = False
    preferred_rx_after_deductible: bool = False
    specialty_rx_after_deductible: bool = False

    def get_service_coinsurance(self, service: str) -> int:
        """Get the coinsurance % for a specific service, falling back to default."""
        override_map = {
            'pcp': self.pcp_coinsurance,
            'specialist': self.specialist_coinsurance,
            'er': self.er_coinsurance,
            'generic_rx': self.generic_rx_coinsurance,
            'preferred_rx': self.preferred_rx_coinsurance,
            'specialty_rx': self.specialty_rx_coinsurance,
        }
        override = override_map.get(service)
        if override is not None:
            return override
        # Fallback to default coinsurance_pct, or 20% if not set
        return self.coinsurance_pct if self.coinsurance_pct is not None else 20

    def format_copay(self, value: Optional[float], service: Optional[str] = None) -> str:
        """Format copay for display.

        Args:
            value: Copay value (None = Ded+Coinsurance, -1 = N/A, -2 = Not Covered)
            service: Optional service name for per-service coinsurance lookup

        Returns:
            Formatted string. Supports combined "$X + Y%" when copay AND coinsurance are both set.
        """
        if value is None:
            coins = self.get_service_coinsurance(service) if service else (self.coinsurance_pct or 20)

            # Check if "after deductible" flag is set for this service
            after_ded_map = {
                'pcp': self.pcp_after_deductible,
                'specialist': self.specialist_after_deductible,
                'er': self.er_after_deductible,
                'generic_rx': self.generic_rx_after_deductible,
                'preferred_rx': self.preferred_rx_after_deductible,
                'specialty_rx': self.specialty_rx_after_deductible,
            }
            after_ded = after_ded_map.get(service, False) if service else False

            if after_ded:
                return f"{coins}% after deductible"
            else:
                return f"{coins}%"
        elif value == -1:
            return "N/A"
        elif value == -2:
            return "Not Covered"
        elif value == 0:
            return "No charge"
        else:
            # Check if this service has explicit coinsurance set (combined copay + coinsurance)
            if service:
                coinsurance_map = {
                    'pcp': self.pcp_coinsurance,
                    'specialist': self.specialist_coinsurance,
                    'er': self.er_coinsurance,
                    'generic_rx': self.generic_rx_coinsurance,
                    'preferred_rx': self.preferred_rx_coinsurance,
                    'specialty_rx': self.specialty_rx_coinsurance,
                }
                explicit_coinsurance = coinsurance_map.get(service)
                if explicit_coinsurance is not None and explicit_coinsurance > 0:
                    return f"${value:,.0f} + {explicit_coinsurance}%"
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
    metal_levels: List[str] = field(default_factory=lambda: ["Bronze", "Expanded Bronze", "Silver", "Gold", "Platinum", "Catastrophic"])
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


def is_plan_better(current_plan: CurrentEmployerPlan,
                   marketplace_plan: MarketplacePlanDetails) -> tuple:
    """
    Check if marketplace plan is objectively better than current.

    Returns:
        (is_better, green_count, red_count)
        - is_better: True if at least 1 green AND 0 reds
        - green_count: Number of "better" benefits
        - red_count: Number of "worse" benefits
    """
    comparisons = []

    # Compare deductibles (lower is better)
    comparisons.append(compare_benefit(
        current_plan.individual_deductible,
        marketplace_plan.individual_deductible,
        lower_is_better=True
    ))

    # Compare OOPM (lower is better)
    comparisons.append(compare_benefit(
        current_plan.individual_oop_max,
        marketplace_plan.individual_oop_max,
        lower_is_better=True
    ))

    # Compare copays (lower is better) - only if current has values
    copay_pairs = [
        (current_plan.pcp_copay, marketplace_plan.pcp_copay),
        (current_plan.specialist_copay, marketplace_plan.specialist_copay),
        (current_plan.generic_rx_copay, marketplace_plan.generic_rx_copay),
    ]
    for current_copay, mp_copay in copay_pairs:
        if current_copay is not None and current_copay > 0:
            if mp_copay is not None:
                comparisons.append(compare_benefit(current_copay, mp_copay, lower_is_better=True))

    green_count = sum(1 for c in comparisons if c == 'better')
    red_count = sum(1 for c in comparisons if c == 'worse')

    is_better = green_count >= 1 and red_count == 0

    return is_better, green_count, red_count


def calculate_enhanced_ranking_score(
    current_plan: CurrentEmployerPlan,
    marketplace_plan: MarketplacePlanDetails,
    match_score: float
) -> tuple:
    """
    Calculate enhanced ranking score that considers cost.

    Returns:
        (ranking_score, tier) where tier is 'premium', 'standard', or 'value'

    Ranking tiers:
    - Premium (300-400): Better benefits + within 10% of renewal cost
    - Standard (100-200): Good match score, may exceed cost threshold
    - Value (0-100): Lower match scores
    """
    renewal_premium = current_plan.renewal_premium
    age_21_premium = marketplace_plan.age_21_premium

    # Check if plan is objectively better
    is_better, green_count, red_count = is_plan_better(current_plan, marketplace_plan)

    # Check cost threshold (within 10% of renewal)
    cost_comparable = False
    is_cheaper = False
    if renewal_premium and renewal_premium > 0 and age_21_premium:
        cost_diff_pct = abs(age_21_premium - renewal_premium) / renewal_premium * 100
        cost_comparable = cost_diff_pct <= 10
        is_cheaper = age_21_premium < renewal_premium

    # Calculate final ranking score
    if is_better and cost_comparable:
        # PREMIUM TIER: Better benefits + comparable cost
        tier = 'premium'
        base_score = 300 + match_score

        # Extra bonus if cheaper
        if is_cheaper:
            savings_pct = (renewal_premium - age_21_premium) / renewal_premium * 100
            base_score += min(50, savings_pct * 5)
    elif is_better:
        # Better benefits but cost exceeds threshold
        tier = 'standard'
        base_score = 150 + match_score
    elif cost_comparable:
        # Comparable cost but not objectively "better"
        base_score = 100 + match_score
        tier = 'standard'
    else:
        # Neither better nor cost-comparable
        tier = 'value'
        base_score = match_score

    return base_score, tier


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
