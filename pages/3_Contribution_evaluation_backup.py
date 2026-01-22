"""
Contribution Evaluation Page - AI-Powered ICHRA Analysis
Evaluates what employees can get on the marketplace for their current contribution.
"""

import streamlit as st
import pandas as pd
import json
import logging
import os
import plotly.graph_objects as go

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed, will use system env vars

# Try to import anthropic
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

from database import get_database_connection
from contribution_strategies import calculate_affordability_impact
from queries import MarketplaceQueries
from utils import render_feedback_sidebar


def get_anthropic_api_key():
    """Get Anthropic API key from environment or Streamlit secrets."""
    # Check environment variable first
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if api_key:
        return api_key
    # Check Streamlit secrets
    try:
        if hasattr(st, 'secrets') and 'anthropic' in st.secrets:
            if 'api_key' in st.secrets['anthropic']:
                return st.secrets['anthropic']['api_key']
        # Also check top-level ANTHROPIC_API_KEY in secrets
        if hasattr(st, 'secrets') and 'ANTHROPIC_API_KEY' in st.secrets:
            return st.secrets['ANTHROPIC_API_KEY']
    except Exception:
        pass
    return None


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Page config
st.set_page_config(page_title="Contribution Evaluation", page_icon="💰", layout="wide")

# Sidebar: Client name for exports
with st.sidebar:
    st.markdown("**📋 Client Name**")
    if 'client_name' not in st.session_state:
        st.session_state.client_name = ''
    st.text_input(
        "Client name",
        placeholder="Enter client name",
        key="client_name",
        help="Used in export filenames",
        label_visibility="collapsed"
    )

# Scroll fix CSS removed - was causing button interaction issues

# =============================================================================
# STYLING
# =============================================================================

BADGE_CSS = """
<style>
/* ============================================
   BASE STYLES & VARIABLES
   ============================================ */
:root {
    --gray-50: #f9fafb;
    --gray-100: #f3f4f6;
    --gray-200: #e5e7eb;
    --gray-300: #d1d5db;
    --gray-400: #9ca3af;
    --gray-500: #6b7280;
    --gray-600: #4b5563;
    --gray-700: #374151;
    --gray-800: #1f2937;
    --gray-900: #111827;

    --blue-50: #eff6ff;
    --blue-100: #dbeafe;
    --blue-500: #3b82f6;
    --blue-600: #2563eb;
    --blue-700: #1d4ed8;

    --green-50: #f0fdf4;
    --green-100: #dcfce7;
    --green-500: #22c55e;
    --green-600: #16a34a;
    --green-700: #15803d;

    --amber-50: #E8F1FD;
    --amber-100: #B3D4FC;
    --amber-500: #0047AB;
    --amber-600: #003d91;

    --red-50: #fef2f2;
    --red-100: #fee2e2;
    --red-500: #ef4444;
    --red-600: #dc2626;
}

/* ============================================
   SIDEBAR STYLING
   ============================================ */
[data-testid="stSidebar"] {
    background-color: #F0F4FA;
}
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
[data-testid="stSidebar"] button {
    background-color: #E8F1FD !important;
    border: 1px solid #B3D4FC !important;
    color: #0047AB !important;
}
[data-testid="stSidebar"] button:hover {
    background-color: #B3D4FC !important;
    border-color: #0047AB !important;
}
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

/* ============================================
   SECTION CARDS
   ============================================ */
.section-card {
    background: white;
    border: 1px solid var(--gray-200);
    border-radius: 12px;
    padding: 1.5rem;
    margin-bottom: 1rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}

.section-card--highlight {
    border-left: 4px solid var(--blue-500);
}

.section-card--success {
    border-left: 4px solid var(--green-500);
    background: linear-gradient(to right, var(--green-50), white 20%);
}

.section-card--warning {
    border-left: 4px solid var(--amber-500);
    background: linear-gradient(to right, var(--amber-50), white 20%);
}

.section-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--gray-700);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 1rem;
    padding-bottom: 0.75rem;
    border-bottom: 1px solid var(--gray-100);
}

.section-header-icon {
    width: 20px;
    height: 20px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--gray-100);
    border-radius: 6px;
    font-size: 0.75rem;
}

/* ============================================
   STATS GRID (for employee details, premiums)
   ============================================ */
.stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
    gap: 1.5rem;
}

.stat-item {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
}

.stat-label {
    font-size: 0.75rem;
    font-weight: 500;
    color: var(--gray-500);
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

.stat-value {
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--gray-900);
    letter-spacing: -0.02em;
}

.stat-value--small {
    font-size: 1.125rem;
}

.stat-value--large {
    font-size: 2rem;
}

/* ============================================
   PREMIUM DISPLAY (the 3-column layout)
   ============================================ */
.premium-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 1rem;
    margin-top: 1rem;
}

.premium-item {
    padding: 1rem;
    border-radius: 8px;
    background: var(--gray-50);
    border: 1px solid var(--gray-100);
}

.premium-item--total {
    background: var(--gray-100);
}

.premium-item--employer {
    background: var(--blue-50);
    border-color: var(--blue-100);
}

.premium-item--employee {
    background: var(--green-50);
    border-color: var(--green-100);
}

.premium-item--employee-warning {
    background: var(--amber-50);
    border-color: var(--amber-100);
}

.premium-label {
    font-size: 0.75rem;
    font-weight: 500;
    color: var(--gray-500);
    margin-bottom: 0.25rem;
}

.premium-value {
    font-size: 1.75rem;
    font-weight: 700;
    color: var(--gray-900);
    letter-spacing: -0.02em;
}

.premium-item--employer .premium-value {
    color: var(--blue-700);
}

.premium-item--employee .premium-value {
    color: var(--green-700);
}

.premium-item--employee-warning .premium-value {
    color: var(--amber-600);
}

/* ============================================
   PLAN BADGE (the main improvement you asked for)
   ============================================ */
.plan-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.625rem;
    padding: 0.625rem 1rem;
    background: white;
    border: 1px solid var(--gray-200);
    border-radius: 8px;
    font-size: 0.875rem;
    box-shadow:
        0 1px 2px rgba(0,0,0,0.04),
        inset 0 1px 0 rgba(255,255,255,0.8);
    margin: 0.75rem 0;
}

.plan-badge-label {
    font-size: 0.625rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: white;
    background: var(--gray-500);
    padding: 0.25rem 0.5rem;
    border-radius: 4px;
}

.plan-badge-label--silver {
    background: linear-gradient(135deg, #94a3b8, #64748b);
}

.plan-badge-label--bronze {
    background: linear-gradient(135deg, #d97706, #b45309);
}

.plan-badge-label--gold {
    background: linear-gradient(135deg, #eab308, #ca8a04);
}

.plan-badge-name {
    font-weight: 600;
    color: var(--gray-800);
}

/* ============================================
   METADATA ROW (Plan ID, Deductible, OOPM)
   ============================================ */
.meta-row {
    display: flex;
    flex-wrap: wrap;
    gap: 1rem;
    margin-top: 1rem;
    padding-top: 1rem;
    border-top: 1px solid var(--gray-100);
}

.meta-item {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    font-size: 0.8125rem;
    color: var(--gray-600);
}

.meta-label {
    color: var(--gray-400);
}

.meta-value {
    font-weight: 600;
    color: var(--gray-700);
}

.meta-value--link {
    color: var(--blue-600);
    text-decoration: none;
}

.meta-value--link:hover {
    text-decoration: underline;
}

.meta-divider {
    color: var(--gray-300);
}

/* ============================================
   CONTRIBUTION BADGE
   ============================================ */
.contribution-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem 0.75rem;
    background: var(--blue-50);
    border: 1px solid var(--blue-100);
    border-radius: 6px;
    font-size: 0.8125rem;
    color: var(--blue-700);
    font-weight: 500;
    margin-top: 0.75rem;
}

/* ============================================
   PRICE DIFFERENCE INDICATOR
   ============================================ */
.price-diff {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.375rem 0.625rem;
    border-radius: 6px;
    font-size: 0.8125rem;
    font-weight: 600;
    margin-top: 0.75rem;
}

.price-diff--positive {
    background: var(--red-50);
    color: var(--red-600);
    border: 1px solid var(--red-100);
}

.price-diff--negative {
    background: var(--green-50);
    color: var(--green-600);
    border: 1px solid var(--green-100);
}

.price-diff-icon {
    font-size: 0.75rem;
}

/* ============================================
   UTILITY CLASSES
   ============================================ */
.text-muted { color: var(--gray-500); }
.text-small { font-size: 0.8125rem; }
.font-mono { font-family: ui-monospace, monospace; font-size: 0.8125rem; }
.mt-1 { margin-top: 0.5rem; }
.mt-2 { margin-top: 1rem; }
</style>
"""

st.markdown(BADGE_CSS, unsafe_allow_html=True)

# =============================================================================
# SESSION STATE INITIALIZATION
# =============================================================================

if 'db' not in st.session_state:
    st.session_state.db = get_database_connection()

if 'contribution_settings' not in st.session_state:
    st.session_state.contribution_settings = {
        'default_percentage': 75,
        'by_class': {},
        'contribution_type': 'percentage'
    }

if 'contribution_analysis' not in st.session_state:
    st.session_state.contribution_analysis = {}

if 'eval_chat_messages' not in st.session_state:
    st.session_state.eval_chat_messages = []

if 'selected_employee_id' not in st.session_state:
    st.session_state.selected_employee_id = None

# =============================================================================
# TOOL DEFINITIONS FOR AI
# =============================================================================

GET_MARKETPLACE_OPTIONS_TOOL = {
    "name": "get_marketplace_options",
    "description": "Get marketplace plan options for an employee based on their rating area, age, and family status. Returns plans with premiums, deductibles, and metal levels sorted by cost.",
    "input_schema": {
        "type": "object",
        "properties": {
            "employee_id": {
                "type": "string",
                "description": "Employee ID/Number from the census"
            },
            "metal_levels": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional filter by metal levels: Bronze, Silver, Gold, Platinum"
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of plans to return (default: 5)"
            }
        },
        "required": ["employee_id"]
    }
}

COMPARE_COSTS_TOOL = {
    "name": "compare_current_vs_marketplace",
    "description": "Compare an employee's current contribution to what they would pay for marketplace plans under ICHRA. Shows the cost difference (savings or additional cost).",
    "input_schema": {
        "type": "object",
        "properties": {
            "employee_id": {
                "type": "string",
                "description": "Employee ID/Number from the census"
            },
            "include_family": {
                "type": "boolean",
                "description": "Whether to include family members in the calculation (default: true for ES/EC/F statuses)"
            }
        },
        "required": ["employee_id"]
    }
}

GET_LCSP_TOOL = {
    "name": "get_lcsp",
    "description": "Get the Lowest Cost Silver Plan (LCSP) for an employee. Critical for ICHRA affordability safe harbor analysis under IRS rules.",
    "input_schema": {
        "type": "object",
        "properties": {
            "employee_id": {
                "type": "string",
                "description": "Employee ID/Number from the census"
            },
            "coverage_type": {
                "type": "string",
                "enum": ["self_only", "family"],
                "description": "Coverage type for LCSP lookup (default: based on family status)"
            }
        },
        "required": ["employee_id"]
    }
}

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_employee_by_id(employee_id: str) -> dict:
    """Get employee data from census by ID"""
    if 'census_df' not in st.session_state or st.session_state.census_df is None:
        return None

    df = st.session_state.census_df

    # Try to find by Employee Number column
    id_col = None
    for col in ['Employee Number', 'employee_number', 'EmployeeNumber', 'employee_id']:
        if col in df.columns:
            id_col = col
            break

    if id_col is None:
        return None

    # Convert to string for comparison
    matches = df[df[id_col].astype(str) == str(employee_id)]
    if matches.empty:
        return None

    row = matches.iloc[0]
    return row.to_dict()


def get_age_band(age: int) -> str:
    """Convert age to RBIS age band string"""
    if age <= 14:
        return "0-14"
    elif age >= 64:
        return "64 and over"
    else:
        return str(age)


def get_employer_contribution(employee: dict) -> float:
    """Calculate employer ICHRA contribution for an employee"""
    settings = st.session_state.contribution_settings
    family_status = str(employee.get('family_status', 'EE')).upper()
    contribution_type = settings.get('contribution_type', 'percentage')

    # Handle class-based contributions (from StrategyApplicator)
    if contribution_type == 'class_based':
        # Try to get employee_id from various column names
        employee_id = str(
            employee.get('employee_id') or
            employee.get('Employee Number') or
            employee.get('employee_number', '')
        )
        employee_assignments = settings.get('employee_assignments', {})

        # Direct lookup by employee_id
        if employee_id in employee_assignments:
            return float(employee_assignments[employee_id]['monthly_contribution'])

        # Fallback: find matching class by criteria
        classes = settings.get('classes', [])
        employee_age = employee.get('age') or employee.get('ee_age') or employee.get('Age')
        if employee_age is not None:
            try:
                employee_age = int(employee_age)
            except (ValueError, TypeError):
                employee_age = 30
        else:
            employee_age = 30

        employee_state = str(employee.get('state') or employee.get('Home State', '')).upper()

        for cls in classes:
            criteria = cls.get('criteria', {})

            # Check family status match
            if criteria.get('family_status') and criteria['family_status'] != family_status:
                continue

            # Check age range match (for age-banded)
            if 'age_min' in criteria and 'age_max' in criteria:
                if not (criteria['age_min'] <= employee_age <= criteria['age_max']):
                    continue

            # Check state match (for location-based)
            if criteria.get('state') and criteria['state'] != employee_state:
                continue

            # Found matching class
            return float(cls.get('monthly_contribution', 0))

        # No match found - return 0 (should not happen with proper setup)
        return 0.0

    # Handle percentage-based (default)
    else:
        # For percentage-based, we need the premium first - return the percentage
        return float(settings.get('default_percentage', 75))


def calculate_family_premium(employee: dict, plan_id: str, db) -> float:
    """Calculate total family premium for a plan using MarketplaceQueries"""
    family_status = str(employee.get('family_status', 'EE')).upper()
    rating_area_id = employee.get('rating_area_id')

    if not rating_area_id:
        return None

    total_premium = 0.0
    ra_id = int(rating_area_id)

    # Employee premium
    ee_age = employee.get('age', employee.get('ee_age', 30))
    age_band = get_age_band(int(ee_age))

    ee_rate = MarketplaceQueries.get_rate_by_plan_area_age(db, plan_id, ra_id, age_band)
    if ee_rate is None:
        return None

    total_premium = ee_rate

    # Add spouse if applicable
    if family_status in ['ES', 'F']:
        spouse_age = employee.get('spouse_age')
        if spouse_age:
            spouse_band = get_age_band(int(spouse_age))
            spouse_rate = MarketplaceQueries.get_rate_by_plan_area_age(db, plan_id, ra_id, spouse_band)
            if spouse_rate:
                total_premium += spouse_rate

    # Add children if applicable (max 3 oldest under 21 per ACA rules)
    if family_status in ['EC', 'F']:
        child_ages = []
        for i in range(2, 7):  # Dep 2 through Dep 6
            child_age = employee.get(f'dep_{i}_age')
            if child_age and int(child_age) < 21:
                child_ages.append(int(child_age))

        # Sort and take oldest 3
        child_ages.sort(reverse=True)
        for age in child_ages[:3]:
            child_band = get_age_band(age)
            child_rate = MarketplaceQueries.get_rate_by_plan_area_age(db, plan_id, ra_id, child_band)
            if child_rate:
                total_premium += child_rate

    return total_premium


# =============================================================================
# TOOL HANDLERS
# =============================================================================

def get_marketplace_options(employee_id: str, metal_levels: list = None, max_results: int = 5) -> dict:
    """Get marketplace plan options for an employee using MarketplaceQueries"""
    employee = get_employee_by_id(employee_id)
    if not employee:
        return {"error": f"Employee '{employee_id}' not found in census"}

    rating_area_id = employee.get('rating_area_id')
    if not rating_area_id:
        return {"error": f"No rating area found for employee '{employee_id}'. Check ZIP code mapping."}

    ee_age = employee.get('age', employee.get('ee_age', 30))
    age_band = get_age_band(int(ee_age))
    state = employee.get('state', employee.get('home_state', ''))

    try:
        db = st.session_state.db

        # Use MarketplaceQueries for plan lookup
        df = MarketplaceQueries.get_marketplace_plans_for_employee(
            db=db,
            state=state,
            rating_area_id=int(rating_area_id),
            age_band=age_band,
            metal_levels=metal_levels,
            limit=max_results,
            on_exchange_only=False
        )

        if df.empty:
            return {"error": f"No plans found for rating area {rating_area_id}, age {ee_age}"}

        # Get employer contribution
        contribution = get_employer_contribution(employee)
        settings = st.session_state.contribution_settings
        family_status = str(employee.get('family_status', 'EE')).upper()

        plans = []
        for _, row in df.iterrows():
            ee_premium = float(row['monthly_premium'])

            # Calculate family premium if applicable
            if family_status in ['ES', 'EC', 'F']:
                family_premium = calculate_family_premium(employee, row['plan_id'], db)
                if family_premium:
                    premium = family_premium
                else:
                    # Fallback to employee-only if family calc fails
                    premium = ee_premium
            else:
                premium = ee_premium

            # Calculate employee cost based on contribution type
            if settings.get('contribution_type') == 'class_based':
                # Class-based: contribution is a fixed dollar amount
                employee_cost = max(0, premium - contribution)
            else:
                # Percentage-based (default)
                employer_pays = premium * (contribution / 100)
                employee_cost = premium - employer_pays

            plan_info = {
                "plan_id": row['plan_id'],
                "plan_name": row['plan_name'],
                "metal_level": row['metal_level'],
                "plan_type": row['plan_type'],
                "total_premium": f"${premium:,.2f}",
                "employee_cost": f"${employee_cost:,.2f}",
                "_premium_num": premium,
                "_employee_cost_num": employee_cost
            }

            # Add family status info for clarity
            if family_status in ['ES', 'EC', 'F']:
                plan_info['ee_only_premium'] = f"${ee_premium:,.2f}"
                plan_info['is_family_rate'] = True

            plans.append(plan_info)

        return {
            "employee_id": employee_id,
            "employee_name": f"{employee.get('first_name', '')} {employee.get('last_name', '')}".strip(),
            "rating_area": rating_area_id,
            "age": ee_age,
            "family_status": employee.get('family_status', 'EE'),
            "plans": plans,
            "num_plans": len(plans),
            "employer_contribution": f"${contribution:,.2f}/mo" if settings.get('contribution_type') == 'class_based' else f"{contribution}%"
        }

    except Exception as e:
        logger.error(f"Error getting marketplace options: {e}")
        return {"error": str(e)}


def compare_current_vs_marketplace(employee_id: str, include_family: bool = True) -> dict:
    """Compare current contribution to marketplace options"""
    employee = get_employee_by_id(employee_id)
    if not employee:
        return {"error": f"Employee '{employee_id}' not found in census"}

    # Get current contribution from census (columns are lowercase after parsing)
    current_ee = employee.get('current_ee_monthly', 0)
    current_er = employee.get('current_er_monthly', 0)

    # Parse contribution values
    def parse_currency(val):
        if pd.isna(val) or val == '' or val is None:
            return 0.0
        if isinstance(val, (int, float)):
            return float(val)
        return float(str(val).replace('$', '').replace(',', '').strip() or 0)

    current_ee = parse_currency(current_ee)
    current_er = parse_currency(current_er)
    current_total = current_ee + current_er

    # Get marketplace options
    options_result = get_marketplace_options(employee_id, max_results=5)
    if "error" in options_result:
        return options_result

    family_status = str(employee.get('family_status', 'EE')).upper()
    settings = st.session_state.contribution_settings

    # Calculate family premiums if needed
    if include_family and family_status in ['ES', 'EC', 'F']:
        db = st.session_state.db
        for plan in options_result['plans']:
            family_premium = calculate_family_premium(employee, plan['plan_id'], db)
            if family_premium:
                plan['family_premium'] = f"${family_premium:,.2f}"
                plan['_family_premium_num'] = family_premium

                # Recalculate employee cost for family
                if settings.get('contribution_type') == 'class_based':
                    contribution = get_employer_contribution(employee)
                    plan['family_employee_cost'] = f"${max(0, family_premium - contribution):,.2f}"
                else:
                    contribution_pct = settings.get('default_percentage', 75) / 100
                    employer_pays = family_premium * contribution_pct
                    plan['family_employee_cost'] = f"${family_premium - employer_pays:,.2f}"

    # Build comparison
    comparisons = []
    for plan in options_result['plans']:
        if include_family and family_status in ['ES', 'EC', 'F'] and '_family_premium_num' in plan:
            marketplace_employee_cost = float(plan.get('family_employee_cost', '0').replace('$', '').replace(',', ''))
            marketplace_total = plan['_family_premium_num']
        else:
            marketplace_employee_cost = plan['_employee_cost_num']
            marketplace_total = plan['_premium_num']

        cost_delta = marketplace_employee_cost - current_ee

        comparisons.append({
            "plan_id": plan.get('plan_id', 'N/A'),
            "plan_name": plan['plan_name'],
            "metal_level": plan['metal_level'],
            "plan_type": plan.get('plan_type', 'N/A'),
            "marketplace_total_premium": f"${marketplace_total:,.2f}",
            "marketplace_employee_pays": f"${marketplace_employee_cost:,.2f}",
            "current_employee_pays": f"${current_ee:,.2f}",
            "monthly_difference": f"${cost_delta:+,.2f}",
            "annual_difference": f"${cost_delta * 12:+,.2f}",
            "saves_money": cost_delta < 0
        })

    return {
        "employee_id": employee_id,
        "employee_name": f"{employee.get('first_name', '')} {employee.get('last_name', '')}".strip(),
        "family_status": family_status,
        "current_contribution": {
            "employee_pays": f"${current_ee:,.2f}/mo",
            "employer_pays": f"${current_er:,.2f}/mo",
            "total": f"${current_total:,.2f}/mo"
        },
        "has_current_data": current_ee > 0 or current_er > 0,
        "comparisons": comparisons,
        "summary": f"Found {len(comparisons)} marketplace options to compare"
    }


def get_lcsp(employee_id: str, coverage_type: str = None) -> dict:
    """Get Lowest Cost Silver Plan for affordability analysis using MarketplaceQueries"""
    employee = get_employee_by_id(employee_id)
    if not employee:
        return {"error": f"Employee '{employee_id}' not found in census"}

    rating_area_id = employee.get('rating_area_id')
    if not rating_area_id:
        return {"error": f"No rating area found for employee '{employee_id}'"}

    ee_age = employee.get('age', employee.get('ee_age', 30))
    age_band = get_age_band(int(ee_age))
    family_status = str(employee.get('family_status', 'EE')).upper()
    state = employee.get('state', employee.get('home_state', ''))

    # Determine coverage type
    if coverage_type is None:
        coverage_type = 'family' if family_status in ['ES', 'EC', 'F'] else 'self_only'

    try:
        db = st.session_state.db

        # Get LCSP using MarketplaceQueries (on-exchange only for IRS safe harbor)
        lcsp = MarketplaceQueries.get_lcsp_for_employee(
            db=db,
            state=state,
            rating_area_id=int(rating_area_id),
            age_band=age_band
        )

        if lcsp is None:
            return {"error": f"No Silver plans found for rating area {rating_area_id}"}

        lcsp_premium = lcsp['monthly_premium']
        plan_id = lcsp['plan_id']

        # For family coverage, calculate total family premium
        if coverage_type == 'family' and family_status in ['ES', 'EC', 'F']:
            family_premium = calculate_family_premium(employee, plan_id, db)
            if family_premium:
                lcsp_premium = family_premium

        # Get deductible and OOPM using MarketplaceQueries
        cost_share = MarketplaceQueries.get_deductible_and_oopm(db, plan_id)
        deductible = cost_share['deductible']
        oopm = cost_share['oopm']

        def format_dollar(val):
            if pd.isna(val) or val is None:
                return "N/A"
            try:
                return f"${float(val):,.0f}"
            except (ValueError, TypeError):
                return str(val)

        # Calculate affordability threshold (9.12% of household income for 2026)
        # Using 9.96% as safe harbor
        monthly_income = employee.get('monthly_income', 0)
        if monthly_income:
            monthly_income = float(str(monthly_income).replace('$', '').replace(',', '').strip() or 0)
            affordability_threshold = monthly_income * 0.0996
            is_affordable = lcsp_premium <= affordability_threshold
        else:
            affordability_threshold = None
            is_affordable = None

        return {
            "employee_id": employee_id,
            "employee_name": f"{employee.get('first_name', '')} {employee.get('last_name', '')}".strip(),
            "coverage_type": coverage_type,
            "lcsp": {
                "plan_id": plan_id,
                "plan_name": lcsp['plan_name'],
                "metal_level": lcsp['metal_level'],
                "plan_type": lcsp.get('plan_type', 'N/A'),
                "deductible": format_dollar(deductible),
                "oopm": format_dollar(oopm),
                "monthly_premium": f"${lcsp_premium:,.2f}"
            },
            "affordability": {
                "threshold_pct": "9.96%",
                "monthly_threshold": f"${affordability_threshold:,.2f}" if affordability_threshold else "N/A (no income data)",
                "is_affordable": is_affordable
            } if affordability_threshold else None,
            "note": "LCSP is used for ICHRA affordability safe harbor. Employer contribution must make LCSP affordable (cost < 9.96% of household income)."
        }

    except Exception as e:
        logger.error(f"Error getting LCSP: {e}")
        return {"error": str(e)}


def get_equivalent_plan(employee_id: str, target_premium: float = None) -> dict:
    """Find the plan closest in price to the employee's current total premium using MarketplaceQueries"""
    employee = get_employee_by_id(employee_id)
    if not employee:
        return {"error": f"Employee '{employee_id}' not found in census"}

    rating_area_id = employee.get('rating_area_id')
    if not rating_area_id:
        return {"error": f"No rating area found for employee '{employee_id}'"}

    ee_age = employee.get('age', employee.get('ee_age', 30))
    age_band = get_age_band(int(ee_age))
    family_status = str(employee.get('family_status', 'EE')).upper()
    state = employee.get('state', employee.get('home_state', ''))

    # Get target premium from census if not provided
    if target_premium is None:
        current_ee = employee.get('current_ee_monthly', 0)
        current_er = employee.get('current_er_monthly', 0)

        def parse_currency(val):
            if pd.isna(val) or val == '' or val is None:
                return 0.0
            if isinstance(val, (int, float)):
                return float(val)
            return float(str(val).replace('$', '').replace(',', '').strip() or 0)

        target_premium = parse_currency(current_ee) + parse_currency(current_er)

    if target_premium <= 0:
        return {"error": "No current premium data to match against"}

    try:
        db = st.session_state.db

        # Get all available plans using MarketplaceQueries (get more plans to find best match)
        df = MarketplaceQueries.get_marketplace_plans_for_employee(
            db=db,
            state=state,
            rating_area_id=int(rating_area_id),
            age_band=age_band,
            metal_levels=None,  # All metal levels
            limit=100,  # Get more plans to find best match
            on_exchange_only=False
        )

        if df.empty:
            return {"error": f"No plans found for rating area {rating_area_id}"}

        # Calculate actual premium for each plan (individual or family)
        closest_plan = None
        smallest_diff = float('inf')

        for _, plan in df.iterrows():
            plan_id = plan['plan_id']

            # Calculate the appropriate premium based on family status
            if family_status in ['ES', 'EC', 'F']:
                actual_premium = calculate_family_premium(employee, plan_id, db)
                if not actual_premium:
                    continue  # Skip if family premium calculation fails
            else:
                actual_premium = float(plan['monthly_premium'])

            # Calculate absolute difference from target
            price_diff = abs(actual_premium - target_premium)

            # Track the closest match
            if price_diff < smallest_diff:
                smallest_diff = price_diff
                closest_plan = {
                    'plan_id': plan_id,
                    'plan_name': plan['plan_name'],
                    'metal_level': plan['metal_level'],
                    'plan_type': plan['plan_type'],
                    'exchange_status': plan.get('exchange_status', 'N/A'),
                    'premium': actual_premium
                }

        if not closest_plan:
            return {"error": "Could not calculate premiums for any available plans"}

        plan_id = closest_plan['plan_id']
        plan_premium = closest_plan['premium']

        # Get deductible and OOPM using MarketplaceQueries
        cost_share = MarketplaceQueries.get_deductible_and_oopm(db, plan_id)
        deductible = cost_share['deductible']
        oopm = cost_share['oopm']

        def format_dollar(val):
            if pd.isna(val) or val is None:
                return "N/A"
            try:
                return f"${float(val):,.0f}"
            except (ValueError, TypeError):
                return str(val)

        return {
            "plan_id": plan_id,
            "plan_name": closest_plan['plan_name'],
            "metal_level": closest_plan['metal_level'],
            "plan_type": closest_plan.get('plan_type', 'N/A'),
            "exchange_status": closest_plan.get('exchange_status', 'N/A'),
            "monthly_premium": f"${plan_premium:,.2f}",
            "deductible": format_dollar(deductible),
            "oopm": format_dollar(oopm),
            "target_premium": f"${target_premium:,.2f}",
            "difference": f"${plan_premium - target_premium:+,.2f}"
        }

    except Exception as e:
        logger.error(f"Error getting equivalent plan: {e}")
        return {"error": str(e)}


# =============================================================================
# AI CHAT FUNCTION
# =============================================================================

EVAL_SYSTEM_PROMPT = """You are an ICHRA contribution evaluation advisor helping employers understand the transition from group to individual marketplace coverage.

## CONTEXT
{context}

## YOUR ROLE
Help evaluate what employees can get on the Individual marketplace compared to their current group plan contributions. Focus on:
1. Finding marketplace plans that cost around what they currently pay
2. Showing the cost difference (savings or additional cost)
3. Explaining the trade-offs between current and marketplace options

## COST DISPLAY FORMAT
For family coverage (ES/EC/F), the tool results already include family premiums:
- "total_premium" field shows the FULL FAMILY PREMIUM (employee + dependents)
- "employee_cost" field shows what the employee pays after ICHRA contribution
- For family status EE (employee only), "total_premium" is the individual rate

ALWAYS clarify when showing family vs individual rates.

## TOOLS AVAILABLE
- get_marketplace_options: Returns plans with premiums already calculated for family status (ES/EC/F includes all family members)
- compare_current_vs_marketplace: Compare current vs marketplace costs
- get_lcsp: Get Lowest Cost Silver Plan for affordability analysis (returns self-only rate, use with family calculation if needed)

## RESPONSE STYLE
- Be concise and focus on actionable insights
- Lead with the bottom line (saves money vs costs more)
- Use specific dollar amounts
- Acknowledge when current contribution data is missing
"""


def get_evaluation_response(user_message: str, context: str) -> str:
    """Get AI response for contribution evaluation"""
    if not ANTHROPIC_AVAILABLE:
        return "AI evaluation requires the Anthropic library. Install with: pip install anthropic"

    api_key = get_anthropic_api_key()
    if not api_key:
        return "AI evaluation requires ANTHROPIC_API_KEY (set in environment or Streamlit secrets)."

    client = anthropic.Anthropic(api_key=api_key)

    # Build messages from history
    messages = []
    for msg in st.session_state.eval_chat_messages:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": user_message})

    available_tools = [GET_MARKETPLACE_OPTIONS_TOOL, COMPARE_COSTS_TOOL, GET_LCSP_TOOL]

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            system=EVAL_SYSTEM_PROMPT.format(context=context),
            messages=messages,
            tools=available_tools
        )

        # Handle tool use
        max_iterations = 3
        iteration = 0

        while response.stop_reason == "tool_use" and iteration < max_iterations:
            iteration += 1
            tool_results = []

            for block in response.content:
                if block.type == "tool_use":
                    tool_name = block.name
                    tool_input = block.input

                    if tool_name == "get_marketplace_options":
                        result = get_marketplace_options(
                            tool_input.get("employee_id", ""),
                            tool_input.get("metal_levels"),
                            tool_input.get("max_results", 5)
                        )
                    elif tool_name == "compare_current_vs_marketplace":
                        result = compare_current_vs_marketplace(
                            tool_input.get("employee_id", ""),
                            tool_input.get("include_family", True)
                        )
                    elif tool_name == "get_lcsp":
                        result = get_lcsp(
                            tool_input.get("employee_id", ""),
                            tool_input.get("coverage_type")
                        )
                    else:
                        result = {"error": f"Unknown tool: {tool_name}"}

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, indent=2)
                    })

            # Continue conversation
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4000,
                system=EVAL_SYSTEM_PROMPT.format(context=context),
                messages=messages,
                tools=available_tools
            )

        # Extract text response
        response_text = ""
        for block in response.content:
            if hasattr(block, 'text'):
                response_text += block.text

        return response_text

    except Exception as e:
        logger.error(f"AI evaluation error: {e}")
        return f"Error: {str(e)}"


# =============================================================================
# PAGE UI
# =============================================================================

st.markdown("""
<div class="hero-section">
    <div class="hero-title">💰 Contribution Evaluation</div>
    <p class="hero-subtitle">Evaluate what employees can get on the marketplace compared to their current contributions</p>
</div>
""", unsafe_allow_html=True)

# Check for census
if 'census_df' not in st.session_state or st.session_state.census_df is None:
    st.warning("⚠️ Please upload employee census data first.")
    st.markdown("Go to **1️⃣ Employee census** to upload your census file.")
    st.stop()

census_df = st.session_state.census_df
num_employees = len(census_df)

st.success(f"✓ {num_employees} employees loaded from census")

# ALE vs Non-ALE Context
is_ale = num_employees >= 50
if is_ale:
    st.info(
        "**⚖️ ALE Employer (50+ employees)** — Subject to ACA employer mandate. "
        "Primary goal is ensuring ICHRA contributions meet the **9.96% affordability threshold** "
        "to avoid IRS penalties. Use the affordability analysis tools below to verify compliance."
    )
else:
    st.info(
        "**🎯 Non-ALE Employer (<50 employees)** — Not subject to ACA employer mandate. "
        "You have flexibility to design contributions that may be **intentionally unaffordable**, "
        "allowing employees to decline ICHRA and qualify for marketplace subsidies instead. "
        "Use the **Subsidy Analysis** section to model this strategy."
    )

# Auto-run affordability analysis if income data exists
if 'affordability_analysis' not in st.session_state:
    # Check if any employees have income data
    has_income_data = census_df['monthly_income'].notna().any() if 'monthly_income' in census_df.columns else False

    if has_income_data:
        with st.spinner("Analyzing IRS affordability requirements..."):
            import time
            from affordability import AffordabilityAnalyzer, ContributionRecommender

            try:
                logging.info("=" * 60)
                logging.info("AFFORDABILITY: Starting IRS affordability analysis...")
                logging.info(f"AFFORDABILITY: Census has {len(census_df)} employees")
                afford_start = time.time()

                db = st.session_state.db
                logging.info("AFFORDABILITY: Calling AffordabilityAnalyzer.analyze_workforce()...")
                analysis = AffordabilityAnalyzer.analyze_workforce(census_df, db)
                afford_elapsed = time.time() - afford_start
                logging.info(f"AFFORDABILITY: analyze_workforce() completed in {afford_elapsed:.1f}s")

                # Check if analysis returned an error
                if 'error' in analysis:
                    logging.error(f"AFFORDABILITY: Analysis returned error: {analysis['error']}")
                    st.error(f"⚠️ Affordability analysis error: {analysis['error']}")
                    st.info("💡 Tip: Ensure your census has been processed with age and location data")
                    st.session_state.affordability_analysis = None
                else:
                    recommendations = ContributionRecommender.generate_recommendations(
                        analysis, census_df
                    )

                    st.session_state.affordability_analysis = {
                        'summary': analysis['summary'],
                        'recommendations': recommendations,
                        'employee_details': analysis['employee_details'],
                        'flagged_employees': analysis['flagged_employees']
                    }
            except Exception as e:
                import traceback
                error_details = traceback.format_exc()
                st.error(f"⚠️ Error running affordability analysis: {e}")
                st.info(f"💡 Census columns available: {', '.join(census_df.columns.tolist())}")
                with st.expander("🔍 Full error details (for debugging)"):
                    st.code(error_details)
                st.session_state.affordability_analysis = None
    else:
        st.info("ℹ️ Add 'Monthly Income' column to census for IRS affordability analysis")

# Check for current contribution data (columns are lowercase after parsing)
has_contribution_data = False
if 'current_ee_monthly' in census_df.columns or 'current_er_monthly' in census_df.columns:
    # Count how many have data
    ee_col = census_df.get('current_ee_monthly', pd.Series())
    er_col = census_df.get('current_er_monthly', pd.Series())
    has_data_count = ((ee_col.notna()) | (er_col.notna())).sum()
    if has_data_count > 0:
        has_contribution_data = True
        # Calculate totals
        total_ee = pd.to_numeric(ee_col, errors='coerce').fillna(0).sum()
        total_er = pd.to_numeric(er_col, errors='coerce').fillna(0).sum()
        total_premium = total_ee + total_er

        st.markdown("**📊 Current group plan costs**")
        contrib_col1, contrib_col2, contrib_col3, contrib_col4 = st.columns(4)
        contrib_col1.metric("EE monthly", f"${total_ee:,.0f}")
        contrib_col2.metric("ER monthly", f"${total_er:,.0f}")
        contrib_col3.metric("Total monthly", f"${total_premium:,.0f}")
        contrib_col4.metric("Employees w/ data", f"{has_data_count}/{num_employees}")
    else:
        st.warning("⚠️ Census has contribution columns but no data. Add 'Current EE Monthly' and 'Current ER Monthly' values for cost comparison.")
else:
    st.warning("⚠️ No current contribution data in census. Add 'Current EE Monthly' and 'Current ER Monthly' columns for cost comparison.")

st.markdown("---")

# =============================================================================
# UNIFIED CONTRIBUTION STRATEGY MODELER
# =============================================================================

st.markdown("## Contribution strategy modeler")
st.markdown("*Design contributions that meet IRS affordability requirements¹*")

# Load affordability context on first run
if 'affordability_context' not in st.session_state or not st.session_state.affordability_context.get('loaded'):
    with st.spinner("Loading affordability data..."):
        from affordability import load_affordability_context
        st.session_state.affordability_context = load_affordability_context(census_df, st.session_state.db)

aff_context = st.session_state.affordability_context

# -----------------------------------------------------------------------------
# AFFORDABILITY CONTEXT PANEL (Always Visible)
# -----------------------------------------------------------------------------
context_cols = st.columns(4)

with context_cols[0]:
    st.markdown("**Workforce**")
    workforce = aff_context.get('workforce', {})
    st.metric("Employees", workforce.get('total_employees', 0))
    st.caption(f"{len(workforce.get('states', []))} states | Avg age: {workforce.get('avg_age', 0):.0f}")

with context_cols[1]:
    st.markdown("**LCSP benchmark**")
    lcsp_data = aff_context.get('lcsp_data', {})
    lcsp_min = lcsp_data.get('min', 0)
    lcsp_max = lcsp_data.get('max', 0)
    lcsp_avg = lcsp_data.get('avg', 0)
    st.metric("Average", f"${lcsp_avg:,.0f}/mo")
    st.markdown(f"**Range: ${lcsp_min:,.0f} – ${lcsp_max:,.0f}**")

with context_cols[2]:
    # Current ER Spend
    from utils import ContributionComparison
    _contrib_totals = ContributionComparison.aggregate_contribution_totals(census_df)
    _current_er_annual = _contrib_totals.get('total_current_er_annual', 0)
    st.markdown("**Current ER spend**")
    st.metric("2025", f"${_current_er_annual:,.0f}")
    st.caption("Annual employer cost")

with context_cols[3]:
    # Projected 2026 ER Spend
    from financial_calculator import FinancialSummaryCalculator
    projected_2026_er = 0
    financial_summary = st.session_state.get('financial_summary')
    if financial_summary and financial_summary.get('renewal_monthly'):
        projected_2026_er = financial_summary['renewal_monthly'] * 12
    else:
        projected_data = FinancialSummaryCalculator.calculate_projected_2026_total(census_df)
        if projected_data['has_data']:
            projected_2026_er = projected_data['total_annual']
    st.markdown("**Projected ER spend**")
    if projected_2026_er > 0:
        st.metric("2026", f"${projected_2026_er:,.0f}")
        trend_pct = ((projected_2026_er / _current_er_annual) - 1) * 100 if _current_er_annual > 0 else 0
        st.caption(f"+{trend_pct:.0f}% trend" if trend_pct > 0 else "Projected renewal")
    else:
        st.metric("2026", "N/A")
        st.caption("Add '2026 Premium' to census")

# Current affordability status (compact display)
current_status = aff_context.get('current_status', {})
total_analyzed = current_status.get('affordable_at_current', 0) + current_status.get('needs_increase', 0)
total_employees = len(census_df) if 'census_df' in dir() else total_analyzed
if total_analyzed > 0:
    needs_increase_count = current_status.get('needs_increase', 0)
    affordable_count = current_status.get('affordable_at_current', 0)
    affordable_pct = (affordable_count / total_analyzed * 100) if total_analyzed > 0 else 0

    # Note if some employees lack income data
    missing_income_note = ""
    if total_analyzed < total_employees:
        missing_count = total_employees - total_analyzed
        missing_income_note = f" ({missing_count} employee{'s' if missing_count != 1 else ''} missing income data)"

    # Compact status line
    if needs_increase_count > 0:
        st.warning(f"⚠️ **{needs_increase_count}** of {total_analyzed} employees need contribution increase for affordability{missing_income_note}")
    else:
        st.success(f"✅ All {total_analyzed} employees meet affordability threshold{missing_income_note}")

    # Show which employees need increases
    if needs_increase_count > 0:
        lcsp_by_employee = aff_context.get('lcsp_data', {}).get('by_employee', {})
        employees_needing_increase = []

        for emp_id, emp_data in lcsp_by_employee.items():
            if not emp_data.get('is_affordable', True):
                gap = emp_data.get('gap', 0)
                if gap > 0:
                    employees_needing_increase.append({
                        'Employee ID': emp_id,
                        'Name': emp_data.get('name', 'N/A'),
                        'State': emp_data.get('state', 'N/A'),
                        'Age': emp_data.get('age', 'N/A'),
                        'LCSP': f"${emp_data.get('lcsp', 0):,.0f}",
                        'Current ER': f"${emp_data.get('current_er', 0):,.0f}",
                        'Min Required': f"${emp_data.get('min_er', 0):,.0f}",
                        'Gap': f"${gap:,.0f}/mo"
                    })

        if employees_needing_increase:
            with st.expander(f"View {len(employees_needing_increase)} employees needing contribution increase", expanded=False):
                st.dataframe(
                    pd.DataFrame(employees_needing_increase),
                    hide_index=True,
                    width='stretch'
                )
                st.caption("Gap = minimum additional monthly employer contribution needed for IRS affordability")

st.markdown("---")

# -----------------------------------------------------------------------------
# STRATEGY CONFIGURATION
# -----------------------------------------------------------------------------
st.markdown("### Strategy configuration")

# Initialize strategy config in session state
if 'strategy_config' not in st.session_state:
    st.session_state.strategy_config = {
        'active_strategy': 'flat_amount',
        'flat_amount': 400.0,
        'base_age': 21,
        'base_contribution': 200.0,
        'lcsp_percentage': 75,
        'fpl_buffer': 5.0,  # FPL Safe Harbor buffer
        'apply_family_multipliers': False,
        'apply_location_adjustment': False,
        'high_cost_adjustment': 100.0,
        'high_cost_states': [],
    }

# Strategy selection with radio buttons (explicit selection tracking)
STRATEGY_OPTIONS = {
    'flat_amount': 'Flat amount',
    'base_age_curve': 'Base age + ACA 3:1 curve',
    'percentage_lcsp': 'Percentage of LCSP',
    'fpl_safe_harbor': 'FPL Safe Harbor'
}

selected_strategy = st.radio(
    "Select contribution strategy",
    options=list(STRATEGY_OPTIONS.keys()),
    format_func=lambda x: STRATEGY_OPTIONS[x],
    index=list(STRATEGY_OPTIONS.keys()).index(st.session_state.strategy_config.get('active_strategy', 'base_age_curve')),
    key="strategy_selector",
    horizontal=True
)

# Update active strategy based on radio selection
st.session_state.strategy_config['active_strategy'] = selected_strategy

# Show configuration for selected strategy only
if selected_strategy == 'flat_amount':
    st.markdown("""
    All employees receive the same base contribution.
    Family multipliers can be applied on top.
    """)

    flat_amount = st.number_input(
        "Monthly contribution ($/month)",
        min_value=0.0,
        max_value=5000.0,
        value=float(st.session_state.strategy_config.get('flat_amount', 400.0)),
        step=25.0,
        key="flat_amount_input"
    )

    # Save to session state
    st.session_state.strategy_config['flat_amount'] = flat_amount

    if is_ale:
        st.info(f"""
        **${flat_amount:,.0f}/month** for all employees (before family multipliers).
        **ALE Note:** Verify this amount meets the 9.96% affordability threshold for your workforce
        using the affordability analysis below.
        """)
    else:
        st.info(f"""
        **${flat_amount:,.0f}/month** for all employees (before family multipliers).
        **Non-ALE Tip:** You can set this below the affordability threshold intentionally.
        Use **Subsidy Analysis** to see if employees would benefit more from marketplace subsidies.
        """)

elif selected_strategy == 'base_age_curve':
    st.markdown("""
    Set a base contribution at a reference age. The system scales contributions
    using the ACA 3:1 age curve (age 64 = 3x age 21).
    """)

    input_cols = st.columns(2)
    with input_cols[0]:
        base_age = st.selectbox(
            "Base age",
            options=[21, 25, 30, 35, 40],
            index=[21, 25, 30, 35, 40].index(st.session_state.strategy_config.get('base_age', 21)),
            key="base_age_select"
        )
    with input_cols[1]:
        base_contribution = st.number_input(
            "Base contribution ($/month)",
            min_value=0.0,
            max_value=5000.0,
            value=float(st.session_state.strategy_config.get('base_contribution', 200.0)),
            step=25.0,
            key="base_contribution_input"
        )

    # Save to session state
    st.session_state.strategy_config['base_age'] = base_age
    st.session_state.strategy_config['base_contribution'] = base_contribution

    # Preview curve scaling
    from constants import ACA_AGE_CURVE
    base_ratio = ACA_AGE_CURVE.get(base_age, 1.0)
    preview_ages = [21, 30, 40, 50, 64]
    preview_data = []
    for age in preview_ages:
        ratio = ACA_AGE_CURVE.get(age, 1.0)
        amount = base_contribution * (ratio / base_ratio)
        preview_data.append({"Age": age, "Contribution": f"${amount:,.0f}"})
    st.dataframe(pd.DataFrame(preview_data), hide_index=True, width='stretch')

elif selected_strategy == 'percentage_lcsp':
    st.markdown("""
    Each employee receives X% of their individual LCSP premium.
    Higher-cost employees get proportionally larger contributions.
    """)

    lcsp_percentage = st.slider(
        "Percentage of LCSP",
        min_value=50,
        max_value=100,
        value=st.session_state.strategy_config.get('lcsp_percentage', 75),
        step=5,
        format="%d%%",
        key="lcsp_pct_slider"
    )

    # Save to session state
    st.session_state.strategy_config['lcsp_percentage'] = lcsp_percentage

    if is_ale:
        st.info(f"""
        At **{lcsp_percentage}%**: Employees pay {100-lcsp_percentage}% of LCSP out-of-pocket.
        **ALE Note:** Higher percentages (90%+) more likely to meet 9.96% affordability threshold.
        """)
    else:
        st.info(f"""
        At **{lcsp_percentage}%**: Employees pay {100-lcsp_percentage}% of LCSP out-of-pocket.
        **Non-ALE Tip:** Lower percentages create intentional unaffordability.
        Use **Subsidy Analysis** to compare with marketplace subsidies.
        """)

elif selected_strategy == 'fpl_safe_harbor':
    from constants import FPL_ANNUAL_2026, FPL_SAFE_HARBOR_THRESHOLD_2026

    st.markdown("""
    **Guarantees IRS affordability for ALL employees** — no income data required.

    Uses the Federal Poverty Level (FPL) safe harbor: if an employee's cost for the
    lowest-cost silver plan (LCSP) is ≤ 9.96% of FPL, the ICHRA is deemed affordable
    for everyone regardless of actual income.
    """)

    # Show FPL details
    fpl_cols = st.columns(3)
    with fpl_cols[0]:
        st.metric("2026 FPL (Single)", f"${FPL_ANNUAL_2026:,.0f}/yr")
    with fpl_cols[1]:
        st.metric("9.96% Threshold", f"${FPL_SAFE_HARBOR_THRESHOLD_2026:,.0f}/mo")
    with fpl_cols[2]:
        fpl_buffer = st.number_input(
            "Safety buffer ($/mo)",
            min_value=0.0,
            max_value=50.0,
            value=float(st.session_state.strategy_config.get('fpl_buffer', 5.0)),
            step=1.0,
            key="fpl_buffer_input",
            help="Extra buffer above minimum to ensure compliance"
        )

    # Save to session state
    st.session_state.strategy_config['fpl_buffer'] = fpl_buffer

    st.info(f"""
    **How it works:** Each employee's contribution is set so their out-of-pocket cost
    for LCSP is ≤ ${FPL_SAFE_HARBOR_THRESHOLD_2026:,.0f}/month (plus ${fpl_buffer:,.0f} buffer).

    **Contribution formula:** `LCSP - ${FPL_SAFE_HARBOR_THRESHOLD_2026:,.0f} + ${fpl_buffer:,.0f}`

    ✅ **100% IRS compliant** — no affordability failures possible
    """)

    if not is_ale:
        st.warning("""
        **Non-ALE Note:** This strategy guarantees affordability by design. If your goal is to allow
        employees to qualify for marketplace subsidies, consider **Flat Amount** or **Percentage LCSP**
        strategies which can create intentional unaffordability.
        """)

st.markdown("---")

# -----------------------------------------------------------------------------
# MODIFIERS SECTION
# -----------------------------------------------------------------------------
st.markdown("### Modifiers")

modifier_cols = st.columns(2)

with modifier_cols[0]:
    apply_family_multipliers = st.checkbox(
        "Apply family multipliers",
        value=st.session_state.strategy_config.get('apply_family_multipliers', False),
        key="apply_family_mult"
    )
    if apply_family_multipliers:
        st.caption("EE=1.0x, ES=1.5x, EC=1.3x, F=1.8x")

with modifier_cols[1]:
    apply_location_adjustment = st.checkbox(
        "Apply location adjustment",
        value=st.session_state.strategy_config.get('apply_location_adjustment', False),
        key="apply_location_adj"
    )

# Save modifier values to session state
st.session_state.strategy_config['apply_family_multipliers'] = apply_family_multipliers
st.session_state.strategy_config['apply_location_adjustment'] = apply_location_adjustment

# Location adjustment configuration
if apply_location_adjustment:
    with st.expander("Configure location adjustments", expanded=True):
        st.markdown("""
        Add flat dollar adjustments by state to account for premium differences across locations.
        """)

        # Auto-detect high-cost states
        from contribution_strategies import get_high_cost_states, ContributionStrategyCalculator
        calculator = ContributionStrategyCalculator(st.session_state.db, census_df)
        workforce_summary = calculator.get_workforce_summary()
        detected_high_cost = get_high_cost_states(workforce_summary, threshold_pct=15.0)

        loc_cols = st.columns(2)
        with loc_cols[0]:
            high_cost_adjustment = st.number_input(
                "High-cost state adjustment ($/mo)",
                min_value=0.0,
                max_value=500.0,
                value=st.session_state.strategy_config.get('high_cost_adjustment', 100.0),
                step=25.0,
                key="high_cost_adj"
            )
            if detected_high_cost:
                st.caption(f"Detected high-cost: {', '.join(detected_high_cost)}")
            else:
                st.caption("No high-cost states detected (>15% above avg)")

        with loc_cols[1]:
            all_states = workforce.get('states', [])
            high_cost_states = st.multiselect(
                "High-cost states",
                options=all_states,
                default=detected_high_cost if detected_high_cost else [],
                key="high_cost_states_select"
            )

        # Save location adjustment values to session state
        st.session_state.strategy_config['high_cost_adjustment'] = high_cost_adjustment
        st.session_state.strategy_config['high_cost_states'] = high_cost_states

st.markdown("---")

# Initialize strategy results state if needed
if 'strategy_results' not in st.session_state:
    st.session_state.strategy_results = {}

# -----------------------------------------------------------------------------
# CALCULATE BUTTON
# -----------------------------------------------------------------------------
st.markdown("### Calculate strategy")

if st.button("Calculate contributions", type="primary", key="calc_strategy_btn"):
    from contribution_strategies import (
        ContributionStrategyCalculator,
        StrategyConfig,
        StrategyType as StratType,
        calculate_affordability_impact
    )

    with st.spinner("Calculating contributions..."):
        try:
            calculator = ContributionStrategyCalculator(st.session_state.db, census_df)

            # Read all strategy values from session state (set by tabs and modifiers above)
            cfg = st.session_state.strategy_config
            strategy_type = cfg.get('active_strategy', 'base_age_curve')

            # Read modifier values from session state
            use_family_mult = cfg.get('apply_family_multipliers', False)
            use_location_adj = cfg.get('apply_location_adjustment', False)

            # Build location adjustments dict from session state
            location_adjustments = {}
            if use_location_adj:
                high_cost_adj = cfg.get('high_cost_adjustment', 100.0)
                high_cost_list = cfg.get('high_cost_states', [])
                for state in high_cost_list:
                    location_adjustments[state] = high_cost_adj

            # Build config based on active strategy (set when user interacts with tabs)
            if strategy_type == "base_age_curve":
                config = StrategyConfig(
                    strategy_type=StratType.BASE_AGE_CURVE,
                    base_age=cfg.get('base_age', 21),
                    base_contribution=cfg.get('base_contribution', 400.0),
                    apply_family_multipliers=use_family_mult,
                    apply_location_adjustment=use_location_adj,
                    location_adjustments=location_adjustments
                )
            elif strategy_type == "percentage_lcsp":
                config = StrategyConfig(
                    strategy_type=StratType.PERCENTAGE_LCSP,
                    lcsp_percentage=cfg.get('lcsp_percentage', 75),
                    apply_family_multipliers=use_family_mult,
                    apply_location_adjustment=use_location_adj,
                    location_adjustments=location_adjustments
                )
            elif strategy_type == "flat_amount":
                config = StrategyConfig(
                    strategy_type=StratType.FLAT_AMOUNT,
                    flat_amount=cfg.get('flat_amount', 400.0),
                    apply_family_multipliers=use_family_mult,
                    apply_location_adjustment=use_location_adj,
                    location_adjustments=location_adjustments
                )
            else:  # fpl_safe_harbor
                config = StrategyConfig(
                    strategy_type=StratType.FPL_SAFE_HARBOR,
                    fpl_buffer=cfg.get('fpl_buffer', 5.0),
                    apply_family_multipliers=use_family_mult,
                    apply_location_adjustment=use_location_adj,
                    location_adjustments=location_adjustments
                )

            result = calculator.calculate_strategy(config)

            # Calculate affordability impact
            result['affordability_impact'] = calculate_affordability_impact(
                result,
                st.session_state.affordability_context
            )

            st.session_state.strategy_results = {'current': result}
            st.success(f"Strategy calculated: **{result['strategy_name']}**")
            st.rerun()

        except Exception as e:
            st.error(f"Error calculating strategy: {e}")
            import traceback
            st.code(traceback.format_exc())

# -----------------------------------------------------------------------------
# STRATEGY RESULTS DISPLAY
# -----------------------------------------------------------------------------
if st.session_state.strategy_results and st.session_state.strategy_results.get('current'):
    result = st.session_state.strategy_results['current']

    st.markdown("---")

    # Strategy header with adjustment indicator
    adjustment_flags = []
    if result.get('affordability_adjusted'):
        adjustment_flags.append("Affordability")
    if result.get('employees_ratio_adjusted', 0) > 0:
        adjustment_flags.append("3:1 Ratio")

    if adjustment_flags:
        buffer_info = f" (+{result.get('buffer_applied', 0)}% buffer)" if result.get('buffer_applied') else ""
        flags_str = " & ".join(adjustment_flags)
        st.markdown(f"### Strategy results: {result['strategy_name']} ✓ {flags_str} adjusted{buffer_info}")

        if result.get('affordability_adjusted'):
            st.info("Contributions have been adjusted to meet IRS 9.96% affordability threshold for all employees.")

        if result.get('employees_ratio_adjusted', 0) > 0:
            ratio_count = result['employees_ratio_adjusted']
            ratio_details = result.get('ratio_adjustment_details', [])
            if ratio_details:
                # Get the required floor (all adjusted employees have same new_base)
                required_floor = ratio_details[0]['new_base']
                # The max contribution that triggered this is floor * 3
                max_contrib = required_floor * 3
                st.warning(f"⚠️ {ratio_count} employee(s) had contributions raised to maintain ICHRA 3:1 age ratio compliance. "
                          f"Floor raised to ${required_floor:,.2f}/mo (highest contribution ${max_contrib:,.2f} ÷ 3).")
    else:
        st.markdown(f"### Strategy results: {result['strategy_name']}")

    # Summary metrics row
    metric_cols = st.columns(4)
    metric_cols[0].metric("Monthly total", f"${result['total_monthly']:,.0f}")
    metric_cols[1].metric("Annual total", f"${result['total_annual']:,.0f}")
    metric_cols[2].metric("Employees", result['employees_covered'])
    avg = result['total_monthly'] / result['employees_covered'] if result['employees_covered'] > 0 else 0
    metric_cols[3].metric("Avg/Employee", f"${avg:,.0f}/mo")

    # Prominent Cost Comparison - ER to ER (employer cost focus)
    aff_impact = result.get('affordability_impact', {})
    strategy_spend = result.get('total_annual', 0)

    # Get current ER spend and 2026 projected renewal
    from financial_calculator import FinancialSummaryCalculator
    from utils import ContributionComparison

    # Current ER Spend (what employer pays now)
    contrib_totals = ContributionComparison.aggregate_contribution_totals(census_df)
    current_er_annual = contrib_totals.get('total_current_er_annual', 0)

    # 2026 Projected Renewal (for context)
    projected_2026 = 0
    _financial_summary = st.session_state.get('financial_summary')
    if _financial_summary and _financial_summary.get('renewal_monthly'):
        projected_2026 = _financial_summary['renewal_monthly'] * 12
    else:
        projected_data = FinancialSummaryCalculator.calculate_projected_2026_total(census_df)
        if projected_data['has_data']:
            projected_2026 = projected_data['total_annual']

    # Show comparison section if we have ER data
    if current_er_annual > 0 or projected_2026 > 0:
        st.markdown("---")
        st.markdown("### 💰 Employer cost summary")

        # Row 1: Cost totals
        cost_cols = st.columns(3)
        with cost_cols[0]:
            st.metric("Current ER", f"${current_er_annual:,.0f}/yr" if current_er_annual > 0 else "N/A")
        with cost_cols[1]:
            st.metric("Renewal ER", f"${projected_2026:,.0f}/yr" if projected_2026 > 0 else "N/A")
        with cost_cols[2]:
            st.metric("Proposed ICHRA", f"${strategy_spend:,.0f}/yr")

        # Row 2: Savings comparisons
        from utils import SavingsFormatter
        savings_cols = st.columns(3)

        # ICHRA vs Current
        with savings_cols[0]:
            if current_er_annual > 0:
                savings_vs_current = current_er_annual - strategy_spend
                pct_vs_current = (savings_vs_current / current_er_annual) * 100
                delta_text, delta_color = SavingsFormatter.for_metric_with_pct(savings_vs_current, pct_vs_current)
                st.metric("Savings vs Current", f"${abs(savings_vs_current):,.0f}", delta=delta_text, delta_color=delta_color)
            else:
                st.metric("Savings vs Current", "N/A")

        # ICHRA vs Renewal
        with savings_cols[1]:
            if projected_2026 > 0:
                savings_vs_renewal = projected_2026 - strategy_spend
                pct_vs_renewal = (savings_vs_renewal / projected_2026) * 100
                delta_text, delta_color = SavingsFormatter.for_metric_with_pct(savings_vs_renewal, pct_vs_renewal)
                st.metric("Savings vs Renewal", f"${abs(savings_vs_renewal):,.0f}", delta=delta_text, delta_color=delta_color)
            else:
                st.metric("Savings vs Renewal", "N/A")

        # ICHRA Projected (70% take rate)
        with savings_cols[2]:
            take_rate = 0.70
            projected_ichra = strategy_spend * take_rate
            st.metric("ICHRA Projected (70%)", f"${projected_ichra:,.0f}/yr",
                     help="Estimated cost assuming 70% of employees enroll in ICHRA")
    if aff_impact:
        st.markdown("---")
        st.markdown("### IRS affordability compliance")

        before = aff_impact.get('before', {})
        after = aff_impact.get('after', {})
        delta = aff_impact.get('delta', {})

        # Progress bar first - most important visual
        employees_analyzed = after.get('employees_analyzed', 0)
        affordable_count = after.get('affordable_count', 0)
        unaffordable_count = employees_analyzed - affordable_count

        if employees_analyzed > 0:
            aff_pct = affordable_count / employees_analyzed
            st.progress(aff_pct, text=f"Affordability: {aff_pct*100:.0f}% ({affordable_count}/{employees_analyzed} employees meet 9.96% threshold)")

            # Simplified metrics - focus on strategy outcome
            aff_cols = st.columns(3)
            with aff_cols[0]:
                st.metric("Employees affordable", f"{affordable_count}/{employees_analyzed}",
                         help="Employees meeting IRS 9.96% affordability threshold with this strategy")
            with aff_cols[1]:
                st.metric("Need higher contribution", unaffordable_count if unaffordable_count > 0 else "None",
                         delta_color="inverse" if unaffordable_count > 0 else "normal")
            with aff_cols[2]:
                gap_annual = after.get('total_gap', 0)
                st.metric("Cost to reach 100%", f"${gap_annual:,.0f}/yr" if gap_annual > 0 else "$0",
                         help="Additional annual spend needed for all employees to meet affordability")

            if aff_pct >= 1.0:
                st.success("All employees meet IRS affordability threshold")
            elif aff_pct >= 0.8:
                st.warning(f"{unaffordable_count} employee{'s' if unaffordable_count != 1 else ''} still need{'s' if unaffordable_count == 1 else ''} higher contributions")
            else:
                st.error(f"Significant gap: {unaffordable_count} employee{'s' if unaffordable_count != 1 else ''} unaffordable")

            # Show which employees are unaffordable with detailed adjustment table
            if unaffordable_count > 0:
                unaffordable_employees = aff_impact.get('unaffordable_employees', [])
                if unaffordable_employees:
                    with st.expander(f"View {len(unaffordable_employees)} employee{'s' if len(unaffordable_employees) != 1 else ''} needing adjustment", expanded=False):
                        # Build detailed adjustment table
                        unaff_data = []
                        total_current = 0
                        total_min_needed = 0
                        total_gap = 0

                        for emp in unaffordable_employees:
                            current = emp.get('current_contribution', 0)
                            min_needed = emp.get('min_affordable', 0)
                            gap = emp.get('gap', 0)

                            total_current += current
                            total_min_needed += min_needed
                            total_gap += gap

                            unaff_data.append({
                                'Employee': emp.get('name', emp.get('employee_id', 'N/A')),
                                'Age': emp.get('age', ''),
                                'Status': emp.get('family_status', 'EE'),
                                'Income': f"${emp.get('monthly_income', 0):,.0f}",
                                'LCSP': f"${emp.get('lcsp_ee_rate', 0):,.0f}",
                                'Current': f"${current:,.0f}",
                                'Min Needed': f"${min_needed:,.0f}",
                                'Gap': f"${gap:,.0f}"
                            })

                        if unaff_data:
                            st.dataframe(pd.DataFrame(unaff_data), hide_index=True, width='stretch')

                            # Totals row
                            totals_cols = st.columns(4)
                            with totals_cols[0]:
                                st.metric("Current spend (unaffordable)", f"${total_current:,.0f}/mo")
                            with totals_cols[1]:
                                st.metric("Min needed (unaffordable)", f"${total_min_needed:,.0f}/mo")
                            with totals_cols[2]:
                                st.metric("Total gap to close", f"${total_gap:,.0f}/mo",
                                         help="Additional monthly spend required to make all employees affordable")
                            with totals_cols[3]:
                                st.metric("Annual gap", f"${total_gap * 12:,.0f}/yr")

                            st.markdown("---")

                            # Action buttons for adjustments
                            st.markdown("**Apply minimum affordable amounts**")
                            st.caption("Adjust contributions for unaffordable employees to meet the IRS 9.96% threshold. Includes $1/mo buffer to ensure compliance.")

                            apply_cols = st.columns([2, 1])
                            with apply_cols[0]:
                                if st.button("Apply minimum to unaffordable employees", key="apply_min_btn",
                                           help="Sets contribution to exact minimum needed for each unaffordable employee"):
                                    # Merge minimum amounts into strategy results
                                    emp_contribs = result.get('employee_contributions', {})
                                    adjusted_total = result.get('total_monthly', 0)

                                    for emp in unaffordable_employees:
                                        emp_id = emp.get('employee_id')
                                        if emp_id and emp_id in emp_contribs:
                                            old_contrib = emp_contribs[emp_id].get('monthly_contribution', 0)
                                            min_needed = emp.get('min_affordable', old_contrib)
                                            gap = emp.get('gap', 0)
                                            new_contrib = min_needed
                                            # Update contribution
                                            emp_contribs[emp_id]['monthly_contribution'] = round(new_contrib, 2)
                                            emp_contribs[emp_id]['annual_contribution'] = round(new_contrib * 12, 2)
                                            emp_contribs[emp_id]['adjusted_for_affordability'] = True
                                            emp_contribs[emp_id]['min_needed'] = round(min_needed, 2)
                                            emp_contribs[emp_id]['original_gap'] = round(gap, 2)
                                            # Update running total
                                            adjusted_total = adjusted_total - old_contrib + new_contrib

                                    # Update result totals
                                    result['total_monthly'] = round(adjusted_total, 2)
                                    result['total_annual'] = round(adjusted_total * 12, 2)
                                    result['affordability_adjusted'] = True

                                    # Recalculate affordability impact with updated contributions
                                    result['affordability_impact'] = calculate_affordability_impact(
                                        result,
                                        st.session_state.affordability_context
                                    )

                                    # Store back to session state
                                    st.session_state.strategy_results['current'] = result

                                    st.success(f"✓ Applied minimum affordable amounts to {len(unaffordable_employees)} employees. Total monthly spend: ${adjusted_total:,.0f}")
                                    st.rerun()

                            with apply_cols[1]:
                                buffer_pct = st.number_input("Buffer %", min_value=0, max_value=25, value=5, key="buffer_pct",
                                                           help="Add a buffer above the minimum for safety margin")

                                if st.button(f"Apply with {buffer_pct}% Buffer", key="apply_buffer_btn"):
                                    # Merge minimum amounts + buffer into strategy results
                                    emp_contribs = result.get('employee_contributions', {})
                                    adjusted_total = result.get('total_monthly', 0)
                                    buffer_mult = 1 + (buffer_pct / 100)

                                    for emp in unaffordable_employees:
                                        emp_id = emp.get('employee_id')
                                        if emp_id and emp_id in emp_contribs:
                                            old_contrib = emp_contribs[emp_id].get('monthly_contribution', 0)
                                            min_needed = emp.get('min_affordable', old_contrib)
                                            gap = emp.get('gap', 0)
                                            new_contrib = min_needed * buffer_mult
                                            # Update contribution
                                            emp_contribs[emp_id]['monthly_contribution'] = round(new_contrib, 2)
                                            emp_contribs[emp_id]['annual_contribution'] = round(new_contrib * 12, 2)
                                            emp_contribs[emp_id]['adjusted_for_affordability'] = True
                                            emp_contribs[emp_id]['min_needed'] = round(min_needed, 2)
                                            emp_contribs[emp_id]['original_gap'] = round(gap, 2)
                                            emp_contribs[emp_id]['buffer_applied'] = buffer_pct
                                            # Update running total
                                            adjusted_total = adjusted_total - old_contrib + new_contrib

                                    # Update result totals
                                    result['total_monthly'] = round(adjusted_total, 2)
                                    result['total_annual'] = round(adjusted_total * 12, 2)
                                    result['affordability_adjusted'] = True
                                    result['buffer_applied'] = buffer_pct

                                    # Recalculate affordability impact with updated contributions
                                    result['affordability_impact'] = calculate_affordability_impact(
                                        result,
                                        st.session_state.affordability_context
                                    )

                                    # Store back to session state
                                    st.session_state.strategy_results['current'] = result

                                    st.success(f"✓ Applied minimum + {buffer_pct}% buffer to {len(unaffordable_employees)} employees. Total monthly spend: ${adjusted_total:,.0f}")
                                    st.rerun()

    # Expandable breakdown sections
    with st.expander("Age tier breakdown", expanded=False):
        by_age = result.get('by_age_tier', {})
        if by_age:
            age_data = []
            for tier, data in by_age.items():
                avg_amt = data['total_monthly'] / data['count'] if data['count'] > 0 else 0
                age_data.append({
                    'Age Tier': tier,
                    'Employees': data['count'],
                    'Total Monthly': f"${data['total_monthly']:,.0f}",
                    'Avg Monthly': f"${avg_amt:,.0f}"
                })
            age_df = pd.DataFrame(age_data).sort_values('Employees', ascending=False)
            st.dataframe(age_df, hide_index=True, width='stretch')

    with st.expander("Family status breakdown", expanded=False):
        by_fs = result.get('by_family_status', {})
        if by_fs:
            fs_data = []
            for fs, data in by_fs.items():
                avg_amt = data['total_monthly'] / data['count'] if data['count'] > 0 else 0
                fs_data.append({
                    'Family Status': fs,
                    'Employees': data['count'],
                    'Total Monthly': f"${data['total_monthly']:,.0f}",
                    'Avg Monthly': f"${avg_amt:,.0f}"
                })
            fs_df = pd.DataFrame(fs_data).sort_values('Employees', ascending=False)
            st.dataframe(fs_df, hide_index=True, width='stretch')

    if result.get('by_state'):
        with st.expander("State/location breakdown", expanded=False):
            by_state = result.get('by_state', {})
            state_data = []
            for state, data in by_state.items():
                avg_amt = data['total_monthly'] / data['count'] if data['count'] > 0 else 0
                state_data.append({
                    'State': state,
                    'Employees': data['count'],
                    'Adjustment': f"${data.get('adjustment', 0):,.0f}",
                    'Total Monthly': f"${data['total_monthly']:,.0f}",
                    'Avg Monthly': f"${avg_amt:,.0f}"
                })
            st.dataframe(pd.DataFrame(state_data), hide_index=True, width='stretch')

    with st.expander("Employee detail", expanded=False):
        emp_contribs = result.get('employee_contributions', {})
        if emp_contribs:
            detail_data = []
            for emp_id, data in emp_contribs.items():
                emp_row = census_df[
                    (census_df['employee_id'].astype(str) == str(emp_id)) |
                    (census_df.get('Employee Number', pd.Series()).astype(str) == str(emp_id))
                ] if 'employee_id' in census_df.columns or 'Employee Number' in census_df.columns else pd.DataFrame()

                if not emp_row.empty:
                    emp = emp_row.iloc[0]
                    first_name = emp.get('first_name') or emp.get('First Name', '')
                    last_name = emp.get('last_name') or emp.get('Last Name', '')
                    name = f"{first_name} {last_name}".strip() or emp_id
                else:
                    name = emp_id

                detail_data.append({
                    'Employee': name,
                    'Age': data.get('age', ''),
                    'State': data.get('state', ''),
                    'Family': data.get('family_status', ''),
                    'LCSP': f"${data.get('lcsp_ee_rate', 0):,.0f}" if data.get('lcsp_ee_rate') else '-',
                    'Monthly': f"${data['monthly_contribution']:,.2f}",
                    'Annual': f"${data['annual_contribution']:,.2f}"
                })

            detail_df = pd.DataFrame(detail_data)
            st.dataframe(detail_df, hide_index=True, width='stretch')

    # Action buttons
    st.markdown("---")
    action_cols = st.columns(3)

    with action_cols[0]:
        st.markdown("**Save this strategy for use in subsequent pages:**")

        # Define callback to handle button click
        def apply_strategy_callback():
            st.session_state.apply_strategy_clicked = True

        st.button(
            "Use this strategy →",
            type="primary",
            key="apply_strategy_btn",
            on_click=apply_strategy_callback
        )

        # Check if callback was triggered
        if st.session_state.get('apply_strategy_clicked', False):
            st.session_state.apply_strategy_clicked = False  # Reset flag

            try:
                # Convert result to contribution_settings format
                emp_contribs = result.get('employee_contributions', {})
                st.session_state.contribution_settings = {
                    'contribution_type': 'class_based',
                    'strategy_applied': result['strategy_type'],
                    'strategy_name': result['strategy_name'],
                    'total_monthly': result['total_monthly'],
                    'total_annual': result['total_annual'],
                    'employees_assigned': result['employees_covered'],
                    'employee_assignments': {
                        emp_id: {
                            'monthly_contribution': data['monthly_contribution'],
                            'annual_contribution': data['annual_contribution']
                        } for emp_id, data in emp_contribs.items()
                    },
                    'config': result.get('config', {})
                }

                # Also populate contribution_analysis for Page 4 (Employer Summary)
                contribution_analysis = {}
                for emp_id, data in emp_contribs.items():
                    lcsp_tier_premium = data.get('lcsp_tier_premium', 0) or data.get('lcsp_ee_rate', 0) or 0
                    employer_contribution = data.get('monthly_contribution', 0)
                    employee_cost = max(0, lcsp_tier_premium - employer_contribution)

                    contribution_analysis[emp_id] = {
                        'employee_name': emp_id,
                        'family_status': data.get('family_status', 'EE'),
                        'ichra_analysis': {
                            'plan_type': 'LCSP',
                            'plan_id': '',
                            'plan_name': 'Lowest Cost Silver Plan',
                            'metal_level': 'Silver',
                            'monthly_premium': lcsp_tier_premium,
                            'employer_contribution': employer_contribution,
                            'employee_cost': employee_cost
                        }
                    }
                st.session_state.contribution_analysis = contribution_analysis

                # Also update strategy_results with format Employer Summary expects
                st.session_state.strategy_results['calculated'] = True
                st.session_state.strategy_results['result'] = result

                st.success(f"✓ Strategy saved! {len(contribution_analysis)} employees assigned. Proceed to **Employer summary** page to see results.")
            except Exception as e:
                st.error(f"Error saving strategy: {e}")
                import traceback
                st.code(traceback.format_exc())

    with action_cols[1]:
        # CSV Export
        emp_contribs = result.get('employee_contributions', {})
        if emp_contribs:
            export_rows = []
            # Check if any employee has affordability adjustments
            has_affordability_data = any(
                data.get('adjusted_for_affordability') for data in emp_contribs.values()
            )
            has_buffer = result.get('buffer_applied', 0) > 0

            # Get multi_metal_results for Bronze/Silver/Gold rates
            financial_summary = st.session_state.get('financial_summary', {})
            multi_metal_results = financial_summary.get('multi_metal_scenario', {})

            # Build employee rate lookup from multi_metal_results
            # emp_id -> {Bronze: rate, Silver: rate, Gold: rate}
            emp_metal_rates = {}
            for metal in ['Bronze', 'Silver', 'Gold']:
                metal_data = multi_metal_results.get(metal, {})
                for emp_detail in metal_data.get('employee_details', []):
                    eid = str(emp_detail.get('employee_id', ''))
                    if eid not in emp_metal_rates:
                        emp_metal_rates[eid] = {'Bronze': 0, 'Silver': 0, 'Gold': 0}
                    # Use aggregate family premium if available, otherwise estimated_tier_premium
                    emp_metal_rates[eid][metal] = (
                        emp_detail.get('aggregate_family_premium') or
                        emp_detail.get('estimated_tier_premium') or
                        emp_detail.get('lcp_ee_rate', 0)
                    )

            # Build detailed strategy string with config
            strategy_type = result['strategy_type']
            config = result.get('config', {})
            if strategy_type == 'percentage_lcsp':
                strategy_str = f"percentage_lcsp_{int(config.get('lcsp_percentage', 0))}"
            elif strategy_type == 'base_age_curve':
                strategy_str = f"base_age_curve_{int(config.get('base_contribution', 0))}"
            else:
                strategy_str = strategy_type

            for emp_id, data in emp_contribs.items():
                row = {
                    'Employee ID': emp_id,
                    'Age': data.get('age', ''),
                    'State': data.get('state', ''),
                    'Family Status': data.get('family_status', ''),
                    'LCSP EE Rate': data.get('lcsp_ee_rate', ''),
                    'Location Adjustment': data.get('location_adjustment', 0),
                    'Monthly Contribution': data['monthly_contribution'],
                    'Annual Contribution': data['annual_contribution'],
                    'Strategy': strategy_str
                }

                # Add Bronze/Silver/Gold marketplace rates
                emp_rates = emp_metal_rates.get(str(emp_id), {})
                row['Bronze Rate'] = emp_rates.get('Bronze', '') or ''
                row['Silver Rate'] = emp_rates.get('Silver', '') or ''
                row['Gold Rate'] = emp_rates.get('Gold', '') or ''

                # Add affordability columns if adjustments were made
                if has_affordability_data:
                    if data.get('adjusted_for_affordability'):
                        row['Original Amount'] = data.get('min_needed', '')
                        row['Original Gap'] = data.get('original_gap', '')
                        row['Adjusted'] = 'Yes'
                        if has_buffer:
                            row['Buffer %'] = data.get('buffer_applied', '')
                    else:
                        row['Original Amount'] = ''
                        row['Original Gap'] = ''
                        row['Adjusted'] = 'No'
                        if has_buffer:
                            row['Buffer %'] = ''

                # Add 3:1 ratio adjustment column
                if data.get('ratio_adjusted'):
                    row['Ratio Adjusted'] = 'Yes'
                    row['Ratio From'] = data.get('ratio_adjustment_from', '')
                    row['Ratio To'] = data.get('ratio_adjustment_to', '')
                else:
                    row['Ratio Adjusted'] = 'No'
                    row['Ratio From'] = ''
                    row['Ratio To'] = ''

                export_rows.append(row)

            export_df = pd.DataFrame(export_rows)
            csv_data = export_df.to_csv(index=False)

            # Use dynamic key to prevent caching issues
            adjusted_suffix = "_adjusted" if has_affordability_data else ""
            buffer_suffix = f"_buffer{result.get('buffer_applied', 0)}" if has_buffer else ""

            # Build filename with client name and timestamp
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            client_name = st.session_state.get('client_name', '').strip()
            base_name = f"ichra_{result['strategy_type']}{adjusted_suffix}{buffer_suffix}_contributions"
            if client_name:
                safe_name = client_name.replace(' ', '_').replace('/', '-')
                csv_filename = f"{base_name}_{safe_name}_{timestamp}.csv"
            else:
                csv_filename = f"{base_name}_{timestamp}.csv"

            st.download_button(
                label="Download CSV",
                data=csv_data,
                file_name=csv_filename,
                mime="text/csv",
                key=f"strategy_csv_export_{has_affordability_data}_{has_buffer}_{len(export_rows)}"
            )

    with action_cols[2]:
        if st.button("Clear & start over", key="clear_strategy_results",
                    help="Clears calculated results so you can try a different strategy configuration."):
            st.session_state.strategy_results = {}
            # Keep strategy_config intact so user doesn't lose their inputs
            st.rerun()

# Affordability footnote
st.caption("¹ *IRS Affordability Safe Harbor: Employee cost for self-only LCSP must not exceed 9.96% of household income (2026 threshold).*")

# Note: The IRS Affordability Analysis is now integrated into the unified modeler above.
# The separate affordability_analysis session state is deprecated in favor of affordability_context.

# Skip displaying old standalone affordability analysis - it's now in the unified modeler
_skip_old_affordability = True
if not _skip_old_affordability and 'affordability_analysis' in st.session_state and st.session_state.affordability_analysis:
    analysis = st.session_state.affordability_analysis
    summary = analysis['summary']

    st.markdown("## 📊 IRS Affordability Analysis (Legacy)")

    with st.expander("ℹ️ What is IRS Affordability?", expanded=False):
        st.markdown("""
        **The IRS Affordability Rule:**

        An ICHRA is considered "affordable" if the employee's required contribution for **self-only LCSP**
        (Lowest Cost Silver Plan) does not exceed **9.96% of their household income** (2026 threshold).

        **Why this matters:**
        - ✅ **Affordable ICHRA** = No employer penalties, employees can use pre-tax dollars
        - ⚠️ **Unaffordable ICHRA** = Employer faces ACA penalties, employee can decline and buy marketplace plan with subsidies

        **How we calculate it:**
        1. Get employee's monthly income (from census)
        2. Calculate 9.96% of income = max employee should pay
        3. Get self-only LCSP premium for their location/age
        4. Min Employer Contribution = LCSP premium - (9.96% × income)
        5. Compare to current ER contribution to find gap

        **Example:**
        - Employee makes $5,000/month
        - Max employee should pay: $5,000 × 9.96% = $498/month
        - LCSP premium: $650/month
        - **Min ER contribution needed: $650 - $498 = $152/month** ✓
        """)

    st.markdown("*Analysis based on 9.96% of household income affordability threshold (2026 IRS safe harbor)*")

    # Current Status Metrics (Row 1)
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Employees analyzed",
            f"{summary['employees_analyzed']}/{summary['total_employees']}",
            help="Number of employees with income data. Only employees with 'Monthly Income' in census can be analyzed for affordability."
        )

    with col2:
        affordable_pct = (summary['affordable_at_current'] / summary['employees_analyzed'] * 100) if summary['employees_analyzed'] > 0 else 0
        st.metric(
            "✅ Affordable",
            summary['affordable_at_current'],
            f"{affordable_pct:.0f}%",
            help="Employees whose CURRENT ER contribution already meets the IRS 9.96% affordability threshold."
        )

    with col3:
        st.metric(
            "⚠️ Need Increase",
            summary['needs_increase'],
            delta=None if summary['needs_increase'] == 0 else f"-{summary['needs_increase']}",
            delta_color="inverse",
            help="Employees requiring INCREASED ER contribution to meet affordability."
        )

    with col4:
        # Show Current ER Spend for employer cost comparison
        _er_totals = ContributionComparison.aggregate_contribution_totals(census_df)
        _current_er = _er_totals.get('total_current_er_annual', 0)
        st.metric(
            "💰 Current ER spend",
            f"${_current_er:,.0f}",
            help="Current annual employer contribution to group plan."
        )

    # Proposed Strategy Comparison (shows when strategy is applied)
    contribution_settings = st.session_state.get('contribution_settings', {})
    if contribution_settings.get('contribution_type') == 'class_based' and contribution_settings.get('strategy_applied'):
        strategy_name = contribution_settings.get('strategy_applied', '').replace('_', ' ').title()
        proposed_annual = contribution_settings.get('total_annual', 0)
        # ER to ER comparison
        _er_for_compare = ContributionComparison.aggregate_contribution_totals(census_df)
        current_er_annual = _er_for_compare.get('total_current_er_annual', 0)
        change = proposed_annual - current_er_annual

        st.markdown("---")
        st.markdown(f"### 📋 Proposed: {strategy_name}")

        prop_col1, prop_col2, prop_col3, prop_col4 = st.columns(4)

        with prop_col1:
            st.metric(
                "ICHRA Annual Cost",
                f"${proposed_annual:,.0f}",
                help="Total annual employer spend with the applied contribution strategy."
            )

        with prop_col2:
            if change < 0:
                delta_text = f"-${abs(change):,.0f}"
                delta_label = "Savings"
            elif change > 0:
                delta_text = f"+${change:,.0f}"
                delta_label = "Additional"
            else:
                delta_text = "$0"
                delta_label = ""
            st.metric(
                "vs Current ER",
                delta_text,
                delta_label,
                delta_color="normal" if change <= 0 else "inverse",
                help="Difference between ICHRA cost and current ER spend."
            )

        with prop_col3:
            st.metric(
                "Employees covered",
                len(contribution_settings.get('employee_assignments', {})),
                help="Number of employees assigned to contribution classes."
            )

        with prop_col4:
            st.metric(
                "Achieves affordability",
                "100%",
                "✓",
                help="This strategy is designed to meet IRS affordability requirements for all employees."
            )

    # Visualization: Affordable vs Needs Increase (Pie Chart)
    if summary['employees_analyzed'] > 0:
        fig = go.Figure(data=[go.Pie(
            labels=['Affordable', 'Needs Increase'],
            values=[summary['affordable_at_current'], summary['needs_increase']],
            marker_colors=['#10b981', '#0047AB'],
            hole=0.4,  # Donut style
            textinfo='label+value',
            textposition='outside',
            textfont_size=12
        )])
        fig.update_layout(
            height=250,
            showlegend=False,
            margin=dict(l=20, r=20, t=20, b=20)
        )
        st.plotly_chart(fig, width='stretch')

    # ===========================================================================
    # RECOMMENDED CONTRIBUTION STRATEGIES
    # ===========================================================================

    st.markdown("### 💡 Recommended Contribution Strategies")
    st.markdown("""
    Based on your workforce analysis, here are the optimal contribution structures that ensure **100% affordability** while minimizing cost.
    Each strategy guarantees all employees meet the IRS 9.96% threshold.
    """)

    with st.expander("ℹ️ How are these calculated?", expanded=False):
        st.markdown("""
        **Strategy Types:**

        1. **Age-Based Contribution Tiers**
           - Uses fixed age tiers that align with ICHRA/ACA rating patterns:
             - **21** (standalone tier for age 21 exactly)
             - **18-25** (includes age 21 for range calculations)
             - **26-35**, **36-45**, **46-55**, **56-63**, **64+**
           - **Base Contribution** = MAXIMUM required contribution within each tier
           - This ensures all employees in the tier meet IRS affordability
           - More cost-efficient than flat: younger employees typically need less

        2. **Location-Based** (If multi-state with variance)
           - Groups by state/rating area
           - Accounts for geographic premium differences
           - **Base Contribution** = MAXIMUM required contribution per location
           - Only shown if location variance > 10%

        **How Base Contribution is Calculated:**
        - For each employee, we calculate: `Min ER Contribution = LCSP - (9.96% × Monthly Income)`
        - The **Base Contribution** for a tier is the MAXIMUM of all employees' min ER contributions in that tier
        - This guarantees 100% affordability for everyone in the tier

        **Family Multipliers (Optional):**
        - EE (Employee Only): 1.0x base
        - ES (Employee + Spouse): 1.5x base
        - EC (Employee + Children): 1.3x base
        - F (Family): 1.8x base

        **Metrics:**
        - **Annual Cost** = Total employer spend for 100% affordability
        - **vs Current** = Comparison to your current ER spend (positive = savings, negative = increase)
        """)

    recommendations = analysis['recommendations']
    current_applied = st.session_state.contribution_settings.get('strategy_applied', None)

    # Display each recommendation as a collapsed expander
    for idx, rec in enumerate(recommendations):
        is_active = current_applied == rec['strategy_type']

        # Build expander label with active indicator
        expander_label = f"✅ {rec['name']}" if is_active else rec['name']

        with st.expander(expander_label, expanded=False):
            # Applied badge
            if is_active:
                st.success("APPLIED")

            # Strategy details - display as formatted table
            if rec['strategy_type'] == 'age_banded':
                st.markdown("##### Age-Based Contribution Tiers")

                # Create a clean table for age tiers
                tier_data = []
                for tier in rec['tiers']:
                    count = tier.get('count', 0)
                    count_with_income = tier.get('count_with_income', count)
                    # Show employees with income data if different from total
                    if count_with_income != count and count > 0:
                        emp_display = f"{count_with_income}/{count}"
                    else:
                        emp_display = count

                    tier_data.append({
                        'Age Tier': tier['age_range'],
                        'Base Contribution': f"${tier['contribution']:,.2f}",
                        'Employees': emp_display
                    })

                tier_df = pd.DataFrame(tier_data)
                st.dataframe(
                    tier_df,
                    hide_index=True,
                    width="stretch",
                    column_config={
                        'Age Tier': st.column_config.TextColumn('Age Tier', width='medium'),
                        'Base Contribution': st.column_config.TextColumn('Base Contribution', width='medium'),
                        'Employees': st.column_config.TextColumn('Employees', width='small', help='Employees with income data / Total employees')
                    }
                )

            elif rec['strategy_type'] == 'location_based':
                st.markdown("##### Location-Based Contribution Tiers")

                tier_data = []
                for tier in rec['tiers']:
                    tier_data.append({
                        'Location': tier['location'],
                        'Base Contribution': f"${tier['contribution']:,.0f}",
                        'Employees': tier.get('count', 0)
                    })

                tier_df = pd.DataFrame(tier_data)
                st.dataframe(
                    tier_df,
                    hide_index=True,
                    width="stretch",
                    column_config={
                        'Location': st.column_config.TextColumn('Location', width='medium'),
                        'Base Contribution': st.column_config.TextColumn('Base Contribution', width='medium'),
                        'Employees': st.column_config.NumberColumn('Employees', width='small')
                    }
                )

            st.markdown("")  # Spacing

            # Metrics row
            metric_cols = st.columns(4)
            metric_cols[0].metric("Annual cost", f"${rec['annual_cost']:,.0f}")
            metric_cols[1].metric("Affordability", rec['achieves_affordability'])
            savings_vs_current = rec.get('savings_vs_current', 0)
            if savings_vs_current != 0:
                if savings_vs_current > 0:
                    metric_cols[2].metric("vs Current", f"+${savings_vs_current:,.0f}", delta="Savings", delta_color="normal")
                else:
                    metric_cols[2].metric("vs Current", f"-${abs(savings_vs_current):,.0f}", delta="Increase", delta_color="inverse")

            # Pros/Cons in a cleaner layout
            st.markdown("")  # Spacing
            col_pro, col_con = st.columns(2)
            with col_pro:
                st.markdown("**Pros:**")
                for pro in rec['pros']:
                    st.markdown(f"- {pro}")
            with col_con:
                st.markdown("**Cons:**")
                for con in rec.get('cons', []):
                    st.markdown(f"- {con}")

            st.markdown("---")

            # Action row: checkbox and button
            action_cols = st.columns([3, 1])
            with action_cols[0]:
                apply_multipliers = st.checkbox(
                    "Apply family multipliers (EE=1.0x, ES=1.5x, EC=1.3x, F=1.8x)",
                    value=False,
                    key=f"multiplier_{idx}"
                )
            with action_cols[1]:
                button_label = "Re-apply" if is_active else "Apply strategy"
                if st.button(button_label, key=f"apply_{idx}", type="secondary"):
                    from affordability import StrategyApplicator

                    try:
                        new_settings = StrategyApplicator.apply_strategy(
                            strategy=rec,
                            census_df=census_df,
                            apply_family_multipliers=apply_multipliers
                        )
                        st.session_state.contribution_settings = new_settings
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error applying strategy: {e}")

            # INLINE APPLIED OUTPUT - Only show when THIS strategy is applied
            if is_active:
                settings = st.session_state.contribution_settings

                st.markdown("---")
                st.markdown("##### Applied Configuration")

                # Summary metrics for applied strategy
                summary_cols = st.columns(4)
                summary_cols[0].metric("Employees", settings.get('employees_assigned', 0))
                summary_cols[1].metric("Monthly total", f"${settings.get('total_monthly', 0):,.0f}")
                summary_cols[2].metric("Annual total", f"${settings.get('total_annual', 0):,.0f}")
                summary_cols[3].metric(
                    "Family multipliers",
                    "Enabled" if settings.get('apply_family_multipliers') else "Disabled"
                )

                # Class breakdown table (expandable)
                with st.expander("View contribution classes", expanded=False):
                    classes = settings.get('classes', [])
                    if classes:
                        class_data = []
                        for cls in classes:
                            assignments = settings.get('employee_assignments', {})
                            count = sum(1 for a in assignments.values() if a.get('class_id') == cls['class_id'])
                            class_data.append({
                                'Class ID': cls['class_id'],
                                'Description': cls['description'],
                                'Monthly': f"${cls['monthly_contribution']:,.2f}",
                                'Employees': count
                            })
                        class_df = pd.DataFrame(class_data)
                        st.dataframe(class_df, hide_index=True, width='stretch')

                # Employee assignments table (expandable)
                with st.expander("View employee assignments", expanded=False):
                    assignments = settings.get('employee_assignments', {})
                    if assignments:
                        assignment_data = []
                        for emp_id, assign in assignments.items():
                            emp_row = census_df[
                                (census_df['employee_id'].astype(str) == str(emp_id)) |
                                (census_df.get('Employee Number', pd.Series()).astype(str) == str(emp_id))
                            ] if 'employee_id' in census_df.columns or 'Employee Number' in census_df.columns else pd.DataFrame()

                            if not emp_row.empty:
                                emp = emp_row.iloc[0]
                                first_name = emp.get('first_name') or emp.get('First Name', '')
                                last_name = emp.get('last_name') or emp.get('Last Name', '')
                                name = f"{first_name} {last_name}".strip() or emp_id
                                family_status = emp.get('family_status') or emp.get('Family Status', 'EE')
                                age = emp.get('age') or emp.get('ee_age', 'N/A')
                                state = emp.get('state') or emp.get('Home State', 'N/A')
                            else:
                                name = emp_id
                                family_status = 'N/A'
                                age = 'N/A'
                                state = 'N/A'

                            assignment_data.append({
                                'Employee ID': emp_id,
                                'Name': name,
                                'Age': age,
                                'State': state,
                                'Family Status': family_status,
                                'Class': assign['class_id'],
                                'Monthly': f"${assign['monthly_contribution']:,.2f}",
                                'Annual': f"${assign['annual_contribution']:,.2f}"
                            })
                        assign_df = pd.DataFrame(assignment_data)
                        st.dataframe(assign_df, hide_index=True, width='stretch')

                # CSV Export section
                st.markdown("---")
                st.markdown("##### Export Contribution Data")

                # Build comprehensive export DataFrame
                assignments = settings.get('employee_assignments', {})
                if assignments:
                    # Get multi_metal_results for Bronze/Silver/Gold rates
                    financial_summary = st.session_state.get('financial_summary', {})
                    multi_metal_results = financial_summary.get('multi_metal_scenario', {})

                    # Build employee rate lookup from multi_metal_results
                    emp_metal_rates = {}
                    for metal in ['Bronze', 'Silver', 'Gold']:
                        metal_data = multi_metal_results.get(metal, {})
                        for emp_detail in metal_data.get('employee_details', []):
                            eid = str(emp_detail.get('employee_id', ''))
                            if eid not in emp_metal_rates:
                                emp_metal_rates[eid] = {'Bronze': 0, 'Silver': 0, 'Gold': 0}
                            # Use aggregate family premium if available
                            emp_metal_rates[eid][metal] = (
                                emp_detail.get('aggregate_family_premium') or
                                emp_detail.get('estimated_tier_premium') or
                                emp_detail.get('lcp_ee_rate', 0)
                            )

                    export_data = []
                    for emp_id, assign in assignments.items():
                        emp_row = census_df[
                            (census_df['employee_id'].astype(str) == str(emp_id)) |
                            (census_df.get('Employee Number', pd.Series()).astype(str) == str(emp_id))
                        ] if 'employee_id' in census_df.columns or 'Employee Number' in census_df.columns else pd.DataFrame()

                        if not emp_row.empty:
                            emp = emp_row.iloc[0]
                            first_name = emp.get('first_name') or emp.get('First Name', '')
                            last_name = emp.get('last_name') or emp.get('Last Name', '')
                            name = f"{first_name} {last_name}".strip() or emp_id
                            family_status = emp.get('family_status') or emp.get('Family Status', 'EE')
                            age = emp.get('age') or emp.get('ee_age', '')
                            state = emp.get('state') or emp.get('Home State', '')
                            rating_area = emp.get('rating_area_id', '')
                            # zip_code is the canonical column name after census processing
                            zip_code = emp.get('zip_code') or emp.get('home_zip') or emp.get('Home Zip', '')
                        else:
                            name = emp_id
                            first_name = ''
                            last_name = ''
                            family_status = ''
                            age = ''
                            state = ''
                            rating_area = ''
                            zip_code = ''

                        # Get rates for this employee
                        emp_rates = emp_metal_rates.get(str(emp_id), {})

                        export_data.append({
                            'Employee ID': emp_id,
                            'First Name': first_name,
                            'Last Name': last_name,
                            'Age': age,
                            'State': state,
                            'ZIP': zip_code,
                            'Rating Area': rating_area,
                            'Family Status': family_status,
                            'Contribution Class': assign['class_id'],
                            'Monthly Contribution': assign['monthly_contribution'],
                            'Annual Contribution': assign['annual_contribution'],
                            'Bronze Rate': emp_rates.get('Bronze', '') or '',
                            'Silver Rate': emp_rates.get('Silver', '') or '',
                            'Gold Rate': emp_rates.get('Gold', '') or ''
                        })

                    export_df = pd.DataFrame(export_data)

                    # Convert to CSV
                    csv_data = export_df.to_csv(index=False)

                    # Strategy name for filename
                    strategy_name = settings.get('strategy_applied', 'contribution')

                    # Build filename with client name and timestamp
                    from datetime import datetime
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    client_name = st.session_state.get('client_name', '').strip()
                    base_name = f"ichra_{strategy_name}_contributions"
                    if client_name:
                        safe_name = client_name.replace(' ', '_').replace('/', '-')
                        csv_filename = f"{base_name}_{safe_name}_{timestamp}.csv"
                    else:
                        csv_filename = f"{base_name}_{timestamp}.csv"

                    st.download_button(
                        label="Download full contribution schedule (CSV)",
                        data=csv_data,
                        file_name=csv_filename,
                        mime="text/csv",
                        key=f"export_csv_{idx}"
                    )

                    st.caption(f"Export includes {len(export_data)} employees with contribution assignments")

                # Clear strategy button
                if st.button("Clear strategy", key=f"clear_{idx}"):
                    st.session_state.contribution_settings = {
                        'default_percentage': 75,
                        'by_class': {},
                        'contribution_type': 'percentage'
                    }
                    st.rerun()

    # ===========================================================================
    # FLAGGED HIGH-COST EMPLOYEES
    # ===========================================================================

    # Flagged high-cost employees
    if analysis.get('flagged_employees'):
        with st.expander(f"⚠️ High-cost employees ({len(analysis['flagged_employees'])} flagged)", expanded=False):
            st.markdown("These employees require significantly higher contributions than average (>2× median):")

            flagged_df = pd.DataFrame(analysis['flagged_employees'])

            # Format the dataframe for display
            display_df = flagged_df[[
                'employee_id', 'age', 'state', 'rating_area_id',
                'lcsp_premium', 'min_er_contribution', 'current_er_contribution', 'gap'
            ]].copy()

            # Format currency columns
            for col in ['lcsp_premium', 'min_er_contribution', 'current_er_contribution', 'gap']:
                display_df[col] = display_df[col].apply(lambda x: f"${x:,.0f}")

            # Rename columns for display
            display_df.columns = [
                'Employee ID', 'Age', 'State', 'Rating Area',
                'LCSP Premium', 'Min ER Contribution', 'Current ER', 'Gap'
            ]

            st.dataframe(display_df, hide_index=True, width='stretch')

            st.markdown("""
            **Options for high-cost employees:**
            - Verify income data is accurate
            - Consider individual contribution adjustments
            - Evaluate alternative coverage options
            - Review if employee qualifies for premium subsidies
            """)

# Show current budget status
if st.session_state.contribution_analysis:
    st.markdown("---")
    analyzed_count = len(st.session_state.contribution_analysis)
    total_employees = len(census_df)

    # Calculate totals from contribution_analysis
    total_er = sum(
        a['ichra_analysis'].get('employer_contribution', 0)
        for a in st.session_state.contribution_analysis.values()
        if 'ichra_analysis' in a
    )
    total_ee = sum(
        a['ichra_analysis'].get('employee_cost', 0)
        for a in st.session_state.contribution_analysis.values()
        if 'ichra_analysis' in a
    )

    st.success(f"✅ Strategy applied to {analyzed_count} of {total_employees} employees")

    budget_cols = st.columns(2)
    budget_cols[0].metric("ICHRA ER monthly", f"${total_er:,.2f}")
    budget_cols[1].metric("ICHRA EE monthly", f"${total_ee:,.2f}")
    # budget_cols[2].metric("ICHRA ER Annual", f"${total_er * 12:,.2f}")

    st.info("💡 Go to **4️⃣ Employer summary** to compare this ICHRA budget against your current group plan costs")

# Navigation hint to Individual Analysis page
st.info("💡 **Need to analyze individual employees?** Go to **5️⃣ Individual analysis** to view LCSP, marketplace options, and affordability details for specific employees.")

st.markdown("---")

# =============================================================================
# UNAFFORDABILITY & SUBSIDY ANALYSIS (Non-ALE Strategy)
# =============================================================================

# Only show if we have strategy results
if st.session_state.strategy_results and st.session_state.strategy_results.get('current'):
    current_result = st.session_state.strategy_results['current']
    strategy_type = current_result.get('strategy_type', '').lower()

    # Check if this strategy can use unaffordability analysis
    from subsidy_calculator import can_use_unaffordability_strategy

    can_analyze = can_use_unaffordability_strategy(strategy_type)

    # Check for income data
    has_income = census_df['monthly_income'].notna().any() if 'monthly_income' in census_df.columns else False

    with st.expander("📊 Unaffordability & Subsidy Analysis (Non-ALE)", expanded=False):
        st.markdown("""
        **For non-ALE employers:** Model intentional ICHRA unaffordability to help employees
        qualify for marketplace subsidies. Core premise: *Use the larger of either the subsidy
        or the ICHRA contribution.*
        """)

        if not can_analyze:
            st.warning("""
            ⚠️ **Not applicable with FPL Safe Harbor strategy**

            The FPL Safe Harbor guarantees ICHRA affordability for all employees by definition.
            Unaffordability analysis only applies to strategies where some employees may have
            unaffordable ICHRA offers (Flat Amount, Age Curve, Age Tiers, or Percentage LCSP < 90%).
            """)
        elif not has_income:
            st.warning("""
            ⚠️ **Income data required**

            Add a 'Monthly Income' column to your census to enable unaffordability analysis.
            This data is needed to:
            - Calculate FPL percentage for each employee
            - Determine subsidy eligibility (must be < 400% FPL)
            - Compare ICHRA contribution vs potential marketplace subsidy
            """)
        else:
            # Run the unaffordability analysis
            if st.button("Run Subsidy Analysis", key="run_subsidy_analysis", type="secondary"):
                from subsidy_calculator import analyze_workforce_unaffordability
                from queries import PlanQueries
                # Note: get_age_band() is defined locally in this file around line 595

                with st.spinner("Calculating subsidies and comparing to ICHRA contributions..."):
                    try:
                        # Build employee locations for SLCSP query
                        employee_locations = []
                        emp_lookup = {}  # Map (state, ra, age_band) -> employee_ids

                        for _, emp in census_df.iterrows():
                            emp_id = str(emp.get('employee_id') or
                                       emp.get('Employee Number') or
                                       emp.get('employee_number', ''))
                            state = str(emp.get('state') or emp.get('Home State', '')).upper()
                            ra_id = emp.get('rating_area_id')
                            age = int(emp.get('age') or emp.get('ee_age', 30))
                            age_band = get_age_band(age)

                            if state and ra_id:
                                loc = {'state_code': state, 'rating_area_id': int(ra_id), 'age_band': age_band}
                                key = (state, int(ra_id), age_band)
                                employee_locations.append(loc)
                                if key not in emp_lookup:
                                    emp_lookup[key] = []
                                emp_lookup[key].append(emp_id)

                        # Get LCSP and SLCSP data
                        db = st.session_state.db
                        lcsp_slcsp_df = PlanQueries.get_lcsp_and_slcsp_batch(db, employee_locations)

                        # Build LCSP and SLCSP dictionaries by employee
                        lcsp_data = {}
                        slcsp_data = {}

                        for _, row in lcsp_slcsp_df.iterrows():
                            state = row['state_code']
                            ra_id = int(row['rating_area_id'])
                            age_band = row['age_band']
                            premium = float(row['premium'])
                            rank = int(row['plan_rank'])
                            key = (state, ra_id, age_band)

                            for emp_id in emp_lookup.get(key, []):
                                if rank == 1:  # LCSP
                                    lcsp_data[emp_id] = {'lcsp_premium': premium}
                                elif rank == 2:  # SLCSP
                                    slcsp_data[emp_id] = {'slcsp_premium': premium}

                        # Get employee contributions from strategy results
                        employee_contributions = current_result.get('employee_contributions', {})

                        # Run analysis
                        analysis_results = analyze_workforce_unaffordability(
                            census_df=census_df,
                            employee_contributions=employee_contributions,
                            lcsp_data=lcsp_data,
                            slcsp_data=slcsp_data,
                            household_size=1  # Default to single
                        )

                        # Store in session state
                        st.session_state.subsidy_analysis = analysis_results
                        st.rerun()

                    except Exception as e:
                        st.error(f"Error running subsidy analysis: {e}")
                        import traceback
                        st.code(traceback.format_exc())

            # Display results if available
            if 'subsidy_analysis' in st.session_state and st.session_state.subsidy_analysis:
                analysis = st.session_state.subsidy_analysis
                summary = analysis['summary']
                under_65 = analysis['under_65']
                medicare = analysis['medicare']

                st.markdown("---")
                st.markdown("### Analysis Results")

                # Summary metrics
                summary_cols = st.columns(4)

                with summary_cols[0]:
                    st.metric("Under 65", summary['under_65_count'])
                    st.caption(f"Affordable: {summary['affordable_count']}")
                    st.caption(f"Unaffordable: {summary['unaffordable_count']}")

                with summary_cols[1]:
                    st.metric("Medicare (65+)", summary['medicare_count'])
                    st.caption("ICHRA only")
                    st.caption("(no subsidy eligibility)")

                with summary_cols[2]:
                    st.metric("Subsidy Recommended", summary['subsidy_recommended_count'])
                    st.caption("Better off with marketplace")

                with summary_cols[3]:
                    total_subsidies = summary['total_potential_subsidies_monthly']
                    st.metric("Potential Subsidies", f"${total_subsidies:,.0f}/mo")
                    st.caption(f"${total_subsidies * 12:,.0f}/yr")

                # Cost comparison
                st.markdown("---")
                st.markdown("#### Cost Comparison")

                cost_cols = st.columns(4)
                with cost_cols[0]:
                    st.metric("Total ER ICHRA (all)", f"${summary['total_er_ichra_monthly']:,.0f}/mo")
                with cost_cols[1]:
                    st.metric("ER ICHRA (affordable only)", f"${summary['total_er_ichra_affordable_monthly']:,.0f}/mo")
                with cost_cols[2]:
                    st.metric("Total Potential Subsidies", f"${summary['total_potential_subsidies_monthly']:,.0f}/mo")
                with cost_cols[3]:
                    net_benefit = summary['net_employee_benefit_monthly']
                    st.metric("Net EE Benefit", f"${net_benefit:,.0f}/mo",
                             help="Subsidy - foregone ICHRA for unaffordable employees")

                # Employee detail tables
                st.markdown("---")
                st.markdown("#### Employee Detail (Under 65)")

                if under_65:
                    detail_data = []
                    for r in under_65:
                        detail_data.append({
                            'Name': r.employee_name,
                            'Age': r.age,
                            'Income': f"${r.monthly_income:,.0f}",
                            'LCSP': f"${r.lcsp_premium:,.0f}",
                            'SLCSP': f"${r.slcsp_premium:,.0f}" if r.slcsp_premium else '-',
                            'ER Contrib': f"${r.er_contribution:,.0f}",
                            'Subsidy': f"${r.subsidy_value:,.0f}" if r.subsidy_value else '-',
                            'Affordable': '✅' if r.is_affordable else '❌',
                            'Recommend': r.recommendation,
                        })

                    detail_df = pd.DataFrame(detail_data)
                    st.dataframe(detail_df, hide_index=True, width='stretch')
                else:
                    st.info("No employees under 65 with income data.")

                # Medicare employees (separate section)
                if medicare:
                    st.markdown("---")
                    st.markdown("#### Medicare-Eligible Employees (65+)")
                    st.caption("*Medicare-eligible employees cannot receive ACA marketplace subsidies.*")

                    medicare_data = []
                    for r in medicare:
                        medicare_data.append({
                            'Name': r.employee_name,
                            'Age': r.age,
                            'ER Contribution': f"${r.er_contribution:,.0f}",
                            'Note': 'ICHRA for Medicare premiums only'
                        })

                    medicare_df = pd.DataFrame(medicare_data)
                    st.dataframe(medicare_df, hide_index=True, width='stretch')

                # Export to Excel
                st.markdown("---")
                if st.button("Export Subsidy Analysis to CSV", key="export_subsidy_csv"):
                    export_rows = []

                    for r in under_65 + medicare:
                        export_rows.append({
                            'Employee ID': r.employee_id,
                            'Name': r.employee_name,
                            'Age': r.age,
                            'State': r.state,
                            'Family Status': r.family_status,
                            'Monthly Income': r.monthly_income,
                            'Annual Income': r.annual_income,
                            'LCSP Premium': r.lcsp_premium,
                            'SLCSP Premium': r.slcsp_premium or '',
                            'ER Contribution': r.er_contribution,
                            'EE Cost w/ICHRA': r.ee_cost_with_ichra,
                            'Max Affordable EE Cost': r.max_affordable_ee_cost,
                            'Is Affordable': r.is_affordable,
                            'FPL %': r.fpl_percentage or '',
                            'Applicable %': r.applicable_percentage or '',
                            'Expected Contribution': r.expected_contribution or '',
                            'Subsidy Value': r.subsidy_value or '',
                            'Medicare Eligible': r.is_medicare_eligible,
                            'Recommendation': r.recommendation,
                            'Net Benefit': r.net_benefit,
                            'Notes': r.notes
                        })

                    export_df = pd.DataFrame(export_rows)
                    csv_data = export_df.to_csv(index=False)

                    from datetime import datetime
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    client_name = st.session_state.get('client_name', '').strip()
                    if client_name:
                        safe_name = client_name.replace(' ', '_').replace('/', '-')
                        filename = f"subsidy_analysis_{safe_name}_{timestamp}.csv"
                    else:
                        filename = f"subsidy_analysis_{timestamp}.csv"

                    st.download_button(
                        label="Download CSV",
                        data=csv_data,
                        file_name=filename,
                        mime="text/csv",
                        key="subsidy_csv_download"
                    )

                # Clear analysis button
                if st.button("Clear Subsidy Analysis", key="clear_subsidy_analysis"):
                    del st.session_state.subsidy_analysis
                    st.rerun()

st.markdown("---")

# =============================================================================
# AI CHAT INTERFACE
# =============================================================================

st.subheader("🤖 AI evaluation assistant")

if not ANTHROPIC_AVAILABLE:
    st.warning("AI features require the `anthropic` library. Install with: `pip install anthropic`")
elif not get_anthropic_api_key():
    st.warning("Set ANTHROPIC_API_KEY in environment or Streamlit secrets to enable AI features.")
else:
    # Build context for AI
    context_parts = [
        f"Census: {num_employees} employees",
        f"Contribution type: {st.session_state.contribution_settings.get('contribution_type', 'percentage')}",
    ]

    contrib_type = st.session_state.contribution_settings.get('contribution_type', 'percentage')
    if contrib_type == 'percentage':
        context_parts.append(f"Default contribution: {st.session_state.contribution_settings.get('default_percentage', 75)}%")
    else:  # class_based
        strategy = st.session_state.contribution_settings.get('strategy_applied', 'unknown')
        total_monthly = st.session_state.contribution_settings.get('total_monthly', 0)
        context_parts.append(f"Strategy: {strategy}, Total monthly: ${total_monthly:,.0f}")

    context = "\n".join(context_parts)

    # Display chat history
    for msg in st.session_state.eval_chat_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input
    if prompt := st.chat_input("Ask about contribution evaluation..."):
        # Add user message
        st.session_state.eval_chat_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Get AI response
        with st.chat_message("assistant"):
            with st.spinner("Analyzing..."):
                response = get_evaluation_response(prompt, context)
                st.markdown(response)
                st.session_state.eval_chat_messages.append({"role": "assistant", "content": response})

    # Clear chat button
    if st.session_state.eval_chat_messages:
        if st.button("Clear chat"):
            st.session_state.eval_chat_messages = []
            st.rerun()

# Suggested prompts
st.markdown("---")
st.markdown("**Try asking:**")
col1, col2, col3 = st.columns(3)
with col1:
    st.markdown("- What marketplace options does employee 1001 have?")
with col2:
    st.markdown("- Compare current vs ICHRA costs for all employees")
with col3:
    st.markdown("- What's the LCSP for employee 1002?")

# Feedback button in sidebar
render_feedback_sidebar()
