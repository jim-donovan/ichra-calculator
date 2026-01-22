"""
Formatting utilities and CSS for Contribution Evaluation components.
"""

from typing import Optional


def format_currency(value: float, include_sign: bool = False) -> str:
    """
    Format a number as currency.

    Args:
        value: The numeric value to format
        include_sign: If True, prefix with +/- for positive/negative values

    Returns:
        Formatted string like "$1,234.56" or "+$1,234.56"
    """
    if value is None:
        return "—"

    if include_sign:
        return f"${value:+,.0f}" if value >= 0 else f"-${abs(value):,.0f}"
    return f"${value:,.0f}"


def format_percentage(value: float, decimals: int = 0) -> str:
    """Format a number as a percentage."""
    if value is None:
        return "—"
    return f"{value:.{decimals}f}%"


def format_delta(value: float, invert: bool = False) -> str:
    """
    Format a delta value with color-coded sign.

    Args:
        value: The delta value
        invert: If True, negative is good (e.g., cost savings)

    Returns:
        HTML string with colored arrow and value
    """
    if value is None:
        return "—"

    is_positive = value > 0
    is_good = (not is_positive) if invert else is_positive

    color = "var(--green-600)" if is_good else "var(--red-600)"
    arrow = "↑" if is_positive else "↓"

    return f'<span style="color: {color}">{arrow} ${abs(value):,.0f}</span>'


def render_metric_card(
    label: str,
    value: str,
    sublabel: Optional[str] = None,
    variant: str = "default"
) -> str:
    """
    Render a metric card as HTML.

    Args:
        label: The metric label (e.g., "Monthly Cost")
        value: The formatted value (e.g., "$5,000")
        sublabel: Optional secondary text (e.g., "per month")
        variant: Card style variant (default, success, warning, primary)

    Returns:
        HTML string for the metric card
    """
    variant_classes = {
        "default": "",
        "success": "metric-card--success",
        "warning": "metric-card--warning",
        "primary": "metric-card--primary",
    }
    variant_class = variant_classes.get(variant, "")

    sublabel_html = f'<span class="metric-sublabel">{sublabel}</span>' if sublabel else ""

    return f'''
    <div class="metric-card {variant_class}">
        <span class="metric-label">{label}</span>
        <span class="metric-value">{value}</span>
        {sublabel_html}
    </div>
    '''


def render_status_badge(
    text: str,
    status: str = "info"
) -> str:
    """
    Render a status badge as HTML.

    Args:
        text: Badge text
        status: Badge status (success, warning, error, info)

    Returns:
        HTML string for the badge
    """
    return f'<span class="status-badge status-badge--{status}">{text}</span>'


# =============================================================================
# CSS STYLES
# =============================================================================

CONTRIBUTION_EVAL_CSS = """
<style>
/* ============================================
   CSS VARIABLES
   ============================================ */
:root {
    --gray-50: #f9fafb;
    --gray-100: #f3f4f6;
    --gray-200: #e5e7eb;
    --gray-300: #d1d5db;
    --gray-400: #9ca3af;
    --gray-500: #6b7280;
    --gray-600: #4b5563;
    --gray-700: #374151;
    --gray-800: #1f2937;
    --gray-900: #111827;

    --blue-50: #eff6ff;
    --blue-100: #dbeafe;
    --blue-500: #3b82f6;
    --blue-600: #2563eb;
    --blue-700: #1d4ed8;

    --green-50: #f0fdf4;
    --green-100: #dcfce7;
    --green-500: #22c55e;
    --green-600: #16a34a;
    --green-700: #15803d;

    --amber-50: #fffbeb;
    --amber-100: #fef3c7;
    --amber-500: #f59e0b;
    --amber-600: #d97706;

    --red-50: #fef2f2;
    --red-100: #fee2e2;
    --red-500: #ef4444;
    --red-600: #dc2626;

    /* Brand colors */
    --brand-primary: #0047AB;
    --brand-light: #E8F1FD;
    --brand-accent: #37BEAE;
}

/* ============================================
   SIDEBAR STYLING
   ============================================ */
[data-testid="stSidebar"] {
    background-color: #F0F4FA;
}
[data-testid="stSidebarNav"] a {
    background-color: transparent !important;
}
[data-testid="stSidebarNav"] a[aria-selected="true"] {
    background-color: var(--brand-light) !important;
    border-left: 3px solid var(--brand-primary) !important;
}
[data-testid="stSidebarNav"] a:hover {
    background-color: var(--brand-light) !important;
}

/* ============================================
   CONTEXT BAR
   ============================================ */
.context-bar {
    display: flex;
    align-items: center;
    gap: 1.5rem;
    padding: 0.75rem 1rem;
    background: var(--gray-50);
    border: 1px solid var(--gray-200);
    border-radius: 8px;
    margin-bottom: 1.5rem;
}

.context-item {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.875rem;
    color: var(--gray-600);
}

.context-item-value {
    font-weight: 600;
    color: var(--gray-800);
}

.context-badge {
    display: inline-flex;
    align-items: center;
    padding: 0.25rem 0.5rem;
    font-size: 0.75rem;
    font-weight: 600;
    border-radius: 4px;
}

.context-badge--ale {
    background: var(--amber-100);
    color: var(--amber-600);
}

.context-badge--non-ale {
    background: var(--green-100);
    color: var(--green-600);
}

.context-badge--income {
    background: var(--blue-100);
    color: var(--blue-700);
}

.context-badge--no-income {
    background: var(--gray-100);
    color: var(--gray-500);
}

/* ============================================
   GOAL SELECTION
   ============================================ */
.goal-selection {
    display: flex;
    gap: 1rem;
    margin-bottom: 1.5rem;
}

.goal-card {
    flex: 1;
    padding: 1rem;
    background: white;
    border: 2px solid var(--gray-200);
    border-radius: 8px;
}

.goal-card--selected {
    border-color: var(--brand-primary);
    background: var(--brand-light);
}

.goal-card-title {
    font-size: 1rem;
    font-weight: 600;
    color: var(--gray-800);
    margin-bottom: 0.25rem;
}

.goal-card-description {
    font-size: 0.8125rem;
    color: var(--gray-500);
}

/* ============================================
   AI RECOMMENDATION CARD
   ============================================ */
.recommendation-card {
    background: white;
    border: 1px solid var(--gray-200);
    border-left: 4px solid var(--brand-primary);
    border-radius: 8px;
    padding: 1.5rem;
    margin-bottom: 1.5rem;
}

.recommendation-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 1rem;
}

.recommendation-title {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 1rem;
    font-weight: 600;
    color: var(--gray-800);
}

.recommendation-title-icon {
    color: var(--brand-primary);
}

.recommendation-strategy {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.75rem 1rem;
    background: var(--gray-50);
    border-radius: 6px;
    margin-bottom: 1rem;
}

.strategy-badge {
    padding: 0.25rem 0.5rem;
    font-size: 0.75rem;
    font-weight: 600;
    background: var(--brand-primary);
    color: white;
    border-radius: 4px;
}

.strategy-details {
    font-size: 0.875rem;
    color: var(--gray-700);
}

.recommendation-explanation {
    font-size: 0.875rem;
    color: var(--gray-600);
    line-height: 1.5;
    padding: 0.75rem;
    background: var(--blue-50);
    border-radius: 6px;
    border-left: 3px solid var(--blue-500);
}

/* ============================================
   METRICS GRID
   ============================================ */
.metrics-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 1rem;
    margin-bottom: 1.5rem;
}

.metric-card {
    display: flex;
    flex-direction: column;
    padding: 1rem;
    background: white;
    border: 1px solid var(--gray-200);
    border-radius: 8px;
}

.metric-card--primary {
    background: var(--brand-light);
    border-color: var(--brand-primary);
}

.metric-card--success {
    background: var(--green-50);
    border-color: var(--green-200);
}

.metric-card--warning {
    background: var(--amber-50);
    border-color: var(--amber-200);
}

.metric-card--danger {
    background: var(--red-50);
    border-color: var(--red-100);
}

.metric-label {
    font-size: 0.75rem;
    font-weight: 500;
    color: var(--gray-500);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 0.25rem;
}

.metric-value {
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--gray-900);
    letter-spacing: -0.02em;
}

.metric-card--primary .metric-value {
    color: var(--brand-primary);
}

.metric-card--success .metric-value {
    color: var(--green-700);
}

.metric-card--warning .metric-value {
    color: var(--amber-600);
}

.metric-card--danger .metric-value {
    color: var(--red-600);
}

.metric-sublabel {
    font-size: 0.75rem;
    color: var(--gray-400);
    margin-top: 0.25rem;
}

/* ============================================
   COLLAPSIBLE PANELS
   ============================================ */
.panel {
    background: white;
    border: 1px solid var(--gray-200);
    border-radius: 8px;
    margin-bottom: 1rem;
}

.panel-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1rem;
    cursor: pointer;
    user-select: none;
}

.panel-header:hover {
    background: var(--gray-50);
}

.panel-title {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.9375rem;
    font-weight: 600;
    color: var(--gray-700);
}

.panel-toggle {
    color: var(--gray-400);
    transition: transform 0.2s ease;
}

.panel-toggle--open {
    transform: rotate(180deg);
}

.panel-content {
    padding: 0 1rem 1rem;
    border-top: 1px solid var(--gray-100);
}

/* ============================================
   COMPARE OPTIONS TABLE
   ============================================ */
.compare-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.875rem;
}

.compare-table th {
    text-align: left;
    padding: 0.75rem;
    background: var(--gray-50);
    border-bottom: 1px solid var(--gray-200);
    font-weight: 600;
    color: var(--gray-700);
}

.compare-table td {
    padding: 0.75rem;
    border-bottom: 1px solid var(--gray-100);
    color: var(--gray-600);
}

.compare-table tr:hover td {
    background: var(--gray-50);
}

.compare-table .select-btn {
    padding: 0.375rem 0.75rem;
    font-size: 0.8125rem;
    font-weight: 500;
    color: var(--brand-primary);
    background: white;
    border: 1px solid var(--brand-primary);
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.15s ease;
}

.compare-table .select-btn:hover {
    background: var(--brand-light);
}

/* ============================================
   CUSTOMIZE PANEL
   ============================================ */
.customize-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 1rem;
    margin-bottom: 1rem;
}

.customize-field {
    display: flex;
    flex-direction: column;
    gap: 0.375rem;
}

.customize-label {
    font-size: 0.8125rem;
    font-weight: 500;
    color: var(--gray-600);
}

.preview-chart {
    padding: 1rem;
    background: var(--gray-50);
    border-radius: 6px;
    margin-top: 1rem;
}

.preview-title {
    font-size: 0.8125rem;
    font-weight: 600;
    color: var(--gray-700);
    margin-bottom: 0.75rem;
}

.preview-row {
    display: flex;
    justify-content: space-between;
    padding: 0.5rem 0;
    font-size: 0.875rem;
    border-bottom: 1px solid var(--gray-200);
}

.preview-row:last-child {
    border-bottom: none;
}

.preview-age {
    color: var(--gray-500);
}

.preview-amount {
    font-weight: 600;
    color: var(--gray-800);
}

/* ============================================
   EMPLOYEE BREAKDOWN TABS
   ============================================ */
.breakdown-tabs {
    display: flex;
    gap: 0.5rem;
    margin-bottom: 1rem;
    border-bottom: 1px solid var(--gray-200);
    padding-bottom: 0.5rem;
}

.breakdown-tab {
    padding: 0.5rem 1rem;
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--gray-500);
    background: none;
    border: none;
    cursor: pointer;
    border-radius: 4px 4px 0 0;
    transition: all 0.15s ease;
}

.breakdown-tab:hover {
    color: var(--gray-700);
    background: var(--gray-50);
}

.breakdown-tab--active {
    color: var(--brand-primary);
    background: var(--brand-light);
    border-bottom: 2px solid var(--brand-primary);
}

/* ============================================
   ACTION BAR
   ============================================ */
.action-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1rem 1.5rem;
    background: var(--gray-50);
    border: 1px solid var(--gray-200);
    border-radius: 8px;
    margin-top: 1.5rem;
}

.action-buttons {
    display: flex;
    gap: 0.75rem;
}

.action-warning {
    font-size: 0.875rem;
    color: var(--amber-600);
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

/* ============================================
   STATUS BADGES
   ============================================ */
.status-badge {
    display: inline-flex;
    align-items: center;
    padding: 0.25rem 0.5rem;
    font-size: 0.75rem;
    font-weight: 600;
    border-radius: 4px;
}

.status-badge--success {
    background: var(--green-100);
    color: var(--green-700);
}

.status-badge--warning {
    background: var(--amber-100);
    color: var(--amber-600);
}

.status-badge--error {
    background: var(--red-100);
    color: var(--red-600);
}

.status-badge--info {
    background: var(--blue-100);
    color: var(--blue-700);
}

/* ============================================
   SAFE HARBOR COMPARISON
   ============================================ */
.safe-harbor-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 1rem;
    margin-bottom: 1rem;
}

.safe-harbor-card {
    padding: 1rem;
    background: var(--gray-50);
    border: 1px solid var(--gray-200);
    border-radius: 8px;
}

.safe-harbor-card--selected {
    background: var(--brand-light);
    border: 2px solid var(--brand-primary);
    box-shadow: 0 0 0 3px rgba(0, 71, 171, 0.1);
}

.safe-harbor-card--disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

.safe-harbor-title {
    font-size: 0.9375rem;
    font-weight: 600;
    color: var(--gray-800);
    margin-bottom: 0.5rem;
}

.safe-harbor-cost {
    font-size: 1.25rem;
    font-weight: 700;
    color: var(--gray-900);
    margin-bottom: 0.5rem;
}

.safe-harbor-detail {
    font-size: 0.8125rem;
    color: var(--gray-500);
}

/* ============================================
   UTILITY CLASSES
   ============================================ */
.text-muted { color: var(--gray-500); }
.text-small { font-size: 0.8125rem; }
.font-mono { font-family: ui-monospace, monospace; font-size: 0.8125rem; }
.mt-1 { margin-top: 0.5rem; }
.mt-2 { margin-top: 1rem; }
.mb-1 { margin-bottom: 0.5rem; }
.mb-2 { margin-bottom: 1rem; }
</style>
"""
