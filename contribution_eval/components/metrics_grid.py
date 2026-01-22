"""
Metrics Grid Component

Displays 4 key metrics that vary by operating mode:

| Card | Standard | Subsidy-optimized | ALE |
|------|----------|-------------------|-----|
| 1 | ER Cost (mo/yr) | ER Cost (mo/yr) | ER Cost (mo/yr) |
| 2 | vs Current | Subsidies Unlocked | Affordable (X/Y ✓ or ⚠️) |
| 3 | Employees | Eligible (X/Y) | vs Current |
| 4 | Avg/Employee | Avg/Employee | Avg/Employee |
"""

import streamlit as st
from typing import Dict, Any, Optional

from contribution_eval import OperatingMode
from contribution_eval.utils.formatting import format_currency


def render_metrics_grid(
    mode: OperatingMode,
    strategy_result: Dict[str, Any],
    current_er_spend: Optional[float] = None,
    affordability_data: Optional[Dict[str, Any]] = None,
    subsidy_data: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Render the 4-column metrics grid.

    Metrics displayed depend on the operating mode:
    - Standard: ER Cost, vs Current (or Employees), Employees, Avg/Employee
    - Subsidy: ER Cost, Subsidies Unlocked, Eligible, Avg/Employee
    - ALE: ER Cost, Affordable, vs Current, Avg/Employee

    Args:
        mode: Current operating mode
        strategy_result: Strategy calculation result
        current_er_spend: Current monthly employer spend (if available)
        affordability_data: Affordability analysis (ALE mode)
        subsidy_data: Subsidy analysis (Subsidy mode)
    """
    total_monthly = strategy_result.get('total_monthly', 0)
    total_annual = strategy_result.get('total_annual', 0)
    total_employees = strategy_result.get('employees_covered', 0)
    medicare_excluded = strategy_result.get('medicare_excluded_count', 0)

    # Active employee count excludes Medicare-eligible (65+) who have $0 contributions
    employee_count = total_employees - medicare_excluded
    avg_per_employee = total_monthly / employee_count if employee_count > 0 else 0

    # Calculate vs current
    vs_current = None
    if current_er_spend and current_er_spend > 0:
        vs_current = total_monthly - current_er_spend

    # Build metrics based on mode
    if mode == OperatingMode.NON_ALE_STANDARD:
        metrics = _build_standard_metrics(
            total_monthly, total_annual, employee_count, avg_per_employee, vs_current
        )
    elif mode == OperatingMode.NON_ALE_SUBSIDY:
        metrics = _build_subsidy_metrics(
            total_monthly, total_annual, employee_count, avg_per_employee, subsidy_data
        )
    else:  # ALE
        metrics = _build_ale_metrics(
            total_monthly, total_annual, employee_count, avg_per_employee,
            vs_current, affordability_data
        )

    # Render the grid
    cols = st.columns(4)
    for i, metric in enumerate(metrics):
        with cols[i]:
            _render_metric_card(metric)

    # Add spacing after metrics grid
    st.markdown("<div style='margin-bottom: 1.5rem;'></div>", unsafe_allow_html=True)


def _build_standard_metrics(
    total_monthly: float,
    total_annual: float,
    employee_count: int,
    avg_per_employee: float,
    vs_current: Optional[float],
) -> list:
    """Build metrics for Non-ALE Standard mode."""
    metrics = [
        {
            'label': 'ER Cost',
            'value': format_currency(total_monthly),
            'sublabel': f'${total_annual:,.0f}/year',
            'variant': 'primary',
        }
    ]

    # Card 2: vs Current or Employees
    if vs_current is not None:
        delta_text = f"${abs(vs_current):,.0f}/mo"
        if vs_current < 0:
            # Savings - show without minus sign
            metrics.append({
                'label': 'vs Current',
                'value': delta_text,
                'sublabel': 'savings',
                'variant': 'success',
            })
        else:
            # Increase - show with plus sign in red
            metrics.append({
                'label': 'vs Current',
                'value': f"+{delta_text}",
                'sublabel': 'increase',
                'variant': 'danger',
            })
    else:
        metrics.append({
            'label': 'Employees',
            'value': str(employee_count),
            'sublabel': 'covered',
            'variant': 'default',
        })

    # Card 3: Employees (if not already shown)
    if vs_current is not None:
        metrics.append({
            'label': 'Employees',
            'value': str(employee_count),
            'sublabel': 'covered',
            'variant': 'default',
        })
    else:
        # Show age distribution summary
        metrics.append({
            'label': 'Coverage',
            'value': '100%',
            'sublabel': 'of census',
            'variant': 'default',
        })

    # Card 4: Avg/Employee
    metrics.append({
        'label': 'Avg/Employee',
        'value': format_currency(avg_per_employee),
        'sublabel': 'monthly',
        'variant': 'default',
    })

    return metrics


def _build_subsidy_metrics(
    total_monthly: float,
    total_annual: float,
    employee_count: int,
    avg_per_employee: float,
    subsidy_data: Optional[Dict[str, Any]],
) -> list:
    """Build metrics for Non-ALE Subsidy-optimized mode."""
    metrics = [
        {
            'label': 'ER Cost',
            'value': format_currency(total_monthly),
            'sublabel': f'${total_annual:,.0f}/year',
            'variant': 'primary',
        }
    ]

    # Check census-level income data flag
    has_income_data = subsidy_data.get('has_income_data', True) if subsidy_data else True

    # Card 2: Subsidies Unlocked
    if subsidy_data:
        if not has_income_data:
            # Census missing income data - can't analyze subsidies
            metrics.append({
                'label': 'Subsidies',
                'value': '—',
                'sublabel': 'Income data required',
                'variant': 'warning',
            })
        else:
            eligible = subsidy_data.get('eligible_count', 0)
            total_subsidy = subsidy_data.get('total_monthly_subsidy', 0)
            metrics.append({
                'label': 'Subsidies Unlocked',
                'value': format_currency(total_subsidy),
                'sublabel': f'{eligible} employees eligible',
                'variant': 'success' if eligible > 0 else 'default',
            })
    else:
        metrics.append({
            'label': 'Subsidies',
            'value': '—',
            'sublabel': 'Analyzing...',
            'variant': 'default',
        })

    # Card 3: Eligible
    if subsidy_data:
        if not has_income_data:
            # Census missing income data
            metrics.append({
                'label': 'Eligible',
                'value': '—',
                'sublabel': 'add Monthly Income column',
                'variant': 'warning',
            })
        else:
            eligible = subsidy_data.get('eligible_count', 0)
            medicare = subsidy_data.get('medicare_count', 0)
            total = subsidy_data.get('total_analyzed', employee_count)
            # Show eligible/analyzable (excluding Medicare from denominator context)
            if medicare > 0:
                pct = (eligible / (total - medicare) * 100) if (total - medicare) > 0 else 0
                metrics.append({
                    'label': 'Eligible',
                    'value': f'{eligible}/{total - medicare}',
                    'sublabel': f'{pct:.0f}% (excl. {medicare} Medicare)',
                    'variant': 'default',
                })
            else:
                pct = (eligible / total * 100) if total > 0 else 0
                metrics.append({
                    'label': 'Eligible',
                    'value': f'{eligible}/{total}',
                    'sublabel': f'{pct:.0f}% of workforce',
                    'variant': 'default',
                })
    else:
        metrics.append({
            'label': 'Eligible',
            'value': '—',
            'sublabel': 'needs income data',
            'variant': 'default',
        })

    # Card 4: Avg/Employee
    metrics.append({
        'label': 'Avg/Employee',
        'value': format_currency(avg_per_employee),
        'sublabel': 'monthly',
        'variant': 'default',
    })

    return metrics


def _build_ale_metrics(
    total_monthly: float,
    total_annual: float,
    employee_count: int,
    avg_per_employee: float,
    vs_current: Optional[float],
    affordability_data: Optional[Dict[str, Any]],
) -> list:
    """Build metrics for ALE mode."""
    metrics = [
        {
            'label': 'ER Cost',
            'value': format_currency(total_monthly),
            'sublabel': f'${total_annual:,.0f}/year',
            'variant': 'primary',
        }
    ]

    # Card 2: Affordable
    if affordability_data:
        affordable = affordability_data.get('affordable_count', 0)
        total = affordability_data.get('total_analyzed', employee_count)
        all_affordable = affordability_data.get('all_affordable', False)

        if all_affordable:
            metrics.append({
                'label': 'Affordable',
                'value': f'{affordable}/{total} ✓',
                'sublabel': '100% compliant',
                'variant': 'success',
            })
        else:
            gap_count = total - affordable
            metrics.append({
                'label': 'Affordable',
                'value': f'{affordable}/{total} ⚠️',
                'sublabel': f'{gap_count} need adjustment',
                'variant': 'warning',
            })
    else:
        metrics.append({
            'label': 'Affordable',
            'value': '—',
            'sublabel': 'Calculating...',
            'variant': 'default',
        })

    # Card 3: vs Current
    if vs_current is not None:
        delta_text = f"${abs(vs_current):,.0f}/mo"
        if vs_current < 0:
            # Savings - show without minus sign
            metrics.append({
                'label': 'vs Current',
                'value': delta_text,
                'sublabel': 'savings',
                'variant': 'success',
            })
        else:
            # Increase - show with plus sign in red
            metrics.append({
                'label': 'vs Current',
                'value': f"+{delta_text}",
                'sublabel': 'increase',
                'variant': 'danger',
            })
    else:
        metrics.append({
            'label': 'Employees',
            'value': str(employee_count),
            'sublabel': 'covered',
            'variant': 'default',
        })

    # Card 4: Avg/Employee
    metrics.append({
        'label': 'Avg/Employee',
        'value': format_currency(avg_per_employee),
        'sublabel': 'monthly',
        'variant': 'default',
    })

    return metrics


def _render_metric_card(metric: Dict[str, Any]) -> None:
    """Render a single metric card."""
    label = metric.get('label', '')
    value = metric.get('value', '—')
    sublabel = metric.get('sublabel', '')
    variant = metric.get('variant', 'default')

    variant_class = f"metric-card--{variant}" if variant != 'default' else ""

    html = (
        f'<div class="metric-card {variant_class}">'
        f'<span class="metric-label">{label}</span>'
        f'<span class="metric-value">{value}</span>'
        f'<span class="metric-sublabel">{sublabel}</span>'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)
