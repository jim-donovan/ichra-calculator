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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Page config
st.set_page_config(page_title="Contribution Evaluation", page_icon="💰", layout="wide")

# =============================================================================
# SCROLL TO TOP ON FRESH NAVIGATION
# =============================================================================
# Add anchor at top of page and use CSS/JS to ensure scroll position
st.markdown('<div id="top-anchor"></div>', unsafe_allow_html=True)

# Use session state to detect fresh page load vs rerun
if 'page2_initialized' not in st.session_state:
    st.session_state.page2_initialized = True
    # Inject JavaScript to scroll to top on fresh navigation
    st.markdown("""
    <style>
        /* Ensure page starts at top */
        html, body {
            scroll-behavior: auto !important;
        }
    </style>
    <script>
        // Scroll to top immediately
        window.scrollTo({top: 0, left: 0, behavior: 'instant'});
        // Also try after a short delay for Streamlit's dynamic content
        setTimeout(function() {
            window.scrollTo({top: 0, left: 0, behavior: 'instant'});
        }, 100);
    </script>
    """, unsafe_allow_html=True)

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

    --amber-50: #fffbeb;
    --amber-100: #fef3c7;
    --amber-500: #f59e0b;
    --amber-600: #d97706;

    --red-50: #fef2f2;
    --red-100: #fee2e2;
    --red-500: #ef4444;
    --red-600: #dc2626;
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
    """Calculate total family premium for a plan"""
    family_status = str(employee.get('family_status', 'EE')).upper()
    rating_area_id = employee.get('rating_area_id')

    if not rating_area_id:
        return None

    total_premium = 0.0

    # Employee premium
    ee_age = employee.get('age', employee.get('ee_age', 30))
    age_band = get_age_band(int(ee_age))

    rate_query = """
        SELECT individual_rate
        FROM rbis_insurance_plan_base_rates_20251019202724
        WHERE plan_id = %s
          AND REPLACE(rating_area_id, 'Rating Area ', '')::integer = %s
          AND age = %s
          AND tobacco IN ('No Preference', 'Tobacco User/Non-Tobacco User')
          AND rate_effective_date = '2026-01-01'
        LIMIT 1
    """

    result = db.execute_query(rate_query, (plan_id, int(rating_area_id), age_band))
    if result.empty:
        return None

    total_premium = float(result.iloc[0]['individual_rate'])

    # Add spouse if applicable
    if family_status in ['ES', 'F']:
        spouse_age = employee.get('spouse_age')
        if spouse_age:
            spouse_band = get_age_band(int(spouse_age))
            result = db.execute_query(rate_query, (plan_id, int(rating_area_id), spouse_band))
            if not result.empty:
                total_premium += float(result.iloc[0]['individual_rate'])

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
            result = db.execute_query(rate_query, (plan_id, int(rating_area_id), child_band))
            if not result.empty:
                total_premium += float(result.iloc[0]['individual_rate'])

    return total_premium


# =============================================================================
# TOOL HANDLERS
# =============================================================================

def get_marketplace_options(employee_id: str, metal_levels: list = None, max_results: int = 5) -> dict:
    """Get marketplace plan options for an employee"""
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

        # Build query for plans with rates
        metal_filter = ""
        params = [state.upper(), int(rating_area_id), age_band]

        if metal_levels:
            placeholders = ', '.join(['%s'] * len(metal_levels))
            metal_filter = f"AND p.level_of_coverage IN ({placeholders})"
            params.extend(metal_levels)

        query = f"""
            SELECT DISTINCT
                p.hios_plan_id as plan_id,
                p.plan_marketing_name as plan_name,
                p.level_of_coverage as metal_level,
                p.plan_type,
                r.individual_rate as monthly_premium,
                CASE
                    WHEN v.csr_variation_type = 'Exchange variant (no CSR)' THEN 'On-Exchange'
                    WHEN v.csr_variation_type = 'Non-Exchange variant' THEN 'Off-Exchange'
                    ELSE v.csr_variation_type
                END as exchange_status
            FROM rbis_insurance_plan_20251019202724 p
            JOIN rbis_insurance_plan_variant_20251019202724 v
                ON p.hios_plan_id = v.hios_plan_id
            JOIN rbis_insurance_plan_base_rates_20251019202724 r
                ON p.hios_plan_id = r.plan_id
            WHERE p.market_coverage = 'Individual'
              AND v.csr_variation_type NOT LIKE '%%CSR%%'
              AND SUBSTRING(p.hios_plan_id FROM 6 FOR 2) = %s
              AND REPLACE(r.rating_area_id, 'Rating Area ', '')::integer = %s
              AND r.age = %s
              AND r.tobacco IN ('No Preference', 'Tobacco User/Non-Tobacco User')
              AND r.rate_effective_date = '2026-01-01'
              {metal_filter}
            ORDER BY r.individual_rate ASC
            LIMIT %s
        """
        params.append(max_results)

        df = db.execute_query(query, tuple(params))

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
    """Get Lowest Cost Silver Plan for affordability analysis"""
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

        # Get LCSP (lowest cost silver plan)
        # NOTE: LCSP must be from on-exchange plans only for IRS affordability safe harbor
        query = """
            SELECT
                p.hios_plan_id as plan_id,
                p.plan_marketing_name as plan_name,
                p.level_of_coverage as metal_level,
                p.plan_type,
                r.individual_rate as monthly_premium
            FROM rbis_insurance_plan_20251019202724 p
            JOIN rbis_insurance_plan_variant_20251019202724 v
                ON p.hios_plan_id = v.hios_plan_id
            JOIN rbis_insurance_plan_base_rates_20251019202724 r
                ON p.hios_plan_id = r.plan_id
            WHERE p.level_of_coverage = 'Silver'
              AND p.market_coverage = 'Individual'
              AND v.csr_variation_type = 'Exchange variant (no CSR)'
              AND SUBSTRING(p.hios_plan_id FROM 6 FOR 2) = %s
              AND REPLACE(r.rating_area_id, 'Rating Area ', '')::integer = %s
              AND r.age = %s
              AND r.tobacco IN ('No Preference', 'Tobacco User/Non-Tobacco User')
              AND r.rate_effective_date = '2026-01-01'
            ORDER BY r.individual_rate ASC
            LIMIT 1
        """

        df = db.execute_query(query, (state.upper(), int(rating_area_id), age_band))

        if df.empty:
            return {"error": f"No Silver plans found for rating area {rating_area_id}"}

        lcsp = df.iloc[0]
        lcsp_premium = float(lcsp['monthly_premium'])
        plan_id = lcsp['plan_id']

        # For family coverage, calculate total family premium
        if coverage_type == 'family' and family_status in ['ES', 'EC', 'F']:
            family_premium = calculate_family_premium(employee, plan_id, db)
            if family_premium:
                lcsp_premium = family_premium

        # Get deductible and OOPM
        deductible_query = """
            SELECT individual_ded_moop_amount
            FROM rbis_insurance_plan_variant_ddctbl_moop_20251019202724
            WHERE plan_id = %s
              AND moop_ded_type LIKE '%%Deductible%%'
              AND individual_ded_moop_amount != 'Not Applicable'
              AND network_type = 'In Network'
            LIMIT 1
        """
        ded_result = db.execute_query(deductible_query, (plan_id,))
        deductible = ded_result.iloc[0]['individual_ded_moop_amount'] if not ded_result.empty else None

        moop_query = """
            SELECT individual_ded_moop_amount
            FROM rbis_insurance_plan_variant_ddctbl_moop_20251019202724
            WHERE plan_id = %s
              AND moop_ded_type LIKE '%%Maximum Out of Pocket%%'
              AND individual_ded_moop_amount != 'Not Applicable'
              AND network_type = 'In Network'
            LIMIT 1
        """
        moop_result = db.execute_query(moop_query, (plan_id,))
        oopm = moop_result.iloc[0]['individual_ded_moop_amount'] if not moop_result.empty else None

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
    """Find the plan closest in price to the employee's current total premium"""
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

        # Get all available plans in the rating area for this employee's age
        query = """
            SELECT DISTINCT
                p.hios_plan_id as plan_id,
                p.plan_marketing_name as plan_name,
                p.level_of_coverage as metal_level,
                p.plan_type,
                r.individual_rate as employee_rate,
                CASE
                    WHEN v.csr_variation_type = 'Exchange variant (no CSR)' THEN 'On-Exchange'
                    WHEN v.csr_variation_type = 'Non-Exchange variant' THEN 'Off-Exchange'
                    ELSE v.csr_variation_type
                END as exchange_status
            FROM rbis_insurance_plan_20251019202724 p
            JOIN rbis_insurance_plan_variant_20251019202724 v
                ON p.hios_plan_id = v.hios_plan_id
            JOIN rbis_insurance_plan_base_rates_20251019202724 r
                ON p.hios_plan_id = r.plan_id
            WHERE p.market_coverage = 'Individual'
              AND v.csr_variation_type NOT LIKE '%%CSR%%'
              AND SUBSTRING(p.hios_plan_id FROM 6 FOR 2) = %s
              AND REPLACE(r.rating_area_id, 'Rating Area ', '')::integer = %s
              AND r.age = %s
              AND r.tobacco IN ('No Preference', 'Tobacco User/Non-Tobacco User')
              AND r.rate_effective_date = '2026-01-01'
        """

        df = db.execute_query(query, (state.upper(), int(rating_area_id), age_band))

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
                actual_premium = float(plan['employee_rate'])

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

        # Get deductible and OOPM from the deductible/MOOP table
        deductible_query = """
            SELECT individual_ded_moop_amount
            FROM rbis_insurance_plan_variant_ddctbl_moop_20251019202724
            WHERE plan_id = %s
              AND moop_ded_type LIKE '%%Deductible%%'
              AND individual_ded_moop_amount != 'Not Applicable'
              AND network_type = 'In Network'
            LIMIT 1
        """
        ded_result = db.execute_query(deductible_query, (plan_id,))
        deductible = ded_result.iloc[0]['individual_ded_moop_amount'] if not ded_result.empty else None

        moop_query = """
            SELECT individual_ded_moop_amount
            FROM rbis_insurance_plan_variant_ddctbl_moop_20251019202724
            WHERE plan_id = %s
              AND moop_ded_type LIKE '%%Maximum Out of Pocket%%'
              AND individual_ded_moop_amount != 'Not Applicable'
              AND network_type = 'In Network'
            LIMIT 1
        """
        moop_result = db.execute_query(moop_query, (plan_id,))
        oopm = moop_result.iloc[0]['individual_ded_moop_amount'] if not moop_result.empty else None

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

    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        return "AI evaluation requires ANTHROPIC_API_KEY environment variable."

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

st.title("💰 Contribution Evaluation")
st.markdown("Evaluate what employees can get on the marketplace compared to their current contributions.")

# Check for census
if 'census_df' not in st.session_state or st.session_state.census_df is None:
    st.warning("⚠️ Please upload employee census data first.")
    st.markdown("Go to **1️⃣ Employee Census** to upload your census file.")
    st.stop()

census_df = st.session_state.census_df
num_employees = len(census_df)

st.success(f"✓ {num_employees} employees loaded from census")

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
                with st.expander("🔍 Full Error Details (for debugging)"):
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
        total_ee = ee_col.fillna(0).sum()
        total_er = er_col.fillna(0).sum()
        total_premium = total_ee + total_er

        st.markdown("**📊 Current Group Plan Costs**")
        contrib_col1, contrib_col2, contrib_col3, contrib_col4 = st.columns(4)
        contrib_col1.metric("EE Monthly", f"${total_ee:,.0f}")
        contrib_col2.metric("ER Monthly", f"${total_er:,.0f}")
        contrib_col3.metric("Total Monthly", f"${total_premium:,.0f}")
        contrib_col4.metric("Employees w/ Data", f"{has_data_count}/{num_employees}")
    else:
        st.warning("⚠️ Census has contribution columns but no data. Add 'Current EE Monthly' and 'Current ER Monthly' values for cost comparison.")
else:
    st.warning("⚠️ No current contribution data in census. Add 'Current EE Monthly' and 'Current ER Monthly' columns for cost comparison.")

st.markdown("---")

# =============================================================================
# CONTRIBUTION STRATEGY MODELER
# =============================================================================

st.markdown("## 🎯 Contribution Strategy Modeler")

st.markdown("""
Model different employer contribution strategies to find the optimal approach for your workforce.
Each strategy calculates per-employee contributions based on their actual LCSP and demographics.
""")

# Initialize strategy state if needed
if 'strategy_results' not in st.session_state:
    st.session_state.strategy_results = {}

# Strategy type selector
strategy_options = [
    ("Base Age + ACA 3:1 Curve", "base_age_curve"),
    ("Percentage of Per-Employee LCSP", "percentage_lcsp"),
    ("Fixed Age Tiers", "fixed_age_tiers"),
    ("Custom Dollar Amounts", "custom"),
]

selected_strategy = st.selectbox(
    "Select Strategy Type",
    options=strategy_options,
    format_func=lambda x: x[0],
    key="strategy_type_selector"
)

strategy_type = selected_strategy[1]

# Strategy-specific configuration
strategy_config_col1, strategy_config_col2 = st.columns([2, 1])

with strategy_config_col1:
    if strategy_type == "base_age_curve":
        st.markdown("##### Base Age + ACA 3:1 Curve")
        st.markdown("""
        Set a base contribution for a reference age. The system scales contributions using the
        ACA 3:1 age rating curve (age 64 costs 3x age 21).
        """)

        curve_col1, curve_col2 = st.columns(2)
        with curve_col1:
            base_age = st.selectbox(
                "Base Age",
                options=[21, 25, 30, 35, 40],
                index=0,
                key="base_age_select"
            )
        with curve_col2:
            base_contribution = st.number_input(
                "Base Contribution ($/month)",
                min_value=0.0,
                max_value=5000.0,
                value=400.0,
                step=25.0,
                key="base_contribution_input"
            )

        # Show preview of curve
        from constants import ACA_AGE_CURVE
        base_ratio = ACA_AGE_CURVE.get(base_age, 1.0)
        age_64_amount = base_contribution * (ACA_AGE_CURVE[64] / base_ratio)
        age_40_amount = base_contribution * (ACA_AGE_CURVE[40] / base_ratio)
        st.info(f"**Preview:** Age {base_age}: ${base_contribution:,.0f}/mo → Age 40: ${age_40_amount:,.0f}/mo → Age 64: ${age_64_amount:,.0f}/mo")

    elif strategy_type == "percentage_lcsp":
        st.markdown("##### Percentage of Per-Employee LCSP")
        st.markdown("""
        Each employee receives a contribution equal to X% of their individual LCSP premium.
        The LCSP is calculated using each employee's specific rating area and age.
        """)

        lcsp_percentage = st.slider(
            "Percentage of LCSP to Cover",
            min_value=50,
            max_value=100,
            value=75,
            step=5,
            format="%d%%",
            key="lcsp_percentage_slider"
        )
        st.info(f"**{lcsp_percentage}%** of each employee's LCSP will be contributed. Lower-cost employees get smaller contributions, higher-cost employees get larger contributions.")

    elif strategy_type == "fixed_age_tiers":
        st.markdown("##### Fixed Age Tiers")
        st.markdown("""
        Set specific dollar amounts for each age tier. Employees are assigned to tiers based on their age.
        """)

        # Editable tier amounts
        tier_amounts = {}
        tier_cols = st.columns(4)
        default_amounts = {'21': 300, '18-25': 350, '26-35': 400, '36-45': 500, '46-55': 600, '56-63': 750, '64+': 900}

        tier_labels = ['21', '18-25', '26-35', '36-45', '46-55', '56-63', '64+']
        for i, tier in enumerate(tier_labels):
            col_idx = i % 4
            with tier_cols[col_idx]:
                tier_amounts[tier] = st.number_input(
                    f"Age {tier}",
                    min_value=0.0,
                    max_value=5000.0,
                    value=float(default_amounts.get(tier, 400)),
                    step=25.0,
                    key=f"tier_amount_{tier}"
                )

    elif strategy_type == "custom":
        st.markdown("##### Custom Dollar Amounts")
        st.markdown("Define custom contribution classes with specific criteria and amounts.")
        st.warning("Custom class configuration is coming soon. Use Fixed Age Tiers for now.")
        tier_amounts = {}  # Placeholder

with strategy_config_col2:
    st.markdown("##### Options")
    apply_family_multipliers = st.checkbox(
        "Apply Family Multipliers",
        value=True,
        help="EE=1.0x, ES=1.5x, EC=1.3x, F=1.8x",
        key="apply_family_mult"
    )

    if apply_family_multipliers:
        st.caption("Family multipliers: EE=1.0x, ES=1.5x, EC=1.3x, F=1.8x")

# Calculate button
if st.button("Calculate Strategy", type="primary", key="calc_strategy_btn"):
    from contribution_strategies import (
        ContributionStrategyCalculator,
        StrategyConfig,
        StrategyType as StratType
    )

    with st.spinner("Calculating contributions..."):
        try:
            calculator = ContributionStrategyCalculator(st.session_state.db, census_df)

            # Build config based on strategy type
            if strategy_type == "base_age_curve":
                config = StrategyConfig(
                    strategy_type=StratType.BASE_AGE_CURVE,
                    base_age=base_age,
                    base_contribution=base_contribution,
                    apply_family_multipliers=apply_family_multipliers
                )
            elif strategy_type == "percentage_lcsp":
                config = StrategyConfig(
                    strategy_type=StratType.PERCENTAGE_LCSP,
                    lcsp_percentage=lcsp_percentage,
                    apply_family_multipliers=apply_family_multipliers
                )
            elif strategy_type == "fixed_age_tiers":
                config = StrategyConfig(
                    strategy_type=StratType.FIXED_AGE_TIERS,
                    tier_amounts=tier_amounts,
                    apply_family_multipliers=apply_family_multipliers
                )
            else:
                st.error("Custom strategy not yet implemented")
                config = None

            if config:
                result = calculator.calculate_strategy(config)
                st.session_state.strategy_results[strategy_type] = result
                st.success(f"Strategy calculated: **{result['strategy_name']}**")
                st.rerun()

        except Exception as e:
            st.error(f"Error calculating strategy: {e}")
            import traceback
            st.code(traceback.format_exc())

# Display strategy results if available
if st.session_state.strategy_results:
    st.markdown("---")
    st.markdown("### 📈 Strategy Results")

    # Get most recent result (or allow selection if multiple)
    available_strategies = list(st.session_state.strategy_results.keys())

    if len(available_strategies) > 1:
        st.markdown("**Calculated Strategies:**")
        for strat_key in available_strategies:
            result = st.session_state.strategy_results[strat_key]
            st.markdown(f"- {result['strategy_name']}: **${result['total_annual']:,.0f}/year**")

    # Show detailed results for most recent
    current_result = st.session_state.strategy_results.get(strategy_type)
    if current_result:
        result = current_result

        # Summary metrics
        metric_cols = st.columns(4)
        metric_cols[0].metric("Total Monthly", f"${result['total_monthly']:,.0f}")
        metric_cols[1].metric("Total Annual", f"${result['total_annual']:,.0f}")
        metric_cols[2].metric("Employees", f"{result['employees_covered']}")
        avg_monthly = result['total_monthly'] / result['employees_covered'] if result['employees_covered'] > 0 else 0
        metric_cols[3].metric("Avg Monthly", f"${avg_monthly:,.0f}")

        # Breakdown by age tier
        with st.expander("📊 Breakdown by Age Tier", expanded=False):
            by_age = result.get('by_age_tier', {})
            if by_age:
                age_data = []
                for tier, data in by_age.items():
                    avg = data['total_monthly'] / data['count'] if data['count'] > 0 else 0
                    age_data.append({
                        'Age Tier': tier,
                        'Employees': data['count'],
                        'Total Monthly': f"${data['total_monthly']:,.0f}",
                        'Avg Monthly': f"${avg:,.0f}"
                    })
                st.dataframe(pd.DataFrame(age_data), hide_index=True, width="stretch")

        # Breakdown by family status
        with st.expander("👨‍👩‍👧 Breakdown by Family Status", expanded=False):
            by_fs = result.get('by_family_status', {})
            if by_fs:
                fs_data = []
                for fs, data in by_fs.items():
                    avg = data['total_monthly'] / data['count'] if data['count'] > 0 else 0
                    fs_data.append({
                        'Family Status': fs,
                        'Employees': data['count'],
                        'Total Monthly': f"${data['total_monthly']:,.0f}",
                        'Avg Monthly': f"${avg:,.0f}"
                    })
                st.dataframe(pd.DataFrame(fs_data), hide_index=True, width="stretch")

        # Employee-level detail
        with st.expander("📋 Employee Contribution Detail", expanded=False):
            emp_contribs = result.get('employee_contributions', {})
            if emp_contribs:
                detail_data = []
                for emp_id, data in emp_contribs.items():
                    # Get employee name from census
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
                st.dataframe(detail_df, hide_index=True, width="stretch")

        # CSV Export
        st.markdown("---")
        st.markdown("##### Export Strategy Data")

        emp_contribs = result.get('employee_contributions', {})
        if emp_contribs:
            export_rows = []
            for emp_id, data in emp_contribs.items():
                emp_row = census_df[
                    (census_df['employee_id'].astype(str) == str(emp_id)) |
                    (census_df.get('Employee Number', pd.Series()).astype(str) == str(emp_id))
                ] if 'employee_id' in census_df.columns or 'Employee Number' in census_df.columns else pd.DataFrame()

                if not emp_row.empty:
                    emp = emp_row.iloc[0]
                    first_name = emp.get('first_name') or emp.get('First Name', '')
                    last_name = emp.get('last_name') or emp.get('Last Name', '')
                    zip_code = emp.get('zip_code') or emp.get('home_zip') or emp.get('Home Zip', '')
                else:
                    first_name = ''
                    last_name = ''
                    zip_code = ''

                export_rows.append({
                    'Employee ID': emp_id,
                    'First Name': first_name,
                    'Last Name': last_name,
                    'Age': data.get('age', ''),
                    'State': data.get('state', ''),
                    'ZIP': zip_code,
                    'Rating Area': data.get('rating_area', ''),
                    'Family Status': data.get('family_status', ''),
                    'LCSP EE Rate': data.get('lcsp_ee_rate', ''),
                    'Age Ratio': data.get('age_ratio', ''),
                    'Base Contribution': data.get('base_contribution', ''),
                    'Family Multiplier': data.get('family_multiplier', ''),
                    'Monthly Contribution': data['monthly_contribution'],
                    'Annual Contribution': data['annual_contribution'],
                    'Strategy Type': result['strategy_type']
                })

            export_df = pd.DataFrame(export_rows)
            csv_data = export_df.to_csv(index=False)

            st.download_button(
                label="Download Contribution Schedule (CSV)",
                data=csv_data,
                file_name=f"ichra_{result['strategy_type']}_contributions.csv",
                mime="text/csv",
                key="strategy_csv_export"
            )
            st.caption(f"Export includes {len(export_rows)} employees")

        # Clear button
        if st.button("Clear All Strategy Results", key="clear_strategy_results"):
            st.session_state.strategy_results = {}
            st.rerun()

st.markdown("---")

# =============================================================================
# IRS AFFORDABILITY ANALYSIS
# =============================================================================

if 'affordability_analysis' in st.session_state and st.session_state.affordability_analysis:
    analysis = st.session_state.affordability_analysis
    summary = analysis['summary']

    st.markdown("## 📊 IRS Affordability Analysis")

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

    # Calculate LCSP average from employee details
    employee_details = analysis.get('employee_details', [])
    lcsp_avg = 0
    if employee_details:
        lcsp_premiums = [e.get('lcsp_premium', 0) for e in employee_details if e.get('lcsp_premium')]
        if lcsp_premiums:
            lcsp_avg = sum(lcsp_premiums) / len(lcsp_premiums)

    # Current Status Metrics (Row 1)
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric(
            "Employees Analyzed",
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
        st.metric(
            "💰 Current ER Spend/yr",
            f"${summary.get('current_er_spend_annual', 0):,.0f}",
            help="Current annual employer spend on health benefits (sum of 'Current ER Monthly' × 12)."
        )

    with col5:
        st.metric(
            "📊 Avg LCSP",
            f"${lcsp_avg:,.0f}/mo",
            help="Average Lowest Cost Silver Plan premium across all analyzed employees."
        )

    # Proposed Strategy Comparison (shows when strategy is applied)
    contribution_settings = st.session_state.get('contribution_settings', {})
    if contribution_settings.get('contribution_type') == 'class_based' and contribution_settings.get('strategy_applied'):
        strategy_name = contribution_settings.get('strategy_applied', '').replace('_', ' ').title()
        proposed_annual = contribution_settings.get('total_annual', 0)
        current_annual = summary.get('current_er_spend_annual', 0)
        savings = current_annual - proposed_annual

        st.markdown("---")
        st.markdown(f"### 📋 Proposed: {strategy_name}")

        prop_col1, prop_col2, prop_col3, prop_col4 = st.columns(4)

        with prop_col1:
            st.metric(
                "Proposed ER Spend/yr",
                f"${proposed_annual:,.0f}",
                help="Total annual employer spend with the applied contribution strategy."
            )

        with prop_col2:
            delta_text = f"+${savings:,.0f}" if savings > 0 else f"-${abs(savings):,.0f}"
            st.metric(
                "vs Current",
                delta_text if savings != 0 else "$0",
                "Savings" if savings > 0 else ("Additional" if savings < 0 else ""),
                delta_color="normal" if savings >= 0 else "inverse",
                help="Difference between proposed and current annual spend."
            )

        with prop_col3:
            st.metric(
                "Employees Covered",
                len(contribution_settings.get('employee_assignments', {})),
                help="Number of employees assigned to contribution classes."
            )

        with prop_col4:
            st.metric(
                "Achieves Affordability",
                "100%",
                "✓",
                help="This strategy is designed to meet IRS affordability requirements for all employees."
            )

    # Visualization: Affordable vs Needs Increase (Pie Chart)
    if summary['employees_analyzed'] > 0:
        fig = go.Figure(data=[go.Pie(
            labels=['Affordable', 'Needs Increase'],
            values=[summary['affordable_at_current'], summary['needs_increase']],
            marker_colors=['#10b981', '#f59e0b'],
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
            metric_cols[0].metric("Annual Cost", f"${rec['annual_cost']:,.0f}")
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
                button_label = "Re-apply" if is_active else "Apply Strategy"
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
                summary_cols[1].metric("Monthly Total", f"${settings.get('total_monthly', 0):,.0f}")
                summary_cols[2].metric("Annual Total", f"${settings.get('total_annual', 0):,.0f}")
                summary_cols[3].metric(
                    "Family Multipliers",
                    "Enabled" if settings.get('apply_family_multipliers') else "Disabled"
                )

                # Class breakdown table (expandable)
                with st.expander("View Contribution Classes", expanded=False):
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
                with st.expander("View Employee Assignments", expanded=False):
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
                            'Annual Contribution': assign['annual_contribution']
                        })

                    export_df = pd.DataFrame(export_data)

                    # Convert to CSV
                    csv_data = export_df.to_csv(index=False)

                    # Strategy name for filename
                    strategy_name = settings.get('strategy_applied', 'contribution')

                    st.download_button(
                        label="Download Full Contribution Schedule (CSV)",
                        data=csv_data,
                        file_name=f"ichra_{strategy_name}_contributions.csv",
                        mime="text/csv",
                        key=f"export_csv_{idx}"
                    )

                    st.caption(f"Export includes {len(export_data)} employees with contribution assignments")

                # Clear strategy button
                if st.button("Clear Strategy", key=f"clear_{idx}"):
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
        with st.expander(f"⚠️ High-Cost Employees ({len(analysis['flagged_employees'])} flagged)", expanded=False):
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

    st.markdown("---")

# =============================================================================
# BATCH ICHRA BUDGET CALCULATION
# =============================================================================

st.subheader("💰 ICHRA Budget Proposal")

st.info("""
**Calculate ICHRA Budget for All Employees**

This will calculate employer costs based on the **Lowest Cost Silver Plan (LCSP)** for each employee.
The LCSP is the IRS benchmark used for ICHRA affordability calculations.

This creates a budget proposal that ensures all employees have access to affordable coverage.
""")

col1, col2 = st.columns([3, 1])
with col1:
    st.markdown("Click below to calculate ICHRA budget for all employees based on LCSP:")
with col2:
    calculate_button = st.button("📊 Calculate Budget", type="primary")

# Process button click and show results outside column context (full-width)
if calculate_button:
    with st.spinner("Calculating ICHRA budget for all employees..."):
        contribution_analysis = {}
        errors = []

        for idx, employee in census_df.iterrows():
            employee_id = employee.get('employee_id')
            if not employee_id:
                continue

            try:
                # Get LCSP for this employee
                lcsp_result = get_lcsp(employee_id)

                if 'error' in lcsp_result:
                    errors.append(f"{employee_id}: {lcsp_result['error']}")
                    continue

                lcsp = lcsp_result['lcsp']
                lcsp_premium = float(lcsp['monthly_premium'].replace('$', '').replace(',', ''))

                # Calculate employer contribution based on settings
                family_status = str(employee.get('family_status', 'EE')).upper()
                settings = st.session_state.contribution_settings
                contrib_type = settings.get('contribution_type', 'percentage')

                if contrib_type == 'percentage':
                    pct = settings.get('default_percentage', 75)
                    employer_contribution = lcsp_premium * (pct / 100)
                    employee_cost = lcsp_premium - employer_contribution
                else:  # class_based
                    # Get contribution from employee assignment
                    emp_id_str = str(employee_id)
                    assignments = settings.get('employee_assignments', {})
                    if emp_id_str in assignments:
                        employer_contribution = assignments[emp_id_str].get('monthly_contribution', 0)
                    else:
                        # Fallback: employee not in assignments, use 0
                        employer_contribution = 0
                    employee_cost = max(0, lcsp_premium - employer_contribution)

                # Store in contribution_analysis for Employer Summary
                contribution_analysis[employee_id] = {
                    'employee_name': f"{employee.get('first_name', '')} {employee.get('last_name', '')}",
                    'family_status': family_status,
                    'ichra_analysis': {
                        'plan_type': 'LCSP',
                        'plan_id': lcsp.get('plan_id', 'N/A'),
                        'plan_name': lcsp.get('plan_name', 'N/A'),
                        'metal_level': lcsp.get('metal_level', 'Silver'),
                        'monthly_premium': lcsp_premium,
                        'employer_contribution': employer_contribution,
                        'employee_cost': employee_cost
                    }
                }

            except Exception as e:
                errors.append(f"{employee_id}: {str(e)}")
                continue

        # Save to session state
        st.session_state.contribution_analysis = contribution_analysis

    # Show results (full-width, outside column context)
    st.markdown("---")

    if contribution_analysis:
        st.success(f"✅ Budget calculated for {len(contribution_analysis)} employees!")

        total_er = sum(a['ichra_analysis']['employer_contribution'] for a in contribution_analysis.values())
        total_ee = sum(a['ichra_analysis']['employee_cost'] for a in contribution_analysis.values())

        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Total ER Monthly", f"${total_er:,.2f}")
        col_b.metric("Total ER Annual", f"${total_er * 12:,.2f}")
        col_c.metric("Employees Analyzed", len(contribution_analysis))

        st.info("💡 Go to **3️⃣ Employer Summary** to compare this ICHRA budget against your current group plan costs")

    if errors:
        with st.expander(f"⚠️ {len(errors)} employees could not be calculated", expanded=False):
            for error in errors[:20]:  # Show first 20
                st.text(error)

# Show current budget status
if st.session_state.contribution_analysis:
    analyzed_count = len(st.session_state.contribution_analysis)
    total_employees = len(census_df)
    st.caption(f"✓ ICHRA budget calculated for {analyzed_count} of {total_employees} employees")

# Navigation hint to Individual Analysis page
st.info("💡 **Need to analyze individual employees?** Go to **5️⃣ Individual Analysis** in the sidebar to view LCSP, marketplace options, and affordability details for specific employees.")

st.markdown("---")

# =============================================================================
# AI CHAT INTERFACE
# =============================================================================

st.subheader("🤖 AI Evaluation Assistant")

if not ANTHROPIC_AVAILABLE:
    st.warning("AI features require the `anthropic` library. Install with: `pip install anthropic`")
elif not os.getenv('ANTHROPIC_API_KEY'):
    st.warning("Set ANTHROPIC_API_KEY environment variable to enable AI features.")
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
        if st.button("Clear Chat"):
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
