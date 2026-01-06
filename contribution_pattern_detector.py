"""
Contribution Pattern Detector

Detects whether employer uses percentage-based or flat-rate contributions
per Family Status tier (EE, ES, EC, F) from census data.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime
import pandas as pd
import numpy as np

from constants import PATTERN_VARIANCE_THRESHOLD, PATTERN_MIN_SAMPLE_SIZE


# Tier display labels
TIER_LABELS = {
    'EE': 'Employee Only',
    'ES': 'Employee + Spouse',
    'EC': 'Employee + Children',
    'F': 'Family'
}


@dataclass
class TierContributionPattern:
    """Detected contribution pattern for a single family status tier."""
    tier: str  # 'EE', 'ES', 'EC', 'F'
    pattern_type: str  # 'percentage', 'flat_rate', 'uncertain', 'unknown'

    # For percentage pattern
    er_percentage: float = 0.0  # e.g., 0.70 = 70%
    er_percentage_variance: float = 0.0  # Coefficient of variation

    # For flat-rate pattern
    flat_amount: float = 0.0  # Fixed $ amount
    flat_amount_variance: float = 0.0  # Standard deviation

    # Confidence metrics
    sample_size: int = 0
    confidence: str = 'high'  # 'high', 'medium', 'low'
    needs_review: bool = False  # Flag for user confirmation
    review_reason: str = ''  # Explanation if needs_review=True

    @property
    def tier_label(self) -> str:
        """Get display label for tier."""
        return TIER_LABELS.get(self.tier, self.tier)


@dataclass
class ContributionPatternResult:
    """Complete detected contribution pattern across all tiers."""
    patterns: Dict[str, TierContributionPattern] = field(default_factory=dict)
    overall_pattern_type: str = 'unknown'  # 'percentage', 'flat_rate', 'mixed', 'unknown'
    detection_timestamp: str = ''
    has_sufficient_data: bool = False
    warnings: List[str] = field(default_factory=list)

    def get_pattern(self, tier: str) -> Optional[TierContributionPattern]:
        """Get pattern for a specific tier."""
        return self.patterns.get(tier)

    def needs_any_review(self) -> bool:
        """Check if any tier needs user review."""
        return any(p.needs_review for p in self.patterns.values())

    def get_tiers_needing_review(self) -> List[TierContributionPattern]:
        """Get list of tiers that need user review."""
        return [p for p in self.patterns.values() if p.needs_review]


def detect_contribution_pattern(
    census_df: pd.DataFrame,
    variance_threshold: float = None,
    min_sample_size: int = None
) -> ContributionPatternResult:
    """
    Detect whether employer uses percentage-based or flat-rate contributions per tier.

    Algorithm:
    1. Group employees by family_status (EE, ES, EC, F)
    2. For each tier with >= min_sample_size employees:
       a. Calculate ER% for each employee: er_monthly / (er_monthly + ee_monthly)
       b. Calculate variance metrics:
          - ER% coefficient of variation (CV) = std_dev / mean
          - ER$ standard deviation
       c. Determine pattern:
          - If ER% CV < variance_threshold: percentage-based pattern
          - If ER$ std_dev is low BUT ER% CV is high: flat-rate pattern
          - Otherwise: flag for review
    3. For tiers with < min_sample_size: flag as insufficient data

    Args:
        census_df: Census DataFrame with current_ee_monthly, current_er_monthly, family_status
        variance_threshold: Maximum CV to consider "consistent" (default from constants)
        min_sample_size: Minimum employees per tier for reliable detection (default from constants)

    Returns:
        ContributionPatternResult with detected patterns per tier
    """
    # Use defaults from constants if not provided
    if variance_threshold is None:
        variance_threshold = PATTERN_VARIANCE_THRESHOLD
    if min_sample_size is None:
        min_sample_size = PATTERN_MIN_SAMPLE_SIZE

    patterns = {}
    warnings = []

    # Check if required columns exist
    required_cols = ['current_ee_monthly', 'current_er_monthly', 'family_status']
    missing_cols = [col for col in required_cols if col not in census_df.columns]

    if missing_cols:
        return ContributionPatternResult(
            patterns={},
            overall_pattern_type='unknown',
            detection_timestamp=datetime.now().isoformat(),
            has_sufficient_data=False,
            warnings=[f"Missing required columns: {', '.join(missing_cols)}"]
        )

    # Process each tier
    for tier in ['EE', 'ES', 'EC', 'F']:
        tier_df = census_df[census_df['family_status'] == tier].copy()

        # Filter to rows with valid contribution data
        tier_df = tier_df[
            tier_df['current_er_monthly'].notna() &
            tier_df['current_ee_monthly'].notna() &
            (pd.to_numeric(tier_df['current_er_monthly'], errors='coerce') > 0)
        ]

        # Convert to numeric
        tier_df['current_er_monthly'] = pd.to_numeric(tier_df['current_er_monthly'], errors='coerce')
        tier_df['current_ee_monthly'] = pd.to_numeric(tier_df['current_ee_monthly'], errors='coerce')

        sample_size = len(tier_df)

        if sample_size == 0:
            # No data for this tier
            patterns[tier] = TierContributionPattern(
                tier=tier,
                pattern_type='unknown',
                sample_size=0,
                confidence='low',
                needs_review=False,
                review_reason='No employees in this tier'
            )
            continue

        if sample_size < min_sample_size:
            # Insufficient data - calculate what we can but flag for review
            total_premiums = tier_df['current_ee_monthly'] + tier_df['current_er_monthly']
            er_percentages = tier_df['current_er_monthly'] / total_premiums
            er_pct_mean = er_percentages.mean() if len(er_percentages) > 0 else 0
            er_amt_mean = tier_df['current_er_monthly'].mean()

            patterns[tier] = TierContributionPattern(
                tier=tier,
                pattern_type='uncertain',
                er_percentage=er_pct_mean,
                flat_amount=er_amt_mean,
                sample_size=sample_size,
                confidence='low',
                needs_review=True,
                review_reason=f'Only {sample_size} employee(s) in tier (minimum: {min_sample_size})'
            )
            warnings.append(f'{TIER_LABELS[tier]}: Insufficient sample size ({sample_size})')
            continue

        # Calculate metrics
        total_premiums = tier_df['current_ee_monthly'] + tier_df['current_er_monthly']
        er_percentages = tier_df['current_er_monthly'] / total_premiums
        er_amounts = tier_df['current_er_monthly']

        er_pct_mean = er_percentages.mean()
        er_pct_std = er_percentages.std()
        er_pct_cv = er_pct_std / er_pct_mean if er_pct_mean > 0 else float('inf')

        er_amt_mean = er_amounts.mean()
        er_amt_std = er_amounts.std()
        er_amt_cv = er_amt_std / er_amt_mean if er_amt_mean > 0 else float('inf')

        # Determine pattern type
        if er_pct_cv < variance_threshold:
            # Low variance in percentage - percentage-based pattern
            confidence = 'high' if er_pct_cv < variance_threshold / 2 else 'medium'
            patterns[tier] = TierContributionPattern(
                tier=tier,
                pattern_type='percentage',
                er_percentage=er_pct_mean,
                er_percentage_variance=er_pct_cv,
                flat_amount=er_amt_mean,
                flat_amount_variance=er_amt_std,
                sample_size=sample_size,
                confidence=confidence,
                needs_review=False
            )
        elif er_amt_cv < variance_threshold:
            # Low variance in dollar amount but high in percentage - flat-rate
            confidence = 'high' if er_amt_cv < variance_threshold / 2 else 'medium'
            patterns[tier] = TierContributionPattern(
                tier=tier,
                pattern_type='flat_rate',
                er_percentage=er_pct_mean,
                er_percentage_variance=er_pct_cv,
                flat_amount=er_amt_mean,
                flat_amount_variance=er_amt_std,
                sample_size=sample_size,
                confidence=confidence,
                needs_review=False
            )
        else:
            # High variance in both - needs review
            patterns[tier] = TierContributionPattern(
                tier=tier,
                pattern_type='uncertain',
                er_percentage=er_pct_mean,
                er_percentage_variance=er_pct_cv,
                flat_amount=er_amt_mean,
                flat_amount_variance=er_amt_std,
                sample_size=sample_size,
                confidence='low',
                needs_review=True,
                review_reason=f'High variance: ER% CV={er_pct_cv:.1%}, ER$ std=${er_amt_std:.0f}'
            )
            warnings.append(f'{TIER_LABELS[tier]}: Pattern unclear, recommend manual review')

    # Determine overall pattern
    pattern_types = [p.pattern_type for p in patterns.values()
                     if p.pattern_type not in ('unknown', 'uncertain')]

    if len(pattern_types) == 0:
        overall = 'unknown'
    elif len(set(pattern_types)) == 1:
        overall = pattern_types[0]
    else:
        overall = 'mixed'

    # Check if we have sufficient data overall
    has_data = any(p.sample_size >= min_sample_size for p in patterns.values())

    return ContributionPatternResult(
        patterns=patterns,
        overall_pattern_type=overall,
        detection_timestamp=datetime.now().isoformat(),
        has_sufficient_data=has_data,
        warnings=warnings
    )


def apply_pattern_to_renewal(
    census_df: pd.DataFrame,
    pattern_result: ContributionPatternResult,
    fallback_er_pct: float = 0.60
) -> pd.DataFrame:
    """
    Apply detected contribution pattern to calculate 2026 renewal ER/EE projections.

    For each employee:
    1. Get their projected_2026_premium (total renewal)
    2. Look up their tier's detected pattern
    3. Apply pattern to calculate projected_2026_er and projected_2026_ee

    Args:
        census_df: Census DataFrame with projected_2026_premium and family_status
        pattern_result: Detected contribution pattern from detect_contribution_pattern()
        fallback_er_pct: Default ER% to use if pattern is unknown (default 60%)

    Returns:
        Census DataFrame with new columns:
        - projected_2026_er: Employer's projected 2026 contribution
        - projected_2026_ee: Employee's projected 2026 contribution
    """
    result_df = census_df.copy()
    result_df['projected_2026_er'] = 0.0
    result_df['projected_2026_ee'] = 0.0

    # Check if renewal premium column exists
    renewal_col = None
    for col in ['projected_2026_premium', '2026 Premium', '2026_premium']:
        if col in result_df.columns:
            renewal_col = col
            break

    if renewal_col is None:
        # No renewal data - return unchanged
        return result_df

    for idx, row in result_df.iterrows():
        renewal_premium = pd.to_numeric(row.get(renewal_col, 0), errors='coerce') or 0

        if renewal_premium <= 0:
            continue

        tier = row.get('family_status', 'EE')
        pattern = pattern_result.get_pattern(tier)

        if pattern is None or pattern.pattern_type in ('unknown',):
            # Fallback: use default ER%
            er_amount = renewal_premium * fallback_er_pct
            ee_amount = renewal_premium - er_amount
        elif pattern.pattern_type == 'percentage':
            er_pct = pattern.er_percentage if pattern.er_percentage > 0 else fallback_er_pct
            er_amount = renewal_premium * er_pct
            ee_amount = renewal_premium - er_amount
        elif pattern.pattern_type == 'flat_rate':
            # Flat rate: ER pays fixed amount, EE pays remainder
            er_amount = min(pattern.flat_amount, renewal_premium)  # Can't exceed total
            ee_amount = renewal_premium - er_amount
        else:  # 'uncertain' or other
            # Use percentage as fallback for uncertain patterns
            er_pct = pattern.er_percentage if pattern.er_percentage > 0 else fallback_er_pct
            er_amount = renewal_premium * er_pct
            ee_amount = renewal_premium - er_amount

        result_df.at[idx, 'projected_2026_er'] = round(er_amount, 2)
        result_df.at[idx, 'projected_2026_ee'] = round(ee_amount, 2)

    return result_df


def get_pattern_summary(pattern_result: ContributionPatternResult) -> Dict:
    """
    Get a summary of detected patterns for display.

    Returns dict with:
    - overall_type: 'percentage', 'flat_rate', 'mixed', 'unknown'
    - tiers: list of tier summaries
    - needs_review: bool
    - warnings: list of warning messages
    """
    tier_summaries = []

    for tier_code in ['EE', 'ES', 'EC', 'F']:
        pattern = pattern_result.get_pattern(tier_code)
        if pattern:
            tier_summaries.append({
                'tier': tier_code,
                'label': pattern.tier_label,
                'pattern_type': pattern.pattern_type,
                'er_percentage': pattern.er_percentage,
                'er_percentage_display': f"{pattern.er_percentage * 100:.1f}%",
                'flat_amount': pattern.flat_amount,
                'flat_amount_display': f"${pattern.flat_amount:,.0f}",
                'sample_size': pattern.sample_size,
                'confidence': pattern.confidence,
                'needs_review': pattern.needs_review,
                'review_reason': pattern.review_reason
            })

    return {
        'overall_type': pattern_result.overall_pattern_type,
        'tiers': tier_summaries,
        'needs_review': pattern_result.needs_any_review(),
        'tiers_needing_review': [t['tier'] for t in tier_summaries if t['needs_review']],
        'warnings': pattern_result.warnings,
        'has_sufficient_data': pattern_result.has_sufficient_data
    }
