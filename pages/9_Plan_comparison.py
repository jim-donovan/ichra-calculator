"""
Plan Comparison Tool (Page 9)
Compare current employer group plan benefits against marketplace alternatives.
Three-stage workflow:
1. Input current employer plan details
2. Filter and select marketplace plans
3. View side-by-side benefit comparison
"""

import streamlit as st
import pandas as pd
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import get_database_connection, DatabaseConnection
from plan_comparison_types import (
    CurrentEmployerPlan,
    MarketplacePlanDetails,
    ComparisonLocation,
    ComparisonFilters,
    calculate_match_score,
    compare_benefit,
    is_plan_better,
    calculate_enhanced_ranking_score,
)
from queries import PlanComparisonQueries, PlanQueries
from pptx_plan_comparison import (
    PlanComparisonSlideData,
    PlanColumnData,
    generate_plan_comparison_slide,
)
from sbc_parser import parse_sbc_markdown
from constants import (
    PLAN_TYPES,
    METAL_LEVELS,
    COMPARISON_BENEFIT_ROWS,
    COMPARISON_INDICATORS,
    MAX_COMPARISON_PLANS,
    TARGET_STATES,
)

# Comparison thresholds for premium rows (absolute $ difference)
# These determine when a marketplace plan is "better", "similar", or "worse"
AGE_21_PREMIUM_THRESHOLD = 10  # $10 difference threshold for Age 21 Premium
TOTAL_PREMIUM_THRESHOLD = 50   # $50 difference threshold for Total Premium

# Page configuration
st.set_page_config(
    page_title="Plan Comparison | ICHRA Calculator",
    page_icon="📊",
    layout="wide"
)

# Custom CSS to match dashboard styling
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&family=Inter:wght@400;700&display=swap');

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

    .stage-header {
        background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
        border-radius: 10px;
        padding: 20px 24px;
        border-left: 4px solid #0047AB;
        margin-bottom: 24px;
    }

    .stage-title {
        font-size: 18px;
        font-weight: 700;
        color: #101828;
        margin-bottom: 4px;
    }

    .stage-description {
        font-size: 14px;
        color: #667085;
        margin-bottom: 16px;
    }

    .section-header {
        font-size: 16px;
        font-weight: 600;
        color: #344054;
        margin-top: 16px;
        margin-bottom: 12px;
        padding-bottom: 8px;
        border-bottom: 1px solid #e5e7eb;
    }

    .info-box {
        background: #eff6ff;
        border: 1px solid #93c5fd;
        border-radius: 8px;
        padding: 12px;
        margin-bottom: 16px;
    }

    .info-text {
        color: #1e40af;
        font-size: 14px;
    }

    .success-box {
        background: #dcfce7;
        border: 1px solid #86efac;
        border-radius: 8px;
        padding: 12px;
    }

    .success-text {
        color: #166534;
        font-size: 14px;
        font-weight: 500;
    }

    /* Comparison indicators */
    .indicator-better { color: #16a34a; }
    .indicator-similar { color: #ca8a04; }
    .indicator-worse { color: #dc2626; }

    /* Match score badge */
    .match-score {
        background: #f0fdf4;
        border: 1px solid #86efac;
        border-radius: 6px;
        padding: 4px 12px;
        font-weight: 600;
        color: #166534;
    }

    .match-score-low {
        background: #fef2f2;
        border: 1px solid #fecaca;
        color: #991b1b;
    }

    .match-score-medium {
        background: #E8F1FD;
        border: 1px solid #B3D4FC;
        color: #003d91;
    }
</style>
""", unsafe_allow_html=True)


# ==============================================================================
# SESSION STATE INITIALIZATION
# ==============================================================================

def get_ee_premiums_from_census() -> tuple:
    """
    Extract EE-only current and renewal premiums from census data.
    Returns (current_premium, renewal_premium) or (None, None) if not available.
    """
    census_df = st.session_state.get('census_df')
    if census_df is None or census_df.empty:
        return None, None

    # Normalize column names for lookup
    cols = {c.lower().replace(' ', '_'): c for c in census_df.columns}

    # Get family status column
    family_col = cols.get('family_status') or cols.get('family status')
    if not family_col:
        return None, None

    # Filter for EE-only employees
    ee_employees = census_df[census_df[family_col].str.upper() == 'EE']
    if ee_employees.empty:
        return None, None

    current_premium = None
    renewal_premium = None

    # Try to get 2025_Premium (current total) - find the column
    premium_2025_col = cols.get('2025_premium') or cols.get('current_total_premium')
    if premium_2025_col and premium_2025_col in ee_employees.columns:
        vals = ee_employees[premium_2025_col].dropna()
        if len(vals) > 0:
            try:
                current_premium = float(vals.mode().iloc[0])
            except (IndexError, ValueError):
                current_premium = float(vals.iloc[0])

    # Fallback: sum of Current EE Monthly + Current ER Monthly
    if current_premium is None:
        ee_col = cols.get('current_ee_monthly') or cols.get('current ee monthly')
        er_col = cols.get('current_er_monthly') or cols.get('current er monthly')
        if ee_col and er_col and ee_col in ee_employees.columns and er_col in ee_employees.columns:
            ee_vals = ee_employees[ee_col].fillna(0).infer_objects(copy=False)
            er_vals = ee_employees[er_col].fillna(0).infer_objects(copy=False)
            total_vals = ee_vals + er_vals
            non_zero = total_vals[total_vals > 0]
            if len(non_zero) > 0:
                try:
                    current_premium = float(non_zero.mode().iloc[0])
                except (IndexError, ValueError):
                    current_premium = float(non_zero.iloc[0])

    # Try to get 2026_Premium (renewal total)
    premium_2026_col = cols.get('2026_premium') or cols.get('renewal_premium') or cols.get('projected_2026_premium')
    if premium_2026_col and premium_2026_col in ee_employees.columns:
        vals = ee_employees[premium_2026_col].dropna()
        if len(vals) > 0:
            try:
                renewal_premium = float(vals.mode().iloc[0])
            except (IndexError, ValueError):
                renewal_premium = float(vals.iloc[0])

    return current_premium, renewal_premium


def init_session_state():
    """Initialize session state for plan comparison."""
    if 'current_employer_plan' not in st.session_state:
        # Pre-populate EE-only premiums from census if available
        current_premium, renewal_premium = get_ee_premiums_from_census()
        st.session_state.current_employer_plan = CurrentEmployerPlan(
            current_premium=current_premium,
            renewal_premium=renewal_premium,
        )
    else:
        # If plan exists but has no premiums, try to get them from census
        # (handles case where page 9 was visited before census was loaded)
        plan = st.session_state.current_employer_plan
        if plan.current_premium is None or plan.renewal_premium is None:
            census_current, census_renewal = get_ee_premiums_from_census()
            if census_current or census_renewal:
                # Update the plan with census premiums (only if missing)
                st.session_state.current_employer_plan = CurrentEmployerPlan(
                    plan_name=plan.plan_name,
                    carrier=plan.carrier,
                    plan_type=plan.plan_type,
                    metal_tier=plan.metal_tier,
                    hsa_eligible=plan.hsa_eligible,
                    current_premium=plan.current_premium or census_current,
                    renewal_premium=plan.renewal_premium or census_renewal,
                    individual_deductible=plan.individual_deductible,
                    family_deductible=plan.family_deductible,
                    individual_oop_max=plan.individual_oop_max,
                    family_oop_max=plan.family_oop_max,
                    coinsurance_pct=plan.coinsurance_pct,
                    pcp_copay=plan.pcp_copay,
                    specialist_copay=plan.specialist_copay,
                    er_copay=plan.er_copay,
                    generic_rx_copay=plan.generic_rx_copay,
                    preferred_rx_copay=plan.preferred_rx_copay,
                    specialty_rx_copay=plan.specialty_rx_copay,
                    pcp_coinsurance=plan.pcp_coinsurance,
                    specialist_coinsurance=plan.specialist_coinsurance,
                    er_coinsurance=plan.er_coinsurance,
                    generic_rx_coinsurance=plan.generic_rx_coinsurance,
                    preferred_rx_coinsurance=plan.preferred_rx_coinsurance,
                    specialty_rx_coinsurance=plan.specialty_rx_coinsurance,
                    pcp_after_deductible=plan.pcp_after_deductible,
                    specialist_after_deductible=plan.specialist_after_deductible,
                    er_after_deductible=plan.er_after_deductible,
                    generic_rx_after_deductible=plan.generic_rx_after_deductible,
                    preferred_rx_after_deductible=plan.preferred_rx_after_deductible,
                    specialty_rx_after_deductible=plan.specialty_rx_after_deductible,
                )
                # Clear premium widget keys so they refresh with new values
                for key in ['current_premium_input', 'renewal_premium_input']:
                    if key in st.session_state:
                        del st.session_state[key]

    if 'comparison_location' not in st.session_state:
        # Try to prefill with most common ZIP from census
        default_location = ComparisonLocation()
        census_df = st.session_state.get('census_df')
        if census_df is not None and not census_df.empty:
            # Find the most populated ZIP code (census stores as 'zip_code')
            zip_col = 'zip_code' if 'zip_code' in census_df.columns else 'Home Zip' if 'Home Zip' in census_df.columns else None
            if zip_col and zip_col in census_df.columns:
                zip_counts = census_df[zip_col].value_counts()
                if not zip_counts.empty:
                    most_common_zip = str(zip_counts.index[0]).zfill(5)[:5]  # Ensure 5 digits
                    default_location = ComparisonLocation(zip_code=most_common_zip)
        st.session_state.comparison_location = default_location

    if 'comparison_filters' not in st.session_state:
        st.session_state.comparison_filters = ComparisonFilters()

    if 'selected_comparison_plans' not in st.session_state:
        st.session_state.selected_comparison_plans = []

    if 'comparison_stage' not in st.session_state:
        st.session_state.comparison_stage = 1

    # Comparison mode: "Compare to Current" or "Marketplace Only"
    if 'comparison_mode' not in st.session_state:
        st.session_state.comparison_mode = "Compare to Current"

    if 'parsed_sbc_data' not in st.session_state:
        st.session_state.parsed_sbc_data = None

    # Form refresh counter - incrementing this forces widget recreation
    if 'form_refresh_counter' not in st.session_state:
        st.session_state.form_refresh_counter = 0


# ==============================================================================
# STAGE 1: CURRENT EMPLOYER PLAN INPUT
# ==============================================================================

def render_stage_1_current_plan():
    """Render the current employer plan input form."""
    st.markdown('''
    <div class="stage-header">
        <p class="stage-title">Stage 1: Current Employer Plan</p>
        <p class="stage-description">Enter your current group health plan details for comparison.</p>
    </div>
    ''', unsafe_allow_html=True)

    # Quick Import from SBC
    with st.expander("Quick Import from SBC (Optional)", expanded=False):
        st.caption("Upload a pre-processed SBC markdown file to auto-fill plan details.")
        uploaded_sbc = st.file_uploader(
            "Upload SBC Markdown",
            type=['md', 'txt'],
            help="Upload a transformed SBC file from your SBC processing tool",
            key="sbc_uploader"
        )

        if uploaded_sbc is not None:
            try:
                # Read file content and seek back to beginning for potential re-reads
                content = uploaded_sbc.read().decode('utf-8')
                uploaded_sbc.seek(0)  # Reset file pointer for subsequent reads

                # Skip parsing if content is empty (can happen after rerun)
                if not content.strip():
                    st.info("File appears empty. Please re-upload the SBC file.")
                else:
                    # Cache parsing result to avoid re-parsing on every widget change
                    # Use file name + size as cache key to detect new uploads
                    cache_key = f"{uploaded_sbc.name}_{uploaded_sbc.size}"

                    if 'sbc_parse_cache_key' not in st.session_state or st.session_state.sbc_parse_cache_key != cache_key:
                        # New file or first parse - call AI
                        parsed = parse_sbc_markdown(content)
                        # Cache both the result and the key
                        st.session_state.pending_sbc_data = parsed
                        st.session_state.sbc_parse_cache_key = cache_key
                    else:
                        # Already parsed this file - use cached result
                        parsed = st.session_state.pending_sbc_data

                    if parsed.get("plan_name"):
                        st.success(f"Extracted: **{parsed['plan_name']}**")

                        # Show preview of extracted values
                        preview_cols = st.columns(3)
                        with preview_cols[0]:
                            st.metric("Deductible (Individual)", f"${parsed.get('individual_deductible', 0):,.0f}" if parsed.get('individual_deductible') else "—")
                        with preview_cols[1]:
                            st.metric("OOP Max (Individual)", f"${parsed.get('individual_oop_max', 0):,.0f}" if parsed.get('individual_oop_max') else "—")
                        with preview_cols[2]:
                            st.metric("Coinsurance", f"{parsed.get('coinsurance_pct', 0)}%" if parsed.get('coinsurance_pct') else "—")

                        if st.button("Apply to Form", type="primary"):
                            # Store parsed data and create updated plan
                            # PRESERVE existing premium values (from census or user input)
                            existing_plan = st.session_state.current_employer_plan

                            # Try to get premium values: first from existing plan, then from census
                            current_prem = existing_plan.current_premium
                            renewal_prem = existing_plan.renewal_premium
                            if not current_prem or not renewal_prem:
                                # Try to fetch from census if not already set
                                census_current, census_renewal = get_ee_premiums_from_census()
                                if not current_prem and census_current:
                                    current_prem = census_current
                                if not renewal_prem and census_renewal:
                                    renewal_prem = census_renewal

                            # Create the updated plan object
                            new_plan = CurrentEmployerPlan(
                                plan_name=parsed.get("plan_name", ""),
                                carrier=parsed.get("carrier"),
                                plan_type=parsed.get("plan_type", "HMO"),
                                metal_tier=parsed.get("metal_tier"),
                                hsa_eligible=parsed.get("hsa_eligible", False),
                                # Preserve premium values (from existing plan or census)
                                current_premium=current_prem,
                                renewal_premium=renewal_prem,
                                individual_deductible=parsed.get("individual_deductible", 0) or 0,
                                family_deductible=parsed.get("family_deductible"),
                                individual_oop_max=parsed.get("individual_oop_max", 0) or 0,
                                family_oop_max=parsed.get("family_oop_max"),
                                coinsurance_pct=parsed.get("coinsurance_pct", 20) or 20,
                                pcp_copay=parsed.get("pcp_copay"),
                                specialist_copay=parsed.get("specialist_copay"),
                                er_copay=parsed.get("er_copay"),
                                generic_rx_copay=parsed.get("generic_rx_copay"),
                                preferred_rx_copay=parsed.get("preferred_rx_copay"),
                                specialty_rx_copay=parsed.get("specialty_rx_copay"),
                            )
                            st.session_state.parsed_sbc_data = parsed
                            st.session_state.current_employer_plan = new_plan

                            # DIRECTLY SET widget values in session state
                            # This ensures widgets display the correct values on rerun
                            st.session_state['plan_name_input'] = new_plan.plan_name
                            st.session_state['carrier_input'] = new_plan.carrier or ""
                            st.session_state['hsa_eligible_checkbox'] = new_plan.hsa_eligible
                            st.session_state['current_premium_input'] = int(new_plan.current_premium or 0)
                            st.session_state['renewal_premium_input'] = int(new_plan.renewal_premium or 0)
                            st.session_state['individual_deductible_input'] = int(new_plan.individual_deductible)
                            st.session_state['family_deductible_input'] = int(new_plan.family_deductible or 0)
                            st.session_state['individual_oop_max_input'] = int(new_plan.individual_oop_max)
                            st.session_state['family_oop_max_input'] = int(new_plan.family_oop_max or 0)
                            st.session_state['coinsurance_slider'] = int(new_plan.coinsurance_pct)

                            # Set plan type selectbox index
                            plan_type_val = new_plan.plan_type or "HMO"
                            if plan_type_val in PLAN_TYPES:
                                st.session_state['plan_type_select'] = plan_type_val

                            # Set metal tier selectbox
                            metal_options = ["N/A", "Bronze", "Silver", "Gold", "Platinum"]
                            if new_plan.metal_tier in metal_options:
                                st.session_state['metal_tier_select'] = new_plan.metal_tier
                            else:
                                st.session_state['metal_tier_select'] = "N/A"

                            # Set copay type dropdowns based on copay values
                            def get_copay_type(copay_value):
                                if copay_value == -1:
                                    return "N/A"
                                elif copay_value == -2:
                                    return "Not Covered"
                                elif copay_value is None:
                                    return "Ded + Coinsurance"
                                else:
                                    return "Flat Copay"

                            st.session_state['pcp_type'] = get_copay_type(new_plan.pcp_copay)
                            st.session_state['specialist_type'] = get_copay_type(new_plan.specialist_copay)
                            st.session_state['er_type'] = get_copay_type(new_plan.er_copay)
                            st.session_state['generic_type'] = get_copay_type(new_plan.generic_rx_copay)
                            st.session_state['preferred_type'] = get_copay_type(new_plan.preferred_rx_copay)
                            st.session_state['specialty_type'] = get_copay_type(new_plan.specialty_rx_copay)

                            # Set copay value inputs (only if Flat Copay)
                            if new_plan.pcp_copay and new_plan.pcp_copay > 0:
                                st.session_state['pcp_copay_input'] = int(new_plan.pcp_copay)
                            if new_plan.specialist_copay and new_plan.specialist_copay > 0:
                                st.session_state['specialist_copay_input'] = int(new_plan.specialist_copay)
                            if new_plan.er_copay and new_plan.er_copay > 0:
                                st.session_state['er_copay_input'] = int(new_plan.er_copay)
                            if new_plan.generic_rx_copay and new_plan.generic_rx_copay > 0:
                                st.session_state['generic_copay_input'] = int(new_plan.generic_rx_copay)
                            if new_plan.preferred_rx_copay and new_plan.preferred_rx_copay > 0:
                                st.session_state['preferred_copay_input'] = int(new_plan.preferred_rx_copay)
                            if new_plan.specialty_rx_copay and new_plan.specialty_rx_copay > 0:
                                st.session_state['specialty_copay_input'] = int(new_plan.specialty_rx_copay)

                            # Increment form refresh counter to signal update
                            st.session_state.form_refresh_counter += 1
                            st.rerun()
                    else:
                        st.warning("Could not extract plan name from the file. Please check the file format.")
            except Exception as e:
                st.error(f"Error parsing file: {str(e)}")

    # Get current plan from session state
    plan = st.session_state.current_employer_plan

    # Initialize widget keys with defaults from plan (only if not already set by SBC parsing)
    # This prevents "widget created with default value but also had value set via Session State" warnings
    if 'plan_name_input' not in st.session_state:
        st.session_state['plan_name_input'] = plan.plan_name
    if 'carrier_input' not in st.session_state:
        st.session_state['carrier_input'] = plan.carrier or ""
    if 'hsa_eligible_checkbox' not in st.session_state:
        st.session_state['hsa_eligible_checkbox'] = plan.hsa_eligible
    if 'current_premium_input' not in st.session_state:
        st.session_state['current_premium_input'] = int(plan.current_premium or 0)
    if 'renewal_premium_input' not in st.session_state:
        st.session_state['renewal_premium_input'] = int(plan.renewal_premium or 0)
    if 'coinsurance_slider' not in st.session_state:
        st.session_state['coinsurance_slider'] = int(plan.coinsurance_pct)

    # Plan Overview Section
    st.markdown('<p class="section-header">Plan Overview</p>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        plan_name = st.text_input(
            "Plan Name *",
            placeholder="e.g., Acme Corp Gold PPO",
            help="Name of your current group health plan",
            key="plan_name_input"
        )

        plan_type = st.selectbox(
            "Plan Type *",
            options=PLAN_TYPES,
            index=PLAN_TYPES.index(plan.plan_type) if plan.plan_type in PLAN_TYPES else 1,
            help="HMO, PPO, EPO, or POS",
            key="plan_type_select"
        )

        hsa_eligible = st.checkbox(
            "HSA Eligible",
            help="Is this a High Deductible Health Plan (HDHP) that qualifies for HSA?",
            key="hsa_eligible_checkbox"
        )

    with col2:
        carrier = st.text_input(
            "Carrier",
            placeholder="e.g., Blue Cross Blue Shield",
            help="Insurance carrier name (optional)",
            key="carrier_input"
        )

        # Initialize session state if not set
        if 'metal_tier_select' not in st.session_state:
            if plan.metal_tier in ["Bronze", "Silver", "Gold", "Platinum"]:
                st.session_state['metal_tier_select'] = plan.metal_tier
            else:
                st.session_state['metal_tier_select'] = "N/A"

        metal_tier = st.selectbox(
            "Metal Tier (if applicable)",
            options=["N/A", "Bronze", "Silver", "Gold", "Platinum"],
            help="Metal tier if known (most group plans don't have one)",
            key="metal_tier_select"
        )

    # Monthly Premium Section (EE-only)
    st.markdown('<p class="section-header">Monthly Premiums (EE-Only)</p>', unsafe_allow_html=True)
    st.caption("Total monthly premium for employee-only coverage (EE + ER contributions combined). Used for cost comparison.")

    col1, col2, col3 = st.columns(3)

    with col1:
        current_premium = st.number_input(
            "Current Premium",
            min_value=0,
            max_value=5000,
            step=10,
            help="Current monthly premium for EE-only coverage",
            key="current_premium_input"
        )

    with col2:
        renewal_premium = st.number_input(
            "Renewal Premium",
            min_value=0,
            max_value=5000,
            step=10,
            help="Renewal monthly premium for EE-only coverage",
            key="renewal_premium_input"
        )

    with col3:
        # Calculate and display gap if both are provided
        if current_premium > 0 and renewal_premium > 0:
            gap = renewal_premium - current_premium
            gap_pct = (gap / current_premium) * 100 if current_premium > 0 else 0
            st.metric(
                "Premium Increase",
                f"${gap:,.0f}",
                f"{gap_pct:+.1f}%",
                delta_color="inverse"
            )
        else:
            st.text_input("Premium Increase", value="—", disabled=True, help="Enter both premiums to see increase")

    # Deductibles & Out-of-Pocket Section
    st.markdown('<p class="section-header">Deductibles & Out-of-Pocket Maximum</p>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Individual (Single Coverage)**")

        # Initialize session state if not set
        if 'individual_deductible_input' not in st.session_state:
            st.session_state['individual_deductible_input'] = int(plan.individual_deductible)

        individual_deductible = st.number_input(
            "Individual Deductible *",
            min_value=0,
            max_value=20000,
            step=100,
            help="Annual deductible for single coverage",
            key="individual_deductible_input"
        )

        # Initialize session state if not set
        if 'individual_oop_max_input' not in st.session_state:
            st.session_state['individual_oop_max_input'] = int(plan.individual_oop_max)

        individual_oop_max = st.number_input(
            "Individual Out-of-Pocket Maximum *",
            min_value=0,
            max_value=20000,
            step=100,
            help="Maximum annual out-of-pocket for single coverage",
            key="individual_oop_max_input"
        )

    with col2:
        st.markdown("**Family Coverage**")

        # Initialize session state if not set
        if 'family_deductible_input' not in st.session_state:
            st.session_state['family_deductible_input'] = int(plan.family_deductible or 0)

        family_deductible = st.number_input(
            "Family Deductible",
            min_value=0,
            max_value=40000,
            step=100,
            help="Annual deductible for family coverage (leave 0 if N/A)",
            key="family_deductible_input"
        )

        # Initialize session state if not set
        if 'family_oop_max_input' not in st.session_state:
            st.session_state['family_oop_max_input'] = int(plan.family_oop_max or 0)

        family_oop_max = st.number_input(
            "Family Out-of-Pocket Maximum",
            min_value=0,
            max_value=40000,
            step=100,
            help="Maximum annual out-of-pocket for family (leave 0 if N/A)",
            key="family_oop_max_input"
        )

    # Coinsurance Section
    st.markdown('<p class="section-header">Coinsurance</p>', unsafe_allow_html=True)

    coinsurance_pct = st.slider(
        "Coinsurance % (Employee pays after deductible)",
        min_value=0,
        max_value=100,
        step=5,
        help="After meeting deductible, employee pays this % of costs (e.g., 20% = 80/20 plan, 100% = no coverage after deductible)",
        key="coinsurance_slider"
    )

    # Copays Section
    st.markdown('<p class="section-header">Copays</p>', unsafe_allow_html=True)
    st.caption("Select 'Flat Copay' for a fixed dollar amount, or 'Ded + Coinsurance' if the benefit requires meeting the deductible first.")

    # Helper to render copay input with type toggle
    # Convention: None = Ded + Coinsurance, -1 = N/A, -2 = Not Covered
    # New: copay > 0 AND coinsurance set = Copay + Coinsurance (e.g., "$50 + 100%")
    COPAY_TYPES = ["Flat Copay", "Copay + Coinsurance", "Ded + Coinsurance", "N/A", "Not Covered"]

    def get_copay_type_index(copay_value, coinsurance_value=None):
        """Determine selectbox index based on copay and coinsurance values."""
        if copay_value == -1:
            return 3  # N/A
        elif copay_value == -2:
            return 4  # Not Covered
        elif copay_value is None:
            return 2  # Ded + Coinsurance
        elif copay_value is not None and copay_value > 0 and coinsurance_value is not None:
            return 1  # Copay + Coinsurance
        else:
            return 0  # Flat Copay

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**Office Visits**")

        # PCP Copay
        pcp_type = st.selectbox(
            "PCP Visit",
            options=COPAY_TYPES,
            index=get_copay_type_index(plan.pcp_copay, plan.pcp_coinsurance),
            key="pcp_type"
        )
        if pcp_type == "Flat Copay":
            pcp_copay = st.number_input(
                "PCP Copay Amount",
                min_value=0,
                max_value=200,
                value=int(plan.pcp_copay) if plan.pcp_copay and plan.pcp_copay > 0 else 0,
                step=5,
                key="pcp_copay_input"
            )
            pcp_coinsurance = None
            pcp_after_deductible = False
        elif pcp_type == "Copay + Coinsurance":
            pcp_copay = st.number_input(
                "PCP Copay Amount",
                min_value=0,
                max_value=500,
                value=int(plan.pcp_copay) if plan.pcp_copay and plan.pcp_copay > 0 else 0,
                step=5,
                key="pcp_copay_combo_input"
            )
            pcp_coinsurance = st.slider(
                "Plus Coinsurance %",
                min_value=0, max_value=100,
                value=int(plan.pcp_coinsurance if plan.pcp_coinsurance is not None else coinsurance_pct),
                step=5, key="pcp_coins_combo_slider"
            )
            pcp_after_deductible = False
        elif pcp_type == "Ded + Coinsurance":
            pcp_copay = None
            pcp_coinsurance = st.slider(
                "PCP Coinsurance %",
                min_value=0, max_value=100,
                value=int(plan.pcp_coinsurance if plan.pcp_coinsurance is not None else coinsurance_pct),
                step=5, key="pcp_coins_slider"
            )
            pcp_after_deductible = st.checkbox(
                "After deductible",
                value=plan.pcp_after_deductible,
                help="Check if coinsurance applies only after the deductible is met",
                key="pcp_after_ded_checkbox"
            )
        elif pcp_type == "N/A":
            pcp_copay = -1
            pcp_coinsurance = None
            pcp_after_deductible = False
            st.info("N/A")
        else:  # Not Covered
            pcp_copay = -2
            pcp_coinsurance = None
            pcp_after_deductible = False
            st.warning("Not Covered")

        # Specialist Copay
        specialist_type = st.selectbox(
            "Specialist Visit",
            options=COPAY_TYPES,
            index=get_copay_type_index(plan.specialist_copay, plan.specialist_coinsurance),
            key="specialist_type"
        )
        if specialist_type == "Flat Copay":
            specialist_copay = st.number_input(
                "Specialist Copay Amount",
                min_value=0,
                max_value=200,
                value=int(plan.specialist_copay) if plan.specialist_copay and plan.specialist_copay > 0 else 0,
                step=5,
                key="specialist_copay_input"
            )
            specialist_coinsurance = None
            specialist_after_deductible = False
        elif specialist_type == "Copay + Coinsurance":
            specialist_copay = st.number_input(
                "Specialist Copay Amount",
                min_value=0,
                max_value=500,
                value=int(plan.specialist_copay) if plan.specialist_copay and plan.specialist_copay > 0 else 0,
                step=5,
                key="specialist_copay_combo_input"
            )
            specialist_coinsurance = st.slider(
                "Plus Coinsurance %",
                min_value=0, max_value=100,
                value=int(plan.specialist_coinsurance if plan.specialist_coinsurance is not None else coinsurance_pct),
                step=5, key="specialist_coins_combo_slider"
            )
            specialist_after_deductible = False
        elif specialist_type == "Ded + Coinsurance":
            specialist_copay = None
            specialist_coinsurance = st.slider(
                "Specialist Coinsurance %",
                min_value=0, max_value=100,
                value=int(plan.specialist_coinsurance if plan.specialist_coinsurance is not None else coinsurance_pct),
                step=5, key="specialist_coins_slider"
            )
            specialist_after_deductible = st.checkbox(
                "After deductible",
                value=plan.specialist_after_deductible,
                help="Check if coinsurance applies only after the deductible is met",
                key="specialist_after_ded_checkbox"
            )
        elif specialist_type == "N/A":
            specialist_copay = -1
            specialist_coinsurance = None
            specialist_after_deductible = False
            st.info("N/A")
        else:  # Not Covered
            specialist_copay = -2
            specialist_coinsurance = None
            specialist_after_deductible = False
            st.warning("Not Covered")

    with col2:
        st.markdown("**Emergency Care**")

        # ER Copay
        er_type = st.selectbox(
            "ER Visit",
            options=COPAY_TYPES,
            index=get_copay_type_index(plan.er_copay, plan.er_coinsurance),
            key="er_type"
        )
        if er_type == "Flat Copay":
            er_copay = st.number_input(
                "ER Copay Amount",
                min_value=0,
                max_value=1000,
                value=int(plan.er_copay) if plan.er_copay and plan.er_copay > 0 else 0,
                step=25,
                key="er_copay_input"
            )
            er_coinsurance = None
            er_after_deductible = False
        elif er_type == "Copay + Coinsurance":
            er_copay = st.number_input(
                "ER Copay Amount",
                min_value=0,
                max_value=1000,
                value=int(plan.er_copay) if plan.er_copay and plan.er_copay > 0 else 0,
                step=25,
                key="er_copay_combo_input"
            )
            er_coinsurance = st.slider(
                "Plus Coinsurance %",
                min_value=0, max_value=100,
                value=int(plan.er_coinsurance if plan.er_coinsurance is not None else coinsurance_pct),
                step=5, key="er_coins_combo_slider"
            )
            er_after_deductible = False
        elif er_type == "Ded + Coinsurance":
            er_copay = None
            er_coinsurance = st.slider(
                "ER Coinsurance %",
                min_value=0, max_value=100,
                value=int(plan.er_coinsurance if plan.er_coinsurance is not None else coinsurance_pct),
                step=5, key="er_coins_slider"
            )
            er_after_deductible = st.checkbox(
                "After deductible",
                value=plan.er_after_deductible,
                help="Check if coinsurance applies only after the deductible is met",
                key="er_after_ded_checkbox"
            )
        elif er_type == "N/A":
            er_copay = -1
            er_coinsurance = None
            er_after_deductible = False
            st.info("N/A")
        else:  # Not Covered
            er_copay = -2
            er_coinsurance = None
            er_after_deductible = False
            st.warning("Not Covered")

    with col3:
        st.markdown("**Prescription Drugs**")

        # Generic Rx Copay
        generic_type = st.selectbox(
            "Generic Rx",
            options=COPAY_TYPES,
            index=get_copay_type_index(plan.generic_rx_copay, plan.generic_rx_coinsurance),
            key="generic_type"
        )
        if generic_type == "Flat Copay":
            generic_rx_copay = st.number_input(
                "Generic Rx Copay Amount",
                min_value=0,
                max_value=100,
                value=int(plan.generic_rx_copay) if plan.generic_rx_copay and plan.generic_rx_copay > 0 else 0,
                step=5,
                key="generic_copay_input"
            )
            generic_rx_coinsurance = None
            generic_rx_after_deductible = False
        elif generic_type == "Copay + Coinsurance":
            generic_rx_copay = st.number_input(
                "Generic Rx Copay Amount",
                min_value=0,
                max_value=200,
                value=int(plan.generic_rx_copay) if plan.generic_rx_copay and plan.generic_rx_copay > 0 else 0,
                step=5,
                key="generic_copay_combo_input"
            )
            generic_rx_coinsurance = st.slider(
                "Plus Coinsurance %",
                min_value=0, max_value=100,
                value=int(plan.generic_rx_coinsurance if plan.generic_rx_coinsurance is not None else coinsurance_pct),
                step=5, key="generic_coins_combo_slider"
            )
            generic_rx_after_deductible = False
        elif generic_type == "Ded + Coinsurance":
            generic_rx_copay = None
            generic_rx_coinsurance = st.slider(
                "Generic Rx Coinsurance %",
                min_value=0, max_value=100,
                value=int(plan.generic_rx_coinsurance if plan.generic_rx_coinsurance is not None else coinsurance_pct),
                step=5, key="generic_coins_slider"
            )
            generic_rx_after_deductible = st.checkbox(
                "After deductible",
                value=plan.generic_rx_after_deductible,
                help="Check if coinsurance applies only after the deductible is met",
                key="generic_rx_after_ded_checkbox"
            )
        elif generic_type == "N/A":
            generic_rx_copay = -1
            generic_rx_coinsurance = None
            generic_rx_after_deductible = False
            st.info("N/A")
        else:  # Not Covered
            generic_rx_copay = -2
            generic_rx_coinsurance = None
            generic_rx_after_deductible = False
            st.warning("Not Covered")

        # Preferred Brand Rx Copay
        preferred_type = st.selectbox(
            "Preferred Brand Rx",
            options=COPAY_TYPES,
            index=get_copay_type_index(plan.preferred_rx_copay, plan.preferred_rx_coinsurance),
            key="preferred_type"
        )
        if preferred_type == "Flat Copay":
            preferred_rx_copay = st.number_input(
                "Preferred Rx Copay Amount",
                min_value=0,
                max_value=200,
                value=int(plan.preferred_rx_copay) if plan.preferred_rx_copay and plan.preferred_rx_copay > 0 else 0,
                step=5,
                key="preferred_copay_input"
            )
            preferred_rx_coinsurance = None
            preferred_rx_after_deductible = False
        elif preferred_type == "Copay + Coinsurance":
            preferred_rx_copay = st.number_input(
                "Preferred Rx Copay Amount",
                min_value=0,
                max_value=500,
                value=int(plan.preferred_rx_copay) if plan.preferred_rx_copay and plan.preferred_rx_copay > 0 else 0,
                step=5,
                key="preferred_copay_combo_input"
            )
            preferred_rx_coinsurance = st.slider(
                "Plus Coinsurance %",
                min_value=0, max_value=100,
                value=int(plan.preferred_rx_coinsurance if plan.preferred_rx_coinsurance is not None else coinsurance_pct),
                step=5, key="preferred_coins_combo_slider"
            )
            preferred_rx_after_deductible = False
        elif preferred_type == "Ded + Coinsurance":
            preferred_rx_copay = None
            preferred_rx_coinsurance = st.slider(
                "Preferred Rx Coinsurance %",
                min_value=0, max_value=100,
                value=int(plan.preferred_rx_coinsurance if plan.preferred_rx_coinsurance is not None else coinsurance_pct),
                step=5, key="preferred_coins_slider"
            )
            preferred_rx_after_deductible = st.checkbox(
                "After deductible",
                value=plan.preferred_rx_after_deductible,
                help="Check if coinsurance applies only after the deductible is met",
                key="preferred_rx_after_ded_checkbox"
            )
        elif preferred_type == "N/A":
            preferred_rx_copay = -1
            preferred_rx_coinsurance = None
            preferred_rx_after_deductible = False
            st.info("N/A")
        else:  # Not Covered
            preferred_rx_copay = -2
            preferred_rx_coinsurance = None
            preferred_rx_after_deductible = False
            st.warning("Not Covered")

        # Specialty Rx Copay
        specialty_type = st.selectbox(
            "Specialty Rx",
            options=COPAY_TYPES,
            index=get_copay_type_index(plan.specialty_rx_copay, plan.specialty_rx_coinsurance),
            key="specialty_type"
        )
        if specialty_type == "Flat Copay":
            specialty_rx_copay = st.number_input(
                "Specialty Rx Copay Amount",
                min_value=0,
                max_value=500,
                value=int(plan.specialty_rx_copay) if plan.specialty_rx_copay and plan.specialty_rx_copay > 0 else 0,
                step=25,
                key="specialty_copay_input"
            )
            specialty_rx_coinsurance = None
            specialty_rx_after_deductible = False
        elif specialty_type == "Copay + Coinsurance":
            specialty_rx_copay = st.number_input(
                "Specialty Rx Copay Amount",
                min_value=0,
                max_value=1000,
                value=int(plan.specialty_rx_copay) if plan.specialty_rx_copay and plan.specialty_rx_copay > 0 else 0,
                step=25,
                key="specialty_copay_combo_input"
            )
            specialty_rx_coinsurance = st.slider(
                "Plus Coinsurance %",
                min_value=0, max_value=100,
                value=int(plan.specialty_rx_coinsurance if plan.specialty_rx_coinsurance is not None else coinsurance_pct),
                step=5, key="specialty_coins_combo_slider"
            )
            specialty_rx_after_deductible = False
        elif specialty_type == "Ded + Coinsurance":
            specialty_rx_copay = None
            specialty_rx_coinsurance = st.slider(
                "Specialty Rx Coinsurance %",
                min_value=0, max_value=100,
                value=int(plan.specialty_rx_coinsurance if plan.specialty_rx_coinsurance is not None else coinsurance_pct),
                step=5, key="specialty_coins_slider"
            )
            specialty_rx_after_deductible = st.checkbox(
                "After deductible",
                value=plan.specialty_rx_after_deductible,
                help="Check if coinsurance applies only after the deductible is met",
                key="specialty_rx_after_ded_checkbox"
            )
        elif specialty_type == "N/A":
            specialty_rx_copay = -1
            specialty_rx_coinsurance = None
            specialty_rx_after_deductible = False
            st.info("N/A")
        else:  # Not Covered
            specialty_rx_copay = -2
            specialty_rx_coinsurance = None
            specialty_rx_after_deductible = False
            st.warning("Not Covered")

    # Update session state with form values
    # Note: copay values are None when "Ded + Coinsurance" is selected
    st.session_state.current_employer_plan = CurrentEmployerPlan(
        plan_name=plan_name,
        carrier=carrier if carrier else None,
        plan_type=plan_type,
        metal_tier=metal_tier if metal_tier != "N/A" else None,
        hsa_eligible=hsa_eligible,
        current_premium=float(current_premium) if current_premium > 0 else None,
        renewal_premium=float(renewal_premium) if renewal_premium > 0 else None,
        individual_deductible=float(individual_deductible),
        family_deductible=float(family_deductible) if family_deductible > 0 else None,
        individual_oop_max=float(individual_oop_max),
        family_oop_max=float(family_oop_max) if family_oop_max > 0 else None,
        coinsurance_pct=coinsurance_pct,
        pcp_copay=float(pcp_copay) if pcp_copay is not None else None,
        specialist_copay=float(specialist_copay) if specialist_copay is not None else None,
        er_copay=float(er_copay) if er_copay is not None else None,
        generic_rx_copay=float(generic_rx_copay) if generic_rx_copay is not None else None,
        preferred_rx_copay=float(preferred_rx_copay) if preferred_rx_copay is not None else None,
        specialty_rx_copay=float(specialty_rx_copay) if specialty_rx_copay is not None else None,
        # Per-service coinsurance overrides
        pcp_coinsurance=pcp_coinsurance,
        specialist_coinsurance=specialist_coinsurance,
        er_coinsurance=er_coinsurance,
        generic_rx_coinsurance=generic_rx_coinsurance,
        preferred_rx_coinsurance=preferred_rx_coinsurance,
        specialty_rx_coinsurance=specialty_rx_coinsurance,
        # Per-service "after deductible" flags
        pcp_after_deductible=pcp_after_deductible,
        specialist_after_deductible=specialist_after_deductible,
        er_after_deductible=er_after_deductible,
        generic_rx_after_deductible=generic_rx_after_deductible,
        preferred_rx_after_deductible=preferred_rx_after_deductible,
        specialty_rx_after_deductible=specialty_rx_after_deductible,
    )

    # Validation and navigation
    st.markdown("---")

    plan_valid = st.session_state.current_employer_plan.is_complete()

    if plan_valid:
        st.markdown(
            '<div class="success-box"><span class="success-text">Plan details complete. Ready to proceed to Stage 2.</span></div>',
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            '<div class="info-box"><span class="info-text">Fill in required fields (*) to continue to marketplace plan selection.</span></div>',
            unsafe_allow_html=True
        )

    if st.button("Continue to Stage 2: Select Marketplace Plans", disabled=not plan_valid, type="primary"):
        st.session_state.comparison_stage = 2
        st.rerun()


# ==============================================================================
# STAGE 2: FILTER & SELECT MARKETPLACE PLANS
# ==============================================================================

def lookup_state_from_zip(db: DatabaseConnection, zip_code: str) -> Optional[str]:
    """
    Look up state from ZIP code (auto-detect state).
    Returns state code (e.g., 'WI') or None if not found.
    """
    try:
        query = """
        SELECT UPPER("State") as state_code
        FROM zip_to_county_correct
        WHERE "ZIP" = %s
        LIMIT 1
        """
        result = db.execute_query(query, (zip_code,))
        if not result.empty:
            return result.iloc[0]['state_code']
    except Exception:
        pass
    return None


def lookup_rating_area(db: DatabaseConnection, zip_code: str, state: str) -> tuple:
    """
    Look up county and rating area from ZIP code.
    Returns (county, rating_area_id) or (None, None) if not found.
    """
    try:
        result = PlanQueries.get_county_by_zip(db, zip_code, state)
        if not result.empty:
            return result.iloc[0]['county'], result.iloc[0]['rating_area_id']
    except Exception as e:
        st.warning(f"ZIP lookup error: {e}")
    return None, None


def parse_copay_string(copay_str: str) -> Optional[float]:
    """
    Parse copay string from database into numeric value.
    Returns None if it's pure coinsurance-based (no flat copay amount).

    Examples:
        "$30" -> 30.0
        "$0" -> 0.0
        "No Charge" -> 0.0
        "500 Copay after deductible" -> 500.0 (still a flat copay)
        "10 Copay after deductible" -> 10.0
        "0% after deductible" -> None (pure coinsurance)
        "20% Coinsurance" -> None (pure coinsurance)
        "Not Applicable" -> None
    """
    import re

    if not copay_str or copay_str in ('Not Applicable', 'N/A', ''):
        return None

    copay_str = str(copay_str).strip()

    # "No Charge" = $0 copay
    if copay_str.lower() == 'no charge':
        return 0.0

    # Check for pure coinsurance patterns (no dollar amount, just percentage)
    # e.g., "20% Coinsurance", "0% after deductible"
    if '%' in copay_str and 'copay' not in copay_str.lower():
        return None

    # Extract dollar amount - handles formats like:
    # "$30", "30", "500 Copay after deductible", "$50 after deductible"
    match = re.search(r'\$?([\d,]+(?:\.\d{2})?)', copay_str)
    if match:
        try:
            return float(match.group(1).replace(',', ''))
        except ValueError:
            return None

    return None


def pivot_copay_data(copay_df: pd.DataFrame) -> Dict[str, Dict]:
    """
    Pivot copay DataFrame (one row per benefit) into a dict of plan_id -> copay values.

    Returns dict like: {
        'plan_id_1': {'pcp_copay': 30.0, 'specialist_copay': 50.0, ...},
        'plan_id_2': {...}
    }
    """
    if copay_df.empty:
        return {}

    # Mapping from benefit name patterns to our field names
    # Note: Order matters - more specific patterns should come first
    benefit_mapping = [
        ('primary care visit', 'pcp_copay'),
        ('specialist visit', 'specialist_copay'),
        ('emergency room services', 'er_copay'),
        ('generic drugs', 'generic_rx_copay'),
        ('preferred brand drugs', 'preferred_rx_copay'),
        ('specialty drugs', 'specialty_rx_copay'),
    ]

    result = {}
    for _, row in copay_df.iterrows():
        plan_id = row['hios_plan_id']
        if plan_id not in result:
            result[plan_id] = {}

        benefit = str(row.get('benefit', '')).lower()
        copay_str = row.get('copay', '')

        # Match benefit to our field name
        for pattern, field_name in benefit_mapping:
            if pattern in benefit:
                parsed_value = parse_copay_string(copay_str)
                result[plan_id][field_name] = parsed_value
                break

    return result


def search_marketplace_plans(db: DatabaseConnection, state: str, rating_area_id: int,
                              filters: ComparisonFilters, current_plan: Optional[CurrentEmployerPlan] = None) -> List[Dict]:
    """
    Search for marketplace plans and calculate match scores.
    Returns list of plan dictionaries with match scores.

    If current_plan is None (Marketplace Only mode), plans are sorted by
    premium (lowest first) instead of match score.
    """
    try:
        # Get plans with full details (includes deductible and OOPM)
        plans_df = PlanComparisonQueries.get_plans_with_full_details(
            db=db,
            state_code=state,
            rating_area_id=rating_area_id,
            metal_levels=filters.metal_levels if filters.metal_levels else None,
            plan_types=filters.plan_types if filters.plan_types else None,
            max_deductible=filters.max_deductible,
            max_oopm=filters.max_oop_max if hasattr(filters, 'max_oop_max') else None,
            hsa_only=filters.hsa_only
        )

        if plans_df.empty:
            return []

        # Get copay data for these plans and pivot it
        plan_ids = plans_df['hios_plan_id'].tolist()
        copay_df = PlanComparisonQueries.get_plan_copays_for_comparison(db, plan_ids)
        copay_data = pivot_copay_data(copay_df)

        # Get family deductibles and OOPM
        family_df = PlanComparisonQueries.get_plan_family_deductibles_oopm(db, plan_ids)
        family_data = {}
        if not family_df.empty:
            for _, row in family_df.iterrows():
                plan_id = row['plan_id']
                if plan_id not in family_data:
                    family_data[plan_id] = {}
                moop_ded_type = str(row.get('moop_ded_type', '')).lower()
                if 'deductible' in moop_ded_type:
                    family_data[plan_id]['family_deductible'] = row.get('family_amount')
                elif 'maximum' in moop_ded_type or 'out of pocket' in moop_ded_type:
                    family_data[plan_id]['family_oop_max'] = row.get('family_amount')

        # Get age-21 premiums for the plans
        # Query base rates directly for age 21 in the rating area
        age_21_query = f"""
        SELECT plan_id as hios_plan_id, individual_rate as premium
        FROM rbis_insurance_plan_base_rates_20251019202724
        WHERE plan_id IN ({', '.join(['%s'] * len(plan_ids))})
          AND rating_area_id = %s
          AND age = '21'
          AND rate_effective_date = '2026-01-01'
        """
        age_21_rates = db.execute_query(age_21_query, tuple(plan_ids) + (f"Rating Area {rating_area_id}",))
        premium_data = {}
        if not age_21_rates.empty:
            for _, row in age_21_rates.iterrows():
                pid = row.get('hios_plan_id')
                premium = row.get('premium')
                if pid and premium:
                    premium_data[pid] = float(premium)

        # Calculate match scores for each plan
        results = []
        seen_ids = set()

        for _, row in plans_df.iterrows():
            plan_id = row['hios_plan_id']

            # Skip duplicates (can happen from the join)
            if plan_id in seen_ids:
                continue
            seen_ids.add(plan_id)

            # Get copay data for this plan
            plan_copays = copay_data.get(plan_id, {})
            plan_family = family_data.get(plan_id, {})

            # Parse HSA eligibility (comes as 'Yes'/'No' string)
            hsa_eligible = str(row.get('hsa_eligible', '')).lower() == 'yes'

            # Parse family deductible/OOPM from string (e.g., "$15000 per group" -> 15000.0)
            def parse_dollar_amount(val):
                if val is None or val == '' or pd.isna(val):
                    return None
                try:
                    import re
                    # Handle strings like "$15000 per group" or "$7500 per person"
                    val_str = str(val)
                    # Extract just the numeric portion
                    match = re.search(r'\$?([\d,]+(?:\.\d+)?)', val_str)
                    if match:
                        return float(match.group(1).replace(',', ''))
                    return None
                except (ValueError, TypeError):
                    return None

            family_ded = parse_dollar_amount(plan_family.get('family_deductible'))
            family_oopm = parse_dollar_amount(plan_family.get('family_oop_max'))

            # Derive coinsurance from metal level (typical ACA values)
            metal = row.get('metal_level', '')
            coinsurance_by_metal = {
                'Bronze': 40,
                'Expanded Bronze': 40,
                'Silver': 20,
                'Gold': 20,
                'Platinum': 10,
                'Catastrophic': 50,
            }
            coinsurance_pct = coinsurance_by_metal.get(metal, 20)

            # Parse actuarial value (may be percentage like '70.0' or None)
            av_raw = row.get('av_percent')
            av_value = None
            if av_raw is not None and av_raw != '' and not pd.isna(av_raw):
                try:
                    av_value = float(av_raw)
                except (ValueError, TypeError):
                    av_value = None

            # Create MarketplacePlanDetails object
            # Note: query returns 'individual_oopm', not 'individual_oop_max'
            mp = MarketplacePlanDetails(
                hios_plan_id=plan_id,
                plan_name=row.get('plan_marketing_name', plan_id),
                issuer_name=row.get('issuer_name', None),
                metal_level=row.get('metal_level', ''),
                plan_type=row.get('plan_type', ''),
                hsa_eligible=hsa_eligible,
                individual_deductible=float(row.get('individual_deductible', 0) or 0),
                family_deductible=family_ded,
                individual_oop_max=float(row.get('individual_oopm', 0) or 0),  # Column name from query
                family_oop_max=family_oopm,
                coinsurance_pct=coinsurance_pct,
                pcp_copay=plan_copays.get('pcp_copay'),
                specialist_copay=plan_copays.get('specialist_copay'),
                er_copay=plan_copays.get('er_copay'),
                generic_rx_copay=plan_copays.get('generic_rx_copay'),
                preferred_rx_copay=plan_copays.get('preferred_rx_copay'),
                specialty_rx_copay=plan_copays.get('specialty_rx_copay'),
                age_21_premium=premium_data.get(plan_id),
                actuarial_value=av_value,
            )

            # Calculate match score (only if current_plan provided)
            if current_plan is not None:
                score = calculate_match_score(current_plan, mp)
                mp.match_score = score

                # Calculate enhanced ranking (includes cost consideration)
                ranking_score, tier = calculate_enhanced_ranking_score(current_plan, mp, score)
            else:
                # Marketplace Only mode: no match score, rank by premium
                score = None
                ranking_score = None
                tier = None

            results.append({
                'plan': mp,
                'issuer': row.get('issuer_name', 'Unknown'),
                'match_score': score,
                'ranking_score': ranking_score,
                'tier': tier,
            })

        # Sort results
        if current_plan is not None:
            # Sort by RANKING score (includes cost consideration), not just match score
            results.sort(key=lambda x: x['ranking_score'], reverse=True)
        else:
            # Marketplace Only: sort by premium (lowest first), then AV (highest first)
            def sort_key(x):
                premium = x['plan'].age_21_premium or float('inf')
                av = x['plan'].actuarial_value or 0
                return (premium, -av)
            results.sort(key=sort_key)
        return results

    except Exception as e:
        st.error(f"Error searching plans: {e}")
        import traceback
        traceback.print_exc()
        return []


def render_stage_2_marketplace_selection():
    """Render marketplace plan filtering and selection."""
    is_marketplace_only = st.session_state.comparison_mode == "Marketplace Only"

    # Adjust header based on mode
    if is_marketplace_only:
        stage_title = "Stage 1: Select Marketplace Plans"
        stage_desc = "Filter and select up to 5 marketplace plans to compare against each other."
    else:
        stage_title = "Stage 2: Select Marketplace Plans"
        stage_desc = "Filter and select up to 5 marketplace plans to compare against your current plan."

    st.markdown(f'''
    <div class="stage-header">
        <p class="stage-title">{stage_title}</p>
        <p class="stage-description">{stage_desc}</p>
    </div>
    ''', unsafe_allow_html=True)

    # Initialize search results in session state
    if 'search_results' not in st.session_state:
        st.session_state.search_results = []

    # Show current plan summary (only in Compare to Current mode)
    if not is_marketplace_only:
        plan = st.session_state.current_employer_plan
        with st.expander("Current Plan Summary", expanded=False):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.write(f"**{plan.plan_name}**")
                st.write(f"Type: {plan.plan_type}")
                st.write(f"HSA: {'Yes' if plan.hsa_eligible else 'No'}")
            with col2:
                st.write(f"Deductible: ${plan.individual_deductible:,.0f}")
                st.write(f"OOP Max: ${plan.individual_oop_max:,.0f}")
                st.write(f"Coinsurance: {plan.coinsurance_pct}%")
            with col3:
                st.write(f"PCP Copay: {plan.format_copay(plan.pcp_copay)}")
                st.write(f"Specialist: {plan.format_copay(plan.specialist_copay)}")
                st.write(f"Generic Rx: {plan.format_copay(plan.generic_rx_copay)}")

    # Location Input
    st.markdown('<p class="section-header">Location</p>', unsafe_allow_html=True)

    location = st.session_state.comparison_location

    # Prefill ZIP from census if not set and census is available
    prefilled_zip = location.zip_code
    census_zip_hint = None
    census_df = st.session_state.get('census_df')
    if census_df is not None and not census_df.empty:
        zip_col = 'zip_code' if 'zip_code' in census_df.columns else 'Home Zip' if 'Home Zip' in census_df.columns else None
        if zip_col and zip_col in census_df.columns:
            zip_counts = census_df[zip_col].value_counts()
            if not zip_counts.empty:
                most_common_zip = str(zip_counts.index[0]).zfill(5)[:5]
                employee_count = zip_counts.iloc[0]
                total_employees = len(census_df)
                census_zip_hint = f"Most common ZIP in census: {most_common_zip} ({employee_count}/{total_employees} employees)"
                # Auto-fill if location ZIP is empty
                if not prefilled_zip:
                    prefilled_zip = most_common_zip

    col1, col2, col3 = st.columns(3)

    with col1:
        zip_code = st.text_input(
            "ZIP Code *",
            value=prefilled_zip,
            max_chars=5,
            placeholder="e.g., 63101",
            help=census_zip_hint if census_zip_hint else "5-digit ZIP code for marketplace plan lookup"
        )

    # Auto-detect state from ZIP code
    auto_detected_state = location.state
    if zip_code and len(zip_code) == 5:
        # Only auto-detect if ZIP changed or state not set
        if zip_code != location.zip_code or not location.state:
            db = get_database_connection()
            if db:
                detected = lookup_state_from_zip(db, zip_code)
                if detected and detected in TARGET_STATES:
                    auto_detected_state = detected

    with col2:
        state = st.selectbox(
            "State *",
            options=[""] + TARGET_STATES,
            index=TARGET_STATES.index(auto_detected_state) + 1 if auto_detected_state in TARGET_STATES else 0,
            help="Auto-detected from ZIP code"
        )

    # Auto-lookup county and rating area when ZIP/state change
    county_display = location.county
    rating_area_id = location.rating_area_id

    if zip_code and len(zip_code) == 5 and state:
        # Check if we need to look up
        if (zip_code != location.zip_code or state != location.state or
            not location.county or not location.rating_area_id):
            db = get_database_connection()
            if db:
                county_lookup, ra_lookup = lookup_rating_area(db, zip_code, state)
                if county_lookup:
                    county_display = county_lookup
                    rating_area_id = ra_lookup

    with col3:
        st.text_input(
            "County / Rating Area",
            value=f"{county_display} (RA {rating_area_id})" if county_display and rating_area_id else "",
            disabled=True,
            help="Auto-populated from ZIP lookup"
        )

    # Update location in session state
    st.session_state.comparison_location = ComparisonLocation(
        zip_code=zip_code,
        state=state,
        county=county_display or "",
        rating_area_id=rating_area_id,
    )

    # Filter Options
    st.markdown('<p class="section-header">Filters</p>', unsafe_allow_html=True)

    filters = st.session_state.comparison_filters

    col1, col2 = st.columns(2)

    with col1:
        metal_levels = st.multiselect(
            "Metal Levels",
            options=["Bronze", "Expanded Bronze", "Silver", "Gold", "Platinum", "Catastrophic"],
            default=filters.metal_levels,
            help="Filter by ACA metal tier"
        )

        hsa_only = st.checkbox(
            "HSA-eligible plans only",
            value=filters.hsa_only,
            help="Only show High Deductible Health Plans eligible for HSA"
        )

    with col2:
        plan_types = st.multiselect(
            "Plan Types",
            options=PLAN_TYPES,
            default=filters.plan_types,
            help="Filter by network type (HMO, PPO, etc.)"
        )

        max_deductible = st.number_input(
            "Max Deductible",
            min_value=0,
            max_value=10000,
            value=int(filters.max_deductible or 0),
            step=500,
            help="Maximum individual deductible (0 = no limit)"
        )

    # Update filters in session state
    st.session_state.comparison_filters = ComparisonFilters(
        metal_levels=metal_levels if metal_levels else ["Bronze", "Expanded Bronze", "Silver", "Gold", "Platinum", "Catastrophic"],
        plan_types=plan_types if plan_types else PLAN_TYPES,
        hsa_only=hsa_only,
        max_deductible=float(max_deductible) if max_deductible > 0 else None,
    )

    # Search for plans
    st.markdown("---")

    # Validate location
    location_valid = bool(zip_code and len(zip_code) == 5 and state and rating_area_id)

    if not location_valid:
        if zip_code and len(zip_code) == 5 and state and not rating_area_id:
            st.warning("Could not find rating area for this ZIP code. Please verify the ZIP and state.")
        else:
            st.info("Enter a valid ZIP code and state to search for marketplace plans.")
    else:
        if st.button("Search Marketplace Plans", type="primary"):
            with st.spinner("Searching for plans..."):
                db = get_database_connection()
                if db:
                    # In Marketplace Only mode, don't pass current plan (sort by premium instead)
                    current_plan_for_search = None if is_marketplace_only else st.session_state.current_employer_plan
                    results = search_marketplace_plans(
                        db=db,
                        state=state,
                        rating_area_id=rating_area_id,
                        filters=st.session_state.comparison_filters,
                        current_plan=current_plan_for_search
                    )
                    st.session_state.search_results = results
                    if results:
                        st.success(f"Found {len(results)} plans matching your criteria.")
                    else:
                        st.warning("No plans found matching your criteria. Try adjusting your filters.")
                else:
                    st.error("Could not connect to database.")

    # Display search results
    if st.session_state.search_results:
        st.markdown('<p class="section-header">Available Plans</p>', unsafe_allow_html=True)

        # Plan name search filter
        plan_search = st.text_input(
            "🔍 Search by plan name",
            value="",
            placeholder="Type to filter plans by name...",
            key="plan_name_search"
        )

        # Display selected plans as removable chips
        selected_plan_ids = st.session_state.selected_comparison_plans
        if selected_plan_ids:
            # Build lookup of plan details from search results
            plan_lookup = {r['plan'].hios_plan_id: r['plan'] for r in st.session_state.search_results}

            # Create chip container with CSS
            st.markdown("""
            <style>
            .chip-container {
                display: flex;
                flex-wrap: wrap;
                gap: 8px;
                margin: 12px 0;
            }
            .plan-chip {
                display: inline-flex;
                align-items: center;
                background-color: #e3f2fd;
                border: 1px solid #90caf9;
                border-radius: 16px;
                padding: 4px 12px;
                font-size: 0.85em;
                color: #1565c0;
            }
            .plan-chip-name {
                max-width: 200px;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
            }
            </style>
            """, unsafe_allow_html=True)

            st.markdown(f"**Selected Plans ({len(selected_plan_ids)}/{MAX_COMPARISON_PLANS}):**")

            # Display chips with remove buttons
            chip_cols = st.columns(min(len(selected_plan_ids), 3) + 1)
            for idx, plan_id in enumerate(selected_plan_ids):
                plan = plan_lookup.get(plan_id)
                if plan:
                    col_idx = idx % 3
                    with chip_cols[col_idx]:
                        # Truncate long plan names
                        display_name = plan.plan_name[:30] + "..." if len(plan.plan_name) > 30 else plan.plan_name
                        if st.button(f"✕ {display_name}", key=f"remove_chip_{plan_id}", help=f"Remove {plan.plan_name}"):
                            st.session_state.selected_comparison_plans.remove(plan_id)
                            st.rerun()

            st.markdown("---")

        # Filter results by search term
        all_results = st.session_state.search_results
        if plan_search.strip():
            search_lower = plan_search.strip().lower()
            filtered_results = [
                r for r in all_results
                if search_lower in r['plan'].plan_name.lower()
                or search_lower in (r.get('issuer', '') or '').lower()
            ]
        else:
            filtered_results = all_results

        # Pagination settings (must be before caption that uses these vars)
        PLANS_PER_PAGE = 25
        total_plans = len(filtered_results)
        total_pages = max(1, (total_plans + PLANS_PER_PAGE - 1) // PLANS_PER_PAGE)

        # Initialize page in session state
        if 'plan_list_page' not in st.session_state:
            st.session_state.plan_list_page = 0

        # Reset page if search changed or out of bounds
        current_page = st.session_state.plan_list_page
        if current_page >= total_pages:
            current_page = 0
            st.session_state.plan_list_page = 0

        # Calculate slice for current page
        start_idx = current_page * PLANS_PER_PAGE
        end_idx = min(start_idx + PLANS_PER_PAGE, total_plans)

        if total_plans > PLANS_PER_PAGE:
            st.caption(f"Showing {start_idx + 1}-{end_idx} of {total_plans} plans (filtered from {len(all_results)}). Select up to {MAX_COMPARISON_PLANS} to compare.")
        else:
            st.caption(f"Showing {total_plans} of {len(all_results)} plans. Select up to {MAX_COMPARISON_PLANS} to compare.")

        with st.expander("How are plans ranked?"):
            st.markdown("""
            Plans are sorted by **Match Score** (highest first), which measures how similar each marketplace plan is to your current employer plan.

            **Scoring weights:**
            | Factor | Weight | Description |
            |--------|--------|-------------|
            | Deductible | 25% | Compares individual deductible amounts |
            | Out-of-Pocket Max | 25% | Compares individual OOPM limits |
            | Plan Type | 15% | PPO↔PPO scores higher than PPO↔HMO |
            | HSA Eligibility | 10% | Penalizes if current has HSA but marketplace doesn't |
            | Copays | 25% | Compares PCP, Specialist, and Generic Rx copays |

            Higher scores indicate plans more similar to your current coverage.
            """)

        # Get currently selected plans
        selected = set(st.session_state.selected_comparison_plans)

        # Handle no results after filtering
        if not filtered_results:
            if plan_search.strip():
                st.info(f"No plans match '{plan_search}'. Try a different search term.")
            # Don't show plan list if no filtered results
        else:
            # Display plans with checkboxes (paginated)
            page_results = filtered_results[start_idx:end_idx]

            for i, result in enumerate(page_results):
                actual_idx = start_idx + i  # Global index for unique keys
                mp = result['plan']
                score = result['match_score']

                # Determine score styling
                if score >= 70:
                    score_class = "match-score"
                elif score >= 50:
                    score_class = "match-score match-score-medium"
                else:
                    score_class = "match-score match-score-low"

                col1, col2, col3, col4, col5 = st.columns([0.5, 3, 1.5, 1.5, 1])

                with col1:
                    # Checkbox for selection
                    is_selected = mp.hios_plan_id in selected
                    can_select = len(selected) < MAX_COMPARISON_PLANS or is_selected

                    # Use only plan ID in key (not index) to maintain state across pagination/filtering
                    checkbox_key = f"select_plan_{mp.hios_plan_id}"

                    # Initialize checkbox state if not present
                    if checkbox_key not in st.session_state:
                        st.session_state[checkbox_key] = is_selected

                    checkbox_value = st.checkbox(
                        f"Select {mp.plan_name}",
                        key=checkbox_key,
                        disabled=not can_select,
                        label_visibility="collapsed"
                    )

                    # Update selected set based on checkbox state
                    if checkbox_value:
                        selected.add(mp.hios_plan_id)
                    else:
                        selected.discard(mp.hios_plan_id)

                with col2:
                    st.write(f"**{mp.plan_name}**")
                    st.caption(f"{result['issuer']} | {mp.plan_type}")

                with col3:
                    st.write(f"{mp.metal_level}")
                    st.caption(f"Ded: ${mp.individual_deductible:,.0f}")

                with col4:
                    st.write(f"OOP: ${mp.individual_oop_max:,.0f}")
                    hsa_text = "HSA" if mp.hsa_eligible else ""
                    st.caption(hsa_text)

                with col5:
                    st.markdown(f'<span class="{score_class}">{score:.0f}%</span>', unsafe_allow_html=True)

            # Pagination controls (inside else block)
            if total_pages > 1:
                st.markdown("---")
                pcol1, pcol2, pcol3 = st.columns([1, 2, 1])
                with pcol1:
                    if st.button("← Previous", disabled=current_page == 0, key="prev_page"):
                        st.session_state.plan_list_page = current_page - 1
                        st.rerun()
                with pcol2:
                    st.markdown(f"<div style='text-align: center;'>Page {current_page + 1} of {total_pages} ({total_plans} plans)</div>", unsafe_allow_html=True)
                with pcol3:
                    if st.button("Next →", disabled=current_page >= total_pages - 1, key="next_page"):
                        st.session_state.plan_list_page = current_page + 1
                        st.rerun()

        # Update selected plans in session state
        st.session_state.selected_comparison_plans = list(selected)

        if len(selected) >= MAX_COMPARISON_PLANS:
            st.info(f"Maximum {MAX_COMPARISON_PLANS} plans selected. Deselect a plan to choose a different one.")

    elif st.session_state.search_results is not None and len(st.session_state.search_results) == 0:
        # Empty list means search was performed but no results
        pass  # Warning already shown above

    # Navigation
    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Back to Stage 1"):
            st.session_state.comparison_stage = 1
            st.rerun()

    with col2:
        # Enable when plans are selected
        plans_selected = len(st.session_state.selected_comparison_plans) > 0
        if st.button("Continue to Stage 3: Compare Benefits", disabled=not plans_selected, type="primary"):
            st.session_state.comparison_stage = 3
            st.rerun()


# ==============================================================================
# STAGE 3: BENEFIT COMPARISON TABLE
# ==============================================================================

def get_plan_value(plan, attr: str):
    """Get attribute value from either CurrentEmployerPlan or MarketplacePlanDetails."""
    return getattr(plan, attr, None)


def get_coinsurance_for_attr(plan: CurrentEmployerPlan, attr: str) -> int:
    """Get the coinsurance percentage for a specific attribute.

    Uses per-service coinsurance if set, otherwise falls back to default coinsurance_pct.
    """
    service_map = {
        'pcp_copay': plan.pcp_coinsurance,
        'specialist_copay': plan.specialist_coinsurance,
        'er_copay': plan.er_coinsurance,
        'generic_rx_copay': plan.generic_rx_coinsurance,
        'preferred_rx_copay': plan.preferred_rx_coinsurance,
        'specialty_rx_copay': plan.specialty_rx_coinsurance,
    }
    override = service_map.get(attr)
    return override if override is not None else plan.coinsurance_pct


def is_combined_copay_coinsurance(plan: CurrentEmployerPlan, attr: str) -> bool:
    """Check if this copay field should display combined format ($X + Y%).

    Combined format applies when:
    - The copay value is > 0 (not None, -1, -2, or 0)
    - The per-service coinsurance is explicitly set (not None)
    """
    if 'copay' not in attr:
        return False

    # Get copay value
    copay_value = get_plan_value(plan, attr)
    if copay_value is None or copay_value <= 0:
        return False

    # Check if per-service coinsurance is explicitly set
    coinsurance_map = {
        'pcp_copay': plan.pcp_coinsurance,
        'specialist_copay': plan.specialist_coinsurance,
        'er_copay': plan.er_coinsurance,
        'generic_rx_copay': plan.generic_rx_coinsurance,
        'preferred_rx_copay': plan.preferred_rx_coinsurance,
        'specialty_rx_copay': plan.specialty_rx_coinsurance,
    }
    return coinsurance_map.get(attr) is not None


def compare_copay_benefit(
    current_value: Optional[float],
    current_coinsurance: int,
    is_combined: bool,
    mp_value: Optional[float],
    mp_coinsurance: int,
    mp_actuarial_value: Optional[float] = None
) -> str:
    """Compare copay benefits with awareness of different cost structures.

    Handles comparisons between:
    - Flat copay vs Ded+Coinsurance
    - Copay+Coinsurance vs Ded+Coinsurance
    - Copay+Coinsurance vs Flat copay

    Returns: 'better', 'similar', 'worse'

    Logic:
    - 100% coinsurance = no coverage after copay/deductible (very bad)
    - Lower coinsurance % = better coverage
    - When structures differ, compare effective coverage levels
    """
    # Handle sentinel values - N/A or Not Covered
    if current_value == -1 or current_value == -2:
        return 'similar'  # Can't compare N/A or Not Covered
    if mp_value == -1 or mp_value == -2:
        return 'similar'

    # Both have same structure - use standard numeric comparison
    if current_value is not None and mp_value is not None:
        # Both are flat copays (or copay portion of combined)
        if current_value == mp_value:
            # If combined format, also compare coinsurance
            if is_combined:
                if current_coinsurance > mp_coinsurance:
                    return 'better'  # MP has lower coinsurance
                elif current_coinsurance < mp_coinsurance:
                    return 'worse'
            return 'better'  # Equal copays = equivalent

        # Standard copay comparison (lower is better)
        diff_pct = (mp_value - current_value) / current_value * 100 if current_value > 0 else 0
        if abs(diff_pct) <= 5:
            return 'similar'
        return 'better' if diff_pct < 0 else 'worse'

    # Both use Ded+Coinsurance (both values are None)
    if current_value is None and mp_value is None:
        # Compare coinsurance percentages
        if current_coinsurance == mp_coinsurance:
            return 'better'  # Equivalent
        elif mp_coinsurance < current_coinsurance:
            return 'better'  # MP has lower coinsurance
        else:
            return 'worse'

    # STRUCTURE MISMATCH: One has copay, other has Ded+Coinsurance

    # Case 1: Current has copay (or copay+coinsurance), MP has Ded+Coinsurance
    if current_value is not None and current_value > 0 and mp_value is None:
        if is_combined:
            # Current: $X + Y% coinsurance vs MP: Ded + Z% coinsurance
            # Compare coinsurance levels - this is the key coverage indicator
            if current_coinsurance >= 100:
                # 100% coinsurance = member pays everything after copay = terrible
                # Any marketplace plan with <100% coinsurance is better
                return 'better' if mp_coinsurance < 100 else 'similar'
            elif current_coinsurance > mp_coinsurance:
                # MP has lower coinsurance = better coverage
                return 'better'
            elif current_coinsurance < mp_coinsurance:
                # Current has lower coinsurance, but also has copay
                # This is ambiguous - depends on service cost
                return 'similar'
            else:
                # Same coinsurance, but current also has copay = MP slightly better
                return 'better'
        else:
            # Current: Flat $X copay vs MP: Ded + Y% coinsurance
            # Hard to compare directly - depends on service cost and deductible status
            # Use AV as a quality signal if available
            if mp_actuarial_value and mp_actuarial_value >= 70:
                # Good AV plan likely provides better coverage overall
                return 'similar'  # Conservative - don't assume better
            return 'similar'

    # Case 2: Current has Ded+Coinsurance, MP has copay
    if current_value is None and mp_value is not None and mp_value > 0:
        # MP has flat copay, current has coinsurance
        # Generally flat copays are predictable but coinsurance can be better for low-cost services
        return 'similar'  # Can't determine without knowing service costs

    # Default fallback
    return 'similar'


def format_value(value, attr: str, coinsurance_pct: int = 20, combined_format: bool = False) -> str:
    """Format a benefit value for display.

    Copay conventions:
    - None = Deductible + Coinsurance applies
    - -1 = N/A (field not applicable)
    - -2 = Not Covered (service excluded)
    - 0 = No charge
    - >0 = Dollar amount
    - combined_format=True = Show "$X + Y%" when copay AND coinsurance both apply
    """
    # Handle None for copay fields = "Ded + Coinsurance"
    if value is None:
        if 'copay' in attr:
            return f"Ded + {coinsurance_pct}%"
        return "N/A"

    # Handle sentinel values for copays
    if 'copay' in attr:
        if value == -1:
            return "N/A"
        elif value == -2:
            return "Not Covered"

    if attr == 'hsa_eligible':
        return "Yes" if value else "No"
    elif attr == 'plan_type':
        return str(value)
    elif attr == 'coinsurance_pct':
        return f"{value}%"
    elif 'deductible' in attr or 'oop_max' in attr or 'copay' in attr:
        if value == 0:
            return "No charge"
        # Handle combined copay + coinsurance format
        if combined_format and 'copay' in attr and coinsurance_pct > 0:
            return f"${value:,.0f} + {coinsurance_pct}%"
        return f"${value:,.0f}"
    else:
        return str(value)

def build_slide_data(current_plan: CurrentEmployerPlan,
                     selected_plans: List[MarketplacePlanDetails],
                     comparison_data: Dict[str, Any]) -> PlanComparisonSlideData:
    """
    Build PlanComparisonSlideData from current comparison context.

    Args:
        current_plan: The current employer plan
        selected_plans: List of selected marketplace plans
        comparison_data: Dict with keys:
            - employee_count: int
            - avg_age: float
            - current_total: float (current plan total premium)
            - renewal_total: float (renewal total premium)
            - marketplace_totals: Dict[plan_id, total]
            - affordable_contributions: Dict[plan_id, {total, avg, min, max}]
            - footnote: str
    """
    plans = []
    employee_count = comparison_data.get('employee_count', 0)

    # Build current plan column
    current_coinsurance = current_plan.coinsurance_pct
    current_total = comparison_data.get('current_total', 0)
    renewal_total = comparison_data.get('renewal_total', 0)
    avg_current = current_total / employee_count if employee_count > 0 and current_total > 0 else None
    avg_renewal = renewal_total / employee_count if employee_count > 0 and renewal_total > 0 else None

    # Get current plan premiums from the plan object
    current_age_21 = getattr(current_plan, 'current_premium', None)
    renewal_age_21 = getattr(current_plan, 'renewal_premium', None)

    current_col = PlanColumnData(
        plan_name=current_plan.plan_name or "Current Plan",
        issuer_name=current_plan.carrier or "",
        plan_type=(current_plan.plan_type or "Group", 'similar'),  # Tuple format
        is_current=True,
        hsa_eligible=(current_plan.hsa_eligible, 'similar'),
        # Current/renewal premium pairs
        current_age_21_premium=current_age_21,
        renewal_age_21_premium=renewal_age_21,
        current_total_premium=current_total if current_total > 0 else None,
        renewal_total_premium=renewal_total if renewal_total > 0 else None,
        current_avg_premium=avg_current,
        renewal_avg_premium=avg_renewal,
        # Benefits
        individual_deductible=(current_plan.individual_deductible, 'similar'),
        family_deductible=(current_plan.family_deductible, 'similar'),
        individual_oop_max=(current_plan.individual_oop_max, 'similar'),
        family_oop_max=(current_plan.family_oop_max, 'similar'),
        coinsurance_pct=(current_coinsurance, 'similar'),
    )
    plans.append(current_col)

    # Build marketplace plan columns
    marketplace_totals = comparison_data.get('marketplace_totals', {})
    affordable_contributions = comparison_data.get('affordable_contributions', {})

    for mp in selected_plans:
        mp_total = marketplace_totals.get(mp.hios_plan_id, 0)
        mp_avg = mp_total / employee_count if employee_count > 0 and mp_total > 0 else None
        mp_coinsurance = mp.coinsurance_pct or 20

        # Get affordable contribution data
        contrib_data = affordable_contributions.get(mp.hios_plan_id, {})
        contrib_total = contrib_data.get('total') if contrib_data else None
        contrib_min = contrib_data.get('min', 0)
        contrib_max = contrib_data.get('max', 0)
        contrib_range = f"${contrib_min:,.0f}–${contrib_max:,.0f}/ee" if contrib_data and contrib_min != contrib_max else ""

        # Calculate comparisons for each benefit
        def get_comparison(current_val, mp_val, lower_is_better=True):
            if current_val is None or mp_val is None:
                return 'similar'
            return compare_benefit(current_val, mp_val, lower_is_better)

        # Premium comparisons - EXACT same logic as UI (NOT compare_benefit!)
        # UI uses absolute $ thresholds, not percentage thresholds

        # Age 21 Premium comparison using threshold constant
        age_21_comparison = 'similar'  # Default if we can't calculate
        if mp.age_21_premium and renewal_age_21:
            diff = mp.age_21_premium - renewal_age_21
            if diff < -AGE_21_PREMIUM_THRESHOLD:
                age_21_comparison = 'better'
            elif diff > AGE_21_PREMIUM_THRESHOLD:
                age_21_comparison = 'worse'
            else:
                age_21_comparison = 'similar'

        # Total Premium comparison using threshold constant
        total_premium_comparison = 'similar'  # Default if we can't calculate
        if mp_total > 0 and renewal_total > 0:
            diff = mp_total - renewal_total
            if diff < -TOTAL_PREMIUM_THRESHOLD:
                total_premium_comparison = 'better'
            elif diff > TOTAL_PREMIUM_THRESHOLD:
                total_premium_comparison = 'worse'
            else:
                total_premium_comparison = 'similar'

        # Categorical comparisons - EXACT same logic as UI (lines 1958-1960):
        # comparison = 'better' if current_value == mp_value else 'similar'
        plan_type_comparison = 'better' if mp.plan_type == current_plan.plan_type else 'similar'
        hsa_comparison = 'better' if mp.hsa_eligible == current_plan.hsa_eligible else 'similar'

        mp_col = PlanColumnData(
            plan_name=mp.plan_name,
            issuer_name=mp.issuer_name or "",
            plan_type=(mp.plan_type, plan_type_comparison),  # Tuple with comparison
            metal_level=mp.metal_level,
            hsa_eligible=(mp.hsa_eligible, hsa_comparison),
            actuarial_value=mp.actuarial_value,
            is_current=False,
            age_21_premium=mp.age_21_premium,
            age_21_premium_comparison=age_21_comparison,  # Same logic as UI
            total_premium=mp_total if mp_total > 0 else None,
            total_premium_comparison=total_premium_comparison,  # Same logic as UI
            avg_premium=mp_avg,
            affordable_contribution=contrib_total,
            contribution_range=contrib_range,
            individual_deductible=(mp.individual_deductible, get_comparison(current_plan.individual_deductible, mp.individual_deductible)),
            family_deductible=(mp.family_deductible, get_comparison(current_plan.family_deductible, mp.family_deductible)),
            individual_oop_max=(mp.individual_oop_max, get_comparison(current_plan.individual_oop_max, mp.individual_oop_max)),
            family_oop_max=(mp.family_oop_max, get_comparison(current_plan.family_oop_max, mp.family_oop_max)),
            coinsurance_pct=(mp_coinsurance, get_comparison(current_coinsurance, mp_coinsurance)),
        )
        plans.append(mp_col)

    return PlanComparisonSlideData(
        plans=plans,
        employee_count=employee_count,
        avg_age=comparison_data.get('avg_age', 0),
        footnote=comparison_data.get('footnote', ''),
        client_name=st.session_state.get('client_name', ''),
    )


def generate_comparison_csv(current_plan: CurrentEmployerPlan,
                            selected_plans: List[MarketplacePlanDetails]) -> str:
    """Generate CSV content for comparison export."""
    import io

    # Build header - use full plan names, no truncation
    headers = ['Benefit', f'Current Plan: {current_plan.plan_name}']
    for mp in selected_plans:
        headers.append(f"{mp.metal_level}: {mp.plan_name}")

    # Get coinsurance percentages
    current_coinsurance = current_plan.coinsurance_pct

    # Build rows
    csv_rows = []

    # Add premium row first (use getattr for backwards compatibility)
    current_premium = getattr(current_plan, 'current_premium', None)
    renewal_premium = getattr(current_plan, 'renewal_premium', None)

    if current_premium and renewal_premium:
        current_premium_str = f"${current_premium:,.0f} / ${renewal_premium:,.0f}"
    elif current_premium:
        current_premium_str = f"${current_premium:,.0f}"
    elif renewal_premium:
        current_premium_str = f"${renewal_premium:,.0f}"
    else:
        current_premium_str = "N/A"

    premium_row = ['Monthly Premium (Age 21)', current_premium_str]
    for mp in selected_plans:
        if mp.age_21_premium:
            premium_row.append(f"${mp.age_21_premium:,.0f}")
        else:
            premium_row.append("N/A")
    csv_rows.append(premium_row)

    # Add benefit comparison rows
    for attr, label, lower_is_better in COMPARISON_BENEFIT_ROWS:
        attr_coinsurance = get_coinsurance_for_attr(current_plan, attr)
        is_combined = is_combined_copay_coinsurance(current_plan, attr)
        row = [label, format_value(get_plan_value(current_plan, attr), attr, attr_coinsurance, is_combined)]
        for mp in selected_plans:
            mp_coinsurance = mp.coinsurance_pct or 20
            row.append(format_value(get_plan_value(mp, attr), attr, mp_coinsurance))
        csv_rows.append(row)

    # Create CSV
    output = io.StringIO()
    import csv
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(csv_rows)

    return output.getvalue()


def get_metal_badge_color(metal_level: str) -> str:
    """Get badge background color for metal level."""
    colors = {
        'Bronze': '#d97706',      # amber-600
        'Expanded Bronze': '#d97706',
        'Silver': '#6366f1',      # indigo-500
        'Gold': '#059669',        # emerald-600
        'Platinum': '#7c3aed',    # violet-600
        'Catastrophic': '#64748b', # slate-500
    }
    return colors.get(metal_level, '#6b7280')  # gray-500 default


def get_cell_bg_color(comparison: str) -> str:
    """Get cell background color based on comparison result."""
    colors = {
        'better': '#ecfdf5',   # emerald-50
        'similar': '#E8F1FD',  # cobalt-50
        'worse': '#fef2f2',    # red-50
    }
    return colors.get(comparison, '#f9fafb')  # gray-50 default


def render_stage_3_comparison_table():
    """Render the side-by-side benefit comparison table."""
    is_marketplace_only = st.session_state.comparison_mode == "Marketplace Only"

    # Adjust header based on mode
    if is_marketplace_only:
        stage_title = "Stage 2: Benefit Comparison"
        stage_desc = "Side-by-side comparison of selected marketplace plans. First plan selected is used as baseline."
    else:
        stage_title = "Stage 3: Benefit Comparison"
        stage_desc = "Side-by-side comparison of your current plan with selected marketplace alternatives."

    st.markdown(f'''
    <div class="stage-header">
        <p class="stage-title">{stage_title}</p>
        <p class="stage-description">{stage_desc}</p>
    </div>
    ''', unsafe_allow_html=True)

    # Get selected marketplace plans
    selected_plan_ids = st.session_state.selected_comparison_plans

    # Find the selected plans from search results
    selected_plans = []
    if st.session_state.search_results:
        for result in st.session_state.search_results:
            if result['plan'].hios_plan_id in selected_plan_ids:
                selected_plans.append(result['plan'])

    if not selected_plans:
        st.warning("No plans selected for comparison. Go back to select plans.")
        if st.button("Back to Select Plans"):
            st.session_state.comparison_stage = 2
            st.rerun()
        return

    # In Marketplace Only mode, use first selected plan as baseline
    if is_marketplace_only:
        if len(selected_plans) < 2:
            st.warning("Select at least 2 plans to compare in Marketplace Only mode.")
            if st.button("Back to Select Plans"):
                st.session_state.comparison_stage = 2
                st.rerun()
            return

        baseline_mp = selected_plans[0]  # First plan is baseline
        comparison_plans = selected_plans[1:]  # Rest are compared against baseline

        # Create a "fake" CurrentEmployerPlan from the baseline marketplace plan
        current_plan = CurrentEmployerPlan(
            plan_name=baseline_mp.plan_name,
            carrier=baseline_mp.issuer_name,
            plan_type=baseline_mp.plan_type,
            hsa_eligible=baseline_mp.hsa_eligible,
            current_premium=baseline_mp.age_21_premium,
            renewal_premium=baseline_mp.age_21_premium,
            individual_deductible=baseline_mp.individual_deductible,
            family_deductible=baseline_mp.family_deductible,
            individual_oop_max=baseline_mp.individual_oop_max,
            family_oop_max=baseline_mp.family_oop_max,
            coinsurance_pct=baseline_mp.coinsurance_pct,
            pcp_copay=baseline_mp.pcp_copay,
            specialist_copay=baseline_mp.specialist_copay,
            er_copay=baseline_mp.er_copay,
            generic_rx_copay=baseline_mp.generic_rx_copay,
            preferred_rx_copay=baseline_mp.preferred_rx_copay,
            specialty_rx_copay=baseline_mp.specialty_rx_copay,
        )
        selected_plans = comparison_plans
        baseline_label = "Baseline"
    else:
        current_plan = st.session_state.current_employer_plan
        baseline_label = "Current plan"

    num_plans = len(selected_plans)
    current_coinsurance = current_plan.coinsurance_pct

    # Build the HTML table
    # CSS for the comparison table
    table_css = """
    <style>
    .comparison-container {
        font-family: 'Poppins', sans-serif;
        background: white;
        border-radius: 16px;
        overflow: hidden;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        margin: 16px 0;
    }
    .comparison-legend {
        padding: 24px 32px 16px;
        display: flex;
        align-items: center;
        gap: 24px;
        font-size: 14px;
    }
    .legend-item {
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .legend-box {
        width: 16px;
        height: 16px;
        border-radius: 4px;
    }
    .legend-box.better { background: #ecfdf5; border: 1px solid #a7f3d0; }
    .legend-box.similar { background: #E8F1FD; border: 1px solid #B3D4FC; }
    .legend-box.worse { background: #fef2f2; border: 1px solid #fecaca; }
    .legend-text { color: #6b7280; }

    .comparison-table {
        width: 100%;
        border-collapse: collapse;
        table-layout: fixed;
    }
    .comparison-table th {
        padding: 16px 12px;
        text-align: center;
        vertical-align: top;
        border-bottom: 1px solid #e5e7eb;
        word-wrap: break-word;
        overflow-wrap: break-word;
    }
    .comparison-table th:first-child {
        width: 140px;
        text-align: left;
        padding-left: 24px;
    }
    .comparison-table th.current-plan {
        background: #f9fafb;
    }
    .plan-header {
        display: flex;
        flex-direction: column;
        align-items: center;
        height: 100%;
        min-height: 180px;
    }
    .plan-header .plan-chip {
        margin-top: auto;
    }
    .plan-metal {
        font-weight: 600;
        font-size: 15px;
    }
    .plan-name {
        font-weight: 400;
        color: #374151;
        font-size: 12px;
        line-height: 1.4;
        word-wrap: break-word;
        overflow-wrap: break-word;
    }
    .current-label {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 9999px;
        font-size: 11px;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: white;
        background: #374151;
        margin-top: 4px;
    }

    .section-row td {
        padding: 12px 24px;
        background: #f9fafb;
        border-bottom: 1px solid #e5e7eb;
    }
    .section-label {
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: #6b7280;
        font-weight: 500;
    }

    .comparison-table td {
        padding: 14px 12px;
        text-align: center;
        border-bottom: 1px solid #f3f4f6;
        font-size: 14px;
        word-wrap: break-word;
        overflow-wrap: break-word;
    }
    .comparison-table td:first-child {
        text-align: left;
        padding-left: 24px;
        color: #374151;
    }
    .comparison-table td.current-col {
        background: #f9fafb;
    }
    .comparison-table td:first-child {
        font-weight: 600;
    }
    .cell-value {
        font-weight: 400;
        color: #111827;
        font-size: 14px;
    }
    .cell-detail {
        font-size: 12px;
        color: #6b7280;
        font-weight: 400;
        margin-top: 2px;
    }
    .plan-chip {
        display: inline-block;
        padding: 6px 16px;
        border-radius: 9999px;
        font-size: 12px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: white;
        margin-top: 8px;
    }
    .plan-av {
        font-size: 13px;
        color: #6b7280;
        margin: 4px 0;
    }
    .plan-issuer {
        font-size: 13px;
        color: #374151;
        font-weight: 500;
        margin: 4px 0;
    }
    </style>
    """

    # Build header row HTML - use single lines to avoid Streamlit HTML parsing issues
    header_html = '<tr><th></th>'

    # Baseline/Current plan header - plan name, carrier, label, chip with plan type
    current_name = current_plan.plan_name or ('Baseline Plan' if is_marketplace_only else 'Current Plan')
    current_carrier = current_plan.carrier or ''
    current_type = current_plan.plan_type or ('Marketplace' if is_marketplace_only else 'Group')
    carrier_html = f'<div class="plan-issuer">{current_carrier}</div>' if current_carrier else ''
    header_html += f'<th class="current-plan"><div class="plan-header"><div class="plan-name" style="font-weight: 600; font-size: 14px;">{current_name}</div>{carrier_html}<div class="plan-issuer">{baseline_label}</div><span class="plan-chip" style="background: #374151;">{current_type}</span></div></th>'

    # Marketplace plan headers - plan name, issuer, plan ID, AV%, chip with metal level + HSA
    for mp in selected_plans:
        badge_color = get_metal_badge_color(mp.metal_level)
        mp_name = mp.plan_name or 'Unknown Plan'
        mp_issuer = mp.issuer_name or ''
        mp_plan_id = mp.hios_plan_id or ''

        # Build AV display
        if mp.actuarial_value:
            av_html = f'<div class="plan-av">{mp.actuarial_value:.0f}% AV</div>'
        else:
            av_html = ''

        # Build issuer display
        issuer_html = f'<div class="plan-issuer">{mp_issuer}</div>' if mp_issuer else ''

        # Build plan ID display (smaller font, muted color)
        plan_id_html = f'<div style="font-size: 10px; color: #9ca3af; font-family: monospace; margin-top: 2px;">{mp_plan_id}</div>' if mp_plan_id else ''

        # Build chip text - METAL • HSA or just METAL
        chip_text = mp.metal_level.upper()
        if mp.hsa_eligible:
            chip_text += ' • HSA'

        # Group AV and chip at bottom with margin-top: auto
        header_html += f'<th><div class="plan-header"><div class="plan-name" style="font-weight: 600; font-size: 14px;">{mp_name}</div>{issuer_html}{plan_id_html}<div style="margin-top: auto;">{av_html}<span class="plan-chip" style="background: {badge_color};">{chip_text}</span></div></div></th>'

    header_html += '</tr>'

    # Build body rows HTML
    body_html = ''

    # Premium section (special handling - not in standard sections loop)
    body_html += f'<tr class="section-row"><td colspan="{num_plans + 2}"><div class="section-label">Monthly Premium (EE-Only)</div></td></tr>'

    # Current plan premium display - used for comparison calculations
    # Age 21 Premium is a marketplace concept, not applicable to group plans
    current_prem = getattr(current_plan, 'current_premium', None)
    renewal_prem = getattr(current_plan, 'renewal_premium', None)

    body_html += '<tr>'
    body_html += '<td>Age 21 Premium</td>'
    # Show current plan premium with note that it's a flat rate (not age-banded like marketplace)
    display_prem = renewal_prem if renewal_prem else current_prem
    if display_prem:
        body_html += f'<td class="current-col"><div class="cell-value">${display_prem:,.0f}</div><div class="cell-detail" style="color: #6b7280;">(EE-only, all ages)</div></td>'
    else:
        body_html += '<td class="current-col"><div class="cell-value">—</div></td>'

    # Marketplace plan premiums
    for mp in selected_plans:
        if mp.age_21_premium:
            # Compare to renewal premium if available
            if renewal_prem:
                diff = mp.age_21_premium - renewal_prem
                if diff < -AGE_21_PREMIUM_THRESHOLD:
                    comparison = 'better'
                    diff_text = f'<div class="cell-detail" style="color: #059669;">${abs(diff):,.0f} less</div>'
                elif diff > AGE_21_PREMIUM_THRESHOLD:
                    comparison = 'worse'
                    diff_text = f'<div class="cell-detail" style="color: #dc2626;">${diff:,.0f} more</div>'
                else:
                    comparison = 'similar'
                    diff_text = ''
                mp_premium_display = f'<div class="cell-value">${mp.age_21_premium:,.0f}</div>{diff_text}'
            else:
                comparison = 'similar'
                mp_premium_display = f'<div class="cell-value">${mp.age_21_premium:,.0f}</div>'
        else:
            mp_premium_display = '<div class="cell-value">—</div>'
            comparison = 'similar'

        bg_color = get_cell_bg_color(comparison)
        body_html += f'<td style="background: {bg_color};">{mp_premium_display}</td>'

    body_html += '</tr>'

    # Total Monthly Premium row (if census data available)
    census_df = st.session_state.get('census_df')
    location = st.session_state.get('comparison_location')
    has_census = census_df is not None and not census_df.empty and location and location.rating_area_id

    # Initialize variables for use in comparison export data
    employee_ages = []
    employee_data = []
    current_total = 0.0
    renewal_total = 0.0
    marketplace_totals = {}
    affordable_contributions = {}
    footnote_lines = []

    # Show info message if census data is missing
    if not has_census:
        missing = []
        if census_df is None or (census_df is not None and census_df.empty):
            missing.append("census data (upload on Page 1)")
        if not location or not location.rating_area_id:
            missing.append("rating area (enter ZIP in Stage 2)")
        if missing:
            body_html += f'<tr><td colspan="{num_plans + 2}" style="padding: 12px 24px; font-size: 12px; color: #6b7280; font-style: italic;">Total Premium and Affordable Contribution rows require: {", ".join(missing)}</td></tr>'

    if has_census:
        # Calculate current plan totals from census - flexible column matching
        current_total = 0.0
        renewal_total = 0.0

        # Find EE, ER, and 2026 Premium columns (flexible matching)
        ee_col = None
        er_col = None
        renewal_col = None
        for col in census_df.columns:
            col_lower = col.lower().strip()
            # Current EE Monthly
            if ee_col is None and 'ee' in col_lower and 'monthly' in col_lower:
                ee_col = col
            elif ee_col is None and col_lower in ['current ee monthly', 'ee monthly']:
                ee_col = col
            # Current ER Monthly
            if er_col is None and 'er' in col_lower and 'monthly' in col_lower:
                er_col = col
            elif er_col is None and col_lower in ['current er monthly', 'er monthly']:
                er_col = col
            # 2026 Premium (renewal)
            if renewal_col is None and '2026' in col_lower and 'premium' in col_lower:
                renewal_col = col
            elif renewal_col is None and col_lower in ['2026 premium', '2026_premium', 'renewal premium']:
                renewal_col = col

        # Calculate current total (EE + ER)
        if ee_col or er_col:
            ee_sum = census_df[ee_col].sum() if ee_col and census_df[ee_col].notna().any() else 0
            er_sum = census_df[er_col].sum() if er_col and census_df[er_col].notna().any() else 0
            current_total = float(ee_sum) + float(er_sum)

        # Calculate renewal total - prefer 2026 Premium column if available
        if renewal_col and census_df[renewal_col].notna().any():
            renewal_total = float(census_df[renewal_col].sum())
        elif current_total > 0:
            # Fall back to applying ratio from individual premiums
            if current_prem and renewal_prem and current_prem > 0:
                renewal_ratio = renewal_prem / current_prem
                renewal_total = current_total * renewal_ratio
            else:
                renewal_total = current_total

        # Calculate marketplace plan totals - get rates for all employee ages
        # Find DOB column (flexible matching)
        dob_col = None
        for col in census_df.columns:
            col_lower = col.lower()
            if 'ee' in col_lower and 'dob' in col_lower:
                dob_col = col
                break
            elif col_lower in ['dob', 'date of birth', 'birth date', 'ee dob']:
                dob_col = col
                break

        # Find Monthly Income column for affordability calculation
        income_col = None
        for col in census_df.columns:
            col_lower = col.lower().strip()
            if 'monthly' in col_lower and 'income' in col_lower:
                income_col = col
                break
            elif col_lower in ['monthly income', 'income', 'monthly_income']:
                income_col = col
                break

        # Build employee data: list of (age_band, monthly_income) tuples
        employee_data = []
        if dob_col:
            from utils import calculate_age_from_dob
            for idx, row in census_df.iterrows():
                dob = row.get(dob_col)
                if pd.isna(dob):
                    continue
                try:
                    age = calculate_age_from_dob(dob)
                    if age:
                        # Convert to age band
                        if age <= 14:
                            age_band = '0-14'
                        elif age >= 64:
                            age_band = '64 and over'
                        else:
                            age_band = str(age)

                        # Get monthly income (default to 0 if not available)
                        monthly_income = 0
                        if income_col and not pd.isna(row.get(income_col)):
                            try:
                                monthly_income = float(row.get(income_col))
                            except (ValueError, TypeError):
                                pass

                        employee_data.append((age_band, monthly_income))
                        employee_ages.append(age)
                except:
                    pass

        # Query rates for all ages for these plans
        marketplace_totals = {}
        affordable_contributions = {}  # {plan_id: {'avg': x, 'min': y, 'max': z}}
        rate_lookup = {}

        if employee_data and selected_plans:
            db = get_database_connection()
            if db:
                plan_ids = [mp.hios_plan_id for mp in selected_plans]
                # Get unique age bands
                age_bands = [ed[0] for ed in employee_data]
                unique_ages = list(set(age_bands))

                # Query rates for all age bands
                rates_query = f"""
                SELECT plan_id, age, individual_rate
                FROM rbis_insurance_plan_base_rates_20251019202724
                WHERE plan_id IN ({', '.join(['%s'] * len(plan_ids))})
                  AND rating_area_id = %s
                  AND age IN ({', '.join(['%s'] * len(unique_ages))})
                  AND rate_effective_date = '2026-01-01'
                """
                params = tuple(plan_ids) + (f"Rating Area {location.rating_area_id}",) + tuple(unique_ages)
                try:
                    rates_df = db.execute_query(rates_query, params)
                    if not rates_df.empty:
                        # Build rate lookup: {plan_id: {age: rate}}
                        for _, row in rates_df.iterrows():
                            pid = row['plan_id']
                            age_str = row['age']
                            rate = float(row['individual_rate']) if row['individual_rate'] else 0
                            if pid not in rate_lookup:
                                rate_lookup[pid] = {}
                            rate_lookup[pid][age_str] = rate

                        # Calculate total and affordable contributions for each plan
                        AFFORDABILITY_THRESHOLD = 0.0996  # 9.96% for 2026

                        for mp in selected_plans:
                            total = 0.0
                            contributions = []

                            for age_band, monthly_income in employee_data:
                                rate = rate_lookup.get(mp.hios_plan_id, {}).get(age_band, 0)
                                total += rate

                                # Calculate affordable contribution
                                # Employee can afford: monthly_income * 9.96%
                                # Employer must contribute: premium - affordable_amount
                                if monthly_income > 0 and rate > 0:
                                    affordable_amount = monthly_income * AFFORDABILITY_THRESHOLD
                                    required_contribution = max(0, rate - affordable_amount)
                                    contributions.append(required_contribution)

                            marketplace_totals[mp.hios_plan_id] = total

                            if contributions:
                                affordable_contributions[mp.hios_plan_id] = {
                                    'total': sum(contributions),
                                    'avg': sum(contributions) / len(contributions),
                                    'min': min(contributions),
                                    'max': max(contributions),
                                }
                except Exception as e:
                    pass  # Silently fail, will show N/A

        # Build the Affordable Contribution row (if income data available)
        has_income_data = any(inc > 0 for _, inc in employee_data)
        if has_income_data and affordable_contributions:
            body_html += '<tr>'
            body_html += '<td>Affordable Contribution*</td>'
            body_html += '<td class="current-col"><div class="cell-value">—</div></td>'

            for mp in selected_plans:
                contrib_data = affordable_contributions.get(mp.hios_plan_id)
                if contrib_data:
                    total_c = contrib_data['total']
                    min_c = contrib_data['min']
                    max_c = contrib_data['max']
                    # Show total with per-employee range below
                    range_text = f'<div class="cell-detail">${min_c:,.0f} – ${max_c:,.0f}/ee</div>' if min_c != max_c else ''
                    contrib_display = f'<div class="cell-value">${total_c:,.0f}</div>{range_text}'
                else:
                    contrib_display = '<div class="cell-value">—</div>'
                body_html += f'<td>{contrib_display}</td>'

            body_html += '</tr>'

        # Build the Total row
        body_html += '<tr>'
        # Include employee count and average age context in the label
        employee_count = len(census_df)
        avg_age_text = ''
        if employee_ages:
            avg_age = sum(employee_ages) / len(employee_ages)
            avg_age_text = f'<div class="cell-detail">{employee_count} employees, avg age {avg_age:.0f}</div>'
        elif employee_count > 0:
            avg_age_text = f'<div class="cell-detail">{employee_count} employees</div>'
        body_html += f'<td>Total Monthly Premium*{avg_age_text}</td>'

        # Current plan total
        if current_total > 0:
            if renewal_total > 0 and renewal_total != current_total:
                avg_current = current_total / employee_count
                avg_renewal = renewal_total / employee_count
                current_total_display = f'<div class="cell-value">${current_total:,.0f} / ${renewal_total:,.0f}</div><div class="cell-detail">${avg_current:,.0f} / ${avg_renewal:,.0f} avg</div>'
            else:
                avg_current = current_total / employee_count
                current_total_display = f'<div class="cell-value">${current_total:,.0f}</div><div class="cell-detail">${avg_current:,.0f} avg</div>'
        else:
            current_total_display = '<div class="cell-value">—</div>'
        body_html += f'<td class="current-col">{current_total_display}</td>'

        # Marketplace plan totals
        for mp in selected_plans:
            mp_total = marketplace_totals.get(mp.hios_plan_id, 0)
            if mp_total > 0:
                mp_avg = mp_total / employee_count
                avg_text = f'<div class="cell-detail">${mp_avg:,.0f} avg</div>'
                # Compare to renewal total if available
                if renewal_total > 0:
                    diff = mp_total - renewal_total
                    if diff < -TOTAL_PREMIUM_THRESHOLD:
                        comparison = 'better'
                        diff_text = f'<div class="cell-detail" style="color: #059669;">${abs(diff):,.0f} less</div>'
                    elif diff > TOTAL_PREMIUM_THRESHOLD:
                        comparison = 'worse'
                        diff_text = f'<div class="cell-detail" style="color: #dc2626;">${diff:,.0f} more</div>'
                    else:
                        comparison = 'similar'
                        diff_text = ''
                    mp_total_display = f'<div class="cell-value">${mp_total:,.0f}</div>{diff_text}{avg_text}'
                else:
                    comparison = 'similar'
                    mp_total_display = f'<div class="cell-value">${mp_total:,.0f}</div>{avg_text}'
            else:
                mp_total_display = '<div class="cell-value">—</div>'
                comparison = 'similar'

            bg_color = get_cell_bg_color(comparison)
            body_html += f'<td style="background: {bg_color};">{mp_total_display}</td>'

        body_html += '</tr>'

    # Define sections - Plan Features first, then Deductibles, then Copays
    sections = [
        ('Plan Features', [
            ('plan_type', 'Plan Type', False),
            ('hsa_eligible', 'HSA Eligible', False),
            ('coinsurance_pct', 'Coinsurance', True),
        ]),
        ('Deductibles & Out-of-Pocket', [
            ('individual_deductible', 'Deductible (Individual)', True),
            ('family_deductible', 'Deductible (Family)', True),
            ('individual_oop_max', 'OOP Max (Individual)', True),
            ('family_oop_max', 'OOP Max (Family)', True),
        ]),
        ('Coverage & Copays', [
            ('pcp_copay', 'PCP Visit', True),
            ('specialist_copay', 'Specialist Visit', True),
            ('er_copay', 'ER Visit', True),
            ('generic_rx_copay', 'Generic Rx', True),
            ('preferred_rx_copay', 'Preferred Brand Rx', True),
            ('specialty_rx_copay', 'Specialty Rx', True),
        ]),
    ]

    for section_name, benefits in sections:
        # Section header row - single line to avoid Streamlit HTML parsing issues
        body_html += f'<tr class="section-row"><td colspan="{num_plans + 2}"><div class="section-label">{section_name}</div></td></tr>'

        for attr, label, lower_is_better in benefits:
            # Get current plan value
            current_value = get_plan_value(current_plan, attr)
            attr_coinsurance = get_coinsurance_for_attr(current_plan, attr)
            is_combined = is_combined_copay_coinsurance(current_plan, attr)
            current_display = format_value(current_value, attr, attr_coinsurance, is_combined)

            body_html += '<tr>'
            body_html += f'<td>{label}</td>'
            body_html += f'<td class="current-col"><span class="cell-value">{current_display}</span></td>'

            # Marketplace plan values
            for mp in selected_plans:
                mp_value = get_plan_value(mp, attr)
                mp_coinsurance = mp.coinsurance_pct or 20
                mp_display = format_value(mp_value, attr, mp_coinsurance)

                # Determine comparison color
                if 'copay' in attr:
                    # Use structure-aware copay comparison
                    comparison = compare_copay_benefit(
                        current_value=current_value,
                        current_coinsurance=attr_coinsurance,
                        is_combined=is_combined,
                        mp_value=mp_value,
                        mp_coinsurance=mp_coinsurance,
                        mp_actuarial_value=mp.actuarial_value
                    )
                elif current_value is not None and mp_value is not None:
                    if lower_is_better:
                        # Numeric comparison (deductibles, OOPM, etc.)
                        comparison = compare_benefit(current_value, mp_value, lower_is_better)
                    else:
                        # Categorical comparison (HSA, Plan Type) - equivalent = green
                        comparison = 'better' if current_value == mp_value else 'similar'
                else:
                    comparison = 'similar'

                bg_color = get_cell_bg_color(comparison)
                body_html += f'<td style="background: {bg_color};"><span class="cell-value">{mp_display}</span></td>'

            body_html += '</tr>'

    # Build footnote if census data was used
    footnote_html = ''
    if has_census:
        employee_count = len(employee_ages) if employee_ages else 0
        footnote_lines = []
        footnote_lines.append(f'*Assumes all {employee_count} employees are located in the selected rating area ({location.county}, {location.state} - Rating Area {location.rating_area_id}).')

        # Add affordability explanation if income data was available
        has_income_data = any(inc > 0 for _, inc in employee_data) if employee_data else False
        if has_income_data:
            footnote_lines.append('Affordable Contribution = minimum employer contribution to meet 9.96% IRS affordability threshold (Premium − Monthly Income × 9.96%).')

        footnote_html = f'<div style="padding: 12px 24px; font-size: 12px; color: #6b7280; line-height: 1.6;">{" ".join(footnote_lines)}</div>'

    # Store comparison data for export
    avg_age_calc = sum(employee_ages) / len(employee_ages) if employee_ages else 0
    comparison_export_data = {
        'employee_count': len(census_df) if has_census else 0,
        'avg_age': avg_age_calc,
        'current_total': current_total if has_census else 0,
        'renewal_total': renewal_total if has_census else 0,
        'marketplace_totals': marketplace_totals if has_census else {},
        'affordable_contributions': affordable_contributions if has_census else {},
        'footnote': " ".join(footnote_lines) if has_census else '',
    }

    # Combine into full table
    table_html = f'''
    {table_css}
    <div class="comparison-container">
        <div class="comparison-legend">
            <div class="legend-item">
                <div class="legend-box better"></div>
                <span class="legend-text">Equivalent or better</span>
            </div>
            <div class="legend-item">
                <div class="legend-box similar"></div>
                <span class="legend-text">Similar</span>
            </div>
            <div class="legend-item">
                <div class="legend-box worse"></div>
                <span class="legend-text">Less generous</span>
            </div>
        </div>
        <div style="overflow-x: auto;">
            <table class="comparison-table">
                <thead>{header_html}</thead>
                <tbody>{body_html}</tbody>
            </table>
        </div>
        {footnote_html}
    </div>
    '''

    st.markdown(table_html, unsafe_allow_html=True)

    # Match Score Summary - clean design matching the table
    st.markdown("---")
    st.markdown('<p class="section-header">Match Score Summary</p>', unsafe_allow_html=True)

    # Build match score cards HTML
    def get_score_color(score: float) -> str:
        if score >= 70:
            return '#059669'  # emerald-600
        elif score >= 50:
            return '#d97706'  # amber-600
        else:
            return '#dc2626'  # red-600

    def get_score_label(score: float) -> str:
        if score >= 70:
            return 'Strong match'
        elif score >= 50:
            return 'Moderate match'
        else:
            return 'Different'

    score_cards_html = '<div style="display: flex; gap: 16px; margin: 16px 0;">'
    for plan in selected_plans:
        score = plan.match_score
        color = get_score_color(score)
        label = get_score_label(score)
        score_cards_html += f'''<div style="flex: 1; background: white; border: 1px solid #e5e7eb; border-radius: 12px; padding: 20px; font-family: 'Poppins', sans-serif; display: flex; flex-direction: column; min-height: 120px;">
<div style="font-weight: 600; color: #111827; font-size: 14px; line-height: 1.4;">{plan.plan_name}</div>
<div style="display: flex; align-items: baseline; gap: 8px; margin-top: auto;">
<span style="font-size: 28px; font-weight: 700; color: {color};">{score:.0f}%</span>
<span style="font-size: 13px; color: #6b7280;">{label}</span>
</div>
</div>'''
    score_cards_html += '</div>'

    st.markdown(score_cards_html, unsafe_allow_html=True)

    # Explanation in expander
    with st.expander("How is the Match Score calculated?"):
        st.markdown("""
        The **Match Score** measures how similar a marketplace plan is to your current employer plan (0-100%).

        **Scoring weights:**
        - **Deductible similarity** (25%) - How close the individual deductible is to current plan
        - **Out-of-Pocket Max similarity** (25%) - How close the OOPM is to current plan
        - **Plan Type match** (15%) - PPO↔PPO scores higher than PPO↔HMO
        - **HSA eligibility match** (10%) - Penalty if current has HSA and marketplace doesn't
        - **Copay similarity** (25%) - PCP, Specialist, and Generic Rx copays compared

        **Score ranges:**
        - 🟢 **70%+** = Strong match - Very similar benefits structure
        - 🟡 **50-69%** = Moderate match - Some differences but comparable
        - 🔴 **Below 50%** = Different - Significantly different coverage
        """)

    # Export options
    st.markdown("---")
    st.markdown('<p class="section-header">Export</p>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)

    with col1:
        # Generate CSV
        csv_content = generate_comparison_csv(current_plan, selected_plans)
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Build filename with client name
        client_name = st.session_state.get('client_name', '').strip()
        if client_name:
            safe_name = client_name.replace(' ', '_').replace('/', '-')
            csv_filename = f"plan_comparison_{safe_name}_{timestamp}.csv"
            pptx_filename = f"plan_comparison_{safe_name}_{timestamp}.pptx"
        else:
            csv_filename = f"plan_comparison_{timestamp}.csv"
            pptx_filename = f"plan_comparison_{timestamp}.pptx"

        st.download_button(
            label="Export Comparison (CSV)",
            data=csv_content,
            file_name=csv_filename,
            mime="text/csv"
        )

    with col2:
        # Generate PowerPoint slide
        try:
            slide_data = build_slide_data(current_plan, selected_plans, comparison_export_data)
            pptx_buffer = generate_plan_comparison_slide(slide_data)
            st.download_button(
                label="Download Slide (PPTX)",
                data=pptx_buffer,
                file_name=pptx_filename,
                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation"
            )
        except Exception as e:
            st.button("Download Slide (PPTX)", disabled=True, help=f"Error generating slide: {e}")

    with col3:
        st.button("Export Comparison (PDF)", disabled=True, help="PDF export coming soon")

    # Navigation
    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Back to Stage 2"):
            st.session_state.comparison_stage = 2
            st.rerun()

    with col2:
        if st.button("Start New Comparison", type="primary"):
            # Reset state
            st.session_state.comparison_stage = 1
            st.session_state.selected_comparison_plans = []
            st.session_state.search_results = []

            # Clear all plan selection checkbox states
            keys_to_remove = [key for key in st.session_state.keys() if key.startswith('select_plan_')]
            for key in keys_to_remove:
                del st.session_state[key]

            st.rerun()


# ==============================================================================
# MAIN PAGE
# ==============================================================================

def main():
    """Main page function."""
    # Initialize session state
    init_session_state()

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

    # Page header
    st.markdown("""
    <div class="hero-section">
        <div class="hero-title">⚖️ Plan Comparison Tool</div>
        <p class="hero-subtitle">Compare your current employer group plan against marketplace alternatives</p>
    </div>
    """, unsafe_allow_html=True)

    # Comparison mode toggle
    mode_col1, mode_col2 = st.columns([2, 3])
    with mode_col1:
        comparison_mode = st.radio(
            "Comparison Mode",
            ["Compare to Current", "Marketplace Only"],
            horizontal=True,
            key="comparison_mode_radio",
            help="Compare to Current: compare marketplace plans against your current employer plan. Marketplace Only: compare marketplace plans against each other."
        )
        # Sync to session state
        if comparison_mode != st.session_state.comparison_mode:
            st.session_state.comparison_mode = comparison_mode
            # Reset to appropriate stage when mode changes
            if comparison_mode == "Marketplace Only":
                st.session_state.comparison_stage = 2  # Skip Stage 1
            else:
                st.session_state.comparison_stage = 1  # Start at Stage 1
            st.rerun()

    is_marketplace_only = st.session_state.comparison_mode == "Marketplace Only"

    # Progress indicator - adjust for mode
    if is_marketplace_only:
        stages = ["1. Select Plans", "2. Compare"]
        # Map internal stage numbers to display
        current_stage = st.session_state.comparison_stage
        display_stage = current_stage - 1 if current_stage >= 2 else 1  # Stage 2->1, Stage 3->2

        cols = st.columns(2)
        for i, (col, stage_name) in enumerate(zip(cols, stages), 1):
            with col:
                if i < display_stage:
                    st.markdown(f"**{stage_name}**")
                elif i == display_stage:
                    st.markdown(f"**{stage_name}**")
                else:
                    st.markdown(f"<span style='color: #9ca3af'>{stage_name}</span>", unsafe_allow_html=True)
    else:
        stages = ["1. Current Plan", "2. Select Plans", "3. Compare"]
        current_stage = st.session_state.comparison_stage

        cols = st.columns(3)
        for i, (col, stage_name) in enumerate(zip(cols, stages), 1):
            with col:
                if i < current_stage:
                    st.markdown(f"**{stage_name}**")
                elif i == current_stage:
                    st.markdown(f"**{stage_name}**")
                else:
                    st.markdown(f"<span style='color: #9ca3af'>{stage_name}</span>", unsafe_allow_html=True)

    st.markdown("---")

    # Render appropriate stage
    current_stage = st.session_state.comparison_stage

    # In Marketplace Only mode, skip Stage 1
    if is_marketplace_only and current_stage == 1:
        st.session_state.comparison_stage = 2
        current_stage = 2

    if current_stage == 1:
        render_stage_1_current_plan()
    elif current_stage == 2:
        render_stage_2_marketplace_selection()
    elif current_stage == 3:
        render_stage_3_comparison_table()


if __name__ == "__main__":
    main()
