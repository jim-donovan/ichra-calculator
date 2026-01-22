"""
Customize Panel Component

Collapsible panel for fine-tuning strategy parameters:
- Strategy type dropdown (filtered by mode)
- Base age dropdown (21-64)
- Base contribution input
- Preview showing contributions at key ages
- Modifier checkboxes (family multipliers, location adjustment)

Conditionally shows options based on census data:
- Family multipliers: hidden if all employees are EE (no dependents)
- Location adjustment: hidden if no high-cost states (CA, NY, MA, AK)
"""

import streamlit as st
from typing import Dict, List, Any, Optional, Callable

from contribution_eval import OperatingMode, CensusContext
from contribution_eval.utils.formatting import format_currency
from contribution_eval.utils.calculations import calculate_contribution_preview
from constants import ACA_AGE_CURVE


# High-cost states that support location adjustment
HIGH_COST_STATES = {'CA', 'NY', 'MA', 'AK'}


def render_customize_panel(
    mode: OperatingMode,
    current_config: Dict[str, Any],
    available_strategies: List[Dict[str, str]],
    on_recalculate: Callable[[Dict[str, Any]], None],
    census_context: Optional[CensusContext] = None,
) -> Optional[Dict[str, Any]]:
    """
    Render the Customize collapsible panel.

    Allows users to adjust strategy parameters and see a live preview
    of contributions at key ages.

    Args:
        mode: Current operating mode
        current_config: Current strategy configuration
        available_strategies: List of available strategy options
        on_recalculate: Callback when user clicks Recalculate
        census_context: Optional census context for conditional options

    Returns:
        Updated config if recalculate clicked, None otherwise
    """
    # Determine which options to show based on census
    show_family_multipliers = True
    show_location_adjustment = True

    if census_context:
        # Hide family multipliers if all employees are EE (no dependents)
        family_dist = census_context.family_status_distribution
        if family_dist:
            has_dependents = any(
                family_dist.get(status, 0) > 0
                for status in ['ES', 'EC', 'F']
            )
            show_family_multipliers = has_dependents

        # Hide location adjustment if no high-cost states
        if census_context.states:
            has_high_cost_state = any(
                state.upper() in HIGH_COST_STATES
                for state in census_context.states
            )
            show_location_adjustment = has_high_cost_state

    with st.expander("⚙️ Customize Strategy", expanded=False):
        # Strategy type
        st.markdown("#### Strategy Configuration")

        col1, col2, col3 = st.columns(3)

        with col1:
            strategy_options = {s['value']: s['label'] for s in available_strategies}
            current_type = current_config.get('strategy_type', 'base_age_curve')

            selected_type = st.selectbox(
                "Strategy Type",
                options=list(strategy_options.keys()),
                format_func=lambda x: strategy_options.get(x, x),
                index=list(strategy_options.keys()).index(current_type) if current_type in strategy_options else 0,
                key="customize_strategy_type",
            )

        with col2:
            # Base age (only show for age curve strategies)
            if selected_type in ['base_age_curve', 'fixed_age_tiers']:
                base_age = st.selectbox(
                    "Base Age",
                    options=list(range(21, 65)),
                    index=current_config.get('base_age', 21) - 21,
                    key="customize_base_age",
                )
            else:
                base_age = 21
                # Don't show Base Age field for non-age strategies

        with col3:
            # Base contribution - default to $200
            if selected_type != 'percentage_lcsp':
                base_contribution = st.number_input(
                    "Base Contribution ($)",
                    min_value=0,
                    max_value=5000,
                    value=int(current_config.get('base_contribution', 200)),
                    step=25,
                    key="customize_base_contribution",
                )
            else:
                # For %LCSP, show percentage
                lcsp_pct = st.number_input(
                    "% of LCSP",
                    min_value=50,
                    max_value=150,
                    value=int(current_config.get('lcsp_percentage', 100)),
                    step=5,
                    key="customize_lcsp_pct",
                )
                base_contribution = 0

        # Preview chart
        st.markdown("#### Contribution Preview")
        _render_contribution_preview(
            selected_type, base_age, base_contribution if selected_type != 'percentage_lcsp' else 0
        )

        # Modifiers - only show if relevant
        if show_family_multipliers or show_location_adjustment:
            st.markdown("#### Modifiers")
            col1, col2 = st.columns(2)

            with col1:
                if show_family_multipliers:
                    apply_family = st.checkbox(
                        "Apply family multipliers",
                        value=current_config.get('apply_family_multipliers', False),
                        help="Increase contributions for ES, EC, F based on multiplier ratios",
                        key="customize_family_mult",
                    )
                else:
                    apply_family = False

            with col2:
                if show_location_adjustment:
                    apply_location = st.checkbox(
                        "Apply location adjustment",
                        value=current_config.get('apply_location_adjustment', False),
                        help="Add flat amount for high-cost states (CA, NY, MA, AK)",
                        key="customize_location_adj",
                    )
                else:
                    apply_location = False

            # Location adjustment details
            adjustments = current_config.get('location_adjustments', {})
            if apply_location and show_location_adjustment:
                st.markdown("**Location Adjustments ($/month)**")

                # Only show states that are in the census
                states_to_show = []
                if census_context and census_context.states:
                    states_to_show = [
                        s.upper() for s in census_context.states
                        if s.upper() in HIGH_COST_STATES
                    ]
                else:
                    states_to_show = list(HIGH_COST_STATES)

                if states_to_show:
                    location_cols = st.columns(len(states_to_show))
                    for i, state in enumerate(states_to_show):
                        with location_cols[i]:
                            adjustments[state] = st.number_input(
                                state,
                                min_value=0,
                                max_value=500,
                                value=adjustments.get(state, 0),
                                step=25,
                                key=f"location_{state}",
                            )
        else:
            apply_family = False
            apply_location = False
            adjustments = {}

        # Recalculate button
        st.markdown("---")

        if st.button("🔄 Recalculate", type="primary", width="stretch"):
            new_config = {
                'strategy_type': selected_type,
                'base_age': base_age,
                'base_contribution': base_contribution,
                'lcsp_percentage': lcsp_pct if selected_type == 'percentage_lcsp' else 100,
                'apply_family_multipliers': apply_family,
                'apply_location_adjustment': apply_location,
                'location_adjustments': adjustments if apply_location else {},
            }
            on_recalculate(new_config)
            return new_config

    return None


def _render_contribution_preview(
    strategy_type: str,
    base_age: int,
    base_contribution: float,
) -> None:
    """
    Render live preview of contributions at key ages.

    Args:
        strategy_type: Selected strategy type
        base_age: Base age for calculation
        base_contribution: Base contribution amount
    """
    preview_ages = [21, 30, 40, 50, 64]
    preview_data = calculate_contribution_preview(
        strategy_type, base_age, base_contribution, preview_ages
    )

    if strategy_type == 'percentage_lcsp':
        st.info("Contributions vary by each employee's individual LCSP (Lowest Cost Silver Plan)")
        return

    if strategy_type == 'fpl_safe_harbor':
        st.info("Contributions vary based on LCSP minus FPL threshold for each employee")
        return

    # Render preview table - no indentation to avoid Streamlit markdown issues
    html = '<div class="preview-chart">'
    html += '<div class="preview-title">Monthly Contribution by Age</div>'

    for age, amount in preview_data:
        if amount is not None:
            # Highlight base age
            is_base = (age == base_age)
            style = "font-weight: 700; color: var(--brand-primary);" if is_base else ""
            marker = " (base)" if is_base else ""

            html += (
                f'<div class="preview-row">'
                f'<span class="preview-age">Age {age}{marker}</span>'
                f'<span class="preview-amount" style="{style}">{format_currency(amount)}</span>'
                f'</div>'
            )

    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)

    # Show 3:1 ratio note for age curve
    if strategy_type == 'base_age_curve':
        min_contrib = min(a for _, a in preview_data if a is not None)
        max_contrib = max(a for _, a in preview_data if a is not None)
        ratio = max_contrib / min_contrib if min_contrib > 0 else 0

        if ratio > 3.0:
            st.warning(f"⚠️ Current ratio is {ratio:.2f}:1, which exceeds the 3:1 limit")
        else:
            st.caption(f"✓ Ratio is {ratio:.2f}:1 (within 3:1 limit)")


def get_default_config(mode: OperatingMode) -> Dict[str, Any]:
    """
    Get default configuration for the given mode.

    Default base contribution is $200 for all modes.
    Family multipliers default to OFF.

    Args:
        mode: Operating mode

    Returns:
        Default config dict
    """
    if mode == OperatingMode.ALE:
        return {
            'strategy_type': 'fpl_safe_harbor',
            'base_age': 21,
            'base_contribution': 200,
            'apply_family_multipliers': False,
            'apply_location_adjustment': False,
        }
    elif mode == OperatingMode.NON_ALE_SUBSIDY:
        return {
            'strategy_type': 'subsidy_optimized',
            'base_age': 21,
            'base_contribution': 50,  # Placeholder - actual is calculated by strategy
            'apply_family_multipliers': False,
            'apply_location_adjustment': False,
        }
    else:
        return {
            'strategy_type': 'base_age_curve',
            'base_age': 21,
            'base_contribution': 200,
            'apply_family_multipliers': False,
            'apply_location_adjustment': False,
        }
