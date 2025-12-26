"""
Plan Suggestion Engine for ICHRA Calculator

This module provides plan recommendations using:
1. ACA-based scoring (cost efficiency, coverage, actuarial value, network flexibility)
2. LLM analysis (optional) for strategic cost savings narrative

Scoring Methodology:
- Cost Efficiency (40%): Percentile rank of cost per covered employee
- Geographic Coverage (30%): % of state employees with rates available
- Actuarial Value (20%): ACA metal level (Bronze=60, Silver=70, Gold=80, Platinum=90)
- Network Flexibility (10%): Plan type (PPO=100, POS=80, EPO=60, HMO=40)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
import pandas as pd
import logging
import os
import re
from dotenv import load_dotenv
import anthropic
import json
from queries import PlanQueries

# Load environment variables
load_dotenv()


# ==============================================================================
# LLM OUTPUT CLEANUP
# ==============================================================================

def clean_llm_output(text: str) -> str:
    """
    Post-process LLM output to remove formatting artifacts and weird characters.

    Handles:
    - LaTeX-style math notation that renders oddly
    - Leaked variable names like TotalAnnualEmployeeCost(MarketplacePlans)
    - Unicode math symbols that display inconsistently
    - Excessive markdown formatting
    """
    if not text:
        return text

    # Remove LaTeX-style inline math: $...$
    text = re.sub(r'\$([^$]+)\$', r'\1', text)

    # Remove LaTeX display math: $$...$$
    text = re.sub(r'\$\$([^$]+)\$\$', r'\1', text)

    # Remove backslash commands from LaTeX (\text{}, \mathbf{}, etc.)
    text = re.sub(r'\\text\{([^}]*)\}', r'\1', text)
    text = re.sub(r'\\mathbf\{([^}]*)\}', r'\1', text)
    text = re.sub(r'\\textbf\{([^}]*)\}', r'\1', text)
    text = re.sub(r'\\textit\{([^}]*)\}', r'\1', text)
    text = re.sub(r'\\mathrm\{([^}]*)\}', r'\1', text)
    text = re.sub(r'\\times', 'x', text)
    text = re.sub(r'\\approx', '≈', text)
    text = re.sub(r'\\sim', '~', text)

    # Remove leaked camelCase variable names like TotalAnnualEmployeeCost(MarketplacePlans)
    text = re.sub(r'[A-Z][a-zA-Z]+\([A-Za-z]+\)', '', text)

    # Clean up camelCase variable names in text (e.g., TotalAnnualCost -> leave as is, but remove if it looks like code)
    text = re.sub(r'\b([A-Z][a-z]+){3,}\b(?!\s*[=:])', '', text)  # Remove 3+ word camelCase unless followed by = or :

    # Replace common unicode math symbols with ASCII equivalents
    replacements = {
        '×': 'x',
        '÷': '/',
        '−': '-',  # Unicode minus
        '–': '-',  # En dash
        '—': '-',  # Em dash
        '≈': '~',
        '≠': '!=',
        '≤': '<=',
        '≥': '>=',
        '′': "'",  # Prime
        '″': '"',  # Double prime
        '∼': '~',
        '⁄': '/',  # Fraction slash
    }
    for unicode_char, ascii_char in replacements.items():
        text = text.replace(unicode_char, ascii_char)

    # Remove orphaned backslashes
    text = re.sub(r'\\(?![n\\])', '', text)

    # Clean up multiple spaces/newlines
    text = re.sub(r' {3,}', '  ', text)  # Max 2 spaces
    text = re.sub(r'\n{4,}', '\n\n\n', text)  # Max 3 newlines

    # Remove empty bold/italic markers
    text = re.sub(r'\*\*\s*\*\*', '', text)
    text = re.sub(r'\*\s*\*', '', text)

    return text.strip()


# ==============================================================================
# SYSTEM PROMPT FOR ICHRA ANALYSIS
# ==============================================================================

ICHRA_SYSTEM_PROMPT = """You are an expert employee benefits consultant specializing in ICHRA (Individual Coverage Health Reimbursement Arrangement) strategies.

Your role is to help benefits consultants analyze health insurance options for their employer clients who are considering transitioning from traditional group health plans to ICHRA.

Key expertise areas:
- ICHRA regulations and compliance (IRS, DOL, HHS requirements)
- Individual marketplace plan analysis (ACA metal levels, plan types, rating areas)
- Cost comparison methodologies (employer vs employee costs, contribution strategies)
- Non-traditional benefit options (Direct Primary Care, health sharing, virtual care platforms)
- Multi-state employer considerations (rating area variations, plan availability)
- Employee demographics impact on plan selection (age banding, family status)

**CRITICAL: ICHRA Affordability Requirements**
Under IRS regulations, an ICHRA is considered "affordable" if the employer's contribution allows employees to purchase the LOWEST-COST SILVER PLAN (LCSP) in their rating area without exceeding 9.96% of household income (2026 threshold).

**LCSP Data is Pre-Calculated:** The `lcsp_benchmarks` array in the context contains the LCSP for each unique state/rating area/age band combination. Use this pre-calculated data for affordability analysis:
- Use the provided LCSP premiums as the benchmark - do NOT attempt to identify LCSP from marketplace plan lists
- LCSP premiums are queried directly from the CMS database for accuracy
- Each entry contains: state_code, rating_area_id, age_band, lcsp_plan_id, lcsp_plan_name, lcsp_premium
- Calculate whether employer contribution covers at least the LCSP premium
- Note if employer contribution exceeds, meets, or falls short of the LCSP threshold
- Recommend contribution strategies that meet the affordability safe harbor

Communication style:
- Professional and consultative, suitable for presentation to C-suite executives
- Data-driven with specific dollar amounts and percentages
- Focus on business value and ROI
- Transparent about assumptions and methodology
- Balanced presentation of benefits and considerations

Output formatting:
- Use plain text without excessive markdown formatting
- Format currency as $X,XXX.XX (with commas, no cents for round numbers)
- Format percentages as whole numbers (e.g., 25% not 0.25)
- Structure responses with clear headers and bullet points
- Keep analysis concise and actionable"""


# ==============================================================================
# DATA CLASSES
# ==============================================================================

@dataclass
class EmployerPreferences:
    """Captures employer preferences for plan filtering"""

    # Contribution settings
    contribution_pct: float = 75.0  # Default employer contribution %

    # Plan filters
    metal_levels: List[str] = field(default_factory=lambda: ["Bronze", "Silver", "Gold", "Platinum"])
    plan_types: List[str] = field(default_factory=lambda: ["HMO", "PPO", "EPO", "POS"])

    # Selection constraints
    max_plans_per_state: int = 1  # Number of plans to recommend per state


@dataclass
class ScoredPlan:
    """Represents a plan with its calculated scores"""

    plan_id: str
    plan_name: str
    state_code: str
    metal_level: str
    plan_type: str

    # Cost metrics
    total_annual_cost: float
    avg_monthly_cost_per_employee: float

    # Coverage metrics
    employees_covered: int
    total_employees: int
    coverage_percentage: float

    # Scores (0-100)
    cost_efficiency_score: float = 0.0
    coverage_score: float = 0.0
    actuarial_value_score: float = 0.0
    network_flexibility_score: float = 0.0
    total_score: float = 0.0

    # Score breakdown for display
    score_breakdown: Dict[str, float] = field(default_factory=dict)

    # Details
    strengths: List[str] = field(default_factory=list)
    considerations: List[str] = field(default_factory=list)


# ==============================================================================
# PLAN SCORER - ACA-Based Methodology
# ==============================================================================

class PlanScorer:
    """
    ACA-based scoring engine for plan evaluation.

    All scores are derived from actual data with no placeholders:
    - Cost Efficiency: Percentile rank based on actual premium costs
    - Coverage: Direct percentage of employees with rates
    - Actuarial Value: ACA-defined metal level values
    - Network Flexibility: Objective plan type ranking
    """

    # Fixed weights (no user customization)
    WEIGHT_COST_EFFICIENCY = 0.40
    WEIGHT_COVERAGE = 0.30
    WEIGHT_ACTUARIAL_VALUE = 0.20
    WEIGHT_NETWORK_FLEXIBILITY = 0.10

    # ACA Actuarial Values by metal level
    ACTUARIAL_VALUES = {
        'Bronze': 60,
        'Silver': 70,
        'Gold': 80,
        'Platinum': 90
    }

    # Network flexibility scores by plan type
    NETWORK_FLEXIBILITY = {
        'PPO': 100,  # Most flexible - out-of-network coverage
        'POS': 80,   # Moderate - out-of-network with referral
        'EPO': 60,   # Limited - in-network only, no referral needed
        'HMO': 40    # Most restrictive - in-network only, referral required
    }

    @staticmethod
    def score_cost_efficiency(cost_per_employee: float, all_costs: List[float]) -> Tuple[float, List[str], List[str]]:
        """
        Score cost efficiency using percentile rank (0-100).

        Lowest cost = 100, highest cost = 0.
        Uses relative ranking within the candidate plan set.

        Args:
            cost_per_employee: Annual cost per employee for this plan
            all_costs: List of all plan costs for percentile calculation

        Returns:
            Tuple of (score, strengths, considerations)
        """
        strengths = []
        considerations = []

        if not all_costs or len(all_costs) == 0:
            return 50.0, strengths, considerations

        # Handle single plan case
        if len(all_costs) == 1:
            strengths.append(f"${cost_per_employee/12:.0f}/mo avg per employee")
            return 50.0, strengths, considerations

        # Calculate percentile rank (lower cost = higher score)
        costs_below = sum(1 for c in all_costs if c > cost_per_employee)
        percentile = (costs_below / (len(all_costs) - 1)) * 100
        score = percentile

        # Determine position for messaging
        sorted_costs = sorted(all_costs)
        rank = sorted_costs.index(cost_per_employee) + 1

        if rank <= len(all_costs) * 0.25:
            strengths.append(f"Top 25% most affordable (${cost_per_employee/12:.0f}/mo avg)")
        elif rank <= len(all_costs) * 0.5:
            strengths.append(f"Above average affordability (${cost_per_employee/12:.0f}/mo avg)")
        elif rank > len(all_costs) * 0.75:
            considerations.append(f"Higher cost option (${cost_per_employee/12:.0f}/mo avg)")

        return score, strengths, considerations

    @staticmethod
    def score_coverage(employees_covered: int, total_employees: int) -> Tuple[float, List[str], List[str]]:
        """
        Score geographic coverage as direct percentage (0-100).

        Args:
            employees_covered: Number of employees with premium rates available
            total_employees: Total employees in state

        Returns:
            Tuple of (score, strengths, considerations)
        """
        strengths = []
        considerations = []

        if total_employees == 0:
            return 0.0, strengths, considerations

        coverage_pct = (employees_covered / total_employees) * 100
        score = coverage_pct

        if coverage_pct >= 100:
            strengths.append(f"Full coverage ({employees_covered}/{total_employees} employees)")
        elif coverage_pct >= 90:
            strengths.append(f"Excellent coverage ({coverage_pct:.0f}%)")
        elif coverage_pct >= 75:
            considerations.append(f"Partial coverage ({coverage_pct:.0f}%, {total_employees - employees_covered} employees uncovered)")
        else:
            considerations.append(f"Limited coverage ({coverage_pct:.0f}%, {total_employees - employees_covered} employees uncovered)")

        return score, strengths, considerations

    @staticmethod
    def score_actuarial_value(metal_level: str) -> Tuple[float, List[str], List[str]]:
        """
        Score actuarial value using ACA-defined metal levels (60-90).

        ACA Actuarial Values:
        - Bronze: 60% (plan pays 60% of average costs)
        - Silver: 70%
        - Gold: 80%
        - Platinum: 90%

        Args:
            metal_level: Plan metal level

        Returns:
            Tuple of (score, strengths, considerations)
        """
        strengths = []
        considerations = []

        score = PlanScorer.ACTUARIAL_VALUES.get(metal_level, 50)

        if metal_level == 'Platinum':
            strengths.append("Platinum - lowest out-of-pocket costs (90% AV)")
        elif metal_level == 'Gold':
            strengths.append("Gold - low out-of-pocket costs (80% AV)")
        elif metal_level == 'Silver':
            pass  # Neutral - no strength or consideration
        elif metal_level == 'Bronze':
            considerations.append("Bronze - higher out-of-pocket costs (60% AV)")

        return score, strengths, considerations

    @staticmethod
    def score_network_flexibility(plan_type: str) -> Tuple[float, List[str], List[str]]:
        """
        Score network flexibility based on plan type (40-100).

        Scoring based on out-of-network access and referral requirements:
        - PPO (100): Out-of-network coverage, no referrals
        - POS (80): Out-of-network coverage, referrals for specialists
        - EPO (60): In-network only, no referrals needed
        - HMO (40): In-network only, referrals required

        Args:
            plan_type: Plan type (HMO, PPO, EPO, POS)

        Returns:
            Tuple of (score, strengths, considerations)
        """
        strengths = []
        considerations = []

        score = PlanScorer.NETWORK_FLEXIBILITY.get(plan_type, 50)

        if plan_type == 'PPO':
            strengths.append("PPO - maximum provider flexibility")
        elif plan_type == 'POS':
            strengths.append("POS - out-of-network options available")
        elif plan_type == 'EPO':
            considerations.append("EPO - in-network providers only")
        elif plan_type == 'HMO':
            considerations.append("HMO - in-network only, requires referrals")

        return score, strengths, considerations

    @staticmethod
    def calculate_total_score(
        cost_efficiency_score: float,
        coverage_score: float,
        actuarial_value_score: float,
        network_flexibility_score: float
    ) -> float:
        """
        Calculate weighted total score.

        Formula:
        total = (cost × 0.40) + (coverage × 0.30) + (actuarial × 0.20) + (network × 0.10)
        """
        return (
            cost_efficiency_score * PlanScorer.WEIGHT_COST_EFFICIENCY +
            coverage_score * PlanScorer.WEIGHT_COVERAGE +
            actuarial_value_score * PlanScorer.WEIGHT_ACTUARIAL_VALUE +
            network_flexibility_score * PlanScorer.WEIGHT_NETWORK_FLEXIBILITY
        )


# ==============================================================================
# MAIN SUGGESTION ENGINE
# ==============================================================================

class AISuggestionEngine:
    """Orchestrates the plan suggestion workflow"""

    @staticmethod
    def _map_age_to_band(age: int) -> str:
        """
        Map census age (integer) to database age band (string).

        Database format:
        - "0-14" for ages 0-14
        - "15", "16", ... "63" for ages 15-63
        - "64 and over" for ages 64+

        Args:
            age: Integer age from census

        Returns:
            String age band matching database format
        """
        if age <= 14:
            return "0-14"
        elif age >= 64:
            return "64 and over"
        else:
            return str(age)

    def _query_lcsp_for_census(self, census_df: pd.DataFrame) -> List[Dict]:
        """
        Query LCSP (Lowest Cost Silver Plan) for each unique employee location.

        The LCSP is used as the benchmark for ICHRA affordability safe harbor
        compliance (employee contribution must not exceed 9.96% of household income
        for the LCSP premium).

        Args:
            census_df: Employee census DataFrame with columns: state, rating_area_id, age

        Returns:
            List of dicts with LCSP data for each unique (state, rating_area, age_band):
            [
                {
                    'state_code': 'NY',
                    'rating_area_id': 1,
                    'age_band': '35',
                    'lcsp_plan_id': '12345NY0010001',
                    'lcsp_plan_name': 'Oscar Silver Simple',
                    'lcsp_premium': 425.50
                },
                ...
            ]
        """
        from constants import FAMILY_TIER_STATES

        lcsp_benchmarks = []

        # Check required columns exist
        required_cols = ['state', 'rating_area_id', 'age']
        if not all(col in census_df.columns for col in required_cols):
            self.logger.warning(f"Census missing required columns for LCSP lookup: {required_cols}")
            return lcsp_benchmarks

        # Build unique location combinations
        employee_locations = []
        seen = set()

        for _, row in census_df.iterrows():
            state = row['state']
            rating_area = row['rating_area_id']
            age = row['age']

            # Handle family-tier states (NY, VT)
            if state in FAMILY_TIER_STATES:
                age_band = "Family-Tier Rates"
            else:
                age_band = self._map_age_to_band(int(age))

            key = (state, rating_area, age_band)
            if key not in seen:
                seen.add(key)
                employee_locations.append({
                    'state_code': state,
                    'rating_area_id': int(rating_area),
                    'age_band': age_band
                })

        if not employee_locations:
            return lcsp_benchmarks

        # Query LCSP for all unique combinations
        try:
            lcsp_df = PlanQueries.get_lcsp_for_employees_batch(self.db, employee_locations)

            if not lcsp_df.empty:
                for _, row in lcsp_df.iterrows():
                    lcsp_benchmarks.append({
                        'state_code': row['state_code'],
                        'rating_area_id': int(row['rating_area_id']),
                        'age_band': row['age_band'],
                        'lcsp_plan_id': row['hios_plan_id'],
                        'lcsp_plan_name': row['plan_name'],
                        'lcsp_premium': float(row['premium'])
                    })

            self.logger.info(f"Retrieved LCSP data for {len(lcsp_benchmarks)} unique location/age combinations")

        except Exception as e:
            self.logger.error(f"Error querying LCSP data: {e}")

        return lcsp_benchmarks

    def __init__(self, db_connection, use_llm: bool = False):
        """
        Initialize with database connection.

        Args:
            db_connection: Database connection object
            use_llm: Whether to initialize LLM analyzer (requires API key)
        """
        self.db = db_connection
        self.scorer = PlanScorer()
        self.llm_analyzer = None
        self.logger = logging.getLogger(__name__)

        # Initialize LLM analyzer if requested
        if use_llm:
            try:
                self.llm_analyzer = LLMPlanAnalyzer()
                self.logger.info("LLM analyzer initialized successfully")
            except Exception as e:
                self.logger.warning(f"Could not initialize LLM analyzer: {e}")
                self.logger.info("Continuing without LLM analysis capability")

    def generate_suggestions(
        self,
        census_df: pd.DataFrame,
        preferences: EmployerPreferences,
        use_llm: bool = False
    ) -> Tuple[List[ScoredPlan], Optional[str]]:
        """
        Generate plan suggestions using ACA-based scoring.

        Args:
            census_df: Employee census DataFrame
            preferences: Employer preferences for filtering
            use_llm: Whether to use LLM for analysis (optional)

        Returns:
            Tuple of (scored_plans, llm_analysis)
            - scored_plans: List of scored and ranked plan suggestions
            - llm_analysis: Optional markdown-formatted LLM analysis (None if not used)
        """
        self.logger.info("=" * 80)
        self.logger.info("PLAN SUGGESTION ENGINE - STARTING")
        self.logger.info("=" * 80)
        self.logger.info(f"Census: {len(census_df)} employees across {census_df['state'].nunique()} states")
        self.logger.info(f"Filters: Metal={preferences.metal_levels}, Type={preferences.plan_types}")
        self.logger.info(f"Contribution: {preferences.contribution_pct}%")
        self.logger.info(f"Scoring: Cost={PlanScorer.WEIGHT_COST_EFFICIENCY:.0%}, Coverage={PlanScorer.WEIGHT_COVERAGE:.0%}, AV={PlanScorer.WEIGHT_ACTUARIAL_VALUE:.0%}, Network={PlanScorer.WEIGHT_NETWORK_FLEXIBILITY:.0%}")
        self.logger.info("")

        # Stage 1: Filter viable plans
        self.logger.info("STAGE 1: Filtering viable plan candidates...")
        viable_plans = self._filter_viable_plans(census_df, preferences)
        self.logger.info(f"Stage 1 Complete: {len(viable_plans)} viable plans found")
        self.logger.info("")

        if not viable_plans:
            self.logger.warning("No viable plans found matching criteria")
            return [], None

        # Stage 2: Score all viable plans
        self.logger.info(f"STAGE 2: Scoring {len(viable_plans)} plans...")
        scored_plans = self._score_plans(viable_plans, census_df, preferences)
        self.logger.info(f"Stage 2 Complete: Successfully scored {len(scored_plans)} plans")
        self.logger.info("")

        # Stage 3: Plan Selection
        llm_analysis = None

        if use_llm and self.llm_analyzer:
            # LLM-DRIVEN SELECTION: AI selects from top candidates
            self.logger.info("STAGE 3: AI-Driven Plan Selection...")
            self.logger.info("  Preparing candidate plans for AI analysis...")

            # Get top N candidates per state (more options for AI to consider)
            candidates_per_state = 5  # Give AI 5 options per state to choose from
            candidate_plans = self._get_top_candidates_per_state(scored_plans, candidates_per_state)
            self.logger.info(f"  Prepared {len(candidate_plans)} candidate plans for AI selection")

            # Let LLM select the best plan(s)
            selected_ids, llm_analysis = self.llm_analyzer.select_plans_from_candidates(
                candidate_plans=candidate_plans,
                census_df=census_df,
                preferences=preferences,
                max_per_state=preferences.max_plans_per_state
            )

            # Filter scored_plans to only include AI-selected plans
            top_plans = [p for p in candidate_plans if p.plan_id in selected_ids]

            # Ensure we have plans in the right order (by state)
            top_plans = sorted(top_plans, key=lambda p: p.state_code)

            self.logger.info(f"Stage 3 Complete: AI selected {len(top_plans)} plans")
        else:
            # ALGORITHMIC SELECTION: Use scoring-based selection
            self.logger.info("STAGE 3: Algorithmic Plan Selection (no AI)...")
            top_plans = self._select_top_plans_per_state(scored_plans, preferences)
            self.logger.info(f"Stage 3 Complete: Selected {len(top_plans)} plans (one per state)")

        self.logger.info("")
        self.logger.info("=" * 80)
        self.logger.info(f"SUGGESTION COMPLETE: Returning {len(top_plans)} recommended plans")
        self.logger.info("=" * 80)

        return top_plans, llm_analysis

    def _filter_viable_plans(
        self,
        census_df: pd.DataFrame,
        preferences: EmployerPreferences
    ) -> List[Dict]:
        """
        Filter plans that meet basic criteria.

        Returns:
            List of plan dictionaries from database that match filtering criteria
        """
        try:
            # Extract unique states from census
            if 'state' not in census_df.columns:
                self.logger.error("Census data missing 'state' column")
                return []

            state_codes = census_df['state'].unique().tolist()
            self.logger.info(f"  Filtering plans for states: {state_codes}")

            # Query database for plans in the states
            plans_df = PlanQueries.get_plans_by_filters(
                db=self.db,
                state_codes=state_codes
            )

            self.logger.info(f"  Database returned {len(plans_df)} plans")

            if plans_df.empty:
                return []

            # Get rating area column
            rating_area_col = None
            if 'rating_area_id' in census_df.columns:
                rating_area_col = 'rating_area_id'
            elif 'rating_area' in census_df.columns:
                rating_area_col = 'rating_area'
            else:
                self.logger.error("Census data missing 'rating_area_id' or 'rating_area' column")
                return []

            # Extract unique (state, rating_area) combinations from census
            census_locations = census_df[['state', rating_area_col]].drop_duplicates()

            # Extract rating area numbers
            def extract_rating_area_num(x):
                if pd.isna(x):
                    return None
                x_str = str(x)
                if 'Rating Area' in x_str:
                    return int(x_str.replace('Rating Area', '').strip())
                return int(x_str)

            census_locations['rating_area_num'] = census_locations[rating_area_col].apply(extract_rating_area_num)
            census_locations = census_locations.dropna(subset=['rating_area_num'])

            # Group rating areas by state
            state_rating_areas = (
                census_locations.groupby('state')['rating_area_num']
                .apply(lambda x: sorted([int(ra) for ra in x]))
                .to_dict()
            )

            self.logger.info(f"  Employee rating areas by state: {state_rating_areas}")

            # Get plans with rating area coverage
            plan_ids_to_check = plans_df['hios_plan_id'].unique().tolist()

            coverage_results = PlanQueries.get_plans_with_rating_area_coverage(
                self.db,
                plan_ids_to_check,
                state_rating_areas
            )

            if coverage_results.empty:
                self.logger.warning("  No plans found with coverage for employee rating areas")
                return []

            # Filter to valid plans
            valid_plan_ids = coverage_results['hios_plan_id'].unique().tolist()
            plans_df = plans_df[plans_df['hios_plan_id'].isin(valid_plan_ids)]

            self.logger.info(f"  After rating area filtering: {len(plans_df)} plans")

            # Convert to list of dicts
            viable_plans = plans_df.to_dict('records') if not plans_df.empty else []

            # Filter by metal level
            if preferences.metal_levels:
                viable_plans = [
                    plan for plan in viable_plans
                    if plan.get('metal_level') in preferences.metal_levels
                ]
                self.logger.info(f"  After metal level filtering: {len(viable_plans)} plans")

            # Filter by plan type
            if preferences.plan_types:
                viable_plans = [
                    plan for plan in viable_plans
                    if plan.get('plan_type') in preferences.plan_types
                ]
                self.logger.info(f"  After plan type filtering: {len(viable_plans)} plans")

            return viable_plans

        except Exception as e:
            self.logger.error(f"Error filtering viable plans: {e}")
            return []

    def _score_plans(
        self,
        plans: List[Dict],
        census_df: pd.DataFrame,
        preferences: EmployerPreferences
    ) -> List[ScoredPlan]:
        """
        Score each plan using ACA-based methodology.

        Calculates actual costs and applies all 4 scoring dimensions.
        """
        scored_plans = []

        # Extract census states
        census_states = census_df['state'].unique().tolist() if 'state' in census_df.columns else []

        # Filter plans to only those matching census states
        state_matched_plans = [
            plan for plan in plans
            if len(plan.get('hios_plan_id', '')) >= 7 and plan['hios_plan_id'][5:7] in census_states
        ]

        self.logger.info(f"  State filtering: {len(plans)} plans -> {len(state_matched_plans)} state-matched plans")

        # Load premium rates
        plan_ids = [p['hios_plan_id'] for p in state_matched_plans]

        # Convert census ages to database age bands
        ages_raw = census_df['age'].unique().tolist() if 'age' in census_df.columns else []
        ages = list(set(self._map_age_to_band(int(age)) for age in ages_raw))

        self.logger.info(f"  Loading premium rates: {len(plan_ids)} plans x {len(ages)} age bands...")
        self.logger.info(f"  Age bands: {sorted(ages, key=lambda x: (0 if x == '0-14' else (100 if 'over' in x else int(x))))}")
        premium_rates = PlanQueries.get_plan_rates_by_age(
            db=self.db,
            plan_ids=plan_ids,
            ages=ages
        )
        self.logger.info(f"  Loaded {len(premium_rates):,} premium rate records")

        # First pass: calculate costs for all plans (needed for percentile ranking)
        plan_costs = {}
        for plan in state_matched_plans:
            plan_id = plan.get('hios_plan_id')
            if not plan_id:
                continue

            cost_data = self._calculate_plan_cost(
                plan_id=plan_id,
                census_df=census_df,
                premium_rates=premium_rates,
                contribution_pct=preferences.contribution_pct
            )

            if cost_data['total_annual_cost'] > 0:
                plan_costs[plan_id] = cost_data

        self.logger.info(f"  Calculated costs for {len(plan_costs)} plans")

        # Get list of all costs for percentile calculation
        all_costs = [data['cost_per_employee'] for data in plan_costs.values()]

        # Second pass: score all plans
        for plan in state_matched_plans:
            plan_id = plan.get('hios_plan_id')
            if not plan_id or plan_id not in plan_costs:
                continue

            cost_data = plan_costs[plan_id]

            # Score 1: Cost Efficiency (percentile rank)
            cost_score, cost_strengths, cost_considerations = PlanScorer.score_cost_efficiency(
                cost_per_employee=cost_data['cost_per_employee'],
                all_costs=all_costs
            )

            # Score 2: Geographic Coverage (direct percentage)
            coverage_score, coverage_strengths, coverage_considerations = PlanScorer.score_coverage(
                employees_covered=cost_data['employees_covered'],
                total_employees=cost_data['total_state_employees']
            )

            # Score 3: Actuarial Value (ACA metal level)
            av_score, av_strengths, av_considerations = PlanScorer.score_actuarial_value(
                metal_level=plan.get('metal_level', '')
            )

            # Score 4: Network Flexibility (plan type)
            network_score, network_strengths, network_considerations = PlanScorer.score_network_flexibility(
                plan_type=plan.get('plan_type', '')
            )

            # Calculate total score
            total_score = PlanScorer.calculate_total_score(
                cost_efficiency_score=cost_score,
                coverage_score=coverage_score,
                actuarial_value_score=av_score,
                network_flexibility_score=network_score
            )

            # Combine strengths and considerations
            all_strengths = cost_strengths + coverage_strengths + av_strengths + network_strengths
            all_considerations = cost_considerations + coverage_considerations + av_considerations + network_considerations

            # Create ScoredPlan
            scored_plan = ScoredPlan(
                plan_id=plan_id,
                plan_name=plan.get('plan_marketing_name', 'Unknown Plan'),
                state_code=plan_id[5:7] if len(plan_id) >= 7 else '',
                metal_level=plan.get('metal_level', ''),
                plan_type=plan.get('plan_type', ''),
                total_annual_cost=cost_data['total_annual_cost'],
                avg_monthly_cost_per_employee=cost_data['cost_per_employee'] / 12,
                employees_covered=cost_data['employees_covered'],
                total_employees=cost_data['total_state_employees'],
                coverage_percentage=(cost_data['employees_covered'] / cost_data['total_state_employees'] * 100) if cost_data['total_state_employees'] > 0 else 0,
                cost_efficiency_score=cost_score,
                coverage_score=coverage_score,
                actuarial_value_score=av_score,
                network_flexibility_score=network_score,
                total_score=total_score,
                score_breakdown={
                    'Cost Efficiency': cost_score,
                    'Geographic Coverage': coverage_score,
                    'Actuarial Value': av_score,
                    'Network Flexibility': network_score
                },
                strengths=all_strengths,
                considerations=all_considerations
            )

            scored_plans.append(scored_plan)

        self.logger.info(f"  Scoring complete: {len(scored_plans)} plans scored")
        if scored_plans:
            avg_score = sum(p.total_score for p in scored_plans) / len(scored_plans)
            self.logger.info(f"  Score range: {min(p.total_score for p in scored_plans):.1f} - {max(p.total_score for p in scored_plans):.1f} (avg: {avg_score:.1f})")

        return scored_plans

    def _select_top_plans_per_state(
        self,
        scored_plans: List[ScoredPlan],
        preferences: EmployerPreferences
    ) -> List[ScoredPlan]:
        """
        Select top N plans per state based on total score.
        """
        # Group plans by state
        plans_by_state = {}
        for plan in scored_plans:
            state = plan.state_code
            if state not in plans_by_state:
                plans_by_state[state] = []
            plans_by_state[state].append(plan)

        # Select top plans for each state
        top_plans = []
        for state in sorted(plans_by_state.keys()):
            state_plans = sorted(plans_by_state[state], key=lambda x: x.total_score, reverse=True)
            selected = state_plans[:preferences.max_plans_per_state]

            for plan in selected:
                # Add selection rationale
                rationale_parts = []

                if plan.coverage_percentage >= 90:
                    rationale_parts.append(f"Excellent coverage ({plan.coverage_percentage:.0f}%)")
                elif plan.coverage_percentage >= 70:
                    rationale_parts.append(f"Good coverage ({plan.coverage_percentage:.0f}%)")
                else:
                    rationale_parts.append(f"Limited coverage ({plan.coverage_percentage:.0f}%)")

                rationale_parts.append(f"${plan.avg_monthly_cost_per_employee:.0f}/mo avg")
                rationale_parts.append(f"{plan.metal_level} {plan.plan_type}")

                plan.considerations.insert(0, f"**Selected for {state}:** " + ", ".join(rationale_parts))

                self.logger.info(f"  {state}: {plan.plan_name} (Score: {plan.total_score:.1f}/100)")

            top_plans.extend(selected)

        return top_plans

    def _get_top_candidates_per_state(
        self,
        scored_plans: List[ScoredPlan],
        n_candidates: int = 5
    ) -> List[ScoredPlan]:
        """
        Get top N candidate plans per state for LLM selection.

        Unlike _select_top_plans_per_state, this returns multiple options
        per state to give the LLM more choices to analyze.
        """
        # Group plans by state
        plans_by_state = {}
        for plan in scored_plans:
            state = plan.state_code
            if state not in plans_by_state:
                plans_by_state[state] = []
            plans_by_state[state].append(plan)

        # Get top N candidates for each state
        candidates = []
        for state in sorted(plans_by_state.keys()):
            state_plans = sorted(plans_by_state[state], key=lambda x: x.total_score, reverse=True)
            # Take top N candidates (or fewer if not enough plans)
            top_n = state_plans[:n_candidates]
            candidates.extend(top_n)
            self.logger.info(f"  {state}: {len(top_n)} candidate plans (scores: {[f'{p.total_score:.0f}' for p in top_n]})")

        return candidates

    def _calculate_plan_cost(
        self,
        plan_id: str,
        census_df: pd.DataFrame,
        premium_rates: pd.DataFrame,
        contribution_pct: float
    ) -> Dict:
        """
        Calculate total annual employer cost for a plan.

        Returns dict with:
        - total_annual_cost
        - cost_per_employee
        - employees_covered
        - total_state_employees
        """
        result = {
            'total_annual_cost': 0.0,
            'cost_per_employee': 0.0,
            'employees_covered': 0,
            'total_state_employees': 0
        }

        # Extract plan state from plan ID
        plan_state = plan_id[5:7] if len(plan_id) >= 7 else None
        if not plan_state:
            return result

        # Filter census to only employees in the plan's state
        state_census = census_df[census_df['state'] == plan_state].copy()
        if state_census.empty:
            return result

        # Filter to valid ages (18-64)
        state_census = state_census[(state_census['age'] >= 18) & (state_census['age'] <= 64)]
        if state_census.empty:
            return result

        result['total_state_employees'] = len(state_census)

        # Get rating area column
        rating_area_col = None
        if 'rating_area_id' in state_census.columns:
            rating_area_col = 'rating_area_id'
        elif 'rating_area' in state_census.columns:
            rating_area_col = 'rating_area'

        if not rating_area_col:
            return result

        # Extract rating area numbers
        state_census['rating_area_num'] = state_census[rating_area_col].apply(
            lambda x: int(str(x).replace('Rating Area', '').strip()) if pd.notna(x) and 'Rating Area' in str(x) else (int(x) if pd.notna(x) else None)
        )

        state_census = state_census.dropna(subset=['rating_area_num'])
        if state_census.empty:
            return result

        # Check required columns in premium_rates
        required_cols = ['hios_plan_id', 'state_code', 'rating_area_id', 'age', 'premium']
        if not all(col in premium_rates.columns for col in required_cols):
            return result

        # Filter premium_rates to this plan and state
        plan_rates = premium_rates[
            (premium_rates['hios_plan_id'] == plan_id) &
            (premium_rates['state_code'] == plan_state)
        ].copy()

        if plan_rates.empty:
            return result

        # Prepare for merge - map census ages to database age bands
        state_census['age_str'] = state_census['age'].apply(self._map_age_to_band)
        plan_rates['age_str'] = plan_rates['age'].astype(str)

        # Merge census with rates
        merged = state_census.merge(
            plan_rates,
            left_on=['age_str', 'rating_area_num'],
            right_on=['age_str', 'rating_area_id'],
            how='left'
        )

        # Filter to employees with valid rates
        merged = merged[merged['premium'].notna() & (merged['premium'] > 0)]

        if merged.empty:
            return result

        # Calculate costs
        merged['premium'] = merged['premium'].astype(float)
        merged['employer_monthly'] = merged['premium'] * (contribution_pct / 100)
        merged['employer_annual'] = merged['employer_monthly'] * 12

        result['total_annual_cost'] = float(merged['employer_annual'].sum())
        result['employees_covered'] = len(merged)
        result['cost_per_employee'] = result['total_annual_cost'] / result['employees_covered'] if result['employees_covered'] > 0 else 0

        return result


# ==============================================================================
# LLM ANALYSIS
# ==============================================================================

class LLMPlanAnalyzer:
    """Uses Claude API to provide intelligent analysis of plan recommendations"""

    def __init__(self):
        """Initialize Claude API client"""
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key or api_key == 'your_api_key_here':
            raise ValueError(
                "ANTHROPIC_API_KEY not set in .env file. "
                "Please add your API key from https://console.anthropic.com/settings/keys"
            )

        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = os.getenv('ANTHROPIC_MODEL', 'claude-sonnet-4-5-20250929')
        self.max_tokens = int(os.getenv('ANTHROPIC_MAX_TOKENS', '16000'))
        self.logger = logging.getLogger(__name__)

    def analyze_recommendations(
        self,
        scored_plans: List[ScoredPlan],
        census_df: pd.DataFrame,
        preferences: EmployerPreferences,
        top_n: int = 3
    ) -> str:
        """
        Generate LLM-powered analysis of top plan recommendations.

        Args:
            scored_plans: List of scored plans (already sorted by score)
            census_df: Employee census data
            preferences: Employer preferences
            top_n: Number of top plans to analyze

        Returns:
            Markdown-formatted analysis text
        """
        try:
            # Prepare context for LLM
            context = self._prepare_context(scored_plans[:top_n], census_df, preferences)

            # Create prompt
            prompt = self._create_analysis_prompt(context)

            # Call Claude API with system prompt
            self.logger.info(f"Calling Claude API for plan analysis (model: {self.model})")
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=ICHRA_SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            # Extract analysis text and clean up formatting artifacts
            analysis = response.content[0].text
            analysis = clean_llm_output(analysis)
            self.logger.info("Successfully generated LLM analysis")

            return analysis

        except Exception as e:
            self.logger.error(f"Error generating LLM analysis: {e}")
            return f"**Error generating AI analysis:** {str(e)}"

    def _prepare_context(
        self,
        top_plans: List[ScoredPlan],
        census_df: pd.DataFrame,
        preferences: EmployerPreferences
    ) -> Dict:
        """Prepare structured context for LLM"""

        # Census summary
        census_summary = {
            'total_employees': len(census_df),
            'states': census_df['state'].unique().tolist() if 'state' in census_df.columns else [],
            'age_range': {
                'min': int(census_df['age'].min()) if 'age' in census_df.columns else None,
                'max': int(census_df['age'].max()) if 'age' in census_df.columns else None,
                'avg': float(census_df['age'].mean()) if 'age' in census_df.columns else None
            }
        }

        # Query LCSP (Lowest Cost Silver Plan) for each unique employee location
        # This provides the affordability safe harbor benchmark for ICHRA compliance
        lcsp_benchmarks = self._query_lcsp_for_census(census_df)

        # Plan summaries
        plan_summaries = []
        for i, plan in enumerate(top_plans, 1):
            plan_summaries.append({
                'rank': i,
                'plan_id': plan.plan_id,
                'plan_name': plan.plan_name,
                'state': plan.state_code,
                'metal_level': plan.metal_level,
                'plan_type': plan.plan_type,
                'total_annual_cost': plan.total_annual_cost,
                'avg_monthly_cost_per_employee': plan.avg_monthly_cost_per_employee,
                'coverage_percentage': plan.coverage_percentage,
                'employees_covered': plan.employees_covered,
                'total_employees': plan.total_employees,
                'scores': {
                    'total': round(plan.total_score, 1),
                    'cost_efficiency': round(plan.cost_efficiency_score, 1),
                    'coverage': round(plan.coverage_score, 1),
                    'actuarial_value': round(plan.actuarial_value_score, 1),
                    'network_flexibility': round(plan.network_flexibility_score, 1)
                },
                'strengths': plan.strengths,
                'considerations': plan.considerations
            })

        # Preferences summary
        preferences_summary = {
            'contribution_pct': preferences.contribution_pct,
            'metal_levels': preferences.metal_levels,
            'plan_types': preferences.plan_types
        }

        # Calculate marketplace average from top plans
        marketplace_avg_annual = sum(p.total_annual_cost for p in top_plans) / len(top_plans) if top_plans else 0

        # Get group plan data from session state if available
        group_plan_data = None
        try:
            import streamlit as st
            if hasattr(st, 'session_state') and hasattr(st.session_state, 'group_plan'):
                group_plan_data = st.session_state.group_plan
        except (ImportError, AttributeError, RuntimeError):
            pass

        # Build context
        context = {
            'census': census_summary,
            'lcsp_benchmarks': lcsp_benchmarks,
            'marketplace_plans': plan_summaries,
            'preferences': preferences_summary,
            'current_group_plan': group_plan_data
        }

        # Marketplace savings analysis vs group plan
        if group_plan_data:
            group_cost = group_plan_data.get('total_annual_cost')
            if group_cost:
                savings_vs_group = group_cost - marketplace_avg_annual
                context['savings_analysis'] = {
                    'marketplace_vs_group': {
                        'savings': savings_vs_group,
                        'percentage': (savings_vs_group / group_cost * 100) if group_cost > 0 else 0
                    }
                }

        return context

    def _create_analysis_prompt(self, context: Dict) -> str:
        """Create the analysis prompt for Claude - focused on ICHRA cost savings strategy"""

        context_json = json.dumps(context, indent=2)

        # Formatting guidelines
        formatting_guidelines = """**Guidelines:**
- **Output plain text only. Do not use markdown formatting like **bold** or *italics*.
Format currency as plain numbers with $ prefix (e.g., $545,859.13).**
- All numbers should be formatted as USD with commas (e.g., $12,345.67)
- All percentages should be shown as whole numbers (e.g., 25% not 0.25)
- Use consistent formatting for all dollar amounts and percentages throughout
- Write in a professional, consultative tone focused on business value
- Use specific dollar amounts and percentages from the data
- Emphasize cost savings and ROI throughout
- Position ICHRA as a strategic transformation, not just a plan change
- Keep total response under 1500 words
- Use markdown formatting with clear headers and bullet points
- Focus on actionable insights that help the employer make a decision

**TRANSPARENCY REQUIREMENT - Be explicit about what factors influenced your analysis:**
- If employee age distribution affected your recommendations, state this explicitly (e.g., "Given your workforce's younger age profile averaging X years...")
- If geographic location/state coverage influenced plan selection, explain how
- If contribution percentage assumptions drove cost calculations, show the math
- If certain metal levels or plan types were preferred based on the workforce demographics, explain why
- State any assumptions you made about the data
- When comparing costs, be clear about what is being compared (employer cost, employee cost, total cost)
- If certain employees would benefit more from specific options, identify why (age, location, family status)"""

        prompt = f"""Analyze this ICHRA transition opportunity for an employer considering moving from traditional group health insurance to marketplace plans.

**Context:**
{context_json}

**Your Task:**
Provide a strategic ICHRA marketplace analysis for the benefits consultant to present to their client. Structure your response as follows:

## ICHRA Affordability & Cost Analysis (40% of analysis)

**Start with affordability compliance, then lead with the numbers.**

**AFFORDABILITY ANALYSIS (Critical):**
1. The LOWEST-COST SILVER PLAN (LCSP) data is provided in the `lcsp_benchmarks` array in the context
2. Use these pre-calculated LCSP premiums as the benchmark - do NOT attempt to identify LCSP from the marketplace plans
3. This is the affordability benchmark - employer contributions must make the LCSP affordable (9.96% safe harbor)
4. Calculate the minimum employer contribution needed for affordability safe harbor compliance using the provided LCSP premiums
5. Flag any states/rating areas where the current contribution level may not meet affordability requirements

**Cost Analysis:**
- Total annual employer cost for the recommended marketplace plans
- Comparison to current group plan cost (if available in context)
- Projected savings from transitioning to marketplace ICHRA
- Per-employee cost breakdown by state
- **Key message:** Focus on the employer's contribution strategy and affordability compliance

## Recommended Marketplace Plans (40% of analysis)

**Position these as your recommendations.** For each plan:
- Plan name, state, and metal level
- Monthly and annual costs
- Key benefits (deductible, out-of-pocket max, plan type)
- Compare to the LCSP benchmark from `lcsp_benchmarks` (note how this plan compares to the affordability benchmark)
- Why this plan was scored highly
- Which employee demographics it best serves
- **Key message:** These are curated recommendations based on the employer's preferences and employee needs

## ICHRA Implementation Strategy (20% of analysis)

**Practical next steps:**
- Minimum contribution recommendations based on LCSP data provided (use the `lcsp_benchmarks` premiums)
- How to set contribution amounts by employee class
- Employee communication considerations
- Enrollment timeline recommendations
- Key advantages of ICHRA for this employer (employee choice, cost predictability, etc.)

{formatting_guidelines}

**Output Format:**
Return your analysis in markdown format following the three-section structure above."""

        return prompt

    def select_plans_from_candidates(
        self,
        candidate_plans: List[ScoredPlan],
        census_df: pd.DataFrame,
        preferences: EmployerPreferences,
        max_per_state: int = 1
    ) -> Tuple[List[str], str]:
        """
        Use LLM to intelligently select the best plans from scored candidates.

        Args:
            candidate_plans: List of pre-scored candidate plans (top N per state)
            census_df: Employee census data
            preferences: Employer preferences
            max_per_state: Maximum plans to select per state

        Returns:
            Tuple of (selected_plan_ids, analysis_markdown)
        """
        try:
            # Group candidates by state
            candidates_by_state = {}
            for plan in candidate_plans:
                state = plan.state_code
                if state not in candidates_by_state:
                    candidates_by_state[state] = []
                candidates_by_state[state].append(plan)

            # Prepare context for LLM selection
            context = self._prepare_selection_context(
                candidates_by_state,
                census_df,
                preferences
            )

            # Create selection prompt
            prompt = self._create_selection_prompt(context, max_per_state)

            # Call Claude API with system prompt
            self.logger.info(f"Calling Claude API for AI-driven plan selection (model: {self.model})")
            response = self.client.messages.create(
                model=self.model,
                max_tokens=16000,  # More tokens for selection + analysis
                system=ICHRA_SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            response_text = response.content[0].text
            self.logger.info("LLM selection response received")

            # Parse the response to extract selected plan IDs and analysis
            selected_ids, analysis = self._parse_selection_response(response_text, candidate_plans)

            self.logger.info(f"AI selected {len(selected_ids)} plans: {selected_ids}")

            return selected_ids, analysis

        except Exception as e:
            self.logger.error(f"Error in LLM plan selection: {e}")
            # Fallback to algorithmic selection (top 1 per state by score)
            fallback_ids = []
            for state_plans in candidates_by_state.values():
                if state_plans:
                    best = max(state_plans, key=lambda p: p.total_score)
                    fallback_ids.append(best.plan_id)
            return fallback_ids, f"**Note:** AI selection unavailable. Using algorithmic selection.\n\nError: {str(e)}"

    def _prepare_selection_context(
        self,
        candidates_by_state: Dict[str, List[ScoredPlan]],
        census_df: pd.DataFrame,
        preferences: EmployerPreferences
    ) -> Dict:
        """Prepare context for LLM plan selection"""

        # Census summary
        census_summary = {
            'total_employees': len(census_df),
            'states': census_df['state'].unique().tolist() if 'state' in census_df.columns else [],
            'age_range': {
                'min': int(census_df['age'].min()) if 'age' in census_df.columns else None,
                'max': int(census_df['age'].max()) if 'age' in census_df.columns else None,
                'avg': float(census_df['age'].mean()) if 'age' in census_df.columns else None
            }
        }

        # Employees per state
        if 'state' in census_df.columns:
            census_summary['employees_by_state'] = census_df['state'].value_counts().to_dict()

        # Candidate plans by state
        candidates_data = {}
        for state, plans in candidates_by_state.items():
            candidates_data[state] = []
            for plan in plans:
                candidates_data[state].append({
                    'plan_id': plan.plan_id,
                    'plan_name': plan.plan_name,
                    'metal_level': plan.metal_level,
                    'plan_type': plan.plan_type,
                    'total_annual_cost': plan.total_annual_cost,
                    'avg_monthly_cost_per_employee': plan.avg_monthly_cost_per_employee,
                    'employees_covered': plan.employees_covered,
                    'coverage_percentage': plan.coverage_percentage,
                    'scores': {
                        'total': round(plan.total_score, 1),
                        'cost_efficiency': round(plan.cost_efficiency_score, 1),
                        'coverage': round(plan.coverage_score, 1),
                        'actuarial_value': round(plan.actuarial_value_score, 1),
                        'network_flexibility': round(plan.network_flexibility_score, 1)
                    },
                    'strengths': plan.strengths,
                    'considerations': plan.considerations
                })

        # Preferences
        preferences_data = {
            'contribution_pct': preferences.contribution_pct,
            'metal_levels': preferences.metal_levels,
            'plan_types': preferences.plan_types
        }

        context = {
            'census': census_summary,
            'candidates_by_state': candidates_data,
            'preferences': preferences_data
        }

        return context

    def _create_selection_prompt(self, context: Dict, max_per_state: int) -> str:
        """Create prompt for LLM to select best plans"""

        context_json = json.dumps(context, indent=2)

        prompt = f"""SELECT the best marketplace plan(s) for each state based on the employer's workforce, preferences, and ICHRA affordability requirements.

**Context:**
{context_json}

**Your Task:**
1. Analyze the candidate plans for each state
2. IDENTIFY the lowest-cost Silver plan in each state (critical for ICHRA affordability safe harbor)
3. SELECT the best {max_per_state} plan(s) per state based on:
   - **Lowest-cost Silver benchmark** - Always identify and highlight this plan for affordability compliance
   - Cost efficiency for this specific workforce
   - Coverage percentage (how many employees can use the plan)
   - Alignment with employer's metal level and plan type preferences
   - Balance of cost vs. benefits
4. Provide your reasoning for each selection, noting how it relates to the lowest-cost Silver threshold

**IMPORTANT: Response Format**

You MUST respond in exactly this format:

```json
{{
  "selections": [
    {{"state": "CA", "plan_id": "12345CA0123456", "reason": "Brief reason"}},
    {{"state": "TX", "plan_id": "67890TX0654321", "reason": "Brief reason"}}
  ]
}}
```

Then provide your detailed analysis below the JSON block.

---

## Your Analysis

After the JSON block, provide a comprehensive analysis including:

### Cost Analysis & Affordability
- **Lowest-cost Silver plan by state** - Identify the benchmark plan for each state
- Total employer cost across all selected plans
- Cost breakdown by state
- Per-employee cost averages
- Affordability assessment: Does the employer contribution cover the lowest-cost Silver?

### Why These Plans Were Selected
For each state, explain:
- Why the selected plan is the best choice
- How it compares to the lowest-cost Silver benchmark
- Key trade-offs considered
- How it aligns with employer preferences

### ICHRA Implementation Recommendations
- Contribution strategy to meet affordability safe harbor (lowest-cost Silver benchmark)
- Recommended minimum contribution per employee class (if applicable)
- Employee communication considerations
- Any state-specific considerations

**TRANSPARENCY REQUIREMENT:**
Be explicit about what factors influenced your selections:
- State how employee age distribution affected plan choice
- Explain how geographic coverage influenced the selection
- Show how the contribution percentage was factored into cost calculations
- If certain employees would benefit more from specific plans, identify why (age, location, family status)

Remember: Start your response with the JSON block containing your plan selections, then provide the detailed analysis."""

        return prompt

    def _parse_selection_response(
        self,
        response_text: str,
        candidate_plans: List[ScoredPlan]
    ) -> Tuple[List[str], str]:
        """Parse LLM response to extract selected plan IDs and analysis"""

        import re

        selected_ids = []
        analysis = ""

        # Try multiple patterns to find JSON block
        # Pattern 1: Markdown code fences (```json ... ```)
        json_match = re.search(r'```json\s*(\{[\s\S]*?\})\s*```', response_text)

        # Pattern 2: Just code fences without json tag (``` ... ```)
        if not json_match:
            json_match = re.search(r'```\s*(\{[\s\S]*?"selections"[\s\S]*?\})\s*```', response_text)

        # Pattern 3: Unfenced JSON object with selections key
        if not json_match:
            json_match = re.search(r'(\{\s*["\']selections["\'][\s\S]*?\}\s*\][\s\S]*?\})', response_text)

        if json_match:
            try:
                json_str = json_match.group(1)
                selection_data = json.loads(json_str)

                if 'selections' in selection_data:
                    for sel in selection_data['selections']:
                        plan_id = sel.get('plan_id', '')
                        # Validate plan_id exists in candidates
                        if any(p.plan_id == plan_id for p in candidate_plans):
                            selected_ids.append(plan_id)
                        else:
                            self.logger.warning(f"LLM selected invalid plan_id: {plan_id}")

                # Remove the entire JSON block from the response to get clean analysis
                # First, find the full match span in original text
                full_json_pattern = re.search(r'```json[\s\S]*?```|```[\s\S]*?```|\{[\s\S]*?"selections"[\s\S]*?\}\s*\][\s\S]*?\}', response_text)
                if full_json_pattern:
                    analysis = response_text[:full_json_pattern.start()] + response_text[full_json_pattern.end():]
                else:
                    analysis = response_text

                # Clean up the analysis
                analysis = analysis.strip()
                # Remove leading dashes/separators
                analysis = re.sub(r'^[\s\-]*', '', analysis)
                # Remove any "Here is my selection:" type prefixes
                analysis = re.sub(r'^(Here (is|are) (my|the) (selection|plan|recommendation)s?:?\s*)', '', analysis, flags=re.IGNORECASE)

            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse LLM JSON response: {e}")
                # Try to extract plan IDs from the text using regex
                plan_ids_in_response = re.findall(r'\d{5}[A-Z]{2}\d{7}', response_text)
                for pid in plan_ids_in_response:
                    if any(p.plan_id == pid for p in candidate_plans) and pid not in selected_ids:
                        selected_ids.append(pid)
                analysis = response_text

        else:
            # No JSON found - use full response as analysis
            analysis = response_text

        # Fallback if no valid selections found
        if not selected_ids:
            self.logger.warning("No valid plan selections parsed from LLM response, using top-scored plans")
            # Group by state and take top scorer
            plans_by_state = {}
            for plan in candidate_plans:
                if plan.state_code not in plans_by_state:
                    plans_by_state[plan.state_code] = []
                plans_by_state[plan.state_code].append(plan)

            for state_plans in plans_by_state.values():
                if state_plans:
                    best = max(state_plans, key=lambda p: p.total_score)
                    selected_ids.append(best.plan_id)

        # Final cleanup - remove any remaining JSON-like structures from analysis
        analysis = re.sub(r'\{\s*["\']selections["\'][\s\S]*?\}\s*\][\s\S]*?\}', '', analysis)
        analysis = analysis.strip()

        # Apply comprehensive LLM output cleanup
        analysis = clean_llm_output(analysis)

        return selected_ids, analysis
