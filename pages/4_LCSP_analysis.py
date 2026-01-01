"""
LCSP Analysis Page - Lowest Cost Silver Plan Comparison

Compares current group plan costs to 100% LCSP (Lowest Cost Silver Plan) premiums.
Shows what it would cost if the employer covered 100% of each employee's LCSP.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

from database import get_database_connection
from financial_calculator import FinancialSummaryCalculator

# Page config
st.set_page_config(page_title="LCSP Analysis", page_icon="📊", layout="wide")


# =============================================================================
# STYLING
# =============================================================================


# =============================================================================
# PAGE HEADER
# =============================================================================

st.title("📊 LCSP analysis")
st.markdown("Compare current group plan costs to 100% LCSP (Lowest Cost Silver Plan) premiums across all states.")

# =============================================================================
# VALIDATION
# =============================================================================

# Check for census data
if 'census_df' not in st.session_state or st.session_state.census_df is None:
    st.warning("⚠️ No census data loaded. Please upload a census on **1️⃣ Census input** first.")
    st.stop()

census_df = st.session_state.census_df

# Initialize database connection
if 'db' not in st.session_state:
    st.session_state.db = get_database_connection()
db = st.session_state.db

# Initialize financial summary state (handle both missing key and None value)
if 'financial_summary' not in st.session_state or st.session_state.financial_summary is None:
    st.session_state.financial_summary = {
        'renewal_monthly': None,
        'results': {}
    }

# =============================================================================
# CENSUS SUMMARY
# =============================================================================

st.subheader("📋 Census summary")

# Calculate current totals from census
current_totals = FinancialSummaryCalculator.calculate_current_totals(census_df)
total_lives = FinancialSummaryCalculator.count_total_lives(census_df)
state_counts = FinancialSummaryCalculator.get_state_employee_counts(census_df)

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Employees", len(census_df))
col2.metric("Covered lives", total_lives)
col3.metric("States", len(state_counts))
col4.metric(
    "Employees w/ data",
    current_totals['employees_with_data'],
    help="Employees with current premium data"
)
col5.metric(
    "Current total/mo",
    f"${current_totals['total_premium_monthly']:,.0f}",
    help="Total monthly premium (EE + ER combined)"
)

# Show breakdown
with st.expander("View current cost breakdown"):
    bk_col1, bk_col2, bk_col3 = st.columns(3)
    bk_col1.metric("ER monthly", f"${current_totals['total_er_monthly']:,.0f}")
    bk_col2.metric("EE monthly", f"${current_totals['total_ee_monthly']:,.0f}")
    bk_col3.metric("Total monthly", f"${current_totals['total_premium_monthly']:,.0f}")

    st.caption("Annual totals:")
    ann_col1, ann_col2, ann_col3 = st.columns(3)
    ann_col1.metric("ER annual", f"${current_totals['total_er_annual']:,.0f}")
    ann_col2.metric("EE annual", f"${current_totals['total_ee_annual']:,.0f}")
    ann_col3.metric("Total annual", f"${current_totals['total_premium_annual']:,.0f}")

st.markdown("---")

# =============================================================================
# 2026 PROJECTED RENEWAL
# =============================================================================

# Check if census has 2026 Premium data
projected_2026_data = FinancialSummaryCalculator.calculate_projected_2026_total(census_df)
has_csv_projected = projected_2026_data['has_data']

st.subheader("📈 2026 projected renewal")

if has_csv_projected:
    # CSV has 2026 Premium data - show it and allow override
    st.success(f"✓ Found **2026 Premium** data in census for {projected_2026_data['employees_with_data']} employees")

    renewal_col1, renewal_col2, renewal_col3 = st.columns([2, 2, 1])

    with renewal_col1:
        st.metric(
            "From census data",
            f"${projected_2026_data['total_monthly']:,.0f}/mo",
            help="Sum of '2026 Premium' column from uploaded census"
        )
        st.caption(f"${projected_2026_data['total_annual']:,.0f}/year")

    with renewal_col2:
        current_total = current_totals['total_premium_monthly']
        if current_total > 0:
            increase_pct = ((projected_2026_data['total_monthly'] - current_total) / current_total * 100)
            st.metric(
                "vs current premium",
                f"${projected_2026_data['total_monthly'] - current_total:+,.0f}/mo",
                f"{increase_pct:+.1f}% increase",
                delta_color="inverse"
            )

    with renewal_col3:
        use_manual = st.checkbox("Override", value=False, help="Enter a different renewal amount")

    if use_manual:
        manual_renewal = st.number_input(
            "Manual 2026 Renewal (monthly)",
            min_value=0.0,
            value=projected_2026_data['total_monthly'],
            step=1000.0,
            format="%.0f",
            help="Override the census-calculated renewal amount"
        )
        st.session_state.financial_summary['renewal_monthly'] = manual_renewal if manual_renewal > 0 else None
        st.session_state.financial_summary['renewal_source'] = 'manual'
    else:
        # Use census data
        st.session_state.financial_summary['renewal_monthly'] = projected_2026_data['total_monthly']
        st.session_state.financial_summary['renewal_source'] = 'census'
else:
    # No CSV data - show manual input
    st.info("No '2026 Premium' column found in census. Enter renewal amount manually, or re-upload census with this column.")

    renewal_col1, renewal_col2 = st.columns([2, 3])
    with renewal_col1:
        renewal_monthly = st.number_input(
            "2026 Renewal Total Premium (monthly)",
            min_value=0.0,
            value=st.session_state.financial_summary.get('renewal_monthly') or 0.0,
            step=1000.0,
            format="%.0f",
            help="Enter the total monthly renewal premium (EE + ER combined). This allows comparison of LCSP costs vs renewal."
        )
        st.session_state.financial_summary['renewal_monthly'] = renewal_monthly if renewal_monthly > 0 else None
        st.session_state.financial_summary['renewal_source'] = 'manual' if renewal_monthly > 0 else None

    with renewal_col2:
        if st.session_state.financial_summary.get('renewal_monthly'):
            renewal_monthly = st.session_state.financial_summary['renewal_monthly']
            current_total = current_totals['total_premium_monthly']
            if current_total > 0:
                increase_pct = ((renewal_monthly - current_total) / current_total * 100)
                st.metric(
                    "Renewal vs Current Total",
                    f"${renewal_monthly - current_total:+,.0f}/mo",
                    f"{increase_pct:+.1f}%",
                    delta_color="inverse"
                )
        else:
            st.caption("Enter renewal premium to enable comparison")

st.markdown("---")

# =============================================================================
# PLAN SELECTION BY STATE
# =============================================================================

st.subheader("📋 Plan selection by state")

states = FinancialSummaryCalculator.get_states_from_census(census_df)

if not states:
    st.error("No state data found in census")
    st.stop()

st.markdown(f"Your workforce spans **{len(states)} states**. This shows the cost of covering 100% of each employee's Lowest Cost Silver Plan (LCSP) based on their rating area, age, and family status.")

# =============================================================================
# LCSP-BASED CALCULATION
# =============================================================================

# Get dependents_df from session state for family member calculations
dependents_df = st.session_state.get('dependents_df', None)

# Auto-calculate LCSP if not already done
if not st.session_state.financial_summary.get('results'):
    with st.spinner("Calculating Lowest Cost Silver Plan (LCSP) for all employees..."):
        results = FinancialSummaryCalculator.calculate_lcsp_scenario(census_df, db, 'Silver', dependents_df)
        st.session_state.financial_summary['results'] = results
        st.rerun()

# =============================================================================
# RESULTS DISPLAY
# =============================================================================

results = st.session_state.financial_summary.get('results', {})

if results and 'total_monthly' in results:
    st.markdown("---")
    st.subheader("📊 Financial comparison")
    st.caption("100% LCSP = total cost to cover each employee's Lowest Cost Silver Plan based on their rating area, age, and family status.")

    # Main comparison metrics
    ichra_monthly = results['total_monthly']
    ichra_annual = results['total_annual']
    current_monthly = current_totals['total_premium_monthly']
    current_annual = current_totals['total_premium_annual']

    # Get 2026 renewal from session state (set above from census or manual input)
    renewal_monthly = st.session_state.financial_summary.get('renewal_monthly', 0) or 0
    renewal_annual = renewal_monthly * 12
    renewal_source = st.session_state.financial_summary.get('renewal_source', None)
    has_renewal = renewal_monthly > 0

    # Variance calculations
    vs_current_monthly = current_monthly - ichra_monthly
    vs_current_annual = vs_current_monthly * 12
    vs_current_pct = (vs_current_monthly / current_monthly * 100) if current_monthly > 0 else 0

    vs_renewal_monthly = renewal_monthly - ichra_monthly if has_renewal else 0
    vs_renewal_annual = vs_renewal_monthly * 12 if has_renewal else 0
    vs_renewal_pct = (vs_renewal_monthly / renewal_monthly * 100) if renewal_monthly > 0 else 0

    # Comparison table
    st.markdown("### Cost comparison")

    comp_col1, comp_col2, comp_col3 = st.columns(3)

    with comp_col1:
        st.metric("Current (2025)", f"${current_monthly:,.0f}/mo")
        st.caption(f"${current_annual:,.0f}/year")

    with comp_col2:
        if has_renewal:
            source_label = "(from census)" if renewal_source == 'census' else "(manual)"
            st.metric(f"2026 renewal {source_label}", f"${renewal_monthly:,.0f}/mo")
            st.caption(f"${renewal_annual:,.0f}/year")
        else:
            st.metric("2026 renewal", "Not set")
            st.caption("Set renewal amount above")

    with comp_col3:
        metal_level = results.get('metal_level', 'Silver')
        st.metric("100% LCSP", f"${ichra_monthly:,.0f}/mo",
                 help="Total cost if the employer paid 100% of each employee's Lowest Cost Silver Plan. This is a benchmark for comparison — actual ICHRA contributions may be less.")
        st.caption(f"${ichra_annual:,.0f}/year")

    # Row 2: Variance metrics (3 columns to align with row above)
    var_col1, var_col2, var_col3 = st.columns(3)

    with var_col1:
        if vs_current_monthly >= 0:
            st.metric(
                "LCSP savings vs current",
                f"${vs_current_monthly:,.0f}/mo",
                f"{vs_current_pct:.1f}%",
                delta_color="normal",
                help="100% LCSP costs LESS than your current plan. This is the monthly savings if you switched."
            )
        else:
            st.metric(
                "LCSP increase vs current",
                f"+${abs(vs_current_monthly):,.0f}/mo",
                f"{abs(vs_current_pct):.1f}% more",
                delta_color="inverse",
                help="100% LCSP costs MORE than your current plan. This is the additional monthly cost if you covered 100% of everyone's LCSP."
            )

    with var_col2:
        if has_renewal:
            if vs_renewal_monthly >= 0:
                st.metric(
                    "LCSP savings vs 2026 renewal",
                    f"${vs_renewal_monthly:,.0f}/mo",
                    f"{vs_renewal_pct:.1f}%",
                    delta_color="normal",
                    help="100% LCSP costs LESS than your projected 2026 renewal. This is the monthly savings if you switched."
                )
            else:
                st.metric(
                    "LCSP increase vs 2026 renewal",
                    f"+${abs(vs_renewal_monthly):,.0f}/mo",
                    f"{abs(vs_renewal_pct):.1f}% more",
                    delta_color="inverse",
                    help="100% LCSP costs MORE than your projected 2026 renewal. This is the additional monthly cost if you covered 100% of everyone's LCSP."
                )

    with var_col3:
        # Calculate and show average LCSP
        employee_details = results.get('employee_details', [])
        if employee_details:
            lcsp_rates = [e.get('lcsp_ee_rate', 0) for e in employee_details if e.get('lcsp_ee_rate')]
            if lcsp_rates:
                avg_lcsp = sum(lcsp_rates) / len(lcsp_rates)
                st.metric(
                    "📊 Avg LCSP",
                    f"${avg_lcsp:,.0f}/mo",
                    help="Average Lowest Cost Silver Plan premium per employee. Useful for budgeting ICHRA contributions."
                )

    # Detailed comparison table
    st.markdown("### Detailed variance analysis")

    metal_level = results.get('metal_level', 'Selected')
    table_data = {
        'Metric': ['Total Monthly', 'Total Annual'],
        'Current (2025)': [
            f"${current_monthly:,.0f}",
            f"${current_annual:,.0f}"
        ],
    }

    # Add 2026 Renewal if available
    if has_renewal:
        table_data['2026 Renewal'] = [
            f"${renewal_monthly:,.0f}",
            f"${renewal_annual:,.0f}"
        ]

    table_data['100% LCSP'] = [
        f"${ichra_monthly:,.0f}",
        f"${ichra_annual:,.0f}"
    ]

    # Add variance vs 2026 Renewal if available
    if has_renewal:
        table_data['vs 2026 Renewal'] = [
            f"{'(' if vs_renewal_monthly > 0 else ''}${abs(vs_renewal_monthly):,.0f}{')' if vs_renewal_monthly > 0 else ''}" + (" savings" if vs_renewal_monthly > 0 else " increase"),
            f"{'(' if vs_renewal_annual > 0 else ''}${abs(vs_renewal_annual):,.0f}{')' if vs_renewal_annual > 0 else ''}" + (" savings" if vs_renewal_annual > 0 else " increase")
        ]

    table_data['vs Current'] = [
        f"{'(' if vs_current_monthly > 0 else ''}${abs(vs_current_monthly):,.0f}{')' if vs_current_monthly > 0 else ''}" + (" savings" if vs_current_monthly > 0 else " increase"),
        f"{'(' if vs_current_annual > 0 else ''}${abs(vs_current_annual):,.0f}{')' if vs_current_annual > 0 else ''}" + (" savings" if vs_current_annual > 0 else " increase")
    ]

    comp_df = pd.DataFrame(table_data)
    st.dataframe(comp_df, hide_index=True, width='stretch')

    if has_renewal:
        source_note = "from census '2026 Premium' column" if renewal_source == 'census' else "manually entered"
        st.caption(f"Values in () indicate savings. 2026 Renewal = {source_note}.")
    else:
        st.caption("Values in () indicate savings. Set 2026 Renewal above to compare against projected costs.")

    # State breakdown
    if results.get('by_state'):
        with st.expander("📍 Breakdown by state", expanded=True):
            metal_level = results.get('metal_level', 'Plan')
            state_data = []
            for state, state_info in results['by_state'].items():
                employees = state_info['employees']
                monthly = state_info['monthly']
                avg_per_employee = monthly / employees if employees > 0 else 0

                state_data.append({
                    'State': state,
                    'Employees': employees,
                    'Lives': state_info['lives'],
                    'Total Monthly': f"${monthly:,.0f}",
                    f'Avg {metal_level}/Employee': f"${avg_per_employee:,.0f}",
                })

            state_df = pd.DataFrame(state_data)
            state_df = state_df.sort_values('Employees', ascending=False)
            st.dataframe(state_df, hide_index=True, width='stretch')

    # Savings Heatmap by Age and Family Status
    if results.get('employee_details') and has_renewal:
        with st.expander("🗺️ Savings heatmap by age & family status", expanded=True):
            st.markdown("**Monthly savings per employee** comparing 2026 Renewal vs LCSP. Green = savings, Red = increase.")

            detail_df = pd.DataFrame(results['employee_details'])

            # Calculate savings for each employee (renewal - LCSP = savings)
            detail_df['savings'] = detail_df['projected_2026_premium'] - detail_df['estimated_tier_premium']

            # Create age bands for cleaner display
            def age_to_band(age):
                if age < 20:
                    return 'Under 20'
                elif age < 25:
                    return '20-24'
                elif age < 30:
                    return '25-29'
                elif age < 35:
                    return '30-34'
                elif age < 40:
                    return '35-39'
                elif age < 45:
                    return '40-44'
                elif age < 50:
                    return '45-49'
                elif age < 55:
                    return '50-54'
                elif age < 60:
                    return '55-59'
                elif age < 65:
                    return '60-64'
                else:
                    return '65+'

            detail_df['age_band'] = detail_df['ee_age'].apply(age_to_band)

            # Family status labels
            status_labels = {'EE': 'Employee Only', 'ES': 'EE + Spouse', 'EC': 'EE + Child(ren)', 'F': 'Family'}
            detail_df['family_label'] = detail_df['family_status'].map(status_labels).fillna(detail_df['family_status'])

            # Create pivot tables for heatmap
            # Average savings by age band and family status
            pivot_savings = detail_df.pivot_table(
                values='savings',
                index='age_band',
                columns='family_label',
                aggfunc='mean'
            )

            # Count of employees
            pivot_count = detail_df.pivot_table(
                values='savings',
                index='age_band',
                columns='family_label',
                aggfunc='count'
            ).fillna(0).astype(int)

            # Ensure consistent ordering
            age_order = ['Under 20', '20-24', '25-29', '30-34', '35-39', '40-44', '45-49', '50-54', '55-59', '60-64', '65+']
            status_order = ['Employee Only', 'EE + Spouse', 'EE + Child(ren)', 'Family']

            # Reindex to ensure order (only include bands that exist)
            age_order = [a for a in age_order if a in pivot_savings.index]
            status_order = [s for s in status_order if s in pivot_savings.columns]

            if age_order and status_order:
                pivot_savings = pivot_savings.reindex(index=age_order, columns=status_order)
                pivot_count = pivot_count.reindex(index=age_order, columns=status_order).fillna(0).astype(int)

                # Create hover text with savings and count
                hover_text = []
                for i, age in enumerate(pivot_savings.index):
                    row_text = []
                    for j, status in enumerate(pivot_savings.columns):
                        savings_val = pivot_savings.iloc[i, j]
                        count_val = pivot_count.iloc[i, j]
                        if pd.notna(savings_val) and count_val > 0:
                            if savings_val >= 0:
                                row_text.append(f"Age: {age}<br>Status: {status}<br>Avg Savings: ${savings_val:,.0f}/mo<br>Employees: {count_val}")
                            else:
                                row_text.append(f"Age: {age}<br>Status: {status}<br>Avg Increase: ${abs(savings_val):,.0f}/mo<br>Employees: {count_val}")
                        else:
                            row_text.append(f"Age: {age}<br>Status: {status}<br>No employees")
                    hover_text.append(row_text)

                # Create annotation text (show savings value and count)
                annotations = []
                for i, age in enumerate(pivot_savings.index):
                    for j, status in enumerate(pivot_savings.columns):
                        savings_val = pivot_savings.iloc[i, j]
                        count_val = pivot_count.iloc[i, j]
                        if pd.notna(savings_val) and count_val > 0:
                            if savings_val >= 0:
                                text = f"${savings_val:,.0f}<br><sub>({count_val})</sub>"
                            else:
                                text = f"-${abs(savings_val):,.0f}<br><sub>({count_val})</sub>"
                        else:
                            text = ""
                        annotations.append(text)

                # Create heatmap
                fig = go.Figure(data=go.Heatmap(
                    z=pivot_savings.values,
                    x=pivot_savings.columns.tolist(),
                    y=pivot_savings.index.tolist(),
                    hovertext=hover_text,
                    hoverinfo='text',
                    colorscale=[
                        [0, '#dc2626'],      # Red for losses
                        [0.35, '#fca5a5'],   # Light red
                        [0.5, '#fef3c7'],    # Yellow/neutral
                        [0.65, '#86efac'],   # Light green
                        [1, '#16a34a']       # Green for savings
                    ],
                    zmid=0,  # Center color scale at 0
                    colorbar=dict(
                        title="Monthly<br>Savings",
                        tickprefix="$",
                        tickformat=",.0f"
                    )
                ))

                # Add annotations
                annotation_idx = 0
                for i, age in enumerate(pivot_savings.index):
                    for j, status in enumerate(pivot_savings.columns):
                        fig.add_annotation(
                            x=status,
                            y=age,
                            text=annotations[annotation_idx],
                            showarrow=False,
                            font=dict(size=11, color='black')
                        )
                        annotation_idx += 1

                fig.update_layout(
                    title=dict(
                        text="Average monthly savings: 2026 renewal vs LCSP",
                        font=dict(size=16)
                    ),
                    xaxis_title="Family status",
                    yaxis_title="Employee age band",
                    height=450,
                    yaxis=dict(autorange='reversed'),  # Youngest at top
                    margin=dict(l=80, r=40, t=60, b=60)
                )

                st.plotly_chart(fig, width='stretch')

                # Summary stats below heatmap
                st.markdown("**Quick Stats:**")
                stats_col1, stats_col2, stats_col3, stats_col4 = st.columns(4)

                # Employees with savings vs increases
                emp_with_savings = (detail_df['savings'] > 0).sum()
                emp_with_increase = (detail_df['savings'] < 0).sum()
                total_emp = len(detail_df)

                with stats_col1:
                    st.metric("Employees with savings", f"{emp_with_savings}", f"{emp_with_savings/total_emp*100:.0f}%")
                with stats_col2:
                    st.metric("Employees with increase", f"{emp_with_increase}", f"{emp_with_increase/total_emp*100:.0f}%")
                with stats_col3:
                    avg_savings = detail_df['savings'].mean()
                    if avg_savings >= 0:
                        st.metric("Avg savings/employee", f"${avg_savings:,.0f}/mo")
                    else:
                        st.metric("Avg increase/employee", f"${abs(avg_savings):,.0f}/mo")
                with stats_col4:
                    max_savings = detail_df['savings'].max()
                    max_increase = detail_df['savings'].min()
                    st.metric("Range", f"${max_increase:,.0f} to ${max_savings:,.0f}")
            else:
                st.info("Not enough data to generate heatmap.")

    # Employee Impact Analysis - categorize by savings/breakeven/increase
    if results.get('employee_details') and has_renewal:
        with st.expander("👥 Employee impact analysis", expanded=True):
            st.markdown("**How does 100% LCSP compare for each employee?** Comparing 2026 Renewal vs LCSP costs.")

            impact_df = pd.DataFrame(results['employee_details'])
            impact_df['savings'] = impact_df['projected_2026_premium'] - impact_df['estimated_tier_premium']

            # Categorize employees
            BREAKEVEN_THRESHOLD = 50  # Within $50/month is "breakeven"

            saves_money = impact_df[impact_df['savings'] > BREAKEVEN_THRESHOLD]
            breakeven = impact_df[(impact_df['savings'] >= -BREAKEVEN_THRESHOLD) & (impact_df['savings'] <= BREAKEVEN_THRESHOLD)]
            pays_more = impact_df[impact_df['savings'] < -BREAKEVEN_THRESHOLD]

            total_emp = len(impact_df)
            n_saves = len(saves_money)
            n_breakeven = len(breakeven)
            n_pays_more = len(pays_more)

            # Create donut chart
            fig_donut = go.Figure(data=[go.Pie(
                labels=['Saves Money', 'Breakeven (±$50)', 'Pays More'],
                values=[n_saves, n_breakeven, n_pays_more],
                hole=0.5,
                marker_colors=['#16a34a', '#fbbf24', '#dc2626'],
                textinfo='label+percent',
                textposition='outside',
                pull=[0.02, 0, 0.02]
            )])

            fig_donut.update_layout(
                title=dict(text="Employee impact distribution", font=dict(size=16)),
                height=350,
                showlegend=False,
                annotations=[dict(
                    text=f'{total_emp}<br>Employees',
                    x=0.5, y=0.5,
                    font_size=16,
                    showarrow=False
                )]
            )

            chart_col, detail_col = st.columns([1, 1])

            with chart_col:
                st.plotly_chart(fig_donut, width='stretch')

            with detail_col:
                # Detailed breakdown
                st.markdown("#### Breakdown")

                # Saves Money
                st.markdown(f"""
                <div style="background: #dcfce7; padding: 12px; border-radius: 8px; margin-bottom: 8px; border-left: 4px solid #16a34a;">
                    <strong style="color: #16a34a;">✓ Saves Money: {n_saves} employees ({n_saves/total_emp*100:.0f}%)</strong><br>
                    <span style="font-size: 0.9em;">Avg savings: ${saves_money['savings'].mean():,.0f}/mo</span> |
                    <span style="font-size: 0.9em;">Total: ${saves_money['savings'].sum():,.0f}/mo</span>
                </div>
                """, unsafe_allow_html=True)

                # Breakeven
                st.markdown(f"""
                <div style="background: #fef3c7; padding: 12px; border-radius: 8px; margin-bottom: 8px; border-left: 4px solid #fbbf24;">
                    <strong style="color: #b45309;">≈ Breakeven (±$50): {n_breakeven} employees ({n_breakeven/total_emp*100:.0f}%)</strong><br>
                    <span style="font-size: 0.9em;">Avg difference: ${breakeven['savings'].mean():,.0f}/mo</span> |
                    <span style="font-size: 0.9em;">Total: ${breakeven['savings'].sum():,.0f}/mo</span>
                </div>
                """, unsafe_allow_html=True)

                # Pays More
                st.markdown(f"""
                <div style="background: #fee2e2; padding: 12px; border-radius: 8px; margin-bottom: 8px; border-left: 4px solid #dc2626;">
                    <strong style="color: #dc2626;">✗ Pays More: {n_pays_more} employees ({n_pays_more/total_emp*100:.0f}%)</strong><br>
                    <span style="font-size: 0.9em;">Avg increase: ${abs(pays_more['savings'].mean()) if len(pays_more) > 0 else 0:,.0f}/mo</span> |
                    <span style="font-size: 0.9em;">Total: ${abs(pays_more['savings'].sum()) if len(pays_more) > 0 else 0:,.0f}/mo</span>
                </div>
                """, unsafe_allow_html=True)

            # Net impact summary
            st.markdown("---")
            net_savings = impact_df['savings'].sum()
            net_col1, net_col2, net_col3 = st.columns(3)

            with net_col1:
                if net_savings >= 0:
                    st.metric("Net monthly impact", f"${net_savings:,.0f} savings", f"${net_savings * 12:,.0f}/year")
                else:
                    st.metric("Net monthly impact", f"-${abs(net_savings):,.0f} increase", f"-${abs(net_savings) * 12:,.0f}/year")

            with net_col2:
                favorable_pct = (n_saves + n_breakeven) / total_emp * 100
                st.metric("Favorable outcomes", f"{n_saves + n_breakeven} employees", f"{favorable_pct:.0f}% of workforce")

            with net_col3:
                if n_pays_more > 0:
                    max_increase = abs(pays_more['savings'].min())
                    st.metric("Max individual increase", f"${max_increase:,.0f}/mo", "Consider mitigation strategy")
                else:
                    st.metric("Max individual increase", "$0/mo", "No employees pay more")

            # Breakdown by family status
            st.markdown("#### Impact by family status")
            status_labels = {'EE': 'Employee Only', 'ES': 'EE + Spouse', 'EC': 'EE + Child(ren)', 'F': 'Family'}

            status_summary = []
            for status_code, status_name in status_labels.items():
                status_df = impact_df[impact_df['family_status'] == status_code]
                if len(status_df) > 0:
                    n_status_saves = len(status_df[status_df['savings'] > BREAKEVEN_THRESHOLD])
                    n_status_breakeven = len(status_df[(status_df['savings'] >= -BREAKEVEN_THRESHOLD) & (status_df['savings'] <= BREAKEVEN_THRESHOLD)])
                    n_status_pays = len(status_df[status_df['savings'] < -BREAKEVEN_THRESHOLD])
                    avg_impact = status_df['savings'].mean()

                    status_summary.append({
                        'Family Status': status_name,
                        'Employees': len(status_df),
                        'Saves Money': n_status_saves,
                        'Breakeven': n_status_breakeven,
                        'Pays More': n_status_pays,
                        'Avg Impact': f"${avg_impact:+,.0f}/mo"
                    })

            if status_summary:
                status_summary_df = pd.DataFrame(status_summary)
                st.dataframe(status_summary_df, hide_index=True, width='stretch')

    # Errors/warnings
    if results.get('errors'):
        with st.expander(f"⚠️ Calculation warnings ({len(results['errors'])} issues)"):
            for error in results['errors'][:20]:
                st.text(error)
            if len(results['errors']) > 20:
                st.text(f"... and {len(results['errors']) - 20} more")

    # CSV Download button (no preview)
    if results.get('employee_details'):
        # Create DataFrame from employee details
        detail_df = pd.DataFrame(results['employee_details'])

        # Calculate savings columns
        detail_df['savings_vs_2025'] = detail_df['current_total_monthly'] - detail_df['estimated_tier_premium']
        detail_df['savings_vs_2026'] = detail_df['projected_2026_premium'] - detail_df['estimated_tier_premium']

        # Reorder columns for clarity
        column_order = [
            'employee_id', 'last_name', 'first_name', 'state', 'rating_area',
            'family_status', 'ee_age', 'lcsp_plan_name', 'lcsp_ee_rate',
            'tier_multiplier', 'estimated_tier_premium',
            'current_ee_monthly', 'current_er_monthly', 'current_total_monthly',
            'savings_vs_2025',
            'projected_2026_premium',
            'savings_vs_2026'
        ]
        detail_df = detail_df[[c for c in column_order if c in detail_df.columns]]

        # Rename columns for readability
        metal_level = results.get('metal_level', 'Plan')
        detail_df = detail_df.rename(columns={
            'employee_id': 'Employee ID',
            'last_name': 'Last Name',
            'first_name': 'First Name',
            'state': 'State',
            'rating_area': 'Rating Area',
            'family_status': 'Family Status',
            'ee_age': 'EE Age',
            'lcsp_plan_name': f'{metal_level} LCSP Plan Name',
            'lcsp_ee_rate': f'2026 {metal_level} LCSP (EE Only)',
            'tier_multiplier': 'Tier Multiplier',
            'estimated_tier_premium': '2026 LCSP Tier Premium',
            'current_ee_monthly': '2025 Current EE Monthly',
            'current_er_monthly': '2025 Current ER Monthly',
            'current_total_monthly': '2025 Current Total Monthly',
            'savings_vs_2025': '2025 Savings (Current - LCSP)',
            'projected_2026_premium': '2026 Projected Renewal',
            'savings_vs_2026': '2026 Savings (Renewal - LCSP)'
        })

        csv_data = detail_df.to_csv(index=False)
        st.download_button(
            label="📥 Download full Silver LCSP detail CSV",
            data=csv_data,
            file_name="lcsp_silver_detail.csv",
            mime="text/csv",
            type="secondary"
        )

    # ==========================================================================
    # BOTTOM LINE SUMMARY
    # ==========================================================================
    st.markdown("---")
    st.markdown("## 📌 Bottom line")

    # Determine primary comparison (renewal if available, otherwise current)
    if has_renewal:
        primary_savings = vs_renewal_annual
        primary_monthly = vs_renewal_monthly
        primary_pct = vs_renewal_pct
        primary_label = "vs 2026 Renewal"
    else:
        primary_savings = vs_current_annual
        primary_monthly = vs_current_monthly
        primary_pct = vs_current_pct
        primary_label = "vs Current (2025)"

    # Large annual savings/increase display
    if primary_savings >= 0:
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #dcfce7 0%, #bbf7d0 100%); padding: 24px; border-radius: 12px; text-align: center; border: 2px solid #16a34a;">
            <div style="font-size: 0.9em; color: #166534; margin-bottom: 8px;">ESTIMATED ANNUAL SAVINGS {primary_label.upper()}</div>
            <div style="font-size: 2.5em; font-weight: bold; color: #16a34a;">${primary_savings:,.0f}</div>
            <div style="font-size: 1em; color: #166534; margin-top: 8px;">${primary_monthly:,.0f}/month · {primary_pct:.1f}% reduction</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%); padding: 24px; border-radius: 12px; text-align: center; border: 2px solid #dc2626;">
            <div style="font-size: 0.9em; color: #991b1b; margin-bottom: 8px;">ESTIMATED ANNUAL INCREASE {primary_label.upper()}</div>
            <div style="font-size: 2.5em; font-weight: bold; color: #dc2626;">${abs(primary_savings):,.0f}</div>
            <div style="font-size: 1em; color: #991b1b; margin-top: 8px;">${abs(primary_monthly):,.0f}/month · {abs(primary_pct):.1f}% increase</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("")  # Spacer

    # Comparison details in columns
    if has_renewal:
        detail_col1, detail_col2, detail_col3 = st.columns(3)

        with detail_col1:
            if vs_current_monthly >= 0:
                st.metric("vs Current (2025)", f"${vs_current_annual:,.0f}/yr savings", f"{vs_current_pct:.1f}%")
            else:
                st.metric("vs Current (2025)", f"-${abs(vs_current_annual):,.0f}/yr", f"+{abs(vs_current_pct):.1f}%", delta_color="inverse")

        with detail_col2:
            if vs_renewal_monthly >= 0:
                st.metric("vs 2026 Renewal", f"${vs_renewal_annual:,.0f}/yr savings", f"{vs_renewal_pct:.1f}%")
            else:
                st.metric("vs 2026 Renewal", f"-${abs(vs_renewal_annual):,.0f}/yr", f"+{abs(vs_renewal_pct):.1f}%", delta_color="inverse")

        with detail_col3:
            st.metric("Coverage", f"{results['employees_covered']} employees", f"{results['lives_covered']} lives")
    else:
        detail_col1, detail_col2 = st.columns(2)

        with detail_col1:
            if vs_current_monthly >= 0:
                st.metric("vs Current (2025)", f"${vs_current_annual:,.0f}/yr savings", f"{vs_current_pct:.1f}%")
            else:
                st.metric("vs Current (2025)", f"-${abs(vs_current_annual):,.0f}/yr", f"+{abs(vs_current_pct):.1f}%", delta_color="inverse")

        with detail_col2:
            st.metric("Coverage", f"{results['employees_covered']} employees", f"{results['lives_covered']} lives")

        st.caption("Add '2026 Premium' column to census or enter renewal amount above for comparison to projected renewal costs.")

else:
    st.info("LCSP calculation in progress...")
