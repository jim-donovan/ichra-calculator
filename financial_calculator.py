"""
Financial Summary Calculator for Multi-State ICHRA Comparison

Calculates total workforce premium across multiple states for ICHRA plan scenarios.
Handles age-banding, ACA 3-child rule, and NY/VT family-tier states.
"""

import warnings
import logging
import time
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from database import DatabaseConnection
from constants import FAMILY_TIER_STATES

# Suppress pandas warning about psycopg2 connections
warnings.filterwarnings('ignore', message='.*pandas only supports SQLAlchemy.*')


class FinancialSummaryCalculator:
    """Calculate multi-state workforce premium totals"""

    @staticmethod
    def get_age_band(age: int) -> str:
        """Convert age to ACA age band string for rate lookup"""
        if age <= 14:
            return "0-14"
        elif age >= 64:
            return "64 and over"
        else:
            return str(age)

    @staticmethod
    def get_metal_level_filter(metal_level: str) -> Tuple[str, List[str]]:
        """
        Get SQL filter clause and values for metal level queries.
        Bronze includes both 'Bronze' and 'Expanded Bronze'.
        Excludes Catastrophic.

        Args:
            metal_level: 'Bronze', 'Silver', 'Gold', or 'Platinum'

        Returns:
            Tuple of (sql_clause, list_of_values)
            e.g., ("p.level_of_coverage IN (%s, %s)", ['Bronze', 'Expanded Bronze'])
        """
        if metal_level == 'Bronze':
            return ("p.level_of_coverage IN (%s, %s)", ['Bronze', 'Expanded Bronze'])
        else:
            return ("p.level_of_coverage = %s", [metal_level])

    @staticmethod
    def get_states_from_census(census_df: pd.DataFrame) -> List[str]:
        """Get unique states from census, sorted by employee count descending"""
        state_col = None
        for col in ['Home State', 'home_state', 'state']:
            if col in census_df.columns:
                state_col = col
                break

        if state_col is None:
            return []

        state_counts = census_df[state_col].value_counts()
        return state_counts.index.tolist()

    @staticmethod
    def get_state_employee_counts(census_df: pd.DataFrame) -> Dict[str, Dict]:
        """Get employee and lives count per state"""
        state_col = None
        for col in ['Home State', 'home_state', 'state']:
            if col in census_df.columns:
                state_col = col
                break

        if state_col is None:
            return {}

        result = {}
        for state in census_df[state_col].unique():
            state_df = census_df[census_df[state_col] == state]
            employees = len(state_df)

            # Count lives (employees + dependents)
            lives = employees  # Start with employees
            for _, row in state_df.iterrows():
                family_status = row.get('Family Status', row.get('family_status', 'EE'))
                if family_status == 'ES':
                    lives += 1  # Spouse
                elif family_status == 'EC':
                    # Count children
                    for col in ['Dep 2 DOB', 'Dep 3 DOB', 'Dep 4 DOB', 'Dep 5 DOB', 'Dep 6 DOB']:
                        if col in row.index and pd.notna(row.get(col)) and str(row.get(col)).strip():
                            lives += 1
                elif family_status == 'F':
                    lives += 1  # Spouse
                    for col in ['Dep 2 DOB', 'Dep 3 DOB', 'Dep 4 DOB', 'Dep 5 DOB', 'Dep 6 DOB']:
                        if col in row.index and pd.notna(row.get(col)) and str(row.get(col)).strip():
                            lives += 1

            result[state] = {
                'employees': employees,
                'lives': lives
            }

        return result

    @staticmethod
    def get_available_plans_by_state(
        db: DatabaseConnection,
        states: List[str],
        metal_levels: List[str] = None
    ) -> Dict[str, List[Dict]]:
        """
        Get available individual marketplace plans for each state.

        Returns:
            {state: [{'plan_id': ..., 'name': ..., 'metal': ..., 'type': ...}, ...]}
        """
        if metal_levels is None:
            metal_levels = ['Gold', 'Silver', 'Bronze']

        # Expand metal levels to include 'Expanded Bronze' when 'Bronze' is requested
        expanded_levels = list(metal_levels)
        if 'Bronze' in metal_levels and 'Expanded Bronze' not in expanded_levels:
            expanded_levels.append('Expanded Bronze')

        result = {}

        for state in states:
            query = """
            SELECT DISTINCT
                p.hios_plan_id as plan_id,
                p.plan_marketing_name as name,
                p.level_of_coverage as metal,
                p.plan_type as type
            FROM rbis_insurance_plan_20251019202724 p
            WHERE SUBSTRING(p.hios_plan_id, 6, 2) = %s
              AND p.market_coverage = 'Individual'
              AND p.plan_effective_date = '2026-01-01'
              AND p.level_of_coverage IN %s
            ORDER BY p.level_of_coverage, p.plan_marketing_name
            """

            try:
                df = pd.read_sql(query, db.engine, params=(state, tuple(expanded_levels)))
                result[state] = df.to_dict('records')
            except Exception as e:
                print(f"Error fetching plans for {state}: {e}")
                result[state] = []

        return result

    @staticmethod
    def get_lowest_cost_plans_by_state(
        db: DatabaseConnection,
        census_df: pd.DataFrame,
        metal_level: str = 'Gold'
    ) -> Dict[str, str]:
        """
        Get the lowest cost plan of a given metal level for each state.
        Uses a sample employee (median age) to determine lowest cost.
        Tries multiple rating areas if the first one has no plans.

        Returns:
            {state: plan_id}
        """
        states = FinancialSummaryCalculator.get_states_from_census(census_df)
        result = {}

        for state in states:
            # Get state employees
            state_col = 'Home State' if 'Home State' in census_df.columns else 'state'
            state_df = census_df[census_df[state_col] == state]

            if state_df.empty:
                continue

            # Get median age for sample
            age_col = 'age' if 'age' in state_df.columns else 'ee_age'
            if age_col in state_df.columns:
                median_age = int(state_df[age_col].median())
            else:
                median_age = 40  # Default

            age_band = FinancialSummaryCalculator.get_age_band(median_age)

            # Get unique rating areas for this state's employees
            rating_areas = state_df['rating_area_id'].dropna().unique().tolist()
            if not rating_areas:
                rating_areas = [1]  # Default fallback

            # Try each rating area until we find plans
            plan_found = False
            # Get metal level filter (Bronze includes Expanded Bronze)
            metal_clause, metal_values = FinancialSummaryCalculator.get_metal_level_filter(metal_level)

            for rating_area in rating_areas:
                if pd.isna(rating_area):
                    continue
                rating_area = int(rating_area)

                query = f"""
                SELECT
                    p.hios_plan_id as plan_id,
                    p.plan_marketing_name as name,
                    r.individual_rate as rate
                FROM rbis_insurance_plan_20251019202724 p
                JOIN rbis_insurance_plan_base_rates_20251019202724 r
                    ON p.hios_plan_id = r.plan_id
                WHERE SUBSTRING(p.hios_plan_id, 6, 2) = %s
                  AND p.market_coverage = 'Individual'
                  AND p.plan_effective_date = '2026-01-01'
                  AND {metal_clause}
                  AND r.market_coverage = 'Individual'
                  AND r.rating_area_id = %s
                  AND r.age = %s
                ORDER BY r.individual_rate ASC
                LIMIT 1
                """

                try:
                    params = [state] + metal_values + [f"Rating Area {rating_area}", age_band]
                    df = pd.read_sql(query, db.engine, params=tuple(params))
                    if not df.empty:
                        result[state] = df.iloc[0]['plan_id']
                        plan_found = True
                        break
                except Exception as e:
                    print(f"Error finding {metal_level} for {state} RA {rating_area}: {e}")

            # If no plan found in any employee's rating area, try Rating Area 1 as fallback
            if not plan_found and 1 not in rating_areas:
                try:
                    fallback_params = [state] + metal_values + ["Rating Area 1", age_band]
                    df = pd.read_sql(query, db.engine, params=tuple(fallback_params))
                    if not df.empty:
                        result[state] = df.iloc[0]['plan_id']
                except Exception as e:
                    print(f"Error finding {metal_level} fallback for {state}: {e}")

        return result

    @staticmethod
    def _parse_dob_to_age(dob_str, ref_date=None) -> Optional[int]:
        """Parse DOB string to age as of reference date (default 2026-01-01)"""
        if ref_date is None:
            ref_date = datetime(2026, 1, 1)

        if pd.isna(dob_str) or not str(dob_str).strip():
            return None

        dob_str = str(dob_str).strip()

        for fmt in ['%m/%d/%y', '%m/%d/%Y', '%Y-%m-%d']:
            try:
                dob = datetime.strptime(dob_str, fmt)
                # Handle 2-digit years
                if dob.year > 2050:
                    dob = dob.replace(year=dob.year - 100)
                age = (ref_date - dob).days // 365
                return max(0, age)
            except ValueError:
                continue

        return None

    @staticmethod
    def _get_rated_members(employee_row: pd.Series) -> List[Tuple[str, int]]:
        """
        Get list of (member_type, age) tuples for premium calculation.
        Applies ACA 3-child rule: only 3 oldest children under 21 are rated.
        """
        members = []

        # Employee
        ee_age = employee_row.get('age', employee_row.get('ee_age'))
        if ee_age is None:
            ee_age = FinancialSummaryCalculator._parse_dob_to_age(
                employee_row.get('EE DOB', employee_row.get('ee_dob'))
            )
        if ee_age is not None:
            members.append(('EE', int(ee_age)))

        # Spouse
        family_status = employee_row.get('Family Status', employee_row.get('family_status', 'EE'))
        if family_status in ['ES', 'F']:
            spouse_age = FinancialSummaryCalculator._parse_dob_to_age(
                employee_row.get('Spouse DOB', employee_row.get('spouse_dob'))
            )
            if spouse_age is not None:
                members.append(('SP', int(spouse_age)))

        # Children (collect all, then apply 3-child rule)
        children = []
        if family_status in ['EC', 'F']:
            for i in range(2, 7):
                dep_col = f'Dep {i} DOB'
                alt_col = f'dep_{i}_dob'
                dob = employee_row.get(dep_col, employee_row.get(alt_col))
                child_age = FinancialSummaryCalculator._parse_dob_to_age(dob)
                if child_age is not None:
                    children.append((f'D{i}', int(child_age)))

        # ACA 3-child rule: only rate 3 oldest children under 21
        # Children 21+ are rated individually (not subject to 3-child rule)
        children_under_21 = [(m, a) for m, a in children if a < 21]
        children_21_plus = [(m, a) for m, a in children if a >= 21]

        # Sort under-21 children by age descending, take top 3
        children_under_21_sorted = sorted(children_under_21, key=lambda x: x[1], reverse=True)
        rated_children = children_under_21_sorted[:3] + children_21_plus

        members.extend(rated_children)

        return members

    @staticmethod
    def get_rates_for_plans(
        db: DatabaseConnection,
        plan_ids: List[str]
    ) -> pd.DataFrame:
        """
        Batch fetch rates for multiple plans.

        Returns DataFrame with columns:
            plan_id, rating_area_id, age, individual_rate
        """
        if not plan_ids:
            return pd.DataFrame()

        query = """
        SELECT
            plan_id,
            rating_area_id,
            age,
            individual_rate as rate
        FROM rbis_insurance_plan_base_rates_20251019202724
        WHERE plan_id IN %s
          AND market_coverage = 'Individual'
        """

        try:
            df = pd.read_sql(query, db.engine, params=(tuple(plan_ids),))
            return df
        except Exception as e:
            print(f"Error fetching rates: {e}")
            return pd.DataFrame()

    @staticmethod
    def calculate_employee_premium(
        employee_row: pd.Series,
        plan_id: str,
        rates_df: pd.DataFrame,
        rating_area: int
    ) -> float:
        """
        Calculate total monthly premium for an employee and their family.
        """
        state_code = plan_id[5:7]  # Extract state from HIOS plan ID

        # Handle NY/VT family-tier states
        if state_code in FAMILY_TIER_STATES:
            return FinancialSummaryCalculator._calculate_family_tier_premium(
                employee_row, plan_id, rates_df, rating_area
            )

        # Age-based rating (most states)
        members = FinancialSummaryCalculator._get_rated_members(employee_row)

        total_premium = 0.0
        rating_area_str = f"Rating Area {rating_area}"

        for member_type, age in members:
            age_band = FinancialSummaryCalculator.get_age_band(age)

            # Look up rate
            rate_row = rates_df[
                (rates_df['plan_id'] == plan_id) &
                (rates_df['rating_area_id'] == rating_area_str) &
                (rates_df['age'] == age_band)
            ]

            if not rate_row.empty:
                total_premium += float(rate_row.iloc[0]['rate'])

        return total_premium

    @staticmethod
    def _calculate_family_tier_premium(
        employee_row: pd.Series,
        plan_id: str,
        rates_df: pd.DataFrame,
        rating_area: int
    ) -> float:
        """Calculate premium for NY/VT family-tier states"""
        family_status = employee_row.get('Family Status', employee_row.get('family_status', 'EE'))
        rating_area_str = f"Rating Area {rating_area}"

        # Look up family-tier rate
        rate_row = rates_df[
            (rates_df['plan_id'] == plan_id) &
            (rates_df['rating_area_id'] == rating_area_str) &
            (rates_df['age'] == 'Family-Tier Rates')
        ]

        if rate_row.empty:
            return 0.0

        base_rate = float(rate_row.iloc[0]['rate'])

        # Apply tier multiplier
        tier_multipliers = {
            'EE': 1.0,
            'ES': 2.0,
            'EC': 1.7,  # Approximate
            'F': 2.85   # Approximate
        }

        multiplier = tier_multipliers.get(family_status, 1.0)
        return base_rate * multiplier

    @staticmethod
    def calculate_scenario_totals(
        census_df: pd.DataFrame,
        plan_selections: Dict[str, str],  # {state: plan_id}
        db: DatabaseConnection
    ) -> Dict:
        """
        Calculate total workforce premium for a plan scenario.

        Args:
            census_df: Employee census with state, rating_area_id, age data
            plan_selections: Mapping of state code to selected plan_id
            db: Database connection

        Returns:
            {
                'total_monthly': float,
                'total_annual': float,
                'employees_covered': int,
                'lives_covered': int,
                'by_state': {
                    state: {
                        'employees': int,
                        'lives': int,
                        'monthly': float,
                        'plan_id': str,
                        'plan_name': str
                    }
                },
                'errors': List[str]
            }
        """
        # Get all plan IDs and fetch rates in batch
        plan_ids = list(set(plan_selections.values()))
        rates_df = FinancialSummaryCalculator.get_rates_for_plans(db, plan_ids)

        # Get plan names
        plan_names = FinancialSummaryCalculator._get_plan_names(db, plan_ids)

        # Determine state column
        state_col = None
        for col in ['Home State', 'home_state', 'state']:
            if col in census_df.columns:
                state_col = col
                break

        if state_col is None:
            return {'error': 'No state column found in census'}

        result = {
            'total_monthly': 0.0,
            'total_annual': 0.0,
            'employees_covered': 0,
            'lives_covered': 0,
            'by_state': {},
            'errors': []
        }

        # Process each state
        for state, plan_id in plan_selections.items():
            state_df = census_df[census_df[state_col] == state]

            if state_df.empty:
                continue

            state_monthly = 0.0
            state_lives = 0

            for _, emp_row in state_df.iterrows():
                # Get rating area
                rating_area = emp_row.get('rating_area_id', 1)
                if pd.isna(rating_area):
                    rating_area = 1
                rating_area = int(rating_area)

                # Calculate premium
                premium = FinancialSummaryCalculator.calculate_employee_premium(
                    emp_row, plan_id, rates_df, rating_area
                )

                if premium == 0:
                    result['errors'].append(
                        f"No rate found for employee in {state}, RA {rating_area}"
                    )

                state_monthly += premium

                # Count lives
                members = FinancialSummaryCalculator._get_rated_members(emp_row)
                state_lives += len(members)

            result['by_state'][state] = {
                'employees': len(state_df),
                'lives': state_lives,
                'monthly': state_monthly,
                'plan_id': plan_id,
                'plan_name': plan_names.get(plan_id, 'Unknown')
            }

            result['total_monthly'] += state_monthly
            result['employees_covered'] += len(state_df)
            result['lives_covered'] += state_lives

        result['total_annual'] = result['total_monthly'] * 12

        return result

    @staticmethod
    def _get_plan_names(db: DatabaseConnection, plan_ids: List[str]) -> Dict[str, str]:
        """Get plan marketing names for a list of plan IDs"""
        if not plan_ids:
            return {}

        query = """
        SELECT hios_plan_id, plan_marketing_name
        FROM rbis_insurance_plan_20251019202724
        WHERE hios_plan_id IN %s
        """

        try:
            df = pd.read_sql(query, db.engine, params=(tuple(plan_ids),))
            return dict(zip(df['hios_plan_id'], df['plan_marketing_name']))
        except Exception:
            return {}

    @staticmethod
    def calculate_current_totals(census_df: pd.DataFrame) -> Dict:
        """
        Calculate current group plan totals from census data.

        Returns:
            {
                'total_ee_monthly': float,
                'total_er_monthly': float,
                'total_gap_monthly': float,
                'total_premium_monthly': float (includes gap),
                'total_ee_annual': float,
                'total_er_annual': float,
                'total_gap_annual': float,
                'total_premium_annual': float (includes gap),
                'employees_with_data': int
            }
        """
        def parse_currency(val):
            if pd.isna(val):
                return 0.0
            s = str(val).replace('$', '').replace(',', '').replace('"', '').strip()
            try:
                return float(s)
            except (ValueError, TypeError):
                return 0.0

        # Find contribution columns
        ee_col = None
        er_col = None
        gap_col = None
        for col in census_df.columns:
            if 'current' in col.lower() and 'ee' in col.lower():
                ee_col = col
            elif 'current' in col.lower() and 'er' in col.lower():
                er_col = col
            elif col == 'gap_insurance_monthly' or col == 'Gap Insurance':
                gap_col = col

        result = {
            'total_ee_monthly': 0.0,
            'total_er_monthly': 0.0,
            'total_gap_monthly': 0.0,
            'total_premium_monthly': 0.0,
            'total_ee_annual': 0.0,
            'total_er_annual': 0.0,
            'total_gap_annual': 0.0,
            'total_premium_annual': 0.0,
            'employees_with_data': 0
        }

        if ee_col and er_col:
            ee_values = census_df[ee_col].apply(parse_currency)
            er_values = census_df[er_col].apply(parse_currency)
            gap_values = census_df[gap_col].apply(parse_currency) if gap_col else pd.Series([0.0] * len(census_df))

            result['total_ee_monthly'] = ee_values.sum()
            result['total_er_monthly'] = er_values.sum()
            result['total_gap_monthly'] = gap_values.sum()
            # Gap insurance is ER-paid, include in total premium
            result['total_premium_monthly'] = result['total_ee_monthly'] + result['total_er_monthly'] + result['total_gap_monthly']
            result['total_ee_annual'] = result['total_ee_monthly'] * 12
            result['total_er_annual'] = result['total_er_monthly'] * 12
            result['total_gap_annual'] = result['total_gap_monthly'] * 12
            result['total_premium_annual'] = result['total_premium_monthly'] * 12
            result['employees_with_data'] = ((ee_values > 0) | (er_values > 0)).sum()

        return result

    @staticmethod
    def calculate_projected_2026_total(census_df: pd.DataFrame) -> Dict:
        """
        Calculate projected 2026 renewal totals from census data.

        Looks for '2026 Premium' column (or parsed 'projected_2026_premium' column).

        Returns:
            {
                'total_monthly': float (includes gap insurance),
                'total_annual': float (includes gap insurance),
                'total_gap_monthly': float,
                'total_gap_annual': float,
                'employees_with_data': int,
                'has_data': bool  # True if 2026 Premium column exists with values
            }
        """
        def parse_currency(val):
            if pd.isna(val):
                return 0.0
            s = str(val).replace('$', '').replace(',', '').replace('"', '').strip()
            if not s:
                return 0.0
            try:
                return float(s)
            except (ValueError, TypeError):
                return 0.0

        result = {
            'total_monthly': 0.0,
            'total_annual': 0.0,
            'total_gap_monthly': 0.0,
            'total_gap_annual': 0.0,
            'employees_with_data': 0,
            'has_data': False
        }

        # Check for 2026 Premium column (raw from CSV or parsed)
        premium_col = None
        for col in ['2026 Premium', 'projected_2026_premium']:
            if col in census_df.columns:
                premium_col = col
                break

        # Check for gap insurance column
        gap_col = None
        for col in ['gap_insurance_monthly', 'Gap Insurance']:
            if col in census_df.columns:
                gap_col = col
                break

        if premium_col:
            values = census_df[premium_col].apply(parse_currency)
            gap_values = census_df[gap_col].apply(parse_currency) if gap_col else pd.Series([0.0] * len(census_df))

            result['total_gap_monthly'] = gap_values.sum()
            result['total_gap_annual'] = result['total_gap_monthly'] * 12
            # Include gap insurance in renewal totals (gap continues to renewal)
            result['total_monthly'] = values.sum() + result['total_gap_monthly']
            result['total_annual'] = result['total_monthly'] * 12
            result['employees_with_data'] = (values > 0).sum()
            result['has_data'] = result['employees_with_data'] > 0

        return result

    @staticmethod
    def count_total_lives(census_df: pd.DataFrame) -> int:
        """
        Count total covered lives in census.

        Counts employee + spouse (if ES or F) + all children with DOB data.
        Unlike _get_rated_members(), this counts ALL covered lives, not just
        the rated members used for premium calculation.
        """
        total = 0
        for _, row in census_df.iterrows():
            # Always count the employee
            lives = 1

            family_status = row.get('Family Status', row.get('family_status', 'EE'))

            # Count spouse for ES (Employee + Spouse) or F (Family)
            if family_status in ['ES', 'F']:
                lives += 1

            # Count all children with DOB data for EC (Employee + Children) or F (Family)
            if family_status in ['EC', 'F']:
                for col in ['Dep 2 DOB', 'Dep 3 DOB', 'Dep 4 DOB', 'Dep 5 DOB', 'Dep 6 DOB']:
                    if col in row.index and pd.notna(row.get(col)) and str(row.get(col)).strip():
                        lives += 1

            total += lives
        return total

    # Tier multipliers for estimating family coverage costs (legacy - use calculate_actual_family_premium instead)
    TIER_MULTIPLIERS = {
        'EE': 1.0,
        'ES': 1.5,
        'EC': 1.3,
        'F': 1.8
    }

    @staticmethod
    def get_rate_for_age(
        db: DatabaseConnection,
        plan_id: str,
        rating_area: int,
        age: int
    ) -> float:
        """
        Get the individual rate for a specific plan, rating area, and age.

        Args:
            db: Database connection
            plan_id: HIOS plan ID
            rating_area: Rating area number (integer)
            age: Age (integer, will be converted to age band)

        Returns:
            Individual rate as float, or 0.0 if not found
        """
        # Convert age to age band
        if age <= 14:
            age_band = '0-14'
        elif age >= 64:
            age_band = '64 and over'
        else:
            age_band = str(age)

        query = """
        SELECT individual_rate
        FROM rbis_insurance_plan_base_rates_20251019202724
        WHERE plan_id = %s
          AND rating_area_numeric = %s
          AND age = %s
          AND rate_effective_date = '2026-01-01'
        LIMIT 1
        """
        try:
            result = db.execute_query(query, (plan_id, rating_area, age_band))
            if result is not None and not result.empty:
                return float(result.iloc[0]['individual_rate'])
            return 0.0
        except Exception as e:
            print(f"Error getting rate for {plan_id} RA{rating_area} age {age}: {e}")
            return 0.0

    @staticmethod
    def calculate_actual_family_premium(
        db: DatabaseConnection,
        plan_id: str,
        employee_row: pd.Series,
        rating_area: int = None
    ) -> float:
        """
        Calculate actual family premium by summing individual rates for each family member.

        Unlike the tier multiplier approach, this sums the actual ACA rates for:
        - Employee
        - Spouse (if family status is ES or F)
        - Up to 3 oldest children under 21 (ACA 3-child rule)
        - Children 21+ are rated individually

        Args:
            db: Database connection
            plan_id: HIOS plan ID
            employee_row: Row from census DataFrame
            rating_area: Optional rating area (if not provided, uses rating_area_id from row)

        Returns:
            Total monthly premium for the family
        """
        # Get rating area from row if not provided
        if rating_area is None:
            rating_area = employee_row.get('rating_area_id')
            if rating_area is None:
                return 0.0
            try:
                rating_area = int(rating_area)
            except (ValueError, TypeError):
                return 0.0

        # Get rated members (employee, spouse, children with 3-child rule applied)
        members = FinancialSummaryCalculator._get_rated_members(employee_row)

        if not members:
            return 0.0

        total_premium = 0.0
        for member_type, age in members:
            rate = FinancialSummaryCalculator.get_rate_for_age(db, plan_id, rating_area, age)
            total_premium += rate

        return total_premium

    @staticmethod
    def calculate_workforce_actual_premium(
        db: DatabaseConnection,
        plan_id: str,
        census_df: pd.DataFrame
    ) -> Dict:
        """
        Calculate total workforce premium using actual family rates (no tier multipliers).

        This sums the actual individual rates for all family members across all employees.

        Args:
            db: Database connection
            plan_id: HIOS plan ID
            census_df: Employee census with rating_area_id and family data

        Returns:
            {
                'total_monthly': float,
                'total_annual': float,
                'employee_count': int,
                'covered_lives': int,
                'by_employee': List[Dict]  # Optional detailed breakdown
            }
        """
        total_monthly = 0.0
        covered_lives = 0
        employee_details = []

        for idx, emp in census_df.iterrows():
            # Get rated members count
            members = FinancialSummaryCalculator._get_rated_members(emp)
            covered_lives += len(members)

            # Calculate actual family premium
            family_premium = FinancialSummaryCalculator.calculate_actual_family_premium(
                db, plan_id, emp
            )
            total_monthly += family_premium

            employee_details.append({
                'employee_id': emp.get('employee_id', idx),
                'family_status': emp.get('family_status', 'EE'),
                'members_rated': len(members),
                'monthly_premium': family_premium
            })

        return {
            'total_monthly': total_monthly,
            'total_annual': total_monthly * 12,
            'employee_count': len(census_df),
            'covered_lives': covered_lives,
            'by_employee': employee_details
        }

    @staticmethod
    def calculate_lcsp_scenario(
        census_df: pd.DataFrame,
        db: DatabaseConnection,
        metal_level: str = 'Silver',
        dependents_df: pd.DataFrame = None
    ) -> Dict:
        """
        Calculate total workforce premium using LCSP (Lowest Cost Silver/Gold/Bronze Plan)
        for each employee based on their specific rating area.

        Uses tier multipliers to estimate family coverage:
        - EE: 1.0x
        - ES: 1.5x
        - EC: 1.3x
        - F: 1.8x

        Args:
            census_df: Employee census with state, rating_area_id, age data
            db: Database connection
            metal_level: 'Silver', 'Gold', or 'Bronze'
            dependents_df: Optional (not used in tier multiplier approach)

        Returns:
            {
                'total_monthly': float,
                'total_annual': float,
                'employees_covered': int,
                'lives_covered': int,
                'by_state': {state: {'employees': int, 'lives': int, 'monthly': float}},
                'errors': List[str],
                'metal_level': str,
                'employee_details': List[Dict]  # Per-employee breakdown for debugging
            }
        """
        # Determine state column
        state_col = None
        for col in ['Home State', 'home_state', 'state']:
            if col in census_df.columns:
                state_col = col
                break

        if state_col is None:
            return {'error': 'No state column found in census'}

        # Lives count per tier
        tier_lives = {'EE': 1, 'ES': 2, 'EC': 2, 'F': 3}

        result = {
            'total_monthly': 0.0,
            'total_annual': 0.0,
            'total_projected_2026': 0.0,  # Sum of projected 2026 renewal premiums
            'employees_covered': 0,
            'lives_covered': 0,
            'by_state': {},
            'errors': [],
            'metal_level': metal_level,
            'employee_details': []  # Per-employee breakdown
        }

        # Pre-process all employees to collect unique (state, rating_area, age_band) tuples
        employee_data = []
        location_keys = set()

        for idx, emp_row in census_df.iterrows():
            state = emp_row.get(state_col)
            if not state:
                continue

            # Get employee identifiers
            employee_id = emp_row.get('employee_id', emp_row.get('Employee Number', ''))
            first_name = emp_row.get('first_name', emp_row.get('First Name', ''))
            last_name = emp_row.get('last_name', emp_row.get('Last Name', ''))
            family_status = emp_row.get('Family Status', emp_row.get('family_status', 'EE'))

            # Get current premium from census (2025 data)
            # Note: NaN or 0 evaluates to NaN (not 0) because bool(NaN) == True
            current_ee_val = emp_row.get('current_ee_monthly', 0)
            current_ee = 0.0 if pd.isna(current_ee_val) else float(current_ee_val or 0)
            current_er_val = emp_row.get('current_er_monthly', 0)
            current_er = 0.0 if pd.isna(current_er_val) else float(current_er_val or 0)
            gap_insurance_val = emp_row.get('gap_insurance_monthly', 0)
            gap_insurance = 0.0 if pd.isna(gap_insurance_val) else float(gap_insurance_val or 0)
            current_total = current_ee + current_er

            # Get projected 2026 renewal premium (if available)
            # Note: NaN or 0 evaluates to NaN (not 0) because bool(NaN) == True
            # Must explicitly check for NaN using pd.isna()
            projected_2026_val = emp_row.get('projected_2026_premium', 0)
            projected_2026 = 0.0 if pd.isna(projected_2026_val) else float(projected_2026_val or 0)

            # Get rating area
            rating_area = emp_row.get('rating_area_id', 1)
            if pd.isna(rating_area):
                rating_area = 1
            rating_area = int(rating_area)
            rating_area_str = f"Rating Area {rating_area}"

            # Get employee age
            ee_age = emp_row.get('age', emp_row.get('ee_age'))
            if ee_age is None:
                result['errors'].append(f"No age found for employee {employee_id} in {state}")
                continue
            ee_age = int(ee_age)
            age_band = FinancialSummaryCalculator.get_age_band(ee_age)

            # Handle NY/VT family-tier states
            if state in FAMILY_TIER_STATES:
                age_band = 'Family-Tier Rates'

            # Store employee data and location key for batch lookup
            location_key = (state, rating_area_str, age_band)
            location_keys.add(location_key)

            employee_data.append({
                'employee_id': employee_id,
                'first_name': first_name,
                'last_name': last_name,
                'state': state,
                'rating_area': rating_area,
                'rating_area_str': rating_area_str,
                'family_status': family_status,
                'ee_age': ee_age,
                'age_band': age_band,
                'current_ee': current_ee,
                'current_er': current_er,
                'gap_insurance': gap_insurance,
                'current_total': current_total,
                'projected_2026': projected_2026,
                'location_key': location_key
            })

        # Batch query: Get lowest cost plan for all unique (state, rating_area, age) combos
        lcsp_lookup = {}
        if location_keys:
            # OPTIMIZED: Single DISTINCT ON query instead of N UNION ALL subqueries
            # Extract unique values for IN clauses
            states = list(set(k[0] for k in location_keys))
            rating_areas = list(set(k[1] for k in location_keys))
            age_bands = list(set(k[2] for k in location_keys))

            # Determine metal levels to query (Bronze includes Expanded Bronze)
            if metal_level == 'Bronze':
                metal_levels_list = ['Bronze', 'Expanded Bronze']
            else:
                metal_levels_list = [metal_level]

            batch_query = """
            SELECT DISTINCT ON (state, rating_area_str, age_band)
                SUBSTRING(p.hios_plan_id, 6, 2) as state,
                r.rating_area_id as rating_area_str,
                r.age as age_band,
                p.plan_marketing_name,
                r.individual_rate as lcsp_rate
            FROM rbis_insurance_plan_20251019202724 p
            JOIN rbis_insurance_plan_base_rates_20251019202724 r
                ON p.hios_plan_id = r.plan_id
            WHERE SUBSTRING(p.hios_plan_id, 6, 2) IN %s
              AND p.market_coverage = 'Individual'
              AND p.plan_effective_date = '2026-01-01'
              AND p.level_of_coverage IN %s
              AND r.market_coverage = 'Individual'
              AND r.rating_area_id IN %s
              AND r.age IN %s
            ORDER BY state, rating_area_str, age_band, r.individual_rate ASC
            """

            try:
                query_start = time.time()
                batch_df = pd.read_sql(batch_query, db.engine, params=(
                    tuple(states),
                    tuple(metal_levels_list),
                    tuple(rating_areas),
                    tuple(age_bands)
                ))
                logging.info(f"LCSP SCENARIO: Query returned {len(batch_df)} rows in {time.time() - query_start:.2f}s")

                for _, row in batch_df.iterrows():
                    key = (row['state'], row['rating_area_str'], row['age_band'])
                    lcsp_lookup[key] = {
                        'rate': float(row['lcsp_rate']) if pd.notna(row['lcsp_rate']) else 0.0,
                        'plan_name': row['plan_marketing_name']
                    }
            except (ValueError, TypeError) as e:
                result['errors'].append(f"Batch query error: {str(e)}")

        # Process each employee using the batch lookup results
        for emp in employee_data:
            lcsp_data = lcsp_lookup.get(emp['location_key'])

            if lcsp_data:
                lcsp_ee_rate = lcsp_data['rate']
                lcsp_plan_name = lcsp_data['plan_name']
            else:
                lcsp_ee_rate = 0.0
                lcsp_plan_name = None
                result['errors'].append(
                    f"No {metal_level} rate for {emp['state']} RA {emp['rating_area']}, age {emp['age_band']}"
                )

            # Apply tier multiplier
            tier_multiplier = FinancialSummaryCalculator.TIER_MULTIPLIERS.get(emp['family_status'], 1.0)
            estimated_tier_premium = lcsp_ee_rate * tier_multiplier

            # Estimate lives based on tier
            lives = tier_lives.get(emp['family_status'], 1)

            # Store employee detail record
            result['employee_details'].append({
                'employee_id': emp['employee_id'],
                'first_name': emp['first_name'],
                'last_name': emp['last_name'],
                'state': emp['state'],
                'rating_area': emp['rating_area'],
                'family_status': emp['family_status'],
                'ee_age': emp['ee_age'],
                'lcsp_plan_name': lcsp_plan_name or 'No plan found',
                'lcsp_ee_rate': lcsp_ee_rate,
                'tier_multiplier': tier_multiplier,
                'estimated_tier_premium': estimated_tier_premium,
                'current_ee_monthly': emp['current_ee'],
                'current_er_monthly': emp['current_er'],
                'gap_insurance_monthly': emp['gap_insurance'],
                'current_total_monthly': emp['current_total'],
                'projected_2026_premium': emp['projected_2026']
            })

            # Add to state totals
            state = emp['state']
            if state not in result['by_state']:
                result['by_state'][state] = {
                    'employees': 0,
                    'lives': 0,
                    'monthly': 0.0,
                    'plan_name': f'Lowest Cost {metal_level} (varies by location)'
                }

            result['by_state'][state]['employees'] += 1
            result['by_state'][state]['lives'] += lives
            result['by_state'][state]['monthly'] += estimated_tier_premium

            result['total_monthly'] += estimated_tier_premium
            result['total_projected_2026'] += emp['projected_2026']
            result['employees_covered'] += 1
            result['lives_covered'] += lives

        result['total_annual'] = result['total_monthly'] * 12
        result['total_projected_2026_annual'] = result['total_projected_2026'] * 12

        return result

    @staticmethod
    def calculate_multi_metal_scenario(
        census_df: pd.DataFrame,
        db: DatabaseConnection,
        metal_levels: list = None,
        dependents_df: pd.DataFrame = None
    ) -> Dict[str, Dict]:
        """
        Calculate total workforce premium for multiple metal levels (Bronze, Silver, Gold)
        in a single pass using an optimized batch query.

        This is more efficient than calling calculate_lcsp_scenario() three times
        because it queries all metal levels in one database round-trip.

        Args:
            census_df: Employee census with state, rating_area_id, age data
            db: Database connection
            metal_levels: List of metal levels (default: ['Bronze', 'Silver', 'Gold'])
            dependents_df: Optional (not used in tier multiplier approach)

        Returns:
            {
                'Bronze': {
                    'total_monthly': float,
                    'total_annual': float,
                    'employees_covered': int,
                    'lives_covered': int,
                    'by_state': {...},
                    'employee_details': [...]
                },
                'Silver': {...},
                'Gold': {...}
            }
        """
        import logging
        import time

        if metal_levels is None:
            metal_levels = ['Bronze', 'Silver', 'Gold']

        logging.info(f"MULTI-METAL: Calculating for {len(census_df)} employees, metals: {metal_levels}")
        start_time = time.time()

        # Determine state column
        state_col = None
        for col in ['Home State', 'home_state', 'state']:
            if col in census_df.columns:
                state_col = col
                break

        if state_col is None:
            return {metal: {'error': 'No state column found in census'} for metal in metal_levels}

        # Lives count per tier
        tier_lives = {'EE': 1, 'ES': 2, 'EC': 2, 'F': 3}

        # Initialize results for each metal level
        results = {}
        for metal in metal_levels:
            results[metal] = {
                'total_monthly': 0.0,
                'total_annual': 0.0,
                'employees_covered': 0,
                'lives_covered': 0,
                'by_state': {},
                'errors': [],
                'metal_level': metal,
                'employee_details': [],
                '_av_values': [],  # Temporary list to collect AV values for averaging
                'average_av': None  # Will be calculated at the end
            }

        # Pre-process all employees to collect unique (state, rating_area, age_band) tuples
        employee_data = []
        location_keys = set()

        for idx, emp_row in census_df.iterrows():
            state = emp_row.get(state_col)
            if not state:
                continue

            # Get employee identifiers
            employee_id = emp_row.get('employee_id', emp_row.get('Employee Number', ''))
            first_name = emp_row.get('first_name', emp_row.get('First Name', ''))
            last_name = emp_row.get('last_name', emp_row.get('Last Name', ''))
            family_status = emp_row.get('Family Status', emp_row.get('family_status', 'EE'))

            # Get current premium from census (2025 data)
            current_ee_val = emp_row.get('current_ee_monthly', 0)
            current_ee = 0.0 if pd.isna(current_ee_val) else float(current_ee_val or 0)
            current_er_val = emp_row.get('current_er_monthly', 0)
            current_er = 0.0 if pd.isna(current_er_val) else float(current_er_val or 0)
            gap_insurance_val = emp_row.get('gap_insurance_monthly', 0)
            gap_insurance = 0.0 if pd.isna(gap_insurance_val) else float(gap_insurance_val or 0)
            # Include gap insurance in current total (ER-paid coverage)
            current_total = current_ee + current_er + gap_insurance

            # Get projected 2026 renewal premium (if available)
            # Include gap insurance in renewal (assumes gap continues to renewal)
            projected_2026_val = emp_row.get('projected_2026_premium', 0)
            projected_2026_base = 0.0 if pd.isna(projected_2026_val) else float(projected_2026_val or 0)
            projected_2026 = projected_2026_base + gap_insurance

            # Get rating area
            rating_area = emp_row.get('rating_area_id', 1)
            if pd.isna(rating_area):
                rating_area = 1
            rating_area = int(rating_area)
            rating_area_str = f"Rating Area {rating_area}"

            # Get employee age
            ee_age = emp_row.get('age', emp_row.get('ee_age'))
            if ee_age is None:
                for metal in metal_levels:
                    results[metal]['errors'].append(f"No age found for employee {employee_id} in {state}")
                continue
            ee_age = int(ee_age)
            age_band = FinancialSummaryCalculator.get_age_band(ee_age)

            # Handle NY/VT family-tier states
            if state in FAMILY_TIER_STATES:
                age_band = 'Family-Tier Rates'

            # Store employee data and location key for batch lookup
            location_key = (state, rating_area_str, age_band)
            location_keys.add(location_key)

            employee_data.append({
                'employee_id': employee_id,
                'first_name': first_name,
                'last_name': last_name,
                'state': state,
                'rating_area': rating_area,
                'rating_area_str': rating_area_str,
                'family_status': family_status,
                'ee_age': ee_age,
                'age_band': age_band,
                'current_ee': current_ee,
                'current_er': current_er,
                'gap_insurance': gap_insurance,
                'current_total': current_total,
                'projected_2026': projected_2026,
                'location_key': location_key
            })

        # Batch query: Get lowest cost plan for all unique (state, rating_area, age, metal) combos
        # Structure: {(state, rating_area_str, age_band): {metal: {'rate': float, 'plan_name': str, 'actuarial_value': str}}}
        lcp_lookup = {}

        if location_keys:
            # Extract unique states, rating areas, and age bands
            states = list(set(k[0] for k in location_keys))
            rating_areas = list(set(k[1] for k in location_keys))
            age_bands = list(set(k[2] for k in location_keys))

            # Single efficient query using DISTINCT ON to get lowest cost plan per grouping
            # This replaces 100+ UNION ALL subqueries with one query
            batch_query = """
            SELECT DISTINCT ON (state, rating_area_id, age, metal_level)
                SUBSTRING(p.hios_plan_id, 6, 2) as state,
                r.rating_area_id as rating_area_str,
                r.age as age_band,
                p.level_of_coverage as metal_level,
                p.hios_plan_id as lcp_plan_id,
                p.plan_marketing_name,
                r.individual_rate as lcp_rate,
                v.issuer_actuarial_value
            FROM rbis_insurance_plan_20251019202724 p
            JOIN rbis_insurance_plan_base_rates_20251019202724 r
                ON p.hios_plan_id = r.plan_id
            LEFT JOIN rbis_insurance_plan_variant_20251019202724 v
                ON p.hios_plan_id = v.hios_plan_id
                AND v.csr_variation_type = 'Exchange variant (no CSR)'
            WHERE SUBSTRING(p.hios_plan_id, 6, 2) IN %s
              AND p.market_coverage = 'Individual'
              AND p.plan_effective_date = '2026-01-01'
              AND p.level_of_coverage IN ('Bronze', 'Expanded Bronze', 'Silver', 'Gold')
              AND r.market_coverage = 'Individual'
              AND r.rating_area_id IN %s
              AND r.age IN %s
            ORDER BY state, rating_area_id, age, metal_level, r.individual_rate ASC
            """
            query_start = time.time()

            try:
                batch_df = pd.read_sql(batch_query, db.engine, params=(
                    tuple(states),
                    tuple(rating_areas),
                    tuple(age_bands)
                ))
                logging.info(f"MULTI-METAL: Query returned {len(batch_df)} rows in {time.time() - query_start:.2f}s")

                for _, row in batch_df.iterrows():
                    loc_key = (row['state'], row['rating_area_str'], row['age_band'])
                    metal = row['metal_level']

                    # Map "Expanded Bronze" to "Bronze" for lookup
                    lookup_metal = 'Bronze' if metal == 'Expanded Bronze' else metal

                    if loc_key not in lcp_lookup:
                        lcp_lookup[loc_key] = {}

                    # Parse actuarial value (stored as "60.00%" string)
                    av_str = row.get('issuer_actuarial_value', '')
                    av_pct = None
                    if av_str and pd.notna(av_str):
                        try:
                            av_pct = float(str(av_str).replace('%', '').strip())
                        except (ValueError, TypeError):
                            pass

                    # Only store if we don't have this metal yet, or if this rate is lower
                    # (handles Bronze vs Expanded Bronze - keep lowest rate)
                    existing = lcp_lookup[loc_key].get(lookup_metal)
                    rate = float(row['lcp_rate']) if pd.notna(row['lcp_rate']) else 0.0
                    if existing is None or rate < existing['rate']:
                        lcp_lookup[loc_key][lookup_metal] = {
                            'rate': rate,
                            'plan_id': row.get('lcp_plan_id'),
                            'plan_name': row['plan_marketing_name'],
                            'actuarial_value': av_pct
                        }

                        # Collect unique AV values per metal level (from query results, not per-employee)
                        if av_pct is not None and lookup_metal in results:
                            results[lookup_metal]['_av_values'].append(av_pct)

            except (ValueError, TypeError) as e:
                for metal in metal_levels:
                    results[metal]['errors'].append(f"Batch query error: {str(e)}")

        # Process each employee using the batch lookup results
        for emp in employee_data:
            loc_rates = lcp_lookup.get(emp['location_key'], {})

            for metal in metal_levels:
                metal_data = loc_rates.get(metal)

                if metal_data:
                    lcp_rate = metal_data['rate']
                    plan_id = metal_data.get('plan_id')
                    plan_name = metal_data['plan_name']
                    actuarial_value = metal_data.get('actuarial_value')
                else:
                    lcp_rate = 0.0
                    plan_id = None
                    plan_name = None
                    actuarial_value = None
                    results[metal]['errors'].append(
                        f"No {metal} rate for {emp['state']} RA {emp['rating_area']}, age {emp['age_band']}"
                    )

                # Apply tier multiplier
                tier_multiplier = FinancialSummaryCalculator.TIER_MULTIPLIERS.get(emp['family_status'], 1.0)
                estimated_tier_premium = lcp_rate * tier_multiplier

                # Estimate lives based on tier
                lives = tier_lives.get(emp['family_status'], 1)

                # Store employee detail record
                results[metal]['employee_details'].append({
                    'employee_id': emp['employee_id'],
                    'first_name': emp['first_name'],
                    'last_name': emp['last_name'],
                    'state': emp['state'],
                    'rating_area': emp['rating_area'],
                    'family_status': emp['family_status'],
                    'ee_age': emp['ee_age'],
                    'lcp_plan_id': plan_id,
                    'lcp_plan_name': plan_name or 'No plan found',
                    'lcp_ee_rate': lcp_rate,
                    'tier_multiplier': tier_multiplier,
                    'estimated_tier_premium': estimated_tier_premium,
                    'actuarial_value': actuarial_value,
                    'current_ee_monthly': emp['current_ee'],
                    'current_er_monthly': emp['current_er'],
                    'gap_insurance_monthly': emp['gap_insurance'],
                    'current_total_monthly': emp['current_total'],
                    'projected_2026_premium': emp['projected_2026']
                })

                # Add to state totals
                state = emp['state']
                if state not in results[metal]['by_state']:
                    results[metal]['by_state'][state] = {
                        'employees': 0,
                        'lives': 0,
                        'monthly': 0.0,
                        'plan_name': f'Lowest Cost {metal} (varies by location)'
                    }

                results[metal]['by_state'][state]['employees'] += 1
                results[metal]['by_state'][state]['lives'] += lives
                results[metal]['by_state'][state]['monthly'] += estimated_tier_premium

                results[metal]['total_monthly'] += estimated_tier_premium
                results[metal]['employees_covered'] += 1
                results[metal]['lives_covered'] += lives

        # Calculate annual totals and average AV for each metal level
        for metal in metal_levels:
            results[metal]['total_annual'] = results[metal]['total_monthly'] * 12

            # Calculate average actuarial value from collected values
            av_values = results[metal].pop('_av_values', [])  # Remove temp list
            if av_values:
                results[metal]['average_av'] = round(sum(av_values) / len(av_values), 1)
            else:
                # Fallback to standard AV if no data
                fallback_av = {'Bronze': 60.0, 'Silver': 70.0, 'Gold': 80.0}
                results[metal]['average_av'] = fallback_av.get(metal)

        logging.info(f"MULTI-METAL: Complete in {time.time() - start_time:.2f}s")
        for metal in metal_levels:
            avg_av = results[metal].get('average_av', 'N/A')
            logging.info(f"  {metal}: ${results[metal]['total_monthly']:,.0f}/mo ({results[metal]['employees_covered']} employees, avg AV: {avg_av}%)")

        return results
