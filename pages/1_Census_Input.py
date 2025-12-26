"""
Census Input Page - Streamlined Single Format
Handles employee census upload with ZIP codes, DOBs, and Family Status codes
"""

import streamlit as st
import pandas as pd
from database import get_database_connection
from utils import CensusProcessor, ContributionComparison
from constants import FAMILY_STATUS_CODES


# Page config
st.set_page_config(page_title="Census Input", page_icon="📊", layout="wide")

# Initialize session state
if 'db' not in st.session_state:
    st.session_state.db = get_database_connection()

if 'census_df' not in st.session_state:
    st.session_state.census_df = None

if 'dependents_df' not in st.session_state:
    st.session_state.dependents_df = None

# Header
st.title("📊 Employee Census Input")
st.markdown("Upload your employee census with ZIP codes, dates of birth, and family status.")

# ==============================================================================
# TEMPLATE DOWNLOAD
# ==============================================================================

st.header("📥 Step 1: Download Census Template")

col1, col2 = st.columns([2, 1])

with col1:
    st.markdown("""
    **Census Format Requirements:**

    **Required Columns:**
    - **Employee Number** - Unique identifier for each employee
    - **Home Zip** - 5-digit ZIP code
    - **Home State** - 2-letter state code (e.g., NY, CA, PA)
    - **Family Status** - Code indicating family coverage:
      - **EE** = Employee Only
      - **ES** = Employee + Spouse
      - **EC** = Employee + Children
      - **F** = Family (Employee + Spouse + Children)
    - **EE DOB** - Employee date of birth (M/D/YY format)

    **Optional Columns** (based on Family Status):
    - **Spouse DOB** - Required if Family Status = ES or F
    - **Dep 2 DOB** through **Dep 6 DOB** - Child dates of birth (required if Family Status = EC or F)

    **Current Group Plan Contributions** (optional - for cost comparison):
    - **Current EE Monthly** - Employee's current monthly contribution (e.g., "$250" or "250")
    - **Current ER Monthly** - Employer's current monthly contribution for this employee
    - **2026 Premium** - Projected 2026 renewal premium for this employee (from carrier rate table)

    *If provided, enables per-employee comparison between current/renewal and ICHRA costs.*
    """)

with col2:
    # Generate and offer template download
    template_csv = CensusProcessor.create_new_census_template()

    st.download_button(
        label="📄 Download Template CSV",
        data=template_csv,
        file_name="census_template.csv",
        mime="text/csv",
        help="Download a CSV template with example data"
    )

    st.info("The template includes 4 example employees showing all Family Status codes.")

st.markdown("---")

# ==============================================================================
# FILE UPLOAD
# ==============================================================================

st.header("📤 Step 2: Upload Your Census File")

# Check if census is already loaded in session state
if st.session_state.census_df is not None:
    st.success(f"✅ Census already loaded with {len(st.session_state.census_df)} employees")

    # Show summary and option to replace
    col_a, col_b = st.columns([3, 1])
    with col_a:
        st.markdown(f"**Current Census:** {len(st.session_state.census_df)} employees")
        if st.session_state.dependents_df is not None and not st.session_state.dependents_df.empty:
            st.markdown(f"**Dependents:** {len(st.session_state.dependents_df)} dependents")
    with col_b:
        if st.button("📤 Upload New Census", type="secondary"):
            st.session_state.census_df = None
            st.session_state.dependents_df = None
            st.session_state.contribution_analysis = {}
            st.rerun()

    # Display the loaded census data
    st.markdown("---")
    st.subheader("📋 Loaded Census Data")

    employees_df = st.session_state.census_df
    dependents_df = st.session_state.dependents_df if st.session_state.dependents_df is not None else pd.DataFrame()

    # Check for per-employee contribution data
    if ContributionComparison.has_individual_contributions(employees_df):
        contrib_totals = ContributionComparison.aggregate_contribution_totals(employees_df)
        st.info(f"""
        **📊 Per-Employee Contribution Data Found:**
        - Employees with data: **{contrib_totals['employees_with_data']}**
        - Total current EE contributions: **${contrib_totals['total_current_ee_monthly']:,.2f}/mo** (${contrib_totals['total_current_ee_annual']:,.2f}/yr)
        - Total current ER contributions: **${contrib_totals['total_current_er_monthly']:,.2f}/mo** (${contrib_totals['total_current_er_annual']:,.2f}/yr)

        *Per-employee cost comparisons will be available in **Employer Summary**.*
        """)

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Employees", len(employees_df))

    with col2:
        num_deps = len(dependents_df) if not dependents_df.empty else 0
        st.metric("Total Dependents", num_deps)

    with col3:
        total_lives = len(employees_df) + num_deps
        st.metric("Covered Lives", total_lives)

    with col4:
        unique_states = employees_df['state'].nunique()
        st.metric("States", unique_states)

    st.markdown("---")

    tab1, tab2, tab3 = st.tabs(["👥 Employees", "👶 Dependents", "📍 Geography"])

    with tab1:
        st.markdown("### 📊 Employee Demographics")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Total Employees:** {len(employees_df)}")
            st.markdown(f"**Average Age:** {employees_df['age'].mean():.1f} years")
            st.markdown(f"**Median Age:** {employees_df['age'].median():.1f} years")

        with col2:
            st.markdown("**Age Range:**")
            st.markdown(f"- Youngest: {employees_df['age'].min():.0f} years")
            st.markdown(f"- Oldest: {employees_df['age'].max():.0f} years")

        # Employee Only (EE) Class Statistics
        ee_employees = employees_df[employees_df['family_status'] == 'EE']
        if len(ee_employees) > 0:
            st.markdown("---")
            st.markdown("### 👤 Employee Only (EE) Class")

            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**Count:** {len(ee_employees)} employees")
                st.markdown(f"**Average Age:** {ee_employees['age'].mean():.1f} years")
                st.markdown(f"**Median Age:** {ee_employees['age'].median():.1f} years")

            with col2:
                st.markdown("**Age Range:**")
                st.markdown(f"- Youngest: {ee_employees['age'].min():.0f} years")
                st.markdown(f"- Oldest: {ee_employees['age'].max():.0f} years")

        st.markdown("---")
        st.markdown("### 👨‍👩‍👧‍👦 Family Status Breakdown")
        status_counts = employees_df['family_status'].value_counts()
        for status, count in status_counts.items():
            status_name = FAMILY_STATUS_CODES.get(status, status)
            pct = (count / len(employees_df)) * 100
            st.markdown(f"- **{status_name}:** {count} employees ({pct:.1f}%)")

        st.markdown("---")
        st.markdown("### 📋 Employee Data")
        display_cols = ['employee_id', 'first_name', 'last_name', 'age', 'state', 'county', 'family_status']
        if 'current_ee_monthly' in employees_df.columns:
            display_cols.extend(['current_ee_monthly', 'current_er_monthly'])
        st.dataframe(employees_df[display_cols], width="stretch")

    with tab2:
        if not dependents_df.empty:
            st.markdown("### 👶 Dependent Overview")

            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**Total Dependents:** {len(dependents_df)}")
                total_lives = len(employees_df) + len(dependents_df)
                ratio = total_lives / len(employees_df)
                st.markdown(f"**Coverage Burden:** {ratio:.2f}:1")
                st.markdown(f"**Average Age:** {dependents_df['age'].mean():.1f} years")
                st.markdown(f"**Median Age:** {dependents_df['age'].median():.1f} years")

            with col2:
                st.markdown("**Age Range:**")
                st.markdown(f"- Youngest: {dependents_df['age'].min():.0f} years")
                st.markdown(f"- Oldest: {dependents_df['age'].max():.0f} years")

            st.markdown("---")
            # Overall breakdown by relationship
            rel_counts = dependents_df['relationship'].value_counts()
            st.markdown("**By Relationship:**")
            for rel, count in rel_counts.items():
                pct = (count / len(dependents_df)) * 100
                st.markdown(f"- **{rel.title()}s:** {count} ({pct:.1f}%)")

            # Children analysis
            children_df = dependents_df[dependents_df['relationship'] == 'child']
            spouses_df = dependents_df[dependents_df['relationship'] == 'spouse']

            if not children_df.empty:
                st.markdown("---")
                st.markdown("### 👧👦 Children Analysis")

                # Get employees with children
                employees_with_children = employees_df[employees_df['family_status'].isin(['EC', 'F'])]

                col1, col2 = st.columns(2)

                with col1:
                    st.markdown("**Overall Statistics:**")
                    st.markdown(f"- Total Children: {len(children_df)}")
                    st.markdown(f"- Families with Children: {len(employees_with_children)}")
                    if len(employees_with_children) > 0:
                        avg_children = len(children_df) / len(employees_with_children)
                        st.markdown(f"- Avg Children per Family: {avg_children:.1f}")

                with col2:
                    st.markdown("**Age Statistics:**")
                    st.markdown(f"- Average Age: {children_df['age'].mean():.1f} years")
                    st.markdown(f"- Median Age: {children_df['age'].median():.1f} years")
                    st.markdown(f"- Age Range: {children_df['age'].min():.0f} - {children_df['age'].max():.0f} years")

                # Breakdown by family type
                st.markdown("---")
                st.markdown("### 📊 Children by Family Type")

                # Employee + Children (EC)
                ec_employees = employees_df[employees_df['family_status'] == 'EC']
                if len(ec_employees) > 0:
                    ec_children = children_df[children_df['employee_id'].isin(ec_employees['employee_id'])]
                    st.markdown("**Employee + Children (EC):**")
                    st.markdown(f"- Families: {len(ec_employees)}")
                    st.markdown(f"- Total Children: {len(ec_children)}")
                    if len(ec_children) > 0:
                        avg_ec = len(ec_children) / len(ec_employees)
                        st.markdown(f"- Avg per Family: {avg_ec:.1f}")
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
                        st.markdown(f"- Avg per Family: {avg_f:.1f}")
                        st.markdown(f"- Avg Age: {f_children['age'].mean():.1f} years | Median: {f_children['age'].median():.1f} years")
                        st.markdown(f"- Age Range: {int(f_children['age'].min())} - {int(f_children['age'].max())} years")
                else:
                    st.markdown("**Full Family (F):** No F families in census")

            # Spouse analysis
            if not spouses_df.empty:
                st.markdown("---")
                st.markdown("### 💑 Spouse Analysis")

                # Get employees with spouses
                employees_with_spouses = employees_df[employees_df['family_status'].isin(['ES', 'F'])]

                col1, col2 = st.columns(2)

                with col1:
                    st.markdown("**Coverage Statistics:**")
                    st.markdown(f"- Total Spouses: {len(spouses_df)}")
                    st.markdown(f"- Families with Spouse Coverage: {len(employees_with_spouses)}")

                with col2:
                    st.markdown("**Overall Age Statistics:**")
                    st.markdown(f"- Average Age: {spouses_df['age'].mean():.1f} years")
                    st.markdown(f"- Median Age: {spouses_df['age'].median():.1f} years")

                st.markdown("---")
                st.markdown("**By Family Type:**")

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
            st.markdown("### 📋 Dependent Data")
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

        st.markdown("**Employees by County:**")
        county_counts = employees_df.groupby(['state', 'county']).size().reset_index(name='count')
        county_counts = county_counts.sort_values('count', ascending=False)
        st.dataframe(county_counts, width="stretch")

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

        try:
            # Security validation for file upload
            MAX_FILE_SIZE_MB = 10
            MAX_ROWS = 10000

            # Check file size
            file_size_mb = len(uploaded_file.getvalue()) / (1024 * 1024)
            if file_size_mb > MAX_FILE_SIZE_MB:
                st.error(f"❌ File too large: {file_size_mb:.1f}MB. Maximum allowed is {MAX_FILE_SIZE_MB}MB.")
                st.stop()

            # Read the uploaded file, forcing ZIP codes to be read as strings
            # This preserves leading zeros and prevents float conversion (e.g., 60005.0)
            # Auto-detect delimiter (handles comma, tab, semicolon, etc.)
            import csv
            import io

            # Read file content to detect delimiter
            try:
                file_content = uploaded_file.getvalue().decode('utf-8')
            except UnicodeDecodeError:
                st.error("❌ File encoding error. Please save the file as UTF-8 encoded CSV.")
                st.stop()

            # Use csv.Sniffer to detect delimiter
            try:
                sample = file_content[:4096]  # Sample first 4KB
                dialect = csv.Sniffer().sniff(sample, delimiters=',\t;|')
                detected_delimiter = dialect.delimiter
            except csv.Error:
                # Default to comma if detection fails
                detected_delimiter = ','

            # Read with detected delimiter
            uploaded_file.seek(0)  # Reset file pointer
            census_raw = pd.read_csv(
                io.StringIO(file_content),
                dtype={'Home Zip': str},
                sep=detected_delimiter
            )

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

            with st.spinner("Validating data, looking up counties from ZIP codes, and extracting dependents..."):
                try:
                    # Parse using new format
                    employees_df, dependents_df = CensusProcessor.parse_new_census_format(
                        census_raw,
                        st.session_state.db
                    )

                    # Store in session state
                    st.session_state.census_df = employees_df
                    st.session_state.dependents_df = dependents_df

                    # DEBUG: Verify what rating areas were stored in session state
                    import logging
                    logging.warning("=" * 80)
                    logging.warning("DEBUG: Census stored in session state. Rating area DISTRIBUTION by state:")
                    for state in sorted(employees_df['state'].unique()):
                        state_df = employees_df[employees_df['state'] == state]
                        rating_area_counts = state_df['rating_area_id'].value_counts().sort_index()
                        logging.warning(f"  {state}:")
                        for ra, count in rating_area_counts.items():
                            logging.warning(f"    Rating Area {ra}: {count} employees")
                    logging.warning("=" * 80)

                    # Show success summary
                    st.success("✅ Census processed successfully!")

                    # Check for per-employee contribution data
                    if ContributionComparison.has_individual_contributions(employees_df):
                        contrib_totals = ContributionComparison.aggregate_contribution_totals(employees_df)
                        st.info(f"""
                        **📊 Per-Employee Contribution Data Found:**
                        - Employees with data: **{contrib_totals['employees_with_data']}**
                        - Total current EE contributions: **${contrib_totals['total_current_ee_monthly']:,.2f}/mo** (${contrib_totals['total_current_ee_annual']:,.2f}/yr)
                        - Total current ER contributions: **${contrib_totals['total_current_er_monthly']:,.2f}/mo** (${contrib_totals['total_current_er_annual']:,.2f}/yr)

                        *Per-employee cost comparisons will be available in **Employer Summary**.*
                        """)

                    # Summary metrics
                    col1, col2, col3, col4 = st.columns(4)

                    with col1:
                        st.metric("Total Employees", len(employees_df))

                    with col2:
                        num_deps = len(dependents_df) if not dependents_df.empty else 0
                        st.metric("Total Dependents", num_deps)

                    with col3:
                        total_lives = len(employees_df) + num_deps
                        st.metric("Covered Lives", total_lives)

                    with col4:
                        unique_states = employees_df['state'].nunique()
                        st.metric("States", unique_states)

                    # Detailed breakdown
                    st.markdown("---")
                    st.subheader("📊 Census Summary")

                    tab1, tab2, tab3 = st.tabs(["👥 Employees", "👶 Dependents", "📍 Geography"])

                    with tab1:
                        st.markdown("### 📊 Employee Demographics")

                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown(f"**Total Employees:** {len(employees_df)}")
                            st.markdown(f"**Average Age:** {employees_df['age'].mean():.1f} years")
                            st.markdown(f"**Median Age:** {employees_df['age'].median():.1f} years")

                        with col2:
                            st.markdown("**Age Range:**")
                            st.markdown(f"- Youngest: {employees_df['age'].min():.0f} years")
                            st.markdown(f"- Oldest: {employees_df['age'].max():.0f} years")

                        # Employee Only (EE) Class Statistics
                        ee_employees = employees_df[employees_df['family_status'] == 'EE']
                        if len(ee_employees) > 0:
                            st.markdown("---")
                            st.markdown("### 👤 Employee Only (EE) Class")

                            col1, col2 = st.columns(2)
                            with col1:
                                st.markdown(f"**Count:** {len(ee_employees)} employees")
                                st.markdown(f"**Average Age:** {ee_employees['age'].mean():.1f} years")
                                st.markdown(f"**Median Age:** {ee_employees['age'].median():.1f} years")

                            with col2:
                                st.markdown("**Age Range:**")
                                st.markdown(f"- Youngest: {ee_employees['age'].min():.0f} years")
                                st.markdown(f"- Oldest: {ee_employees['age'].max():.0f} years")

                        st.markdown("---")
                        st.markdown("### 👨‍👩‍👧‍👦 Family Status Breakdown")
                        status_counts = employees_df['family_status'].value_counts()
                        for status, count in status_counts.items():
                            status_name = FAMILY_STATUS_CODES.get(status, status)
                            pct = (count / len(employees_df)) * 100
                            st.markdown(f"- **{status_name}:** {count} employees ({pct:.1f}%)")

                        st.markdown("---")
                        st.markdown("### 📋 Employee Data")
                        display_cols = ['employee_id', 'first_name', 'last_name', 'age', 'state', 'county', 'family_status']
                        if 'current_ee_monthly' in employees_df.columns:
                            display_cols.extend(['current_ee_monthly', 'current_er_monthly'])
                        st.dataframe(employees_df[display_cols], width="stretch")

                    with tab2:
                        if not dependents_df.empty:
                            st.markdown("### 👶 Dependent Overview")

                            col1, col2 = st.columns(2)
                            with col1:
                                st.markdown(f"**Total Dependents:** {len(dependents_df)}")
                                total_lives = len(employees_df) + len(dependents_df)
                                ratio = total_lives / len(employees_df)
                                st.markdown(f"**Coverage Burden:** {ratio:.2f}:1")
                                st.markdown(f"**Average Age:** {dependents_df['age'].mean():.1f} years")
                                st.markdown(f"**Median Age:** {dependents_df['age'].median():.1f} years")

                            with col2:
                                st.markdown("**Age Range:**")
                                st.markdown(f"- Youngest: {dependents_df['age'].min():.0f} years")
                                st.markdown(f"- Oldest: {dependents_df['age'].max():.0f} years")

                            st.markdown("---")
                            # Overall breakdown by relationship
                            rel_counts = dependents_df['relationship'].value_counts()
                            st.markdown("**By Relationship:**")
                            for rel, count in rel_counts.items():
                                pct = (count / len(dependents_df)) * 100
                                st.markdown(f"- **{rel.title()}s:** {count} ({pct:.1f}%)")

                            # Children analysis
                            children_df = dependents_df[dependents_df['relationship'] == 'child']
                            spouses_df = dependents_df[dependents_df['relationship'] == 'spouse']

                            if not children_df.empty:
                                st.markdown("---")
                                st.markdown("### 👧👦 Children Analysis")

                                # Get employees with children
                                employees_with_children = employees_df[employees_df['family_status'].isin(['EC', 'F'])]

                                col1, col2 = st.columns(2)

                                with col1:
                                    st.markdown("**Overall Statistics:**")
                                    st.markdown(f"- Total Children: {len(children_df)}")
                                    st.markdown(f"- Families with Children: {len(employees_with_children)}")
                                    if len(employees_with_children) > 0:
                                        avg_children = len(children_df) / len(employees_with_children)
                                        st.markdown(f"- Avg Children per Family: {avg_children:.1f}")

                                with col2:
                                    st.markdown("**Age Statistics:**")
                                    st.markdown(f"- Average Age: {children_df['age'].mean():.1f} years")
                                    st.markdown(f"- Median Age: {children_df['age'].median():.1f} years")
                                    st.markdown(f"- Age Range: {children_df['age'].min():.0f} - {children_df['age'].max():.0f} years")

                                # Breakdown by family type
                                st.markdown("---")
                                st.markdown("### 📊 Children by Family Type")

                                # Employee + Children (EC)
                                ec_employees = employees_df[employees_df['family_status'] == 'EC']
                                if len(ec_employees) > 0:
                                    ec_children = children_df[children_df['employee_id'].isin(ec_employees['employee_id'])]
                                    st.markdown("**Employee + Children (EC):**")
                                    st.markdown(f"- Families: {len(ec_employees)}")
                                    st.markdown(f"- Total Children: {len(ec_children)}")
                                    if len(ec_children) > 0:
                                        avg_ec = len(ec_children) / len(ec_employees)
                                        st.markdown(f"- Avg per Family: {avg_ec:.1f}")
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
                                        st.markdown(f"- Avg per Family: {avg_f:.1f}")
                                        st.markdown(f"- Avg Age: {f_children['age'].mean():.1f} years | Median: {f_children['age'].median():.1f} years")
                                        st.markdown(f"- Age Range: {int(f_children['age'].min())} - {int(f_children['age'].max())} years")
                                else:
                                    st.markdown("**Full Family (F):** No F families in census")

                            # Spouse analysis
                            if not spouses_df.empty:
                                st.markdown("---")
                                st.markdown("### 💑 Spouse Analysis")

                                # Get employees with spouses
                                employees_with_spouses = employees_df[employees_df['family_status'].isin(['ES', 'F'])]

                                col1, col2 = st.columns(2)

                                with col1:
                                    st.markdown("**Coverage Statistics:**")
                                    st.markdown(f"- Total Spouses: {len(spouses_df)}")
                                    st.markdown(f"- Families with Spouse Coverage: {len(employees_with_spouses)}")

                                with col2:
                                    st.markdown("**Overall Age Statistics:**")
                                    st.markdown(f"- Average Age: {spouses_df['age'].mean():.1f} years")
                                    st.markdown(f"- Median Age: {spouses_df['age'].median():.1f} years")

                                st.markdown("---")
                                st.markdown("**By Family Type:**")

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
                            st.markdown("### 📋 Dependent Data")
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

                        st.markdown("**Employees by County:**")
                        county_counts = employees_df.groupby(['state', 'county']).size().reset_index(name='count')
                        county_counts = county_counts.sort_values('count', ascending=False)
                        st.dataframe(county_counts, width="stretch")

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
                    with st.expander("Technical Details"):
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

with st.expander("ℹ️ Help & Instructions"):
    st.markdown("""
    ## Census File Format

    Your census file should be a CSV file (comma or tab-delimited) with the following structure:

    ### Required Columns

    1. **Employee Number** - Unique identifier for each employee (e.g., EMP001, 12345)
    2. **Home Zip** - 5-digit ZIP code (e.g., 10001, 90210)
       - Leading zeros will be preserved (e.g., 00501 for Holtsville, NY)
    3. **Home State** - 2-letter state code (e.g., NY, CA, PA, FL)
    4. **Family Status** - One of these codes:
       - **EE** = Employee Only (no dependents)
       - **ES** = Employee + Spouse (spouse coverage, no children)
       - **EC** = Employee + Children (children only, no spouse)
       - **F** = Family (employee + spouse + children)
    5. **EE DOB** - Employee date of birth (flexible format: m/d/yy, mm/dd/yy, m/d/yyyy, mm/dd/yyyy)

    ### Optional Columns (Conditional)

    - **Spouse DOB** - Required if Family Status is ES or F
    - **Dep 2 DOB** - First child DOB (required if Family Status is EC or F)
    - **Dep 3 DOB** through **Dep 6 DOB** - Additional children (optional)

    ### Example Rows

    | Employee Number | Home Zip | Home State | Family Status | EE DOB | Spouse DOB | Dep 2 DOB | Dep 3 DOB |
    |----------------|----------|------------|---------------|--------|------------|-----------|-----------|
    | EMP001 | 10001 | NY | F | 05/15/1985 | 07/22/1987 | 03/10/2015 | 11/05/2017 |
    | EMP002 | 60601 | IL | ES | 12/03/1978 | 06/18/1980 | | |
    | EMP003 | 18801 | PA | EC | 08/25/1990 | | 02/14/2018 | |
    | EMP004 | 33101 | FL | EE | 10/30/1995 | | | |

    ### Notes

    - **File formats:** Both comma-delimited (.csv) and tab-delimited (.tsv/.txt) files are supported
    - **Date formats accepted:** Flexible formats supported
      - With 4-digit year: `m/d/yyyy` or `mm/dd/yyyy` (e.g., 3/15/1985 or 03/15/1985)
      - With 2-digit year: `m/d/yy` or `mm/dd/yy` (e.g., 3/15/85 or 03/15/85)
      - 2-digit year logic: 00-29 → 2000s, 30-99 → 1900s
    - ZIP codes will be automatically looked up to determine county and rating area
    - Family Status must match the dependent DOBs provided:
      - ES and F require Spouse DOB
      - EC and F require at least one child DOB (Dep 2 DOB)
    - Children must be age 0-26
    - Employees must be age 18-64

    ### Common Errors

    - **Invalid ZIP code** - ZIP not found in database for the specified state
    - **Missing required field** - ES/F without Spouse DOB, or EC/F without child DOB
    - **Invalid date format** - Accepted formats: m/d/yy, mm/dd/yy, m/d/yyyy, mm/dd/yyyy
    - **Age out of range** - Employee too young (<18) or too old (>64), or child over 26
    """)

# Show current census status in sidebar
with st.sidebar:
    st.markdown("### Census Status")

    if st.session_state.census_df is not None:
        num_employees = len(st.session_state.census_df)
        num_dependents = len(st.session_state.dependents_df) if st.session_state.dependents_df is not None else 0

        st.success(f"✅ **{num_employees}** employees loaded")

        if num_dependents > 0:
            st.info(f"👨‍👩‍👧‍👦 **{num_dependents}** dependents")

        st.metric("Covered Lives", num_employees + num_dependents)

        if st.button("Clear Census"):
            st.session_state.census_df = None
            st.session_state.dependents_df = None
            st.rerun()
    else:
        st.warning("No census loaded")
        st.info("Upload a census file or generate sample data")
