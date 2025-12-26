"""
GLOVE ICHRA Fit Score Calculator

Calculates a 0-100 score across 6 categories to determine
how well-suited a company is for ICHRA adoption.

Categories:
1. Cost Advantage (25%) - Savings vs current/renewal costs
2. Market Readiness (20%) - Marketplace plan availability
3. Workforce Fit (20%) - Age distribution favorability
4. Geographic Complexity (15%) - Multi-state complexity (inverse)
5. Employee Experience (10%) - Transition ease based on family mix
6. Admin Readiness (10%) - Data quality and simplicity
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple, Optional
from database import DatabaseConnection
from queries import PlanQueries

# Category weights (must sum to 100)
FIT_SCORE_WEIGHTS = {
    'cost_advantage': 25,
    'market_readiness': 20,
    'workforce_fit': 20,
    'geographic_complexity': 15,
    'employee_experience': 10,
    'admin_readiness': 10,
}


class FitScoreCalculator:
    """Calculate GLOVE ICHRA Fit Score from census and analysis data"""

    def __init__(
        self,
        census_df: pd.DataFrame,
        dependents_df: Optional[pd.DataFrame] = None,
        financial_summary: Optional[Dict] = None,
        contribution_settings: Optional[Dict] = None,
        db: Optional[DatabaseConnection] = None
    ):
        """
        Initialize calculator with analysis data.

        Args:
            census_df: Employee census DataFrame
            dependents_df: Dependents DataFrame (optional)
            financial_summary: Financial summary from Page 2 (optional)
            contribution_settings: Contribution settings (optional)
            db: Database connection for plan queries (optional)
        """
        self.census_df = census_df
        self.dependents_df = dependents_df if dependents_df is not None else pd.DataFrame()
        self.financial_summary = financial_summary or {}
        self.contribution_settings = contribution_settings or {}
        self.db = db

    def calculate(self) -> Tuple[int, Dict[str, int]]:
        """
        Calculate overall Fit Score and category scores.

        Returns:
            Tuple of (overall_score, {category: score})
            Each category score is 0-100
            Overall score is weighted average
        """
        category_scores = {
            'cost_advantage': self._calculate_cost_advantage(),
            'market_readiness': self._calculate_market_readiness(),
            'workforce_fit': self._calculate_workforce_fit(),
            'geographic_complexity': self._calculate_geographic_complexity(),
            'employee_experience': self._calculate_employee_experience(),
            'admin_readiness': self._calculate_admin_readiness(),
        }

        # Calculate weighted average
        overall = sum(
            score * (FIT_SCORE_WEIGHTS[cat] / 100)
            for cat, score in category_scores.items()
        )

        return int(round(overall)), category_scores

    def _calculate_cost_advantage(self) -> int:
        """
        Score based on savings vs current/renewal costs.

        Logic:
        - Get current ER annual from census (if available)
        - Get ICHRA LCSP cost from financial_summary
        - Calculate % savings
        - Score: >20% savings = 100, 10-20% = 80, 5-10% = 60, 0-5% = 40, increase = 20
        """
        try:
            # Try to get current costs from census
            current_er_annual = 0
            if 'current_er_monthly' in self.census_df.columns:
                current_er_monthly = self.census_df['current_er_monthly'].sum()
                if pd.notna(current_er_monthly) and current_er_monthly > 0:
                    current_er_annual = current_er_monthly * 12

            # Get proposed ICHRA cost from financial summary
            proposed_annual = 0
            results = self.financial_summary.get('results', {})
            if results:
                proposed_annual = results.get('total_annual', 0)

            # If we don't have comparison data, return neutral score
            if current_er_annual == 0 or proposed_annual == 0:
                return 70  # Neutral-positive score when data unavailable

            # Calculate savings percentage
            savings_pct = (current_er_annual - proposed_annual) / current_er_annual * 100

            # Score based on savings
            if savings_pct >= 20:
                return 100
            elif savings_pct >= 15:
                return 90
            elif savings_pct >= 10:
                return 80
            elif savings_pct >= 5:
                return 70
            elif savings_pct >= 0:
                return 50
            elif savings_pct >= -5:
                return 40
            else:
                return 20  # Costs increase significantly

        except Exception:
            return 70  # Default neutral score on error

    def _calculate_market_readiness(self) -> int:
        """
        Score based on marketplace plan availability.

        Logic:
        - Query plan counts per state/rating area
        - More plans available = higher score
        - Score: All areas have 10+ plans = 100, 5-10 = 80, etc.
        """
        try:
            if self.db is None:
                return 75  # Default when no DB connection

            # Get unique state/rating area combinations
            if 'rating_area_id' not in self.census_df.columns:
                return 75

            locations = self.census_df[['state', 'rating_area_id']].drop_duplicates()

            if locations.empty:
                return 75

            plan_counts = []
            for _, loc in locations.iterrows():
                state = loc['state']
                rating_area = loc['rating_area_id']

                # Query plan count for this location
                try:
                    count = PlanQueries.get_plan_count_for_area(
                        self.db, state, f"Rating Area {rating_area}"
                    )
                    plan_counts.append(count)
                except Exception:
                    plan_counts.append(5)  # Default assumption

            if not plan_counts:
                return 75

            # Score based on minimum plan count across all areas
            min_plans = min(plan_counts)
            avg_plans = sum(plan_counts) / len(plan_counts)

            # Weight both min and average
            if min_plans >= 15 and avg_plans >= 20:
                return 100
            elif min_plans >= 10 and avg_plans >= 15:
                return 90
            elif min_plans >= 7 and avg_plans >= 10:
                return 80
            elif min_plans >= 5 and avg_plans >= 7:
                return 70
            elif min_plans >= 3:
                return 60
            else:
                return 40

        except Exception:
            return 75  # Default on error

    def _calculate_workforce_fit(self) -> int:
        """
        Score based on age distribution (younger = better for ICHRA savings).

        Logic:
        - Calculate % of employees under 45
        - Younger workforce benefits more from individual marketplace
        - Score: >65% under 45 = 100, 50-65% = 80, etc.
        """
        try:
            # Get age column
            age_col = 'age' if 'age' in self.census_df.columns else 'employee_age'
            if age_col not in self.census_df.columns:
                return 70

            ages = self.census_df[age_col].dropna()
            if ages.empty:
                return 70

            total = len(ages)
            under_45 = len(ages[ages < 45])
            under_35 = len(ages[ages < 35])
            over_55 = len(ages[ages >= 55])

            pct_under_45 = (under_45 / total) * 100
            pct_under_35 = (under_35 / total) * 100
            pct_over_55 = (over_55 / total) * 100

            # Younger workforces benefit more from ICHRA
            # Older workforces (55+) have higher individual premiums

            base_score = 50

            # Bonus for young workforce
            if pct_under_35 >= 40:
                base_score += 30
            elif pct_under_35 >= 25:
                base_score += 20
            elif pct_under_35 >= 15:
                base_score += 10

            if pct_under_45 >= 65:
                base_score += 20
            elif pct_under_45 >= 50:
                base_score += 10

            # Penalty for older workforce
            if pct_over_55 >= 30:
                base_score -= 20
            elif pct_over_55 >= 20:
                base_score -= 10

            return max(20, min(100, base_score))

        except Exception:
            return 70

    def _calculate_geographic_complexity(self) -> int:
        """
        Score based on geographic spread (simpler = better).

        Logic:
        - Fewer states = easier administration
        - Single state = 100, 2-3 = 90, 4-5 = 75, 6-10 = 60, 11+ = 40
        """
        try:
            if 'state' not in self.census_df.columns:
                return 80

            unique_states = self.census_df['state'].nunique()

            # Also consider rating areas if available
            unique_rating_areas = 1
            if 'rating_area_id' in self.census_df.columns:
                unique_rating_areas = self.census_df['rating_area_id'].nunique()

            # Score based on state count (primary factor)
            if unique_states == 1:
                state_score = 100
            elif unique_states <= 3:
                state_score = 90
            elif unique_states <= 5:
                state_score = 75
            elif unique_states <= 10:
                state_score = 60
            elif unique_states <= 20:
                state_score = 45
            else:
                state_score = 30

            # Minor adjustment for rating area complexity
            if unique_rating_areas > 10:
                state_score -= 10
            elif unique_rating_areas > 5:
                state_score -= 5

            return max(20, min(100, state_score))

        except Exception:
            return 75

    def _calculate_employee_experience(self) -> int:
        """
        Score based on expected employee transition experience.

        Logic:
        - More EE-only = easier transition (fewer dependents to enroll)
        - Younger workforce = more tech-savvy for marketplace navigation
        """
        try:
            # Family status distribution
            if 'family_status' not in self.census_df.columns:
                return 75

            family_counts = self.census_df['family_status'].value_counts()
            total = len(self.census_df)

            ee_only = family_counts.get('EE', 0)
            pct_ee_only = (ee_only / total) * 100 if total > 0 else 0

            # Higher EE-only percentage = easier transition
            if pct_ee_only >= 70:
                base_score = 90
            elif pct_ee_only >= 55:
                base_score = 80
            elif pct_ee_only >= 40:
                base_score = 70
            elif pct_ee_only >= 25:
                base_score = 60
            else:
                base_score = 50

            # Age factor (younger = more tech comfortable)
            age_col = 'age' if 'age' in self.census_df.columns else 'employee_age'
            if age_col in self.census_df.columns:
                avg_age = self.census_df[age_col].mean()
                if avg_age < 35:
                    base_score += 10
                elif avg_age < 40:
                    base_score += 5
                elif avg_age > 50:
                    base_score -= 5

            return max(30, min(100, base_score))

        except Exception:
            return 70

    def _calculate_admin_readiness(self) -> int:
        """
        Score based on data quality and administrative simplicity.

        Logic:
        - Census completeness (all required fields present)
        - Current contribution data availability (shows mature benefits admin)
        - Number of unique classes (fewer = simpler)
        """
        try:
            base_score = 60

            # Check census data quality
            required_cols = ['state', 'family_status']
            optional_useful_cols = ['current_er_monthly', 'current_ee_monthly', 'rating_area_id']

            # Points for required columns being present and complete
            for col in required_cols:
                if col in self.census_df.columns:
                    completeness = 1 - (self.census_df[col].isna().sum() / len(self.census_df))
                    if completeness >= 0.95:
                        base_score += 8
                    elif completeness >= 0.8:
                        base_score += 5

            # Points for having contribution data (shows benefits maturity)
            has_contribution_data = False
            for col in ['current_er_monthly', 'current_ee_monthly']:
                if col in self.census_df.columns:
                    non_null = self.census_df[col].notna().sum()
                    if non_null > 0:
                        has_contribution_data = True
                        completeness = non_null / len(self.census_df)
                        if completeness >= 0.9:
                            base_score += 10
                        elif completeness >= 0.5:
                            base_score += 5

            if has_contribution_data:
                base_score += 5  # Bonus for having any contribution data

            # Rating area resolution success
            if 'rating_area_id' in self.census_df.columns:
                resolved = self.census_df['rating_area_id'].notna().sum()
                resolution_rate = resolved / len(self.census_df)
                if resolution_rate >= 0.95:
                    base_score += 8
                elif resolution_rate >= 0.8:
                    base_score += 4

            return max(30, min(100, base_score))

        except Exception:
            return 60


def calculate_fit_score(
    census_df: pd.DataFrame,
    dependents_df: Optional[pd.DataFrame] = None,
    financial_summary: Optional[Dict] = None,
    contribution_settings: Optional[Dict] = None,
    db: Optional[DatabaseConnection] = None
) -> Tuple[int, Dict[str, int]]:
    """
    Convenience function to calculate GLOVE ICHRA Fit Score.

    Args:
        census_df: Employee census DataFrame
        dependents_df: Dependents DataFrame (optional)
        financial_summary: Financial summary data (optional)
        contribution_settings: Contribution settings (optional)
        db: Database connection (optional)

    Returns:
        Tuple of (overall_score, {category: score})
    """
    calculator = FitScoreCalculator(
        census_df=census_df,
        dependents_df=dependents_df,
        financial_summary=financial_summary,
        contribution_settings=contribution_settings,
        db=db
    )
    return calculator.calculate()


if __name__ == "__main__":
    # Test with sample data
    sample_census = pd.DataFrame({
        'employee_id': ['E001', 'E002', 'E003', 'E004', 'E005'],
        'age': [28, 35, 42, 55, 31],
        'state': ['IL', 'IL', 'IL', 'TX', 'IL'],
        'family_status': ['EE', 'ES', 'EE', 'F', 'EE'],
        'rating_area_id': [1, 1, 1, 1, 1],
        'current_er_monthly': [500, 750, 500, 900, 500],
    })

    score, categories = calculate_fit_score(sample_census)

    print("GLOVE ICHRA Fit Score Calculator - Test")
    print("=" * 50)
    print(f"\nOverall Score: {score}/100")
    print("\nCategory Breakdown:")
    for cat, cat_score in categories.items():
        weight = FIT_SCORE_WEIGHTS[cat]
        label = cat.replace('_', ' ').title()
        print(f"  {label}: {cat_score}/100 (weight: {weight}%)")
