"""
Page 3: Employer Summary
Aggregate cost analysis and census demographics for ICHRA contribution evaluation
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils import DataFormatter, ContributionComparison
from database import get_database_connection


st.set_page_config(page_title="Employer Summary", page_icon="📊", layout="wide")

# Initialize session state
if 'db' not in st.session_state:
    st.session_state.db = get_database_connection()

if 'census_df' not in st.session_state:
    st.session_state.census_df = None

if 'dependents_df' not in st.session_state:
    st.session_state.dependents_df = None

if 'contribution_analysis' not in st.session_state:
    st.session_state.contribution_analysis = {}

if 'contribution_settings' not in st.session_state:
    st.session_state.contribution_settings = {'default_percentage': 75}


# Page header
st.title("📊 Employer Summary")
st.markdown("Review aggregate costs, contribution analysis, and census demographics")

# Check prerequisites
if st.session_state.census_df is None:
    st.warning("⚠️ No employee census loaded. Please complete **Census Input** first.")
    st.info("👉 Go to **1️⃣ Census Input** in the sidebar to upload your census")
    st.stop()

st.markdown("---")

# Get census data
census_df = st.session_state.census_df
dependents_df = st.session_state.dependents_df

# Check if dependents are included
has_dependents = (dependents_df is not None and not dependents_df.empty)

# Check if per-employee contribution data exists
has_individual_contribs = ContributionComparison.has_individual_contributions(census_df)

# ============================================================================
# EXECUTIVE SUMMARY
# ============================================================================

st.subheader("📋 Executive Summary")

if has_dependents:
    # Four columns when dependents present
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Employees", len(census_df))

    with col2:
        num_dependents = len(dependents_df)
        st.metric("Total Dependents", num_dependents)

    with col3:
        total_covered_lives = len(census_df) + num_dependents
        st.metric("Covered Lives", total_covered_lives)

    with col4:
        unique_states = census_df['state'].nunique()
        st.metric("States", unique_states)

else:
    # Three columns for employee-only mode
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total Employees", len(census_df))

    with col2:
        unique_states = census_df['state'].nunique()
        st.metric("States", unique_states)

    with col3:
        unique_rating_areas = census_df['rating_area_id'].nunique()
        st.metric("Rating Areas", unique_rating_areas)

st.markdown("---")

# ============================================================================
# CURRENT VS PROPOSED ICHRA CONTRIBUTIONS
# ============================================================================

if has_individual_contribs:
    st.subheader("💰 Current Group Plan vs Proposed ICHRA Contributions")

    # Get contribution totals
    contrib_totals = ContributionComparison.aggregate_contribution_totals(census_df)

    # Get contribution settings
    contribution_pct = st.session_state.contribution_settings.get('default_percentage', 75)

    # Build summary table
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Current Group Plan Costs")
        st.metric(
            "Current ER Monthly",
            DataFormatter.format_currency(contrib_totals['total_current_er_monthly']),
            help="Sum of all employer contributions from census"
        )
        st.metric(
            "Current ER Annual",
            DataFormatter.format_currency(contrib_totals['total_current_er_annual'])
        )
        st.metric(
            "Current EE Monthly",
            DataFormatter.format_currency(contrib_totals['total_current_ee_monthly']),
            help="Sum of all employee contributions from census"
        )

        # Calculate and display average EE Monthly
        if contrib_totals['employees_with_data'] > 0:
            current_ee_avg = contrib_totals['total_current_ee_monthly'] / contrib_totals['employees_with_data']
            st.caption(f"Current EE Monthly Average: {DataFormatter.format_currency(current_ee_avg)}")

        st.metric(
            "Current EE Annual",
            DataFormatter.format_currency(contrib_totals['total_current_ee_annual'])
        )

        st.caption(f"Based on {contrib_totals['employees_with_data']} employees with contribution data")

    with col2:
        # Check if contribution analysis has been run
        if st.session_state.contribution_analysis:
            st.markdown("### Proposed ICHRA Budget")
            st.caption("💡 Based on Lowest Cost Silver Plan (LCSP) — IRS affordability benchmark")

            # Calculate proposed totals from contribution analysis
            proposed_er_monthly = 0.0
            proposed_ee_monthly = 0.0
            employees_analyzed = 0

            for emp_id, analysis in st.session_state.contribution_analysis.items():
                if 'ichra_analysis' in analysis and analysis['ichra_analysis']:
                    proposed_er_monthly += analysis['ichra_analysis'].get('employer_contribution', 0)
                    proposed_ee_monthly += analysis['ichra_analysis'].get('employee_cost', 0)
                    employees_analyzed += 1

            if employees_analyzed > 0:
                st.metric(
                    "Proposed ER Monthly",
                    DataFormatter.format_currency(proposed_er_monthly)
                )
                st.metric(
                    "Proposed ER Annual",
                    DataFormatter.format_currency(proposed_er_monthly * 12)
                )
                st.metric(
                    "Proposed EE Monthly",
                    DataFormatter.format_currency(proposed_ee_monthly)
                )

                # Calculate and display average EE Monthly
                if employees_analyzed > 0:
                    proposed_ee_avg = proposed_ee_monthly / employees_analyzed
                    st.caption(f"Proposed EE Monthly Average: {DataFormatter.format_currency(proposed_ee_avg)}")

                st.metric(
                    "Proposed EE Annual",
                    DataFormatter.format_currency(proposed_ee_monthly * 12)
                )

                st.caption(f"Based on LCSP for {employees_analyzed} employees")
            else:
                st.info("Apply a contribution strategy on Page 2 to see proposed ICHRA costs")
        else:
            st.markdown("### Proposed ICHRA Budget")
            st.info("""
            **Configure Contribution Strategy First**

            Go to **2️⃣ Contribution Evaluation** and use the **Contribution Strategy Modeler** to:
            1. Select a strategy (Base Age Curve, % of LCSP, or Fixed Tiers)
            2. Configure strategy parameters and modifiers
            3. Click **"Calculate"** to preview results
            4. Click **"Apply to Session"** to save

            This creates an ICHRA budget proposal based on the IRS affordability benchmark (LCSP).
            """)

    # Show change metrics below both columns (full width)
    if st.session_state.contribution_analysis:
        # Calculate proposed totals (need to recalculate outside col2 context)
        proposed_er_monthly = sum(
            analysis['ichra_analysis'].get('employer_contribution', 0)
            for analysis in st.session_state.contribution_analysis.values()
            if 'ichra_analysis' in analysis and analysis['ichra_analysis']
        )
        proposed_ee_monthly = sum(
            analysis['ichra_analysis'].get('employee_cost', 0)
            for analysis in st.session_state.contribution_analysis.values()
            if 'ichra_analysis' in analysis and analysis['ichra_analysis']
        )

        # Calculate changes
        er_change_monthly = proposed_er_monthly - contrib_totals['total_current_er_monthly']
        er_change_annual = er_change_monthly * 12
        ee_change_monthly = proposed_ee_monthly - contrib_totals['total_current_ee_monthly']
        ee_change_annual = ee_change_monthly * 12

        st.markdown("---")
        st.markdown("### Cost Impact Analysis")

        col_a, col_b = st.columns(2)

        with col_a:
            er_change_color = "normal" if er_change_annual < 0 else "inverse"
            st.metric(
                "Proposed ER Change (Annual)",
                DataFormatter.format_currency(er_change_annual, include_sign=True),
                delta=f"{er_change_annual:+,.0f}",
                delta_color=er_change_color
            )

        with col_b:
            ee_change_color = "normal" if ee_change_annual < 0 else "inverse"
            st.metric(
                "Proposed EE Change (Annual)",
                DataFormatter.format_currency(ee_change_annual, include_sign=True),
                delta=f"{ee_change_annual:+,.0f}",
                delta_color=ee_change_color
            )

        # Interpretation
        if er_change_annual < 0:
            st.success(f"💰 Potential annual employer savings of **{DataFormatter.format_currency(abs(er_change_annual))}** under ICHRA")
        elif er_change_annual > 0:
            st.warning(f"⚠️ ICHRA would cost employers **{DataFormatter.format_currency(er_change_annual)}** more annually")
        else:
            st.info("ICHRA employer costs approximately the same as current plan")

    # Detailed employee breakdown
    if st.session_state.contribution_analysis:
        with st.expander("📋 View Employee-Level Comparison", expanded=False):
            comparison_rows = []

            for emp_id, analysis in st.session_state.contribution_analysis.items():
                emp_data = census_df[census_df['employee_id'] == emp_id]
                if emp_data.empty:
                    continue

                emp = emp_data.iloc[0]
                current_ee = emp.get('current_ee_monthly')
                current_er = emp.get('current_er_monthly')

                ichra_data = analysis.get('ichra_analysis', {})
                proposed_ee = ichra_data.get('employee_cost', 0)
                proposed_er = ichra_data.get('employer_contribution', 0)
                lcsp_premium = ichra_data.get('monthly_premium', 0)

                # Calculate changes and totals
                ee_change = None
                er_change = None
                total_change = None

                if pd.notna(current_ee):
                    ee_change = proposed_ee - current_ee
                if pd.notna(current_er):
                    er_change = proposed_er - current_er

                # Calculate totals
                current_total = None
                if pd.notna(current_ee) and pd.notna(current_er):
                    current_total = current_ee + current_er
                    total_change = lcsp_premium - current_total

                comparison_rows.append({
                    'Employee ID': emp_id,
                    'Age': int(emp.get('age', 0)) if pd.notna(emp.get('age')) else 'N/A',
                    'State': emp.get('state', 'N/A'),
                    'County': emp.get('county', 'N/A'),
                    'Rating Area': emp.get('rating_area_id', 'N/A'),
                    'Family Status': emp.get('family_status', 'EE'),
                    'LCSP Plan ID': ichra_data.get('plan_id', 'N/A'),
                    'LCSP Plan Name': ichra_data.get('plan_name', 'N/A'),
                    'LCSP Premium': DataFormatter.format_currency(lcsp_premium),
                    'Current EE': DataFormatter.format_currency(current_ee) if pd.notna(current_ee) else 'N/A',
                    'Current ER': DataFormatter.format_currency(current_er) if pd.notna(current_er) else 'N/A',
                    'Current Total': DataFormatter.format_currency(current_total) if current_total is not None else 'N/A',
                    'ICHRA ER': DataFormatter.format_currency(proposed_er),
                    'ICHRA EE': DataFormatter.format_currency(proposed_ee),
                    'ER Change': DataFormatter.format_currency(er_change, include_sign=True) if er_change is not None else 'N/A',
                    'EE Change': DataFormatter.format_currency(ee_change, include_sign=True) if ee_change is not None else 'N/A',
                    'Total Change': DataFormatter.format_currency(total_change, include_sign=True) if total_change is not None else 'N/A',
                })

            if comparison_rows:
                comparison_df = pd.DataFrame(comparison_rows)
                st.dataframe(comparison_df, width="stretch", hide_index=True)
                st.caption("Negative change = savings, Positive change = increase")
            else:
                st.info("No employee comparisons available")

else:
    st.subheader("💰 Contribution Summary")
    st.info("""
    **No per-employee contribution data in census**

    To see current vs ICHRA cost comparison:
    1. Add **Current EE Monthly** and **Current ER Monthly** columns to your census
    2. Re-upload on the Census Input page

    These optional columns enable:
    - Per-employee cost comparison
    - Aggregate savings analysis
    - ROI calculations
    """)

st.markdown("---")

# ============================================================================
# CONTRIBUTION SETTINGS SUMMARY
# ============================================================================

st.subheader("⚙️ Contribution Settings")

settings = st.session_state.contribution_settings
contribution_type = settings.get('contribution_type', 'percentage')

if contribution_type == 'class_based':
    strategy_name = settings.get('strategy_name', 'Class-Based')
    st.markdown(f"**Strategy:** {strategy_name}")
    st.markdown(f"**Total Monthly:** ${settings.get('total_monthly', 0):,.2f}")
    st.markdown(f"**Total Annual:** ${settings.get('total_annual', 0):,.2f}")
    st.markdown(f"**Employees Assigned:** {settings.get('employees_assigned', 0)}")

    if settings.get('apply_family_multipliers'):
        st.markdown("**Family Multipliers:** Enabled (EE=1.0x, ES=1.5x, EC=1.3x, F=1.8x)")

    # Show tier summary if available
    if settings.get('strategy_applied') == 'age_banded' and settings.get('tiers'):
        st.markdown("**Age Tiers:**")
        for tier in settings['tiers']:
            st.markdown(f"- {tier['age_range']}: ${tier['contribution']:.0f}/mo")
    elif settings.get('strategy_applied') == 'location_based' and settings.get('tiers'):
        st.markdown("**Location Tiers:**")
        for tier in settings['tiers']:
            st.markdown(f"- {tier['location']}: ${tier['contribution']:.0f}/mo")

else:
    contribution_pct = settings.get('default_percentage', 75)
    st.markdown(f"**Contribution Type:** Percentage")
    st.markdown(f"**Employer Contribution:** {contribution_pct}%")

    if 'by_class' in settings and settings['by_class']:
        st.markdown("**By Employee Class:**")
        for class_name, pct in settings['by_class'].items():
            st.markdown(f"- {class_name}: {pct}%")

st.markdown("---")

# ============================================================================
# CENSUS DEMOGRAPHICS
# ============================================================================

st.subheader("👥 Census Demographics")

# Employee age distribution
col1, col2 = st.columns(2)

with col1:
    # Age distribution
    age_bins = [0, 30, 40, 50, 60, 100]
    age_labels = ['Under 30', '30-39', '40-49', '50-59', '60+']

    age_col = 'employee_age' if 'employee_age' in census_df.columns else 'age'
    census_with_age_group = census_df.copy()
    census_with_age_group['age_group'] = pd.cut(
        census_with_age_group[age_col],
        bins=age_bins,
        labels=age_labels,
        right=False
    )

    age_dist = census_with_age_group['age_group'].value_counts().sort_index()

    fig = px.pie(
        values=age_dist.values,
        names=age_dist.index,
        title='Employee Age Distribution'
    )

    st.plotly_chart(fig, width="stretch")

with col2:
    # State distribution
    state_dist = census_df['state'].value_counts()

    fig = px.bar(
        x=state_dist.index,
        y=state_dist.values,
        title='Employees by State',
        labels={'x': 'State', 'y': 'Number of Employees'}
    )

    st.plotly_chart(fig, width="stretch")

# Family status distribution
if 'family_status' in census_df.columns:
    st.markdown("### Family Status Distribution")

    from constants import FAMILY_STATUS_CODES

    family_counts = census_df['family_status'].value_counts()

    # Create display labels
    family_labels = [f"{code} ({FAMILY_STATUS_CODES.get(code, code)})" for code in family_counts.index]

    col1, col2 = st.columns([2, 1])

    with col1:
        fig = px.pie(
            values=family_counts.values,
            names=family_labels,
            title='Employees by Family Status'
        )
        st.plotly_chart(fig, width="stretch")

    with col2:
        st.markdown("**Family Status Breakdown:**")
        for code, count in family_counts.items():
            pct = count / len(census_df) * 100
            desc = FAMILY_STATUS_CODES.get(code, code)
            st.markdown(f"- **{code}** ({desc}): {count} ({pct:.1f}%)")

# Dependent demographics (if present)
if has_dependents:
    st.markdown("### Dependent Demographics")

    dep_col1, dep_col2 = st.columns(2)

    with dep_col1:
        # Dependent relationship breakdown
        rel_counts = dependents_df['relationship'].value_counts()

        fig = px.pie(
            values=rel_counts.values,
            names=[rel.title() + 's' for rel in rel_counts.index],
            title='Dependents by Relationship'
        )

        st.plotly_chart(fig, width="stretch")

    with dep_col2:
        # Dependent age distribution
        dependents_with_age_group = dependents_df.copy()

        # Use different age bins for dependents (more granular for children)
        dep_age_bins = [0, 5, 13, 18, 21, 30, 40, 50, 100]
        dep_age_labels = ['0-4', '5-12', '13-17', '18-20', '21-29', '30-39', '40-49', '50+']

        dependents_with_age_group['age_group'] = pd.cut(
            dependents_with_age_group['age'],
            bins=dep_age_bins,
            labels=dep_age_labels,
            right=False
        )

        dep_age_dist = dependents_with_age_group['age_group'].value_counts().sort_index()

        fig = px.bar(
            x=dep_age_dist.index,
            y=dep_age_dist.values,
            title='Dependent Age Distribution',
            labels={'x': 'Age Group', 'y': 'Number of Dependents'}
        )

        st.plotly_chart(fig, width="stretch")

# Rating area distribution
st.markdown("### Geographic Distribution")

col1, col2 = st.columns(2)

with col1:
    # Rating areas by state
    ra_counts = census_df.groupby(['state', 'rating_area_id']).size().reset_index(name='count')
    ra_counts = ra_counts.sort_values(['state', 'rating_area_id'])

    st.markdown("**Employees by Rating Area:**")
    st.dataframe(ra_counts, width="stretch", hide_index=True)

with col2:
    # County distribution (top 10)
    county_counts = census_df['county'].value_counts().head(10)

    fig = px.bar(
        x=county_counts.values,
        y=county_counts.index,
        orientation='h',
        title='Top 10 Counties by Employee Count',
        labels={'x': 'Number of Employees', 'y': 'County'}
    )
    fig.update_layout(yaxis={'categoryorder': 'total ascending'})

    st.plotly_chart(fig, width="stretch")

# ============================================================================
# NAVIGATION
# ============================================================================

st.markdown("---")
st.success("✅ Summary complete! Ready to **Export Results** →")
st.markdown("Click **4️⃣ Export Results** in the sidebar to generate reports and exports")
