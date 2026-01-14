"""
ICHRA Comparison Dashboard
Based on Figma design - Broker presentation view for client census analysis
Data-driven: All values calculated from census upload
"""

import streamlit as st
import pandas as pd
# Opt-in to future pandas behavior for fillna (avoids FutureWarning)
pd.set_option('future.no_silent_downcasting', True)
import plotly.express as px
import plotly.graph_objects as go
import sys
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import get_database_connection, DatabaseConnection
from utils import ContributionComparison, PremiumCalculator
from financial_calculator import FinancialSummaryCalculator
from pptx_cooperative_health import CooperativeHealthData, generate_cooperative_health_slide
from pptx_employee_examples import generate_employee_examples_pptx
from queries import get_plan_deductible_and_moop_batch, HealthCheckQueries
from constants import (
    FAMILY_STATUS_CODES,
    AFFORDABILITY_THRESHOLD_2026,
    CURRENT_PLAN_YEAR,
    RENEWAL_PLAN_YEAR,
    COOPERATIVE_CONFIG,
    METAL_COST_RATIOS,
    DEFAULT_ADOPTION_RATES,
    OLDER_POPULATION_WARNING_AGE,
    DISPLAY_PLACEHOLDERS,
    TIER_COLORS,
    TIER_LABELS,
)

# Custom CSS to match Figma design
st.markdown("""
<style>
    /* Import Poppins font */
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&family=Inter:wght@400;700&display=swap');

    /* Base styles */
    .stApp {
        font-family: 'Poppins', sans-serif;
        background-color: #ffffff;
    }

    [data-testid="stSidebar"] {
        background-color: #F0F4FA;
    }

    /* Sidebar navigation links */
    [data-testid="stSidebarNav"] a {
        background-color: transparent !important;
    }
    [data-testid="stSidebarNav"] a[aria-selected="true"] {
        background-color: #E8F1FD !important;
        border-left: 3px solid #0047AB !important;
    }
    [data-testid="stSidebarNav"] a:hover {
        background-color: #E8F1FD !important;
    }

    /* Sidebar buttons */
    [data-testid="stSidebar"] button {
        background-color: #E8F1FD !important;
        border: 1px solid #B3D4FC !important;
        color: #0047AB !important;
    }
    [data-testid="stSidebar"] button:hover {
        background-color: #B3D4FC !important;
        border-color: #0047AB !important;
    }

    /* Info boxes in sidebar */
    [data-testid="stSidebar"] [data-testid="stAlert"] {
        background-color: #E8F1FD !important;
        border: 1px solid #B3D4FC !important;
        color: #003d91 !important;
    }

    /* Hero section */
    .hero-section {
        background: linear-gradient(135deg, #ffffff 0%, #e8f1fd 100%);
        border-radius: 12px;
        padding: 32px;
        margin-bottom: 24px;
        border-left: 4px solid #0047AB;
    }

    .hero-title {
        font-family: 'Poppins', sans-serif;
        font-size: 28px;
        font-weight: 700;
        color: #0a1628;
        margin-bottom: 8px;
    }

    .hero-subtitle {
        font-size: 16px;
        color: #475569;
        margin: 0;
    }

    /* Header styles */
    .client-header {
        background: white;
        border-bottom: 4px solid #e5e7eb;
        padding: 24px 0;
        margin-bottom: 24px;
        box-shadow: 0px 1px 3px rgba(0,0,0,0.1);
    }

    .client-name {
        font-size: 24px;
        font-weight: 500;
        color: #101828;
        margin: 0;
        font-family: 'Poppins', sans-serif;
    }

    .client-meta {
        font-size: 16px;
        color: #364153;
        font-weight: 500;
    }

    .client-meta-divider {
        color: #99a1af;
        margin: 0 8px;
    }

    /* Recommendation banner */
    .recommendation-banner {
        background: #dcfce7;
        border: 2px solid #7bf1a8;
        border-radius: 10px;
        padding: 12px 24px;
        display: flex;
        align-items: center;
        gap: 8px;
    }

    .recommendation-text {
        color: #016630;
        font-size: 18px;
        font-weight: 700;
    }

    /* Savings display */
    .savings-amount {
        color: #00a63e;
        font-size: 16px;
        font-weight: 700;
        font-family: 'Inter', sans-serif;
    }

    /* Increase badge */
    .increase-badge {
        background: #ffe2e2;
        color: #c10007;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 14px;
        font-weight: 500;
    }

    /* Card styles */
    .insight-card {
        background: white;
        border-radius: 10px;
        padding: 24px;
        box-shadow: 0px 1px 3px rgba(0,0,0,0.1);
        height: 100%;
    }

    .card-title {
        font-size: 18px;
        font-weight: 700;
        color: #101828;
        margin-bottom: 16px;
    }

    /* Warning/info boxes */
    .warning-box {
        background: #E8F1FD;
        border: 1px solid #B3D4FC;
        border-radius: 8px;
        padding: 12px;
        display: flex;
        gap: 8px;
        align-items: flex-start;
    }

    .warning-text {
        color: #003d91;
        font-size: 14px;
    }

    .error-box {
        background: #fef2f2;
        border: 1px solid #ffc9c9;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 16px;
    }

    .error-title {
        color: #101828;
        font-size: 16px;
        font-weight: 500;
        margin-bottom: 4px;
    }

    .error-subtitle {
        color: #364153;
        font-size: 14px;
    }

    .info-box {
        background: #eff6ff;
        border: 1px solid #bedbff;
        border-radius: 8px;
        padding: 12px 16px;
    }

    .info-text {
        color: #1c398e;
        font-size: 14px;
        font-weight: 500;
    }

    .success-box {
        background: #f0fdf4;
        border: 1px solid #b9f8cf;
        border-radius: 8px;
        padding: 12px 16px;
    }

    .success-text {
        color: #0d542b;
        font-size: 16px;
    }

    /* Progress bar colors */
    .stProgress > div > div {
        height: 8px;
        border-radius: 9999px;
    }

    /* Table styles */
    .comparison-table {
        width: 100%;
        border-collapse: collapse;
        font-family: 'Poppins', sans-serif;
    }

    .comparison-table th {
        padding: 16px 12px;
        text-align: center;
        font-weight: 700;
        font-size: 16px;
    }

    .comparison-table td {
        padding: 12px;
        text-align: right;
        font-family: 'Inter', sans-serif;
        font-size: 16px;
    }

    .comparison-table .row-label {
        text-align: left;
        font-family: 'Poppins', sans-serif;
        font-weight: 500;
        color: #101828;
    }

    /* Column header backgrounds */
    .col-current { background: #E8F1FD; color: #0047AB; border-left: 4px solid #0047AB; }
    .col-renewal { background: #fef2f2; color: #82181a; border-left: 4px solid #ffa2a2; }
    .col-bronze { background: #FEF3E2; color: #92400e; }
    .col-silver { background: #E8F1FD; color: #003d91; }
    .col-gold { background: #FEF9C3; color: #854d0e; }
    .col-coop { background: #ecfdf5; color: #047857; }

    /* Employee card */
    .employee-card {
        background: white;
        border: 2px solid #e5e7eb;
        border-radius: 10px;
        padding: 24px;
    }

    .employee-name {
        font-size: 18px;
        font-weight: 700;
        color: #101828;
    }

    .employee-meta {
        font-size: 14px;
        color: #4a5565;
    }

    /* Key messages */
    .key-message {
        background: #f0fdf4;
        border: 1px solid #b9f8cf;
        border-radius: 8px;
        padding: 12px;
        margin-bottom: 12px;
    }

    .key-message-text {
        color: #101828;
        font-size: 16px;
    }

    /* Button styles */
    .primary-button {
        background: #155dfc;
        color: white;
        padding: 12px 24px;
        border-radius: 10px;
        font-weight: 700;
        font-size: 16px;
        text-align: center;
        cursor: pointer;
        border: none;
        width: 100%;
    }

    /* Metric overrides */
    [data-testid="stMetricValue"] {
        font-family: 'Inter', sans-serif;
    }
</style>
""", unsafe_allow_html=True)


# =============================================================================
# DATA LOADER - Calculates all metrics from census
# =============================================================================

@dataclass
class DashboardData:
    """Container for all dashboard data calculated from census"""
    # Client info
    client_name: str = "Company"
    employee_count: int = 0
    avg_age: float = 0
    location: str = ""
    current_premium: float = 0
    renewal_premium: float = 0
    increase_pct: float = 0

    # Workforce composition
    composition: Dict[str, Dict] = field(default_factory=dict)

    # Demographics
    youngest_age: int = 0
    oldest_age: int = 0
    average_age: float = 0

    # Plan costs by tier
    tier_costs: Dict[str, Dict[str, float]] = field(default_factory=dict)

    # Company totals
    company_totals: Dict[str, float] = field(default_factory=dict)

    # Savings vs renewal
    savings_vs_renewal: Dict[str, Dict] = field(default_factory=dict)

    # Employee examples
    employee_examples: List[Dict] = field(default_factory=list)

    # Expected adoption
    expected_adoption: Dict[str, Dict] = field(default_factory=dict)

    # Affordability
    affordability_failures: int = 0
    total_analyzed: int = 0

    # States
    states: List[str] = field(default_factory=list)

    # Data availability flags
    has_current_costs: bool = False
    has_renewal_data: bool = False
    has_lcsp_data: bool = False

    # Multi-metal results from database (Bronze, Silver, Gold)
    multi_metal_results: Dict[str, Dict] = field(default_factory=dict)

    # Diagnostic information for debugging
    diagnostic_errors: List[str] = field(default_factory=list)
    diagnostic_info: Dict[str, Any] = field(default_factory=dict)

    # Contribution percentage from Page 2
    contribution_pct: float = 0.65

    # EE/ER contribution split (calculated from census)
    ee_contribution_pct: float = 0.0  # Employee share (e.g., 0.35 = 35%)
    er_contribution_pct: float = 0.0  # Employer share (e.g., 0.65 = 65%)

    # Actuarial values for each metal level (from database)
    metal_av: Dict[str, float] = field(default_factory=lambda: {
        'Bronze': 60.0,  # Default fallback
        'Silver': 70.0,
        'Gold': 80.0
    })


def load_dashboard_data(census_df: pd.DataFrame, dependents_df: pd.DataFrame = None,
                        contribution_analysis: Dict = None, financial_summary: Dict = None,
                        contribution_settings: Dict = None,
                        client_name: str = "Company", db=None,
                        dashboard_config: Dict = None) -> DashboardData:
    """
    Load and calculate all dashboard data from census and session state.

    Args:
        census_df: Employee census DataFrame
        dependents_df: Dependents DataFrame (optional)
        contribution_analysis: Per-employee ICHRA analysis (optional)
        financial_summary: Financial summary data (optional)
        contribution_settings: Employer contribution settings from Page 2 (optional)
        client_name: Client/company name
        db: Database connection for LCSP lookups
        dashboard_config: User-adjustable dashboard settings (adoption rates, cooperative ratio)

    Returns:
        DashboardData with all calculated values
    """
    data = DashboardData()

    # Extract contribution settings from Page 2 (default 65%)
    flat_amounts = None
    if contribution_settings:
        data.contribution_pct = contribution_settings.get('default_percentage', 65) / 100.0
        # Get flat amounts if in flat_amount mode
        if contribution_settings.get('input_mode') == 'flat_amount':
            flat_amounts = contribution_settings.get('flat_amounts', {})
            # Filter out None values
            flat_amounts = {k: v for k, v in flat_amounts.items() if v is not None}
            if not flat_amounts:
                flat_amounts = None
    else:
        data.contribution_pct = 0.65  # Default fallback
    data.client_name = client_name

    if census_df is None or census_df.empty:
        return data

    # ==========================================================================
    # BASIC DEMOGRAPHICS
    # ==========================================================================
    data.employee_count = len(census_df)

    # Age calculations - check multiple possible column names
    age_col = None
    for col_name in ['age', 'Age', 'EE Age', 'ee_age']:
        if col_name in census_df.columns:
            age_col = col_name
            break

    if age_col:
        ages = pd.to_numeric(census_df[age_col], errors='coerce').dropna()
        if len(ages) > 0:
            data.youngest_age = int(ages.min())
            data.oldest_age = int(ages.max())
            data.average_age = round(ages.mean(), 1)
            data.avg_age = data.average_age

    # States - check multiple possible column names
    state_col = None
    for col_name in ['state', 'State', 'Home State', 'home_state']:
        if col_name in census_df.columns:
            state_col = col_name
            break

    if state_col:
        data.states = census_df[state_col].dropna().unique().tolist()
        if len(data.states) == 1:
            data.location = f"{data.states[0]} only"
        else:
            data.location = f"{len(data.states)} states"

    # ==========================================================================
    # WORKFORCE COMPOSITION (Family Status breakdown)
    # ==========================================================================
    # Check for family_status column (lowercase from parser) or Family Status (raw)
    family_col = None
    if 'family_status' in census_df.columns:
        family_col = 'family_status'
    elif 'Family Status' in census_df.columns:
        family_col = 'Family Status'

    if family_col:
        status_counts = census_df[family_col].value_counts()
        for code in ["EE", "ES", "EC", "F"]:
            # Handle both uppercase and potential variations
            count = 0
            if code in status_counts.index:
                count = int(status_counts[code])
            elif code.lower() in status_counts.index:
                count = int(status_counts[code.lower()])

            if count > 0:
                data.composition[TIER_LABELS.get(code, code)] = {
                    "count": count,
                    "color": TIER_COLORS.get(code, "#6a7282")
                }

    # ==========================================================================
    # CURRENT COSTS (from census if available)
    # ==========================================================================
    contrib_totals = ContributionComparison.aggregate_contribution_totals(census_df)
    current_er_monthly = contrib_totals.get('total_current_er_monthly', 0)
    current_ee_monthly = contrib_totals.get('total_current_ee_monthly', 0)
    current_total_monthly = current_er_monthly + current_ee_monthly

    if current_total_monthly > 0:
        data.has_current_costs = True
        data.current_premium = current_total_monthly

    # ==========================================================================
    # CONTRIBUTION PATTERN DETECTION (percentage vs flat-rate per tier)
    # ==========================================================================
    contribution_pattern = None
    if ContributionComparison.has_individual_contributions(census_df):
        contribution_pattern = ContributionComparison.detect_contribution_pattern(census_df)
        # Store in session state for use by PPTX generator and other pages
        st.session_state['detected_contribution_pattern'] = contribution_pattern

    # Calculate overall EE/ER contribution split from census
    if current_total_monthly > 0:
        data.er_contribution_pct = current_er_monthly / current_total_monthly
        data.ee_contribution_pct = current_ee_monthly / current_total_monthly

    # ==========================================================================
    # RENEWAL DATA (from financial summary or census)
    # ==========================================================================
    renewal_monthly = 0
    if financial_summary and financial_summary.get('renewal_monthly'):
        renewal_monthly = financial_summary['renewal_monthly']
        data.has_renewal_data = True
    else:
        # Try to calculate from census 2026 premium column
        projected_data = FinancialSummaryCalculator.calculate_projected_2026_total(census_df)
        if projected_data.get('has_data'):
            renewal_monthly = projected_data.get('total_monthly', 0)
            data.has_renewal_data = True

    if renewal_monthly > 0:
        data.renewal_premium = renewal_monthly
        if data.current_premium > 0:
            data.increase_pct = round(((renewal_monthly / data.current_premium) - 1) * 100, 1)

    # ==========================================================================
    # MULTI-METAL COSTS (Bronze, Silver, Gold from database)
    # ==========================================================================
    if db is not None:
        try:
            # Collect diagnostic info about census data before calculation
            rating_area_col = 'rating_area_id' if 'rating_area_id' in census_df.columns else None
            if rating_area_col:
                ra_values = census_df[rating_area_col].dropna().unique().tolist()
                null_ra_count = census_df[rating_area_col].isna().sum()
                data.diagnostic_info['rating_areas_found'] = ra_values
                data.diagnostic_info['employees_missing_rating_area'] = int(null_ra_count)
                if null_ra_count > 0:
                    data.diagnostic_errors.append(
                        f"{null_ra_count} employees have no rating_area_id (ZIP lookup failed)"
                    )
            else:
                data.diagnostic_errors.append("Census is missing 'rating_area_id' column - ZIP lookup may have failed")

            # Get unique states
            state_col = 'state' if 'state' in census_df.columns else 'Home State'
            if state_col in census_df.columns:
                data.diagnostic_info['states'] = census_df[state_col].unique().tolist()

            data.multi_metal_results = FinancialSummaryCalculator.calculate_multi_metal_scenario(
                census_df, db, ['Bronze', 'Silver', 'Gold'], dependents_df
            )
            data.has_lcsp_data = True

            # Extract average actuarial values and errors from multi-metal results
            for metal in ['Bronze', 'Silver', 'Gold']:
                metal_data = data.multi_metal_results.get(metal, {})
                avg_av = metal_data.get('average_av')
                if avg_av is not None:
                    data.metal_av[metal] = avg_av

                # Capture errors from the calculation
                metal_errors = metal_data.get('errors', [])
                if metal_errors:
                    # Just show first few unique errors to avoid overwhelming
                    unique_errors = list(set(metal_errors))[:5]
                    data.diagnostic_errors.extend([f"[{metal}] {e}" for e in unique_errors])
                    if len(metal_errors) > 5:
                        data.diagnostic_errors.append(f"[{metal}] ...and {len(metal_errors) - 5} more errors")

                # Check if we got zero results
                total_monthly = metal_data.get('total_monthly', 0)
                employees_covered = metal_data.get('employees_covered', 0)
                data.diagnostic_info[f'{metal}_total_monthly'] = total_monthly
                data.diagnostic_info[f'{metal}_employees_covered'] = employees_covered

                if total_monthly == 0 and employees_covered > 0:
                    data.diagnostic_errors.append(
                        f"[{metal}] {employees_covered} employees processed but total premium is $0"
                    )

        except Exception as e:
            import logging
            import traceback
            logging.warning(f"Multi-metal calculation failed: {e}")
            logging.warning(traceback.format_exc())
            data.diagnostic_errors.append(f"Multi-metal calculation exception: {str(e)}")
            data.multi_metal_results = {}
    else:
        data.diagnostic_errors.append("Database connection is None - cannot calculate ICHRA rates")

    # ==========================================================================
    # TIER-LEVEL COSTS (average per family status)
    # ==========================================================================
    # Get cooperative_ratio from dashboard_config if provided
    cooperative_ratio = COOPERATIVE_CONFIG['default_discount_ratio']
    if dashboard_config and 'cooperative_ratio' in dashboard_config:
        cooperative_ratio = dashboard_config['cooperative_ratio']

    # Load cooperative rate table from database (cached)
    coop_rates_df = load_cooperative_rate_table(_db_available=db is not None)

    data.tier_costs = calculate_tier_costs(
        census_df, contribution_analysis, db,
        multi_metal_results=data.multi_metal_results,
        renewal_monthly=renewal_monthly,
        cooperative_ratio=cooperative_ratio,
        coop_rates_df=coop_rates_df,
        dependents_df=dependents_df
    )

    # ==========================================================================
    # COMPANY TOTALS
    # ==========================================================================
    data.company_totals = calculate_company_totals(
        census_df, contribution_analysis, data.tier_costs,
        multi_metal_results=data.multi_metal_results,
        contribution_pct=data.contribution_pct,
        renewal_monthly=renewal_monthly,
        cooperative_ratio=cooperative_ratio,
        coop_rates_df=coop_rates_df,
        dependents_df=dependents_df
    )

    # ==========================================================================
    # SAVINGS VS RENEWAL
    # ==========================================================================
    if data.has_renewal_data and data.renewal_premium > 0:
        renewal_total = data.company_totals.get(f'Renewal {RENEWAL_PLAN_YEAR}', data.renewal_premium)
        for scenario in ['ICHRA Bronze', 'ICHRA Silver', 'ICHRA Gold', 'Cooperative']:
            scenario_total = data.company_totals.get(scenario, 0)
            if scenario_total > 0:
                savings = renewal_total - scenario_total
                base_for_pct = renewal_total if renewal_total > 0 else 1  # Avoid div by zero
                pct = round((savings / base_for_pct) * 100, 1)
                data.savings_vs_renewal[scenario] = {
                    "amount": savings,
                    "pct": -pct  # Negative to show reduction
                }

    # ==========================================================================
    # EMPLOYEE EXAMPLES (youngest, mid-age family, oldest)
    # ==========================================================================
    # Load Sedera rates if Sedera is enabled in plan_configurator
    sedera_rates_df = None
    plan_config = st.session_state.get('plan_configurator', {})
    if plan_config.get('sedera_enabled', False) and plan_config.get('sedera_iuas'):
        sedera_rates_df = load_sedera_rate_table(_db_available=db is not None)

    data.employee_examples = select_employee_examples(
        census_df, contribution_analysis, data.tier_costs,
        data.multi_metal_results, data.contribution_pct,
        cooperative_ratio=cooperative_ratio,
        dependents_df=dependents_df,
        db=db,
        coop_rates_df=coop_rates_df,
        flat_amounts=flat_amounts,
        sedera_rates_df=sedera_rates_df,
        plan_config=plan_config,
        contribution_settings=contribution_settings
    )

    # ==========================================================================
    # EXPECTED ADOPTION (from dashboard_config or defaults)
    # ==========================================================================
    # Use dashboard_config if provided, otherwise fall back to constants
    adoption_rates = DEFAULT_ADOPTION_RATES.copy()
    if dashboard_config and 'adoption_rates' in dashboard_config:
        adoption_rates = dashboard_config['adoption_rates']

    data.expected_adoption = {
        "Cooperative": {"pct": adoption_rates.get('Cooperative', 70), "color": "#00c950"},
        "ICHRA Silver": {"pct": adoption_rates.get('ICHRA Silver', 20), "color": "#6a7282"},
        "ICHRA Gold": {"pct": adoption_rates.get('ICHRA Gold', 10), "color": "#f0b100"},
    }

    # ==========================================================================
    # AFFORDABILITY ANALYSIS
    # ==========================================================================
    if contribution_analysis:
        for emp_id, analysis in contribution_analysis.items():
            if 'affordability' in analysis:
                data.total_analyzed += 1
                if not analysis['affordability'].get('is_affordable', True):
                    data.affordability_failures += 1

    return data


def calculate_tier_costs(census_df: pd.DataFrame, contribution_analysis: Dict = None,
                         db=None, multi_metal_results: Dict = None,
                         renewal_monthly: float = None,
                         cooperative_ratio: float = None,
                         coop_rates_df: pd.DataFrame = None,
                         dependents_df: pd.DataFrame = None) -> Dict[str, Dict[str, float]]:
    """
    Calculate average costs per family status tier.

    Uses actual Bronze/Silver/Gold data from multi_metal_results when available,
    otherwise falls back to estimates.

    Args:
        census_df: Employee census DataFrame
        contribution_analysis: Per-employee ICHRA analysis (optional)
        db: Database connection (unused, kept for API compatibility)
        multi_metal_results: Results from calculate_multi_metal_scenario() with actual rates
        renewal_monthly: Actual renewal amount from Page 3 (optional)
        cooperative_ratio: Cooperative cost as fraction of Silver (from dashboard_config)
        dependents_df: DataFrame with dependent info for family rate calculations

    Returns dict with structure:
    {
        "Employee Only": {"Current 2025": 650, "Renewal 2026": 780, ...},
        "EE + Spouse": {...},
        ...
    }
    """
    # Use provided cooperative_ratio or fall back to constant
    if cooperative_ratio is None:
        cooperative_ratio = COOPERATIVE_CONFIG['default_discount_ratio']
    tier_mapping = {
        "EE": "Employee Only",
        "ES": "Employee + Spouse",
        "EC": "Employee + Children",
        "F": "Family",
    }

    tier_costs = {
        "Employee Only": {},
        "Employee + Spouse": {},
        "Employee + Children": {},
        "Family": {},
    }

    # Group census by family status
    family_col = 'family_status' if 'family_status' in census_df.columns else None
    if not family_col and 'Family Status' in census_df.columns:
        family_col = 'Family Status'

    if not family_col:
        return tier_costs

    # OPTIMIZATION: Build cooperative rate lookup once for O(1) access
    coop_lookup = build_cooperative_rate_lookup(coop_rates_df) if coop_rates_df is not None else {}

    # Pre-calculate metal costs by tier from multi_metal_results
    metal_costs_by_tier = {}
    if multi_metal_results:
        for metal in ['Bronze', 'Silver', 'Gold']:
            metal_data = multi_metal_results.get(metal, {})
            employee_details = metal_data.get('employee_details', [])

            # Group by family status and calculate average
            for status_code, tier_name in tier_mapping.items():
                tier_premiums = [
                    emp['estimated_tier_premium']
                    for emp in employee_details
                    if emp.get('family_status') == status_code and emp.get('estimated_tier_premium', 0) > 0
                ]
                if tier_premiums:
                    avg_premium = sum(tier_premiums) / len(tier_premiums)
                    if tier_name not in metal_costs_by_tier:
                        metal_costs_by_tier[tier_name] = {}
                    metal_costs_by_tier[tier_name][f'ICHRA {metal}'] = round(avg_premium, 0)

    for status_code, tier_name in tier_mapping.items():
        tier_employees = census_df[census_df[family_col] == status_code]
        if tier_employees.empty:
            continue

        # Current costs (from census) - TOTAL PREMIUM (ER + EE)
        current_total = 0
        if 'current_er_monthly' in tier_employees.columns:
            current_er = tier_employees['current_er_monthly'].fillna(0).mean()
            current_total += current_er if pd.notna(current_er) else 0
        if 'current_ee_monthly' in tier_employees.columns:
            current_ee = tier_employees['current_ee_monthly'].fillna(0).mean()
            current_total += current_ee if pd.notna(current_ee) else 0
        if current_total > 0:
            tier_costs[tier_name][f'Current {CURRENT_PLAN_YEAR}'] = round(current_total, 0)

        # Renewal costs - TOTAL PREMIUM, use actual data if available, otherwise estimate
        if renewal_monthly and renewal_monthly > 0:
            # Pro-rate renewal by tier's share of current total premium
            total_current_all = 0
            if 'current_er_monthly' in census_df.columns:
                total_current_all += census_df['current_er_monthly'].fillna(0).sum()
            if 'current_ee_monthly' in census_df.columns:
                total_current_all += census_df['current_ee_monthly'].fillna(0).sum()

            tier_current_total = 0
            if 'current_er_monthly' in tier_employees.columns:
                tier_current_total += tier_employees['current_er_monthly'].fillna(0).sum()
            if 'current_ee_monthly' in tier_employees.columns:
                tier_current_total += tier_employees['current_ee_monthly'].fillna(0).sum()

            if total_current_all > 0:
                tier_share = tier_current_total / total_current_all
                tier_renewal = (renewal_monthly * tier_share) / len(tier_employees) if len(tier_employees) > 0 else 0
                tier_costs[tier_name][f'Renewal {RENEWAL_PLAN_YEAR}'] = round(tier_renewal, 0)
            # No fallback - if no renewal data, leave empty (will show N/A)
        # No fallback - require actual renewal data

        # ICHRA costs - use actual data from multi_metal_results if available
        if tier_name in metal_costs_by_tier:
            for metal_key, cost in metal_costs_by_tier[tier_name].items():
                tier_costs[tier_name][metal_key] = cost

            # Cooperative - use rate table if available, otherwise ratio of silver
            # Uses eldest family member's age band for all members
            if coop_lookup:
                # Calculate cooperative rate for each employee using family rate function
                # This applies the eldest member age band rule
                coop_rates = []
                for _, emp_row in tier_employees.iterrows():
                    coop_rate = calculate_cooperative_family_rate(
                        emp_row, status_code, coop_lookup, dependents_df
                    )
                    if coop_rate > 0:
                        coop_rates.append(coop_rate)
                if coop_rates:
                    tier_costs[tier_name]['Cooperative'] = round(sum(coop_rates) / len(coop_rates), 0)
                else:
                    # Fallback to ratio if no rates found
                    silver_cost = metal_costs_by_tier[tier_name].get('ICHRA Silver', 0)
                    if silver_cost > 0:
                        tier_costs[tier_name]['Cooperative'] = round(silver_cost * cooperative_ratio, 0)
            else:
                # Fallback to ratio if no rate table
                silver_cost = metal_costs_by_tier[tier_name].get('ICHRA Silver', 0)
                if silver_cost > 0:
                    tier_costs[tier_name]['Cooperative'] = round(silver_cost * cooperative_ratio, 0)
        elif contribution_analysis:
            # Fallback to contribution_analysis if multi_metal not available
            ichra_costs = []
            for _, row in tier_employees.iterrows():
                emp_id = row.get('employee_id')
                if emp_id and emp_id in contribution_analysis:
                    analysis = contribution_analysis[emp_id]
                    ichra_data = analysis.get('ichra_analysis', {})
                    if ichra_data.get('monthly_premium'):
                        ichra_costs.append(ichra_data['monthly_premium'])

            if ichra_costs:
                avg_lcsp = sum(ichra_costs) / len(ichra_costs)
                # Fallback estimates using metal cost ratios from constants
                tier_costs[tier_name]['ICHRA Bronze'] = round(avg_lcsp * METAL_COST_RATIOS['Bronze'], 0)
                tier_costs[tier_name]['ICHRA Silver'] = round(avg_lcsp * METAL_COST_RATIOS['Silver'], 0)
                tier_costs[tier_name]['ICHRA Gold'] = round(avg_lcsp * METAL_COST_RATIOS['Gold'], 0)
                tier_costs[tier_name]['Cooperative'] = round(avg_lcsp * cooperative_ratio, 0)

    return tier_costs


@st.cache_data(show_spinner=False, ttl=3600)  # Cache for 1 hour
def load_cooperative_rate_table(_db_available: bool = False) -> pd.DataFrame:
    """Load the HAS (Health Access Solutions) cooperative rate table from database."""
    db = st.session_state.get('db')
    if db is None:
        return pd.DataFrame()

    query = """
    SELECT age_band, family_status, deductible_1k, deductible_2_5k
    FROM hap_cooperative_rates
    ORDER BY age_band, family_status
    """
    try:
        return pd.read_sql(query, db.engine)
    except Exception as e:
        print(f"Error loading cooperative rates: {e}")
        return pd.DataFrame()


def _get_age_band(age: int) -> str:
    """Convert age to cooperative rate age band."""
    if age < 30:
        return "18-29"
    elif age < 40:
        return "30-39"
    elif age < 50:
        return "40-49"
    elif age < 60:
        return "50-59"
    else:
        return "60-64"


def build_cooperative_rate_lookup(coop_rates_df: pd.DataFrame, deductible: str = "2.5k") -> Dict:
    """
    Build a lookup dictionary from cooperative rates DataFrame for O(1) access.

    Args:
        coop_rates_df: DataFrame from load_cooperative_rate_table()
        deductible: "1k" or "2.5k" (default "2.5k")

    Returns:
        Dict mapping (age_band, family_status) -> rate
    """
    if coop_rates_df is None or coop_rates_df.empty:
        return {}

    col = 'deductible_2_5k' if deductible == "2.5k" else 'deductible_1k'
    lookup = {}
    for _, row in coop_rates_df.iterrows():
        key = (row['age_band'], row['family_status'])
        lookup[key] = float(row[col]) if pd.notna(row[col]) else 0
    return lookup


def get_cooperative_rate(age: int, family_status: str, coop_rates_df: pd.DataFrame,
                         deductible: str = "2.5k") -> float:
    """
    Look up cooperative rate based on age and family status.

    Args:
        age: Employee age
        family_status: EE, ES, EC, or F
        coop_rates_df: DataFrame from load_cooperative_rate_table()
        deductible: "1k" or "2.5k" (default "2.5k")

    Returns:
        Monthly cooperative rate
    """
    if coop_rates_df is None or coop_rates_df.empty:
        return 0

    # Map family status codes
    status_map = {"EE": "EE", "ES": "ES", "EC": "EC", "F": "F"}
    fs = status_map.get(family_status, "EE")

    age_band = _get_age_band(age)

    # Look up rate
    row = coop_rates_df[(coop_rates_df['age_band'] == age_band) &
                        (coop_rates_df['family_status'] == fs)]
    if not row.empty:
        col = 'deductible_2_5k' if deductible == "2.5k" else 'deductible_1k'
        return float(row[col].iloc[0])
    return 0


def get_cooperative_rate_fast(age: int, family_status: str, lookup: Dict) -> float:
    """
    Fast O(1) lookup for cooperative rate using pre-built dictionary.

    Args:
        age: Employee age
        family_status: EE, ES, EC, or F
        lookup: Dictionary from build_cooperative_rate_lookup()

    Returns:
        Monthly cooperative rate
    """
    if not lookup:
        return 0

    status_map = {"EE": "EE", "ES": "ES", "EC": "EC", "F": "F"}
    fs = status_map.get(family_status, "EE")
    age_band = _get_age_band(age)

    return lookup.get((age_band, fs), 0)


def calculate_cooperative_family_rate(
    employee_row: pd.Series,
    family_status: str,
    lookup: Dict,
    dependents_df: pd.DataFrame = None,
    return_breakdown: bool = False
) -> Union[float, Dict]:
    """
    Calculate cooperative rate using GROUP PRICING - single rate based on oldest member's age band.

    IMPORTANT: HAS/Cooperative uses GROUP PRICING, meaning the family pays ONE rate based on the
    eldest family member's age band. Unlike individual marketplace plans which charge
    per-member rates, HAS charges a single family rate.

    Args:
        employee_row: Census row for the employee
        family_status: EE, ES, EC, or F
        lookup: Dictionary from build_cooperative_rate_lookup()
        dependents_df: DataFrame with dependent info (employee_id, relationship, age)
        return_breakdown: If True, return dict with rate info

    Returns:
        If return_breakdown=False: Total monthly cooperative premium (float) - single rate for family
        If return_breakdown=True: Dict with structure:
            {
                'ee_rate': float, 'ee_age': int,
                'spouse_rate': None (not applicable for group pricing),
                'child_X_rate': None (not applicable for group pricing),
                'total_rate': float (same as ee_rate for group pricing),
                'eldest_age_band': str,
                'rate_per_member': float (the single group rate)
            }
    """
    # Initialize breakdown structure
    member_rates = {
        'ee_rate': 0.0,
        'ee_age': None,
        'spouse_rate': None,
        'spouse_age': None,
    }
    for i in range(1, 6):
        member_rates[f'child_{i}_rate'] = None
        member_rates[f'child_{i}_age'] = None

    if not lookup:
        if return_breakdown:
            return {**member_rates, 'total_rate': 0.0, 'eldest_age_band': None, 'rate_per_member': 0.0}
        return 0.0

    emp_id = employee_row.get('employee_id', '')
    emp_age = int(employee_row.get('age', 0))
    member_rates['ee_age'] = emp_age

    # For Employee Only, just get the EE rate using employee's age
    if family_status == 'EE':
        rate = get_cooperative_rate_fast(emp_age, family_status, lookup)
        if return_breakdown:
            member_rates['ee_rate'] = rate
            eldest_age_band = _get_age_band(emp_age)
            return {**member_rates, 'total_rate': rate, 'eldest_age_band': eldest_age_band, 'rate_per_member': rate}
        return rate

    # Collect all family member ages to find the eldest
    all_ages = [emp_age]
    spouse_age = None
    child_ages = []

    # Get family members from dependents_df
    if dependents_df is not None and not dependents_df.empty:
        emp_deps = dependents_df[dependents_df['employee_id'] == emp_id]

        # Add spouse age (if ES or F)
        if family_status in ['ES', 'F']:
            spouse_rows = emp_deps[emp_deps['relationship'].str.lower() == 'spouse']
            if not spouse_rows.empty:
                spouse_age = int(spouse_rows.iloc[0]['age'])
                all_ages.append(spouse_age)
                member_rates['spouse_age'] = spouse_age

        # Add ALL children ages (if EC or F) - no 3-child cap for cooperative
        if family_status in ['EC', 'F']:
            child_rows = emp_deps[emp_deps['relationship'].str.lower() == 'child']
            for _, child in child_rows.iterrows():
                child_age = int(child['age'])
                all_ages.append(child_age)
                child_ages.append(child_age)

    # Find eldest age and use that age band for the GROUP RATE
    eldest_age = max(all_ages)
    eldest_age_band = _get_age_band(eldest_age)

    # GROUP PRICING: Single rate for the entire family based on eldest member's age band
    # The rate lookup uses (age_band, family_status) as key
    group_rate = lookup.get((eldest_age_band, family_status), 0)
    total_rate = group_rate  # Single rate, NOT multiplied by member count

    if return_breakdown:
        # Group pricing: only the employee rate applies (covers entire family)
        member_rates['ee_rate'] = group_rate

        # Store ages for reference but rates are None (group pricing)
        if spouse_age is not None:
            member_rates['spouse_rate'] = None  # Included in group rate

        # Store child ages for reference but rates are None (group pricing)
        for i, child_age in enumerate(child_ages[:5], start=1):
            member_rates[f'child_{i}_rate'] = None  # Included in group rate
            member_rates[f'child_{i}_age'] = child_age

        return {**member_rates, 'total_rate': total_rate, 'eldest_age_band': eldest_age_band, 'rate_per_member': group_rate}

    return total_rate


def calculate_hap_totals(census_df: pd.DataFrame, coop_rates_df: pd.DataFrame,
                         dependents_df: pd.DataFrame = None) -> Dict:
    """
    Calculate HAS totals for $1k and $2.5k deductible plans.

    Uses GROUP PRICING - single rate per family based on oldest member's age band.
    Unlike marketplace plans which charge per-member rates, HAS charges one family rate.

    Args:
        census_df: Employee census DataFrame with age and family_status columns
        coop_rates_df: DataFrame from load_cooperative_rate_table()
        dependents_df: DataFrame with dependent info for family rate calculations

    Returns:
        Dict with structure:
        {
            'hap_1k': {
                'total': float,  # Total monthly premium for all employees
                'by_tier': {
                    'EE': {'total': float, 'count': int},
                    'ES': {...}, 'EC': {...}, 'F': {...}
                },
                'rate_ranges': {
                    'EE': {'min': float, 'max': float},  # youngest to oldest age band rates
                    'ES': {...}, 'EC': {...}, 'F': {...}
                }
            },
            'hap_2_5k': {...}
        }
    """
    result = {
        'hap_1k': {
            'total': 0,
            'by_tier': {code: {'total': 0, 'count': 0} for code in ['EE', 'ES', 'EC', 'F']},
            'rate_ranges': {code: {'min': 0, 'max': 0} for code in ['EE', 'ES', 'EC', 'F']}
        },
        'hap_2_5k': {
            'total': 0,
            'by_tier': {code: {'total': 0, 'count': 0} for code in ['EE', 'ES', 'EC', 'F']},
            'rate_ranges': {code: {'min': 0, 'max': 0} for code in ['EE', 'ES', 'EC', 'F']}
        }
    }

    if census_df is None or census_df.empty:
        return result

    if coop_rates_df is None or coop_rates_df.empty:
        return result

    # Build lookup dicts for both deductible levels
    lookup_1k = build_cooperative_rate_lookup(coop_rates_df, "1k")
    lookup_2_5k = build_cooperative_rate_lookup(coop_rates_df, "2.5k")

    # Calculate rate ranges from the rate table itself (youngest to oldest age band)
    youngest_band = "18-29"
    oldest_band = "60-64"
    for family_status in ['EE', 'ES', 'EC', 'F']:
        # $1k deductible ranges
        min_rate_1k = lookup_1k.get((youngest_band, family_status), 0)
        max_rate_1k = lookup_1k.get((oldest_band, family_status), 0)
        result['hap_1k']['rate_ranges'][family_status] = {'min': min_rate_1k, 'max': max_rate_1k}

        # $2.5k deductible ranges
        min_rate_2_5k = lookup_2_5k.get((youngest_band, family_status), 0)
        max_rate_2_5k = lookup_2_5k.get((oldest_band, family_status), 0)
        result['hap_2_5k']['rate_ranges'][family_status] = {'min': min_rate_2_5k, 'max': max_rate_2_5k}

    # Determine column names
    family_col = 'family_status' if 'family_status' in census_df.columns else None
    if not family_col and 'Family Status' in census_df.columns:
        family_col = 'Family Status'
    age_col = 'age' if 'age' in census_df.columns else None

    if not family_col or not age_col:
        return result

    # Loop through each employee and accumulate totals
    for _, emp in census_df.iterrows():
        family_status = emp.get(family_col, 'EE')

        # Calculate aggregate family rate (summing all family members)
        # For EE, uses single rate; for ES/EC/F, sums employee + dependent rates
        rate_1k = calculate_cooperative_family_rate(emp, family_status, lookup_1k, dependents_df)
        rate_2_5k = calculate_cooperative_family_rate(emp, family_status, lookup_2_5k, dependents_df)

        # Accumulate totals
        result['hap_1k']['total'] += rate_1k
        result['hap_2_5k']['total'] += rate_2_5k

        # Accumulate by tier
        if family_status in result['hap_1k']['by_tier']:
            result['hap_1k']['by_tier'][family_status]['total'] += rate_1k
            result['hap_1k']['by_tier'][family_status]['count'] += 1
            result['hap_2_5k']['by_tier'][family_status]['total'] += rate_2_5k
            result['hap_2_5k']['by_tier'][family_status]['count'] += 1

    return result


# =============================================================================
# SEDERA RATE FUNCTIONS
# =============================================================================

# Plan Configurator Constants
SEDERA_IUA_OPTIONS = ['500', '1000', '1500', '2500', '5000']
HAS_IUA_OPTIONS = ['1k', '2.5k']
PREVENTIVE_CARE_RATE_WITH_DPC = 124.0
PREVENTIVE_CARE_RATE_WITHOUT_DPC = 107.0


@st.cache_data(show_spinner=False, ttl=3600)  # Cache for 1 hour
def load_sedera_rate_table(_db_available: bool = False) -> pd.DataFrame:
    """Load Sedera rates from sedera_rates_with_dpc table."""
    db = st.session_state.get('db')
    if db is None:
        return pd.DataFrame()

    query = """
    SELECT "Plan", "IUA", age_band, family_status, family_status_sedera, sedera_monthly_rate
    FROM sedera_rates_with_dpc
    ORDER BY "IUA", age_band, family_status
    """
    try:
        return pd.read_sql(query, db.engine)
    except Exception as e:
        print(f"Error loading Sedera rates: {e}")
        return pd.DataFrame()


def _get_sedera_age_band(age: int) -> str:
    """Convert age to Sedera rate age band."""
    if age < 30:
        return "18-29"
    elif age < 40:
        return "30-39"
    elif age < 50:
        return "40-49"
    elif age < 60:
        return "50-59"
    else:
        return "60+"


def build_sedera_rate_lookup(sedera_rates_df: pd.DataFrame, iua: str) -> Dict:
    """
    Build a lookup dictionary from Sedera rates DataFrame for O(1) access.

    Args:
        sedera_rates_df: DataFrame from load_sedera_rate_table()
        iua: IUA level as string ('500', '1000', '1500', '2500', '5000')

    Returns:
        Dict mapping (age_band, family_status) -> rate
    """
    if sedera_rates_df is None or sedera_rates_df.empty:
        return {}

    # Filter by IUA
    iua_df = sedera_rates_df[sedera_rates_df['IUA'] == iua]
    if iua_df.empty:
        return {}

    lookup = {}
    for _, row in iua_df.iterrows():
        key = (row['age_band'], row['family_status'])
        lookup[key] = float(row['sedera_monthly_rate']) if pd.notna(row['sedera_monthly_rate']) else 0
    return lookup


def get_sedera_rate_fast(age: int, family_status: str, lookup: Dict) -> float:
    """
    Fast O(1) lookup for Sedera rate using pre-built dictionary.

    Args:
        age: Employee age
        family_status: EE, ES, EC, or F
        lookup: Dictionary from build_sedera_rate_lookup()

    Returns:
        Monthly Sedera rate
    """
    if not lookup:
        return 0

    status_map = {"EE": "EE", "ES": "ES", "EC": "EC", "F": "F"}
    fs = status_map.get(family_status, "EE")
    age_band = _get_sedera_age_band(age)

    return lookup.get((age_band, fs), 0)


def calculate_sedera_family_rate(
    employee_row: pd.Series,
    family_status: str,
    lookup: Dict,
    dependents_df: pd.DataFrame = None,
    return_breakdown: bool = False
) -> Union[float, Dict]:
    """
    Calculate Sedera rate using GROUP PRICING - single rate based on oldest member's age band.

    IMPORTANT: Sedera uses GROUP PRICING, meaning the family pays ONE rate based on the
    eldest family member's age band. Unlike individual marketplace plans which charge
    per-member rates, Sedera charges a single family rate.

    Args:
        employee_row: Census row for the employee
        family_status: EE, ES, EC, or F
        lookup: Dictionary from build_sedera_rate_lookup()
        dependents_df: DataFrame with dependent info (employee_id, relationship, age)
        return_breakdown: If True, return dict with rate info

    Returns:
        If return_breakdown=False: Total monthly Sedera premium (float) - single rate for family
        If return_breakdown=True: Dict with structure:
            {
                'ee_rate': float, 'ee_age': int,
                'spouse_rate': None (not applicable for group pricing),
                'child_X_rate': None (not applicable for group pricing),
                'total_rate': float (same as ee_rate for group pricing),
                'eldest_age_band': str,
                'rate_per_member': float (the single group rate)
            }
    """
    # Initialize breakdown structure
    member_rates = {
        'ee_rate': 0.0,
        'ee_age': None,
        'spouse_rate': None,
        'spouse_age': None,
    }
    for i in range(1, 6):
        member_rates[f'child_{i}_rate'] = None
        member_rates[f'child_{i}_age'] = None

    if not lookup:
        if return_breakdown:
            return {**member_rates, 'total_rate': 0.0, 'eldest_age_band': None, 'rate_per_member': 0.0}
        return 0.0

    emp_id = employee_row.get('employee_id', '')
    emp_age = int(employee_row.get('age', 0))
    member_rates['ee_age'] = emp_age

    # For Employee Only, just get the EE rate using employee's age
    if family_status == 'EE':
        rate = get_sedera_rate_fast(emp_age, family_status, lookup)
        if return_breakdown:
            member_rates['ee_rate'] = rate
            eldest_age_band = _get_sedera_age_band(emp_age)
            return {**member_rates, 'total_rate': rate, 'eldest_age_band': eldest_age_band, 'rate_per_member': rate}
        return rate

    # Collect all family member ages to find the eldest
    all_ages = [emp_age]
    spouse_age = None
    child_ages = []

    # Get family members from dependents_df
    if dependents_df is not None and not dependents_df.empty:
        emp_deps = dependents_df[dependents_df['employee_id'] == emp_id]

        # Add spouse age (if ES or F)
        if family_status in ['ES', 'F']:
            spouse_rows = emp_deps[emp_deps['relationship'].str.lower() == 'spouse']
            if not spouse_rows.empty:
                spouse_age = int(spouse_rows.iloc[0]['age'])
                all_ages.append(spouse_age)
                member_rates['spouse_age'] = spouse_age

        # Add ALL children ages (if EC or F) - no 3-child cap for Sedera
        if family_status in ['EC', 'F']:
            child_rows = emp_deps[emp_deps['relationship'].str.lower() == 'child']
            for _, child in child_rows.iterrows():
                child_age = int(child['age'])
                all_ages.append(child_age)
                child_ages.append(child_age)

    # Find eldest age and use that age band for the GROUP RATE
    eldest_age = max(all_ages)
    eldest_age_band = _get_sedera_age_band(eldest_age)

    # GROUP PRICING: Single rate for the entire family based on eldest member's age band
    # The rate lookup uses (age_band, family_status) as key
    group_rate = lookup.get((eldest_age_band, family_status), 0)
    total_rate = group_rate  # Single rate, NOT multiplied by member count

    if return_breakdown:
        # Group pricing: only the employee rate applies (covers entire family)
        member_rates['ee_rate'] = group_rate

        # Store ages for reference but rates are None (group pricing)
        if spouse_age is not None:
            member_rates['spouse_rate'] = None  # Included in group rate

        # Store child ages for reference but rates are None (group pricing)
        for i, child_age in enumerate(child_ages[:5], start=1):
            member_rates[f'child_{i}_rate'] = None  # Included in group rate
            member_rates[f'child_{i}_age'] = child_age

        return {**member_rates, 'total_rate': total_rate, 'eldest_age_band': eldest_age_band, 'rate_per_member': group_rate}

    return total_rate


def calculate_sedera_totals(census_df: pd.DataFrame, sedera_rates_df: pd.DataFrame,
                            selected_iuas: set, dependents_df: pd.DataFrame = None) -> Dict:
    """
    Calculate Sedera totals for selected IUA levels.

    Uses GROUP PRICING - single rate per family based on oldest member's age band.
    Dependents are needed only to determine the eldest family member's age.

    Args:
        census_df: Employee census DataFrame with age and family_status columns
        sedera_rates_df: DataFrame from load_sedera_rate_table()
        selected_iuas: Set of selected IUA levels (e.g., {'500', '1000'})
        dependents_df: DataFrame with dependent info for family rate calculations

    Returns:
        Dict with structure per IUA:
        {
            'sedera_500': {
                'total': float,
                'by_tier': {
                    'EE': {'total': float, 'count': int},
                    ...
                },
                'rate_ranges': {
                    'EE': {'min': float, 'max': float},
                    ...
                }
            },
            ...
        }
    """
    result = {}

    if census_df is None or census_df.empty:
        return result

    if sedera_rates_df is None or sedera_rates_df.empty:
        return result

    # Sedera age bands for rate ranges
    youngest_band = "18-29"
    oldest_band = "60+"

    # Determine column names
    family_col = 'family_status' if 'family_status' in census_df.columns else None
    if not family_col and 'Family Status' in census_df.columns:
        family_col = 'Family Status'
    age_col = 'age' if 'age' in census_df.columns else None

    if not family_col or not age_col:
        return result

    for iua in selected_iuas:
        key = f'sedera_{iua}'
        result[key] = {
            'total': 0,
            'by_tier': {code: {'total': 0, 'count': 0} for code in ['EE', 'ES', 'EC', 'F']},
            'rate_ranges': {code: {'min': 0, 'max': 0} for code in ['EE', 'ES', 'EC', 'F']}
        }

        # Build lookup for this IUA
        lookup = build_sedera_rate_lookup(sedera_rates_df, iua)
        if not lookup:
            continue

        # Calculate rate ranges
        for family_status in ['EE', 'ES', 'EC', 'F']:
            min_rate = lookup.get((youngest_band, family_status), 0)
            max_rate = lookup.get((oldest_band, family_status), 0)
            result[key]['rate_ranges'][family_status] = {'min': min_rate, 'max': max_rate}

        # Loop through each employee and accumulate totals
        for _, emp in census_df.iterrows():
            family_status = emp.get(family_col, 'EE')

            # Calculate aggregate family rate (summing all family members)
            # For EE, uses single rate; for ES/EC/F, sums employee + dependent rates
            rate = calculate_sedera_family_rate(emp, family_status, lookup, dependents_df)

            # Accumulate totals
            result[key]['total'] += rate

            # Accumulate by tier
            if family_status in result[key]['by_tier']:
                result[key]['by_tier'][family_status]['total'] += rate
                result[key]['by_tier'][family_status]['count'] += 1

    return result


def calculate_admin_fee_total(admin_fee_pepm: float, employee_count: int) -> float:
    """Calculate total admin fee: PEPM × employee count."""
    return admin_fee_pepm * employee_count


def calculate_preventive_care_total(include_dpc: bool, employee_count: int) -> float:
    """
    Calculate preventive care add-on: rate × employee count.
    Rate: $124/mo with DPC, $107/mo without DPC.
    """
    rate = PREVENTIVE_CARE_RATE_WITH_DPC if include_dpc else PREVENTIVE_CARE_RATE_WITHOUT_DPC
    return rate * employee_count


def calculate_age_bracket_costs(census_df: pd.DataFrame, multi_metal_results: Dict = None,
                                 cooperative_ratio: float = None,
                                 coop_rates_df: pd.DataFrame = None) -> Dict[str, Dict[str, float]]:
    """
    Calculate average costs by age bracket using individual ee_rate (not tier premium).

    Age brackets: 18-29, 30-39, 40-49, 50-59, 60-64, 65+

    For each bracket, calculates average of individual rates for employees in that bracket.
    This shows true age-based cost differences without family status multipliers.

    Args:
        census_df: Employee census DataFrame
        multi_metal_results: Results from calculate_multi_metal_scenario()
        cooperative_ratio: Cooperative cost as fraction of Silver
        coop_rates_df: Cooperative rate table DataFrame

    Returns:
        Dict with age bracket keys and scenario cost values
    """
    if cooperative_ratio is None:
        cooperative_ratio = COOPERATIVE_CONFIG['default_discount_ratio']

    # Define age brackets
    age_brackets = [
        ("18-29", 18, 29),
        ("30-39", 30, 39),
        ("40-49", 40, 49),
        ("50-59", 50, 59),
        ("60-64", 60, 64),
        ("65+", 65, 999),
    ]

    # Initialize results
    bracket_costs = {}
    for bracket_name, _, _ in age_brackets:
        bracket_costs[bracket_name] = {
            'count': 0,
            f'Current {CURRENT_PLAN_YEAR}': 0,
            f'Renewal {RENEWAL_PLAN_YEAR}': 0,
            'ICHRA Bronze': 0,
            'ICHRA Silver': 0,
            'ICHRA Gold': 0,
            'Cooperative': 0,
        }

    if census_df is None or census_df.empty:
        return bracket_costs

    # Build employee lookup from multi_metal_results (using ee_rate, not tier_premium)
    emp_metal_rates = {}  # emp_id -> {Bronze: rate, Silver: rate, Gold: rate}
    if multi_metal_results:
        for metal in ['Bronze', 'Silver', 'Gold']:
            metal_data = multi_metal_results.get(metal, {})
            for emp_detail in metal_data.get('employee_details', []):
                emp_id = emp_detail.get('employee_id')
                if emp_id not in emp_metal_rates:
                    emp_metal_rates[emp_id] = {}
                # Use ee_rate (individual rate) not estimated_tier_premium
                emp_metal_rates[emp_id][metal] = emp_detail.get('lcp_ee_rate', 0) or 0

    # Collect costs per bracket
    bracket_data = {b[0]: {'current': [], 'renewal': [], 'bronze': [], 'silver': [], 'gold': [], 'coop': [], 'ages': []}
                    for b in age_brackets}

    age_col = 'age' if 'age' in census_df.columns else None
    if not age_col:
        return bracket_costs

    for _, row in census_df.iterrows():
        age = int(row.get(age_col, 0))
        emp_id = row.get('employee_id', '')
        family_status = row.get('family_status', 'EE')

        # Find which bracket this employee belongs to
        bracket_name = None
        for name, min_age, max_age in age_brackets:
            if min_age <= age <= max_age:
                bracket_name = name
                break

        if not bracket_name:
            continue

        # Current costs (total premium for reference)
        current_er = row.get('current_er_monthly', 0)
        current_er = 0 if pd.isna(current_er) else (current_er or 0)
        current_ee = row.get('current_ee_monthly', 0)
        current_ee = 0 if pd.isna(current_ee) else (current_ee or 0)
        current_total = current_er + current_ee
        if current_total > 0:
            bracket_data[bracket_name]['current'].append(current_total)

        # Renewal (projected 2026 premium)
        # Try to get from multi_metal_results first
        projected_2026 = 0
        if emp_id in emp_metal_rates and multi_metal_results:
            # Look up projected_2026_premium from any metal's employee_details
            for metal in ['Silver', 'Bronze', 'Gold']:
                metal_data = multi_metal_results.get(metal, {})
                for emp_detail in metal_data.get('employee_details', []):
                    if emp_detail.get('employee_id') == emp_id:
                        projected_2026 = emp_detail.get('projected_2026_premium', 0) or 0
                        break
                if projected_2026 > 0:
                    break

        if projected_2026 > 0:
            bracket_data[bracket_name]['renewal'].append(projected_2026)

        # ICHRA rates (individual ee_rate)
        if emp_id in emp_metal_rates:
            rates = emp_metal_rates[emp_id]
            if rates.get('Bronze', 0) > 0:
                bracket_data[bracket_name]['bronze'].append(rates['Bronze'])
            if rates.get('Silver', 0) > 0:
                bracket_data[bracket_name]['silver'].append(rates['Silver'])
            if rates.get('Gold', 0) > 0:
                bracket_data[bracket_name]['gold'].append(rates['Gold'])

            # Cooperative - use rate table with actual family status, otherwise ratio of silver
            silver_rate = rates.get('Silver', 0)
            if coop_rates_df is not None and not coop_rates_df.empty:
                # Get rate from cooperative table using actual family status
                coop_rate = get_cooperative_rate(age, family_status, coop_rates_df)
                if coop_rate > 0:
                    bracket_data[bracket_name]['coop'].append(coop_rate)
                elif silver_rate > 0:
                    bracket_data[bracket_name]['coop'].append(silver_rate * cooperative_ratio)
            elif silver_rate > 0:
                bracket_data[bracket_name]['coop'].append(silver_rate * cooperative_ratio)

        bracket_data[bracket_name]['ages'].append(age)

    # Calculate averages for each bracket (for row display) and sums (for totals)
    for bracket_name, data in bracket_data.items():
        count = len(data['ages'])
        bracket_costs[bracket_name]['count'] = count

        if count > 0:
            if data['current']:
                bracket_costs[bracket_name][f'Current {CURRENT_PLAN_YEAR}'] = round(sum(data['current']) / len(data['current']), 0)
                bracket_costs[bracket_name][f'Current {CURRENT_PLAN_YEAR}_sum'] = sum(data['current'])
            if data['renewal']:
                bracket_costs[bracket_name][f'Renewal {RENEWAL_PLAN_YEAR}'] = round(sum(data['renewal']) / len(data['renewal']), 0)
                bracket_costs[bracket_name][f'Renewal {RENEWAL_PLAN_YEAR}_sum'] = sum(data['renewal'])
            if data['bronze']:
                bracket_costs[bracket_name]['ICHRA Bronze'] = round(sum(data['bronze']) / len(data['bronze']), 0)
                bracket_costs[bracket_name]['ICHRA Bronze_sum'] = sum(data['bronze'])
            if data['silver']:
                bracket_costs[bracket_name]['ICHRA Silver'] = round(sum(data['silver']) / len(data['silver']), 0)
                bracket_costs[bracket_name]['ICHRA Silver_sum'] = sum(data['silver'])
            if data['gold']:
                bracket_costs[bracket_name]['ICHRA Gold'] = round(sum(data['gold']) / len(data['gold']), 0)
                bracket_costs[bracket_name]['ICHRA Gold_sum'] = sum(data['gold'])
            if data['coop']:
                bracket_costs[bracket_name]['Cooperative'] = round(sum(data['coop']) / len(data['coop']), 0)
                bracket_costs[bracket_name]['Cooperative_sum'] = sum(data['coop'])

    return bracket_costs


def calculate_tier_marketplace_costs(
    census_df: pd.DataFrame,
    multi_metal_results: Dict = None,
    db: 'DatabaseConnection' = None,
    dependents_df: pd.DataFrame = None
) -> Dict:
    """
    Calculate marketplace costs grouped by family status tier.

    Shows rate ranges (youngest to oldest age band) and totals for each tier.
    Uses aggregate family premiums (summed rates for employee + dependents)
    with ACA 3-child rule for ES/EC/F tiers.

    Args:
        census_df: Employee census DataFrame
        multi_metal_results: Results from calculate_multi_metal_scenario()
        db: Database connection for plan counts and rate lookups
        dependents_df: DataFrame with dependent info for family rate calculations

    Returns:
        Dict with structure:
        {
            'plan_counts': {'Bronze': 45, 'Silver': 38, 'Gold': 22},
            'tiers': {
                'Employee Only': {
                    'code': 'EE',
                    'count': 23,
                    'Bronze': {'min': 303, 'max': 565, 'total': 6969},
                    'Silver': {...},
                    'Gold': {...},
                },
                ...
            },
            'totals': {
                'Bronze': {'monthly': X, 'annual': X*12},
                'Silver': {...},
                'Gold': {...},
            }
        }
    """
    # Initialize result structure
    tier_info = {
        'Employee Only': 'EE',
        'Employee + Spouse': 'ES',
        'Employee + Children': 'EC',
        'Family': 'F',
    }

    result = {
        'plan_counts': {'Bronze': 0, 'Silver': 0, 'Gold': 0},
        'tiers': {},
        'totals': {
            'Bronze': {'monthly': 0, 'annual': 0},
            'Silver': {'monthly': 0, 'annual': 0},
            'Gold': {'monthly': 0, 'annual': 0},
        }
    }

    # Get plan counts from database - filtered to census rating areas
    if db and census_df is not None and not census_df.empty:
        try:
            from queries import PlanQueries
            # Extract unique (state_code, rating_area_id) tuples from census
            state_col = 'Home State' if 'Home State' in census_df.columns else 'state'
            # Check for both possible rating area column names
            if 'rating_area_id' in census_df.columns:
                ra_col = 'rating_area_id'
            elif 'rating_area' in census_df.columns:
                ra_col = 'rating_area'
            else:
                ra_col = None

            if ra_col and state_col in census_df.columns:
                # Get unique state/rating area combinations
                state_ra_pairs = census_df[[state_col, ra_col]].dropna().drop_duplicates()

                def parse_rating_area(val):
                    """Parse rating area from various formats: int, 'Rating Area 7', '7', etc."""
                    if val is None or pd.isna(val):
                        return None
                    if isinstance(val, (int, float)):
                        return int(val)
                    if isinstance(val, str):
                        if val.startswith('Rating Area '):
                            return int(val.replace('Rating Area ', ''))
                        return int(val)
                    return None

                state_rating_areas = [
                    (row[state_col], ra_int)
                    for _, row in state_ra_pairs.iterrows()
                    if (ra_int := parse_rating_area(row[ra_col])) is not None
                ]
                if state_rating_areas:
                    result['plan_counts'] = PlanQueries.get_plan_counts_by_metal_for_census(db, state_rating_areas)
        except Exception:
            pass  # Keep default zeros

    if census_df is None or census_df.empty or not multi_metal_results:
        return result

    # Build employee lookup from multi_metal_results
    # emp_id -> {metal -> {plan_id, rating_area, lcp_ee_rate, family_status}}
    emp_metal_info = {}
    for metal in ['Bronze', 'Silver', 'Gold']:
        metal_data = multi_metal_results.get(metal, {})
        for emp_detail in metal_data.get('employee_details', []):
            emp_id = emp_detail.get('employee_id')
            if emp_id not in emp_metal_info:
                emp_metal_info[emp_id] = {'Bronze': {}, 'Silver': {}, 'Gold': {}}
            emp_metal_info[emp_id][metal] = {
                'plan_id': emp_detail.get('lcp_plan_id'),
                'rating_area': emp_detail.get('rating_area'),
                'lcp_ee_rate': emp_detail.get('lcp_ee_rate', 0) or 0,
                'family_status': emp_detail.get('family_status', 'EE')
            }

    # Create census lookup by employee_id for aggregate family premium calculation
    census_by_id = census_df.set_index('employee_id') if 'employee_id' in census_df.columns else census_df

    # Process each tier
    for tier_name, tier_code in tier_info.items():
        tier_employees = census_df[census_df['family_status'] == tier_code]
        count = len(tier_employees)

        if count == 0:
            continue

        # Calculate average age for this tier
        avg_age = 0
        if 'age' in tier_employees.columns and count > 0:
            avg_age = round(tier_employees['age'].mean())

        tier_data = {
            'code': tier_code,
            'count': count,
            'avg_age': avg_age,
            'Bronze': {'min': 0, 'max': 0, 'total': 0, 'rates': []},
            'Silver': {'min': 0, 'max': 0, 'total': 0, 'rates': []},
            'Gold': {'min': 0, 'max': 0, 'total': 0, 'rates': []},
        }

        # Collect rates for each employee in this tier
        for _, row in tier_employees.iterrows():
            emp_id = row.get('employee_id', '')
            age = int(row.get('age', 0))

            if emp_id in emp_metal_info:
                for metal in ['Bronze', 'Silver', 'Gold']:
                    metal_info = emp_metal_info[emp_id].get(metal, {})
                    plan_id = metal_info.get('plan_id')
                    rating_area = metal_info.get('rating_area')
                    lcp_ee_rate = metal_info.get('lcp_ee_rate', 0)

                    # For EE, use lcp_ee_rate directly. For ES/EC/F, calculate aggregate family premium
                    if tier_code == 'EE':
                        rate = lcp_ee_rate
                    elif plan_id and rating_area and db:
                        # Parse rating_area to int if it's a string like "Rating Area 7"
                        ra_int = rating_area
                        if isinstance(rating_area, str):
                            if rating_area.startswith('Rating Area '):
                                ra_int = int(rating_area.replace('Rating Area ', ''))
                            else:
                                try:
                                    ra_int = int(rating_area)
                                except ValueError:
                                    ra_int = 1

                        # Calculate aggregate family premium with ACA 3-child rule
                        rate = calculate_aggregate_family_premium(
                            employee_row=row,
                            plan_id=plan_id,
                            rating_area=ra_int,
                            db=db,
                            dependents_df=dependents_df
                        )
                        # Fallback to lcp_ee_rate if aggregate returns 0
                        if rate <= 0:
                            rate = lcp_ee_rate
                    else:
                        rate = lcp_ee_rate

                    if rate > 0:
                        tier_data[metal]['rates'].append({'rate': rate, 'age': age})

        # Calculate min, max, total for each metal
        for metal in ['Bronze', 'Silver', 'Gold']:
            rates_list = tier_data[metal]['rates']
            if rates_list:
                # Sort by age to get youngest and oldest rates
                sorted_rates = sorted(rates_list, key=lambda x: x['age'])
                tier_data[metal]['min'] = sorted_rates[0]['rate']  # Youngest employee's rate
                tier_data[metal]['max'] = sorted_rates[-1]['rate']  # Oldest employee's rate
                tier_data[metal]['total'] = sum(r['rate'] for r in rates_list)

                # Add to overall totals
                result['totals'][metal]['monthly'] += tier_data[metal]['total']

            # Clean up - don't need rates list in output
            del tier_data[metal]['rates']

        result['tiers'][tier_name] = tier_data

    # Calculate annual totals
    for metal in ['Bronze', 'Silver', 'Gold']:
        result['totals'][metal]['annual'] = result['totals'][metal]['monthly'] * 12

    return result


def calculate_company_totals(census_df: pd.DataFrame, contribution_analysis: Dict = None,
                              tier_costs: Dict = None, multi_metal_results: Dict = None,
                              contribution_pct: float = 0.65,
                              renewal_monthly: float = None,
                              cooperative_ratio: float = None,
                              coop_rates_df: pd.DataFrame = None,
                              dependents_df: pd.DataFrame = None) -> Dict[str, float]:
    """
    Calculate company-wide totals for each scenario.

    Uses actual Bronze/Silver/Gold data from multi_metal_results when available,
    and applies the configured contribution percentage from Page 2.
    Cooperative rates use aggregate family premiums (sums rates for employee + all dependents).

    Args:
        census_df: Employee census DataFrame
        contribution_analysis: Per-employee ICHRA analysis (optional)
        tier_costs: Pre-calculated tier costs (optional)
        multi_metal_results: Results from calculate_multi_metal_scenario() with actual rates
        contribution_pct: Employer contribution percentage (default 0.65 = 65%)
        renewal_monthly: Actual renewal amount from Page 3 (optional)
        cooperative_ratio: Cooperative cost as fraction of Silver (from dashboard_config)
        dependents_df: DataFrame with dependent info for family rate calculations
    """
    # Use provided cooperative_ratio or fall back to constant
    if cooperative_ratio is None:
        cooperative_ratio = COOPERATIVE_CONFIG['default_discount_ratio']

    totals = {
        f"Current {CURRENT_PLAN_YEAR}": 0,
        f"Renewal {RENEWAL_PLAN_YEAR}": 0,
        "ICHRA Bronze": 0,
        "ICHRA Silver": 0,
        "ICHRA Gold": 0,
        "Cooperative": 0,
    }

    if census_df is None or census_df.empty:
        return totals

    # Sum current costs from census - EMPLOYER PORTION ONLY for fair comparison
    current_er_total = 0
    current_total = 0  # Total premium (ER + EE) for calculating ER ratio
    if 'current_er_monthly' in census_df.columns:
        current_er_total = census_df['current_er_monthly'].fillna(0).sum()
        current_er_total = current_er_total if pd.notna(current_er_total) else 0
    if 'current_ee_monthly' in census_df.columns:
        ee_sum = census_df['current_ee_monthly'].fillna(0).sum()
        current_total = current_er_total + (ee_sum if pd.notna(ee_sum) else 0)
    else:
        current_total = current_er_total
    totals[f'Current {CURRENT_PLAN_YEAR}'] = current_er_total  # ER only

    # Renewal costs - EMPLOYER PORTION (apply same ER ratio as current plan)
    if renewal_monthly and renewal_monthly > 0:
        if current_total > 0:
            er_ratio = current_er_total / current_total
        else:
            er_ratio = contribution_pct  # Fallback to ICHRA contribution %
        totals[f'Renewal {RENEWAL_PLAN_YEAR}'] = renewal_monthly * er_ratio

    # ICHRA costs - use actual data from multi_metal_results if available
    if multi_metal_results:
        for metal in ['Bronze', 'Silver', 'Gold']:
            metal_data = multi_metal_results.get(metal, {})
            total_monthly = metal_data.get('total_monthly', 0)
            # Apply contribution percentage (what employer pays)
            totals[f'ICHRA {metal}'] = total_monthly * contribution_pct

        # Cooperative - use rate table if available, otherwise ratio of silver
        if coop_rates_df is not None and not coop_rates_df.empty:
            # Sum cooperative rates from rate table for each employee
            # Uses aggregate family rates (sums employee + dependent rates, no 3-child cap)
            coop_lookup = build_cooperative_rate_lookup(coop_rates_df)
            coop_total = 0
            family_col = 'family_status' if 'family_status' in census_df.columns else None
            if family_col:
                for _, emp_row in census_df.iterrows():
                    emp_fs = emp_row.get(family_col, 'EE')
                    coop_rate = calculate_cooperative_family_rate(emp_row, emp_fs, coop_lookup, dependents_df)
                    if coop_rate > 0:
                        coop_total += coop_rate
            if coop_total > 0:
                totals['Cooperative'] = coop_total
            else:
                # Fallback to ratio if no rates found
                silver_total = multi_metal_results.get('Silver', {}).get('total_monthly', 0)
                totals['Cooperative'] = silver_total * cooperative_ratio
        else:
            # Fallback to ratio if no rate table
            silver_total = multi_metal_results.get('Silver', {}).get('total_monthly', 0)
            totals['Cooperative'] = silver_total * cooperative_ratio

    elif contribution_analysis:
        # Fallback to contribution_analysis if multi_metal not available
        for emp_id, analysis in contribution_analysis.items():
            ichra_data = analysis.get('ichra_analysis', {})
            lcsp = ichra_data.get('monthly_premium', 0)
            if lcsp > 0:
                # Apply contribution percentage with metal ratios from constants
                totals['ICHRA Bronze'] += lcsp * contribution_pct * METAL_COST_RATIOS['Bronze']
                totals['ICHRA Silver'] += lcsp * contribution_pct * METAL_COST_RATIOS['Silver']
                totals['ICHRA Gold'] += lcsp * contribution_pct * METAL_COST_RATIOS['Gold']
                totals['Cooperative'] += lcsp * contribution_pct * cooperative_ratio

    # Round all totals
    for key in totals:
        totals[key] = round(totals[key], 0)

    return totals


def get_age_band(age: int) -> str:
    """Convert age to RBIS age band format."""
    if age <= 14:
        return "0-14"
    elif age >= 64:
        return "64 and over"
    else:
        return str(age)


def calculate_aggregate_family_premium(
    employee_row: pd.Series,
    plan_id: str,
    rating_area: int,
    db,
    dependents_df: pd.DataFrame = None,
    return_breakdown: bool = False
):
    """
    Calculate actual aggregate family premium by summing individual rates.

    Applies ACA 3-child rule: only 3 oldest children under 21 are rated.
    Children 21+ are rated individually (not subject to 3-child rule).

    Args:
        employee_row: Census row for the employee
        plan_id: HIOS plan ID to look up rates for
        rating_area: Rating area ID (integer)
        db: Database connection
        dependents_df: DataFrame with dependent info (employee_id, relationship, age)
        return_breakdown: If True, return dict with individual member rates

    Returns:
        If return_breakdown=False: Total monthly premium (float)
        If return_breakdown=True: Dict with ee_rate, spouse_rate, child_1_rate..child_5_rate, total_rate
    """
    # Initialize breakdown structure
    member_rates = {
        'ee_rate': 0.0,
        'ee_age': None,
        'spouse_rate': None,
        'spouse_age': None,
    }
    for i in range(1, 6):
        member_rates[f'child_{i}_rate'] = None
        member_rates[f'child_{i}_age'] = None

    if db is None or not plan_id:
        if return_breakdown:
            return {**member_rates, 'total_rate': 0.0, 'rated_count': 0, 'is_family_tier': False}
        return 0.0

    emp_id = employee_row.get('employee_id', '')
    emp_age = int(employee_row.get('age', 0))
    family_status = employee_row.get('family_status', 'EE')
    state_code = plan_id[5:7] if len(plan_id) >= 7 else ''

    member_rates['ee_age'] = emp_age

    # For Employee Only, just get the EE rate
    if family_status == 'EE':
        ee_rate = get_single_rate(plan_id, rating_area, emp_age, db, state_code)
        member_rates['ee_rate'] = ee_rate
        if return_breakdown:
            return {**member_rates, 'total_rate': ee_rate, 'rated_count': 1, 'is_family_tier': False}
        return ee_rate

    # Build list of (member_type, age) for all rated members
    rated_members = [('EE', emp_age)]

    # Get family members from dependents_df
    if dependents_df is not None and not dependents_df.empty:
        emp_deps = dependents_df[dependents_df['employee_id'] == emp_id]

        # Collect spouse
        if family_status in ['ES', 'F']:
            spouse_rows = emp_deps[emp_deps['relationship'].str.lower() == 'spouse']
            if not spouse_rows.empty:
                spouse_age = int(spouse_rows.iloc[0]['age'])
                rated_members.append(('SP', spouse_age))
                member_rates['spouse_age'] = spouse_age

        # Collect children
        if family_status in ['EC', 'F']:
            child_rows = emp_deps[emp_deps['relationship'].str.lower() == 'child']
            children = []
            for _, child in child_rows.iterrows():
                child_age = int(child['age'])
                children.append(child_age)

            # ACA 3-child rule: only rate 3 oldest children under 21
            children_under_21 = [a for a in children if a < 21]
            children_21_plus = [a for a in children if a >= 21]

            # Sort under-21 by age descending, take top 3
            children_under_21_sorted = sorted(children_under_21, reverse=True)[:3]

            # Add rated children (track which ones are rated)
            child_idx = 0
            for age in children_under_21_sorted:
                rated_members.append(('CH', age))
                child_idx += 1
                if child_idx <= 5:
                    member_rates[f'child_{child_idx}_age'] = age
            for age in children_21_plus:
                rated_members.append(('CH', age))
                child_idx += 1
                if child_idx <= 5:
                    member_rates[f'child_{child_idx}_age'] = age

    # Handle NY/VT family-tier states
    from constants import FAMILY_TIER_STATES
    if state_code in FAMILY_TIER_STATES:
        total = get_family_tier_premium(plan_id, rating_area, family_status, db)
        if return_breakdown:
            # For family-tier states, we can't break down individual rates
            member_rates['ee_rate'] = total  # Put total in EE for display purposes
            return {**member_rates, 'total_rate': total, 'rated_count': len(rated_members),
                    'is_family_tier': True, 'family_tier_note': 'NY/VT family-tier rates apply'}
        return total

    # Sum up rates for all rated members, tracking individual rates
    total_premium = 0.0
    child_idx = 0
    for member_type, age in rated_members:
        rate = get_single_rate(plan_id, rating_area, age, db, state_code)
        total_premium += rate

        if member_type == 'EE':
            member_rates['ee_rate'] = rate
        elif member_type == 'SP':
            member_rates['spouse_rate'] = rate
        elif member_type == 'CH':
            child_idx += 1
            if child_idx <= 5:
                member_rates[f'child_{child_idx}_rate'] = rate

    if return_breakdown:
        return {**member_rates, 'total_rate': total_premium, 'rated_count': len(rated_members),
                'is_family_tier': False}
    return total_premium


def get_single_rate(plan_id: str, rating_area: int, age: int, db, state_code: str = '') -> float:
    """Get individual rate for a single person."""
    if db is None:
        return 0.0

    from constants import FAMILY_TIER_STATES

    # Handle NY/VT - they use family-tier rates
    if state_code in FAMILY_TIER_STATES:
        age_band = 'Family-Tier Rates'
    else:
        age_band = get_age_band(age)

    rating_area_str = f"Rating Area {rating_area}"

    query = """
    SELECT individual_rate
    FROM rbis_insurance_plan_base_rates_20251019202724
    WHERE plan_id = %s
      AND rating_area_id = %s
      AND age = %s
      AND market_coverage = 'Individual'
    LIMIT 1
    """

    try:
        result = pd.read_sql(query, db.engine, params=(plan_id, rating_area_str, age_band))
        if not result.empty:
            return float(result.iloc[0]['individual_rate'])
    except Exception as e:
        pass

    return 0.0


def get_family_tier_premium(plan_id: str, rating_area: int, family_status: str, db) -> float:
    """Get premium for NY/VT family-tier states using tier multipliers."""
    base_rate = get_single_rate(plan_id, rating_area, 21, db, plan_id[5:7] if len(plan_id) >= 7 else '')

    tier_multipliers = {
        'EE': 1.0,
        'ES': 2.0,
        'EC': 1.7,
        'F': 2.85
    }

    return base_rate * tier_multipliers.get(family_status, 1.0)


def select_employee_examples(census_df: pd.DataFrame, contribution_analysis: Dict = None,
                              tier_costs: Dict = None, multi_metal_results: Dict = None,
                              contribution_pct: float = 0.65,
                              cooperative_ratio: float = None,
                              dependents_df: pd.DataFrame = None,
                              db=None,
                              coop_rates_df: pd.DataFrame = None,
                              flat_amounts: Dict = None,
                              sedera_rates_df: pd.DataFrame = None,
                              plan_config: Dict = None,
                              contribution_settings: Dict = None) -> List[Dict]:
    """Select 3 representative employees: youngest, mid-age family, oldest."""
    examples = []

    if census_df is None or census_df.empty or 'age' not in census_df.columns:
        return examples

    # Get exclude_dependent_ichra setting (default False = include dependents in ER contribution)
    # When True, ER only covers employee rate; dependents fall to employee
    exclude_deps = False
    if contribution_settings:
        exclude_deps = contribution_settings.get('exclude_dependent_ichra', False)

    # Sort by age to find youngest/oldest
    sorted_df = census_df.sort_values('age')

    # Youngest Employee Only (EE status only)
    # For EE-only employees, use_ee_rate_only is always True (no dependents)
    ee_only = sorted_df[sorted_df['family_status'] == 'EE']
    if not ee_only.empty:
        youngest = ee_only.iloc[0]
        examples.append(build_employee_example(
            youngest, "Youngest Employee", contribution_analysis, tier_costs,
            multi_metal_results, contribution_pct, cooperative_ratio, dependents_df, db,
            use_ee_rate_only=True,  # EE-only always uses individual rate
            coop_rates_df=coop_rates_df,
            flat_amounts=flat_amounts,
            sedera_rates_df=sedera_rates_df,
            plan_config=plan_config,
            contribution_settings=contribution_settings
        ))

    # Mid-age family (Family status preferred)
    # For families, use_ee_rate_only depends on exclude_deps toggle
    families = sorted_df[sorted_df['family_status'] == 'F']
    if not families.empty:
        mid_idx = len(families) // 2
        mid_family = families.iloc[mid_idx]
        examples.append(build_employee_example(
            mid_family, "Mid-Age Family", contribution_analysis, tier_costs,
            multi_metal_results, contribution_pct, cooperative_ratio, dependents_df, db,
            use_ee_rate_only=exclude_deps,  # When True, ER only covers employee rate
            coop_rates_df=coop_rates_df,
            flat_amounts=flat_amounts,
            sedera_rates_df=sedera_rates_df,
            plan_config=plan_config,
            contribution_settings=contribution_settings
        ))

    # Oldest
    oldest = sorted_df.iloc[-1]
    # For oldest, also respect the exclude_deps toggle if they have family
    oldest_family_status = oldest.get('family_status', 'EE')
    use_ee_only_for_oldest = oldest_family_status == 'EE' or exclude_deps
    examples.append(build_employee_example(
        oldest, "Oldest Employee", contribution_analysis, tier_costs,
        multi_metal_results, contribution_pct, cooperative_ratio, dependents_df, db,
        use_ee_rate_only=use_ee_only_for_oldest,
        coop_rates_df=coop_rates_df,
        flat_amounts=flat_amounts,
        sedera_rates_df=sedera_rates_df,
        plan_config=plan_config,
        contribution_settings=contribution_settings
    ))

    return examples


def build_employee_example(employee_row: pd.Series, label: str,
                           contribution_analysis: Dict = None, tier_costs: Dict = None,
                           multi_metal_results: Dict = None, contribution_pct: float = 0.65,
                           cooperative_ratio: float = None,
                           dependents_df: pd.DataFrame = None,
                           db=None,
                           use_ee_rate_only: bool = False,
                           coop_rates_df: pd.DataFrame = None,
                           flat_amounts: Dict = None,
                           sedera_rates_df: pd.DataFrame = None,
                           plan_config: Dict = None,
                           contribution_settings: Dict = None) -> Dict:
    """Build employee example dict from census row.

    Args:
        use_ee_rate_only: If True, use individual ee_rate instead of estimated_tier_premium
                          (ignores family status multiplier). Used for youngest employee.
        flat_amounts: Optional dict of flat employer contribution amounts by tier
                      {'EE': 200, 'ES': 400, 'EC': 350, 'F': 500}
                      If provided for this employee's tier, uses flat amount instead of percentage.
        sedera_rates_df: Optional Sedera rates DataFrame for Sedera cost calculation.
        plan_config: Plan configurator dict with hap_enabled, hap_iuas, sedera_enabled, sedera_iuas.
        contribution_settings: Contribution configurator settings including strategy_type, base_age, etc.
    """
    # Use provided cooperative_ratio or fall back to constant
    if cooperative_ratio is None:
        cooperative_ratio = COOPERATIVE_CONFIG['default_discount_ratio']

    emp_id = employee_row.get('employee_id', '')
    first_name = employee_row.get('first_name', 'Employee')
    age = int(employee_row.get('age', 0))
    family_status = employee_row.get('family_status', 'EE')
    state = employee_row.get('state', '')
    zip_code = employee_row.get('zip', '')
    county = employee_row.get('county', '')

    # Get rating area for family premium calculation
    rating_area = employee_row.get('rating_area') or employee_row.get('rating_area_id')
    if rating_area is not None:
        # Handle "Rating Area X" format
        if isinstance(rating_area, str) and rating_area.startswith('Rating Area '):
            rating_area = int(rating_area.replace('Rating Area ', ''))
        else:
            rating_area = int(rating_area) if pd.notna(rating_area) else None

    # Map family status to tier description
    tier_map = {
        "EE": "Employee Only",
        "ES": "Employee + Spouse",
        "EC": "Employee + Children",
        "F": "Family",
    }
    tier = tier_map.get(family_status, family_status)

    # Location string
    location = f"{county}, {state} {zip_code}" if county else f"{state} {zip_code}"

    # Get current costs (handle NaN values - 'or 0' doesn't work for NaN)
    current_er = employee_row.get('current_er_monthly', 0)
    current_er = 0 if pd.isna(current_er) else (current_er or 0)
    current_ee = employee_row.get('current_ee_monthly', 0)
    current_ee = 0 if pd.isna(current_ee) else (current_ee or 0)

    # ICHRA costs and plan details - prefer multi_metal_results (actual LCSP from DB)
    ichra_premium = 0
    ichra_er = 0
    ichra_ee = 0
    projected_2026_premium = 0
    plan_details = {
        'plan_id': None,
        'plan_name': None,
        'actuarial_value': None,
        'ee_rate': None,
    }

    # Comprehensive metal plan details for Bronze, Silver, Gold
    metal_plan_details = {}

    # Store member rate breakdowns for all plan types
    member_breakdowns = {}

    # Get employee details from multi_metal_results for all metal levels
    if multi_metal_results:
        # Collect plan IDs for batch metadata lookup
        plan_ids_to_fetch = []

        for metal in ['Bronze', 'Silver', 'Gold']:
            if metal in multi_metal_results:
                metal_details = multi_metal_results[metal].get('employee_details', [])
                for emp_detail in metal_details:
                    if emp_detail.get('employee_id') == emp_id:
                        plan_id = emp_detail.get('lcp_plan_id')
                        # Calculate aggregate family premium and breakdown
                        aggregate_premium = 0
                        breakdown = None

                        # Always calculate breakdown for non-EE families (for display purposes)
                        if family_status in ['ES', 'EC', 'F'] and rating_area and db and plan_id:
                            result = calculate_aggregate_family_premium(
                                employee_row, plan_id, rating_area, db, dependents_df, return_breakdown=True
                            )
                            if isinstance(result, dict):
                                aggregate_premium = result.get('total_rate', 0)
                                breakdown = result
                            else:
                                aggregate_premium = result

                            # Use EE rate for cost calc if flag is set, otherwise use aggregate
                            if use_ee_rate_only:
                                aggregate_premium = emp_detail.get('lcp_ee_rate', 0)
                        else:
                            # EE-only or missing required data
                            aggregate_premium = emp_detail.get('estimated_tier_premium', 0) or emp_detail.get('lcp_ee_rate', 0)
                            # For EE-only, create a basic breakdown
                            if family_status == 'EE':
                                breakdown = {
                                    'ee_rate': emp_detail.get('lcp_ee_rate', 0),
                                    'ee_age': age,
                                    'spouse_rate': None, 'spouse_age': None,
                                    'child_1_rate': None, 'child_1_age': None,
                                    'child_2_rate': None, 'child_2_age': None,
                                    'child_3_rate': None, 'child_3_age': None,
                                    'child_4_rate': None, 'child_4_age': None,
                                    'child_5_rate': None, 'child_5_age': None,
                                    'total_rate': emp_detail.get('lcp_ee_rate', 0),
                                    'rated_count': 1,
                                    'is_family_tier': False,
                                }

                        # Store breakdown for this metal level
                        if breakdown:
                            member_breakdowns[metal] = breakdown

                        metal_plan_details[metal] = {
                            'plan_id': plan_id,
                            'plan_name': emp_detail.get('lcp_plan_name'),
                            'actuarial_value': emp_detail.get('actuarial_value'),
                            'ee_rate': emp_detail.get('lcp_ee_rate', 0),
                            'estimated_tier_premium': emp_detail.get('estimated_tier_premium', 0),
                            'aggregate_family_premium': aggregate_premium,  # Actual family premium
                            'member_breakdown': breakdown,  # Individual member rates
                            'issuer_name': None,
                            'plan_type': None,
                            'deductible': None,
                            'moop': None,
                            'hsa_eligible': None,
                        }
                        if plan_id:
                            plan_ids_to_fetch.append(plan_id)

                        # Use Silver for the main ICHRA premium calculation
                        if metal == 'Silver':
                            # Store both employee-only and family rates for proper ER/EE split
                            silver_ee_rate = emp_detail.get('lcp_ee_rate', 0) or 0
                            silver_family_total = aggregate_premium or emp_detail.get('estimated_tier_premium', 0) or silver_ee_rate
                            # ichra_premium is used for ER calculation (based on toggle)
                            if use_ee_rate_only:
                                ichra_premium = silver_ee_rate
                            else:
                                ichra_premium = silver_family_total
                            projected_2026_premium = emp_detail.get('projected_2026_premium', 0) or 0
                            plan_details = {
                                'plan_id': plan_id,
                                'plan_name': emp_detail.get('lcp_plan_name'),
                                'actuarial_value': emp_detail.get('actuarial_value'),
                                'ee_rate': silver_ee_rate,
                                'family_total': silver_family_total,
                            }
                        break

        # Batch fetch plan metadata from database (deductible, moop)
        if db is not None and plan_ids_to_fetch:
            try:
                plan_ids_tuple = tuple(set(plan_ids_to_fetch))

                # Query deductible and MOOP separately then combine
                # Deductible query - check for both Medical EHB and Combined Medical/Drug patterns
                ded_query = """
                SELECT plan_id, individual_ded_moop_amount as deductible
                FROM rbis_insurance_plan_variant_ddctbl_moop_20251019202724
                WHERE plan_id IN %s
                  AND network_type = 'In Network'
                  AND (
                      moop_ded_type LIKE '%%Medical EHB Deductible%%'
                      OR moop_ded_type LIKE '%%Combined Medical and Drug EHB Deductible%%'
                  )
                  AND individual_ded_moop_amount NOT IN ('Not Applicable', 'N/A', '')
                """
                ded_df = pd.read_sql(ded_query, db.engine, params=(plan_ids_tuple,))

                # MOOP query
                moop_query = """
                SELECT plan_id, individual_ded_moop_amount as moop
                FROM rbis_insurance_plan_variant_ddctbl_moop_20251019202724
                WHERE plan_id IN %s
                  AND network_type = 'In Network'
                  AND moop_ded_type LIKE '%%Maximum Out of Pocket%%'
                """
                moop_df = pd.read_sql(moop_query, db.engine, params=(plan_ids_tuple,))

                # Build lookup
                plan_info_lookup = {pid: {'deductible': None, 'moop': None} for pid in plan_ids_tuple}

                for _, row in ded_df.iterrows():
                    pid = row['plan_id']
                    if pid in plan_info_lookup:
                        plan_info_lookup[pid]['deductible'] = float(row['deductible']) if pd.notna(row['deductible']) else None

                for _, row in moop_df.iterrows():
                    pid = row['plan_id']
                    if pid in plan_info_lookup:
                        plan_info_lookup[pid]['moop'] = float(row['moop']) if pd.notna(row['moop']) else None

                # Update metal_plan_details with fetched metadata
                for metal, details in metal_plan_details.items():
                    plan_id = details.get('plan_id')
                    if plan_id:
                        info = plan_info_lookup.get(plan_id, {})
                        details['deductible'] = info.get('deductible')
                        details['moop'] = info.get('moop')

            except Exception as e:
                import logging
                logging.warning(f"Error fetching plan metadata for employee examples: {e}")

    # Fallback to contribution_analysis if no multi_metal data
    if ichra_premium == 0 and contribution_analysis and emp_id in contribution_analysis:
        analysis = contribution_analysis[emp_id]
        ichra_data = analysis.get('ichra_analysis', {})
        ichra_premium = ichra_data.get('monthly_premium', 0)

    # Renewal costs - use projected 2026 premium from census if available
    # Apply same ER/EE split ratio as current costs
    if projected_2026_premium > 0:
        current_total = current_er + current_ee
        if current_total > 0:
            er_ratio = current_er / current_total
            renewal_er = projected_2026_premium * er_ratio
            renewal_ee = projected_2026_premium * (1 - er_ratio)
        else:
            # Default to same contribution percentage as ICHRA
            renewal_er = projected_2026_premium * contribution_pct
            renewal_ee = projected_2026_premium * (1 - contribution_pct)
    else:
        renewal_er = 0
        renewal_ee = 0

    # Check if flat amount is provided for this employee's tier
    flat_er_amount = None
    if flat_amounts and family_status in flat_amounts:
        flat_er_amount = flat_amounts.get(family_status)

    # Helper to calculate ER/EE split - uses flat amount if provided, otherwise percentage
    def calc_er_ee_split(premium, flat_amount=None):
        if premium <= 0:
            return 0, 0
        if flat_amount is not None and flat_amount > 0:
            # Use flat employer contribution, employee pays remainder
            er = min(flat_amount, premium)  # Cap at premium (employer can't pay more than total)
            ee = max(0, premium - er)
            return er, ee
        else:
            # Use percentage split
            er = premium * contribution_pct
            ee = premium - er
            return er, ee

    # Calculate ER/EE split for ICHRA Silver
    # Get the family total from plan_details (stored during Silver extraction)
    silver_family_total = plan_details.get('family_total', 0) if plan_details else 0

    if ichra_premium > 0:
        if use_ee_rate_only and silver_family_total > 0:
            # Toggle OFF: ER based on employee-only rate, EE pays the rest (including dependents)
            ichra_er, _ = calc_er_ee_split(ichra_premium, flat_er_amount)
            ichra_ee = max(0, silver_family_total - ichra_er)
        else:
            # Toggle ON: standard ER/EE split on full family rate
            ichra_er, ichra_ee = calc_er_ee_split(ichra_premium, flat_er_amount)
            silver_family_total = ichra_premium  # For EE employees, family total = individual
    else:
        ichra_er, ichra_ee = 0, 0
        silver_family_total = 0

    # Calculate Bronze and Gold costs from metal_plan_details
    # Total premium is ALWAYS the family rate (what they actually pay)
    # ER contribution is based on toggle: employee-only rate OR family rate
    bronze_premium = 0
    bronze_family_total = 0
    gold_premium = 0
    gold_family_total = 0
    if metal_plan_details:
        bronze_details = metal_plan_details.get('Bronze', {})
        gold_details = metal_plan_details.get('Gold', {})

        # Always get the family total for displaying Total
        bronze_family_total = bronze_details.get('aggregate_family_premium', 0) or bronze_details.get('estimated_tier_premium', 0) or bronze_details.get('ee_rate', 0) or 0
        gold_family_total = gold_details.get('aggregate_family_premium', 0) or gold_details.get('estimated_tier_premium', 0) or gold_details.get('ee_rate', 0) or 0

        # ER contribution is based on toggle: employee-only OR family rate
        if use_ee_rate_only:
            # Toggle OFF: ER covers employee only, dependents fall to employee
            bronze_premium = bronze_details.get('ee_rate', 0) or 0
            gold_premium = gold_details.get('ee_rate', 0) or 0
        else:
            # Toggle ON: ER covers full family
            bronze_premium = bronze_family_total
            gold_premium = gold_family_total

    # Calculate ER/EE split
    # When toggle is OFF: ER is based on employee-only rate, EE pays the rest (including dependents)
    # When toggle is ON: ER is based on family rate, standard split
    if use_ee_rate_only and bronze_family_total > 0:
        # ER contribution based on employee-only rate
        bronze_er, _ = calc_er_ee_split(bronze_premium, flat_er_amount)
        # EE pays the difference: family total - ER contribution
        bronze_ee = max(0, bronze_family_total - bronze_er)
        # Use family total for display (Total = ER + EE)
    else:
        bronze_er, bronze_ee = calc_er_ee_split(bronze_premium, flat_er_amount)
        bronze_family_total = bronze_premium  # For EE employees, family total = individual

    if use_ee_rate_only and gold_family_total > 0:
        gold_er, _ = calc_er_ee_split(gold_premium, flat_er_amount)
        gold_ee = max(0, gold_family_total - gold_er)
    else:
        gold_er, gold_ee = calc_er_ee_split(gold_premium, flat_er_amount)
        gold_family_total = gold_premium

    # Base costs dictionary
    costs = {
        "Current": {"employer": round(current_er, 0), "employee": round(current_ee, 0)},
        "Renewal": {"employer": round(renewal_er, 0), "employee": round(renewal_ee, 0)},
        "ICHRA Bronze": {"employer": round(bronze_er, 0), "employee": round(bronze_ee, 0)},
        "ICHRA Silver": {"employer": round(ichra_er, 0), "employee": round(ichra_ee, 0)},
        "ICHRA Gold": {"employer": round(gold_er, 0), "employee": round(gold_ee, 0)},
    }

    # Get plan config or use defaults
    if plan_config is None:
        plan_config = {
            'hap_enabled': False,
            'hap_iuas': {'1k', '2.5k'},
            'sedera_enabled': False,
            'sedera_iuas': set(),
        }

    # HAS (Cooperative) - calculate rate for each enabled IUA level
    # Uses aggregate family rate (sums employee + dependent rates, no 3-child cap)
    if plan_config.get('hap_enabled') and plan_config.get('hap_iuas') and coop_rates_df is not None and not coop_rates_df.empty:
        # Sort IUAs for consistent ordering (1k, 2.5k, 5k)
        sorted_hap_iuas = sorted(plan_config['hap_iuas'], key=lambda x: float(x.replace('k', '')))
        for iua in sorted_hap_iuas:
            coop_lookup = build_cooperative_rate_lookup(coop_rates_df, iua)
            result = calculate_cooperative_family_rate(employee_row, family_status, coop_lookup, dependents_df, return_breakdown=True)
            if isinstance(result, dict):
                coop_family_total = result.get('total_rate', 0)
                coop_ee_rate = result.get('ee_rate', 0) or coop_family_total
                member_breakdowns[f"HAS ${iua}"] = result
            else:
                coop_family_total = result
                coop_ee_rate = result
            coop_premium = coop_family_total if coop_family_total > 0 else (ichra_premium * cooperative_ratio if ichra_premium > 0 else 0)

            # Apply toggle logic: ER based on ee-only or family rate
            if use_ee_rate_only and coop_family_total > 0 and coop_ee_rate != coop_family_total:
                # Toggle OFF: ER based on employee-only rate
                coop_er, _ = calc_er_ee_split(coop_ee_rate, flat_er_amount)
                coop_ee = max(0, coop_family_total - coop_er)
            else:
                coop_er, coop_ee = calc_er_ee_split(coop_premium, flat_er_amount)
            # Key format: "HAS $1k", "HAS $2.5k", etc.
            costs[f"HAS ${iua}"] = {"employer": round(coop_er, 0), "employee": round(coop_ee, 0)}

    # Sedera - calculate rate for each enabled IUA level
    # Uses aggregate family rate (sums employee + dependent rates, no 3-child cap)
    if plan_config.get('sedera_enabled') and plan_config.get('sedera_iuas') and sedera_rates_df is not None and not sedera_rates_df.empty:
        # Sort IUAs for consistent ordering (500, 1000, 1500, 2500, 5000)
        sorted_sedera_iuas = sorted(plan_config['sedera_iuas'], key=lambda x: int(x))
        for iua in sorted_sedera_iuas:
            sedera_lookup = build_sedera_rate_lookup(sedera_rates_df, iua)
            result = calculate_sedera_family_rate(employee_row, family_status, sedera_lookup, dependents_df, return_breakdown=True)
            iua_display = iua if int(iua) < 1000 else f"{int(iua)//1000}k" if int(iua) % 1000 == 0 else f"{int(iua)/1000}k"
            if isinstance(result, dict):
                sedera_family_total = result.get('total_rate', 0)
                sedera_ee_rate = result.get('ee_rate', 0) or sedera_family_total
                member_breakdowns[f"Sedera ${iua_display}"] = result
            else:
                sedera_family_total = result
                sedera_ee_rate = result
            sedera_premium = sedera_family_total if sedera_family_total > 0 else 0

            # Apply toggle logic: ER based on ee-only or family rate
            if use_ee_rate_only and sedera_family_total > 0 and sedera_ee_rate != sedera_family_total:
                # Toggle OFF: ER based on employee-only rate
                sedera_er, _ = calc_er_ee_split(sedera_ee_rate, flat_er_amount)
                sedera_ee = max(0, sedera_family_total - sedera_er)
            else:
                sedera_er, sedera_ee = calc_er_ee_split(sedera_premium, flat_er_amount)
            costs[f"Sedera ${iua_display}"] = {"employer": round(sedera_er, 0), "employee": round(sedera_ee, 0)}

    # Determine winner (lowest total cost for employee)
    winner = "ICHRA Silver"  # Default
    min_ee_cost = costs.get('ICHRA Silver', {}).get('employee', float('inf'))
    for plan, plan_costs in costs.items():
        if plan not in ['Current', 'Renewal'] and plan_costs['employee'] < min_ee_cost:
            min_ee_cost = plan_costs['employee']
            winner = plan

    # Generate insight
    renewal_total = costs['Renewal']['employer'] + costs['Renewal']['employee']
    winner_total = costs.get(winner, {}).get('employer', 0) + costs.get(winner, {}).get('employee', 0)
    savings = (renewal_total - winner_total) * 12

    if 'HAS' in winner or 'Sedera' in winner:
        if min_ee_cost == 0:
            insight = f"Saves ${savings:,.0f}/year vs. renewal, or gets free coverage via {winner}"
        else:
            insight = f"{winner} at ${min_ee_cost:,.0f}/mo makes healthcare actually accessible"
    else:
        insight = f"Best option: {winner} with ${min_ee_cost:,.0f}/mo employee cost"

    # Get family member ages if available
    family_ages = []
    if dependents_df is not None and not dependents_df.empty and family_status in ['ES', 'EC', 'F']:
        emp_deps = dependents_df[dependents_df['employee_id'] == emp_id]
        if not emp_deps.empty:
            for _, dep in emp_deps.iterrows():
                rel = dep.get('relationship', 'Dependent')
                dep_age = dep.get('age')
                if dep_age is not None and not pd.isna(dep_age):
                    family_ages.append({'relationship': rel, 'age': int(dep_age)})

    # Calculate current and renewal totals for variance calculations
    current_total = current_er + current_ee
    renewal_total_monthly = costs['Renewal']['employer'] + costs['Renewal']['employee']

    return {
        "name": first_name,
        "label": label,
        "age": age,
        "tier": tier,
        "location": location,
        "family_status": family_status,
        "family_ages": family_ages,
        "costs": costs,
        "plan_details": plan_details,
        "metal_plan_details": metal_plan_details,  # Bronze, Silver, Gold with full metadata
        "member_breakdowns": member_breakdowns,  # Individual member rates for all plan types
        "current_total_monthly": current_total,
        "renewal_total_monthly": renewal_total_monthly,
        "winner": winner,
        "insight": insight,
        "use_ee_rate_only": use_ee_rate_only,  # Flag to use individual rate in displays
    }


# =============================================================================
# CSV EXPORT FUNCTIONS
# =============================================================================

def generate_scenario_rates_csv(census_df: pd.DataFrame,
                                 coop_rates_df: pd.DataFrame,
                                 sedera_rates_df: pd.DataFrame = None,
                                 config: dict = None,
                                 dependents_df: pd.DataFrame = None) -> pd.DataFrame:
    """
    Generate CSV data with employee details and plan rates.

    Uses aggregate family rates for HAS and Sedera (sums employee + dependent rates).

    Includes:
    - Employee metadata (name, age, zip, state, family status)
    - Current/Renewal premiums (including gap insurance if present)
    - Gap insurance monthly amount
    - HAS rates (based on config) - aggregate family rates
    - Sedera rates (based on config) - aggregate family rates

    Args:
        census_df: Employee census DataFrame
        coop_rates_df: HAS cooperative rates DataFrame
        sedera_rates_df: Sedera rates DataFrame (optional)
        config: Plan configurator config dict (optional)
        dependents_df: DataFrame with dependent info for family rate calculations

    Returns:
        DataFrame ready for CSV export
    """
    if census_df is None or census_df.empty:
        return pd.DataFrame()

    # Get config or use defaults
    if config is None:
        config = {
            'hap_enabled': False,
            'hap_iuas': {'1k', '2.5k'},
            'sedera_enabled': False,
            'sedera_iuas': set(),
        }

    # Build lookup dicts for HAS rates
    hap_lookups = {}
    if config['hap_enabled'] and config['hap_iuas']:
        for iua in config['hap_iuas']:
            hap_lookups[iua] = build_cooperative_rate_lookup(coop_rates_df, iua) if coop_rates_df is not None else {}

    # Build lookup dicts for Sedera rates
    sedera_lookups = {}
    if config['sedera_enabled'] and config['sedera_iuas'] and sedera_rates_df is not None:
        for iua in config['sedera_iuas']:
            sedera_lookups[iua] = build_sedera_rate_lookup(sedera_rates_df, iua)

    all_rows = []

    for _, emp in census_df.iterrows():
        # Get employee data
        emp_id = emp.get('employee_id', emp.get('Employee Number', ''))
        first_name = emp.get('first_name', emp.get('First Name', ''))
        last_name = emp.get('last_name', emp.get('Last Name', ''))
        age = int(emp.get('age', 0)) if pd.notna(emp.get('age')) else 0
        family_status = emp.get('family_status', emp.get('Family Status', 'EE'))
        state = emp.get('state', emp.get('Home State', ''))
        zip_code = emp.get('zip_code', emp.get('Home Zip', ''))
        county = emp.get('county', '')
        rating_area = emp.get('rating_area_id', '')

        # Current/Renewal premiums
        current_ee = emp.get('current_ee_monthly', 0)
        current_ee = 0 if pd.isna(current_ee) else (current_ee or 0)
        current_er = emp.get('current_er_monthly', 0)
        current_er = 0 if pd.isna(current_er) else (current_er or 0)
        gap_insurance = emp.get('gap_insurance_monthly', 0) or 0
        current_total = current_ee + current_er + gap_insurance
        renewal = emp.get('projected_2026_premium', 0) or 0

        # Calculate age band for cooperative rates
        age_band = _get_age_band(age) if age > 0 else ''

        row = {
            'employee_id': emp_id,
            'first_name': first_name,
            'last_name': last_name,
            'age': age,
            'age_band': age_band,
            'family_status': family_status,
            'state': state,
            'zip': zip_code,
            'county': county,
            'rating_area': rating_area,
            'current_ee_monthly': current_ee,
            'current_er_monthly': current_er,
            'gap_insurance_monthly': gap_insurance,
            'current_total_monthly': current_total,
            'renewal_premium': renewal,
        }

        # Add HAS rates based on config (aggregate family rates with member breakdown)
        # Use None (not '') for empty values to keep columns numeric in CSV output
        for iua in sorted(hap_lookups.keys(), key=lambda x: float(x.replace('k', ''))):
            breakdown = calculate_cooperative_family_rate(emp, family_status, hap_lookups[iua], dependents_df, return_breakdown=True)
            iua_col = iua.replace('.', '_')  # e.g., '2.5k' -> '2_5k'
            row[f'hap_{iua_col}_total_rate'] = breakdown['total_rate']
            row[f'hap_{iua_col}_ee_rate'] = breakdown['ee_rate']
            row[f'hap_{iua_col}_spouse_rate'] = breakdown['spouse_rate']  # None for N/A
            for i in range(1, 6):
                row[f'hap_{iua_col}_child_{i}_rate'] = breakdown.get(f'child_{i}_rate')  # None for N/A

        # Add Sedera rates based on config (aggregate family rates with member breakdown)
        iua_display_map = {'500': '500', '1000': '1k', '1500': '1_5k', '2500': '2_5k', '5000': '5k'}
        for iua in sorted(sedera_lookups.keys(), key=lambda x: int(x)):
            breakdown = calculate_sedera_family_rate(emp, family_status, sedera_lookups[iua], dependents_df, return_breakdown=True)
            col_name = iua_display_map.get(iua, iua)
            row[f'sedera_{col_name}_total_rate'] = breakdown['total_rate']
            row[f'sedera_{col_name}_ee_rate'] = breakdown['ee_rate']
            row[f'sedera_{col_name}_spouse_rate'] = breakdown['spouse_rate']  # None for N/A
            for i in range(1, 6):
                row[f'sedera_{col_name}_child_{i}_rate'] = breakdown.get(f'child_{i}_rate')  # None for N/A

        all_rows.append(row)

    if not all_rows:
        return pd.DataFrame()

    df = pd.DataFrame(all_rows)

    # Sort by last name, first name
    df = df.sort_values(['last_name', 'first_name'])

    return df


def generate_marketplace_rates_csv(census_df: pd.DataFrame,
                                   multi_metal_results: Dict,
                                   dependents_df: pd.DataFrame = None,
                                   db = None) -> pd.DataFrame:
    """
    Generate CSV data with employee details and marketplace plan rates.

    Uses aggregate family premiums (employee + dependent rates with ACA 3-child rule)
    for ES/EC/F employees.

    Includes:
    - Employee metadata (name, age, zip, state, family status)
    - For each metal level (Bronze, Silver, Gold): plan name, EE rate, and family rate

    Args:
        census_df: Employee census DataFrame
        multi_metal_results: Results from calculate_multi_metal_scenario()
        dependents_df: DataFrame with dependent info for family rate calculations
        db: Database connection for rate lookups

    Returns:
        DataFrame ready for CSV export
    """
    if census_df is None or census_df.empty:
        return pd.DataFrame()

    if not multi_metal_results:
        return pd.DataFrame()

    # Build lookup from multi_metal_results: emp_id -> {Bronze: {ee_rate, family_rate, plan}, ...}
    emp_metal_data = {}
    for metal in ['Bronze', 'Silver', 'Gold']:
        metal_data = multi_metal_results.get(metal, {})
        for emp_detail in metal_data.get('employee_details', []):
            emp_id = emp_detail.get('employee_id')
            if emp_id not in emp_metal_data:
                emp_metal_data[emp_id] = {}
            emp_metal_data[emp_id][metal] = {
                'ee_rate': emp_detail.get('lcp_ee_rate', 0) or 0,
                'family_rate': (
                    emp_detail.get('aggregate_family_premium') or
                    emp_detail.get('estimated_tier_premium') or
                    emp_detail.get('lcp_ee_rate', 0) or 0
                ),
                'plan_name': emp_detail.get('lcp_plan_name', 'N/A'),
                'plan_id': emp_detail.get('lcp_plan_id', ''),
                'rating_area': emp_detail.get('rating_area', ''),
            }

    all_rows = []

    for _, emp in census_df.iterrows():
        # Get employee data
        emp_id = emp.get('employee_id', emp.get('Employee Number', ''))
        first_name = emp.get('first_name', emp.get('First Name', ''))
        last_name = emp.get('last_name', emp.get('Last Name', ''))
        age = int(emp.get('age', 0)) if pd.notna(emp.get('age')) else 0
        family_status = emp.get('family_status', emp.get('Family Status', 'EE'))
        state = emp.get('state', emp.get('Home State', ''))
        zip_code = emp.get('zip_code', emp.get('Home Zip', ''))
        county = emp.get('county', '')
        rating_area = emp.get('rating_area_id', '')

        # Get metal plan data for this employee
        metal_info = emp_metal_data.get(emp_id, {})

        # For EE, use ee_rate; for ES/EC/F, calculate aggregate family premium if not already in data
        bronze_info = metal_info.get('Bronze', {})
        silver_info = metal_info.get('Silver', {})
        gold_info = metal_info.get('Gold', {})

        # Use family_rate for the main rate column (includes dependents for ES/EC/F)
        bronze_rate = bronze_info.get('family_rate', 0)
        silver_rate = silver_info.get('family_rate', 0)
        gold_rate = gold_info.get('family_rate', 0)

        # Store member breakdowns for each metal
        metal_breakdowns = {'Bronze': None, 'Silver': None, 'Gold': None}

        # If family_rate is 0 or same as ee_rate for non-EE, try to calculate
        if family_status != 'EE' and db is not None:
            for metal, info, current_rate in [
                ('Bronze', bronze_info, bronze_rate),
                ('Silver', silver_info, silver_rate),
                ('Gold', gold_info, gold_rate)
            ]:
                plan_id = info.get('plan_id')
                ra = info.get('rating_area') or rating_area
                if plan_id and ra:
                    # Parse rating area
                    ra_int = ra
                    if isinstance(ra, str):
                        if ra.startswith('Rating Area '):
                            ra_int = int(ra.replace('Rating Area ', ''))
                        else:
                            try:
                                ra_int = int(ra)
                            except ValueError:
                                ra_int = 1
                    # Calculate aggregate family premium with breakdown
                    breakdown = calculate_aggregate_family_premium(emp, plan_id, ra_int, db, dependents_df, return_breakdown=True)
                    if isinstance(breakdown, dict) and breakdown.get('total_rate', 0) > 0:
                        metal_breakdowns[metal] = breakdown
                        if current_rate == 0 or current_rate == info.get('ee_rate', 0):
                            if metal == 'Bronze':
                                bronze_rate = breakdown['total_rate']
                            elif metal == 'Silver':
                                silver_rate = breakdown['total_rate']
                            elif metal == 'Gold':
                                gold_rate = breakdown['total_rate']

        row = {
            'employee_id': emp_id,
            'first_name': first_name,
            'last_name': last_name,
            'age': age,
            'family_status': family_status,
            'state': state,
            'zip': zip_code,
            'county': county,
            'rating_area': rating_area,
            'bronze_ee_rate': bronze_info.get('ee_rate', 0),
            'bronze_family_rate': bronze_rate,
            'bronze_plan_name': bronze_info.get('plan_name', 'N/A'),
            'silver_ee_rate': silver_info.get('ee_rate', 0),
            'silver_family_rate': silver_rate,
            'silver_plan_name': silver_info.get('plan_name', 'N/A'),
            'gold_ee_rate': gold_info.get('ee_rate', 0),
            'gold_family_rate': gold_rate,
            'gold_plan_name': gold_info.get('plan_name', 'N/A'),
        }

        # Add individual member rate columns for each metal level
        # Use None (not '') for empty values to keep columns numeric in CSV output
        for metal in ['bronze', 'silver', 'gold']:
            breakdown = metal_breakdowns.get(metal.capitalize())
            if breakdown:
                row[f'{metal}_spouse_rate'] = breakdown.get('spouse_rate')  # None for N/A
                for i in range(1, 6):
                    row[f'{metal}_child_{i}_rate'] = breakdown.get(f'child_{i}_rate')  # None for N/A
            else:
                # No breakdown available (EE-only or no plan data)
                row[f'{metal}_spouse_rate'] = None
                for i in range(1, 6):
                    row[f'{metal}_child_{i}_rate'] = None

        all_rows.append(row)

    if not all_rows:
        return pd.DataFrame()

    df = pd.DataFrame(all_rows)

    # Sort by last name, first name
    df = df.sort_values(['last_name', 'first_name'])

    return df


def generate_employee_examples_csv(employee_examples: List[Dict], plan_config: Dict = None) -> pd.DataFrame:
    """
    Generate CSV data from employee examples matching the UI table format.

    Format matches the UI exactly:
    - One section per employee with header row showing employee info
    - Columns: Plan names (Current, Renewal, Bronze, Silver, Gold, HAS, Sedera)
    - Rows: Employee cost, Employer cost, Total

    Args:
        employee_examples: List of employee example dicts from build_employee_example()
        plan_config: Plan configurator settings to determine which columns to show

    Returns:
        DataFrame ready for CSV export
    """
    if not employee_examples:
        return pd.DataFrame()

    plan_config = plan_config or {}
    all_rows = []

    # Get contribution strategy description
    strategy_desc = get_contribution_strategy_description()

    for emp in employee_examples:
        name = emp.get('name', '')
        label = emp.get('label', '')
        age = emp.get('age', 0)
        tier = emp.get('tier', '')
        location = emp.get('location', '')
        costs = emp.get('costs', {})

        # Build column list matching UI (only enabled plans)
        plan_columns = ['Current', 'Renewal', 'ICHRA Bronze', 'ICHRA Silver', 'ICHRA Gold']

        # Add HAS columns for each enabled IUA level
        if plan_config.get('hap_enabled') and plan_config.get('hap_iuas'):
            sorted_hap_iuas = sorted(plan_config['hap_iuas'], key=lambda x: float(x.replace('k', '')))
            for iua in sorted_hap_iuas:
                key = f"HAS ${iua}"
                if key in costs:
                    plan_columns.append(key)

        # Add Sedera columns for each enabled IUA level
        if plan_config.get('sedera_enabled') and plan_config.get('sedera_iuas'):
            sorted_sedera_iuas = sorted(plan_config['sedera_iuas'], key=lambda x: int(x))
            for iua in sorted_sedera_iuas:
                iua_display = iua if int(iua) < 1000 else f"{int(iua)//1000}k" if int(iua) % 1000 == 0 else f"{int(iua)/1000}k"
                key = f"Sedera ${iua_display}"
                if key in costs:
                    plan_columns.append(key)

        # Header row with employee info
        header_row = {'': f"{label}: {name} | Age {age} | {tier} | {location}"}
        for col in plan_columns:
            header_row[col] = ''
        all_rows.append(header_row)

        # Strategy row
        strategy_row = {'': strategy_desc}
        for col in plan_columns:
            strategy_row[col] = ''
        all_rows.append(strategy_row)

        # Employee (EE) cost row
        ee_row = {'': 'Employee'}
        for col in plan_columns:
            ee_row[col] = f"${costs.get(col, {}).get('employee', 0):,.0f}"
        all_rows.append(ee_row)

        # Employer (ER) cost row
        er_row = {'': 'Employer'}
        for col in plan_columns:
            er_row[col] = f"${costs.get(col, {}).get('employer', 0):,.0f}"
        all_rows.append(er_row)

        # Total row
        total_row = {'': 'Total'}
        for col in plan_columns:
            ee_val = costs.get(col, {}).get('employee', 0)
            er_val = costs.get(col, {}).get('employer', 0)
            total_row[col] = f"${ee_val + er_val:,.0f}"
        all_rows.append(total_row)

        # Empty row between employees
        empty_row = {'': ''}
        for col in plan_columns:
            empty_row[col] = ''
        all_rows.append(empty_row)

    # Build DataFrame with consistent columns
    if all_rows:
        # Get all unique columns from first employee's data
        first_emp_costs = employee_examples[0].get('costs', {})
        base_columns = ['Current', 'Renewal', 'ICHRA Bronze', 'ICHRA Silver', 'ICHRA Gold']

        if plan_config.get('hap_enabled') and plan_config.get('hap_iuas'):
            for iua in sorted(plan_config['hap_iuas'], key=lambda x: float(x.replace('k', ''))):
                key = f"HAS ${iua}"
                if key in first_emp_costs:
                    base_columns.append(key)

        if plan_config.get('sedera_enabled') and plan_config.get('sedera_iuas'):
            for iua in sorted(plan_config['sedera_iuas'], key=lambda x: int(x)):
                iua_display = iua if int(iua) < 1000 else f"{int(iua)//1000}k" if int(iua) % 1000 == 0 else f"{int(iua)/1000}k"
                key = f"Sedera ${iua_display}"
                if key in first_emp_costs:
                    base_columns.append(key)

        df = pd.DataFrame(all_rows, columns=[''] + base_columns)
        return df

    return pd.DataFrame()


# =============================================================================
# HEADER SECTION
# =============================================================================

def render_header(data: DashboardData):
    st.markdown(f"""
    <p class="client-name">{data.client_name}</p>
    <p class="client-meta">
        {data.employee_count} employees
        <span class="client-meta-divider">|</span>
        Avg age {data.avg_age:.0f}
        <span class="client-meta-divider">|</span>
        {data.location}
    </p>
    <p style="color: #364153; font-size: 14px;">
        Renewal: <span style="font-family: Inter;">${data.current_premium:,.0f}</span> →
        <span style="font-family: Inter;">${data.renewal_premium:,.0f}/month</span>
        <span class="increase-badge">+{data.increase_pct:.0f}% increase</span>
    </p>
    """, unsafe_allow_html=True)


# =============================================================================
# EMPLOYER CONTRIBUTION INPUT
# =============================================================================

def render_contribution_input_card():
    """Render optional employer contribution input card.

    Allows users to specify either:
    1. Percentage split (e.g., 70% employer paid)
    2. Flat dollar amount by family status tier

    Updates ICHRA Bronze/Silver/Gold and Cooperative columns in Employee Examples.
    """
    # Ensure contribution_settings is initialized
    if 'contribution_settings' not in st.session_state:
        st.session_state.contribution_settings = {
            'strategy_type': 'percentage',  # percentage, flat_amount, base_age_curve, percentage_lcsp, fixed_age_tiers
            'default_percentage': 75,
            'by_class': {},
            'input_mode': 'percentage',  # Keep for backwards compat
            'flat_amounts': {'EE': None, 'ES': None, 'EC': None, 'F': None},
            'exclude_dependent_ichra': False,  # Toggle: when True, ER only covers employee rate
            'show_ichra_metals': False,  # Toggle for showing ICHRA metal plans in rate breakdown
            # Base age curve params
            'base_age': 21,
            'base_contribution': 400.0,
            # % of LCSP params
            'lcsp_percentage': 75,
            # Fixed age tiers params
            'tier_amounts': {'21': 300, '18-25': 350, '26-35': 400, '36-45': 500, '46-55': 600, '56-63': 750, '64+': 900}
        }

    st.markdown('<p class="card-title">Employer contribution configurator</p>', unsafe_allow_html=True)
    st.markdown("""
    <p style="font-size: 14px; color: #6b7280; margin-bottom: 16px;">
        Set how employer contribution is calculated for ICHRA plan comparisons
    </p>
    """, unsafe_allow_html=True)

    # Get current settings
    settings = st.session_state.get('contribution_settings', {})
    current_strategy = settings.get('strategy_type', 'percentage')
    current_pct = settings.get('default_percentage', 75)
    flat_amounts = settings.get('flat_amounts', {})

    # Employer ICHRA contribution scope toggle (default: include dependents, opt-in to exclude)
    exclude_deps = st.checkbox(
        "Exclude individual dependents from employer ICHRA contribution strategy",
        value=settings.get('exclude_dependent_ichra', False),
        help="When checked, employer ICHRA allowance is calculated on the employee's individual rate only. Dependent premiums become the employee's responsibility.",
        key="exclude_dependent_ichra_checkbox"
    )
    st.session_state.contribution_settings['exclude_dependent_ichra'] = exclude_deps
    if exclude_deps:
        st.caption("Dependent premiums fall to employee")

    # Strategy selector (expanded from 2 to 5 options)
    STRATEGY_OPTIONS = {
        'percentage': 'Percentage of premium',
        'flat_amount': 'Flat amount by tier',
        'base_age_curve': 'Base age + ACA 3:1 curve',
        'percentage_lcsp': '% of LCSP',
        'fixed_age_tiers': 'Fixed age tiers'
    }

    # Determine current index
    strategy_keys = list(STRATEGY_OPTIONS.keys())
    current_index = strategy_keys.index(current_strategy) if current_strategy in strategy_keys else 0

    strategy_type = st.radio(
        "Contribution strategy",
        options=strategy_keys,
        format_func=lambda x: STRATEGY_OPTIONS[x],
        index=current_index,
        horizontal=True,
        key="contribution_strategy_radio",
        label_visibility="collapsed"
    )

    # Update strategy type in session state
    if strategy_type != current_strategy:
        st.session_state.contribution_settings['strategy_type'] = strategy_type
        # Keep input_mode in sync for backwards compat
        st.session_state.contribution_settings['input_mode'] = strategy_type

    if strategy_type == 'percentage':
        # Percentage slider
        pct = st.slider(
            "Employer contribution",
            min_value=0,
            max_value=100,
            value=current_pct,
            step=5,
            format="%d%%",
            help="Percentage of premium paid by employer",
            key="contribution_pct_slider"
        )

        # Update percentage in session state
        if pct != current_pct:
            st.session_state.contribution_settings['default_percentage'] = pct

        # Show split preview
        ee_pct = 100 - pct
        st.markdown(f"""
        <div style="display: flex; gap: 24px; margin-top: 8px; margin-bottom: 8px;">
            <div style="flex: 1; text-align: center; padding: 12px; background: #f0fdf4; border-radius: 8px;">
                <span style="font-size: 13px; color: #166534;">Employer pays</span><br>
                <span style="font-size: 20px; font-weight: 600; color: #166534;">{pct}%</span>
            </div>
            <div style="flex: 1; text-align: center; padding: 12px; background: #fef3c7; border-radius: 8px;">
                <span style="font-size: 13px; color: #92400e;">Employee pays</span><br>
                <span style="font-size: 20px; font-weight: 600; color: #92400e;">{ee_pct}%</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    elif strategy_type == 'flat_amount':
        # Flat amount inputs by tier
        st.markdown("""
        <p style="font-size: 13px; color: #6b7280; margin-bottom: 8px;">
            Monthly employer contribution by coverage tier
        </p>
        """, unsafe_allow_html=True)

        col1, col2, col3, col4 = st.columns(4)

        tier_labels = {
            'EE': ('Employee Only', col1),
            'ES': ('EE + Spouse', col2),
            'EC': ('EE + Child(ren)', col3),
            'F': ('Family', col4)
        }

        updated_amounts = {}
        for tier, (label, col) in tier_labels.items():
            with col:
                current_val = flat_amounts.get(tier)
                val = st.number_input(
                    label,
                    min_value=0,
                    max_value=5000,
                    value=current_val if current_val is not None else 0,
                    step=25,
                    format="%d",
                    key=f"flat_amount_{tier}",
                    help=f"Employer contribution for {label}"
                )
                # Store None if 0 (means not set), otherwise store value
                updated_amounts[tier] = val if val > 0 else None

        # Update flat amounts in session state
        st.session_state.contribution_settings['flat_amounts'] = updated_amounts

        # Show summary if any values are set
        set_amounts = {k: v for k, v in updated_amounts.items() if v is not None}
        if set_amounts:
            summary = " · ".join([f"{k}: ${v:,}" for k, v in set_amounts.items()])
            st.markdown(f"""
            <div style="margin-top: 8px; padding: 8px 12px; background: #f0fdf4; border-radius: 6px; font-size: 13px; color: #166534;">
                <strong>ER contribution:</strong> {summary}
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="margin-top: 8px; padding: 8px 12px; background: #f9fafb; border-radius: 6px; font-size: 13px; color: #6b7280;">
                Enter amounts above to override default percentage
            </div>
            """, unsafe_allow_html=True)

    elif strategy_type == 'base_age_curve':
        # Base age + ACA 3:1 curve
        st.markdown("""
        <p style="font-size: 13px; color: #6b7280; margin-bottom: 8px;">
            Set a base contribution at a reference age. The system scales contributions using the ACA 3:1 age curve.
        </p>
        """, unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            base_age_options = [21, 25, 30, 35, 40]
            current_base_age = settings.get('base_age', 21)
            base_age_idx = base_age_options.index(current_base_age) if current_base_age in base_age_options else 0
            base_age = st.selectbox(
                "Base age",
                options=base_age_options,
                index=base_age_idx,
                key="base_age_select",
                help="Reference age for contribution calculation"
            )
        with col2:
            base_contribution = st.number_input(
                "Base contribution ($/month)",
                min_value=0.0,
                max_value=5000.0,
                value=float(settings.get('base_contribution', 400.0)),
                step=25.0,
                key="base_contribution_input",
                help="Monthly contribution for the base age"
            )

        st.session_state.contribution_settings['base_age'] = base_age
        st.session_state.contribution_settings['base_contribution'] = base_contribution

        # Show preview table
        from constants import ACA_AGE_CURVE
        base_ratio = ACA_AGE_CURVE.get(base_age, 1.0)
        preview_ages = [21, 30, 40, 50, 64]
        preview_data = []
        for age in preview_ages:
            ratio = ACA_AGE_CURVE.get(age, 1.0)
            amount = base_contribution * (ratio / base_ratio)
            preview_data.append({"Age": age, "Contribution": f"${amount:,.0f}"})

        st.markdown("<p style='font-size: 12px; color: #6b7280; margin-top: 8px;'>Preview by age:</p>", unsafe_allow_html=True)
        st.dataframe(pd.DataFrame(preview_data), hide_index=True, use_container_width=True)

    elif strategy_type == 'percentage_lcsp':
        # Percentage of LCSP
        st.markdown("""
        <p style="font-size: 13px; color: #6b7280; margin-bottom: 8px;">
            Each employee receives X% of their individual LCSP (Lowest Cost Silver Plan) premium.
        </p>
        """, unsafe_allow_html=True)

        lcsp_pct = st.slider(
            "Percentage of LCSP",
            min_value=50,
            max_value=100,
            value=settings.get('lcsp_percentage', 75),
            step=5,
            format="%d%%",
            key="lcsp_pct_slider",
            help="Percentage of each employee's LCSP premium covered by employer"
        )
        st.session_state.contribution_settings['lcsp_percentage'] = lcsp_pct

        ee_pct = 100 - lcsp_pct
        st.markdown(f"""
        <div style="margin-top: 8px; padding: 12px; background: #eff6ff; border-radius: 8px; font-size: 13px; color: #1e40af;">
            At <strong>{lcsp_pct}%</strong>: Employees pay {ee_pct}% of their individual LCSP premium.
            Higher-cost employees get proportionally larger contributions.
        </div>
        """, unsafe_allow_html=True)

    elif strategy_type == 'fixed_age_tiers':
        # Fixed age tiers
        st.markdown("""
        <p style="font-size: 13px; color: #6b7280; margin-bottom: 8px;">
            Set fixed dollar amounts for each age tier. Employees are assigned based on their age.
        </p>
        """, unsafe_allow_html=True)

        tier_labels = ['21', '18-25', '26-35', '36-45', '46-55', '56-63', '64+']
        current_tier_amounts = settings.get('tier_amounts', {})

        tier_cols = st.columns(4)
        updated_tier_amounts = {}
        for i, tier in enumerate(tier_labels):
            with tier_cols[i % 4]:
                default_val = current_tier_amounts.get(tier, 400)
                updated_tier_amounts[tier] = st.number_input(
                    f"Age {tier}",
                    min_value=0.0,
                    max_value=5000.0,
                    value=float(default_val),
                    step=25.0,
                    key=f"age_tier_{tier}",
                    help=f"Monthly contribution for age {tier}"
                )

        st.session_state.contribution_settings['tier_amounts'] = updated_tier_amounts


# =============================================================================
# WORKFORCE COMPOSITION
# =============================================================================

def render_workforce_composition(data: DashboardData):
    st.markdown('<p class="card-title">Workforce composition</p>', unsafe_allow_html=True)

    if not data.composition:
        st.info("No workforce composition data available")
        return

    max_count = max(item["count"] for item in data.composition.values()) if data.composition else 1

    for tier, tier_data in data.composition.items():
        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown(f'<span style="font-size: 14px; font-weight: 500; color: #364153;">{tier}</span>', unsafe_allow_html=True)
        with col2:
            st.markdown(f'<span style="font-size: 14px; font-weight: 700; color: #101828;">{tier_data["count"]}</span>', unsafe_allow_html=True)

        # Custom progress bar
        progress_pct = tier_data["count"] / max_count
        st.markdown(f"""
        <div style="background: #e5e7eb; height: 8px; border-radius: 9999px; margin-bottom: 12px;">
            <div style="background: {tier_data['color']}; height: 8px; border-radius: 9999px; width: {progress_pct * 100}%;"></div>
        </div>
        """, unsafe_allow_html=True)

    # Age stats
    st.markdown("<hr style='border: none; border-top: 1px solid #e5e7eb; margin: 16px 0;'>", unsafe_allow_html=True)

    for label, value in [("Youngest", data.youngest_age), ("Oldest", data.oldest_age), ("Average", int(data.average_age))]:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f'<span style="font-size: 14px; color: #364153;">{label}:</span>', unsafe_allow_html=True)
        with col2:
            st.markdown(f'<span style="font-size: 14px; font-weight: 500; color: #364153;">{value}</span>', unsafe_allow_html=True)

    # Warning if older population
    if data.average_age > OLDER_POPULATION_WARNING_AGE:
        st.markdown("""
        <div class="warning-box" style="margin-top: 16px;">
            <span style="font-size: 18px;">⚠</span>
            <span class="warning-text">Older population increases individual market rates</span>
        </div>
        """, unsafe_allow_html=True)


# =============================================================================
# CONTRIBUTION PATTERN CARD
# =============================================================================

def render_contribution_pattern_card():
    """Render contribution pattern as a card (moved from left nav expander)."""
    contribution_pattern = st.session_state.get('detected_contribution_pattern')

    if not contribution_pattern:
        st.markdown('<p class="card-title">Contribution Pattern</p>', unsafe_allow_html=True)
        st.markdown("""
        <p style="color: #6b7280; font-size: 14px;">
            Upload census data to detect contribution patterns
        </p>
        """, unsafe_allow_html=True)
        return

    from contribution_pattern_detector import get_pattern_summary
    summary = get_pattern_summary(contribution_pattern)

    # Card title with overall pattern as description
    pattern_type = summary['overall_type'].replace('_', ' ').title()
    st.markdown(f'<p class="card-title">Contribution Pattern</p>', unsafe_allow_html=True)
    st.markdown(f"""
    <p style="color: #4a5565; font-size: 14px; margin-bottom: 16px;">
        {pattern_type}
    </p>
    """, unsafe_allow_html=True)

    # Show warning if review needed
    if contribution_pattern.needs_any_review():
        st.warning("Some tiers have high variance and may need review")

    # Tier breakdown table
    pattern_data = []
    for tier in summary['tiers']:
        row = {
            'Tier': tier['label'],
            'Pattern': tier['pattern_type'].replace('_', ' ').title(),
            'ER%': tier['er_percentage_display'] if tier['pattern_type'] == 'percentage' else '-',
            'Count': tier['sample_size']
        }
        if contribution_pattern.needs_any_review():
            row['Status'] = '⚠️' if tier['needs_review'] else '✓'
        pattern_data.append(row)

    import pandas as pd
    st.dataframe(pd.DataFrame(pattern_data), use_container_width=True, hide_index=True)

    # Show any warnings
    if summary.get('warnings'):
        for warning in summary['warnings']:
            st.caption(f"⚠️ {warning}")


# =============================================================================
# PLAN CONFIGURATOR
# =============================================================================

def init_plan_configurator(total_employees: int = 0):
    """Initialize plan configurator session state with defaults."""
    if 'plan_configurator' not in st.session_state:
        st.session_state.plan_configurator = {
            'hap_enabled': False,
            'hap_iuas': {'1k', '2.5k'},  # Set of selected IUAs
            'hap_admin_fee': 0.0,
            'sedera_enabled': False,
            'sedera_iuas': set(),  # Empty = none selected
            'sedera_admin_fee': 0.0,
            'preventive_enabled': False,
            'preventive_include_dpc': True,
            'preventive_employee_count': total_employees,
        }
    # Update max employee count if census changes
    if total_employees > 0:
        config = st.session_state.plan_configurator
        # Cap preventive employee count to new total if it exceeds
        if config['preventive_employee_count'] > total_employees:
            config['preventive_employee_count'] = total_employees


def render_plan_configurator(total_employees: int = 0):
    """
    Render the Plan Configurator UI for selecting plan options.

    Returns the current configuration dict from session state.
    """
    init_plan_configurator(total_employees)
    config = st.session_state.plan_configurator

    with st.expander("Plan Configurator", expanded=False):
        col1, col2, col3 = st.columns(3)

        # HAS Plans Section
        with col1:
            st.markdown("**HAS Plans**")
            hap_enabled = st.toggle("Enable HAS", value=config['hap_enabled'], key="hap_enabled_toggle")
            config['hap_enabled'] = hap_enabled

            if hap_enabled:
                # Deductible selection with chips-style multiselect
                hap_options = ['$1k', '$2.5k']
                hap_defaults = [f"${iua}" for iua in config['hap_iuas']]
                selected_hap = st.multiselect(
                    "Deductible",
                    options=hap_options,
                    default=hap_defaults,
                    key="hap_iua_select"
                )
                # Convert back to internal format
                config['hap_iuas'] = {opt.replace('$', '') for opt in selected_hap}

                # Admin fee
                hap_admin = st.number_input(
                    "Admin Fee (PEPM)",
                    min_value=0.0,
                    max_value=100.0,
                    value=float(config['hap_admin_fee']),
                    step=1.0,
                    format="%.2f",
                    key="hap_admin_input"
                )
                config['hap_admin_fee'] = hap_admin

        # Sedera Plans Section
        with col2:
            st.markdown("**Sedera Plans**")
            sedera_enabled = st.toggle("Enable Sedera", value=config['sedera_enabled'], key="sedera_enabled_toggle")
            config['sedera_enabled'] = sedera_enabled

            if sedera_enabled:
                # IUA selection
                sedera_options = ['$500', '$1k', '$1.5k', '$2.5k', '$5k']
                sedera_defaults = []
                for iua in config['sedera_iuas']:
                    # Map internal format to display format
                    if iua == '500':
                        sedera_defaults.append('$500')
                    elif iua == '1000':
                        sedera_defaults.append('$1k')
                    elif iua == '1500':
                        sedera_defaults.append('$1.5k')
                    elif iua == '2500':
                        sedera_defaults.append('$2.5k')
                    elif iua == '5000':
                        sedera_defaults.append('$5k')

                selected_sedera = st.multiselect(
                    "IUA Levels",
                    options=sedera_options,
                    default=sedera_defaults,
                    key="sedera_iua_select"
                )
                # Convert back to internal format (database uses '500', '1000', etc.)
                iua_map = {'$500': '500', '$1k': '1000', '$1.5k': '1500', '$2.5k': '2500', '$5k': '5000'}
                config['sedera_iuas'] = {iua_map[opt] for opt in selected_sedera}

                # Admin fee
                sedera_admin = st.number_input(
                    "Admin Fee (PEPM)",
                    min_value=0.0,
                    max_value=100.0,
                    value=float(config['sedera_admin_fee']),
                    step=1.0,
                    format="%.2f",
                    key="sedera_admin_input"
                )
                config['sedera_admin_fee'] = sedera_admin

        # Preventive Care Section
        with col3:
            st.markdown("**Preventive Care**")
            preventive_enabled = st.toggle("Include Preventive", value=config['preventive_enabled'], key="preventive_enabled_toggle")
            config['preventive_enabled'] = preventive_enabled

            if preventive_enabled:
                # DPC toggle
                include_dpc = st.toggle(
                    "Include DPC ($124/mo)",
                    value=config['preventive_include_dpc'],
                    key="preventive_dpc_toggle",
                    help="With DPC: $124/mo, Without: $107/mo"
                )
                config['preventive_include_dpc'] = include_dpc

                # Employee count
                max_employees = total_employees if total_employees > 0 else 100
                emp_count = st.number_input(
                    f"Employees (max: {max_employees})",
                    min_value=0,
                    max_value=max_employees,
                    value=min(config['preventive_employee_count'], max_employees),
                    step=1,
                    key="preventive_emp_count"
                )
                config['preventive_employee_count'] = emp_count

                # Show monthly cost preview
                rate = PREVENTIVE_CARE_RATE_WITH_DPC if include_dpc else PREVENTIVE_CARE_RATE_WITHOUT_DPC
                monthly_cost = rate * emp_count
                st.caption(f"Monthly: ${monthly_cost:,.0f}")

    return config


# =============================================================================
# COMPARISON TABLE
# =============================================================================

def render_comparison_table(data: DashboardData, db=None, census_df: pd.DataFrame = None,
                             dependents_df: pd.DataFrame = None):
    """Render the Monthly Premium by Scenario comparison table with HAS options."""
    # Get employee count for configurator
    total_employees = len(census_df) if census_df is not None and not census_df.empty else 0

    # Render Plan Configurator above table
    config = render_plan_configurator(total_employees)

    # Title row (no scenario selector)
    st.markdown("""
    <p style="font-size: 20px; font-weight: 500; color: #101828; margin-bottom: 4px;">Cooperative Health Plan Comparison</p>
    <p style="font-size: 16px; color: #4a5565; margin-bottom: 24px;">Monthly employer costs: traditional group plan vs. Health Access Plan alternatives</p>
    """, unsafe_allow_html=True)

    # Helper to format currency or show --
    def fmt(val):
        return f"${val:,.0f}" if val and val > 0 else "--"

    # Helper to format savings (handles positive and negative)
    def fmt_savings(amount, pct):
        if amount is None or amount == 0:
            return ("--", "#6b7280")  # Gray for no data
        elif amount > 0:
            return (f"${amount:,.0f}", "#00a63e")  # Green for savings
        else:
            return (f"-${abs(amount):,.0f}", "#dc2626")  # Red for cost increase

    # Plan year keys
    current_key = f"Current {CURRENT_PLAN_YEAR}"
    renewal_key = f"Renewal {RENEWAL_PLAN_YEAR}"

    # Map tier names to family status codes
    # Order: EE, EC, ES, F (Employee Only, Employee + Children, Employee + Spouse, Family)
    tier_info = {
        "Employee Only": {"code": "EE"},
        "Employee + Children": {"code": "EC"},
        "Employee + Spouse": {"code": "ES"},
        "Family": {"code": "F"},
    }
    tiers = list(tier_info.keys())

    # Load HAS rates and calculate totals (cached)
    # Uses aggregate family rates - sums rates for employee + all dependents
    coop_rates_df = load_cooperative_rate_table(_db_available=db is not None)
    hap_totals = calculate_hap_totals(census_df, coop_rates_df, dependents_df)

    # Load Sedera rates if enabled (cached)
    # Uses aggregate family rates - sums rates for employee + all dependents
    sedera_rates_df = None
    sedera_totals = {}
    if config['sedera_enabled'] and config['sedera_iuas']:
        sedera_rates_df = load_sedera_rate_table(_db_available=db is not None)
        sedera_totals = calculate_sedera_totals(census_df, sedera_rates_df, config['sedera_iuas'], dependents_df)

    # Build list of plan columns based on configuration
    # Each column: {'key': str, 'label': str, 'subtitle': str, 'style_class': str, 'totals_key': str}
    plan_columns = []

    # HAS columns (if enabled)
    if config['hap_enabled'] and config['hap_iuas']:
        for iua in sorted(config['hap_iuas'], key=lambda x: float(x.replace('k', ''))):
            col_key = f'HAS ${iua}'
            totals_key = f'hap_{iua.replace(".", "_")}' if '.' not in iua else f'hap_{iua.replace(".", "_")}'
            # Map to hap_totals keys: 'hap_1k' or 'hap_2_5k'
            if iua == '1k':
                totals_key = 'hap_1k'
            elif iua == '2.5k':
                totals_key = 'hap_2_5k'
            plan_columns.append({
                'key': col_key,
                'label': f'HAS ${iua}',
                'subtitle': 'Health Access Solutions',
                'style_class': 'col-header-has',
                'totals_key': totals_key,
                'type': 'has',
                'iua': iua,
                'admin_fee': config['hap_admin_fee'],
            })

    # Sedera columns (if enabled)
    if config['sedera_enabled'] and config['sedera_iuas']:
        # Map database IUA values to display labels
        iua_display_map = {'500': '$500', '1000': '$1k', '1500': '$1.5k', '2500': '$2.5k', '5000': '$5k'}
        for iua in sorted(config['sedera_iuas'], key=lambda x: int(x)):
            display_iua = iua_display_map.get(iua, f'${iua}')
            col_key = f'Sedera {display_iua}'
            totals_key = f'sedera_{iua}'
            plan_columns.append({
                'key': col_key,
                'label': f'Sedera {display_iua}',
                'subtitle': 'Prime+ with DPC',
                'style_class': 'col-header-sedera',
                'totals_key': totals_key,
                'type': 'sedera',
                'iua': iua,
                'admin_fee': config['sedera_admin_fee'],
            })

    # Count employees per tier and calculate current/renewal totals per tier
    tier_counts = {}
    tier_avg_age = {}  # Average age per tier
    tier_current = {}
    tier_renewal = {}
    tier_current_rate_per_ee = {}  # Typical per-employee rate from census (not averaged)
    tier_renewal_rate_per_ee = {}  # Typical per-employee renewal rate from census
    if census_df is not None and not census_df.empty and 'family_status' in census_df.columns:
        for tier_name, info in tier_info.items():
            tier_employees = census_df[census_df['family_status'] == info['code']]
            tier_counts[tier_name] = len(tier_employees)

            # Calculate average age for this tier
            if 'age' in tier_employees.columns and len(tier_employees) > 0:
                tier_avg_age[tier_name] = round(tier_employees['age'].mean())
            else:
                tier_avg_age[tier_name] = 0

            # Sum current premiums for this tier
            if 'current_er_monthly' in census_df.columns and 'current_ee_monthly' in census_df.columns:
                current_er = tier_employees['current_er_monthly'].fillna(0).sum()
                current_ee = tier_employees['current_ee_monthly'].fillna(0).sum()
                tier_current[tier_name] = current_er + current_ee
                # Get the typical per-employee rate (most common value, or first non-zero)
                ee_vals = tier_employees['current_ee_monthly'].fillna(0).infer_objects(copy=False)
                er_vals = tier_employees['current_er_monthly'].fillna(0).infer_objects(copy=False)
                per_ee_rates = ee_vals + er_vals
                non_zero_rates = per_ee_rates[per_ee_rates > 0]
                if len(non_zero_rates) > 0:
                    # Use mode (most common rate) or first non-zero if mode fails
                    try:
                        tier_current_rate_per_ee[tier_name] = float(non_zero_rates.mode().iloc[0])
                    except (IndexError, ValueError):
                        tier_current_rate_per_ee[tier_name] = float(non_zero_rates.iloc[0])
                else:
                    tier_current_rate_per_ee[tier_name] = 0
            else:
                tier_current[tier_name] = 0
                tier_current_rate_per_ee[tier_name] = 0

            # Sum renewal premiums for this tier
            if 'projected_2026_premium' in census_df.columns:
                tier_renewal[tier_name] = tier_employees['projected_2026_premium'].fillna(0).sum()
                # Get typical per-employee renewal rate
                renewal_vals = tier_employees['projected_2026_premium'].fillna(0).infer_objects(copy=False)
                non_zero_renewal = renewal_vals[renewal_vals > 0]
                if len(non_zero_renewal) > 0:
                    try:
                        tier_renewal_rate_per_ee[tier_name] = float(non_zero_renewal.mode().iloc[0])
                    except (IndexError, ValueError):
                        tier_renewal_rate_per_ee[tier_name] = float(non_zero_renewal.iloc[0])
                else:
                    tier_renewal_rate_per_ee[tier_name] = 0
            else:
                tier_renewal[tier_name] = 0
                tier_renewal_rate_per_ee[tier_name] = 0
    else:
        tier_counts = {tier: 0 for tier in tiers}
        tier_avg_age = {tier: 0 for tier in tiers}
        tier_current = {tier: 0 for tier in tiers}
        tier_renewal = {tier: 0 for tier in tiers}
        tier_current_rate_per_ee = {tier: 0 for tier in tiers}
        tier_renewal_rate_per_ee = {tier: 0 for tier in tiers}

    # Calculate gap insurance per tier (for display breakdown)
    # Current: only count gap for employees with current coverage
    # Renewal: count gap for employees with 2026 coverage
    tier_gap_current = {}
    tier_gap_renewal = {}
    gap_rates_by_tier = {}
    total_gap = 0
    has_gap_data = False

    if census_df is not None and not census_df.empty and 'gap_insurance_monthly' in census_df.columns:
        gap_series = census_df['gap_insurance_monthly'].fillna(0).infer_objects(copy=False)
        if gap_series.sum() > 0:
            has_gap_data = True
            for tier_name, info in tier_info.items():
                tier_employees = census_df[census_df['family_status'] == info['code']]

                # Current: gap for employees with current coverage (current_er + current_ee > 0)
                if 'current_er_monthly' in tier_employees.columns and 'current_ee_monthly' in tier_employees.columns:
                    current_total = tier_employees['current_er_monthly'].fillna(0).infer_objects(copy=False) + tier_employees['current_ee_monthly'].fillna(0).infer_objects(copy=False)
                    employees_with_current = tier_employees[current_total > 0]
                    tier_gap_current[tier_name] = employees_with_current['gap_insurance_monthly'].fillna(0).infer_objects(copy=False).sum()
                else:
                    tier_gap_current[tier_name] = 0

                # Renewal: gap for employees with 2026 coverage (projected_2026_premium > 0)
                if 'projected_2026_premium' in tier_employees.columns:
                    renewal_total = tier_employees['projected_2026_premium'].fillna(0).infer_objects(copy=False)
                    employees_with_renewal = tier_employees[renewal_total > 0]
                    tier_gap_renewal[tier_name] = employees_with_renewal['gap_insurance_monthly'].fillna(0).infer_objects(copy=False).sum()
                else:
                    tier_gap_renewal[tier_name] = tier_gap_current.get(tier_name, 0)

            total_gap = sum(tier_gap_renewal.values())

            # Get per-tier fixed gap rates (for footnote)
            for code in ['EE', 'ES', 'EC', 'F']:
                tier_employees = census_df[census_df['family_status'] == code]
                gap_vals = tier_employees['gap_insurance_monthly'].dropna()
                gap_vals = gap_vals[gap_vals > 0]
                gap_rates_by_tier[code] = float(gap_vals.iloc[0]) if len(gap_vals) > 0 else 0

    # Build tier rows HTML with dynamic plan columns
    tier_rows = ""
    for tier in tiers:
        code = tier_info[tier]['code']
        count = tier_counts.get(tier, 0)
        avg_age = tier_avg_age.get(tier, 0)

        # Current and Renewal base premiums (without gap)
        current_base = tier_current.get(tier, 0)
        renewal_base = tier_renewal.get(tier, 0)

        # Gap amounts for this tier (different for current vs renewal)
        gap_current = tier_gap_current.get(tier, 0)
        gap_renewal = tier_gap_renewal.get(tier, 0)

        # Total includes gap insurance if present
        current_val = current_base + gap_current
        renewal_val = renewal_base + gap_renewal

        # Get per-employee rates directly from census (not calculated averages)
        gap_rate_per_ee = gap_rates_by_tier.get(code, 0)
        current_base_per_ee = tier_current_rate_per_ee.get(tier, 0)
        renewal_base_per_ee = tier_renewal_rate_per_ee.get(tier, 0)

        # Format breakdown text with PER-EMPLOYEE rates
        if has_gap_data and gap_rate_per_ee > 0:
            # With gap: show base rate + gap rate
            current_breakdown = f'<br><span class="gap-breakdown">${current_base_per_ee:,.0f} + ${gap_rate_per_ee:,.0f} gap</span>'
            renewal_breakdown = f'<br><span class="gap-breakdown">${renewal_base_per_ee:,.0f} + ${gap_rate_per_ee:,.0f} gap</span>'
        elif current_base_per_ee > 0:
            # Without gap: show per-employee rate
            current_breakdown = f'<br><span class="gap-breakdown">${current_base_per_ee:,.0f}</span>'
            renewal_breakdown = f'<br><span class="gap-breakdown">${renewal_base_per_ee:,.0f}</span>'
        else:
            current_breakdown = ""
            renewal_breakdown = ""

        # Build dynamic plan columns for this tier
        plan_cols_html = ""
        for col in plan_columns:
            if col['type'] == 'has':
                totals_data = hap_totals.get(col['totals_key'], {})
            else:  # sedera
                totals_data = sedera_totals.get(col['totals_key'], {})

            tier_total = totals_data.get('by_tier', {}).get(code, {}).get('total', 0)
            rate_range = totals_data.get('rate_ranges', {}).get(code, {'min': 0, 'max': 0})

            # Format rate range
            range_str = f"${rate_range['min']:,.0f}-${rate_range['max']:,.0f}" if rate_range['min'] > 0 else ""

            plan_cols_html += f'<td><span style="font-weight: 600;">{fmt(tier_total)}</span><br><span class="rate-range">{range_str}</span></td>'

        # Format employee count with average age
        age_suffix = f" · avg age {avg_age}" if avg_age > 0 else ""
        tier_rows += f'<tr><td>{tier}<br><span class="tier-subtitle">{count} employees{age_suffix}</span></td><td><span style="font-weight: 600;">{fmt(current_val)}</span>{current_breakdown}</td><td><span style="font-weight: 600;">{fmt(renewal_val)}</span>{renewal_breakdown}</td>{plan_cols_html}</tr>'

    # Calculate total premiums by summing tier totals (which already include gap)
    total_premium = {}

    # Sum tier totals for Current and Renewal (using appropriate gap for each)
    total_current = sum(tier_current.get(t, 0) + tier_gap_current.get(t, 0) for t in tiers)
    total_renewal = sum(tier_renewal.get(t, 0) + tier_gap_renewal.get(t, 0) for t in tiers)

    total_premium[current_key] = total_current
    total_premium[renewal_key] = total_renewal

    # Add totals for each plan column
    for col in plan_columns:
        if col['type'] == 'has':
            total_premium[col['key']] = hap_totals.get(col['totals_key'], {}).get('total', 0)
        else:  # sedera
            total_premium[col['key']] = sedera_totals.get(col['totals_key'], {}).get('total', 0)

    # Calculate admin fees and preventive care totals
    admin_fee_totals = {}
    for col in plan_columns:
        admin_fee_totals[col['key']] = calculate_admin_fee_total(col['admin_fee'], total_employees)

    preventive_total = 0
    if config['preventive_enabled']:
        preventive_total = calculate_preventive_care_total(
            config['preventive_include_dpc'],
            config['preventive_employee_count']
        )

    # Calculate grand totals (premium + admin fee + preventive)
    grand_totals = {}
    for col in plan_columns:
        grand_totals[col['key']] = total_premium.get(col['key'], 0) + admin_fee_totals.get(col['key'], 0) + preventive_total

    # Calculate annual totals (using grand totals for plan columns)
    annual_totals = {current_key: total_premium[current_key] * 12, renewal_key: total_premium[renewal_key] * 12}
    for col in plan_columns:
        annual_totals[col['key']] = grand_totals[col['key']] * 12

    # Calculate savings vs renewal (annual) for all plan columns
    renewal_annual = annual_totals.get(renewal_key, 0)
    plan_savings = {}
    for col in plan_columns:
        plan_annual = annual_totals.get(col['key'], 0)
        if renewal_annual > 0 and plan_annual > 0:
            savings_amount = renewal_annual - plan_annual
            savings_pct = (savings_amount / renewal_annual) * 100
            plan_savings[col['key']] = {'amount': savings_amount, 'pct': savings_pct}
        else:
            plan_savings[col['key']] = {'amount': 0, 'pct': 0}

    # Asterisk for Total Monthly row (only if gap data exists)
    total_monthly_asterisk = "*" if has_gap_data else ""

    # Build dynamic header columns HTML
    header_cols_html = ""
    for col in plan_columns:
        header_cols_html += f'<th class="{col["style_class"]}">{col["label"]}<br><span class="header-subtitle">{col["subtitle"]}</span></th>'

    # Build dynamic total premium row cells
    total_premium_cells = ""
    for col in plan_columns:
        total_premium_cells += f'<td style="font-weight: 700;">{fmt(total_premium.get(col["key"], 0))}</td>'

    # Build admin fee row (only if any admin fee is > 0)
    has_admin_fees = any(col['admin_fee'] > 0 for col in plan_columns)
    admin_fee_row = ""
    if has_admin_fees:
        admin_fee_cells = ""
        for col in plan_columns:
            admin_fee_cells += f'<td>{fmt(admin_fee_totals.get(col["key"], 0))}<br><span class="rate-range">${col["admin_fee"]:.2f} × {total_employees} PEPM</span></td>'
        admin_fee_row = f'<tr><td>Admin Fee</td><td></td><td></td>{admin_fee_cells}</tr>'

    # Build preventive care row (only if enabled)
    preventive_row = ""
    if config['preventive_enabled'] and preventive_total > 0:
        rate_label = f"${PREVENTIVE_CARE_RATE_WITH_DPC:.0f}" if config['preventive_include_dpc'] else f"${PREVENTIVE_CARE_RATE_WITHOUT_DPC:.0f}"
        dpc_label = "with DPC" if config['preventive_include_dpc'] else "without DPC"
        preventive_cells = ""
        for col in plan_columns:
            preventive_cells += f'<td>{fmt(preventive_total)}<br><span class="rate-range">{rate_label}/mo × {config["preventive_employee_count"]} EEs</span></td>'
        preventive_row = f'<tr><td>Preventive Care<br><span class="tier-subtitle">{dpc_label}</span></td><td></td><td></td>{preventive_cells}</tr>'

    # Build grand total row (only if there are add-ons)
    grand_total_row = ""
    if has_admin_fees or (config['preventive_enabled'] and preventive_total > 0):
        grand_total_cells = ""
        for col in plan_columns:
            grand_total_cells += f'<td style="font-weight: 700;">{fmt(grand_totals.get(col["key"], 0))}</td>'
        grand_total_row = f'<tr class="total-row"><td style="font-weight: 700;">Grand Total</td><td></td><td></td>{grand_total_cells}</tr>'

    # Build annual total row cells
    annual_cells = ""
    for col in plan_columns:
        annual_cells += f'<td style="font-weight: 600;">{fmt(annual_totals.get(col["key"], 0))}</td>'

    # Build savings row cells
    savings_cells = ""
    for col in plan_columns:
        savings_data = plan_savings.get(col['key'], {'amount': 0, 'pct': 0})
        color = fmt_savings(savings_data['amount'], savings_data['pct'])[1]
        text = fmt_savings(savings_data['amount'], savings_data['pct'])[0]
        pct = savings_data.get('pct', 0)
        savings_cells += f'<td style="color: {color}; font-weight: 600;">{text}<br><span style="font-size: 12px;">({pct:.0f}%)</span></td>'

    # Build Annual Total row
    annual_row = f'<tr><td style="font-weight: 600;">Annual Total</td><td style="font-weight: 600;">{fmt(annual_totals.get(current_key, 0))}</td><td style="font-weight: 600;">{fmt(annual_totals.get(renewal_key, 0))}</td>{annual_cells}</tr>'

    # Build Savings row
    savings_row = f'<tr><td style="font-weight: 600;">Savings vs Renewal</td><td></td><td style="color: #6b7280;">—</td>{savings_cells}</tr>'

    # Build Total Monthly row
    total_monthly_row = f'<tr class="total-row"><td style="font-weight: 700;">Total Monthly{total_monthly_asterisk}</td><td style="font-weight: 700;">{fmt(total_premium.get(current_key, 0))}{total_monthly_asterisk}</td><td style="font-weight: 700;">{fmt(total_premium.get(renewal_key, 0))}{total_monthly_asterisk}</td>{total_premium_cells}</tr>'

    # Build header row
    header_row = f'<tr><th style="text-align: left; background: white;">Coverage type</th><th class="col-header-current">{current_key}</th><th class="col-header-renewal">{renewal_key}</th>{header_cols_html}</tr>'

    # Custom HTML table with dynamic columns - all rows pre-built as single-line strings
    table_html = f"""<style>
.scenario-table {{ width: 100%; border-collapse: collapse; font-family: 'Poppins', sans-serif; margin-bottom: 16px; }}
.scenario-table th {{ padding: 12px 16px; text-align: center; font-weight: 600; font-size: 14px; border-bottom: 2px solid #e5e7eb; }}
.scenario-table td {{ padding: 12px 16px; text-align: center; font-family: 'Inter', sans-serif; font-size: 16px; border-bottom: 1px solid #e5e7eb; }}
.scenario-table td:first-child {{ text-align: left; font-family: 'Poppins', sans-serif; font-weight: 500; color: #101828; }}
.scenario-table .total-row td {{ font-weight: 700; border-top: 2px solid #101828; padding-top: 16px; }}
.col-header-current {{ background: #E8F1FD; color: #0047AB; border-left: 4px solid #0047AB; }}
.col-header-renewal {{ background: #fef2f2; color: #82181a; border-left: 4px solid #ffa2a2; }}
.col-header-has {{ background: #ecfdf5; color: #047857; }}
.col-header-sedera {{ background: #E8F1FD; color: #003d91; }}
.header-subtitle {{ font-size: 12px; font-weight: 400; color: #6a7282; }}
.tier-subtitle {{ font-size: 12px; font-weight: 400; color: #6a7282; }}
.rate-range {{ font-size: 12px; font-weight: 400; color: #6a7282; }}
.gap-breakdown {{ font-size: 12px; font-weight: 400; color: #6a7282; }}
.footnote-text {{ font-size: 12px; color: #6a7282; margin-top: 8px; }}
</style>
<table class="scenario-table">
<thead>{header_row}</thead>
<tbody>{tier_rows}{total_monthly_row}{preventive_row}{admin_fee_row}{grand_total_row}{annual_row}{savings_row}</tbody>
</table>"""

    st.markdown(table_html, unsafe_allow_html=True)

    # Footer row with download buttons
    footer_col1, footer_col2, footer_col3 = st.columns([2.5, 1, 1])

    with footer_col1:
        # Build footnote with gap breakdown if gap data exists
        if has_gap_data and total_gap > 0:
            gap_footnote = f"* Includes ${total_gap:,.0f}/mo gap coverage "
            gap_footnote += f"(EE: ${gap_rates_by_tier.get('EE', 0):,.0f} | "
            gap_footnote += f"ES: ${gap_rates_by_tier.get('ES', 0):,.0f} | "
            gap_footnote += f"EC: ${gap_rates_by_tier.get('EC', 0):,.0f} | "
            gap_footnote += f"F: ${gap_rates_by_tier.get('F', 0):,.0f})"
            st.markdown(f"""
            <p class="footnote-text">{gap_footnote}</p>
            """, unsafe_allow_html=True)

        st.markdown("""
        <p style="font-size: 13px; color: #6b7280;">
            Totals calculated from census data. HAS rates based on employee age and family status.
        </p>
        """, unsafe_allow_html=True)

    with footer_col2:
        # CSV download button for detailed rate data (includes aggregate family rates)
        if db is not None and census_df is not None and not census_df.empty:
            csv_df = generate_scenario_rates_csv(census_df, coop_rates_df, sedera_rates_df, config, dependents_df)
            if csv_df is not None and not csv_df.empty:
                csv_data = csv_df.to_csv(index=False)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                client_name = st.session_state.get('client_name', '').strip()
                if client_name:
                    safe_name = client_name.replace(' ', '_').replace('/', '-')
                    csv_filename = f"plan_rate_details_{safe_name}_{timestamp}.csv"
                else:
                    csv_filename = f"plan_rate_details_{timestamp}.csv"
                st.download_button(
                    label="📥 Rate details CSV",
                    data=csv_data,
                    file_name=csv_filename,
                    mime="text/csv",
                    help="Download employee census with current, renewal, and cooperative plan rates"
                )

    with footer_col3:
        # PowerPoint download button for comparison table slide
        if census_df is not None and not census_df.empty:
            # Build CooperativeHealthData from current table data
            from pptx_cooperative_health import TierData, PlanColumnData, PlanColumnTotals

            # Build PPTX plan columns from UI plan_columns (1:1 mapping)
            pptx_plan_columns = []
            for col in plan_columns:
                pptx_plan_columns.append(PlanColumnTotals(
                    key=col['key'],
                    label=col['label'],
                    subtitle=col['subtitle'],
                    plan_type=col['type'],
                    monthly_total=total_premium.get(col['key'], 0),
                    annual_total=annual_totals.get(col['key'], 0),
                    savings_amount=plan_savings.get(col['key'], {}).get('amount', 0),
                    savings_pct=plan_savings.get(col['key'], {}).get('pct', 0),
                    admin_fee_pepm=col.get('admin_fee', 0),
                    admin_fee_total=admin_fee_totals.get(col['key'], 0),
                ))

            pptx_tiers = []
            for tier_name, info in tier_info.items():
                tier_code = info['code']

                # Base premiums (without gap)
                current_base = tier_current.get(tier_name, 0) or 0
                renewal_base = tier_renewal.get(tier_name, 0) or 0
                gap_current = tier_gap_current.get(tier_name, 0) or 0
                gap_renewal = tier_gap_renewal.get(tier_name, 0) or 0
                count = tier_counts.get(tier_name, 0) or 0
                avg_age = tier_avg_age.get(tier_name, 0) or 0

                # Totals include gap insurance (different gap for current vs renewal)
                current_total = current_base + gap_current
                renewal_total = renewal_base + gap_renewal

                # Get per-employee rates directly from census (not calculated averages)
                current_rate_per_ee = tier_current_rate_per_ee.get(tier_name, 0)
                renewal_rate_per_ee = tier_renewal_rate_per_ee.get(tier_name, 0)
                gap_rate_per_ee = gap_rates_by_tier.get(tier_code, 0)

                # Build plan column data for this tier (1:1 mapping from UI)
                tier_plan_columns = {}
                for col in plan_columns:
                    if col['type'] == 'has':
                        totals_data = hap_totals.get(col['totals_key'], {})
                    else:  # sedera
                        totals_data = sedera_totals.get(col['totals_key'], {})

                    tier_total = totals_data.get('by_tier', {}).get(tier_code, {}).get('total', 0)
                    rate_range = totals_data.get('rate_ranges', {}).get(tier_code, {'min': 0, 'max': 0})

                    tier_plan_columns[col['key']] = PlanColumnData(
                        key=col['key'],
                        label=col['label'],
                        subtitle=col['subtitle'],
                        plan_type=col['type'],
                        total=tier_total,
                        min_rate=rate_range.get('min', 0),
                        max_rate=rate_range.get('max', 0),
                    )

                pptx_tiers.append(TierData(
                    name=tier_name,
                    code=tier_code,
                    current_total=current_total,
                    current_base=current_base,
                    current_gap=gap_current,
                    renewal_total=renewal_total,
                    renewal_base=renewal_base,
                    renewal_gap=gap_renewal,
                    plan_columns=tier_plan_columns,
                    employee_count=count,
                    avg_age=avg_age,
                    current_rate_per_ee=current_rate_per_ee,
                    renewal_rate_per_ee=renewal_rate_per_ee,
                    gap_rate_per_ee=gap_rate_per_ee,
                ))

            # Use the SAME values as UI (total_premium, annual_totals, plan_savings)
            # to ensure PPTX matches the displayed table exactly
            monthly_current = total_premium.get(current_key, 0)
            monthly_renewal = total_premium.get(renewal_key, 0)
            annual_current = annual_totals.get(current_key, 0)
            annual_renewal = annual_totals.get(renewal_key, 0)

            # Determine preventive care rate based on DPC setting
            preventive_rate = PREVENTIVE_CARE_RATE_WITH_DPC if config['preventive_include_dpc'] else PREVENTIVE_CARE_RATE_WITHOUT_DPC

            pptx_data = CooperativeHealthData(
                tiers=pptx_tiers,
                plan_columns=pptx_plan_columns,
                total_current=monthly_current,
                total_renewal=monthly_renewal,
                annual_current=annual_current,
                annual_renewal=annual_renewal,
                has_gap=has_gap_data,
                total_gap_monthly=total_gap,
                gap_rate_ee=gap_rates_by_tier.get('EE', 0),
                gap_rate_es=gap_rates_by_tier.get('ES', 0),
                gap_rate_ec=gap_rates_by_tier.get('EC', 0),
                gap_rate_f=gap_rates_by_tier.get('F', 0),
                # Preventive care
                has_preventive=config['preventive_enabled'] and preventive_total > 0,
                preventive_total=preventive_total,
                preventive_rate=preventive_rate,
                preventive_employee_count=config['preventive_employee_count'],
                preventive_include_dpc=config['preventive_include_dpc'],
                # Admin fees
                has_admin_fees=has_admin_fees,
                client_name=st.session_state.get('client_name', ''),
            )

            pptx_buffer = generate_cooperative_health_slide(pptx_data)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            client_name = st.session_state.get('client_name', '').strip()
            if client_name:
                safe_name = client_name.replace(' ', '_').replace('/', '-')
                filename = f"cooperative_health_{safe_name}_{timestamp}.pptx"
            else:
                filename = f"cooperative_health_{timestamp}.pptx"

            st.download_button(
                label="📊 Download slide",
                data=pptx_buffer,
                file_name=filename,
                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                help="Download PowerPoint slide with comparison table"
            )


# =============================================================================
# AGE BRACKET TABLE
# =============================================================================

def render_age_bracket_table(data: DashboardData, db: DatabaseConnection = None, census_df: pd.DataFrame = None):
    """
    Render the Average Rates Across the Workforce table grouped by age bracket.

    Shows individual ee_rate averages (not tier premiums) for each age group.
    """
    st.markdown("""
    <p style="font-size: 20px; font-weight: 500; color: #101828; margin-bottom: 4px;">Average rates across the workforce*</p>
    <p style="font-size: 16px; color: #4a5565; margin-bottom: 24px;">Individual rates by age group (excludes family multipliers)</p>
    """, unsafe_allow_html=True)

    # Calculate age bracket costs (cached)
    coop_rates_df = load_cooperative_rate_table(_db_available=db is not None)
    bracket_costs = calculate_age_bracket_costs(
        census_df,
        multi_metal_results=data.multi_metal_results,
        cooperative_ratio=COOPERATIVE_CONFIG['default_discount_ratio'],
        coop_rates_df=coop_rates_df
    )

    # Get DPC cost from constants
    dpc_cost = COOPERATIVE_CONFIG['dpc_monthly_cost']

    # Define columns and keys
    current_key = f"Current {CURRENT_PLAN_YEAR}"
    renewal_key = f"Renewal {RENEWAL_PLAN_YEAR}"
    scenarios = [current_key, renewal_key, "ICHRA Bronze", "ICHRA Silver", "ICHRA Gold", "Cooperative"]

    # Helper to format currency or show --
    def fmt(val):
        return f"${val:,.0f}" if val and val > 0 else "--"

    # Build age bracket rows - only show brackets with employees
    age_brackets_ordered = ["18-29", "30-39", "40-49", "50-59", "60-64", "65+"]
    bracket_rows = ""

    # Calculate totals using actual sums from the data
    totals = {s: 0 for s in scenarios}

    for bracket in age_brackets_ordered:
        bracket_data = bracket_costs.get(bracket, {})
        count = bracket_data.get('count', 0)

        if count == 0:
            continue  # Skip empty brackets

        # Add to totals using actual sums (not average * count)
        for scenario in scenarios:
            sum_key = f"{scenario}_sum"
            sum_val = bracket_data.get(sum_key, 0)
            if sum_val > 0:
                totals[scenario] += sum_val

        # Find lowest ICHRA cost for highlighting
        ichra_vals = [bracket_data.get(s, 0) for s in ["ICHRA Bronze", "ICHRA Silver", "ICHRA Gold", "Cooperative"]]
        min_cost = min([v for v in ichra_vals if v > 0]) if any(v > 0 for v in ichra_vals) else 0

        bracket_rows += f'''<tr><td>{bracket}<br><span class="tier-subtitle">{count} employees</span></td>'''
        for scenario in scenarios:
            val = bracket_data.get(scenario, 0)
            is_lowest = val > 0 and val == min_cost and scenario in ["ICHRA Bronze", "ICHRA Silver", "ICHRA Gold", "Cooperative"]
            css_class = ' class="lowest-cost"' if is_lowest else ''
            bracket_rows += f"<td{css_class}>{fmt(val)}</td>"
        bracket_rows += "</tr>"

    # Calculate vs Renewal and savings percentage
    renewal_total = totals.get(renewal_key, 0)

    def fmt_vs_renewal(scenario_total):
        if renewal_total <= 0 or scenario_total <= 0:
            return ("", "#6b7280")
        diff = renewal_total - scenario_total
        if diff > 0:
            return (f"${diff:,.0f}", "#00a63e")  # Savings (green)
        elif diff < 0:
            return (f"${abs(diff):,.0f}", "#dc2626")  # Cost increase (red) - no sign needed, red indicates increase
        else:
            return ("—", "#6b7280")

    def fmt_savings_pct(scenario_total):
        if renewal_total <= 0 or scenario_total <= 0:
            return ("", "#6b7280")
        diff = renewal_total - scenario_total
        pct = (diff / renewal_total) * 100
        if pct > 0:
            return (f"{pct:.0f}%", "#00a63e")
        elif pct < 0:
            return ("—", "#6b7280")  # Don't show negative percentage
        else:
            return ("—", "#6b7280")

    # Custom HTML table (matching scenario table style)
    st.markdown(f"""
    <style>
        .age-bracket-table {{
            width: 100%;
            border-collapse: collapse;
            font-family: 'Poppins', sans-serif;
            margin-bottom: 16px;
        }}
        .age-bracket-table th {{
            padding: 12px 16px;
            text-align: center;
            font-weight: 600;
            font-size: 14px;
            border-bottom: 2px solid #e5e7eb;
        }}
        .age-bracket-table td {{
            padding: 12px 16px;
            text-align: center;
            font-family: 'Inter', sans-serif;
            font-size: 16px;
            border-bottom: 1px solid #e5e7eb;
        }}
        .age-bracket-table td:first-child {{
            text-align: left;
            font-family: 'Poppins', sans-serif;
            font-weight: 500;
            color: #101828;
        }}
        .age-bracket-table .total-row td {{
            font-weight: 700;
            border-top: 2px solid #101828;
            padding-top: 16px;
        }}
    </style>

    <table class="age-bracket-table">
        <thead>
            <tr>
                <th style="text-align: left; background: white;"></th>
                <th class="col-header-current">
                    {current_key}<br>
                    <span class="header-subtitle">(for reference)</span>
                </th>
                <th class="col-header-renewal">
                    {renewal_key}<br>
                    <span class="header-subtitle">(for reference)</span>
                </th>
                <th class="col-header-bronze">
                    ICHRA Bronze<br>
                    <span class="header-subtitle">{data.metal_av.get('Bronze', 60):.1f}% AV</span>
                </th>
                <th class="col-header-silver">
                    ICHRA Silver<br>
                    <span class="header-subtitle">{data.metal_av.get('Silver', 70):.1f}% AV</span>
                </th>
                <th class="col-header-gold">
                    ICHRA Gold<br>
                    <span class="header-subtitle">{data.metal_av.get('Gold', 80):.1f}% AV</span>
                </th>
                <th class="col-header-coop">
                    Cooperative<br>
                    <span class="header-subtitle">Health Access + DPC (${dpc_cost}/mo)</span>
                </th>
            </tr>
        </thead>
        <tbody>
            {bracket_rows}
            <tr class="total-row">
                <td style="font-weight: 700;">Total premium</td>
                <td style="font-weight: 700;">{fmt(totals.get(current_key, 0))}</td>
                <td style="font-weight: 700;">{fmt(totals.get(renewal_key, 0))}</td>
                <td style="font-weight: 700;">{fmt(totals.get('ICHRA Bronze', 0))}</td>
                <td style="font-weight: 700;">{fmt(totals.get('ICHRA Silver', 0))}</td>
                <td style="font-weight: 700;">{fmt(totals.get('ICHRA Gold', 0))}</td>
                <td style="font-weight: 700; color: #0d542b;">{fmt(totals.get('Cooperative', 0))}</td>
            </tr>
            <tr>
                <td style="font-weight: 600;">vs Renewal</td>
                <td></td>
                <td style="color: #6b7280;">—</td>
                <td style="color: {fmt_vs_renewal(totals.get('ICHRA Bronze', 0))[1]}; font-weight: 600;">{fmt_vs_renewal(totals.get('ICHRA Bronze', 0))[0]}</td>
                <td style="color: {fmt_vs_renewal(totals.get('ICHRA Silver', 0))[1]}; font-weight: 600;">{fmt_vs_renewal(totals.get('ICHRA Silver', 0))[0]}</td>
                <td style="color: {fmt_vs_renewal(totals.get('ICHRA Gold', 0))[1]}; font-weight: 600;">{fmt_vs_renewal(totals.get('ICHRA Gold', 0))[0]}</td>
                <td style="color: {fmt_vs_renewal(totals.get('Cooperative', 0))[1]}; font-weight: 600;">{fmt_vs_renewal(totals.get('Cooperative', 0))[0]}</td>
            </tr>
            <tr>
                <td style="font-weight: 600;">Premium savings</td>
                <td></td>
                <td></td>
                <td style="color: {fmt_savings_pct(totals.get('ICHRA Bronze', 0))[1]}; font-weight: 600;">{fmt_savings_pct(totals.get('ICHRA Bronze', 0))[0]}</td>
                <td style="color: {fmt_savings_pct(totals.get('ICHRA Silver', 0))[1]}; font-weight: 600;">{fmt_savings_pct(totals.get('ICHRA Silver', 0))[0]}</td>
                <td style="color: {fmt_savings_pct(totals.get('ICHRA Gold', 0))[1]}; font-weight: 600;">{fmt_savings_pct(totals.get('ICHRA Gold', 0))[0]}</td>
                <td style="color: {fmt_savings_pct(totals.get('Cooperative', 0))[1]}; font-weight: 700; font-size: 18px;">{fmt_savings_pct(totals.get('Cooperative', 0))[0]}</td>
            </tr>
        </tbody>
    </table>
    """, unsafe_allow_html=True)

    # Footer note
    st.markdown("""
    <p style="font-size: 13px; color: #6b7280; margin-top: 8px;">
        * Rates are calculated at the individual level based on state, rating area, and age.
        Averages are calculated from these individual rates by age group.
    </p>
    """, unsafe_allow_html=True)


# =============================================================================
# MARKETPLACE RATES TABLE (by Coverage Type)
# =============================================================================

def render_marketplace_rates_table(data: DashboardData, db: DatabaseConnection = None, census_df: pd.DataFrame = None, dependents_df: pd.DataFrame = None):
    """
    Render the Marketplace Rates by Coverage Type table.

    Shows Bronze, Silver, Gold columns with rate ranges and totals by family status tier.
    Uses aggregate family premiums with ACA 3-child rule for ES/EC/F tiers.
    """
    st.markdown("""
    <p style="font-size: 20px; font-weight: 500; color: #101828; margin-bottom: 4px;">Marketplace rates by coverage type</p>
    <p style="font-size: 16px; color: #4a5565; margin-bottom: 24px;">Lowest cost plans by metal level</p>
    """, unsafe_allow_html=True)

    # Calculate tier marketplace costs with aggregate family premiums
    tier_costs = calculate_tier_marketplace_costs(
        census_df,
        multi_metal_results=data.multi_metal_results,
        db=db,
        dependents_df=dependents_df
    )

    # Get totals for comparison
    totals = tier_costs.get('totals', {})
    tiers_data = tier_costs.get('tiers', {})

    # Get renewal total for savings calculation
    renewal_monthly = data.renewal_premium or 0

    # Helper to format currency or show --
    def fmt(val):
        return f"${val:,.0f}" if val and val > 0 else "--"

    def fmt_range(min_val, max_val):
        if min_val > 0 and max_val > 0:
            if min_val == max_val:
                return f"${min_val:,.0f}"
            return f"${min_val:,.0f}–${max_val:,.0f}"
        return "--"

    # Calculate vs Renewal and savings percentage
    def fmt_vs_renewal(metal_monthly):
        if renewal_monthly <= 0 or metal_monthly <= 0:
            return ("—", "#6b7280")
        diff = renewal_monthly - metal_monthly
        if diff > 0:
            return (f"${diff:,.0f}", "#00a63e")  # Savings (green)
        elif diff < 0:
            return (f"${abs(diff):,.0f}", "#dc2626")  # Cost increase (red) - no sign needed, red indicates increase
        else:
            return ("—", "#6b7280")

    def fmt_savings_pct(metal_monthly):
        if renewal_monthly <= 0 or metal_monthly <= 0:
            return ("", "#6b7280")
        diff = renewal_monthly - metal_monthly
        pct = (diff / renewal_monthly) * 100
        if pct > 0:
            return (f"{pct:.0f}%", "#00a63e")
        else:
            return ("—", "#6b7280")

    # Get totals for footer rows (need these first to determine lowest cost column)
    bronze_monthly = totals.get('Bronze', {}).get('monthly', 0)
    silver_monthly = totals.get('Silver', {}).get('monthly', 0)
    gold_monthly = totals.get('Gold', {}).get('monthly', 0)

    # Build tier rows
    tier_order = ['Employee Only', 'Employee + Spouse', 'Employee + Children', 'Family']
    tier_rows = ""

    for tier_name in tier_order:
        tier_data = tiers_data.get(tier_name)
        if not tier_data:
            continue

        count = tier_data.get('count', 0)
        avg_age = tier_data.get('avg_age', 0)
        if count == 0:
            continue

        # Format employee count with average age
        age_suffix = f" · avg age {avg_age}" if avg_age > 0 else ""
        tier_rows += f'<tr><td style="text-align: left; font-weight: 500; color: #101828;">{tier_name}<br><span style="font-size: 12px; color: #6a7282; font-weight: 400;">{count} employee{"s" if count != 1 else ""}{age_suffix}</span></td>'

        for metal in ['Bronze', 'Silver', 'Gold']:
            metal_data = tier_data.get(metal, {})
            min_rate = metal_data.get('min', 0)
            max_rate = metal_data.get('max', 0)
            total = metal_data.get('total', 0)
            tier_rows += f'<td><span style="font-size: 16px; font-weight: 600;">{fmt(total)}</span><br><span style="font-size: 12px; color: #6a7282;">{fmt_range(min_rate, max_rate)}</span></td>'

        tier_rows += "</tr>"

    # Build the HTML table
    st.markdown(f"""
    <style>
        .marketplace-rates-table {{
            width: 100%;
            border-collapse: collapse;
            font-family: 'Poppins', sans-serif;
            margin-bottom: 16px;
        }}
        .marketplace-rates-table th {{
            padding: 12px 16px;
            text-align: center;
            font-weight: 600;
            font-size: 14px;
            border-bottom: 2px solid #e5e7eb;
        }}
        .marketplace-rates-table td {{
            padding: 12px 16px;
            text-align: center;
            font-family: 'Inter', sans-serif;
            font-size: 16px;
            border-bottom: 1px solid #e5e7eb;
        }}
        .marketplace-rates-table td:first-child {{
            text-align: left;
            font-family: 'Poppins', sans-serif;
        }}
        .marketplace-rates-table .total-row td {{
            font-weight: 700;
            border-top: 2px solid #101828;
            padding-top: 16px;
        }}
        .marketplace-rates-table .renewal-row td {{
            background: #E5E7EB;
            font-style: italic;
            color: #374151;
            font-weight: 600;
            text-align: center;
            border-top: 1px solid #d1d5db;
            border-bottom: 1px solid #d1d5db;
        }}
        .col-header-bronze {{
            background: #FEF3E2;
            color: #92400e;
        }}
        .col-header-silver {{
            background: #E8F1FD;
            color: #003d91;
        }}
        .col-header-gold {{
            background: #FEF9C3;
            color: #854d0e;
        }}
    </style>

    <table class="marketplace-rates-table">
        <thead>
            <tr>
                <th style="text-align: left; background: white;">Coverage Type</th>
                <th class="col-header-bronze">
                    Bronze<br>
                    <span style="font-size: 12px; font-weight: 400; color: #b45309;">{data.metal_av.get('Bronze', 60):.0f}% AV</span>
                </th>
                <th class="col-header-silver">
                    Silver<br>
                    <span style="font-size: 12px; font-weight: 400; color: #6b7280;">{data.metal_av.get('Silver', 70):.0f}% AV</span>
                </th>
                <th class="col-header-gold">
                    Gold<br>
                    <span style="font-size: 12px; font-weight: 400; color: #a16207;">{data.metal_av.get('Gold', 80):.0f}% AV</span>
                </th>
            </tr>
        </thead>
        <tbody>
            {tier_rows}
            <tr class="total-row">
                <td style="font-weight: 700;">Total Monthly</td>
                <td style="font-weight: 700;">{fmt(bronze_monthly)}</td>
                <td style="font-weight: 700;">{fmt(silver_monthly)}</td>
                <td style="font-weight: 700;">{fmt(gold_monthly)}</td>
            </tr>
            <tr class="renewal-row">
                <td colspan="4" style="text-align: center;">vs a renewal of {fmt(renewal_monthly)}/mo:</td>
            </tr>
            <tr>
                <td style="font-weight: 600;">Monthly Savings</td>
                <td style="color: {fmt_vs_renewal(bronze_monthly)[1]}; font-weight: 600;">{fmt_vs_renewal(bronze_monthly)[0]}</td>
                <td style="color: {fmt_vs_renewal(silver_monthly)[1]}; font-weight: 600;">{fmt_vs_renewal(silver_monthly)[0]}</td>
                <td style="color: {fmt_vs_renewal(gold_monthly)[1]}; font-weight: 600;">{fmt_vs_renewal(gold_monthly)[0]}</td>
            </tr>
            <tr>
                <td style="font-weight: 600;">Premium Savings %</td>
                <td style="color: {fmt_savings_pct(bronze_monthly)[1]}; font-weight: 600;">{fmt_savings_pct(bronze_monthly)[0]}</td>
                <td style="color: {fmt_savings_pct(silver_monthly)[1]}; font-weight: 600;">{fmt_savings_pct(silver_monthly)[0]}</td>
                <td style="color: {fmt_savings_pct(gold_monthly)[1]}; font-weight: 600;">{fmt_savings_pct(gold_monthly)[0]}</td>
            </tr>
        </tbody>
    </table>
    """, unsafe_allow_html=True)

    # Footer with note and download buttons
    footer_col1, footer_col2, footer_col3 = st.columns([3, 1, 1])

    with footer_col1:
        st.markdown("""
        <p style="font-size: 13px; color: #6b7280; margin-top: 8px;">
            Rate ranges show lowest cost plan rates from youngest to oldest age band within each coverage tier.
            Totals represent cost if all employees selected the lowest-cost plan in each metal level.
        </p>
        """, unsafe_allow_html=True)

    with footer_col2:
        # CSV download button for marketplace rate details (includes aggregate family rates)
        if census_df is not None and not census_df.empty and data.multi_metal_results:
            csv_df = generate_marketplace_rates_csv(census_df, data.multi_metal_results, dependents_df, db)
            if csv_df is not None and not csv_df.empty:
                csv_data = csv_df.to_csv(index=False)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                client_name = st.session_state.get('client_name', '').strip()
                if client_name:
                    safe_name = client_name.replace(' ', '_').replace('/', '-')
                    csv_filename = f"marketplace_rate_details_{safe_name}_{timestamp}.csv"
                else:
                    csv_filename = f"marketplace_rate_details_{timestamp}.csv"
                st.download_button(
                    label="📥 Rate details CSV",
                    data=csv_data,
                    file_name=csv_filename,
                    mime="text/csv",
                    help="Download employee census with Bronze, Silver, Gold plan names and rates"
                )

    with footer_col3:
        # PowerPoint export button
        if census_df is not None and not census_df.empty and tier_costs:
            if st.button("📊 Export PPTX", key="marketplace_rates_pptx", help="Download as PowerPoint slide"):
                try:
                    from pptx_marketplace_rates import MarketplaceRatesData, generate_marketplace_rates_slide

                    # Build data for slide
                    pptx_data = MarketplaceRatesData.from_dashboard_data(
                        tier_costs=tier_costs,
                        renewal_monthly=renewal_monthly,
                        metal_av=data.metal_av,
                        client_name=st.session_state.get('client_name', '')
                    )

                    # Generate PowerPoint
                    pptx_buffer = generate_marketplace_rates_slide(pptx_data)

                    # Build filename
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    client_name = st.session_state.get('client_name', '').strip()
                    if client_name:
                        safe_name = client_name.replace(' ', '_').replace('/', '-')
                        filename = f"marketplace_rates_{safe_name}_{timestamp}.pptx"
                    else:
                        filename = f"marketplace_rates_{timestamp}.pptx"

                    st.download_button(
                        label="⬇️ Download PPTX",
                        data=pptx_buffer,
                        file_name=filename,
                        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                        key="marketplace_rates_pptx_download"
                    )
                except Exception as e:
                    st.error(f"Error generating PowerPoint: {str(e)}")


# =============================================================================
# EMPLOYEE CARDS
# =============================================================================

def get_contribution_strategy_description() -> str:
    """Generate a human-readable description of the current contribution strategy.

    Clarifies that amounts shown are Employer (ER) contributions.
    Family status tier codes: EE=Single, ES=+Spouse, EC=+Child, F=Family
    """
    settings = st.session_state.get('contribution_settings', {})
    strategy_type = settings.get('strategy_type', 'percentage')
    exclude_deps = settings.get('exclude_dependent_ichra', False)

    # Map tier codes to readable labels
    tier_labels = {'EE': 'Single', 'ES': '+Spouse', 'EC': '+Child', 'F': 'Family'}

    # Build base description - prefix with "ER:" to clarify employer contribution
    if strategy_type == 'percentage':
        pct = settings.get('default_percentage', 75)
        desc = f"ER: {pct}% of premium"
    elif strategy_type == 'flat_amount':
        flat_amounts = settings.get('flat_amounts', {})
        # Show non-null amounts with readable tier labels
        parts = []
        for tier in ['EE', 'ES', 'EC', 'F']:
            amt = flat_amounts.get(tier)
            if amt is not None and amt > 0:
                label = tier_labels.get(tier, tier)
                parts.append(f"{label}: ${amt:,.0f}")
        if parts:
            desc = f"ER flat amount ({', '.join(parts)})"
        else:
            desc = "ER flat amount by tier"
    elif strategy_type == 'base_age_curve':
        base_age = settings.get('base_age', 21)
        base_contrib = settings.get('base_contribution', 400)
        desc = f"ER: ACA 3:1 curve from ${base_contrib:,.0f} at age {base_age}"
    elif strategy_type == 'percentage_lcsp':
        lcsp_pct = settings.get('lcsp_percentage', 75)
        desc = f"ER: {lcsp_pct}% of LCSP"
    elif strategy_type == 'fixed_age_tiers':
        tier_amounts = settings.get('tier_amounts', {})
        if tier_amounts:
            min_amt = min(v for v in tier_amounts.values() if v > 0) if any(v > 0 for v in tier_amounts.values()) else 0
            max_amt = max(tier_amounts.values()) if tier_amounts else 0
            desc = f"ER: Fixed age tiers (${min_amt:,.0f}-${max_amt:,.0f}/mo)"
        else:
            desc = "ER: Fixed age tiers"
    else:
        desc = "Default ER contribution"

    # Add dependent exclusion note if applicable
    if exclude_deps:
        desc += " • Dependents excluded"

    return desc


def render_employee_card(employee):
    # Build family ages string if available
    family_ages_str = ""
    family_ages = employee.get('family_ages', [])
    if family_ages:
        age_parts = []
        # Group by relationship type (values are 'spouse' and 'child' from dependents_df)
        spouse_ages = [f"Spouse ({fa['age']})" for fa in family_ages if fa.get('relationship', '').lower() == 'spouse']
        # Get child ages and sort in ascending order
        child_ages = sorted([fa['age'] for fa in family_ages if fa.get('relationship', '').lower() == 'child'])
        if spouse_ages:
            age_parts.extend(spouse_ages)
        if child_ages:
            if len(child_ages) == 1:
                age_parts.append(f"Child ({child_ages[0]})")
            else:
                age_parts.append(f"Children ({', '.join(str(a) for a in child_ages)})")
        if age_parts:
            family_ages_str = f"<br><span style='font-size: 13px; color: #6b7280;'>{' | '.join(age_parts)}</span>"

    # Get contribution strategy description
    strategy_desc = get_contribution_strategy_description()

    # Card header
    st.markdown(f"""
    <div style="border-bottom: 2px solid #e5e7eb; padding-bottom: 16px; margin-bottom: 16px;">
        <p style="font-size: 18px; font-weight: 700; color: #101828; margin-bottom: 4px;">{employee['label']}: {employee['name']}</p>
        <p style="font-size: 14px; color: #4a5565; margin-bottom: 2px;">
            <strong>Age {employee['age']}</strong> | {employee['tier']}{family_ages_str}
        </p>
        <p style="font-size: 14px; color: #4a5565; margin-bottom: 2px;">{employee['location']}</p>
        <p style="font-family: 'Poppins', sans-serif; font-size: 13px; color: #6b7280; margin-bottom: 0;">{strategy_desc}</p>
    </div>
    """, unsafe_allow_html=True)

    # Get plan configurator settings to determine which columns to show
    config = st.session_state.get('plan_configurator', {})

    # Get costs data - use original costs calculated in build_employee_example
    # The ER/EE split is calculated correctly there, accounting for the dependent toggle:
    # - Toggle OFF: ER based on employee-only rate, EE = family_total - ER
    # - Toggle ON: Standard split on family rate
    # Since build_employee_example is called on every page rerun with current settings,
    # we should use those values directly rather than recalculating incorrectly here.
    costs = employee['costs']

    # Build column definitions dynamically
    # Each column: (header_text, header_class, scenario_key)
    columns = [
        ('', '', None),  # Label column
        ('Current', 'th-current', 'Current'),
        ('Renewal', 'th-renewal', 'Renewal'),
        ('Bronze', 'th-bronze', 'ICHRA Bronze'),
        ('Silver', 'th-silver', 'ICHRA Silver'),
        ('Gold', 'th-gold', 'ICHRA Gold'),
    ]

    # Add HAS columns for each enabled IUA level
    if config.get('hap_enabled') and config.get('hap_iuas'):
        sorted_hap_iuas = sorted(config['hap_iuas'], key=lambda x: float(x.replace('k', '')))
        for iua in sorted_hap_iuas:
            key = f"HAS ${iua}"
            if key in costs:
                columns.append((f'HAS ${iua}', 'th-coop', key))

    # Add Sedera columns for each enabled IUA level
    if config.get('sedera_enabled') and config.get('sedera_iuas'):
        sorted_sedera_iuas = sorted(config['sedera_iuas'], key=lambda x: int(x))
        for iua in sorted_sedera_iuas:
            # Match the display format used in build_employee_example
            iua_display = iua if int(iua) < 1000 else f"{int(iua)//1000}k" if int(iua) % 1000 == 0 else f"{int(iua)/1000}k"
            key = f"Sedera ${iua_display}"
            if key in costs:
                columns.append((f'Sedera ${iua_display}', 'th-sedera', key))

    # Build header cells
    header_cells = []
    for header_text, header_class, _ in columns:
        if header_text == '':
            header_cells.append('<th style="text-align: left; background: white;"></th>')
        else:
            header_cells.append(f'<th class="{header_class}">{header_text}</th>')

    # Build Employee cells
    ee_cells = ['<td>Employee</td>']
    for _, _, scenario_key in columns[1:]:  # Skip label column
        val = costs.get(scenario_key, {}).get('employee', 0)
        ee_cells.append(f'<td>${val:,.0f}</td>')

    # Build Employer cells
    er_cells = ['<td>Employer</td>']
    for _, _, scenario_key in columns[1:]:
        val = costs.get(scenario_key, {}).get('employer', 0)
        er_cells.append(f'<td>${val:,.0f}</td>')

    # Build Total cells
    total_cells = ['<td>Total</td>']
    for _, _, scenario_key in columns[1:]:
        ee_val = costs.get(scenario_key, {}).get('employee', 0)
        er_val = costs.get(scenario_key, {}).get('employer', 0)
        total_cells.append(f'<td>${ee_val + er_val:,.0f}</td>')

    # Build Annual cells
    annual_total_cells = ['<td>Annual</td>']
    for _, _, scenario_key in columns[1:]:
        ee_val = costs.get(scenario_key, {}).get('employee', 0)
        er_val = costs.get(scenario_key, {}).get('employer', 0)
        annual_total_cells.append(f'<td>${(ee_val + er_val) * 12:,.0f}</td>')

    # Build complete HTML table as single string (avoids f-string interpolation issues with HTML tags)
    table_html = """
    <style>
        .emp-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
            margin-bottom: 12px;
        }
        .emp-table th {
            padding: 8px 6px;
            font-weight: 600;
            font-size: 11px;
            text-align: center;
            border-bottom: 1px solid #e5e7eb;
        }
        .emp-table td {
            padding: 6px;
            text-align: center;
            font-family: 'Inter', sans-serif;
        }
        .emp-table td:first-child {
            text-align: left;
            font-family: 'Poppins', sans-serif;
            font-weight: 500;
            color: #364153;
        }
        .emp-table .winner-row td {
            font-weight: 500;
        }
        .th-current { background: #E8F1FD; color: #0047AB; }
        .th-renewal { background: #fef2f2; color: #82181a; }
        .th-bronze { background: #FEF3E2; color: #92400e; }
        .th-silver { background: #E8F1FD; color: #003d91; }
        .th-gold { background: #FEF9C3; color: #854d0e; }
        .th-coop { background: #ecfdf5; color: #047857; }
        .th-sedera { background: #fef3c7; color: #92400e; }
    </style>
    <table class="emp-table">
        <thead>
            <tr>""" + ''.join(header_cells) + """</tr>
        </thead>
        <tbody>
            <tr>""" + ''.join(ee_cells) + """</tr>
            <tr>""" + ''.join(er_cells) + """</tr>
            <tr style="border-top: 1px solid #e5e7eb; font-weight: 600;">""" + ''.join(total_cells) + """</tr>
            <tr style="font-weight: 600; color: #6b7280; font-size: 12px;">""" + ''.join(annual_total_cells) + """</tr>
        </tbody>
    </table>
    """

    st.markdown(table_html, unsafe_allow_html=True)

    # Insight box
    st.markdown(f"""
    <div style="background: #eff6ff; border: 1px solid #bedbff; border-radius: 8px; padding: 12px; margin-top: 8px;">
        <p style="display: flex; align-items: flex-start; gap: 8px; margin: 0;">
            <span style="color: #155dfc;">💡</span>
            <span style="color: #1c398e; font-size: 14px;">{employee['insight']}</span>
        </p>
    </div>
    """, unsafe_allow_html=True)

    with st.expander("+ Show Plan Details"):
        metal_plan_details = employee.get('metal_plan_details', {})
        # Convert to float to avoid decimal.Decimal arithmetic errors
        current_total = float(employee.get('current_total_monthly', 0) or 0)
        renewal_total = float(employee.get('renewal_total_monthly', 0) or 0)
        use_ee_rate_only = employee.get('use_ee_rate_only', False)

        if metal_plan_details:
            # Helper function to format currency
            def fmt_currency(val):
                if val is None:
                    return "--"
                return f"${val:,.0f}"

            # Build data for each metal (monthly values)
            # Use costs dict for premium totals - it has the correct ER+EE values matching the main table
            costs = employee.get('costs', {})
            plan_data = {}
            for metal in ['Bronze', 'Silver', 'Gold']:
                details = metal_plan_details.get(metal, {})
                if details:
                    # Get premium from costs dict (employer + employee = total)
                    # This matches the "Total" row in the main table above
                    cost_key = f"ICHRA {metal}"
                    metal_costs = costs.get(cost_key, {})
                    family_premium = metal_costs.get('employer', 0) + metal_costs.get('employee', 0)

                    monthly_cost = family_premium if family_premium > 0 else None
                    # Calculate monthly savings (positive = savings, negative = increase)
                    monthly_savings = (renewal_total - family_premium) if renewal_total > 0 and monthly_cost else None
                    savings_pct = (monthly_savings / renewal_total * 100) if monthly_savings and renewal_total > 0 else None

                    plan_data[metal] = {
                        'plan_name': details.get('plan_name') or 'N/A',
                        'deductible': details.get('deductible'),
                        'moop': details.get('moop'),
                        'monthly_cost': monthly_cost,
                        'monthly_savings': monthly_savings,
                        'savings_pct': savings_pct,
                    }

            # Renewal monthly for comparison
            renewal_monthly = renewal_total if renewal_total > 0 else None

            if plan_data:
                # Get plan names (allow wrapping)
                bronze_name = plan_data.get('Bronze', {}).get('plan_name') or 'N/A'
                silver_name = plan_data.get('Silver', {}).get('plan_name') or 'N/A'
                gold_name = plan_data.get('Gold', {}).get('plan_name') or 'N/A'

                # Get values with defaults
                bronze = plan_data.get('Bronze', {})
                silver = plan_data.get('Silver', {})
                gold = plan_data.get('Gold', {})

                # Format savings values
                def fmt_savings(val):
                    if val is None:
                        return "--"
                    elif val > 0:
                        return f"${val:,.0f}"
                    elif val < 0:
                        return f"-${abs(val):,.0f}"
                    else:
                        return "$0"

                def fmt_pct(val):
                    if val is None:
                        return "--"
                    return f"{abs(val):.0f}%"

                st.markdown(f"""
                <style>
                    .plan-details-table {{
                        width: 100%;
                        border-collapse: collapse;
                        font-family: 'Poppins', sans-serif;
                        margin-bottom: 8px;
                        table-layout: fixed;
                    }}
                    .plan-details-table th {{
                        padding: 10px 12px;
                        text-align: center;
                        font-weight: 600;
                        font-size: 13px;
                        border-bottom: 2px solid #e5e7eb;
                        word-wrap: break-word;
                        overflow-wrap: break-word;
                    }}
                    .plan-details-table th:first-child {{
                        width: 20%;
                    }}
                    .plan-details-table th:not(:first-child) {{
                        width: 26.67%;
                    }}
                    .plan-details-table td {{
                        padding: 8px 12px;
                        text-align: center;
                        font-family: 'Inter', sans-serif;
                        font-size: 14px;
                        border-bottom: 1px solid #e5e7eb;
                    }}
                    .plan-details-table td:first-child {{
                        text-align: left;
                        font-family: 'Poppins', sans-serif;
                        font-weight: 500;
                        color: #364153;
                        font-size: 13px;
                    }}
                    .pd-header-bronze {{ background: #FEF3E2; color: #92400e; }}
                    .pd-header-silver {{ background: #E8F1FD; color: #003d91; }}
                    .pd-header-gold {{ background: #FEF9C3; color: #854d0e; }}
                    .pd-plan-name {{ font-size: 11px; font-weight: 400; color: #6b7280; margin-top: 4px; line-height: 1.3; word-wrap: break-word; overflow-wrap: break-word; }}
                </style>

                <table class="plan-details-table">
                    <thead>
                        <tr>
                            <th style="text-align: left; background: white;"></th>
                            <th class="pd-header-bronze">
                                Bronze
                                <div class="pd-plan-name">{bronze_name}</div>
                            </th>
                            <th class="pd-header-silver">
                                Silver
                                <div class="pd-plan-name">{silver_name}</div>
                            </th>
                            <th class="pd-header-gold">
                                Gold
                                <div class="pd-plan-name">{gold_name}</div>
                            </th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>Deductible</td>
                            <td>{fmt_currency(bronze.get('deductible'))}</td>
                            <td>{fmt_currency(silver.get('deductible'))}</td>
                            <td>{fmt_currency(gold.get('deductible'))}</td>
                        </tr>
                        <tr>
                            <td>OOP Max</td>
                            <td>{fmt_currency(bronze.get('moop'))}</td>
                            <td>{fmt_currency(silver.get('moop'))}</td>
                            <td>{fmt_currency(gold.get('moop'))}</td>
                        </tr>
                        <tr>
                            <td>Monthly premium</td>
                            <td>{fmt_currency(bronze.get('monthly_cost'))}</td>
                            <td>{fmt_currency(silver.get('monthly_cost'))}</td>
                            <td>{fmt_currency(gold.get('monthly_cost'))}</td>
                        </tr>
                        <tr>
                            <td colspan="4" style="background: #E8F1FD; text-align: center; font-style: italic; color: #364153; padding: 10px;">vs {fmt_currency(renewal_monthly)}/mo renewal</td>
                        </tr>
                        <tr>
                            <td>Monthly Savings</td>
                            <td style="color: #00a63e; font-weight: 600;">{fmt_savings(bronze.get('monthly_savings'))}</td>
                            <td style="color: #00a63e; font-weight: 600;">{fmt_savings(silver.get('monthly_savings'))}</td>
                            <td style="color: #00a63e; font-weight: 600;">{fmt_savings(gold.get('monthly_savings'))}</td>
                        </tr>
                        <tr>
                            <td>Savings %</td>
                            <td style="color: #00a63e; font-weight: 600;">{fmt_pct(bronze.get('savings_pct'))}</td>
                            <td style="color: #00a63e; font-weight: 600;">{fmt_pct(silver.get('savings_pct'))}</td>
                            <td style="color: #00a63e; font-weight: 600;">{fmt_pct(gold.get('savings_pct'))}</td>
                        </tr>
                    </tbody>
                </table>
                """, unsafe_allow_html=True)

                st.caption("Lowest cost plan at each metal level. Monthly premium = total family premium.")

                # Member Rate Breakdown Table
                # Always show for non-EE employees - rates are always visible
                # The "Include dependent ICHRA" toggle controls ER/EE cost split, not rate visibility
                member_breakdowns = employee.get('member_breakdowns', {})
                family_status = employee.get('family_status', 'EE')

                if family_status != 'EE' and member_breakdowns:
                    st.markdown("<p style='font-weight: 600; margin-top: 20px; margin-bottom: 8px; color: #101828;'>Member Rate Breakdown</p>",
                                unsafe_allow_html=True)

                    # Get toggle value for showing ICHRA metal plans (default True)
                    show_ichra_metals = st.session_state.get('contribution_settings', {}).get('show_ichra_metals', True)

                    # Collect all plan types that have breakdowns
                    plan_types = []
                    # Only include ICHRA metal plans if toggle is enabled
                    if show_ichra_metals:
                        for key in ['Bronze', 'Silver', 'Gold']:
                            if key in member_breakdowns and member_breakdowns[key]:
                                plan_types.append((key, key.lower()))

                    # Add HAS/Sedera from breakdowns (always shown)
                    for key in member_breakdowns:
                        if key.startswith('HAS ') and member_breakdowns[key]:
                            plan_types.append((key, 'coop'))
                        elif key.startswith('Sedera ') and member_breakdowns[key]:
                            plan_types.append((key, 'sedera'))

                    if plan_types:
                        # Build header row
                        header_cells = ['<th style="text-align: left; background: white;">Member</th>',
                                       '<th style="text-align: center; background: white;">Age</th>']
                        for plan_name, plan_class in plan_types:
                            if plan_class == 'bronze':
                                header_cells.append(f'<th class="pd-header-bronze">{plan_name}</th>')
                            elif plan_class == 'silver':
                                header_cells.append(f'<th class="pd-header-silver">{plan_name}</th>')
                            elif plan_class == 'gold':
                                header_cells.append(f'<th class="pd-header-gold">{plan_name}</th>')
                            elif plan_class == 'coop':
                                header_cells.append(f'<th style="background: #ecfdf5; color: #047857;">{plan_name}</th>')
                            elif plan_class == 'sedera':
                                header_cells.append(f'<th style="background: #fef3c7; color: #92400e;">{plan_name}</th>')

                        # Build data rows for each member
                        data_rows = []

                        # Employee row
                        emp_age = employee.get('age', 0)
                        ee_row = [f'<td style="text-align: left;">Employee</td>', f'<td style="text-align: center;">{emp_age}</td>']
                        for plan_name, _ in plan_types:
                            breakdown = member_breakdowns.get(plan_name, {})
                            rate = breakdown.get('ee_rate', 0)
                            ee_row.append(f'<td style="text-align: center;">${rate:,.0f}</td>' if rate else '<td style="text-align: center;">--</td>')
                        data_rows.append('<tr>' + ''.join(ee_row) + '</tr>')

                        # Spouse row (if applicable)
                        family_ages = employee.get('family_ages', [])
                        spouse_ages = [fa for fa in family_ages if fa.get('relationship', '').lower() == 'spouse']
                        if spouse_ages:
                            spouse_age = spouse_ages[0].get('age', 0)
                            sp_row = [f'<td style="text-align: left;">Spouse</td>', f'<td style="text-align: center;">{spouse_age}</td>']
                            for plan_name, _ in plan_types:
                                breakdown = member_breakdowns.get(plan_name, {})
                                rate = breakdown.get('spouse_rate')
                                sp_row.append(f'<td style="text-align: center;">${rate:,.0f}</td>' if rate else '<td style="text-align: center;">--</td>')
                            data_rows.append('<tr>' + ''.join(sp_row) + '</tr>')

                        # Child rows
                        child_ages = [fa for fa in family_ages if fa.get('relationship', '').lower() == 'child']
                        for idx, child in enumerate(child_ages[:5], start=1):
                            child_age = child.get('age', 0)
                            ch_row = [f'<td style="text-align: left;">Child {idx}</td>', f'<td style="text-align: center;">{child_age}</td>']
                            for plan_name, _ in plan_types:
                                breakdown = member_breakdowns.get(plan_name, {})
                                rate = breakdown.get(f'child_{idx}_rate')
                                ch_row.append(f'<td style="text-align: center;">${rate:,.0f}</td>' if rate else '<td style="text-align: center;">--</td>')
                            data_rows.append('<tr>' + ''.join(ch_row) + '</tr>')

                        # Total row
                        total_row = ['<td style="text-align: left; font-weight: 600;">Total</td>', '<td></td>']
                        for plan_name, _ in plan_types:
                            breakdown = member_breakdowns.get(plan_name, {})
                            total_rate = breakdown.get('total_rate', 0)
                            total_row.append(f'<td style="text-align: center; font-weight: 600;">${total_rate:,.0f}</td>')
                        data_rows.append('<tr style="border-top: 2px solid #e5e7eb;">' + ''.join(total_row) + '</tr>')

                        breakdown_table = """
                        <table class="plan-details-table">
                            <thead>
                                <tr>""" + ''.join(header_cells) + """</tr>
                            </thead>
                            <tbody>
                                """ + ''.join(data_rows) + """
                            </tbody>
                        </table>
                        """
                        st.markdown(breakdown_table, unsafe_allow_html=True)
                        st.caption("Individual rates for each family member. Marketplace plans use ACA age-based rating (3-child cap); Cooperative/Sedera use eldest family member's age band for all members.")

            else:
                st.info("Plan details not available.")
        else:
            st.info("Plan details not available. Complete contribution analysis to see plan options.")


def render_employee_examples(data: DashboardData):
    # Header with export button
    header_col, export_col = st.columns([4, 1])
    with header_col:
        st.markdown("""
        <p style="font-size: 20px; font-weight: 500; color: #101828; margin-bottom: 4px;">How this affects your employees</p>
        <p style="font-size: 16px; color: #4a5565; margin-bottom: 24px;">Three representative examples showing employer vs. employee costs</p>
        """, unsafe_allow_html=True)

    if not data.employee_examples:
        st.info("Employee examples will be available after census upload and contribution analysis")
        return

    # Export options
    with export_col:
        include_qr_links = st.checkbox(
            "Include QR links",
            value=False,
            help="Add scannable QR codes linking to detailed rate breakdown pages (links expire after 7 days)",
            key="employee_examples_qr_links"
        )
        # Toggle for showing ICHRA metal plans in Member Rate Breakdown
        show_ichra_metals = st.checkbox(
            "Show Alternative plans",
            value=st.session_state.get('contribution_settings', {}).get('show_ichra_metals', False),
            help="Select if you want to show alternative plans",
            key="show_ichra_metals_checkbox"
        )
        st.session_state.contribution_settings['show_ichra_metals'] = show_ichra_metals

        if st.button("📊 Export to PPT", key="export_employee_examples_pptx"):
            # Transform data for PPTX generator
            # Use costs directly from employee examples - they are already calculated correctly
            # by build_employee_example with the current contribution settings and toggles
            pptx_data = []
            for emp in data.employee_examples:
                use_ee_rate = emp.get('use_ee_rate_only', False)

                # Transform metal_plan_details to match PPTX generator format
                # Use costs dict for premium - it has correct ER+EE matching the main table
                costs = emp.get('costs', {})
                metal_details = {}
                for metal in ['Bronze', 'Silver', 'Gold']:
                    orig = emp.get('metal_plan_details', {}).get(metal, {})
                    if orig:
                        # Get premium from costs dict (employer + employee = total)
                        cost_key = f"ICHRA {metal}"
                        metal_costs = costs.get(cost_key, {})
                        premium = metal_costs.get('employer', 0) + metal_costs.get('employee', 0)
                        metal_details[metal] = {
                            'plan_name': orig.get('plan_name', '—'),
                            'premium': premium,
                            'deductible': orig.get('deductible'),
                            'moop': orig.get('moop'),
                        }
                pptx_data.append({
                    'label': emp.get('label', ''),
                    'name': emp.get('name', ''),
                    'age': emp.get('age', 0),
                    'tier': emp.get('tier', ''),
                    'location': emp.get('location', ''),
                    'family_ages': emp.get('family_ages', []),
                    'family_status': emp.get('family_status', 'EE'),
                    'costs': emp.get('costs', {}),  # Use original costs - already correctly calculated
                    'winner': emp.get('winner', ''),
                    'insight': emp.get('insight', ''),
                    'metal_plan_details': metal_details,
                    'member_breakdowns': emp.get('member_breakdowns', {}),
                    'current_total_monthly': emp.get('current_total_monthly', 0),
                    'renewal_total_monthly': emp.get('renewal_total_monthly', 0),
                    'use_ee_rate_only': use_ee_rate,
                    'contribution_strategy': get_contribution_strategy_description(),
                })

            # Generate PPTX with plan configurator settings for dynamic columns
            pptx_buffer = generate_employee_examples_pptx(
                pptx_data,
                client_name=data.client_name or '',
                plan_config=st.session_state.get('plan_configurator', {}),
                include_qr_links=include_qr_links
            )

            # Create filename with datetime stamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            client_slug = (data.client_name or 'client').replace(' ', '_').lower()
            filename = f"{client_slug}_employee_examples_{timestamp}.pptx"

            st.download_button(
                label="⬇️ Download PPT",
                data=pptx_buffer,
                file_name=filename,
                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                key="download_employee_examples_pptx"
            )

        # CSV Export button
        if st.button("📋 Export to CSV", key="export_employee_examples_csv"):
            csv_df = generate_employee_examples_csv(
                data.employee_examples,
                plan_config=st.session_state.get('plan_configurator', {})
            )
            if csv_df is not None and not csv_df.empty:
                csv_data = csv_df.to_csv(index=False)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                client_slug = (data.client_name or 'client').replace(' ', '_').lower()
                csv_filename = f"{client_slug}_employee_examples_{timestamp}.csv"
                st.download_button(
                    label="⬇️ Download CSV",
                    data=csv_data,
                    file_name=csv_filename,
                    mime="text/csv",
                    key="download_employee_examples_csv"
                )

    # Each employee example gets its own full-width row
    for employee in data.employee_examples:
        with st.container(border=True):
            render_employee_card(employee)


# =============================================================================
# KEY MESSAGES & ADOPTION
# =============================================================================

def render_key_messages(data: DashboardData):
    st.markdown('<p class="card-title">Key messages</p>', unsafe_allow_html=True)

    # Generate dynamic messages based on actual data
    increase_pct = data.increase_pct if data.increase_pct > 0 else 20
    messages = [
        f"Eliminate your {increase_pct:.0f}% increase entirely with cooperative adoption",
        "Give employees choice: Those who need better coverage can buy up to Gold",
        "Younger employees no longer subsidize older employees",
        "Cooperative + DPC makes care actually accessible (vs. high deductibles)",
    ]

    for msg in messages:
        st.markdown(f"""
        <div class="key-message">
            <span style="color: #00a63e; font-weight: 700; margin-right: 8px;">✓</span>
            <span class="key-message-text">{msg}</span>
        </div>
        """, unsafe_allow_html=True)


def render_expected_adoption(data: DashboardData):
    st.markdown('<p class="card-title">Expected adoption</p>', unsafe_allow_html=True)

    adoption = data.expected_adoption
    if not adoption:
        st.info("Adoption estimates will be available after analysis")
        return

    # Donut chart
    fig = go.Figure(data=[go.Pie(
        labels=list(adoption.keys()),
        values=[v["pct"] for v in adoption.values()],
        marker_colors=[v["color"] for v in adoption.values()],
        hole=0.6,
        textinfo='percent',
        textposition='inside',
    )])
    fig.update_layout(
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.2),
        margin=dict(t=20, b=60, l=20, r=20),
        height=200,
    )
    st.plotly_chart(fig, key="adoption_pie_chart")

    # Calculate blended employer cost based on adoption
    # 70% Cooperative + 20% Silver + 10% Gold
    coop_cost = data.company_totals.get('Cooperative', 0)
    silver_cost = data.company_totals.get('ICHRA Silver', 0)
    gold_cost = data.company_totals.get('ICHRA Gold', 0)

    blended_cost = (coop_cost * 0.70) + (silver_cost * 0.20) + (gold_cost * 0.10)
    renewal_cost = data.company_totals.get('Renewal 2026', data.renewal_premium)
    savings_monthly = renewal_cost - blended_cost if renewal_cost > 0 else 0
    savings_annual = savings_monthly * 12

    # Summary stats
    st.markdown("""
    <hr style="border: none; border-top: 2px solid #e5e7eb; margin: 16px 0;">
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<span style="color: #364153; font-weight: 500;">Blended employer cost:</span>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<span style="font-family: Inter; font-weight: 700; font-size: 18px;">${blended_cost:,.0f}/month</span>', unsafe_allow_html=True)

    st.markdown(f"""
    <div class="success-box" style="margin-top: 16px;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <span style="color: #0d542b; font-weight: 500;">Savings vs renewal:</span>
            <div style="text-align: right;">
                <p style="font-family: Inter; font-weight: 700; color: #008236; font-size: 18px; margin: 0;">${savings_monthly:,.0f}/month</p>
                <p style="color: #00a63e; font-size: 14px; margin: 0;">(${savings_annual:,.0f} annually)</p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Export button
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("📄 Export proposal to PDF", type="primary", use_container_width=True):
        st.toast("PDF export coming soon!", icon="📄")


# =============================================================================
# MAIN LAYOUT
# =============================================================================

# Page title
st.markdown("""
<div class="hero-section">
    <div class="hero-title">📊 ICHRA Comparison Dashboard</div>
    <p class="hero-subtitle">Compare current group plan costs with ICHRA marketplace alternatives</p>
</div>
""", unsafe_allow_html=True)

# Check for census data
census_df = st.session_state.get('census_df')
if census_df is None or (hasattr(census_df, 'empty') and census_df.empty):
    st.warning("No census data loaded. Please upload a census file on the Census input page first.")
    st.info("This dashboard will display ICHRA comparison analysis once census data is available.")
    st.stop()

# Get database connection
db = None
db_health_issues = []
try:
    db = get_database_connection()

    # Quick health check for required tables using HealthCheckQueries
    if db is not None:
        try:
            # Check for critical tables needed for ICHRA calculations
            missing_tables = HealthCheckQueries.get_missing_tables(db)
            if missing_tables:
                db_health_issues.append(f"Missing tables: {', '.join(missing_tables)}")

            # Check if rating area table has FIPS column (needed for ZIP lookup)
            if 'rbis_state_rating_area_amended' not in missing_tables:
                if not HealthCheckQueries.check_fips_column(db):
                    db_health_issues.append("Table 'rbis_state_rating_area_amended' is missing 'FIPS' column for ZIP lookup")

        except Exception as health_check_error:
            db_health_issues.append(f"Health check failed: {str(health_check_error)}")

except Exception as e:
    st.warning(f"Database connection unavailable: {e}")
    db_health_issues.append(f"Connection failed: {str(e)}")

# Show database health issues if any
if db_health_issues:
    with st.sidebar:
        with st.expander("🔴 Database Issues", expanded=True):
            st.error("Database configuration issues detected:")
            for issue in db_health_issues:
                st.markdown(f"- {issue}")

# =============================================================================
# SIDEBAR: Client Name & Scenario Settings
# =============================================================================
with st.sidebar:
    # Client name input for export filenames
    st.markdown("**📋 Client Name**")
    if 'client_name' not in st.session_state:
        st.session_state.client_name = ''
    st.text_input(
        "Client name",
        placeholder="Enter client name",
        key="client_name",
        help="Used in export filenames and proposal headers",
        label_visibility="collapsed"
    )
    st.markdown("---")

    with st.expander("⚙️ Scenario Settings", expanded=False):
        st.markdown("**Adoption Rate Assumptions**")
        st.caption("Estimate how employees will choose their coverage")

        # Get current values from session state or defaults
        if 'dashboard_config' not in st.session_state:
            st.session_state.dashboard_config = {
                'cooperative_ratio': COOPERATIVE_CONFIG['default_discount_ratio'],
                'adoption_rates': DEFAULT_ADOPTION_RATES.copy(),
            }

        current_rates = st.session_state.dashboard_config.get('adoption_rates', DEFAULT_ADOPTION_RATES)

        coop_pct = st.slider(
            "Cooperative %", 0, 100,
            value=current_rates.get('Cooperative', 70),
            key='adoption_coop_slider'
        )
        silver_pct = st.slider(
            "ICHRA Silver %", 0, 100,
            value=current_rates.get('ICHRA Silver', 20),
            key='adoption_silver_slider'
        )
        gold_pct = st.slider(
            "ICHRA Gold %", 0, 100,
            value=current_rates.get('ICHRA Gold', 10),
            key='adoption_gold_slider'
        )

        # Validate sum = 100
        total = coop_pct + silver_pct + gold_pct
        if total != 100:
            st.warning(f"⚠️ Rates must sum to 100% (currently {total}%)")
        else:
            st.session_state.dashboard_config['adoption_rates'] = {
                'Cooperative': coop_pct,
                'ICHRA Silver': silver_pct,
                'ICHRA Gold': gold_pct,
            }

        st.markdown("---")
        st.markdown("**Cooperative Pricing**")
        st.caption("Cooperative cost as percentage of Silver LCSP")

        coop_ratio_pct = st.slider(
            "Coop as % of Silver", 50, 100,
            value=int(st.session_state.dashboard_config.get('cooperative_ratio', 0.72) * 100),
            key='coop_ratio_slider'
        )
        st.session_state.dashboard_config['cooperative_ratio'] = coop_ratio_pct / 100

# Initialize contribution_settings BEFORE loading data (to ensure toggle value is available)
if 'contribution_settings' not in st.session_state:
    st.session_state.contribution_settings = {
        'strategy_type': 'percentage',
        'default_percentage': 75,
        'by_class': {},
        'input_mode': 'percentage',
        'flat_amounts': {'EE': None, 'ES': None, 'EC': None, 'F': None},
        'exclude_dependent_ichra': False,  # Toggle: when True, ER only covers employee rate
        'show_ichra_metals': True,  # Toggle for showing ICHRA metals in Member Rate Breakdown
        'base_age': 21,
        'base_contribution': 400.0,
        'lcsp_percentage': 75,
        'tier_amounts': {'21': 300, '18-25': 350, '26-35': 400, '36-45': 500, '46-55': 600, '56-63': 750, '64+': 900}
    }

# Ensure show_ichra_metals exists in older sessions (key was added later)
if 'show_ichra_metals' not in st.session_state.contribution_settings:
    st.session_state.contribution_settings['show_ichra_metals'] = True

# Sync widget keys with contribution_settings (widgets update their keys on change)
# This ensures load_dashboard_data gets the latest values from widget interactions
if 'exclude_dependent_ichra_checkbox' in st.session_state:
    st.session_state.contribution_settings['exclude_dependent_ichra'] = st.session_state.exclude_dependent_ichra_checkbox
if 'contribution_strategy_radio' in st.session_state:
    st.session_state.contribution_settings['strategy_type'] = st.session_state.contribution_strategy_radio
    st.session_state.contribution_settings['input_mode'] = st.session_state.contribution_strategy_radio
# Sync percentage slider
if 'contribution_pct_slider' in st.session_state:
    st.session_state.contribution_settings['default_percentage'] = st.session_state.contribution_pct_slider
# Sync base age curve settings
if 'base_age_select' in st.session_state:
    st.session_state.contribution_settings['base_age'] = st.session_state.base_age_select
if 'base_contribution_input' in st.session_state:
    st.session_state.contribution_settings['base_contribution'] = st.session_state.base_contribution_input
# Sync LCSP percentage
if 'lcsp_pct_slider' in st.session_state:
    st.session_state.contribution_settings['lcsp_percentage'] = st.session_state.lcsp_pct_slider

# Load all dashboard data from session state
data = load_dashboard_data(
    census_df=census_df,
    dependents_df=st.session_state.get('dependents_df'),
    contribution_analysis=st.session_state.get('contribution_analysis'),
    financial_summary=st.session_state.get('financial_summary'),
    contribution_settings=st.session_state.get('contribution_settings'),
    client_name=st.session_state.get('client_name', 'Company'),
    db=db,
    dashboard_config=st.session_state.get('dashboard_config')
)

# ==========================================================================
# DIAGNOSTIC DISPLAY - Show errors if ICHRA calculations failed
# ==========================================================================
if data.diagnostic_errors:
    with st.expander("⚠️ **ICHRA Calculation Issues Detected** - Click to view details", expanded=True):
        st.error("The ICHRA columns are showing N/A or $0 due to the following issues:")
        for error in data.diagnostic_errors:
            st.markdown(f"- {error}")

        # Show diagnostic info
        if data.diagnostic_info:
            st.markdown("---")
            st.markdown("**Diagnostic Information:**")
            diag_cols = st.columns(2)
            with diag_cols[0]:
                if 'states' in data.diagnostic_info:
                    st.markdown(f"**States in census:** {', '.join(map(str, data.diagnostic_info['states']))}")
                if 'rating_areas_found' in data.diagnostic_info:
                    ra_list = data.diagnostic_info['rating_areas_found']
                    if ra_list:
                        st.markdown(f"**Rating areas found:** {', '.join(map(str, ra_list[:10]))}{'...' if len(ra_list) > 10 else ''}")
                    else:
                        st.markdown("**Rating areas found:** None (ZIP lookup failed)")
                if 'employees_missing_rating_area' in data.diagnostic_info:
                    st.markdown(f"**Employees missing rating area:** {data.diagnostic_info['employees_missing_rating_area']}")
            with diag_cols[1]:
                for metal in ['Bronze', 'Silver', 'Gold']:
                    monthly = data.diagnostic_info.get(f'{metal}_total_monthly', 'N/A')
                    covered = data.diagnostic_info.get(f'{metal}_employees_covered', 'N/A')
                    if monthly != 'N/A':
                        st.markdown(f"**{metal}:** ${monthly:,.0f}/mo ({covered} employees)")

        st.markdown("---")
        st.markdown("**Common causes:**")
        st.markdown("""
        1. **Missing database tables** - `zip_to_county_correct` or `rbis_state_rating_area_amended` may not exist
        2. **FIPS column mismatch** - The rating area table may be missing the `"FIPS"` column for ZIP→County joins
        3. **No plans for rating area** - The state/rating area combination may have no Individual marketplace plans
        4. **Column name case sensitivity** - PostgreSQL quoted columns like `"ZIP"` require exact case matching
        """)

# Header
render_header(data)

st.markdown("<br>", unsafe_allow_html=True)

# Row 1: Workforce Composition + Current Plan Problems
col1, col2 = st.columns(2)

with col1:
    with st.container(border=True):
        render_workforce_composition(data)

with col2:
    with st.container(border=True):
        render_contribution_pattern_card()

st.markdown("<br>", unsafe_allow_html=True)

# Row 1.5: Employer Contribution Input (optional)
with st.container(border=True):
    render_contribution_input_card()

st.markdown("<br>", unsafe_allow_html=True)

# Row 2: Comparison Table (by Family Status)
with st.container(border=True):
    render_comparison_table(data, db=db, census_df=census_df,
                            dependents_df=st.session_state.get('dependents_df'))

st.markdown("<br>", unsafe_allow_html=True)

# Row 3: Marketplace Rates by Coverage Type
with st.container(border=True):
    render_marketplace_rates_table(data, db=db, census_df=census_df,
                                   dependents_df=st.session_state.get('dependents_df'))

st.markdown("<br>", unsafe_allow_html=True)

# Row 4: Employee Examples
render_employee_examples(data)

st.markdown("<br>", unsafe_allow_html=True)

# Row 5: Key Messages + Expected Adoption
col1, col2 = st.columns([2, 1])

with col1:
    with st.container(border=True):
        render_key_messages(data)

with col2:
    with st.container(border=True):
        render_expected_adoption(data)
