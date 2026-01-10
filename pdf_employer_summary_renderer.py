"""
Employer Summary PDF Renderer using Playwright + Jinja2

Renders employer cost summary as a one-page PDF by:
1. Loading HTML template with Jinja2
2. Rendering with Playwright headless Chromium
3. Generating pixel-perfect PDF output

Note: Requires Chromium system dependencies on the server.
For Railway deployment, see nixpacks.toml for required apt packages.
"""

from dataclasses import dataclass
from jinja2 import Environment, FileSystemLoader
from io import BytesIO
from pathlib import Path
import logging
import subprocess
import sys

# Flag to track if browser has been installed this session
_browser_installed = False


def _ensure_playwright_browser():
    """Ensure Playwright Chromium browser is installed."""
    global _browser_installed
    if _browser_installed:
        return

    try:
        # Try to import and check if browser exists
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            # Try to launch - if it fails, browser needs to be installed
            try:
                browser = p.chromium.launch(headless=True)
                browser.close()
                _browser_installed = True
                return
            except Exception:
                pass

        # Browser not installed, install it
        logging.info("Installing Playwright Chromium browser...")
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            check=True,
            capture_output=True
        )
        _browser_installed = True
        logging.info("Playwright Chromium browser installed successfully")
    except Exception as e:
        logging.warning(f"Could not install Playwright browser: {e}")


@dataclass
class EmployerSummaryData:
    """Data container for employer summary PDF generation."""

    client_name: str = ""

    # Strategy info
    strategy_name: str = ""
    strategy_description: str = ""  # e.g., "65% of Silver LCSP" or "$400/mo flat"
    employees_covered: int = 0
    er_share_pct: float = 0.0

    # Current (2025) costs
    current_er_annual: float = 0.0
    current_ee_annual: float = 0.0
    current_total_annual: float = 0.0

    # Projected 2026 Renewal costs
    projected_er_annual: float = 0.0
    projected_ee_annual: float = 0.0
    renewal_total_annual: float = 0.0
    renewal_increase_pct: float = 0.0

    # Proposed ICHRA
    proposed_ichra_annual: float = 0.0
    avg_per_employee_monthly: float = 0.0

    # Comparisons
    delta_vs_current: float = 0.0  # ICHRA - Current ER (negative = savings)
    delta_vs_current_pct: float = 0.0

    savings_vs_renewal_er: float = 0.0  # Renewal ER - ICHRA (positive = savings)
    savings_vs_renewal_er_pct: float = 0.0

    savings_vs_current_total: float = 0.0  # Current Total - ICHRA
    savings_vs_current_total_pct: float = 0.0

    savings_vs_renewal_total: float = 0.0  # Renewal Total - ICHRA
    savings_vs_renewal_total_pct: float = 0.0

    # ICHRA projected at 70% take rate
    ichra_projected_70: float = 0.0
    savings_ichra_70_vs_renewal: float = 0.0  # Renewal Total - ICHRA 70%
    savings_ichra_70_vs_renewal_pct: float = 0.0

    # Affordability metrics
    has_affordability_data: bool = False
    affordability_adjusted: bool = False  # True if contributions were adjusted to meet threshold
    employees_analyzed: int = 0  # Employees with income data
    employees_affordable: int = 0  # Meeting 9.96% threshold
    employees_affordable_pct: float = 0.0
    employees_needing_increase: int = 0
    affordability_gap_annual: float = 0.0  # Additional cost for 100% compliance


def _savings_format(amount, decimals=0):
    """Jinja2 filter for consistent savings formatting."""
    if amount > 0:
        return f"${amount:,.{decimals}f} saved"
    elif amount < 0:
        return f"${abs(amount):,.{decimals}f} more"
    else:
        return "no change"


def _savings_er_only(amount, decimals=0):
    """Jinja2 filter for ER-only fine print."""
    if amount > 0:
        return f"ER only: ${amount:,.{decimals}f} saved"
    elif amount < 0:
        return f"ER only: ${abs(amount):,.{decimals}f} more"
    else:
        return "ER only: no change"


class EmployerSummaryPDFRenderer:
    """Render employer summary as PDF using Playwright + Jinja2"""

    TEMPLATE_DIR = Path(__file__).parent / 'templates' / 'employer_summary'

    def __init__(self):
        """Initialize renderer with Jinja2 environment."""
        self.env = Environment(
            loader=FileSystemLoader(str(self.TEMPLATE_DIR)),
            autoescape=False  # We control the HTML, no XSS risk
        )
        # Add custom filters for savings formatting
        self.env.filters['savings_format'] = _savings_format
        self.env.filters['savings_er_only'] = _savings_er_only

    def generate(self, data: EmployerSummaryData) -> BytesIO:
        """
        Generate PDF from HTML template.

        Args:
            data: EmployerSummaryData instance with all cost fields

        Returns:
            BytesIO buffer containing the PDF
        """
        # Ensure browser is installed
        _ensure_playwright_browser()

        # Import playwright here (lazy import)
        from playwright.sync_api import sync_playwright

        # 1. Render HTML with Jinja2
        template = self.env.get_template('employer_summary.html')
        html_content = template.render(data=data)

        # 2. Convert to PDF with Playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # Set content and wait for fonts/images to load
            page.set_content(html_content, wait_until='networkidle')

            # Generate PDF with portrait letter size
            pdf_bytes = page.pdf(
                format='Letter',
                landscape=False,
                print_background=True,
                margin={
                    'top': '0',
                    'right': '0',
                    'bottom': '0',
                    'left': '0'
                }
            )

            browser.close()

        # Return as BytesIO buffer
        buffer = BytesIO(pdf_bytes)
        buffer.seek(0)
        return buffer

    def generate_html(self, data: EmployerSummaryData) -> str:
        """
        Generate HTML only (useful for debugging).

        Args:
            data: EmployerSummaryData instance

        Returns:
            Rendered HTML string
        """
        template = self.env.get_template('employer_summary.html')
        return template.render(data=data)

    def save_html(self, data: EmployerSummaryData, path: str) -> None:
        """
        Save rendered HTML to file for debugging.

        Args:
            data: EmployerSummaryData instance
            path: Output file path
        """
        html_content = self.generate_html(data)
        with open(path, 'w') as f:
            f.write(html_content)


def build_employer_summary_data(
    strategy_results: dict,
    contrib_totals: dict,
    renewal_data: dict,
    client_name: str = "",
    affordability_impact: dict = None
) -> EmployerSummaryData:
    """
    Build EmployerSummaryData from session state data.

    Args:
        strategy_results: Strategy calculation results from session_state
        contrib_totals: Contribution totals from ContributionComparison.aggregate_contribution_totals()
        renewal_data: Dict with renewal_total_annual, projected_er_annual, projected_ee_annual
        client_name: Client/company name
        affordability_impact: Optional dict from calculate_affordability_impact() with:
            - after: {affordable_count, affordable_pct, employees_analyzed, total_gap}

    Returns:
        EmployerSummaryData instance
    """
    data = EmployerSummaryData(client_name=client_name)

    # Strategy info
    result = strategy_results.get('result', {})
    data.strategy_name = result.get('strategy_name', 'Applied Strategy')
    data.employees_covered = result.get('employees_covered', 0)

    # Build strategy description from config
    config = strategy_results.get('config', {})
    strategy_type = config.get('strategy_type', '')
    if strategy_type == 'PERCENTAGE_LCSP':
        pct = config.get('lcsp_percentage', 0)
        data.strategy_description = f"{pct:.0f}% of lowest-cost Silver plan (LCSP)"
    elif strategy_type == 'BASE_AGE_CURVE':
        base = config.get('base_amount', 0)
        data.strategy_description = f"${base:,.0f}/mo base (age 21), scaled by ACA age curve"
    elif strategy_type == 'FIXED_AGE_TIERS':
        data.strategy_description = "Fixed dollar amounts by age tier"
    elif strategy_type == 'flat' or 'flat' in data.strategy_name.lower():
        # Flat contribution - calculate from total/employees
        if data.employees_covered > 0:
            proposed_monthly = result.get('total_monthly', 0)
            avg_monthly = proposed_monthly / data.employees_covered
            data.strategy_description = f"${avg_monthly:,.0f}/mo flat contribution per employee"
        else:
            data.strategy_description = "Flat contribution per employee"
    else:
        # Default: try to use strategy name or calculate from totals
        if data.employees_covered > 0:
            proposed_monthly = result.get('total_monthly', 0)
            avg_monthly = proposed_monthly / data.employees_covered
            data.strategy_description = f"~${avg_monthly:,.0f}/mo average per employee"
        else:
            data.strategy_description = data.strategy_name

    # Proposed ICHRA
    data.proposed_ichra_annual = result.get('total_annual', 0)
    proposed_monthly = result.get('total_monthly', 0)
    data.avg_per_employee_monthly = proposed_monthly / data.employees_covered if data.employees_covered > 0 else 0

    # Current (2025) costs
    data.current_er_annual = contrib_totals.get('total_current_er_annual', 0)
    data.current_ee_annual = contrib_totals.get('total_current_ee_annual', 0)
    data.current_total_annual = data.current_er_annual + data.current_ee_annual

    current_er_monthly = contrib_totals.get('total_current_er_monthly', 0)
    current_total_monthly = current_er_monthly + contrib_totals.get('total_current_ee_monthly', 0)

    # ER share percentage
    data.er_share_pct = (current_er_monthly / current_total_monthly * 100) if current_total_monthly > 0 else 60.0

    # Renewal data
    data.renewal_total_annual = renewal_data.get('renewal_total_annual', 0)
    data.projected_er_annual = renewal_data.get('projected_er_annual', 0)
    data.projected_ee_annual = renewal_data.get('projected_ee_annual', 0)

    # Renewal increase percentage
    if data.current_total_annual > 0:
        data.renewal_increase_pct = ((data.renewal_total_annual / data.current_total_annual) - 1) * 100
    else:
        data.renewal_increase_pct = 0

    # Comparisons
    # 1. vs Current ER (negative = ICHRA saves)
    data.delta_vs_current = data.proposed_ichra_annual - data.current_er_annual
    if data.current_er_annual > 0:
        data.delta_vs_current_pct = (data.delta_vs_current / data.current_er_annual) * 100
    else:
        data.delta_vs_current_pct = 0

    # 2. vs Renewal ER (positive = ICHRA saves)
    data.savings_vs_renewal_er = data.projected_er_annual - data.proposed_ichra_annual
    if data.projected_er_annual > 0:
        data.savings_vs_renewal_er_pct = (data.savings_vs_renewal_er / data.projected_er_annual) * 100
    else:
        data.savings_vs_renewal_er_pct = 0

    # 3. vs Current Total (positive = ICHRA saves)
    data.savings_vs_current_total = data.current_total_annual - data.proposed_ichra_annual
    if data.current_total_annual > 0:
        data.savings_vs_current_total_pct = (data.savings_vs_current_total / data.current_total_annual) * 100
    else:
        data.savings_vs_current_total_pct = 0

    # 4. vs Renewal Total (positive = ICHRA saves)
    data.savings_vs_renewal_total = data.renewal_total_annual - data.proposed_ichra_annual
    if data.renewal_total_annual > 0:
        data.savings_vs_renewal_total_pct = (data.savings_vs_renewal_total / data.renewal_total_annual) * 100
    else:
        data.savings_vs_renewal_total_pct = 0

    # 5. ICHRA projected at 70% take rate
    data.ichra_projected_70 = data.proposed_ichra_annual * 0.70

    # 6. Savings: ICHRA 70% vs Renewal Total
    data.savings_ichra_70_vs_renewal = data.renewal_total_annual - data.ichra_projected_70
    if data.renewal_total_annual > 0:
        data.savings_ichra_70_vs_renewal_pct = (data.savings_ichra_70_vs_renewal / data.renewal_total_annual) * 100
    else:
        data.savings_ichra_70_vs_renewal_pct = 0

    # 7. Affordability metrics (if provided)
    if affordability_impact:
        after = affordability_impact.get('after', {})
        data.has_affordability_data = True
        employees_analyzed_raw = after.get('employees_analyzed', 0)
        # Fall back to employees_covered if employees_analyzed is 0
        data.employees_analyzed = employees_analyzed_raw if employees_analyzed_raw > 0 else data.employees_covered
        data.employees_affordable = after.get('affordable_count', 0)
        # If no affordability data but we have employees, assume all are affordable
        if data.employees_affordable == 0 and employees_analyzed_raw == 0 and data.employees_covered > 0:
            data.employees_affordable = data.employees_covered
        data.employees_affordable_pct = after.get('affordable_pct', 0)
        data.employees_needing_increase = data.employees_analyzed - data.employees_affordable
        data.affordability_gap_annual = after.get('total_gap', 0)

        # Check if contributions were already adjusted to meet affordability
        data.affordability_adjusted = result.get('affordability_adjusted', False)
    else:
        # No affordability data provided - use employees_covered as fallback
        data.has_affordability_data = True  # Show the section anyway
        data.employees_analyzed = data.employees_covered
        data.employees_affordable = data.employees_covered  # Assume all affordable
        data.employees_affordable_pct = 100.0
        data.employees_needing_increase = 0
        data.affordability_gap_annual = 0
        data.affordability_adjusted = False

    return data


def generate_employer_summary_pdf(
    strategy_results: dict,
    contrib_totals: dict,
    renewal_data: dict,
    client_name: str = "",
    affordability_impact: dict = None
) -> BytesIO:
    """
    Convenience function to generate employer summary PDF.

    Args:
        strategy_results: Strategy calculation results
        contrib_totals: Contribution totals
        renewal_data: Renewal cost data
        client_name: Client/company name
        affordability_impact: Optional affordability metrics

    Returns:
        BytesIO buffer containing the PDF
    """
    data = build_employer_summary_data(
        strategy_results=strategy_results,
        contrib_totals=contrib_totals,
        renewal_data=renewal_data,
        client_name=client_name,
        affordability_impact=affordability_impact
    )

    renderer = EmployerSummaryPDFRenderer()
    return renderer.generate(data)


if __name__ == "__main__":
    # Test with sample data
    strategy_results = {
        'calculated': True,
        'result': {
            'strategy_name': 'Base Age 21 + ACA 3:1 Curve',
            'employees_covered': 49,
            'total_annual': 144427.20,
            'total_monthly': 12035.60
        }
    }

    contrib_totals = {
        'total_current_er_annual': 294000.00,
        'total_current_ee_annual': 0.00,
        'total_current_er_monthly': 24500.00,
        'total_current_ee_monthly': 0.00
    }

    renewal_data = {
        'renewal_total_annual': 294000.00,
        'projected_er_annual': 294000.00,
        'projected_ee_annual': 0.00
    }

    data = build_employer_summary_data(
        strategy_results=strategy_results,
        contrib_totals=contrib_totals,
        renewal_data=renewal_data,
        client_name="Test Company"
    )

    renderer = EmployerSummaryPDFRenderer()

    # Save HTML for debugging
    renderer.save_html(data, '/tmp/employer_summary_test.html')
    print("HTML saved to /tmp/employer_summary_test.html")

    # Generate PDF
    pdf_buffer = renderer.generate(data)
    with open('/tmp/employer_summary_test.pdf', 'wb') as f:
        f.write(pdf_buffer.read())
    print("PDF saved to /tmp/employer_summary_test.pdf")
