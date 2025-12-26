"""
Page 7: Proposal Generator
Generate branded GLOVE PowerPoint proposals from ICHRA analysis
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

# Template path for PPTX (with placeholders)
PPTX_TEMPLATE_PATH = Path(__file__).parent.parent / 'templates' / 'glove_proposal_template.pptx'

# Page config
st.set_page_config(page_title="Proposal Generator", page_icon="📑", layout="wide")

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

# Page header
st.title("📑 Proposal Generator")
st.markdown("Generate a branded GLOVE ICHRA proposal PowerPoint presentation")

# Note: PPTX template check is done at generation time (PDF doesn't need template)

# Check prerequisites
if st.session_state.census_df is None or st.session_state.census_df.empty:
    st.warning("⚠️ No census data loaded. Please complete **Census Input** first.")
    st.info("👉 Go to **1️⃣ Census Input** in the sidebar to upload your census")
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
st.subheader("📋 Client Information")

col1, col2 = st.columns(2)

with col1:
    client_name = st.text_input(
        "Client/Company Name",
        value=st.session_state.get('proposal_client_name', 'ABC Company'),
        help="This will appear on the cover slide",
        key="client_name_input"
    )
    st.session_state.proposal_client_name = client_name

    consultant_name = st.text_input(
        "Consultant Name",
        value=st.session_state.get('proposal_consultant_name', 'Your Name'),
        key="consultant_name_input"
    )
    st.session_state.proposal_consultant_name = consultant_name

with col2:
    proposal_date = st.date_input(
        "Proposal Date",
        value=datetime.now(),
        key="proposal_date_input"
    )

    plan_year = st.selectbox(
        "Plan Year",
        options=[2026, 2027],
        index=0,
        key="plan_year_input"
    )

# =============================================================================
# SECTION 2: FIT SCORE CALCULATION
# =============================================================================
st.markdown("---")
st.subheader("🎯 GLOVE ICHRA Fit Score")

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
use_override = st.checkbox("Override calculated Fit Score", value=False)
if use_override:
    fit_score = st.slider(
        "Manual Fit Score",
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
        score_label = "Strong Fit"
    elif fit_score >= 50:
        score_color = "#f59e0b"  # Amber
        score_label = "Moderate Fit"
    else:
        score_color = "#dc2626"  # Red
        score_label = "Needs Review"

    st.markdown(f"""
    <div style="text-align: center; padding: 20px; background: linear-gradient(135deg, #f8fafc, #e2e8f0); border-radius: 12px; border: 2px solid {score_color};">
        <div style="font-size: 3.5em; font-weight: bold; color: {score_color};">{fit_score}</div>
        <div style="font-size: 1.1em; color: #64748b; margin-top: 5px;">{score_label}</div>
    </div>
    """, unsafe_allow_html=True)

with score_col2:
    st.markdown("**Category Breakdown:**")

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

# =============================================================================
# SECTION 3: PROPOSAL DATA PREVIEW (Editable)
# =============================================================================
st.markdown("---")
st.subheader("📊 Proposal Data Preview")

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
            "Renewal Increase %",
            value=float(proposal_data.renewal_percentage) if proposal_data.renewal_percentage else 0.0,
            min_value=0.0,
            max_value=100.0,
            format="%.1f",
            help="Expected renewal increase percentage"
        )
        proposal_data.renewal_percentage = renewal_pct

    with cov_col2:
        total_renewal = st.number_input(
            "Total Renewal Cost ($)",
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
        st.metric("Covered Lives", proposal_data.covered_lives)
    with metric_col2:
        st.metric("Avg Monthly Premium", f"${proposal_data.avg_monthly_premium:,.0f}")
    with metric_col3:
        st.metric("States", proposal_data.total_states)

with st.expander("📈 Cost Burden (Slide 5)", expanded=False):
    burden_col1, burden_col2, burden_col3 = st.columns(3)

    with burden_col1:
        st.metric("Employees", proposal_data.employee_count)

    with burden_col2:
        st.metric("Total Annual Salaries", f"${proposal_data.total_annual_salaries:,.0f}")

    with burden_col3:
        healthcare_burden = st.number_input(
            "Healthcare Burden ($)",
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

with st.expander("🗺️ Geographic Distribution (Slide 8)", expanded=False):
    st.markdown("**Top States by Employee Count:**")

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

with st.expander("👥 Census Demographics (Slide 9)", expanded=False):
    demo_col1, demo_col2 = st.columns(2)

    with demo_col1:
        st.markdown("**Population Overview:**")
        st.metric("Covered Lives", proposal_data.covered_lives)
        st.metric("Employees", proposal_data.total_employees)
        st.metric("Dependents", proposal_data.total_dependents)

        st.markdown("**Age Statistics:**")
        st.text(f"Average Age: {proposal_data.avg_employee_age:.1f}")
        st.text(f"Age Range: {proposal_data.age_range_min} - {proposal_data.age_range_max}")

    with demo_col2:
        st.markdown("**Family Status Breakdown:**")
        for code, count in proposal_data.family_status_breakdown.items():
            desc = FAMILY_STATUS_CODES.get(code, code)
            pct = (count / proposal_data.total_employees * 100) if proposal_data.total_employees > 0 else 0
            st.text(f"{code} ({desc}): {count} ({pct:.1f}%)")

        st.markdown("**Dependents:**")
        st.text(f"Spouses: {proposal_data.total_spouses}")
        st.text(f"Children: {proposal_data.total_children}")

with st.expander("💰 Cost Analysis (Slides 9-10)", expanded=False):
    cost_col1, cost_col2 = st.columns(2)

    with cost_col1:
        st.markdown("**Current Group Plan Costs:**")

        current_er_monthly = st.number_input(
            "Current ER Monthly Total",
            value=float(proposal_data.current_er_monthly),
            min_value=0.0,
            format="%.2f"
        )
        proposal_data.current_er_monthly = current_er_monthly
        proposal_data.current_er_annual = current_er_monthly * 12

        current_ee_monthly = st.number_input(
            "Current EE Monthly Total",
            value=float(proposal_data.current_ee_monthly),
            min_value=0.0,
            format="%.2f"
        )
        proposal_data.current_ee_monthly = current_ee_monthly
        proposal_data.current_ee_annual = current_ee_monthly * 12

        st.metric(
            "Current Total Annual",
            f"${(proposal_data.current_er_annual + proposal_data.current_ee_annual):,.0f}"
        )

    with cost_col2:
        st.markdown("**Proposed ICHRA Costs:**")

        proposed_er_monthly = st.number_input(
            "Proposed ER Monthly",
            value=float(proposal_data.proposed_er_monthly),
            min_value=0.0,
            format="%.2f"
        )
        proposal_data.proposed_er_monthly = proposed_er_monthly
        proposal_data.proposed_er_annual = proposed_er_monthly * 12

        st.metric("Proposed ER Annual", f"${proposal_data.proposed_er_annual:,.0f}")

        # Calculate savings
        if proposal_data.current_er_annual > 0:
            proposal_data.annual_savings = proposal_data.current_er_annual - proposal_data.proposed_er_annual
            proposal_data.savings_percentage = (proposal_data.annual_savings / proposal_data.current_er_annual) * 100

            savings_color = "normal" if proposal_data.annual_savings >= 0 else "inverse"
            st.metric(
                "Potential Annual Savings",
                f"${proposal_data.annual_savings:,.0f}",
                delta=f"{proposal_data.savings_percentage:.1f}%",
                delta_color=savings_color
            )

with st.expander("📊 ICHRA Evaluation Workflow (Slide 13 - Final)", expanded=True):
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
st.subheader("🎨 Generate Proposal")

# Note: Healthcare burden is calculated as 30% of total annual salaries
# in ProposalData.from_session_state() - we preserve that calculation here

# Summary before generation
st.markdown("**Proposal Summary:**")
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
st.markdown("**Export Format:**")
export_format = st.radio(
    "Choose format",
    options=["PDF (Recommended)", "PowerPoint"],
    horizontal=True,
    help="PDF renders perfectly every time. PowerPoint is editable but some graphics may not display correctly.",
    label_visibility="collapsed"
)

st.markdown("---")

generate_col1, generate_col2 = st.columns([2, 1])

with generate_col1:
    button_label = "🚀 Generate PDF Proposal" if "PDF" in export_format else "🚀 Generate PowerPoint Proposal"
    if st.button(button_label, type="primary", use_container_width=True):
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
                    st.session_state.proposal_filename = f"GLOVE_Proposal_{client_name_safe}_{timestamp}.pdf"
                    st.session_state.proposal_mime = "application/pdf"
                else:
                    # Generate PowerPoint using template filler
                    from pptx_template_filler import PPTXTemplateFiller
                    filler = PPTXTemplateFiller(proposal_data)
                    output_buffer = filler.generate()
                    st.session_state.proposal_buffer = output_buffer
                    st.session_state.proposal_filename = f"GLOVE_Proposal_{client_name_safe}_{timestamp}.pptx"
                    st.session_state.proposal_mime = "application/vnd.openxmlformats-officedocument.presentationml.presentation"

                st.success("✅ Proposal generated successfully!")

            except Exception as e:
                st.error(f"Error generating proposal: {e}")
                import traceback
                st.code(traceback.format_exc())

with generate_col2:
    # Download button (only shown after generation)
    if st.session_state.proposal_buffer is not None:
        download_label = "📥 Download PDF" if st.session_state.proposal_filename.endswith('.pdf') else "📥 Download PowerPoint"
        st.download_button(
            label=download_label,
            data=st.session_state.proposal_buffer.getvalue(),
            file_name=st.session_state.proposal_filename,
            mime=st.session_state.get('proposal_mime', 'application/pdf'),
            type="primary",
            use_container_width=True
        )

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
""")
