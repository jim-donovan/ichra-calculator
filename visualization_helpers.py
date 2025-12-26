"""
Visualization Helpers for ICHRA Calculator

Reusable chart generation functions that can produce visualizations for both
Streamlit display and PDF embedding.

Author: Claude Code
Date: 2025-12-06
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from typing import Dict, List, Optional, Tuple, Union
from io import BytesIO


def generate_age_distribution_chart(
    census_df: pd.DataFrame,
    age_column: str = 'age',
    title: str = 'Employee Age Distribution',
    return_image: bool = False
) -> Union[go.Figure, bytes]:
    """
    Generate age distribution pie chart.

    Args:
        census_df: Employee census DataFrame
        age_column: Name of age column
        title: Chart title
        return_image: If True, return image bytes for PDF. If False, return Plotly figure for Streamlit

    Returns:
        Plotly Figure object or PNG image bytes
    """
    # Define age bins
    age_bins = [18, 25, 35, 45, 55, 65, 100]
    age_labels = ['18-24', '25-34', '35-44', '45-54', '55-64', '65+']

    # Create age groups
    census_with_age_group = census_df.copy()
    census_with_age_group['age_group'] = pd.cut(
        census_with_age_group[age_column],
        bins=age_bins,
        labels=age_labels,
        right=False
    )

    age_dist = census_with_age_group['age_group'].value_counts().sort_index()

    # Create figure
    fig = px.pie(
        values=age_dist.values,
        names=age_dist.index,
        title=title,
        color_discrete_sequence=px.colors.qualitative.Set3
    )

    fig.update_traces(textposition='inside', textinfo='percent+label')
    fig.update_layout(showlegend=True)

    if return_image:
        # Convert to image bytes for PDF embedding
        return fig.to_image(format="png", width=600, height=400)
    else:
        return fig


def generate_state_distribution_chart(
    census_df: pd.DataFrame,
    state_column: str = 'state',
    title: str = 'Employees by State',
    return_image: bool = False
) -> Union[go.Figure, bytes]:
    """
    Generate state distribution bar chart.

    Args:
        census_df: Employee census DataFrame
        state_column: Name of state column
        title: Chart title
        return_image: If True, return image bytes for PDF

    Returns:
        Plotly Figure object or PNG image bytes
    """
    state_dist = census_df[state_column].value_counts().sort_index()

    fig = px.bar(
        x=state_dist.index,
        y=state_dist.values,
        title=title,
        labels={'x': 'State', 'y': 'Number of Employees'},
        color=state_dist.values,
        color_continuous_scale='Blues'
    )

    fig.update_layout(showlegend=False, height=400)
    fig.update_xaxes(title='State')
    fig.update_yaxes(title='Number of Employees')

    if return_image:
        return fig.to_image(format="png", width=600, height=400)
    else:
        return fig


def generate_savings_comparison_chart(
    group_plan_cost: float,
    ichra_costs: Dict[str, float],
    plan_names: Dict[str, str],
    title: str = 'Annual Employer Cost Comparison',
    return_image: bool = False
) -> Union[go.Figure, bytes]:
    """
    Generate savings comparison bar chart showing current group plan vs ICHRA options.

    Args:
        group_plan_cost: Annual cost of current group plan
        ichra_costs: Dict of {plan_id: annual_cost}
        plan_names: Dict of {plan_id: plan_name}
        title: Chart title
        return_image: If True, return image bytes for PDF

    Returns:
        Plotly Figure object or PNG image bytes
    """
    # Build visualization data
    viz_data = []

    # Add current group plan
    viz_data.append({
        'Plan': 'Current',
        'Option': 'Current\nGroup Plan',
        'Annual Cost': group_plan_cost
    })

    # Add ICHRA options
    for plan_id, ichra_cost in ichra_costs.items():
        plan_name = plan_names.get(plan_id, plan_id)

        # Wrap long plan names
        wrapped_plan_name = '\n'.join([
            plan_name[i:i+20] for i in range(0, len(plan_name), 20)
        ])[:60]  # Limit to 3 lines

        viz_data.append({
            'Plan': 'ICHRA',
            'Option': wrapped_plan_name,
            'Annual Cost': ichra_cost
        })

    viz_df = pd.DataFrame(viz_data)

    fig = px.bar(
        viz_df,
        x='Option',
        y='Annual Cost',
        color='Plan',
        title=title,
        labels={'Annual Cost': 'Annual Employer Cost ($)'},
        barmode='group',
        color_discrete_map={'Current': '#ff7f0e', 'ICHRA': '#1f77b4'}
    )

    fig.update_layout(height=500)
    fig.update_xaxes(tickangle=-45)

    if return_image:
        return fig.to_image(format="png", width=800, height=500)
    else:
        return fig


def generate_family_composition_chart(
    census_df: pd.DataFrame,
    dependents_df: Optional[pd.DataFrame] = None,
    title: str = 'Family Composition Distribution',
    return_image: bool = False
) -> Union[go.Figure, bytes]:
    """
    Generate family composition bar chart.

    Args:
        census_df: Employee census DataFrame
        dependents_df: Dependents DataFrame (if available)
        title: Chart title
        return_image: If True, return image bytes for PDF

    Returns:
        Plotly Figure object or PNG image bytes
    """
    # Count families by composition
    family_comp_counts = {}

    if dependents_df is not None and not dependents_df.empty:
        for _, emp in census_df.iterrows():
            employee_id = emp.get('employee_id', emp.name)

            # Get dependents for this employee
            emp_deps = dependents_df[dependents_df['employee_id'] == employee_id]

            # Determine family composition
            if emp_deps.empty:
                comp = "Employee Only"
            else:
                has_spouse = not emp_deps[emp_deps['relationship'] == 'spouse'].empty
                num_children = len(emp_deps[emp_deps['relationship'] == 'child'])

                if has_spouse and num_children > 0:
                    comp = f"EE + Spouse + {num_children} Child{'ren' if num_children > 1 else ''}"
                elif has_spouse:
                    comp = "EE + Spouse"
                elif num_children > 0:
                    comp = f"EE + {num_children} Child{'ren' if num_children > 1 else ''}"
                else:
                    comp = "Employee Only"

            family_comp_counts[comp] = family_comp_counts.get(comp, 0) + 1
    else:
        # No dependents data - all employee only
        family_comp_counts['Employee Only'] = len(census_df)

    # Create figure
    fig = px.bar(
        x=list(family_comp_counts.keys()),
        y=list(family_comp_counts.values()),
        title=title,
        labels={'x': 'Family Type', 'y': 'Number of Employees'},
        color=list(family_comp_counts.values()),
        color_continuous_scale='Greens'
    )

    fig.update_layout(showlegend=False, height=400)
    fig.update_xaxes(title='Family Type', tickangle=-45)
    fig.update_yaxes(title='Number of Employees')

    if return_image:
        return fig.to_image(format="png", width=600, height=400)
    else:
        return fig


def generate_dependent_age_distribution_chart(
    dependents_df: pd.DataFrame,
    title: str = 'Dependent Age Distribution',
    return_image: bool = False
) -> Union[go.Figure, bytes]:
    """
    Generate dependent age distribution bar chart.

    Args:
        dependents_df: Dependents DataFrame
        title: Chart title
        return_image: If True, return image bytes for PDF

    Returns:
        Plotly Figure object or PNG image bytes
    """
    # Use different age bins for dependents (more granular for children)
    dep_age_bins = [0, 5, 13, 18, 21, 30, 40, 50, 100]
    dep_age_labels = ['0-4', '5-12', '13-17', '18-20', '21-29', '30-39', '40-49', '50+']

    dependents_with_age_group = dependents_df.copy()
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
        title=title,
        labels={'x': 'Age Group', 'y': 'Number of Dependents'},
        color=dep_age_dist.values,
        color_continuous_scale='Purples'
    )

    fig.update_layout(showlegend=False, height=400)
    fig.update_xaxes(title='Age Group')
    fig.update_yaxes(title='Number of Dependents')

    if return_image:
        return fig.to_image(format="png", width=600, height=400)
    else:
        return fig


def generate_dependent_relationship_chart(
    dependents_df: pd.DataFrame,
    title: str = 'Dependents by Relationship',
    return_image: bool = False
) -> Union[go.Figure, bytes]:
    """
    Generate dependent relationship pie chart.

    Args:
        dependents_df: Dependents DataFrame
        title: Chart title
        return_image: If True, return image bytes for PDF

    Returns:
        Plotly Figure object or PNG image bytes
    """
    rel_counts = dependents_df['relationship'].value_counts()

    fig = px.pie(
        values=rel_counts.values,
        names=[rel.title() + 's' for rel in rel_counts.index],
        title=title,
        color_discrete_sequence=px.colors.qualitative.Pastel
    )

    fig.update_traces(textposition='inside', textinfo='percent+label')
    fig.update_layout(showlegend=True)

    if return_image:
        return fig.to_image(format="png", width=600, height=400)
    else:
        return fig


# Helper function to get all demographic charts at once
def generate_all_demographic_charts(
    census_df: pd.DataFrame,
    dependents_df: Optional[pd.DataFrame] = None,
    return_images: bool = False
) -> Dict[str, Union[go.Figure, bytes]]:
    """
    Generate all demographic charts in one call.

    Args:
        census_df: Employee census DataFrame
        dependents_df: Dependents DataFrame (optional)
        return_images: If True, return image bytes. If False, return Plotly figures

    Returns:
        Dictionary of chart names to figures/images
    """
    charts = {}

    # Employee charts
    charts['age_distribution'] = generate_age_distribution_chart(
        census_df, return_image=return_images
    )
    charts['state_distribution'] = generate_state_distribution_chart(
        census_df, return_image=return_images
    )
    charts['family_composition'] = generate_family_composition_chart(
        census_df, dependents_df, return_image=return_images
    )

    # Dependent charts (if data available)
    if dependents_df is not None and not dependents_df.empty:
        charts['dependent_age_distribution'] = generate_dependent_age_distribution_chart(
            dependents_df, return_image=return_images
        )
        charts['dependent_relationship'] = generate_dependent_relationship_chart(
            dependents_df, return_image=return_images
        )

    return charts
