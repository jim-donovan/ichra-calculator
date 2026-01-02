"""
ICHRA Comparison Dashboard
Based on Figma design - Broker presentation view for client census analysis
Data-driven: All values calculated from census upload
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import get_database_connection, DatabaseConnection
from utils import ContributionComparison, PremiumCalculator
from financial_calculator import FinancialSummaryCalculator
from queries import get_plan_deductible_and_moop_batch
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
        background: #fffbeb;
        border: 1px solid #fee685;
        border-radius: 8px;
        padding: 12px;
        display: flex;
        gap: 8px;
        align-items: flex-start;
    }

    .warning-text {
        color: #973c00;
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
    .col-current { background: #eff6ff; color: #1c398e; }
    .col-renewal { background: #fef2f2; color: #82181a; border-left: 4px solid #ffa2a2; }
    .col-bronze { background: #fffbeb; color: #7b3306; }
    .col-silver { background: #f9fafb; color: #101828; }
    .col-gold { background: #fefce8; color: #733e0a; }
    .col-coop { background: #f0fdf4; color: #0d542b; }

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

    # Contribution percentage from Page 2
    contribution_pct: float = 0.65

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

    # Extract contribution percentage from Page 2 settings (default 65%)
    if contribution_settings:
        data.contribution_pct = contribution_settings.get('default_percentage', 65) / 100.0
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
            data.multi_metal_results = FinancialSummaryCalculator.calculate_multi_metal_scenario(
                census_df, db, ['Bronze', 'Silver', 'Gold'], dependents_df
            )
            data.has_lcsp_data = True

            # Extract average actuarial values from multi-metal results
            for metal in ['Bronze', 'Silver', 'Gold']:
                metal_data = data.multi_metal_results.get(metal, {})
                avg_av = metal_data.get('average_av')
                if avg_av is not None:
                    data.metal_av[metal] = avg_av
        except Exception as e:
            import logging
            logging.warning(f"Multi-metal calculation failed: {e}")
            data.multi_metal_results = {}

    # ==========================================================================
    # TIER-LEVEL COSTS (average per family status)
    # ==========================================================================
    # Get cooperative_ratio from dashboard_config if provided
    cooperative_ratio = COOPERATIVE_CONFIG['default_discount_ratio']
    if dashboard_config and 'cooperative_ratio' in dashboard_config:
        cooperative_ratio = dashboard_config['cooperative_ratio']

    # Load cooperative rate table from database
    coop_rates_df = load_cooperative_rate_table(db)

    data.tier_costs = calculate_tier_costs(
        census_df, contribution_analysis, db,
        multi_metal_results=data.multi_metal_results,
        renewal_monthly=renewal_monthly,
        cooperative_ratio=cooperative_ratio,
        coop_rates_df=coop_rates_df
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
        coop_rates_df=coop_rates_df
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
                pct = round((savings / renewal_total) * 100, 1) if renewal_total > 0 else 0
                data.savings_vs_renewal[scenario] = {
                    "amount": savings,
                    "pct": -pct  # Negative to show reduction
                }

    # ==========================================================================
    # EMPLOYEE EXAMPLES (youngest, mid-age family, oldest)
    # ==========================================================================
    data.employee_examples = select_employee_examples(
        census_df, contribution_analysis, data.tier_costs,
        data.multi_metal_results, data.contribution_pct,
        cooperative_ratio=cooperative_ratio,
        dependents_df=dependents_df,
        db=db,
        coop_rates_df=coop_rates_df
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
                         coop_rates_df: pd.DataFrame = None) -> Dict[str, Dict[str, float]]:
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
            if coop_rates_df is not None and not coop_rates_df.empty:
                # Look up cooperative rate for each employee in tier and average
                age_col = 'age' if 'age' in tier_employees.columns else None
                coop_rates = []
                if age_col:
                    for _, emp_row in tier_employees.iterrows():
                        emp_age = int(emp_row.get(age_col, 40))
                        coop_rate = get_cooperative_rate(emp_age, status_code, coop_rates_df)
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


def load_cooperative_rate_table(db: DatabaseConnection = None) -> pd.DataFrame:
    """Load the HAP cooperative rate table from database."""
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

    # Determine age band
    if age < 30:
        age_band = "18-29"
    elif age < 40:
        age_band = "30-39"
    elif age < 50:
        age_band = "40-49"
    elif age < 60:
        age_band = "50-59"
    else:
        age_band = "60-64"

    # Look up rate
    row = coop_rates_df[(coop_rates_df['age_band'] == age_band) &
                        (coop_rates_df['family_status'] == fs)]
    if not row.empty:
        col = 'deductible_2_5k' if deductible == "2.5k" else 'deductible_1k'
        return float(row[col].iloc[0])
    return 0


def calculate_tier_costs_by_age(census_df: pd.DataFrame, multi_metal_results: Dict = None,
                                 mode: str = "youngest", cooperative_ratio: float = None,
                                 coop_rates_df: pd.DataFrame = None) -> Dict[str, Dict[str, float]]:
    """
    Calculate tier costs using youngest or oldest employee per tier.

    Args:
        census_df: Employee census DataFrame
        multi_metal_results: Results from calculate_multi_metal_scenario()
        mode: "youngest" or "oldest"
        cooperative_ratio: Cooperative cost as fraction of Silver
        coop_rates_df: Cooperative rate table DataFrame

    Returns dict with structure:
    {
        "Employee Only": {"ICHRA Bronze": X, "ICHRA Silver": Y, ...},
        ...
    }
    """
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

    family_col = 'family_status' if 'family_status' in census_df.columns else None
    if not family_col and 'Family Status' in census_df.columns:
        family_col = 'Family Status'
    if not family_col:
        return tier_costs

    age_col = 'age' if 'age' in census_df.columns else None
    if not age_col:
        return tier_costs

    # For each tier, find the youngest or oldest employee
    for status_code, tier_name in tier_mapping.items():
        tier_employees = census_df[census_df[family_col] == status_code]
        if tier_employees.empty:
            continue

        # Sort by age and pick first (youngest) or last (oldest)
        sorted_tier = tier_employees.sort_values(age_col)
        if mode == "youngest":
            target_employee = sorted_tier.iloc[0]
        else:  # oldest
            target_employee = sorted_tier.iloc[-1]

        emp_id = target_employee.get('employee_id')
        emp_age = int(target_employee.get(age_col, 0))

        # Current and renewal costs for this specific employee
        current_er = target_employee.get('current_er_monthly', 0) or 0
        current_ee = target_employee.get('current_ee_monthly', 0) or 0
        current_total = current_er + current_ee
        if current_total > 0:
            tier_costs[tier_name][f'Current {CURRENT_PLAN_YEAR}'] = round(current_total, 0)

        # Get 2026 projected premium if available
        projected_2026 = target_employee.get('projected_2026_premium', 0) or 0
        if projected_2026 > 0:
            tier_costs[tier_name][f'Renewal {RENEWAL_PLAN_YEAR}'] = round(projected_2026, 0)

        # Get ICHRA costs from multi_metal_results for this specific employee
        if multi_metal_results:
            for metal in ['Bronze', 'Silver', 'Gold']:
                metal_data = multi_metal_results.get(metal, {})
                employee_details = metal_data.get('employee_details', [])
                for emp_detail in employee_details:
                    if emp_detail.get('employee_id') == emp_id:
                        premium = emp_detail.get('estimated_tier_premium', 0)
                        if premium > 0:
                            tier_costs[tier_name][f'ICHRA {metal}'] = round(premium, 0)
                        break

            # Cooperative - use rate table if available, otherwise use ratio
            silver_cost = tier_costs[tier_name].get('ICHRA Silver', 0)
            if coop_rates_df is not None and not coop_rates_df.empty:
                coop_rate = get_cooperative_rate(emp_age, status_code, coop_rates_df)
                if coop_rate > 0:
                    tier_costs[tier_name]['Cooperative'] = round(coop_rate, 0)
                elif silver_cost > 0:
                    tier_costs[tier_name]['Cooperative'] = round(silver_cost * cooperative_ratio, 0)
            elif silver_cost > 0:
                tier_costs[tier_name]['Cooperative'] = round(silver_cost * cooperative_ratio, 0)

    return tier_costs


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
        current_er = row.get('current_er_monthly', 0) or 0
        current_ee = row.get('current_ee_monthly', 0) or 0
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


def calculate_company_totals(census_df: pd.DataFrame, contribution_analysis: Dict = None,
                              tier_costs: Dict = None, multi_metal_results: Dict = None,
                              contribution_pct: float = 0.65,
                              renewal_monthly: float = None,
                              cooperative_ratio: float = None,
                              coop_rates_df: pd.DataFrame = None) -> Dict[str, float]:
    """
    Calculate company-wide totals for each scenario.

    Uses actual Bronze/Silver/Gold data from multi_metal_results when available,
    and applies the configured contribution percentage from Page 2.

    Args:
        census_df: Employee census DataFrame
        contribution_analysis: Per-employee ICHRA analysis (optional)
        tier_costs: Pre-calculated tier costs (optional)
        multi_metal_results: Results from calculate_multi_metal_scenario() with actual rates
        contribution_pct: Employer contribution percentage (default 0.65 = 65%)
        renewal_monthly: Actual renewal amount from Page 3 (optional)
        cooperative_ratio: Cooperative cost as fraction of Silver (from dashboard_config)
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
            coop_total = 0
            age_col = 'age' if 'age' in census_df.columns else None
            family_col = 'family_status' if 'family_status' in census_df.columns else None
            if age_col and family_col:
                for _, emp_row in census_df.iterrows():
                    emp_age = int(emp_row.get(age_col, 40))
                    emp_fs = emp_row.get(family_col, 'EE')
                    coop_rate = get_cooperative_rate(emp_age, emp_fs, coop_rates_df)
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


def select_employee_examples(census_df: pd.DataFrame, contribution_analysis: Dict = None,
                              tier_costs: Dict = None, multi_metal_results: Dict = None,
                              contribution_pct: float = 0.65,
                              cooperative_ratio: float = None,
                              dependents_df: pd.DataFrame = None,
                              db=None,
                              coop_rates_df: pd.DataFrame = None) -> List[Dict]:
    """Select 3 representative employees: youngest, mid-age family, oldest."""
    examples = []

    if census_df is None or census_df.empty or 'age' not in census_df.columns:
        return examples

    # Sort by age to find youngest/oldest
    sorted_df = census_df.sort_values('age')

    # Youngest Employee Only (EE status only)
    ee_only = sorted_df[sorted_df['family_status'] == 'EE']
    if not ee_only.empty:
        youngest = ee_only.iloc[0]
        examples.append(build_employee_example(
            youngest, "Youngest Employee", contribution_analysis, tier_costs,
            multi_metal_results, contribution_pct, cooperative_ratio, dependents_df, db,
            use_ee_rate_only=True,  # ICHRA is individual-level
            coop_rates_df=coop_rates_df
        ))

    # Mid-age family (Family status preferred)
    families = sorted_df[sorted_df['family_status'] == 'F']
    if not families.empty:
        mid_idx = len(families) // 2
        mid_family = families.iloc[mid_idx]
        examples.append(build_employee_example(
            mid_family, "Mid-Age Family", contribution_analysis, tier_costs,
            multi_metal_results, contribution_pct, cooperative_ratio, dependents_df, db,
            coop_rates_df=coop_rates_df
        ))

    # Oldest
    oldest = sorted_df.iloc[-1]
    examples.append(build_employee_example(
        oldest, "Oldest Employee", contribution_analysis, tier_costs,
        multi_metal_results, contribution_pct, cooperative_ratio, dependents_df, db,
        coop_rates_df=coop_rates_df
    ))

    return examples


def build_employee_example(employee_row: pd.Series, label: str,
                           contribution_analysis: Dict = None, tier_costs: Dict = None,
                           multi_metal_results: Dict = None, contribution_pct: float = 0.65,
                           cooperative_ratio: float = None,
                           dependents_df: pd.DataFrame = None,
                           db=None,
                           use_ee_rate_only: bool = False,
                           coop_rates_df: pd.DataFrame = None) -> Dict:
    """Build employee example dict from census row.

    Args:
        use_ee_rate_only: If True, use individual ee_rate instead of estimated_tier_premium
                          (ignores family status multiplier). Used for youngest employee.
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

    # Get current costs
    current_er = employee_row.get('current_er_monthly', 0) or 0
    current_ee = employee_row.get('current_ee_monthly', 0) or 0

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
                        metal_plan_details[metal] = {
                            'plan_id': plan_id,
                            'plan_name': emp_detail.get('lcp_plan_name'),
                            'actuarial_value': emp_detail.get('actuarial_value'),
                            'ee_rate': emp_detail.get('lcp_ee_rate', 0),
                            'estimated_tier_premium': emp_detail.get('estimated_tier_premium', 0),
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
                            # Use ee_rate (individual only) if flag is set, otherwise use tier premium
                            if use_ee_rate_only:
                                ichra_premium = emp_detail.get('lcp_ee_rate', 0)
                            else:
                                ichra_premium = emp_detail.get('estimated_tier_premium', 0)
                            projected_2026_premium = emp_detail.get('projected_2026_premium', 0) or 0
                            plan_details = {
                                'plan_id': plan_id,
                                'plan_name': emp_detail.get('lcp_plan_name'),
                                'actuarial_value': emp_detail.get('actuarial_value'),
                                'ee_rate': emp_detail.get('lcp_ee_rate', 0),
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

    # Calculate ER/EE split using contribution percentage
    if ichra_premium > 0:
        ichra_er = ichra_premium * contribution_pct
        ichra_ee = ichra_premium - ichra_er

    # Calculate Bronze and Gold costs from metal_plan_details
    bronze_premium = 0
    gold_premium = 0
    if metal_plan_details:
        bronze_details = metal_plan_details.get('Bronze', {})
        gold_details = metal_plan_details.get('Gold', {})
        if use_ee_rate_only:
            bronze_premium = bronze_details.get('ee_rate', 0) or 0
            gold_premium = gold_details.get('ee_rate', 0) or 0
        else:
            bronze_premium = bronze_details.get('estimated_tier_premium', 0) or 0
            gold_premium = gold_details.get('estimated_tier_premium', 0) or 0

    bronze_er = bronze_premium * contribution_pct if bronze_premium > 0 else 0
    bronze_ee = bronze_premium - bronze_er if bronze_premium > 0 else 0
    gold_er = gold_premium * contribution_pct if gold_premium > 0 else 0
    gold_ee = gold_premium - gold_er if gold_premium > 0 else 0

    # Cooperative - use rate table if available, otherwise ratio of silver (100% employer paid, $0 employee)
    if coop_rates_df is not None and not coop_rates_df.empty:
        coop_rate = get_cooperative_rate(age, family_status, coop_rates_df)
        coop_er = coop_rate if coop_rate > 0 else (ichra_premium * cooperative_ratio if ichra_premium > 0 else 0)
    else:
        coop_er = ichra_premium * cooperative_ratio if ichra_premium > 0 else 0
    coop_ee = 0

    costs = {
        "Current": {"employer": round(current_er, 0), "employee": round(current_ee, 0)},
        "Renewal": {"employer": round(renewal_er, 0), "employee": round(renewal_ee, 0)},
        "ICHRA Bronze": {"employer": round(bronze_er, 0), "employee": round(bronze_ee, 0)},
        "ICHRA Silver": {"employer": round(ichra_er, 0), "employee": round(ichra_ee, 0)},
        "ICHRA Gold": {"employer": round(gold_er, 0), "employee": round(gold_ee, 0)},
        "Cooperative": {"employer": round(coop_er, 0), "employee": round(coop_ee, 0)},
    }

    # Determine winner (lowest total cost for employee)
    winner = "Cooperative"  # Default
    min_ee_cost = coop_ee
    for plan, plan_costs in costs.items():
        if plan_costs['employee'] < min_ee_cost:
            min_ee_cost = plan_costs['employee']
            winner = plan

    # Generate insight
    renewal_total = costs['Renewal']['employer'] + costs['Renewal']['employee']
    coop_total = costs['Cooperative']['employer'] + costs['Cooperative']['employee']
    savings = (renewal_total - coop_total) * 12

    if winner == "Cooperative":
        if coop_ee == 0:
            insight = f"Saves ${savings:,.0f}/year vs. renewal, or gets free coverage via cooperative"
        else:
            insight = f"Cooperative at ${coop_ee:,.0f}/mo makes healthcare actually accessible"
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
        "current_total_monthly": current_total,
        "renewal_total_monthly": renewal_total_monthly,
        "winner": winner,
        "insight": insight,
        "use_ee_rate_only": use_ee_rate_only,  # Flag to use individual rate in displays
    }


# =============================================================================
# CSV EXPORT FUNCTIONS
# =============================================================================

def generate_scenario_rates_csv(multi_metal_results: Dict, db, census_df: pd.DataFrame,
                                 dependents_df: pd.DataFrame = None,
                                 scenario_mode: str = "all") -> pd.DataFrame:
    """
    Generate detailed CSV data for plans used in the Monthly Premium by Scenario table.

    Includes Bronze, Silver, Gold plan details with:
    - Employee metadata (name, age, zip, state, rating area, family status)
    - Plan details (plan ID, name, metal level, plan type, actuarial value)
    - Costs (EE rate, tier premium, deductible, MOOP)

    Args:
        multi_metal_results: Results from calculate_multi_metal_scenario()
        db: Database connection for fetching plan metadata
        census_df: Employee census DataFrame
        dependents_df: Dependents DataFrame (optional)
        scenario_mode: "all" for all employees, "youngest" for youngest per tier,
                       "oldest" for oldest per tier

    Returns:
        DataFrame ready for CSV export
    """
    if not multi_metal_results or db is None:
        return pd.DataFrame()

    all_rows = []

    # Determine which employee IDs to include based on scenario_mode
    included_employee_ids = None  # None means include all
    if scenario_mode in ["youngest", "oldest"] and census_df is not None and not census_df.empty:
        included_employee_ids = set()
        family_col = 'family_status' if 'family_status' in census_df.columns else None
        age_col = 'age' if 'age' in census_df.columns else None

        if family_col and age_col:
            for status_code in ['EE', 'ES', 'EC', 'F']:
                tier_employees = census_df[census_df[family_col] == status_code]
                if not tier_employees.empty:
                    sorted_tier = tier_employees.sort_values(age_col)
                    if scenario_mode == "youngest":
                        target_emp = sorted_tier.iloc[0]
                    else:  # oldest
                        target_emp = sorted_tier.iloc[-1]
                    emp_id = target_emp.get('employee_id')
                    if emp_id:
                        included_employee_ids.add(emp_id)

    # Collect all unique plan IDs across all metal levels (filtered by scenario)
    all_plan_ids = set()
    for metal in ['Bronze', 'Silver', 'Gold']:
        metal_data = multi_metal_results.get(metal, {})
        for emp in metal_data.get('employee_details', []):
            # Filter by included employees if mode is youngest/oldest
            if included_employee_ids is not None:
                if emp.get('employee_id') not in included_employee_ids:
                    continue
            plan_id = emp.get('lcp_plan_id')
            if plan_id:
                all_plan_ids.add(plan_id)

    # Batch fetch plan metadata (type, issuer, deductible, MOOP)
    plan_metadata = {}
    if all_plan_ids:
        # Get plan type and issuer from plan table
        plan_ids_tuple = tuple(all_plan_ids)
        plan_query = """
        SELECT
            hios_plan_id,
            plan_marketing_name,
            plan_type,
            issuer_name,
            level_of_coverage as metal_level
        FROM rbis_insurance_plan_20251019202724
        WHERE hios_plan_id IN %s
        """
        try:
            plan_df = pd.read_sql(plan_query, db.engine, params=(plan_ids_tuple,))
            for _, row in plan_df.iterrows():
                plan_metadata[row['hios_plan_id']] = {
                    'plan_type': row['plan_type'],
                    'issuer_name': row['issuer_name'],
                    'metal_level': row['metal_level']
                }
        except Exception as e:
            import logging
            logging.warning(f"Error fetching plan metadata: {e}")

        # Get deductible and MOOP
        ded_moop = get_plan_deductible_and_moop_batch(db, list(all_plan_ids))
        for plan_id, values in ded_moop.items():
            if plan_id in plan_metadata:
                plan_metadata[plan_id]['individual_deductible'] = values.get('individual_deductible')
                plan_metadata[plan_id]['individual_moop'] = values.get('individual_moop')
            else:
                plan_metadata[plan_id] = {
                    'individual_deductible': values.get('individual_deductible'),
                    'individual_moop': values.get('individual_moop')
                }

    # Build employee zip lookup from census
    zip_lookup = {}
    for _, row in census_df.iterrows():
        emp_id = row.get('employee_id', row.get('Employee Number', ''))
        zip_code = row.get('zip', row.get('Home Zip', ''))
        county = row.get('county', '')
        zip_lookup[emp_id] = {'zip': zip_code, 'county': county}

    # Process each metal level
    for metal in ['Bronze', 'Silver', 'Gold']:
        metal_data = multi_metal_results.get(metal, {})
        employee_details = metal_data.get('employee_details', [])

        for emp in employee_details:
            # Filter by included employees if mode is youngest/oldest
            if included_employee_ids is not None:
                if emp.get('employee_id') not in included_employee_ids:
                    continue
            plan_id = emp.get('lcp_plan_id')
            meta = plan_metadata.get(plan_id, {}) if plan_id else {}
            emp_zip_data = zip_lookup.get(emp.get('employee_id'), {})

            row = {
                # Employee info
                'employee_id': emp.get('employee_id'),
                'first_name': emp.get('first_name'),
                'last_name': emp.get('last_name'),
                'age': emp.get('ee_age'),
                'family_status': emp.get('family_status'),
                'state': emp.get('state'),
                'zip': emp_zip_data.get('zip', ''),
                'county': emp_zip_data.get('county', ''),
                'rating_area': emp.get('rating_area'),

                # Metal level
                'metal_level': metal,

                # Plan details
                'plan_id': plan_id,
                'plan_name': emp.get('lcp_plan_name'),
                'plan_type': meta.get('plan_type', ''),
                'issuer_name': meta.get('issuer_name', ''),
                'actuarial_value': emp.get('actuarial_value'),

                # Costs
                'ee_monthly_rate': emp.get('lcp_ee_rate'),
                'tier_multiplier': emp.get('tier_multiplier'),
                'estimated_tier_premium': emp.get('estimated_tier_premium'),

                # Deductible/MOOP
                'individual_deductible': meta.get('individual_deductible'),
                'individual_moop': meta.get('individual_moop'),

                # Current plan comparison
                'current_ee_monthly': emp.get('current_ee_monthly'),
                'current_er_monthly': emp.get('current_er_monthly'),
                'projected_2026_premium': emp.get('projected_2026_premium'),
            }
            all_rows.append(row)

    if not all_rows:
        return pd.DataFrame()

    df = pd.DataFrame(all_rows)

    # Sort by metal level (Bronze, Silver, Gold) then by employee
    metal_order = {'Bronze': 1, 'Silver': 2, 'Gold': 3}
    df['_metal_sort'] = df['metal_level'].map(metal_order)
    df = df.sort_values(['_metal_sort', 'last_name', 'first_name'])
    df = df.drop(columns=['_metal_sort'])

    return df


# =============================================================================
# HEADER SECTION
# =============================================================================

def render_header(data: DashboardData):
    col1, col2 = st.columns([1, 1])

    # Calculate projected savings
    renewal = data.company_totals.get('Renewal 2026', data.renewal_premium)
    coop = data.company_totals.get('Cooperative', 0)
    projected_savings = renewal - coop if renewal > 0 and coop > 0 else 0
    savings_pct = round((projected_savings / renewal) * 100, 0) if renewal > 0 else 0

    with col1:
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

    with col2:
        st.markdown(f"""
        <div style="display: flex; justify-content: flex-end;">
            <div class="recommendation-banner">
                <span style="color: #00a63e; font-size: 18px;">✓</span>
                <span style="color: #00a63e; font-size: 18px;">✓</span>
                <span class="recommendation-text">ICHRA + Cooperative Recommended</span>
            </div>
        </div>
        <p style="text-align: right; margin-top: 8px;">
            Projected savings: <span class="savings-amount">${projected_savings:,.0f}/month</span>
            <span style="color: #4a5565;">({savings_pct:.0f}%)</span>
        </p>
        <p style="text-align: right; color: #6a7282; font-size: 14px;">
            with 70% cooperative adoption
        </p>
        """, unsafe_allow_html=True)


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
# CURRENT PLAN PROBLEMS
# =============================================================================

def render_plan_problems(data: DashboardData):
    st.markdown('<p class="card-title">Current plan problems</p>', unsafe_allow_html=True)

    # Calculate employee cost share percentage
    ee_pct = 35  # Default
    if data.has_current_costs and data.current_premium > 0:
        # This would need actual employee share data from census
        ee_pct = 35  # Placeholder - could be calculated from census

    # Use display placeholders from constants
    deductible = DISPLAY_PLACEHOLDERS['typical_deductible']
    cost_min = DISPLAY_PLACEHOLDERS['employee_annual_cost_min']
    cost_max = DISPLAY_PLACEHOLDERS['employee_annual_cost_max']

    # Problem 1
    st.markdown(f"""
    <div class="error-box">
        <p class="error-title">Employees pay {ee_pct}% of premium + ${deductible:,} deductible</p>
        <p class="error-subtitle">
            Total employee cost: <strong style="font-family: Inter;">${cost_min:,}-${cost_max:,}/year</strong> before coverage kicks in
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Problem 2 - Affordability failures
    affordability_pct = AFFORDABILITY_THRESHOLD_2026 * 100
    if data.affordability_failures > 0:
        st.markdown(f"""
        <div class="error-box">
            <p style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
                <span style="color: #e7000b;">❌</span>
                <span class="error-title" style="margin: 0;">{data.affordability_failures} employees fail affordability test</span>
            </p>
            <p class="error-subtitle" style="margin-left: 26px;">({affordability_pct:.2f}% income threshold for {RENEWAL_PLAN_YEAR})</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="info-box">
            <p style="display: flex; align-items: center; gap: 8px;">
                <span style="color: #155dfc;">ℹ</span>
                <span style="color: #1c398e; font-weight: 500;">Affordability analysis available after contribution evaluation</span>
            </p>
        </div>
        """, unsafe_allow_html=True)

    # Consequence
    st.markdown("""
    <div class="info-box" style="margin-top: 16px;">
        <p style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
            <span style="color: #155dfc; font-weight: 700;">→</span>
            <span style="color: #101828; font-weight: 500;">Employees can't actually afford to use this coverage</span>
        </p>
        <p style="color: #364153; font-size: 14px; margin-left: 26px;">
            High premiums + high deductibles = unusable benefits
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <p style="font-style: italic; color: #4a5565; font-size: 14px; margin-top: 16px;">
        💡 ICHRA + Cooperative eliminates deductibles and makes care truly accessible
    </p>
    """, unsafe_allow_html=True)


# =============================================================================
# COMPARISON TABLE
# =============================================================================

def render_comparison_table(data: DashboardData, db=None, census_df: pd.DataFrame = None,
                             dependents_df: pd.DataFrame = None):
    # Title and subtitle row with scenario selector
    title_col, selector_col = st.columns([2, 1])

    with title_col:
        st.markdown("""
        <p style="font-size: 20px; font-weight: 500; color: #101828; margin-bottom: 4px;">Monthly premium by scenario</p>
        <p style="font-size: 16px; color: #4a5565; margin-bottom: 24px;">Monthly costs if all employees enrolled in each option</p>
        """, unsafe_allow_html=True)

    with selector_col:
        # Scenario selector
        scenario_options = ["Lowest average cost", "Youngest cost", "Oldest cost"]
        selected_scenario = st.radio(
            "Cost view",
            scenario_options,
            horizontal=True,
            label_visibility="collapsed",
            key="scenario_cost_view"
        )

    # Calculate tier costs based on selected scenario
    if selected_scenario == "Lowest average cost":
        # Use the pre-calculated average tier costs
        tier_costs_display = data.tier_costs
    else:
        # Calculate youngest or oldest tier costs
        mode = "youngest" if selected_scenario == "Youngest cost" else "oldest"
        coop_rates_df = load_cooperative_rate_table(db)
        tier_costs_display = calculate_tier_costs_by_age(
            census_df,
            multi_metal_results=data.multi_metal_results,
            mode=mode,
            cooperative_ratio=COOPERATIVE_CONFIG['default_discount_ratio'],
            coop_rates_df=coop_rates_df
        )

    # Helper to format currency or show N/A
    def fmt(val):
        return f"${val:,.0f}" if val and val > 0 else "N/A"

    # Helper to format savings (handles positive and negative)
    def fmt_savings(amount, pct):
        if amount is None or amount == 0:
            return ("N/A", "#6b7280")  # Gray for no data
        elif amount > 0:
            return (f"${amount:,.0f}", "#00a63e")  # Green for savings
        else:
            return (f"-${abs(amount):,.0f}", "#dc2626")  # Red for cost increase

    # Get DPC cost from constants
    dpc_cost = COOPERATIVE_CONFIG['dpc_monthly_cost']

    # Get tier costs with defaults - use dynamic plan year keys
    tiers = ["Employee Only", "Employee + Spouse", "Employee + Children", "Family"]
    current_key = f"Current {CURRENT_PLAN_YEAR}"
    renewal_key = f"Renewal {RENEWAL_PLAN_YEAR}"
    scenarios = [current_key, renewal_key, "ICHRA Bronze", "ICHRA Silver", "ICHRA Gold", "Cooperative"]

    # Map tier names to family status codes and multipliers
    tier_info = {
        "Employee Only": {"code": "EE", "multiplier": 1.0},
        "Employee + Spouse": {"code": "ES", "multiplier": 1.5},
        "Employee + Children": {"code": "EC", "multiplier": 1.3},
        "Family": {"code": "F", "multiplier": 1.8},
    }

    # Count employees per tier
    tier_counts = {}
    if census_df is not None and not census_df.empty and 'family_status' in census_df.columns:
        for tier_name, info in tier_info.items():
            tier_counts[tier_name] = len(census_df[census_df['family_status'] == info['code']])
    else:
        tier_counts = {tier: 0 for tier in tiers}

    # Build tier rows HTML
    tier_rows = ""
    for tier in tiers:
        tier_data = tier_costs_display.get(tier, {})
        # Find lowest cost for this tier
        ichra_costs = [tier_data.get(s, 0) for s in scenarios[2:]]  # ICHRA options only
        min_cost = min([c for c in ichra_costs if c > 0]) if any(c > 0 for c in ichra_costs) else 0

        # Get count and multiplier for this tier
        count = tier_counts.get(tier, 0)
        multiplier = tier_info.get(tier, {}).get('multiplier', 1.0)

        tier_rows += f'''<tr><td>{tier}<br><span class="tier-subtitle">{count} employees · {multiplier}x multiplier</span></td>'''
        for scenario in scenarios:
            val = tier_data.get(scenario, 0)
            is_lowest = val > 0 and val == min_cost and scenario in scenarios[2:]
            css_class = ' class="lowest-cost"' if is_lowest else ''
            tier_rows += f"<td{css_class}>{fmt(val)}</td>"
        tier_rows += "</tr>"

    # Build totals row with savings
    totals = data.company_totals  # ER portion only
    savings = data.savings_vs_renewal

    # Calculate total premium (ER + EE combined) for each scenario
    total_premium = {}
    # Current: sum of all premiums from census
    if census_df is not None and not census_df.empty:
        current_er = census_df['current_er_monthly'].fillna(0).sum() if 'current_er_monthly' in census_df.columns else 0
        current_ee = census_df['current_ee_monthly'].fillna(0).sum() if 'current_ee_monthly' in census_df.columns else 0
        total_premium[current_key] = current_er + current_ee
        # Renewal: full premium
        total_premium[renewal_key] = data.renewal_premium if data.renewal_premium else 0
    # ICHRA: full premium from multi_metal_results
    if data.multi_metal_results:
        for metal in ['Bronze', 'Silver', 'Gold']:
            metal_data = data.multi_metal_results.get(metal, {})
            total_premium[f'ICHRA {metal}'] = metal_data.get('total_monthly', 0)
        # Cooperative: Silver total * cooperative ratio (employer pays all)
        silver_total = data.multi_metal_results.get('Silver', {}).get('total_monthly', 0)
        total_premium['Cooperative'] = silver_total * COOPERATIVE_CONFIG['default_discount_ratio']

    # Custom HTML table
    st.markdown(f"""
    <style>
        .scenario-table {{
            width: 100%;
            border-collapse: collapse;
            font-family: 'Poppins', sans-serif;
            margin-bottom: 16px;
        }}
        .scenario-table th {{
            padding: 12px 16px;
            text-align: center;
            font-weight: 600;
            font-size: 14px;
            border-bottom: 2px solid #e5e7eb;
        }}
        .scenario-table td {{
            padding: 12px 16px;
            text-align: center;
            font-family: 'Inter', sans-serif;
            font-size: 16px;
            border-bottom: 1px solid #e5e7eb;
        }}
        .scenario-table td:first-child {{
            text-align: left;
            font-family: 'Poppins', sans-serif;
            font-weight: 500;
            color: #101828;
        }}
        .scenario-table .total-row td {{
            font-weight: 700;
            border-top: 2px solid #101828;
            padding-top: 16px;
        }}
        .scenario-table .savings-cell {{
            font-size: 14px;
            color: #00a63e;
        }}
        .col-header-current {{ background: #eff6ff; color: #1c398e; }}
        .col-header-renewal {{ background: #fef2f2; color: #82181a; border-left: 4px solid #ffa2a2; }}
        .col-header-bronze {{ background: #fffbeb; color: #7b3306; }}
        .col-header-silver {{ background: #f9fafb; color: #101828; }}
        .col-header-gold {{ background: #fefce8; color: #733e0a; }}
        .col-header-coop {{ background: #f0fdf4; color: #0d542b; }}
        .header-subtitle {{ font-size: 12px; font-weight: 400; color: #6a7282; }}
        .tier-subtitle {{ font-size: 12px; font-weight: 400; color: #6a7282; }}
        .silver-warning {{ font-size: 11px; color: #b45309; margin-top: 4px; }}
        .lowest-cost {{ color: #00a63e; font-weight: 700; }}
    </style>

    <table class="scenario-table">
        <thead>
            <tr>
                <th style="text-align: left; background: white;">Coverage type</th>
                <th class="col-header-current">{current_key}</th>
                <th class="col-header-renewal">{renewal_key}</th>
                <th class="col-header-bronze">
                    ICHRA Bronze<br>
                    <span class="header-subtitle">{data.metal_av.get('Bronze', 60):.1f}% AV</span>
                </th>
                <th class="col-header-silver">
                    ICHRA Silver<br>
                    <span class="header-subtitle">{data.metal_av.get('Silver', 70):.1f}% AV</span><br>
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
            {tier_rows}
            <tr class="total-row">
                <td style="font-weight: 700;">Total Premium</td>
                <td style="font-weight: 700;">{fmt(total_premium.get(current_key, 0))}</td>
                <td style="font-weight: 700;">{fmt(total_premium.get(renewal_key, 0))}</td>
                <td style="font-weight: 700;">{fmt(total_premium.get('ICHRA Bronze', 0))}</td>
                <td style="font-weight: 700;">{fmt(total_premium.get('ICHRA Silver', 0))}</td>
                <td style="font-weight: 700;">{fmt(total_premium.get('ICHRA Gold', 0))}</td>
                <td style="font-weight: 700;">{fmt(total_premium.get('Cooperative', 0))}</td>
            </tr>
            <tr>
                <td style="font-weight: 600;">ER Savings vs Renewal</td>
                <td></td>
                <td style="color: #6b7280;">—</td>
                <td style="color: {fmt_savings(savings.get('ICHRA Bronze', {}).get('amount'), savings.get('ICHRA Bronze', {}).get('pct'))[1]}; font-weight: 600;">
                    {fmt_savings(savings.get('ICHRA Bronze', {}).get('amount'), savings.get('ICHRA Bronze', {}).get('pct'))[0]}<br>
                    <span style="font-size: 12px;">({savings.get('ICHRA Bronze', {}).get('pct', 0):.1f}%)</span>
                </td>
                <td style="color: {fmt_savings(savings.get('ICHRA Silver', {}).get('amount'), savings.get('ICHRA Silver', {}).get('pct'))[1]}; font-weight: 600;">
                    {fmt_savings(savings.get('ICHRA Silver', {}).get('amount'), savings.get('ICHRA Silver', {}).get('pct'))[0]}<br>
                    <span style="font-size: 12px;">({savings.get('ICHRA Silver', {}).get('pct', 0):.1f}%)</span>
                </td>
                <td style="color: {fmt_savings(savings.get('ICHRA Gold', {}).get('amount'), savings.get('ICHRA Gold', {}).get('pct'))[1]}; font-weight: 600;">
                    {fmt_savings(savings.get('ICHRA Gold', {}).get('amount'), savings.get('ICHRA Gold', {}).get('pct'))[0]}<br>
                    <span style="font-size: 12px;">({savings.get('ICHRA Gold', {}).get('pct', 0):.1f}%)</span>
                </td>
                <td style="color: {fmt_savings(savings.get('Cooperative', {}).get('amount'), savings.get('Cooperative', {}).get('pct'))[1]}; font-weight: 600;">
                    {fmt_savings(savings.get('Cooperative', {}).get('amount'), savings.get('Cooperative', {}).get('pct'))[0]}<br>
                    <span style="font-size: 12px;">({savings.get('Cooperative', {}).get('pct', 0):.1f}%)</span>
                </td>
            </tr>
            <tr>
                <td style="font-weight: 600;">AFFORDABILITY</td>
                <td></td>
                <td style="color: #b45309;">{'⚠ ' + str(data.affordability_failures) + ' employees require subsidy' if data.affordability_failures > 0 else ''}</td>
                <td style="color: #00a63e;">✓ All employees affordable</td>
                <td style="color: #00a63e;">✓ All employees affordable</td>
                <td></td>
                <td style="color: #00a63e;">✓ All employees affordable</td>
            </tr>
        </tbody>
    </table>
    """, unsafe_allow_html=True)

    # Footer row
    footer_col1, footer_col2, footer_col3 = st.columns([2, 1, 1])

    with footer_col1:
        st.markdown(f"""
        <p style="font-size: 13px; color: #6b7280;">
            Total Premium = ER + EE combined. ER Savings based on {int(data.contribution_pct * 100)}% employer contribution.
        </p>
        """, unsafe_allow_html=True)

    with footer_col2:
        st.markdown("""
        <p style="text-align: right; font-size: 14px; color: #155dfc; cursor: pointer;">
            View contribution strategy →
        </p>
        """, unsafe_allow_html=True)

    with footer_col3:
        # CSV download button for detailed rate data
        if data.multi_metal_results and db is not None and census_df is not None:
            # Map selected scenario to CSV mode
            if selected_scenario == "Youngest cost":
                csv_scenario_mode = "youngest"
            elif selected_scenario == "Oldest cost":
                csv_scenario_mode = "oldest"
            else:
                csv_scenario_mode = "all"

            csv_df = generate_scenario_rates_csv(
                data.multi_metal_results, db, census_df, dependents_df,
                scenario_mode=csv_scenario_mode
            )
            if not csv_df.empty:
                csv_data = csv_df.to_csv(index=False)
                # Include scenario mode in filename
                scenario_suffix = f"_{csv_scenario_mode}" if csv_scenario_mode != "all" else ""
                st.download_button(
                    label="📥 Download rate details (CSV)",
                    data=csv_data,
                    file_name=f"ichra_scenario_rates{scenario_suffix}.csv",
                    mime="text/csv",
                    help="Download detailed plan data (Bronze, Silver, Gold) with deductibles, MOOP, and all employee metadata"
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

    # Calculate age bracket costs
    coop_rates_df = load_cooperative_rate_table(db)
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

    # Helper to format currency or show N/A
    def fmt(val):
        return f"${val:,.0f}" if val and val > 0 else "N/A"

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
            return (f"-${diff:,.0f}", "#00a63e")  # Savings (green)
        elif diff < 0:
            return (f"+${abs(diff):,.0f}", "#dc2626")  # Cost increase (red)
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
# EMPLOYEE CARDS
# =============================================================================

def render_employee_card(employee):
    # Build family ages string if available
    family_ages_str = ""
    family_ages = employee.get('family_ages', [])
    if family_ages:
        age_parts = []
        # Group by relationship type (values are 'spouse' and 'child' from dependents_df)
        spouse_ages = [f"Spouse ({fa['age']})" for fa in family_ages if fa.get('relationship', '').lower() == 'spouse']
        child_ages = [str(fa['age']) for fa in family_ages if fa.get('relationship', '').lower() == 'child']
        if spouse_ages:
            age_parts.extend(spouse_ages)
        if child_ages:
            if len(child_ages) == 1:
                age_parts.append(f"Child ({child_ages[0]})")
            else:
                age_parts.append(f"Children ({', '.join(child_ages)})")
        if age_parts:
            family_ages_str = f"<br><span style='font-size: 13px; color: #6b7280;'>{' | '.join(age_parts)}</span>"

    # Card header
    st.markdown(f"""
    <div style="border-bottom: 2px solid #e5e7eb; padding-bottom: 16px; margin-bottom: 16px;">
        <p style="font-size: 18px; font-weight: 700; color: #101828; margin-bottom: 4px;">{employee['label']}: {employee['name']}</p>
        <p style="font-size: 14px; color: #4a5565; margin-bottom: 2px;">
            <strong>Age {employee['age']}</strong> | {employee['tier']}{family_ages_str}
        </p>
        <p style="font-size: 14px; color: #4a5565;">{employee['location']}</p>
    </div>
    """, unsafe_allow_html=True)

    # Mini comparison table with colored headers
    winner = employee['winner']
    costs = employee['costs']
    st.markdown(f"""
    <style>
        .emp-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
            margin-bottom: 12px;
        }}
        .emp-table th {{
            padding: 8px 6px;
            font-weight: 600;
            font-size: 11px;
            text-align: center;
            border-bottom: 1px solid #e5e7eb;
        }}
        .emp-table td {{
            padding: 6px;
            text-align: center;
            font-family: 'Inter', sans-serif;
        }}
        .emp-table td:first-child {{
            text-align: left;
            font-family: 'Poppins', sans-serif;
            font-weight: 500;
            color: #364153;
        }}
        .emp-table .winner-row td {{
            font-weight: 500;
        }}
        .th-current {{ background: #eff6ff; color: #1c398e; }}
        .th-renewal {{ background: #fef2f2; color: #82181a; }}
        .th-bronze {{ background: #fef3c7; color: #92400e; }}
        .th-silver {{ background: #f3f4f6; color: #374151; }}
        .th-gold {{ background: #fef9c3; color: #854d0e; }}
        .th-coop {{ background: #f0fdf4; color: #0d542b; }}
    </style>

    <table class="emp-table">
        <thead>
            <tr>
                <th style="text-align: left; background: white;"></th>
                <th class="th-current">Current</th>
                <th class="th-renewal">Renewal</th>
                <th class="th-bronze">Bronze</th>
                <th class="th-silver">Silver</th>
                <th class="th-gold">Gold</th>
                <th class="th-coop">Coop</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td>Employee</td>
                <td>${costs['Current']['employee']:,.0f}</td>
                <td>${costs['Renewal']['employee']:,.0f}</td>
                <td>${costs['ICHRA Bronze']['employee']:,.0f}</td>
                <td>${costs['ICHRA Silver']['employee']:,.0f}</td>
                <td>${costs['ICHRA Gold']['employee']:,.0f}</td>
                <td>${costs['Cooperative']['employee']:,.0f}</td>
            </tr>
            <tr>
                <td>Employer</td>
                <td>${costs['Current']['employer']:,.0f}</td>
                <td>${costs['Renewal']['employer']:,.0f}</td>
                <td>${costs['ICHRA Bronze']['employer']:,.0f}</td>
                <td>${costs['ICHRA Silver']['employer']:,.0f}</td>
                <td>${costs['ICHRA Gold']['employer']:,.0f}</td>
                <td>${costs['Cooperative']['employer']:,.0f}</td>
            </tr>
            <tr style="border-top: 1px solid #e5e7eb; font-weight: 600;">
                <td>Total</td>
                <td>${costs['Current']['employee'] + costs['Current']['employer']:,.0f}</td>
                <td>${costs['Renewal']['employee'] + costs['Renewal']['employer']:,.0f}</td>
                <td>${costs['ICHRA Bronze']['employee'] + costs['ICHRA Bronze']['employer']:,.0f}</td>
                <td>${costs['ICHRA Silver']['employee'] + costs['ICHRA Silver']['employer']:,.0f}</td>
                <td>${costs['ICHRA Gold']['employee'] + costs['ICHRA Gold']['employer']:,.0f}</td>
                <td>${costs['Cooperative']['employee'] + costs['Cooperative']['employer']:,.0f}</td>
            </tr>
        </tbody>
    </table>
    """, unsafe_allow_html=True)

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
        current_total = employee.get('current_total_monthly', 0)
        renewal_total = employee.get('renewal_total_monthly', 0)
        use_ee_rate_only = employee.get('use_ee_rate_only', False)

        if metal_plan_details:
            # Helper function to format currency
            def fmt_currency(val):
                if val is None:
                    return "N/A"
                return f"${val:,.0f}"

            # Helper to format variance with color
            def fmt_variance(val):
                if val is None:
                    return ("N/A", "#6b7280")
                elif val > 0:
                    return (f"+${val:,.0f}", "#dc2626")  # Red for higher cost
                elif val < 0:
                    return (f"-${abs(val):,.0f}", "#00a63e")  # Green for savings
                else:
                    return ("$0", "#6b7280")

            # Build data for each metal
            plan_data = {}
            for metal in ['Bronze', 'Silver', 'Gold']:
                details = metal_plan_details.get(metal, {})
                if details:
                    if use_ee_rate_only:
                        tier_premium = details.get('ee_rate', 0) or 0
                    else:
                        tier_premium = details.get('estimated_tier_premium', 0) or 0

                    variance_current = (tier_premium - current_total) * 12 if current_total > 0 else None
                    variance_renewal = (tier_premium - renewal_total) * 12 if renewal_total > 0 else None

                    plan_data[metal] = {
                        'plan_name': details.get('plan_name') or 'N/A',
                        'deductible': details.get('deductible'),
                        'moop': details.get('moop'),
                        'annual_cost': tier_premium * 12 if tier_premium else None,
                        'variance_current': variance_current,
                        'variance_renewal': variance_renewal,
                    }

            if plan_data:
                # Get plan names (allow wrapping)
                bronze_name = plan_data.get('Bronze', {}).get('plan_name') or 'N/A'
                silver_name = plan_data.get('Silver', {}).get('plan_name') or 'N/A'
                gold_name = plan_data.get('Gold', {}).get('plan_name') or 'N/A'

                # Get values with defaults
                bronze = plan_data.get('Bronze', {})
                silver = plan_data.get('Silver', {})
                gold = plan_data.get('Gold', {})

                # Format variance cells
                bronze_vs_current = fmt_variance(bronze.get('variance_current'))
                bronze_vs_renewal = fmt_variance(bronze.get('variance_renewal'))
                silver_vs_current = fmt_variance(silver.get('variance_current'))
                silver_vs_renewal = fmt_variance(silver.get('variance_renewal'))
                gold_vs_current = fmt_variance(gold.get('variance_current'))
                gold_vs_renewal = fmt_variance(gold.get('variance_renewal'))

                st.markdown(f"""
                <style>
                    .plan-details-table {{
                        width: 100%;
                        border-collapse: collapse;
                        font-family: 'Poppins', sans-serif;
                        margin-bottom: 8px;
                    }}
                    .plan-details-table th {{
                        padding: 10px 12px;
                        text-align: center;
                        font-weight: 600;
                        font-size: 13px;
                        border-bottom: 2px solid #e5e7eb;
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
                    .pd-header-bronze {{ background: #fef3c7; color: #92400e; }}
                    .pd-header-silver {{ background: #f3f4f6; color: #374151; }}
                    .pd-header-gold {{ background: #fef9c3; color: #854d0e; }}
                    .pd-plan-name {{ font-size: 11px; font-weight: 400; color: #6b7280; margin-top: 4px; line-height: 1.3; }}
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
                            <td>Annual Cost</td>
                            <td>{fmt_currency(bronze.get('annual_cost'))}</td>
                            <td>{fmt_currency(silver.get('annual_cost'))}</td>
                            <td>{fmt_currency(gold.get('annual_cost'))}</td>
                        </tr>
                        <tr>
                            <td>vs Current</td>
                            <td style="color: {bronze_vs_current[1]};">{bronze_vs_current[0]}</td>
                            <td style="color: {silver_vs_current[1]};">{silver_vs_current[0]}</td>
                            <td style="color: {gold_vs_current[1]};">{gold_vs_current[0]}</td>
                        </tr>
                        <tr>
                            <td>vs Renewal</td>
                            <td style="color: {bronze_vs_renewal[1]};">{bronze_vs_renewal[0]}</td>
                            <td style="color: {silver_vs_renewal[1]};">{silver_vs_renewal[0]}</td>
                            <td style="color: {gold_vs_renewal[1]};">{gold_vs_renewal[0]}</td>
                        </tr>
                    </tbody>
                </table>
                """, unsafe_allow_html=True)

                rate_type = "individual (EE) rate" if use_ee_rate_only else "tier premium"
                st.caption(f"Lowest cost plan at each metal level. Annual Cost = {rate_type} × 12.")
            else:
                st.info("Plan details not available.")
        else:
            st.info("Plan details not available. Complete contribution analysis to see plan options.")


def render_employee_examples(data: DashboardData):
    st.markdown("""
    <p style="font-size: 20px; font-weight: 500; color: #101828; margin-bottom: 4px;">How this affects your employees</p>
    <p style="font-size: 16px; color: #4a5565; margin-bottom: 24px;">Three representative examples showing employer vs. employee costs</p>
    """, unsafe_allow_html=True)

    if not data.employee_examples:
        st.info("Employee examples will be available after census upload and contribution analysis")
        return

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
    if st.button("📄 Export proposal to PDF", type="primary", width="stretch"):
        st.toast("PDF export coming soon!", icon="📄")


# =============================================================================
# MAIN LAYOUT
# =============================================================================

# Page title
st.title("ICHRA Comparison Dashboard")

# Check for census data
census_df = st.session_state.get('census_df')
if census_df is None or (hasattr(census_df, 'empty') and census_df.empty):
    st.warning("No census data loaded. Please upload a census file on the Census input page first.")
    st.info("This dashboard will display ICHRA comparison analysis once census data is available.")

    # Show demo mode option
    if st.button("Load demo data for preview"):
        st.info("Demo mode not yet implemented. Please upload actual census data.")
    st.stop()

# Get database connection
db = None
try:
    db = get_database_connection()
except Exception as e:
    st.warning(f"Database connection unavailable: {e}")

# =============================================================================
# SIDEBAR: Scenario Settings (User-Adjustable)
# =============================================================================
with st.sidebar:
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
        render_plan_problems(data)

st.markdown("<br>", unsafe_allow_html=True)

# Row 2: Comparison Table (by Family Status)
with st.container(border=True):
    render_comparison_table(data, db=db, census_df=census_df,
                            dependents_df=st.session_state.get('dependents_df'))

st.markdown("<br>", unsafe_allow_html=True)

# Row 3: Age Bracket Table
with st.container(border=True):
    render_age_bracket_table(data, db=db, census_df=census_df)

st.markdown("<br>", unsafe_allow_html=True)

# Row 4: Employee Examples
render_employee_examples(data)

st.markdown("<br>", unsafe_allow_html=True)

# Row 4: Key Messages + Expected Adoption
col1, col2 = st.columns([2, 1])

with col1:
    with st.container(border=True):
        render_key_messages(data)

with col2:
    with st.container(border=True):
        render_expected_adoption(data)
