"""
Cooperative Health Plan Comparison Slide Generator

Generates a single PowerPoint slide with the Cooperative Health Plan Comparison table
that matches the design from the ICHRA dashboard.
"""

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from typing import Dict, List, Optional, Any
from io import BytesIO
from pathlib import Path
from dataclasses import dataclass, field
import pandas as pd


# Color scheme matching Figma design
COLORS = {
    # Current 2025 - Blue
    'current_bg': RGBColor(0xEF, 0xF6, 0xFF),      # #EFF6FF
    'current_text': RGBColor(0x1C, 0x39, 0x8E),    # #1C398E
    'current_header': RGBColor(0xDB, 0xEA, 0xFE),  # #DBEAFE

    # Renewal 2026 - Red
    'renewal_bg': RGBColor(0xFE, 0xF2, 0xF2),      # #FEF2F2
    'renewal_text': RGBColor(0x82, 0x18, 0x1A),    # #82181A
    'renewal_header': RGBColor(0xFE, 0xCA, 0xCA),  # #FECACA

    # HAP - Green
    'hap_bg': RGBColor(0xF0, 0xFD, 0xF4),          # #F0FDF4
    'hap_text': RGBColor(0x0D, 0x54, 0x2B),        # #0D542B
    'hap_header': RGBColor(0xBB, 0xF7, 0xD0),      # #BBF7D0

    # Neutral
    'row_label_bg': RGBColor(0xF9, 0xFA, 0xFB),    # #F9FAFB
    'row_label_text': RGBColor(0x37, 0x41, 0x51),  # #374151
    'total_bg': RGBColor(0xF3, 0xF4, 0xF6),        # #F3F4F6
    'total_text': RGBColor(0x11, 0x18, 0x27),      # #111827
    'gap_text': RGBColor(0x6A, 0x72, 0x82),        # #6A7282 - gray for breakdown
    'border': RGBColor(0xE5, 0xE7, 0xEB),          # #E5E7EB
    'white': RGBColor(0xFF, 0xFF, 0xFF),           # #FFFFFF
}

# Slide dimensions (standard widescreen 16:9)
SLIDE_WIDTH = Inches(13.333)
SLIDE_HEIGHT = Inches(7.5)

# Decorative image paths
DECORATIVE_IMAGES_DIR = Path(__file__).parent.parent / "glove-design" / "✍️ Design + Crit 01"
CORNER_IMAGE = DECORATIVE_IMAGES_DIR / "glove-tile-corner.png"
EDGE_IMAGE = DECORATIVE_IMAGES_DIR / "glove-tile-edge-h-fade.png"


@dataclass
class TierData:
    """Data for a single coverage tier row"""
    name: str  # Display name (e.g., "Employee Only")
    code: str  # Tier code (e.g., "EE")
    current_total: float = 0.0
    current_base: float = 0.0
    current_gap: float = 0.0
    renewal_total: float = 0.0
    renewal_base: float = 0.0
    renewal_gap: float = 0.0
    hap_1k_total: float = 0.0
    hap_1k_min: float = 0.0
    hap_1k_max: float = 0.0
    hap_25k_total: float = 0.0
    hap_25k_min: float = 0.0
    hap_25k_max: float = 0.0
    # New fields for employee count and per-employee rates
    employee_count: int = 0
    avg_age: int = 0  # Average age of employees in this tier
    current_rate_per_ee: float = 0.0  # Average per-employee base rate (current)
    renewal_rate_per_ee: float = 0.0  # Average per-employee base rate (renewal)
    gap_rate_per_ee: float = 0.0      # Fixed gap rate per employee for this tier


@dataclass
class CooperativeHealthData:
    """Data container for Cooperative Health Plan Comparison slide"""

    # Tier breakdown
    tiers: List[TierData] = field(default_factory=list)

    # Monthly totals
    total_current: float = 0.0
    total_renewal: float = 0.0
    total_hap_1k: float = 0.0
    total_hap_25k: float = 0.0

    # Annual totals
    annual_current: float = 0.0
    annual_renewal: float = 0.0
    annual_hap_1k: float = 0.0
    annual_hap_25k: float = 0.0

    # Savings vs renewal (annual)
    savings_hap_1k: float = 0.0
    savings_hap_1k_pct: float = 0.0
    savings_hap_25k: float = 0.0
    savings_hap_25k_pct: float = 0.0

    # Gap insurance details
    has_gap: bool = False
    total_gap_monthly: float = 0.0
    gap_rate_ee: float = 0.0
    gap_rate_es: float = 0.0
    gap_rate_ec: float = 0.0
    gap_rate_f: float = 0.0

    # Client info
    client_name: str = ""

    @classmethod
    def from_session_state(cls, session_state) -> 'CooperativeHealthData':
        """
        Build CooperativeHealthData from Streamlit session_state.

        Args:
            session_state: st.session_state object

        Returns:
            Populated CooperativeHealthData instance
        """
        data = cls()

        census_df = session_state.get('census_df')
        financial_summary = session_state.get('financial_summary', {})
        client_name = session_state.get('client_name', '')

        data.client_name = client_name

        if census_df is None or census_df.empty:
            return data

        # Get multi-metal scenario data if available
        multi_metal = financial_summary.get('multi_metal_scenario', {})
        tier_totals = multi_metal.get('tier_totals', {})
        hap_analysis = multi_metal.get('hap_analysis', {})

        # Check for gap insurance data
        has_gap_col = 'gap_insurance_monthly' in census_df.columns
        if has_gap_col:
            gap_values = census_df['gap_insurance_monthly'].fillna(0)
            if gap_values.sum() > 0:
                data.has_gap = True
                data.total_gap_monthly = float(gap_values.sum())

                # Get gap rates by tier (fixed per tier - take first non-zero)
                for code, attr in [('EE', 'gap_rate_ee'), ('ES', 'gap_rate_es'),
                                   ('EC', 'gap_rate_ec'), ('F', 'gap_rate_f')]:
                    tier_emps = census_df[census_df['family_status'] == code]
                    if not tier_emps.empty:
                        gap_vals = tier_emps['gap_insurance_monthly'].dropna()
                        gap_vals = gap_vals[gap_vals > 0]
                        if len(gap_vals) > 0:
                            setattr(data, attr, float(gap_vals.iloc[0]))

        # Define tier info
        tier_info = {
            'Employee Only': {'code': 'EE', 'display': 'Employee Only'},
            'Employee + Spouse': {'code': 'ES', 'display': 'Employee + Spouse'},
            'Employee + Children': {'code': 'EC', 'display': 'Employee + Children'},
            'Family': {'code': 'F', 'display': 'Family'},
        }

        # Build tier data
        for tier_name, info in tier_info.items():
            tier_data = tier_totals.get(tier_name, {})
            code = info['code']

            # Calculate gap for this tier
            tier_gap = 0.0
            if data.has_gap:
                tier_emps = census_df[census_df['family_status'] == code]
                if not tier_emps.empty:
                    tier_gap = float(tier_emps['gap_insurance_monthly'].fillna(0).sum())

            # Get HAP analysis for this tier
            hap_1k = hap_analysis.get('hap_1k', {}).get(tier_name, {})
            hap_25k = hap_analysis.get('hap_2.5k', {}).get(tier_name, {})

            # Base premiums (without gap)
            current_base = tier_data.get('current_total', 0) or 0
            renewal_base = tier_data.get('renewal_2026', 0) or 0

            # Total includes gap insurance if present
            current_total = current_base + tier_gap
            renewal_total = renewal_base + tier_gap

            # Get employee count for this tier
            tier_emps = census_df[census_df['family_status'] == code]
            employee_count = len(tier_emps)

            # Get typical per-employee current rate (most common value from census)
            if 'current_ee_monthly' in census_df.columns and 'current_er_monthly' in census_df.columns:
                ee_vals = tier_emps['current_ee_monthly'].fillna(0)
                er_vals = tier_emps['current_er_monthly'].fillna(0)
                per_ee_rates = ee_vals + er_vals
                non_zero_rates = per_ee_rates[per_ee_rates > 0]
                if len(non_zero_rates) > 0:
                    try:
                        current_rate_per_ee = float(non_zero_rates.mode().iloc[0])
                    except (IndexError, ValueError):
                        current_rate_per_ee = float(non_zero_rates.iloc[0])
                else:
                    current_rate_per_ee = 0
            else:
                current_rate_per_ee = 0

            # Get typical per-employee renewal rate (most common value from census)
            if 'projected_2026_premium' in census_df.columns:
                renewal_vals = tier_emps['projected_2026_premium'].fillna(0)
                non_zero_renewal = renewal_vals[renewal_vals > 0]
                if len(non_zero_renewal) > 0:
                    try:
                        renewal_rate_per_ee = float(non_zero_renewal.mode().iloc[0])
                    except (IndexError, ValueError):
                        renewal_rate_per_ee = float(non_zero_renewal.iloc[0])
                else:
                    renewal_rate_per_ee = 0
            else:
                renewal_rate_per_ee = 0

            # Get gap rate for this tier (fixed per tier)
            gap_rate_per_ee = getattr(data, f'gap_rate_{code.lower()}', 0)

            # Calculate average age for this tier
            avg_age = 0
            if 'age' in tier_emps.columns and employee_count > 0:
                avg_age = round(tier_emps['age'].mean())

            tier = TierData(
                name=tier_name,
                code=code,
                current_total=current_total,
                current_base=current_base,
                current_gap=tier_gap,
                renewal_total=renewal_total,
                renewal_base=renewal_base,
                renewal_gap=tier_gap,
                hap_1k_total=hap_1k.get('total', 0) or 0,
                hap_1k_min=hap_1k.get('min_rate', 0) or 0,
                hap_1k_max=hap_1k.get('max_rate', 0) or 0,
                hap_25k_total=hap_25k.get('total', 0) or 0,
                hap_25k_min=hap_25k.get('min_rate', 0) or 0,
                hap_25k_max=hap_25k.get('max_rate', 0) or 0,
                employee_count=employee_count,
                avg_age=avg_age,
                current_rate_per_ee=current_rate_per_ee,
                renewal_rate_per_ee=renewal_rate_per_ee,
                gap_rate_per_ee=gap_rate_per_ee,
            )
            data.tiers.append(tier)

        # Calculate totals
        data.total_current = sum(t.current_total for t in data.tiers)
        data.total_renewal = sum(t.renewal_total for t in data.tiers)
        data.total_hap_1k = sum(t.hap_1k_total for t in data.tiers)
        data.total_hap_25k = sum(t.hap_25k_total for t in data.tiers)

        return data


class CooperativeHealthSlideGenerator:
    """Generate Cooperative Health Plan Comparison PowerPoint slide"""

    def __init__(self):
        """Initialize with a new blank presentation"""
        self.prs = Presentation()
        # Set slide dimensions to standard widescreen
        self.prs.slide_width = SLIDE_WIDTH
        self.prs.slide_height = SLIDE_HEIGHT

    def _set_cell_fill(self, cell, color: RGBColor):
        """Set cell background color"""
        cell.fill.solid()
        cell.fill.fore_color.rgb = color

    def _set_cell_text(self, cell, text: str, color: RGBColor,
                       font_size: int = 11, bold: bool = False,
                       align: PP_ALIGN = PP_ALIGN.CENTER):
        """Set cell text with formatting"""
        cell.text = text
        cell.text_frame.paragraphs[0].alignment = align
        cell.text_frame.paragraphs[0].font.name = 'Poppins'
        cell.text_frame.paragraphs[0].font.size = Pt(font_size)
        cell.text_frame.paragraphs[0].font.color.rgb = color
        cell.text_frame.paragraphs[0].font.bold = bold
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE

    def _add_cell_line(self, cell, text: str, color: RGBColor,
                       font_size: int = 10, bold: bool = False,
                       align: PP_ALIGN = PP_ALIGN.CENTER):
        """Add additional line to cell"""
        p = cell.text_frame.add_paragraph()
        p.text = text
        p.alignment = align
        p.font.name = 'Poppins'
        p.font.size = Pt(font_size)
        p.font.color.rgb = color
        p.font.bold = bold

    def _format_currency(self, value: float) -> str:
        """Format value as currency"""
        return f"${value:,.0f}"

    def create_slide(self, data: CooperativeHealthData) -> None:
        """
        Create the Cooperative Health Plan Comparison slide.

        Args:
            data: CooperativeHealthData with values to display
        """
        # Add blank slide
        blank_layout = self.prs.slide_layouts[6]  # Blank layout
        slide = self.prs.slides.add_slide(blank_layout)

        # Add title
        title_left = Inches(0.5)
        title_top = Inches(0.4)
        title_width = Inches(12.33)
        title_height = Inches(0.6)

        title_box = slide.shapes.add_textbox(title_left, title_top, title_width, title_height)
        title_tf = title_box.text_frame
        title_tf.paragraphs[0].text = "Cooperative Health Plan Comparison"
        title_tf.paragraphs[0].font.name = 'Poppins'
        title_tf.paragraphs[0].font.size = Pt(28)
        title_tf.paragraphs[0].font.bold = True
        title_tf.paragraphs[0].font.color.rgb = COLORS['total_text']

        # Add subtitle/description
        subtitle_top = Inches(1.0)
        subtitle_height = Inches(0.4)

        subtitle_box = slide.shapes.add_textbox(title_left, subtitle_top, title_width, subtitle_height)
        subtitle_tf = subtitle_box.text_frame
        subtitle_tf.paragraphs[0].text = "Traditional group plan vs. Health Access Plan alternatives"
        subtitle_tf.paragraphs[0].font.name = 'Poppins'
        subtitle_tf.paragraphs[0].font.size = Pt(14)
        subtitle_tf.paragraphs[0].font.color.rgb = COLORS['gap_text']

        # Create table
        table_left = Inches(0.5)
        table_top = Inches(1.6)
        table_width = Inches(12.33)

        # Calculate row heights
        header_height = Inches(0.5)
        tier_height = Inches(0.65) if data.has_gap else Inches(0.5)
        summary_height = Inches(0.5)

        num_rows = 8  # Header + 4 tiers + Total Monthly + Annual Total + Savings vs Renewal
        table_height = header_height + (4 * tier_height) + (3 * summary_height)

        # Add table: 8 rows x 5 columns
        table = slide.shapes.add_table(num_rows, 5, table_left, table_top,
                                        table_width, table_height).table

        # Set column widths
        col_widths = [Inches(2.5), Inches(2.46), Inches(2.46), Inches(2.46), Inches(2.46)]
        for i, width in enumerate(col_widths):
            table.columns[i].width = width

        # Style header row
        headers = ['Coverage Type', 'Current 2025', 'Renewal 2026', 'HAP $1k', 'HAP $2.5k']
        header_colors = [
            (COLORS['row_label_bg'], COLORS['row_label_text']),
            (COLORS['current_header'], COLORS['current_text']),
            (COLORS['renewal_header'], COLORS['renewal_text']),
            (COLORS['hap_header'], COLORS['hap_text']),
            (COLORS['hap_header'], COLORS['hap_text']),
        ]

        for col_idx, (header_text, (bg_color, text_color)) in enumerate(zip(headers, header_colors)):
            cell = table.cell(0, col_idx)
            self._set_cell_fill(cell, bg_color)
            self._set_cell_text(cell, header_text, text_color, font_size=12, bold=True)

        # Data cell text colors (used for tier rows and summary rows)
        data_text_colors = [
            COLORS['row_label_text'],
            COLORS['current_text'],
            COLORS['renewal_text'],
            COLORS['hap_text'],
            COLORS['hap_text'],
        ]

        # Style tier rows (white background for data cells)
        for row_idx, tier in enumerate(data.tiers, start=1):
            # Coverage Type column - with employee count (left-aligned)
            cell = table.cell(row_idx, 0)
            self._set_cell_fill(cell, COLORS['row_label_bg'])
            self._set_cell_text(cell, tier.name, data_text_colors[0],
                               font_size=11, bold=True, align=PP_ALIGN.LEFT)
            if tier.employee_count > 0:
                # Format employee count with average age
                age_suffix = f" · avg age {tier.avg_age}" if tier.avg_age > 0 else ""
                self._add_cell_line(cell, f"{tier.employee_count} employees{age_suffix}", COLORS['gap_text'],
                                   font_size=10, align=PP_ALIGN.LEFT)

            # Current 2025 column - white background
            cell = table.cell(row_idx, 1)
            self._set_cell_fill(cell, COLORS['white'])
            self._set_cell_text(cell, self._format_currency(tier.current_total),
                               data_text_colors[1], font_size=12, bold=True)
            # Breakdown: show per-employee rate (with gap if applicable)
            if tier.current_rate_per_ee > 0:
                if data.has_gap and tier.gap_rate_per_ee > 0:
                    breakdown = f"${tier.current_rate_per_ee:,.0f} + ${tier.gap_rate_per_ee:,.0f} gap"
                else:
                    breakdown = f"${tier.current_rate_per_ee:,.0f}"
                self._add_cell_line(cell, breakdown, COLORS['gap_text'], font_size=10)

            # Renewal 2026 column - white background
            cell = table.cell(row_idx, 2)
            self._set_cell_fill(cell, COLORS['white'])
            self._set_cell_text(cell, self._format_currency(tier.renewal_total),
                               data_text_colors[2], font_size=12, bold=True)
            # Breakdown: show per-employee rate (with gap if applicable)
            if tier.renewal_rate_per_ee > 0:
                if data.has_gap and tier.gap_rate_per_ee > 0:
                    breakdown = f"${tier.renewal_rate_per_ee:,.0f} + ${tier.gap_rate_per_ee:,.0f} gap"
                else:
                    breakdown = f"${tier.renewal_rate_per_ee:,.0f}"
                self._add_cell_line(cell, breakdown, COLORS['gap_text'], font_size=10)

            # HAP $1k column - white background
            cell = table.cell(row_idx, 3)
            self._set_cell_fill(cell, COLORS['white'])
            self._set_cell_text(cell, self._format_currency(tier.hap_1k_total),
                               data_text_colors[3], font_size=12, bold=True)
            if tier.hap_1k_min > 0 and tier.hap_1k_max > 0:
                rate_range = f"${tier.hap_1k_min:,.0f}-${tier.hap_1k_max:,.0f}"
                self._add_cell_line(cell, rate_range, COLORS['gap_text'], font_size=10)

            # HAP $2.5k column - white background
            cell = table.cell(row_idx, 4)
            self._set_cell_fill(cell, COLORS['white'])
            self._set_cell_text(cell, self._format_currency(tier.hap_25k_total),
                               data_text_colors[4], font_size=12, bold=True)
            if tier.hap_25k_min > 0 and tier.hap_25k_max > 0:
                rate_range = f"${tier.hap_25k_min:,.0f}-${tier.hap_25k_max:,.0f}"
                self._add_cell_line(cell, rate_range, COLORS['gap_text'], font_size=10)

        # Row 5: Total Monthly
        total_monthly_row = 5
        total_label = "Total Monthly*" if data.has_gap else "Total Monthly"

        cell = table.cell(total_monthly_row, 0)
        self._set_cell_fill(cell, COLORS['total_bg'])
        self._set_cell_text(cell, total_label, COLORS['total_text'],
                           font_size=12, bold=True, align=PP_ALIGN.LEFT)

        monthly_totals = [data.total_current, data.total_renewal, data.total_hap_1k, data.total_hap_25k]
        for col_idx, total_val in enumerate(monthly_totals, start=1):
            cell = table.cell(total_monthly_row, col_idx)
            self._set_cell_fill(cell, COLORS['white'])
            self._set_cell_text(cell, self._format_currency(total_val), data_text_colors[col_idx],
                               font_size=13, bold=True)

        # Row 6: Annual Total
        annual_row = 6
        cell = table.cell(annual_row, 0)
        self._set_cell_fill(cell, COLORS['total_bg'])
        self._set_cell_text(cell, "Annual Total", COLORS['total_text'],
                           font_size=12, bold=True, align=PP_ALIGN.LEFT)

        annual_totals = [data.annual_current, data.annual_renewal, data.annual_hap_1k, data.annual_hap_25k]
        for col_idx, annual_val in enumerate(annual_totals, start=1):
            cell = table.cell(annual_row, col_idx)
            self._set_cell_fill(cell, COLORS['white'])
            self._set_cell_text(cell, self._format_currency(annual_val), data_text_colors[col_idx],
                               font_size=12, bold=True)

        # Row 7: Savings vs Renewal
        savings_row = 7
        cell = table.cell(savings_row, 0)
        self._set_cell_fill(cell, COLORS['total_bg'])
        self._set_cell_text(cell, "Savings vs Renewal", COLORS['total_text'],
                           font_size=12, bold=True, align=PP_ALIGN.LEFT)

        # Current column: empty
        cell = table.cell(savings_row, 1)
        self._set_cell_fill(cell, COLORS['white'])

        # Renewal column: dash
        cell = table.cell(savings_row, 2)
        self._set_cell_fill(cell, COLORS['white'])
        self._set_cell_text(cell, "—", COLORS['gap_text'], font_size=12)

        # HAP $1k: savings amount + percentage (green)
        cell = table.cell(savings_row, 3)
        self._set_cell_fill(cell, COLORS['white'])
        self._set_cell_text(cell, self._format_currency(data.savings_hap_1k),
                           COLORS['hap_text'], font_size=12, bold=True)
        if data.savings_hap_1k_pct > 0:
            self._add_cell_line(cell, f"({data.savings_hap_1k_pct:.0f}%)", COLORS['hap_text'], font_size=14, bold=True)

        # HAP $2.5k: savings amount + percentage (green)
        cell = table.cell(savings_row, 4)
        self._set_cell_fill(cell, COLORS['white'])
        self._set_cell_text(cell, self._format_currency(data.savings_hap_25k),
                           COLORS['hap_text'], font_size=12, bold=True)
        if data.savings_hap_25k_pct > 0:
            self._add_cell_line(cell, f"({data.savings_hap_25k_pct:.0f}%)", COLORS['hap_text'], font_size=14, bold=True)

        # Add footnote if gap insurance exists
        if data.has_gap:
            footnote_top = table_top + table_height + Inches(0.15)
            footnote_box = slide.shapes.add_textbox(table_left, footnote_top,
                                                     table_width, Inches(0.3))
            footnote_tf = footnote_box.text_frame

            gap_breakdown = (f"* Includes {self._format_currency(data.total_gap_monthly)}/mo gap coverage "
                           f"(EE: {self._format_currency(data.gap_rate_ee)} | "
                           f"ES: {self._format_currency(data.gap_rate_es)} | "
                           f"EC: {self._format_currency(data.gap_rate_ec)} | "
                           f"F: {self._format_currency(data.gap_rate_f)})")

            footnote_tf.paragraphs[0].text = gap_breakdown
            footnote_tf.paragraphs[0].font.name = 'Poppins'
            footnote_tf.paragraphs[0].font.size = Pt(11)
            footnote_tf.paragraphs[0].font.color.rgb = COLORS['gap_text']

        # Add legend/explanation
        legend_top = Inches(6.8)
        legend_box = slide.shapes.add_textbox(table_left, legend_top, Inches(8), Inches(0.4))
        legend_tf = legend_box.text_frame
        legend_tf.paragraphs[0].text = "HAP = Health Access Plan with specified deductible | Rates shown are total monthly employer costs"
        legend_tf.paragraphs[0].font.name = 'Poppins'
        legend_tf.paragraphs[0].font.size = Pt(10)
        legend_tf.paragraphs[0].font.color.rgb = COLORS['gap_text']

        # Add decorative corner and edge images
        self._add_decoratives(slide)

    def _add_savings_hero(self, slide, data: CooperativeHealthData) -> None:
        """Add hero savings callout to bottom-right area"""
        # Use the larger savings percentage (HAP $2.5k typically)
        max_savings_pct = max(data.savings_hap_1k_pct, data.savings_hap_25k_pct)
        max_savings_amt = data.savings_hap_25k if data.savings_hap_25k_pct >= data.savings_hap_1k_pct else data.savings_hap_1k

        if max_savings_pct <= 0:
            return  # No savings to display

        # Position: bottom-right area, above the decorative edge
        hero_left = Inches(9.5)
        hero_top = Inches(5.2)
        hero_width = Inches(3.3)
        hero_height = Inches(1.4)

        # Add background shape (rounded rectangle effect via textbox with fill)
        from pptx.enum.shapes import MSO_SHAPE
        hero_shape = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            hero_left, hero_top, hero_width, hero_height
        )
        hero_shape.fill.solid()
        hero_shape.fill.fore_color.rgb = COLORS['hap_header']  # Light green background
        hero_shape.line.fill.background()  # No border

        # Add "SAVE UP TO" label
        label_box = slide.shapes.add_textbox(hero_left, hero_top + Inches(0.15), hero_width, Inches(0.3))
        label_tf = label_box.text_frame
        label_tf.paragraphs[0].text = "SAVE UP TO"
        label_tf.paragraphs[0].alignment = PP_ALIGN.CENTER
        label_tf.paragraphs[0].font.name = 'Poppins'
        label_tf.paragraphs[0].font.size = Pt(12)
        label_tf.paragraphs[0].font.bold = True
        label_tf.paragraphs[0].font.color.rgb = COLORS['hap_text']

        # Add big percentage number
        pct_box = slide.shapes.add_textbox(hero_left, hero_top + Inches(0.4), hero_width, Inches(0.7))
        pct_tf = pct_box.text_frame
        pct_tf.paragraphs[0].text = f"{max_savings_pct:.0f}%"
        pct_tf.paragraphs[0].alignment = PP_ALIGN.CENTER
        pct_tf.paragraphs[0].font.name = 'Poppins'
        pct_tf.paragraphs[0].font.size = Pt(48)
        pct_tf.paragraphs[0].font.bold = True
        pct_tf.paragraphs[0].font.color.rgb = COLORS['hap_text']

        # Add "annually" or savings amount subtitle
        subtitle_box = slide.shapes.add_textbox(hero_left, hero_top + Inches(1.05), hero_width, Inches(0.3))
        subtitle_tf = subtitle_box.text_frame
        subtitle_tf.paragraphs[0].text = f"({self._format_currency(max_savings_amt)}/year)"
        subtitle_tf.paragraphs[0].alignment = PP_ALIGN.CENTER
        subtitle_tf.paragraphs[0].font.name = 'Poppins'
        subtitle_tf.paragraphs[0].font.size = Pt(11)
        subtitle_tf.paragraphs[0].font.color.rgb = COLORS['hap_text']

    def _add_decoratives(self, slide) -> None:
        """Add decorative corner and edge images to the slide"""
        # Corner image - top left (175x175px → ~1.5" at 120 DPI scale)
        corner_size = Inches(1.5)
        if CORNER_IMAGE.exists():
            slide.shapes.add_picture(
                str(CORNER_IMAGE),
                left=Inches(0),
                top=Inches(0),
                width=corner_size,
                height=corner_size
            )

        # Edge image - bottom right (smaller for better balance)
        edge_width = Inches(3.2)
        edge_height = Inches(0.8)
        if EDGE_IMAGE.exists():
            slide.shapes.add_picture(
                str(EDGE_IMAGE),
                left=SLIDE_WIDTH - edge_width,
                top=SLIDE_HEIGHT - edge_height,
                width=edge_width,
                height=edge_height
            )

    def generate(self) -> BytesIO:
        """
        Generate PowerPoint and return as BytesIO buffer.

        Returns:
            BytesIO buffer containing the .pptx file
        """
        buffer = BytesIO()
        self.prs.save(buffer)
        buffer.seek(0)
        return buffer

    def save(self, output_path: str) -> None:
        """
        Save PowerPoint to file.

        Args:
            output_path: Path to save the file
        """
        self.prs.save(output_path)


def generate_cooperative_health_slide(data: CooperativeHealthData) -> BytesIO:
    """
    Convenience function to generate a Cooperative Health slide.

    Args:
        data: CooperativeHealthData with values to populate

    Returns:
        BytesIO buffer with generated PowerPoint
    """
    generator = CooperativeHealthSlideGenerator()
    generator.create_slide(data)
    return generator.generate()


def generate_cooperative_health_from_session(session_state) -> BytesIO:
    """
    Generate Cooperative Health slide from Streamlit session state.

    Args:
        session_state: st.session_state object

    Returns:
        BytesIO buffer with generated PowerPoint
    """
    data = CooperativeHealthData.from_session_state(session_state)
    return generate_cooperative_health_slide(data)


if __name__ == "__main__":
    # Test with sample data
    print("Testing Cooperative Health Slide Generator...")

    # Create sample data
    data = CooperativeHealthData(
        has_gap=True,
        total_gap_monthly=2464,
        gap_rate_ee=119,
        gap_rate_es=212,
        gap_rate_ec=187,
        gap_rate_f=245,
        tiers=[
            TierData(
                name="Employee Only",
                code="EE",
                current_total=4523,
                current_base=4047,
                current_gap=476,
                renewal_total=4978,
                renewal_base=4502,
                renewal_gap=476,
                hap_1k_total=3845,
                hap_1k_min=303,
                hap_1k_max=565,
                hap_25k_total=3412,
                hap_25k_min=268,
                hap_25k_max=498,
            ),
            TierData(
                name="Employee + Spouse",
                code="ES",
                current_total=3245,
                current_base=2821,
                current_gap=424,
                renewal_total=3570,
                renewal_base=3146,
                renewal_gap=424,
                hap_1k_total=2756,
                hap_1k_min=458,
                hap_1k_max=847,
                hap_25k_total=2445,
                hap_25k_min=405,
                hap_25k_max=748,
            ),
            TierData(
                name="Employee + Children",
                code="EC",
                current_total=2156,
                current_base=1782,
                current_gap=374,
                renewal_total=2372,
                renewal_base=1998,
                renewal_gap=374,
                hap_1k_total=1834,
                hap_1k_min=389,
                hap_1k_max=623,
                hap_25k_total=1627,
                hap_25k_min=344,
                hap_25k_max=551,
            ),
            TierData(
                name="Family",
                code="F",
                current_total=2308,
                current_base=1818,
                current_gap=490,
                renewal_total=2539,
                renewal_base=2049,
                renewal_gap=490,
                hap_1k_total=1839,
                hap_1k_min=534,
                hap_1k_max=892,
                hap_25k_total=1632,
                hap_25k_min=472,
                hap_25k_max=788,
            ),
        ],
        total_current=12232,
        total_renewal=13459,
        total_hap_1k=10274,
        total_hap_25k=9116,
        client_name="Sample Company",
    )

    # Generate slide
    generator = CooperativeHealthSlideGenerator()
    generator.create_slide(data)

    # Save to test file
    output_path = Path(__file__).parent / 'test_cooperative_health.pptx'
    generator.save(str(output_path))

    print(f"Generated test slide: {output_path}")
    print("Test complete!")
