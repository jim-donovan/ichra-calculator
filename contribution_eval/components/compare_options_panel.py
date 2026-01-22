"""
Compare Options Panel Component

Collapsible panel for comparing strategy alternatives:
- ALE: Safe Harbor radio selection + strategy comparison table
- All modes: Strategy comparison table

Collapsed by default. Selecting an option updates the recommendation.
"""

import streamlit as st
from typing import Dict, List, Any, Optional

from contribution_eval import OperatingMode, SafeHarborType
from contribution_eval.utils.formatting import format_currency


def render_compare_options_panel(
    mode: OperatingMode,
    strategy_results: List[Dict[str, Any]],
    safe_harbor_comparison: Optional[Dict[str, Dict[str, Any]]] = None,
    current_strategy: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Render the Compare Options collapsible panel.

    For ALE mode, shows Safe Harbor radio buttons then strategy comparison.
    For Non-ALE modes, shows only strategy comparison.

    Args:
        mode: Current operating mode
        strategy_results: List of strategy calculation results for comparison
        safe_harbor_comparison: Safe harbor cost comparison (ALE only)
        current_strategy: Currently selected strategy type

    Returns:
        Selected option dict if user clicks a selection button, None otherwise
    """
    with st.expander("📊 Compare Options", expanded=False):
        selected = None

        # ALE: Show Safe Harbor radio buttons
        if mode == OperatingMode.ALE and safe_harbor_comparison:
            selected_harbor = _render_safe_harbor_radio(safe_harbor_comparison)
            if selected_harbor:
                return {'type': 'safe_harbor', 'value': selected_harbor}

            st.markdown("---")

        # Strategy comparison table (all modes)
        st.markdown("#### Strategy Comparison")
        selected_strategy = _render_strategy_comparison(
            strategy_results, mode, current_strategy
        )
        if selected_strategy:
            return {'type': 'strategy', 'value': selected_strategy}

        return None


def _render_safe_harbor_radio(
    comparison: Dict[str, Dict[str, Any]]
) -> Optional[SafeHarborType]:
    """
    Render Safe Harbor as simple radio buttons for ALE employers.

    Args:
        comparison: Dict with 'rate_of_pay', 'fpl' data

    Returns:
        Selected SafeHarborType if changed, None otherwise
    """
    # Get current selection from session state
    # Default matches what AI recommends (stored in session state by recommendation service)
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

    # Find current index
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

    # Check if selection changed
    if new_selection != current_selection:
        st.session_state.selected_safe_harbor = new_selection
        return new_selection

    return None


def _render_strategy_comparison(
    results: List[Dict[str, Any]],
    mode: OperatingMode,
    current_strategy: Optional[str] = None,
) -> Optional[str]:
    """
    Render strategy comparison as columns with selectable cards.

    Args:
        results: List of strategy results
        mode: Operating mode (determines display)
        current_strategy: Currently selected strategy

    Returns:
        Selected strategy type if changed, None otherwise
    """
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

        # Determine if this is the selected strategy
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

            # Render card with button
            card_class = "strategy-card strategy-card--selected" if is_selected else "strategy-card"

            st.markdown(f"""
            <div class="{card_class}">
                <div class="strategy-card-name">{strategy_name}</div>
                <div class="strategy-card-cost">{format_currency(total_monthly)}/mo</div>
                <div class="strategy-card-subtitle">{subtitle}</div>
            </div>
            """, unsafe_allow_html=True)

            # Button to select
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
