"""
Page 3: Employer Summary
Aggregate cost analysis and census demographics for ICHRA contribution evaluation
"""

import streamlit as st
import pandas as pd
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
    st.markdown("**Contribution Type:** Percentage")
    st.markdown(f"**Employer Contribution:** {contribution_pct}%")

    if 'by_class' in settings and settings['by_class']:
        st.markdown("**By Employee Class:**")
        for class_name, pct in settings['by_class'].items():
            st.markdown(f"- {class_name}: {pct}%")

st.markdown("---")

# ============================================================================
# ICHRA COST IMPACT - Total premium comparison (apples to apples)
# ============================================================================

if has_individual_contribs:
    from financial_calculator import FinancialSummaryCalculator

    # Get contribution totals
    contrib_totals = ContributionComparison.aggregate_contribution_totals(census_df)
    strategy_results = st.session_state.get('strategy_results', {})
    has_strategy = strategy_results.get('calculated', False)

    if has_strategy:
        result = strategy_results.get('result', {})
        proposed_annual = result.get('total_annual', 0)
        proposed_monthly = result.get('total_monthly', 0)
        employees_covered = result.get('employees_covered', 0)
        strategy_name = result.get('strategy_name', 'Applied Strategy')

        # Current costs (2025)
        current_er_annual = contrib_totals['total_current_er_annual']
        current_ee_annual = contrib_totals['total_current_ee_annual']
        current_total_annual = current_er_annual + current_ee_annual
        current_er_monthly = contrib_totals['total_current_er_monthly']
        current_ee_monthly = contrib_totals['total_current_ee_monthly']
        current_total_monthly = current_er_monthly + current_ee_monthly

        # 2026 Renewal TOTAL premium (from census or financial summary)
        renewal_total_annual = 0
        renewal_total_monthly = 0
        if 'financial_summary' in st.session_state and st.session_state.financial_summary.get('renewal_monthly'):
            renewal_total_monthly = st.session_state.financial_summary['renewal_monthly']
            renewal_total_annual = renewal_total_monthly * 12
        else:
            projected_data = FinancialSummaryCalculator.calculate_projected_2026_total(census_df)
            if projected_data['has_data']:
                renewal_total_monthly = projected_data['total_monthly']
                renewal_total_annual = projected_data['total_annual']

        # Calculate ER/EE split percentages from current costs
        er_pct = current_er_monthly / current_total_monthly if current_total_monthly > 0 else 0.60
        ee_pct = current_ee_monthly / current_total_monthly if current_total_monthly > 0 else 0.40

        # PROJECT the 2026 ER contribution using same split ratio
        # This is the KEY metric - what would employer pay at renewal
        projected_er_monthly_2026 = renewal_total_monthly * er_pct
        projected_er_annual_2026 = projected_er_monthly_2026 * 12
        projected_ee_monthly_2026 = renewal_total_monthly * ee_pct
        projected_ee_annual_2026 = projected_ee_monthly_2026 * 12

        # Calculate all comparisons
        # 1. vs Current ER (employer-to-employer, same year baseline)
        delta_vs_current_er = proposed_annual - current_er_annual
        delta_vs_current_er_pct = (delta_vs_current_er / current_er_annual * 100) if current_er_annual > 0 else 0

        # 2. vs Projected Renewal ER - THE PRIMARY SALES COMPARISON
        savings_vs_renewal_er = projected_er_annual_2026 - proposed_annual
        savings_vs_renewal_er_pct = (savings_vs_renewal_er / projected_er_annual_2026 * 100) if projected_er_annual_2026 > 0 else 0

        # 3. vs Renewal Total (for context - apples to oranges but big number)
        savings_vs_renewal_total = renewal_total_annual - proposed_annual
        savings_vs_renewal_total_pct = (savings_vs_renewal_total / renewal_total_annual * 100) if renewal_total_annual > 0 else 0

        st.info("💡 **Key insight:** ICHRA is employer contribution only. 'vs Renewal ER' shows what you save by switching to ICHRA instead of accepting the renewal. 'vs Renewal Total' includes employee premiums and appears larger but isn't an apples-to-apples comparison.")

            # === HEADLINE: EMPLOYER COST COMPARISON ===
        st.subheader("💰 Employer Cost Comparison")

        # === DETAILED SUMMARY ===
        st.markdown("---")
        summary_cols = st.columns(3)

        with summary_cols[0]:
            st.metric("Current ER (2025)", DataFormatter.format_currency(current_er_annual),
                     help=f"Current employer contribution ({er_pct*100:.1f}% of total)")

        with summary_cols[1]:
            if projected_er_annual_2026 > 0:
                st.metric("Projected Renewal ER", DataFormatter.format_currency(projected_er_annual_2026),
                         help=f"2026 renewal × {er_pct*100:.1f}% ER share")
            else:
                st.metric("Projected Renewal ER", "N/A")

        with summary_cols[2]:
            st.metric("Proposed ICHRA", DataFormatter.format_currency(proposed_annual),
                     help="Total employer ICHRA budget")
             
        st.caption("Comparing ICHRA to Current → Renewal ER")

        # Three comparison cards side by side
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                label="ICHRA vs Current ER Annual Cost",
                value=f"${abs(delta_vs_current_er):,.0f}",
                delta=f"{delta_vs_current_er_pct:+.1f}%",
                delta_color="inverse"  # red if positive (costs more)
            )
            if delta_vs_current_er > 0:
                st.caption("ICHRA costs more than current")
            else:
                st.caption("ICHRA saves vs current")

        with col2:
            # PRIMARY COMPARISON - make it stand out
            st.metric(
                label="ICHRA vs Accepting Renewal ER Annual Cost",
                value=f"${savings_vs_renewal_er:,.0f}" if savings_vs_renewal_er >= 0 else f"-${abs(savings_vs_renewal_er):,.0f}",
                delta=f"{savings_vs_renewal_er_pct:.1f}% savings" if savings_vs_renewal_er >= 0 else f"{savings_vs_renewal_er_pct:.1f}%",
                delta_color="normal" if savings_vs_renewal_er >= 0 else "inverse"
            )
            st.caption("**Primary comparison** - avoiding the renewal")

        with col3:
            st.metric(
                label="ICHRA Annual Savings vs Renewal ER",
                value=f"${savings_vs_renewal_total:,.0f}" if savings_vs_renewal_total >= 0 else f"-${abs(savings_vs_renewal_total):,.0f}",
                delta=f"{savings_vs_renewal_total_pct:.1f}%",
                delta_color="normal" if savings_vs_renewal_total >= 0 else "inverse"
            )
            st.caption("Total premium comparison*")

        # === DETAILS IN EXPANDER ===
        with st.expander("View cost breakdown details"):
            st.caption(f"Strategy: {strategy_name} · {employees_covered} employees · ER share: {er_pct*100:.1f}%")

            detail_col1, detail_col2, detail_col3 = st.columns(3)

            with detail_col1:
                st.markdown("**Current (2025)**")
                st.write(f"- ER: {DataFormatter.format_currency(current_er_annual)}/yr")
                st.write(f"- EE: {DataFormatter.format_currency(current_ee_annual)}/yr")
                st.write(f"- **Total**: {DataFormatter.format_currency(current_total_annual)}/yr")

            with detail_col2:
                st.markdown("**2026 Renewal (Projected)**")
                st.write(f"- ER: {DataFormatter.format_currency(projected_er_annual_2026)}/yr")
                st.write(f"- EE: {DataFormatter.format_currency(projected_ee_annual_2026)}/yr")
                st.write(f"- **Total**: {DataFormatter.format_currency(renewal_total_annual)}/yr")
                st.caption(f"+{((renewal_total_annual/current_total_annual)-1)*100:.1f}% increase" if current_total_annual > 0 else "")

            with detail_col3:
                st.markdown("**Proposed ICHRA**")
                avg_per_emp = proposed_monthly / employees_covered if employees_covered > 0 else 0
                st.write(f"- ER Budget: {DataFormatter.format_currency(proposed_annual)}/yr")
                st.write(f"- Avg/Employee: {DataFormatter.format_currency(avg_per_emp)}/mo")
                st.write(f"- Employees: {employees_covered}")

    else:
        # No strategy applied yet
        st.subheader("💰 Employer Cost Impact")
        st.info("""
        **Configure a contribution strategy to see cost comparison**

        Go to **Contribution Evaluation** → Use the Strategy Modeler → Click **"Use This Strategy"**
        """)

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

# ============================================================================
# NAVIGATION
# ============================================================================

st.markdown("---")
st.success("✅ Summary complete! Ready to **Export Results** →")
st.markdown("Click **4️⃣ Export Results** in the sidebar to generate reports and exports")
