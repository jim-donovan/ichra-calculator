"""
Individual Employee Analysis Page
Analyze individual employees' marketplace options and ICHRA contributions.
"""

import streamlit as st
import pandas as pd
import logging

from database import get_database_connection
from constants import FAMILY_STATUS_CODES

# Configure logging
logger = logging.getLogger(__name__)

# Page config
st.set_page_config(page_title="Individual Analysis", page_icon="👤", layout="wide")

# =============================================================================
# STYLING
# =============================================================================

st.markdown("""
<style>
.plan-badge {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 0.5rem 1rem;
    border-radius: 8px;
    font-weight: 500;
    margin-bottom: 1rem;
    display: inline-block;
}
.plan-badge-label {
    opacity: 0.8;
    margin-right: 0.5rem;
}
</style>
""", unsafe_allow_html=True)

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
        employee_id = str(
            employee.get('employee_id') or
            employee.get('Employee Number') or
            employee.get('employee_number', '')
        )
        employee_assignments = settings.get('employee_assignments', {})

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

            if criteria.get('family_status') and criteria['family_status'] != family_status:
                continue

            if 'age_min' in criteria and 'age_max' in criteria:
                if not (criteria['age_min'] <= employee_age <= criteria['age_max']):
                    continue

            if criteria.get('state') and criteria['state'] != employee_state:
                continue

            return float(cls.get('monthly_contribution', 0))

        return 0.0

    elif contribution_type == 'flat':
        flat_amounts = settings.get('flat_amounts', {})
        return float(flat_amounts.get(family_status, flat_amounts.get('EE', 400)))

    else:
        return float(settings.get('default_percentage', 75))


def calculate_family_premium(employee: dict, plan_id: str, db) -> float:
    """Calculate total family premium for a plan"""
    family_status = str(employee.get('family_status', 'EE')).upper()
    rating_area_id = employee.get('rating_area_id')

    if not rating_area_id:
        return None

    total_premium = 0.0

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

    if family_status in ['ES', 'F']:
        spouse_age = employee.get('spouse_age')
        if spouse_age:
            spouse_band = get_age_band(int(spouse_age))
            result = db.execute_query(rate_query, (plan_id, int(rating_area_id), spouse_band))
            if not result.empty:
                total_premium += float(result.iloc[0]['individual_rate'])

    if family_status in ['EC', 'F']:
        child_ages = []
        for i in range(2, 7):
            child_age = employee.get(f'dep_{i}_age')
            if child_age and int(child_age) < 21:
                child_ages.append(int(child_age))

        child_ages.sort(reverse=True)
        for age in child_ages[:3]:
            child_band = get_age_band(age)
            result = db.execute_query(rate_query, (plan_id, int(rating_area_id), child_band))
            if not result.empty:
                total_premium += float(result.iloc[0]['individual_rate'])

    return total_premium


def compare_current_vs_marketplace(employee_id: str, include_family: bool = True) -> dict:
    """Compare current contribution to marketplace options"""
    employee = get_employee_by_id(employee_id)
    if not employee:
        return {"error": f"Employee '{employee_id}' not found in census"}

    current_ee = employee.get('current_ee_monthly', 0)
    current_er = employee.get('current_er_monthly', 0)

    def parse_currency(val):
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return 0
        if isinstance(val, (int, float)):
            return float(val)
        try:
            return float(str(val).replace('$', '').replace(',', '').strip())
        except (ValueError, TypeError):
            return 0

    current_ee = parse_currency(current_ee)
    current_er = parse_currency(current_er)
    current_total = current_ee + current_er

    has_current_data = current_total > 0

    rating_area_id = employee.get('rating_area_id')
    if not rating_area_id:
        return {"error": f"No rating area found for employee '{employee_id}'"}

    ee_age = employee.get('age', employee.get('ee_age', 30))
    age_band = get_age_band(int(ee_age))
    state = employee.get('state', employee.get('home_state', ''))
    family_status = str(employee.get('family_status', 'EE')).upper()

    try:
        db = st.session_state.db

        query = """
            SELECT DISTINCT
                p.hios_plan_id as plan_id,
                p.plan_marketing_name as plan_name,
                p.level_of_coverage as metal_level,
                p.plan_type,
                r.individual_rate as monthly_premium,
                CASE
                    WHEN v.csr_variation_type = 'Exchange variant (no CSR)' THEN 'On-Exchange'
                    ELSE 'Off-Exchange'
                END as exchange_status
            FROM rbis_insurance_plan_20251019202724 p
            JOIN rbis_insurance_plan_variant_20251019202724 v
                ON p.hios_plan_id = v.hios_plan_id
            JOIN rbis_insurance_plan_base_rates_20251019202724 r
                ON p.hios_plan_id = r.plan_id
            WHERE p.market_coverage = 'Individual'
              AND v.csr_variation_type IN ('Exchange variant (no CSR)', 'Non-Exchange variant')
              AND SUBSTRING(p.hios_plan_id FROM 6 FOR 2) = %s
              AND REPLACE(r.rating_area_id, 'Rating Area ', '')::integer = %s
              AND r.age = %s
              AND r.tobacco IN ('No Preference', 'Tobacco User/Non-Tobacco User')
              AND r.rate_effective_date = '2026-01-01'
            ORDER BY r.individual_rate ASC
            LIMIT 10
        """

        df = db.execute_query(query, (state.upper(), int(rating_area_id), age_band))

        if df.empty:
            return {"error": f"No marketplace plans found for this location"}

        settings = st.session_state.contribution_settings
        contribution = get_employer_contribution(employee)

        comparisons = []
        for _, row in df.iterrows():
            ee_premium = float(row['monthly_premium'])

            if include_family and family_status in ['ES', 'EC', 'F']:
                family_premium = calculate_family_premium(employee, row['plan_id'], db)
                premium = family_premium if family_premium else ee_premium
            else:
                premium = ee_premium

            if settings.get('contribution_type') == 'flat' or settings.get('contribution_type') == 'class_based':
                employer_pays = min(contribution, premium)
                employee_pays = max(0, premium - contribution)
            else:
                employer_pays = premium * (contribution / 100)
                employee_pays = premium - employer_pays

            monthly_diff = employee_pays - current_ee
            annual_diff = monthly_diff * 12

            comparisons.append({
                "plan_id": row['plan_id'],
                "plan_name": row['plan_name'],
                "metal_level": row['metal_level'],
                "plan_type": row['plan_type'],
                "marketplace_total_premium": f"${premium:,.2f}",
                "marketplace_employer_pays": f"${employer_pays:,.2f}",
                "marketplace_employee_pays": f"${employee_pays:,.2f}",
                "current_employee_pays": f"${current_ee:,.2f}",
                "monthly_difference": f"${monthly_diff:+,.2f}",
                "annual_difference": f"${annual_diff:+,.2f}",
                "saves_money": monthly_diff < 0,
                "_premium_num": premium,
                "_employee_cost_num": employee_pays
            })

        return {
            "employee_id": employee_id,
            "employee_name": f"{employee.get('first_name', '')} {employee.get('last_name', '')}".strip(),
            "family_status": family_status,
            "current_contribution": {
                "employee_pays": f"${current_ee:,.2f}",
                "employer_pays": f"${current_er:,.2f}",
                "total": f"${current_total:,.2f}"
            },
            "has_current_data": has_current_data,
            "comparisons": comparisons
        }

    except Exception as e:
        logger.error(f"Error comparing plans: {e}")
        return {"error": str(e)}


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

    if coverage_type is None:
        coverage_type = 'family' if family_status in ['ES', 'EC', 'F'] else 'self_only'

    try:
        db = st.session_state.db

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

        if coverage_type == 'family' and family_status in ['ES', 'EC', 'F']:
            family_premium = calculate_family_premium(employee, plan_id, db)
            if family_premium:
                lcsp_premium = family_premium

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
              AND moop_ded_type LIKE '%%Out of Pocket%%'
              AND individual_ded_moop_amount != 'Not Applicable'
              AND network_type = 'In Network'
            LIMIT 1
        """
        moop_result = db.execute_query(moop_query, (plan_id,))
        oopm = moop_result.iloc[0]['individual_ded_moop_amount'] if not moop_result.empty else None

        return {
            "employee_id": employee_id,
            "coverage_type": coverage_type,
            "lcsp": {
                "plan_id": plan_id,
                "plan_name": lcsp['plan_name'],
                "metal_level": lcsp['metal_level'],
                "plan_type": lcsp['plan_type'],
                "monthly_premium": f"${lcsp_premium:,.2f}",
                "deductible": deductible,
                "oopm": oopm
            }
        }

    except Exception as e:
        logger.error(f"Error getting LCSP: {e}")
        return {"error": str(e)}


def get_equivalent_plan(employee_id: str, target_premium: float = None) -> dict:
    """Get marketplace plan closest to current contribution"""
    employee = get_employee_by_id(employee_id)
    if not employee:
        return {"error": f"Employee '{employee_id}' not found in census"}

    if target_premium is None:
        current_total = 0
        current_ee = employee.get('current_ee_monthly', 0)
        current_er = employee.get('current_er_monthly', 0)

        def parse_currency(val):
            if val is None or (isinstance(val, float) and pd.isna(val)):
                return 0
            if isinstance(val, (int, float)):
                return float(val)
            try:
                return float(str(val).replace('$', '').replace(',', '').strip())
            except (ValueError, TypeError):
                return 0

        current_total = parse_currency(current_ee) + parse_currency(current_er)

        if current_total <= 0:
            return {"error": "No current contribution data to match against"}

        target_premium = current_total

    rating_area_id = employee.get('rating_area_id')
    if not rating_area_id:
        return {"error": f"No rating area found for employee '{employee_id}'"}

    ee_age = employee.get('age', employee.get('ee_age', 30))
    age_band = get_age_band(int(ee_age))
    state = employee.get('state', employee.get('home_state', ''))
    family_status = str(employee.get('family_status', 'EE')).upper()

    try:
        db = st.session_state.db

        query = """
            SELECT DISTINCT
                p.hios_plan_id as plan_id,
                p.plan_marketing_name as plan_name,
                p.level_of_coverage as metal_level,
                p.plan_type,
                r.individual_rate as monthly_premium,
                CASE
                    WHEN v.csr_variation_type = 'Exchange variant (no CSR)' THEN 'On-Exchange'
                    ELSE 'Off-Exchange'
                END as exchange_status,
                ABS(r.individual_rate - %s) as rate_diff
            FROM rbis_insurance_plan_20251019202724 p
            JOIN rbis_insurance_plan_variant_20251019202724 v
                ON p.hios_plan_id = v.hios_plan_id
            JOIN rbis_insurance_plan_base_rates_20251019202724 r
                ON p.hios_plan_id = r.plan_id
            WHERE p.market_coverage = 'Individual'
              AND v.csr_variation_type IN ('Exchange variant (no CSR)', 'Non-Exchange variant')
              AND SUBSTRING(p.hios_plan_id FROM 6 FOR 2) = %s
              AND REPLACE(r.rating_area_id, 'Rating Area ', '')::integer = %s
              AND r.age = %s
              AND r.tobacco IN ('No Preference', 'Tobacco User/Non-Tobacco User')
              AND r.rate_effective_date = '2026-01-01'
            ORDER BY rate_diff ASC
            LIMIT 1
        """

        df = db.execute_query(query, (target_premium, state.upper(), int(rating_area_id), age_band))

        if df.empty:
            return {"error": "No matching plans found"}

        plan = df.iloc[0]
        ee_premium = float(plan['monthly_premium'])

        if family_status in ['ES', 'EC', 'F']:
            family_premium = calculate_family_premium(employee, plan['plan_id'], db)
            premium = family_premium if family_premium else ee_premium
        else:
            premium = ee_premium

        difference = premium - target_premium

        deductible_query = """
            SELECT individual_ded_moop_amount
            FROM rbis_insurance_plan_variant_ddctbl_moop_20251019202724
            WHERE plan_id = %s
              AND moop_ded_type LIKE '%%Deductible%%'
              AND individual_ded_moop_amount != 'Not Applicable'
              AND network_type = 'In Network'
            LIMIT 1
        """
        ded_result = db.execute_query(deductible_query, (plan['plan_id'],))
        deductible = ded_result.iloc[0]['individual_ded_moop_amount'] if not ded_result.empty else 'N/A'

        moop_query = """
            SELECT individual_ded_moop_amount
            FROM rbis_insurance_plan_variant_ddctbl_moop_20251019202724
            WHERE plan_id = %s
              AND moop_ded_type LIKE '%%Out of Pocket%%'
              AND individual_ded_moop_amount != 'Not Applicable'
              AND network_type = 'In Network'
            LIMIT 1
        """
        moop_result = db.execute_query(moop_query, (plan['plan_id'],))
        oopm = moop_result.iloc[0]['individual_ded_moop_amount'] if not moop_result.empty else 'N/A'

        return {
            "plan_id": plan['plan_id'],
            "plan_name": plan['plan_name'],
            "metal_level": plan['metal_level'],
            "plan_type": plan['plan_type'],
            "exchange_status": plan['exchange_status'],
            "monthly_premium": f"${premium:,.2f}",
            "target_premium": f"${target_premium:,.2f}",
            "difference": f"${difference:+,.2f}",
            "deductible": deductible,
            "oopm": oopm
        }

    except Exception as e:
        logger.error(f"Error finding equivalent plan: {e}")
        return {"error": str(e)}


# =============================================================================
# PAGE CONTENT
# =============================================================================

st.title("👤 Individual Employee Analysis")

# Check for census
if 'census_df' not in st.session_state or st.session_state.census_df is None:
    st.warning("Please upload employee census data first.")
    st.markdown("Go to **1️⃣ Employee Census** to upload your census file.")
    st.stop()

census_df = st.session_state.census_df
num_employees = len(census_df)

st.success(f"✓ {num_employees} employees loaded from census")

# Initialize contribution settings if needed
if 'contribution_settings' not in st.session_state:
    st.session_state.contribution_settings = {
        'default_percentage': 75,
        'by_class': {},
        'contribution_type': 'percentage',
        'flat_amounts': {'EE': 400, 'ES': 600, 'EC': 600, 'F': 800}
    }

# Get employee list for selector
id_col = None
for col in ['Employee Number', 'employee_number', 'EmployeeNumber', 'employee_id']:
    if col in census_df.columns:
        id_col = col
        break

if id_col is None:
    st.error("Census must have an 'Employee Number' column")
    st.stop()

# Create display labels
employee_options = []
for _, row in census_df.iterrows():
    emp_id = str(row[id_col])
    name = f"{row.get('first_name', '')} {row.get('last_name', '')}".strip()
    status = row.get('family_status', 'EE')
    employee_options.append(f"{emp_id} - {name} ({status})")

col1, col2 = st.columns([2, 1])

with col1:
    selected = st.selectbox(
        "Select Employee to Analyze",
        options=employee_options,
        index=0
    )

    selected_id = selected.split(" - ")[0] if selected else None
    st.session_state.selected_employee_id = selected_id

with col2:
    if st.button("🔍 Analyze Employee", type="primary"):
        if selected_id:
            with st.spinner("Analyzing..."):
                result = compare_current_vs_marketplace(selected_id)
                employee = get_employee_by_id(selected_id)

                if "error" in result:
                    st.error(result["error"])
                else:
                    st.session_state['_quick_analysis_result'] = result
                    st.session_state['_quick_analysis_employee'] = employee

                    lcsp_result = get_lcsp(selected_id)
                    st.session_state['_quick_analysis_lcsp'] = lcsp_result

                    equiv_result = get_equivalent_plan(selected_id)
                    st.session_state['_quick_analysis_equiv'] = equiv_result

# Display Analysis Results
if '_quick_analysis_result' in st.session_state and st.session_state['_quick_analysis_result']:
    result = st.session_state['_quick_analysis_result']
    employee = st.session_state.get('_quick_analysis_employee', {})
    settings = st.session_state.contribution_settings

    family_status = result.get('family_status', 'EE')
    status_label = FAMILY_STATUS_CODES.get(family_status, family_status)
    age = employee.get('age', employee.get('ee_age', 'N/A'))
    state = employee.get('state', 'N/A')
    city = employee.get('city', 'N/A')
    county = employee.get('county', 'N/A')
    rating_area = employee.get('rating_area_id', 'N/A')
    zip_code = employee.get('zip_code', 'N/A')

    st.markdown("---")
    st.subheader(f"📊 {result['employee_name']}")
    st.caption(f"Employee ID: `{result['employee_id']}` · Family Status: **{family_status}** ({status_label})")

    # Employee Details
    with st.expander("👤 Employee Details", expanded=True):
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        col1.metric("Age", age)
        col2.metric("State", state)
        col3.metric("City", city if city != 'N/A' else "—")
        col4.metric("County", county if county != 'N/A' else "—")
        col5.metric("ZIP", zip_code if zip_code != 'N/A' else "—")
        col6.metric("Rating Area", rating_area)

    # Affordability Status
    if 'affordability_analysis' in st.session_state and st.session_state.affordability_analysis:
        st.markdown("#### IRS Affordability Status")

        emp_details = st.session_state.affordability_analysis['employee_details']
        selected_employee_id = result.get('employee_id')
        emp_afford = next((e for e in emp_details if e['employee_id'] == selected_employee_id), None)

        if emp_afford and emp_afford.get('has_income_data'):
            if emp_afford['is_affordable_at_current']:
                st.success(f"""
                ✅ **AFFORDABLE** - Current ER contribution meets IRS requirements

                - Employee income: ${emp_afford['monthly_income']:,.0f}/mo
                - Max employee should pay: ${emp_afford['max_ee_contribution']:.0f}/mo (9.96% of income)
                - LCSP premium: ${emp_afford['lcsp_premium']:.0f}/mo
                - **Current ER contribution: ${emp_afford['current_er_contribution']:.0f}/mo** ✓
                - Minimum needed: ${emp_afford['min_er_contribution']:.0f}/mo
                """)
            else:
                st.warning(f"""
                ⚠️ **NOT AFFORDABLE** - Needs increase to meet IRS 9.96% threshold

                - Employee income: ${emp_afford['monthly_income']:,.0f}/mo
                - Max employee should pay: ${emp_afford['max_ee_contribution']:.0f}/mo (9.96% of income)
                - LCSP premium: ${emp_afford['lcsp_premium']:.0f}/mo
                - Current ER contribution: ${emp_afford['current_er_contribution']:.0f}/mo ❌
                - **Minimum needed: ${emp_afford['min_er_contribution']:.0f}/mo**
                - **Gap: ${emp_afford['gap']:.0f}/mo** (increase needed)
                """)
        elif emp_afford:
            st.info("ℹ️ No income data available for affordability calculation. Add 'Monthly Income' to census for this employee.")

    # Current Group Plan
    with st.expander("💵 Current Group Plan", expanded=True):
        if result['has_current_data']:
            curr = result['current_contribution']
            col1, col2, col3 = st.columns(3)
            col1.metric("Premium", curr['total'])
            col2.metric("Employer pays", curr['employer_pays'])
            col3.metric("Employee pays", curr['employee_pays'])
        else:
            st.warning("No current contribution data in census for this employee")

    # ICHRA/LCSP Section
    with st.expander("💰 ICHRA Contribution (LCSP)", expanded=True):
        lcsp_data = st.session_state.get('_quick_analysis_lcsp', {})
        if lcsp_data and 'lcsp' in lcsp_data:
            lcsp = lcsp_data['lcsp']
            lcsp_premium_str = lcsp.get('monthly_premium', '$0.00')
            lcsp_premium = float(lcsp_premium_str.replace('$', '').replace(',', ''))

            st.markdown("**Lowest Cost Silver Plan (LCSP)**")

            plan_name = lcsp.get('plan_name', 'N/A')
            st.markdown(f'<div class="plan-badge"><span class="plan-badge-label">Plan:</span>{plan_name}</div>', unsafe_allow_html=True)

            col1, col2, col3 = st.columns(3)

            contrib_type = settings.get('contribution_type')
            if contrib_type == 'flat':
                flat_amt = settings['flat_amounts'].get(family_status, 400)
                lcsp_er_pays = min(flat_amt, lcsp_premium)
                lcsp_ee_pays = max(0, lcsp_premium - flat_amt)
            elif contrib_type == 'class_based':
                contribution = get_employer_contribution(employee)
                lcsp_er_pays = min(contribution, lcsp_premium)
                lcsp_ee_pays = max(0, lcsp_premium - contribution)
            else:
                pct = settings.get('default_percentage', 75)
                lcsp_er_pays = lcsp_premium * (pct / 100)
                lcsp_ee_pays = lcsp_premium - lcsp_er_pays

            col1.metric("Premium", f"{lcsp_premium_str}/mo")
            col2.metric("Employer pays", f"${lcsp_er_pays:,.2f}/mo")
            col3.metric("Employee pays", f"${lcsp_ee_pays:,.2f}/mo")

            st.caption(f"Plan ID: `{lcsp.get('plan_id', 'N/A')}`")
            st.caption(f"{lcsp.get('metal_level', 'N/A')} | {lcsp.get('plan_type', 'N/A')} | Deductible: {lcsp.get('deductible', 'N/A')} | OOPM: {lcsp.get('oopm', 'N/A')}")

            if contrib_type == 'class_based':
                st.caption(f"Contribution: Class-Based - ${contribution:,.0f}/mo")
            elif contrib_type == 'flat':
                st.caption(f"Contribution: Flat Amount - ${flat_amt:,.0f}/mo ({family_status})")
            else:
                pct = settings.get('default_percentage', 75)
                st.caption(f"Contribution: {pct}% Employer / {100-pct}% Employee")

    # Equivalent Plan
    equiv_data = st.session_state.get('_quick_analysis_equiv', {})
    if equiv_data and 'plan_id' in equiv_data:
        with st.expander("🎯 Equivalent Plan (Closest to Current Premium)", expanded=True):
            equiv_plan_name = equiv_data.get('plan_name', 'N/A')
            st.markdown(f'<div class="plan-badge"><span class="plan-badge-label">Plan:</span>{equiv_plan_name}</div>', unsafe_allow_html=True)

            equiv_premium_str = equiv_data.get('monthly_premium', '$0.00')
            equiv_premium = float(equiv_premium_str.replace('$', '').replace(',', ''))

            if settings.get('contribution_type') == 'flat':
                flat_amt = settings['flat_amounts'].get(family_status, 400)
                equiv_er_pays = min(flat_amt, equiv_premium)
                equiv_ee_pays = max(0, equiv_premium - flat_amt)
            elif settings.get('contribution_type') == 'class_based':
                contribution = get_employer_contribution(employee)
                equiv_er_pays = min(contribution, equiv_premium)
                equiv_ee_pays = max(0, equiv_premium - contribution)
            else:
                pct = settings.get('default_percentage', 75)
                equiv_er_pays = equiv_premium * (pct / 100)
                equiv_ee_pays = equiv_premium - equiv_er_pays

            col1, col2, col3 = st.columns(3)
            col1.metric("Premium", equiv_premium_str)
            col2.metric("Employer pays", f"${equiv_er_pays:,.2f}/mo")
            col3.metric("Employee pays", f"${equiv_ee_pays:,.2f}/mo")

            st.caption(f"Plan ID: `{equiv_data.get('plan_id', 'N/A')}`")
            st.caption(f"{equiv_data.get('metal_level', 'N/A')} | {equiv_data.get('plan_type', 'N/A')} | {equiv_data.get('exchange_status', 'N/A')} | Deductible: {equiv_data.get('deductible', 'N/A')} | OOPM: {equiv_data.get('oopm', 'N/A')}")
            st.caption(f"Price difference from current: {equiv_data.get('difference', 'N/A')}")
    elif equiv_data and 'error' in equiv_data:
        with st.expander("🎯 Equivalent Plan", expanded=False):
            st.info(equiv_data['error'])

    # Marketplace Plans
    with st.expander("🏥 Marketplace Plan Options", expanded=True):
        plan_data = []
        for comp in result['comparisons'][:5]:
            plan_data.append({
                "Plan": comp['plan_name'],
                "ID": comp.get('plan_id', 'N/A'),
                "Metal": comp['metal_level'],
                "Type": comp.get('plan_type', 'N/A'),
                "Premium": comp['marketplace_total_premium'],
                "You Pay": comp['marketplace_employee_pays'],
                "Δ Monthly": comp['monthly_difference'],
                "Δ Annual": comp['annual_difference'],
            })

        if plan_data:
            df = pd.DataFrame(plan_data)
            st.dataframe(
                df,
                width='stretch',
                hide_index=True,
                column_config={
                    "Plan": st.column_config.TextColumn("Plan Name", width="large"),
                    "ID": st.column_config.TextColumn("Plan ID", width="medium"),
                    "Metal": st.column_config.TextColumn("Metal", width="small"),
                    "Type": st.column_config.TextColumn("Type", width="small"),
                    "Premium": st.column_config.TextColumn("Premium", width="small"),
                    "You Pay": st.column_config.TextColumn("You Pay", width="small"),
                    "Δ Monthly": st.column_config.TextColumn("Monthly Δ", width="small"),
                    "Δ Annual": st.column_config.TextColumn("Annual Δ", width="small"),
                }
            )

            savings_plans = [c for c in result['comparisons'] if c['saves_money']]
            if savings_plans:
                best = savings_plans[0]
                st.success(f"✅ **Best option:** {best['plan_name']} — Employee saves **{best['monthly_difference']}**/mo ({best['annual_difference']}/yr)")
            else:
                st.warning("⚠️ All marketplace options cost more than current contribution")
        else:
            st.info("No marketplace plans found for this employee's location")

    # Clear button
    if st.button("Clear Analysis", key="clear_analysis"):
        st.session_state.pop('_quick_analysis_result', None)
        st.session_state.pop('_quick_analysis_employee', None)
        st.session_state.pop('_quick_analysis_lcsp', None)
        st.session_state.pop('_quick_analysis_equiv', None)
        st.rerun()
