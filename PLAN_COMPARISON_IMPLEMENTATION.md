# Plan Comparison Feature Implementation Plan

## Overview

Create a new **Page 9: Plan Comparison** that enables brokers/employers to compare their current group health plan against marketplace alternatives. This helps answer the question: "How do available ICHRA plans stack up against our current employer plan?"

**Primary Use Case:** A benefits broker wants to show an employer that marketplace Silver plans have comparable (or better) benefits than their current group plan, making ICHRA a viable alternative.

## Reference Implementation

An employee-facing plan comparison UI already exists at:
```
/Users/jimdonovan/Desktop/jimdonovan/employee_app/
```

Key files to reference:
- `pages/1_Employee_Sandbox.py` - Plan selection UI, cost estimation, benefit display
- `queries.py` - `CostEstimatorQueries` class with copay/deductible/MOOP queries
- `constants.py` - Benefit types, family status codes

The employee app compares marketplace plans for a single employee. Our broker view adapts this to compare marketplace plans against a **current employer plan baseline**.

---

## Architecture Decision

**Standalone Page** (not dashboard integration)
- Complexity and distinct purpose warrant separate page
- Clean separation from census-driven analysis flow
- Can be used independently or after census upload

**File:** `pages/9_Plan_comparison.py`

---

## Three-Stage User Flow

### Stage 1: Current Employer Plan Input

User enters their current group plan details via CSV upload OR manual form.

**Input Fields:**
| Field | Type | Required | Example |
|-------|------|----------|---------|
| plan_name | string | Yes | "Acme Corp Gold PPO" |
| carrier | string | No | "Blue Cross Blue Shield" |
| plan_type | select | Yes | HMO, PPO, EPO, POS |
| metal_tier | select | No | Bronze, Silver, Gold, Platinum |
| hsa_eligible | boolean | Yes | True/False |
| individual_deductible | currency | Yes | $1,500 |
| family_deductible | currency | No | $3,000 |
| individual_oop_max | currency | Yes | $6,000 |
| family_oop_max | currency | No | $12,000 |
| coinsurance_pct | integer | Yes | 20 (meaning 20% employee pays) |
| pcp_copay | currency | Yes | $25 |
| specialist_copay | currency | Yes | $50 |
| er_copay | currency | No | $250 |
| urgent_care_copay | currency | No | $75 |
| generic_rx_copay | currency | Yes | $10 |
| preferred_rx_copay | currency | No | $35 |
| specialty_rx_copay | currency | No | $100 |

**Data Storage:**
```python
@dataclass
class CurrentEmployerPlan:
    plan_name: str
    carrier: Optional[str]
    plan_type: str  # HMO, PPO, EPO, POS
    metal_tier: Optional[str]
    hsa_eligible: bool
    individual_deductible: float
    family_deductible: Optional[float]
    individual_oop_max: float
    family_oop_max: Optional[float]
    coinsurance_pct: int
    pcp_copay: float
    specialist_copay: float
    er_copay: Optional[float]
    urgent_care_copay: Optional[float]
    generic_rx_copay: float
    preferred_rx_copay: Optional[float]
    specialty_rx_copay: Optional[float]

# Store in session state
st.session_state.current_employer_plan = CurrentEmployerPlan(...)
```

### Stage 2: Filter & Select Marketplace Plans

**Location Context** (Required):
Since marketplace plans vary by location, user must specify a reference location:
- **Option A (if census loaded):** Select a reference employee from census dropdown
- **Option B (standalone):** Enter ZIP code + State manually

This determines the rating_area_id for plan availability filtering.

**Filter Panel:**
```
┌─────────────────────────────────────────────────────────┐
│ 📍 Location: [ZIP: 64111] [State: MO] [Rating Area: 3]  │
├─────────────────────────────────────────────────────────┤
│ Metal Level:  [Bronze] [Silver ✓] [Gold ✓] [All]        │
│ HSA Eligible: [ ] Only show HSA-eligible plans          │
│ Plan Type:    [✓ HMO] [✓ PPO] [✓ EPO] [✓ POS]          │
│ Max Deductible: [$0 ──────●────── $10,000]              │
│ Max OOPM:       [$0 ──────●────── $15,000]              │
└─────────────────────────────────────────────────────────┘
```

**Plan Selection UI:**
- Display filtered plans with key metrics
- Checkbox selection (max 5 plans for comparison)
- Show "match score" percentage relative to current plan
- "Clear Selection" button

**Match Score Algorithm:**
```python
def calculate_match_score(current_plan: CurrentEmployerPlan, 
                          marketplace_plan: dict) -> float:
    """
    Calculate similarity score (0-100%) between plans.
    Higher = more similar to current plan.
    """
    score = 100.0
    
    # Deductible comparison (weight: 25%)
    ded_diff_pct = abs(marketplace_plan['deductible'] - current_plan.individual_deductible) / max(current_plan.individual_deductible, 1)
    score -= min(25, ded_diff_pct * 25)
    
    # OOPM comparison (weight: 25%)
    oopm_diff_pct = abs(marketplace_plan['moop'] - current_plan.individual_oop_max) / max(current_plan.individual_oop_max, 1)
    score -= min(25, oopm_diff_pct * 25)
    
    # Plan type match (weight: 15%)
    if marketplace_plan['plan_type'] != current_plan.plan_type:
        score -= 15
    
    # HSA eligibility match (weight: 10%)
    if marketplace_plan['hsa_eligible'] != current_plan.hsa_eligible:
        score -= 10
    
    # Copay comparison (weight: 25% split across PCP, Specialist, Generic Rx)
    pcp_diff = abs(marketplace_plan.get('pcp_copay', 30) - current_plan.pcp_copay) / max(current_plan.pcp_copay, 1)
    specialist_diff = abs(marketplace_plan.get('specialist_copay', 50) - current_plan.specialist_copay) / max(current_plan.specialist_copay, 1)
    rx_diff = abs(marketplace_plan.get('generic_rx_copay', 15) - current_plan.generic_rx_copay) / max(current_plan.generic_rx_copay, 1)
    
    score -= min(8.33, pcp_diff * 8.33)
    score -= min(8.33, specialist_diff * 8.33)
    score -= min(8.34, rx_diff * 8.34)
    
    return max(0, score)
```

### Stage 3: Benefit Comparison Table

Side-by-side comparison with color-coded indicators.

**Comparison Logic:**
```python
def compare_benefit(current_value: float, marketplace_value: float, 
                    lower_is_better: bool = True) -> str:
    """
    Returns: 'better', 'similar', 'worse'
    """
    if current_value == 0 and marketplace_value == 0:
        return 'similar'
    
    # Calculate percentage difference
    diff_pct = (marketplace_value - current_value) / max(current_value, 1) * 100
    
    # Threshold: within 10% = similar
    if abs(diff_pct) <= 10:
        return 'similar'
    
    if lower_is_better:
        return 'better' if diff_pct < 0 else 'worse'
    else:
        return 'better' if diff_pct > 0 else 'worse'
```

**Table Structure:**
```
┌────────────────────┬─────────────────┬─────────────────┬─────────────────┬─────────────────┐
│ Benefit            │ Current Plan    │ Blue Shield     │ Oscar Health    │ Ambetter        │
│                    │ (Acme Gold PPO) │ Silver PPO      │ Silver HMO      │ Bronze EPO      │
├────────────────────┼─────────────────┼─────────────────┼─────────────────┼─────────────────┤
│ Plan Type          │ PPO             │ PPO 🟢          │ HMO 🟡          │ EPO 🟡          │
│ HSA Eligible       │ No              │ No 🟢           │ Yes 🟢          │ Yes 🟢          │
├────────────────────┼─────────────────┼─────────────────┼─────────────────┼─────────────────┤
│ Individual Ded.    │ $1,500          │ $1,200 🟢       │ $2,000 🔴       │ $6,500 🔴       │
│ Family Ded.        │ $3,000          │ $2,400 🟢       │ $4,000 🔴       │ $13,000 🔴      │
│ Individual OOPM    │ $6,000          │ $5,500 🟢       │ $7,500 🔴       │ $8,700 🔴       │
│ Family OOPM        │ $12,000         │ $11,000 🟢      │ $15,000 🔴      │ $17,400 🔴      │
├────────────────────┼─────────────────┼─────────────────┼─────────────────┼─────────────────┤
│ PCP Copay          │ $25             │ $30 🟡          │ $20 🟢          │ 0% after ded 🟡 │
│ Specialist Copay   │ $50             │ $60 🟡          │ $50 🟢          │ 0% after ded 🟡 │
│ ER Copay           │ $250            │ $300 🟡         │ $250 🟢         │ 0% after ded 🟡 │
│ Urgent Care        │ $75             │ $75 🟢          │ $50 🟢          │ 0% after ded 🟡 │
├────────────────────┼─────────────────┼─────────────────┼─────────────────┼─────────────────┤
│ Generic Rx         │ $10             │ $15 🟡          │ $10 🟢          │ 0% after ded 🟡 │
│ Preferred Rx       │ $35             │ $45 🟡          │ $40 🟡          │ 0% after ded 🟡 │
│ Specialty Rx       │ $100            │ 20% coins 🟡    │ $150 🔴         │ 0% after ded 🟡 │
├────────────────────┼─────────────────┼─────────────────┼─────────────────┼─────────────────┤
│ Coinsurance        │ 20%             │ 20% 🟢          │ 25% 🔴          │ 0% 🟢           │
├────────────────────┼─────────────────┼─────────────────┼─────────────────┼─────────────────┤
│ MATCH SCORE        │ —               │ 92% ⭐          │ 78%             │ 45%             │
└────────────────────┴─────────────────┴─────────────────┴─────────────────┴─────────────────┘

Legend: 🟢 Better than current │ 🟡 Similar to current │ 🔴 Less generous
```

**Color Coding Rules:**
- **Deductible/OOPM:** Lower = 🟢, Within 10% = 🟡, Higher = 🔴
- **Copays:** Lower = 🟢, Within $10 or 20% = 🟡, Higher = 🔴
- **Coinsurance:** Lower = 🟢, Same = 🟡, Higher = 🔴
- **HSA Eligible:** Match = 🟢, Mismatch but marketplace has HSA = 🟢
- **Plan Type:** Match = 🟢, Similar (PPO↔POS) = 🟡, Different = 🟡

---

## Database Queries Required

### Existing Queries to Reuse

From `queries.py` (already in ichra_calculator_v2):

```python
# Plan filtering
PlanQueries.get_plans_by_filters(db, state_code, metal_level, plan_type)

# Rating area resolution  
PlanQueries.get_county_by_zip(db, zip_code, state_code)

# Deductible/MOOP
PlanQueries.get_plan_deductibles_moop(db, hios_plan_ids)
```

### Queries to Add (from employee_app or new)

```python
class PlanComparisonQueries:
    """Queries for Plan Comparison page"""
    
    @staticmethod
    def get_plan_copays_for_comparison(db, plan_ids: list) -> pd.DataFrame:
        """
        Get copay data for key services needed in comparison table.
        
        Adapted from employee_app CostEstimatorQueries.get_plan_copays()
        """
        placeholders = ', '.join(['%s'] * len(plan_ids))
        query = f"""
        SELECT
            hios_plan_id,
            benefit,
            co_payment as copay,
            co_insurance as coinsurance,
            network_type
        FROM rbis_insurance_plan_benefit_cost_share_20251019202724
        WHERE hios_plan_id IN ({placeholders})
            AND csr_variation_type = 'Exchange variant (no CSR)'
            AND network_type = 'In Network'
            AND (
                LOWER(benefit) LIKE '%primary care%'
                OR LOWER(benefit) LIKE '%specialist visit%'
                OR LOWER(benefit) LIKE '%generic drug%'
                OR LOWER(benefit) LIKE '%preferred brand drug%'
                OR LOWER(benefit) LIKE '%emergency room%'
                OR LOWER(benefit) LIKE '%urgent care%'
            )
        ORDER BY hios_plan_id, benefit
        """
        return db.execute_query(query, tuple(plan_ids))
    
    @staticmethod
    def get_plan_hsa_eligibility(db, plan_ids: list) -> pd.DataFrame:
        """Get HSA eligibility from plan variant table"""
        placeholders = ', '.join(['%s'] * len(plan_ids))
        query = f"""
        SELECT 
            hios_plan_id,
            hsa_eligible
        FROM rbis_insurance_plan_variant_20251019202724
        WHERE hios_plan_id IN ({placeholders})
            AND csr_variation_type = 'Exchange variant (no CSR)'
        """
        return db.execute_query(query, tuple(plan_ids))
    
    @staticmethod
    def get_plans_with_full_details(db, state_code: str, rating_area_id: int,
                                     metal_levels: list = None,
                                     plan_types: list = None,
                                     max_deductible: float = None,
                                     max_oopm: float = None,
                                     hsa_only: bool = False) -> pd.DataFrame:
        """
        Get marketplace plans with deductibles, OOPM, and HSA eligibility
        for the comparison filter panel.
        """
        query = """
        SELECT DISTINCT
            p.hios_plan_id,
            p.plan_marketing_name,
            p.plan_type,
            p.level_of_coverage as metal_level,
            SUBSTRING(p.hios_plan_id FROM 1 FOR 5) as issuer_id,
            v.hsa_eligible,
            dm_ded.individual_ded_moop_amount as individual_deductible,
            dm_moop.individual_ded_moop_amount as individual_oopm
        FROM rbis_insurance_plan_20251019202724 p
        JOIN rbis_insurance_plan_variant_20251019202724 v 
            ON p.hios_plan_id = v.hios_plan_id
        LEFT JOIN rbis_insurance_plan_variant_ddctbl_moop_20251019202724 dm_ded
            ON p.hios_plan_id = dm_ded.plan_id
            AND dm_ded.variant_component = 'Exchange variant (no CSR)'
            AND dm_ded.network_type = 'In Network'
            AND LOWER(dm_ded.moop_ded_type) LIKE '%deductible%'
        LEFT JOIN rbis_insurance_plan_variant_ddctbl_moop_20251019202724 dm_moop
            ON p.hios_plan_id = dm_moop.plan_id
            AND dm_moop.variant_component = 'Exchange variant (no CSR)'
            AND dm_moop.network_type = 'In Network'
            AND LOWER(dm_moop.moop_ded_type) LIKE '%maximum out of pocket%'
        JOIN rbis_insurance_plan_base_rates_20251019202724 br
            ON p.hios_plan_id = br.plan_id
            AND REPLACE(br.rating_area_id, 'Rating Area ', '')::integer = %s
        WHERE SUBSTRING(p.hios_plan_id FROM 6 FOR 2) = %s
            AND p.market_coverage = 'Individual'
            AND p.plan_effective_date = '2026-01-01'
            AND v.csr_variation_type = 'Exchange variant (no CSR)'
        """
        params = [rating_area_id, state_code]
        
        if metal_levels:
            placeholders = ', '.join(['%s'] * len(metal_levels))
            query += f" AND p.level_of_coverage IN ({placeholders})"
            params.extend(metal_levels)
        
        if plan_types:
            placeholders = ', '.join(['%s'] * len(plan_types))
            query += f" AND p.plan_type IN ({placeholders})"
            params.extend(plan_types)
        
        if hsa_only:
            query += " AND v.hsa_eligible = 'Yes'"
        
        if max_deductible:
            query += " AND dm_ded.individual_ded_moop_amount::numeric <= %s"
            params.append(max_deductible)
        
        if max_oopm:
            query += " AND dm_moop.individual_ded_moop_amount::numeric <= %s"
            params.append(max_oopm)
        
        query += " ORDER BY p.plan_marketing_name"
        
        return db.execute_query(query, tuple(params))
```

---

## Session State Structure

```python
# Current employer plan (from Stage 1)
st.session_state.current_employer_plan = CurrentEmployerPlan(...)

# Location context (from Stage 2)
st.session_state.comparison_location = {
    'zip_code': '64111',
    'state': 'MO',
    'county': 'Jackson',
    'rating_area_id': 3,
    'source': 'manual'  # or 'census_employee_123'
}

# Filter settings (from Stage 2)
st.session_state.comparison_filters = {
    'metal_levels': ['Silver', 'Gold'],
    'plan_types': ['HMO', 'PPO', 'EPO', 'POS'],
    'hsa_only': False,
    'max_deductible': 5000,
    'max_oopm': 10000
}

# Selected plans for comparison (from Stage 2)
st.session_state.selected_comparison_plans = [
    'hios_plan_id_1',
    'hios_plan_id_2',
    'hios_plan_id_3'
]  # Max 5

# Enriched plan data with copays (populated in Stage 3)
st.session_state.comparison_plan_details = {
    'hios_plan_id_1': {
        'plan_name': '...',
        'metal_level': 'Silver',
        'plan_type': 'PPO',
        'hsa_eligible': True,
        'individual_deductible': 1200,
        'family_deductible': 2400,
        'individual_oopm': 5500,
        'family_oopm': 11000,
        'pcp_copay': 30,
        'specialist_copay': 60,
        'er_copay': 300,
        'urgent_care_copay': 75,
        'generic_rx_copay': 15,
        'preferred_rx_copay': 45,
        'coinsurance_pct': 20,
        'match_score': 92.5
    },
    # ... more plans
}
```

---

## Files to Create/Modify

### New Files

1. **`pages/9_Plan_comparison.py`** - Main page implementation
2. **`plan_comparison_types.py`** - Dataclasses (CurrentEmployerPlan, ComparisonResult)

### Modified Files

1. **`queries.py`** - Add `PlanComparisonQueries` class
2. **`constants.py`** - Add comparison-related constants:
   ```python
   COMPARISON_BENEFIT_ROWS = [
       ('plan_type', 'Plan Type', False),
       ('hsa_eligible', 'HSA Eligible', False),
       ('individual_deductible', 'Individual Deductible', True),
       ('family_deductible', 'Family Deductible', True),
       ('individual_oopm', 'Individual OOPM', True),
       ('family_oopm', 'Family OOPM', True),
       ('pcp_copay', 'PCP Copay', True),
       ('specialist_copay', 'Specialist Copay', True),
       ('er_copay', 'ER Copay', True),
       ('urgent_care_copay', 'Urgent Care', True),
       ('generic_rx_copay', 'Generic Rx', True),
       ('preferred_rx_copay', 'Preferred Rx', True),
       ('coinsurance_pct', 'Coinsurance', True),
   ]
   ```

---

## Implementation Order

### Phase 1: Foundation (queries + types)
1. Add `CurrentEmployerPlan` dataclass to `constants.py` or new `plan_comparison_types.py`
2. Add `PlanComparisonQueries` class to `queries.py`
3. Test queries independently

### Phase 2: Stage 1 UI (current plan input)
1. Create `pages/9_Plan_comparison.py` skeleton
2. Build manual form for current employer plan entry
3. Add CSV upload option (parse SBC-style exports)
4. Store in `st.session_state.current_employer_plan`

### Phase 3: Stage 2 UI (filter + select)
1. Add location input (ZIP/state or census employee selector)
2. Build filter panel (metal, plan type, HSA, deductible, OOPM sliders)
3. Query and display filtered plans
4. Implement checkbox selection (max 5)
5. Calculate and display match scores

### Phase 4: Stage 3 UI (comparison table)
1. Fetch full plan details for selected plans
2. Build comparison table with color coding
3. Implement benefit comparison logic
4. Add export option (CSV/PDF of comparison)

### Phase 5: Polish
1. Add "Back" navigation between stages
2. Persist state across page navigation
3. Add tooltips explaining benefit comparisons
4. Test edge cases (missing data, zero values)

---

## Helper Functions from Employee App

These can be copied/adapted from `/Users/jimdonovan/Desktop/jimdonovan/employee_app/pages/1_Employee_Sandbox.py`:

```python
# Parsing helpers
def parse_copay_amount(copay_str) -> Optional[float]
def parse_coinsurance_pct(coinsurance_str) -> Optional[float]
def format_cost_sharing(row, is_out_of_network=False) -> str

# Deductible parsing
def parse_deductibles_moop(deductibles_df) -> dict

# Benefit extraction
def extract_key_benefits(cost_share_df) -> list

# CSS injection for cards
def inject_card_css()
```

---

## Test Scenarios

1. **Happy Path:** Upload current plan, filter to Silver PPO, select 3 plans, view comparison
2. **Census Integration:** Use census employee for location, compare plans
3. **Edge Cases:**
   - Current plan has $0 deductible (HDHP comparison)
   - Marketplace plan has coinsurance instead of copay
   - Missing family deductible in marketplace plan
4. **No Plans Found:** Filter too restrictive, no plans in rating area

---

## Open Questions (Resolved)

| Question | Resolution |
|----------|------------|
| Match % algorithm | Weighted comparison: 25% ded, 25% OOPM, 15% plan type, 10% HSA, 25% copays |
| Employee context for filtering | Standalone ZIP/state input OR select from loaded census |
| Premium display | **No premiums in comparison** - focus on benefit structure only. Premiums shown elsewhere (LCSP analysis, individual analysis) |
| Family vs individual | Show both individual AND family deductible/OOPM rows where available |

---

## Notes for Implementation

1. **No Premium Calculation:** This page compares benefit structures, not costs. Premium analysis is already covered in Pages 4-6.

2. **Service Area Filtering:** Use `check_plan_serves_county()` from employee app to filter out plans that don't serve the selected location.

3. **Coinsurance vs Copay Display:** When marketplace plan has coinsurance instead of copay (e.g., "20% after deductible"), display clearly and mark as 🟡 (different but not worse).

4. **Export Option:** Consider adding "Export Comparison" button that generates a PDF or CSV of the comparison table for broker presentations.
