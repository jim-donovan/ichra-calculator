"""
SQL queries for ICHRA Calculator
All queries against pricing-proposal PostgreSQL database
"""

from typing import List, Optional
import pandas as pd
from database import DatabaseConnection


class PlanQueries:
    """SQL queries for plan data retrieval"""

    @staticmethod
    def get_available_states(db: DatabaseConnection) -> pd.DataFrame:
        """Get list of states with available Individual market plans"""
        query = """
        SELECT DISTINCT
            SUBSTRING(hios_plan_id FROM 6 FOR 2) as state_code,
            COUNT(DISTINCT hios_plan_id) as plan_count
        FROM rbis_insurance_plan_20251019202724
        WHERE market_coverage = 'Individual'
            AND plan_effective_date = '2026-01-01'
            AND plan_expiration_date = '2026-12-31'
        GROUP BY SUBSTRING(hios_plan_id FROM 6 FOR 2)
        ORDER BY state_code
        """
        return db.execute_query(query)

    @staticmethod
    def get_plans_by_filters(db: DatabaseConnection, state_code: Optional[str] = None,
                             state_codes: Optional[List[str]] = None,
                             metal_level: Optional[str] = None,
                             plan_type: Optional[str] = None) -> pd.DataFrame:
        """
        Get Individual market plans filtered by state(s), metal level, and plan type

        Args:
            db: Database connection
            state_code: Single two-letter state code (e.g., 'CA', 'NY') - deprecated, use state_codes
            state_codes: List of two-letter state codes for multi-state filtering
            metal_level: Bronze, Silver, Gold, Platinum
            plan_type: HMO, PPO, EPO, POS, etc.

        Returns:
            DataFrame of filtered plans
        """
        query = """
        SELECT
	p.hios_plan_id,
	p.plan_marketing_name,
	p.plan_type,
	p.level_of_coverage AS metal_level,
	p.network_id,
	p.service_area_id,
	p.formulary_id,
	SUBSTRING(p.hios_plan_id FROM 1 FOR 5) AS issuer_id,
	SUBSTRING(p.hios_plan_id FROM 6 FOR 2) AS state_code
FROM
	rbis_insurance_plan_20251019202724 p
	LEFT JOIN rbis_insurance_plan_variant_20251019202724 v ON p.hios_plan_id = v.hios_plan_id
WHERE
	p.market_coverage = 'Individual'
	AND p.plan_effective_date = '2026-01-01'
	AND v.csr_variation_type = 'Exchange variant (no CSR)'
        """

        filters = []
        params = []

        # Handle both single state_code (deprecated) and state_codes (preferred)
        if state_codes:
            placeholders = ', '.join(['%s'] * len(state_codes))
            filters.append(f"SUBSTRING(p.hios_plan_id FROM 6 FOR 2) IN ({placeholders})")
            params.extend(state_codes)
        elif state_code:
            filters.append("SUBSTRING(p.hios_plan_id FROM 6 FOR 2) = %s")
            params.append(state_code)

        if metal_level:
            filters.append("p.level_of_coverage = %s")
            params.append(metal_level)

        if plan_type:
            filters.append("p.plan_type = %s")
            params.append(plan_type)

        if filters:
            query += " AND " + " AND ".join(filters)

        query += " ORDER BY p.plan_marketing_name"

        return db.execute_query(query, tuple(params) if params else None)

    @staticmethod
    def get_plans_with_rating_area_coverage(db: DatabaseConnection, plan_ids: List[str],
                                           state_rating_areas: dict) -> pd.DataFrame:
        """
        Get rating area coverage info for plans across multiple states in a single query

        Args:
            db: Database connection
            plan_ids: List of HIOS plan IDs to check
            state_rating_areas: Dict mapping state codes to lists of required rating area integers
                               e.g., {'CA': [1, 2, 3], 'NY': [1, 2]}

        Returns:
            DataFrame with columns: hios_plan_id, state_code, num_areas_covered, covered_areas,
                                   num_employee_areas_covered, required_areas
        """
        if not plan_ids or not state_rating_areas:
            return pd.DataFrame()

        # Build CASE statements for each state's rating areas
        case_statements = []
        all_required_areas = []

        import re
        # Validate inputs to prevent SQL injection
        state_pattern = re.compile(r'^[A-Z]{2}$')

        for state, rating_areas in state_rating_areas.items():
            # Validate state code format (must be exactly 2 uppercase letters)
            if not state_pattern.match(str(state)):
                raise ValueError(f"Invalid state code format: {state}")

            # Validate rating areas are integers
            validated_areas = []
            for ra in rating_areas:
                if not isinstance(ra, (int, float)) or int(ra) != ra or int(ra) < 1 or int(ra) > 99:
                    raise ValueError(f"Invalid rating area: {ra}")
                validated_areas.append(int(ra))

            # Store required areas for this state (will be joined back later)
            for ra in validated_areas:
                all_required_areas.append((state, ra))

            # Create a CASE WHEN for counting employee area coverage per state
            # Safe to interpolate after validation above
            # Use regex extraction for safe integer conversion (handles malformed data)
            rating_area_list = ', '.join([str(ra) for ra in validated_areas])
            case_statements.append(f"""
                WHEN SUBSTRING(p.hios_plan_id, 6, 2) = '{state}'
                    AND br.rating_area_id ~ '^Rating Area [0-9]+$'
                    AND (REGEXP_REPLACE(br.rating_area_id, '[^0-9]', '', 'g'))::integer IN ({rating_area_list})
                THEN (REGEXP_REPLACE(br.rating_area_id, '[^0-9]', '', 'g'))::integer
            """)

        case_when_clause = '\n'.join(case_statements)
        plan_placeholders = ', '.join(['%s'] * len(plan_ids))

        query = f"""
        WITH plan_coverage AS (
            SELECT
                p.hios_plan_id,
                SUBSTRING(p.hios_plan_id, 6, 2) as state_code,
                COUNT(DISTINCT CASE
                    WHEN br.rating_area_id ~ '^Rating Area [0-9]+$'
                    THEN (REGEXP_REPLACE(br.rating_area_id, '[^0-9]', '', 'g'))::integer
                END) as num_areas_covered,
                ARRAY_AGG(DISTINCT CASE
                    WHEN br.rating_area_id ~ '^Rating Area [0-9]+$'
                    THEN (REGEXP_REPLACE(br.rating_area_id, '[^0-9]', '', 'g'))::integer
                END ORDER BY CASE
                    WHEN br.rating_area_id ~ '^Rating Area [0-9]+$'
                    THEN (REGEXP_REPLACE(br.rating_area_id, '[^0-9]', '', 'g'))::integer
                END) as covered_areas,
                COUNT(DISTINCT CASE
                    {case_when_clause}
                END) as num_employee_areas_covered
            FROM rbis_insurance_plan_base_rates_20251019202724 br
            JOIN rbis_insurance_plan_20251019202724 p ON br.plan_id = p.hios_plan_id
            WHERE p.hios_plan_id IN ({plan_placeholders})
                AND br.rating_area_id ~ '^Rating Area [0-9]+$'
            GROUP BY p.hios_plan_id
        )
        SELECT *
        FROM plan_coverage
        WHERE num_employee_areas_covered > 0
        ORDER BY state_code, num_employee_areas_covered DESC, num_areas_covered DESC
        """

        result = db.execute_query(query, tuple(plan_ids))

        # Add required_areas column by matching state
        if not result.empty:
            result['required_areas'] = result['state_code'].map(state_rating_areas)

        return result

    @staticmethod
    def get_plan_deductibles_moop(db: DatabaseConnection, hios_plan_ids: List[str]) -> pd.DataFrame:
        """
        Get deductible and MOOP information for specific plans

        Args:
            db: Database connection
            hios_plan_ids: List of HIOS Plan IDs

        Returns:
            DataFrame with deductible and MOOP amounts
        """
        if not hios_plan_ids:
            return pd.DataFrame()

        placeholders = ', '.join(['%s'] * len(hios_plan_ids))
        query = f"""
        SELECT
            plan_id as hios_plan_id,
            moop_ded_type as deductible_type,
            individual_ded_moop_amount as individual_amount,
            family_ded_moop_per_person as family_per_person,
            family_ded_moop_per_group as family_per_group,
            network_type
        FROM rbis_insurance_plan_variant_ddctbl_moop_20251019202724
        WHERE plan_id IN ({placeholders})
            AND network_type = 'In Network'
        """
        return db.execute_query(query, tuple(hios_plan_ids))

    @staticmethod
    def get_plan_rates_by_age(db: DatabaseConnection, plan_ids: List[str],
                               ages: List[int], rating_area_id: Optional[str] = None) -> pd.DataFrame:
        """
        Get premium rates for specific plans, ages, and rating area

        Args:
            db: Database connection
            plan_ids: List of HIOS Plan IDs
            ages: List of ages to retrieve rates for
            rating_area_id: Specific rating area (optional)

        Returns:
            DataFrame with premium rates
        """
        if not plan_ids or not ages:
            return pd.DataFrame()

        # Convert ages to strings
        age_list = [str(age) for age in ages]

        # Check if any plans are from family-tier rating states (NY, VT)
        # These states use "Family-Tier Rates" instead of age-based rating
        from constants import FAMILY_TIER_STATES
        has_family_tier_plans = any(
            plan_id[5:7] in FAMILY_TIER_STATES
            for plan_id in plan_ids
            if len(plan_id) >= 7
        )

        # Add "Family-Tier Rates" to age list if needed
        if has_family_tier_plans and "Family-Tier Rates" not in age_list:
            age_list.append("Family-Tier Rates")
            print("DEBUG: Added 'Family-Tier Rates' to age list for family-tier plans")

        print(f"DEBUG: Querying for ages: {age_list[:5]}..." if len(age_list) > 5 else f"DEBUG: Querying for ages: {age_list}")
        print(f"DEBUG: Querying for plan IDs: {plan_ids}")

        plan_placeholders = ', '.join(['%s'] * len(plan_ids))
        age_placeholders = ', '.join(['%s'] * len(age_list))

        query = f"""
        SELECT DISTINCT
            p.hios_plan_id,
            SUBSTRING(p.hios_plan_id, 6, 2) AS state_code,
            CASE
                WHEN br.rating_area_id ~ '^Rating Area [0-9]+$'
                THEN (REGEXP_REPLACE(br.rating_area_id, '[^0-9]', '', 'g'))::integer
                ELSE NULL
            END AS rating_area_id,
            br.age,
            br.individual_rate AS premium,
            br.rate_effective_date,
            br.rate_expiration_date
        FROM rbis_insurance_plan_base_rates_20251019202724 br
        JOIN rbis_insurance_plan_20251019202724 p
            ON br.plan_id = p.hios_plan_id
        WHERE p.hios_plan_id IN ({plan_placeholders})
        AND br.age IN ({age_placeholders})
        AND br.rate_effective_date = '2026-01-01'
        AND (br.tobacco IN ('No Preference', 'None', 'Tobacco User/Non-Tobacco User') OR br.tobacco IS NULL)
        """

        params = list(plan_ids) + age_list

        if rating_area_id:
            # rating_area_id comes as integer from census, but stored as 'Rating Area X' in DB
            # Use regex extraction for safe integer comparison
            query += " AND br.rating_area_id ~ '^Rating Area [0-9]+$' AND (REGEXP_REPLACE(br.rating_area_id, '[^0-9]', '', 'g'))::integer = %s"
            params.append(rating_area_id)

        query += " ORDER BY p.hios_plan_id, br.age"

        result_df = db.execute_query(query, tuple(params))

        # Log only if query returns empty (potential issue)
        if result_df.empty:
            import logging
            logging.warning(f"No rates found for plan_ids={plan_ids}, ages={age_list}, rating_area={rating_area_id}")

        return result_df

    @staticmethod
    def get_rating_area_by_county(db: DatabaseConnection, state: str, county: str) -> pd.DataFrame:
        """
        Get rating area for a specific county

        Args:
            db: Database connection
            state: Two-letter state code
            county: County name

        Returns:
            DataFrame with rating area information
        """
        # rating_area_id is already integer in rbis_state_rating_area_amended
        query = """
        SELECT
            state_code,
            county,
            rating_area_id,
            market
        FROM rbis_state_rating_area_amended
        WHERE UPPER(state_code) = UPPER(%s)
            AND UPPER(county) = UPPER(%s)
            AND market = 'Individual'
        LIMIT 1
        """
        return db.execute_query(query, (state, county))

    @staticmethod
    def get_rating_areas_batch(db: DatabaseConnection,
                                state_county_pairs: List[tuple]) -> pd.DataFrame:
        """
        Batch lookup rating areas for multiple (state, county) pairs.
        More efficient than calling get_rating_area_by_county() in a loop.

        Args:
            db: Database connection
            state_county_pairs: List of (state_code, county) tuples

        Returns:
            DataFrame with columns: state_code, county, rating_area_id
        """
        if not state_county_pairs:
            return pd.DataFrame(columns=['state_code', 'county', 'rating_area_id'])

        # Deduplicate pairs
        unique_pairs = list(set(state_county_pairs))

        # Build a query with multiple OR conditions
        conditions = []
        params = []
        for state, county in unique_pairs:
            conditions.append("(UPPER(state_code) = UPPER(%s) AND UPPER(county) = UPPER(%s))")
            params.extend([state, county])

        where_clause = " OR ".join(conditions)

        # rating_area_id is already integer in rbis_state_rating_area_amended
        query = f"""
        SELECT DISTINCT
            UPPER(state_code) as state_code,
            UPPER(county) as county,
            rating_area_id
        FROM rbis_state_rating_area_amended
        WHERE ({where_clause})
            AND market = 'Individual'
        """
        return db.execute_query(query, tuple(params))

    @staticmethod
    def get_counties_by_state(db: DatabaseConnection, state: str) -> pd.DataFrame:
        """
        Get all counties for a specific state

        Args:
            db: Database connection
            state: Two-letter state code

        Returns:
            DataFrame with county list
        """
        # rating_area_id is already integer in rbis_state_rating_area_amended
        query = """
        SELECT DISTINCT
            state_code,
            county,
            rating_area_id,
            market
        FROM rbis_state_rating_area_amended
        WHERE UPPER(state_code) = UPPER(%s)
            AND market = 'Individual'
        ORDER BY county
        """
        return db.execute_query(query, (state,))

    @staticmethod
    def get_county_by_zip(db: DatabaseConnection, zip_code: str, state_code: str) -> pd.DataFrame:
        """
        Get county name and rating area for a ZIP code

        Args:
            db: Database connection
            zip_code: 5-digit ZIP code (as string with leading zeros)
            state_code: Two-letter state code (e.g., 'NY', 'CA')

        Returns:
            DataFrame with county, rating_area_id, and state_code
        """
        import logging
        import time

        # Handle ZIP+4 format (e.g., "29654-7352" -> "29654") and ensure 5 digits
        zip_code = str(zip_code).strip().split('-')[0].zfill(5)[:5]
        logging.debug(f"ZIP LOOKUP: Looking up {zip_code} in {state_code}")

        # rating_area_id is already integer in rbis_state_rating_area_amended
        query = """
        SELECT
            ra.state_code,
            ra.county,
            ra.rating_area_id,
            zc."USPS Default City for ZIP" as city
        FROM zip_to_county_correct zc
        JOIN rbis_state_rating_area_amended ra
            ON zc."County FIPS code" = ra."FIPS"
        WHERE zc."ZIP" = %s
            AND UPPER(zc."State") = UPPER(%s)
            AND ra.market = 'Individual'
        LIMIT 1
        """

        query_start = time.time()
        logging.debug(f"ZIP LOOKUP: Executing primary query for {zip_code}...")
        result = db.execute_query(query, (zip_code, state_code))
        logging.debug(f"ZIP LOOKUP: Primary query took {time.time() - query_start:.3f}s, got {len(result)} rows")

        if result.empty:
            # Try fallback using 3-digit ZIP prefix from original rating area table
            # This is needed for counties missing from amended table (e.g., Los Angeles County CA)

            # Get state full name for lookup
            state_name_map = {
                'CA': 'California', 'NY': 'New York', 'TX': 'Texas', 'FL': 'Florida',
                'IL': 'Illinois', 'PA': 'Pennsylvania', 'OH': 'Ohio', 'GA': 'Georgia',
                'NC': 'North Carolina', 'MI': 'Michigan', 'NJ': 'New Jersey', 'VA': 'Virginia',
                'WA': 'Washington', 'AZ': 'Arizona', 'MA': 'Massachusetts', 'TN': 'Tennessee',
                'IN': 'Indiana', 'MO': 'Missouri', 'MD': 'Maryland', 'WI': 'Wisconsin',
                'CO': 'Colorado', 'MN': 'Minnesota', 'SC': 'South Carolina', 'AL': 'Alabama',
                'LA': 'Louisiana', 'KY': 'Kentucky', 'OR': 'Oregon', 'OK': 'Oklahoma',
                'CT': 'Connecticut', 'IA': 'Iowa', 'MS': 'Mississippi', 'AR': 'Arkansas',
                'UT': 'Utah', 'KS': 'Kansas', 'NV': 'Nevada', 'NM': 'New Mexico',
                'NE': 'Nebraska', 'WV': 'West Virginia', 'ID': 'Idaho', 'HI': 'Hawaii',
                'NH': 'New Hampshire', 'ME': 'Maine', 'RI': 'Rhode Island', 'MT': 'Montana',
                'DE': 'Delaware', 'SD': 'South Dakota', 'ND': 'North Dakota', 'AK': 'Alaska',
                'VT': 'Vermont', 'WY': 'Wyoming', 'DC': 'District of Columbia'
            }

            state_full_name = state_name_map.get(state_code.upper(), None)

            if state_full_name:
                # Extract 3-digit ZIP prefix
                zip_prefix = zip_code[:3]

                fallback_query = """
                SELECT
                    %s as state_code,
                    county,
                    rating_area_id,
                    '' as city
                FROM rbis_state_rating_area_20251019202724
                WHERE state = %s
                    AND three_digit_zip = %s
                    AND market = 'Individual'
                LIMIT 1
                """

                result = db.execute_query(fallback_query, (state_code, state_full_name, zip_prefix))

                if not result.empty:
                    # Successfully found via ZIP prefix fallback
                    return result

            # If still empty, provide diagnostic info
            zip_check = db.execute_query(
                "SELECT * FROM zip_to_county_correct WHERE \"ZIP\" = %s AND UPPER(\"State\") = UPPER(%s)",
                (zip_code, state_code)
            )
            if zip_check.empty:
                print(f"⚠ ZIP code {zip_code} not found for state {state_code}")
            else:
                fips = zip_check.iloc[0]['County FIPS code']
                print(f"⚠ ZIP {zip_code} (FIPS {fips}) not found in rating area tables (tried both amended and original)")

        return result

    @staticmethod
    def get_lcsp_by_rating_area(db: DatabaseConnection, state_code: str,
                                 rating_area_id: int, age_band: str) -> pd.DataFrame:
        """
        Get the Lowest Cost Silver Plan (LCSP) for a specific rating area and age band.

        The LCSP is the benchmark for ICHRA affordability safe harbor compliance.
        This returns the single lowest-premium Silver plan available in the given
        rating area for the specified age band.

        Args:
            db: Database connection
            state_code: Two-letter state code (e.g., 'CA', 'NY')
            rating_area_id: Rating area as integer (e.g., 1, 2, 3)
            age_band: Age band string (e.g., "0-14", "35", "64 and over", "Family-Tier Rates")

        Returns:
            DataFrame with columns: hios_plan_id, plan_name, state_code,
                                   rating_area_id, age, premium
            Returns single row (the LCSP) or empty if no plans found.
        """
        query = """
        SELECT
            p.hios_plan_id,
            p.plan_marketing_name as plan_name,
            SUBSTRING(p.hios_plan_id, 6, 2) AS state_code,
            CASE
                WHEN br.rating_area_id ~ '^Rating Area [0-9]+$'
                THEN (REGEXP_REPLACE(br.rating_area_id, '[^0-9]', '', 'g'))::integer
                ELSE NULL
            END AS rating_area_id,
            br.age,
            br.individual_rate as premium
        FROM rbis_insurance_plan_base_rates_20251019202724 br
        JOIN rbis_insurance_plan_20251019202724 p ON br.plan_id = p.hios_plan_id
        JOIN rbis_insurance_plan_variant_20251019202724 v ON p.hios_plan_id = v.hios_plan_id
        WHERE p.level_of_coverage = 'Silver'
            AND p.market_coverage = 'Individual'
            AND v.csr_variation_type = 'Exchange variant (no CSR)'
            AND SUBSTRING(p.hios_plan_id, 6, 2) = %s
            AND br.rating_area_id ~ '^Rating Area [0-9]+$'
            AND (REGEXP_REPLACE(br.rating_area_id, '[^0-9]', '', 'g'))::integer = %s
            AND br.age = %s
            AND br.rate_effective_date = '2026-01-01'
            AND (br.tobacco IN ('No Preference', 'None', 'Tobacco User/Non-Tobacco User') OR br.tobacco IS NULL)
        ORDER BY br.individual_rate ASC
        LIMIT 1
        """
        return db.execute_query(query, (state_code, rating_area_id, age_band))

    @staticmethod
    def get_lcsp_for_employees_batch(db: DatabaseConnection,
                                      employee_locations: list) -> pd.DataFrame:
        """
        Get LCSP for multiple (state, rating_area, age_band) combinations in one query.

        More efficient than calling get_lcsp_by_rating_area() multiple times.

        Args:
            db: Database connection
            employee_locations: List of dicts with keys: state_code, rating_area_id, age_band
                               e.g., [{'state_code': 'CA', 'rating_area_id': 1, 'age_band': '35'}, ...]

        Returns:
            DataFrame with columns: hios_plan_id, plan_name, state_code,
                                   rating_area_id, age_band, premium
        """
        import logging
        import time
        logging.info(f"LCSP BATCH: Called with {len(employee_locations)} locations")
        batch_start = time.time()

        if not employee_locations:
            return pd.DataFrame()

        # Deduplicate combinations
        unique_combos = []
        seen = set()
        for loc in employee_locations:
            key = (loc['state_code'], loc['rating_area_id'], loc['age_band'])
            if key not in seen:
                seen.add(key)
                unique_combos.append(loc)

        logging.info(f"LCSP BATCH: {len(unique_combos)} unique combinations after dedup")

        if not unique_combos:
            return pd.DataFrame()

        # Build UNION ALL query for each unique combination
        # This allows us to get the LCSP for each combo in a single round-trip
        union_queries = []
        params = []

        for combo in unique_combos:
            union_queries.append("""
            (SELECT
                p.hios_plan_id,
                p.plan_marketing_name as plan_name,
                SUBSTRING(p.hios_plan_id, 6, 2) AS state_code,
                CASE
                    WHEN br.rating_area_id ~ '^Rating Area [0-9]+$'
                    THEN (REGEXP_REPLACE(br.rating_area_id, '[^0-9]', '', 'g'))::integer
                    ELSE NULL
                END AS rating_area_id,
                br.age as age_band,
                br.individual_rate as premium
            FROM rbis_insurance_plan_base_rates_20251019202724 br
            JOIN rbis_insurance_plan_20251019202724 p ON br.plan_id = p.hios_plan_id
            JOIN rbis_insurance_plan_variant_20251019202724 v ON p.hios_plan_id = v.hios_plan_id
            WHERE p.level_of_coverage = 'Silver'
                AND p.market_coverage = 'Individual'
                AND v.csr_variation_type = 'Exchange variant (no CSR)'
                AND SUBSTRING(p.hios_plan_id, 6, 2) = %s
                AND br.rating_area_id ~ '^Rating Area [0-9]+$'
                AND (REGEXP_REPLACE(br.rating_area_id, '[^0-9]', '', 'g'))::integer = %s
                AND br.age = %s
                AND br.rate_effective_date = '2026-01-01'
                AND (br.tobacco IN ('No Preference', 'None', 'Tobacco User/Non-Tobacco User') OR br.tobacco IS NULL)
            ORDER BY br.individual_rate ASC
            LIMIT 1)
            """)
            params.extend([combo['state_code'], combo['rating_area_id'], combo['age_band']])

        query = "\nUNION ALL\n".join(union_queries)
        logging.info(f"LCSP BATCH: Executing query with {len(unique_combos)} UNION ALLs...")
        query_start = time.time()
        result = db.execute_query(query, tuple(params))
        logging.info(f"LCSP BATCH: Query completed in {time.time() - query_start:.2f}s, returned {len(result)} rows")
        logging.info(f"LCSP BATCH: Total batch time: {time.time() - batch_start:.2f}s")
        return result

    @staticmethod
    def get_lowest_cost_plan_by_rating_area(db: DatabaseConnection, state_code: str,
                                             rating_area_id: int, age_band: str,
                                             metal_level: str = 'Silver') -> pd.DataFrame:
        """
        Get the Lowest Cost Plan for a specific metal level, rating area, and age band.

        Generalizes get_lcsp_by_rating_area() to support Bronze, Silver, or Gold.
        For Silver, this returns the LCSP (Lowest Cost Silver Plan) used for IRS affordability.
        For Bronze/Gold, returns the lowest cost plan at that metal level.

        Args:
            db: Database connection
            state_code: Two-letter state code (e.g., 'CA', 'NY')
            rating_area_id: Rating area as integer (e.g., 1, 2, 3)
            age_band: Age band string (e.g., "0-14", "35", "64 and over", "Family-Tier Rates")
            metal_level: Metal tier - 'Bronze', 'Silver', or 'Gold' (default: 'Silver')

        Returns:
            DataFrame with columns: hios_plan_id, plan_name, state_code,
                                   rating_area_id, age, premium, metal_level
            Returns single row (the lowest cost plan) or empty if no plans found.
        """
        query = """
        SELECT
            p.hios_plan_id,
            p.plan_marketing_name as plan_name,
            SUBSTRING(p.hios_plan_id, 6, 2) AS state_code,
            CASE
                WHEN br.rating_area_id ~ '^Rating Area [0-9]+$'
                THEN (REGEXP_REPLACE(br.rating_area_id, '[^0-9]', '', 'g'))::integer
                ELSE NULL
            END AS rating_area_id,
            br.age,
            br.individual_rate as premium,
            p.level_of_coverage as metal_level
        FROM rbis_insurance_plan_base_rates_20251019202724 br
        JOIN rbis_insurance_plan_20251019202724 p ON br.plan_id = p.hios_plan_id
        JOIN rbis_insurance_plan_variant_20251019202724 v ON p.hios_plan_id = v.hios_plan_id
        WHERE p.level_of_coverage = %s
            AND p.market_coverage = 'Individual'
            AND v.csr_variation_type = 'Exchange variant (no CSR)'
            AND SUBSTRING(p.hios_plan_id, 6, 2) = %s
            AND br.rating_area_id ~ '^Rating Area [0-9]+$'
            AND (REGEXP_REPLACE(br.rating_area_id, '[^0-9]', '', 'g'))::integer = %s
            AND br.age = %s
            AND br.rate_effective_date = '2026-01-01'
            AND (br.tobacco IN ('No Preference', 'None', 'Tobacco User/Non-Tobacco User') OR br.tobacco IS NULL)
        ORDER BY br.individual_rate ASC
        LIMIT 1
        """
        return db.execute_query(query, (metal_level, state_code, rating_area_id, age_band))

    @staticmethod
    def get_lowest_cost_plans_batch(db: DatabaseConnection,
                                     employee_locations: list,
                                     metal_level: str = 'Silver') -> pd.DataFrame:
        """
        Get lowest cost plan for multiple (state, rating_area, age_band) combinations in one query.

        Generalizes get_lcsp_for_employees_batch() to support Bronze, Silver, or Gold.
        More efficient than calling get_lowest_cost_plan_by_rating_area() multiple times.

        Args:
            db: Database connection
            employee_locations: List of dicts with keys: state_code, rating_area_id, age_band
                               e.g., [{'state_code': 'CA', 'rating_area_id': 1, 'age_band': '35'}, ...]
            metal_level: Metal tier - 'Bronze', 'Silver', or 'Gold' (default: 'Silver')

        Returns:
            DataFrame with columns: hios_plan_id, plan_name, state_code,
                                   rating_area_id, age_band, premium, metal_level
        """
        import logging
        import time
        logging.info(f"LCP BATCH [{metal_level}]: Called with {len(employee_locations)} locations")
        batch_start = time.time()

        if not employee_locations:
            return pd.DataFrame()

        # Deduplicate combinations
        unique_combos = []
        seen = set()
        for loc in employee_locations:
            key = (loc['state_code'], loc['rating_area_id'], loc['age_band'])
            if key not in seen:
                seen.add(key)
                unique_combos.append(loc)

        logging.info(f"LCP BATCH [{metal_level}]: {len(unique_combos)} unique combinations after dedup")

        if not unique_combos:
            return pd.DataFrame()

        # Build UNION ALL query for each unique combination
        union_queries = []
        params = []

        for combo in unique_combos:
            union_queries.append("""
            (SELECT
                p.hios_plan_id,
                p.plan_marketing_name as plan_name,
                SUBSTRING(p.hios_plan_id, 6, 2) AS state_code,
                CASE
                    WHEN br.rating_area_id ~ '^Rating Area [0-9]+$'
                    THEN (REGEXP_REPLACE(br.rating_area_id, '[^0-9]', '', 'g'))::integer
                    ELSE NULL
                END AS rating_area_id,
                br.age as age_band,
                br.individual_rate as premium,
                p.level_of_coverage as metal_level
            FROM rbis_insurance_plan_base_rates_20251019202724 br
            JOIN rbis_insurance_plan_20251019202724 p ON br.plan_id = p.hios_plan_id
            JOIN rbis_insurance_plan_variant_20251019202724 v ON p.hios_plan_id = v.hios_plan_id
            WHERE p.level_of_coverage = %s
                AND p.market_coverage = 'Individual'
                AND v.csr_variation_type = 'Exchange variant (no CSR)'
                AND SUBSTRING(p.hios_plan_id, 6, 2) = %s
                AND br.rating_area_id ~ '^Rating Area [0-9]+$'
                AND (REGEXP_REPLACE(br.rating_area_id, '[^0-9]', '', 'g'))::integer = %s
                AND br.age = %s
                AND br.rate_effective_date = '2026-01-01'
                AND (br.tobacco IN ('No Preference', 'None', 'Tobacco User/Non-Tobacco User') OR br.tobacco IS NULL)
            ORDER BY br.individual_rate ASC
            LIMIT 1)
            """)
            params.extend([metal_level, combo['state_code'], combo['rating_area_id'], combo['age_band']])

        query = "\nUNION ALL\n".join(union_queries)
        logging.info(f"LCP BATCH [{metal_level}]: Executing query with {len(unique_combos)} UNION ALLs...")
        query_start = time.time()
        result = db.execute_query(query, tuple(params))
        logging.info(f"LCP BATCH [{metal_level}]: Query completed in {time.time() - query_start:.2f}s, returned {len(result)} rows")
        logging.info(f"LCP BATCH [{metal_level}]: Total batch time: {time.time() - batch_start:.2f}s")
        return result

    @staticmethod
    def get_lowest_cost_plans_all_metals_batch(db: DatabaseConnection,
                                                employee_locations: list,
                                                metal_levels: list = None) -> pd.DataFrame:
        """
        Get lowest cost plans for ALL metal levels in a single efficient query.

        Fetches Bronze, Silver, and Gold lowest-cost plans for all employee locations
        in one database round-trip using a combined UNION ALL query.

        Args:
            db: Database connection
            employee_locations: List of dicts with keys: state_code, rating_area_id, age_band
            metal_levels: List of metal levels to query (default: ['Bronze', 'Silver', 'Gold'])

        Returns:
            DataFrame with columns: hios_plan_id, plan_name, state_code,
                                   rating_area_id, age_band, premium, metal_level
            Contains one row per (location, metal_level) combination.
        """
        import logging
        import time

        if metal_levels is None:
            metal_levels = ['Bronze', 'Silver', 'Gold']

        logging.info(f"LCP ALL METALS BATCH: Called with {len(employee_locations)} locations, metals: {metal_levels}")
        batch_start = time.time()

        if not employee_locations:
            return pd.DataFrame()

        # Deduplicate combinations
        unique_combos = []
        seen = set()
        for loc in employee_locations:
            key = (loc['state_code'], loc['rating_area_id'], loc['age_band'])
            if key not in seen:
                seen.add(key)
                unique_combos.append(loc)

        logging.info(f"LCP ALL METALS BATCH: {len(unique_combos)} unique location combinations")

        if not unique_combos:
            return pd.DataFrame()

        # Build UNION ALL query for each (location, metal_level) combination
        union_queries = []
        params = []

        for combo in unique_combos:
            for metal in metal_levels:
                union_queries.append("""
                (SELECT
                    p.hios_plan_id,
                    p.plan_marketing_name as plan_name,
                    SUBSTRING(p.hios_plan_id, 6, 2) AS state_code,
                    CASE
                        WHEN br.rating_area_id ~ '^Rating Area [0-9]+$'
                        THEN (REGEXP_REPLACE(br.rating_area_id, '[^0-9]', '', 'g'))::integer
                        ELSE NULL
                    END AS rating_area_id,
                    br.age as age_band,
                    br.individual_rate as premium,
                    p.level_of_coverage as metal_level
                FROM rbis_insurance_plan_base_rates_20251019202724 br
                JOIN rbis_insurance_plan_20251019202724 p ON br.plan_id = p.hios_plan_id
                JOIN rbis_insurance_plan_variant_20251019202724 v ON p.hios_plan_id = v.hios_plan_id
                WHERE p.level_of_coverage = %s
                    AND p.market_coverage = 'Individual'
                    AND v.csr_variation_type = 'Exchange variant (no CSR)'
                    AND SUBSTRING(p.hios_plan_id, 6, 2) = %s
                    AND br.rating_area_id ~ '^Rating Area [0-9]+$'
                    AND (REGEXP_REPLACE(br.rating_area_id, '[^0-9]', '', 'g'))::integer = %s
                    AND br.age = %s
                    AND br.rate_effective_date = '2026-01-01'
                    AND (br.tobacco IN ('No Preference', 'None', 'Tobacco User/Non-Tobacco User') OR br.tobacco IS NULL)
                ORDER BY br.individual_rate ASC
                LIMIT 1)
                """)
                params.extend([metal, combo['state_code'], combo['rating_area_id'], combo['age_band']])

        query = "\nUNION ALL\n".join(union_queries)
        total_queries = len(unique_combos) * len(metal_levels)
        logging.info(f"LCP ALL METALS BATCH: Executing query with {total_queries} UNION ALLs ({len(unique_combos)} locations x {len(metal_levels)} metals)...")
        query_start = time.time()
        result = db.execute_query(query, tuple(params))
        logging.info(f"LCP ALL METALS BATCH: Query completed in {time.time() - query_start:.2f}s, returned {len(result)} rows")
        logging.info(f"LCP ALL METALS BATCH: Total batch time: {time.time() - batch_start:.2f}s")
        return result


class ComprehensivePlanQueries:
    """SQL queries for comprehensive plan data retrieval"""

    @staticmethod
    def get_full_plan_details(db: DatabaseConnection, hios_plan_id: str) -> pd.DataFrame:
        """
        Get ALL fields from rbis_insurance_plan for a specific plan

        Args:
            db: Database connection
            hios_plan_id: HIOS Plan ID

        Returns:
            DataFrame with all plan fields
        """
        query = """
        SELECT *
        FROM rbis_insurance_plan_20251019202724
        WHERE hios_plan_id = %s
        """
        return db.execute_query(query, (hios_plan_id,))

    @staticmethod
    def get_plan_variant_details(db: DatabaseConnection, hios_plan_id: str,
                                  csr_type: str = 'Exchange variant (no CSR)') -> pd.DataFrame:
        """
        Get ALL fields from rbis_insurance_plan_variant for a specific plan and CSR type
        Includes plan_brochure and url_for_summary_of_benefits_and_coverage

        Args:
            db: Database connection
            hios_plan_id: HIOS Plan ID
            csr_type: CSR variation type (default: 'Exchange variant (no CSR)')

        Returns:
            DataFrame with all variant fields including document URLs
        """
        query = """
        SELECT *
        FROM rbis_insurance_plan_variant_20251019202724
        WHERE hios_plan_id = %s
            AND csr_variation_type = %s
        """
        return db.execute_query(query, (hios_plan_id, csr_type))

    @staticmethod
    def get_plan_document_urls_batch(db: DatabaseConnection, plan_ids: list,
                                      csr_type: str = 'Exchange variant (no CSR)') -> pd.DataFrame:
        """
        Get brochure and SBC URLs for multiple plans at once.

        Args:
            db: Database connection
            plan_ids: List of HIOS Plan IDs
            csr_type: CSR variation type (default: 'Exchange variant (no CSR)')

        Returns:
            DataFrame with hios_plan_id, plan_brochure, url_for_summary_of_benefits_and_coverage
        """
        if not plan_ids:
            return pd.DataFrame()

        placeholders = ', '.join(['%s'] * len(plan_ids))
        query = f"""
        SELECT hios_plan_id, plan_brochure, url_for_summary_of_benefits_and_coverage
        FROM rbis_insurance_plan_variant_20251019202724
        WHERE hios_plan_id IN ({placeholders})
            AND csr_variation_type = %s
        """
        params = tuple(plan_ids) + (csr_type,)
        return db.execute_query(query, params)

    @staticmethod
    def get_plan_benefits_full(db: DatabaseConnection, hios_plan_id: str) -> pd.DataFrame:
        """
        Get ALL fields from rbis_insurance_plan_benefits for a specific plan

        Args:
            db: Database connection
            hios_plan_id: HIOS Plan ID

        Returns:
            DataFrame with all benefit coverage fields
        """
        query = """
        SELECT *
        FROM rbis_insurance_plan_benefits_20251019202724
        WHERE hios_plan_id = %s
        ORDER BY benefit
        """
        return db.execute_query(query, (hios_plan_id,))

    @staticmethod
    def get_plan_benefit_cost_share_full(db: DatabaseConnection, hios_plan_id: str,
                                          csr_type: str = 'Exchange variant (no CSR)') -> pd.DataFrame:
        """
        Get ALL fields from rbis_insurance_plan_benefit_cost_share for a specific plan

        Args:
            db: Database connection
            hios_plan_id: HIOS Plan ID
            csr_type: CSR variation type (default: 'Exchange variant (no CSR)')

        Returns:
            DataFrame with all benefit cost-sharing fields
        """
        query = """
        SELECT *
        FROM rbis_insurance_plan_benefit_cost_share_20251019202724
        WHERE hios_plan_id = %s
            AND csr_variation_type = %s
        ORDER BY benefit, network_type
        """
        return db.execute_query(query, (hios_plan_id, csr_type))

    @staticmethod
    def get_plan_deductibles_moop_full(db: DatabaseConnection, hios_plan_id: str,
                                        variant: str = 'Exchange variant (no CSR)') -> pd.DataFrame:
        """
        Get ALL fields from rbis_insurance_plan_variant_ddctbl_moop for a specific plan

        Args:
            db: Database connection
            hios_plan_id: HIOS Plan ID
            variant: Variant component (default: 'Exchange variant (no CSR)')

        Returns:
            DataFrame with all deductible/MOOP fields
        """
        query = """
        SELECT *
        FROM rbis_insurance_plan_variant_ddctbl_moop_20251019202724
        WHERE plan_id = %s
            AND variant_component = %s
        ORDER BY moop_ded_type, network_type
        """
        return db.execute_query(query, (hios_plan_id, variant))

    @staticmethod
    def get_plan_sbc_scenarios(db: DatabaseConnection, hios_plan_id: str,
                                variant: str = 'Exchange variant (no CSR)') -> pd.DataFrame:
        """
        Get ALL fields from rbis_insurance_plan_variant_sbc_scenario for a specific plan

        Args:
            db: Database connection
            hios_plan_id: HIOS Plan ID
            variant: Variant component (default: 'Exchange variant (no CSR)')

        Returns:
            DataFrame with all SBC scenario fields
        """
        query = """
        SELECT *
        FROM rbis_insurance_plan_variant_sbc_scenario_20251019202724
        WHERE plan_id = %s
            AND variant_component = %s
        ORDER BY sbc_coverage_name
        """
        return db.execute_query(query, (hios_plan_id, variant))


class CostEstimatorQueries:
    """SQL queries for the Best Plan Advisor / Cost Estimator feature"""

    @staticmethod
    def get_plan_copays(db: DatabaseConnection, plan_ids: List[str]) -> pd.DataFrame:
        """
        Get copay/coinsurance amounts for key services used in cost estimation.

        Returns copays for: PCP visits, specialist visits, generic Rx, brand Rx,
        specialty Rx, ER, urgent care, mental health, and inpatient hospital.

        Args:
            db: Database connection
            plan_ids: List of HIOS Plan IDs

        Returns:
            DataFrame with columns: hios_plan_id, benefit, copay, coinsurance, network_type
        """
        if not plan_ids:
            return pd.DataFrame()

        placeholders = ', '.join(['%s'] * len(plan_ids))

        # Key benefits we need for cost estimation
        query = f"""
        SELECT
            hios_plan_id,
            benefit,
            co_payment as copay,
            co_insurance as coinsurance,
            network_type
        FROM rbis_insurance_plan_benefit_cost_share_20251019202724
        WHERE hios_plan_id IN ({placeholders})
            AND csr_variation_type = 'Exchange variant (no CSR)'
            AND network_type = 'In Network'
            AND (
                LOWER(benefit) LIKE '%%primary care%%'
                OR LOWER(benefit) LIKE '%%specialist visit%%'
                OR LOWER(benefit) LIKE '%%generic drug%%'
                OR LOWER(benefit) LIKE '%%preferred brand drug%%'
                OR LOWER(benefit) LIKE '%%non-preferred brand%%'
                OR LOWER(benefit) LIKE '%%specialty drug%%'
                OR LOWER(benefit) LIKE '%%emergency room%%'
                OR LOWER(benefit) LIKE '%%urgent care%%'
                OR LOWER(benefit) LIKE '%%mental health outpatient%%'
                OR LOWER(benefit) LIKE '%%inpatient hospital%%'
                OR LOWER(benefit) LIKE '%%outpatient facility%%'
            )
        ORDER BY hios_plan_id, benefit
        """
        return db.execute_query(query, tuple(plan_ids))

    @staticmethod
    def get_plan_sbc_scenarios(db: DatabaseConnection, plan_ids: List[str]) -> pd.DataFrame:
        """
        Get SBC (Summary of Benefits and Coverage) scenario costs for plans.

        Returns estimated costs for standard scenarios like "Having a Baby"
        and "Managing Type 2 Diabetes".

        Args:
            db: Database connection
            plan_ids: List of HIOS Plan IDs

        Returns:
            DataFrame with columns: plan_id, sbc_coverage_name, sbc_deductible_amount,
                                   sbc_copayment_amount, sbc_coinsurance_amount, sbc_limit_amount
        """
        if not plan_ids:
            return pd.DataFrame()

        placeholders = ', '.join(['%s'] * len(plan_ids))

        query = f"""
        SELECT
            plan_id,
            sbc_coverage_name,
            sbc_deductible_amount,
            sbc_copayment_amount,
            sbc_coinsurance_amount,
            sbc_limit_amount
        FROM rbis_insurance_plan_variant_sbc_scenario_20251019202724
        WHERE plan_id IN ({placeholders})
            AND variant_component = 'Exchange variant (no CSR)'
        ORDER BY plan_id, sbc_coverage_name
        """
        return db.execute_query(query, tuple(plan_ids))

    @staticmethod
    def get_plan_deductible_and_moop(db: DatabaseConnection, plan_ids: List[str]) -> pd.DataFrame:
        """
        Get individual in-network deductible and MOOP for cost estimation.

        Args:
            db: Database connection
            plan_ids: List of HIOS Plan IDs

        Returns:
            DataFrame with columns: plan_id, deductible, moop
        """
        if not plan_ids:
            return pd.DataFrame()

        placeholders = ', '.join(['%s'] * len(plan_ids))

        query = f"""
        SELECT
            plan_id,
            moop_ded_type,
            individual_ded_moop_amount
        FROM rbis_insurance_plan_variant_ddctbl_moop_20251019202724
        WHERE plan_id IN ({placeholders})
            AND variant_component = 'Exchange variant (no CSR)'
            AND network_type = 'In Network'
            AND (
                LOWER(moop_ded_type) LIKE '%%deductible%%'
                OR LOWER(moop_ded_type) LIKE '%%maximum out of pocket%%'
            )
        ORDER BY plan_id, moop_ded_type
        """
        return db.execute_query(query, tuple(plan_ids))

    @staticmethod
    def get_plan_cost_sharing_for_ai(db: DatabaseConnection, plan_ids: List[str]) -> dict:
        """
        Get high-impact cost-sharing data for AI recommendation.

        Fetches deductibles, MOOP, hospital coinsurance, and ER costs
        for both in-network and out-of-network to help AI evaluate
        the true cost/risk profile of each plan.

        Args:
            db: Database connection
            plan_ids: List of HIOS Plan IDs

        Returns:
            Dict keyed by plan_id with cost-sharing details:
            {
                'plan_id': {
                    'deductible_in_network': float,
                    'deductible_out_of_network': float,
                    'moop_in_network': float,
                    'moop_out_of_network': float,
                    'hospital_coinsurance_in_network': str,
                    'hospital_coinsurance_out_of_network': str,
                    'er_cost': str,
                }
            }
        """
        if not plan_ids:
            return {}

        placeholders = ', '.join(['%s'] * len(plan_ids))

        # Query 1: Deductibles and MOOP (both networks)
        ded_moop_query = f"""
        SELECT
            plan_id,
            network_type,
            moop_ded_type,
            individual_ded_moop_amount
        FROM rbis_insurance_plan_variant_ddctbl_moop_20251019202724
        WHERE plan_id IN ({placeholders})
            AND variant_component = 'Exchange variant (no CSR)'
            AND (
                LOWER(moop_ded_type) LIKE '%%medical ehb deductible%%'
                OR LOWER(moop_ded_type) LIKE '%%maximum out of pocket%%'
            )
        ORDER BY plan_id, network_type, moop_ded_type
        """
        ded_moop_df = db.execute_query(ded_moop_query, tuple(plan_ids))

        # Query 2: Hospital and ER coinsurance (both networks)
        coinsurance_query = f"""
        SELECT
            hios_plan_id as plan_id,
            network_type,
            benefit,
            co_payment as copay,
            co_insurance as coinsurance
        FROM rbis_insurance_plan_benefit_cost_share_20251019202724
        WHERE hios_plan_id IN ({placeholders})
            AND csr_variation_type = 'Exchange variant (no CSR)'
            AND (
                LOWER(benefit) LIKE '%%inpatient hospital%%'
                OR LOWER(benefit) LIKE '%%emergency room%%'
            )
        ORDER BY hios_plan_id, network_type, benefit
        """
        coinsurance_df = db.execute_query(coinsurance_query, tuple(plan_ids))

        # Build result dict
        result = {}
        for plan_id in plan_ids:
            result[plan_id] = {
                'deductible_in_network': None,
                'deductible_out_of_network': None,
                'moop_in_network': None,
                'moop_out_of_network': None,
                'hospital_coinsurance_in_network': None,
                'hospital_coinsurance_out_of_network': None,
                'er_cost': None,
            }

        # Parse deductible/MOOP data
        if not ded_moop_df.empty:
            for _, row in ded_moop_df.iterrows():
                plan_id = row['plan_id']
                if plan_id not in result:
                    continue

                network = row['network_type']
                moop_type = row['moop_ded_type'].lower() if row['moop_ded_type'] else ''
                amount = row['individual_ded_moop_amount']

                if 'deductible' in moop_type:
                    if network == 'In Network':
                        result[plan_id]['deductible_in_network'] = amount
                    elif network == 'Out of Network':
                        result[plan_id]['deductible_out_of_network'] = amount
                elif 'maximum out of pocket' in moop_type:
                    if network == 'In Network':
                        result[plan_id]['moop_in_network'] = amount
                    elif network == 'Out of Network':
                        result[plan_id]['moop_out_of_network'] = amount

        # Parse coinsurance data
        if not coinsurance_df.empty:
            for _, row in coinsurance_df.iterrows():
                plan_id = row['plan_id']
                if plan_id not in result:
                    continue

                network = row['network_type']
                benefit = row['benefit'].lower() if row['benefit'] else ''
                copay = row['copay']
                coinsurance = row['coinsurance']

                # Format cost string
                if copay and str(copay).strip() and str(copay).strip() != '0':
                    cost_str = f"${copay} copay"
                elif coinsurance and str(coinsurance).strip():
                    cost_str = f"{coinsurance}% coinsurance"
                else:
                    cost_str = "Not covered" if network == 'Out of Network' else "See plan"

                if 'inpatient hospital' in benefit or 'inpatient' in benefit:
                    if network == 'In Network':
                        result[plan_id]['hospital_coinsurance_in_network'] = cost_str
                    elif network == 'Out of Network':
                        result[plan_id]['hospital_coinsurance_out_of_network'] = cost_str
                elif 'emergency room' in benefit or 'emergency' in benefit:
                    # ER is typically same cost regardless of network
                    if network == 'In Network':
                        result[plan_id]['er_cost'] = cost_str

        return result


class BenefitQueries:
    """SQL queries for benefit cost-sharing data"""

    @staticmethod
    def get_plan_benefits(db: DatabaseConnection, hios_plan_ids: List[str],
                          benefit_types: Optional[List[str]] = None) -> pd.DataFrame:
        """
        Get benefit cost-sharing information for specific plans

        Args:
            db: Database connection
            hios_plan_ids: List of HIOS Plan IDs
            benefit_types: Specific benefit types to retrieve (optional)

        Returns:
            DataFrame with benefit cost-sharing data
        """
        if not hios_plan_ids:
            return pd.DataFrame()

        placeholders = ', '.join(['%s'] * len(hios_plan_ids))
        query = f"""
        SELECT
            hios_plan_id,
            csr_variation_type,
            benefit,
            network_type,
            co_payment as copay,
            co_insurance as coinsurance
        FROM rbis_insurance_plan_benefit_cost_share_20251019202724
        WHERE hios_plan_id IN ({placeholders})
            AND network_type = 'In Network'
        """

        params = list(hios_plan_ids)

        if benefit_types:
            benefit_placeholders = ', '.join(['%s'] * len(benefit_types))
            query += f" AND benefit IN ({benefit_placeholders})"
            params.extend(benefit_types)

        query += " ORDER BY hios_plan_id, benefit"

        return db.execute_query(query, tuple(params))

    @staticmethod
    def get_key_benefits(db: DatabaseConnection, hios_plan_ids: List[str]) -> pd.DataFrame:
        """
        Get key benefits for plan comparison (PCP, Specialist, Drugs, ER, Hospital)

        Args:
            db: Database connection
            hios_plan_ids: List of HIOS Plan IDs

        Returns:
            DataFrame with key benefit information
        """
        key_benefits = [
            'Primary Care Visit to Treat an Injury or Illness',
            'Specialist Visit',
            'Generic Drugs',
            'Preferred Brand Drugs',
            'Emergency Room Services',
            'Inpatient Hospital Services'
        ]

        return BenefitQueries.get_plan_benefits(db, hios_plan_ids, key_benefits)


# Utility functions for common queries

def get_plan_deductible_and_moop_batch(db: DatabaseConnection, plan_ids: list) -> dict:
    """
    Get individual in-network deductible and MOOP for multiple plans.

    Args:
        db: Database connection
        plan_ids: List of HIOS Plan IDs

    Returns:
        dict: {plan_id: {'individual_deductible': amount, 'individual_moop': amount}}
    """
    import pandas as pd

    if not plan_ids:
        return {}

    placeholders = ', '.join(['%s'] * len(plan_ids))
    query = f"""
        SELECT plan_id, individual_ded_moop_amount, moop_ded_type
        FROM rbis_insurance_plan_variant_ddctbl_moop_20251019202724
        WHERE plan_id IN ({placeholders})
          AND variant_component = 'Exchange variant (no CSR)'
          AND network_type = 'In Network'
          AND (
              LOWER(moop_ded_type) LIKE '%%maximum out of pocket%%'
              OR LOWER(moop_ded_type) LIKE '%%deductible%%'
          )
    """
    result = db.execute_query(query, tuple(plan_ids))

    # Build lookup dict
    lookup = {}
    for plan_id in plan_ids:
        lookup[plan_id] = {'individual_deductible': None, 'individual_moop': None}

    if result.empty:
        return lookup

    for _, row in result.iterrows():
        plan_id = row['plan_id']
        ded_type = str(row.get('moop_ded_type', '')).lower()
        amount = row.get('individual_ded_moop_amount')

        # Parse amount
        parsed_amount = None
        if pd.notna(amount):
            try:
                if isinstance(amount, str):
                    amount = amount.replace('$', '').replace(',', '').strip()
                    if amount.lower() not in ('not applicable', 'n/a', ''):
                        parsed_amount = float(amount)
                else:
                    parsed_amount = float(amount)
            except (ValueError, TypeError):
                pass

        if parsed_amount is not None:
            if 'maximum out of pocket' in ded_type or 'moop' in ded_type:
                # Only update if not already set (prefer first match)
                if lookup[plan_id]['individual_moop'] is None:
                    lookup[plan_id]['individual_moop'] = parsed_amount
            elif 'deductible' in ded_type:
                if lookup[plan_id]['individual_deductible'] is None:
                    lookup[plan_id]['individual_deductible'] = parsed_amount

    return lookup


def get_plan_full_details(db: DatabaseConnection, hios_plan_id: str) -> dict:
    """
    Get comprehensive details for a single plan

    Args:
        db: Database connection
        plan_id: HIOS Plan ID

    Returns:
        Dictionary with plan details, deductibles, and key benefits
    """
    plan_data = PlanQueries.get_plans_by_filters(db)
    plan_data = plan_data[plan_data['hios_plan_id'] == hios_plan_id]

    if plan_data.empty:
        return {}

    plan_info = plan_data.iloc[0].to_dict()

    # Get deductibles/MOOP
    deductibles = PlanQueries.get_plan_deductibles_moop(db, [hios_plan_id])

    # Get key benefits
    benefits = BenefitQueries.get_key_benefits(db, [hios_plan_id])

    return {
        'plan_info': plan_info,
        'deductibles': deductibles.to_dict('records') if not deductibles.empty else [],
        'benefits': benefits.to_dict('records') if not benefits.empty else []
    }


class FinancialQueries:
    """SQL queries for Financial Summary calculations"""

    @staticmethod
    def get_plans_for_state(
        db: DatabaseConnection,
        state_code: str,
        metal_level: str = None
    ) -> pd.DataFrame:
        """
        Get all individual marketplace plans for a state.

        Args:
            db: Database connection
            state_code: Two-letter state code
            metal_level: Optional filter (Gold, Silver, Bronze, Platinum)

        Returns:
            DataFrame with plan_id, name, metal, type columns
        """
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
        """

        params = [state_code]

        if metal_level:
            query += " AND p.level_of_coverage = %s"
            params.append(metal_level)

        query += " ORDER BY p.level_of_coverage, p.plan_marketing_name"

        return pd.read_sql(query, db.engine, params=params)

    @staticmethod
    def get_rates_batch(
        db: DatabaseConnection,
        plan_ids: List[str]
    ) -> pd.DataFrame:
        """
        Batch fetch rates for multiple plans.

        Args:
            db: Database connection
            plan_ids: List of HIOS plan IDs

        Returns:
            DataFrame with plan_id, rating_area_id, age, rate columns
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

        return pd.read_sql(query, db.engine, params=(tuple(plan_ids),))

    @staticmethod
    def get_plan_summary(
        db: DatabaseConnection,
        plan_id: str
    ) -> dict:
        """
        Get plan summary including name, metal level, deductible, OOPM.

        Args:
            db: Database connection
            plan_id: HIOS plan ID

        Returns:
            Dict with plan_id, name, metal, type, deductible, oopm
        """
        query = """
        SELECT
            p.hios_plan_id as plan_id,
            p.plan_marketing_name as name,
            p.level_of_coverage as metal,
            p.plan_type as type,
            d.individual_medical_deductible_innetwork as deductible,
            d.individual_medical_moops_innetwork as oopm
        FROM rbis_insurance_plan_20251019202724 p
        LEFT JOIN rbis_insurance_plan_variant_ddctbl_moop_20251019202724 d
            ON p.hios_plan_id = d.hios_plan_id
        WHERE p.hios_plan_id = %s
          AND (d.csr_variation_type = 'Exchange variant (no CSR)'
               OR d.csr_variation_type IS NULL)
        LIMIT 1
        """

        df = pd.read_sql(query, db.engine, params=(plan_id,))

        if df.empty:
            return {}

        return df.iloc[0].to_dict()

    @staticmethod
    def get_plan_summaries_batch(
        db: DatabaseConnection,
        plan_ids: List[str]
    ) -> pd.DataFrame:
        """
        Get plan summaries for multiple plans.

        Returns:
            DataFrame with plan_id, name, metal, type, deductible, oopm
        """
        if not plan_ids:
            return pd.DataFrame()

        query = """
        SELECT DISTINCT ON (p.hios_plan_id)
            p.hios_plan_id as plan_id,
            p.plan_marketing_name as name,
            p.level_of_coverage as metal,
            p.plan_type as type,
            d.individual_medical_deductible_innetwork as deductible,
            d.individual_medical_moops_innetwork as oopm
        FROM rbis_insurance_plan_20251019202724 p
        LEFT JOIN rbis_insurance_plan_variant_ddctbl_moop_20251019202724 d
            ON p.hios_plan_id = d.hios_plan_id
            AND d.csr_variation_type = 'Exchange variant (no CSR)'
        WHERE p.hios_plan_id IN %s
        ORDER BY p.hios_plan_id
        """

        return pd.read_sql(query, db.engine, params=(tuple(plan_ids),))


if __name__ == "__main__":
    # Test queries
    from database import get_database_connection

    db = get_database_connection()

    print("Testing queries...")

    # Test 1: Get available states
    states = PlanQueries.get_available_states(db)
    print(f"\n✓ Available states: {len(states)}")
    print(states.head())

    # Test 2: Get plans for CA
    ca_plans = PlanQueries.get_plans_by_filters(db, state_code='CA', metal_level='Silver')
    print(f"\n✓ CA Silver plans: {len(ca_plans)}")
    print(ca_plans.head())

    print("\nAll queries working!")
