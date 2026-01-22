"""
Employee Breakdown Component

4-tab component showing employee-level contribution details:
- Summary (default): Total ER cost, avg contribution, mode-specific summary
- By Age: Visual breakdown by age bands with bar chart
- By Family Status: Visual breakdown by family status with bar chart
- Full Detail: Per-employee table with pagination
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from typing import Dict, List, Any, Optional

from contribution_eval import OperatingMode
from contribution_eval.utils.formatting import format_currency
from contribution_eval.utils.calculations import calculate_age_band

# Brand colors
BRAND_PRIMARY = '#0047AB'
BRAND_ACCENT = '#37BEAE'
GREEN = '#047857'
AMBER = '#B45309'
GRAY = '#9CA3AF'


ROWS_PER_PAGE = 20


def render_employee_breakdown(
    mode: OperatingMode,
    strategy_result: Dict[str, Any],
    affordability_data: Optional[Dict[str, Any]] = None,
    subsidy_data: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Render the 4-tab employee breakdown section.

    Args:
        mode: Current operating mode (determines columns)
        strategy_result: Strategy calculation result with employee_contributions
        affordability_data: Affordability analysis (ALE mode)
        subsidy_data: Subsidy analysis (Subsidy mode)
    """
    st.markdown("### Employee Breakdown")

    employee_contributions = strategy_result.get('employee_contributions', {})

    # Create tabs based on mode
    if mode == OperatingMode.NON_ALE_SUBSIDY:
        # Import comparison component for subsidy mode
        from .affordability_subsidy_comparison import render_affordability_subsidy_comparison

        tab_comparison, tab_summary, tab_age, tab_family, tab_detail = st.tabs([
            "⚖️ Affordability vs Subsidy",
            "📊 Summary",
            "🎂 By Age",
            "👨‍👩‍👧‍👦 By Family Status",
            "📋 Full Detail"
        ])

        with tab_comparison:
            render_affordability_subsidy_comparison(
                employee_contributions=employee_contributions,
                subsidy_data=subsidy_data,
                affordability_threshold=0.0996,
            )
    else:
        tab_summary, tab_age, tab_family, tab_detail = st.tabs([
            "📊 Summary",
            "🎂 By Age",
            "👨‍👩‍👧‍👦 By Family Status",
            "📋 Full Detail"
        ])

    with tab_summary:
        _render_summary_tab(mode, strategy_result, affordability_data, subsidy_data)

    with tab_age:
        _render_age_tab_graph(employee_contributions)

    with tab_family:
        _render_family_tab_graph(employee_contributions)

    with tab_detail:
        _render_detail_tab(mode, employee_contributions, affordability_data, subsidy_data)


def _render_summary_tab(
    mode: OperatingMode,
    strategy_result: Dict[str, Any],
    affordability_data: Optional[Dict[str, Any]],
    subsidy_data: Optional[Dict[str, Any]],
) -> None:
    """Render the Summary tab with metrics and charts."""
    employee_contributions = strategy_result.get('employee_contributions', {})
    total_monthly = strategy_result.get('total_monthly', 0)
    total_annual = strategy_result.get('total_annual', 0)
    employee_count = strategy_result.get('employees_covered', 0)
    avg_contribution = total_monthly / employee_count if employee_count > 0 else 0

    # Top metrics row
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total ER Cost", format_currency(total_monthly) + "/mo")
        st.caption(f"{format_currency(total_annual)}/yr")

    with col2:
        st.metric("Avg Contribution", format_currency(avg_contribution))
        st.caption("Per employee/month")

    with col3:
        if mode == OperatingMode.ALE and affordability_data:
            affordable = affordability_data.get('affordable_count', 0)
            total = affordability_data.get('total_analyzed', employee_count)
            st.metric("Affordable", f"{affordable}/{total}")
            st.caption("Employees")
        elif mode == OperatingMode.NON_ALE_SUBSIDY and subsidy_data:
            has_income_data = subsidy_data.get('has_income_data', True)
            if has_income_data:
                eligible = subsidy_data.get('eligible_count', 0)
                medicare = subsidy_data.get('medicare_count', 0)
                analyzable = employee_count - medicare
                st.metric("Subsidy Eligible", f"{eligible}/{analyzable}")
                st.caption("Employees (excl. Medicare)" if medicare > 0 else "Employees")
            else:
                st.metric("Subsidy Eligible", "—")
                st.caption("Income data required")
        else:
            # Standard mode - vs current if available
            current_total = sum(
                e.get('current_er_contribution', 0)
                for e in employee_contributions.values()
            )
            if current_total > 0:
                delta = total_monthly - current_total
                arrow = "↓" if delta < 0 else "↑"
                st.metric("vs Current", f"{arrow} {format_currency(abs(delta))}/mo")
                st.caption("Savings" if delta < 0 else "Increase")
            else:
                st.metric("Employees", employee_count)
                st.caption("Covered")

    # Charts section
    st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)

    # Build chart data
    age_data = _build_age_distribution_data(employee_contributions)
    status_data = _build_status_data(mode, employee_contributions, affordability_data, subsidy_data)
    family_data = _build_family_distribution_data(employee_contributions)

    # Charts row 1: Age distribution + Status breakdown
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.markdown("**Contribution by Age Band**")
        if age_data:
            fig_age = px.bar(
                age_data,
                x='band',
                y='avg_contribution',
                text='avg_contribution',
                color_discrete_sequence=[BRAND_PRIMARY],
            )
            fig_age.update_traces(
                texttemplate='$%{text:,.0f}',
                textposition='outside',
                hovertemplate='<b>%{x}</b><br>Avg: $%{y:,.0f}<br>Employees: %{customdata}<extra></extra>',
                customdata=[d['employees'] for d in age_data],
            )
            # Get max value for y-axis range
            max_val = max(d['avg_contribution'] for d in age_data)
            fig_age.update_layout(
                xaxis_title='',
                yaxis_title='',
                showlegend=False,
                margin=dict(l=20, r=20, t=40, b=40),  # Increased top margin
                height=300,
                yaxis=dict(
                    tickformat='$,.0f',
                    range=[0, max_val * 1.25],  # Add 25% headroom for labels
                ),
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
            )
            fig_age.update_xaxes(tickfont=dict(size=11))
            fig_age.update_yaxes(tickfont=dict(size=11), gridcolor='#E5E7EB')
            st.plotly_chart(fig_age, width="stretch", config={'displayModeBar': False})
        else:
            st.info("No age data available")

    with chart_col2:
        # Status title varies by mode
        if mode == OperatingMode.NON_ALE_SUBSIDY:
            st.markdown("**Subsidy Eligibility**")
        elif mode == OperatingMode.ALE:
            st.markdown("**Affordability Status**")
        else:
            st.markdown("**Cost Impact vs Current**")

        if status_data and any(d['value'] > 0 for d in status_data):
            fig_status = go.Figure(data=[go.Pie(
                labels=[d['name'] for d in status_data],
                values=[d['value'] for d in status_data],
                marker=dict(colors=[d['color'] for d in status_data]),
                hole=0.5,
                textinfo='value',
                textfont=dict(size=14),
                hovertemplate='<b>%{label}</b><br>%{value} employees<extra></extra>',
            )])
            fig_status.update_layout(
                showlegend=True,
                legend=dict(
                    orientation='h',
                    yanchor='bottom',
                    y=-0.15,
                    xanchor='center',
                    x=0.5,
                    font=dict(size=11),
                ),
                margin=dict(l=20, r=20, t=40, b=60),  # Increased top margin
                height=300,
                paper_bgcolor='rgba(0,0,0,0)',
            )
            st.plotly_chart(fig_status, width="stretch", config={'displayModeBar': False})
        else:
            st.info("No status data available")

    # Chart row 2: Family status distribution
    st.markdown("**Contribution by Family Status**")
    if family_data:
        fig_family = px.bar(
            family_data,
            y='status',
            x='avg_contribution',
            text='avg_contribution',
            orientation='h',
            color_discrete_sequence=[BRAND_PRIMARY],
        )
        fig_family.update_traces(
            texttemplate='$%{text:,.0f}',
            textposition='outside',
            hovertemplate='<b>%{y}</b><br>Avg: $%{x:,.0f}<br>Employees: %{customdata}<extra></extra>',
            customdata=[d['employees'] for d in family_data],
        )
        # Get max value for x-axis range
        max_val = max(d['avg_contribution'] for d in family_data)
        fig_family.update_layout(
            xaxis_title='',
            yaxis_title='',
            showlegend=False,
            margin=dict(l=20, r=80, t=10, b=20),  # Increased right margin
            height=180,
            xaxis=dict(
                tickformat='$,.0f',
                range=[0, max_val * 1.3],  # Add 30% headroom for labels
            ),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
        )
        fig_family.update_xaxes(tickfont=dict(size=11), gridcolor='#E5E7EB')
        fig_family.update_yaxes(tickfont=dict(size=11))
        st.plotly_chart(fig_family, width="stretch", config={'displayModeBar': False})
    else:
        st.info("No family status data available")

    # ALE Mode: Show employees needing higher contributions
    if mode == OperatingMode.ALE and affordability_data:
        _render_needs_adjustment_section(employee_contributions, affordability_data)


def _build_age_distribution_data(employee_contributions: Dict[str, Dict]) -> List[Dict]:
    """Build age distribution data for chart."""
    age_bands = ['21-29', '30-39', '40-49', '50-59', '60-64']
    grouped = {band: {'employees': 0, 'total': 0} for band in age_bands}

    for emp_id, data in employee_contributions.items():
        age = data.get('age', 30)
        band = calculate_age_band(age)
        if band in grouped:
            grouped[band]['employees'] += 1
            grouped[band]['total'] += data.get('monthly_contribution', 0)

    result = []
    for band in age_bands:
        if grouped[band]['employees'] > 0:
            result.append({
                'band': band,
                'avg_contribution': grouped[band]['total'] / grouped[band]['employees'],
                'employees': grouped[band]['employees'],
                'total': grouped[band]['total'],
            })

    return result


def _build_status_data(
    mode: OperatingMode,
    employee_contributions: Dict[str, Dict],
    affordability_data: Optional[Dict[str, Any]],
    subsidy_data: Optional[Dict[str, Any]],
) -> List[Dict]:
    """Build status breakdown data for pie chart."""
    total = len(employee_contributions)
    if total == 0:
        return []

    if mode == OperatingMode.NON_ALE_SUBSIDY and subsidy_data:
        has_income_data = subsidy_data.get('has_income_data', True)
        if not has_income_data:
            # Census missing income data - show placeholder
            return [
                {'name': 'Cannot Analyze', 'value': total, 'color': GRAY},
            ]

        eligible = subsidy_data.get('eligible_count', 0)
        medicare = subsidy_data.get('medicare_count', 0)
        ineligible_non_medicare = total - eligible - medicare

        # Build pie chart segments
        segments = []
        if eligible > 0:
            segments.append({'name': 'Subsidy Eligible', 'value': eligible, 'color': GREEN})
        if ineligible_non_medicare > 0:
            segments.append({'name': 'Not Eligible', 'value': ineligible_non_medicare, 'color': GRAY})
        if medicare > 0:
            segments.append({'name': 'Medicare (65+)', 'value': medicare, 'color': AMBER})

        return segments if segments else [{'name': 'None', 'value': total, 'color': GRAY}]

    elif mode == OperatingMode.ALE and affordability_data:
        affordable = affordability_data.get('affordable_count', 0)
        return [
            {'name': 'Affordable', 'value': affordable, 'color': GREEN},
            {'name': 'Needs Adjustment', 'value': total - affordable, 'color': AMBER},
        ]

    else:
        # Standard mode: cost impact
        saves_count = sum(
            1 for e in employee_contributions.values()
            if e.get('current_er_contribution', 0) > 0 and
            e.get('monthly_contribution', 0) < e.get('current_er_contribution', 0)
        )
        has_current = sum(
            1 for e in employee_contributions.values()
            if e.get('current_er_contribution', 0) > 0
        )
        if has_current > 0:
            return [
                {'name': 'Saves vs Current', 'value': saves_count, 'color': GREEN},
                {'name': 'Costs More', 'value': has_current - saves_count, 'color': AMBER},
            ]
        return []


def _build_family_distribution_data(employee_contributions: Dict[str, Dict]) -> List[Dict]:
    """Build family status distribution data for chart."""
    status_labels = {
        'EE': 'Employee Only',
        'ES': 'Employee + Spouse',
        'EC': 'Employee + Child',
        'F': 'Family',
    }

    grouped = {s: {'employees': 0, 'total': 0} for s in status_labels.keys()}

    for emp_id, data in employee_contributions.items():
        status = data.get('family_status', 'EE').upper()
        if status in grouped:
            grouped[status]['employees'] += 1
            grouped[status]['total'] += data.get('monthly_contribution', 0)

    result = []
    for status in ['EE', 'ES', 'EC', 'F']:
        if grouped[status]['employees'] > 0:
            result.append({
                'status': status_labels[status],
                'status_code': status,
                'avg_contribution': grouped[status]['total'] / grouped[status]['employees'],
                'employees': grouped[status]['employees'],
                'total': grouped[status]['total'],
            })

    return result


def _render_needs_adjustment_section(
    employee_contributions: Dict[str, Dict],
    affordability_data: Dict[str, Any],
) -> None:
    """Render section showing employees who need higher contributions (ALE mode)."""
    employee_affordability = affordability_data.get('employee_affordability', {})

    # Find employees who are not affordable
    needs_adjustment = []
    for emp_id, aff_data in employee_affordability.items():
        if not aff_data.get('is_affordable', True):
            emp_data = employee_contributions.get(emp_id, {})
            needs_adjustment.append({
                'name': emp_data.get('name', emp_id),
                'age': emp_data.get('age', '—'),
                'current_contribution': emp_data.get('monthly_contribution', 0),
                'gap': aff_data.get('gap', 0),
                'min_needed': emp_data.get('monthly_contribution', 0) + aff_data.get('gap', 0),
            })

    if not needs_adjustment:
        return  # All employees are affordable, no section needed

    # Sort by gap (highest first)
    needs_adjustment.sort(key=lambda x: x['gap'], reverse=True)

    st.markdown("---")
    st.markdown(f"""
    <div style="background: #FEF3C7; border-left: 4px solid #B45309; padding: 16px; border-radius: 8px; margin: 16px 0;">
        <div style="font-weight: 600; color: #92400E; margin-bottom: 8px;">
            ⚠️ {len(needs_adjustment)} Employee{'s' if len(needs_adjustment) != 1 else ''} Need Higher Contributions
        </div>
        <div style="color: #78350F; font-size: 14px;">
            The following employees require contribution increases to meet affordability requirements.
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Build DataFrame for display
    df = pd.DataFrame(needs_adjustment)
    df = df.rename(columns={
        'name': 'Employee',
        'age': 'Age',
        'current_contribution': 'Current',
        'gap': 'Gap',
        'min_needed': 'Min Needed',
    })

    # Format currency columns
    df['Current'] = df['Current'].apply(lambda x: format_currency(x))
    df['Gap'] = df['Gap'].apply(lambda x: f"+{format_currency(x)}")
    df['Min Needed'] = df['Min Needed'].apply(lambda x: format_currency(x))

    # Show up to 10 employees, with option to see more in Full Detail
    display_df = df.head(10)
    st.dataframe(display_df, width="stretch", hide_index=True)

    if len(needs_adjustment) > 10:
        st.caption(f"Showing top 10 by gap. See **Full Detail** tab for all {len(needs_adjustment)} employees.")


def _render_age_tab_graph(employee_contributions: Dict[str, Dict]) -> None:
    """Render the By Age tab with visual graphs."""
    if not employee_contributions:
        st.info("No employee data available")
        return

    age_data = _build_age_distribution_data(employee_contributions)

    if not age_data:
        st.info("No age data available")
        return

    # Summary metrics
    col1, col2, col3 = st.columns(3)
    total_monthly = sum(d['total'] for d in age_data)
    total_employees = sum(d['employees'] for d in age_data)

    with col1:
        st.metric("Total Monthly", format_currency(total_monthly))
    with col2:
        st.metric("Employees", total_employees)
    with col3:
        avg = total_monthly / total_employees if total_employees > 0 else 0
        st.metric("Average", format_currency(avg))

    st.markdown("---")

    # Bar chart showing total contribution by age band
    st.markdown("**Total Contribution by Age Band**")
    fig_total = px.bar(
        age_data,
        x='band',
        y='total',
        text='total',
        color_discrete_sequence=[BRAND_PRIMARY],
    )
    fig_total.update_traces(
        texttemplate='$%{text:,.0f}',
        textposition='outside',
        hovertemplate='<b>%{x}</b><br>Total: $%{y:,.0f}<br>Employees: %{customdata}<extra></extra>',
        customdata=[d['employees'] for d in age_data],
    )
    max_val = max(d['total'] for d in age_data)
    fig_total.update_layout(
        xaxis_title='Age Band',
        yaxis_title='Total Contribution',
        showlegend=False,
        margin=dict(l=20, r=20, t=40, b=40),
        height=300,
        yaxis=dict(tickformat='$,.0f', range=[0, max_val * 1.25]),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
    )
    fig_total.update_xaxes(tickfont=dict(size=12))
    fig_total.update_yaxes(tickfont=dict(size=11), gridcolor='#E5E7EB')
    st.plotly_chart(fig_total, width="stretch", config={'displayModeBar': False})

    # Bar chart showing employee count by age band
    st.markdown("**Employee Count by Age Band**")
    fig_count = px.bar(
        age_data,
        x='band',
        y='employees',
        text='employees',
        color_discrete_sequence=[BRAND_ACCENT],
    )
    fig_count.update_traces(
        textposition='outside',
        hovertemplate='<b>%{x}</b><br>Employees: %{y}<extra></extra>',
    )
    max_emp = max(d['employees'] for d in age_data)
    fig_count.update_layout(
        xaxis_title='Age Band',
        yaxis_title='Employees',
        showlegend=False,
        margin=dict(l=20, r=20, t=40, b=40),
        height=250,
        yaxis=dict(range=[0, max_emp * 1.25]),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
    )
    fig_count.update_xaxes(tickfont=dict(size=12))
    fig_count.update_yaxes(tickfont=dict(size=11), gridcolor='#E5E7EB')
    st.plotly_chart(fig_count, width="stretch", config={'displayModeBar': False})

    # Table summary
    st.markdown("**Summary Table**")
    df = pd.DataFrame(age_data)
    df = df.rename(columns={
        'band': 'Age Band',
        'employees': 'Employees',
        'total': 'Total',
        'avg_contribution': 'Average'
    })
    df['Total'] = df['Total'].apply(lambda x: format_currency(x))
    df['Average'] = df['Average'].apply(lambda x: format_currency(x))
    st.dataframe(df[['Age Band', 'Employees', 'Total', 'Average']], width="stretch", hide_index=True)


def _render_family_tab_graph(employee_contributions: Dict[str, Dict]) -> None:
    """Render the By Family Status tab with visual graphs."""
    if not employee_contributions:
        st.info("No employee data available")
        return

    family_data = _build_family_distribution_data(employee_contributions)

    if not family_data:
        st.info("No family status data available")
        return

    # Summary metrics
    col1, col2, col3 = st.columns(3)
    total_monthly = sum(d['total'] for d in family_data)
    total_employees = sum(d['employees'] for d in family_data)

    with col1:
        st.metric("Total Monthly", format_currency(total_monthly))
    with col2:
        st.metric("Employees", total_employees)
    with col3:
        avg = total_monthly / total_employees if total_employees > 0 else 0
        st.metric("Average", format_currency(avg))

    st.markdown("---")

    # Bar chart showing total contribution by family status
    st.markdown("**Total Contribution by Family Status**")
    fig_total = px.bar(
        family_data,
        x='status',
        y='total',
        text='total',
        color_discrete_sequence=[BRAND_PRIMARY],
    )
    fig_total.update_traces(
        texttemplate='$%{text:,.0f}',
        textposition='outside',
        hovertemplate='<b>%{x}</b><br>Total: $%{y:,.0f}<br>Employees: %{customdata}<extra></extra>',
        customdata=[d['employees'] for d in family_data],
    )
    max_val = max(d['total'] for d in family_data)
    fig_total.update_layout(
        xaxis_title='Family Status',
        yaxis_title='Total Contribution',
        showlegend=False,
        margin=dict(l=20, r=20, t=40, b=40),
        height=300,
        yaxis=dict(tickformat='$,.0f', range=[0, max_val * 1.25]),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
    )
    fig_total.update_xaxes(tickfont=dict(size=11))
    fig_total.update_yaxes(tickfont=dict(size=11), gridcolor='#E5E7EB')
    st.plotly_chart(fig_total, width="stretch", config={'displayModeBar': False})

    # Pie chart showing employee distribution
    st.markdown("**Employee Distribution by Family Status**")
    fig_pie = go.Figure(data=[go.Pie(
        labels=[d['status'] for d in family_data],
        values=[d['employees'] for d in family_data],
        marker=dict(colors=[BRAND_PRIMARY, BRAND_ACCENT, GREEN, AMBER][:len(family_data)]),
        hole=0.4,
        textinfo='label+percent',
        textfont=dict(size=12),
        hovertemplate='<b>%{label}</b><br>%{value} employees<br>%{percent}<extra></extra>',
    )])
    fig_pie.update_layout(
        showlegend=False,
        margin=dict(l=20, r=20, t=20, b=20),
        height=280,
        paper_bgcolor='rgba(0,0,0,0)',
    )
    st.plotly_chart(fig_pie, width="stretch", config={'displayModeBar': False})

    # Table summary
    st.markdown("**Summary Table**")
    df = pd.DataFrame(family_data)
    df = df.rename(columns={
        'status': 'Family Status',
        'employees': 'Employees',
        'total': 'Total',
        'avg_contribution': 'Average'
    })
    df['Total'] = df['Total'].apply(lambda x: format_currency(x))
    df['Average'] = df['Average'].apply(lambda x: format_currency(x))
    st.dataframe(df[['Family Status', 'Employees', 'Total', 'Average']], width="stretch", hide_index=True)


def _render_detail_tab(
    mode: OperatingMode,
    employee_contributions: Dict[str, Dict],
    affordability_data: Optional[Dict[str, Any]],
    subsidy_data: Optional[Dict[str, Any]],
) -> None:
    """Render the Full Detail tab with pagination."""
    if not employee_contributions:
        st.info("No employee data available")
        return

    # Build DataFrame
    rows = []
    for emp_id, data in employee_contributions.items():
        row = {
            'Employee': data.get('name', emp_id),
            'Age': data.get('age', '—'),
            'State': data.get('state', '—'),
            'Family': data.get('family_status', 'EE'),
            'Contribution': data.get('monthly_contribution', 0),
        }

        # Mode-specific columns
        if mode == OperatingMode.NON_ALE_STANDARD:
            # vs Current column
            current = data.get('current_er_contribution', 0)
            if current > 0:
                delta = data.get('monthly_contribution', 0) - current
                row['vs Current'] = delta
            else:
                row['vs Current'] = None

        elif mode == OperatingMode.NON_ALE_SUBSIDY and subsidy_data:
            # Subsidy columns
            has_income_data = subsidy_data.get('has_income_data', True)
            emp_subsidy = _find_employee_in_subsidy_data(emp_id, subsidy_data)

            # Check Medicare status from subsidy_data or directly from age
            is_medicare = (
                (emp_subsidy and emp_subsidy.get('is_medicare', False)) or
                (data.get('age') and int(data.get('age', 0)) >= 65)
            )

            if is_medicare:
                # Medicare-eligible: show dashes (can't get ACA subsidies)
                row['Eligible?'] = '—'
                row['Est. Subsidy'] = None  # Will format as "—"
            elif emp_subsidy:
                if not has_income_data:
                    row['Eligible?'] = '—'  # Can't determine
                    row['Est. Subsidy'] = 0
                else:
                    row['Eligible?'] = '✓' if emp_subsidy.get('eligible') else '✗'
                    row['Est. Subsidy'] = emp_subsidy.get('subsidy', 0)

        elif mode == OperatingMode.ALE and affordability_data:
            # Affordability columns
            emp_aff = _find_employee_in_affordability_data(emp_id, affordability_data)
            if emp_aff:
                row['Affordable?'] = '✓' if emp_aff.get('is_affordable') else '✗'
                row['Gap'] = emp_aff.get('gap', 0) if not emp_aff.get('is_affordable') else 0

        rows.append(row)

    df = pd.DataFrame(rows)

    # Format currency columns
    if 'Contribution' in df.columns:
        df['Contribution'] = df['Contribution'].apply(lambda x: format_currency(x))
    if 'vs Current' in df.columns:
        df['vs Current'] = df['vs Current'].apply(
            lambda x: f"+{format_currency(x)}" if pd.notna(x) and x > 0 else format_currency(x) if pd.notna(x) else '—'
        )
    if 'Est. Subsidy' in df.columns:
        df['Est. Subsidy'] = df['Est. Subsidy'].apply(lambda x: format_currency(x) if x else '—')
    if 'Gap' in df.columns:
        df['Gap'] = df['Gap'].apply(lambda x: format_currency(x) if x else '—')

    # Pagination
    total_rows = len(df)
    total_pages = (total_rows + ROWS_PER_PAGE - 1) // ROWS_PER_PAGE

    if total_pages > 1:
        # Initialize page state if not exists
        if 'detail_page' not in st.session_state:
            st.session_state.detail_page = 1

        # Ensure page is within valid range
        current_page = max(1, min(st.session_state.detail_page, total_pages))

        # Pagination controls row
        col_prev, col_pages, col_next = st.columns([1, 3, 1])

        with col_prev:
            if st.button("← Previous", disabled=(current_page == 1), key="detail_prev", use_container_width=True):
                st.session_state.detail_page = current_page - 1
                st.rerun()

        with col_pages:
            # Page selector dropdown
            page_options = list(range(1, total_pages + 1))
            selected_page = st.selectbox(
                "Page",
                options=page_options,
                index=current_page - 1,
                format_func=lambda x: f"Page {x} of {total_pages}",
                key="detail_page_select",
                label_visibility="collapsed",
            )
            if selected_page != current_page:
                st.session_state.detail_page = selected_page
                st.rerun()

        with col_next:
            if st.button("Next →", disabled=(current_page == total_pages), key="detail_next", use_container_width=True):
                st.session_state.detail_page = current_page + 1
                st.rerun()

        start_idx = (current_page - 1) * ROWS_PER_PAGE
        end_idx = min(start_idx + ROWS_PER_PAGE, total_rows)

        st.caption(f"Showing {start_idx + 1}-{end_idx} of {total_rows} employees")
        st.dataframe(df.iloc[start_idx:end_idx], width="stretch", hide_index=True)
    else:
        st.dataframe(df, width="stretch", hide_index=True)


def _find_employee_in_subsidy_data(emp_id: str, subsidy_data: Dict[str, Any]) -> Optional[Dict]:
    """Find employee data in subsidy analysis results."""
    by_employee = subsidy_data.get('by_employee', [])
    for emp in by_employee:
        if emp.get('employee_id') == emp_id:
            return emp
    return None


def _find_employee_in_affordability_data(emp_id: str, affordability_data: Dict[str, Any]) -> Optional[Dict]:
    """Find employee data in affordability analysis results."""
    employee_affordability = affordability_data.get('employee_affordability', {})
    return employee_affordability.get(emp_id)
