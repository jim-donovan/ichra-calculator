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

from constants import APP_CONFIG, PAGE_NAMES
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
            'by_class': {}
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

    # Navigation state
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 'home'


def main():
    """Main application entry point"""

    # Initialize session state
    initialize_session_state()

    # Sidebar navigation
    st.sidebar.title("📊 ICHRA Calculator")
    st.sidebar.markdown("---")

    # Navigation menu
    st.sidebar.subheader("Navigation")

    # Home/Welcome
    if st.sidebar.button("🏠 Home", width="stretch"):
        st.session_state.current_page = 'home'

    st.sidebar.markdown("---")
    st.sidebar.subheader("Calculator Steps")

    # Step navigation buttons
    pages = [
        ('census', PAGE_NAMES['census']),
        ('contribution_eval', PAGE_NAMES['contribution_eval']),
        ('employer_summary', PAGE_NAMES['employer_summary']),
        ('export', PAGE_NAMES['export'])
    ]

    for page_key, page_name in pages:
        if st.sidebar.button(page_name, width="stretch"):
            st.session_state.current_page = page_key

    # Sidebar info
    st.sidebar.markdown("---")
    st.sidebar.subheader("Quick Stats")

    if st.session_state.census_df is not None:
        st.sidebar.metric("Employees", len(st.session_state.census_df))
    else:
        st.sidebar.info("No census loaded")

    # Test database connection
    st.sidebar.markdown("---")
    if st.sidebar.button("🔌 Test Database Connection"):
        with st.sidebar:
            with st.spinner("Testing connection..."):
                if test_connection():
                    st.success("Database connected!")
                else:
                    st.error("Connection failed")

    # Main content area
    st.title(APP_CONFIG['title'])

    # Route to appropriate page
    if st.session_state.current_page == 'home':
        show_home_page()
    elif st.session_state.current_page == 'census':
        st.info("Navigate to pages in the sidebar or use the multi-page structure")
        st.markdown("Go to **pages/1_Census_Input.py** to enter employee census data")
    elif st.session_state.current_page == 'contribution_eval':
        st.info("Navigate to pages in the sidebar or use the multi-page structure")
        st.markdown("Go to **pages/2_Contribution_Evaluation.py** to evaluate ICHRA contributions")
    elif st.session_state.current_page == 'employer_summary':
        st.info("Navigate to pages in the sidebar or use the multi-page structure")
        st.markdown("Go to **pages/3_Employer_Summary.py** to view employer summary")
    elif st.session_state.current_page == 'export':
        st.info("Navigate to pages in the sidebar or use the multi-page structure")
        st.markdown("Go to **pages/4_Export_Results.py** to export results")


def show_home_page():
    """Display home/welcome page"""

    st.markdown("""
    ## Welcome to the ICHRA Plan Calculator

    This tool helps benefits consultants evaluate ICHRA (Individual Coverage Health
    Reimbursement Arrangement) contributions by comparing what employees could get
    on the Individual marketplace for their current contribution.

    ### Getting Started

    Follow these steps to create an ICHRA proposal:

    1. **📋 Employee Census** - Upload employee census data with current contribution info
    2. **💰 Contribution Evaluation** - AI-powered analysis of marketplace options vs. current costs
    3. **📊 Employer Summary** - Review aggregate employer cost savings
    4. **📄 Export Results** - Generate PDF proposal and export data

    ### Key Features

    - **AI-Powered Evaluation**: Intelligent comparison of current vs. marketplace options
    - **Cost Comparison**: See what employees can get for their current contribution
    - **Approved Class Support**: Set different contribution levels by employee class
    - **Rating Area Accuracy**: Automatic county-to-rating-area mapping for accurate pricing
    - **Professional Exports**: Generate client-ready PDF proposals

    ### Data Source

    This calculator uses official 2026 RBIS (Rate Based Insurance System) data from CMS,
    covering Individual marketplace plans across all 50 states + DC.

    ### Getting Help

    - Use the **sidebar navigation** to move between steps
    - Look for ℹ️ info boxes for guidance on each page
    - Quick stats in the sidebar show your progress

    ---

    **Ready to start?** Click on **1️⃣ Employee Census** in the sidebar to begin!
    """)

    # Show database connection status
    st.markdown("### System Status")
    col1, col2 = st.columns(2)

    with col1:
        if test_connection():
            st.success("✓ Database Connected")
        else:
            st.error("✗ Database Connection Failed")

    with col2:
        st.info("Data Year: 2026")

if __name__ == "__main__":
    main()
