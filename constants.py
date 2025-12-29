"""
Constants and reference data for ICHRA Calculator
Includes approved ICHRA classes and other configuration
"""

from pathlib import Path

# ICHRA Approved Employee Classes
# Source: IRS Notice 2018-88
APPROVED_CLASSES = [
    "Full-time employees",
    "Part-time employees",
    "Seasonal employees",
    "Employees in a waiting period",
    "Non-resident aliens with no US source income",
    "Employees in different rating areas",
    "Salaried employees",
    "Hourly employees (non-salaried)",
    "Employees covered by a collective bargaining agreement",
    "Temporary employees from staffing firm"
]

# Metal levels for ACA marketplace plans
METAL_LEVELS = [
    "Bronze",
    "Silver",
    "Gold",
    "Platinum",
    "Catastrophic"
]

# Common plan types
PLAN_TYPES = [
    "HMO",
    "PPO",
    "EPO",
    "POS"
]

# IRS Affordability Threshold (2026 Plan Year)
# Source: IRS Revenue Procedure 2024-35
# An ICHRA is affordable if employee's self-only LCSP cost ≤ 9.96% of household income
AFFORDABILITY_THRESHOLD_2026 = 0.0996  # 9.96% of household income

# ==============================================================================
# ACA 3:1 AGE RATING CURVE
# ==============================================================================
# Source: CMS Market Rating Reforms, 45 CFR 147.102
# Federal default age rating curve - ratio relative to age 21 (base = 1.000)
# Age 21 = 1.000 (base), Age 64 = 3.000 (maximum allowed ratio)
# These are the federal default age curve factors used by most states

ACA_AGE_CURVE = {
    # Children (0-20): All rated at 0.635 relative to age 21
    0: 0.635, 1: 0.635, 2: 0.635, 3: 0.635, 4: 0.635,
    5: 0.635, 6: 0.635, 7: 0.635, 8: 0.635, 9: 0.635,
    10: 0.635, 11: 0.635, 12: 0.635, 13: 0.635, 14: 0.635,
    15: 0.635, 16: 0.635, 17: 0.635, 18: 0.635, 19: 0.635,
    20: 0.635,
    # Young adults (21-24): Base rate at 1.000
    21: 1.000, 22: 1.000, 23: 1.000, 24: 1.000,
    # Adults (25-64): Gradual increase to 3.000
    25: 1.004, 26: 1.024, 27: 1.048, 28: 1.087, 29: 1.119,
    30: 1.135, 31: 1.159, 32: 1.183, 33: 1.198, 34: 1.214,
    35: 1.222, 36: 1.230, 37: 1.238, 38: 1.246, 39: 1.262,
    40: 1.278, 41: 1.302, 42: 1.325, 43: 1.357, 44: 1.397,
    45: 1.444, 46: 1.500, 47: 1.563, 48: 1.635, 49: 1.706,
    50: 1.786, 51: 1.865, 52: 1.952, 53: 2.040, 54: 2.135,
    55: 2.230, 56: 2.333, 57: 2.437, 58: 2.548, 59: 2.603,
    60: 2.714, 61: 2.810, 62: 2.873, 63: 2.952,
    # Seniors (64+): Maximum ratio of 3.000
    64: 3.000,
}

# Default family status multipliers for contribution calculations
# These approximate the cost increase for adding family members
DEFAULT_FAMILY_MULTIPLIERS = {
    'EE': 1.0,   # Employee Only (baseline)
    'ES': 1.5,   # Employee + Spouse (+50%)
    'EC': 1.3,   # Employee + Children (+30%)
    'F': 1.8,    # Family (+80%)
}

# All 50 US states + DC (full RBIS coverage)
TARGET_STATES = [
    "AK",  # Alaska
    "AL",  # Alabama
    "AR",  # Arkansas
    "AZ",  # Arizona
    "CA",  # California
    "CO",  # Colorado
    "CT",  # Connecticut
    "DC",  # District of Columbia
    "DE",  # Delaware
    "FL",  # Florida
    "GA",  # Georgia
    "HI",  # Hawaii
    "IA",  # Iowa
    "ID",  # Idaho
    "IL",  # Illinois
    "IN",  # Indiana
    "KS",  # Kansas
    "KY",  # Kentucky
    "LA",  # Louisiana
    "MA",  # Massachusetts
    "MD",  # Maryland
    "ME",  # Maine
    "MI",  # Michigan
    "MN",  # Minnesota
    "MO",  # Missouri
    "MS",  # Mississippi
    "MT",  # Montana
    "NC",  # North Carolina
    "ND",  # North Dakota
    "NE",  # Nebraska
    "NH",  # New Hampshire
    "NJ",  # New Jersey
    "NM",  # New Mexico
    "NV",  # Nevada
    "NY",  # New York
    "OH",  # Ohio
    "OK",  # Oklahoma
    "OR",  # Oregon
    "PA",  # Pennsylvania
    "RI",  # Rhode Island
    "SC",  # South Carolina
    "SD",  # South Dakota
    "TN",  # Tennessee
    "TX",  # Texas
    "UT",  # Utah
    "VA",  # Virginia
    "VT",  # Vermont
    "WA",  # Washington
    "WI",  # Wisconsin
    "WV",  # West Virginia
    "WY",  # Wyoming
]

# State names mapping (all 50 states + DC)
STATE_NAMES = {
    "AK": "Alaska",
    "AL": "Alabama",
    "AR": "Arkansas",
    "AZ": "Arizona",
    "CA": "California",
    "CO": "Colorado",
    "CT": "Connecticut",
    "DC": "District of Columbia",
    "DE": "Delaware",
    "FL": "Florida",
    "GA": "Georgia",
    "HI": "Hawaii",
    "IA": "Iowa",
    "ID": "Idaho",
    "IL": "Illinois",
    "IN": "Indiana",
    "KS": "Kansas",
    "KY": "Kentucky",
    "LA": "Louisiana",
    "MA": "Massachusetts",
    "MD": "Maryland",
    "ME": "Maine",
    "MI": "Michigan",
    "MN": "Minnesota",
    "MO": "Missouri",
    "MS": "Mississippi",
    "MT": "Montana",
    "NC": "North Carolina",
    "ND": "North Dakota",
    "NE": "Nebraska",
    "NH": "New Hampshire",
    "NJ": "New Jersey",
    "NM": "New Mexico",
    "NV": "Nevada",
    "NY": "New York",
    "OH": "Ohio",
    "OK": "Oklahoma",
    "OR": "Oregon",
    "PA": "Pennsylvania",
    "RI": "Rhode Island",
    "SC": "South Carolina",
    "SD": "South Dakota",
    "TN": "Tennessee",
    "TX": "Texas",
    "UT": "Utah",
    "VA": "Virginia",
    "VT": "Vermont",
    "WA": "Washington",
    "WI": "Wisconsin",
    "WV": "West Virginia",
    "WY": "Wyoming"
}

# Contribution percentage options (common employer contribution levels)
CONTRIBUTION_PERCENTAGES = [
    0, 10, 20, 25, 30, 40, 50, 55, 60, 70, 75, 80, 90, 100
]

# Age range for ACA marketplace plans
MIN_AGE = 15
MAX_AGE = 64
CHILD_RATING_AGE_MAX = 20  # Rated as children in ACA marketplace (ages 0-20)

# Special age bands in RBIS rate tables (stored as strings, not numeric ages)
AGE_BAND_0_14 = "0-14"      # Single rate for children 0-14
AGE_BAND_64_PLUS = "64 and over"  # Single rate for seniors 64+

# States that use family-tier rating instead of age-based rating
FAMILY_TIER_STATES = ['NY', 'VT']

# Key benefit types for comparison
KEY_BENEFIT_TYPES = [
    'Primary Care Visit to Treat an Injury or Illness',
    'Specialist Visit',
    'Generic Drugs',
    'Preferred Brand Drugs',
    'Emergency Room Services',
    'Inpatient Hospital Services',
    'Outpatient Surgery'
]

# Display names for benefits (shorter versions for tables)
BENEFIT_DISPLAY_NAMES = {
    'Primary Care Visit to Treat an Injury or Illness': 'PCP Visit',
    'Specialist Visit': 'Specialist',
    'Generic Drugs': 'Generic Rx',
    'Preferred Brand Drugs': 'Preferred Brand Rx',
    'Emergency Room Services': 'ER Visit',
    'Inpatient Hospital Services': 'Inpatient Hospital',
    'Outpatient Surgery': 'Outpatient Surgery'
}

# Deductible types
DEDUCTIBLE_TYPES = {
    'medical': 'Medical EHB Deductible',
    'drug': 'Drug EHB Deductible',
    'medical_moop': 'Medical EHB Out of Pocket Maximum',
    'drug_moop': 'Drug EHB Out of Pocket Maximum'
}

# Network types
NETWORK_TYPES = [
    'In Network',
    'Out of Network'
]

# Sample employee age brackets for comparison tables
AGE_COMPARISON_BRACKETS = [21, 27, 35, 45, 55, 63]

# ==============================================================================
# NEW CENSUS FORMAT (Single Standardized Format)
# ==============================================================================

# Required census columns
NEW_CENSUS_REQUIRED_COLUMNS = [
    'Employee Number',    # Unique employee identifier
    'Last Name',         # Employee last name
    'First Name',        # Employee first name
    'Home Zip',          # 5-digit ZIP code
    'Home State',        # 2-letter state code (e.g., NY, CA)
    'Family Status',     # EE, EC, ES, or F
    'EE DOB'            # Employee date of birth (MM/DD/YYYY)
]

# Optional census columns (dependent on Family Status)
NEW_CENSUS_OPTIONAL_COLUMNS = [
    'Spouse DOB',      # Required if Family Status = ES or F
    'Dep 2 DOB',       # Required if Family Status = EC or F (first child)
    'Dep 3 DOB',       # Optional (second child)
    'Dep 4 DOB',       # Optional (third child)
    'Dep 5 DOB',       # Optional (fourth child)
    'Dep 6 DOB',       # Optional (fifth child)
    'Monthly Income',  # Optional: Monthly household income for ACA affordability (e.g., $5000 or 5000)
    'Current EE Monthly',  # Optional: Employee's current monthly group plan contribution (e.g., $250 or 250)
    'Current ER Monthly',  # Optional: Employer's current monthly contribution for this employee
    '2026 Premium',    # Optional: Projected 2026 renewal premium for this employee (from rate table)
]

# Family Status codes
FAMILY_STATUS_CODES = {
    'EE': 'Employee Only',
    'EC': 'Employee + Children',
    'ES': 'Employee + Spouse',
    'F': 'Family (Employee + Spouse + Children)'
}

# All census columns (for template generation)
NEW_CENSUS_ALL_COLUMNS = NEW_CENSUS_REQUIRED_COLUMNS + NEW_CENSUS_OPTIONAL_COLUMNS

# ==============================================================================
# Dependent-related constants
# ==============================================================================

RELATIONSHIP_TYPES = ['spouse', 'child']

MAX_CHILDREN_PER_FAMILY = 10  # Reasonable maximum for UI

# Family tier types (for NY, VT)
FAMILY_TIERS = [
    'Individual',
    'Employee+Spouse',
    'Employee+Child(ren)',
    'Family'
]

# Dependent contribution strategies
DEPENDENT_CONTRIBUTION_STRATEGIES = [
    "Same as employee",
    "Different percentage",
    "Fixed dollar amount",
    "No contribution"
]

# Application configuration
APP_CONFIG = {
    'title': 'ICHRA Plan Calculator',
    'icon': '📊',
    'layout': 'wide',
    'initial_sidebar_state': 'expanded'
}

# Page names for navigation (4-page structure)
PAGE_NAMES = {
    'census': '1️⃣ Employee Census',
    'contribution_eval': '2️⃣ Contribution Evaluation',
    'employer_summary': '3️⃣ Employer Summary',
    'export': '4️⃣ Export Results'
}

# Help text
HELP_TEXT = {
    'census_upload': """
        Upload a CSV file with your employee census data.
        Required columns: employee_id, age, state, county
        Optional column: approved_class
    """,
    'approved_class': """
        ICHRA allows employers to offer different contribution amounts
        to different classes of employees. Select the class that applies
        to this group of employees.
    """,
    'contribution_percentage': """
        The percentage of the employee's premium that the employer will
        reimburse through the ICHRA. This can vary by approved class.
    """,
    'rating_area': """
        Insurance premiums vary by rating area (typically county-level).
        The calculator automatically determines rating areas based on
        employee county information.
    """,
    'group_plan_comparison': """
        Enter your current group health plan information to compare
        total costs between your current plan and ICHRA options.
    """,
    'dependents': """
        Include spouse and children to model total family coverage costs.

        - Dependents are rated individually by age in most states
        - NY and VT use family-tier rating
        - Children under 21 may be eligible for pediatric plans
        - Employers can set different contribution levels for dependents
    """,
    'dependent_contribution': """
        Set how much the employer contributes toward dependent coverage:

        - Same as employee: Apply same % to dependent premiums
        - Different percentage: Set separate % for dependents (e.g., 50%)
        - Fixed dollar amount: Contribute fixed $ per dependent per month
        - No contribution: Employees pay full cost of dependent coverage
    """
}

# Database table names (for reference)
DB_TABLES = {
    'plans': 'rbis_insurance_plan_20251019202724',
    'variants': 'rbis_insurance_plan_variant_20251019202724',
    'rates': 'rbis_insurance_plan_base_rates_20251019202724',
    'deductibles': 'rbis_insurance_plan_variant_ddctbl_moop_20251019202724',
    'benefits': 'rbis_insurance_plan_benefit_cost_share_20251019202724',
    'rating_areas': 'rbis_state_rating_area_amended'
}

# Export file naming convention
EXPORT_FILE_PREFIX = "ICHRA_Calculator"

# Date format for exports
DATE_FORMAT = "%Y-%m-%d"

# Default employer contribution by class (can be customized)
DEFAULT_CONTRIBUTIONS_BY_CLASS = {
    "Full-time employees": 75,
    "Part-time employees": 50,
    "Seasonal employees": 50,
    "Employees in a waiting period": 0,
    "Non-resident aliens with no US source income": 0,
    "Employees in different rating areas": 75,
    "Salaried employees": 75,
    "Hourly employees (non-salaried)": 60,
    "Employees covered by a collective bargaining agreement": 80,
    "Temporary employees from staffing firm": 25
}

# Color scheme for visualizations
COLOR_SCHEME = {
    'primary': '#1f77b4',
    'secondary': '#ff7f0e',
    'success': '#2ca02c',
    'warning': '#ff7f0e',
    'danger': '#d62728',
    'info': '#17becf'
}

# ==============================================================================
# POWERPOINT PROPOSAL GENERATOR
# ==============================================================================

# Template directory and file
PPTX_TEMPLATE_DIR = Path(__file__).parent / 'templates'
PPTX_TEMPLATE_PATH = PPTX_TEMPLATE_DIR / 'glove_template.pptx'

# GLOVE ICHRA Fit Score category weights (must sum to 100)
FIT_SCORE_WEIGHTS = {
    'cost_advantage': 25,        # Savings vs current/renewal costs
    'market_readiness': 20,      # Marketplace plan availability
    'workforce_fit': 20,         # Age distribution favorability
    'geographic_complexity': 15,  # Multi-state complexity (inverse)
    'employee_experience': 10,    # Transition ease based on family mix
    'admin_readiness': 10,        # Data quality and simplicity
}

# Fit Score thresholds for categorization
FIT_SCORE_THRESHOLDS = {
    'strong': 70,     # >= 70: Strong Fit
    'moderate': 50,   # >= 50: Moderate Fit
    'needs_review': 0 # < 50: Needs Review
}

if __name__ == "__main__":
    # Display constants for verification
    print("ICHRA Calculator Constants")
    print("=" * 50)
    print(f"\nApproved Classes: {len(APPROVED_CLASSES)}")
    for i, cls in enumerate(APPROVED_CLASSES, 1):
        print(f"  {i}. {cls}")

    print(f"\nTarget States: {len(TARGET_STATES)}")
    print(f"  {', '.join(TARGET_STATES)}")

    print(f"\nMetal Levels: {', '.join(METAL_LEVELS)}")
    print(f"Plan Types: {', '.join(PLAN_TYPES)}")

    print("\n✓ All constants loaded successfully!")
