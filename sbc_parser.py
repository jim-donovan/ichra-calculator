"""
SBC (Summary of Benefits and Coverage) Markdown Parser

Parses pre-transformed SBC markdown files to extract plan details
for auto-populating the Plan Comparison form.

DESIGN: Key-based extraction - find standardized SBC questions/labels,
then parse whatever answer format follows. This handles variations in
OCR output and different SBC layouts.
"""

import re
from typing import Optional, Dict, Any, List, Tuple


def parse_sbc_markdown(content: str) -> Dict[str, Any]:
    """
    Extract plan fields from transformed SBC markdown.

    Args:
        content: Raw markdown content from SBC transformation tool

    Returns:
        Dict with extracted plan fields matching CurrentEmployerPlan structure
    """
    result = {
        "plan_name": None,
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
        # SBC scenario costs
        "sbc_having_baby_cost": None,
        "sbc_diabetes_cost": None,
        "sbc_fracture_cost": None,
        # Additional benefits
        "mental_health_outpatient": None,
        "imaging_cost": None,
        "inpatient_cost": None,
    }

    # Extract plan name from various formats
    result["plan_name"] = extract_plan_name(content)

    # Detect carrier, metal tier, HSA from plan name
    if result["plan_name"]:
        result["carrier"] = detect_carrier(result["plan_name"])
        result["metal_tier"] = detect_metal_tier(result["plan_name"])
        result["hsa_eligible"] = detect_hsa_eligible(result["plan_name"])

    # Extract plan type
    result["plan_type"] = extract_plan_type(content, result["plan_name"])

    # Extract deductibles using key-based search
    deductibles = extract_by_key(content, DEDUCTIBLE_KEYS)
    ind_ded, fam_ded = parse_individual_family_amounts(deductibles)
    result["individual_deductible"] = ind_ded
    result["family_deductible"] = fam_ded

    # Extract OOP limits using key-based search
    oop_text = extract_by_key(content, OOP_KEYS)
    ind_oop, fam_oop = parse_individual_family_amounts(oop_text)
    result["individual_oop_max"] = ind_oop
    result["family_oop_max"] = fam_oop

    # Extract copays and coinsurance from service rows
    copays = extract_service_costs(content)
    result.update(copays)

    # Extract coinsurance percentage
    result["coinsurance_pct"] = extract_coinsurance_pct(content)

    # SBC scenario costs
    sbc_scenarios = extract_sbc_scenarios(content)
    result.update(sbc_scenarios)

    return result


# =============================================================================
# KEY DEFINITIONS - Standard SBC questions/labels to search for
# =============================================================================

DEDUCTIBLE_KEYS = [
    "what is the overall deductible",
    "overall deductible",
    "annual deductible",
    "deductible",
]

OOP_KEYS = [
    "what is the out-of-pocket limit",
    "out-of-pocket limit",
    "out-of-pocket maximum",
    "oop limit",
    "oop max",
    "maximum out-of-pocket",
]

SERVICE_KEYS = {
    "pcp_copay": [
        "primary care visit to treat an injury or illness",
        "primary care visit",
        "pcp visit",
        "office visit",
    ],
    "specialist_copay": [
        "specialist visit",
        "specialist",
    ],
    "er_copay": [
        "emergency room care",
        "emergency room services",
        "emergency room",
        "er services",
    ],
    "generic_rx_copay": [
        "generic drugs",
        "generic drug",
        "tier 1 drugs",
    ],
    "preferred_rx_copay": [
        "preferred brand drugs",
        "preferred brand",
        "tier 2 drugs",
        "brand drugs",
    ],
    "specialty_rx_copay": [
        "specialty drugs",
        "specialty drug",
        "tier 4 drugs",
    ],
    "mental_health_outpatient": [
        "mental health outpatient",
        "mental/behavioral health outpatient",
        "behavioral health outpatient",
        "outpatient mental health",
    ],
    "imaging_cost": [
        "imaging (ct/pet scans, mris)",
        "imaging",
        "ct/pet scans",
        "mri",
    ],
    "inpatient_cost": [
        "facility fee (e.g., hospital room)",
        "hospital stay",
        "inpatient hospital",
        "inpatient facility",
    ],
}


# =============================================================================
# KEY-BASED EXTRACTION
# =============================================================================

def extract_by_key(content: str, keys: List[str]) -> Optional[str]:
    """
    Find a key in the content and extract the answer/value that follows.

    Handles various formats:
    - "**Key**: Value"
    - "Key: Value"
    - "**Answer** - **Key**: Value"
    - Table row formats
    """
    content_lower = content.lower()

    for key in keys:
        key_lower = key.lower()

        # Find the key position
        pos = content_lower.find(key_lower)
        if pos == -1:
            continue

        # Extract text after the key (up to next section or 500 chars)
        start = pos + len(key_lower)

        # Find the end - look for next question, section break, or limit
        end_markers = [
            content_lower.find("**why this matters", start),
            content_lower.find("\n##", start),
            content_lower.find("\n---", start),
            content_lower.find("**answer**", start),
            start + 500,
        ]
        end_markers = [e for e in end_markers if e > start]
        end = min(end_markers) if end_markers else start + 500

        # Get the answer text
        answer = content[start:end].strip()

        # Clean up markdown formatting
        answer = re.sub(r'^\*?\*?:?\s*', '', answer)  # Remove leading **:
        answer = re.sub(r'\*\*', '', answer)  # Remove bold markers

        if answer:
            return answer

    return None


def extract_service_cost(content: str, keys: List[str]) -> Optional[str]:
    """
    Extract cost for a specific service (copay, coinsurance, etc.)

    Handles formats:
    - "$40/Visit"
    - "$40 copay"
    - "25% coinsurance"
    - "No charge"
    - "$250/Visit. Deductible does not apply."

    Prioritizes In-Network Tier 1 when multiple tiers exist.
    """
    content_lower = content.lower()

    for key in keys:
        key_lower = key.lower()
        pos = content_lower.find(key_lower)
        if pos == -1:
            continue

        # Get surrounding context (look ahead for the cost)
        context_start = max(0, pos - 50)
        context_end = min(len(content), pos + 300)
        context = content[context_start:context_end]

        # Look for In-Network Tier 1 cost first (most preferred)
        tier1_match = re.search(
            r'(?:In-Network Tier 1|Tier 1|Preferred).*?(?:\$([0-9,]+)(?:/\w+)?|(\d+)%\s*coinsurance|No charge)',
            context,
            re.IGNORECASE | re.DOTALL
        )
        if tier1_match:
            return tier1_match.group(0)

        # Look for any In-Network cost
        in_network_match = re.search(
            r'(?:In-Network|Participating).*?(?:\$([0-9,]+)(?:/\w+)?|(\d+)%\s*coinsurance|No charge)',
            context,
            re.IGNORECASE | re.DOTALL
        )
        if in_network_match:
            return in_network_match.group(0)

        # Fallback: look for any cost pattern after the key
        cost_match = re.search(
            r'(?:\$([0-9,]+)(?:/\w+|\s*copay)?|(\d+)%\s*coinsurance|No charge)',
            context[pos - context_start:],
            re.IGNORECASE
        )
        if cost_match:
            return cost_match.group(0)

    return None


def extract_service_costs(content: str) -> Dict[str, Optional[float]]:
    """Extract costs for all services."""
    result = {}

    for field, keys in SERVICE_KEYS.items():
        cost_text = extract_service_cost(content, keys)
        if cost_text:
            # Parse the cost value
            amount = parse_cost_amount(cost_text)
            result[field] = amount
        else:
            result[field] = None

    return result


# =============================================================================
# AMOUNT PARSING
# =============================================================================

def parse_individual_family_amounts(text: Optional[str]) -> Tuple[Optional[float], Optional[float]]:
    """
    Parse individual and family amounts from text.

    Handles formats:
    - "$2,850 Self only enrollment. $5,700 for an entire Family"
    - "$6,000 person / $12,000 family"
    - "$9,200 individual / $18,400 family"
    - "For Tier 1: $0 person / $0 family"
    - "$9,200 person / $18,400 family"
    """
    if not text:
        return None, None

    individual = None
    family = None

    # Pattern 1: "$X person / $Y family" or "$X individual / $Y family"
    pattern1 = re.search(
        r'\$([0-9,]+)\s*(?:person|individual|self[- ]only).*?\$([0-9,]+)\s*(?:family|for.*family)',
        text,
        re.IGNORECASE
    )
    if pattern1:
        individual = float(pattern1.group(1).replace(",", ""))
        family = float(pattern1.group(2).replace(",", ""))
        return individual, family

    # Pattern 2: Look for individual keywords
    ind_match = re.search(
        r'\$([0-9,]+)\s*(?:person|individual|self[- ]only|per person)',
        text,
        re.IGNORECASE
    )
    if ind_match:
        individual = float(ind_match.group(1).replace(",", ""))

    # Pattern 3: Look for family keywords
    fam_match = re.search(
        r'\$([0-9,]+)\s*(?:family|per family|for.*family|entire family)',
        text,
        re.IGNORECASE
    )
    if fam_match:
        family = float(fam_match.group(1).replace(",", ""))

    # Pattern 4: If we found amounts but no keywords, try positional
    if individual is None and family is None:
        amounts = re.findall(r'\$([0-9,]+)', text)
        if len(amounts) >= 2:
            # Assume first is individual, second is family
            individual = float(amounts[0].replace(",", ""))
            family = float(amounts[1].replace(",", ""))
        elif len(amounts) == 1:
            individual = float(amounts[0].replace(",", ""))

    return individual, family


def parse_cost_amount(text: str) -> Optional[float]:
    """
    Parse a single cost amount from text.

    Returns:
        Float amount for copays, or None for coinsurance/no charge
        (coinsurance plans don't have flat copays)
    """
    if not text:
        return None

    text_lower = text.lower()

    # "No charge" = $0
    if "no charge" in text_lower:
        return 0.0

    # Coinsurance = no flat copay (return None, not the percentage)
    if "coinsurance" in text_lower:
        return None

    # Extract dollar amount
    match = re.search(r'\$([0-9,]+)', text)
    if match:
        return float(match.group(1).replace(",", ""))

    return None


def extract_coinsurance_pct(content: str) -> Optional[int]:
    """
    Extract the plan's general coinsurance percentage.

    Look for coinsurance in primary care or specialist rows,
    or a general "default coinsurance" statement.
    """
    # Look for coinsurance percentage in service descriptions
    patterns = [
        r'primary care.*?(\d+)%\s*coinsurance',
        r'specialist.*?(\d+)%\s*coinsurance',
        r'default coinsurance.*?(\d+)%',
        r'coinsurance.*?(\d+)%',
    ]

    for pattern in patterns:
        match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
        if match:
            return int(match.group(1))

    # Check if plan uses copays (if we found copay amounts, likely 20% default)
    if re.search(r'\$\d+/Visit', content):
        return 20  # Common default for copay-based plans

    return None


# =============================================================================
# PLAN IDENTIFICATION
# =============================================================================

def extract_plan_name(content: str) -> Optional[str]:
    """
    Extract plan name from various formats.

    Formats:
    - "## Plan Name Here" (H2 header)
    - "# Plan Name Here" (H1 header)
    - "**Plan:** Plan Name"
    - "Plan Name" in first significant line
    """
    # Try H2 header (common in OCR output)
    h2_match = re.search(r'^## (.+?)$', content, re.MULTILINE)
    if h2_match:
        name = h2_match.group(1).strip()
        # Skip generic headers
        if name.lower() not in ["summary of benefits", "important questions", "what you will pay"]:
            return name

    # Try H1 header
    h1_match = re.search(r'^# (.+?)$', content, re.MULTILINE)
    if h1_match:
        name = h1_match.group(1).strip()
        if "summary of benefits" not in name.lower():
            return name

    # Try **Plan:** format
    plan_match = re.search(r'\*\*Plan:\*\*\s*(.+?)(?:\s*\n|$)', content)
    if plan_match:
        return plan_match.group(1).strip()

    # Try to find plan name near the top of document
    lines = content.split('\n')[:20]
    for line in lines:
        # Look for lines that look like plan names (contain carrier/metal keywords)
        if any(kw in line.lower() for kw in ['hmo', 'ppo', 'epo', 'pos', 'bronze', 'silver', 'gold', 'platinum']):
            # Clean up the line
            clean = re.sub(r'^[#*\s]+', '', line).strip()
            clean = re.sub(r'\*+$', '', clean).strip()
            if len(clean) > 10:  # Must be substantial
                return clean

    return None


def extract_plan_type(content: str, plan_name: Optional[str] = None) -> Optional[str]:
    """Extract plan type (HMO, PPO, EPO, POS)."""
    # Check explicit Plan Type field
    match = re.search(r'\*\*Plan Type:\*\*\s*(\w+)', content)
    if match:
        plan_type_text = match.group(1).upper()
        for pt in ["PPO", "HMO", "EPO", "POS"]:
            if pt in plan_type_text:
                return pt

    # Check plan name
    if plan_name:
        plan_upper = plan_name.upper()
        for pt in ["PPO", "HMO", "EPO", "POS"]:
            if pt in plan_upper:
                return pt

    # Search content for plan type mentions
    for pt in ["PPO", "HMO", "EPO", "POS"]:
        if re.search(rf'\b{pt}\b', content, re.IGNORECASE):
            return pt

    return None


def detect_carrier(plan_name: str) -> Optional[str]:
    """Detect insurance carrier from plan name."""
    carriers = {
        "Independence Blue Cross": ["independence", "keystone", "ibx"],
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

    for tier in ["platinum", "gold", "silver", "bronze", "catastrophic"]:
        if tier in plan_lower:
            return tier.capitalize()

    return None


def detect_hsa_eligible(plan_name: str) -> bool:
    """Detect if plan is HSA-eligible (HDHP) from plan name."""
    plan_upper = plan_name.upper()
    return "HDHP" in plan_upper or "HSA" in plan_upper


# =============================================================================
# SBC SCENARIO EXTRACTION
# =============================================================================

def extract_sbc_scenarios(content: str) -> Dict[str, Optional[float]]:
    """
    Extract SBC scenario costs (Having a Baby, Managing Diabetes, Simple Fracture).

    These use standardized names: Peg (baby), Joe (diabetes), Mia (fracture)
    """
    result = {
        "sbc_having_baby_cost": None,
        "sbc_diabetes_cost": None,
        "sbc_fracture_cost": None,
    }

    # Having a Baby (Peg)
    baby_patterns = [
        r'total Peg would pay.*?\$([0-9,]+)',
        r'Having a Baby.*?total.*?\$([0-9,]+)',
        r'having a baby.*?you.*?pay.*?\$([0-9,]+)',
    ]
    for pattern in baby_patterns:
        match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
        if match:
            result["sbc_having_baby_cost"] = float(match.group(1).replace(",", ""))
            break

    # Managing Diabetes (Joe)
    diabetes_patterns = [
        r'total Joe would pay.*?\$([0-9,]+)',
        r'Managing.*?Diabetes.*?total.*?\$([0-9,]+)',
        r'diabetes.*?you.*?pay.*?\$([0-9,]+)',
    ]
    for pattern in diabetes_patterns:
        match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
        if match:
            result["sbc_diabetes_cost"] = float(match.group(1).replace(",", ""))
            break

    # Simple Fracture (Mia)
    fracture_patterns = [
        r'total Mia would pay.*?\$([0-9,]+)',
        r'Simple Fracture.*?total.*?\$([0-9,]+)',
        r'fracture.*?you.*?pay.*?\$([0-9,]+)',
    ]
    for pattern in fracture_patterns:
        match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
        if match:
            result["sbc_fracture_cost"] = float(match.group(1).replace(",", ""))
            break

    return result


# =============================================================================
# MAIN / TESTING
# =============================================================================

if __name__ == "__main__":
    import sys

    # Test with file if provided
    if len(sys.argv) > 1:
        with open(sys.argv[1], 'r') as f:
            content = f.read()
        result = parse_sbc_markdown(content)
        print("Parsed SBC:")
        for key, value in result.items():
            if value is not None:
                print(f"  {key}: {value}")
    else:
        # Test with sample formats
        samples = [
            # Format 1: OCR output with tiers
            """
            ## Independence Keystone HMO Silver Proactive

            **Coverage for:** Family | **Plan Type:** HMO

            **Answer** - **What is the overall deductible?**: For Tier 1: $0 person / $0 family; For Tier 2 & 3: $6,000 person / $12,000 family.
            **Answer** - **What is the out-of-pocket limit for this plan?**: For Participating providers $9,200 person / $18,400 family.

            **In-Network Tier 1 - Preferred (You will pay the least)** - Primary care visit: $40/Visit.
            **In-Network Tier 1 - Preferred (You will pay the least)** - Specialist visit: $90/Visit.
            **In-Network Tier 1 - Preferred (You will pay the least)** - Emergency room care: $950/Visit.
            **In-Network Tier 1 - Preferred (You will pay the least)** - Generic Drugs: $30/Fill.
            """,
            # Format 2: Kaiser HDHP
            """
            **Plan:** KAISER PERMANENTE Silver 70 HDHP HMO 2850/25%
            **Coverage for:** Individual / Family | **Plan Type:** Deductible HMO

            **Answers** - **What is the overall deductible?**: $2,850 Self only enrollment.
            $5,700 for an entire Family

            **Answers** - **What is the out-of-pocket limit for this plan?**: $7,500 Self only enrollment.
            $15,000 for an entire Family.

            Primary care visit to treat an injury or illness: 25% coinsurance
            Specialist visit: 25% coinsurance
            Emergency room care: 25% coinsurance
            """,
        ]

        for i, sample in enumerate(samples, 1):
            print(f"\n{'='*60}")
            print(f"Sample {i}")
            print('='*60)
            result = parse_sbc_markdown(sample)
            for key, value in result.items():
                if value is not None:
                    print(f"  {key}: {value}")
