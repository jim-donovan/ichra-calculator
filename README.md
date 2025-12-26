# ICHRA Plan Calculator

A Streamlit web application for benefits consultants to calculate and compare Individual marketplace plans for ICHRA (Individual Coverage Health Reimbursement Arrangement) implementations.

## Features

- **Employee Census Management**: Upload CSV with employee/dependent data, automatic ZIP-to-rating-area resolution
- **AI Contribution Evaluation**: Claude-powered cost comparison analysis
- **Financial Summary**: Multi-state ICHRA comparison with LCSP calculations and heatmaps
- **Employer Summary**: Aggregate costs, current vs proposed ICHRA comparison
- **Individual Analysis**: Per-employee marketplace options and contribution analysis
- **Professional Exports**: PDF proposals, CSV data exports, PowerPoint presentations
- **Approved Class Support**: Set different contribution levels by employee class

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

### 3. Configure Database

Copy the example secrets file and configure your database credentials:

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

Edit `.streamlit/secrets.toml`:

```toml
[database]
host = "localhost"
port = 5432
name = "pricing-proposal"
user = "your_username"
```

### 4. Configure Anthropic API (for AI features)

```bash
export ANTHROPIC_API_KEY="your-key-here"
```

Or create a `.env` file with `ANTHROPIC_API_KEY=your-key-here`

### 5. Verify Database Connection

```bash
python database.py
```

You should see: `✓ Database connection successful!`

## Running Locally

Start the Streamlit app:

```bash
streamlit run app.py
```

The app will open in your browser at `http://localhost:8501`

## Usage Workflow

### Page 1: Census Input

Upload a CSV file with employee data. Required columns:
- `Employee Number`, `Last Name`, `First Name`
- `Home Zip`, `Home State`
- `Family Status` (EE, ES, EC, or F)
- `EE DOB`

Optional columns:
- `Spouse DOB`, `Dep 2 DOB` through `Dep 6 DOB`
- `Monthly Income`, `Current EE Monthly`, `Current ER Monthly`

### Page 2: Contribution Evaluation

AI-powered cost comparison using Claude to analyze current contributions vs marketplace options.

### Page 3: Financial Summary

Multi-state ICHRA comparison with:
- LCSP (Lowest Cost Silver Plan) calculations
- Premium heatmaps by state/rating area
- Workforce cost projections

### Page 4: Employer Summary

- Aggregate costs across all employees
- Current group plan vs proposed ICHRA comparison
- Savings analysis

### Page 5: Individual Analysis

Per-employee breakdown of:
- Available marketplace plans
- Contribution allocations
- Out-of-pocket projections

### Page 6: Export Results

- Generate PDF proposals
- Download CSV data exports

### Page 7: Proposal Generator

- Generate PowerPoint presentations
- Customizable proposal templates

## Project Structure

```
ichra_calculator/
├── app.py                      # Main application entry point
├── database.py                 # Database connection management
├── queries.py                  # SQL queries for data retrieval
├── utils.py                    # Helper functions and calculations
├── constants.py                # Configuration and reference data
├── affordability.py            # IRS affordability safe harbor analysis
├── financial_calculator.py     # Multi-state premium calculations
├── fit_score_calculator.py     # ICHRA fit scoring
├── plan_suggester.py           # AI plan recommendations
├── pptx_generator.py           # PowerPoint generation
├── pptx_template_filler.py     # PowerPoint template filling
├── pdf_proposal_renderer.py    # PDF proposal generation
├── visualization_helpers.py    # Plotly chart helpers
├── requirements.txt            # Python dependencies
├── README.md                   # This file
├── CLAUDE.md                   # AI assistant guidance
├── DATABASE_SCHEMA.md          # Database documentation
├── .streamlit/
│   ├── config.toml             # Streamlit configuration
│   └── secrets.toml.example    # Database credentials template
├── fonts/
│   └── DMSans-*.ttf            # Custom fonts for PDFs
├── templates/
│   └── proposal/               # HTML proposal templates
└── pages/
    ├── 1_Census_Input.py       # Employee census upload
    ├── 2_Contribution_Evaluation.py  # AI cost comparison
    ├── 3_Financial_Summary.py  # Multi-state ICHRA analysis
    ├── 4_Employer_Summary.py   # Aggregate cost summary
    ├── 5_Individual_Analysis.py # Per-employee analysis
    ├── 6_Export_Results.py     # PDF and CSV exports
    └── 7_Proposal_Generator.py # PowerPoint proposals
```

## Database Schema

The application expects the following PostgreSQL tables:

- `rbis_insurance_plan_20251019202724` - Plan details
- `rbis_insurance_plan_variant_20251019202724` - Plan variants
- `rbis_insurance_plan_base_rates_20251019202724` - Age-based premium rates
- `rbis_insurance_plan_variant_ddctbl_moop_20251019202724` - Deductibles and MOOP
- `rbis_insurance_plan_benefit_cost_share_20251019202724` - Benefit cost-sharing
- `rbis_state_rating_area_amended` - County to rating area mapping
- `zip_to_county_correct` - ZIP to county FIPS mapping

See `DATABASE_SCHEMA.md` for detailed documentation.

## Troubleshooting

### Database Connection Failed

- Verify PostgreSQL is running
- Check database credentials in `.streamlit/secrets.toml`
- Ensure database user has SELECT permissions on RBIS tables
- Test connection with: `python database.py`

### No Plans Found

- Verify RBIS data is loaded in database
- Check filters: `market_coverage = 'Individual'`, `plan_effective_date = '2026-01-01'`
- For LCSP queries: use `csr_variation_type = 'Exchange variant (no CSR)'` only

### No Rates Found

- Rating area format: rates table stores `'Rating Area 1'` not integer `1`
- NY/VT use `age = "Family-Tier Rates"` string
- Verify rating area is correctly resolved from ZIP

### PDF Generation Not Available

Install reportlab if missing:

```bash
pip install reportlab
```

## License

Proprietary - Internal use only

## Version

2.0.0
