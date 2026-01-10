"""
ICHRA Plan Calculator - Main Application
Streamlit app for ICHRA benefits consultants to calculate and compare Individual marketplace plans
"""

import sys
import os
import logging
from pathlib import Path

# Configure logging BEFORE importing streamlit
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s',
    datefmt='%H:%M:%S',
    force=True  # Override any existing config
)
print("[APP] Logging configured", flush=True)
logging.info("APP STARTUP: Logging initialized")

import streamlit as st

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from constants import (
    APP_CONFIG, COOPERATIVE_CONFIG, DEFAULT_ADOPTION_RATES
)
from database import get_database_connection, test_connection

def get_cloudflare_user():
    """Get authenticated user from Cloudflare Zero Trust headers."""
    import streamlit as st
    try:
        # Check for Cloudflare Access header
        from streamlit.web.server.websocket_headers import _get_websocket_headers
        headers = _get_websocket_headers()
        if headers:
            return headers.get('Cf-Access-Authenticated-User-Email')
    except Exception:
        pass
    return None

# Page configuration
st.set_page_config(
    page_title=APP_CONFIG['title'],
    page_icon=APP_CONFIG['icon'],
    layout=APP_CONFIG['layout'],
    initial_sidebar_state=APP_CONFIG['initial_sidebar_state']
)


def initialize_session_state():
    """Initialize session state variables"""

    # Employee census data
    if 'census_df' not in st.session_state:
        st.session_state.census_df = None

    # Contribution analysis results (per-employee)
    if 'contribution_analysis' not in st.session_state:
        st.session_state.contribution_analysis = {}

    # Employer contribution settings
    if 'contribution_settings' not in st.session_state:
        st.session_state.contribution_settings = {
            'default_percentage': 75,
            'by_class': {},
            'input_mode': 'percentage',  # 'percentage' or 'flat_amount'
            'flat_amounts': {  # Employer contribution by tier (dollar amounts)
                'EE': None,
                'ES': None,
                'EC': None,
                'F': None
            }
        }

    # Plan comparison results
    if 'plan_costs' not in st.session_state:
        st.session_state.plan_costs = {}

    # Export data
    if 'export_data' not in st.session_state:
        st.session_state.export_data = None

    # Database connection - use cached resource directly
    # get_database_connection() is decorated with @st.cache_resource which handles thread safety
    # We still store in session_state for compatibility, but the actual connection is cached
    if 'db' not in st.session_state:
        try:
            st.session_state.db = get_database_connection()
        except Exception as e:
            # Log the error but don't crash - pages can retry connection
            import logging
            logging.error(f"Failed to initialize database connection: {e}")
            st.session_state.db = None

    # Dashboard configuration (user-adjustable settings)
    if 'dashboard_config' not in st.session_state:
        st.session_state.dashboard_config = {
            'cooperative_ratio': COOPERATIVE_CONFIG['default_discount_ratio'],
            'adoption_rates': DEFAULT_ADOPTION_RATES.copy(),
        }


def main():
    """Main application entry point"""

    # Initialize session state
    initialize_session_state()

    # Sidebar info
    st.sidebar.subheader("Quick stats")

    if st.session_state.census_df is not None:
        st.sidebar.metric("Employees", len(st.session_state.census_df))
    else:
        st.sidebar.info("No census loaded")

    # Client name for exports
    st.sidebar.markdown("---")
    st.sidebar.subheader("Client name")
    if 'client_name' not in st.session_state:
        st.session_state.client_name = ''
    st.sidebar.text_input(
        "Client name",
        placeholder="Enter client name",
        key="client_name",
        help="Used in all export filenames",
        label_visibility="collapsed"
    )

    # Test database connection
    st.sidebar.markdown("---")
    if st.sidebar.button("🔌 Test database connection"):
        with st.sidebar:
            with st.spinner("Testing connection..."):
                if test_connection():
                    st.success("Database connected!")
                else:
                    st.error("Connection failed")

    # Show home page content
    show_home_page()


def show_home_page():
    """Display home/welcome page"""

    # Custom CSS for home page
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

        .workflow-card {
            background: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0px 1px 3px rgba(0,0,0,0.08);
            border: 1px solid #e2e8f0;
            height: 100%;
        }

        .workflow-step {
            display: flex;
            align-items: flex-start;
            gap: 12px;
            padding: 12px 0;
            border-bottom: 1px solid #f1f5f9;
        }

        .workflow-step:last-child {
            border-bottom: none;
        }

        .step-number {
            background: #0047AB;
            color: white;
            width: 24px;
            height: 24px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 12px;
            font-weight: 600;
            flex-shrink: 0;
        }

        .step-content {
            flex: 1;
        }

        .step-title {
            font-weight: 600;
            color: #101828;
            font-size: 14px;
            margin-bottom: 2px;
        }

        .step-desc {
            color: #667085;
            font-size: 13px;
        }

        .feature-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 16px;
            margin-top: 16px;
        }

        .feature-item {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 14px;
            color: #364153;
        }

        .feature-icon {
            color: #0047AB;
        }

        .status-badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 13px;
            font-weight: 500;
        }

        .status-success {
            background: #ecfdf5;
            color: #047857;
        }

        .status-info {
            background: #e8f1fd;
            color: #003d91;
        }
    </style>
    """, unsafe_allow_html=True)

    # Hero section
    st.markdown("""
    <div class="hero-section">
        <div class="hero-title">ICHRA Plan Calculator</div>
        <p class="hero-subtitle">Model ICHRA contributions and compare against marketplace plans using 2026 CMS data.</p>
    </div>
    """, unsafe_allow_html=True)

    # Two-column layout
    col1, col2 = st.columns([3, 2])

    with col1:
        st.markdown("""
        <div class="workflow-card">
            <div style="font-weight: 600; font-size: 16px; color: #101828; margin-bottom: 12px;">Workflow</div>
            <div class="workflow-step">
                <div class="step-number">1</div>
                <div class="step-content">
                    <div class="step-title">Census Input</div>
                    <div class="step-desc">Upload employee data with ZIP codes and family status</div>
                </div>
            </div>
            <div class="workflow-step">
                <div class="step-number">2</div>
                <div class="step-content">
                    <div class="step-title">ICHRA Dashboard</div>
                    <div class="step-desc">Compare current costs vs. ICHRA scenarios</div>
                </div>
            </div>
            <div class="workflow-step">
                <div class="step-number">3</div>
                <div class="step-content">
                    <div class="step-title">Contribution Strategies</div>
                    <div class="step-desc">Model % of LCSP, age curves, or fixed tiers</div>
                </div>
            </div>
            <div class="workflow-step">
                <div class="step-number">4</div>
                <div class="step-content">
                    <div class="step-title">Analysis & Export</div>
                    <div class="step-desc">Generate PDF/PPTX proposals with cost summaries</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div class="workflow-card">
            <div style="font-weight: 600; font-size: 16px; color: #101828; margin-bottom: 12px;">Features</div>
            <div class="feature-item"><span class="feature-icon">✓</span> Multi-state workforce support</div>
            <div class="feature-item"><span class="feature-icon">✓</span> ACA age curve calculations</div>
            <div class="feature-item"><span class="feature-icon">✓</span> IRS affordability analysis</div>
            <div class="feature-item"><span class="feature-icon">✓</span> LCSP by rating area</div>
            <div class="feature-item"><span class="feature-icon">✓</span> Plan benefit comparison</div>
            <div class="feature-item"><span class="feature-icon">✓</span> PDF & PowerPoint exports</div>
        </div>
        """, unsafe_allow_html=True)

    # System status
    st.markdown("<br>", unsafe_allow_html=True)

    status_col1, status_col2, status_col3 = st.columns(3)

    with status_col1:
        if test_connection():
            st.markdown('<span class="status-badge status-success">✓ Database Connected</span>', unsafe_allow_html=True)
        else:
            st.error("Database Connection Failed")

    with status_col2:
        st.markdown('<span class="status-badge status-info">📅 Plan Year: 2026</span>', unsafe_allow_html=True)

    with status_col3:
        st.markdown('<span class="status-badge status-info">📊 50 States + DC</span>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
