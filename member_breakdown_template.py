"""
Member Rate Breakdown HTML Template Generator

Generates mobile-friendly HTML pages showing individual member rate breakdowns
for ICHRA plan comparisons.
"""

import html
from typing import Dict, List, Optional
from datetime import datetime, timedelta


def generate_member_breakdown_html(
    employee_name: str,
    employee_age: int,
    tier: str,
    location: str,
    family_ages: List[Dict],
    member_breakdowns: Dict[str, Dict],
    generated_date: Optional[datetime] = None,
    expiry_days: int = 7,
    client_name: str = ""
) -> str:
    """Generate HTML page for member rate breakdown.

    Args:
        employee_name: Employee's display name
        employee_age: Employee's age
        tier: Coverage tier (e.g., "Family", "Employee + Spouse")
        location: Location string (e.g., "Dallas, TX 75201")
        family_ages: List of dicts with 'relationship' and 'age' keys
        member_breakdowns: Dict of plan_name -> breakdown dict
        generated_date: When the breakdown was generated
        expiry_days: Days until link expires
        client_name: Client/company name (optional)

    Returns:
        Complete HTML string
    """
    if generated_date is None:
        generated_date = datetime.now()

    expiry_date = generated_date + timedelta(days=expiry_days)

    # Escape user-provided strings to prevent XSS
    employee_name = html.escape(str(employee_name))
    tier = html.escape(str(tier))
    location = html.escape(str(location))
    client_name = html.escape(str(client_name)) if client_name else ""

    # Build member rows
    members = [{'label': 'Employee', 'age': employee_age, 'key': 'ee'}]

    # Get spouse
    spouse_age = None
    for fa in family_ages:
        rel = fa.get('relationship', '').lower()
        age = fa.get('age', 0)
        if rel == 'spouse':
            spouse_age = age
            members.append({'label': 'Spouse', 'age': age, 'key': 'spouse'})

    # Get children and sort by age ASCENDING
    children = []
    for fa in family_ages:
        rel = fa.get('relationship', '').lower()
        if rel == 'child':
            children.append(fa.get('age', 0))
    children.sort()  # Ascending order

    # Add children in ascending age order
    for idx, child_age in enumerate(children, 1):
        members.append({
            'label': f'Child {idx}',
            'age': child_age,
            'key': f'child_{idx}'
        })

    # Build family info display for header
    family_parts = []
    if spouse_age is not None:
        family_parts.append(f"Spouse ({spouse_age})")
    if children:
        if len(children) == 1:
            family_parts.append(f"Child ({children[0]})")
        else:
            family_parts.append(f"Children ({', '.join(str(c) for c in children)})")
    family_display = " • ".join(family_parts) if family_parts else ""

    # Determine which plans to show
    plan_order = ['Bronze', 'Silver', 'Gold']
    # Add HAS and Sedera plans
    for plan_name in sorted(member_breakdowns.keys()):
        if plan_name.startswith('HAS') or plan_name.startswith('Sedera'):
            if plan_name not in plan_order:
                plan_order.append(plan_name)

    # Filter to only plans we have data for
    available_plans = [p for p in plan_order if p in member_breakdowns]

    # Generate table headers
    header_cells = '<th class="member-col">Member</th><th class="age-col">Age</th>'
    for plan in available_plans:
        plan_class = _get_plan_class(plan)
        escaped_plan = html.escape(str(plan))
        header_cells += f'<th class="rate-col {plan_class}">{escaped_plan}</th>'

    # Generate table rows
    table_rows = ""
    totals = {plan: 0.0 for plan in available_plans}

    for member in members:
        row_cells = f'<td class="member-col">{member["label"]}</td>'
        row_cells += f'<td class="age-col">{member["age"]}</td>'

        for plan in available_plans:
            breakdown = member_breakdowns.get(plan, {})
            rate_key = f'{member["key"]}_rate'
            rate = breakdown.get(rate_key)

            if rate is not None and rate > 0:
                row_cells += f'<td class="rate-col">${rate:,.0f}</td>'
                totals[plan] += rate
            else:
                row_cells += '<td class="rate-col na">-</td>'

        table_rows += f'<tr>{row_cells}</tr>'

    # Generate totals row
    total_cells = '<td class="member-col"><strong>Total</strong></td><td class="age-col"></td>'
    for plan in available_plans:
        total_cells += f'<td class="rate-col total"><strong>${totals[plan]:,.0f}</strong></td>'

    # Generate HTML
    client_suffix = f" for {client_name}" if client_name else ""

    html_output = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Rate Breakdown - {employee_name}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family: 'Poppins', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: #f8fafc;
            color: #1e293b;
            line-height: 1.5;
            padding: 16px;
        }}

        .container {{
            max-width: 800px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            overflow: hidden;
        }}

        .header {{
            background: linear-gradient(135deg, #0047AB 0%, #003d91 100%);
            color: white;
            padding: 20px;
        }}

        .header h1 {{
            font-size: 1.25rem;
            font-weight: 600;
            margin-bottom: 4px;
        }}

        .header .subtitle {{
            font-size: 0.875rem;
            opacity: 0.9;
        }}

        .employee-info {{
            padding: 16px 20px;
            background: #f1f5f9;
            border-bottom: 1px solid #e2e8f0;
        }}

        .employee-info h2 {{
            font-size: 1.125rem;
            font-weight: 600;
            color: #0f172a;
            margin-bottom: 8px;
        }}

        .info-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: 12px;
        }}

        .info-item {{
            font-size: 0.875rem;
        }}

        .info-label {{
            color: #64748b;
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        .info-value {{
            color: #0f172a;
            font-weight: 500;
        }}

        .family-info {{
            grid-column: 1 / -1;
            margin-top: 4px;
            padding-top: 8px;
            border-top: 1px solid #e2e8f0;
        }}

        .table-container {{
            padding: 16px;
            overflow-x: auto;
        }}

        .table-title {{
            font-size: 0.875rem;
            font-weight: 600;
            color: #475569;
            margin-bottom: 12px;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.875rem;
        }}

        th {{
            background: #f8fafc;
            padding: 10px 12px;
            text-align: center;
            font-weight: 600;
            color: #475569;
            border-bottom: 2px solid #e2e8f0;
            white-space: nowrap;
        }}

        th.member-col, th.age-col {{
            text-align: left;
        }}

        td {{
            padding: 10px 12px;
            text-align: center;
            border-bottom: 1px solid #f1f5f9;
        }}

        td.member-col {{
            text-align: left;
            font-weight: 500;
        }}

        td.age-col {{
            text-align: left;
            color: #64748b;
        }}

        td.na {{
            color: #cbd5e1;
        }}

        td.total {{
            background: #f8fafc;
            border-top: 2px solid #e2e8f0;
        }}

        tr:hover td {{
            background: #f8fafc;
        }}

        tr:last-child td {{
            border-bottom: none;
        }}

        /* Plan-specific header colors */
        th.bronze {{ background: #fef3c7; color: #92400e; }}
        th.silver {{ background: #f3f4f6; color: #374151; }}
        th.gold {{ background: #fef9c3; color: #854d0e; }}
        th.has {{ background: #dcfce7; color: #166534; }}
        th.sedera {{ background: #fef3c7; color: #92400e; }}

        .footer {{
            padding: 16px 20px;
            background: #f8fafc;
            border-top: 1px solid #e2e8f0;
            font-size: 0.75rem;
            color: #64748b;
        }}

        .footer-row {{
            display: flex;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 8px;
        }}

        .expiry-notice {{
            color: #dc2626;
            font-weight: 500;
        }}

        .branding {{
            color: #94a3b8;
        }}

        @media (max-width: 600px) {{
            body {{
                padding: 8px;
            }}

            .header {{
                padding: 16px;
            }}

            .header h1 {{
                font-size: 1.125rem;
            }}

            th, td {{
                padding: 8px 6px;
                font-size: 0.8rem;
            }}

            .info-grid {{
                grid-template-columns: 1fr 1fr;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Member Rate Breakdown</h1>
            <div class="subtitle">Monthly premium rates by family member</div>
        </div>

        <div class="employee-info">
            <h2>{employee_name}</h2>
            <div class="info-grid">
                <div class="info-item">
                    <div class="info-label">Employee Age</div>
                    <div class="info-value">{employee_age}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Coverage Tier</div>
                    <div class="info-value">{tier}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Location</div>
                    <div class="info-value">{location}</div>
                </div>
                {f'<div class="info-item family-info"><div class="info-label">Family Members</div><div class="info-value">{family_display}</div></div>' if family_display else ''}
            </div>
        </div>

        <div class="table-container">
            <div class="table-title">Individual Member Rates (Monthly)</div>
            <table>
                <thead>
                    <tr>
                        {header_cells}
                    </tr>
                </thead>
                <tbody>
                    {table_rows}
                    <tr class="total-row">
                        {total_cells}
                    </tr>
                </tbody>
            </table>
        </div>

        <div class="footer">
            <div class="footer-row">
                <span>Generated {generated_date.strftime('%B %d, %Y')}{client_suffix}</span>
                <span class="expiry-notice">Link expires {expiry_date.strftime('%B %d, %Y')}</span>
            </div>
            <div class="branding" style="margin-top: 8px;">
                ICHRA Plan Calculator by Glove Benefits
            </div>
        </div>
    </div>
</body>
</html>"""

    return html_output


def _get_plan_class(plan_name: str) -> str:
    """Get CSS class for plan header styling."""
    plan_lower = plan_name.lower()
    if 'bronze' in plan_lower:
        return 'bronze'
    elif 'silver' in plan_lower:
        return 'silver'
    elif 'gold' in plan_lower:
        return 'gold'
    elif 'has' in plan_lower:
        return 'has'
    elif 'sedera' in plan_lower:
        return 'sedera'
    return ''


if __name__ == "__main__":
    # Test template generation
    test_breakdowns = {
        'Bronze': {
            'ee_rate': 450.0,
            'ee_age': 35,
            'spouse_rate': 430.0,
            'spouse_age': 33,
            'child_1_rate': 220.0,
            'child_1_age': 8,
            'child_2_rate': 220.0,
            'child_2_age': 6,
            'total_rate': 1320.0,
        },
        'Silver': {
            'ee_rate': 520.0,
            'spouse_rate': 495.0,
            'child_1_rate': 255.0,
            'child_2_rate': 255.0,
            'total_rate': 1525.0,
        },
        'Gold': {
            'ee_rate': 610.0,
            'spouse_rate': 580.0,
            'child_1_rate': 300.0,
            'child_2_rate': 300.0,
            'total_rate': 1790.0,
        },
        'HAS $1k': {
            'ee_rate': 332.0,
            'spouse_rate': 332.0,
            'child_1_rate': 332.0,
            'child_2_rate': 332.0,
            'total_rate': 1328.0,
        },
    }

    test_family = [
        {'relationship': 'spouse', 'age': 33},
        {'relationship': 'child', 'age': 8},
        {'relationship': 'child', 'age': 6},
    ]

    html = generate_member_breakdown_html(
        employee_name="John Smith",
        employee_age=35,
        tier="Family",
        location="Dallas, TX 75201",
        family_ages=test_family,
        member_breakdowns=test_breakdowns,
        client_name="ABC Company"
    )

    # Save test file
    with open("test_breakdown.html", "w") as f:
        f.write(html)

    print(f"Generated test HTML: {len(html)} bytes")
    print("Saved to test_breakdown.html")
