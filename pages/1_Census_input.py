"""
Census Input Page - Streamlined Single Format
Handles employee census upload with ZIP codes, DOBs, and Family Status codes
"""

import streamlit as st
import pandas as pd
import logging
import time

# Configure logging to show in console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s',
    datefmt='%H:%M:%S'
)

from database import get_database_connection
from utils import CensusProcessor, ContributionComparison, render_feedback_sidebar
from constants import FAMILY_STATUS_CODES
# PDF renderer imported lazily when needed (requires playwright)


# PDF template version - increment to invalidate cache when template changes
_PDF_TEMPLATE_VERSION = 4

# Cache expensive chart generation separately (must be at module level for st.cache_data)
@st.cache_data(show_spinner=False)
def _generate_charts_cached(_emp_hash, _dep_hash):
    """Cache expensive chart generation separately from client_name."""
    from visualization_helpers import (
        generate_age_distribution_chart,
        generate_state_distribution_chart,
        generate_family_composition_chart,
        generate_dependent_age_distribution_chart
    )

    emp_df = st.session_state.get('census_df', pd.DataFrame())
    dep_df = st.session_state.get('dependents_df', pd.DataFrame())

    chart_images = {}
    try:
        chart_images['age_dist'] = generate_age_distribution_chart(emp_df, return_image=True)
    except Exception:
        chart_images['age_dist'] = None

    try:
        chart_images['state'] = generate_state_distribution_chart(emp_df, return_image=True)
    except Exception:
        chart_images['state'] = None

    try:
        chart_images['family_status'] = generate_family_composition_chart(emp_df, return_image=True)
    except Exception:
        chart_images['family_status'] = None

    if dep_df is not None and not dep_df.empty:
        try:
            chart_images['dependent_age'] = generate_dependent_age_distribution_chart(dep_df, return_image=True)
        except Exception:
            chart_images['dependent_age'] = None

    return chart_images


@st.cache_data(show_spinner=False)
def _get_plan_availability_cached(ra_hash, _db_available, ra_data_json: str):
    """Cache plan availability query separately from client_name.

    Note: ra_hash is used as cache key (no underscore prefix).
    ra_data_json contains the actual rating area data to query.
    """
    import json
    ra_data = json.loads(ra_data_json)
    emp_df = pd.DataFrame(ra_data)
    db = st.session_state.get('db')

    if emp_df is None or emp_df.empty or 'rating_area_id' not in emp_df.columns or db is None:
        return pd.DataFrame()

    ra_counts = emp_df.groupby(['state', 'county', 'rating_area_id']).size().reset_index(name='employees')
    ra_counts = ra_counts[ra_counts['rating_area_id'].notna()]

    if ra_counts.empty:
        return pd.DataFrame()

    ra_counts['rating_area_id'] = ra_counts['rating_area_id'].astype(int)
    states = ra_counts['state'].unique().tolist()
    rating_areas = [f"Rating Area {ra}" for ra in ra_counts['rating_area_id'].unique().tolist()]

    query = """
    SELECT
        SUBSTRING(p.hios_plan_id, 6, 2) as state,
        r.rating_area_id,
        COUNT(DISTINCT p.hios_plan_id) as plan_count
    FROM rbis_insurance_plan_20251019202724 p
    JOIN rbis_insurance_plan_variant_20251019202724 v ON v.hios_plan_id = p.hios_plan_id
    JOIN rbis_insurance_plan_base_rates_20251019202724 r ON r.plan_id = p.hios_plan_id
    WHERE p.market_coverage = 'Individual'
      AND p.plan_effective_date = '2026-01-01'
      AND v.csr_variation_type IN ('Exchange variant (no CSR)', 'Non-Exchange variant')
      AND SUBSTRING(p.hios_plan_id, 6, 2) IN %s
      AND r.rating_area_id IN %s
    GROUP BY SUBSTRING(p.hios_plan_id, 6, 2), r.rating_area_id
    """
    try:
        plan_counts_df = pd.read_sql(query, db.engine, params=(tuple(states), tuple(rating_areas)))
        if not plan_counts_df.empty:
            plan_counts_df['rating_area_num'] = plan_counts_df['rating_area_id'].str.extract(r'(\d+)').astype(int)
            plan_availability_df = ra_counts.merge(
                plan_counts_df[['state', 'rating_area_num', 'plan_count']],
                left_on=['state', 'rating_area_id'],
                right_on=['state', 'rating_area_num'],
                how='left'
            )
            plan_availability_df = plan_availability_df[['state', 'county', 'rating_area_id', 'employees', 'plan_count']]
            plan_availability_df['plan_count'] = plan_availability_df['plan_count'].fillna(0).astype(int)
            return plan_availability_df
    except Exception:
        pass

    return pd.DataFrame()


def _get_ra_data_json() -> str:
    """Get rating area data as JSON for cache key purposes."""
    import json
    emp_df = st.session_state.get('census_df', pd.DataFrame())
    if emp_df is None or emp_df.empty:
        return "[]"
    cols = ['state', 'county', 'rating_area_id']
    available_cols = [c for c in cols if c in emp_df.columns]
    if not available_cols or 'rating_area_id' not in available_cols:
        return "[]"
    return emp_df[available_cols].dropna().to_json(orient='records')


def generate_census_pdf_cached(_employees_df_hash, _dependents_df_hash, client_name, _db_available, _ra_data_hash, _template_version):
    """Generate PDF. Charts and plan data are cached separately so client_name changes are fast."""
    from pdf_census_renderer import generate_census_analysis_pdf

    # Reconstruct dataframes from session state
    emp_df = st.session_state.get('census_df', pd.DataFrame())
    dep_df = st.session_state.get('dependents_df', pd.DataFrame())

    # Get cached charts (expensive - cached by data hash, NOT client_name)
    chart_images = _generate_charts_cached(_employees_df_hash, _dependents_df_hash)

    # Get cached plan availability (expensive - cached by data hash, NOT client_name)
    ra_data_json = _get_ra_data_json()
    plan_availability_df = _get_plan_availability_cached(_ra_data_hash, _db_available, ra_data_json)

    display_name = client_name if client_name else 'Client'

    pdf_buffer = generate_census_analysis_pdf(
        employees_df=emp_df,
        dependents_df=dep_df,
        plan_availability_df=plan_availability_df,
        client_name=display_name,
        chart_images=chart_images
    )

    return pdf_buffer.getvalue()


def get_census_pdf_filename(client_name: str) -> str:
    """Generate filename with current timestamp (not cached)."""
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if client_name:
        safe_name = client_name.replace(' ', '_').replace('/', '-')
        return f"census_analysis_{safe_name}_{timestamp}.pdf"
    else:
        return f"census_analysis_{timestamp}.pdf"


# Page config
st.set_page_config(page_title="Census Input", page_icon="📊", layout="wide")

# Custom CSS to match app branding
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&family=Inter:wght@400;700&display=swap');

    .stApp {
        font-family: 'Poppins', sans-serif;
        background-color: #ffffff;
    }

    [data-testid="stSidebar"] {
        background-color: #F0F4FA;
    }

    /* Sidebar navigation links */
    [data-testid="stSidebarNav"] a {
        background-color: transparent !important;
    }
    [data-testid="stSidebarNav"] a[aria-selected="true"] {
        background-color: #E8F1FD !important;
        border-left: 3px solid #0047AB !important;
    }
    [data-testid="stSidebarNav"] a:hover {
        background-color: #E8F1FD !important;
    }

    /* Sidebar buttons */
    [data-testid="stSidebar"] button {
        background-color: #E8F1FD !important;
        border: 1px solid #B3D4FC !important;
        color: #0047AB !important;
    }
    [data-testid="stSidebar"] button:hover {
        background-color: #B3D4FC !important;
        border-color: #0047AB !important;
    }

    /* Info boxes in sidebar */
    [data-testid="stSidebar"] [data-testid="stAlert"] {
        background-color: #E8F1FD !important;
        border: 1px solid #B3D4FC !important;
        color: #003d91 !important;
    }

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

    .upload-hint {
        font-size: 14px;
        color: #667085;
        margin-bottom: 16px;
    }

    .template-section {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 8px;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'db' not in st.session_state:
    logging.info("SESSION: Initializing database connection...")
    db_start = time.time()
    st.session_state.db = get_database_connection()
    logging.info(f"SESSION: Database connection established in {time.time() - db_start:.2f}s")

if 'census_df' not in st.session_state:
    st.session_state.census_df = None

if 'dependents_df' not in st.session_state:
    st.session_state.dependents_df = None

# Cache hashes for PDF generation (computed once when census is loaded)
if 'census_emp_hash' not in st.session_state:
    st.session_state.census_emp_hash = 0
if 'census_dep_hash' not in st.session_state:
    st.session_state.census_dep_hash = 0
if 'census_ra_hash' not in st.session_state:
    st.session_state.census_ra_hash = 0

# Header
st.markdown("""
<div class="hero-section">
    <div class="hero-title">📊 Census Input</div>
    <p class="hero-subtitle">Upload employee census data to begin ICHRA analysis</p>
</div>
""", unsafe_allow_html=True)

# ==============================================================================
# UPLOAD SECTION
# ==============================================================================

# Template download inline with hint text
template_csv = CensusProcessor.create_new_census_template()
col1, col2 = st.columns([4, 1])
with col1:
    st.markdown('<p class="upload-hint">Upload a CSV with employee demographics, ZIP codes, and family status.</p>', unsafe_allow_html=True)
with col2:
    st.download_button(
        label="📥 Template",
        data=template_csv,
        file_name="census_template.csv",
        mime="text/csv",
        help="Download CSV template with example data",
        use_container_width=True
    )

# Format requirements in expander
with st.expander("View format requirements"):
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("""
        **Required columns:**
        - `Employee Number` — Unique ID
        - `Home Zip` — 5-digit ZIP
        - `Home State` — 2-letter code
        - `Family Status` — EE, ES, EC, or F
        - `EE DOB` — Employee date of birth
        """)
    with col_b:
        st.markdown("""
        **Optional columns:**
        - `Spouse DOB` — For ES/F status
        - `Dep 2-6 DOB` — Child DOBs for EC/F
        - `Current EE Monthly` — Employee contribution
        - `Current ER Monthly` — Employer contribution
        """)

# Check if census is already loaded in session state
if st.session_state.census_df is not None:
    # Compact loaded state with replace option
    load_col1, load_col2 = st.columns([4, 1])
    with load_col1:
        dep_count = len(st.session_state.dependents_df) if st.session_state.dependents_df is not None and not st.session_state.dependents_df.empty else 0
        st.success(f"Census loaded: **{len(st.session_state.census_df)}** employees, **{dep_count}** dependents")
    with load_col2:
        if st.button("Replace", type="secondary", use_container_width=True):
            st.session_state.census_df = None
            st.session_state.dependents_df = None
            st.session_state.contribution_analysis = {}
            st.rerun()

    st.markdown("---")

    employees_df = st.session_state.census_df
    dependents_df = st.session_state.dependents_df if st.session_state.dependents_df is not None else pd.DataFrame()

    # Check for per-employee contribution data
    if ContributionComparison.has_individual_contributions(employees_df):
        contrib_totals = ContributionComparison.aggregate_contribution_totals(employees_df)
        st.info(f"Contribution data found for **{contrib_totals['employees_with_data']}** employees — EE: **${contrib_totals['total_current_ee_monthly']:,.0f}/mo**, ER: **${contrib_totals['total_current_er_monthly']:,.0f}/mo**")

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total employees", len(employees_df))

    with col2:
        num_deps = len(dependents_df) if not dependents_df.empty else 0
        st.metric("Total dependents", num_deps)

    with col3:
        total_lives = len(employees_df) + num_deps
        st.metric("Covered lives", total_lives)

    with col4:
        unique_states = employees_df['state'].nunique()
        st.metric("States", unique_states)

    # Covered lives age metrics
    col1, col2, col3 = st.columns(3)

    # Calculate ages of all covered lives
    if not dependents_df.empty:
        all_ages = pd.concat([employees_df['age'], dependents_df['age']])
    else:
        all_ages = employees_df['age']

    with col1:
        avg_age_covered = all_ages.mean()
        st.metric("Avg age of covered lives", f"{avg_age_covered:.1f} yrs")

    with col2:
        median_age_covered = all_ages.median()
        st.metric("Median age of covered lives", f"{median_age_covered:.1f} yrs")

    with col3:
        min_age = int(all_ages.min())
        max_age = int(all_ages.max())
        st.metric("Age range of covered lives", f"{min_age} - {max_age} yrs")

    # Export Section
    st.markdown("---")
    export_col1, export_col2, export_col3 = st.columns([3, 1, 1])
    with export_col1:
        if 'client_name' not in st.session_state:
            st.session_state.client_name = ''
        st.text_input(
            "Client name",
            placeholder="For PDF header",
            key="client_name",
            help="Appears in PDF header and filename"
        )

    with export_col2:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)

        # Use pre-computed hashes from session state
        emp_hash = st.session_state.get('census_emp_hash', 0)
        dep_hash = st.session_state.get('census_dep_hash', 0)
        ra_hash = st.session_state.get('census_ra_hash', 0)
        client_name = st.session_state.get('client_name', '').strip()
        db_available = st.session_state.get('db') is not None

        # Check if we need to regenerate (data or client_name changed)
        current_pdf_key = (emp_hash, dep_hash, ra_hash, client_name)
        cached_pdf_key = st.session_state.get('_pdf_cache_key_nav')
        pdf_ready = cached_pdf_key == current_pdf_key and '_pdf_data_nav' in st.session_state

        if pdf_ready:
            # PDF is ready - show download button
            st.download_button(
                label="📄 Export PDF",
                data=st.session_state['_pdf_data_nav'],
                file_name=st.session_state.get('_pdf_filename_nav', 'census_analysis.pdf'),
                mime="application/pdf",
                type="secondary",
                use_container_width=True,
                key="pdf_download_nav"
            )
        else:
            # Need to generate - show generate button
            if st.button("📄 Generate PDF", type="secondary", use_container_width=True, key="pdf_generate_nav"):
                try:
                    with st.spinner("Generating PDF..."):
                        pdf_data = generate_census_pdf_cached(emp_hash, dep_hash, client_name, db_available, ra_hash, _PDF_TEMPLATE_VERSION)
                        filename = get_census_pdf_filename(client_name)
                        st.session_state['_pdf_data_nav'] = pdf_data
                        st.session_state['_pdf_filename_nav'] = filename
                        st.session_state['_pdf_cache_key_nav'] = current_pdf_key
                        st.rerun()
                except Exception as e:
                    st.error(f"Error generating PDF: {str(e)}")
                    logging.exception("PDF generation error")

    with export_col3:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        try:
            from pptx_census_report import generate_census_report_from_session, get_census_report_filename
            pptx_data = generate_census_report_from_session(st.session_state)
            client_name = st.session_state.get('client_name', '').strip()
            filename = get_census_report_filename(client_name)
            st.download_button(
                label="📊 Download slide",
                data=pptx_data,
                file_name=filename,
                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                type="secondary",
                use_container_width=True,
                key="pptx_download_nav"
            )
        except Exception as e:
            if st.button("📊 Download slide", type="secondary", use_container_width=True, key="pptx_error_nav", disabled=True):
                pass
            st.caption(f"Error: {str(e)}")

    st.markdown("---")

    tab1, tab2, tab3, tab4 = st.tabs(["👥 Employees", "👶 Dependents", "📍 Geography", "📊 Demographics"])

    with tab1:
        st.markdown("### 📊 Employee demographics")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Total employees:** {len(employees_df)}")
            st.markdown(f"**Average age:** {employees_df['age'].mean():.1f} years")
            st.markdown(f"**Median age:** {employees_df['age'].median():.1f} years")

        with col2:
            st.markdown("**Age range:**")
            st.markdown(f"- Youngest: {employees_df['age'].min():.0f} years")
            st.markdown(f"- Oldest: {employees_df['age'].max():.0f} years")

        # Employee Only (EE) Class Statistics
        ee_employees = employees_df[employees_df['family_status'] == 'EE']
        if len(ee_employees) > 0:
            st.markdown("---")
            st.markdown("### 👤 Employee only (EE) class")

            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**Count:** {len(ee_employees)} employees")
                st.markdown(f"**Average age:** {ee_employees['age'].mean():.1f} years")
                st.markdown(f"**Median age:** {ee_employees['age'].median():.1f} years")

            with col2:
                st.markdown("**Age range:**")
                st.markdown(f"- Youngest: {ee_employees['age'].min():.0f} years")
                st.markdown(f"- Oldest: {ee_employees['age'].max():.0f} years")

        st.markdown("---")
        st.markdown("### 👨‍👩‍👧‍👦 Family status breakdown")
        status_counts = employees_df['family_status'].value_counts()
        for status, count in status_counts.items():
            status_name = FAMILY_STATUS_CODES.get(status, status)
            pct = (count / len(employees_df)) * 100
            st.markdown(f"- **{status_name}:** {count} employees ({pct:.1f}%)")

        st.markdown("---")
        st.markdown("### 📋 Employee data")
        display_cols = ['employee_id', 'first_name', 'last_name', 'age', 'state', 'county', 'family_status']
        if 'current_ee_monthly' in employees_df.columns:
            display_cols.extend(['current_ee_monthly', 'current_er_monthly'])
        st.dataframe(employees_df[display_cols], width="stretch")

    with tab2:
        if not dependents_df.empty:
            # Calculate key metrics
            total_deps = len(dependents_df)
            total_lives = len(employees_df) + total_deps
            coverage_burden = total_lives / len(employees_df)
            avg_age = dependents_df['age'].mean()
            median_age = dependents_df['age'].median()
            youngest = int(dependents_df['age'].min())
            oldest = int(dependents_df['age'].max())
            rel_counts = dependents_df['relationship'].value_counts()

            # Styled header
            st.markdown("""
            <p style="font-size: 18px; font-weight: 700; color: #101828; margin-bottom: 16px;">
                Dependent Overview
            </p>
            """, unsafe_allow_html=True)

            # Key metrics row
            metric_cols = st.columns(4)
            metrics = [
                ("Total Dependents", f"{total_deps}", "#3b82f6"),
                ("Coverage Burden", f"{coverage_burden:.2f}:1", "#8b5cf6"),
                ("Average Age", f"{avg_age:.1f}", "#10b981"),
                ("Age Range", f"{youngest}–{oldest}", "#0047AB"),
            ]

            for col, (label, value, color) in zip(metric_cols, metrics):
                with col:
                    st.markdown(f"""
                    <div style="background: {color}10; border-left: 4px solid {color}; border-radius: 8px; padding: 12px 16px;">
                        <p style="font-size: 12px; color: #6b7280; margin: 0; text-transform: uppercase; letter-spacing: 0.5px;">{label}</p>
                        <p style="font-size: 24px; font-weight: 700; color: #101828; margin: 4px 0 0 0; font-family: 'Inter', sans-serif;">{value}</p>
                    </div>
                    """, unsafe_allow_html=True)

            st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)

            # Two-column layout for relationship breakdown and age stats
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("""
                <p style="font-size: 14px; font-weight: 600; color: #374151; margin-bottom: 12px;">
                    By Relationship
                </p>
                """, unsafe_allow_html=True)

                # Progress bars for relationship breakdown
                max_count = rel_counts.max() if not rel_counts.empty else 1
                rel_colors = {'spouse': '#ec4899', 'child': '#3b82f6'}

                for rel, count in rel_counts.items():
                    pct = (count / total_deps) * 100
                    bar_pct = (count / max_count) * 100
                    color = rel_colors.get(rel, '#6b7280')

                    st.markdown(f"""
                    <div style="margin-bottom: 12px;">
                        <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                            <span style="font-size: 14px; color: #374151;">{rel.title()}s</span>
                            <span style="font-size: 14px; font-weight: 600; color: #101828;">{count} <span style="color: #9ca3af; font-weight: 400;">({pct:.0f}%)</span></span>
                        </div>
                        <div style="background: #e5e7eb; height: 8px; border-radius: 9999px;">
                            <div style="background: {color}; height: 8px; border-radius: 9999px; width: {bar_pct}%;"></div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

            with col2:
                st.markdown("""
                <p style="font-size: 14px; font-weight: 600; color: #374151; margin-bottom: 12px;">
                    Age Statistics
                </p>
                """, unsafe_allow_html=True)

                age_stats = [
                    ("Youngest", f"{youngest} years"),
                    ("Oldest", f"{oldest} years"),
                    ("Average", f"{avg_age:.1f} years"),
                    ("Median", f"{median_age:.1f} years"),
                ]

                for label, value in age_stats:
                    st.markdown(f"""
                    <div style="display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #f3f4f6;">
                        <span style="font-size: 14px; color: #6b7280;">{label}</span>
                        <span style="font-size: 14px; font-weight: 500; color: #374151;">{value}</span>
                    </div>
                    """, unsafe_allow_html=True)

            # Coverage burden footnote
            st.markdown(f"""
            <p style="font-size: 12px; color: #9ca3af; margin-top: 16px; font-style: italic;">
                Coverage burden = (employees + dependents) ÷ employees = ({len(employees_df)} + {total_deps}) ÷ {len(employees_df)} = {coverage_burden:.2f} covered lives per employee
            </p>
            """, unsafe_allow_html=True)

            st.markdown("<hr style='border: none; border-top: 1px solid #e5e7eb; margin: 20px 0;'>", unsafe_allow_html=True)

            # Children analysis
            children_df = dependents_df[dependents_df['relationship'] == 'child']
            spouses_df = dependents_df[dependents_df['relationship'] == 'spouse']

            if not children_df.empty:
                st.markdown("---")
                st.markdown("### 👧👦 Children analysis")

                # Get employees with children
                employees_with_children = employees_df[employees_df['family_status'].isin(['EC', 'F'])]

                col1, col2 = st.columns(2)

                with col1:
                    st.markdown("**Overall statistics:**")
                    st.markdown(f"- Total children: {len(children_df)}")
                    st.markdown(f"- Families with children: {len(employees_with_children)}")
                    if len(employees_with_children) > 0:
                        avg_children = len(children_df) / len(employees_with_children)
                        st.markdown(f"- Avg children per family: {avg_children:.1f}")

                with col2:
                    st.markdown("**Age statistics:**")
                    st.markdown(f"- Average Age: {children_df['age'].mean():.1f} years")
                    st.markdown(f"- Median Age: {children_df['age'].median():.1f} years")
                    st.markdown(f"- Age Range: {children_df['age'].min():.0f} - {children_df['age'].max():.0f} years")

                # Breakdown by family type
                st.markdown("---")
                st.markdown("### 📊 Children by family type")

                # Employee + Children (EC)
                ec_employees = employees_df[employees_df['family_status'] == 'EC']
                if len(ec_employees) > 0:
                    ec_children = children_df[children_df['employee_id'].isin(ec_employees['employee_id'])]
                    st.markdown("**Employee + Children (EC):**")
                    st.markdown(f"- Families: {len(ec_employees)}")
                    st.markdown(f"- Total Children: {len(ec_children)}")
                    if len(ec_children) > 0:
                        avg_ec = len(ec_children) / len(ec_employees)
                        st.markdown(f"- Avg per family: {avg_ec:.1f}")
                        st.markdown(f"- Avg Age: {ec_children['age'].mean():.1f} years | Median: {ec_children['age'].median():.1f} years")
                        st.markdown(f"- Age Range: {int(ec_children['age'].min())} - {int(ec_children['age'].max())} years")
                else:
                    st.markdown("**Employee + Children (EC):** No EC families in census")

                # Full Family (F)
                f_employees = employees_df[employees_df['family_status'] == 'F']
                if len(f_employees) > 0:
                    f_children = children_df[children_df['employee_id'].isin(f_employees['employee_id'])]
                    st.markdown("**Full Family (F - Employee + Spouse + Children):**")
                    st.markdown(f"- Families: {len(f_employees)}")
                    st.markdown(f"- Total Children: {len(f_children)}")
                    if len(f_children) > 0:
                        avg_f = len(f_children) / len(f_employees)
                        st.markdown(f"- Avg per family: {avg_f:.1f}")
                        st.markdown(f"- Avg Age: {f_children['age'].mean():.1f} years | Median: {f_children['age'].median():.1f} years")
                        st.markdown(f"- Age Range: {int(f_children['age'].min())} - {int(f_children['age'].max())} years")
                else:
                    st.markdown("**Full Family (F):** No F families in census")

            # Spouse analysis
            if not spouses_df.empty:
                st.markdown("---")
                st.markdown("### 💑 Spouse analysis")

                # Get employees with spouses
                employees_with_spouses = employees_df[employees_df['family_status'].isin(['ES', 'F'])]

                col1, col2 = st.columns(2)

                with col1:
                    st.markdown("**Coverage statistics:**")
                    st.markdown(f"- Total spouses: {len(spouses_df)}")
                    st.markdown(f"- Families with spouse coverage: {len(employees_with_spouses)}")

                with col2:
                    st.markdown("**Overall age statistics:**")
                    st.markdown(f"- Average Age: {spouses_df['age'].mean():.1f} years")
                    st.markdown(f"- Median Age: {spouses_df['age'].median():.1f} years")

                st.markdown("---")
                st.markdown("**By family type:**")

                # Employee + Spouse (ES)
                es_employees = employees_df[employees_df['family_status'] == 'ES']
                if len(es_employees) > 0:
                    es_spouses = spouses_df[spouses_df['employee_id'].isin(es_employees['employee_id'])]
                    st.markdown(f"**Employee + Spouse (ES):**")
                    st.markdown(f"- Count: {len(es_spouses)} spouses")
                    if len(es_spouses) > 0:
                        st.markdown(f"- Avg Age: {es_spouses['age'].mean():.1f} years | Median: {es_spouses['age'].median():.1f} years")
                        st.markdown(f"- Age Range: {es_spouses['age'].min():.0f} - {es_spouses['age'].max():.0f} years")

                # Full Family (F)
                f_employees = employees_df[employees_df['family_status'] == 'F']
                if len(f_employees) > 0:
                    f_spouses = spouses_df[spouses_df['employee_id'].isin(f_employees['employee_id'])]
                    st.markdown(f"**Full Family (F):**")
                    st.markdown(f"- Count: {len(f_spouses)} spouses")
                    if len(f_spouses) > 0:
                        st.markdown(f"- Avg Age: {f_spouses['age'].mean():.1f} years | Median: {f_spouses['age'].median():.1f} years")
                        st.markdown(f"- Age Range: {f_spouses['age'].min():.0f} - {f_spouses['age'].max():.0f} years")

            st.markdown("---")
            st.markdown("### 📋 Dependent data")
            st.dataframe(dependents_df, width="stretch")
        else:
            st.info("No dependents in this census (all employees have Family Status = EE)")

    with tab3:
        # Geographic distribution
        st.markdown("**Employees by State:**")
        state_counts = employees_df['state'].value_counts()
        for state, count in state_counts.items():
            pct = (count / len(employees_df)) * 100
            st.markdown(f"- **{state}:** {count} employees ({pct:.1f}%)")

        st.markdown("---")
        st.markdown("**Employees by County:**")
        county_counts = employees_df.groupby(['state', 'county']).size().reset_index(name='count')
        county_counts = county_counts.sort_values('count', ascending=False)
        st.dataframe(county_counts, width="stretch", hide_index=True)

        # Plan availability by rating area
        st.markdown("---")
        st.markdown("### 📋 Plan availability by rating area")
        st.caption("Count of Individual marketplace plans available in each rating area")

        # Use cached plan availability data (same cache as PDF generation)
        ra_hash = st.session_state.get('census_ra_hash', 0)
        db_available = st.session_state.get('db') is not None

        if 'rating_area_id' in employees_df.columns and db_available:
            # Get cached plan availability (no DB query on every keystroke!)
            ra_data_json = _get_ra_data_json()
            plan_availability_df = _get_plan_availability_cached(ra_hash, db_available, ra_data_json)

            if not plan_availability_df.empty:
                display_df = plan_availability_df.copy()
                display_df = display_df.sort_values(['state', 'county', 'rating_area_id'])
                display_df.columns = ['State', 'County', 'Rating Area', 'Employees', 'Plans Available']
                st.dataframe(display_df, width="stretch", hide_index=True)
            else:
                st.info("No plan data available")
        else:
            st.info("Rating area data not available. Ensure census has been processed.")

    with tab4:
        import plotly.express as px

        # Diverse accessible color palette (high contrast between adjacent segments)
        CHART_COLORS = ['#0047AB', '#f59e0b', '#10b981', '#8b5cf6', '#ef4444', '#06b6d4', '#f97316', '#6366f1']

        # Age distribution chart
        st.markdown("### Age distribution")
        col1, col2 = st.columns(2)

        with col1:
            age_bins = [0, 30, 40, 50, 60, 100]
            age_labels = ['Under 30', '30-39', '40-49', '50-59', '60+']

            age_col = 'employee_age' if 'employee_age' in employees_df.columns else 'age'
            census_with_age_group = employees_df.copy()
            census_with_age_group['age_group'] = pd.cut(
                census_with_age_group[age_col],
                bins=age_bins,
                labels=age_labels,
                right=False
            )

            age_dist = census_with_age_group['age_group'].value_counts().sort_index()

            fig = px.pie(
                values=age_dist.values,
                names=age_dist.index,
                title='Employee age distribution',
                color_discrete_sequence=CHART_COLORS
            )
            st.plotly_chart(fig, width='stretch')

        with col2:
            # State distribution bar chart
            state_dist = employees_df['state'].value_counts()

            fig = px.bar(
                x=state_dist.index,
                y=state_dist.values,
                title='Employees by State',
                labels={'x': 'State', 'y': 'Number of employees'},
                color_discrete_sequence=['#0047AB']
            )
            st.plotly_chart(fig, width='stretch')

        # Family status distribution
        if 'family_status' in employees_df.columns:
            st.markdown("### Family status distribution")

            family_counts = employees_df['family_status'].value_counts()
            family_labels = [f"{code} ({FAMILY_STATUS_CODES.get(code, code)})" for code in family_counts.index]

            col1, col2 = st.columns([2, 1])

            with col1:
                fig = px.pie(
                    values=family_counts.values,
                    names=family_labels,
                    title='Employees by family status',
                    color_discrete_sequence=CHART_COLORS
                )
                st.plotly_chart(fig, width='stretch')

            with col2:
                st.markdown("**Family Status Breakdown:**")
                for code, count in family_counts.items():
                    pct = count / len(employees_df) * 100
                    desc = FAMILY_STATUS_CODES.get(code, code)
                    st.markdown(f"- **{code}** ({desc}): {count} ({pct:.1f}%)")

        # Dependent demographics (if present)
        if not dependents_df.empty:
            st.markdown("### Dependent demographics")

            dep_col1, dep_col2 = st.columns(2)

            with dep_col1:
                rel_counts = dependents_df['relationship'].value_counts()

                fig = px.pie(
                    values=rel_counts.values,
                    names=[rel.title() + 's' for rel in rel_counts.index],
                    title='Dependents by relationship',
                    color_discrete_sequence=CHART_COLORS
                )
                st.plotly_chart(fig, width='stretch')

            with dep_col2:
                dependents_with_age_group = dependents_df.copy()

                dep_age_bins = [0, 5, 13, 18, 21, 30, 40, 50, 100]
                dep_age_labels = ['0-4', '5-12', '13-17', '18-20', '21-29', '30-39', '40-49', '50+']

                dependents_with_age_group['age_group'] = pd.cut(
                    dependents_with_age_group['age'],
                    bins=dep_age_bins,
                    labels=dep_age_labels,
                    right=False
                )

                dep_age_dist = dependents_with_age_group['age_group'].value_counts().sort_index()

                fig = px.bar(
                    x=dep_age_dist.index,
                    y=dep_age_dist.values,
                    title='Dependent age distribution',
                    labels={'x': 'Age group', 'y': 'Number of dependents'},
                    color_discrete_sequence=['#0891b2']
                )
                st.plotly_chart(fig, width='stretch')

        # Rating area distribution
        st.markdown("### Geographic distribution")

        col1, col2 = st.columns(2)

        with col1:
            ra_counts = employees_df.groupby(['state', 'rating_area_id']).size().reset_index(name='count')
            ra_counts = ra_counts.sort_values(['state', 'rating_area_id'])

            st.markdown("**Employees by Rating Area:**")
            st.dataframe(ra_counts, width='stretch', hide_index=True)

        with col2:
            county_counts = employees_df['county'].value_counts().head(10)

            fig = px.bar(
                x=county_counts.values,
                y=county_counts.index,
                orientation='h',
                title='Top 10 counties by employee count',
                labels={'x': 'Number of employees', 'y': 'County'},
                color_discrete_sequence=['#6366f1']
            )
            fig.update_layout(yaxis={'categoryorder': 'total ascending'})
            st.plotly_chart(fig, width='stretch')

else:
    # No census loaded - show file uploader
    # Rate limiting for file uploads
    import time
    MAX_UPLOADS_PER_HOUR = 20
    UPLOAD_WINDOW_SECONDS = 3600  # 1 hour

    if 'upload_timestamps' not in st.session_state:
        st.session_state.upload_timestamps = []

    # Clean old timestamps
    current_time = time.time()
    st.session_state.upload_timestamps = [
        t for t in st.session_state.upload_timestamps
        if current_time - t < UPLOAD_WINDOW_SECONDS
    ]

    uploads_remaining = MAX_UPLOADS_PER_HOUR - len(st.session_state.upload_timestamps)
    if uploads_remaining <= 0:
        st.error("❌ Upload rate limit reached. Please wait before uploading more files.")
        st.stop()

    uploaded_file = st.file_uploader(
        "Choose your census file",
        type=['csv', 'txt', 'tsv'],
        help="Upload a CSV file (comma or tab-delimited) following the template format"
    )

    if uploaded_file is not None:
        # Record this upload attempt
        st.session_state.upload_timestamps.append(current_time)
        upload_start = time.time()
        print(f"[UPLOAD] ======== Starting upload: {uploaded_file.name} ========", flush=True)
        logging.info("=" * 60)
        logging.info(f"FILE UPLOAD: Starting upload processing for '{uploaded_file.name}'")

        try:
            # Security validation for file upload
            MAX_FILE_SIZE_MB = 10
            MAX_ROWS = 10000

            # Check file size
            logging.info("FILE UPLOAD: Reading file bytes...")
            file_size_mb = len(uploaded_file.getvalue()) / (1024 * 1024)
            logging.info(f"FILE UPLOAD: File size = {file_size_mb:.2f} MB")
            if file_size_mb > MAX_FILE_SIZE_MB:
                st.error(f"❌ File too large: {file_size_mb:.1f}MB. Maximum allowed is {MAX_FILE_SIZE_MB}MB.")
                st.stop()

            # Read the uploaded file, forcing ZIP codes to be read as strings
            # This preserves leading zeros and prevents float conversion (e.g., 60005.0)
            # Auto-detect delimiter (handles comma, tab, semicolon, etc.)
            import csv
            import io

            # Read file content to detect delimiter - try multiple encodings
            logging.info("FILE UPLOAD: Decoding file content...")
            file_bytes = uploaded_file.getvalue()
            file_content = None
            detected_encoding = None

            # Try common encodings in order of likelihood
            encodings_to_try = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252', 'iso-8859-1']
            decode_start = time.time()

            for encoding in encodings_to_try:
                try:
                    file_content = file_bytes.decode(encoding)
                    detected_encoding = encoding
                    logging.info(f"FILE UPLOAD: Decoded with {encoding} - {len(file_content):,} chars in {time.time() - decode_start:.2f}s")
                    break
                except (UnicodeDecodeError, LookupError):
                    continue

            if file_content is None:
                logging.error("FILE UPLOAD: All encoding attempts failed")
                st.error("❌ File encoding error. Could not decode file. Please save as UTF-8 encoded CSV.")
                st.stop()

            # Show encoding info if not UTF-8
            if detected_encoding and detected_encoding not in ('utf-8', 'utf-8-sig'):
                st.info(f"📝 File encoding detected: {detected_encoding} (converted to UTF-8)")

            # Use csv.Sniffer to detect delimiter
            try:
                sample = file_content[:4096]  # Sample first 4KB
                dialect = csv.Sniffer().sniff(sample, delimiters=',\t;|')
                detected_delimiter = dialect.delimiter
            except csv.Error:
                # Default to comma if detection fails
                detected_delimiter = ','

            # Read with detected delimiter
            logging.info(f"FILE UPLOAD: Reading CSV with delimiter '{repr(detected_delimiter)}'...")
            uploaded_file.seek(0)  # Reset file pointer
            csv_start = time.time()
            census_raw = pd.read_csv(
                io.StringIO(file_content),
                dtype={'Home Zip': str},
                sep=detected_delimiter
            )
            csv_elapsed = time.time() - csv_start
            logging.info(f"FILE UPLOAD: CSV parsed in {csv_elapsed:.2f}s - {len(census_raw)} rows, {len(census_raw.columns)} columns")

            # Show detected format
            delimiter_name = {',': 'comma', '\t': 'tab', ';': 'semicolon', '|': 'pipe'}.get(detected_delimiter, 'custom')
            st.caption(f"📄 Detected format: {delimiter_name}-delimited")

            # Validate row count
            if len(census_raw) > MAX_ROWS:
                st.error(f"❌ File has {len(census_raw):,} rows. Maximum allowed is {MAX_ROWS:,}.")
                st.stop()

            if len(census_raw) == 0:
                st.error("❌ File appears to be empty or has no valid data rows.")
                st.stop()

            # Validate required columns exist
            required_columns = ['Employee Number', 'Home Zip', 'Home State', 'Family Status', 'EE DOB']
            missing_columns = [col for col in required_columns if col not in census_raw.columns]
            if missing_columns:
                st.error(f"❌ Missing required columns: {', '.join(missing_columns)}")
                st.info("Please download and use the template to ensure all required columns are present.")
                st.stop()

            # Security: Check for CSV formula injection
            # Formulas starting with =, @, +, - can execute when opened in Excel
            formula_pattern = r'^[\s]*[=@\+\-]'
            import re
            for col in census_raw.columns:
                if census_raw[col].dtype == 'object':  # Only check string columns
                    suspicious = census_raw[col].astype(str).str.match(formula_pattern, na=False)
                    if suspicious.any():
                        # Sanitize by prefixing with single quote (Excel treats as text)
                        census_raw[col] = census_raw[col].apply(
                            lambda x: f"'{x}" if isinstance(x, str) and re.match(formula_pattern, x) else x
                        )
                        st.warning(f"⚠️ Sanitized potential formula content in column '{col}'")

            # Clean up ZIP codes: remove .0 suffix if present (from Excel numeric formatting)
            # Handle ZIP+4 format (e.g., "29654-7352" -> "29654")
            if 'Home Zip' in census_raw.columns:
                census_raw['Home Zip'] = census_raw['Home Zip'].astype(str).str.replace(r'\.0$', '', regex=True)
                # Extract first 5 digits (handles ZIP+4 format) and pad with leading zeros
                census_raw['Home Zip'] = census_raw['Home Zip'].str.split('-').str[0].str.zfill(5).str[:5]

            st.success(f"✅ File uploaded: {len(census_raw)} rows")

            # Show preview
            with st.expander("📋 Preview uploaded data (first 10 rows)", expanded=True):
                st.dataframe(census_raw.head(10), width="stretch")

            # Parse and validate
            st.info("🔄 Processing census data...")
            logging.info("FILE UPLOAD: Starting census parsing...")

            with st.spinner("Validating data, looking up counties from ZIP codes, and extracting dependents..."):
                try:
                    # Parse using new format
                    parse_start = time.time()
                    logging.info("FILE UPLOAD: Calling CensusProcessor.parse_new_census_format()...")
                    employees_df, dependents_df = CensusProcessor.parse_new_census_format(
                        census_raw,
                        st.session_state.db
                    )
                    parse_elapsed = time.time() - parse_start
                    logging.info(f"FILE UPLOAD: Census parsing complete in {parse_elapsed:.1f}s")

                    # Store in session state
                    st.session_state.census_df = employees_df
                    st.session_state.dependents_df = dependents_df

                    # Pre-compute FAST hashes for PDF caching (avoid expensive to_json())
                    # Use shape + key column sums as proxy for data identity
                    def fast_df_hash(df, key_cols=None):
                        """Fast hash using shape and numeric column sums."""
                        if df is None or df.empty:
                            return 0
                        parts = [len(df), len(df.columns)]
                        if 'age' in df.columns:
                            parts.append(int(df['age'].sum()))
                        if key_cols:
                            for col in key_cols:
                                if col in df.columns:
                                    parts.append(hash(tuple(df[col].head(5).tolist())))
                        return hash(tuple(parts))

                    st.session_state.census_emp_hash = fast_df_hash(employees_df, ['employee_id', 'zip_code', 'state'])
                    st.session_state.census_dep_hash = fast_df_hash(dependents_df, ['employee_id'])
                    st.session_state.census_ra_hash = hash(tuple(sorted(employees_df['rating_area_id'].dropna().unique()))) if 'rating_area_id' in employees_df.columns else 0

                    # Show success summary
                    st.success("✅ Census processed successfully!")

                    # Check for per-employee contribution data
                    if ContributionComparison.has_individual_contributions(employees_df):
                        contrib_totals = ContributionComparison.aggregate_contribution_totals(employees_df)
                        st.info(
                            f"📊 Contribution data found for {contrib_totals['employees_with_data']} employees — "
                            f"EE: \\${contrib_totals['total_current_ee_monthly']:,.0f}/mo, "
                            f"ER: \\${contrib_totals['total_current_er_monthly']:,.0f}/mo"
                        )

                    # Summary metrics
                    col1, col2, col3, col4 = st.columns(4)

                    with col1:
                        st.metric("Total employees", len(employees_df))

                    with col2:
                        num_deps = len(dependents_df) if not dependents_df.empty else 0
                        st.metric("Total dependents", num_deps)

                    with col3:
                        total_lives = len(employees_df) + num_deps
                        st.metric("Covered lives", total_lives)

                    with col4:
                        unique_states = employees_df['state'].nunique()
                        st.metric("States", unique_states)

                    # Covered lives age metrics
                    col1, col2, col3 = st.columns(3)

                    # Calculate ages of all covered lives
                    if not dependents_df.empty:
                        all_ages = pd.concat([employees_df['age'], dependents_df['age']])
                    else:
                        all_ages = employees_df['age']

                    with col1:
                        avg_age_covered = all_ages.mean()
                        st.metric("Avg age of covered lives", f"{avg_age_covered:.1f} yrs")

                    with col2:
                        median_age_covered = all_ages.median()
                        st.metric("Median age of covered lives", f"{median_age_covered:.1f} yrs")

                    with col3:
                        min_age = int(all_ages.min())
                        max_age = int(all_ages.max())
                        st.metric("Age range of covered lives", f"{min_age} - {max_age} yrs")

                    # Export Section
                    st.markdown("### 📄 Export Census Analysis")
                    export_col1, export_col2, export_col3 = st.columns([3, 1, 1])
                    with export_col1:
                        # Initialize client_name in session state if not present
                        if 'client_name' not in st.session_state:
                            st.session_state.client_name = ''

                        # Client name input - bound directly to session state via key
                        st.text_input(
                            "Client name (optional)",
                            placeholder="Enter client name for PDF",
                            key="client_name",
                            help="Client name will appear in the PDF header and filename"
                        )

                    with export_col2:
                        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)  # Align with input

                        # Use pre-computed hashes from session state
                        emp_hash = st.session_state.get('census_emp_hash', 0)
                        dep_hash = st.session_state.get('census_dep_hash', 0)
                        ra_hash = st.session_state.get('census_ra_hash', 0)
                        client_name = st.session_state.get('client_name', '').strip()
                        db_available = st.session_state.get('db') is not None

                        # Check if we need to regenerate (data or client_name changed)
                        current_pdf_key = (emp_hash, dep_hash, ra_hash, client_name)
                        cached_pdf_key = st.session_state.get('_pdf_cache_key_upload')
                        pdf_ready = cached_pdf_key == current_pdf_key and '_pdf_data_upload' in st.session_state

                        if pdf_ready:
                            # PDF is ready - show download button
                            st.download_button(
                                label="📄 Export PDF",
                                data=st.session_state['_pdf_data_upload'],
                                file_name=st.session_state.get('_pdf_filename_upload', 'census_analysis.pdf'),
                                mime="application/pdf",
                                type="secondary",
                                use_container_width=True,
                                key="pdf_download_upload"
                            )
                        else:
                            # Need to generate - show generate button
                            if st.button("📄 Generate PDF", type="secondary", use_container_width=True, key="pdf_generate_upload"):
                                try:
                                    with st.spinner("Generating PDF..."):
                                        pdf_data = generate_census_pdf_cached(emp_hash, dep_hash, client_name, db_available, ra_hash, _PDF_TEMPLATE_VERSION)
                                        filename = get_census_pdf_filename(client_name)
                                        st.session_state['_pdf_data_upload'] = pdf_data
                                        st.session_state['_pdf_filename_upload'] = filename
                                        st.session_state['_pdf_cache_key_upload'] = current_pdf_key
                                        st.rerun()
                                except Exception as e:
                                    st.error(f"Error generating PDF: {str(e)}")
                                    logging.exception("PDF generation error")

                    with export_col3:
                        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                        try:
                            from pptx_census_report import generate_census_report_from_session, get_census_report_filename
                            pptx_data = generate_census_report_from_session(st.session_state)
                            client_name = st.session_state.get('client_name', '').strip()
                            filename = get_census_report_filename(client_name)
                            st.download_button(
                                label="📊 Download slide",
                                data=pptx_data,
                                file_name=filename,
                                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                                type="secondary",
                                use_container_width=True,
                                key="pptx_download_upload"
                            )
                        except Exception as e:
                            if st.button("📊 Download slide", type="secondary", use_container_width=True, key="pptx_error_upload", disabled=True):
                                pass
                            st.caption(f"Error: {str(e)}")

                    # Detailed breakdown
                    st.markdown("---")
                    st.subheader("📊 Census summary")

                    tab1, tab2, tab3, tab4 = st.tabs(["👥 Employees", "👶 Dependents", "📍 Geography", "📊 Demographics"])

                    with tab1:
                        st.markdown("### 📊 Employee demographics")

                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown(f"**Total employees:** {len(employees_df)}")
                            st.markdown(f"**Average age:** {employees_df['age'].mean():.1f} years")
                            st.markdown(f"**Median age:** {employees_df['age'].median():.1f} years")

                        with col2:
                            st.markdown("**Age range:**")
                            st.markdown(f"- Youngest: {employees_df['age'].min():.0f} years")
                            st.markdown(f"- Oldest: {employees_df['age'].max():.0f} years")

                        # Employee Only (EE) Class Statistics
                        ee_employees = employees_df[employees_df['family_status'] == 'EE']
                        if len(ee_employees) > 0:
                            st.markdown("---")
                            st.markdown("### 👤 Employee only (EE) class")

                            col1, col2 = st.columns(2)
                            with col1:
                                st.markdown(f"**Count:** {len(ee_employees)} employees")
                                st.markdown(f"**Average age:** {ee_employees['age'].mean():.1f} years")
                                st.markdown(f"**Median age:** {ee_employees['age'].median():.1f} years")

                            with col2:
                                st.markdown("**Age range:**")
                                st.markdown(f"- Youngest: {ee_employees['age'].min():.0f} years")
                                st.markdown(f"- Oldest: {ee_employees['age'].max():.0f} years")

                        st.markdown("---")
                        st.markdown("### 👨‍👩‍👧‍👦 Family status breakdown")
                        status_counts = employees_df['family_status'].value_counts()
                        for status, count in status_counts.items():
                            status_name = FAMILY_STATUS_CODES.get(status, status)
                            pct = (count / len(employees_df)) * 100
                            st.markdown(f"- **{status_name}:** {count} employees ({pct:.1f}%)")

                        st.markdown("---")
                        st.markdown("### 📋 Employee data")
                        display_cols = ['employee_id', 'first_name', 'last_name', 'age', 'state', 'county', 'family_status']
                        if 'current_ee_monthly' in employees_df.columns:
                            display_cols.extend(['current_ee_monthly', 'current_er_monthly'])
                        st.dataframe(employees_df[display_cols], width="stretch")

                    with tab2:
                        if not dependents_df.empty:
                            # Calculate key metrics
                            total_deps = len(dependents_df)
                            total_lives = len(employees_df) + total_deps
                            coverage_burden = total_lives / len(employees_df)
                            avg_age = dependents_df['age'].mean()
                            median_age = dependents_df['age'].median()
                            youngest = int(dependents_df['age'].min())
                            oldest = int(dependents_df['age'].max())
                            rel_counts = dependents_df['relationship'].value_counts()

                            # Styled header
                            st.markdown("""
                            <p style="font-size: 18px; font-weight: 700; color: #101828; margin-bottom: 16px;">
                                Dependent Overview
                            </p>
                            """, unsafe_allow_html=True)

                            # Key metrics row
                            metric_cols = st.columns(4)
                            metrics = [
                                ("Total Dependents", f"{total_deps}", "#3b82f6"),
                                ("Coverage Burden", f"{coverage_burden:.2f}:1", "#8b5cf6"),
                                ("Average Age", f"{avg_age:.1f}", "#10b981"),
                                ("Age Range", f"{youngest}–{oldest}", "#0047AB"),
                            ]

                            for col, (label, value, color) in zip(metric_cols, metrics):
                                with col:
                                    st.markdown(f"""
                                    <div style="background: {color}10; border-left: 4px solid {color}; border-radius: 8px; padding: 12px 16px;">
                                        <p style="font-size: 12px; color: #6b7280; margin: 0; text-transform: uppercase; letter-spacing: 0.5px;">{label}</p>
                                        <p style="font-size: 24px; font-weight: 700; color: #101828; margin: 4px 0 0 0; font-family: 'Inter', sans-serif;">{value}</p>
                                    </div>
                                    """, unsafe_allow_html=True)

                            st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)

                            # Two-column layout for relationship breakdown and age stats
                            col1, col2 = st.columns(2)

                            with col1:
                                st.markdown("""
                                <p style="font-size: 14px; font-weight: 600; color: #374151; margin-bottom: 12px;">
                                    By Relationship
                                </p>
                                """, unsafe_allow_html=True)

                                # Progress bars for relationship breakdown
                                max_count = rel_counts.max() if not rel_counts.empty else 1
                                rel_colors = {'spouse': '#ec4899', 'child': '#3b82f6'}

                                for rel, count in rel_counts.items():
                                    pct = (count / total_deps) * 100
                                    bar_pct = (count / max_count) * 100
                                    color = rel_colors.get(rel, '#6b7280')

                                    st.markdown(f"""
                                    <div style="margin-bottom: 12px;">
                                        <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                                            <span style="font-size: 14px; color: #374151;">{rel.title()}s</span>
                                            <span style="font-size: 14px; font-weight: 600; color: #101828;">{count} <span style="color: #9ca3af; font-weight: 400;">({pct:.0f}%)</span></span>
                                        </div>
                                        <div style="background: #e5e7eb; height: 8px; border-radius: 9999px;">
                                            <div style="background: {color}; height: 8px; border-radius: 9999px; width: {bar_pct}%;"></div>
                                        </div>
                                    </div>
                                    """, unsafe_allow_html=True)

                            with col2:
                                st.markdown("""
                                <p style="font-size: 14px; font-weight: 600; color: #374151; margin-bottom: 12px;">
                                    Age Statistics
                                </p>
                                """, unsafe_allow_html=True)

                                age_stats = [
                                    ("Youngest", f"{youngest} years"),
                                    ("Oldest", f"{oldest} years"),
                                    ("Average", f"{avg_age:.1f} years"),
                                    ("Median", f"{median_age:.1f} years"),
                                ]

                                for label, value in age_stats:
                                    st.markdown(f"""
                                    <div style="display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #f3f4f6;">
                                        <span style="font-size: 14px; color: #6b7280;">{label}</span>
                                        <span style="font-size: 14px; font-weight: 500; color: #374151;">{value}</span>
                                    </div>
                                    """, unsafe_allow_html=True)

                            # Coverage burden footnote
                            st.markdown(f"""
                            <p style="font-size: 12px; color: #9ca3af; margin-top: 16px; font-style: italic;">
                                Coverage burden = (employees + dependents) ÷ employees = ({len(employees_df)} + {total_deps}) ÷ {len(employees_df)} = {coverage_burden:.2f} covered lives per employee
                            </p>
                            """, unsafe_allow_html=True)

                            st.markdown("<hr style='border: none; border-top: 1px solid #e5e7eb; margin: 20px 0;'>", unsafe_allow_html=True)

                            # Children analysis
                            children_df = dependents_df[dependents_df['relationship'] == 'child']
                            spouses_df = dependents_df[dependents_df['relationship'] == 'spouse']

                            if not children_df.empty:
                                st.markdown("---")
                                st.markdown("### 👧👦 Children analysis")

                                # Get employees with children
                                employees_with_children = employees_df[employees_df['family_status'].isin(['EC', 'F'])]

                                col1, col2 = st.columns(2)

                                with col1:
                                    st.markdown("**Overall statistics:**")
                                    st.markdown(f"- Total children: {len(children_df)}")
                                    st.markdown(f"- Families with children: {len(employees_with_children)}")
                                    if len(employees_with_children) > 0:
                                        avg_children = len(children_df) / len(employees_with_children)
                                        st.markdown(f"- Avg children per family: {avg_children:.1f}")

                                with col2:
                                    st.markdown("**Age statistics:**")
                                    st.markdown(f"- Average Age: {children_df['age'].mean():.1f} years")
                                    st.markdown(f"- Median Age: {children_df['age'].median():.1f} years")
                                    st.markdown(f"- Age Range: {children_df['age'].min():.0f} - {children_df['age'].max():.0f} years")

                                # Breakdown by family type
                                st.markdown("---")
                                st.markdown("### 📊 Children by family type")

                                # Employee + Children (EC)
                                ec_employees = employees_df[employees_df['family_status'] == 'EC']
                                if len(ec_employees) > 0:
                                    ec_children = children_df[children_df['employee_id'].isin(ec_employees['employee_id'])]
                                    st.markdown("**Employee + Children (EC):**")
                                    st.markdown(f"- Families: {len(ec_employees)}")
                                    st.markdown(f"- Total Children: {len(ec_children)}")
                                    if len(ec_children) > 0:
                                        avg_ec = len(ec_children) / len(ec_employees)
                                        st.markdown(f"- Avg per family: {avg_ec:.1f}")
                                        st.markdown(f"- Avg Age: {ec_children['age'].mean():.1f} years | Median: {ec_children['age'].median():.1f} years")
                                        st.markdown(f"- Age Range: {int(ec_children['age'].min())} - {int(ec_children['age'].max())} years")
                                else:
                                    st.markdown("**Employee + Children (EC):** No EC families in census")

                                # Full Family (F)
                                f_employees = employees_df[employees_df['family_status'] == 'F']
                                if len(f_employees) > 0:
                                    f_children = children_df[children_df['employee_id'].isin(f_employees['employee_id'])]
                                    st.markdown("**Full Family (F - Employee + Spouse + Children):**")
                                    st.markdown(f"- Families: {len(f_employees)}")
                                    st.markdown(f"- Total Children: {len(f_children)}")
                                    if len(f_children) > 0:
                                        avg_f = len(f_children) / len(f_employees)
                                        st.markdown(f"- Avg per family: {avg_f:.1f}")
                                        st.markdown(f"- Avg Age: {f_children['age'].mean():.1f} years | Median: {f_children['age'].median():.1f} years")
                                        st.markdown(f"- Age Range: {int(f_children['age'].min())} - {int(f_children['age'].max())} years")
                                else:
                                    st.markdown("**Full Family (F):** No F families in census")

                            # Spouse analysis
                            if not spouses_df.empty:
                                st.markdown("---")
                                st.markdown("### 💑 Spouse analysis")

                                # Get employees with spouses
                                employees_with_spouses = employees_df[employees_df['family_status'].isin(['ES', 'F'])]

                                col1, col2 = st.columns(2)

                                with col1:
                                    st.markdown("**Coverage statistics:**")
                                    st.markdown(f"- Total spouses: {len(spouses_df)}")
                                    st.markdown(f"- Families with spouse coverage: {len(employees_with_spouses)}")

                                with col2:
                                    st.markdown("**Overall age statistics:**")
                                    st.markdown(f"- Average Age: {spouses_df['age'].mean():.1f} years")
                                    st.markdown(f"- Median Age: {spouses_df['age'].median():.1f} years")

                                st.markdown("---")
                                st.markdown("**By family type:**")

                                # Employee + Spouse (ES)
                                es_employees = employees_df[employees_df['family_status'] == 'ES']
                                if len(es_employees) > 0:
                                    es_spouses = spouses_df[spouses_df['employee_id'].isin(es_employees['employee_id'])]
                                    st.markdown(f"**Employee + Spouse (ES):**")
                                    st.markdown(f"- Count: {len(es_spouses)} spouses")
                                    if len(es_spouses) > 0:
                                        st.markdown(f"- Avg Age: {es_spouses['age'].mean():.1f} years | Median: {es_spouses['age'].median():.1f} years")
                                        st.markdown(f"- Age Range: {es_spouses['age'].min():.0f} - {es_spouses['age'].max():.0f} years")

                                # Full Family (F)
                                f_employees = employees_df[employees_df['family_status'] == 'F']
                                if len(f_employees) > 0:
                                    f_spouses = spouses_df[spouses_df['employee_id'].isin(f_employees['employee_id'])]
                                    st.markdown(f"**Full Family (F):**")
                                    st.markdown(f"- Count: {len(f_spouses)} spouses")
                                    if len(f_spouses) > 0:
                                        st.markdown(f"- Avg Age: {f_spouses['age'].mean():.1f} years | Median: {f_spouses['age'].median():.1f} years")
                                        st.markdown(f"- Age Range: {f_spouses['age'].min():.0f} - {f_spouses['age'].max():.0f} years")

                            st.markdown("---")
                            st.markdown("### 📋 Dependent data")
                            st.dataframe(dependents_df, width="stretch")
                        else:
                            st.info("No dependents in this census (all employees have Family Status = EE)")

                    with tab3:
                        # Geographic distribution
                        st.markdown("**Employees by State:**")
                        state_counts = employees_df['state'].value_counts()
                        for state, count in state_counts.items():
                            pct = (count / len(employees_df)) * 100
                            st.markdown(f"- **{state}:** {count} employees ({pct:.1f}%)")

                        st.markdown("---")
                        st.markdown("**Employees by County:**")
                        county_counts = employees_df.groupby(['state', 'county']).size().reset_index(name='count')
                        county_counts = county_counts.sort_values('count', ascending=False)
                        st.dataframe(county_counts, width="stretch", hide_index=True)

                        # Plan availability by rating area
                        st.markdown("---")
                        st.markdown("### 📋 Plan availability by rating area")
                        st.caption("Count of Individual marketplace plans available in each rating area")

                        # Use cached plan availability data (same cache as PDF generation)
                        ra_hash = st.session_state.get('census_ra_hash', 0)
                        db_available = st.session_state.get('db') is not None

                        if 'rating_area_id' in employees_df.columns and db_available:
                            # Get cached plan availability (no DB query on every keystroke!)
                            ra_data_json = _get_ra_data_json()
                            plan_availability_df = _get_plan_availability_cached(ra_hash, db_available, ra_data_json)

                            if not plan_availability_df.empty:
                                display_df = plan_availability_df.copy()
                                display_df = display_df.sort_values(['state', 'county', 'rating_area_id'])
                                display_df.columns = ['State', 'County', 'Rating Area', 'Employees', 'Plans Available']
                                st.dataframe(display_df, width="stretch", hide_index=True)
                            else:
                                st.info("No plan data available")
                        else:
                            st.info("Rating area data not available. Ensure census has been processed.")

                    with tab4:
                        import plotly.express as px

                        # Diverse accessible color palette (high contrast between adjacent segments)
                        CHART_COLORS = ['#0047AB', '#f59e0b', '#10b981', '#8b5cf6', '#ef4444', '#06b6d4', '#f97316', '#6366f1']

                        # Age distribution chart
                        st.markdown("### Age distribution")
                        col1, col2 = st.columns(2)

                        with col1:
                            age_bins = [0, 30, 40, 50, 60, 100]
                            age_labels = ['Under 30', '30-39', '40-49', '50-59', '60+']

                            age_col = 'employee_age' if 'employee_age' in employees_df.columns else 'age'
                            census_with_age_group = employees_df.copy()
                            census_with_age_group['age_group'] = pd.cut(
                                census_with_age_group[age_col],
                                bins=age_bins,
                                labels=age_labels,
                                right=False
                            )

                            age_dist = census_with_age_group['age_group'].value_counts().sort_index()

                            fig = px.pie(
                                values=age_dist.values,
                                names=age_dist.index,
                                title='Employee age distribution',
                                color_discrete_sequence=CHART_COLORS
                            )
                            st.plotly_chart(fig, width='stretch')

                        with col2:
                            # State distribution bar chart
                            state_dist = employees_df['state'].value_counts()

                            fig = px.bar(
                                x=state_dist.index,
                                y=state_dist.values,
                                title='Employees by State',
                                labels={'x': 'State', 'y': 'Number of employees'},
                                color_discrete_sequence=['#0047AB']
                            )
                            st.plotly_chart(fig, width='stretch')

                        # Family status distribution
                        if 'family_status' in employees_df.columns:
                            st.markdown("### Family status distribution")

                            family_counts = employees_df['family_status'].value_counts()
                            family_labels = [f"{code} ({FAMILY_STATUS_CODES.get(code, code)})" for code in family_counts.index]

                            col1, col2 = st.columns([2, 1])

                            with col1:
                                fig = px.pie(
                                    values=family_counts.values,
                                    names=family_labels,
                                    title='Employees by family status',
                                    color_discrete_sequence=CHART_COLORS
                                )
                                st.plotly_chart(fig, width='stretch')

                            with col2:
                                st.markdown("**Family status breakdown:**")
                                for code, count in family_counts.items():
                                    pct = count / len(employees_df) * 100
                                    desc = FAMILY_STATUS_CODES.get(code, code)
                                    st.markdown(f"- **{code}** ({desc}): {count} ({pct:.1f}%)")

                        # Dependent demographics (if present)
                        if not dependents_df.empty:
                            st.markdown("### Dependent demographics")

                            dep_col1, dep_col2 = st.columns(2)

                            with dep_col1:
                                rel_counts = dependents_df['relationship'].value_counts()

                                fig = px.pie(
                                    values=rel_counts.values,
                                    names=[rel.title() + 's' for rel in rel_counts.index],
                                    title='Dependents by relationship',
                                    color_discrete_sequence=CHART_COLORS
                                )
                                st.plotly_chart(fig, width='stretch')

                            with dep_col2:
                                dependents_with_age_group = dependents_df.copy()

                                dep_age_bins = [0, 5, 13, 18, 21, 30, 40, 50, 100]
                                dep_age_labels = ['0-4', '5-12', '13-17', '18-20', '21-29', '30-39', '40-49', '50+']

                                dependents_with_age_group['age_group'] = pd.cut(
                                    dependents_with_age_group['age'],
                                    bins=dep_age_bins,
                                    labels=dep_age_labels,
                                    right=False
                                )

                                dep_age_dist = dependents_with_age_group['age_group'].value_counts().sort_index()

                                fig = px.bar(
                                    x=dep_age_dist.index,
                                    y=dep_age_dist.values,
                                    title='Dependent Age Distribution',
                                    labels={'x': 'Age Group', 'y': 'Number of Dependents'},
                                    color_discrete_sequence=['#0891b2']
                                )
                                st.plotly_chart(fig, width='stretch')

                        # Rating area distribution
                        st.markdown("### Geographic distribution")

                        col1, col2 = st.columns(2)

                        with col1:
                            ra_counts = employees_df.groupby(['state', 'rating_area_id']).size().reset_index(name='count')
                            ra_counts = ra_counts.sort_values(['state', 'rating_area_id'])

                            st.markdown("**Employees by Rating Area:**")
                            st.dataframe(ra_counts, width='stretch', hide_index=True)

                        with col2:
                            county_counts = employees_df['county'].value_counts().head(10)

                            fig = px.bar(
                                x=county_counts.values,
                                y=county_counts.index,
                                orientation='h',
                                title='Top 10 Counties by Employee Count',
                                labels={'x': 'Number of Employees', 'y': 'County'},
                                color_discrete_sequence=['#6366f1']
                            )
                            fig.update_layout(yaxis={'categoryorder': 'total ascending'})
                            st.plotly_chart(fig, width='stretch')

                    # Navigation
                    st.markdown("---")
                    st.success("✅ Census loaded! Ready to proceed to **Plan Selection** →")
                    st.markdown("Click **2️⃣ Plan Selection** in the sidebar to continue")

                except ValueError as e:
                    st.error(f"❌ Census validation failed:\n\n{str(e)}")
                    st.info("Please fix the errors in your CSV file and re-upload.")

                except Exception as e:
                    st.error(f"❌ Error processing census: {str(e)}")
                    st.error("Please check your file format and try again.")
                    import traceback
                    with st.expander("Technical details"):
                        st.code(traceback.format_exc())

        except Exception as e:
            st.error(f"❌ Error reading CSV file: {str(e)}")
            st.info("Please ensure the file is a valid CSV file.")

    else:
        # No file uploaded - show help
        st.info("👆 Upload your census CSV file to get started")

# ==============================================================================
# HELP SECTION
# ==============================================================================

st.markdown("---")

with st.expander("Help & Format Reference"):
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        **Required Columns**
        - `Employee Number` — Unique ID
        - `Home Zip` — 5-digit ZIP code
        - `Home State` — 2-letter state code
        - `Family Status` — EE, ES, EC, or F
        - `EE DOB` — Employee date of birth

        **Family Status Codes**
        - **EE** = Employee Only
        - **ES** = Employee + Spouse
        - **EC** = Employee + Children
        - **F** = Full Family
        """)
    with col2:
        st.markdown("""
        **Conditional Columns**
        - `Spouse DOB` — Required for ES/F
        - `Dep 2-6 DOB` — Child DOBs for EC/F

        **Date Formats**
        - `m/d/yy` or `mm/dd/yyyy`
        - 2-digit years: 00-29 → 2000s

        **Limits**
        - Employees: age 18-64
        - Children: age 0-26
        """)

# Show current census status in sidebar
with st.sidebar:
    st.markdown("### Census Status")

    if st.session_state.census_df is not None:
        num_employees = len(st.session_state.census_df)
        num_dependents = len(st.session_state.dependents_df) if st.session_state.dependents_df is not None else 0

        st.success(f"**{num_employees}** employees")
        if num_dependents > 0:
            st.info(f"**{num_dependents}** dependents")
        st.metric("Covered Lives", num_employees + num_dependents)

        if st.button("Clear Census", use_container_width=True):
            st.session_state.census_df = None
            st.session_state.dependents_df = None
            st.rerun()
    else:
        st.markdown("""
        <div style="background: rgba(255,255,255,0.9); padding: 12px 16px; border-radius: 8px; color: #374151; font-size: 14px;">
            No census loaded
        </div>
        """, unsafe_allow_html=True)

    # Feedback button in sidebar
    render_feedback_sidebar()
