"""
Contribution Evaluation Page - AI-Powered Strategy Recommendations

Refactored modular implementation based on PRD requirements.
Replaces AI chat interface with proactive recommendations.

Three Operating Modes:
- Non-ALE Standard: <46 employees, minimize cost
- Non-ALE Subsidy: <46 employees, optimize for ACA subsidies
- ALE: ≥46 employees, must achieve 100% affordability

AI Integration (Phase 2):
- Uses Claude API to select optimal strategy and generate explanations
- Automatic fallback to rule-based when API unavailable
- Per PRD NFR-1: AI recommendation within 5 seconds
- Per PRD NFR-2: Loading state during AI processing
"""

import streamlit as st
import logging

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from database import get_database_connection
from utils import render_feedback_sidebar

# Import contribution evaluation module
from contribution_eval import (
    OperatingMode,
    GoalType,
    CensusContext,
    StrategyRecommendation,
    SafeHarborType,
    get_available_strategies,
)
from contribution_eval.utils import (
    CONTRIBUTION_EVAL_CSS,
    build_census_context,
)
from contribution_eval.services import (
    StrategyService,
    RecommendationService,
    SubsidyService,
    is_ai_available,
)
from contribution_eval.components import (
    render_context_bar,
    render_goal_selection,
    render_ai_recommendation,
    render_loading_recommendation,
    render_ai_status_indicator,
    render_metrics_grid,
    render_strategy_adjustment_panel,
    render_employee_breakdown,
    render_action_bar,
    get_default_config,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Page config
st.set_page_config(
    page_title="Contribution Evaluation",
    page_icon="💰",
    layout="wide"
)

# Apply CSS
st.markdown(CONTRIBUTION_EVAL_CSS, unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.markdown("**📋 Client Name**")
    if 'client_name' not in st.session_state:
        st.session_state.client_name = ''
    st.text_input(
        "Client name",
        placeholder="Enter client name",
        key="client_name",
        help="Used in export filenames",
        label_visibility="collapsed"
    )
    render_feedback_sidebar()

    # AI status indicator in sidebar
    st.markdown("---")
    render_ai_status_indicator()


# =============================================================================
# SESSION STATE INITIALIZATION
# =============================================================================

def init_session_state():
    """Initialize session state for contribution evaluation."""
    if 'db' not in st.session_state:
        st.session_state.db = get_database_connection()

    if 'contribution_goal' not in st.session_state:
        st.session_state.contribution_goal = GoalType.STANDARD

    if 'current_strategy_config' not in st.session_state:
        st.session_state.current_strategy_config = None

    if 'current_strategy_result' not in st.session_state:
        st.session_state.current_strategy_result = None

    # Track previous goal to detect changes
    if 'previous_goal' not in st.session_state:
        st.session_state.previous_goal = None


init_session_state()


# =============================================================================
# MAIN PAGE LOGIC
# =============================================================================

def main():
    """Main page orchestrator."""
    # Page header
    st.markdown("""
    <div class="hero-section" style="background: linear-gradient(135deg, #ffffff 0%, #e8f1fd 100%); border-radius: 12px; padding: 32px; margin-bottom: 24px; border-left: 4px solid #0047AB;">
        <h1 style="font-size: 28px; font-weight: 700; color: #0a1628; margin-bottom: 8px;">Contribution Evaluation</h1>
        <p style="font-size: 16px; color: #475569; margin: 0;">AI-powered strategy recommendations for your ICHRA contribution design</p>
    </div>
    """, unsafe_allow_html=True)

    # Check for census data
    if 'census_df' not in st.session_state or st.session_state.census_df is None:
        st.warning("⚠️ No census data found. Please upload employee data on the Census Input page first.")
        if st.button("→ Go to Census Input"):
            st.switch_page("pages/1_Census_input.py")
        return

    census_df = st.session_state.census_df
    db = st.session_state.db

    # Build census context
    context = build_census_context(census_df)

    if context.employee_count == 0:
        st.error("Census data is empty. Please upload valid employee data.")
        return

    # Render context bar
    render_context_bar(context)

    # Get current goal
    current_goal = st.session_state.get('contribution_goal', GoalType.STANDARD)

    # Render goal selection (Non-ALE only)
    if not context.is_ale:
        new_goal = render_goal_selection(context, current_goal)
        if new_goal:
            # Detect goal change and invalidate cached recommendation
            if st.session_state.previous_goal != new_goal:
                if st.session_state.previous_goal is not None:
                    # Goal changed - clear cached results to trigger new AI recommendation
                    st.session_state.current_strategy_result = None
                    st.session_state.current_recommendation = None
                    logger.info(f"Goal changed from {st.session_state.previous_goal} to {new_goal} - regenerating recommendation")
                st.session_state.previous_goal = new_goal
                st.session_state.contribution_goal = new_goal

            current_goal = new_goal

    # Determine operating mode
    mode = context.get_operating_mode(current_goal or GoalType.STANDARD)

    # Get or create LCSP cache (avoids repeated database queries on each Streamlit rerun)
    lcsp_cache = st.session_state.get('lcsp_cache')
    if lcsp_cache is None:
        # First run - fetch LCSP data and cache it
        temp_service = StrategyService(db, census_df)
        lcsp_cache = temp_service.get_lcsp_cache()
        st.session_state.lcsp_cache = lcsp_cache
        logger.info(f"LCSP cache created with {len(lcsp_cache)} employees")

    # Initialize services with cached LCSP data
    strategy_service = StrategyService(db, census_df, lcsp_cache)
    recommendation_service = RecommendationService(db, census_df, context, lcsp_cache)
    subsidy_service = SubsidyService(db, census_df) if mode == OperatingMode.NON_ALE_SUBSIDY else None

    # Generate or use cached recommendation
    if st.session_state.current_strategy_result is None:
        # Show loading state
        st.markdown("### Recommended Strategy")
        loading_placeholder = st.empty()

        with loading_placeholder.container():
            render_loading_recommendation()

        # Generate recommendation (includes AI call if available)
        recommendation = recommendation_service.generate_recommendation(mode, current_goal or GoalType.STANDARD)

        # Calculate full strategy result
        if recommendation.strategy_type == 'percentage_lcsp':
            strategy_result = strategy_service.calculate_strategy(
                strategy_type=recommendation.strategy_type,
                lcsp_percentage=100,
            )
        elif recommendation.strategy_type == 'fpl_safe_harbor':
            strategy_result = strategy_service.calculate_strategy(
                strategy_type=recommendation.strategy_type,
                apply_family_multipliers=True,
            )
        else:
            strategy_result = strategy_service.calculate_strategy(
                strategy_type=recommendation.strategy_type,
                base_age=recommendation.base_age,
                base_contribution=recommendation.base_contribution,
            )

        # Add strategy_type to result for tracking
        strategy_result['strategy_type'] = recommendation.strategy_type

        # Add affordability for ALE mode
        if mode == OperatingMode.ALE:
            strategy_result = strategy_service.calculate_with_affordability(
                strategy_result,
                recommendation.safe_harbor or st.session_state.get('selected_safe_harbor'),
            )

        # Store in session state
        st.session_state.current_strategy_result = strategy_result
        st.session_state.current_recommendation = recommendation
        st.session_state.current_strategy_config = {
            'strategy_type': recommendation.strategy_type,
            'base_age': recommendation.base_age,
            'base_contribution': recommendation.base_contribution,
            'apply_family_multipliers': False,
            'apply_location_adjustment': False,
        }
        # Set safe harbor from AI recommendation (for ALE mode)
        if recommendation.safe_harbor:
            st.session_state.selected_safe_harbor = recommendation.safe_harbor

        # Clear loading and rerun to show final result
        loading_placeholder.empty()
        st.rerun()
    else:
        strategy_result = st.session_state.current_strategy_result
        recommendation = st.session_state.get('current_recommendation')

    # Render AI recommendation
    if recommendation:
        render_ai_recommendation(recommendation, mode)

    # Get affordability and subsidy data
    affordability_data = strategy_result.get('affordability') if mode == OperatingMode.ALE else None

    subsidy_data = None
    if mode == OperatingMode.NON_ALE_SUBSIDY and subsidy_service:
        # Get LCSP data from strategy result
        lcsp_data = {
            emp_id: data.get('lcsp_ee_rate', 0)
            for emp_id, data in strategy_result.get('employee_contributions', {}).items()
        }
        slcsp_data = lcsp_data  # Use LCSP as proxy for now

        subsidy_data = subsidy_service.analyze_workforce_subsidy_potential(
            strategy_result, lcsp_data, slcsp_data
        )

    # Render metrics grid
    render_metrics_grid(
        mode=mode,
        strategy_result=strategy_result,
        current_er_spend=context.total_current_er_monthly,
        affordability_data=affordability_data,
        subsidy_data=subsidy_data,
    )

    # ==========================================================================
    # STRATEGY ADJUSTMENT PANEL (Unified Compare + Customize)
    # ==========================================================================

    available_strategies = strategy_service.get_available_strategies(mode)

    # Get current safe harbor for ALE mode (default to FPL if not set)
    current_safe_harbor = st.session_state.get('selected_safe_harbor', SafeHarborType.FPL)

    # Get current config - use customized values if available, otherwise AI recommendation
    current_config = st.session_state.get('current_strategy_config', get_default_config(mode))

    # Use customized parameters for comparison (so Compare tab reflects Customize changes)
    comparison_base = current_config.get('base_contribution') or (recommendation.base_contribution if recommendation else 400)
    comparison_lcsp_pct = current_config.get('lcsp_percentage', 100)

    # Calculate comparison strategies using current customization parameters
    # For all modes (including ALE), use the customized params so users can see affordability gaps
    comparison_results = strategy_service.calculate_multiple_strategies(
        mode,
        base_contribution=comparison_base,
        lcsp_percentage=comparison_lcsp_pct,
        safe_harbor=current_safe_harbor,
        use_optimized_ale=False,  # Don't optimize - show results with user's params
    )

    # For Non-ALE Subsidy mode, add subsidy eligibility to comparison results
    if mode == OperatingMode.NON_ALE_SUBSIDY and subsidy_service:
        for result in comparison_results:
            lcsp_data = {
                emp_id: data.get('lcsp_ee_rate', 0)
                for emp_id, data in result.get('employee_contributions', {}).items()
            }
            strategy_subsidy = subsidy_service.analyze_workforce_subsidy_potential(
                result, lcsp_data, lcsp_data
            )
            result['subsidy_eligible'] = strategy_subsidy.get('eligible_count', 0)

    # Get safe harbor comparison for ALE
    safe_harbor_comparison = None
    if mode == OperatingMode.ALE:
        safe_harbor_comparison = strategy_service.calculate_safe_harbor_comparison()

    def on_recalculate(new_config):
        """Handle recalculate from customize tab."""
        new_result = strategy_service.calculate_strategy(
            strategy_type=new_config['strategy_type'],
            base_age=new_config.get('base_age', 21),
            base_contribution=new_config.get('base_contribution', comparison_base),
            lcsp_percentage=new_config.get('lcsp_percentage', 100),
            apply_family_multipliers=new_config.get('apply_family_multipliers', True),
            apply_location_adjustment=new_config.get('apply_location_adjustment', False),
            location_adjustments=new_config.get('location_adjustments', {}),
        )
        new_result['strategy_type'] = new_config['strategy_type']

        if mode == OperatingMode.ALE:
            new_result = strategy_service.calculate_with_affordability(
                new_result, current_safe_harbor
            )

        st.session_state.current_strategy_result = new_result
        st.session_state.current_strategy_config = new_config

    # Render unified adjustment panel with Compare and Customize tabs
    selected_option = render_strategy_adjustment_panel(
        mode=mode,
        strategy_results=comparison_results,
        current_strategy=strategy_result.get('strategy_type'),
        current_config=current_config,
        available_strategies=available_strategies,
        on_recalculate=on_recalculate,
        safe_harbor_comparison=safe_harbor_comparison,
        census_context=context,
    )

    # Handle selection from any tab
    if selected_option:
        if selected_option['type'] == 'safe_harbor':
            # Safe harbor changed - recalculate OPTIMIZED strategies for new safe harbor
            new_safe_harbor = selected_option['value']

            # Calculate optimal strategies for this safe harbor (100% affordability)
            optimized_results = strategy_service.calculate_multiple_strategies(
                mode,
                safe_harbor=new_safe_harbor,
                use_optimized_ale=True,  # Optimize for 100% affordability
            )

            # Pick the lowest cost strategy that achieves 100% affordability
            best_result = None
            for result in optimized_results:
                affordability = result.get('affordability', {})
                if affordability.get('all_affordable', False):
                    if best_result is None or result.get('total_monthly', 0) < best_result.get('total_monthly', float('inf')):
                        best_result = result

            # If none are 100% affordable, pick the one with highest affordability %
            if best_result is None and optimized_results:
                best_result = max(optimized_results, key=lambda r: r.get('affordability', {}).get('affordable_pct', 0))

            if best_result:
                st.session_state.current_strategy_result = best_result
                st.session_state.current_strategy_config = {
                    'strategy_type': best_result.get('strategy_type'),
                    'base_age': best_result.get('config', {}).get('base_age', 21),
                    'base_contribution': best_result.get('config', {}).get('base_contribution', 400),
                    'lcsp_percentage': best_result.get('config', {}).get('lcsp_percentage', 100),
                    'apply_family_multipliers': False,
                    'apply_location_adjustment': False,
                }

            st.rerun()

        elif selected_option['type'] == 'strategy':
            # Strategy selected from Compare tab
            new_type = selected_option['value']
            matching_result = next(
                (r for r in comparison_results if r.get('strategy_type') == new_type),
                None
            )

            if matching_result:
                st.session_state.current_strategy_result = matching_result
                st.session_state.current_strategy_config = {
                    'strategy_type': new_type,
                    'base_age': matching_result.get('config', {}).get('base_age', 21),
                    'base_contribution': matching_result.get('config', {}).get('base_contribution', comparison_base),
                    'lcsp_percentage': matching_result.get('config', {}).get('lcsp_percentage', comparison_lcsp_pct),
                    'apply_family_multipliers': False,
                    'apply_location_adjustment': False,
                }
                st.rerun()

        elif selected_option['type'] == 'customize':
            # Custom config from Customize tab - already handled by on_recalculate
            st.rerun()

    # Render Employee Breakdown
    render_employee_breakdown(
        mode=mode,
        strategy_result=strategy_result,
        affordability_data=affordability_data,
        subsidy_data=subsidy_data,
    )

    # Render Action Bar
    def on_use_strategy(result):
        """Handle Use This Strategy button."""
        # Save to session state
        st.session_state.contribution_settings = {
            'strategy_type': result.get('strategy_type', 'base_age_curve'),
            'strategy_name': result.get('strategy_name', ''),
            'contribution_type': 'class_based',
            'config': result.get('config', {}),
            'employee_assignments': {
                emp_id: {
                    'monthly_contribution': data.get('monthly_contribution', 0),
                    'annual_contribution': data.get('annual_contribution', 0),
                }
                for emp_id, data in result.get('employee_contributions', {}).items()
            },
        }
        st.session_state.strategy_results = {
            'total_monthly': result.get('total_monthly', 0),
            'total_annual': result.get('total_annual', 0),
            'employees_covered': result.get('employees_covered', 0),
        }
        st.session_state.contribution_evaluation_complete = True

        if 'affordability' in result:
            st.session_state.affordability_results = result['affordability']

        st.success("✅ Strategy saved! Proceed to Employer Summary.")

    def on_start_over():
        """Handle Start Over button."""
        keys_to_clear = [
            'current_strategy_result',
            'current_strategy_config',
            'current_recommendation',
            'contribution_goal',
            'previous_goal',
            # Clear customize tab widget states
            'customize_strategy_type',
            'customize_base_age',
            'customize_base_contribution',
            'customize_lcsp_pct',
            'customize_family_mult',
            'customize_location_adj',
        ]
        for key in keys_to_clear:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()

    render_action_bar(
        mode=mode,
        strategy_result=strategy_result,
        affordability_data=affordability_data,
        on_use_strategy=on_use_strategy,
        on_start_over=on_start_over,
    )


# Run main
if __name__ == "__main__":
    main()
else:
    main()
