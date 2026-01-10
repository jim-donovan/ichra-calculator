"""
SBC (Summary of Benefits and Coverage) Markdown Parser

Uses Claude to intelligently extract plan details from pre-transformed SBC markdown files.

This parser is designed to be a WIZARD at extracting data from ANY SBC format:
- Standard CMS SBC format
- Multi-tier network plans (Tier 1/2/3, Preferred/Enhanced/Standard)
- Schedule of Benefits (SOB) documents
- Various carrier-specific formats (IBC, Kaiser, BCBS, Aetna, Cigna, United, etc.)
- OCR artifacts and formatting variations
"""

import os
import json
import re
import time
import logging
from typing import Optional, Dict, Any, List, Tuple

try:
    import streamlit as st
    HAS_STREAMLIT = True
except ImportError:
    HAS_STREAMLIT = False

from anthropic import Anthropic

# Configure logging
logger = logging.getLogger(__name__)


def _log_api_call(
    model: str,
    input_tokens: int,
    output_tokens: int,
    duration_ms: float,
    success: bool,
    error: Optional[str] = None,
    content_length: int = 0
) -> None:
    """Log API call details in a structured format."""
    log_data = {
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "duration_ms": round(duration_ms, 2),
        "tokens_per_sec": round(output_tokens / (duration_ms / 1000), 1) if duration_ms > 0 else 0,
        "content_length": content_length,
        "success": success,
    }

    if error:
        log_data["error"] = error

    # Calculate approximate cost (Haiku: $0.25/1M input, $1.25/1M output)
    input_cost = (input_tokens / 1_000_000) * 0.25
    output_cost = (output_tokens / 1_000_000) * 1.25
    log_data["cost_usd"] = round(input_cost + output_cost, 6)

    if success:
        logger.info(
            f"[Haiku API] ✓ {input_tokens:,} in → {output_tokens:,} out | "
            f"{duration_ms:.0f}ms | ${log_data['cost_usd']:.6f}"
        )
    else:
        logger.error(f"[Haiku API] ✗ {error} | {duration_ms:.0f}ms")

    # Also print to console for visibility during development
    if success:
        print(
            f"[SBC Parser] Haiku API: {input_tokens:,} in → {output_tokens:,} out | "
            f"{duration_ms:.0f}ms ({log_data['tokens_per_sec']:.0f} tok/s) | "
            f"${log_data['cost_usd']:.6f}"
        )
    else:
        print(f"[SBC Parser] Haiku API ERROR: {error} | {duration_ms:.0f}ms")


def _get_api_key() -> Optional[str]:
    """Get Anthropic API key from environment, .env file, or Streamlit secrets."""
    # Try environment variable first
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if api_key:
        return api_key

    # Try loading from .env file
    try:
        from dotenv import load_dotenv
        load_dotenv()
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if api_key:
            return api_key
    except ImportError:
        pass

    # Try Streamlit secrets
    if HAS_STREAMLIT and hasattr(st, 'secrets'):
        # Try nested format (anthropic.api_key)
        if 'anthropic' in st.secrets and 'api_key' in st.secrets['anthropic']:
            return st.secrets['anthropic']['api_key']
        # Try top-level ANTHROPIC_API_KEY
        if 'ANTHROPIC_API_KEY' in st.secrets:
            return st.secrets['ANTHROPIC_API_KEY']

    return None


# =============================================================================
# MASTER EXTRACTION PROMPT - The "Wizard" prompt
# =============================================================================

SYSTEM_PROMPT = """You are an EXPERT health insurance SBC (Summary of Benefits and Coverage) data extractor. Your job is to extract PRECISE numeric values from ANY SBC format with 100% accuracy.

## YOUR MISSION
Extract the EXACT dollar amounts and percentages from the document. Do NOT guess. Do NOT use defaults. Only extract values that are EXPLICITLY stated in the document.

## CRITICAL RULES

### Rule 1: ALWAYS Use Tier 1 / Preferred / In-Network Values
SBCs often have multiple tiers. ALWAYS extract from the BEST/CHEAPEST tier:
- "Tier 1", "Tier 1 - Preferred", "Preferred" = USE THIS
- "Tier 2", "Enhanced" = IGNORE
- "Tier 3", "Standard" = IGNORE
- "Out-of-Network" = IGNORE

### Rule 2: Pattern Recognition for Copays
Look for these EXACT patterns and extract the NUMBER:

**Primary Care / PCP:**
- "$40/Visit" → pcp_copay = 40
- "$40 no deductible" → pcp_copay = 40
- "$40/Visit. Deductible does not apply" → pcp_copay = 40
- "No charge" → pcp_copay = 0

**Specialist:**
- "$90/Visit" → specialist_copay = 90
- "$90 no deductible" → specialist_copay = 90

**Emergency Room:**
- "$950/Visit" → er_copay = 950
- "$250/Visit. Deductible does not apply" → er_copay = 250
- "Subject to deductible and $250" → er_copay = 250 (but note: deductible applies)

**Generic Rx:**
- "$30/Fill" → generic_rx_copay = 30
- "$10 no deductible" → generic_rx_copay = 10
- "Retail: $30/Fill" → generic_rx_copay = 30

**Preferred Brand Rx:**
- "$125/Fill" → preferred_rx_copay = 125
- "$60 after deductible" → preferred_rx_copay = 60

**Specialty Rx:**
- "50% coinsurance" → specialty_rx_copay = null, note coinsurance in notes
- "$500/Fill" → specialty_rx_copay = 500
- "50% up to $1,000" → specialty_rx_copay = null (it's coinsurance, not a copay)

### Rule 3: Multi-Tier Document Formats
Documents may have benefits listed like this:

```
**In-Network Tier 1 - Preferred (You will pay the least)** - **Primary care visit**: $40/Visit.
**In-Network Tier 2 - Enhanced** - **Primary care visit**: $70/Visit.
**In-Network Tier 3 - Standard** - **Primary care visit**: $80/Visit.
```

→ Extract from Tier 1 line: pcp_copay = 40

Or like this:
```
**Tier 1 - Preferred** - **Primary Care Physician (PCP)**: $40 no deductible
**Tier 2 - Enhanced** - **Primary Care Physician (PCP)**: $70 no deductible
```

→ Extract from Tier 1 line: pcp_copay = 40

### Rule 4: Section Headers Matter
SBCs group services under headers. The ER copay is often under:
- "If you need immediate medical attention"
- "Emergency Services"
- "Emergency Room"

Look for "Emergency room care" or "Emergency Room" in that section, then find the Tier 1 amount.

### Rule 5: Rx Drug Sections
Drug copays are usually under:
- "If you need drugs to treat your illness or condition"
- "Prescription Drugs"
- "Drug Benefits"

Drug tiers in SBCs:
- "Tier 1" or "Generic" or "Low-Cost Generic" → generic_rx_copay
- "Tier 2" or "Generic Drugs" (NOT Low-Cost) → also maps to generic_rx_copay if lower tier not present
- "Tier 3" or "Preferred Brand" → preferred_rx_copay
- "Tier 4" or "Non-Preferred" → can note in notes field
- "Tier 5" or "Specialty" → specialty_rx_copay (often coinsurance)

### Rule 6: Coinsurance vs Copay
- Copay = flat dollar amount ("$40/Visit") → extract as copay
- Coinsurance = percentage ("20% coinsurance", "20% after deductible") → copay should be null

If a service uses coinsurance instead of copay, set that copay field to null.
Set coinsurance_pct to the most common coinsurance percentage mentioned (often for hospital/surgery services).

### Rule 7: Deductibles and OOP Max
Look for these patterns:
- "overall deductible" or "What is the overall deductible?"
- "$1,500 person / $3,000 family" or "$1,500 individual / $3,000 family"
- "out-of-pocket limit" or "out-of-pocket maximum"
- "$9,200 person / $18,400 family"

For multi-tier plans, use Tier 1 deductible unless it says "$0" (then note in notes).

### Rule 8: Plan Metadata
- **plan_name**: Full plan name from header (e.g., "Independence Keystone HMO Silver Proactive Value")
- **carrier**: Insurance company (Independence Blue Cross, Kaiser, Aetna, etc.)
- **plan_type**: HMO, PPO, EPO, or POS (look in plan name or "Plan Type:" field)
- **metal_tier**: Bronze, Silver, Gold, Platinum (look in plan name)
- **hsa_eligible**: true ONLY if "HDHP" or "HSA" appears in plan name

### Rule 9: When Values Are Missing
If you cannot find a value explicitly stated in the document:
- Set it to null
- Do NOT guess or use typical values
- Do NOT use defaults like $25 or $50

### Rule 10: Notes Field
Use the notes field to capture important context:
- Multi-tier structure details
- If ER requires deductible
- If drugs have a separate deductible
- Any unusual plan features

## OUTPUT FORMAT
Return ONLY a valid JSON object. No markdown code blocks. No explanations. Just the JSON.

Example output:
{
    "plan_name": "Independence Keystone HMO Silver Proactive Value",
    "carrier": "Independence Blue Cross",
    "plan_type": "HMO",
    "metal_tier": "Silver",
    "hsa_eligible": false,
    "individual_deductible": 1500,
    "family_deductible": 3000,
    "individual_oop_max": 9200,
    "family_oop_max": 18400,
    "coinsurance_pct": 20,
    "pcp_copay": 40,
    "specialist_copay": 90,
    "er_copay": 950,
    "generic_rx_copay": 30,
    "preferred_rx_copay": 125,
    "specialty_rx_copay": null,
    "notes": "Multi-tier network (Tier 1/2/3). Specialty Rx is 50% coinsurance up to $1,000/fill. Rx has separate $500 deductible."
}"""


# Schema description for the user prompt
EXTRACTION_SCHEMA = {
    "plan_name": "Full plan name from the document header",
    "carrier": "Insurance carrier/issuer (e.g., 'Independence Blue Cross', 'Kaiser Permanente')",
    "plan_type": "HMO, PPO, EPO, or POS",
    "metal_tier": "Bronze, Silver, Gold, Platinum, or null",
    "hsa_eligible": "true only if HDHP/HSA in plan name, otherwise false",
    "individual_deductible": "Individual in-network deductible (Tier 1 if multi-tier)",
    "family_deductible": "Family in-network deductible",
    "individual_oop_max": "Individual in-network out-of-pocket maximum",
    "family_oop_max": "Family in-network out-of-pocket maximum",
    "coinsurance_pct": "Default coinsurance % member pays (null if plan uses copays)",
    "pcp_copay": "Primary care visit copay in dollars (Tier 1), null if coinsurance",
    "specialist_copay": "Specialist visit copay in dollars (Tier 1), null if coinsurance",
    "er_copay": "Emergency room copay in dollars (Tier 1), null if coinsurance",
    "generic_rx_copay": "Generic drug copay in dollars, null if coinsurance",
    "preferred_rx_copay": "Preferred brand drug copay in dollars, null if coinsurance",
    "specialty_rx_copay": "Specialty drug copay in dollars, null if coinsurance",
    "notes": "Important context about plan structure, tier details, separate Rx deductible, etc.",
}


def _preprocess_content(content: str) -> str:
    """
    Preprocess SBC content to improve extraction accuracy.

    - Removes OCR quality evaluation sections
    - Normalizes formatting
    - Truncates if needed while preserving key sections
    """
    # Remove quality evaluation report section (added by OCR tool, not part of SBC)
    quality_markers = [
        "QUALITY EVALUATION REPORT",
        "📋 QUALITY EVALUATION",
        "EVALUATOR COMPARISON",
        "DEBUG INFORMATION",
    ]
    for marker in quality_markers:
        idx = content.find(marker)
        if idx > 0:
            content = content[:idx].strip()
            break

    # If still very long, intelligently truncate
    # Keep: first 8000 chars (plan info, deductibles, office visits)
    # + look for key sections
    if len(content) > 20000:
        # Keep beginning (has plan name, deductibles, Q&A, office visits)
        result = content[:8000]

        # Find and append key sections
        sections_to_find = [
            ("immediate medical attention", 2000),  # ER section
            ("need drugs", 3000),  # Rx section
            ("prescription drug", 3000),  # Alternative Rx section header
            ("emergency room", 1500),  # Direct ER mention
        ]

        for section_marker, chars_to_grab in sections_to_find:
            idx = content.lower().find(section_marker)
            if idx > 8000:  # Only append if not already in the kept portion
                section_content = content[idx:idx + chars_to_grab]
                if section_content not in result:
                    result += f"\n\n[...section: {section_marker}...]\n" + section_content

        content = result + "\n\n[Content truncated for processing...]"

    return content


def _extract_with_ai(content: str) -> Dict[str, Any]:
    """Use Claude to extract plan details with wizard-level accuracy."""
    api_key = _get_api_key()
    if not api_key:
        raise ValueError("No Anthropic API key found. Set ANTHROPIC_API_KEY environment variable or Streamlit secrets.")

    client = Anthropic(api_key=api_key)
    original_content_length = len(content)

    # Preprocess content
    content = _preprocess_content(content)

    # Build the extraction prompt with explicit field descriptions
    schema_description = "\n".join([f"- **{k}**: {v}" for k, v in EXTRACTION_SCHEMA.items()])

    user_prompt = f"""Extract plan details from this SBC document. Return JSON with these fields:

{schema_description}

IMPORTANT REMINDERS:
1. Use Tier 1 / Preferred values for all copays
2. Look for "Emergency room care" in the "immediate medical attention" section
3. Extract EXACT dollar amounts - do NOT guess
4. Set to null if value not found (don't use defaults)
5. Generic Rx might be listed as "Tier 1" or "Tier 2" in Rx drug tiers

---
SBC DOCUMENT:
---
{content}
---

Return ONLY the JSON object, no markdown formatting."""

    model = "claude-3-5-haiku-20241022"
    start_time = time.time()

    try:
        response = client.messages.create(
            model=model,
            max_tokens=1500,
            temperature=0,  # Deterministic extraction
            messages=[
                {"role": "user", "content": user_prompt}
            ],
            system=SYSTEM_PROMPT,
        )

        duration_ms = (time.time() - start_time) * 1000

        # Log successful API call
        _log_api_call(
            model=model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            duration_ms=duration_ms,
            success=True,
            content_length=original_content_length
        )

        # Parse the response
        response_text = response.content[0].text.strip()

        # Clean up response if it has markdown code blocks
        if response_text.startswith("```"):
            response_text = re.sub(r'^```json?\n?', '', response_text)
            response_text = re.sub(r'\n?```$', '', response_text)

        result = json.loads(response_text)

        # Ensure all expected keys exist
        for key in EXTRACTION_SCHEMA.keys():
            if key not in result:
                result[key] = None

        # Post-processing validation
        result = _validate_and_clean(result)

        return result

    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        _log_api_call(
            model=model,
            input_tokens=0,
            output_tokens=0,
            duration_ms=duration_ms,
            success=False,
            error=str(e),
            content_length=original_content_length
        )
        raise


def _validate_and_clean(result: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and clean extracted values."""
    # Ensure numeric fields are numbers or None
    numeric_fields = [
        'individual_deductible', 'family_deductible',
        'individual_oop_max', 'family_oop_max',
        'coinsurance_pct',
        'pcp_copay', 'specialist_copay', 'er_copay',
        'generic_rx_copay', 'preferred_rx_copay', 'specialty_rx_copay'
    ]

    for field in numeric_fields:
        if field in result and result[field] is not None:
            try:
                # Handle string values like "$40" or "40"
                val = result[field]
                if isinstance(val, str):
                    val = val.replace('$', '').replace(',', '').strip()
                    if val.lower() in ['null', 'none', 'n/a', '']:
                        result[field] = None
                    else:
                        result[field] = float(val)
                elif isinstance(val, (int, float)):
                    result[field] = float(val)
                else:
                    result[field] = None
            except (ValueError, TypeError):
                result[field] = None

    # Ensure boolean field
    if 'hsa_eligible' in result:
        result['hsa_eligible'] = bool(result.get('hsa_eligible', False))

    # Validate plan_type
    valid_plan_types = ['HMO', 'PPO', 'EPO', 'POS']
    if result.get('plan_type') and result['plan_type'].upper() in valid_plan_types:
        result['plan_type'] = result['plan_type'].upper()
    elif result.get('plan_type'):
        # Try to extract from string
        for pt in valid_plan_types:
            if pt in str(result['plan_type']).upper():
                result['plan_type'] = pt
                break

    # Validate metal_tier
    valid_tiers = ['Bronze', 'Silver', 'Gold', 'Platinum', 'Catastrophic']
    if result.get('metal_tier'):
        tier = result['metal_tier'].capitalize()
        if tier in valid_tiers:
            result['metal_tier'] = tier
        else:
            result['metal_tier'] = None

    return result


def _extract_with_regex(content: str) -> Dict[str, Any]:
    """
    Enhanced regex-based extraction fallback.
    Works offline but less accurate than AI extraction.
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
        "notes": "Extracted with regex fallback - verify values manually",
    }

    # Preprocess
    content = _preprocess_content(content)

    # =========================================================================
    # Plan Name Extraction
    # =========================================================================
    # Try multiple patterns
    patterns = [
        r'#+\s*(?:Summary of Benefits.*?:\s*)?(.+?(?:HMO|PPO|EPO|POS).+?)(?:\n|$)',
        r'##\s*(.+?(?:HMO|PPO|EPO|POS).+?)(?:\n|$)',
        r'\*\*Plan(?:\s*Name)?:\*\*\s*(.+?)(?:\n|$)',
        r'(?:Coverage for|Plan Name).*?:\s*(.+?)(?:\n|$)',
    ]
    for pattern in patterns:
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            # Clean up the name
            name = re.sub(r'\s+', ' ', name)
            if len(name) > 10 and len(name) < 150:
                result["plan_name"] = name
                break

    # =========================================================================
    # Extract metadata from plan name
    # =========================================================================
    if result["plan_name"]:
        name = result["plan_name"]
        name_lower = name.lower()
        name_upper = name.upper()

        # Plan type
        for pt in ["PPO", "HMO", "EPO", "POS"]:
            if pt in name_upper:
                result["plan_type"] = pt
                break

        # Metal tier
        for tier in ["platinum", "gold", "silver", "bronze", "catastrophic"]:
            if tier in name_lower:
                result["metal_tier"] = tier.capitalize()
                break

        # HSA
        result["hsa_eligible"] = "HDHP" in name_upper or "HSA" in name_upper

        # Carrier detection
        carriers = {
            "Independence Blue Cross": ["independence", "keystone", "ibx"],
            "Kaiser Permanente": ["kaiser", "kp "],
            "Blue Cross Blue Shield": ["bcbs", "blue cross", "anthem", "blue shield"],
            "Aetna": ["aetna"],
            "Cigna": ["cigna"],
            "UnitedHealthcare": ["united", "uhc", "unitedhealthcare"],
            "Humana": ["humana"],
            "Molina": ["molina"],
            "Oscar": ["oscar"],
            "Ambetter": ["ambetter"],
        }
        for carrier, keywords in carriers.items():
            if any(kw in name_lower for kw in keywords):
                result["carrier"] = carrier
                break

        # Also check full content for carrier
        if not result["carrier"]:
            content_lower = content.lower()
            for carrier, keywords in carriers.items():
                if any(kw in content_lower[:2000] for kw in keywords):
                    result["carrier"] = carrier
                    break

    # =========================================================================
    # Deductibles
    # =========================================================================
    # Pattern: "$1,500 person / $3,000 family" or "For Tier 1: $1,500 person / $3,000 family"
    ded_patterns = [
        r'(?:overall\s+)?deductible.*?(?:Tier\s*1[^$]*?)?\$([0-9,]+)\s*(?:person|individual).*?\$([0-9,]+)\s*family',
        r'deductible.*?\$([0-9,]+)\s*/\s*\$([0-9,]+)',
        r'Individual/Family.*?\$([0-9,]+)/\$([0-9,]+)',
    ]
    for pattern in ded_patterns:
        match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
        if match:
            result["individual_deductible"] = float(match.group(1).replace(",", ""))
            result["family_deductible"] = float(match.group(2).replace(",", ""))
            break

    # =========================================================================
    # Out-of-Pocket Maximum
    # =========================================================================
    oop_patterns = [
        r'out-of-pocket\s+(?:limit|max).*?\$([0-9,]+)\s*(?:person|individual).*?\$([0-9,]+)\s*family',
        r'out-of-pocket.*?\$([0-9,]+)\s*/\s*\$([0-9,]+)',
    ]
    for pattern in oop_patterns:
        match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
        if match:
            result["individual_oop_max"] = float(match.group(1).replace(",", ""))
            result["family_oop_max"] = float(match.group(2).replace(",", ""))
            break

    # =========================================================================
    # Copays - Using Tier 1 / Preferred values
    # =========================================================================

    def extract_tier1_copay(service_patterns: List[str], content: str) -> Optional[float]:
        """Extract copay from Tier 1/Preferred line for given service patterns."""
        for service_pattern in service_patterns:
            # Try Tier 1 specific patterns first
            tier1_patterns = [
                rf'Tier\s*1[^$\n]*{service_pattern}[^$\n]*\$(\d+)',
                rf'{service_pattern}[^$\n]*Tier\s*1[^$\n]*\$(\d+)',
                rf'\*\*In-Network Tier 1[^*]*\*\*[^$]*{service_pattern}[^$]*\$(\d+)',
                rf'Tier 1 - Preferred[^$]*{service_pattern}[^$]*\$(\d+)',
            ]
            for pattern in tier1_patterns:
                match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
                if match:
                    return float(match.group(1))

            # Fallback: first dollar amount near service name
            fallback = re.search(rf'{service_pattern}[^$\n]{{0,100}}\$(\d+)', content, re.IGNORECASE)
            if fallback:
                return float(fallback.group(1))

        return None

    # PCP
    result["pcp_copay"] = extract_tier1_copay(
        ["primary care", "pcp", "office visit"],
        content
    )

    # Specialist
    result["specialist_copay"] = extract_tier1_copay(
        ["specialist"],
        content
    )

    # Emergency Room
    result["er_copay"] = extract_tier1_copay(
        ["emergency room", "emergency care", "er visit"],
        content
    )

    # Generic Rx
    result["generic_rx_copay"] = extract_tier1_copay(
        ["generic drug", "generic rx", "tier 1.*drug", "tier 2 generic"],
        content
    )

    # Preferred Brand Rx
    result["preferred_rx_copay"] = extract_tier1_copay(
        ["preferred brand", "tier 3.*brand", "brand drug"],
        content
    )

    # Specialty Rx - often coinsurance, so may be None
    specialty_match = re.search(r'specialty.*?\$(\d+)', content, re.IGNORECASE)
    if specialty_match:
        result["specialty_rx_copay"] = float(specialty_match.group(1))

    # =========================================================================
    # Coinsurance
    # =========================================================================
    coins_match = re.search(r'(\d+)%\s*(?:coinsurance|after\s+deductible)', content, re.IGNORECASE)
    if coins_match:
        result["coinsurance_pct"] = int(coins_match.group(1))

    return result


def parse_sbc_markdown(content: str, use_ai: bool = True) -> Dict[str, Any]:
    """
    Extract plan fields from transformed SBC markdown.

    Args:
        content: Raw markdown content from SBC transformation tool
        use_ai: If True, use Claude for extraction. If False, use regex fallback.

    Returns:
        Dict with extracted plan fields matching CurrentEmployerPlan structure
    """
    if use_ai:
        try:
            return _extract_with_ai(content)
        except Exception as e:
            print(f"AI extraction failed: {e}, falling back to regex")
            return _extract_with_regex(content)
    else:
        return _extract_with_regex(content)


# =============================================================================
# CLI / TESTING
# =============================================================================

if __name__ == "__main__":
    import sys

    # Load .env file if present (for CLI testing)
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    if len(sys.argv) > 1:
        filepath = sys.argv[1]
        use_ai = "--no-ai" not in sys.argv

        with open(filepath, 'r') as f:
            content = f.read()

        print(f"Parsing: {filepath}")
        print(f"Mode: {'AI-powered (wizard mode)' if use_ai else 'Regex fallback'}")
        print("-" * 60)

        result = parse_sbc_markdown(content, use_ai=use_ai)

        print("\nExtracted Values:")
        print("-" * 40)
        for key, value in result.items():
            if value is not None:
                print(f"  {key}: {value}")

        print("\n" + "-" * 40)
        print("Null/Missing fields:")
        for key, value in result.items():
            if value is None:
                print(f"  {key}: null")
    else:
        print("SBC Parser - Wizard Mode")
        print("=" * 60)
        print("Usage: python sbc_parser.py <sbc_markdown_file> [--no-ai]")
        print()
        print("Options:")
        print("  --no-ai    Use regex fallback instead of AI extraction")
        print()
        print("Examples:")
        print("  python sbc_parser.py path/to/sbc.md")
        print("  python sbc_parser.py path/to/sbc.md --no-ai")
