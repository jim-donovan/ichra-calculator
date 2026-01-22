"""
Subsidy Optimization Page - Optimal Uniform Contribution Calculator

Helps non-ALE employers (<46 employees) find the optimal ICHRA contribution
that maximizes total employee benefit across the entire workforce.

Key Insight: The optimal contribution balances:
- PTC-eligible employees who may be better off declining ICHRA to claim PTCs
- Non-PTC-eligible employees who need the ICHRA since it's their only benefit

Algorithm:
For each possible contribution amount, calculate total workforce benefit
and return the contribution that maximizes total benefit.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from io import BytesIO
import sys
from pathlib import Path
from typing import Dict, List, Tuple
from dataclasses import dataclass
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import get_database_connection, DatabaseConnection
from queries import PlanQueries
from utils import render_feedback_sidebar
from pdf_subsidy_optimization_renderer import (
    SubsidyOptimizationPDFRenderer,
    build_subsidy_optimization_data,
)
from subsidy_utils import (
    get_household_size,
    get_fpl_for_household,
    get_applicable_percentage,
    FPL_2025_BASE,
    AFFORDABILITY_THRESHOLD_2026,
)
from contribution_eval.utils import build_census_context
from census_schema import (
    COL_STATE, COL_RATING_AREA, COL_AGE, COL_FAMILY_STATUS,
    COL_EMPLOYEE_ID, COL_FIRST_NAME, COL_LAST_NAME, COL_MONTHLY_INCOME,
    get_age_band,
)
from constants import ACA_AGE_CURVE

# =============================================================================
# CONSTANTS
# =============================================================================

AFFORDABILITY_PCT = AFFORDABILITY_THRESHOLD_2026  # 0.0996 for 2026
FPL_400_SINGLE = FPL_2025_BASE * 4  # 400% FPL for single person


# =============================================================================
# CSS STYLING
# =============================================================================

SUBSIDY_PAGE_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&family=Inter:wght@400;700&display=swap');

:root {
    --gray-50: #f9fafb;
    --gray-100: #f3f4f6;
    --gray-200: #e5e7eb;
    --gray-300: #d1d5db;
    --gray-400: #9ca3af;
    --gray-500: #6b7280;
    --gray-600: #4b5563;
    --gray-700: #374151;
    --gray-800: #1f2937;
    --gray-900: #111827;
    --blue-50: #eff6ff;
    --blue-100: #dbeafe;
    --blue-500: #3b82f6;
    --blue-600: #2563eb;
    --blue-700: #1d4ed8;
    --green-50: #f0fdf4;
    --green-100: #dcfce7;
    --green-500: #22c55e;
    --green-600: #16a34a;
    --green-700: #15803d;
    --amber-50: #fffbeb;
    --amber-100: #fef3c7;
    --amber-500: #f59e0b;
    --amber-600: #d97706;
    --red-50: #fef2f2;
    --red-100: #fee2e2;
    --red-500: #ef4444;
    --red-600: #dc2626;
    --teal-400: #2dd4bf;
    --teal-500: #14b8a6;
    --teal-600: #0d9488;
    --brand-primary: #0047AB;
    --brand-light: #E8F1FD;
    --brand-accent: #37BEAE;
}

[data-testid="stSidebar"] { background-color: #F0F4FA; }
[data-testid="stSidebarNav"] a { background-color: transparent !important; }
[data-testid="stSidebarNav"] a[aria-selected="true"] {
    background-color: var(--brand-light) !important;
    border-left: 3px solid var(--brand-primary) !important;
}

.hero-section {
    background: linear-gradient(135deg, #ffffff 0%, #e8f1fd 100%);
    border-radius: 12px;
    padding: 32px;
    margin-bottom: 24px;
    border-left: 4px solid #37BEAE;
}

.summary-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
    margin-bottom: 24px;
}

.summary-card {
    background: white;
    border-radius: 10px;
    padding: 20px;
    text-align: center;
    border: 1px solid var(--gray-200);
}

.summary-card--primary { background: var(--brand-light); border-color: var(--brand-primary); }
.summary-card--success { background: var(--green-50); border-color: var(--green-500); }
.summary-card--accent { background: rgba(55, 190, 174, 0.1); border-color: var(--brand-accent); }

.summary-label {
    font-size: 12px;
    font-weight: 600;
    color: var(--gray-500);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 8px;
}

.summary-value {
    font-size: 28px;
    font-weight: 700;
    color: var(--gray-900);
}

.summary-card--primary .summary-value { color: var(--brand-primary); }
.summary-card--success .summary-value { color: var(--green-600); }
.summary-card--accent .summary-value { color: var(--brand-accent); }

.summary-sublabel {
    font-size: 12px;
    color: var(--gray-400);
    margin-top: 4px;
}

.analysis-table {
    width: 100%;
    border-collapse: collapse;
    font-family: 'Poppins', sans-serif;
    margin-bottom: 24px;
}

.analysis-table th {
    padding: 14px 16px;
    text-align: center;
    font-weight: 600;
    font-size: 13px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    border-bottom: 2px solid var(--gray-200);
    background: var(--gray-50);
    color: var(--gray-700);
}

.analysis-table th.col-band { text-align: left; background: var(--gray-100); }
.analysis-table th.col-source { background: var(--brand-accent); color: white; }
.analysis-table th.col-benefit { background: var(--brand-primary); color: white; }

.analysis-table td {
    padding: 14px 16px;
    text-align: center;
    font-family: 'Inter', sans-serif;
    font-size: 15px;
    border-bottom: 1px solid var(--gray-200);
    color: var(--gray-700);
}

.analysis-table td.band-cell {
    text-align: left;
    font-weight: 600;
    color: var(--gray-800);
    background: var(--gray-50);
}

.analysis-table td.source-ptc { background: rgba(55, 190, 174, 0.1); color: var(--teal-600); font-weight: 600; }
.analysis-table td.source-ichra { background: rgba(0, 71, 171, 0.05); color: var(--brand-primary); font-weight: 600; }

.analysis-table tr.total-row { background: var(--gray-100); font-weight: 700; }
.analysis-table tr.total-row td { border-top: 2px solid var(--gray-300); font-weight: 700; color: var(--gray-900); }

.tradeoff-banner {
    background: linear-gradient(135deg, var(--blue-50) 0%, rgba(55, 190, 174, 0.1) 100%);
    border: 2px solid var(--blue-500);
    border-radius: 12px;
    padding: 20px 24px;
    margin: 24px 0;
}

.tradeoff-title {
    font-size: 16px;
    font-weight: 700;
    color: var(--blue-700);
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    gap: 8px;
}

.tradeoff-content {
    font-size: 15px;
    color: var(--gray-700);
    line-height: 1.6;
}

.tradeoff-highlight-gain { color: var(--green-600); font-weight: 600; }
.tradeoff-highlight-loss { color: var(--amber-600); font-weight: 600; }

.comparison-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 24px;
    margin-bottom: 24px;
}

.comparison-card {
    background: white;
    border-radius: 12px;
    padding: 24px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    border: 2px solid var(--gray-200);
}

.comparison-card--standard { border-color: var(--gray-300); }
.comparison-card--optimal { border-color: var(--brand-accent); box-shadow: 0 0 0 3px rgba(55, 190, 174, 0.15); }

.comparison-title {
    font-size: 18px;
    font-weight: 600;
    margin-bottom: 16px;
    display: flex;
    align-items: center;
    gap: 8px;
}

.comparison-card--standard .comparison-title { color: var(--gray-700); }
.comparison-card--optimal .comparison-title { color: var(--brand-accent); }

.comparison-row {
    display: flex;
    justify-content: space-between;
    padding: 10px 0;
    border-bottom: 1px solid var(--gray-100);
}

.comparison-row:last-child { border-bottom: none; }
.comparison-label { color: var(--gray-500); font-size: 14px; }
.comparison-value { font-weight: 600; font-size: 16px; color: var(--gray-800); }
.comparison-value--positive { color: var(--green-600); }
.comparison-value--negative { color: var(--red-600); }
.comparison-value--highlight { color: var(--brand-accent); }

.warning-banner {
    background: var(--amber-50);
    border: 2px solid var(--amber-500);
    border-radius: 10px;
    padding: 16px 24px;
    margin-bottom: 24px;
}

.warning-banner-title { font-size: 18px; font-weight: 600; color: var(--amber-600); margin-bottom: 8px; }
.warning-banner-text { font-size: 14px; color: var(--gray-700); }

.info-banner {
    background: var(--blue-50);
    border: 1px solid var(--blue-500);
    border-radius: 10px;
    padding: 16px 24px;
    margin-bottom: 24px;
}

.info-banner-title { font-size: 16px; font-weight: 600; color: var(--blue-700); margin-bottom: 4px; }
.info-banner-text { font-size: 14px; color: var(--gray-600); }

.text-muted { color: var(--gray-500); }
.text-small { font-size: 13px; }

/* Employee Breakdown Table */
.employee-table {
    width: 100%;
    border-collapse: collapse;
    font-family: 'Poppins', sans-serif;
    margin: 24px 0;
    border-radius: 10px;
    overflow: hidden;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}

.employee-table th {
    padding: 14px 12px;
    text-align: center;
    font-weight: 600;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    background: var(--gray-100);
    color: var(--gray-700);
    border-bottom: 2px solid var(--gray-200);
}

.employee-table th.col-name { text-align: left; min-width: 140px; }
.employee-table th.col-standard { background: var(--gray-200); color: var(--gray-700); }
.employee-table th.col-optimal { background: var(--brand-accent); color: white; }

.employee-table td {
    padding: 12px;
    text-align: center;
    font-family: 'Inter', sans-serif;
    font-size: 14px;
    border-bottom: 1px solid var(--gray-100);
    color: var(--gray-700);
}

.employee-table td.name-cell {
    text-align: left;
    font-weight: 500;
    color: var(--gray-800);
    white-space: nowrap;
}

.employee-table td.source-ptc {
    background: rgba(55, 190, 174, 0.12);
    color: var(--teal-600);
    font-weight: 600;
}

.employee-table td.source-ichra {
    background: rgba(0, 71, 171, 0.06);
    color: var(--brand-primary);
    font-weight: 600;
}

.employee-table td.diff-positive {
    color: var(--green-600);
    font-weight: 700;
    background: var(--green-50);
}

.employee-table td.diff-negative {
    color: var(--red-500);
    font-weight: 600;
}

.employee-table tr:hover { background: var(--gray-50); }
.employee-table tr.total-row { background: var(--gray-100); }
.employee-table tr.total-row:hover { background: var(--gray-100); }
.employee-table tr.total-row td {
    border-top: 2px solid var(--gray-300);
    font-weight: 700;
    color: var(--gray-900);
    padding: 14px 12px;
}
</style>
"""

# =============================================================================
# PAGE CONFIG
# =============================================================================

st.set_page_config(
    page_title="Subsidy Optimization",
    page_icon="💎",
    layout="wide"
)

st.markdown(SUBSIDY_PAGE_CSS, unsafe_allow_html=True)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class EmployeeAnalysis:
    """Analysis for a single employee."""
    employee_id: str
    name: str
    age: int
    family_status: str
    annual_income: float
    monthly_income: float
    fpl_percentage: float
    lcsp: float
    slcsp: float
    is_ptc_eligible: bool
    is_medicare: bool
    has_income: bool
    income_band: str


@dataclass
class ContributionScenario:
    """Results for a specific contribution amount."""
    contribution: float
    total_monthly_benefit: float
    total_annual_benefit: float
    employees_taking_ichra: int
    employees_taking_ptc: int
    avg_ichra_benefit: float
    avg_ptc_benefit: float


@dataclass
class OptimizationResult:
    """Complete optimization analysis."""
    optimal_contribution: float
    optimal_total_benefit: float
    all_scenarios: List[ContributionScenario]
    employee_analyses: List[EmployeeAnalysis]
    income_band_summary: Dict[str, Dict]


# =============================================================================
# CORE ALGORITHM
# =============================================================================

def estimate_ptc(annual_income: float, slcsp: float, family_status: str = 'EE') -> float:
    """
    Estimate monthly PTC based on ACA sliding scale.

    Args:
        annual_income: Annual household income
        slcsp: Second Lowest Cost Silver Plan premium (monthly)
        family_status: EE, ES, EC, or F

    Returns:
        Estimated monthly PTC amount
    """
    if annual_income <= 0 or slcsp <= 0:
        return 0.0

    household_size = get_household_size(family_status)
    fpl = get_fpl_for_household(household_size)
    fpl_pct = annual_income / fpl

    # Above 400% FPL = no PTC
    if fpl_pct > 4.0:
        return 0.0

    # ACA sliding scale expected contribution percentages
    if fpl_pct <= 1.0:
        expected_pct = 0.0
    elif fpl_pct <= 1.5:
        expected_pct = 0.0 + (fpl_pct - 1.0) * 0.04 / 0.5  # 0% to 4%
    elif fpl_pct <= 2.0:
        expected_pct = 0.04 + (fpl_pct - 1.5) * 0.025 / 0.5  # 4% to 6.5%
    elif fpl_pct <= 2.5:
        expected_pct = 0.065 + (fpl_pct - 2.0) * 0.02 / 0.5  # 6.5% to 8.5%
    else:
        expected_pct = 0.085  # 8.5% cap for 250-400% FPL

    expected_contribution = (annual_income * expected_pct) / 12
    ptc = max(0.0, slcsp - expected_contribution)
    return ptc


def get_income_band(fpl_pct: float) -> str:
    """Get income band label based on FPL percentage."""
    if fpl_pct <= 150:
        return "<150% FPL"
    elif fpl_pct <= 250:
        return "150-250% FPL"
    elif fpl_pct <= 400:
        return "250-400% FPL"
    else:
        return ">400% FPL"


def calculate_age_curve_contribution(
    base_contribution: float,
    base_age: int,
    employee_age: int,
) -> float:
    """
    Calculate contribution for an employee using the ACA 3:1 age curve.

    Args:
        base_contribution: The contribution at the base age
        base_age: The reference age (e.g., 21, 40)
        employee_age: The employee's actual age

    Returns:
        Scaled contribution based on the age curve ratio
    """
    # Clamp ages to valid range (21-64 for adults)
    base_age_clamped = max(21, min(64, base_age))
    emp_age_clamped = max(21, min(64, employee_age))

    base_ratio = ACA_AGE_CURVE.get(base_age_clamped, 1.0)
    emp_ratio = ACA_AGE_CURVE.get(emp_age_clamped, 1.0)

    # Scale: contribution = base * (emp_ratio / base_ratio)
    return round(base_contribution * (emp_ratio / base_ratio), 2)


def calculate_employee_benefit(
    emp: EmployeeAnalysis,
    contribution: float,
) -> Tuple[float, str]:
    """
    Calculate employee benefit at a given contribution level.

    Returns:
        Tuple of (benefit_amount, benefit_source)
        benefit_source is 'ICHRA' or 'PTC'
    """
    if emp.is_medicare or not emp.has_income:
        # Medicare employees or those without income data get ICHRA
        return contribution, 'ICHRA'

    # Calculate affordability
    affordability_threshold = emp.monthly_income * AFFORDABILITY_PCT
    employee_share = emp.lcsp - contribution
    is_affordable = employee_share <= affordability_threshold

    if is_affordable:
        # ICHRA is affordable - employee must accept
        return contribution, 'ICHRA'

    if not emp.is_ptc_eligible:
        # Not PTC eligible (>400% FPL) - must take ICHRA even if unaffordable
        return contribution, 'ICHRA'

    # ICHRA is unaffordable AND employee is PTC eligible
    # Compare: ICHRA benefit vs PTC benefit
    ptc_amount = estimate_ptc(emp.annual_income, emp.slcsp, emp.family_status)

    # Employee will choose the better option
    if ptc_amount > contribution:
        return ptc_amount, 'PTC'
    else:
        return contribution, 'ICHRA'


def calculate_optimal_contribution(
    employees: List[EmployeeAnalysis],
    step: int = 10,
) -> OptimizationResult:
    """
    Find the optimal uniform contribution that maximizes total workforce benefit.

    Args:
        employees: List of employee analyses with LCSP/SLCSP data
        step: Contribution increment to test (default $10)

    Returns:
        OptimizationResult with optimal contribution and all scenarios
    """
    # Find max LCSP for upper bound
    max_lcsp = max(emp.lcsp for emp in employees if emp.lcsp > 0) if employees else 800

    scenarios = []

    # Test contribution amounts from $0 to max LCSP
    for contribution in range(0, int(max_lcsp) + step, step):
        total_benefit = 0.0
        ichra_count = 0
        ptc_count = 0
        ichra_benefits = []
        ptc_benefits = []

        for emp in employees:
            if emp.is_medicare:
                continue  # Skip Medicare employees

            benefit, source = calculate_employee_benefit(emp, contribution)
            total_benefit += benefit

            if source == 'ICHRA':
                ichra_count += 1
                ichra_benefits.append(benefit)
            else:
                ptc_count += 1
                ptc_benefits.append(benefit)

        scenarios.append(ContributionScenario(
            contribution=float(contribution),
            total_monthly_benefit=total_benefit,
            total_annual_benefit=total_benefit * 12,
            employees_taking_ichra=ichra_count,
            employees_taking_ptc=ptc_count,
            avg_ichra_benefit=sum(ichra_benefits) / len(ichra_benefits) if ichra_benefits else 0,
            avg_ptc_benefit=sum(ptc_benefits) / len(ptc_benefits) if ptc_benefits else 0,
        ))

    # Find optimal (maximum total benefit)
    optimal = max(scenarios, key=lambda s: s.total_monthly_benefit)

    # Build income band summary at optimal contribution
    band_summary = {}
    for band in ["<150% FPL", "150-250% FPL", "250-400% FPL", ">400% FPL"]:
        band_emps = [e for e in employees if e.income_band == band and not e.is_medicare]
        if band_emps:
            benefits_sources = [calculate_employee_benefit(e, optimal.contribution) for e in band_emps]
            avg_lcsp = sum(e.lcsp for e in band_emps) / len(band_emps)

            # Determine if band is affordable at optimal contribution
            affordable_count = sum(1 for e in band_emps
                                   if (e.lcsp - optimal.contribution) <= (e.monthly_income * AFFORDABILITY_PCT))
            is_affordable = affordable_count > len(band_emps) / 2  # Majority

            # Primary benefit source for this band
            ptc_count = sum(1 for _, src in benefits_sources if src == 'PTC')
            primary_source = 'PTC' if ptc_count > len(band_emps) / 2 else 'ICHRA'

            avg_benefit = sum(b for b, _ in benefits_sources) / len(benefits_sources)

            band_summary[band] = {
                'count': len(band_emps),
                'avg_lcsp': avg_lcsp,
                'is_affordable': is_affordable,
                'primary_source': primary_source,
                'avg_benefit': avg_benefit,
                'total_benefit': sum(b for b, _ in benefits_sources),
            }

    return OptimizationResult(
        optimal_contribution=optimal.contribution,
        optimal_total_benefit=optimal.total_monthly_benefit,
        all_scenarios=scenarios,
        employee_analyses=employees,
        income_band_summary=band_summary,
    )


# =============================================================================
# DATA LOADING
# =============================================================================

def analyze_workforce(
    census_df: pd.DataFrame,
    db: DatabaseConnection,
) -> List[EmployeeAnalysis]:
    """Load employee data and LCSP/SLCSP information."""
    analyses = []

    # Build location list for batch LCSP/SLCSP query
    # Census_df is normalized, so use canonical column names from census_schema
    employee_locations = []
    for idx, row in census_df.iterrows():
        age = int(row.get(COL_AGE, 30) or 30)
        age_band = get_age_band(age)
        state_code = str(row.get(COL_STATE, '')).upper()
        rating_area = row.get(COL_RATING_AREA, 1)

        if state_code and rating_area:
            employee_locations.append({
                'state_code': state_code,
                'rating_area_id': int(rating_area) if pd.notna(rating_area) else 1,
                'age_band': str(age_band),
                'idx': idx,
            })

    # Fetch LCSP and SLCSP in batch
    lcsp_slcsp_df = PlanQueries.get_lcsp_and_slcsp_batch(db, employee_locations)

    # Create lookup dictionary
    plan_lookup = {}
    if not lcsp_slcsp_df.empty:
        for _, row in lcsp_slcsp_df.iterrows():
            key = (row['state_code'], int(row['rating_area_id']), int(row['age_band']))
            if key not in plan_lookup:
                plan_lookup[key] = {'lcsp': None, 'slcsp': None}
            rank = int(row.get('plan_rank', 1))
            if rank == 1:
                plan_lookup[key]['lcsp'] = float(row['premium'])
            elif rank == 2:
                plan_lookup[key]['slcsp'] = float(row['premium'])

    # Analyze each employee
    for idx, row in census_df.iterrows():
        emp_id = str(row.get(COL_EMPLOYEE_ID, idx))
        first_name = str(row.get(COL_FIRST_NAME, ''))
        last_name = str(row.get(COL_LAST_NAME, ''))
        name = f"{first_name} {last_name}".strip() or f"Employee {emp_id}"

        age = int(row.get(COL_AGE, 30) or 30)
        age_band = get_age_band(age)
        family_status = str(row.get(COL_FAMILY_STATUS, 'EE')).upper()
        state_code = str(row.get(COL_STATE, '')).upper()
        rating_area_val = row.get(COL_RATING_AREA, 1)
        rating_area = int(rating_area_val) if pd.notna(rating_area_val) else 1

        is_medicare = age >= 65

        # Get income (use canonical column name from normalized census)
        monthly_income = None
        if COL_MONTHLY_INCOME in row.index:
            val = row.get(COL_MONTHLY_INCOME)
            if val is not None and not pd.isna(val) and val != '':
                if isinstance(val, (int, float)):
                    monthly_income = float(val) if val > 0 else None
                else:
                    try:
                        monthly_income = float(str(val).replace('$', '').replace(',', '').strip())
                        if monthly_income <= 0:
                            monthly_income = None
                    except:
                        monthly_income = None

        has_income = monthly_income is not None and monthly_income > 0
        annual_income = monthly_income * 12 if has_income else 0

        # Get LCSP/SLCSP
        lookup_key = (state_code, rating_area, age_band)
        plans = plan_lookup.get(lookup_key, {'lcsp': None, 'slcsp': None})
        lcsp = plans['lcsp'] or 400.0
        slcsp = plans['slcsp'] or lcsp * 1.05

        # Calculate FPL percentage
        fpl_pct = 0.0
        if has_income:
            household_size = get_household_size(family_status)
            fpl = get_fpl_for_household(household_size)
            fpl_pct = (annual_income / fpl) * 100

        is_ptc_eligible = has_income and fpl_pct <= 400 and not is_medicare
        income_band = get_income_band(fpl_pct) if has_income else "No Income Data"

        analyses.append(EmployeeAnalysis(
            employee_id=emp_id,
            name=name,
            age=age,
            family_status=family_status,
            annual_income=annual_income,
            monthly_income=monthly_income or 0,
            fpl_percentage=fpl_pct,
            lcsp=lcsp,
            slcsp=slcsp,
            is_ptc_eligible=is_ptc_eligible,
            is_medicare=is_medicare,
            has_income=has_income,
            income_band=income_band,
        ))

    return analyses


# =============================================================================
# RENDERING FUNCTIONS
# =============================================================================

def render_optimization_chart(scenarios: List[ContributionScenario], optimal: float) -> None:
    """Render the optimization curve using Plotly."""
    contributions = [s.contribution for s in scenarios]
    benefits = [s.total_monthly_benefit for s in scenarios]

    fig = go.Figure()

    # Main curve
    fig.add_trace(go.Scatter(
        x=contributions,
        y=benefits,
        mode='lines',
        name='Total Workforce Benefit',
        line=dict(color='#0047AB', width=3),
        fill='tozeroy',
        fillcolor='rgba(0, 71, 171, 0.1)',
    ))

    # Optimal point
    optimal_benefit = next(s.total_monthly_benefit for s in scenarios if s.contribution == optimal)
    fig.add_trace(go.Scatter(
        x=[optimal],
        y=[optimal_benefit],
        mode='markers+text',
        name=f'Optimal: ${optimal:,.0f}/mo',
        marker=dict(color='#37BEAE', size=16, symbol='star'),
        text=[f'${optimal:,.0f}'],
        textposition='top center',
        textfont=dict(size=14, color='#37BEAE'),
    ))

    fig.update_layout(
        title=dict(
            text='Contribution Optimization Curve',
            font=dict(size=18, family='Poppins'),
        ),
        xaxis=dict(
            title='Monthly Contribution ($)',
            gridcolor='#e5e7eb',
            tickformat='$,.0f',
        ),
        yaxis=dict(
            title='Total Monthly Workforce Benefit ($)',
            gridcolor='#e5e7eb',
            tickformat='$,.0f',
        ),
        hovermode='x unified',
        showlegend=True,
        legend=dict(yanchor='top', y=0.99, xanchor='right', x=0.99),
        height=400,
        margin=dict(l=60, r=40, t=60, b=60),
        plot_bgcolor='white',
    )

    st.plotly_chart(fig, width='stretch')


def render_analysis_table(band_summary: Dict[str, Dict], optimal_contribution: float) -> str:
    """Render the contribution analysis table."""
    rows = []
    total_employees = 0
    total_benefit = 0.0

    band_order = ["<150% FPL", "150-250% FPL", "250-400% FPL", ">400% FPL"]

    for band in band_order:
        data = band_summary.get(band)
        if data:
            count = data['count']
            total_employees += count
            total_benefit += data['total_benefit']

            affordable_text = "Yes" if data['is_affordable'] else "No"
            source = data['primary_source']
            source_class = 'source-ptc' if source == 'PTC' else 'source-ichra'

            # Escape < for HTML
            display_band = band.replace('<', '&lt;').replace('>', '&gt;')

            rows.append(f'<tr><td class="band-cell">{display_band}</td><td>{count}</td><td>${data["avg_lcsp"]:,.0f}</td><td>{affordable_text}</td><td class="{source_class}">{source}</td><td>${data["avg_benefit"]:,.0f}</td></tr>')

    if total_employees == 0:
        return '<div class="info-banner"><div class="info-banner-title">No Eligible Employees</div><div class="info-banner-text">All employees are either Medicare-eligible or missing income data.</div></div>'

    avg_benefit = total_benefit / total_employees if total_employees > 0 else 0
    rows.append(f'<tr class="total-row"><td class="band-cell">TOTAL</td><td>{total_employees}</td><td>—</td><td>—</td><td>—</td><td>${avg_benefit:,.0f}</td></tr>')

    return f'<table class="analysis-table"><thead><tr><th class="col-band">Income Band</th><th>Employees</th><th>Avg LCSP</th><th>ICHRA Affordable?</th><th class="col-source">Benefit Source</th><th class="col-benefit">Avg Benefit</th></tr></thead><tbody>{"".join(rows)}</tbody></table><p class="text-small text-muted">At optimal contribution of ${optimal_contribution:,.0f}/mo. "Benefit Source" shows whether employees primarily receive value from ICHRA or PTC.</p>'


def render_tradeoff_callout(
    result: OptimizationResult,
    standard_contribution: float,
) -> str:
    """Render the prominent tradeoff callout comparing standard vs optimal."""
    optimal = result.optimal_contribution
    employees = [e for e in result.employee_analyses if not e.is_medicare and e.has_income]

    if not employees:
        return ''

    # Calculate total benefits at each contribution level
    standard_benefits = [calculate_employee_benefit(e, standard_contribution) for e in employees]
    optimal_benefits = [calculate_employee_benefit(e, optimal) for e in employees]

    total_benefit_standard = sum(b[0] for b in standard_benefits)
    total_benefit_optimal = sum(b[0] for b in optimal_benefits)

    # Count benefit sources at optimal
    ptc_count_optimal = sum(1 for b in optimal_benefits if b[1] == 'PTC')
    ichra_count_optimal = sum(1 for b in optimal_benefits if b[1] == 'ICHRA')

    # Employer cost (only pays for ICHRA, not PTC)
    employer_cost_standard = standard_contribution * len(employees)
    employer_cost_optimal = optimal * ichra_count_optimal

    # Differences
    employee_benefit_diff = total_benefit_optimal - total_benefit_standard
    employer_cost_diff = employer_cost_optimal - employer_cost_standard

    gain_class = 'tradeoff-highlight-gain'
    loss_class = 'tradeoff-highlight-loss'

    # Employee benefit line
    if employee_benefit_diff > 0:
        benefit_line = f'<strong class="{gain_class}">Employees gain ${employee_benefit_diff:,.0f}/mo</strong> total benefit at optimal vs standard.'
    elif employee_benefit_diff < 0:
        benefit_line = f'<strong class="{loss_class}">Employees lose ${abs(employee_benefit_diff):,.0f}/mo</strong> total benefit at optimal vs standard.'
    else:
        benefit_line = f'<strong>Employees receive the same total benefit</strong> at both contribution levels.'

    # Employer cost line
    if employer_cost_diff > 0:
        cost_line = f'<strong class="{loss_class}">Employer spends ${employer_cost_diff:,.0f}/mo more</strong> at optimal (${employer_cost_optimal:,.0f}) vs standard (${employer_cost_standard:,.0f}).'
    elif employer_cost_diff < 0:
        cost_line = f'<strong class="{gain_class}">Employer saves ${abs(employer_cost_diff):,.0f}/mo</strong> at optimal (${employer_cost_optimal:,.0f}) vs standard (${employer_cost_standard:,.0f}).'
    else:
        cost_line = f'<strong>Employer cost is the same</strong> at both contribution levels (${employer_cost_optimal:,.0f}/mo).'

    # Benefit source breakdown
    if ptc_count_optimal > 0:
        source_line = f'At optimal: <strong>{ptc_count_optimal}</strong> employees take PTC, <strong>{ichra_count_optimal}</strong> take ICHRA.'
    else:
        source_line = f'At optimal: All <strong>{ichra_count_optimal}</strong> employees take ICHRA (no PTC access at this level).'

    return f'''<div class="tradeoff-banner">
<div class="tradeoff-title">⚖️ Comparison: Baseline ${standard_contribution:,.0f}/mo vs Optimal ${optimal:,.0f}/mo</div>
<div class="tradeoff-content">
{benefit_line}<br><br>
{cost_line}<br><br>
{source_line}
</div>
</div>'''


def render_comparison_cards(
    emp: EmployeeAnalysis,
    optimal_contribution: float,
    standard_contribution: float,
) -> str:
    """Render side-by-side comparison for selected employee."""
    # Baseline scenario
    std_benefit, std_source = calculate_employee_benefit(emp, standard_contribution)
    std_ee_cost = max(0, emp.lcsp - standard_contribution)
    std_ptc = 0 if std_source == 'ICHRA' else estimate_ptc(emp.annual_income, emp.slcsp, emp.family_status)

    # Optimal scenario
    opt_benefit, opt_source = calculate_employee_benefit(emp, optimal_contribution)
    opt_ee_cost = max(0, emp.lcsp - optimal_contribution)
    opt_ptc = 0 if opt_source == 'ICHRA' else estimate_ptc(emp.annual_income, emp.slcsp, emp.family_status)

    # Determine which is better
    better = 'optimal' if opt_benefit > std_benefit else ('standard' if std_benefit > opt_benefit else 'tie')

    std_card = f'<div class="comparison-card comparison-card--standard"><div class="comparison-title">📊 Standard ICHRA (${standard_contribution:,.0f}/mo)</div><div class="comparison-row"><span class="comparison-label">ICHRA Contribution</span><span class="comparison-value">${standard_contribution:,.0f}/mo</span></div><div class="comparison-row"><span class="comparison-label">Employee Cost for LCSP</span><span class="comparison-value">${std_ee_cost:,.0f}/mo</span></div><div class="comparison-row"><span class="comparison-label">PTC Available</span><span class="comparison-value">${std_ptc:,.0f}/mo</span></div><div class="comparison-row"><span class="comparison-label">Total Benefit</span><span class="comparison-value">${std_benefit:,.0f}/mo</span></div><div style="padding: 12px; background: var(--gray-100); border-radius: 6px; margin-top: 12px;"><span class="text-small text-muted">Benefit source: {std_source}</span></div></div>'

    opt_value_class = 'comparison-value--positive' if better == 'optimal' else ''
    opt_card = f'<div class="comparison-card comparison-card--optimal"><div class="comparison-title">✨ Optimal ICHRA (${optimal_contribution:,.0f}/mo)</div><div class="comparison-row"><span class="comparison-label">ICHRA Contribution</span><span class="comparison-value">${optimal_contribution:,.0f}/mo</span></div><div class="comparison-row"><span class="comparison-label">Employee Cost for LCSP</span><span class="comparison-value">${opt_ee_cost:,.0f}/mo</span></div><div class="comparison-row"><span class="comparison-label">PTC Available</span><span class="comparison-value comparison-value--highlight">${opt_ptc:,.0f}/mo</span></div><div class="comparison-row"><span class="comparison-label">Total Benefit</span><span class="comparison-value {opt_value_class}">${opt_benefit:,.0f}/mo</span></div><div style="padding: 12px; background: rgba(55, 190, 174, 0.1); border-radius: 6px; margin-top: 12px;"><span class="text-small" style="color: var(--teal-600);">Benefit source: {opt_source}</span></div></div>'

    return f'<div class="comparison-grid">{std_card}{opt_card}</div>'


def build_employee_breakdown_dataframe(
    employees: List[EmployeeAnalysis],
    base_contribution: float,
    strategy_type: str = 'flat',  # 'flat' or 'age_curve'
    base_age: int = 21,
) -> Tuple[pd.DataFrame, Dict]:
    """Build DataFrame for employee breakdown table with sortable columns.

    Args:
        employees: List of employee analyses
        base_contribution: For flat strategy, this is the contribution amount.
                          For age_curve, this is the contribution at base_age.
        strategy_type: 'flat' for uniform contribution, 'age_curve' for 3:1 ACA curve
        base_age: Reference age for age_curve strategy (default 21)

    Column names (updated for readability):
        - Income (was Monthly Income)
        - ER Contrib (was ER Allowance)
        - Threshold (was Afford. Threshold)
        - Affordability (was Affordable?) - now shows delta "$X under" or "$X over"
        - Expected EE Contrib (was ACA Expected)
        - EE Pays (was Cost w/ PTC)
    """

    # Filter to eligible employees
    eligible = [e for e in employees if not e.is_medicare and e.has_income]

    if not eligible:
        return pd.DataFrame(), {}

    rows = []
    total_employer_cost = 0.0

    for emp in eligible:
        # Calculate contribution based on strategy
        if strategy_type == 'age_curve':
            emp_contribution = calculate_age_curve_contribution(
                base_contribution, base_age, emp.age
            )
        else:
            emp_contribution = base_contribution

        std_benefit, std_source = calculate_employee_benefit(emp, emp_contribution)

        # Track actual employer cost (only if taking ICHRA)
        if std_source == 'ICHRA':
            total_employer_cost += emp_contribution

        # Calculate EE Pays and Subsidy based on benefit source
        # Key insight: PTC employees DON'T get the ICHRA - they decline it to get subsidy
        if std_source == 'PTC':
            subsidy_amount = std_benefit  # The PTC amount
            # PTC employee pays: LCSP - subsidy (they buy marketplace plan with PTC help)
            ee_pays = max(0, emp.lcsp - std_benefit)
        else:
            subsidy_amount = None  # No subsidy - taking ICHRA
            ee_pays = None  # Not applicable - using ICHRA path

        # Always show contribution amount (styling differs by source)
        display_contribution = emp_contribution

        # Calculate both paths so user can trace the logic
        ichra_cost = emp.lcsp - emp_contribution  # What they'd pay if taking ICHRA

        # Calculate affordability threshold (9.96% of income)
        afford_threshold = emp.monthly_income * AFFORDABILITY_THRESHOLD_2026
        is_affordable = ichra_cost <= afford_threshold

        # Build affordability display string - show delta instead of comparison
        # Delta = Threshold - EE Cost (positive = under, negative = over)
        delta = afford_threshold - ichra_cost
        if is_affordable:
            # "$X under" with green styling - employee MUST take ICHRA
            afford_display = f"${abs(delta):.0f} under"
        else:
            # "$X over" with red styling - employee CAN access subsidies
            afford_display = f"${abs(delta):.0f} over"

        # Calculate Expected EE Contrib - this is HOW the subsidy is calculated
        # Subsidy = SLCSP - Expected EE Contrib
        # Expected EE Contrib = Annual Income × Applicable Percentage / 12 (sliding scale 0-8.5%)
        applicable_pct = get_applicable_percentage(emp.annual_income, emp.family_status)
        expected_ee_contrib = (emp.annual_income * applicable_pct) / 12

        row_data = {
            'Employee': emp.name,
            'Age': emp.age,
            'Income': emp.monthly_income,  # Renamed from 'Monthly Income'
            'LCSP': emp.lcsp,
            'SLCSP': emp.slcsp,  # Benchmark for subsidy calculation
            'FPL %': emp.fpl_percentage,
            # Affordability Test columns
            'ER Contrib': display_contribution,  # Renamed from 'ER Allowance'
            'EE Cost': ichra_cost,  # LCSP - ER Contrib
            'Threshold': afford_threshold,  # Renamed from 'Afford. Threshold'
            'Affordability': afford_display,  # Renamed from 'Affordable?' - now shows delta
            # PTC Path columns
            'Expected EE Contrib': expected_ee_contrib,  # Renamed from 'ACA Expected'
            'Subsidy': subsidy_amount,  # SLCSP - Expected EE Contrib
            'EE Pays': ee_pays,  # Renamed from 'Cost w/ PTC' - LCSP - Subsidy
        }

        rows.append(row_data)

    df = pd.DataFrame(rows)

    # Calculate totals
    # PTC count = employees with subsidy (non-null Subsidy means PTC path)
    ptc_count = len(df[df['Subsidy'].notna()])
    ichra_count = len(df) - ptc_count

    totals = {
        'total_employees': len(eligible),
        'total_subsidy': df['Subsidy'].sum(skipna=True),  # Only PTC employees have subsidy
        'total_ee_pays': df['EE Pays'].sum(skipna=True),  # PTC path employee cost
        'total_ee_cost': df['EE Cost'].sum(skipna=True),  # ICHRA path employee cost
        'ptc_count': ptc_count,
        'ichra_count': ichra_count,
        'total_employer_cost': total_employer_cost,
        'strategy_type': strategy_type,
    }

    return df, totals


def style_employee_breakdown(df: pd.DataFrame, detailed: bool = True, show_slcsp: bool = False):
    """Apply conditional formatting to the employee breakdown DataFrame.

    Conditional formatting to aid understanding:
    - FPL %: 4-tier gradient showing subsidy eligibility
    - Subsidy: teal highlight when present
    - Affordability: green for "under" (affordable), red for "over" (unaffordable)
    - Lower cost: green highlight on the better option (EE Cost vs EE Pays)

    Args:
        df: DataFrame with employee data
        detailed: If True, show all columns. If False, show simplified view.
        show_slcsp: If True, include SLCSP column. If False, hide it.
    """

    # Define columns for each view (updated column names)
    # Simple: Just the essentials
    simple_cols = ['Employee', 'Age', 'Income', 'LCSP', 'FPL %', 'EE Cost', 'Threshold', 'Affordability', 'Subsidy', 'EE Pays']

    # Detailed: Full data journey showing how subsidy is calculated
    # Flow: Employee → Income → LCSP/SLCSP → FPL% → ICHRA path → Affordability → PTC calculation → Result
    detailed_cols = ['Employee', 'Age', 'Income',  # Who they are
                     'LCSP', 'SLCSP',                       # Plan costs (SLCSP is subsidy benchmark)
                     'FPL %',                               # Determines PTC eligibility (must be <400%)
                     'ER Contrib', 'EE Cost',               # ICHRA path: LCSP - ER Contrib = EE Cost
                     'Threshold',                           # Income × 9.96% (IRS affordability limit)
                     'Affordability',                       # "$X under" or "$X over" (delta from threshold)
                     'Expected EE Contrib',                 # What ACA expects you to pay (0-8.5% sliding scale)
                     'Subsidy',                             # SLCSP - Expected EE Contrib
                     'EE Pays']                             # LCSP - Subsidy (what you pay with PTC)

    # Select columns based on view mode
    if detailed:
        display_cols = [c for c in detailed_cols if c in df.columns]
    else:
        display_cols = [c for c in simple_cols if c in df.columns]

    # Remove SLCSP if toggle is off
    if not show_slcsp and 'SLCSP' in display_cols:
        display_cols.remove('SLCSP')

    display_df = df[display_cols].copy()

    # --- Conditional formatting functions ---

    def style_fpl(val):
        """FPL % gradient - shows subsidy eligibility tiers."""
        if pd.isna(val):
            return ''
        if val <= 150:
            return 'background-color: rgba(22, 163, 74, 0.25); color: #15803d; font-weight: 600;'  # Green - best subsidy
        elif val <= 250:
            return 'background-color: rgba(234, 179, 8, 0.20); color: #a16207;'  # Yellow
        elif val < 400:
            return 'background-color: rgba(249, 115, 22, 0.20); color: #c2410c;'  # Orange
        else:
            return 'color: #9ca3af;'  # Gray - no subsidy eligible (≥400% FPL)

    def style_subsidy(val):
        """Highlight subsidy when present."""
        if pd.isna(val) or val == 0:
            return 'color: #9ca3af;'  # Gray for no subsidy
        return 'background-color: rgba(13, 148, 136, 0.20); color: #0d9488; font-weight: 600;'  # Teal

    def style_affordability(val):
        """Conditional formatting for Affordability column - green bg for 'under', red bg for 'over'."""
        if pd.isna(val):
            return ''
        val_str = str(val)
        if 'under' in val_str:
            return 'background-color: rgba(22, 163, 74, 0.20); color: #15803d; font-weight: 600;'  # Green bg
        elif 'over' in val_str:
            return 'background-color: rgba(239, 68, 68, 0.20); color: #dc2626; font-weight: 600;'  # Red bg
        return ''

    def style_costs(row):
        """Highlight the lower cost between EE Cost and EE Pays."""
        styles = [''] * len(row)

        # Get column indices
        cols = list(row.index)
        ee_cost_idx = cols.index('EE Cost') if 'EE Cost' in cols else None
        ee_pays_idx = cols.index('EE Pays') if 'EE Pays' in cols else None

        if ee_cost_idx is None or ee_pays_idx is None:
            return styles

        ee_cost = row['EE Cost']
        ee_pays = row['EE Pays']

        # Handle nulls
        if pd.isna(ee_pays):
            # No PTC option - ICHRA is the only path, highlight it
            styles[ee_cost_idx] = 'background-color: rgba(59, 130, 246, 0.15); font-weight: 600;'
        elif pd.isna(ee_cost):
            styles[ee_pays_idx] = 'background-color: rgba(22, 163, 74, 0.15); font-weight: 600;'
        elif ee_cost <= ee_pays:
            # ICHRA is better or equal
            styles[ee_cost_idx] = 'background-color: rgba(59, 130, 246, 0.15); font-weight: 600;'
        else:
            # PTC is better
            styles[ee_pays_idx] = 'background-color: rgba(22, 163, 74, 0.15); font-weight: 600;'

        return styles

    # Apply styling
    styled = display_df.style

    # Apply FPL % styling
    if 'FPL %' in display_df.columns:
        styled = styled.applymap(style_fpl, subset=['FPL %'])

    # Apply Subsidy styling
    if 'Subsidy' in display_df.columns:
        styled = styled.applymap(style_subsidy, subset=['Subsidy'])

    # Apply Affordability styling (green for 'under', red for 'over')
    if 'Affordability' in display_df.columns:
        styled = styled.applymap(style_affordability, subset=['Affordability'])

    # Apply cost comparison styling (highlights the better option)
    if 'EE Cost' in display_df.columns and 'EE Pays' in display_df.columns:
        styled = styled.apply(style_costs, axis=1)

    # Format numbers - use custom formatters for nullable columns
    def format_nullable_currency(val):
        if pd.isna(val):
            return '-'
        return f'${val:,.0f}'

    # Build format dict dynamically based on columns present (updated column names)
    format_dict = {
        'Age': '{:.0f}',
        'Income': '${:,.0f}',
        'FPL %': '{:.0f}%',
        'LCSP': '${:,.0f}',
        'SLCSP': '${:,.0f}',
        'ER Contrib': '${:,.0f}',
        'EE Cost': '${:,.0f}',
        'Threshold': '${:,.0f}',
        'Expected EE Contrib': '${:,.0f}',
        'Subsidy': format_nullable_currency,
        'EE Pays': format_nullable_currency,
    }

    # Only apply formats for columns that exist
    format_dict = {k: v for k, v in format_dict.items() if k in display_df.columns}
    styled = styled.format(format_dict)

    return styled


def render_breakdown_html_table(df: pd.DataFrame, show_slcsp: bool = False) -> str:
    """Render employee breakdown as HTML table with multi-level grouped headers.

    Creates a custom HTML table with:
    - Two-row header: group names (spanning) + column names with formula annotations
    - Subtle borders between groups
    - Conditional formatting (FPL gradient, Affordability colors, Subsidy highlight)
    - Text wrapping in all cells

    Column Groups (3 groups for clarity):
    | Group | Columns | Notes |
    |-------|---------|-------|
    | Employee | Name, Age, Monthly Income, LCSP, [SLCSP], FPL % | All input data |
    | Affordability Test | ER Contrib, EE Cost, Threshold, Result | IRS affordability calc |
    | Subsidy Path | Expected Premium, Govt Subsidy, EE Pays | PTC calculation (if unaffordable) |

    Args:
        df: DataFrame with employee data
        show_slcsp: If True, include SLCSP column

    Returns:
        HTML string for the table
    """
    if df.empty:
        return '<div class="info-banner"><div class="info-banner-text">No employees with income data available.</div></div>'

    # CSS styles for the table
    css = """
    <style>
    .breakdown-table {
        width: 100%;
        border-collapse: collapse;
        font-family: 'Poppins', -apple-system, sans-serif;
        font-size: 13px;
        margin: 16px 0;
        border-radius: 8px;
        overflow: hidden;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    }
    .breakdown-table th, .breakdown-table td {
        padding: 10px 8px;
        text-align: center;
        white-space: normal;
        word-wrap: break-word;
        border-bottom: 1px solid #e5e7eb;
    }
    .breakdown-table th {
        font-weight: 600;
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.03em;
    }
    /* Group header row */
    .breakdown-table .group-header th {
        background: #1f2937;
        color: white;
        border-bottom: 2px solid #374151;
        font-size: 10px;
        padding: 8px 6px;
    }
    .breakdown-table .group-header th.group-employee { background: #374151; }
    .breakdown-table .group-header th.group-afford { background: #0047AB; }
    .breakdown-table .group-header th.group-subsidy { background: #0d9488; }
    /* Column header row */
    .breakdown-table .col-header th {
        background: #f3f4f6;
        color: #374151;
        border-bottom: 2px solid #d1d5db;
        font-size: 10px;
        padding: 8px 6px;
        line-height: 1.3;
    }
    .breakdown-table .col-header th .formula {
        display: block;
        font-size: 8px;
        font-weight: 400;
        color: #6b7280;
        text-transform: none;
        letter-spacing: 0;
        margin-top: 2px;
    }
    /* Data cells */
    .breakdown-table td {
        color: #374151;
        font-family: 'Inter', sans-serif;
        font-size: 13px;
    }
    .breakdown-table td.name-cell {
        text-align: left;
        font-weight: 500;
        color: #1f2937;
        max-width: 120px;
    }
    .breakdown-table td.num-cell {
        text-align: right;
        font-variant-numeric: tabular-nums;
    }
    .breakdown-table tr:nth-child(even) { background: #fafafa; }
    .breakdown-table tr:hover { background: #f0f9ff; }
    /* Conditional formatting */
    .fpl-low { background-color: rgba(22, 163, 74, 0.25) !important; color: #15803d; font-weight: 600; }
    .fpl-med { background-color: rgba(234, 179, 8, 0.20) !important; color: #a16207; }
    .fpl-high { background-color: rgba(249, 115, 22, 0.20) !important; color: #c2410c; }
    .fpl-over { color: #9ca3af; }
    .afford-under { background-color: rgba(22, 163, 74, 0.20) !important; color: #15803d; font-weight: 600; }
    .afford-over { background-color: rgba(239, 68, 68, 0.20) !important; color: #dc2626; font-weight: 600; }
    .subsidy-yes { background-color: rgba(13, 148, 136, 0.20) !important; color: #0d9488; font-weight: 600; }
    .cost-better { background-color: rgba(59, 130, 246, 0.15) !important; font-weight: 600; }
    .cost-ptc-better { background-color: rgba(22, 163, 74, 0.15) !important; font-weight: 600; }
    .null-val { color: #9ca3af; }
    /* Group borders */
    .breakdown-table td.group-end, .breakdown-table th.group-end {
        border-right: 2px solid #d1d5db;
    }
    </style>
    """

    # Build column structure based on show_slcsp
    # Employee group: Name, Age, Monthly Income, LCSP, [SLCSP], FPL %
    employee_span = 6 if show_slcsp else 5

    # Start building HTML
    html = [css, '<table class="breakdown-table">']

    # Group header row - 3 groups instead of 5
    html.append('<thead>')
    html.append('<tr class="group-header">')
    html.append(f'<th colspan="{employee_span}" class="group-employee group-end">Employee</th>')
    html.append('<th colspan="4" class="group-afford group-end">Affordability Test (EE Cost ≤ 9.96% Monthly Income)</th>')
    html.append('<th colspan="3" class="group-subsidy">Subsidy Path (if unaffordable)</th>')
    html.append('</tr>')

    # Column header row with formula annotations
    html.append('<tr class="col-header">')
    # Employee group - all input data
    html.append('<th>Name</th>')
    html.append('<th>Age</th>')
    html.append('<th>Monthly<br>Income</th>')
    html.append('<th>LCSP</th>')
    if show_slcsp:
        html.append('<th>SLCSP</th>')
    html.append('<th class="group-end">FPL %</th>')
    # Affordability Test group - with formula annotations
    html.append('<th>ER Contrib</th>')
    html.append('<th>EE Cost<span class="formula">LCSP − ER Contrib</span></th>')
    html.append('<th>Threshold<span class="formula">Income × 9.96%</span></th>')
    html.append('<th class="group-end">Result</th>')
    # Subsidy Path group - with formula annotations
    html.append('<th>Expected<br>Premium<span class="formula">Income × 0-8.5%</span></th>')
    html.append('<th>Govt<br>Subsidy<span class="formula">SLCSP − Expected</span></th>')
    html.append('<th>EE Pays<span class="formula">LCSP − Subsidy</span></th>')
    html.append('</tr>')
    html.append('</thead>')

    # Data rows
    html.append('<tbody>')
    for _, row in df.iterrows():
        html.append('<tr>')

        # Employee group - all input data together
        html.append(f'<td class="name-cell">{row["Employee"]}</td>')
        html.append(f'<td class="num-cell">{int(row["Age"])}</td>')
        html.append(f'<td class="num-cell">${row["Income"]:,.0f}</td>')
        html.append(f'<td class="num-cell">${row["LCSP"]:,.0f}</td>')
        if show_slcsp:
            html.append(f'<td class="num-cell">${row["SLCSP"]:,.0f}</td>')

        # FPL % with gradient - end of Employee group
        fpl_pct = row['FPL %']
        if fpl_pct <= 150:
            fpl_class = 'fpl-low'
        elif fpl_pct <= 250:
            fpl_class = 'fpl-med'
        elif fpl_pct < 400:
            fpl_class = 'fpl-high'
        else:
            fpl_class = 'fpl-over'
        html.append(f'<td class="num-cell group-end {fpl_class}">{fpl_pct:.0f}%</td>')

        # Affordability Test group
        html.append(f'<td class="num-cell">${row["ER Contrib"]:,.0f}</td>')

        # EE Cost - highlight if better than EE Pays
        ee_cost = row['EE Cost']
        ee_pays = row['EE Pays']
        if pd.isna(ee_pays) or ee_cost <= (ee_pays if not pd.isna(ee_pays) else float('inf')):
            ee_cost_class = 'cost-better'
        else:
            ee_cost_class = ''
        html.append(f'<td class="num-cell {ee_cost_class}">${ee_cost:,.0f}</td>')

        html.append(f'<td class="num-cell">${row["Threshold"]:,.0f}</td>')

        # Result - "$X under" (green) or "$X over" (red)
        afford = row['Affordability']
        if 'under' in str(afford):
            afford_class = 'afford-under'
        elif 'over' in str(afford):
            afford_class = 'afford-over'
        else:
            afford_class = ''
        html.append(f'<td class="group-end {afford_class}">{afford}</td>')

        # Subsidy Path group
        # Expected Premium (what ACA expects employee to pay based on 0-8.5% sliding scale)
        html.append(f'<td class="num-cell">${row["Expected EE Contrib"]:,.0f}</td>')

        # Govt Subsidy - teal highlight when present (what govt pays: SLCSP - Expected Premium)
        subsidy = row['Subsidy']
        if pd.isna(subsidy):
            html.append('<td class="null-val">-</td>')
        else:
            html.append(f'<td class="num-cell subsidy-yes">${subsidy:,.0f}</td>')

        # EE Pays - highlight if better than EE Cost
        if pd.isna(ee_pays):
            html.append('<td class="null-val">-</td>')
        else:
            if ee_pays < ee_cost:
                ee_pays_class = 'cost-ptc-better'
            else:
                ee_pays_class = ''
            html.append(f'<td class="num-cell {ee_pays_class}">${ee_pays:,.0f}</td>')

        html.append('</tr>')

    html.append('</tbody>')
    html.append('</table>')

    return '\n'.join(html)


def export_to_csv(
    employees: List[EmployeeAnalysis],
    base_contribution: float,
    strategy_type: str = 'flat',
    base_age: int = 21,
) -> str:
    """Export employee breakdown to CSV with requested columns."""
    rows = []

    for emp in employees:
        if emp.is_medicare or not emp.has_income:
            continue

        # Calculate contribution based on strategy
        if strategy_type == 'age_curve':
            emp_contribution = calculate_age_curve_contribution(
                base_contribution, base_age, emp.age
            )
        else:
            emp_contribution = base_contribution

        benefit, source = calculate_employee_benefit(emp, emp_contribution)

        # % PTC and % ICHRA as decimals (1.0 or 0.0)
        pct_ptc = 1.0 if source == 'PTC' else 0.0
        pct_ichra = 1.0 if source == 'ICHRA' else 0.0

        # Calculate Subsidy based on benefit source
        # PTC employees pay: LCSP - subsidy (they decline ICHRA to get marketplace subsidy)
        if source == 'PTC':
            subsidy = benefit  # The PTC amount
            ee_pays = max(0, emp.lcsp - subsidy)
        else:
            subsidy = ''  # No subsidy - taking ICHRA
            ee_pays = ''  # Not applicable

        # Always show contribution amount
        display_contribution = emp_contribution

        # Calculate both paths for CSV export
        ichra_cost = emp.lcsp - emp_contribution

        # Calculate affordability
        afford_threshold = emp.monthly_income * AFFORDABILITY_THRESHOLD_2026
        is_affordable = ichra_cost <= afford_threshold
        delta = afford_threshold - ichra_cost
        affordability = f"${abs(delta):.0f} under" if is_affordable else f"${abs(delta):.0f} over"

        # Calculate Expected EE Contrib (0-8.5% sliding scale)
        applicable_pct = get_applicable_percentage(emp.annual_income, emp.family_status)
        expected_ee_contrib = (emp.annual_income * applicable_pct) / 12

        row_data = {
            'Employee': emp.name,
            'Age': emp.age,
            'Income': emp.monthly_income,
            'LCSP': emp.lcsp,
            'SLCSP': emp.slcsp,
            'FPL %': round(emp.fpl_percentage / 100, 4),  # As decimal (e.g., 2.76 for 276%)
            'ER Contrib': display_contribution,
            'EE Cost': ichra_cost,
            'Threshold': afford_threshold,
            'Affordability': affordability,
            'Expected EE Contrib': expected_ee_contrib,
            'Subsidy': subsidy,
            'EE Pays': ee_pays,
            '% PTC': pct_ptc,
            '% ICHRA': pct_ichra,
        }

        rows.append(row_data)

    df = pd.DataFrame(rows)
    return df.to_csv(index=False)


def export_to_excel(result: OptimizationResult, baseline_contribution: float) -> bytes:
    """Export analysis to Excel."""
    output = BytesIO()

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Optimization curve data with all numeric columns
        total_employees = len([e for e in result.employee_analyses if not e.is_medicare])
        curve_data = []
        for s in result.all_scenarios:
            pct_ptc = s.employees_taking_ptc / total_employees if total_employees > 0 else 0
            pct_ichra = s.employees_taking_ichra / total_employees if total_employees > 0 else 0
            curve_data.append({
                'ICHRA contribution': s.contribution,
                'Total monthly ICHRA benefit (ER payout)': s.total_monthly_benefit,
                'Total annual ICHRA benefit (ER payout)': s.total_annual_benefit,
                'Employees Taking ICHRA': s.employees_taking_ichra,
                'Employees Taking PTC': s.employees_taking_ptc,
                '% PTC': round(pct_ptc, 4),
                '% ICHRA': round(pct_ichra, 4),
                'Avg PTC Benefit': s.avg_ptc_benefit,
            })
        pd.DataFrame(curve_data).to_excel(writer, sheet_name='Optimization Curve', index=False)

        # Employee detail at optimal
        emp_data = []
        for e in result.employee_analyses:
            benefit, source = calculate_employee_benefit(e, result.optimal_contribution)
            emp_data.append({
                'Employee ID': e.employee_id,
                'Name': e.name,
                'Age': e.age,
                'Family Status': e.family_status,
                'Annual Income': e.annual_income,
                'FPL %': round(e.fpl_percentage / 100, 4),  # Numeric decimal
                'Income Band': e.income_band,
                'LCSP': e.lcsp,
                'SLCSP': e.slcsp,
                'PTC Eligible': 1 if e.is_ptc_eligible else 0,
                'Medicare': 1 if e.is_medicare else 0,
                'Subsidy': benefit if source == 'PTC' else '',
                'Best Option': source,
            })
        pd.DataFrame(emp_data).to_excel(writer, sheet_name='Employee Detail', index=False)

        # Summary comparison
        summary_data = [{
            'Metric': 'Optimal Contribution',
            'Value': result.optimal_contribution,
        }, {
            'Metric': 'Baseline Contribution',
            'Value': baseline_contribution,
        }, {
            'Metric': 'Total Monthly Benefit at Optimal',
            'Value': result.optimal_total_benefit,
        }]
        pd.DataFrame(summary_data).to_excel(writer, sheet_name='Summary', index=False)

    return output.getvalue()


# =============================================================================
# MAIN PAGE
# =============================================================================

def main():
    """Main page orchestrator."""
    # Sidebar
    with st.sidebar:
        st.markdown("**📋 Client Name**")
        if 'client_name' not in st.session_state:
            st.session_state.client_name = ''
        st.text_input(
            "Client name",
            placeholder="Enter client name",
            key="client_name",
            help="Used in export filenames",
            label_visibility="collapsed"
        )
        render_feedback_sidebar()

    # Page header
    st.markdown('<div class="hero-section"><h1 style="font-size: 28px; font-weight: 700; color: #0a1628; margin-bottom: 8px;">Subsidy Optimization</h1><p style="font-size: 16px; color: #475569; margin: 0;">Find the optimal uniform ICHRA contribution that maximizes total employee benefit</p></div>', unsafe_allow_html=True)

    # Check for census data
    if 'census_df' not in st.session_state or st.session_state.census_df is None:
        st.warning("⚠️ No census data found. Please upload employee data on the Census Input page first.")
        if st.button("→ Go to Census Input"):
            st.switch_page("pages/1_Census_input.py")
        return

    census_df = st.session_state.census_df

    # Get database connection
    if 'db' not in st.session_state:
        st.session_state.db = get_database_connection()
    db = st.session_state.db

    # Build census context for ALE check
    context = build_census_context(census_df)

    # ==========================================================================
    # ALE GATE CHECK
    # ==========================================================================

    if context.is_ale:
        st.markdown(f'<div class="warning-banner"><div class="warning-banner-title">⚠️ ALE Employer Detected ({context.employee_count} employees)</div><div class="warning-banner-text">Subsidy optimization is designed for <strong>non-ALE employers</strong> (fewer than 46 employees). Applicable Large Employers must offer affordable coverage to avoid IRS penalties.<br><br>For ALE contribution strategies, please use the <strong>Contribution Evaluation</strong> page instead.</div></div>', unsafe_allow_html=True)
        if st.button("→ Go to Contribution Evaluation"):
            st.switch_page("pages/3_Contribution_evaluation.py")
        return

    # ==========================================================================
    # INCOME DATA CHECK
    # ==========================================================================

    if not context.has_income_data:
        st.markdown('<div class="warning-banner"><div class="warning-banner-title">⚠️ Income Data Required</div><div class="warning-banner-text">Subsidy optimization requires employee income data to:<ul style="margin-top: 8px;"><li>Determine PTC eligibility (income ≤400% FPL)</li><li>Calculate optimal contribution that maximizes benefit</li><li>Identify which employees benefit from PTC vs ICHRA</li></ul>Please upload a census with the <strong>Monthly Income</strong> column.</div></div>', unsafe_allow_html=True)
        return

    # ==========================================================================
    # WORKFORCE ANALYSIS
    # ==========================================================================

    with st.spinner("Analyzing workforce and calculating optimal contribution..."):
        employees = analyze_workforce(census_df, db)
        result = calculate_optimal_contribution(employees)

    # Filter for analysis
    active_employees = [e for e in employees if not e.is_medicare and e.has_income]
    ptc_eligible_count = len([e for e in active_employees if e.is_ptc_eligible])
    medicare_count = len([e for e in employees if e.is_medicare])

    # ==========================================================================
    # CHECK: Does subsidy optimization provide any benefit?
    # ==========================================================================

    # Check if ANY scenario results in employees taking PTC
    max_ptc_takers = max(s.employees_taking_ptc for s in result.all_scenarios) if result.all_scenarios else 0

    # Get PTC takers at optimal contribution
    optimal_scenario = next((s for s in result.all_scenarios if s.contribution == result.optimal_contribution), None)
    ptc_at_optimal = optimal_scenario.employees_taking_ptc if optimal_scenario else 0

    # Subsidy optimization provides no benefit if:
    # 1. No scenarios have any PTC takers, OR
    # 2. The optimal is at max contribution with 0 PTC takers (just "more money = more benefit")
    subsidy_optimization_applicable = max_ptc_takers > 0 and (ptc_at_optimal > 0 or result.optimal_contribution < max(s.contribution for s in result.all_scenarios) * 0.9)

    # ==========================================================================
    # SECTION 1: SUMMARY METRICS
    # ==========================================================================

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(f'<div class="summary-card summary-card--primary"><div class="summary-label">Total Employees</div><div class="summary-value">{len(employees)}</div><div class="summary-sublabel">{len(active_employees)} with income data</div></div>', unsafe_allow_html=True)

    with col2:
        st.markdown(f'<div class="summary-card summary-card--success"><div class="summary-label">PTC-Eligible</div><div class="summary-value">{ptc_eligible_count}</div><div class="summary-sublabel">under 400% FPL</div></div>', unsafe_allow_html=True)

    with col3:
        if subsidy_optimization_applicable:
            st.markdown(f'<div class="summary-card summary-card--accent"><div class="summary-label">Optimal Contribution</div><div class="summary-value">${result.optimal_contribution:,.0f}</div><div class="summary-sublabel">per month</div></div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="summary-card"><div class="summary-label">Max Tested</div><div class="summary-value">${result.optimal_contribution:,.0f}</div><div class="summary-sublabel">no PTC tradeoff</div></div>', unsafe_allow_html=True)

    with col4:
        st.markdown(f'<div class="summary-card"><div class="summary-label">Total Annual Benefit</div><div class="summary-value">${result.optimal_total_benefit * 12:,.0f}</div><div class="summary-sublabel">${result.optimal_total_benefit:,.0f}/month</div></div>', unsafe_allow_html=True)

    # Medicare note
    if medicare_count > 0:
        st.markdown('<div style="margin-top: 16px;"></div>', unsafe_allow_html=True)
        st.info(f"ℹ️ {medicare_count} employee(s) are Medicare-eligible (65+) and excluded from optimization.")

    # ==========================================================================
    # CHECK: Subsidy optimization not applicable
    # ==========================================================================

    if not subsidy_optimization_applicable:
        st.markdown(f'''<div class="warning-banner">
<div class="warning-banner-title">⚠️ Subsidy Optimization Not Applicable</div>
<div class="warning-banner-text">
Based on this workforce's income distribution, <strong>no employees would benefit from declining ICHRA to access Premium Tax Credits</strong> at any contribution level.
<br><br>
<strong>Why?</strong> {"All employees have income above 400% FPL and don't qualify for PTCs." if ptc_eligible_count == 0 else "Even PTC-eligible employees would receive more value from ICHRA than from PTCs at all tested contribution levels."}
<br><br>
<strong>Recommendation:</strong> Use the standard <strong>Contribution Evaluation</strong> page to design your ICHRA contribution strategy. For this workforce, higher contributions directly translate to higher employee benefit with no PTC tradeoff to optimize.
</div>
</div>''', unsafe_allow_html=True)

        if st.button("→ Go to Contribution Evaluation"):
            st.switch_page("pages/3_Contribution_evaluation.py")

        st.markdown("---")
        st.caption("The analysis below is shown for reference, but subsidy optimization does not apply to this workforce.")

    # ==========================================================================
    # SECTION 2: OPTIMIZATION CURVE
    # ==========================================================================

    st.markdown("---")
    st.subheader("📈 Optimization Curve")

    if subsidy_optimization_applicable:
        st.markdown('<div class="info-banner" style="margin-bottom: 16px;"><div class="info-banner-text"><strong>How to read this chart:</strong> The curve shows total workforce benefit at each contribution level. The optimal point maximizes total benefit by balancing ICHRA value for high-income employees against PTC access for lower-income employees.</div></div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="info-banner" style="margin-bottom: 16px;"><div class="info-banner-text"><strong>Note:</strong> This curve shows a monotonic relationship (more contribution = more benefit) with no PTC tradeoff. This is typical when employees have higher incomes and don\'t qualify for meaningful PTCs.</div></div>', unsafe_allow_html=True)

    render_optimization_chart(result.all_scenarios, result.optimal_contribution)

    # ==========================================================================
    # SECTION 3: CONTRIBUTION ANALYSIS TABLE
    # ==========================================================================

    st.markdown("---")
    st.subheader("📊 Contribution Analysis by Income Band")

    table_html = render_analysis_table(result.income_band_summary, result.optimal_contribution)
    st.markdown(table_html, unsafe_allow_html=True)

    # ==========================================================================
    # SECTION 4: SCENARIO COMPARISON
    # ==========================================================================

    st.markdown("---")
    st.subheader("🔄 Scenario Comparison")

    # Strategy selection
    st.markdown('<div class="info-banner" style="margin-bottom: 16px;"><div class="info-banner-text"><strong>Choose a contribution strategy</strong> to model. Flat Amount gives everyone the same contribution. 3:1 Age Curve scales contributions by age following the ACA age rating curve (older employees get up to 3x more).</div></div>', unsafe_allow_html=True)

    col_strategy, col_base_age = st.columns([2, 1])

    with col_strategy:
        strategy_type = st.radio(
            "Contribution Strategy",
            options=['flat', 'age_curve'],
            format_func=lambda x: 'Flat Amount' if x == 'flat' else '3:1 Age Curve',
            horizontal=True,
            key="strategy_type_radio",
            help="Flat = same amount for all. 3:1 Age Curve = scales by age using ACA ratios."
        )

    with col_base_age:
        if strategy_type == 'age_curve':
            base_age = st.selectbox(
                "Base Age",
                options=[21, 30, 40, 50],
                index=0,
                key="base_age_select",
                help="The reference age for the contribution amount. Other ages scale from this."
            )
        else:
            base_age = 21  # Default, not used for flat

    # Contribution amount input
    if 'baseline_amount' not in st.session_state:
        st.session_state.baseline_amount = 500

    if strategy_type == 'age_curve':
        input_label = f"Contribution at age {base_age} (base amount)"
        input_help = f"Set the contribution for age {base_age}. Other ages scale using the 3:1 ACA curve."
    else:
        input_label = "Flat ICHRA contribution (same for all)"
        input_help = "Set the uniform contribution amount for all employees."

    baseline_contribution = st.number_input(
        input_label,
        min_value=0,
        max_value=2000,
        value=st.session_state.baseline_amount,
        step=1,
        key="baseline_input",
        help=input_help
    )
    st.session_state.baseline_amount = baseline_contribution

    # Show age curve preview for 3:1 strategy
    if strategy_type == 'age_curve':
        preview_ages = [21, 30, 40, 50, 64]
        preview_contribs = [calculate_age_curve_contribution(baseline_contribution, base_age, a) for a in preview_ages]
        preview_str = " → ".join([f"Age {a}: ${c:,.0f}" for a, c in zip(preview_ages, preview_contribs)])
        st.caption(f"📊 Preview: {preview_str}")

    # TRADEOFF CALLOUT (REQUIRED - always visible)
    if ptc_eligible_count > 0:
        tradeoff_html = render_tradeoff_callout(result, baseline_contribution)
        st.markdown(tradeoff_html, unsafe_allow_html=True)

    # Build DataFrame early so we can show totals before the breakdown section
    breakdown_df, totals = build_employee_breakdown_dataframe(
        active_employees,
        baseline_contribution,
        strategy_type=strategy_type,
        base_age=base_age,
    )

    # Totals card (above Employee Breakdown section)
    if not breakdown_df.empty:
        # Build employer cost display
        if strategy_type == 'age_curve':
            er_cost_value = totals['total_employer_cost']
        else:
            er_cost_value = baseline_contribution * totals['total_employees']

        # Handle potential NaN in total_subsidy
        total_subsidy_display = f"${totals['total_subsidy']:,.0f}" if not pd.isna(totals['total_subsidy']) else "$0"

        totals_html = '<div style="background: linear-gradient(135deg, #f0fdfa 0%, #e6fffa 100%); border: 2px solid #0D7377; border-radius: 12px; padding: 20px 24px; margin-top: 16px; margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center;">'
        totals_html += f'<span style="font-size: 18px; font-weight: 700; color: #0D7377;">TOTALS <span style="font-weight: 500; color: var(--gray-600);">({totals["total_employees"]} employees)</span></span>'
        totals_html += '<div style="display: flex; gap: 28px; font-size: 16px; align-items: center;">'
        # ER Cost - eye-catching pill style
        totals_html += f'<span style="background: #0D7377; color: white; padding: 8px 16px; border-radius: 20px; font-weight: 700;"><span style="font-weight: 500; opacity: 0.9;">ER Cost:</span> <span style="font-size: 20px;">${er_cost_value:,.0f}</span>/mo</span>'
        totals_html += f'<span style="color: #0d9488;"><strong>Total Subsidy:</strong> <span style="font-size: 18px; font-weight: 700;">{total_subsidy_display}</span>/mo</span>'
        totals_html += f'<span style="color: #0d9488;"><strong>PTC Takers:</strong> <span style="font-size: 18px; font-weight: 700;">{totals["ptc_count"]}</span></span>'
        totals_html += f'<span><strong>ICHRA Takers:</strong> <span style="font-size: 18px; font-weight: 700;">{totals["ichra_count"]}</span></span>'
        totals_html += '</div></div>'

        st.markdown(totals_html, unsafe_allow_html=True)

    # ==========================================================================
    # SECTION 5: EMPLOYEE BREAKDOWN TABLE
    # ==========================================================================

    st.markdown("---")
    st.subheader("👥 Employee Breakdown")

    # Explanation card - shows formulas for all calculated columns (no black boxes)
    st.markdown(f'''<div style="background: var(--gray-50); border-radius: 10px; padding: 16px 20px; margin-bottom: 16px; border: 1px solid var(--gray-200);">
<div style="font-size: 14px; font-weight: 600; color: var(--gray-800); margin-bottom: 12px;">Calculated Columns (No Black Boxes)</div>
<div style="font-size: 13px; line-height: 1.6;">
<div style="margin-bottom: 10px;">
<span style="background: #0047AB; color: white; padding: 2px 8px; border-radius: 4px; font-weight: 600; font-size: 11px;">AFFORDABILITY TEST</span>
<span style="margin-left: 8px;">If EE Cost ≤ Threshold, ICHRA is affordable and employee <strong>must</strong> accept it</span>
</div>
<div style="margin-bottom: 10px; margin-left: 16px; font-family: monospace; font-size: 12px;">
• <strong>EE Cost</strong> = LCSP − ER Contrib<br>
• <strong>Threshold</strong> = Monthly Income × 9.96%<br>
• <strong>Result</strong>: <span style="background: rgba(22, 163, 74, 0.2); padding: 1px 6px; border-radius: 3px; color: #15803d; font-weight: 600;">$X under</span> if EE Cost ≤ Threshold (must take ICHRA) | <span style="background: rgba(239, 68, 68, 0.2); padding: 1px 6px; border-radius: 3px; color: #dc2626; font-weight: 600;">$X over</span> if EE Cost > Threshold (can access subsidies)
</div>
<div style="margin-bottom: 10px;">
<span style="background: #0d9488; color: white; padding: 2px 8px; border-radius: 4px; font-weight: 600; font-size: 11px;">SUBSIDY PATH</span>
<span style="margin-left: 8px;">Only populated if ICHRA is unaffordable (Result = "$X over")</span>
</div>
<div style="margin-bottom: 8px; margin-left: 16px; font-family: monospace; font-size: 12px;">
• <strong>Expected Premium</strong> = Monthly Income × (0% to 8.5% based on FPL)<br>
• <strong>Govt Subsidy</strong> = SLCSP − Expected Premium<br>
• <strong>EE Pays</strong> = LCSP − Govt Subsidy
</div>
<div style="margin-top: 10px; padding-top: 10px; border-top: 1px solid var(--gray-200); font-size: 12px;">
<strong>ACA Sliding Scale:</strong> 100-150% FPL → 0-4% | 150-200% FPL → 4-6.5% | 200-250% FPL → 6.5-8.5% | 250-400% FPL → 8.5%
</div>
</div>
<div style="margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--gray-200); font-size: 13px; color: var(--gray-600);">
{f'Strategy: <strong>3:1 Age Curve</strong> at ${baseline_contribution:,.0f}/mo (age {base_age})' if strategy_type == 'age_curve' else f'Strategy: <strong>Flat</strong> ${baseline_contribution:,.0f}/mo'}
</div>
</div>''', unsafe_allow_html=True)

    # Sort controls - above the table
    if not breakdown_df.empty:
        sort_col1, sort_col2, sort_col3, sort_col4 = st.columns([1.2, 1, 1.2, 1])
        sortable_columns = list(breakdown_df.columns)

        with sort_col1:
            sort_by = st.selectbox(
                "Sort by",
                options=sortable_columns,
                index=0,
                key="breakdown_sort_column"
            )

        with sort_col2:
            sort_direction = st.radio(
                "Direction",
                options=["Asc", "Desc"],
                horizontal=True,
                key="breakdown_sort_direction"
            )

        with sort_col3:
            # Secondary sort - optional
            sort_by_2 = st.selectbox(
                "Then by",
                options=["(none)"] + sortable_columns,
                index=0,
                key="breakdown_sort_column_2"
            )

        with sort_col4:
            sort_direction_2 = st.radio(
                "Direction",
                options=["Asc", "Desc"],
                horizontal=True,
                key="breakdown_sort_direction_2"
            )

        # Apply sort to DataFrame - this affects both UI display AND PDF export
        ascending = sort_direction == "Asc"
        if sort_by_2 != "(none)":
            ascending_2 = sort_direction_2 == "Asc"
            breakdown_df = breakdown_df.sort_values(
                by=[sort_by, sort_by_2],
                ascending=[ascending, ascending_2],
                na_position='last'
            )
        else:
            breakdown_df = breakdown_df.sort_values(by=sort_by, ascending=ascending, na_position='last')
        breakdown_df = breakdown_df.reset_index(drop=True)

    if breakdown_df.empty:
        st.info("No employees with income data available for comparison.")
    else:
        # Initialize session state for show_slcsp if not exists
        if 'show_slcsp' not in st.session_state:
            st.session_state.show_slcsp = False

        # Toggle controls row
        toggle_col1, toggle_col2 = st.columns([1, 3])
        with toggle_col1:
            show_slcsp = st.toggle(
                "Show SLCSP",
                value=st.session_state.show_slcsp,
                key="show_slcsp_toggle",
                help="Show Second Lowest Cost Silver Plan column (used for subsidy calculation)"
            )
            st.session_state.show_slcsp = show_slcsp

        # Render custom HTML table with multi-level grouped headers
        html_table = render_breakdown_html_table(breakdown_df, show_slcsp=show_slcsp)
        st.markdown(html_table, unsafe_allow_html=True)

    # ==========================================================================
    # SECTION 6: EXPORT
    # ==========================================================================

    st.markdown("---")
    st.subheader("📥 Export Analysis")

    # Build filename with client name and datetime stamp
    client_name_raw = st.session_state.get('client_name', '').strip()
    client_name = client_name_raw.replace(' ', '_') if client_name_raw else 'Client'
    timestamp = datetime.now().strftime('%Y%m%d_%H%M')
    base_filename = f"{client_name}_Subsidy_Optimization_{timestamp}"

    col1, col2, col3 = st.columns([1, 1, 2])

    with col1:
        excel_data = export_to_excel(result, baseline_contribution)
        st.download_button(
            label="📥 Download Excel",
            data=excel_data,
            file_name=f"{base_filename}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    with col2:
        # Build PDF data from the breakdown_df and totals
        if not breakdown_df.empty:
            # Get show_slcsp from session state for PDF consistency with UI
            show_slcsp_for_pdf = st.session_state.get('show_slcsp', False)
            pdf_data = build_subsidy_optimization_data(
                breakdown_df=breakdown_df,
                totals=totals,
                strategy_type=strategy_type,
                base_contribution=baseline_contribution,
                base_age=base_age,
                client_name=client_name_raw,
                show_slcsp=show_slcsp_for_pdf,
            )
            renderer = SubsidyOptimizationPDFRenderer()
            pdf_buffer = renderer.generate(pdf_data)
            st.download_button(
                label="📄 Download PDF",
                data=pdf_buffer,
                file_name=f"{base_filename}.pdf",
                mime="application/pdf"
            )

    with col3:
        st.markdown('''<div class="text-small text-muted">
<strong>Excel:</strong> Optimization Curve, Employee Detail, Summary<br/>
<strong>PDF:</strong> Summary cards, employee breakdown with conditional formatting
</div>''', unsafe_allow_html=True)


if __name__ == "__main__":
    main()
else:
    main()
