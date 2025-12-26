"""
PDF Proposal Renderer for ICHRA Calculator

Renders GLOVE proposal slides as PDF using ReportLab.
Matches the GLOVE brand design from glove-ppld-template.pdf
"""

from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from io import BytesIO
from typing import Optional, List, Dict
from pathlib import Path
import math

from pptx_generator import ProposalData


# =============================================================================
# GLOVE Brand Colors (from template)
# =============================================================================
COLORS = {
    # Backgrounds
    'teal_bg': '#0D7377',           # Dark teal for full-page backgrounds
    'cream_bg': '#F5F0E8',          # Warm cream for light backgrounds
    'dark_card': '#2C3E50',         # Dark navy for cards
    'maroon_card': '#8B4513',       # Maroon/brown for cards

    # Text
    'dark_text': '#2C2C2C',         # Primary dark text
    'cream_text': '#F5F0E8',        # Light text on dark bg
    'teal_text': '#0D7377',         # Teal headings on cream
    'maroon_text': '#8B4513',       # Maroon accent text
    'light_teal': '#5DC1B9',        # Light teal accent
    'mint': '#7ECEC4',              # Mint green for highlights

    # Accents
    'orange': '#C4622D',            # Orange/rust for numbers
    'coral': '#E07B54',             # Coral for emphasis
    'gold': '#C9A227',              # Gold accent

    # Chart colors
    'chart_teal_1': '#0D7377',
    'chart_teal_2': '#159A9C',
    'chart_teal_3': '#5DC1B9',
    'chart_teal_4': '#7ECEC4',
    'chart_brown': '#8B4513',
    'chart_gray': '#6B7280',
}


class PDFProposalRenderer:
    """Render GLOVE proposal slides as PDF using ReportLab"""

    PAGE_WIDTH = 11 * inch
    PAGE_HEIGHT = 8.5 * inch

    def __init__(self, data: ProposalData):
        self.data = data
        self.buffer = BytesIO()
        self.c: Optional[canvas.Canvas] = None

    def generate(self) -> BytesIO:
        """Generate complete PDF proposal"""
        self.c = canvas.Canvas(self.buffer, pagesize=landscape(letter))

        # Draw each slide
        self._draw_slide_1_cover()
        self._draw_slide_2_market_analysis()
        self._draw_slide_3_fit_score()
        self._draw_slide_5_results()
        self._draw_slide_8_geographic()
        self._draw_slide_9_census()
        self._draw_slide_10_ichra_analysis()
        self._draw_slide_workflow()

        self.c.save()
        self.buffer.seek(0)
        return self.buffer

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _new_page(self, bg_color: str = 'cream_bg'):
        """Start a new page with background"""
        self.c.showPage()
        self._draw_background(bg_color)

    def _draw_background(self, bg_color: str = 'cream_bg'):
        """Draw page background"""
        self.c.setFillColor(HexColor(COLORS[bg_color]))
        self.c.rect(0, 0, self.PAGE_WIDTH, self.PAGE_HEIGHT, fill=1, stroke=0)

    def _draw_section_header(self, text: str, y: float, color: str = 'teal_text'):
        """Draw section header with lines: —— TEXT ——"""
        self.c.setStrokeColor(HexColor(COLORS[color]))
        self.c.setLineWidth(1.5)

        # Calculate text width
        self.c.setFont('Courier', 12)
        text_width = self.c.stringWidth(text, 'Courier', 12)

        center_x = self.PAGE_WIDTH / 2
        line_width = 50
        gap = 15

        # Left line
        self.c.line(center_x - text_width/2 - gap - line_width, y,
                   center_x - text_width/2 - gap, y)
        # Right line
        self.c.line(center_x + text_width/2 + gap, y,
                   center_x + text_width/2 + gap + line_width, y)

        # Text
        self.c.setFillColor(HexColor(COLORS[color]))
        self.c.drawCentredString(center_x, y - 4, text)

    def _draw_main_title(self, lines: List[str], y: float, colors_list: List[str] = None):
        """Draw large multi-line title"""
        if colors_list is None:
            colors_list = ['dark_text'] * len(lines)

        line_height = 55
        for i, (line, color) in enumerate(zip(lines, colors_list)):
            self.c.setFont('Helvetica-Bold', 42)
            self.c.setFillColor(HexColor(COLORS[color]))
            self.c.drawString(0.75 * inch, y - i * line_height, line)

    def _draw_rounded_rect(self, x, y, w, h, radius, fill_color, stroke=False):
        """Draw rounded rectangle"""
        self.c.setFillColor(HexColor(fill_color) if isinstance(fill_color, str) else fill_color)
        if stroke:
            self.c.setStrokeColor(HexColor(COLORS['dark_text']))
            self.c.setLineWidth(0.5)
        self.c.roundRect(x, y, w, h, radius, fill=1, stroke=1 if stroke else 0)

    def _draw_stat_large(self, x, y, number: str, label: str, number_color: str = 'teal_text', suffix: str = ''):
        """Draw large statistic with label below"""
        # Number
        self.c.setFont('Helvetica-Bold', 72)
        self.c.setFillColor(HexColor(COLORS[number_color]))
        self.c.drawString(x, y, number)

        # Suffix (like % or x)
        if suffix:
            num_width = self.c.stringWidth(number, 'Helvetica-Bold', 72)
            self.c.setFont('Helvetica-Bold', 36)
            self.c.drawString(x + num_width, y + 20, suffix)

    def _draw_card(self, x, y, w, h, bg_color: str, content_func=None):
        """Draw a card with optional content"""
        self._draw_rounded_rect(x, y, w, h, 15, COLORS[bg_color])
        if content_func:
            content_func(x, y, w, h)

    def _draw_donut_chart(self, cx, cy, outer_r, inner_r, segments: List[Dict], center_text: str = None):
        """Draw a donut/pie chart"""
        start_angle = 90  # Start from top

        for seg in segments:
            extent = seg['pct'] / 100 * 360
            self.c.setFillColor(HexColor(seg['color']))

            # Draw pie slice
            path = self.c.beginPath()
            path.moveTo(cx, cy)
            path.arcTo(cx - outer_r, cy - outer_r, cx + outer_r, cy + outer_r,
                      start_angle, extent)
            path.close()
            self.c.drawPath(path, fill=1, stroke=0)

            start_angle += extent

        # Inner circle (creates donut hole)
        self.c.setFillColor(HexColor(COLORS['cream_bg']))
        self.c.circle(cx, cy, inner_r, fill=1, stroke=0)

        # Center text
        if center_text:
            self.c.setFont('Helvetica-Bold', 64)
            self.c.setFillColor(HexColor(COLORS['orange']))
            self.c.drawCentredString(cx, cy - 20, center_text)

    # =========================================================================
    # Slide 1: Cover
    # =========================================================================

    def _draw_slide_1_cover(self):
        """Cover slide - teal background with client name and stats"""
        self._draw_background('teal_bg')

        # Client name (large, cream)
        self.c.setFont('Helvetica-Bold', 72)
        self.c.setFillColor(HexColor(COLORS['cream_text']))
        self.c.drawString(0.75 * inch, self.PAGE_HEIGHT - 1.5 * inch,
                         self.data.client_name.upper())

        # "is at a" (cream)
        self.c.setFont('Helvetica-Bold', 36)
        self.c.drawString(0.75 * inch, self.PAGE_HEIGHT - 2.2 * inch, "is at a")

        # "FORK" (light teal, italic)
        self.c.setFont('Helvetica-BoldOblique', 72)
        self.c.setFillColor(HexColor(COLORS['light_teal']))
        self.c.drawString(0.75 * inch, self.PAGE_HEIGHT - 3.2 * inch, "FORK")

        # "in the road" (cream)
        self.c.setFont('Helvetica-Bold', 36)
        self.c.setFillColor(HexColor(COLORS['cream_text']))
        self.c.drawString(0.75 * inch, self.PAGE_HEIGHT - 3.9 * inch, "in the road")

        # Right side stats
        right_x = 7 * inch

        # Renewal percentage
        if self.data.renewal_percentage > 0:
            self.c.setFont('Helvetica-Bold', 96)
            self.c.setFillColor(HexColor(COLORS['light_teal']))
            self.c.drawString(right_x, self.PAGE_HEIGHT - 2 * inch,
                             f"{self.data.renewal_percentage:.0f}")
            self.c.setFont('Helvetica-Bold', 48)
            self.c.drawString(right_x + 130, self.PAGE_HEIGHT - 1.7 * inch, "%")

            # Description
            self.c.setFont('Helvetica', 16)
            self.c.setFillColor(HexColor(COLORS['cream_text']))
            self.c.drawString(right_x, self.PAGE_HEIGHT - 2.4 * inch,
                             "renewal isn't a budget")
            self.c.drawString(right_x, self.PAGE_HEIGHT - 2.65 * inch,
                             "problem. It's a shakedown.")

        # Total renewal cost
        if self.data.total_renewal_cost > 0:
            cost_display = f"${self.data.total_renewal_cost/1_000_000:.1f}" if self.data.total_renewal_cost >= 1_000_000 else f"${self.data.total_renewal_cost/1000:.0f}K"
            self.c.setFont('Helvetica-Bold', 72)
            self.c.setFillColor(HexColor(COLORS['light_teal']))
            self.c.drawString(right_x, self.PAGE_HEIGHT - 4 * inch, cost_display)

            if self.data.total_renewal_cost >= 1_000_000:
                self.c.setFont('Helvetica-Bold', 36)
                self.c.drawString(right_x + 160, self.PAGE_HEIGHT - 3.8 * inch, "M")

            self.c.setFont('Helvetica', 16)
            self.c.setFillColor(HexColor(COLORS['cream_text']))
            self.c.drawString(right_x, self.PAGE_HEIGHT - 4.4 * inch, "cost of staying put.")

        # Question at bottom
        self.c.setFont('Courier-Bold', 18)
        self.c.setFillColor(HexColor(COLORS['mint']))
        self.c.drawString(right_x, 1.2 * inch, f"CAN {self.data.client_name.upper()}")
        self.c.drawString(right_x, 0.9 * inch, "SURVIVE THAT?")

    # =========================================================================
    # Slide 2: Market Analysis
    # =========================================================================

    def _draw_slide_2_market_analysis(self):
        """Market Analysis slide"""
        self._new_page('cream_bg')

        # Section header
        self._draw_section_header("MARKET ANALYSIS", self.PAGE_HEIGHT - 0.6 * inch)

        # Main title
        self.c.setFont('Helvetica-Bold', 36)
        self.c.setFillColor(HexColor(COLORS['dark_text']))
        title = "THE MARKET IS CHANGING"
        self.c.drawCentredString(self.PAGE_WIDTH / 2, self.PAGE_HEIGHT - 1.2 * inch, title)

        # Left side - stats
        left_x = 0.75 * inch

        # Large stat - employees facing increases
        self.c.setFont('Helvetica-Bold', 96)
        self.c.setFillColor(HexColor(COLORS['teal_text']))
        self.c.drawString(left_x, self.PAGE_HEIGHT - 3 * inch, "37")
        self.c.setFont('Helvetica-Bold', 48)
        self.c.drawString(left_x + 130, self.PAGE_HEIGHT - 2.7 * inch, "%")

        self.c.setFont('Helvetica', 18)
        self.c.setFillColor(HexColor(COLORS['teal_text']))
        self.c.drawString(left_x + 180, self.PAGE_HEIGHT - 2.6 * inch, "Of employers face")
        self.c.drawString(left_x + 180, self.PAGE_HEIGHT - 2.9 * inch, "11-15% increases")

        # Employee count box
        box_y = self.PAGE_HEIGHT - 4.5 * inch
        self._draw_rounded_rect(left_x, box_y, 3 * inch, 0.8 * inch, 5, '#FFFFFF', stroke=True)
        self.c.setFont('Helvetica-Bold', 28)
        self.c.setFillColor(HexColor(COLORS['dark_text']))
        self.c.drawString(left_x + 20, box_y + 25, str(self.data.employee_count))
        self.c.setFont('Courier', 14)
        self.c.setFillColor(HexColor(COLORS['teal_text']))
        self.c.drawString(left_x + 100, box_y + 28, "Total employees")

        # Avg premium box
        box_y2 = box_y - 1 * inch
        self._draw_rounded_rect(left_x, box_y2, 3 * inch, 0.8 * inch, 5, '#FFFFFF', stroke=True)
        self.c.setFont('Helvetica-Bold', 28)
        self.c.setFillColor(HexColor(COLORS['dark_text']))
        self.c.drawString(left_x + 20, box_y2 + 25, f"${self.data.avg_monthly_premium:,.0f}")
        self.c.setFont('Courier', 14)
        self.c.setFillColor(HexColor(COLORS['teal_text']))
        self.c.drawString(left_x + 120, box_y2 + 28, "Avg. monthly premium")

        # Bottom quote
        self.c.setFont('Helvetica-Bold', 20)
        self.c.setFillColor(HexColor(COLORS['maroon_text']))
        self.c.drawString(left_x, 1.2 * inch, "YOUR RENEWAL NOTICE SHOULDN'T")
        self.c.drawString(left_x, 0.85 * inch, "FEEL LIKE A RANSOM NOTE.")

        # Right side - renewal distribution chart
        chart_x = 6.5 * inch
        chart_y = self.PAGE_HEIGHT - 2 * inch
        chart_w = 4 * inch
        chart_h = 4.5 * inch

        # Chart background
        self._draw_rounded_rect(chart_x, chart_y - chart_h, chart_w, chart_h, 15, COLORS['dark_card'])

        # Chart title
        self.c.setFont('Helvetica-Bold', 12)
        self.c.setFillColor(HexColor(COLORS['cream_text']))
        self.c.drawString(chart_x + 20, chart_y - 30, "2025 RENEWAL INCREASES FOR LARGE EMPLOYERS")

        # Bar chart data
        bars = [
            ('1%-4%', 23, COLORS['chart_gray']),
            ('5%-10%', 37, COLORS['chart_teal_1']),
            ('11%-15%', 24, COLORS['chart_teal_3']),
            ('16%-20%', 10, COLORS['chart_gray']),
            ('20%+', 4, COLORS['chart_gray']),
        ]

        bar_start_y = chart_y - 80
        bar_height = 35
        bar_spacing = 50
        max_bar_width = 2.5 * inch

        for i, (label, pct, color) in enumerate(bars):
            y = bar_start_y - i * bar_spacing

            # Label
            self.c.setFont('Helvetica', 12)
            self.c.setFillColor(HexColor(COLORS['cream_text']))
            self.c.drawString(chart_x + 20, y + 10, label)

            # Bar
            bar_width = (pct / 40) * max_bar_width
            self._draw_rounded_rect(chart_x + 80, y, bar_width, bar_height, 5, color)

            # Percentage
            self.c.setFont('Helvetica-Bold', 12)
            self.c.drawString(chart_x + 85 + bar_width + 10, y + 10, f"{pct}%")

        # Footer
        self.c.setFont('Helvetica', 10)
        self.c.setFillColor(HexColor(COLORS['cream_text']))
        self.c.drawString(chart_x + 20, chart_y - chart_h + 20, "PERCENTAGE OF EMPLOYERS BY INCREASE RANGE")

    # =========================================================================
    # Slide 3: GIFT (Fit Score)
    # =========================================================================

    def _draw_slide_3_fit_score(self):
        """GIFT - GLOVE ICHRA Fit Total"""
        self._new_page('cream_bg')

        # Section header
        self._draw_section_header("GIFT", self.PAGE_HEIGHT - 0.6 * inch)

        # Main title
        self.c.setFont('Helvetica-Bold', 42)
        self.c.setFillColor(HexColor(COLORS['teal_text']))
        self.c.drawCentredString(self.PAGE_WIDTH / 2, self.PAGE_HEIGHT - 1.3 * inch,
                                "YOUR GLOVE ICHRA FIT TOTAL")

        # Center donut chart
        cx = self.PAGE_WIDTH / 2
        cy = self.PAGE_HEIGHT / 2 - 0.3 * inch
        outer_r = 1.5 * inch
        inner_r = 1.0 * inch

        # Category segments (6 equal segments for now, could be weighted)
        segments = [
            {'pct': 16.67, 'color': COLORS['chart_teal_1']},
            {'pct': 16.67, 'color': COLORS['chart_teal_2']},
            {'pct': 16.67, 'color': COLORS['chart_teal_3']},
            {'pct': 16.67, 'color': COLORS['chart_teal_4']},
            {'pct': 16.67, 'color': COLORS['chart_teal_1']},
            {'pct': 16.67, 'color': COLORS['chart_teal_2']},
        ]

        self._draw_donut_chart(cx, cy, outer_r, inner_r, segments, str(self.data.fit_score))

        # Category labels around the chart
        categories = [
            {'name': 'Employee Experience', 'desc': 'Exchange usability, broker support,\nenrollment friction', 'x': 1.5 * inch, 'y': self.PAGE_HEIGHT - 2.2 * inch},
            {'name': 'Geographic Complexity', 'desc': 'Multi-state footprint, rating area issues,\nregulatory impact', 'x': 8 * inch, 'y': self.PAGE_HEIGHT - 2.2 * inch},
            {'name': 'Cost Advantage', 'desc': 'Individual versus group benchmark,\npotential savings.', 'x': 1.5 * inch, 'y': cy - 0.3 * inch},
            {'name': 'Workforce Fit', 'desc': 'Age/income distribution, subsidy eligibility,\nfamily status mix.', 'x': 8 * inch, 'y': cy - 0.3 * inch},
            {'name': 'Market Readiness', 'desc': 'Carrier count, plan options, metal tier\ncoverage for your workforce.', 'x': 3 * inch, 'y': 1.5 * inch},
            {'name': 'Admin Readiness', 'desc': 'Payroll integrations, Individual\nmarketplace support', 'x': 7 * inch, 'y': 1.5 * inch},
        ]

        for cat in categories:
            # Title
            self.c.setFont('Helvetica-Bold', 14)
            self.c.setFillColor(HexColor(COLORS['teal_text']))
            self.c.drawString(cat['x'], cat['y'], cat['name'])

            # Description
            self.c.setFont('Helvetica', 10)
            self.c.setFillColor(HexColor(COLORS['maroon_text']))
            for i, line in enumerate(cat['desc'].split('\n')):
                self.c.drawString(cat['x'], cat['y'] - 15 - i * 12, line)

    # =========================================================================
    # Slide 5: The Results (Cost Burden)
    # =========================================================================

    def _draw_slide_5_results(self):
        """The Results - healthcare burden stats"""
        self._new_page('cream_bg')

        # Section header
        self._draw_section_header("THE RESULTS", self.PAGE_HEIGHT - 0.6 * inch, 'teal_text')

        # Main title
        self.c.setFont('Helvetica-Bold', 42)
        self.c.setFillColor(HexColor(COLORS['dark_text']))
        self.c.drawString(0.75 * inch, self.PAGE_HEIGHT - 1.5 * inch, "WE TRIED TO TREATING")
        self.c.setFillColor(HexColor(COLORS['light_teal']))
        self.c.drawString(0.75 * inch, self.PAGE_HEIGHT - 2.1 * inch, "THE SYMPTOMS.")

        # Large stats
        stats = [
            ('69', '%', 'EMPLOYER CONTRIBUTION INCREASE', 'From 2015 to 2026, outpacing wage growth by nearly 10%', 'teal_text'),
            ('3', 'X', 'DEDUCTIBLES vs. WAGES GAP', 'Deductible tripled since 2012. Wage? Up 66%.', 'teal_text'),
            ('30', '%', '30 CENTS FOR EVERY DOLLAR', 'For every dollar spent is wasted on low-value care.', 'light_teal'),
        ]

        stat_y = self.PAGE_HEIGHT - 3.5 * inch
        for i, (num, suffix, title, desc, color) in enumerate(stats):
            y = stat_y - i * 1.5 * inch

            # Large number
            self.c.setFont('Helvetica-Bold', 72)
            self.c.setFillColor(HexColor(COLORS[color]))
            self.c.drawString(0.75 * inch, y, num)

            # Suffix
            num_width = self.c.stringWidth(num, 'Helvetica-Bold', 72)
            self.c.setFont('Helvetica-Bold', 36)
            self.c.drawString(0.75 * inch + num_width, y + 20, suffix)

            # Title and description
            self.c.setFont('Helvetica-Bold', 14)
            self.c.setFillColor(HexColor(COLORS['dark_text']))
            self.c.drawString(3 * inch, y + 30, title)

            self.c.setFont('Helvetica', 12)
            self.c.drawString(3 * inch, y + 10, desc)

        # Healthcare burden card (right side)
        card_x = 7.5 * inch
        card_y = self.PAGE_HEIGHT - 5 * inch
        card_w = 3 * inch
        card_h = 2.5 * inch

        # White outer card
        self._draw_rounded_rect(card_x, card_y, card_w, card_h, 15, '#FFFFFF')

        # Label
        self.c.setFont('Courier-Bold', 12)
        self.c.setFillColor(HexColor(COLORS['maroon_text']))
        self.c.drawCentredString(card_x + card_w/2, card_y + card_h - 30,
                                f"FOR {self.data.employee_count} EMPLOYEES")

        # Brown inner card
        inner_y = card_y + 20
        inner_h = card_h - 80
        self._draw_rounded_rect(card_x + 20, inner_y, card_w - 40, inner_h, 10, COLORS['maroon_card'])

        # Amount
        burden_display = f"${self.data.additional_healthcare_burden/1000:,.0f}K" if self.data.additional_healthcare_burden > 0 else "$0"
        self.c.setFont('Helvetica-Bold', 36)
        self.c.setFillColor(HexColor(COLORS['cream_text']))
        self.c.drawCentredString(card_x + card_w/2, inner_y + inner_h/2, burden_display)

        # Description
        self.c.setFont('Helvetica', 11)
        self.c.drawCentredString(card_x + card_w/2, inner_y + 20, "additional healthcare burden per year")

    # =========================================================================
    # Slide 8: Geographic Distribution
    # =========================================================================

    def _draw_slide_8_geographic(self):
        """Understanding Your Workforce - Geographic"""
        self._new_page('cream_bg')

        # Section header
        self._draw_section_header("Cost Analysis", self.PAGE_HEIGHT - 0.6 * inch)

        # Main title
        self.c.setFont('Helvetica-Bold', 42)
        self.c.setFillColor(HexColor(COLORS['dark_text']))
        self.c.drawString(0.75 * inch, self.PAGE_HEIGHT - 1.5 * inch, "UNDERSTANDING YOUR")
        self.c.setFillColor(HexColor(COLORS['teal_text']))
        self.c.drawString(0.75 * inch, self.PAGE_HEIGHT - 2.1 * inch, "WORKFORCE")

        # Summary card (employees/states)
        summary_x = 0.75 * inch
        summary_y = self.PAGE_HEIGHT - 3.5 * inch
        summary_w = 4 * inch
        summary_h = 1 * inch

        self._draw_rounded_rect(summary_x, summary_y, summary_w, summary_h, 10, COLORS['maroon_card'])

        # Employees
        self.c.setFont('Helvetica', 10)
        self.c.setFillColor(HexColor(COLORS['cream_text']))
        self.c.drawString(summary_x + 20, summary_y + summary_h - 20, "EMPLOYEES")
        self.c.setFont('Helvetica-Bold', 42)
        self.c.drawString(summary_x + 20, summary_y + 15, str(self.data.employee_count))

        # States
        self.c.setFont('Helvetica', 10)
        self.c.drawString(summary_x + summary_w/2 + 20, summary_y + summary_h - 20, "STATES")
        self.c.setFont('Helvetica-Bold', 42)
        self.c.drawString(summary_x + summary_w/2 + 20, summary_y + 15, str(self.data.total_states))

        # Top 5 states card
        states_x = 0.75 * inch
        states_y = 0.75 * inch
        states_w = 4 * inch
        states_h = 3.5 * inch

        self._draw_rounded_rect(states_x, states_y, states_w, states_h, 15, '#FFFFFF')

        # Header
        self.c.setFont('Courier-Bold', 12)
        self.c.setFillColor(HexColor(COLORS['teal_text']))
        self.c.drawString(states_x + 20, states_y + states_h - 30, "TOP 5 STATES")

        # State bars
        if self.data.top_states:
            bar_y = states_y + states_h - 70
            bar_spacing = 50
            max_count = max(s['count'] for s in self.data.top_states[:5]) if self.data.top_states else 1

            for i, state_data in enumerate(self.data.top_states[:5]):
                y = bar_y - i * bar_spacing
                bar_width = (state_data['count'] / max_count) * (states_w - 60)

                # Bar
                self._draw_rounded_rect(states_x + 20, y, bar_width, 35, 5, COLORS['maroon_card'])

                # Count and state name
                self.c.setFont('Helvetica-Bold', 18)
                self.c.setFillColor(HexColor(COLORS['cream_text']))
                self.c.drawString(states_x + 30, y + 10, str(state_data['count']))

                self.c.setFont('Courier', 12)
                self.c.drawString(states_x + 80, y + 12, state_data['state'].upper())

        # Geographic distribution title (right side)
        self.c.setFont('Helvetica-Bold', 18)
        self.c.setFillColor(HexColor(COLORS['dark_text']))
        self.c.drawString(6 * inch, self.PAGE_HEIGHT - 2.5 * inch, "GEOGRAPHIC DISTRIBUTION")

        # Placeholder for map
        self.c.setFont('Helvetica', 12)
        self.c.setFillColor(HexColor(COLORS['chart_gray']))
        self.c.drawString(6 * inch, self.PAGE_HEIGHT - 3 * inch, "[Map visualization would appear here]")

        # Bottom insight
        insight_y = 1 * inch
        self._draw_rounded_rect(5.5 * inch, insight_y, 5 * inch, 0.8 * inch, 10, COLORS['light_teal'])

        if self.data.top_states:
            top_state = self.data.top_states[0]
            top_pct = (top_state['count'] / self.data.employee_count * 100) if self.data.employee_count > 0 else 0

            self.c.setFont('Helvetica-Bold', 11)
            self.c.setFillColor(HexColor(COLORS['dark_text']))
            insight_text = f"{top_pct:.0f}% of your workforce is in {top_state['state']}, but you've got people scattered across {self.data.total_states} states."
            self.c.drawString(5.7 * inch, insight_y + 45, insight_text[:60])
            self.c.drawString(5.7 * inch, insight_y + 25, f"That's {self.data.total_states} different insurance markets, {self.data.total_states} different cost structures.")

    # =========================================================================
    # Slide 9: Census Data - Population Overview
    # =========================================================================

    def _draw_slide_9_census(self):
        """Census Data - Population Overview"""
        self._new_page('cream_bg')

        # Section header
        self._draw_section_header("CENSUS DATA", self.PAGE_HEIGHT - 0.6 * inch)

        # Main title
        self.c.setFont('Helvetica-Bold', 42)
        self.c.setFillColor(HexColor(COLORS['dark_text']))
        self.c.drawCentredString(self.PAGE_WIDTH / 2, self.PAGE_HEIGHT - 1.3 * inch, "POPULATION OVERVIEW")

        # Left column - Covered Lives card
        card1_x = 0.5 * inch
        card1_y = self.PAGE_HEIGHT - 4.5 * inch
        card1_w = 2.5 * inch
        card1_h = 2.5 * inch

        self._draw_rounded_rect(card1_x, card1_y, card1_w, card1_h, 15, '#FFFFFF')

        self.c.setFont('Courier-Bold', 12)
        self.c.setFillColor(HexColor(COLORS['teal_text']))
        self.c.drawString(card1_x + 20, card1_y + card1_h - 30, "COVERED LIVES")

        self.c.setFont('Helvetica-Bold', 64)
        self.c.setFillColor(HexColor(COLORS['teal_text']))
        self.c.drawString(card1_x + 20, card1_y + card1_h - 100, str(self.data.covered_lives))

        # Employees/Dependents breakdown
        self.c.setFont('Helvetica', 11)
        self.c.setFillColor(HexColor(COLORS['maroon_text']))
        self.c.drawString(card1_x + 20, card1_y + 50, "EMPLOYEES")
        self.c.drawString(card1_x + card1_w/2, card1_y + 50, "DEPENDENTS")

        self.c.setFont('Helvetica-Bold', 24)
        self.c.setFillColor(HexColor(COLORS['teal_text']))
        self.c.drawString(card1_x + 20, card1_y + 20, str(self.data.total_employees))
        self.c.drawString(card1_x + card1_w/2, card1_y + 20, str(self.data.total_dependents))

        # Demographics card
        demo_y = 1 * inch
        self._draw_rounded_rect(card1_x, demo_y, card1_w, 1.5 * inch, 10, '#FFFFFF')

        self.c.setFont('Courier-Bold', 10)
        self.c.setFillColor(HexColor(COLORS['dark_text']))
        self.c.drawCentredString(card1_x + card1_w/2, demo_y + 1.2 * inch, "DEMOGRAPHICS")

        # Age stats
        demo_items = [
            ('AVG AGE', f"{self.data.avg_employee_age:.0f}"),
            ('AGE RANGE', f"{self.data.age_range_min}-{self.data.age_range_max}"),
        ]

        for i, (label, value) in enumerate(demo_items):
            x = card1_x + 20 + i * (card1_w/2 - 10)
            self.c.setFont('Helvetica', 9)
            self.c.setFillColor(HexColor(COLORS['dark_text']))
            self.c.drawString(x, demo_y + 0.8 * inch, label)
            self.c.setFont('Helvetica-Bold', 24)
            self.c.drawString(x, demo_y + 0.3 * inch, value)

        # Middle - Employee coverage type donut
        donut_cx = 4.5 * inch
        donut_cy = self.PAGE_HEIGHT - 4 * inch

        self.c.setFont('Courier-Bold', 12)
        self.c.setFillColor(HexColor(COLORS['dark_text']))
        self.c.drawCentredString(donut_cx, self.PAGE_HEIGHT - 2.3 * inch, "EMPLOYEE COVERAGE TYPE")

        # Get percentages
        total = self.data.total_employees or 1
        ee_pct = (self.data.family_status_breakdown.get('EE', 0) / total) * 100
        es_pct = (self.data.family_status_breakdown.get('ES', 0) / total) * 100
        ec_pct = (self.data.family_status_breakdown.get('EC', 0) / total) * 100
        f_pct = (self.data.family_status_breakdown.get('F', 0) / total) * 100

        segments = [
            {'pct': ee_pct, 'color': COLORS['chart_teal_1']},
            {'pct': es_pct, 'color': COLORS['chart_gray']},
            {'pct': ec_pct, 'color': COLORS['chart_brown']},
            {'pct': f_pct, 'color': COLORS['chart_teal_3']},
        ]

        self._draw_donut_chart(donut_cx, donut_cy, 1 * inch, 0.6 * inch, segments)

        # Legend
        legend_items = [
            ('EMPLOYEE ONLY', f"{ee_pct:.1f}%", COLORS['chart_teal_1']),
            ('FAMILY', f"{f_pct:.1f}%", COLORS['chart_teal_3']),
            ('EMPLOYEE + SPOUSE', f"{es_pct:.1f}%", COLORS['chart_gray']),
        ]

        legend_y = donut_cy - 1.2 * inch
        for i, (label, pct, color) in enumerate(legend_items):
            y = legend_y - i * 25

            # Color swatch
            self._draw_rounded_rect(donut_cx + 0.3 * inch, y, 15, 15, 3, color)

            # Label
            self.c.setFont('Courier', 9)
            self.c.setFillColor(HexColor(COLORS['dark_text']))
            self.c.drawString(donut_cx + 0.6 * inch, y + 3, label)

            self.c.setFont('Helvetica-Bold', 10)
            self.c.setFillColor(HexColor(COLORS['teal_text']))
            self.c.drawString(donut_cx + 1.8 * inch, y + 3, pct)

        # Right side - Cost cards
        cost_x = 7.5 * inch
        cost_y = self.PAGE_HEIGHT - 3 * inch

        # Current EE
        self._draw_rounded_rect(cost_x, cost_y, 1.5 * inch, 1.5 * inch, 10, COLORS['maroon_card'])
        self.c.setFont('Helvetica', 9)
        self.c.setFillColor(HexColor(COLORS['cream_text']))
        self.c.drawString(cost_x + 10, cost_y + 1.2 * inch, "CURRENT EE")
        self.c.setFont('Helvetica-Bold', 14)
        self.c.drawString(cost_x + 10, cost_y + 0.85 * inch, f"${self.data.current_ee_annual:,.0f}")
        self.c.setFont('Helvetica', 9)
        self.c.drawString(cost_x + 10, cost_y + 0.65 * inch, "Annual")

        # Current ER
        self._draw_rounded_rect(cost_x + 1.6 * inch, cost_y, 1.5 * inch, 1.5 * inch, 10, COLORS['teal_bg'])
        self.c.setFont('Helvetica', 9)
        self.c.setFillColor(HexColor(COLORS['cream_text']))
        self.c.drawString(cost_x + 1.7 * inch, cost_y + 1.2 * inch, "CURRENT ER")
        self.c.setFont('Helvetica-Bold', 14)
        self.c.drawString(cost_x + 1.7 * inch, cost_y + 0.85 * inch, f"${self.data.current_er_annual:,.0f}")
        self.c.setFont('Helvetica', 9)
        self.c.drawString(cost_x + 1.7 * inch, cost_y + 0.65 * inch, "Annual")

        # Total
        self._draw_rounded_rect(cost_x + 3.2 * inch, cost_y, 1.5 * inch, 1.5 * inch, 10, COLORS['dark_card'])
        self.c.setFont('Helvetica', 9)
        self.c.setFillColor(HexColor(COLORS['cream_text']))
        self.c.drawString(cost_x + 3.3 * inch, cost_y + 1.2 * inch, "TOTAL")
        self.c.setFont('Helvetica-Bold', 14)
        self.c.drawString(cost_x + 3.3 * inch, cost_y + 0.85 * inch, f"${self.data.current_total_annual:,.0f}")
        self.c.setFont('Helvetica', 9)
        self.c.drawString(cost_x + 3.3 * inch, cost_y + 0.65 * inch, f"${self.data.current_total_monthly:,.0f}/mo")

    # =========================================================================
    # Slide 10: ICHRA Analysis
    # =========================================================================

    def _draw_slide_10_ichra_analysis(self):
        """ICHRA Analysis - Allowance levels"""
        self._new_page('cream_bg')

        # Section header
        self._draw_section_header("ICHRA ANALYSIS", self.PAGE_HEIGHT - 0.6 * inch)

        # Main title
        self.c.setFont('Helvetica-Bold', 32)
        self.c.setFillColor(HexColor(COLORS['dark_text']))
        self.c.drawString(0.5 * inch, self.PAGE_HEIGHT - 1.3 * inch, f"WHAT {self.data.client_name.upper()} PAYS AT DIFFERENT")
        self.c.setFillColor(HexColor(COLORS['teal_text']))
        self.c.drawString(0.5 * inch + self.c.stringWidth(f"WHAT {self.data.client_name.upper()} PAYS AT DIFFERENT", 'Helvetica-Bold', 32) + 10,
                         self.PAGE_HEIGHT - 1.3 * inch, "ALLOWANCE LEVELS")

        # Three allowance cards
        card_width = 3.2 * inch
        card_height = 2.8 * inch
        card_y = self.PAGE_HEIGHT - 4.5 * inch
        card_spacing = 0.2 * inch

        # Calculate savings at different levels (simplified)
        proposed_monthly = self.data.proposed_er_monthly
        renewal_annual = self.data.total_renewal_cost

        allowances = [
            {'amount': 450, 'color': COLORS['dark_card'], 'highlight': False},
            {'amount': 600, 'color': COLORS['dark_card'], 'highlight': True},
            {'amount': 750, 'color': COLORS['dark_card'], 'highlight': False},
        ]

        for i, allowance in enumerate(allowances):
            x = 0.5 * inch + i * (card_width + card_spacing)

            # Card background
            self._draw_rounded_rect(x, card_y, card_width, card_height, 15, allowance['color'])

            # Allowance amount
            self.c.setFont('Helvetica-Bold', 48)
            self.c.setFillColor(HexColor(COLORS['cream_text']))
            self.c.drawString(x + 20, card_y + card_height - 60, f"${allowance['amount']}")

            # Sweet spot badge
            if allowance['highlight']:
                badge_x = x + 140
                badge_y = card_y + card_height - 55
                self._draw_rounded_rect(badge_x, badge_y, 100, 30, 5, COLORS['teal_text'])
                self.c.setFont('Helvetica-Bold', 11)
                self.c.setFillColor(HexColor(COLORS['dark_text']))
                self.c.drawCentredString(badge_x + 50, badge_y + 10, "SWEET SPOT")

            # Annual cost
            annual_cost = allowance['amount'] * self.data.employee_count * 12
            self.c.setFont('Helvetica', 10)
            self.c.setFillColor(HexColor(COLORS['cream_text']))
            self.c.drawString(x + 20, card_y + card_height - 90, "ANNUAL COST")

            self.c.setFont('Helvetica-Bold', 20)
            self.c.setFillColor(HexColor(COLORS['coral'] if 'coral' in COLORS else 'light_teal'))
            self.c.drawString(x + 20, card_y + card_height - 115, f"${annual_cost:,.0f}")

            # vs. renewal savings
            if renewal_annual > 0:
                savings = renewal_annual - annual_cost
                savings_pct = (savings / renewal_annual) * 100 if renewal_annual > 0 else 0

                self.c.setFont('Helvetica', 10)
                self.c.setFillColor(HexColor(COLORS['teal_text']))
                self.c.drawString(x + 20, card_y + card_height - 150, "vs.")

                self.c.setFont('Helvetica', 10)
                self.c.setFillColor(HexColor(COLORS['cream_text']))
                self.c.drawString(x + 20, card_y + card_height - 170, "RENEWAL SAVINGS")

                self.c.setFont('Helvetica-Bold', 16)
                self.c.setFillColor(HexColor(COLORS['coral'] if 'coral' in COLORS else 'light_teal'))
                self.c.drawString(x + 20, card_y + card_height - 195, f"${savings:,.0f}")

                # Percentage
                self.c.setFont('Helvetica-Bold', 28)
                self.c.setFillColor(HexColor(COLORS['light_teal']))
                self.c.drawString(x + 20, card_y + 30, f"{savings_pct:.0f}%")

        # Bottom row - Cost comparison cards
        bottom_y = 0.75 * inch
        bottom_h = 1.8 * inch

        # Cost Impact Analysis
        self._draw_rounded_rect(0.5 * inch, bottom_y, 3 * inch, bottom_h, 15, '#FFFFFF')
        self.c.setFont('Helvetica-Bold', 12)
        self.c.setFillColor(HexColor(COLORS['teal_text']))
        self.c.drawString(0.7 * inch, bottom_y + bottom_h - 25, "Cost Impact Analysis")

        self.c.setFont('Helvetica', 9)
        self.c.setFillColor(HexColor(COLORS['dark_text']))
        self.c.drawString(0.7 * inch, bottom_y + bottom_h - 50, "PROPOSED ER CHARGE (ANNUAL)")

        self.c.setFont('Helvetica-Bold', 18)
        self.c.setFillColor(HexColor(COLORS['coral'] if 'coral' in COLORS else 'teal_text'))
        savings_display = f"-${abs(self.data.annual_savings):,.2f}" if self.data.annual_savings > 0 else f"${abs(self.data.annual_savings):,.2f}"
        self.c.drawString(0.7 * inch, bottom_y + bottom_h - 75, savings_display)

        # Current Group Plan
        self._draw_rounded_rect(3.7 * inch, bottom_y, 3.2 * inch, bottom_h, 15, '#FFFFFF')
        self.c.setFont('Helvetica-Bold', 12)
        self.c.setFillColor(HexColor(COLORS['dark_text']))
        self.c.drawString(3.9 * inch, bottom_y + bottom_h - 25, "$ Current Group Plan")

        self.c.setFont('Helvetica', 9)
        self.c.setFillColor(HexColor(COLORS['dark_text']))
        self.c.drawString(3.9 * inch, bottom_y + bottom_h - 50, "CURRENT ER MONTHLY")
        self.c.setFont('Helvetica-Bold', 14)
        self.c.drawString(3.9 * inch, bottom_y + bottom_h - 70, f"${self.data.current_er_monthly:,.2f}")

        self.c.setFont('Helvetica', 9)
        self.c.drawString(3.9 * inch, bottom_y + 60, "CURRENT ER ANNUAL")
        self.c.setFont('Helvetica-Bold', 14)
        self.c.drawString(3.9 * inch, bottom_y + 40, f"${self.data.current_er_annual:,.2f}")

        # Proposed ICHRA Budget
        self._draw_rounded_rect(7.1 * inch, bottom_y, 3.5 * inch, bottom_h, 15, COLORS['teal_bg'])
        self.c.setFont('Helvetica-Bold', 12)
        self.c.setFillColor(HexColor(COLORS['cream_text']))
        self.c.drawString(7.3 * inch, bottom_y + bottom_h - 25, "Proposed ICHRA Budget")

        self.c.setFont('Helvetica', 8)
        self.c.drawString(7.3 * inch, bottom_y + bottom_h - 40, "Based on Lowest Cost Silver Plan (LCSP) 95% affordability benchmark")

        self.c.setFont('Helvetica', 9)
        self.c.drawString(7.3 * inch, bottom_y + bottom_h - 60, "PROPOSED ER MONTHLY")
        self.c.setFont('Helvetica-Bold', 14)
        self.c.drawString(7.3 * inch, bottom_y + bottom_h - 80, f"${self.data.proposed_er_monthly:,.2f}")

        self.c.setFont('Helvetica', 9)
        self.c.drawString(7.3 * inch, bottom_y + 55, "PROPOSED ER ANNUAL")
        self.c.setFont('Helvetica-Bold', 14)
        self.c.drawString(7.3 * inch, bottom_y + 35, f"${self.data.proposed_er_annual:,.2f}")

    # =========================================================================
    # Slide: ICHRA Evaluation Workflow
    # =========================================================================

    def _draw_slide_workflow(self):
        """ICHRA Evaluation Workflow - the complex visual"""
        self._new_page('cream_bg')

        # Title
        self.c.setFont('Helvetica-Bold', 36)
        self.c.setFillColor(HexColor(COLORS['dark_text']))
        self.c.drawString(0.75 * inch, self.PAGE_HEIGHT - 1 * inch, "ICHRA evaluation workflow")

        # Layout constants
        left_col_x = 1 * inch
        mid_col_x = 4.5 * inch
        right_col_x = 8 * inch

        card_width = 2.5 * inch
        card_height = 1.3 * inch
        badge_width = 1.4 * inch
        badge_height = 0.4 * inch

        # Row positions
        row1_y = self.PAGE_HEIGHT - 2.5 * inch
        row2_y = row1_y - card_height - 0.7 * inch
        row3_y = row2_y - card_height - 0.7 * inch

        # =========================
        # LEFT COLUMN - Monthly costs
        # =========================

        def draw_monthly_card(x, y, label, value):
            self._draw_rounded_rect(x, y - card_height, card_width, card_height, 12, COLORS['cream_bg'])
            # Border
            self.c.setStrokeColor(HexColor(COLORS['dark_text']))
            self.c.setLineWidth(0.5)
            self.c.roundRect(x, y - card_height, card_width, card_height, 12, fill=0, stroke=1)

            # Label
            self.c.setFont('Helvetica-Bold', 12)
            self.c.setFillColor(HexColor(COLORS['dark_text']))
            self.c.drawString(x + 15, y - 25, label)

            # Value
            self.c.setFont('Helvetica-Bold', 28)
            self.c.setFillColor(HexColor(COLORS['maroon_text']))
            self.c.drawString(x + 15, y - 65, value)

        # Current monthly
        draw_monthly_card(left_col_x, row1_y, "Current monthly", f"${self.data.current_total_monthly:,.0f}")

        # Badge: +$X
        badge_x = left_col_x + card_width/2 - badge_width/2
        badge_y = row1_y - card_height - badge_height - 8
        self._draw_rounded_rect(badge_x, badge_y, badge_width, badge_height, 8, COLORS['maroon_card'])
        self.c.setFont('Helvetica-Bold', 12)
        self.c.setFillColor(HexColor(COLORS['cream_text']))
        self.c.drawCentredString(badge_x + badge_width/2, badge_y + 10, f"+${self.data.current_to_renewal_diff_monthly:,.0f}")

        # Dotted line
        self._draw_dotted_line(left_col_x + card_width/2, badge_y, left_col_x + card_width/2, row2_y)

        # Renewal monthly
        draw_monthly_card(left_col_x, row2_y, "Renewal monthly", f"${self.data.renewal_monthly:,.0f}")

        # Badge: -$X
        badge_y2 = row2_y - card_height - badge_height - 8
        self._draw_rounded_rect(badge_x, badge_y2, badge_width, badge_height, 8, COLORS['teal_bg'])
        self.c.setFont('Helvetica-Bold', 12)
        self.c.setFillColor(HexColor(COLORS['cream_text']))
        self.c.drawCentredString(badge_x + badge_width/2, badge_y2 + 10, f"-${self.data.renewal_to_ichra_diff_monthly:,.0f}")

        # Dotted line
        self._draw_dotted_line(left_col_x + card_width/2, badge_y2, left_col_x + card_width/2, row3_y)

        # ICHRA monthly
        draw_monthly_card(left_col_x, row3_y, "ICHRA monthly", f"${self.data.ichra_monthly:,.0f}")

        # =========================
        # MIDDLE COLUMN - Annual
        # =========================
        mid_card_width = 2.8 * inch
        mid_row1_y = row1_y - 0.2 * inch
        mid_row2_y = row2_y - 0.2 * inch

        def draw_annual_card(x, y, label, value):
            self._draw_rounded_rect(x, y - card_height, mid_card_width, card_height, 12, '#FFFFFF')
            self.c.setStrokeColor(HexColor(COLORS['dark_text']))
            self.c.setLineWidth(0.5)
            self.c.roundRect(x, y - card_height, mid_card_width, card_height, 12, fill=0, stroke=1)

            self.c.setFont('Helvetica-Bold', 12)
            self.c.setFillColor(HexColor(COLORS['dark_text']))
            self.c.drawString(x + 15, y - 25, label)

            self.c.setFont('Helvetica-Bold', 26)
            self.c.setFillColor(HexColor(COLORS['maroon_text']))
            self.c.drawString(x + 15, y - 65, value)

        # New annual bottom line
        draw_annual_card(mid_col_x, mid_row1_y, "New annual bottom line", f"${self.data.total_renewal_cost:,.0f}")

        # Dotted line from left to middle
        self._draw_dotted_line(left_col_x + card_width, row1_y - card_height/2, mid_col_x, mid_row1_y - card_height/2)

        # ICHRA annual bottom line
        draw_annual_card(mid_col_x, mid_row2_y + 0.3 * inch, "ICHRA annual bottom line", f"${self.data.proposed_er_annual:,.0f}")

        # Dotted line from left to middle
        self._draw_dotted_line(left_col_x + card_width, row3_y - card_height/2, mid_col_x, mid_row2_y + 0.3 * inch - card_height/2)

        # =========================
        # RIGHT COLUMN - Savings
        # =========================
        savings_card_y = (mid_row1_y + mid_row2_y) / 2
        savings_card_h = 1.8 * inch

        self._draw_rounded_rect(right_col_x, savings_card_y - savings_card_h, card_width, savings_card_h, 12, '#FFFFFF')
        self.c.setStrokeColor(HexColor(COLORS['dark_text']))
        self.c.setLineWidth(0.5)
        self.c.roundRect(right_col_x, savings_card_y - savings_card_h, card_width, savings_card_h, 12, fill=0, stroke=1)

        # Savings label
        self.c.setFont('Helvetica-Bold', 14)
        self.c.setFillColor(HexColor(COLORS['dark_text']))
        self.c.drawCentredString(right_col_x + card_width/2, savings_card_y - 30, "Savings")

        # Savings value
        self.c.setFont('Helvetica-Bold', 32)
        self.c.setFillColor(HexColor(COLORS['maroon_text']))
        self.c.drawCentredString(right_col_x + card_width/2, savings_card_y - 80, f"${self.data.annual_savings_vs_renewal:,.0f}")

        # Percentage badge (circle)
        savings_pct = (self.data.annual_savings_vs_renewal / self.data.total_renewal_cost * 100) if self.data.total_renewal_cost > 0 else 0
        circle_x = right_col_x + card_width - 25
        circle_y = savings_card_y - 10

        self.c.setFillColor(HexColor(COLORS['teal_bg']))
        self.c.circle(circle_x, circle_y, 30, fill=1, stroke=0)

        self.c.setFont('Helvetica-Bold', 14)
        self.c.setFillColor(HexColor(COLORS['cream_text']))
        self.c.drawCentredString(circle_x, circle_y - 5, f"-{savings_pct:.0f}%")

        # Dotted lines to savings
        self._draw_dotted_line(mid_col_x + mid_card_width, mid_row1_y - card_height/2, right_col_x, savings_card_y - savings_card_h * 0.3)
        self._draw_dotted_line(mid_col_x + mid_card_width, mid_row2_y + 0.3 * inch - card_height/2, right_col_x, savings_card_y - savings_card_h * 0.7)

    def _draw_dotted_line(self, x1, y1, x2, y2):
        """Draw a dotted line"""
        self.c.setStrokeColor(HexColor(COLORS['chart_gray']))
        self.c.setLineWidth(1)
        self.c.setDash([4, 4])
        self.c.line(x1, y1, x2, y2)
        self.c.setDash([])


def generate_pdf_proposal(data: ProposalData) -> BytesIO:
    """Convenience function to generate a PDF proposal"""
    renderer = PDFProposalRenderer(data)
    return renderer.generate()


if __name__ == "__main__":
    # Test with sample data
    test_data = ProposalData(
        client_name="Ecentria",
        renewal_percentage=40,
        total_renewal_cost=1_300_000,
        employee_count=226,
        avg_monthly_premium=559,
        covered_lives=377,
        total_employees=226,
        total_dependents=151,
        fit_score=87,
        category_scores={
            'cost_advantage': 85,
            'market_readiness': 80,
            'workforce_fit': 90,
            'geographic_complexity': 85,
            'employee_experience': 75,
            'admin_readiness': 90,
        },
        total_states=18,
        top_states=[
            {'state': 'IL', 'count': 180},
            {'state': 'AZ', 'count': 11},
            {'state': 'UT', 'count': 5},
            {'state': 'TX', 'count': 4},
            {'state': 'IN', 'count': 4},
        ],
        family_status_breakdown={'EE': 155, 'ES': 26, 'EC': 14, 'F': 31},
        current_total_monthly=203048,
        current_total_annual=2436581,
        current_er_monthly=148219,
        current_er_annual=1778631,
        current_ee_monthly=54829,
        current_ee_annual=657950,
        per_life_monthly=538,
        proposed_er_monthly=115935,
        proposed_er_annual=1391216,
        renewal_monthly=84585,
        ichra_monthly=47752,
        current_to_renewal_diff_monthly=6806,
        current_to_renewal_pct=8.75,
        renewal_to_ichra_diff_monthly=36833,
        renewal_to_ichra_pct=43.5,
        annual_savings=387415,
        annual_savings_vs_renewal=441988,
        savings_percentage=21.8,
        additional_healthcare_burden=280000,
        avg_employee_age=40.3,
        age_range_min=21,
        age_range_max=73,
    )

    buffer = generate_pdf_proposal(test_data)

    with open('/tmp/glove_proposal_test.pdf', 'wb') as f:
        f.write(buffer.getvalue())

    print(f"Generated test PDF: {len(buffer.getvalue())} bytes")
    print("Saved to /tmp/glove_proposal_test.pdf")
