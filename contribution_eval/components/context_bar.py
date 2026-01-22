"""
Context Bar Component

Displays contextual information about the census data:
- Employee count
- ALE vs Non-ALE status
- Income data availability indicator
"""

import streamlit as st
from contribution_eval import CensusContext, OperatingMode


def render_context_bar(context: CensusContext) -> None:
    """
    Render the context bar showing census summary and ALE status.

    Displays at the top of the page to provide context for all
    subsequent strategy decisions.

    Args:
        context: CensusContext with computed demographics
    """
    # Determine ALE status
    is_ale = context.is_ale
    ale_status = "ALE" if is_ale else "Non-ALE"
    ale_class = "context-badge--ale" if is_ale else "context-badge--non-ale"

    # Income data indicator
    if context.has_income_data:
        income_status = "Income Data ✓"
        income_class = "context-badge--income"
    else:
        income_status = "No Income Data"
        income_class = "context-badge--no-income"

    # Build states display
    if context.is_multi_state:
        states_display = f"{len(context.states)} states"
    elif context.states:
        states_display = context.states[0]
    else:
        states_display = "—"

    # Render the context bar - no indentation to avoid Streamlit markdown issues
    html = (
        f'<div class="context-bar">'
        f'<div class="context-item">'
        f'<span class="context-item-label">Employees</span>'
        f'<span class="context-item-value">{context.employee_count}</span>'
        f'</div>'
        f'<div class="context-item">'
        f'<span class="context-badge {ale_class}">{ale_status}</span>'
        f'</div>'
        f'<div class="context-item">'
        f'<span class="context-item-label">Avg Age</span>'
        f'<span class="context-item-value">{context.avg_age:.0f}</span>'
        f'</div>'
        f'<div class="context-item">'
        f'<span class="context-item-label">Location</span>'
        f'<span class="context-item-value">{states_display}</span>'
        f'</div>'
        f'<div class="context-item">'
        f'<span class="context-badge {income_class}">{income_status}</span>'
        f'</div>'
        f'</div>'
    )

    st.markdown(html, unsafe_allow_html=True)

    # Show additional context for ALE
    if is_ale:
        st.info(
            "⚠️ **ALE Employer**: With 46+ employees, you must provide affordable coverage. "
            "The strategy must ensure all employees meet the IRS 9.96% affordability threshold.",
            icon=None
        )


def render_context_summary(context: CensusContext) -> dict:
    """
    Return context summary for use in other components.

    Args:
        context: CensusContext

    Returns:
        Dict with summary metrics for display
    """
    return {
        'employee_count': context.employee_count,
        'is_ale': context.is_ale,
        'has_income_data': context.has_income_data,
        'has_current_spend': context.has_current_er_spend,
        'avg_age': context.avg_age,
        'states': context.states,
        'family_distribution': context.family_status_distribution,
    }
