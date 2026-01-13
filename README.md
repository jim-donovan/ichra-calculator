# Canopy

A Streamlit web application for benefits consultants to design and evaluate ICHRA (Individual Coverage Health Reimbursement Arrangement) strategies by analyzing individual marketplace coverage options and costs for their clients' workforces.

## Features

- **Census Management**: Upload employee/dependent CSV data with AI-powered column mapping and automatic ZIP-to-rating-area resolution
- **Plan Extraction**: AI-powered extraction of current group plan rates from benefits PDFs
- **ICHRA Dashboard**: Multi-metal marketplace comparison with Cooperative Health alternatives
- **AI Cost Analysis**: Claude-powered contribution evaluation and cost comparison
- **LCSP Analysis**: Multi-state Lowest Cost Silver Plan calculations with interactive heatmaps
- **Financial Summaries**: Aggregate employer costs with current vs. proposed ICHRA comparison
- **Individual Analysis**: Per-employee marketplace options and detailed contribution breakdowns
- **Professional Exports**: PDF census analysis, CSV data exports, PowerPoint proposals with email delivery
- **Plan Comparison**: Side-by-side benefit comparison of current group plan vs. marketplace alternatives
- **Flexible Contributions**: Support for percentage-based, flat dollar, age-banded, and LCSP percentage strategies

## Data Source

Uses official 2026 RBIS (Rate Based Insurance System) data from CMS covering Individual marketplace plans across all 50 states + DC.

**Plan Year:** 2026-01-01 to 2026-12-31

## Requirements

- Python 3.9+
- PostgreSQL database with RBIS data loaded
- Anthropic API key (for AI-powered contribution evaluation)
- See `requirements.txt` for Python package dependencies

## Installation

### 1. Clone Repository

```bash
git clone https://github.com/jim-donovan/ichra-calculator.git
cd ichra-calculator
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```
## Application Workflow

Canopy follows a 10-page sequential workflow for ICHRA analysis and proposal generation:

### Page 1: Census Input
Upload employee census CSV with automatic AI-powered column mapping. The system resolves ZIP codes to rating areas and validates all required data fields. Generates PDF census analysis with demographics, geographic distribution, and plan availability reports.

**Required:** Employee Number, Name, ZIP/State, Family Status, Date of Birth
**Optional:** Dependent DOBs, Current EE/ER Monthly Premiums, Monthly Income

### Page 2: Plan Extractor (Standalone)
AI-powered extraction of current group plan rates from benefits PDF documents. Automatically identifies plan tiers, rates, and calculates employee/employer contribution splits. Useful for understanding current plan costs before ICHRA modeling.

### Page 3: ICHRA Dashboard
Interactive broker presentation view showing multi-metal marketplace comparison (Bronze, Silver, Gold) with representative employee examples. Includes Cooperative Health alternatives (Health Access + DPC) and flexible contribution strategy configuration.

### Page 4: Contribution Evaluation
AI-powered cost comparison using Claude to analyze current contributions vs. marketplace options for each employee. Provides intelligent recommendations and cost-saving insights.

### Page 5: LCSP Analysis
Multi-state Lowest Cost Silver Plan calculations with interactive heatmaps showing premium variations by rating area. Critical for IRS affordability safe harbor compliance (9.96% threshold for 2026).

### Page 6: Employer Summary
Aggregate financial analysis showing total employer costs across workforce. Compares current group plan spending vs. proposed ICHRA costs with detailed savings breakdowns by state and metal level.

### Page 7: Individual Analysis
Per-employee marketplace plan options with detailed contribution analysis. Shows available plans, out-of-pocket projections, and affordability calculations for each family unit.

### Page 8: Export Results
Generate PDF census reports and export detailed CSV data files for further analysis or record-keeping.

### Page 9: Proposal Generator
Create professional PowerPoint proposals with customizable templates. Includes email delivery via SendGrid with 25MB attachment support. Generates QR codes for shareable proposal links (7-day expiry via Cloudflare R2).

### Page 10: Plan Comparison (Standalone)
Side-by-side benefit comparison tool for evaluating current employer group plan vs. marketplace alternatives. Upload SBC PDFs for automatic benefit extraction, then filter and compare marketplace plans by metal level, plan type, HSA eligibility, and deductible ranges.
