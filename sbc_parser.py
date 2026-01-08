"""
SBC (Summary of Benefits and Coverage) Markdown Parser

Parses pre-transformed SBC markdown files to extract plan details
for auto-populating the Plan Comparison form.
"""

import re
from typing import Optional, Dict, Any


def parse_sbc_markdown(content: str) -> Dict[str, Any]:
    """
    Extract plan fields from transformed SBC markdown.

    Args:
        content: Raw markdown content from SBC transformation tool

    Returns:
        Dict with extracted plan fields matching CurrentEmployerPlan structure
    """
    result = {
        "plan_name": extract_plan_name(content),
        "carrier": None,
        "plan_type": None,
        "metal_tier": None,
        "hsa_eligible": False,
        "individual_deductible": None,
        "family_deductible": None,
        "individual_oop_max": None,
        "family_oop_max": None,
        "coinsurance_pct": None,
        "pcp_copay": None,
        "specialist_copay": None,
        "er_copay": None,
        "generic_rx_copay": None,
        "preferred_rx_copay": None,
        "specialty_rx_copay": None,
        # SBC scenario costs (for comparison with RBIS sbc_scenario data)
        "sbc_having_baby_cost": None,
        "sbc_diabetes_cost": None,
        "sbc_fracture_cost": None,
        # Additional benefits
        "mental_health_outpatient": None,
        "imaging_coinsurance": None,
        "inpatient_coinsurance": None,
    }

    plan_name = result["plan_name"]
    if plan_name:
        result["carrier"] = detect_carrier(plan_name)
        result["metal_tier"] = detect_metal_tier(plan_name)
        result["hsa_eligible"] = detect_hsa_eligible(plan_name)

    result["plan_type"] = extract_plan_type(content)

    deductibles = extract_deductibles(content)
    result["individual_deductible"] = deductibles.get("individual")
    result["family_deductible"] = deductibles.get("family")

    oop_limits = extract_oop_limits(content)
    result["individual_oop_max"] = oop_limits.get("individual")
    result["family_oop_max"] = oop_limits.get("family")

    result["coinsurance_pct"] = extract_coinsurance(content)

    copays = extract_copays(content)
    result.update(copays)

    # SBC scenario costs
    sbc_scenarios = extract_sbc_scenarios(content)
    result.update(sbc_scenarios)

    # Additional benefits
    additional = extract_additional_benefits(content)
    result.update(additional)

    return result


def extract_plan_name(content: str) -> Optional[str]:
    """Extract plan name from **Plan:** line."""
    match = re.search(r'\*\*Plan:\*\*\s*(.+?)(?:\s*\n|$)', content)
    if match:
        return match.group(1).strip()
    return None


def extract_plan_type(content: str) -> Optional[str]:
    """Extract plan type (HMO, PPO, EPO, POS) from **Plan Type:** line or plan name."""
    match = re.search(r'\*\*Plan Type:\*\*\s*(.+?)(?:\s*\n|$)', content)
    if match:
        plan_type_text = match.group(1).strip().upper()
        for pt in ["PPO", "HMO", "EPO", "POS"]:
            if pt in plan_type_text:
                return pt

    plan_name_match = re.search(r'\*\*Plan:\*\*\s*(.+?)(?:\s*\n|$)', content)
    if plan_name_match:
        plan_name = plan_name_match.group(1).upper()
        for pt in ["PPO", "HMO", "EPO", "POS"]:
            if pt in plan_name:
                return pt

    return "HMO"


def extract_deductibles(content: str) -> Dict[str, Optional[float]]:
    """
    Extract individual and family deductibles from "What is the overall deductible?" section.

    Patterns:
    - "$2,850 Self only enrollment"
    - "$5,700 for an entire Family"
    """
    result = {"individual": None, "family": None}

    deductible_section = re.search(
        r'What is the overall deductible\?\*?\*?:?\s*(.*?)(?=\*\*(?:Why This Matters|Are there)|$)',
        content,
        re.IGNORECASE | re.DOTALL
    )

    if deductible_section:
        section_text = deductible_section.group(1)

        individual_match = re.search(r'\$([0-9,]+)\s*(?:Self only|individual)', section_text, re.IGNORECASE)
        if individual_match:
            result["individual"] = float(individual_match.group(1).replace(",", ""))

        family_match = re.search(r'\$([0-9,]+)\s*(?:for an entire Family|family)', section_text, re.IGNORECASE)
        if family_match:
            result["family"] = float(family_match.group(1).replace(",", ""))

    return result


def extract_oop_limits(content: str) -> Dict[str, Optional[float]]:
    """
    Extract individual and family out-of-pocket limits from
    "What is the out-of-pocket limit for this plan?" section.
    """
    result = {"individual": None, "family": None}

    oop_section = re.search(
        r'What is the out-of-pocket limit.*?\*?\*?:?\s*(.*?)(?=\*\*(?:Why This Matters|What is not)|$)',
        content,
        re.IGNORECASE | re.DOTALL
    )

    if oop_section:
        section_text = oop_section.group(1)

        individual_match = re.search(r'\$([0-9,]+)\s*(?:Self only|individual)', section_text, re.IGNORECASE)
        if individual_match:
            result["individual"] = float(individual_match.group(1).replace(",", ""))

        family_match = re.search(r'\$([0-9,]+)\s*(?:for an entire Family|family)', section_text, re.IGNORECASE)
        if family_match:
            result["family"] = float(family_match.group(1).replace(",", ""))

    return result


def extract_coinsurance(content: str) -> Optional[int]:
    """
    Extract coinsurance percentage from primary care or specialist visit row.

    Pattern: "25% coinsurance"
    """
    patterns = [
        r'Primary care visit.*?(\d+)%\s*coinsurance',
        r'Specialist visit.*?(\d+)%\s*coinsurance',
        r'treat an injury or illness.*?(\d+)%\s*coinsurance',
    ]

    for pattern in patterns:
        match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
        if match:
            return int(match.group(1))

    general_match = re.search(r'(\d+)%\s*coinsurance', content)
    if general_match:
        return int(general_match.group(1))

    return 20


def extract_copays(content: str) -> Dict[str, Optional[float]]:
    """
    Extract copay amounts for various services.

    If service shows "$X copay" -> return the copay amount
    If service shows "X% coinsurance" -> return None (uses deductible + coinsurance)

    Note: Many HDHPs and coinsurance-based plans have NO flat copays.
    We only extract explicit "$X copay" amounts, NOT max limits like "$250/prescription".
    """
    result = {
        "pcp_copay": None,
        "specialist_copay": None,
        "er_copay": None,
        "generic_rx_copay": None,
        "preferred_rx_copay": None,
        "specialty_rx_copay": None,
    }

    # For each service, check if it shows "X% coinsurance" first (meaning NO flat copay)
    # Only extract a copay if we find explicit "$X copay" pattern

    coinsurance_services = {
        "pcp_copay": r'Primary care visit.*?(\d+)%\s*coinsurance',
        "specialist_copay": r'Specialist visit.*?(\d+)%\s*coinsurance',
        "er_copay": r'Emergency room care.*?(\d+)%\s*coinsurance',
        "generic_rx_copay": r'Generic drugs.*?(\d+)%\s*coinsurance',
        "preferred_rx_copay": r'Preferred brand.*?(\d+)%\s*coinsurance',
        "specialty_rx_copay": r'Specialty drugs.*?(\d+)%\s*coinsurance',
    }

    copay_patterns = {
        "pcp_copay": r'Primary care visit.*?\$(\d+)\s*(?:copay|co-?pay)(?!\s*/)',
        "specialist_copay": r'Specialist visit.*?\$(\d+)\s*(?:copay|co-?pay)(?!\s*/)',
        "er_copay": r'Emergency room care.*?\$(\d+)\s*(?:copay|co-?pay)(?!\s*/)',
        "generic_rx_copay": r'Generic drugs.*?\$(\d+)\s*(?:copay|co-?pay)(?!\s*/)',
        "preferred_rx_copay": r'Preferred brand.*?\$(\d+)\s*(?:copay|co-?pay)(?!\s*/)',
        "specialty_rx_copay": r'Specialty drugs.*?\$(\d+)\s*(?:copay|co-?pay)(?!\s*/)',
    }

    for field in result.keys():
        # First check if this service uses coinsurance (no flat copay)
        if coinsurance_services.get(field):
            coinsurance_match = re.search(
                coinsurance_services[field], content, re.IGNORECASE | re.DOTALL
            )
            if coinsurance_match:
                # Service uses coinsurance, leave copay as None
                continue

        # Check for explicit copay
        if copay_patterns.get(field):
            copay_match = re.search(
                copay_patterns[field], content, re.IGNORECASE | re.DOTALL
            )
            if copay_match:
                result[field] = float(copay_match.group(1))

    return result


def detect_carrier(plan_name: str) -> Optional[str]:
    """Detect insurance carrier from plan name."""
    carriers = {
        "Kaiser Permanente": ["kaiser", "kp"],
        "Blue Cross Blue Shield": ["bcbs", "blue cross", "blue shield", "anthem"],
        "Aetna": ["aetna"],
        "Cigna": ["cigna"],
        "UnitedHealthcare": ["united", "uhc"],
        "Humana": ["humana"],
        "Molina": ["molina"],
        "Oscar": ["oscar"],
        "Ambetter": ["ambetter"],
        "Centene": ["centene"],
    }

    plan_lower = plan_name.lower()
    for carrier, keywords in carriers.items():
        for keyword in keywords:
            if keyword in plan_lower:
                return carrier

    return None


def detect_metal_tier(plan_name: str) -> Optional[str]:
    """Detect metal tier (Bronze, Silver, Gold, Platinum) from plan name."""
    plan_lower = plan_name.lower()

    for tier in ["platinum", "gold", "silver", "bronze"]:
        if tier in plan_lower:
            return tier.capitalize()

    return None


def detect_hsa_eligible(plan_name: str) -> bool:
    """Detect if plan is HSA-eligible (HDHP) from plan name."""
    plan_upper = plan_name.upper()
    return "HDHP" in plan_upper or "HSA" in plan_upper


def extract_sbc_scenarios(content: str) -> Dict[str, Optional[float]]:
    """
    Extract SBC scenario costs (Having a Baby, Managing Diabetes, Simple Fracture).

    These scenarios are standardized across all SBCs and can be compared
    with RBIS sbc_scenario data for marketplace plans.

    Patterns in markdown tables:
    - "| **The total Peg would pay is** | **$4,860** |"
    - "| **The total Joe would pay is** | **$3,450** |"
    - "| **The total Mia would pay is** | **$2,800** |"
    """
    result = {
        "sbc_having_baby_cost": None,
        "sbc_diabetes_cost": None,
        "sbc_fracture_cost": None,
    }

    # Having a Baby (Peg) - look for table row pattern
    baby_match = re.search(
        r'\*\*The total Peg would pay is\*\*\s*\|\s*\*\*\$([0-9,]+)\*\*',
        content, re.IGNORECASE
    )
    if baby_match:
        result["sbc_having_baby_cost"] = float(baby_match.group(1).replace(",", ""))

    # Managing Diabetes (Joe) - look for table row pattern
    diabetes_match = re.search(
        r'\*\*The total Joe would pay is\*\*\s*\|\s*\*\*\$([0-9,]+)\*\*',
        content, re.IGNORECASE
    )
    if diabetes_match:
        result["sbc_diabetes_cost"] = float(diabetes_match.group(1).replace(",", ""))

    # Simple Fracture (Mia) - look for table row pattern
    fracture_match = re.search(
        r'\*\*The total Mia would pay is\*\*\s*\|\s*\*\*\$([0-9,]+)\*\*',
        content, re.IGNORECASE
    )
    if fracture_match:
        result["sbc_fracture_cost"] = float(fracture_match.group(1).replace(",", ""))

    return result


def extract_additional_benefits(content: str) -> Dict[str, Optional[str]]:
    """
    Extract additional benefit cost-sharing details.

    - Mental health outpatient (often "No charge" or coinsurance)
    - Imaging (CT/MRI coinsurance)
    - Inpatient hospital (coinsurance)
    """
    result = {
        "mental_health_outpatient": None,
        "imaging_coinsurance": None,
        "inpatient_coinsurance": None,
    }

    # Mental health outpatient
    mh_match = re.search(
        r'mental health.*?Outpatient services.*?:?\s*(No charge|(\d+)%\s*coinsurance)',
        content, re.IGNORECASE | re.DOTALL
    )
    if mh_match:
        result["mental_health_outpatient"] = mh_match.group(1).strip()

    # Imaging (CT/PET/MRI)
    imaging_match = re.search(
        r'Imaging.*?(?:CT|PET|MRI).*?:?\s*(\d+)%\s*coinsurance',
        content, re.IGNORECASE | re.DOTALL
    )
    if imaging_match:
        result["imaging_coinsurance"] = f"{imaging_match.group(1)}%"

    # Inpatient hospital (facility fee)
    inpatient_match = re.search(
        r'(?:hospital stay|inpatient).*?Facility fee.*?:?\s*(\d+)%\s*coinsurance',
        content, re.IGNORECASE | re.DOTALL
    )
    if inpatient_match:
        result["inpatient_coinsurance"] = f"{inpatient_match.group(1)}%"

    return result


if __name__ == "__main__":
    sample = """
    **Plan:** KAISER PERMANENTE Silver 70 HDHP HMO 2850/25% + Child Dental
    **Coverage for:** Individual / Family | **Plan Type:** Deductible HMO

    **Answers** - **What is the overall deductible?**: $2,850 Self only enrollment.
    $5,700 for an entire Family

    **Answers** - **What is the out-of-pocket limit for this plan?**: $7,500 Self only enrollment.
    $15,000 for an entire Family.

    Primary care visit to treat an injury or illness: 25% coinsurance
    Specialist visit: 25% coinsurance
    Emergency room care: 25% coinsurance
    """

    result = parse_sbc_markdown(sample)
    print("Parsed SBC:")
    for key, value in result.items():
        print(f"  {key}: {value}")
