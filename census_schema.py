"""
Census DataFrame Schema - Single Source of Truth

All pages should use these constants when accessing census_df columns.
Use normalize_census_df() to ensure consistent column names.

This module solves the problem of inconsistent column naming across the app:
- Census Input creates 'state' but some pages expect 'state_code'
- Census Input creates 'rating_area_id' but some pages expect 'rating_area'
- Original CSV uses 'Family Status' but internal code uses 'family_status'
"""

import pandas as pd
from typing import Optional


# =============================================================================
# CANONICAL COLUMN NAMES
# =============================================================================
# These are the column names that census_df SHOULD always have after normalization.
# All pages should use these constants when accessing census data.

# Employee identification
COL_EMPLOYEE_ID = 'employee_id'
COL_FIRST_NAME = 'first_name'
COL_LAST_NAME = 'last_name'

# Demographics
COL_AGE = 'age'
COL_DOB = 'dob'
COL_FAMILY_STATUS = 'family_status'

# Location
COL_STATE = 'state'                    # 2-letter state code (e.g., 'GA')
COL_COUNTY = 'county'
COL_ZIP = 'zip_code'
COL_RATING_AREA = 'rating_area_id'     # Integer rating area ID

# Financial data (optional)
COL_MONTHLY_INCOME = 'monthly_income'
COL_CURRENT_EE = 'current_ee_monthly'
COL_CURRENT_ER = 'current_er_monthly'


# =============================================================================
# COLUMN ALIASES
# =============================================================================
# Maps alternate column names to canonical names for normalization.
# Key = alias that might appear in raw data or from other sources
# Value = canonical name to normalize to

COLUMN_ALIASES = {
    # State aliases
    'state_code': COL_STATE,
    'Home State': COL_STATE,
    'home_state': COL_STATE,
    'State': COL_STATE,

    # Rating area aliases
    'rating_area': COL_RATING_AREA,
    'Rating Area': COL_RATING_AREA,

    # Family status aliases
    'Family Status': COL_FAMILY_STATUS,

    # Employee ID aliases
    'Employee Number': COL_EMPLOYEE_ID,
    'emp_id': COL_EMPLOYEE_ID,

    # Name aliases
    'First Name': COL_FIRST_NAME,
    'Last Name': COL_LAST_NAME,

    # Location aliases
    'Home Zip': COL_ZIP,
    'zip': COL_ZIP,
    'County': COL_COUNTY,

    # Age aliases
    'ee_age': COL_AGE,
    'Age': COL_AGE,
    'EE Age': COL_AGE,

    # Income aliases
    'Monthly Income': COL_MONTHLY_INCOME,
    'income': COL_MONTHLY_INCOME,

    # Current contribution aliases
    'Current EE Monthly': COL_CURRENT_EE,
    'Current ER Monthly': COL_CURRENT_ER,
}


# =============================================================================
# NORMALIZATION FUNCTION
# =============================================================================

def normalize_census_df(df: pd.DataFrame, inplace: bool = False) -> pd.DataFrame:
    """
    Normalize column names to canonical schema.

    This function renames any alias columns to their canonical names,
    ensuring consistent column access across all pages.

    Args:
        df: Census DataFrame to normalize
        inplace: If True, modify df in place. If False, return a copy.

    Returns:
        Normalized DataFrame with canonical column names

    Example:
        >>> df = pd.DataFrame({'state_code': ['GA'], 'rating_area': [1]})
        >>> df = normalize_census_df(df)
        >>> 'state' in df.columns  # True
        >>> 'rating_area_id' in df.columns  # True
    """
    if df is None or df.empty:
        return df if inplace else df.copy() if df is not None else pd.DataFrame()

    if not inplace:
        df = df.copy()

    # Build rename mapping for columns that exist and need renaming
    rename_map = {}
    for alias, canonical in COLUMN_ALIASES.items():
        if alias in df.columns and canonical not in df.columns:
            rename_map[alias] = canonical

    if rename_map:
        df.rename(columns=rename_map, inplace=True)

    return df


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_age_band(age: int) -> int:
    """
    Convert age to ACA age band (21-64 clamped).

    The ACA age curve uses ages 21-64 for rating. Ages below 21 are rated
    at age 21, and ages above 64 are rated at age 64 (Medicare-eligible
    individuals are typically handled separately).

    Args:
        age: Actual age of the person

    Returns:
        Age band for ACA rating (21-64)
    """
    return max(21, min(64, age))


def get_column(df: pd.DataFrame, canonical_name: str, default=None):
    """
    Get a column from a DataFrame, trying canonical name first then aliases.

    Use this when reading from a DataFrame that may not be normalized.
    Prefer normalizing the DataFrame instead when possible.

    Args:
        df: DataFrame to read from
        canonical_name: The canonical column name to look for
        default: Value to return if column not found

    Returns:
        The column Series if found, otherwise default
    """
    if canonical_name in df.columns:
        return df[canonical_name]

    # Find aliases for this canonical name
    for alias, canon in COLUMN_ALIASES.items():
        if canon == canonical_name and alias in df.columns:
            return df[alias]

    return default


def has_column(df: pd.DataFrame, canonical_name: str) -> bool:
    """
    Check if a DataFrame has a column (checking canonical name and aliases).

    Args:
        df: DataFrame to check
        canonical_name: The canonical column name to look for

    Returns:
        True if the column exists (under canonical or alias name)
    """
    if canonical_name in df.columns:
        return True

    for alias, canon in COLUMN_ALIASES.items():
        if canon == canonical_name and alias in df.columns:
            return True

    return False


def get_employee_state(row: pd.Series) -> Optional[str]:
    """
    Get the state code from an employee row, handling various column names.

    Args:
        row: A pandas Series representing an employee row

    Returns:
        2-letter state code (uppercase) or None if not found
    """
    for col in [COL_STATE, 'state_code', 'Home State', 'home_state']:
        if col in row.index:
            val = row[col]
            if pd.notna(val) and val != '':
                return str(val).upper()
    return None


def get_employee_rating_area(row: pd.Series) -> Optional[int]:
    """
    Get the rating area ID from an employee row, handling various column names.

    Args:
        row: A pandas Series representing an employee row

    Returns:
        Integer rating area ID or None if not found
    """
    for col in [COL_RATING_AREA, 'rating_area']:
        if col in row.index:
            val = row[col]
            if pd.notna(val):
                if isinstance(val, (int, float)):
                    return int(val)
                # Handle string format like "Rating Area 7"
                str_val = str(val)
                if str_val.startswith('Rating Area '):
                    try:
                        return int(str_val.replace('Rating Area ', ''))
                    except ValueError:
                        pass
                try:
                    return int(str_val)
                except ValueError:
                    pass
    return None


def get_employee_age(row: pd.Series) -> Optional[int]:
    """
    Get the age from an employee row, handling various column names.

    Args:
        row: A pandas Series representing an employee row

    Returns:
        Integer age or None if not found
    """
    for col in [COL_AGE, 'ee_age', 'Age', 'EE Age']:
        if col in row.index:
            val = row[col]
            if pd.notna(val):
                try:
                    return int(float(val))
                except (ValueError, TypeError):
                    pass
    return None
