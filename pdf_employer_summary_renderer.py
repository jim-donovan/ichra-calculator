"""
Employer Summary PDF Renderer using Playwright + Jinja2

Renders employer cost summary as a one-page PDF by:
1. Loading HTML template with Jinja2
2. Rendering with Playwright headless Chromium
3. Generating pixel-perfect PDF output
"""

from dataclasses import dataclass
from playwright.sync_api import sync_playwright
from jinja2 import Environment, FileSystemLoader
from io import BytesIO
from pathlib import Path


@dataclass
class EmployerSummaryData:
    """Data container for employer summary PDF generation."""

    client_name: str = ""

    # Strategy info
    strategy_name: str = ""
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

    savings_vs_renewal_total: float = 0.0  # Renewal Total - ICHRA
    savings_vs_renewal_total_pct: float = 0.0


class EmployerSummaryPDFRenderer:
    """Render employer summary as PDF using Playwright + Jinja2"""

    TEMPLATE_DIR = Path(__file__).parent / 'templates' / 'employer_summary'

    def __init__(self):
        """Initialize renderer with Jinja2 environment."""
        self.env = Environment(
            loader=FileSystemLoader(str(self.TEMPLATE_DIR)),
            autoescape=False  # We control the HTML, no XSS risk
        )

    def generate(self, data: EmployerSummaryData) -> BytesIO:
        """
        Generate PDF from HTML template.

        Args:
            data: EmployerSummaryData instance with all cost fields

        Returns:
            BytesIO buffer containing the PDF
        """
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
    client_name: str = ""
) -> EmployerSummaryData:
    """
    Build EmployerSummaryData from session state data.

    Args:
        strategy_results: Strategy calculation results from session_state
        contrib_totals: Contribution totals from ContributionComparison.aggregate_contribution_totals()
        renewal_data: Dict with renewal_total_annual, projected_er_annual, projected_ee_annual
        client_name: Client/company name

    Returns:
        EmployerSummaryData instance
    """
    data = EmployerSummaryData(client_name=client_name)

    # Strategy info
    result = strategy_results.get('result', {})
    data.strategy_name = result.get('strategy_name', 'Applied Strategy')
    data.employees_covered = result.get('employees_covered', 0)

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

    # 3. vs Renewal Total (positive = ICHRA saves)
    data.savings_vs_renewal_total = data.renewal_total_annual - data.proposed_ichra_annual
    if data.renewal_total_annual > 0:
        data.savings_vs_renewal_total_pct = (data.savings_vs_renewal_total / data.renewal_total_annual) * 100
    else:
        data.savings_vs_renewal_total_pct = 0

    return data


def generate_employer_summary_pdf(
    strategy_results: dict,
    contrib_totals: dict,
    renewal_data: dict,
    client_name: str = ""
) -> BytesIO:
    """
    Convenience function to generate employer summary PDF.

    Args:
        strategy_results: Strategy calculation results
        contrib_totals: Contribution totals
        renewal_data: Renewal cost data
        client_name: Client/company name

    Returns:
        BytesIO buffer containing the PDF
    """
    data = build_employer_summary_data(
        strategy_results=strategy_results,
        contrib_totals=contrib_totals,
        renewal_data=renewal_data,
        client_name=client_name
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
