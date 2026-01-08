"""
Page 4: Export Results
Generate PDF reports and export data to CSV for ICHRA contribution evaluation
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from constants import EXPORT_FILE_PREFIX, DATE_FORMAT, FAMILY_STATUS_CODES
from utils import DataFormatter, ContributionComparison
from database import get_database_connection
import re


def sanitize_text_input(text: str, max_length: int = 100) -> str:
    """
    Sanitize text input for safe use in PDF generation.
    - Strips whitespace
    - Removes potentially problematic characters
    - Limits length
    """
    if not text:
        return ""
    # Remove control characters and limit to printable ASCII + common unicode
    sanitized = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', str(text))
    # Strip and limit length
    sanitized = sanitized.strip()[:max_length]
    return sanitized

# Try importing reportlab for PDF generation
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


st.set_page_config(page_title="Export results", page_icon="📄", layout="wide")


# Initialize session state
if 'db' not in st.session_state:
    st.session_state.db = get_database_connection()

if 'census_df' not in st.session_state:
    st.session_state.census_df = None

if 'dependents_df' not in st.session_state:
    st.session_state.dependents_df = None

if 'contribution_analysis' not in st.session_state:
    st.session_state.contribution_analysis = {}

if 'contribution_settings' not in st.session_state:
    st.session_state.contribution_settings = {'default_percentage': 75}


# Page header
st.title("📄 Export results")
st.markdown("Generate PDF reports and export data to CSV")

# Check prerequisites
if st.session_state.census_df is None:
    st.warning("⚠️ No employee census loaded. Please complete **Census input** first.")
    st.info("👉 Go to **1️⃣ Census input** in the sidebar to upload your census")
    st.stop()

census_df = st.session_state.census_df
dependents_df = st.session_state.dependents_df
contribution_analysis = st.session_state.contribution_analysis

# Check if contribution analysis has been run
has_analysis = bool(contribution_analysis)
has_individual_contribs = ContributionComparison.has_individual_contributions(census_df)

st.markdown("---")

# ============================================================================
# PDF GENERATION
# ============================================================================

st.subheader("📊 PDF report generation")

if not REPORTLAB_AVAILABLE:
    st.warning("""
    ⚠️ **PDF generation not available**

    The `reportlab` library is not installed. Install it to enable PDF generation:

    ```
    pip install reportlab
    ```

    For now, you can export data to CSV format below.
    """)

else:
    st.info("Generate a professional PDF report for your ICHRA contribution evaluation")

    # PDF customization options
    with st.expander("⚙️ Customize PDF options", expanded=True):

        col1, col2 = st.columns(2)

        with col1:
            client_name_raw = st.text_input("Client/company name", value="ABC Company", max_chars=100)
            consultant_name_raw = st.text_input("Consultant name", value="Your Name", max_chars=100)
            # Sanitize inputs for safe PDF generation
            client_name = sanitize_text_input(client_name_raw)
            consultant_name = sanitize_text_input(consultant_name_raw)

        with col2:
            include_employee_detail = st.checkbox(
                "Include employee-level cost comparison",
                value=True,
                help="Show per-employee current vs ICHRA cost breakdown"
            )
            include_demographics = st.checkbox(
                "Include census demographics summary",
                value=True,
                help="Show age distribution, family status, and geographic breakdown"
            )

    # Generate PDF button
    if st.button("🎨 Generate PDF report", type="primary"):

        if not has_analysis:
            st.warning("⚠️ No contribution analysis available. Run analysis on Page 2 first for a complete report.")

        with st.spinner("Generating PDF report..."):

            # Create PDF buffer
            buffer = BytesIO()

            doc = SimpleDocTemplate(
                buffer,
                pagesize=letter,
                leftMargin=0.75*inch,
                rightMargin=0.75*inch,
                topMargin=0.75*inch,
                bottomMargin=0.75*inch
            )

            # Container for PDF elements
            elements = []

            # Styles
            styles = getSampleStyleSheet()
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=24,
                textColor=colors.HexColor('#1f77b4'),
                spaceAfter=30
            )

            heading_style = ParagraphStyle(
                'CustomHeading',
                parent=styles['Heading2'],
                fontSize=16,
                textColor=colors.HexColor('#333333'),
                spaceAfter=12,
                spaceBefore=12
            )

            subheading_style = ParagraphStyle(
                'CustomSubheading',
                parent=styles['Heading3'],
                fontSize=12,
                textColor=colors.HexColor('#555555'),
                spaceAfter=8,
                spaceBefore=8
            )

            # Title page
            elements.append(Paragraph("ICHRA contribution evaluation", title_style))
            elements.append(Spacer(1, 0.25*inch))

            elements.append(Paragraph(f"<b>Prepared for:</b> {client_name}", styles['Normal']))
            elements.append(Spacer(1, 0.1*inch))
            elements.append(Paragraph(f"<b>Prepared by:</b> {consultant_name}", styles['Normal']))
            elements.append(Spacer(1, 0.1*inch))
            elements.append(Paragraph(f"<b>Date:</b> {datetime.now().strftime('%B %d, %Y')}", styles['Normal']))
            elements.append(Spacer(1, 0.5*inch))

            # Executive summary
            elements.append(Paragraph("Executive summary", heading_style))

            num_employees = len(census_df)
            num_dependents = len(dependents_df) if dependents_df is not None and not dependents_df.empty else 0
            total_lives = num_employees + num_dependents

            summary_text = f"""
            This report presents an ICHRA (Individual Coverage Health Reimbursement Arrangement)
            contribution evaluation for {num_employees} employees
            {"and " + str(num_dependents) + " dependents " if num_dependents > 0 else ""}
            ({total_lives} total covered lives).
            """
            elements.append(Paragraph(summary_text, styles['Normal']))
            elements.append(Spacer(1, 0.25*inch))

            # Contribution Settings
            settings = st.session_state.contribution_settings
            contribution_type = settings.get('contribution_type', 'percentage')

            if contribution_type == 'class_based':
                strategy_name = settings.get('strategy_name', 'Class-Based')
                total_annual = settings.get('total_annual', 0)
                contrib_text = f"<b>Contribution Strategy:</b> {strategy_name} (Total Annual: ${total_annual:,.0f})"
            else:
                contribution_pct = settings.get('default_percentage', 75)
                contrib_text = f"<b>Employer Contribution:</b> {contribution_pct}% of benchmark premium"

            elements.append(Paragraph(contrib_text, styles['Normal']))
            elements.append(Spacer(1, 0.25*inch))

            # Cost summary (if individual contributions available)
            if has_individual_contribs:
                elements.append(Paragraph("Premium comparison", heading_style))

                contrib_totals = ContributionComparison.aggregate_contribution_totals(census_df)

                # Get ICHRA budget from strategy results (the authoritative source)
                strategy_results = st.session_state.get('strategy_results', {})
                if strategy_results.get('calculated', False):
                    result = strategy_results.get('result', {})
                    proposed_ichra_monthly = result.get('total_monthly', 0)
                    proposed_ichra_annual = result.get('total_annual', 0)
                    employees_analyzed = result.get('employees_covered', 0)
                else:
                    # Fallback to contribution_analysis
                    proposed_ichra_monthly = sum(
                        analysis.get('ichra_analysis', {}).get('employer_contribution', 0)
                        for analysis in contribution_analysis.values()
                    )
                    proposed_ichra_annual = proposed_ichra_monthly * 12
                    employees_analyzed = len(contribution_analysis)

                # Current TOTAL premium (ER + EE) for apples-to-apples comparison
                current_er_monthly = contrib_totals['total_current_er_monthly']
                current_er_annual = contrib_totals['total_current_er_annual']
                current_ee_monthly = contrib_totals['total_current_ee_monthly']
                current_ee_annual = contrib_totals['total_current_ee_annual']
                current_total_monthly = current_er_monthly + current_ee_monthly
                current_total_annual = current_er_annual + current_ee_annual

                # Calculate change (total premium vs ICHRA)
                change_annual = proposed_ichra_annual - current_total_annual
                change_pct = (change_annual / current_total_annual * 100) if current_total_annual > 0 else 0

                # Headline savings/cost message
                if change_annual < 0:
                    savings_text = f"<b>Annual Savings: {DataFormatter.format_currency(abs(change_annual))} ({abs(change_pct):.0f}% reduction)</b>"
                    elements.append(Paragraph(savings_text, ParagraphStyle('Savings', parent=styles['Normal'], textColor=colors.HexColor('#228B22'), fontSize=12)))
                elif change_annual > 0:
                    cost_text = f"<b>Additional Cost: {DataFormatter.format_currency(change_annual)}/year ({change_pct:.0f}% increase)</b>"
                    elements.append(Paragraph(cost_text, ParagraphStyle('Cost', parent=styles['Normal'], textColor=colors.HexColor('#CC0000'), fontSize=12)))
                else:
                    elements.append(Paragraph("<b>Cost Neutral</b>", styles['Normal']))
                elements.append(Spacer(1, 0.15*inch))

                # Simple comparison table - using TOTALS
                cost_table_data = [
                    ['', 'Current Total Premium', 'Proposed ICHRA', 'Change'],
                    [
                        'Annual',
                        DataFormatter.format_currency(current_total_annual),
                        DataFormatter.format_currency(proposed_ichra_annual),
                        DataFormatter.format_currency(change_annual, include_sign=True)
                    ],
                    [
                        'Monthly',
                        DataFormatter.format_currency(current_total_monthly),
                        DataFormatter.format_currency(proposed_ichra_monthly),
                        DataFormatter.format_currency(proposed_ichra_monthly - current_total_monthly, include_sign=True)
                    ],
                ]

                cost_table = Table(cost_table_data, colWidths=[1.3*inch, 1.75*inch, 1.75*inch, 1.5*inch])
                cost_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f77b4')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('FONTSIZE', (0, 1), (-1, -1), 9),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f0f0')])
                ]))

                elements.append(cost_table)
                elements.append(Spacer(1, 0.1*inch))
                elements.append(Paragraph(f"<i>Current Total = ER + EE premium. Based on {employees_analyzed} employees.</i>", styles['Normal']))
                elements.append(Spacer(1, 0.25*inch))

            # Employee detail (if enabled)
            if include_employee_detail and has_analysis:
                elements.append(PageBreak())
                elements.append(Paragraph("Employee-level cost comparison", heading_style))

                detail_table_data = [['Employee ID', 'Family', 'Current Total', 'Proposed ICHRA', 'Change']]

                for emp_id, analysis in contribution_analysis.items():
                    emp_data = census_df[census_df['employee_id'] == emp_id]
                    if emp_data.empty:
                        continue

                    emp = emp_data.iloc[0]
                    # Get current ER and EE to calculate total
                    current_er = emp.get('current_er_monthly')
                    current_ee = emp.get('current_ee_monthly')

                    # Calculate current total (ER + EE)
                    current_total = None
                    if pd.notna(current_er) or pd.notna(current_ee):
                        er_val = current_er if pd.notna(current_er) else 0
                        ee_val = current_ee if pd.notna(current_ee) else 0
                        current_total = er_val + ee_val

                    ichra_data = analysis.get('ichra_analysis', {})
                    proposed_ichra = ichra_data.get('employer_contribution', 0)

                    # Calculate change vs total premium
                    change = None
                    if current_total is not None:
                        change = proposed_ichra - current_total

                    detail_table_data.append([
                        str(emp_id)[:15],
                        emp.get('family_status', 'EE'),
                        DataFormatter.format_currency(current_total) if current_total is not None else 'N/A',
                        DataFormatter.format_currency(proposed_ichra),
                        DataFormatter.format_currency(change, include_sign=True) if change is not None else 'N/A'
                    ])

                detail_table = Table(detail_table_data, colWidths=[1.5*inch, 0.75*inch, 1.25*inch, 1.25*inch, 1.25*inch])
                detail_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f77b4')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('FONTSIZE', (0, 1), (-1, -1), 8),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f0f0')])
                ]))

                elements.append(detail_table)
                elements.append(Spacer(1, 0.1*inch))
                elements.append(Paragraph("<i>Current Total = ER + EE premium per employee (monthly)</i>", styles['Normal']))
                elements.append(Spacer(1, 0.25*inch))

            # Demographics summary (if enabled)
            if include_demographics:
                elements.append(PageBreak())
                elements.append(Paragraph("Census demographics", heading_style))

                # Age distribution
                elements.append(Paragraph("Age distribution", subheading_style))

                age_col = 'employee_age' if 'employee_age' in census_df.columns else 'age'
                age_bins = [0, 30, 40, 50, 60, 100]
                age_labels = ['Under 30', '30-39', '40-49', '50-59', '60+']

                census_with_age = census_df.copy()
                census_with_age['age_group'] = pd.cut(
                    census_with_age[age_col],
                    bins=age_bins,
                    labels=age_labels,
                    right=False
                )
                age_dist = census_with_age['age_group'].value_counts().sort_index()

                age_table_data = [['Age Group', 'Count', 'Percentage']]
                for age_group, count in age_dist.items():
                    pct = count / len(census_df) * 100
                    age_table_data.append([str(age_group), str(count), f"{pct:.1f}%"])

                age_table = Table(age_table_data, colWidths=[2*inch, 1*inch, 1*inch])
                age_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#555555')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f0f0')])
                ]))

                elements.append(age_table)
                elements.append(Spacer(1, 0.25*inch))

                # Family status distribution
                if 'family_status' in census_df.columns:
                    elements.append(Paragraph("Family status distribution", subheading_style))

                    family_counts = census_df['family_status'].value_counts()
                    family_table_data = [['Family Status', 'Description', 'Count', 'Percentage']]

                    for code, count in family_counts.items():
                        pct = count / len(census_df) * 100
                        desc = FAMILY_STATUS_CODES.get(code, code)
                        family_table_data.append([code, desc, str(count), f"{pct:.1f}%"])

                    family_table = Table(family_table_data, colWidths=[1*inch, 2.5*inch, 0.75*inch, 1*inch])
                    family_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#555555')),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('ALIGN', (1, 1), (1, -1), 'LEFT'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, -1), 9),
                        ('GRID', (0, 0), (-1, -1), 1, colors.black),
                        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f0f0')])
                    ]))

                    elements.append(family_table)
                    elements.append(Spacer(1, 0.25*inch))

                # State distribution
                elements.append(Paragraph("Geographic distribution", subheading_style))

                state_counts = census_df['state'].value_counts()
                state_table_data = [['State', 'Employees', 'Percentage']]

                for state, count in state_counts.items():
                    pct = count / len(census_df) * 100
                    state_table_data.append([state, str(count), f"{pct:.1f}%"])

                state_table = Table(state_table_data, colWidths=[1*inch, 1*inch, 1*inch])
                state_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#555555')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f0f0')])
                ]))

                elements.append(state_table)

            # Build PDF
            doc.build(elements)

            # Get PDF bytes
            pdf_bytes = buffer.getvalue()
            buffer.close()

            # Display download button
            st.success("✅ PDF generated successfully!")

            timestamp = datetime.now().strftime(DATE_FORMAT)
            filename = f"{EXPORT_FILE_PREFIX}_{client_name.replace(' ', '_')}_{timestamp}.pdf"

            st.download_button(
                label="📥 Download PDF report",
                data=pdf_bytes,
                file_name=filename,
                mime="application/pdf"
            )

# ============================================================================
# CSV EXPORTS
# ============================================================================

st.markdown("---")
st.subheader("📊 CSV data exports")

st.markdown("Download detailed data in CSV format for further analysis")

col1, col2 = st.columns(2)

with col1:
    # Export census with contribution analysis
    st.markdown("**Employee census with analysis**")

    if st.button("Generate census export"):
        employee_export = []

        # Get contribution settings for reference
        settings = st.session_state.contribution_settings
        contribution_type = settings.get('contribution_type', 'percentage')

        for _, emp in census_df.iterrows():
            employee_id = emp.get('employee_id', '')

            # Get current contribution data
            current_ee = emp.get('current_ee_monthly')
            current_er = emp.get('current_er_monthly')

            # Get analysis data if available
            analysis = contribution_analysis.get(employee_id, {})
            ichra_data = analysis.get('ichra_analysis', {})

            proposed_ee = ichra_data.get('employee_cost', '')
            proposed_er = ichra_data.get('employer_contribution', '')
            total_premium = ichra_data.get('total_premium', '')

            # Calculate changes if data available
            ee_change_monthly = ''
            er_change_monthly = ''
            if pd.notna(current_ee) and proposed_ee != '':
                ee_change_monthly = proposed_ee - current_ee
            if pd.notna(current_er) and proposed_er != '':
                er_change_monthly = proposed_er - current_er

            employee_export.append({
                'employee_id': employee_id,
                'first_name': emp.get('first_name', ''),
                'last_name': emp.get('last_name', ''),
                'age': emp.get('age', ''),
                'state': emp.get('state', ''),
                'county': emp.get('county', ''),
                'rating_area': emp.get('rating_area_id', ''),
                'family_status': emp.get('family_status', 'EE'),
                # Current group plan contributions
                'current_ee_monthly': current_ee if pd.notna(current_ee) else '',
                'current_er_monthly': current_er if pd.notna(current_er) else '',
                # ICHRA analysis
                'ichra_total_premium': total_premium,
                'ichra_employer_contribution': proposed_er,
                'ichra_employee_cost': proposed_ee,
                # Changes
                'ee_change_monthly': ee_change_monthly,
                'er_change_monthly': er_change_monthly,
                'ee_change_annual': ee_change_monthly * 12 if ee_change_monthly != '' else '',
                'er_change_annual': er_change_monthly * 12 if er_change_monthly != '' else '',
            })

        employee_export_df = pd.DataFrame(employee_export)
        csv = employee_export_df.to_csv(index=False)

        # Build filename with client name and timestamp
        timestamp = datetime.now().strftime(DATE_FORMAT)
        client_name = st.session_state.get('client_name', '').strip()
        if client_name:
            safe_name = client_name.replace(' ', '_').replace('/', '-')
            csv_filename = f"{EXPORT_FILE_PREFIX}_census_{safe_name}_{timestamp}.csv"
        else:
            csv_filename = f"{EXPORT_FILE_PREFIX}_census_{timestamp}.csv"

        st.download_button(
            label="📥 Download census CSV",
            data=csv,
            file_name=csv_filename,
            mime="text/csv",
            key="census_export"
        )

with col2:
    # Export contribution summary
    st.markdown("**Contribution summary**")

    if st.button("Generate summary export"):
        summary_rows = []

        if has_individual_contribs:
            contrib_totals = ContributionComparison.aggregate_contribution_totals(census_df)

            # Get ICHRA budget from strategy results (the authoritative source)
            strategy_results = st.session_state.get('strategy_results', {})
            if strategy_results.get('calculated', False):
                result = strategy_results.get('result', {})
                proposed_ichra_monthly = result.get('total_monthly', 0)
                proposed_ichra_annual = result.get('total_annual', 0)
                employees_analyzed = result.get('employees_covered', 0)
            else:
                # Fallback to contribution_analysis
                proposed_ichra_monthly = sum(
                    analysis.get('ichra_analysis', {}).get('employer_contribution', 0)
                    for analysis in contribution_analysis.values()
                )
                proposed_ichra_annual = proposed_ichra_monthly * 12
                employees_analyzed = len(contribution_analysis)

            # ER to ER comparison (what employer pays)
            current_er_monthly = contrib_totals['total_current_er_monthly']
            current_er_annual = contrib_totals['total_current_er_annual']
            change_annual = proposed_ichra_annual - current_er_annual

            summary_rows.append({
                'metric': 'Employees',
                'current_er_spend': len(census_df),
                'proposed_ichra': employees_analyzed,
                'change': ''
            })
            summary_rows.append({
                'metric': 'Annual employer cost',
                'current_er_spend': current_er_annual,
                'proposed_ichra': proposed_ichra_annual,
                'change': change_annual
            })
            summary_rows.append({
                'metric': 'Monthly employer cost',
                'current_er_spend': current_er_monthly,
                'proposed_ichra': proposed_ichra_monthly,
                'change': proposed_ichra_monthly - current_er_monthly
            })
        else:
            summary_rows.append({
                'metric': 'Total employees',
                'current_group': len(census_df),
                'proposed_ichra': len(contribution_analysis),
                'change': ''
            })
            summary_rows.append({
                'metric': 'Note',
                'current_group': 'No contribution data in census',
                'proposed_ichra': '',
                'change': ''
            })

        summary_df = pd.DataFrame(summary_rows)
        csv = summary_df.to_csv(index=False)

        # Build filename with client name and timestamp
        timestamp = datetime.now().strftime(DATE_FORMAT)
        client_name = st.session_state.get('client_name', '').strip()
        if client_name:
            safe_name = client_name.replace(' ', '_').replace('/', '-')
            csv_filename = f"{EXPORT_FILE_PREFIX}_summary_{safe_name}_{timestamp}.csv"
        else:
            csv_filename = f"{EXPORT_FILE_PREFIX}_summary_{timestamp}.csv"

        st.download_button(
            label="📥 Download summary CSV",
            data=csv,
            file_name=csv_filename,
            mime="text/csv",
            key="summary_export"
        )

# Export dependents if available
if dependents_df is not None and not dependents_df.empty:
    st.markdown("---")
    st.markdown("**Dependents export**")

    if st.button("Generate dependents export"):
        csv = dependents_df.to_csv(index=False)

        # Build filename with client name and timestamp
        timestamp = datetime.now().strftime(DATE_FORMAT)
        client_name = st.session_state.get('client_name', '').strip()
        if client_name:
            safe_name = client_name.replace(' ', '_').replace('/', '-')
            csv_filename = f"{EXPORT_FILE_PREFIX}_dependents_{safe_name}_{timestamp}.csv"
        else:
            csv_filename = f"{EXPORT_FILE_PREFIX}_dependents_{timestamp}.csv"

        st.download_button(
            label="📥 Download dependents CSV",
            data=csv,
            file_name=csv_filename,
            mime="text/csv",
            key="dependents_export"
        )

# ============================================================================
# COMPLETION
# ============================================================================

st.markdown("---")
st.success("""
### ✅ ICHRA contribution evaluation complete!

You've successfully completed the ICHRA calculator workflow:

1. ✓ Employee census loaded
2. ✓ Contribution evaluation available
3. ✓ Summary reviewed
4. ✓ Results ready for export

**Next Steps:**
- Download PDF report for client presentation
- Use CSV exports for detailed analysis
- Adjust contribution percentages as needed on Page 2

**Need to make changes?** Use the sidebar navigation to go back to any step.
""")
