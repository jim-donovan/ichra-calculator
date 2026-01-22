"""
AI Recommendation Component

Displays the proactive AI-generated strategy recommendation.
Includes strategy details and "Why this works" explanation.

Per PRD FR-3:
- Auto-generate optimal strategy on page load
- Include strategy type, base age, base contribution, safe harbor (ALE)
- Include "Why this works" explanation (2-3 sentences with specific data points)
"""

import streamlit as st
from contribution_eval import (
    StrategyRecommendation,
    OperatingMode,
    SafeHarborType,
)
from contribution_eval.utils.formatting import format_currency
from contribution_eval.services.ai_client import is_ai_available


def render_ai_recommendation(
    recommendation: StrategyRecommendation,
    mode: OperatingMode,
) -> None:
    """
    Render the AI recommendation card.

    Shows:
    - Recommended strategy type
    - Key parameters (base age, contribution, safe harbor)
    - "Why this works" explanation
    - Monthly/annual cost summary

    Args:
        recommendation: StrategyRecommendation from RecommendationService
        mode: Current operating mode for context
    """
    st.markdown("### Recommended Strategy")

    # Build strategy details string
    if recommendation.strategy_type == 'flat_amount':
        strategy_details = f"${recommendation.base_contribution:,.0f}/month for all employees"
    elif recommendation.strategy_type == 'base_age_curve':
        strategy_details = f"${recommendation.base_contribution:,.0f}/month at age {recommendation.base_age}, scaled by ACA 3:1 curve"
    elif recommendation.strategy_type == 'percentage_lcsp':
        strategy_details = "100% of each employee's individual LCSP"
    elif recommendation.strategy_type == 'fpl_safe_harbor':
        strategy_details = "Minimum contribution for FPL-based affordability"
    elif recommendation.strategy_type == 'rate_of_pay_safe_harbor':
        strategy_details = "Minimum contribution based on actual employee income"
    elif recommendation.strategy_type == 'subsidy_optimized':
        strategy_details = f"${recommendation.base_contribution:,.0f}/month flat rate, maximizing subsidy eligibility"
    else:
        strategy_details = recommendation.strategy_type

    # Build contribution basis note (explains how base contribution was calculated)
    basis_note = ""
    if recommendation.contribution_basis and recommendation.strategy_type in ['flat_amount', 'base_age_curve']:
        basis_note = f'<div class="contribution-basis">📊 {recommendation.contribution_basis}</div>'

    # Safe harbor badge for ALE
    safe_harbor_html = ""
    if recommendation.safe_harbor and mode == OperatingMode.ALE:
        # Handle both enum and string values
        harbor_names = {
            SafeHarborType.RATE_OF_PAY: "Rate of Pay",
            SafeHarborType.FPL: "FPL Safe Harbor",
            SafeHarborType.W2_WAGES: "W-2 Wages",
            'rate_of_pay': "Rate of Pay",
            'fpl': "FPL Safe Harbor",
            'w2_wages': "W-2 Wages",
        }
        safe_harbor = recommendation.safe_harbor
        # If it's an enum, also try its value
        harbor_name = harbor_names.get(safe_harbor)
        if harbor_name is None and hasattr(safe_harbor, 'value'):
            harbor_name = harbor_names.get(safe_harbor.value)
        if harbor_name is None:
            # Last resort - clean up the string representation
            harbor_name = str(safe_harbor).replace('SafeHarborType.', '').replace('_', ' ').title()
        safe_harbor_html = f'<span class="status-badge status-badge--info" style="margin-left: 8px;">{harbor_name}</span>'

    # AI indicator badge
    ai_badge = ""
    if is_ai_available():
        ai_badge = '<span class="ai-powered-badge">AI-Powered</span>'
    else:
        ai_badge = '<span class="ai-fallback-badge">Rule-Based</span>'

    # Build the recommendation card HTML - no indentation to avoid Streamlit markdown issues
    html = (
        f'<div class="recommendation-card">'
        f'<div class="recommendation-header">'
        f'<div class="recommendation-title">'
        f'<span class="recommendation-title-icon">✨</span> AI Recommendation {ai_badge}'
        f'</div></div>'
        f'<div class="recommendation-strategy">'
        f'<span class="strategy-badge">{recommendation.strategy_display_name}</span>'
        f'<span class="strategy-details">{strategy_details}</span>'
        f'{safe_harbor_html}'
        f'</div>'
        f'{basis_note}'
        f'<div class="recommendation-explanation">'
        f'<strong>Why this works:</strong> {recommendation.explanation}'
        f'</div>'
        f'</div>'
    )

    st.markdown(html, unsafe_allow_html=True)

    # Inject additional CSS for badges and contribution basis
    st.markdown("""
    <style>
    .ai-powered-badge {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        font-size: 10px;
        font-weight: 600;
        padding: 2px 8px;
        border-radius: 12px;
        margin-left: 8px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .ai-fallback-badge {
        background: #94a3b8;
        color: white;
        font-size: 10px;
        font-weight: 600;
        padding: 2px 8px;
        border-radius: 12px;
        margin-left: 8px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .contribution-basis {
        font-size: 13px;
        color: #64748b;
        margin: 8px 0 12px 0;
        padding: 8px 12px;
        background: #f8fafc;
        border-radius: 6px;
        border-left: 3px solid #3b82f6;
    }
    </style>
    """, unsafe_allow_html=True)


def render_recommendation_summary(
    recommendation: StrategyRecommendation,
    mode: OperatingMode,
) -> None:
    """
    Render a compact summary of the recommendation for use elsewhere.

    Args:
        recommendation: StrategyRecommendation
        mode: Current operating mode
    """
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            label="Strategy",
            value=recommendation.strategy_display_name,
        )

    with col2:
        st.metric(
            label="Monthly Cost",
            value=format_currency(recommendation.total_monthly),
        )

    with col3:
        if mode == OperatingMode.ALE and recommendation.affordable_pct is not None:
            pct = recommendation.affordable_pct
            st.metric(
                label="Affordable",
                value=f"{pct:.0f}%",
                delta="✓" if pct >= 100 else "Needs adjustment",
                delta_color="normal" if pct >= 100 else "inverse",
            )
        elif recommendation.vs_current_delta is not None:
            st.metric(
                label="vs Current",
                value=format_currency(abs(recommendation.vs_current_delta)),
                delta="savings" if recommendation.vs_current_delta < 0 else "increase",
                delta_color="normal" if recommendation.vs_current_delta < 0 else "inverse",
            )
        else:
            st.metric(
                label="Annual Cost",
                value=format_currency(recommendation.total_annual),
            )


def render_loading_recommendation() -> None:
    """
    Render a loading state for the recommendation.

    Shown while the AI generates the recommendation.
    Per PRD NFR-2: Loading state during AI processing
    """
    # Animated loading card
    html = '''
    <div class="recommendation-card recommendation-card--loading">
        <div class="recommendation-header">
            <div class="recommendation-title">
                <span class="recommendation-title-icon loading-pulse">✨</span>
                Generating AI Recommendation...
            </div>
        </div>
        <div class="loading-content">
            <div class="loading-bar">
                <div class="loading-bar-fill"></div>
            </div>
            <p class="loading-text">Analyzing your census data and calculating optimal strategy</p>
        </div>
    </div>

    <style>
    .recommendation-card--loading {
        background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 24px;
    }

    .loading-pulse {
        animation: pulse 1.5s ease-in-out infinite;
    }

    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.4; }
    }

    .loading-content {
        padding: 16px 0;
        text-align: center;
    }

    .loading-bar {
        width: 100%;
        height: 4px;
        background: #e2e8f0;
        border-radius: 2px;
        overflow: hidden;
        margin-bottom: 16px;
    }

    .loading-bar-fill {
        width: 30%;
        height: 100%;
        background: linear-gradient(90deg, #667eea, #764ba2);
        border-radius: 2px;
        animation: loading-progress 2s ease-in-out infinite;
    }

    @keyframes loading-progress {
        0% { transform: translateX(-100%); }
        50% { transform: translateX(200%); }
        100% { transform: translateX(-100%); }
    }

    .loading-text {
        color: #64748b;
        font-size: 14px;
        margin: 0;
    }
    </style>
    '''
    st.markdown(html, unsafe_allow_html=True)


def render_ai_status_indicator() -> None:
    """
    Render a small indicator showing AI availability status.

    Useful for debugging or informing users about the recommendation source.
    """
    if is_ai_available():
        st.markdown(
            '<div style="font-size: 12px; color: #16a34a;">✓ AI-powered recommendations enabled</div>',
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            '<div style="font-size: 12px; color: #9ca3af;">ℹ Using rule-based recommendations (set ANTHROPIC_API_KEY for AI)</div>',
            unsafe_allow_html=True
        )
