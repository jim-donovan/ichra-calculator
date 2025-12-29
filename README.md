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
