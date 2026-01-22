"""
Strategy Adjustment Panel Component

Unified panel for adjusting strategy with two modes:
- Compare: Pick from pre-computed strategy alternatives
- Customize: Fine-tune parameters manually

Only one mode active at a time to avoid confusion.
"""

import streamlit as st
from typing import Dict, List, Any, Optional, Callable

from contribution_eval import OperatingMode, SafeHarborType, CensusContext
from contribution_eval.utils.formatting import format_currency
from contribution_eval.utils.calculations import calculate_contribution_preview


# High-cost states that support location adjustment
HIGH_COST_STATES = {'CA', 'NY', 'MA', 'AK'}


def render_strategy_adjustment_panel(
    mode: OperatingMode,
    strategy_results: List[Dict[str, Any]],
    current_strategy: Optional[str],
    current_config: Dict[str, Any],
    available_strategies: List[Dict[str, str]],
    on_recalculate: Callable[[Dict[str, Any]], None],
    safe_harbor_comparison: Optional[Dict[str, Dict[str, Any]]] = None,
    census_context: Optional[CensusContext] = None,
) -> Optional[Dict[str, Any]]:
    """
    Render unified strategy adjustment panel with Compare/Customize tabs.

    Args:
        mode: Current operating mode
        strategy_results: Pre-computed strategy results for comparison
        current_strategy: Currently selected strategy type
        current_config: Current strategy configuration
        available_strategies: List of available strategy options
        on_recalculate: Callback when user customizes and recalculates
        safe_harbor_comparison: Safe harbor cost comparison (ALE only)
        census_context: Census context for conditional options

    Returns:
        Selected option dict if user makes a selection, None otherwise
    """
    with st.expander("🔧 Adjust Strategy", expanded=False):
        # ALE: Show Safe Harbor selection first (always visible, not in tabs)
        if mode == OperatingMode.ALE and safe_harbor_comparison:
            selected_harbor = _render_safe_harbor_radio(safe_harbor_comparison)
            if selected_harbor:
                return {'type': 'safe_harbor', 'value': selected_harbor}
            st.markdown("---")

        # Tabs for Compare vs Customize
        tab_compare, tab_customize = st.tabs(["📊 Compare Strategies", "⚙️ Customize"])

        with tab_compare:
            st.caption("Select a pre-calculated strategy option")
            selected_strategy = _render_strategy_comparison(
                strategy_results, mode, current_strategy
            )
            if selected_strategy:
                return {'type': 'strategy', 'value': selected_strategy}

        with tab_customize:
            st.caption("Fine-tune parameters for a custom strategy")
            result = _render_customize_content(
                mode, current_config, available_strategies,
                on_recalculate, census_context
            )
            if result:
                return result

    return None


def _render_safe_harbor_radio(
    comparison: Dict[str, Dict[str, Any]]
) -> Optional[SafeHarborType]:
    """Render Safe Harbor as simple radio buttons for ALE employers."""
    current_selection = st.session_state.get('selected_safe_harbor', SafeHarborType.FPL)

    # Check if Rate of Pay is available (requires income data)
    rop = comparison.get('rate_of_pay', {})
    has_income_data = rop.get('has_data', False)

    # Build options
    options = []
    option_labels = {}

    if has_income_data:
        options.append(SafeHarborType.RATE_OF_PAY)
        option_labels[SafeHarborType.RATE_OF_PAY] = "Rate of Pay (uses actual employee wages)"

    options.append(SafeHarborType.FPL)
    option_labels[SafeHarborType.FPL] = "FPL Safe Harbor (uses Federal Poverty Level)"

    # Ensure current selection is valid
    if current_selection not in options:
        current_selection = options[0] if options else SafeHarborType.FPL

    current_index = options.index(current_selection) if current_selection in options else 0

    st.markdown("#### Safe Harbor Method")
    st.caption("How employee income is measured for affordability calculations")

    new_selection = st.radio(
        "Safe Harbor",
        options=options,
        index=current_index,
        format_func=lambda x: option_labels.get(x, str(x)),
        key="safe_harbor_radio",
        label_visibility="collapsed",
    )

    if new_selection != current_selection:
        st.session_state.selected_safe_harbor = new_selection
        return new_selection

    return None


def _render_strategy_comparison(
    results: List[Dict[str, Any]],
    mode: OperatingMode,
    current_strategy: Optional[str] = None,
) -> Optional[str]:
    """Render strategy comparison as columns with selectable cards."""
    if not results:
        st.info("No strategies to compare. Adjust parameters above.")
        return None

    # Create columns for each strategy (up to 3)
    num_strategies = min(len(results), 3)
    cols = st.columns(num_strategies)

    selected = None

    for i, result in enumerate(results[:3]):
        strategy_type = result.get('strategy_type', 'unknown')
        strategy_name = result.get('strategy_name', strategy_type)
        total_monthly = result.get('total_monthly', 0)
        employee_count = result.get('employees_covered', 1)

        is_selected = (strategy_type == current_strategy)

        with cols[i]:
            # Build mode-specific subtitle
            if mode == OperatingMode.ALE:
                affordability = result.get('affordability', {})
                aff_count = affordability.get('affordable_count', 0)
                total = affordability.get('total_analyzed', employee_count)
                subtitle = f"{aff_count}/{total} affordable"
            elif mode == OperatingMode.NON_ALE_SUBSIDY:
                eligible = result.get('subsidy_eligible', 0)
                subtitle = f"{eligible} subsidy eligible"
            else:
                avg = total_monthly / employee_count if employee_count > 0 else 0
                subtitle = f"Avg {format_currency(avg)}/emp"

            card_class = "strategy-card strategy-card--selected" if is_selected else "strategy-card"

            st.markdown(f"""
            <div class="{card_class}">
                <div class="strategy-card-name">{strategy_name}</div>
                <div class="strategy-card-cost">{format_currency(total_monthly)}/mo</div>
                <div class="strategy-card-subtitle">{subtitle}</div>
            </div>
            """, unsafe_allow_html=True)

            button_label = "✓ Selected" if is_selected else "Select"
            button_type = "primary" if is_selected else "secondary"

            if st.button(
                button_label,
                key=f"strategy_btn_{strategy_type}",
                type=button_type,
                use_container_width=True,
            ):
                if not is_selected:
                    selected = strategy_type

    # Add CSS for strategy cards
    st.markdown("""
    <style>
    .strategy-card {
        background: #f8fafc;
        border: 2px solid #e2e8f0;
        border-radius: 8px;
        padding: 16px;
        text-align: center;
        margin-bottom: 8px;
        transition: all 0.2s ease;
    }
    .strategy-card--selected {
        background: #eff6ff;
        border-color: #3b82f6;
    }
    .strategy-card-name {
        font-size: 14px;
        font-weight: 600;
        color: #1e293b;
        margin-bottom: 8px;
    }
    .strategy-card-cost {
        font-size: 20px;
        font-weight: 700;
        color: #0f172a;
        margin-bottom: 4px;
    }
    .strategy-card-subtitle {
        font-size: 12px;
        color: #64748b;
    }
    </style>
    """, unsafe_allow_html=True)

    return selected


def _render_customize_content(
    mode: OperatingMode,
    current_config: Dict[str, Any],
    available_strategies: List[Dict[str, str]],
    on_recalculate: Callable[[Dict[str, Any]], None],
    census_context: Optional[CensusContext] = None,
) -> Optional[Dict[str, Any]]:
    """Render the customize form content."""
    # Determine which options to show based on census
    show_family_multipliers = True
    show_location_adjustment = True

    if census_context:
        family_dist = census_context.family_status_distribution
        if family_dist:
            has_dependents = any(
                family_dist.get(status, 0) > 0
                for status in ['ES', 'EC', 'F']
            )
            show_family_multipliers = has_dependents

        if census_context.states:
            has_high_cost_state = any(
                state.upper() in HIGH_COST_STATES
                for state in census_context.states
            )
            show_location_adjustment = has_high_cost_state

    col1, col2, col3 = st.columns(3)

    # Build strategy options
    strategy_options = {s['value']: s['label'] for s in available_strategies}
    strategy_keys = list(strategy_options.keys())
    current_type = current_config.get('strategy_type', 'base_age_curve')

    # Initialize session state for widgets if not already set
    # This ensures user selections persist across reruns WITHOUT using index/value params
    if 'customize_strategy_type' not in st.session_state:
        st.session_state.customize_strategy_type = current_type if current_type in strategy_keys else strategy_keys[0]

    if 'customize_base_age' not in st.session_state:
        st.session_state.customize_base_age = current_config.get('base_age', 21)

    if 'customize_base_contribution' not in st.session_state:
        st.session_state.customize_base_contribution = int(current_config.get('base_contribution', 200))

    if 'customize_lcsp_pct' not in st.session_state:
        st.session_state.customize_lcsp_pct = int(current_config.get('lcsp_percentage', 100))

    with col1:
        # Don't pass index - let Streamlit use session_state value
        selected_type = st.selectbox(
            "Strategy Type",
            options=strategy_keys,
            format_func=lambda x: strategy_options.get(x, x),
            key="customize_strategy_type",
        )

    with col2:
        if selected_type in ['base_age_curve', 'fixed_age_tiers']:
            base_age = st.selectbox(
                "Base Age",
                options=list(range(21, 65)),
                key="customize_base_age",
            )
        else:
            base_age = 21

    with col3:
        # Safe harbor strategies calculate contributions automatically - no base contribution input needed
        # subsidy_optimized also auto-calculates to maximize unaffordability (for subsidy eligibility)
        auto_calculated_strategies = ['percentage_lcsp', 'fpl_safe_harbor', 'rate_of_pay_safe_harbor', 'subsidy_optimized']

        if selected_type not in auto_calculated_strategies:
            base_contribution = st.number_input(
                "Base Contribution ($)",
                min_value=0,
                max_value=5000,
                step=25,
                key="customize_base_contribution",
            )
            lcsp_pct = st.session_state.get('customize_lcsp_pct', 100)
        elif selected_type == 'percentage_lcsp':
            lcsp_pct = st.number_input(
                "% of LCSP",
                min_value=50,
                max_value=150,
                step=5,
                key="customize_lcsp_pct",
            )
            base_contribution = st.session_state.get('customize_base_contribution', 0)
        else:
            # Safe harbor strategies - contributions auto-calculated
            st.info("💡 Contributions calculated automatically to meet affordability")
            base_contribution = st.session_state.get('customize_base_contribution', 0)
            lcsp_pct = st.session_state.get('customize_lcsp_pct', 100)

    # Preview
    _render_contribution_preview(
        selected_type, base_age, base_contribution if selected_type not in auto_calculated_strategies else 0
    )

    # Modifiers
    if show_family_multipliers or show_location_adjustment:
        st.markdown("**Modifiers**")
        mod_col1, mod_col2 = st.columns(2)

        with mod_col1:
            if show_family_multipliers:
                apply_family = st.checkbox(
                    "Apply family multipliers",
                    value=current_config.get('apply_family_multipliers', False),
                    help="Increase contributions for ES, EC, F based on multiplier ratios",
                    key="customize_family_mult",
                )
            else:
                apply_family = False

        with mod_col2:
            if show_location_adjustment:
                apply_location = st.checkbox(
                    "Apply location adjustment",
                    value=current_config.get('apply_location_adjustment', False),
                    help="Add flat amount for high-cost states (CA, NY, MA, AK)",
                    key="customize_location_adj",
                )
            else:
                apply_location = False

        adjustments = current_config.get('location_adjustments', {})
        if apply_location and show_location_adjustment:
            st.markdown("**Location Adjustments ($/month)**")
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
    if st.button("🔄 Recalculate", type="primary", use_container_width=True):
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
        return {'type': 'customize', 'config': new_config}

    return None


def _render_contribution_preview(
    strategy_type: str,
    base_age: int,
    base_contribution: float,
) -> None:
    """Render live preview of contributions at key ages."""
    preview_ages = [21, 30, 40, 50, 64]
    preview_data = calculate_contribution_preview(
        strategy_type, base_age, base_contribution, preview_ages
    )

    if strategy_type == 'percentage_lcsp':
        st.info("Contributions vary by each employee's individual LCSP")
        return

    if strategy_type == 'fpl_safe_harbor':
        st.info("Contributions = LCSP minus FPL affordability threshold (~$128/mo)")
        return

    if strategy_type == 'rate_of_pay_safe_harbor':
        st.info("Contributions = LCSP minus 9.96% of each employee's income")
        return

    if strategy_type == 'subsidy_optimized':
        st.info("Max contribution keeping ICHRA unaffordable (preserves subsidy eligibility)")
        return

    # Compact preview
    st.markdown("**Preview by Age**")
    preview_cols = st.columns(len(preview_ages))
    for i, (age, amount) in enumerate(preview_data):
        if amount is not None:
            with preview_cols[i]:
                is_base = (age == base_age)
                label = f"Age {age}" + (" ★" if is_base else "")
                st.metric(label, format_currency(amount))
