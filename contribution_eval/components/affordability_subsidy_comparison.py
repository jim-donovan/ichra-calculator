"""
Affordability & Subsidy Path Comparison Component

Provides a side-by-side comparison view showing:
- Path 1: ICHRA Affordable (employer contribution high enough)
- Path 2: Subsidy Eligible (ICHRA unaffordable, employees get ACA subsidies)
- Decision Recommendation (which path is better for each employee)

Designed for Non-ALE Subsidy mode to help employers understand the trade-offs.
"""

import streamlit as st
import pandas as pd
from typing import Dict, List, Any, Optional, Literal
from contribution_eval.utils.formatting import format_currency

# Brand colors
BRAND_PRIMARY = '#0047AB'
GREEN = '#047857'
AMBER = '#B45309'
RED = '#DC2626'
GRAY = '#9CA3AF'

ViewMode = Literal['side_by_side', 'best_path', 'detailed']


def render_affordability_subsidy_comparison(
    employee_contributions: Dict[str, Dict],
    subsidy_data: Optional[Dict[str, Any]] = None,
    affordability_threshold: float = 0.0996,
) -> None:
    """
    Render the improved affordability/subsidy comparison view.

    Args:
        employee_contributions: Per-employee contribution data from strategy
        subsidy_data: Subsidy analysis data (contains by_employee list)
        affordability_threshold: IRS affordability threshold (default 9.96% for 2026)
    """
    # View mode toggle
    st.markdown("### Affordability vs Subsidy Path Analysis")

    col_view, col_filter, col_sort = st.columns([2, 2, 2])

    with col_view:
        view_mode = st.radio(
            "View Mode",
            options=['side_by_side', 'best_path', 'detailed'],
            format_func=lambda x: {
                'side_by_side': '📊 Side-by-side Comparison',
                'best_path': '✓ Best Path Only',
                'detailed': '📋 Full Breakdown'
            }[x],
            horizontal=True,
            key='comparison_view_mode',
            label_visibility='collapsed'
        )

    with col_filter:
        filter_option = st.selectbox(
            "Filter",
            options=['all', 'subsidy_eligible', 'affordability_required', 'largest_savings'],
            format_func=lambda x: {
                'all': 'All Employees',
                'subsidy_eligible': 'Subsidy Eligible Only',
                'affordability_required': 'Affordability Required',
                'largest_savings': 'Largest Savings (Top 10)'
            }[x],
            key='comparison_filter'
        )

    with col_sort:
        sort_option = st.selectbox(
            "Sort by",
            options=['name', 'age', 'income', 'fpl_pct', 'ee_cost', 'affordability_gap', 'subsidy', 'ee_pays', 'savings'],
            format_func=lambda x: {
                'name': 'Employee Name',
                'age': 'Age (Low to High)',
                'income': 'Income (High to Low)',
                'fpl_pct': 'FPL % (Low to High)',
                'ee_cost': 'EE Cost (Low to High)',
                'affordability_gap': 'Affordability Gap (Over First)',
                'subsidy': 'Govt Subsidy (High to Low)',
                'ee_pays': 'EE Pays w/ Subsidy (Low to High)',
                'savings': 'Subsidy Savings (High to Low)'
            }[x],
            key='comparison_sort'
        )

    # Build comparison data
    comparison_rows = _build_comparison_data(
        employee_contributions,
        subsidy_data,
        affordability_threshold
    )

    # Apply filtering
    filtered_rows = _apply_filters(comparison_rows, filter_option)

    # Apply sorting
    sorted_rows = _apply_sorting(filtered_rows, sort_option)

    # Render based on view mode
    if view_mode == 'side_by_side':
        _render_side_by_side_view(sorted_rows)
    elif view_mode == 'best_path':
        _render_best_path_view(sorted_rows)
    else:  # detailed
        _render_detailed_view(sorted_rows)

    # Summary totals row
    _render_summary_totals(comparison_rows)


def _build_comparison_data(
    employee_contributions: Dict[str, Dict],
    subsidy_data: Optional[Dict[str, Any]],
    affordability_threshold: float,
) -> List[Dict[str, Any]]:
    """
    Build unified comparison data structure for each employee.

    Returns list of dicts with:
    - Employee info (name, age, income, family_status)
    - Path 1 (Affordable): ER contrib, EE cost, threshold, is_affordable
    - Path 2 (Subsidy): Expected premium, govt subsidy, EE pays, savings
    - Recommendation: which path is better
    """
    rows = []

    # Get subsidy data by employee
    subsidy_by_employee = {}
    if subsidy_data and subsidy_data.get('by_employee'):
        for emp in subsidy_data['by_employee']:
            emp_id = emp.get('employee_id')
            if emp_id:
                subsidy_by_employee[emp_id] = emp

    for emp_id, contrib in employee_contributions.items():
        # Employee demographics
        name = contrib.get('name', emp_id)
        age = int(contrib.get('age', 30))
        monthly_income = contrib.get('monthly_income', 0)
        family_status = contrib.get('family_status', 'EE')
        lcsp = contrib.get('lcsp_ee_rate', 0)

        # Path 1: Affordability Test
        er_contribution = contrib.get('monthly_contribution', 0)
        ee_cost = max(0, lcsp - er_contribution)
        threshold = monthly_income * affordability_threshold if monthly_income else 0
        is_affordable = ee_cost <= threshold if threshold > 0 else None
        affordability_gap = max(0, ee_cost - threshold) if threshold > 0 else 0

        # Path 2: Subsidy Path
        emp_subsidy_data = subsidy_by_employee.get(emp_id, {})
        is_medicare = age >= 65 or emp_subsidy_data.get('is_medicare', False)
        is_subsidy_eligible = emp_subsidy_data.get('eligible', False) and not is_medicare
        govt_subsidy = emp_subsidy_data.get('subsidy', 0) if is_subsidy_eligible else 0

        # For subsidy path, calculate what employee would pay with subsidy
        # Expected premium is based on FPL% sliding scale (income * 0-8.5%)
        expected_premium_pct = emp_subsidy_data.get('expected_premium_pct', 0)
        expected_premium = monthly_income * expected_premium_pct if monthly_income else 0

        # SLCSP is used for subsidy calculation
        emp_subsidy_data.get('slcsp', lcsp)

        # Employee pays SLCSP - govt_subsidy (if eligible)
        ee_pays_with_subsidy = max(0, lcsp - govt_subsidy) if is_subsidy_eligible else lcsp

        # Savings calculation: Path 1 (EE pays EE cost) vs Path 2 (EE pays with subsidy)
        subsidy_path_saves = ee_cost - ee_pays_with_subsidy if is_subsidy_eligible else 0

        # Recommendation
        if is_medicare:
            recommendation = 'Medicare (separate analysis required)'
            recommendation_color = GRAY
        elif is_subsidy_eligible and subsidy_path_saves > 20:  # $20/mo threshold for "meaningful"
            recommendation = f'Subsidy Path Saves ${subsidy_path_saves:,.0f}/mo'
            recommendation_color = GREEN
        elif is_affordable is True:
            recommendation = 'Affordability Path (ICHRA affordable)'
            recommendation_color = BRAND_PRIMARY
        elif not monthly_income:
            recommendation = 'Income data required'
            recommendation_color = GRAY
        else:
            recommendation = 'Similar Cost (< $20 difference)'
            recommendation_color = GRAY

        rows.append({
            # Employee info
            'employee_id': emp_id,
            'name': name,
            'age': age,
            'monthly_income': monthly_income,
            'family_status': family_status,
            'lcsp': lcsp,
            'fpl_pct': emp_subsidy_data.get('fpl_pct', 0),

            # Path 1: Affordability
            'er_contribution': er_contribution,
            'ee_cost': ee_cost,
            'affordability_threshold': threshold,
            'is_affordable': is_affordable,
            'affordability_gap': affordability_gap,

            # Path 2: Subsidy
            'is_medicare': is_medicare,
            'is_subsidy_eligible': is_subsidy_eligible,
            'expected_premium': expected_premium,
            'govt_subsidy': govt_subsidy,
            'ee_pays_with_subsidy': ee_pays_with_subsidy,

            # Comparison
            'subsidy_path_saves': subsidy_path_saves,
            'recommendation': recommendation,
            'recommendation_color': recommendation_color,
        })

    return rows


def _apply_filters(rows: List[Dict], filter_option: str) -> List[Dict]:
    """Apply filtering to comparison rows."""
    if filter_option == 'subsidy_eligible':
        return [r for r in rows if r['is_subsidy_eligible']]
    elif filter_option == 'affordability_required':
        return [r for r in rows if r['is_affordable'] is False and not r['is_medicare']]
    elif filter_option == 'largest_savings':
        eligible = [r for r in rows if r['is_subsidy_eligible']]
        eligible.sort(key=lambda x: x['subsidy_path_saves'], reverse=True)
        return eligible[:10]
    else:  # all
        return rows


def _apply_sorting(rows: List[Dict], sort_option: str) -> List[Dict]:
    """Apply sorting to comparison rows."""
    if sort_option == 'savings':
        return sorted(rows, key=lambda x: x['subsidy_path_saves'], reverse=True)
    elif sort_option == 'age':
        return sorted(rows, key=lambda x: x['age'])
    elif sort_option == 'income':
        return sorted(rows, key=lambda x: x['monthly_income'], reverse=True)
    elif sort_option == 'fpl_pct':
        return sorted(rows, key=lambda x: x['fpl_pct'])
    elif sort_option == 'ee_cost':
        return sorted(rows, key=lambda x: x['ee_cost'])
    elif sort_option == 'affordability_gap':
        # Sort by: unaffordable (over) first, then by gap size descending
        return sorted(rows, key=lambda x: (x['is_affordable'] is True, -x['affordability_gap']))
    elif sort_option == 'subsidy':
        return sorted(rows, key=lambda x: x['govt_subsidy'], reverse=True)
    elif sort_option == 'ee_pays':
        return sorted(rows, key=lambda x: x['ee_pays_with_subsidy'] if x['is_subsidy_eligible'] else float('inf'))
    else:  # name
        return sorted(rows, key=lambda x: x['name'])


def _render_side_by_side_view(rows: List[Dict]) -> None:
    """Render side-by-side comparison table."""
    if not rows:
        st.info("No employees to display")
        return

    # Build DataFrame
    df_data = []
    for row in rows:
        df_data.append({
            'NAME': row['name'],
            'AGE': row['age'],
            'INCOME': row['monthly_income'],
            'LCSP': row['lcsp'],
            'FPL %': f"{row['fpl_pct']:.0f}%" if row['fpl_pct'] else '—',

            # Affordability Path (Blue section)
            'ER Contrib': row['er_contribution'],
            'Subsidy Cutoff': row['affordability_threshold'],
            'EE Cost': row['ee_cost'],
            'Affordability Gap': '✓ Affordable' if row['is_affordable'] else f"${row['affordability_gap']:,.0f} over",

            # Subsidy Path (Green section)
            'Expected Premium': row['expected_premium'],
            'Govt Subsidy': row['govt_subsidy'],
            'EE Pays': row['ee_pays_with_subsidy'],

            # Decision
            'Recommendation': row['recommendation'],
        })

    df = pd.DataFrame(df_data)

    # Format currency columns
    currency_cols = ['INCOME', 'LCSP', 'ER Contrib', 'Subsidy Cutoff', 'EE Cost', 'Expected Premium', 'Govt Subsidy', 'EE Pays']
    for col in currency_cols:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: format_currency(x) if x else '—')

    # Custom styling with colored column groups
    st.markdown("""
    <style>
    /* Affordability section - blue tint (ER Contrib, Threshold, EE Cost, Result) */
    .stDataFrame table thead th:nth-child(6),
    .stDataFrame table thead th:nth-child(7),
    .stDataFrame table thead th:nth-child(8),
    .stDataFrame table thead th:nth-child(9) {
        background-color: #EBF5FF !important;
        border-left: 3px solid #0047AB;
    }

    /* Subsidy section - green tint (Expected Premium, Govt Subsidy, EE Pays) */
    .stDataFrame table thead th:nth-child(10),
    .stDataFrame table thead th:nth-child(11),
    .stDataFrame table thead th:nth-child(12) {
        background-color: #ECFDF5 !important;
        border-left: 3px solid #047857;
    }

    /* Decision section (Recommendation) */
    .stDataFrame table thead th:nth-child(13) {
        background-color: #F9FAFB !important;
        border-left: 3px solid #6B7280;
    }
    </style>
    """, unsafe_allow_html=True)

    # Column configuration for better display
    column_config = {
        'NAME': st.column_config.TextColumn('Employee', width='medium'),
        'AGE': st.column_config.NumberColumn('Age', width='small'),
        'INCOME': st.column_config.TextColumn('Monthly Income', width='small'),
        'LCSP': st.column_config.TextColumn('LCSP', width='small'),
        'FPL %': st.column_config.TextColumn('FPL %', width='small'),
        'ER Contrib': st.column_config.TextColumn('ER Contrib', width='small'),
        'Subsidy Cutoff': st.column_config.TextColumn('Subsidy Cutoff', width='small'),
        'EE Cost': st.column_config.TextColumn('EE Cost', width='small'),
        'Affordability Gap': st.column_config.TextColumn('Affordability Gap', width='medium'),
        'Expected Premium': st.column_config.TextColumn('Expected Premium', width='small'),
        'Govt Subsidy': st.column_config.TextColumn('Subsidy', width='small'),
        'EE Pays': st.column_config.TextColumn('EE Pays', width='small'),
        'Recommendation': st.column_config.TextColumn('Best Path', width='large'),
    }

    st.dataframe(
        df,
        column_config=column_config,
        width="stretch",
        hide_index=True,
        height=600
    )


def _render_best_path_view(rows: List[Dict]) -> None:
    """Render simplified view showing only the best path for each employee."""
    if not rows:
        st.info("No employees to display")
        return

    df_data = []
    for row in rows:
        # Determine best path
        if row['is_medicare']:
            best_path = 'Medicare'
            ee_net_cost = '—'
            path_indicator = '—'
        elif row['is_subsidy_eligible'] and row['subsidy_path_saves'] > 20:
            best_path = 'Subsidy Path'
            ee_net_cost = row['ee_pays_with_subsidy']
            path_indicator = f"✓ Saves ${row['subsidy_path_saves']:,.0f}/mo"
        else:
            best_path = 'Affordability Path'
            ee_net_cost = row['ee_cost']
            path_indicator = '✓ Affordable' if row['is_affordable'] else '⚠ Unaffordable'

        df_data.append({
            'Employee': row['name'],
            'Age': row['age'],
            'ER Contribution': row['er_contribution'],
            'Best Path': best_path,
            'EE Net Cost': ee_net_cost,
            'Status': path_indicator,
            'Subsidy Savings': row['subsidy_path_saves'] if row['is_subsidy_eligible'] else 0,
        })

    df = pd.DataFrame(df_data)

    # Format currency
    df['ER Contribution'] = df['ER Contribution'].apply(format_currency)
    df['EE Net Cost'] = df['EE Net Cost'].apply(lambda x: format_currency(x) if isinstance(x, (int, float)) else x)
    df['Subsidy Savings'] = df['Subsidy Savings'].apply(lambda x: format_currency(x) if x > 0 else '—')

    st.dataframe(df, width="stretch", hide_index=True, height=600)


def _render_detailed_view(rows: List[Dict]) -> None:
    """Render detailed breakdown with all calculations visible."""
    if not rows:
        st.info("No employees to display")
        return

    # For detailed view, show expandable rows with full calculation breakdown
    for row in rows:
        with st.expander(f"**{row['name']}** (Age {row['age']}) — {row['recommendation']}", expanded=False):
            col1, col2, col3 = st.columns(3)

            with col1:
                st.markdown("##### Employee Info")
                st.markdown(f"**Monthly Income:** {format_currency(row['monthly_income']) if row['monthly_income'] else '—'}")
                st.markdown(f"**Family Status:** {row['family_status']}")
                st.markdown(f"**LCSP:** {format_currency(row['lcsp'])}")
                st.markdown(f"**FPL %:** {row['fpl_pct']:.0f}%" if row['fpl_pct'] else "—")

            with col2:
                st.markdown("##### Path 1: ICHRA Affordable")
                st.markdown(f"**ER Contribution:** {format_currency(row['er_contribution'])}")
                st.markdown(f"**Subsidy Cutoff (9.96%):** {format_currency(row['affordability_threshold']) if row['affordability_threshold'] else '—'}")
                st.markdown(f"**EE Cost:** {format_currency(row['ee_cost'])}")
                if row['is_affordable'] is True:
                    st.success(f"✓ Affordable (${row['affordability_gap']:,.0f} under threshold)")
                elif row['is_affordable'] is False:
                    st.error(f"✗ Unaffordable (${row['affordability_gap']:,.0f} over threshold)")
                else:
                    st.info("Cannot determine (income data missing)")

            with col3:
                st.markdown("##### Path 2: Subsidy Eligible")
                if row['is_medicare']:
                    st.info("Medicare eligible (65+) — not eligible for ACA subsidies")
                elif row['is_subsidy_eligible']:
                    st.markdown(f"**Expected Premium:** {format_currency(row['expected_premium'])}")
                    st.markdown(f"**Government Subsidy:** {format_currency(row['govt_subsidy'])}")
                    st.markdown(f"**EE Pays:** {format_currency(row['ee_pays_with_subsidy'])}")
                    st.success(f"✓ Saves ${row['subsidy_path_saves']:,.0f}/mo vs affordability path")
                else:
                    st.warning("Not eligible for subsidies")

            # Calculation formula
            with st.container():
                st.markdown("---")
                st.markdown("##### Calculation Details")
                st.code(f"""
Affordability Test:
  LCSP ({format_currency(row['lcsp'])}) - ER Contrib ({format_currency(row['er_contribution'])}) = EE Cost ({format_currency(row['ee_cost'])})
  EE Cost ({format_currency(row['ee_cost'])}) vs Subsidy Cutoff ({format_currency(row['affordability_threshold'])})
  → {"Affordable" if row['is_affordable'] else "Unaffordable" if row['is_affordable'] is not None else "Unknown"}

Subsidy Path:
  Income ({format_currency(row['monthly_income']) if row['monthly_income'] else '—'}) × {row['fpl_pct']:.0f}% FPL
  → Expected Premium: {format_currency(row['expected_premium'])}
  → Govt Subsidy: {format_currency(row['govt_subsidy'])}
  → EE Pays: {format_currency(row['ee_pays_with_subsidy'])}
  → Saves: {format_currency(row['subsidy_path_saves'])} vs affordability path
                """)


def _render_summary_totals(rows: List[Dict]) -> None:
    """Render summary totals row showing aggregate impact."""
    if not rows:
        return

    total_employees = len(rows)
    subsidy_eligible = sum(1 for r in rows if r['is_subsidy_eligible'])
    medicare = sum(1 for r in rows if r['is_medicare'])

    total_er_contrib_affordable = sum(r['er_contribution'] for r in rows)
    total_er_contrib_subsidy = sum(r['er_contribution'] for r in rows if r['is_subsidy_eligible'])

    total_ee_cost_affordable = sum(r['ee_cost'] for r in rows)
    total_ee_cost_subsidy = sum(r['ee_pays_with_subsidy'] for r in rows if r['is_subsidy_eligible'])

    total_savings = sum(r['subsidy_path_saves'] for r in rows if r['is_subsidy_eligible'])

    st.markdown("---")
    st.markdown("### Summary Totals")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Employees", total_employees)
        st.caption(f"Subsidy Eligible: {subsidy_eligible} | Medicare: {medicare}")

    with col2:
        st.metric("Affordability Path", f"{format_currency(total_er_contrib_affordable)}/mo")
        st.caption(f"ER pays • Employees pay {format_currency(total_ee_cost_affordable)}/mo")

    with col3:
        st.metric("Subsidy Path", f"{format_currency(total_er_contrib_subsidy)}/mo")
        st.caption(f"ER pays • Employees pay {format_currency(total_ee_cost_subsidy)}/mo")

    with col4:
        er_saves = total_er_contrib_affordable - total_er_contrib_subsidy
        st.metric("Employer Saves", f"{format_currency(er_saves)}/mo", delta=f"{format_currency(total_savings)}/mo employees save")
        st.caption("with subsidy strategy")
