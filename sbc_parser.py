"""
SBC (Summary of Benefits and Coverage) Markdown Parser

Uses Claude (haiku for speed/cost) to intelligently extract plan details
from pre-transformed SBC markdown files.

AI-powered extraction handles:
- Varying OCR output formats
- Tiered network structures
- Coinsurance vs copay plans
- Ambiguous or missing fields
"""

import os
import json
import re
import time
import logging
from typing import Optional, Dict, Any

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


# Schema for structured extraction
EXTRACTION_SCHEMA = {
    "plan_name": "The full plan name (e.g., 'Independence Keystone HMO Silver Proactive')",
    "carrier": "Insurance carrier/issuer name (e.g., 'Independence Blue Cross', 'Kaiser Permanente')",
    "plan_type": "Network type: HMO, PPO, EPO, or POS",
    "metal_tier": "Metal level: Bronze, Silver, Gold, Platinum, or Catastrophic (null if not ACA plan)",
    "hsa_eligible": "Boolean - is this an HSA-eligible HDHP?",
    "individual_deductible": "Individual in-network deductible in dollars (use the MOST COMMON tier if multi-tier)",
    "family_deductible": "Family in-network deductible in dollars",
    "individual_oop_max": "Individual in-network out-of-pocket maximum in dollars",
    "family_oop_max": "Family in-network out-of-pocket maximum in dollars",
    "coinsurance_pct": "Default coinsurance percentage the MEMBER pays (e.g., 20 for 20%). Null if plan uses copays instead.",
    "pcp_copay": "Primary care visit copay in dollars (null if coinsurance-based)",
    "specialist_copay": "Specialist visit copay in dollars (null if coinsurance-based)",
    "er_copay": "Emergency room copay in dollars (null if coinsurance-based)",
    "generic_rx_copay": "Generic drug copay in dollars (null if coinsurance-based)",
    "preferred_rx_copay": "Preferred brand drug copay in dollars (null if coinsurance-based)",
    "specialty_rx_copay": "Specialty drug copay in dollars (null if coinsurance-based)",
    "notes": "Any important notes about plan structure (e.g., 'Multi-tier network: Tier 1 has $0 deductible, Tier 2/3 have $6,000')",
}

SYSTEM_PROMPT = """You are an expert at extracting health insurance plan details from Summary of Benefits and Coverage (SBC) documents.

Extract the requested fields from the SBC markdown content. Follow these rules:

1. **Deductibles**: If the plan has multiple tiers (Tier 1, Tier 2, etc.), extract the MOST COMMON or PRIMARY tier's deductible. Note the tier structure in the "notes" field.

2. **Copays vs Coinsurance**:
   - If a service has a flat dollar copay (e.g., "$40/Visit"), extract that as the copay
   - If a service has coinsurance (e.g., "25% coinsurance"), leave the copay as null and set coinsurance_pct
   - Many plans use copays for office visits but coinsurance for other services - that's normal

3. **In-Network Only**: Always extract IN-NETWORK costs. Ignore out-of-network.

4. **Tier 1 Preferred**: For tiered networks, prefer Tier 1 / Preferred tier values for copays.

5. **HSA Eligibility**: Mark true only if plan explicitly says "HDHP", "HSA-eligible", or "HSA" in the name.

6. **Null vs Zero**:
   - $0 copay = 0 (the service is free)
   - No copay (coinsurance instead) = null
   - Missing/unknown = null

Return ONLY valid JSON matching the requested schema. No markdown, no explanation."""


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


def _extract_with_ai(content: str) -> Dict[str, Any]:
    """Use Claude to extract plan details."""
    api_key = _get_api_key()
    if not api_key:
        raise ValueError("No Anthropic API key found. Set ANTHROPIC_API_KEY environment variable or Streamlit secrets.")

    client = Anthropic(api_key=api_key)
    original_content_length = len(content)

    # Truncate content if too long (keep first 8000 chars - should cover key info)
    if len(content) > 10000:
        # Keep the important sections (beginning has plan name, Q&A, and service costs)
        content = content[:8000] + "\n\n[Content truncated...]"

    # Build the extraction prompt
    schema_description = "\n".join([f"- {k}: {v}" for k, v in EXTRACTION_SCHEMA.items()])

    user_prompt = f"""Extract the following fields from this SBC document:

{schema_description}

---
SBC CONTENT:
---
{content}
---

Return a JSON object with these exact keys. Use null for missing/unknown values."""

    model = "claude-3-5-haiku-20241022"
    start_time = time.time()

    try:
        response = client.messages.create(
            model=model,
            max_tokens=1024,
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


def _extract_with_regex(content: str) -> Dict[str, Any]:
    """Fallback regex-based extraction (less accurate but works offline)."""
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
        "notes": "Extracted with regex fallback - may be less accurate",
    }

    # Plan name from H2 header or **Plan:** line
    h2_match = re.search(r'^## (.+?)$', content, re.MULTILINE)
    if h2_match:
        name = h2_match.group(1).strip()
        if name.lower() not in ["summary of benefits", "important questions"]:
            result["plan_name"] = name

    if not result["plan_name"]:
        plan_match = re.search(r'\*\*Plan:\*\*\s*(.+?)(?:\s*\n|$)', content)
        if plan_match:
            result["plan_name"] = plan_match.group(1).strip()

    # Detect from plan name
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
            "Kaiser Permanente": ["kaiser", "kp"],
            "Blue Cross Blue Shield": ["bcbs", "blue cross", "anthem"],
            "Aetna": ["aetna"],
            "Cigna": ["cigna"],
            "UnitedHealthcare": ["united", "uhc"],
        }
        for carrier, keywords in carriers.items():
            if any(kw in name_lower for kw in keywords):
                result["carrier"] = carrier
                break

    # Extract dollar amounts with context
    # OOP limits
    oop_match = re.search(r'out-of-pocket limit.*?\$([0-9,]+)\s*(?:person|individual).*?\$([0-9,]+)\s*family',
                          content, re.IGNORECASE | re.DOTALL)
    if oop_match:
        result["individual_oop_max"] = float(oop_match.group(1).replace(",", ""))
        result["family_oop_max"] = float(oop_match.group(2).replace(",", ""))

    # Deductibles
    ded_match = re.search(r'overall deductible.*?\$([0-9,]+)\s*(?:person|individual).*?\$([0-9,]+)\s*family',
                          content, re.IGNORECASE | re.DOTALL)
    if ded_match:
        result["individual_deductible"] = float(ded_match.group(1).replace(",", ""))
        result["family_deductible"] = float(ded_match.group(2).replace(",", ""))

    # Copays - look for "$X/Visit" pattern
    pcp_match = re.search(r'primary care.*?\$(\d+)/Visit', content, re.IGNORECASE | re.DOTALL)
    if pcp_match:
        result["pcp_copay"] = float(pcp_match.group(1))

    specialist_match = re.search(r'specialist.*?\$(\d+)/Visit', content, re.IGNORECASE | re.DOTALL)
    if specialist_match:
        result["specialist_copay"] = float(specialist_match.group(1))

    er_match = re.search(r'emergency room.*?\$(\d+)/Visit', content, re.IGNORECASE | re.DOTALL)
    if er_match:
        result["er_copay"] = float(er_match.group(1))

    generic_match = re.search(r'generic.*?\$(\d+)/Fill', content, re.IGNORECASE | re.DOTALL)
    if generic_match:
        result["generic_rx_copay"] = float(generic_match.group(1))

    return result


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
        print(f"Mode: {'AI-powered' if use_ai else 'Regex fallback'}")
        print("-" * 60)

        result = parse_sbc_markdown(content, use_ai=use_ai)

        for key, value in result.items():
            if value is not None:
                print(f"  {key}: {value}")
    else:
        print("Usage: python sbc_parser.py <sbc_markdown_file> [--no-ai]")
        print()
        print("Options:")
        print("  --no-ai    Use regex fallback instead of AI extraction")
