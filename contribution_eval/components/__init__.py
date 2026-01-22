"""
UI Components for Contribution Evaluation.

Each component is a Streamlit-based function that renders a portion
of the page. Components are designed to be composed together in the
main page orchestrator.
"""

from .context_bar import render_context_bar
from .goal_selection import render_goal_selection
from .ai_recommendation import (
    render_ai_recommendation,
    render_loading_recommendation,
    render_ai_status_indicator,
    render_recommendation_summary,
)
from .metrics_grid import render_metrics_grid
from .compare_options_panel import render_compare_options_panel
from .customize_panel import render_customize_panel, get_default_config
from .strategy_adjustment_panel import render_strategy_adjustment_panel
from .employee_breakdown import render_employee_breakdown
from .action_bar import render_action_bar
from .affordability_subsidy_comparison import render_affordability_subsidy_comparison

__all__ = [
    'render_context_bar',
    'render_goal_selection',
    'render_ai_recommendation',
    'render_loading_recommendation',
    'render_ai_status_indicator',
    'render_recommendation_summary',
    'render_metrics_grid',
    'render_compare_options_panel',
    'render_customize_panel',
    'render_strategy_adjustment_panel',
    'get_default_config',
    'render_employee_breakdown',
    'render_action_bar',
    'render_affordability_subsidy_comparison',
]
