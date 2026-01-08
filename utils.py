"""
Utility functions for ICHRA Calculator
Includes calculations for premiums, employer contributions, and data formatting
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from datetime import datetime, date


def calculate_age_from_dob(dob_str: str, reference_date: Optional[date] = None) -> int:
    """
    Calculate age from date of birth

    Args:
        dob_str: Date of birth as string (flexible format)
                 Accepts: m/d/yy, mm/dd/yy, m/d/yyyy, mm/dd/yyyy, yyyy-mm-dd
        reference_date: Date to calculate age as of (default: January 1, 2026 - plan effective date)

    Returns:
        Age in years

    Raises:
        ValueError: If date format is invalid

    Examples:
        >>> calculate_age_from_dob('03/15/1985')
        40  # As of 2026-01-01
        >>> calculate_age_from_dob('3/15/85')
        40  # As of 2026-01-01 (2-digit year: 85 → 1985)
        >>> calculate_age_from_dob('12/25/10')
        15  # As of 2026-01-01 (2-digit year: 10 → 2010)
    """
    if reference_date is None:
        # Default to plan effective date (2026-01-01)
        reference_date = date(2026, 1, 1)

    # Parse DOB - try multiple formats
    dob_date = None
    dob_str = dob_str.strip()

    # Try slash-separated formats (US style)
    if '/' in dob_str:
        # List of formats to try, in order of preference
        # Support both 4-digit and 2-digit years, with/without leading zeros
        date_formats = [
            '%m/%d/%Y',   # 03/15/1985
            '%m/%d/%y',   # 03/15/85
            '%-m/%-d/%Y', # 3/5/1985 (Unix/Mac)
            '%-m/%-d/%y', # 3/5/85 (Unix/Mac)
        ]

        # Windows doesn't support %-m, so also try without hyphen
        if not any(c in dob_str for c in ['%-']):
            # Try flexible parsing for dates without leading zeros
            parts = dob_str.split('/')
            if len(parts) == 3:
                month, day, year = parts

                # Handle 2-digit year conversion
                if len(year) == 2:
                    year_int = int(year)
                    # Century logic: 00-29 → 2000s, 30-99 → 1900s
                    if year_int <= 29:
                        year = f"20{year}"
                    else:
                        year = f"19{year}"

                # Reconstruct with zero-padded values
                normalized_date = f"{int(month):02d}/{int(day):02d}/{year}"
                try:
                    dob_date = datetime.strptime(normalized_date, '%m/%d/%Y').date()
                except ValueError:
                    pass

        # If not parsed yet, try standard formats
        if dob_date is None:
            for fmt in date_formats:
                try:
                    dob_date = datetime.strptime(dob_str, fmt).date()
                    break
                except ValueError:
                    continue

    # Try hyphen-separated format (ISO style)
    elif '-' in dob_str:
        try:
            dob_date = datetime.strptime(dob_str, '%Y-%m-%d').date()
        except ValueError:
            pass

    # If still not parsed, raise error
    if dob_date is None:
        raise ValueError(
            f"Invalid date format: {dob_str}. "
            f"Accepted formats: m/d/yy, mm/dd/yy, m/d/yyyy, mm/dd/yyyy, or yyyy-mm-dd"
        )

    # Calculate age
    age = reference_date.year - dob_date.year

    # Adjust if birthday hasn't occurred yet this year
    if (reference_date.month, reference_date.day) < (dob_date.month, dob_date.day):
        age -= 1

    # Validate age is reasonable
    if age < 0:
        raise ValueError(f"DOB {dob_str} is in the future")
    if age > 120:
        raise ValueError(f"Age {age} is unreasonably high. Check DOB: {dob_str}")

    return age


def parse_currency(value_str: str) -> Optional[float]:
    """
    Parse a currency string to a float.

    Args:
        value_str: Currency value as string (e.g., "$5,920.23", "$4500", "4500", "5920.23")

    Returns:
        Float value, or None if empty/invalid

    Examples:
        >>> parse_currency('$5,920.23')
        5920.23
        >>> parse_currency('$4500')
        4500.0
        >>> parse_currency('4500')
        4500.0
        >>> parse_currency('')
        None
    """
    if value_str is None or pd.isna(value_str):
        return None

    value_str = str(value_str).strip()
    if value_str == '' or value_str.lower() in ('nan', 'none', 'null'):
        return None

    # Remove currency symbols and commas
    cleaned = value_str.replace('$', '').replace(',', '').strip()

    try:
        return float(cleaned)
    except ValueError:
        return None


class PremiumCalculator:
    """Calculate ICHRA premiums and employee costs"""

    @staticmethod
    def calculate_employee_premium(age: int, premium_rates: pd.DataFrame,
                                   plan_id: str, rating_area: int,
                                   state_code: str,
                                   rating_area_source: str = 'census') -> float:
        """
        Get premium for a specific employee

        Args:
            age: Employee age
            premium_rates: DataFrame with plan rates
            plan_id: HIOS Plan ID
            rating_area: Rating area ID (integer)
            state_code: Employee's state (2-letter code, e.g., 'GA', 'NC')

        Returns:
            Monthly premium amount
        """
        from constants import FAMILY_TIER_STATES, AGE_BAND_0_14, AGE_BAND_64_PLUS

        # Use the employee's state_code (passed as parameter), NOT the plan's state

        # Convert age to age band for lookup
        # Ages 0-14 use "0-14" band, 64+ use "64 and over" band
        if age <= 14:
            age_lookup = AGE_BAND_0_14
        elif age >= 64:
            age_lookup = AGE_BAND_64_PLUS
        else:
            age_lookup = str(age)

        # Ensure rating_area is integer for comparison
        rating_area_int = int(rating_area)

        # For family-tier states (NY/VT), use "Family-Tier Rates" or first valid rate
        if state_code in FAMILY_TIER_STATES:
            # Try "Family-Tier Rates" first
            rate = premium_rates[
                (premium_rates['hios_plan_id'] == plan_id) &
                (premium_rates['state_code'] == state_code) &
                (premium_rates['rating_area_id'] == rating_area_int) &
                (premium_rates['age'] == "Family-Tier Rates")
            ]

            # If no "Family-Tier Rates", use first valid non-zero rate for this plan/rating area
            # (Family-tier plans charge same rate for all ages)
            if rate.empty:
                plan_rates = premium_rates[
                    (premium_rates['hios_plan_id'] == plan_id) &
                    (premium_rates['state_code'] == state_code) &
                    (premium_rates['rating_area_id'] == rating_area_int) &
                    (premium_rates['premium'] > 0)
                ]
                if not plan_rates.empty:
                    return float(plan_rates.iloc[0]['premium'])
                else:
                    return 0.0
        else:
            # For other states, use age-based rating with age bands

            # DEBUG: Before filtering, show what's available for this plan+state
            import logging
            debug_plan_state = premium_rates[
                (premium_rates['hios_plan_id'] == plan_id) &
                (premium_rates['state_code'] == state_code)
            ]

            if not debug_plan_state.empty:
                logging.debug(f"FILTER DEBUG for plan {plan_id}, state {state_code}:")
                logging.debug(f"  Rows matching plan+state: {len(debug_plan_state)}")
                logging.debug(f"  Available ages in DataFrame: {sorted(debug_plan_state['age'].unique().tolist())}")
                logging.debug(f"  Age we're looking for: '{age_lookup}' (type: {type(age_lookup).__name__})")
                logging.debug(f"  Available rating areas: {sorted(debug_plan_state['rating_area_id'].unique().tolist())}")
                logging.debug(f"  Rating area we're looking for: {rating_area_int} (type: {type(rating_area_int).__name__})")

                # Check if age exists at all in the DataFrame
                age_exists = age_lookup in debug_plan_state['age'].values
                logging.debug(f"  Does age '{age_lookup}' exist in DataFrame? {age_exists}")

                # Check if rating area exists
                rating_area_exists = rating_area_int in debug_plan_state['rating_area_id'].values
                logging.debug(f"  Does rating_area {rating_area_int} exist in DataFrame? {rating_area_exists}")

                # Show sample rows
                logging.debug(f"  Sample rows (first 3):")
                for idx, row in debug_plan_state.head(3).iterrows():
                    logging.debug(f"    Age: '{row['age']}', Rating Area: {row['rating_area_id']}, Premium: {row['premium']}")

            rate = premium_rates[
                (premium_rates['hios_plan_id'] == plan_id) &
                (premium_rates['state_code'] == state_code) &
                (premium_rates['rating_area_id'] == rating_area_int) &
                (premium_rates['age'] == age_lookup)
            ]

        if rate.empty:
            # Debug: log why rate wasn't found with detailed type information
            import logging
            plan_rates_available = premium_rates[
                (premium_rates['hios_plan_id'] == plan_id) &
                (premium_rates['state_code'] == state_code)
            ]

            # Check if the issue is with the rating area filter specifically
            plan_age_match = premium_rates[
                (premium_rates['hios_plan_id'] == plan_id) &
                (premium_rates['state_code'] == state_code) &
                (premium_rates['age'] == age_lookup)
            ]

            # Log as DEBUG instead of WARNING - this is expected behavior for plans with partial rating area coverage
            logging.debug(
                f"No rate found for plan_id={plan_id}, state={state_code}, "
                f"rating_area={rating_area_int} (original: {rating_area}, type: {type(rating_area).__name__}) (source: {rating_area_source}), "
                f"age={age} (lookup: '{age_lookup}'). "
                f"Available rating areas for this plan in {state_code}: {plan_rates_available['rating_area_id'].unique()} "
                f"(types: {[type(x).__name__ for x in plan_rates_available['rating_area_id'].unique()[:3]]}). "
                f"Matching plan+state+age but ANY rating area: {plan_age_match['rating_area_id'].unique() if not plan_age_match.empty else 'none'}"
            )
            return 0.0

        return float(rate.iloc[0]['premium'])

    @staticmethod
    def calculate_employer_contribution(premium: float, contribution_pct: float) -> float:
        """
        Calculate employer ICHRA contribution

        Args:
            premium: Monthly premium
            contribution_pct: Employer contribution percentage (0-100)

        Returns:
            Employer contribution amount
        """
        return premium * (contribution_pct / 100.0)

    @staticmethod
    def calculate_employee_net_cost(premium: float, employer_contribution: float) -> float:
        """
        Calculate employee's net cost (premium - employer contribution)

        Args:
            premium: Monthly premium
            employer_contribution: Employer ICHRA contribution

        Returns:
            Employee's net monthly cost
        """
        return max(0.0, premium - employer_contribution)

    @staticmethod
    def aggregate_census_costs(census_df: pd.DataFrame, plan_rates: pd.DataFrame,
                               plan_id: str, contribution_pct: float) -> Dict:
        """
        Calculate aggregate costs for entire employee census

        Args:
            census_df: Employee census with age, state, county
            plan_rates: Premium rates DataFrame
            plan_id: Selected plan ID
            contribution_pct: Employer contribution percentage

        Returns:
            Dictionary with aggregate cost metrics
        """
        total_employees = len(census_df)
        total_premium = 0.0
        total_employer_contribution = 0.0
        total_employee_cost = 0.0

        for _, employee in census_df.iterrows():
            premium = PremiumCalculator.calculate_employee_premium(
                age=employee['age'],
                premium_rates=plan_rates,
                plan_id=plan_id,
                rating_area=employee.get('rating_area_id', 0),
                state_code=employee['state'],
                rating_area_source=f"census_employee_{employee.get('employee_id', 'unknown')}"
            )

            employer_contrib = PremiumCalculator.calculate_employer_contribution(
                premium, contribution_pct
            )

            employee_cost = PremiumCalculator.calculate_employee_net_cost(
                premium, employer_contrib
            )

            total_premium += premium
            total_employer_contribution += employer_contrib
            total_employee_cost += employee_cost

        return {
            'total_employees': total_employees,
            'total_monthly_premium': total_premium,
            'total_annual_premium': total_premium * 12,
            'total_monthly_employer_contribution': total_employer_contribution,
            'total_annual_employer_contribution': total_employer_contribution * 12,
            'total_monthly_employee_cost': total_employee_cost,
            'total_annual_employee_cost': total_employee_cost * 12,
            'avg_monthly_premium_per_employee': total_premium / total_employees if total_employees > 0 else 0,
            'avg_monthly_employer_contribution_per_employee': total_employer_contribution / total_employees if total_employees > 0 else 0,
            'avg_monthly_employee_cost_per_employee': total_employee_cost / total_employees if total_employees > 0 else 0,
            'employer_contribution_percentage': contribution_pct
        }

    @staticmethod
    def aggregate_family_census_costs(
        census_df: pd.DataFrame,
        dependents_df: Optional[pd.DataFrame],
        plan_rates: pd.DataFrame,
        plan_id: str,
        employee_contribution_pct: float,
        dependent_contribution_pct: float = None,
        dependent_contribution_strategy: str = "Same as employee",
        dependent_contribution_amount: float = 0.0
    ) -> Dict:
        """
        Calculate aggregate costs for entire census including dependents

        Args:
            census_df: Employee census
            dependents_df: Dependents table (can be None)
            plan_rates: Premium rates DataFrame
            plan_id: Selected plan ID
            employee_contribution_pct: Employer contribution % for employees
            dependent_contribution_pct: Employer contribution % for dependents
            dependent_contribution_strategy: How to handle dependent contributions
            dependent_contribution_amount: Fixed dollar amount for "Fixed dollar amount" strategy

        Returns:
            Dictionary with comprehensive cost metrics
        """
        # If no dependents, use original calculation
        if dependents_df is None or dependents_df.empty:
            return PremiumCalculator.aggregate_census_costs(
                census_df, plan_rates, plan_id, employee_contribution_pct
            )

        total_employees = len(census_df)
        total_dependents = len(dependents_df)
        total_covered_lives = total_employees + total_dependents

        # Initialize accumulators
        total_employee_premium = 0.0
        total_dependent_premium = 0.0
        total_employer_contribution_employees = 0.0
        total_employer_contribution_dependents = 0.0
        total_employee_cost = 0.0

        # Track by family composition for analysis
        family_composition_costs = {}

        # Import family tier states constant
        from constants import FAMILY_TIER_STATES

        # Set dependent contribution percentage based on strategy
        if dependent_contribution_strategy == "Same as employee":
            dep_contrib_pct = employee_contribution_pct
        elif dependent_contribution_strategy == "Different percentage":
            dep_contrib_pct = dependent_contribution_pct if dependent_contribution_pct is not None else employee_contribution_pct
        else:
            dep_contrib_pct = 0.0  # For "No contribution" or "Fixed dollar amount"

        # Calculate costs for each employee family unit
        for _, emp in census_df.iterrows():
            employee_id = emp.get('employee_id', 'N/A')
            rating_area = emp.get('rating_area_id', 0)

            # Handle both 'age' and 'employee_age' columns for backward compatibility
            emp_age = emp.get('employee_age', emp.get('age', 30))

            # Get dependents for this employee
            family_deps = dependents_df[
                dependents_df['employee_id'] == employee_id
            ]

            # Determine family composition
            num_deps = len(family_deps)
            has_spouse = not family_deps[family_deps['relationship'] == 'spouse'].empty
            num_children = len(family_deps[family_deps['relationship'] == 'child'])

            family_comp = PremiumCalculator._get_family_composition_label(
                has_spouse, num_children
            )

            # Check if THIS employee is in a family-tier state (based on their state, not the plan's state)
            is_family_tier_state = emp['state'] in FAMILY_TIER_STATES

            # Calculate premiums based on rating type
            if is_family_tier_state:
                # Family-tier rating (NY, VT)
                family_tier = PremiumCalculator._determine_family_tier(
                    has_spouse, num_children
                )

                # Get family-tier rate
                family_premium = PremiumCalculator.calculate_family_tier_premium(
                    plan_rates=plan_rates,
                    plan_id=plan_id,
                    rating_area=rating_area,
                    family_tier=family_tier
                )

                # For reporting, split conceptually between employee and dependents
                if num_deps == 0:
                    emp_premium = family_premium
                    dep_premium = 0.0
                else:
                    # Pro-rate based on family structure (rough approximation)
                    emp_premium = family_premium * 0.5  # Employee typically ~50% of family cost
                    dep_premium = family_premium * 0.5

            else:
                # Age-based rating (most states)
                # Employee premium
                emp_premium = PremiumCalculator.calculate_employee_premium(
                    age=emp_age,
                    premium_rates=plan_rates,
                    plan_id=plan_id,
                    rating_area=rating_area,
                    state_code=emp['state'],
                    rating_area_source=f'census_employee_{employee_id}'
                )

                # Dependent premiums
                dep_premiums = []
                for _, dep in family_deps.iterrows():
                    dep_prem = PremiumCalculator.calculate_employee_premium(
                        age=dep['age'],
                        premium_rates=plan_rates,
                        plan_id=plan_id,
                        rating_area=rating_area,
                        state_code=emp['state'],
                        rating_area_source=f'census_dependent_of_{employee_id}'
                    )
                    dep_premiums.append(dep_prem)

                dep_premium = sum(dep_premiums)

            # Calculate employer contributions
            emp_employer_contrib = PremiumCalculator.calculate_employer_contribution(
                emp_premium, employee_contribution_pct
            )

            # Determine contribution value based on strategy
            if dependent_contribution_strategy == "Same as employee":
                dep_contrib_value = dep_contrib_pct  # Same % as employee (set above)
            elif dependent_contribution_strategy == "Different percentage":
                dep_contrib_value = dep_contrib_pct
            else:  # "Fixed dollar amount" or "No contribution"
                dep_contrib_value = dependent_contribution_amount

            dep_employer_contrib = PremiumCalculator.calculate_dependent_contribution(
                dep_premium,
                dependent_contribution_strategy,
                dep_contrib_value,
                num_deps
            )

            # Calculate employee's net cost
            total_family_premium = emp_premium + dep_premium
            total_employer_contrib = emp_employer_contrib + dep_employer_contrib
            family_employee_cost = total_family_premium - total_employer_contrib

            # Accumulate totals
            total_employee_premium += emp_premium
            total_dependent_premium += dep_premium
            total_employer_contribution_employees += emp_employer_contrib
            total_employer_contribution_dependents += dep_employer_contrib
            total_employee_cost += family_employee_cost

            # Track by family composition
            if family_comp not in family_composition_costs:
                family_composition_costs[family_comp] = {
                    'total_premium': 0.0,
                    'employer_contribution': 0.0,
                    'employee_cost': 0.0,
                    'count': 0
                }

            family_composition_costs[family_comp]['total_premium'] += total_family_premium
            family_composition_costs[family_comp]['employer_contribution'] += total_employer_contrib
            family_composition_costs[family_comp]['employee_cost'] += family_employee_cost
            family_composition_costs[family_comp]['count'] += 1

        # Calculate averages for family compositions
        for comp in family_composition_costs:
            count = family_composition_costs[comp]['count']
            if count > 0:
                family_composition_costs[comp]['avg_monthly_premium'] = (
                    family_composition_costs[comp]['total_premium'] / count
                )
                family_composition_costs[comp]['avg_employer_contribution'] = (
                    family_composition_costs[comp]['employer_contribution'] / count
                )
                family_composition_costs[comp]['avg_employee_cost'] = (
                    family_composition_costs[comp]['employee_cost'] / count
                )

        # Calculate aggregate metrics
        total_premium = total_employee_premium + total_dependent_premium
        total_employer_contribution = (
            total_employer_contribution_employees +
            total_employer_contribution_dependents
        )

        return {
            # Totals
            'total_employees': total_employees,
            'total_dependents': total_dependents,
            'total_covered_lives': total_covered_lives,

            # Premium breakdown
            'total_monthly_premium': total_premium,
            'total_annual_premium': total_premium * 12,
            'employee_monthly_premium': total_employee_premium,
            'employee_annual_premium': total_employee_premium * 12,
            'dependent_monthly_premium': total_dependent_premium,
            'dependent_annual_premium': total_dependent_premium * 12,

            # Employer contribution breakdown
            'total_monthly_employer_contribution': total_employer_contribution,
            'total_annual_employer_contribution': total_employer_contribution * 12,
            'employer_contribution_employees': total_employer_contribution_employees,
            'employer_contribution_employees_annual': total_employer_contribution_employees * 12,
            'employer_contribution_dependents': total_employer_contribution_dependents,
            'employer_contribution_dependents_annual': total_employer_contribution_dependents * 12,

            # Employee cost
            'total_monthly_employee_cost': total_employee_cost,
            'total_annual_employee_cost': total_employee_cost * 12,

            # Per-capita metrics
            'avg_monthly_premium_per_employee': total_premium / total_employees if total_employees > 0 else 0,
            'avg_monthly_premium_per_covered_life': total_premium / total_covered_lives if total_covered_lives > 0 else 0,
            'avg_monthly_employer_contribution_per_employee': total_employer_contribution / total_employees if total_employees > 0 else 0,
            'avg_monthly_employee_cost_per_employee': total_employee_cost / total_employees if total_employees > 0 else 0,

            # Contribution percentages
            'employer_contribution_percentage': employee_contribution_pct,
            'dependent_contribution_percentage': dep_contrib_pct,

            # Family composition breakdown
            'by_family_composition': family_composition_costs
        }

    @staticmethod
    def calculate_dependent_contribution(
        dependent_premium: float,
        contribution_strategy: str,
        contribution_value: float,
        num_dependents: int = 1
    ) -> float:
        """
        Calculate employer contribution for dependents

        Args:
            dependent_premium: Total monthly premium for dependents
            contribution_strategy: "Same as employee", "Different percentage", "Fixed dollar amount", "No contribution"
            contribution_value: Percentage (0-100) or dollar amount
            num_dependents: Number of dependents (used for fixed dollar strategy)

        Returns:
            Employer contribution amount
        """
        if contribution_strategy == "No contribution":
            return 0.0
        elif contribution_strategy == "Fixed dollar amount":
            fixed_total = contribution_value * num_dependents
            return min(fixed_total, dependent_premium)  # Can't exceed premium
        else:  # Percentage-based (including "Same as employee" and "Different percentage")
            # Calculate contribution based on percentage
            calculated_contribution = dependent_premium * (contribution_value / 100.0)
            # Cap at dependent premium (can't contribute more than 100%)
            return min(calculated_contribution, dependent_premium)

    @staticmethod
    def _get_family_composition_label(has_spouse: bool, num_children: int) -> str:
        """Get human-readable family composition label"""
        if not has_spouse and num_children == 0:
            return "Employee Only"
        elif has_spouse and num_children == 0:
            return "Employee + Spouse"
        elif not has_spouse and num_children > 0:
            return f"Employee + {num_children} Child{'ren' if num_children > 1 else ''}"
        else:
            return f"Employee + Spouse + {num_children} Child{'ren' if num_children > 1 else ''}"

    @staticmethod
    def _determine_family_tier(has_spouse: bool, num_children: int) -> str:
        """
        Determine family tier for family-tier rating states (NY, VT)

        Returns:
            "Individual", "Employee+Spouse", "Employee+Child(ren)", or "Family"
        """
        if not has_spouse and num_children == 0:
            return "Individual"
        elif has_spouse and num_children == 0:
            return "Employee+Spouse"
        elif not has_spouse and num_children > 0:
            return "Employee+Child(ren)"
        else:
            return "Family"

    @staticmethod
    def calculate_family_tier_premium(
        plan_rates: pd.DataFrame,
        plan_id: str,
        rating_area: int,
        family_tier: str
    ) -> float:
        """
        Get premium for family-tier rating states

        For NY/VT, need to look up specific tier rates
        This uses "Family-Tier Rates" from database with tier multipliers

        Returns:
            Monthly family tier premium
        """
        # Ensure rating_area is integer for comparison
        rating_area_int = int(rating_area)

        # Try to get "Family-Tier Rates" from database
        rate = plan_rates[
            (plan_rates['hios_plan_id'] == plan_id) &
            (plan_rates['rating_area_id'] == rating_area_int) &
            (plan_rates['age'] == "Family-Tier Rates")
        ]

        if not rate.empty:
            # Base rate, apply tier multiplier
            base_rate = float(rate.iloc[0]['premium'])

            # Apply tier multiplier (these are typical ratios, may need adjustment based on actual data)
            tier_multipliers = {
                "Individual": 1.0,
                "Employee+Spouse": 2.0,
                "Employee+Child(ren)": 1.8,
                "Family": 2.5
            }

            multiplier = tier_multipliers.get(family_tier, 1.0)
            return base_rate * multiplier
        else:
            # Fallback: use first valid non-zero rate
            plan_rates_valid = plan_rates[
                (plan_rates['hios_plan_id'] == plan_id) &
                (plan_rates['rating_area_id'] == rating_area_int) &
                (plan_rates['premium'] > 0)
            ]
            if not plan_rates_valid.empty:
                return float(plan_rates_valid.iloc[0]['premium'])

        return 0.0


class CensusProcessor:
    """Process and validate employee census data"""

    @staticmethod
    def validate_census_csv(df: pd.DataFrame) -> Tuple[bool, str]:
        """
        Validate uploaded census CSV

        Args:
            df: Uploaded census DataFrame

        Returns:
            Tuple of (is_valid, error_message)
        """
        required_columns = ['age', 'state', 'county']

        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            return False, f"Missing required columns: {', '.join(missing_columns)}"

        # Validate age range
        if df['age'].min() < 0 or df['age'].max() > 120:
            return False, "Age values must be between 0 and 120"

        # Validate state codes (should be 2 characters)
        if not df['state'].str.len().eq(2).all():
            return False, "State codes must be 2-letter abbreviations (e.g., 'CA', 'NY')"

        return True, ""

    @staticmethod
    def add_rating_areas_to_census(census_df: pd.DataFrame, db) -> pd.DataFrame:
        """
        Add rating area information to census based on state/county

        Args:
            census_df: Employee census DataFrame
            db: Database connection

        Returns:
            Census DataFrame with rating_area_id column added
        """
        from queries import PlanQueries

        census_with_rating = census_df.copy()
        census_with_rating['rating_area_id'] = None

        # Batch query: get unique (state, county) pairs and look up all at once
        if 'state' in census_with_rating.columns and 'county' in census_with_rating.columns:
            # Get unique state/county pairs
            state_county_pairs = list(census_with_rating[['state', 'county']].drop_duplicates().itertuples(index=False, name=None))

            # Batch lookup all rating areas in one query
            rating_areas_df = PlanQueries.get_rating_areas_batch(db, state_county_pairs)

            if not rating_areas_df.empty:
                # Create a lookup dict for fast mapping
                rating_lookup = {}
                for _, row in rating_areas_df.iterrows():
                    key = (row['state_code'].upper(), row['county'].upper())
                    rating_lookup[key] = row['rating_area_id']

                # Apply to census
                census_with_rating['rating_area_id'] = census_with_rating.apply(
                    lambda row: rating_lookup.get(
                        (str(row['state']).upper(), str(row['county']).upper())
                    ),
                    axis=1
                )

        return census_with_rating

    @staticmethod
    def parse_new_census_format(df: pd.DataFrame, db) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Parse new census format with ZIP codes, DOBs, and Family Status codes

        Args:
            df: Raw census DataFrame with new format columns
            db: Database connection

        Returns:
            Tuple of (employees_df, dependents_df)
            - employees_df: Normalized employee data with rating areas
            - dependents_df: Normalized dependent data

        Raises:
            ValueError: If required columns missing or data invalid
        """
        import logging
        import time

        logging.info("=" * 60)
        logging.info(f"CENSUS PARSE: Starting parse_new_census_format with {len(df)} rows")
        parse_start = time.time()

        from constants import NEW_CENSUS_REQUIRED_COLUMNS, FAMILY_STATUS_CODES
        from queries import PlanQueries

        # Validate required columns
        missing = [col for col in NEW_CENSUS_REQUIRED_COLUMNS if col not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {', '.join(missing)}")

        employees = []
        dependents = []
        errors = []

        total_rows = len(df)
        logging.info(f"CENSUS PARSE: Beginning batch ZIP lookup for {total_rows} rows")

        # OPTIMIZATION: Batch lookup all ZIP codes at once instead of N+1 queries
        # Step 1: Collect all unique (zip, state) pairs
        zip_state_pairs = []
        for idx, row in df.iterrows():
            home_zip_raw = str(row['Home Zip']).strip()
            home_zip = home_zip_raw.split('-')[0].zfill(5)[:5]
            home_state = str(row['Home State']).strip().upper()
            zip_state_pairs.append((home_zip, home_state))

        # Step 2: Batch lookup all ZIPs at once (single DB round-trip)
        batch_start = time.time()
        zip_lookup_df = PlanQueries.get_counties_by_zip_batch(db, zip_state_pairs)
        batch_elapsed = time.time() - batch_start
        logging.info(f"CENSUS PARSE: Batch ZIP lookup completed in {batch_elapsed:.3f}s for {len(zip_state_pairs)} pairs")

        # Step 3: Build lookup dictionary for O(1) access
        zip_lookup = {}
        for _, row in zip_lookup_df.iterrows():
            key = (row['zip'], row['state_code'])
            zip_lookup[key] = {
                'county': row['county'],
                'rating_area_id': row['rating_area_id'],
                'city': row.get('city', '')
            }

        logging.info(f"CENSUS PARSE: Built lookup dict with {len(zip_lookup)} entries")

        # Step 4: Process each row using the pre-built lookup
        for idx, row in df.iterrows():
            # Log progress every 50 rows
            if idx % 50 == 0:
                elapsed = time.time() - parse_start
                logging.info(f"CENSUS PARSE: Processing row {idx+1}/{total_rows} ({elapsed:.1f}s elapsed)")

            try:
                employee_number = str(row['Employee Number']).strip()
                # Handle ZIP+4 format (e.g., "29654-7352" -> "29654")
                home_zip_raw = str(row['Home Zip']).strip()
                home_zip = home_zip_raw.split('-')[0].zfill(5)[:5]  # Take first 5 digits only
                home_state = str(row['Home State']).strip().upper()
                family_status = str(row['Family Status']).strip().upper()
                ee_dob = str(row['EE DOB']).strip()

                # Validate Family Status code
                if family_status not in FAMILY_STATUS_CODES:
                    errors.append(f"Row {idx+2}: Invalid Family Status '{family_status}'. Must be EE, EC, ES, or F")
                    continue

                # Calculate employee age from DOB
                try:
                    employee_age = calculate_age_from_dob(ee_dob)
                except ValueError as e:
                    errors.append(f"Row {idx+2}: Invalid EE DOB '{ee_dob}': {e}")
                    continue

                # Validate employee age range
                # Note: ACA rates use "64 and over" band for ages 64+, so older employees are valid
                # Medicare eligibility starts at 65, but employees may still use ICHRA marketplace plans
                if employee_age < 16:
                    errors.append(f"Row {idx+2}: Employee age {employee_age} is under 16. Check DOB: {ee_dob}")
                    continue
                if employee_age > 120:
                    errors.append(f"Row {idx+2}: Employee age {employee_age} appears invalid. Check DOB: {ee_dob}")
                    continue

                # Look up county and rating area from pre-built dictionary (O(1) lookup)
                lookup_key = (home_zip, home_state)
                county_data = zip_lookup.get(lookup_key)

                if county_data is None:
                    errors.append(f"Row {idx+2}: ZIP code {home_zip} not found for state {home_state}")
                    continue

                county = county_data['county']
                rating_area_id = county_data['rating_area_id']
                city = county_data.get('city', '')

                # Log canonical rating area assignment
                logging.debug(
                    f"CENSUS LOAD: Employee {employee_number}, ZIP {home_zip} ({home_state}) "
                    f"→ County '{county}' → rating_area_id = {rating_area_id}"
                )

                # Extract name fields (optional, may not be present)
                last_name = ''
                first_name = ''
                if 'Last Name' in row.index and pd.notna(row.get('Last Name')):
                    last_name = str(row['Last Name']).strip()
                if 'First Name' in row.index and pd.notna(row.get('First Name')):
                    first_name = str(row['First Name']).strip()

                # Extract optional monthly income (for ACA affordability)
                monthly_income = None
                if 'Monthly Income' in row.index:
                    monthly_income = parse_currency(row.get('Monthly Income'))

                # Extract current contribution columns (optional - for group plan comparison)
                current_ee_monthly = None
                current_er_monthly = None

                if 'Current EE Monthly' in row.index:
                    current_ee_monthly = parse_currency(row.get('Current EE Monthly'))

                if 'Current ER Monthly' in row.index:
                    current_er_monthly = parse_currency(row.get('Current ER Monthly'))

                # Extract projected 2026 premium (optional - for renewal comparison)
                projected_2026_premium = None
                if '2026 Premium' in row.index:
                    projected_2026_premium = parse_currency(row.get('2026 Premium'))

                # Extract gap insurance (optional - employer gap coverage cost)
                gap_insurance_monthly = None
                if 'Gap Insurance' in row.index:
                    gap_insurance_monthly = parse_currency(row.get('Gap Insurance'))

                # Create employee record
                employee = {
                    'employee_id': employee_number,
                    'last_name': last_name,
                    'first_name': first_name,
                    'age': employee_age,
                    'dob': ee_dob,
                    'state': home_state,
                    'county': county,
                    'city': city,
                    'zip_code': home_zip,
                    'rating_area_id': rating_area_id,
                    'family_status': family_status,
                    'monthly_income': monthly_income,
                    'current_ee_monthly': current_ee_monthly,
                    'current_er_monthly': current_er_monthly,
                    'projected_2026_premium': projected_2026_premium,
                    'gap_insurance_monthly': gap_insurance_monthly,
                }
                employees.append(employee)

                # Extract dependents based on Family Status
                dependent_id_counter = 1

                # ES or F: Extract spouse
                if family_status in ['ES', 'F']:
                    if 'Spouse DOB' not in row or pd.isna(row['Spouse DOB']) or str(row['Spouse DOB']).strip() == '':
                        errors.append(f"Row {idx+2}: Family Status '{family_status}' requires Spouse DOB")
                        continue

                    spouse_dob = str(row['Spouse DOB']).strip()
                    try:
                        spouse_age = calculate_age_from_dob(spouse_dob)
                    except ValueError as e:
                        errors.append(f"Row {idx+2}: Invalid Spouse DOB '{spouse_dob}': {e}")
                        continue

                    if spouse_age < 0 or spouse_age > 120:
                        errors.append(f"Row {idx+2}: Spouse age {spouse_age} out of range. Check DOB: {spouse_dob}")
                        continue

                    dependents.append({
                        'dependent_id': f"{employee_number}_SPOUSE",
                        'employee_id': employee_number,
                        'relationship': 'spouse',
                        'age': spouse_age,
                        'dob': spouse_dob
                    })

                # EC or F: Extract children
                if family_status in ['EC', 'F']:
                    has_children = False

                    for dep_num in range(2, 7):  # Dep 2 through Dep 6
                        dep_col = f'Dep {dep_num} DOB'

                        if dep_col in row and not pd.isna(row[dep_col]) and str(row[dep_col]).strip() != '':
                            child_dob = str(row[dep_col]).strip()

                            try:
                                child_age = calculate_age_from_dob(child_dob)
                            except ValueError as e:
                                errors.append(f"Row {idx+2}: Invalid {dep_col} '{child_dob}': {e}")
                                continue

                            if child_age < 0 or child_age > 26:
                                errors.append(f"Row {idx+2}: Child age {child_age} out of range (0-26). Check {dep_col}: {child_dob}")
                                continue

                            dependents.append({
                                'dependent_id': f"{employee_number}_CHILD_{dep_num-1}",
                                'employee_id': employee_number,
                                'relationship': 'child',
                                'age': child_age,
                                'dob': child_dob
                            })
                            has_children = True

                    # EC or F requires at least one child
                    if not has_children:
                        errors.append(f"Row {idx+2}: Family Status '{family_status}' requires at least one child (Dep 2 DOB)")
                        continue

            except Exception as e:
                errors.append(f"Row {idx+2}: Unexpected error: {e}")
                continue

        # Log summary of row processing
        total_elapsed = time.time() - parse_start
        logging.info(f"CENSUS PARSE: Row iteration complete in {total_elapsed:.1f}s")
        logging.info(f"CENSUS PARSE: Processed {len(employees)} employees, {len(dependents)} dependents, {len(errors)} errors")

        # Report errors if any
        if errors:
            logging.warning(f"CENSUS PARSE: {len(errors)} validation errors found")
            error_msg = "\n".join(errors[:10])  # Show first 10 errors
            if len(errors) > 10:
                error_msg += f"\n... and {len(errors) - 10} more errors"
            raise ValueError(f"Census validation errors:\n{error_msg}")

        # Create DataFrames
        logging.info("CENSUS PARSE: Creating DataFrames...")
        employees_df = pd.DataFrame(employees)
        dependents_df = pd.DataFrame(dependents) if dependents else pd.DataFrame(
            columns=['dependent_id', 'employee_id', 'relationship', 'age', 'dob']
        )

        # Log canonical rating area summary by state
        import logging
        if not employees_df.empty:
            # Convert rating_area_id to string to handle mixed types (int from amended table, str from ZIP fallback)
            employees_df['rating_area_id'] = employees_df['rating_area_id'].astype(str)

            state_rating_summary = {}
            for state in employees_df['state'].unique():
                state_employees = employees_df[employees_df['state'] == state]
                unique_rating_areas = sorted(state_employees['rating_area_id'].unique())
                state_rating_summary[state] = unique_rating_areas

            logging.debug("=" * 80)
            logging.debug("CANONICAL RATING AREA MAPPING (from census ZIP → FIPS → rating_area_id):")
            for state, areas in sorted(state_rating_summary.items()):
                logging.debug(f"  {state}: {areas}")
            logging.debug("=" * 80)

        return employees_df, dependents_df

    @staticmethod
    def create_sample_census(num_employees: int = 10) -> pd.DataFrame:
        """
        Create sample census data for testing

        Args:
            num_employees: Number of sample employees

        Returns:
            Sample census DataFrame
        """
        np.random.seed(42)

        ages = np.random.randint(25, 65, size=num_employees)
        states = np.random.choice(['CA', 'NY', 'TX', 'FL', 'IL'], size=num_employees)
        counties = {
            'CA': ['LOS ANGELES', 'SAN DIEGO', 'ORANGE', 'ALAMEDA'],
            'NY': ['NEW YORK', 'KINGS', 'QUEENS', 'SUFFOLK'],
            'TX': ['HARRIS', 'DALLAS', 'TRAVIS', 'BEXAR'],
            'FL': ['MIAMI-DADE', 'BROWARD', 'PALM BEACH', 'HILLSBOROUGH'],
            'IL': ['COOK', 'DUPAGE', 'LAKE', 'WILL']
        }

        county_list = [np.random.choice(counties[state]) for state in states]

        return pd.DataFrame({
            'employee_id': [f'EMP{i+1:03d}' for i in range(num_employees)],
            'age': ages,
            'state': states,
            'county': county_list
        })

    @staticmethod
    def create_new_census_template() -> str:
        """
        Create CSV template for new census format

        Returns:
            CSV string with headers and example rows
        """
        from constants import NEW_CENSUS_ALL_COLUMNS
        from datetime import date

        # Create header row
        headers = NEW_CENSUS_ALL_COLUMNS

        # Create example rows
        examples = [
            {
                'Employee Number': 'EMP001',
                'Last Name': 'Smith',
                'First Name': 'John',
                'Home Zip': '10001',
                'Home State': 'NY',
                'Family Status': 'F',
                'EE DOB': '05/15/1985',
                'Spouse DOB': '07/22/1987',
                'Dep 2 DOB': '03/10/2015',
                'Dep 3 DOB': '11/05/2017',
                'Dep 4 DOB': '',
                'Dep 5 DOB': '',
                'Dep 6 DOB': '',
                'Monthly Income': '$7,500',
                'Current EE Monthly': '$425',      # Family tier - higher contribution
                'Current ER Monthly': '$1,705',    # ~80% of family premium
                '2026 Premium': '$2,911.16',       # Projected 2026 renewal (from rate table)
                'Gap Insurance': '$112',           # Employer gap insurance monthly cost
            },
            {
                'Employee Number': 'EMP002',
                'Last Name': 'Johnson',
                'First Name': 'Sarah',
                'Home Zip': '60601',
                'Home State': 'IL',
                'Family Status': 'ES',
                'EE DOB': '12/03/1978',
                'Spouse DOB': '06/18/1980',
                'Dep 2 DOB': '',
                'Dep 3 DOB': '',
                'Dep 4 DOB': '',
                'Dep 5 DOB': '',
                'Dep 6 DOB': '',
                'Monthly Income': '$5,200.50',
                'Current EE Monthly': '$350',
                'Current ER Monthly': '$1,400',
                '2026 Premium': '$1,967.67',       # Projected 2026 renewal
                'Gap Insurance': '$85',            # Employer gap insurance
            },
            {
                'Employee Number': 'EMP003',
                'Last Name': 'Williams',
                'First Name': 'Michael',
                'Home Zip': '18801',
                'Home State': 'PA',
                'Family Status': 'EC',
                'EE DOB': '08/25/1990',
                'Spouse DOB': '',
                'Dep 2 DOB': '02/14/2018',
                'Dep 3 DOB': '',
                'Dep 4 DOB': '',
                'Dep 5 DOB': '',
                'Dep 6 DOB': '',
                'Monthly Income': '4500',
                'Current EE Monthly': '275',       # Without $ sign - also valid
                'Current ER Monthly': '1100',
                '2026 Premium': '1747.71',         # Without $ sign - also valid
                'Gap Insurance': '',               # Optional - can be empty
            },
            {
                'Employee Number': 'EMP004',
                'Last Name': 'Brown',
                'First Name': 'Emily',
                'Home Zip': '33101',
                'Home State': 'FL',
                'Family Status': 'EE',
                'EE DOB': '10/30/1995',
                'Spouse DOB': '',
                'Dep 2 DOB': '',
                'Dep 3 DOB': '',
                'Dep 4 DOB': '',
                'Dep 5 DOB': '',
                'Dep 6 DOB': '',
                'Monthly Income': '',              # Optional - can be empty
                'Current EE Monthly': '',          # Optional - can be empty
                'Current ER Monthly': '',
                '2026 Premium': '',                # Optional - can be empty
                'Gap Insurance': '',               # Optional - can be empty
            }
        ]

        # Convert to DataFrame
        template_df = pd.DataFrame(examples, columns=headers)

        # Return as CSV string
        return template_df.to_csv(index=False)

    @staticmethod
    def create_sample_new_census(num_employees: int = 20) -> pd.DataFrame:
        """
        Create sample census data in new format for testing

        Args:
            num_employees: Number of sample employees

        Returns:
            Sample census DataFrame in new format
        """
        from datetime import date, timedelta
        import random

        np.random.seed(42)
        random.seed(42)

        # Sample ZIP codes by state
        sample_zips = {
            'NY': ['10001', '11201', '14201', '13210'],  # NYC, Brooklyn, Buffalo, Syracuse
            'PA': ['18801', '19019', '15219', '17101'],  # Montrose, Philadelphia, Pittsburgh, Harrisburg
            'IL': ['60601', '60007', '61801', '62901'],  # Chicago, Elk Grove, Champaign, Carbondale
            'FL': ['33101', '33160', '32801', '33301']   # Miami, N. Miami, Orlando, Ft Lauderdale
        }

        employees = []

        for i in range(num_employees):
            # Random state
            state = random.choice(list(sample_zips.keys()))
            zip_code = random.choice(sample_zips[state])

            # Random Family Status
            family_status = random.choice(['EE', 'ES', 'EC', 'F'])

            # Random employee age (25-60)
            ee_age = random.randint(25, 60)
            ee_birth_year = 2026 - ee_age
            ee_dob = f"{random.randint(1,12):02d}/{random.randint(1,28):02d}/{ee_birth_year}"

            # Build employee record
            employee = {
                'Employee Number': f'EMP{i+1:03d}',
                'Home Zip': zip_code,
                'Home State': state,
                'Family Status': family_status,
                'EE DOB': ee_dob,
                'Spouse DOB': '',
                'Dep 2 DOB': '',
                'Dep 3 DOB': '',
                'Dep 4 DOB': '',
                'Dep 5 DOB': '',
                'Dep 6 DOB': ''
            }

            # Add spouse if ES or F
            if family_status in ['ES', 'F']:
                spouse_age = random.randint(25, 60)
                spouse_birth_year = 2026 - spouse_age
                employee['Spouse DOB'] = f"{random.randint(1,12):02d}/{random.randint(1,28):02d}/{spouse_birth_year}"

            # Add children if EC or F
            if family_status in ['EC', 'F']:
                num_children = random.randint(1, 3)
                for child_num in range(num_children):
                    child_age = random.randint(0, 18)
                    child_birth_year = 2026 - child_age
                    employee[f'Dep {child_num+2} DOB'] = f"{random.randint(1,12):02d}/{random.randint(1,28):02d}/{child_birth_year}"

            employees.append(employee)

        return pd.DataFrame(employees)

    @staticmethod
    def parse_census_with_dependents(
        employees_df: pd.DataFrame,
        dependents_df: Optional[pd.DataFrame] = None
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Parse census data with dependents

        Args:
            employees_df: Employee census DataFrame
            dependents_df: Optional separate dependents DataFrame

        Returns:
            Tuple of (employees_df, dependents_df)
        """
        # If dependents_df not provided, check if employees_df has dependent columns
        if dependents_df is None:
            # Check for denormalized format (has_spouse, spouse_age, etc.)
            if 'has_spouse' in employees_df.columns:
                # Convert denormalized to normalized
                dependents_df = CensusProcessor._denormalize_to_normalized(employees_df)
            else:
                # No dependents
                dependents_df = pd.DataFrame(columns=[
                    'dependent_id', 'employee_id', 'relationship', 'age'
                ])

        # Add has_dependents flag to employees
        if not dependents_df.empty:
            dep_counts = dependents_df.groupby('employee_id').size()
            employees_df['has_dependents'] = employees_df['employee_id'].isin(dep_counts.index)
            employees_df['num_dependents'] = employees_df['employee_id'].map(dep_counts).fillna(0).astype(int)
        else:
            employees_df['has_dependents'] = False
            employees_df['num_dependents'] = 0

        return employees_df, dependents_df

    @staticmethod
    def _denormalize_to_normalized(employees_df: pd.DataFrame) -> pd.DataFrame:
        """
        Convert denormalized census (has_spouse, child_1_age columns)
        to normalized dependents table
        """
        dependents_records = []

        for _, emp in employees_df.iterrows():
            employee_id = emp['employee_id']

            # Add spouse if exists
            if emp.get('has_spouse', False) and pd.notna(emp.get('spouse_age')):
                dependents_records.append({
                    'dependent_id': f"{employee_id}_spouse",
                    'employee_id': employee_id,
                    'relationship': 'spouse',
                    'age': int(emp['spouse_age'])
                })

            # Add children
            if emp.get('num_children', 0) > 0:
                for i in range(1, int(emp['num_children']) + 1):
                    child_age_col = f'child_{i}_age'
                    if child_age_col in emp and pd.notna(emp[child_age_col]):
                        dependents_records.append({
                            'dependent_id': f"{employee_id}_child{i}",
                            'employee_id': employee_id,
                            'relationship': 'child',
                            'age': int(emp[child_age_col])
                        })

        return pd.DataFrame(dependents_records)

    @staticmethod
    def create_sample_census_with_dependents(num_employees: int = 10) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Create sample census with dependents for testing

        Returns:
            Tuple of (employees_df, dependents_df)
        """
        np.random.seed(42)

        # Create employees
        employees = CensusProcessor.create_sample_census(num_employees)
        employees.rename(columns={'age': 'employee_age'}, inplace=True)

        # Create dependents
        dependents_records = []

        for _, emp in employees.iterrows():
            employee_id = emp['employee_id']

            # 60% chance of having spouse
            if np.random.random() < 0.6:
                spouse_age = np.random.randint(25, 65)
                dependents_records.append({
                    'dependent_id': f"{employee_id}_spouse",
                    'employee_id': employee_id,
                    'relationship': 'spouse',
                    'age': spouse_age
                })

            # Random number of children (0-3)
            num_children = np.random.choice([0, 0, 1, 1, 2, 3], p=[0.3, 0.1, 0.3, 0.1, 0.15, 0.05])

            for i in range(num_children):
                child_age = np.random.randint(0, 18)
                dependents_records.append({
                    'dependent_id': f"{employee_id}_child{i+1}",
                    'employee_id': employee_id,
                    'relationship': 'child',
                    'age': child_age
                })

        dependents_df = pd.DataFrame(dependents_records)

        return employees, dependents_df

    @staticmethod
    def validate_dependents_csv(df: pd.DataFrame) -> Tuple[bool, str]:
        """
        Validate uploaded dependents CSV

        Returns:
            Tuple of (is_valid, error_message)
        """
        required_columns = ['employee_id', 'relationship', 'age']

        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            return False, f"Missing required columns: {', '.join(missing_columns)}"

        # Validate relationship values
        valid_relationships = ['spouse', 'child']
        invalid_relationships = df[~df['relationship'].str.lower().isin(valid_relationships)]

        if not invalid_relationships.empty:
            return False, "Invalid relationship values. Must be 'spouse' or 'child'"

        # Validate ages
        if df['age'].min() < 0 or df['age'].max() > 120:
            return False, "Age values must be between 0 and 120"

        # Check for multiple spouses per employee
        spouse_counts = df[df['relationship'].str.lower() == 'spouse'].groupby('employee_id').size()
        multiple_spouses = spouse_counts[spouse_counts > 1]

        if not multiple_spouses.empty:
            return False, f"Employees cannot have multiple spouses: {multiple_spouses.index.tolist()}"

        return True, ""


class ComparisonCalculator:
    """Calculate comparisons between current group plan and ICHRA plans"""

    @staticmethod
    def calculate_savings(current_group_cost: float, ichra_cost: float) -> Dict:
        """
        Calculate savings when switching from group plan to ICHRA

        Args:
            current_group_cost: Current annual group plan cost
            ichra_cost: ICHRA annual cost (employer contribution)

        Returns:
            Dictionary with savings metrics
        """
        savings_amount = current_group_cost - ichra_cost
        savings_pct = (savings_amount / current_group_cost * 100) if current_group_cost > 0 else 0

        return {
            'current_group_annual_cost': current_group_cost,
            'ichra_annual_cost': ichra_cost,
            'annual_savings': savings_amount,
            'savings_percentage': savings_pct,
            'is_cost_reduction': savings_amount > 0
        }

    @staticmethod
    def compare_plan_benefits(group_plan_benefits: Dict, ichra_plan_benefits: pd.DataFrame) -> pd.DataFrame:
        """
        Create side-by-side benefit comparison

        Args:
            group_plan_benefits: Dictionary of current group plan benefits
            ichra_plan_benefits: DataFrame of ICHRA plan benefits

        Returns:
            Comparison DataFrame
        """
        comparison_data = []

        benefit_mapping = {
            'deductible_individual': 'Individual Deductible',
            'deductible_family': 'Family Deductible',
            'moop_individual': 'Individual MOOP',
            'moop_family': 'Family MOOP',
            'pcp_copay': 'PCP Visit',
            'specialist_copay': 'Specialist Visit',
            'generic_drug_copay': 'Generic Drugs',
            'er_copay': 'Emergency Room'
        }

        for key, label in benefit_mapping.items():
            comparison_data.append({
                'Benefit': label,
                'Current Group Plan': group_plan_benefits.get(key, 'N/A'),
                'ICHRA Plan': 'TBD'  # Will be filled from ichra_plan_benefits
            })

        return pd.DataFrame(comparison_data)


class CostAggregator:
    """Multi-dimensional cost aggregation for ICHRA analysis"""

    @staticmethod
    def aggregate_multidimensional_costs(
        census_df: pd.DataFrame,
        dependents_df: Optional[pd.DataFrame],
        plan_rates: pd.DataFrame,
        selected_plans_metadata: List[Dict],
        employee_contribution_pct: float,
        dependent_contribution_pct: float = None,
        dependent_contribution_strategy: str = "Same as employee",
        dependent_contribution_amount: float = 0.0
    ) -> Dict:
        """
        Calculate and aggregate ICHRA costs across multiple dimensions

        Args:
            census_df: Employee census dataframe
            dependents_df: Dependents dataframe (can be None)
            plan_rates: Premium rates dataframe
            selected_plans_metadata: List of plan dicts with keys: plan_id, state, metal_level, plan_name
            employee_contribution_pct: Employer contribution percentage for employees
            dependent_contribution_pct: Employer contribution percentage for dependents
            dependent_contribution_strategy: How to handle dependent contributions
            dependent_contribution_amount: Fixed dollar amount for dependent contributions

        Returns:
            Dictionary containing:
                - totals: Overall cost summary
                - by_state: Costs aggregated by state
                - by_metal_level: Costs aggregated by metal level
                - by_family_composition: Costs aggregated by family composition
                - by_plan: Costs aggregated by individual plan
                - detailed_breakdown: Full breakdown with all dimensions
                - coverage_report: Coverage gaps and warnings
        """
        from constants import FAMILY_STATUS_CODES

        # Build plan lookup by state
        plans_by_state = {}
        for plan in selected_plans_metadata:
            state = plan['state']
            if state not in plans_by_state:
                plans_by_state[state] = []
            plans_by_state[state].append(plan)

        # Initialize result collectors
        detailed_rows = []
        employee_plan_assignments = {}  # employee_id -> assigned_plan_id
        uncovered_employees = []

        # Process each employee
        for _, emp in census_df.iterrows():
            employee_id = emp.get('employee_id', 'N/A')
            emp_state = emp['state']
            rating_area = emp.get('rating_area_id', 0)
            emp_age = emp.get('age', 30)
            family_status = emp.get('family_status', 'EE')

            # Get dependents for this employee
            if dependents_df is not None and not dependents_df.empty:
                family_deps = dependents_df[dependents_df['employee_id'] == employee_id]
            else:
                family_deps = pd.DataFrame()

            # Determine family composition
            has_spouse = not family_deps[family_deps['relationship'] == 'spouse'].empty
            num_children = len(family_deps[family_deps['relationship'] == 'child'])
            family_comp = PremiumCalculator._get_family_composition_label(has_spouse, num_children)

            # Find applicable plans for this employee's state
            applicable_plans = plans_by_state.get(emp_state, [])

            if not applicable_plans:
                # Employee has no available plan in their state
                uncovered_employees.append({
                    'employee_id': employee_id,
                    'state': emp_state,
                    'reason': 'No plans selected for state'
                })
                continue

            # Calculate cost for each applicable plan and choose best (max premium = best coverage)
            plan_costs = []
            for plan in applicable_plans:
                plan_id = plan['plan_id']

                # Calculate employee premium
                emp_premium = PremiumCalculator.calculate_employee_premium(
                    age=emp_age,
                    premium_rates=plan_rates,
                    plan_id=plan_id,
                    rating_area=rating_area,
                    state_code=emp_state,
                    rating_area_source=f'census_employee_{employee_id}'
                )

                # Calculate dependent premiums
                dep_premium = 0.0
                if not family_deps.empty:
                    for _, dep in family_deps.iterrows():
                        dep_prem = PremiumCalculator.calculate_employee_premium(
                            age=dep['age'],
                            premium_rates=plan_rates,
                            plan_id=plan_id,
                            rating_area=rating_area,
                            state_code=emp_state,
                            rating_area_source=f'census_dependent_of_{employee_id}'
                        )
                        dep_premium += dep_prem

                # Calculate employer contributions
                total_premium = emp_premium + dep_premium

                # Percentage-based contribution
                emp_employer_contrib = PremiumCalculator.calculate_employer_contribution(
                    emp_premium, employee_contribution_pct
                )
                # Determine dependent contribution value based on strategy
                if dependent_contribution_strategy == "Same as employee":
                    dep_contrib_value = employee_contribution_pct  # Use same % as employee
                elif dependent_contribution_strategy == "Different percentage":
                    dep_contrib_value = dependent_contribution_pct
                else:  # "Fixed dollar amount" or "No contribution"
                    dep_contrib_value = dependent_contribution_amount

                dep_employer_contrib = PremiumCalculator.calculate_dependent_contribution(
                    dep_premium,
                    dependent_contribution_strategy,
                    dep_contrib_value,
                    len(family_deps)
                )
                total_employer_contrib = emp_employer_contrib + dep_employer_contrib
                # Ensure employee cost never goes negative (employer can pay up to 100%)
                total_employee_cost = max(0.0, total_premium - total_employer_contrib)

                plan_costs.append({
                    'plan': plan,
                    'total_premium': total_premium,
                    'emp_premium': emp_premium,
                    'dep_premium': dep_premium,
                    'employer_contrib': total_employer_contrib,
                    'employee_cost': total_employee_cost
                })

            # Choose best plan (highest premium = best coverage value)
            if plan_costs:
                best_plan = max(plan_costs, key=lambda x: x['total_premium'])
                employee_plan_assignments[employee_id] = best_plan['plan']['plan_id']

                # Check if premium is $0.00 and log as uncovered if so
                if best_plan['total_premium'] == 0.0:
                    uncovered_employees.append({
                        'employee_id': employee_id,
                        'state': emp_state,
                        'rating_area': rating_area,
                        'reason': f'No rates found for rating area {rating_area} in selected plans'
                    })

                # Add to detailed breakdown
                detailed_rows.append({
                    'employee_id': employee_id,
                    'state': emp_state,
                    'plan_id': best_plan['plan']['plan_id'],
                    'plan_name': best_plan['plan']['plan_name'],
                    'metal_level': best_plan['plan']['metal_level'],
                    'plan_type': best_plan['plan']['plan_type'],
                    'family_composition': family_comp,
                    'family_status_code': family_status,
                    'num_dependents': len(family_deps),
                    'employee_age': emp_age,
                    'total_monthly_premium': best_plan['total_premium'],
                    'employee_monthly_premium': best_plan['emp_premium'],
                    'dependent_monthly_premium': best_plan['dep_premium'],
                    'employer_monthly_contribution': best_plan['employer_contrib'],
                    'employee_monthly_cost': best_plan['employee_cost'],
                    'total_annual_premium': best_plan['total_premium'] * 12,
                    'employer_annual_contribution': best_plan['employer_contrib'] * 12,
                    'employee_annual_cost': best_plan['employee_cost'] * 12
                })

        # Convert detailed rows to DataFrame
        detailed_df = pd.DataFrame(detailed_rows)

        if detailed_df.empty:
            # Return empty structure if no costs calculated
            return {
                'totals': {},
                'by_state': pd.DataFrame(),
                'by_metal_level': pd.DataFrame(),
                'by_family_composition': pd.DataFrame(),
                'by_plan': pd.DataFrame(),
                'detailed_breakdown': pd.DataFrame(),
                'coverage_report': {
                    'total_employees': len(census_df),
                    'covered_employees': 0,
                    'uncovered_employees': len(uncovered_employees),
                    'coverage_percentage': 0.0,
                    'uncovered_details': uncovered_employees
                }
            }

        # Calculate totals
        totals = {
            'total_employees': len(detailed_df),
            'total_dependents': int(detailed_df['num_dependents'].sum()),
            'total_covered_lives': len(detailed_df) + int(detailed_df['num_dependents'].sum()),
            'total_monthly_premium': float(detailed_df['total_monthly_premium'].sum()),
            'total_annual_premium': float(detailed_df['total_annual_premium'].sum()),
            'total_monthly_employer_contribution': float(detailed_df['employer_monthly_contribution'].sum()),
            'total_annual_employer_contribution': float(detailed_df['employer_annual_contribution'].sum()),
            'total_monthly_employee_cost': float(detailed_df['employee_monthly_cost'].sum()),
            'total_annual_employee_cost': float(detailed_df['employee_annual_cost'].sum()),
            'avg_monthly_premium_per_employee': float(detailed_df['total_monthly_premium'].mean()),
            'avg_monthly_employer_contribution_per_employee': float(detailed_df['employer_monthly_contribution'].mean()),
            'avg_monthly_employee_cost_per_employee': float(detailed_df['employee_monthly_cost'].mean())
        }

        # Aggregate by state
        by_state = detailed_df.groupby('state').agg({
            'employee_id': 'count',
            'num_dependents': 'sum',
            'total_monthly_premium': 'sum',
            'total_annual_premium': 'sum',
            'employer_monthly_contribution': 'sum',
            'employer_annual_contribution': 'sum',
            'employee_monthly_cost': 'sum',
            'employee_annual_cost': 'sum'
        }).rename(columns={'employee_id': 'employee_count'}).reset_index()

        # Add percentage of total
        total_cost = by_state['total_annual_premium'].sum()
        if total_cost > 0:
            by_state['percentage_of_total_cost'] = by_state['total_annual_premium'] / total_cost * 100
        else:
            by_state['percentage_of_total_cost'] = 0.0

        # Aggregate by metal level
        by_metal = detailed_df.groupby('metal_level').agg({
            'employee_id': 'count',
            'num_dependents': 'sum',
            'total_monthly_premium': ['sum', 'mean'],
            'total_annual_premium': 'sum',
            'employer_monthly_contribution': 'sum',
            'employer_annual_contribution': 'sum',
            'employee_monthly_cost': 'sum',
            'employee_annual_cost': 'sum'
        })
        by_metal.columns = ['_'.join(col).strip('_') for col in by_metal.columns.values]
        by_metal = by_metal.rename(columns={'employee_id_count': 'employee_count', 'num_dependents_sum': 'total_dependents'})
        by_metal = by_metal.reset_index()

        # Aggregate by family composition
        by_family = detailed_df.groupby('family_composition').agg({
            'employee_id': 'count',
            'num_dependents': 'sum',
            'total_monthly_premium': ['sum', 'mean'],
            'total_annual_premium': 'sum',
            'employer_monthly_contribution': 'sum',
            'employer_annual_contribution': 'sum',
            'employee_monthly_cost': 'sum',
            'employee_annual_cost': 'sum'
        })
        by_family.columns = ['_'.join(col).strip('_') for col in by_family.columns.values]
        by_family = by_family.rename(columns={'employee_id_count': 'employee_count', 'num_dependents_sum': 'total_dependents'})
        by_family = by_family.reset_index()

        # Aggregate by plan
        by_plan = detailed_df.groupby(['plan_id', 'plan_name', 'state', 'metal_level']).agg({
            'employee_id': 'count',
            'num_dependents': 'sum',
            'total_monthly_premium': ['sum', 'mean'],
            'total_annual_premium': 'sum',
            'employer_monthly_contribution': 'sum',
            'employer_annual_contribution': 'sum',
            'employee_monthly_cost': 'sum',
            'employee_annual_cost': 'sum'
        })
        by_plan.columns = ['_'.join(col).strip('_') for col in by_plan.columns.values]
        by_plan = by_plan.rename(columns={'employee_id_count': 'employee_count', 'num_dependents_sum': 'total_dependents'})
        by_plan = by_plan.reset_index()

        # Coverage report
        coverage_report = {
            'total_employees': len(census_df),
            'covered_employees': len(detailed_df),
            'uncovered_employees': len(uncovered_employees),
            'coverage_percentage': (len(detailed_df) / len(census_df) * 100) if len(census_df) > 0 else 0,
            'uncovered_details': uncovered_employees
        }

        return {
            'totals': totals,
            'by_state': by_state,
            'by_metal_level': by_metal,
            'by_family_composition': by_family,
            'by_plan': by_plan,
            'detailed_breakdown': detailed_df,
            'coverage_report': coverage_report,
            'employee_plan_assignments': employee_plan_assignments
        }


class DataFormatter:
    """Format data for display in Streamlit"""

    @staticmethod
    def format_currency(amount: float, include_sign: bool = False) -> str:
        """Format number as currency

        Args:
            amount: Dollar amount to format
            include_sign: If True, include + or - sign for positive/negative values
        """
        if include_sign:
            if amount >= 0:
                return f"+${amount:,.2f}"
            else:
                return f"-${abs(amount):,.2f}"
        return f"${amount:,.2f}"

    @staticmethod
    def format_percentage(pct: float) -> str:
        """Format number as percentage"""
        return f"{pct:.1f}%"

    @staticmethod
    def format_plan_name(plan_name: str, max_length: int = 50) -> str:
        """Truncate long plan names"""
        if len(plan_name) > max_length:
            return plan_name[:max_length-3] + "..."
        return plan_name

    @staticmethod
    def wrap_plan_name(plan_name: str, width: int = 30, html: bool = False) -> str:
        """
        Wrap long plan names for better display in tables and charts

        Args:
            plan_name: Full plan name (e.g., "12345XX0123456 - Plan Name (Metal Level)")
            width: Maximum characters per line
            html: If True, use <br> for HTML/Plotly; if False, use \n for text

        Returns:
            Wrapped plan name with line breaks
        """
        if len(plan_name) <= width:
            return plan_name

        # Try to break at natural points: " - " or " (" or spaces
        parts = []
        current_line = ""

        # Split by words
        words = plan_name.split()

        for word in words:
            # If adding this word would exceed width
            if len(current_line) + len(word) + 1 > width:
                if current_line:  # Save current line
                    parts.append(current_line.strip())
                    current_line = word
                else:  # Word itself is too long, just add it
                    parts.append(word)
                    current_line = ""
            else:
                current_line += (" " + word) if current_line else word

        # Add remaining text
        if current_line:
            parts.append(current_line.strip())

        # Join with appropriate line break
        separator = "<br>" if html else "\n"
        return separator.join(parts)

    @staticmethod
    def pivot_deductibles(deductibles_df: pd.DataFrame) -> Dict:
        """
        Pivot deductible DataFrame to dictionary format

        Args:
            deductibles_df: DataFrame from get_plan_deductibles_moop query

        Returns:
            Dictionary with deductible/MOOP values
        """
        if deductibles_df.empty:
            return {}

        result = {}

        for _, row in deductibles_df.iterrows():
            ded_type = row['deductible_type']
            individual_amt = row.get('individual_amount', 'N/A')
            family_amt = row.get('family_per_group', 'N/A')

            if 'Medical' in ded_type and 'Deductible' in ded_type:
                result['medical_deductible_individual'] = individual_amt
                result['medical_deductible_family'] = family_amt
            elif 'Drug' in ded_type and 'Deductible' in ded_type:
                result['drug_deductible_individual'] = individual_amt
                result['drug_deductible_family'] = family_amt
            elif 'Medical' in ded_type and 'Maximum' in ded_type:
                result['medical_moop_individual'] = individual_amt
                result['medical_moop_family'] = family_amt
            elif 'Drug' in ded_type and 'Maximum' in ded_type:
                result['drug_moop_individual'] = individual_amt
                result['drug_moop_family'] = family_amt

        return result

    @staticmethod
    def pivot_benefits(benefits_df: pd.DataFrame) -> Dict:
        """
        Pivot benefits DataFrame to dictionary format

        Args:
            benefits_df: DataFrame from get_plan_benefits query

        Returns:
            Dictionary with benefit cost-sharing values
        """
        if benefits_df.empty:
            return {}

        result = {}

        benefit_key_mapping = {
            'Primary Care Visit to Treat an Injury or Illness': 'pcp_visit',
            'Specialist Visit': 'specialist_visit',
            'Generic Drugs': 'generic_drugs',
            'Preferred Brand Drugs': 'preferred_brand_drugs',
            'Emergency Room Services': 'er_services',
            'Inpatient Hospital Services': 'inpatient_hospital'
        }

        for _, row in benefits_df.iterrows():
            benefit_name = row['benefit']
            key = benefit_key_mapping.get(benefit_name)

            if key:
                copay = row.get('copay', 'Not Applicable')
                coinsurance = row.get('coinsurance', 'Not Applicable')

                if copay != 'Not Applicable':
                    result[f'{key}_copay'] = copay
                if coinsurance != 'Not Applicable':
                    result[f'{key}_coinsurance'] = coinsurance

        return result


class SavingsFormatter:
    """
    Standardized formatting for savings/cost comparisons across the app.

    Convention:
    - Positive values = savings (good) → "$X saved"
    - Negative values = costs more (bad) → "$X more"
    - Zero = "no change"

    Usage:
        from utils import SavingsFormatter

        # Basic formatting
        SavingsFormatter.format(1500)      # "$1,500 saved"
        SavingsFormatter.format(-1500)     # "$1,500 more"

        # With percentage
        SavingsFormatter.format_with_pct(1500, 15.5)  # "$1,500 saved (15.5%)"

        # For ER-only fine print
        SavingsFormatter.format_er_only(1500)   # "ER only: $1,500 saved"

        # For Streamlit metrics
        delta, color = SavingsFormatter.for_metric(1500)
    """

    @staticmethod
    def format(amount: float, decimals: int = 0) -> str:
        """
        Format a savings/cost amount.

        Args:
            amount: Positive = savings, Negative = costs more
            decimals: Number of decimal places (default 0)

        Returns:
            "$X saved", "$X more", or "no change"
        """
        if amount > 0:
            return f"${amount:,.{decimals}f} saved"
        elif amount < 0:
            return f"${abs(amount):,.{decimals}f} more"
        else:
            return "no change"

    @staticmethod
    def format_with_pct(amount: float, pct: float, decimals: int = 0) -> str:
        """
        Format amount with percentage.

        Args:
            amount: Positive = savings, Negative = costs more
            pct: Percentage (will show absolute value)
            decimals: Number of decimal places for amount

        Returns:
            "$X saved (Y%)", "$X more (Y%)", or "no change"
        """
        if amount > 0:
            return f"${amount:,.{decimals}f} saved ({abs(pct):.1f}%)"
        elif amount < 0:
            return f"${abs(amount):,.{decimals}f} more ({abs(pct):.1f}%)"
        else:
            return "no change"

    @staticmethod
    def format_er_only(amount: float, decimals: int = 0) -> str:
        """
        Format for ER-only fine print display.

        Args:
            amount: Positive = savings, Negative = costs more
            decimals: Number of decimal places

        Returns:
            "ER only: $X saved", "ER only: $X more", or "ER only: no change"
        """
        if amount > 0:
            return f"ER only: ${amount:,.{decimals}f} saved"
        elif amount < 0:
            return f"ER only: ${abs(amount):,.{decimals}f} more"
        else:
            return "ER only: no change"

    @staticmethod
    def format_short(amount: float, decimals: int = 0) -> str:
        """
        Short format without 'saved'/'more' - just the signed amount.

        Args:
            amount: Positive = savings (shows as-is), Negative = costs more
            decimals: Number of decimal places

        Returns:
            "$X" (positive) or "+$X" (negative/costs more)
        """
        if amount > 0:
            return f"${amount:,.{decimals}f}"
        elif amount < 0:
            return f"+${abs(amount):,.{decimals}f}"
        else:
            return "$0"

    @staticmethod
    def for_metric(amount: float, decimals: int = 0) -> tuple:
        """
        Get delta text and color for Streamlit st.metric().

        Args:
            amount: Positive = savings, Negative = costs more
            decimals: Number of decimal places

        Returns:
            Tuple of (delta_text, delta_color)
            - Savings: ("$X saved", "normal") - shows green
            - Costs more: ("$X more", "inverse") - shows red
        """
        if amount > 0:
            return (f"${amount:,.{decimals}f} saved", "normal")
        elif amount < 0:
            return (f"${abs(amount):,.{decimals}f} more", "inverse")
        else:
            return ("no change", "off")

    @staticmethod
    def for_metric_with_pct(amount: float, pct: float, decimals: int = 0) -> tuple:
        """
        Get delta text with percentage and color for Streamlit st.metric().

        Args:
            amount: Positive = savings, Negative = costs more
            pct: Percentage to display
            decimals: Number of decimal places

        Returns:
            Tuple of (delta_text, delta_color)
        """
        if amount > 0:
            return (f"{abs(pct):.1f}% saved", "normal")
        elif amount < 0:
            return (f"{abs(pct):.1f}% more", "inverse")
        else:
            return ("no change", "off")

    @staticmethod
    def format_comparison(amount: float, label: str = "", decimals: int = 0) -> str:
        """
        Format for comparison displays (e.g., "vs Current: $X saved").

        Args:
            amount: Positive = savings, Negative = costs more
            label: Optional label (e.g., "vs Current", "vs Renewal")
            decimals: Number of decimal places

        Returns:
            "vs Current: $X saved" or "vs Current: $X more"
        """
        prefix = f"{label}: " if label else ""
        if amount > 0:
            return f"{prefix}${amount:,.{decimals}f} saved"
        elif amount < 0:
            return f"{prefix}${abs(amount):,.{decimals}f} more"
        else:
            return f"{prefix}no change"


class ContributionComparison:
    """Compare current group plan contributions vs ICHRA costs"""

    @staticmethod
    def has_individual_contributions(census_df: pd.DataFrame) -> bool:
        """
        Check if census has per-employee contribution data.

        Args:
            census_df: Employee census DataFrame

        Returns:
            True if at least one employee has current_ee_monthly or current_er_monthly data
        """
        if census_df is None or census_df.empty:
            return False

        has_ee = 'current_ee_monthly' in census_df.columns and census_df['current_ee_monthly'].notna().any()
        has_er = 'current_er_monthly' in census_df.columns and census_df['current_er_monthly'].notna().any()
        return has_ee or has_er

    @staticmethod
    def aggregate_contribution_totals(census_df: pd.DataFrame) -> Dict:
        """
        Sum current contributions from all employees with data.

        Args:
            census_df: Employee census DataFrame with current_ee_monthly and current_er_monthly columns

        Returns:
            Dict with:
                - employees_with_data: Number of employees with contribution data
                - total_current_ee_monthly: Sum of all EE contributions
                - total_current_er_monthly: Sum of all ER contributions
                - total_current_ee_annual: Annual EE total
                - total_current_er_annual: Annual ER total
                - total_gap_insurance_monthly: Sum of all gap insurance costs
                - total_gap_insurance_annual: Annual gap insurance total
        """
        if census_df is None or census_df.empty:
            return {
                'employees_with_data': 0,
                'total_current_ee_monthly': 0.0,
                'total_current_er_monthly': 0.0,
                'total_current_ee_annual': 0.0,
                'total_current_er_annual': 0.0,
                'total_gap_insurance_monthly': 0.0,
                'total_gap_insurance_annual': 0.0,
            }

        # Get totals, treating NaN as 0
        total_ee = 0.0
        total_er = 0.0
        total_gap = 0.0

        if 'current_ee_monthly' in census_df.columns:
            total_ee = pd.to_numeric(census_df['current_ee_monthly'], errors='coerce').fillna(0).sum()

        if 'current_er_monthly' in census_df.columns:
            total_er = pd.to_numeric(census_df['current_er_monthly'], errors='coerce').fillna(0).sum()

        if 'gap_insurance_monthly' in census_df.columns:
            total_gap = pd.to_numeric(census_df['gap_insurance_monthly'], errors='coerce').fillna(0).sum()

        # Count employees with any contribution data
        employees_with_data = 0
        if 'current_ee_monthly' in census_df.columns or 'current_er_monthly' in census_df.columns:
            has_ee = census_df.get('current_ee_monthly', pd.Series()).notna()
            has_er = census_df.get('current_er_monthly', pd.Series()).notna()
            employees_with_data = (has_ee | has_er).sum()

        return {
            'employees_with_data': int(employees_with_data),
            'total_current_ee_monthly': float(total_ee),
            'total_current_er_monthly': float(total_er),
            'total_current_ee_annual': float(total_ee * 12),
            'total_current_er_annual': float(total_er * 12),
            'total_gap_insurance_monthly': float(total_gap),
            'total_gap_insurance_annual': float(total_gap * 12),
        }

    @staticmethod
    def calculate_employee_comparison(
        current_ee_monthly: float,
        current_er_monthly: float,
        ichra_ee_monthly: float,
        ichra_er_monthly: float,
    ) -> Dict:
        """
        Calculate comparison between current and ICHRA costs for a single employee.

        Args:
            current_ee_monthly: Employee's current monthly contribution (or None)
            current_er_monthly: Employer's current monthly contribution (or None)
            ichra_ee_monthly: Employee's ICHRA monthly cost
            ichra_er_monthly: Employer's ICHRA monthly contribution

        Returns:
            Dict with current values, ICHRA values, and changes (monthly/annual)
        """
        result = {
            'current_ee_monthly': current_ee_monthly,
            'current_er_monthly': current_er_monthly,
            'ichra_ee_monthly': ichra_ee_monthly,
            'ichra_er_monthly': ichra_er_monthly,
            'ee_change_monthly': None,
            'er_change_monthly': None,
            'ee_change_annual': None,
            'er_change_annual': None,
        }

        if current_ee_monthly is not None and not pd.isna(current_ee_monthly):
            result['ee_change_monthly'] = ichra_ee_monthly - current_ee_monthly
            result['ee_change_annual'] = result['ee_change_monthly'] * 12

        if current_er_monthly is not None and not pd.isna(current_er_monthly):
            result['er_change_monthly'] = ichra_er_monthly - current_er_monthly
            result['er_change_annual'] = result['er_change_monthly'] * 12

        return result

    @staticmethod
    def detect_contribution_pattern(census_df: pd.DataFrame):
        """
        Detect whether employer uses percentage-based or flat-rate contributions per tier.

        Analyzes Current EE Monthly and Current ER Monthly columns grouped by Family Status
        to determine the contribution pattern for each tier (EE, ES, EC, F).

        Args:
            census_df: Employee census DataFrame with current_ee_monthly, current_er_monthly,
                      and family_status columns

        Returns:
            ContributionPatternResult from contribution_pattern_detector module
        """
        from contribution_pattern_detector import detect_contribution_pattern
        return detect_contribution_pattern(census_df)

    @staticmethod
    def apply_contribution_pattern(census_df: pd.DataFrame, pattern_result):
        """
        Apply detected contribution pattern to calculate 2026 renewal ER/EE projections.

        For each employee, applies their tier's detected pattern to calculate
        projected_2026_er and projected_2026_ee columns.

        Args:
            census_df: Census DataFrame with projected_2026_premium and family_status
            pattern_result: ContributionPatternResult from detect_contribution_pattern()

        Returns:
            Census DataFrame with projected_2026_er and projected_2026_ee columns added
        """
        from contribution_pattern_detector import apply_pattern_to_renewal
        return apply_pattern_to_renewal(census_df, pattern_result)


class WorkforceFitAnalyzer:
    """Analyze census demographics to generate strategic workforce insights"""

    @staticmethod
    def analyze_census(census_df: pd.DataFrame) -> Dict:
        """
        Analyze census demographics and return strategic insights

        Args:
            census_df: Employee census DataFrame with columns:
                - 'EE Age' or 'age': Employee age
                - 'Home State' or 'state': Employee state
                - 'rating_area_id': Rating area (if available)
                - 'family_status': Family status code (if available)

        Returns:
            Dictionary with demographic insights and strategic recommendations
        """
        # Normalize column names (handle both 'EE Age' and 'age' formats)
        age_col = 'EE Age' if 'EE Age' in census_df.columns else 'age'
        state_col = 'Home State' if 'Home State' in census_df.columns else 'state'

        total_employees = len(census_df)

        # Age analysis
        avg_age = census_df[age_col].mean()
        min_age = census_df[age_col].min()
        max_age = census_df[age_col].max()

        # Age distribution buckets
        young_workforce_count = len(census_df[census_df[age_col] < 45])
        young_workforce_pct = young_workforce_count / total_employees

        mid_age_count = len(census_df[(census_df[age_col] >= 45) & (census_df[age_col] < 55)])
        mid_age_pct = mid_age_count / total_employees

        senior_workforce_count = len(census_df[census_df[age_col] >= 55])
        senior_workforce_pct = senior_workforce_count / total_employees

        # Geographic analysis
        states = census_df[state_col].unique().tolist()
        state_distribution = census_df[state_col].value_counts().to_dict()
        num_states = len(states)

        # Determine geographic concentration
        if num_states == 1:
            geographic_concentration = f"Single-state employer ({states[0]})"
        elif num_states <= 3:
            geographic_concentration = f"{num_states} states: {', '.join(sorted(states))}"
        else:
            # Show top 3 states by employee count
            top_states = census_df[state_col].value_counts().head(3)
            top_state_str = ', '.join([f"{state} ({count})" for state, count in top_states.items()])
            geographic_concentration = f"{num_states} states (top: {top_state_str})"

        # Family composition analysis (if available)
        family_status_insights = None
        if 'family_status' in census_df.columns:
            family_counts = census_df['family_status'].value_counts().to_dict()
            employee_only_pct = family_counts.get('EE', 0) / total_employees
            family_status_insights = {
                'employee_only_pct': employee_only_pct,
                'has_dependents_pct': 1 - employee_only_pct,
                'breakdown': family_counts
            }

        # Strategic fit calculations

        # Marketplace fit: Everyone can use marketplace
        # Younger workforces may prefer lower-cost Bronze/Silver, older may prefer Gold/Platinum
        marketplace_fit = 1 - (young_workforce_pct * 0.3)  # Most workforces fit marketplace well

        # Generate strategic headline
        headline = WorkforceFitAnalyzer._generate_headline(
            young_workforce_pct=young_workforce_pct,
            mid_age_pct=mid_age_pct,
            senior_workforce_pct=senior_workforce_pct,
            avg_age=avg_age,
            num_states=num_states
        )

        insights = {
            # Basic demographics
            'total_employees': total_employees,
            'avg_age': round(avg_age, 1),
            'age_range': f"{int(min_age)}-{int(max_age)}",

            # Age distribution
            'young_workforce_count': young_workforce_count,
            'young_workforce_pct': round(young_workforce_pct * 100, 1),
            'mid_age_count': mid_age_count,
            'mid_age_pct': round(mid_age_pct * 100, 1),
            'senior_workforce_count': senior_workforce_count,
            'senior_workforce_pct': round(senior_workforce_pct * 100, 1),

            # Geographic
            'num_states': num_states,
            'states': states,
            'state_distribution': state_distribution,
            'geographic_concentration': geographic_concentration,

            # Family composition
            'family_status_insights': family_status_insights,

            # Strategic insights
            'marketplace_fit_score': round(marketplace_fit * 100, 1),

            # Recommendation headline
            'headline': headline,
            'recommendation': WorkforceFitAnalyzer._generate_recommendation(
                young_workforce_pct=young_workforce_pct
            )
        }

        return insights

    @staticmethod
    def _generate_headline(
        young_workforce_pct: float,
        mid_age_pct: float,
        senior_workforce_pct: float,
        avg_age: float,
        num_states: int
    ) -> str:
        """
        Generate compelling strategic insight headline

        Args:
            young_workforce_pct: Percentage under 45
            mid_age_pct: Percentage 45-54
            senior_workforce_pct: Percentage 55+
            avg_age: Average employee age
            num_states: Number of states

        Returns:
            Strategic headline string
        """
        # Primary insight: Age distribution
        if young_workforce_pct >= 0.65:
            age_insight = f"{int(young_workforce_pct * 100)}% under 45 - ideal for lower-cost marketplace plans"
        elif young_workforce_pct >= 0.50:
            age_insight = f"{int(young_workforce_pct * 100)}% under 45 - strong fit for cost-effective ICHRA strategies"
        elif senior_workforce_pct >= 0.40:
            age_insight = f"{int(senior_workforce_pct * 100)}% over 55 - may benefit from richer plan options"
        else:
            age_insight = f"Balanced age distribution (avg {int(avg_age)}) - flexible plan design recommended"

        # Secondary insight: Geographic
        if num_states >= 5:
            geo_insight = f" | Multi-state ({num_states}) - ICHRA offers geographic flexibility"
        elif num_states == 1:
            geo_insight = " | Single-state - consistent plan options"
        else:
            geo_insight = ""

        return age_insight + geo_insight

    @staticmethod
    def _generate_recommendation(
        young_workforce_pct: float
    ) -> str:
        """
        Generate strategic recommendation text

        Args:
            young_workforce_pct: Percentage under 45

        Returns:
            Recommendation text
        """
        if young_workforce_pct >= 0.60:
            return (
                f"With {int(young_workforce_pct * 100)}% of employees under 45, "
                "this workforce is well-suited for cost-effective Bronze and Silver marketplace plans. "
                "Consider offering a tiered ICHRA contribution strategy that provides flexibility "
                "while controlling costs."
            )
        elif young_workforce_pct >= 0.40:
            return (
                f"With {int(young_workforce_pct * 100)}% of employees under 45, "
                "a balanced marketplace strategy with Silver and Gold plan options "
                "will provide good coverage across your workforce demographics."
            )
        else:
            return (
                "This workforce demographics suggest focusing on marketplace Silver and Gold plans "
                "with strong provider networks and comprehensive coverage to meet the needs "
                "of your experienced workforce."
            )


if __name__ == "__main__":
    # Test utility functions
    print("Testing utility functions...")

    # Test sample census creation
    census = CensusProcessor.create_sample_census(5)
    print("\n✓ Sample census created:")
    print(census)

    # Test currency formatting
    print(f"\n✓ Currency format: {DataFormatter.format_currency(1234.56)}")

    # Test percentage formatting
    print(f"✓ Percentage format: {DataFormatter.format_percentage(55.5)}")

    print("\nAll utility functions working!")
