#!/usr/bin/env python3
"""
One-time script to analyze contribution patterns from a census file.
Outputs CSV with per-employee and per-tier breakdown.

Usage: python analyze_contribution_pattern.py
(Reads census from session state or prompts for file)
"""

import pandas as pd
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from contribution_pattern_detector import (
    detect_contribution_pattern,
    apply_pattern_to_renewal,
    get_pattern_summary,
    TIER_LABELS
)


def analyze_census_file(csv_path: str) -> None:
    """Analyze a census CSV and output contribution pattern breakdown."""

    # Read census
    df = pd.read_csv(csv_path)
    print(f"\n{'='*60}")
    print(f"Analyzing: {csv_path}")
    print(f"Total employees: {len(df)}")
    print(f"{'='*60}\n")

    # Normalize column names (handle various formats)
    col_mapping = {
        'Current EE Monthly': 'current_ee_monthly',
        'Current ER Monthly': 'current_er_monthly',
        'Family Status': 'family_status',
        '2026 Premium': 'projected_2026_premium',
        'Projected 2026 Premium': 'projected_2026_premium',
    }

    for old_col, new_col in col_mapping.items():
        if old_col in df.columns and new_col not in df.columns:
            df[new_col] = df[old_col]

    # Check required columns
    required = ['current_ee_monthly', 'current_er_monthly', 'family_status']
    missing = [c for c in required if c not in df.columns]
    if missing:
        print(f"ERROR: Missing required columns: {missing}")
        print(f"Available columns: {list(df.columns)}")
        return

    # Parse currency columns
    for col in ['current_ee_monthly', 'current_er_monthly', 'projected_2026_premium']:
        if col in df.columns:
            df[col] = df[col].replace(r'[\$,]', '', regex=True)
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # Calculate per-employee metrics
    df['total_premium'] = df['current_ee_monthly'].fillna(0) + df['current_er_monthly'].fillna(0)
    df['er_pct'] = df['current_er_monthly'] / df['total_premium']
    df['er_pct'] = df['er_pct'].fillna(0)

    # Detect pattern
    pattern_result = detect_contribution_pattern(df)
    summary = get_pattern_summary(pattern_result)

    # Print pattern summary
    print("DETECTED CONTRIBUTION PATTERN")
    print("-" * 40)
    print(f"Overall pattern type: {summary['overall_type']}")
    print(f"Has sufficient data: {summary['has_sufficient_data']}")
    print(f"Needs review: {summary['needs_review']}")
    print()

    # Per-tier breakdown
    print("PER-TIER BREAKDOWN")
    print("-" * 40)
    tier_rows = []
    for tier_code in ['EE', 'ES', 'EC', 'F']:
        tier_info = next((t for t in summary['tiers'] if t['tier'] == tier_code), None)
        if not tier_info:
            continue

        # Get tier-specific data from original df
        tier_df_subset = df[df['family_status'] == tier_code].copy()

        print(f"\n{tier_info['label']} ({tier_code}):")
        print(f"  Pattern: {tier_info['pattern_type']}")
        print(f"  ER%: {tier_info['er_percentage_display']}")
        print(f"  Flat $: {tier_info['flat_amount_display']}")
        print(f"  Sample size: {tier_info['sample_size']}")
        print(f"  Confidence: {tier_info['confidence']}")
        print(f"  Needs review: {tier_info['needs_review']}")
        if tier_info['review_reason']:
            print(f"  Review reason: {tier_info['review_reason']}")

        # Calculate detailed metrics for CSV
        row = {
            'tier': tier_code,
            'tier_label': tier_info['label'],
            'sample_size': tier_info['sample_size'],
            'pattern_type': tier_info['pattern_type'],
            'confidence': tier_info['confidence'],
            'needs_review': tier_info['needs_review'],
            'review_reason': tier_info['review_reason'] or '',

            # Percentage pattern details
            'detected_er_pct': tier_info['er_percentage'],
            'er_pct_min': tier_df_subset['er_pct'].min() if len(tier_df_subset) > 0 else None,
            'er_pct_max': tier_df_subset['er_pct'].max() if len(tier_df_subset) > 0 else None,
            'er_pct_std': tier_df_subset['er_pct'].std() if len(tier_df_subset) > 1 else 0,

            # Flat amount details
            'detected_flat_amt': tier_info['flat_amount'],
            'er_amt_min': tier_df_subset['current_er_monthly'].min() if len(tier_df_subset) > 0 else None,
            'er_amt_max': tier_df_subset['current_er_monthly'].max() if len(tier_df_subset) > 0 else None,
            'er_amt_std': tier_df_subset['current_er_monthly'].std() if len(tier_df_subset) > 1 else 0,

            # Current totals
            'current_ee_total': tier_df_subset['current_ee_monthly'].sum(),
            'current_er_total': tier_df_subset['current_er_monthly'].sum(),
            'current_premium_total': tier_df_subset['total_premium'].sum(),

            # EE contribution details
            'ee_amt_min': tier_df_subset['current_ee_monthly'].min() if len(tier_df_subset) > 0 else None,
            'ee_amt_max': tier_df_subset['current_ee_monthly'].max() if len(tier_df_subset) > 0 else None,
            'ee_amt_avg': tier_df_subset['current_ee_monthly'].mean() if len(tier_df_subset) > 0 else None,
        }

        # Add 2026 projections if available
        if 'projected_2026_premium' in tier_df_subset.columns:
            row['projected_2026_premium_total'] = tier_df_subset['projected_2026_premium'].sum()

            # Get projected ER/EE from the pattern application
            df_with_proj = apply_pattern_to_renewal(tier_df_subset, pattern_result)
            row['projected_2026_er_total'] = df_with_proj['projected_2026_er'].sum()
            row['projected_2026_ee_total'] = df_with_proj['projected_2026_ee'].sum()

        tier_rows.append(row)

    # Save tier summary
    tier_output_df = pd.DataFrame(tier_rows)
    tier_output = csv_path.replace('.csv', '_tier_patterns.csv')
    tier_output_df.to_csv(tier_output, index=False)
    print(f"\n\nTier patterns saved to: {tier_output}")

    # Per-employee detail
    print("\n\nPER-EMPLOYEE DETAIL")
    print("-" * 40)

    # Start with identifying columns if available
    id_cols = []
    for col in ['Employee Number', 'Last Name', 'First Name']:
        if col in df.columns:
            id_cols.append(col)

    detail_cols = id_cols + [
        'family_status',
        'current_ee_monthly',
        'current_er_monthly',
        'total_premium',
        'er_pct'
    ]

    employee_detail = df[detail_cols].copy()

    if 'projected_2026_premium' in df.columns:
        employee_detail['projected_2026_premium'] = df['projected_2026_premium']

    # Add detected pattern info
    employee_detail['detected_pattern'] = employee_detail['family_status'].map(
        lambda x: pattern_result.patterns.get(x, None)
    ).apply(lambda p: p.pattern_type if p else 'unknown')

    employee_detail['detected_er_pct'] = employee_detail['family_status'].map(
        lambda x: pattern_result.patterns.get(x, None)
    ).apply(lambda p: p.er_percentage if p else 0)

    # Apply pattern to get projected 2026 ER/EE
    if 'projected_2026_premium' in df.columns:
        df_with_projections = apply_pattern_to_renewal(df, pattern_result)
        employee_detail['projected_2026_er'] = df_with_projections['projected_2026_er']
        employee_detail['projected_2026_ee'] = df_with_projections['projected_2026_ee']

    # Save employee detail
    detail_output = csv_path.replace('.csv', '_employee_detail.csv')
    employee_detail.to_csv(detail_output, index=False)
    print(f"Employee detail saved to: {detail_output}")

    # Print summary statistics
    print("\n\nSUMMARY STATISTICS")
    print("-" * 40)
    print(employee_detail.groupby('family_status').agg({
        'current_ee_monthly': ['count', 'sum', 'mean'],
        'current_er_monthly': ['sum', 'mean'],
        'er_pct': ['mean', 'std']
    }).round(2))

    if summary['warnings']:
        print("\n\nWARNINGS")
        print("-" * 40)
        for w in summary['warnings']:
            print(f"  - {w}")


if __name__ == '__main__':
    if len(sys.argv) > 1:
        csv_path = sys.argv[1]
    else:
        # Look for common census file locations
        possible_paths = [
            'test_census.csv',
            'census.csv',
            'sample_census.csv',
        ]
        csv_path = None
        for p in possible_paths:
            if Path(p).exists():
                csv_path = p
                break

        if not csv_path:
            print("Usage: python analyze_contribution_pattern.py <census.csv>")
            print("\nNo census file found. Please provide a path.")
            sys.exit(1)

    analyze_census_file(csv_path)
