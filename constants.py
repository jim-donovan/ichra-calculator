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

# Federal Poverty Level (FPL) Safe Harbor (2026 Plan Year)
# Source: HHS Poverty Guidelines (projected for 2026)
# The FPL Safe Harbor allows employers to use FPL instead of actual employee income
# to determine affordability. If employee's LCSP cost ≤ 9.96% of FPL, it's deemed
# affordable for ALL employees regardless of their actual income.
# 2025 FPL (single, mainland) = $15,060; estimated 2026 with ~2.3% increase
FPL_ANNUAL_2026 = 15400  # $15,400/year for single individual (48 contiguous states)
FPL_MONTHLY_2026 = FPL_ANNUAL_2026 / 12  # ~$1,283/month
FPL_SAFE_HARBOR_THRESHOLD_2026 = FPL_MONTHLY_2026 * AFFORDABILITY_THRESHOLD_2026  # ~$128/month

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

# ==============================================================================
# PLAN COMPARISON (Page 9)
# ==============================================================================
# Configuration for comparing current employer plan vs marketplace alternatives

# Benefit comparison rows for side-by-side table
# Format: (attribute_name, display_label, lower_is_better)
# lower_is_better=True means lower values are better (costs, deductibles)
# lower_is_better=False means it's a categorical/boolean comparison
COMPARISON_BENEFIT_ROWS = [
    # Plan Overview (categorical - no color coding)
    ('plan_type', 'Plan Type', False),
    ('hsa_eligible', 'HSA Eligible', False),
    # Deductibles (lower is better)
    ('individual_deductible', 'Individual Deductible', True),
    ('family_deductible', 'Family Deductible', True),
    # Out-of-Pocket Maximum (lower is better)
    ('individual_oop_max', 'Individual OOP Max', True),
    ('family_oop_max', 'Family OOP Max', True),
    # Coinsurance (lower is better - employee pays less)
    ('coinsurance_pct', 'Coinsurance %', True),
    # Copays (lower is better)
    ('pcp_copay', 'PCP Visit Copay', True),
    ('specialist_copay', 'Specialist Copay', True),
    ('er_copay', 'ER Visit Copay', True),
    ('generic_rx_copay', 'Generic Rx Copay', True),
    ('preferred_rx_copay', 'Preferred Brand Rx Copay', True),
    ('specialty_rx_copay', 'Specialty Rx Copay', True),
]

# Match score algorithm weights (must sum to 100)
COMPARISON_MATCH_WEIGHTS = {
    'deductible': 25,      # Individual deductible similarity
    'oopm': 25,            # Out-of-pocket max similarity
    'plan_type': 15,       # Plan type match (HMO, PPO, etc.)
    'hsa': 10,             # HSA eligibility match
    'copays': 25,          # PCP/Specialist/Rx copay similarity
}

# Comparison result indicators
COMPARISON_INDICATORS = {
    'better': '🟢',    # Marketplace plan is better
    'similar': '🟡',   # Within 10% - essentially equivalent
    'worse': '🔴',     # Marketplace plan is less generous
}

# Similarity threshold (percentage difference considered "similar")
COMPARISON_SIMILARITY_THRESHOLD = 10  # Within 10% = similar

# Maximum plans to compare side-by-side
MAX_COMPARISON_PLANS = 5

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
    'Current Plan Name',   # Optional: Plan name for matching to extracted plans (e.g., 'Gold PPO', 'Silver HMO')
    '2026 Premium',    # Optional: Projected 2026 renewal premium for this employee (from rate table)
    'Gap Insurance',   # Optional: Current employer gap insurance monthly cost (added to ER costs)
]

# Family Status codes
FAMILY_STATUS_CODES = {
    'EE': 'Employee Only',
    'EC': 'Employee + Children',
    'ES': 'Employee + Spouse',
    'F': 'Family (Employee + Spouse + Children)'
}

# All census columns (for template generation) - ordered for user convenience
# Monthly Income in column F for easy data entry
NEW_CENSUS_ALL_COLUMNS = [
    'Employee Number',    # A
    'Last Name',          # B
    'First Name',         # C
    'Home Zip',           # D
    'Home State',         # E
    'Monthly Income',     # F - moved here for convenience
    'Family Status',      # G
    'EE DOB',             # H
    'Spouse DOB',         # I
    'Dep 2 DOB',          # J
    'Dep 3 DOB',          # K
    'Dep 4 DOB',          # L
    'Dep 5 DOB',          # M
    'Dep 6 DOB',          # N
    'Current EE Monthly', # O
    'Current ER Monthly', # P
    'Current Plan Name',  # Q
    '2026 Premium',       # R
    'Gap Insurance',      # S
]

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
    'title': 'Canopy',
    'icon': '🌿',
    'layout': 'wide',
    'initial_sidebar_state': 'expanded'
}

# Page names for navigation (9-page structure)
PAGE_NAMES = {
    'census': '1️⃣ Employee census',
    'dashboard': '2️⃣ ICHRA dashboard',
    'contribution_eval': '3️⃣ Contribution evaluation',
    'lcsp_analysis': '4️⃣ LCSP analysis',
    'employer_summary': '5️⃣ Employer summary',
    'individual_analysis': '6️⃣ Individual analysis',
    'export': '7️⃣ Export results',
    'proposal': '8️⃣ Proposal generator',
    'plan_comparison': '9️⃣ Plan comparison'
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

# ==============================================================================
# 2026 ACA SUBSIDY CALCULATION CONSTANTS
# ==============================================================================
# Used for Unaffordability Analysis - calculating potential ACA subsidies
# when employees decline ICHRA due to unaffordability

# Federal Poverty Level (FPL) 2026 by household size
# Source: HHS Poverty Guidelines (projected for 2026)
# Note: Alaska and Hawaii have higher FPL amounts
FPL_2026_BY_HOUSEHOLD_SIZE = {
    1: 15960,   # Single individual
    2: 21640,
    3: 27320,
    4: 33000,
    5: 38680,
    6: 44360,
    7: 50040,
    8: 55720,
    # Add $5,680 per additional person above 8
}
FPL_2026_PER_ADDITIONAL_PERSON = 5680

# Alaska FPL 2026 (approximately 25% higher)
FPL_2026_ALASKA = {
    1: 19950,
    2: 27050,
    3: 34150,
    4: 41250,
    5: 48350,
    6: 55450,
    7: 62550,
    8: 69650,
}
FPL_2026_ALASKA_PER_ADDITIONAL = 7100

# Hawaii FPL 2026 (approximately 15% higher)
FPL_2026_HAWAII = {
    1: 18360,
    2: 24890,
    3: 31420,
    4: 37950,
    5: 44480,
    6: 51010,
    7: 57540,
    8: 64070,
}
FPL_2026_HAWAII_PER_ADDITIONAL = 6530

# 2026 ACA Applicable Percentage Table for Premium Tax Credit
# Source: IRS Revenue Procedure (The Finance Buff 2026 projections)
# Format: (lower_fpl_pct, upper_fpl_pct, lower_applicable_pct, upper_applicable_pct)
# Linear interpolation between boundaries
ACA_APPLICABLE_PERCENTAGE_2026 = [
    # (FPL lower %, FPL upper %, applicable % at lower, applicable % at upper)
    (100, 133, 2.10, 2.10),      # 100-133% FPL: flat 2.10%
    (133, 150, 3.14, 4.19),      # 133-150% FPL: interpolate 3.14% to 4.19%
    (150, 200, 4.19, 6.60),      # 150-200% FPL: interpolate 4.19% to 6.60%
    (200, 250, 6.60, 8.44),      # 200-250% FPL: interpolate 6.60% to 8.44%
    (250, 300, 8.44, 9.96),      # 250-300% FPL: interpolate 8.44% to 9.96%
    (300, 400, 9.96, 9.96),      # 300-400% FPL: flat 9.96%
]

# Above 400% FPL: No subsidy available
ACA_SUBSIDY_FPL_CAP = 400

# Medicare eligibility age (used for filtering subsidy eligibility)
MEDICARE_ELIGIBILITY_AGE = 65

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

# ICHRA Fit Score category weights (must sum to 100)
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

# ==============================================================================
# ICHRA DASHBOARD CONFIGURATION
# ==============================================================================
# Centralized configuration for ICHRA comparison dashboard
# These values replace hardcoded constants throughout the dashboard

# Plan years for comparison
CURRENT_PLAN_YEAR = 2025
RENEWAL_PLAN_YEAR = 2026

# Cooperative Health Access Plan configuration
COOPERATIVE_CONFIG = {
    'default_discount_ratio': 0.72,  # Default: Cooperative cost as % of Silver LCSP
    'dpc_monthly_cost': 70,          # Direct Primary Care monthly cost ($70/mo)
    'employer_pays_100_pct': True,   # Cooperative is typically 100% employer-paid
}

# Metal level cost ratios relative to Silver (used as fallback when actual rates unavailable)
# Bronze typically ~80% of Silver cost, Gold ~120%
METAL_COST_RATIOS = {
    'Bronze': 0.80,
    'Silver': 1.00,
    'Gold': 1.20,
}

# Default adoption rate assumptions for blended cost calculations
# These are user-adjustable via dashboard sliders
DEFAULT_ADOPTION_RATES = {
    'Cooperative': 70,    # 70% expected to choose cooperative
    'ICHRA Silver': 20,   # 20% expected to choose Silver marketplace plan
    'ICHRA Gold': 10,     # 10% expected to choose Gold marketplace plan
}

# Workforce demographic thresholds
OLDER_POPULATION_WARNING_AGE = 45  # Show warning if avg employee age exceeds this

# Display placeholder values for messaging when actual data unavailable
# These appear in "Current plan problems" section
DISPLAY_PLACEHOLDERS = {
    'typical_deductible': 6300,          # $6,300 typical group plan deductible
    'employee_annual_cost_min': 14000,   # Low estimate for annual employee cost
    'employee_annual_cost_max': 36000,   # High estimate for annual employee cost
}

# Tier colors for workforce composition charts
TIER_COLORS = {
    'EE': '#0047AB',   # Cobalt - Employee Only
    'ES': '#6366f1',   # Indigo - Employee + Spouse
    'EC': '#0d9488',   # Teal - Employee + Children
    'F': '#0891b2',    # Cyan - Family
}

# Tier display labels
TIER_LABELS = {
    'EE': 'EE Only',
    'ES': 'EE + Spouse',
    'EC': 'EE + Children',
    'F': 'Family',
}

# ==============================================================================
# CONTRIBUTION PATTERN DETECTION
# ==============================================================================
# Configuration for detecting employer contribution patterns (percentage vs flat-rate)
# from census data (Current EE Monthly / Current ER Monthly columns)

# Maximum coefficient of variation (CV) to consider a pattern "consistent"
# CV = std_dev / mean; 0.10 = 10% variance allowed
PATTERN_VARIANCE_THRESHOLD = 0.10

# Minimum number of employees in a tier for reliable pattern detection
# Tiers with fewer employees will be flagged for manual review
PATTERN_MIN_SAMPLE_SIZE = 3

# Default ER contribution percentage when pattern cannot be detected
PATTERN_DEFAULT_ER_PCT = 0.60  # 60% employer / 40% employee

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
