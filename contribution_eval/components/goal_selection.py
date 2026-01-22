"""
Goal Selection Component

Allows Non-ALE employers to choose between:
- Standard ICHRA: Minimize cost while providing competitive coverage
- Subsidy-optimized ICHRA: Help lower-income employees access ACA subsidies

Hidden for ALE employers (affordability is mandatory).
"""

import streamlit as st
from contribution_eval import CensusContext, GoalType, OperatingMode


def render_goal_selection(
    context: CensusContext,
    current_goal: GoalType = GoalType.STANDARD
) -> GoalType:
    """
    Render goal selection cards for Non-ALE employers.

    For ALE employers, returns None (goal selection not applicable).
    Changing the goal triggers a strategy recommendation refresh.

    Args:
        context: CensusContext for mode detection
        current_goal: Currently selected goal

    Returns:
        Selected GoalType, or None for ALE employers
    """
    # Hide for ALE employers
    if context.is_ale:
        return None

    st.markdown("### Choose Your Goal")

    col1, col2 = st.columns(2)

    with col1:
        standard_selected = current_goal == GoalType.STANDARD
        card_class = "goal-card goal-card--selected" if standard_selected else "goal-card"

        # Card with description
        st.markdown(f"""
        <div class="{card_class}">
            <div class="goal-card-icon">🎯</div>
            <div class="goal-card-title">Standard ICHRA</div>
            <div class="goal-card-desc">Minimize employer costs while ensuring employees have access to competitive marketplace coverage.</div>
        </div>
        """, unsafe_allow_html=True)

        # Button to select
        button_label = "✓ Selected" if standard_selected else "Select"
        if st.button(
            button_label,
            key="goal_standard",
            use_container_width=True,
            type="primary" if standard_selected else "secondary"
        ):
            if not standard_selected:
                st.session_state.contribution_goal = GoalType.STANDARD
                st.rerun()

    with col2:
        subsidy_selected = current_goal == GoalType.SUBSIDY_OPTIMIZED
        card_class = "goal-card goal-card--selected" if subsidy_selected else "goal-card"

        st.markdown(f"""
        <div class="{card_class}">
            <div class="goal-card-icon">💰</div>
            <div class="goal-card-title">Subsidy-Optimized ICHRA</div>
            <div class="goal-card-desc">Calculates the maximum flat contribution that keeps all high-ROI employees eligible for ACA subsidies.</div>
        </div>
        """, unsafe_allow_html=True)

        button_label = "✓ Selected" if subsidy_selected else "Select"
        if st.button(
            button_label,
            key="goal_subsidy",
            use_container_width=True,
            type="primary" if subsidy_selected else "secondary"
        ):
            if not subsidy_selected:
                st.session_state.contribution_goal = GoalType.SUBSIDY_OPTIMIZED
                st.rerun()

    # Add CSS for goal cards
    st.markdown("""
    <style>
    .goal-card {
        background: #f8fafc;
        border: 2px solid #e2e8f0;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        margin-bottom: 12px;
        transition: all 0.2s ease;
    }
    .goal-card--selected {
        background: #eff6ff;
        border-color: #3b82f6;
        box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
    }
    .goal-card-icon {
        font-size: 32px;
        margin-bottom: 8px;
    }
    .goal-card-title {
        font-size: 16px;
        font-weight: 600;
        color: #1e293b;
        margin-bottom: 8px;
    }
    .goal-card-desc {
        font-size: 13px;
        color: #64748b;
        line-height: 1.4;
    }
    </style>
    """, unsafe_allow_html=True)

    # Show income data note for subsidy mode
    if current_goal == GoalType.SUBSIDY_OPTIMIZED and not context.has_income_data:
        st.warning(
            "📊 **Income data recommended**: Add 'Monthly Income' to your census "
            "for accurate subsidy eligibility analysis.",
            icon=None
        )

    return current_goal


def get_goal_description(goal: GoalType) -> str:
    """
    Get human-readable description of the selected goal.

    Args:
        goal: Selected goal type

    Returns:
        Description string for display
    """
    descriptions = {
        GoalType.STANDARD: (
            "Standard ICHRA focuses on providing cost-effective coverage. "
            "The strategy minimizes employer costs while ensuring employees "
            "can access quality marketplace plans."
        ),
        GoalType.SUBSIDY_OPTIMIZED: (
            "Subsidy-optimized ICHRA uses a flat rate set to the maximum contribution that keeps "
            "all high-ROI employees (≥35% subsidy value) eligible for ACA subsidies. The flat rate "
            "approach ensures no employee accidentally becomes 'affordable' and loses subsidy access."
        ),
    }
    return descriptions.get(goal, "")


def should_show_goal_selection(context: CensusContext) -> bool:
    """
    Determine if goal selection should be shown.

    Args:
        context: CensusContext

    Returns:
        True if goal selection is applicable (Non-ALE only)
    """
    return not context.is_ale
