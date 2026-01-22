"""
Action Bar Component

Renders the bottom action bar with:
- "Use This Strategy" button (disabled for ALE if not 100% affordable)
- "Download CSV" button
- "Start Over" button
- ALE warning message if not 100% affordable
"""

import streamlit as st
import pandas as pd
import io
from datetime import datetime
from typing import Dict, Any, Optional, Callable

from contribution_eval import OperatingMode
from contribution_eval.utils.formatting import format_currency
from constants import ACA_AGE_CURVE, AFFORDABILITY_THRESHOLD_2026, MEDICARE_ELIGIBILITY_AGE
from subsidy_utils import (
    calculate_monthly_subsidy,
    calculate_max_contribution_for_eligibility,
    get_age_factor as get_aca_age_factor,
    is_subsidy_eligible,
    AFFORDABILITY_BUFFER,
)


def render_action_bar(
    mode: OperatingMode,
    strategy_result: Dict[str, Any],
    affordability_data: Optional[Dict[str, Any]] = None,
    on_use_strategy: Optional[Callable[[Dict[str, Any]], None]] = None,
    on_start_over: Optional[Callable[[], None]] = None,
) -> None:
    """
    Render the bottom action bar.

    Args:
        mode: Current operating mode
        strategy_result: Current strategy calculation result
        affordability_data: Affordability analysis (ALE mode)
        on_use_strategy: Callback when "Use This Strategy" is clicked
        on_start_over: Callback when "Start Over" is clicked
    """
    # Check if strategy can be used (ALE must be 100% affordable)
    can_use = True
    warning_message = None

    if mode == OperatingMode.ALE and affordability_data:
        if not affordability_data.get('all_affordable', False):
            can_use = False
            unaffordable = affordability_data.get('unaffordable_employees', [])
            warning_message = f"⚠️ {len(unaffordable)} employees need higher contributions to meet affordability. Adjust the strategy or increase base contribution."

    # Render the action bar
    st.markdown("---")

    col1, col2, col3, col4 = st.columns([3, 2, 2, 3])

    with col1:
        if warning_message:
            st.warning(warning_message, icon=None)

    with col2:
        if st.button(
            "✅ Use This Strategy",
            type="primary",
            disabled=not can_use,
            width="stretch",
            key="use_strategy_btn",
        ):
            if on_use_strategy:
                on_use_strategy(strategy_result)
            else:
                _save_to_session_state(strategy_result)
                st.success("Strategy saved! Proceed to Employer Summary.")

    with col3:
        csv_data = _generate_csv(strategy_result, affordability_data, mode)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        client_name = st.session_state.get('client_name', '')
        if client_name:
            # Sanitize client name for filename (remove special characters)
            safe_name = "".join(c if c.isalnum() or c in (' ', '-', '_') else '' for c in client_name)
            safe_name = safe_name.strip().replace(' ', '_')
            file_name = f"{safe_name}_contribution_strategy_{timestamp}.csv"
        else:
            file_name = f"contribution_strategy_{timestamp}.csv"
        st.download_button(
            label="📥 Download CSV",
            data=csv_data,
            file_name=file_name,
            mime="text/csv",
            width="stretch",
            key="download_csv_btn",
        )

    with col4:
        if st.button(
            "🔄 Start Over",
            type="secondary",
            width="stretch",
            key="start_over_btn",
        ):
            if on_start_over:
                on_start_over()
            else:
                _clear_session_state()
                st.rerun()


def _save_to_session_state(strategy_result: Dict[str, Any]) -> None:
    """
    Save strategy result to session state for use by other pages.

    Formats the data to be compatible with Page 5 (Employer Summary).
    """
    # Build contribution_settings format
    st.session_state.contribution_settings = {
        'strategy_type': strategy_result.get('strategy_type', 'base_age_curve'),
        'strategy_name': strategy_result.get('strategy_name', ''),
        'contribution_type': 'class_based',
        'config': strategy_result.get('config', {}),
    }

    # Build strategy_results format
    st.session_state.strategy_results = {
        'total_monthly': strategy_result.get('total_monthly', 0),
        'total_annual': strategy_result.get('total_annual', 0),
        'employees_covered': strategy_result.get('employees_covered', 0),
        'by_age_tier': strategy_result.get('by_age_tier', {}),
        'by_family_status': strategy_result.get('by_family_status', {}),
    }

    # Build employee assignments for compatibility
    employee_assignments = {}
    for emp_id, data in strategy_result.get('employee_contributions', {}).items():
        employee_assignments[emp_id] = {
            'monthly_contribution': data.get('monthly_contribution', 0),
            'annual_contribution': data.get('annual_contribution', 0),
            'family_status': data.get('family_status', 'EE'),
            'age': data.get('age', 30),
        }

    st.session_state.contribution_settings['employee_assignments'] = employee_assignments

    # Store affordability results if present
    if 'affordability' in strategy_result:
        st.session_state.affordability_results = strategy_result['affordability']

    # Mark that contribution evaluation is complete
    st.session_state.contribution_evaluation_complete = True


def _clear_session_state() -> None:
    """Clear contribution-related session state."""
    keys_to_clear = [
        'contribution_settings',
        'strategy_results',
        'contribution_evaluation_complete',
        'affordability_results',
        'contribution_goal',
        'current_strategy_config',
        'current_strategy_result',
    ]

    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]


def _get_age_factor(age: int) -> float:
    """
    Get the ACA 3:1 age curve factor for a given age.
    Age 21 = 1.0, Age 64 = 3.0, with defined values in between.

    Uses subsidy_utils.get_age_factor for consistent calculation.
    """
    return get_aca_age_factor(age)


def _generate_csv(
    strategy_result: Dict[str, Any],
    affordability_data: Optional[Dict[str, Any]] = None,
    mode: Optional[OperatingMode] = None,
) -> str:
    """
    Generate CSV data from strategy result.

    Args:
        strategy_result: Strategy calculation result
        affordability_data: Affordability analysis (ALE mode) with per-employee data
        mode: Operating mode (affects column display)

    Returns:
        CSV string for download
    """
    employee_contributions = strategy_result.get('employee_contributions', {})
    strategy_type = strategy_result.get('strategy_type', '')

    # Get per-employee affordability data if available (ALE mode)
    employee_affordability = {}
    safe_harbor_type = None
    if affordability_data:
        employee_affordability = affordability_data.get('employee_affordability', {})
        safe_harbor_type = affordability_data.get('safe_harbor', '')

    # ==========================================================================
    # PRE-PASS: Cache subsidy data for CSV export (Non-ALE only)
    # ==========================================================================
    # Uses subsidy_utils for unified eligibility logic.
    # Employees age 65+ are Medicare-eligible and do NOT qualify for ACA
    # marketplace subsidies. They are excluded from subsidy calculations.
    # ==========================================================================
    employee_subsidy_data = {}

    if mode in [OperatingMode.NON_ALE_SUBSIDY, OperatingMode.NON_ALE_STANDARD]:
        for emp_id, data in employee_contributions.items():
            monthly_income = data.get('monthly_income')
            # Convert to float in case values are Decimal from database
            lcsp = float(data.get('lcsp_ee_rate', 0) or 0)
            slcsp = float(data.get('slcsp_ee_rate', 0) or 0)  # ACA benchmark for subsidies
            age = data.get('age', 30)
            family_status = data.get('family_status', 'EE')
            contribution = data.get('monthly_contribution', 0)

            # Skip Medicare-eligible employees (65+) from subsidy calculations
            if age >= MEDICARE_ELIGIBILITY_AGE:
                employee_subsidy_data[emp_id] = {
                    'medicare_eligible': True,
                    'age_factor': 3.0,  # Max factor for display purposes
                }
                continue

            # Use standard ACA age factor (age 21=1.0, age 64=3.0)
            age_factor = get_aca_age_factor(age)

            if monthly_income and monthly_income > 0 and lcsp > 0:
                # Use unified eligibility check from subsidy_utils
                eligibility = is_subsidy_eligible(
                    monthly_income=monthly_income,
                    lcsp=lcsp,
                    contribution=contribution,
                    age=age,
                    slcsp=slcsp,
                    family_status=family_status,
                )

                # Calculate subsidy using SLCSP (ACA benchmark)
                estimated_subsidy = calculate_monthly_subsidy(slcsp, monthly_income, family_status, lcsp)
                # ROI based on LCSP (what employee would actually pay for cheapest plan)
                subsidy_roi = estimated_subsidy / lcsp if lcsp > 0 else 0

                # Get max contribution for eligibility from unified function
                max_for_eligibility = eligibility.get('max_contribution_for_eligibility')

                # Cache for second pass
                employee_subsidy_data[emp_id] = {
                    'medicare_eligible': False,
                    'estimated_subsidy': estimated_subsidy,
                    'subsidy_roi': subsidy_roi,
                    'max_for_eligibility': max_for_eligibility,
                    'age_factor': age_factor,
                    'is_eligible': eligibility.get('eligible', False),
                }
            else:
                # No income data - still cache the age factor
                employee_subsidy_data[emp_id] = {
                    'medicare_eligible': False,
                    'age_factor': age_factor,
                }

    # Determine income column label based on safe harbor
    if safe_harbor_type == 'fpl':
        income_label = 'Income Measure (FPL)'
    elif safe_harbor_type == 'rate_of_pay':
        income_label = 'Income Measure (Rate of Pay)'
    else:
        income_label = 'Monthly Income'

    rows = []
    for emp_id, data in employee_contributions.items():
        # Check if Medicare-eligible from strategy data
        is_medicare = data.get('is_medicare', False)

        row = {
            'Employee ID': emp_id,
            'Name': data.get('name', emp_id),
            'Age': data.get('age', ''),
            'State': data.get('state', ''),
            'Family Status': data.get('family_status', 'EE'),
            'ER Monthly Contribution': data.get('monthly_contribution', 0),
            'ER Annual Contribution': data.get('annual_contribution', 0),
            # LCSP/SLCSP not applicable for Medicare-eligible employees (65+)
            'LCSP Premium': 'N/A (Medicare)' if is_medicare else data.get('lcsp_ee_rate', 0),
            'SLCSP Premium': 'N/A' if is_medicare else (data.get('slcsp_ee_rate') or ''),
            'Rating Area': data.get('rating_area', ''),
        }

        # Mark excluded reason for Medicare employees
        if is_medicare:
            row['Excluded Reason'] = data.get('excluded_reason', 'Medicare-eligible (65+)')

        # ALE mode: Add affordability columns
        if emp_id in employee_affordability:
            aff = employee_affordability[emp_id]
            is_affordable = aff.get('is_affordable', False)
            margin = aff.get('margin_to_threshold', 0)

            row['Employee Cost'] = aff.get('employee_cost', 0)
            row[income_label] = aff.get('income_measure', '')
            row['Affordable'] = 'Yes' if is_affordable else 'No'
            aff_pct = aff.get('affordability_pct', 0)
            row['Affordability %'] = round(aff_pct / 100, 4) if aff_pct else 0
            row['Threshold %'] = 0.0996
            row['Margin %'] = round(margin / 100, 4)
            row['Gap to Affordable'] = aff.get('gap', 0) if not is_affordable else 0

        # Non-ALE mode: Consistent columns for all strategies
        elif mode in [OperatingMode.NON_ALE_SUBSIDY, OperatingMode.NON_ALE_STANDARD]:
            monthly_income = data.get('monthly_income')
            affordability_pct = data.get('affordability_pct')
            margin = data.get('margin_to_unaffordable')
            lcsp = data.get('lcsp_ee_rate', 0) or 0
            contribution = data.get('monthly_contribution', 0)

            # Medicare employees (65+): LCSP/Employee Cost not applicable
            if is_medicare:
                row['Employee Cost'] = 'N/A (Medicare)'
                row['Monthly Income'] = monthly_income if monthly_income is not None else ''
                row['Affordability %'] = 'N/A'
                row['Threshold %'] = ''
                row['Margin %'] = ''
                row['Subsidy Eligible'] = 'N/A (Medicare)'
            else:
                # Regular employees: calculate affordability metrics
                row['Employee Cost'] = data.get('employee_cost', max(0, lcsp - contribution))
                row['Monthly Income'] = monthly_income if monthly_income is not None else ''
                row['Affordability %'] = round(affordability_pct / 100, 4) if affordability_pct is not None else ''
                row['Threshold %'] = AFFORDABILITY_THRESHOLD_2026
                row['Margin %'] = round(margin / 100, 4) if margin is not None else ''

            # Subsidy eligibility (only for non-Medicare)
            if is_medicare:
                pass  # Already set above
            elif emp_id in employee_subsidy_data:
                # Use unified eligibility from subsidy_utils (pre-calculated in pre-pass)
                cached = employee_subsidy_data[emp_id]
                # is_eligible is True only if: NOT Medicare AND ICHRA unaffordable AND subsidy > 0
                if cached.get('is_eligible', False):
                    row['Subsidy Eligible'] = 'Yes'
                else:
                    row['Subsidy Eligible'] = 'No'
            else:
                # No cached data - can't determine eligibility
                row['Subsidy Eligible'] = ''

            # Max contribution that keeps employee subsidy-eligible
            # Uses unified calculation from subsidy_utils
            # N/A for Medicare-eligible employees (they can't get ACA subsidies)
            if is_medicare:
                row['Max Contribution for Eligibility'] = 'N/A (Medicare)'
            elif emp_id in employee_subsidy_data:
                cached = employee_subsidy_data[emp_id]
                max_for_eligibility = cached.get('max_for_eligibility')
                if max_for_eligibility is None:
                    row['Max Contribution for Eligibility'] = 'N/A (already affordable)'
                else:
                    row['Max Contribution for Eligibility'] = round(max_for_eligibility, 2)
            else:
                row['Max Contribution for Eligibility'] = ''

            # Use cached subsidy data from pre-pass
            if emp_id in employee_subsidy_data:
                cached = employee_subsidy_data[emp_id]

                # Check if Medicare-eligible (65+) - all subsidy columns N/A
                if is_medicare or cached.get('medicare_eligible', False):
                    row['Est. Monthly Subsidy'] = 'N/A'
                    row['LCSP after subsidy'] = 'N/A'
                    row['compared to EE Cost'] = 'N/A'
                    row['Subsidy ROI'] = 'N/A'
                # Check if "already affordable" (max_for_eligibility < 0)
                # These employees can NEVER access subsidies regardless of contribution
                elif (cached.get('max_for_eligibility') or 0) < 0:
                    row['Est. Monthly Subsidy'] = ''  # Misleading - they can't access this
                    row['LCSP after subsidy'] = ''    # N/A - subsidies not available
                    row['compared to EE Cost'] = ''   # N/A - can't compare
                    row['Subsidy ROI'] = ''           # Misleading - they can't access this
                else:
                    estimated_subsidy = cached.get('estimated_subsidy', 0)
                    subsidy_roi = cached.get('subsidy_roi', 0)

                    row['Est. Monthly Subsidy'] = round(estimated_subsidy, 2)

                    # LCSP after subsidy = what employee pays for LCSP with ACA subsidies
                    lcsp_after_subsidy = lcsp - estimated_subsidy if estimated_subsidy else lcsp
                    row['LCSP after subsidy'] = round(lcsp_after_subsidy, 2)

                    # compared to EE Cost = (LCSP after subsidy) - (Employee Cost with ICHRA)
                    # Negative means subsidies are cheaper for the employee
                    ichra_employee_cost = row.get('Employee Cost', 0)
                    if ichra_employee_cost and lcsp_after_subsidy:
                        row['compared to EE Cost'] = round(lcsp_after_subsidy - ichra_employee_cost, 2)
                    else:
                        row['compared to EE Cost'] = ''

                    row['Subsidy ROI'] = round(subsidy_roi, 4) if subsidy_roi else 0
            else:
                row['Est. Monthly Subsidy'] = ''
                row['LCSP after subsidy'] = lcsp if lcsp else ''
                row['compared to EE Cost'] = ''
                row['Subsidy ROI'] = ''

        rows.append(row)

    df = pd.DataFrame(rows)

    # Convert to CSV
    output = io.StringIO()
    df.to_csv(output, index=False)
    return output.getvalue()


def render_next_steps(
    strategy_saved: bool = False,
) -> None:
    """
    Render next steps guidance after strategy is saved.

    Args:
        strategy_saved: Whether strategy has been saved
    """
    if not strategy_saved:
        return

    st.success("✅ Strategy saved successfully!")

    st.markdown("""
    ### Next Steps

    1. **Employer Summary** (Page 5) - Review total costs and savings analysis
    2. **Individual Analysis** (Page 6) - See per-employee plan options
    3. **Export Results** (Page 7) - Generate detailed reports
    4. **Proposal Generator** (Page 8) - Create client-ready presentations
    """)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("→ Go to Employer Summary", type="primary"):
            st.switch_page("pages/5_Employer_summary.py")
    with col2:
        if st.button("→ Go to Individual Analysis"):
            st.switch_page("pages/6_Individual_analysis.py")
