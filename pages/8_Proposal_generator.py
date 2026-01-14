"""
Page 7: Proposal Generator
Generate branded Glove PowerPoint proposals from ICHRA analysis
Includes email delivery via SendGrid
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pptx_generator import ProposalData
from fit_score_calculator import FitScoreCalculator, FIT_SCORE_WEIGHTS
from database import get_database_connection
from constants import FAMILY_STATUS_CODES
from utils import ContributionComparison
from email_service import EmailService, validate_email, validate_file_size


def send_email_and_update_state(
    email_service: EmailService,
    recipient_email: str,
    client_name: str,
    file_data: bytes,
    filename: str,
    presentation_id: str
):
    """
    Send proposal email and update session state with result.

    Returns:
        EmailResult from the send operation
    """
    result = email_service.send_proposal_email(
        recipient_email=recipient_email,
        client_name=client_name,
        attachment_data=file_data,
        attachment_filename=filename,
        presentation_id=presentation_id
    )
    st.session_state.email_result = result.to_dict()
    return result


# Template path for PPTX (with placeholders)
PPTX_TEMPLATE_PATH = Path(__file__).parent.parent / 'templates' / 'glove_proposal_template.pptx'

# Page config
st.set_page_config(page_title="Proposal Generator", page_icon="📑", layout="wide")

# Sidebar styling and hero section
st.markdown("""
<style>
    [data-testid="stSidebar"] { background-color: #F0F4FA; }
    [data-testid="stSidebarNav"] a { background-color: transparent !important; }
    [data-testid="stSidebarNav"] a[aria-selected="true"] { background-color: #E8F1FD !important; border-left: 3px solid #0047AB !important; }
    [data-testid="stSidebarNav"] a:hover { background-color: #E8F1FD !important; }
    [data-testid="stSidebar"] button { background-color: #E8F1FD !important; border: 1px solid #B3D4FC !important; color: #0047AB !important; }
    [data-testid="stSidebar"] button:hover { background-color: #B3D4FC !important; border-color: #0047AB !important; }
    [data-testid="stSidebar"] [data-testid="stAlert"] { background-color: #E8F1FD !important; border: 1px solid #B3D4FC !important; color: #003d91 !important; }

    .hero-section {
        background: linear-gradient(135deg, #ffffff 0%, #e8f1fd 100%);
        border-radius: 12px;
        padding: 32px;
        margin-bottom: 24px;
        border-left: 4px solid #0047AB;
    }
    .hero-title {
        font-family: 'Poppins', sans-serif;
        font-size: 28px;
        font-weight: 700;
        color: #0a1628;
        margin-bottom: 8px;
    }
    .hero-subtitle {
        font-size: 16px;
        color: #475569;
        margin: 0;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'db' not in st.session_state:
    st.session_state.db = get_database_connection()

if 'census_df' not in st.session_state:
    st.session_state.census_df = None

if 'dependents_df' not in st.session_state:
    st.session_state.dependents_df = None

if 'financial_summary' not in st.session_state:
    st.session_state.financial_summary = {}

if 'contribution_settings' not in st.session_state:
    st.session_state.contribution_settings = {'default_percentage': 75}

if 'proposal_buffer' not in st.session_state:
    st.session_state.proposal_buffer = None

if 'proposal_filename' not in st.session_state:
    st.session_state.proposal_filename = None

# Email delivery state
if 'email_result' not in st.session_state:
    st.session_state.email_result = None

if 'recipient_email' not in st.session_state:
    st.session_state.recipient_email = ""

if 'send_email_enabled' not in st.session_state:
    st.session_state.send_email_enabled = False

# Page header
st.markdown("""
<div class="hero-section">
    <div class="hero-title">📑 Proposal Generator</div>
    <p class="hero-subtitle">Generate a branded ICHRA proposal PowerPoint presentation</p>
</div>
""", unsafe_allow_html=True)

# Note: PPTX template check is done at generation time (PDF doesn't need template)

# Check prerequisites
if st.session_state.census_df is None or st.session_state.census_df.empty:
    st.warning("⚠️ No census data loaded. Please complete **Census input** first.")
    st.info("👉 Go to **1️⃣ Census input** in the sidebar to upload your census")
    st.stop()

census_df = st.session_state.census_df
dependents_df = st.session_state.dependents_df
financial_summary = st.session_state.financial_summary or {}

# Check if financial analysis is available
has_financial_data = bool(financial_summary.get('results'))

if not has_financial_data:
    st.warning("""
    ⚠️ **Financial analysis recommended**

    Complete the **Financial Summary** page first for accurate ICHRA cost projections.
    The proposal can still be generated with available data.
    """)

st.markdown("---")

# =============================================================================
# SECTION 1: CLIENT INFORMATION (Editable)
# =============================================================================
st.subheader("📋 Client information")

col1, col2 = st.columns(2)

with col1:
    # Initialize from main client_name if available, fallback to proposal_client_name
    default_client = st.session_state.get('client_name', '') or st.session_state.get('proposal_client_name', '') or 'ABC Company'

    client_name = st.text_input(
        "Client/company name",
        value=default_client,
        help="This will appear on the cover slide and all export filenames",
        key="client_name_input"
    )
    # Sync to both session state keys for consistency across pages
    st.session_state.proposal_client_name = client_name
    st.session_state.client_name = client_name

    consultant_name = st.text_input(
        "Consultant name",
        value=st.session_state.get('proposal_consultant_name', 'Your Name'),
        key="consultant_name_input"
    )
    st.session_state.proposal_consultant_name = consultant_name

with col2:
    proposal_date = st.date_input(
        "Proposal date",
        value=datetime.now(),
        key="proposal_date_input"
    )

    plan_year = st.selectbox(
        "Plan year",
        options=[2026, 2027],
        index=0,
        key="plan_year_input"
    )

# =============================================================================
# SECTION 2: FIT SCORE CALCULATION
# =============================================================================
st.markdown("---")
st.subheader("🎯 ICHRA fit score")

# Calculate Fit Score
calculator = FitScoreCalculator(
    census_df=census_df,
    dependents_df=dependents_df,
    financial_summary=financial_summary,
    contribution_settings=st.session_state.contribution_settings,
    db=st.session_state.db
)

calculated_score, category_scores = calculator.calculate()

# Allow manual override
use_override = st.checkbox("Override calculated fit score", value=False)
if use_override:
    fit_score = st.slider(
        "Manual fit score",
        min_value=0,
        max_value=100,
        value=calculated_score,
        help="Override the calculated score if needed"
    )
else:
    fit_score = calculated_score

# Display score
score_col1, score_col2 = st.columns([1, 2])

with score_col1:
    # Score color based on value
    if fit_score >= 70:
        score_color = "#16a34a"  # Green
        score_label = "Strong fit"
    elif fit_score >= 50:
        score_color = "#0047AB"  # Cobalt
        score_label = "Moderate fit"
    else:
        score_color = "#dc2626"  # Red
        score_label = "Needs review"

    st.markdown(f"""
    <div style="text-align: center; padding: 20px; background: linear-gradient(135deg, #f8fafc, #e2e8f0); border-radius: 12px; border: 2px solid {score_color};">
        <div style="font-size: 3.5em; font-weight: bold; color: {score_color};">{fit_score}</div>
        <div style="font-size: 1.1em; color: #64748b; margin-top: 5px;">{score_label}</div>
    </div>
    """, unsafe_allow_html=True)

with score_col2:
    st.markdown("**Category breakdown:**")

    category_labels = {
        'cost_advantage': 'Cost Advantage',
        'market_readiness': 'Market Readiness',
        'workforce_fit': 'Workforce Fit',
        'geographic_complexity': 'Geographic Simplicity',
        'employee_experience': 'Employee Experience',
        'admin_readiness': 'Admin Readiness',
    }

    for category, score in category_scores.items():
        label = category_labels.get(category, category.replace('_', ' ').title())
        weight = FIT_SCORE_WEIGHTS.get(category, 0)

        # Create progress bar with label
        col_label, col_bar, col_score = st.columns([2, 3, 1])
        with col_label:
            st.text(f"{label} ({weight}%)")
        with col_bar:
            st.progress(score / 100)
        with col_score:
            st.text(f"{score}")

    # Expandable section explaining how each category is calculated
    with st.expander("ℹ️ How are these scores calculated?"):
        st.markdown("""
**Cost Advantage (25%)**
Compares proposed ICHRA cost to current ER spend. Higher scores for greater savings (≥20% savings = 100, 10-20% = 80, 5-10% = 70).

**Market Readiness (20%)**
Based on marketplace plan availability in employee locations. Scores minimum and average plan counts across all rating areas.

**Workforce Fit (20%)**
Younger workforces score higher as they benefit more from individual marketplace rates. Considers % under 35, under 45, and over 55.

**Geographic Simplicity (15%)**
Fewer states = simpler administration. Single state = 100, 2-3 states = 90, 4-5 = 75. Also considers rating area count.

**Employee Experience (10%)**
Higher EE-only % = easier transition (fewer dependents to enroll). Also factors average age for tech comfort with marketplace.

**Admin Readiness (10%)**
Measures census data quality: completeness of required fields, presence of current contribution data, and rating area resolution success.
        """)

# =============================================================================
# SECTION 3: PROPOSAL DATA PREVIEW (Editable)
# =============================================================================
st.markdown("---")
st.subheader("📊 Proposal data preview")

# Build ProposalData from session state
proposal_data = ProposalData.from_session_state(st.session_state)
proposal_data.client_name = client_name
proposal_data.fit_score = fit_score
proposal_data.category_scores = category_scores

# Organized in expanders by slide group
with st.expander("📌 Cover & Overview (Slides 1-2)", expanded=True):
    cov_col1, cov_col2, cov_col3 = st.columns(3)

    with cov_col1:
        renewal_pct = st.number_input(
            "Renewal increase %",
            value=float(proposal_data.renewal_percentage) if proposal_data.renewal_percentage else 0.0,
            min_value=-50.0,
            max_value=200.0,
            format="%.1f",
            help="Renewal increase percentage vs current ER spend"
        )
        proposal_data.renewal_percentage = renewal_pct

    with cov_col2:
        total_renewal = st.number_input(
            "Total renewal cost ($)",
            value=float(proposal_data.total_renewal_cost) if proposal_data.total_renewal_cost else 0.0,
            min_value=0.0,
            format="%.0f",
            help="Total annual renewal cost"
        )
        proposal_data.total_renewal_cost = total_renewal

    with cov_col3:
        st.metric("Employees", proposal_data.employee_count)

    st.markdown("---")

    metric_col1, metric_col2, metric_col3 = st.columns(3)
    with metric_col1:
        st.metric("Covered lives", proposal_data.covered_lives)
    with metric_col2:
        st.metric("Avg monthly premium", f"${proposal_data.avg_monthly_premium:,.0f}")
    with metric_col3:
        st.metric("States", proposal_data.total_states)

with st.expander("📈 Cost burden (slide 5)", expanded=False):
    burden_col1, burden_col2, burden_col3 = st.columns(3)

    with burden_col1:
        st.metric("Employees", proposal_data.employee_count)

    with burden_col2:
        st.metric("Total annual salaries", f"${proposal_data.total_annual_salaries:,.0f}")

    with burden_col3:
        healthcare_burden = st.number_input(
            "Healthcare burden ($)",
            value=float(proposal_data.additional_healthcare_burden),
            min_value=0.0,
            format="%.0f",
            help="30% of total annual salaries"
        )
        proposal_data.additional_healthcare_burden = healthcare_burden

    if proposal_data.total_annual_salaries > 0:
        st.caption(f"Healthcare burden = 30% of ${proposal_data.total_annual_salaries:,.0f} total annual salaries")
    else:
        st.caption("Add 'Monthly Income' column to census to auto-calculate healthcare burden from salaries.")

with st.expander("🗺️ Geographic distribution (slide 8)", expanded=False):
    st.markdown("**Top states by employee count:**")

    if proposal_data.top_states:
        top_states_df = pd.DataFrame(proposal_data.top_states)
        edited_states = st.data_editor(
            top_states_df,
            num_rows="fixed",
            hide_index=True,
            column_config={
                "state": st.column_config.TextColumn("State", width="small"),
                "count": st.column_config.NumberColumn("Employees", width="small")
            }
        )
        proposal_data.top_states = edited_states.to_dict('records')
    else:
        st.info("No geographic data available from census")

with st.expander("👥 Census demographics (slide 9)", expanded=False):
    demo_col1, demo_col2 = st.columns(2)

    with demo_col1:
        st.markdown("**Population overview:**")
        st.metric("Covered lives", proposal_data.covered_lives)
        st.metric("Employees", proposal_data.total_employees)
        st.metric("Dependents", proposal_data.total_dependents)

        st.markdown("**Age statistics:**")
        st.text(f"Average age: {proposal_data.avg_employee_age:.1f}")
        st.text(f"Age range: {proposal_data.age_range_min} - {proposal_data.age_range_max}")

    with demo_col2:
        st.markdown("**Family status breakdown:**")
        for code, count in proposal_data.family_status_breakdown.items():
            desc = FAMILY_STATUS_CODES.get(code, code)
            pct = (count / proposal_data.total_employees * 100) if proposal_data.total_employees > 0 else 0
            st.text(f"{code} ({desc}): {count} ({pct:.1f}%)")

        st.markdown("**Dependents:**")
        st.text(f"Spouses: {proposal_data.total_spouses}")
        st.text(f"Children: {proposal_data.total_children}")

with st.expander("💰 Cost analysis (slides 9-10)", expanded=False):
    cost_col1, cost_col2 = st.columns(2)

    with cost_col1:
        st.markdown("**Current group plan costs (2025):**")

        current_er_monthly = st.number_input(
            "Current ER monthly total",
            value=float(proposal_data.current_er_monthly),
            min_value=0.0,
            format="%.2f"
        )
        proposal_data.current_er_monthly = current_er_monthly
        proposal_data.current_er_annual = current_er_monthly * 12

        current_ee_monthly = st.number_input(
            "Current EE monthly total",
            value=float(proposal_data.current_ee_monthly),
            min_value=0.0,
            format="%.2f"
        )
        proposal_data.current_ee_monthly = current_ee_monthly
        proposal_data.current_ee_annual = current_ee_monthly * 12

        # Recalculate ER/EE split percentages
        current_total_monthly = current_er_monthly + current_ee_monthly
        if current_total_monthly > 0:
            proposal_data.er_contribution_pct = current_er_monthly / current_total_monthly
            proposal_data.ee_contribution_pct = current_ee_monthly / current_total_monthly

        st.metric(
            "Current total annual",
            f"${(proposal_data.current_er_annual + proposal_data.current_ee_annual):,.0f}"
        )
        st.caption(f"ER share: {proposal_data.er_contribution_pct*100:.1f}%")

    with cost_col2:
        st.markdown("**Proposed ICHRA costs:**")

        proposed_er_monthly = st.number_input(
            "Proposed ER monthly",
            value=float(proposal_data.proposed_er_monthly),
            min_value=0.0,
            format="%.2f"
        )
        proposal_data.proposed_er_monthly = proposed_er_monthly
        proposal_data.proposed_er_annual = proposed_er_monthly * 12

        st.metric("Proposed ER annual", f"${proposal_data.proposed_er_annual:,.0f}")

        # Recalculate projected renewal ER
        if proposal_data.renewal_monthly > 0:
            proposal_data.projected_er_monthly_2026 = proposal_data.renewal_monthly * proposal_data.er_contribution_pct
            proposal_data.projected_er_annual_2026 = proposal_data.projected_er_monthly_2026 * 12

        # Calculate savings vs RENEWAL ER (the correct comparison)
        if proposal_data.projected_er_annual_2026 > 0:
            proposal_data.savings_vs_renewal_er = proposal_data.projected_er_annual_2026 - proposal_data.proposed_er_annual
            proposal_data.savings_vs_renewal_er_pct = (proposal_data.savings_vs_renewal_er / proposal_data.projected_er_annual_2026) * 100

        # Also calculate delta vs current ER (for transparency)
        if proposal_data.current_er_annual > 0:
            proposal_data.delta_vs_current_er = proposal_data.proposed_er_annual - proposal_data.current_er_annual
            proposal_data.delta_vs_current_er_pct = (proposal_data.delta_vs_current_er / proposal_data.current_er_annual) * 100

            # Keep annual_savings for backwards compatibility (vs current ER)
            proposal_data.annual_savings = proposal_data.current_er_annual - proposal_data.proposed_er_annual
            proposal_data.savings_percentage = (proposal_data.annual_savings / proposal_data.current_er_annual) * 100

    # Show all three comparisons clearly
    st.markdown("---")
    st.markdown("**Employer cost comparison:**")

    compare_cols = st.columns(3)

    with compare_cols[0]:
        st.markdown("**Current ER (2025)**")
        st.markdown(f"${proposal_data.current_er_annual:,.0f}/yr")

    with compare_cols[1]:
        st.markdown("**Projected Renewal ER (2026)**")
        if proposal_data.projected_er_annual_2026 > 0:
            st.markdown(f"${proposal_data.projected_er_annual_2026:,.0f}/yr")
        else:
            st.markdown("N/A")

    with compare_cols[2]:
        st.markdown("**Proposed ICHRA**")
        st.markdown(f"${proposal_data.proposed_er_annual:,.0f}/yr")

    st.markdown("---")
    result_cols = st.columns(2)

    with result_cols[0]:
        st.markdown("**vs Current ER:**")
        if proposal_data.delta_vs_current_er > 0:
            st.warning(f"+${proposal_data.delta_vs_current_er:,.0f} (+{proposal_data.delta_vs_current_er_pct:.1f}%)")
        else:
            st.success(f"${proposal_data.delta_vs_current_er:,.0f} ({proposal_data.delta_vs_current_er_pct:.1f}%)")

    with result_cols[1]:
        st.markdown("**🎯 vs Renewal ER (PRIMARY):**")
        if proposal_data.savings_vs_renewal_er >= 0:
            st.success(f"SAVES ${proposal_data.savings_vs_renewal_er:,.0f} ({proposal_data.savings_vs_renewal_er_pct:.1f}%)")
        else:
            st.warning(f"Costs ${abs(proposal_data.savings_vs_renewal_er):,.0f} more")

with st.expander("📊 ICHRA evaluation workflow (slide 13 - final)", expanded=False):
    st.caption("This slide is appended at the end of the presentation")

    workflow_col1, workflow_col2, workflow_col3 = st.columns(3)

    # Column 1: Monthly values
    with workflow_col1:
        st.metric("Current monthly", f"${proposal_data.current_total_monthly:,.0f}")
        st.caption(f"+${proposal_data.current_to_renewal_diff_monthly:,.0f} | +{proposal_data.current_to_renewal_pct:.0f}%")

        st.metric("Renewal monthly", f"${proposal_data.renewal_monthly:,.0f}")
        st.caption(f"-${proposal_data.renewal_to_ichra_diff_monthly:,.0f} | -{proposal_data.renewal_to_ichra_pct:.0f}%")

        st.metric("ICHRA monthly", f"${proposal_data.ichra_monthly:,.0f}")

    # Column 2: Annual values
    with workflow_col2:
        st.metric("New annual bottom line", f"${proposal_data.total_renewal_cost:,.0f}")
        st.metric("ICHRA annual bottom line", f"${proposal_data.proposed_er_annual:,.0f}")

    # Column 3: Savings
    with workflow_col3:
        st.metric("Savings", f"${proposal_data.annual_savings_vs_renewal:,.0f}")
        if proposal_data.total_renewal_cost > 0:
            savings_pct = (proposal_data.annual_savings_vs_renewal / proposal_data.total_renewal_cost) * 100
            st.caption(f"-{savings_pct:.0f}%")

# =============================================================================
# SECTION 4: GENERATE PROPOSAL
# =============================================================================
st.markdown("---")
st.subheader("🎨 Generate proposal")

# Note: Healthcare burden is calculated as 30% of total annual salaries
# in ProposalData.from_session_state() - we preserve that calculation here

# Summary before generation
st.markdown("**Proposal summary:**")
summary_col1, summary_col2, summary_col3 = st.columns(3)

with summary_col1:
    st.markdown(f"**Client:** {client_name}")
    st.markdown(f"**Employees:** {proposal_data.employee_count}")
    st.markdown(f"**Fit Score:** {fit_score}/100")

with summary_col2:
    st.markdown(f"**Renewal %:** {proposal_data.renewal_percentage:.1f}%")
    st.markdown(f"**Current ER Annual:** ${proposal_data.current_er_annual:,.0f}")
    st.markdown(f"**Proposed ER Annual:** ${proposal_data.proposed_er_annual:,.0f}")

with summary_col3:
    st.markdown(f"**Potential Savings:** ${proposal_data.annual_savings:,.0f}")
    st.markdown(f"**Savings %:** {proposal_data.savings_percentage:.1f}%")
    st.markdown(f"**States:** {proposal_data.total_states}")

st.markdown("---")

# Format selection
st.markdown("**Export format:**")
export_format = st.radio(
    "Choose format",
    options=["PDF (Recommended)", "PowerPoint"],
    horizontal=True,
    help="PDF renders perfectly every time. PowerPoint is editable but some graphics may not display correctly.",
    label_visibility="collapsed"
)

# =============================================================================
# EMAIL DELIVERY SECTION
# =============================================================================
st.markdown("---")
st.subheader("📧 Email delivery (optional)")

# Check if email service is configured
email_service = EmailService()
is_email_configured, email_config_error = email_service.is_configured()

if not is_email_configured:
    st.info("""
    📧 **Email delivery not configured**

    To enable email delivery, set the following environment variables in `.env`:
    - `SENDGRID_API_KEY` - Your SendGrid API key
    - `MONITORING_EMAIL` - Email address for failure notifications (optional)

    You can still generate and download proposals manually.
    """)
    send_email_enabled = False
else:
    send_email_enabled = st.checkbox(
        "Send proposal via email after generation",
        value=st.session_state.send_email_enabled,
        key="send_email_checkbox"
    )
    st.session_state.send_email_enabled = send_email_enabled

    if send_email_enabled:
        email_col1, email_col2 = st.columns([2, 1])

        with email_col1:
            recipient_email = st.text_input(
                "Recipient email address",
                value=st.session_state.recipient_email,
                placeholder="client@example.com",
                help="Enter the email address to send the proposal to",
                key="recipient_email_input"
            )
            st.session_state.recipient_email = recipient_email

            # Validate email in real-time
            if recipient_email:
                is_valid, error_msg = validate_email(recipient_email)
                if not is_valid:
                    st.error(f"⚠️ {error_msg}")

        with email_col2:
            st.markdown("&nbsp;")  # Spacer
            st.caption("📨 The proposal will be sent as an attachment immediately after generation.")

st.markdown("---")

# =============================================================================
# GENERATE AND SEND BUTTONS
# =============================================================================
generate_col1, generate_col2 = st.columns([3, 1])

with generate_col1:
    # Determine button label based on email settings
    if send_email_enabled and st.session_state.recipient_email:
        button_label = "🚀 Generate & Send"
    else:
        button_label = "🚀 Generate PDF Proposal" if "PDF" in export_format else "🚀 Generate PowerPoint Proposal"

    # Validate before allowing generation with email
    can_generate = True
    if send_email_enabled:
        if not st.session_state.recipient_email:
            st.warning("⚠️ Please enter a recipient email address to send the proposal.")
            can_generate = False
        else:
            is_valid, _ = validate_email(st.session_state.recipient_email)
            if not is_valid:
                can_generate = False

    if st.button(button_label, type="primary", width="stretch", disabled=not can_generate):
        # Validate proposal data before generating
        errors, warnings = proposal_data.validate()

        if errors:
            st.error("**Validation errors - cannot generate proposal:**")
            for error in errors:
                st.error(f"• {error}")
            st.stop()

        if warnings:
            st.warning("**Data warnings (proposal will still generate):**")
            for warning in warnings:
                st.warning(f"• {warning}")

        # Reset email result
        st.session_state.email_result = None

        with st.spinner("Generating proposal..."):
            try:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                client_name_safe = client_name.replace(' ', '_').replace('/', '-')

                if "PDF" in export_format:
                    # Generate PDF using ReportLab
                    from pdf_proposal_renderer import PDFProposalRenderer
                    renderer = PDFProposalRenderer(proposal_data)
                    output_buffer = renderer.generate()
                    st.session_state.proposal_buffer = output_buffer
                    st.session_state.proposal_filename = f"Glove_Proposal_{client_name_safe}_{timestamp}.pdf"
                    st.session_state.proposal_mime = "application/pdf"
                else:
                    # Generate PowerPoint using template filler
                    from pptx_template_filler import PPTXTemplateFiller
                    filler = PPTXTemplateFiller(proposal_data)
                    output_buffer = filler.generate()
                    st.session_state.proposal_buffer = output_buffer
                    st.session_state.proposal_filename = f"Glove_Proposal_{client_name_safe}_{timestamp}.pptx"
                    st.session_state.proposal_mime = "application/vnd.openxmlformats-officedocument.presentationml.presentation"

                st.success("✅ Proposal generated successfully!")

                # Check file size before attempting email
                if send_email_enabled and st.session_state.recipient_email:
                    file_data = st.session_state.proposal_buffer.getvalue()
                    is_size_valid, size_error = validate_file_size(file_data, st.session_state.proposal_filename)

                    if not is_size_valid:
                        st.error(f"📁 {size_error}")
                        st.session_state.email_result = {
                            "success": False,
                            "error_message": size_error
                        }
                    else:
                        # Send email
                        with st.spinner("Sending email..."):
                            result = send_email_and_update_state(
                                email_service=email_service,
                                recipient_email=st.session_state.recipient_email,
                                client_name=client_name,
                                file_data=file_data,
                                filename=st.session_state.proposal_filename,
                                presentation_id=f"{client_name_safe}_{timestamp}"
                            )

                            if result.success:
                                st.success(f"✅ Email sent successfully to {result.recipient}!")
                            else:
                                st.error(f"❌ Failed to send email: {result.error_message}")

            except Exception as e:
                st.error(f"Error generating proposal: {e}")
                import traceback
                st.code(traceback.format_exc())

with generate_col2:
    # Download button (only shown after generation)
    if st.session_state.proposal_buffer is not None:
        download_label = "📥 Download"
        st.download_button(
            label=download_label,
            data=st.session_state.proposal_buffer.getvalue(),
            file_name=st.session_state.proposal_filename,
            mime=st.session_state.get('proposal_mime', 'application/pdf'),
            type="secondary",
            width="stretch"
        )

# =============================================================================
# EMAIL STATUS DISPLAY
# =============================================================================
if st.session_state.email_result is not None:
    result = st.session_state.email_result
    if result.get("success"):
        st.markdown(f"""
        <div style="padding: 15px; background: #dcfce7; border-radius: 8px; border-left: 4px solid #16a34a;">
            <strong>📧 Email Delivered</strong><br>
            <span style="color: #166534;">Sent to: {result.get('recipient')}</span><br>
            <span style="color: #166534; font-size: 0.9em;">At: {result.get('sent_at', 'N/A')}</span>
        </div>
        """, unsafe_allow_html=True)
    else:
        error_msg = result.get('error_message', 'Unknown error')
        st.markdown(f"""
        <div style="padding: 15px; background: #fef2f2; border-radius: 8px; border-left: 4px solid #dc2626;">
            <strong>❌ Email Delivery Failed</strong><br>
            <span style="color: #991b1b;">{error_msg}</span><br>
            <span style="color: #991b1b; font-size: 0.9em;">The proposal has been preserved - you can download it manually or retry sending.</span>
        </div>
        """, unsafe_allow_html=True)

        # Retry button (shown inline with error status)
        if st.session_state.proposal_buffer is not None and is_email_configured:
            if st.button("🔄 Retry email", type="secondary"):
                with st.spinner("Retrying email..."):
                    file_data = st.session_state.proposal_buffer.getvalue()
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    client_name_safe = client_name.replace(' ', '_').replace('/', '-')

                    retry_result = send_email_and_update_state(
                        email_service=email_service,
                        recipient_email=st.session_state.recipient_email,
                        client_name=client_name,
                        file_data=file_data,
                        filename=st.session_state.proposal_filename,
                        presentation_id=f"{client_name_safe}_{timestamp}"
                    )

                    if retry_result.success:
                        st.success(f"✅ Email sent successfully to {retry_result.recipient}!")
                        st.rerun()
                    else:
                        st.error(f"❌ Failed to send email: {retry_result.error_message}")

# =============================================================================
# FOOTER
# =============================================================================
st.markdown("---")
st.info("""
**Tips:**
- Review and adjust the data in the expandable sections above before generating
- The Fit Score is automatically calculated but can be overridden
- Current costs should be entered for accurate savings calculations
- **PDF (Recommended):** Renders perfectly every time with all graphics intact
- **PowerPoint:** Editable after download, but complex graphics may not display correctly
- **Email Delivery:** Enable email delivery to automatically send the proposal to your client after generation
""")
