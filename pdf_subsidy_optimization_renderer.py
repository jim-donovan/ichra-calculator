"""
Subsidy Optimization PDF Renderer using Playwright + Jinja2

Renders subsidy optimization analysis as a portrait PDF by:
1. Loading HTML template with Jinja2
2. Rendering with Playwright headless Chromium
3. Generating pixel-perfect PDF output

Follows the same pattern as pdf_employer_summary_renderer.py.
"""

from dataclasses import dataclass, field
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from io import BytesIO
from pathlib import Path
from typing import List, Dict, Optional
import base64
import logging
import math
import pandas as pd

# Import the shared browser installation function
from pdf_employer_summary_renderer import _ensure_playwright_browser
from constants import AFFORDABILITY_THRESHOLD_2026


@dataclass
class SubsidyOptimizationData:
    """Data container for subsidy optimization PDF generation."""

    # Header
    client_name: str = ""
    report_date: str = ""  # Formatted as MM.DD.YY
    logo_base64: str = ""

    # Strategy info
    strategy_type: str = "flat"  # 'flat' or 'age_curve'
    strategy_description: str = ""  # e.g., "Flat $500/mo" or "3:1 Age Curve at $400 (age 21)"
    base_contribution: float = 0.0
    base_age: int = 21  # For age curve only

    # Summary metrics (from totals dict)
    total_employees: int = 0
    ptc_count: int = 0
    ichra_count: int = 0
    total_subsidy: float = 0.0
    total_employer_cost: float = 0.0  # For age curve

    # Display options
    show_slcsp: bool = False  # Whether to show SLCSP column

    # Employee data (list of dicts for table)
    employees: List[Dict] = field(default_factory=list)


def _load_logo_base64() -> str:
    """Load the Glove logo and return as base64 string."""
    try:
        logo_path = Path(__file__).parent / "decoratives" / "glove_logo.png"
        if logo_path.exists():
            with open(logo_path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
    except Exception as e:
        logging.warning(f"Could not load logo: {e}")
    return ""


def format_currency(val: Optional[float]) -> str:
    """Format value as currency or dash if None/NaN."""
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return '-'
    return f'${val:,.0f}'


def format_percent(val: Optional[float]) -> str:
    """Format value as percentage or dash if None/NaN."""
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return '-'
    return f'{val:.0f}%'


class SubsidyOptimizationPDFRenderer:
    """Render subsidy optimization analysis as PDF using Playwright + Jinja2"""

    TEMPLATE_DIR = Path(__file__).parent / 'templates' / 'subsidy_optimization'

    def __init__(self):
        """Initialize renderer with Jinja2 environment."""
        self.env = Environment(
            loader=FileSystemLoader(str(self.TEMPLATE_DIR)),
            autoescape=False  # We control the HTML, no XSS risk
        )
        # Add custom filters
        self.env.filters['format_currency'] = format_currency
        self.env.filters['format_percent'] = format_percent

    def generate(self, data: SubsidyOptimizationData) -> BytesIO:
        """
        Generate PDF from HTML template.

        Args:
            data: SubsidyOptimizationData instance with all fields

        Returns:
            BytesIO buffer containing the PDF
        """
        # Ensure browser is installed
        _ensure_playwright_browser()

        # Import playwright here (lazy import)
        from playwright.sync_api import sync_playwright

        # 1. Render HTML with Jinja2
        template = self.env.get_template('subsidy_optimization.html')
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

    def generate_html(self, data: SubsidyOptimizationData) -> str:
        """
        Generate HTML only (useful for debugging).

        Args:
            data: SubsidyOptimizationData instance

        Returns:
            Rendered HTML string
        """
        template = self.env.get_template('subsidy_optimization.html')
        return template.render(data=data)

    def save_html(self, data: SubsidyOptimizationData, path: str) -> None:
        """
        Save rendered HTML to file for debugging.

        Args:
            data: SubsidyOptimizationData instance
            path: Output file path
        """
        html_content = self.generate_html(data)
        with open(path, 'w') as f:
            f.write(html_content)


def build_subsidy_optimization_data(
    breakdown_df: pd.DataFrame,
    totals: Dict,
    strategy_type: str,
    base_contribution: float,
    base_age: int = 21,
    client_name: str = "",
    show_slcsp: bool = False,
) -> SubsidyOptimizationData:
    """
    Build SubsidyOptimizationData from page data.

    Args:
        breakdown_df: DataFrame with employee breakdown (from build_employee_breakdown_dataframe)
        totals: Dict with summary totals
        strategy_type: 'flat' or 'age_curve'
        base_contribution: The contribution amount (flat) or base amount (age_curve)
        base_age: Reference age for age_curve strategy
        client_name: Client/company name
        show_slcsp: Whether to show SLCSP column in PDF

    Returns:
        SubsidyOptimizationData instance
    """
    data = SubsidyOptimizationData(client_name=client_name)
    data.report_date = datetime.now().strftime("%m.%d.%y")
    data.logo_base64 = _load_logo_base64()
    data.show_slcsp = show_slcsp

    # Strategy info
    data.strategy_type = strategy_type
    data.base_contribution = base_contribution
    data.base_age = base_age

    if strategy_type == 'age_curve':
        data.strategy_description = f"3:1 Age Curve at ${base_contribution:,.0f}/mo (age {base_age})"
    else:
        data.strategy_description = f"Flat ${base_contribution:,.0f}/mo"

    # Summary metrics from totals
    data.total_employees = totals.get('total_employees', 0)
    data.ptc_count = totals.get('ptc_count', 0)
    data.ichra_count = totals.get('ichra_count', 0)

    # Handle NaN values
    total_subsidy = totals.get('total_subsidy', 0)
    data.total_subsidy = 0 if (total_subsidy is None or (isinstance(total_subsidy, float) and math.isnan(total_subsidy))) else total_subsidy

    # For flat strategy, calculate total ER cost as contribution * employee count
    # For age_curve, use the pre-calculated total from totals dict
    if strategy_type == 'age_curve':
        total_employer_cost = totals.get('total_employer_cost', 0)
        data.total_employer_cost = 0 if (total_employer_cost is None or (isinstance(total_employer_cost, float) and math.isnan(total_employer_cost))) else total_employer_cost
    else:
        data.total_employer_cost = base_contribution * data.total_employees

    # Build employee list from DataFrame - preserves sort order
    # Note: DataFrame now uses updated column names (Income, ER Contrib, Expected EE Contrib, EE Pays, Affordability)
    employees = []
    if not breakdown_df.empty:
        for _, row in breakdown_df.iterrows():
            # Extract last name only for PDF (handles "First Last" or "Last, First" formats)
            full_name = row.get('Employee', '')
            if ',' in full_name:
                last_name = full_name.split(',')[0].strip()
            elif ' ' in full_name:
                last_name = full_name.split()[-1]
            else:
                last_name = full_name

            emp = {
                'name': last_name,
                'age': int(row.get('Age', 0)),
                'income': row.get('Income', 0),  # Updated from 'Monthly Income'
                'lcsp': row.get('LCSP', 0),
                'slcsp': row.get('SLCSP', 0),
                'fpl_pct': row.get('FPL %', 0),
            }

            # Get ER Contrib - updated from 'ER Allowance'
            contrib = row.get('ER Contrib')
            if contrib is not None and not (isinstance(contrib, float) and math.isnan(contrib)):
                emp['contribution'] = contrib
            else:
                emp['contribution'] = 0  # Fallback

            # Get EE Cost (LCSP - ER Contrib)
            ee_cost = row.get('EE Cost')
            if ee_cost is not None and not (isinstance(ee_cost, float) and math.isnan(ee_cost)):
                emp['ee_cost'] = ee_cost
            else:
                emp['ee_cost'] = emp['lcsp'] - emp['contribution']  # Calculate if missing

            # Calculate affordability threshold and delta for "Affordability" column
            # Affordable if EE Cost <= 9.96% of monthly income
            afford_threshold = emp['income'] * AFFORDABILITY_THRESHOLD_2026
            emp['afford_threshold'] = afford_threshold
            emp['is_affordable'] = emp['ee_cost'] <= afford_threshold

            # Calculate affordability delta for display
            delta = afford_threshold - emp['ee_cost']
            if emp['is_affordable']:
                emp['affordability_display'] = f"${abs(delta):.0f} under"
            else:
                emp['affordability_display'] = f"${abs(delta):.0f} over"

            # Get Expected EE Contrib - updated from 'ACA Expected'
            expected_ee_contrib = row.get('Expected EE Contrib')
            if expected_ee_contrib is not None and not (isinstance(expected_ee_contrib, float) and math.isnan(expected_ee_contrib)):
                emp['expected_ee_contrib'] = expected_ee_contrib
            else:
                emp['expected_ee_contrib'] = 0

            # Handle nullable Subsidy field
            subsidy = row.get('Subsidy')
            emp['subsidy'] = subsidy if (subsidy is not None and not (isinstance(subsidy, float) and math.isnan(subsidy))) else None

            # Get EE Pays - updated from 'Cost w/ PTC'
            ee_pays = row.get('EE Pays')
            if ee_pays is not None and not (isinstance(ee_pays, float) and math.isnan(ee_pays)):
                emp['ee_pays'] = ee_pays
            elif emp['subsidy'] is not None:
                emp['ee_pays'] = emp['lcsp'] - emp['subsidy']  # Calculate if missing
            else:
                emp['ee_pays'] = None

            employees.append(emp)

    data.employees = employees

    return data


def generate_subsidy_optimization_pdf(
    breakdown_df: pd.DataFrame,
    totals: Dict,
    strategy_type: str,
    base_contribution: float,
    base_age: int = 21,
    client_name: str = "",
) -> BytesIO:
    """
    Convenience function to generate subsidy optimization PDF.

    Args:
        breakdown_df: DataFrame with employee breakdown
        totals: Dict with summary totals
        strategy_type: 'flat' or 'age_curve'
        base_contribution: The contribution amount
        base_age: Reference age for age_curve strategy
        client_name: Client/company name

    Returns:
        BytesIO buffer containing the PDF
    """
    data = build_subsidy_optimization_data(
        breakdown_df=breakdown_df,
        totals=totals,
        strategy_type=strategy_type,
        base_contribution=base_contribution,
        base_age=base_age,
        client_name=client_name,
    )

    renderer = SubsidyOptimizationPDFRenderer()
    return renderer.generate(data)


if __name__ == "__main__":
    # Test with sample data
    import pandas as pd

    # Columns: ACA Expected (0-8.5% sliding scale), Subsidy, Cost w/ PTC
    # EE Cost = LCSP - ER Allowance
    sample_employees = [
        {'Employee': 'Jane Doe', 'Age': 32, 'Monthly Income': 4200, 'FPL %': 245, 'LCSP': 420, 'SLCSP': 480, 'ER Allowance': 500, 'EE Cost': -80, 'ACA Expected': 300, 'Subsidy': 180, 'Cost w/ PTC': 240},
        {'Employee': 'John Smith', 'Age': 55, 'Monthly Income': 6100, 'FPL %': 356, 'LCSP': 680, 'SLCSP': 720, 'ER Allowance': 500, 'EE Cost': 180, 'ACA Expected': 520, 'Subsidy': None, 'Cost w/ PTC': None},
        {'Employee': 'Alice Brown', 'Age': 28, 'Monthly Income': 3500, 'FPL %': 200, 'LCSP': 380, 'SLCSP': 400, 'ER Allowance': 500, 'EE Cost': -120, 'ACA Expected': 180, 'Subsidy': 220, 'Cost w/ PTC': 160},
        {'Employee': 'Bob Wilson', 'Age': 45, 'Monthly Income': 8000, 'FPL %': 467, 'LCSP': 550, 'SLCSP': 600, 'ER Allowance': 500, 'EE Cost': 50, 'ACA Expected': 680, 'Subsidy': None, 'Cost w/ PTC': None},
    ]
    breakdown_df = pd.DataFrame(sample_employees)

    totals = {
        'total_employees': 4,
        'ptc_count': 2,
        'ichra_count': 2,
        'total_subsidy': 400,
        'total_employer_cost': 1000,
        'strategy_type': 'flat',
    }

    data = build_subsidy_optimization_data(
        breakdown_df=breakdown_df,
        totals=totals,
        strategy_type='flat',
        base_contribution=500,
        client_name="Test Company",
    )

    renderer = SubsidyOptimizationPDFRenderer()

    # Save HTML for debugging
    renderer.save_html(data, '/tmp/subsidy_optimization_test.html')
    print("HTML saved to /tmp/subsidy_optimization_test.html")

    # Generate PDF
    pdf_buffer = renderer.generate(data)
    with open('/tmp/subsidy_optimization_test.pdf', 'wb') as f:
        f.write(pdf_buffer.read())
    print("PDF saved to /tmp/subsidy_optimization_test.pdf")
