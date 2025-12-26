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


st.set_page_config(page_title="Export Results", page_icon="📄", layout="wide")

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
st.title("📄 Export Results")
st.markdown("Generate PDF reports and export data to CSV")

# Check prerequisites
if st.session_state.census_df is None:
    st.warning("⚠️ No employee census loaded. Please complete **Census Input** first.")
    st.info("👉 Go to **1️⃣ Census Input** in the sidebar to upload your census")
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

st.subheader("📊 PDF Report Generation")

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
    with st.expander("⚙️ Customize PDF Options", expanded=True):

        col1, col2 = st.columns(2)

        with col1:
            client_name_raw = st.text_input("Client/Company Name", value="ABC Company", max_chars=100)
            consultant_name_raw = st.text_input("Consultant Name", value="Your Name", max_chars=100)
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
    if st.button("🎨 Generate PDF Report", type="primary"):

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
            elements.append(Paragraph("ICHRA Contribution Evaluation", title_style))
            elements.append(Spacer(1, 0.25*inch))

            elements.append(Paragraph(f"<b>Prepared for:</b> {client_name}", styles['Normal']))
            elements.append(Spacer(1, 0.1*inch))
            elements.append(Paragraph(f"<b>Prepared by:</b> {consultant_name}", styles['Normal']))
            elements.append(Spacer(1, 0.1*inch))
            elements.append(Paragraph(f"<b>Date:</b> {datetime.now().strftime('%B %d, %Y')}", styles['Normal']))
            elements.append(Spacer(1, 0.5*inch))

            # Executive Summary
            elements.append(Paragraph("Executive Summary", heading_style))

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
            elif contribution_type == 'flat':
                flat_amounts = settings.get('flat_amounts', {})
                ee_amount = flat_amounts.get('EE', 0)
                contrib_text = f"<b>Employer Contribution:</b> Flat ${ee_amount:,.0f}/month (EE base)"
            else:
                contribution_pct = settings.get('default_percentage', 75)
                contrib_text = f"<b>Employer Contribution:</b> {contribution_pct}% of benchmark premium"

            elements.append(Paragraph(contrib_text, styles['Normal']))
            elements.append(Spacer(1, 0.25*inch))

            # Cost Summary (if individual contributions available)
            if has_individual_contribs:
                elements.append(Paragraph("Current vs Proposed Cost Summary", heading_style))

                contrib_totals = ContributionComparison.aggregate_contribution_totals(census_df)

                # Calculate proposed totals from analysis
                proposed_er_monthly = 0.0
                proposed_ee_monthly = 0.0
                employees_analyzed = 0

                for emp_id, analysis in contribution_analysis.items():
                    if 'ichra_analysis' in analysis and analysis['ichra_analysis']:
                        proposed_er_monthly += analysis['ichra_analysis'].get('employer_contribution', 0)
                        proposed_ee_monthly += analysis['ichra_analysis'].get('employee_cost', 0)
                        employees_analyzed += 1

                cost_table_data = [
                    ['Metric', 'Current Group Plan', 'Proposed ICHRA', 'Change'],
                    [
                        'ER Monthly',
                        DataFormatter.format_currency(contrib_totals['total_current_er_monthly']),
                        DataFormatter.format_currency(proposed_er_monthly) if employees_analyzed > 0 else 'N/A',
                        DataFormatter.format_currency(proposed_er_monthly - contrib_totals['total_current_er_monthly'], include_sign=True) if employees_analyzed > 0 else 'N/A'
                    ],
                    [
                        'ER Annual',
                        DataFormatter.format_currency(contrib_totals['total_current_er_annual']),
                        DataFormatter.format_currency(proposed_er_monthly * 12) if employees_analyzed > 0 else 'N/A',
                        DataFormatter.format_currency((proposed_er_monthly - contrib_totals['total_current_er_monthly']) * 12, include_sign=True) if employees_analyzed > 0 else 'N/A'
                    ],
                    [
                        'EE Monthly',
                        DataFormatter.format_currency(contrib_totals['total_current_ee_monthly']),
                        DataFormatter.format_currency(proposed_ee_monthly) if employees_analyzed > 0 else 'N/A',
                        DataFormatter.format_currency(proposed_ee_monthly - contrib_totals['total_current_ee_monthly'], include_sign=True) if employees_analyzed > 0 else 'N/A'
                    ],
                    [
                        'EE Annual',
                        DataFormatter.format_currency(contrib_totals['total_current_ee_annual']),
                        DataFormatter.format_currency(proposed_ee_monthly * 12) if employees_analyzed > 0 else 'N/A',
                        DataFormatter.format_currency((proposed_ee_monthly - contrib_totals['total_current_ee_monthly']) * 12, include_sign=True) if employees_analyzed > 0 else 'N/A'
                    ],
                ]

                cost_table = Table(cost_table_data, colWidths=[1.5*inch, 1.75*inch, 1.75*inch, 1.5*inch])
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
                elements.append(Paragraph(f"<i>Based on {employees_analyzed} employees with completed analysis</i>", styles['Normal']))
                elements.append(Spacer(1, 0.25*inch))

            # Employee Detail (if enabled)
            if include_employee_detail and has_analysis:
                elements.append(PageBreak())
                elements.append(Paragraph("Employee-Level Cost Comparison", heading_style))

                detail_table_data = [['Employee ID', 'Family', 'Current ER', 'ICHRA ER', 'ER Change']]

                for emp_id, analysis in contribution_analysis.items():
                    emp_data = census_df[census_df['employee_id'] == emp_id]
                    if emp_data.empty:
                        continue

                    emp = emp_data.iloc[0]
                    current_er = emp.get('current_er_monthly')
                    ichra_data = analysis.get('ichra_analysis', {})
                    proposed_er = ichra_data.get('employer_contribution', 0)

                    er_change = None
                    if pd.notna(current_er):
                        er_change = proposed_er - current_er

                    detail_table_data.append([
                        str(emp_id)[:15],
                        emp.get('family_status', 'EE'),
                        DataFormatter.format_currency(current_er) if pd.notna(current_er) else 'N/A',
                        DataFormatter.format_currency(proposed_er),
                        DataFormatter.format_currency(er_change, include_sign=True) if er_change is not None else 'N/A'
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
                elements.append(Spacer(1, 0.25*inch))

            # Demographics Summary (if enabled)
            if include_demographics:
                elements.append(PageBreak())
                elements.append(Paragraph("Census Demographics", heading_style))

                # Age distribution
                elements.append(Paragraph("Age Distribution", subheading_style))

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
                    elements.append(Paragraph("Family Status Distribution", subheading_style))

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
                elements.append(Paragraph("Geographic Distribution", subheading_style))

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
                label="📥 Download PDF Report",
                data=pdf_bytes,
                file_name=filename,
                mime="application/pdf"
            )

# ============================================================================
# CSV EXPORTS
# ============================================================================

st.markdown("---")
st.subheader("📊 CSV Data Exports")

st.markdown("Download detailed data in CSV format for further analysis")

col1, col2 = st.columns(2)

with col1:
    # Export census with contribution analysis
    st.markdown("**Employee Census with Analysis**")

    if st.button("Generate Census Export"):
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

        st.download_button(
            label="📥 Download Census CSV",
            data=csv,
            file_name=f"{EXPORT_FILE_PREFIX}_census_{datetime.now().strftime(DATE_FORMAT)}.csv",
            mime="text/csv",
            key="census_export"
        )

with col2:
    # Export contribution summary
    st.markdown("**Contribution Summary**")

    if st.button("Generate Summary Export"):
        summary_rows = []

        if has_individual_contribs:
            contrib_totals = ContributionComparison.aggregate_contribution_totals(census_df)

            # Calculate proposed totals
            proposed_er_monthly = 0.0
            proposed_ee_monthly = 0.0
            employees_analyzed = 0

            for emp_id, analysis in contribution_analysis.items():
                if 'ichra_analysis' in analysis and analysis['ichra_analysis']:
                    proposed_er_monthly += analysis['ichra_analysis'].get('employer_contribution', 0)
                    proposed_ee_monthly += analysis['ichra_analysis'].get('employee_cost', 0)
                    employees_analyzed += 1

            summary_rows.append({
                'metric': 'Total Employees',
                'current_group': len(census_df),
                'proposed_ichra': employees_analyzed,
                'change': ''
            })
            summary_rows.append({
                'metric': 'ER Monthly Total',
                'current_group': contrib_totals['total_current_er_monthly'],
                'proposed_ichra': proposed_er_monthly,
                'change': proposed_er_monthly - contrib_totals['total_current_er_monthly'] if employees_analyzed > 0 else ''
            })
            summary_rows.append({
                'metric': 'ER Annual Total',
                'current_group': contrib_totals['total_current_er_annual'],
                'proposed_ichra': proposed_er_monthly * 12,
                'change': (proposed_er_monthly - contrib_totals['total_current_er_monthly']) * 12 if employees_analyzed > 0 else ''
            })
            summary_rows.append({
                'metric': 'EE Monthly Total',
                'current_group': contrib_totals['total_current_ee_monthly'],
                'proposed_ichra': proposed_ee_monthly,
                'change': proposed_ee_monthly - contrib_totals['total_current_ee_monthly'] if employees_analyzed > 0 else ''
            })
            summary_rows.append({
                'metric': 'EE Annual Total',
                'current_group': contrib_totals['total_current_ee_annual'],
                'proposed_ichra': proposed_ee_monthly * 12,
                'change': (proposed_ee_monthly - contrib_totals['total_current_ee_monthly']) * 12 if employees_analyzed > 0 else ''
            })
        else:
            summary_rows.append({
                'metric': 'Total Employees',
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

        st.download_button(
            label="📥 Download Summary CSV",
            data=csv,
            file_name=f"{EXPORT_FILE_PREFIX}_summary_{datetime.now().strftime(DATE_FORMAT)}.csv",
            mime="text/csv",
            key="summary_export"
        )

# Export dependents if available
if dependents_df is not None and not dependents_df.empty:
    st.markdown("---")
    st.markdown("**Dependents Export**")

    if st.button("Generate Dependents Export"):
        csv = dependents_df.to_csv(index=False)

        st.download_button(
            label="📥 Download Dependents CSV",
            data=csv,
            file_name=f"{EXPORT_FILE_PREFIX}_dependents_{datetime.now().strftime(DATE_FORMAT)}.csv",
            mime="text/csv",
            key="dependents_export"
        )

# ============================================================================
# COMPLETION
# ============================================================================

st.markdown("---")
st.success("""
### ✅ ICHRA Contribution Evaluation Complete!

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
