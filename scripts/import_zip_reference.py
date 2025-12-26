"""
Import ZIP-to-County reference data into database

Reads ZIP_COUNTY_062025_.xlsx and creates zip_county_reference table
for county lookup by ZIP code.
"""

import pandas as pd
import psycopg2
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import get_database_connection


def create_zip_reference_table(db):
    """Create the zip_county_reference table if it doesn't exist"""

    create_table_query = """
    CREATE TABLE IF NOT EXISTS zip_county_reference (
        zip_code TEXT NOT NULL,
        fips_code TEXT NOT NULL,
        city TEXT,
        state_code TEXT NOT NULL,
        PRIMARY KEY (zip_code, state_code)
    );

    CREATE INDEX IF NOT EXISTS idx_zip_county_zip
        ON zip_county_reference(zip_code);

    CREATE INDEX IF NOT EXISTS idx_zip_county_fips
        ON zip_county_reference(fips_code);
    """

    conn = db.connect()
    cursor = conn.cursor()
    cursor.execute(create_table_query)
    conn.commit()
    cursor.close()

    print("✓ Created zip_county_reference table")


def import_zip_data(db, xlsx_path):
    """Import ZIP code data from Excel file"""

    print(f"Reading {xlsx_path}...")

    # Read the Excel file
    df = pd.read_excel(xlsx_path, sheet_name='Export Worksheet')

    print(f"Loaded {len(df):,} ZIP code records")

    # Clean and format data
    df['zip_code'] = df['ZIP'].astype(str).str.zfill(5)
    df['fips_code'] = df['COUNTY'].astype(str)  # Keep FIPS as-is (no zero-padding)
    df['city'] = df['USPS_ZIP_PREF_CITY'].astype(str)
    df['state_code'] = df['USPS_ZIP_PREF_STATE'].astype(str)

    # Select only needed columns
    df_clean = df[['zip_code', 'fips_code', 'city', 'state_code']]

    # Remove duplicates (keep first for multi-county ZIPs)
    df_clean = df_clean.drop_duplicates(subset=['zip_code', 'state_code'], keep='first')

    print(f"Cleaned to {len(df_clean):,} unique ZIP+State combinations")

    # Clear existing data
    conn = db.connect()
    cursor = conn.cursor()
    cursor.execute("TRUNCATE TABLE zip_county_reference")
    conn.commit()
    cursor.close()

    print("Cleared existing data")

    # Insert data in batches
    batch_size = 1000
    total_inserted = 0

    cursor = conn.cursor()

    for i in range(0, len(df_clean), batch_size):
        batch = df_clean.iloc[i:i+batch_size]

        # Prepare values for bulk insert
        values = []
        for _, row in batch.iterrows():
            values.append((
                row['zip_code'],
                row['fips_code'],
                row['city'],
                row['state_code']
            ))

        # Bulk insert
        insert_query = """
        INSERT INTO zip_county_reference (zip_code, fips_code, city, state_code)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (zip_code, state_code) DO NOTHING
        """

        cursor.executemany(insert_query, values)
        conn.commit()

        total_inserted += len(batch)
        print(f"Inserted {total_inserted:,} / {len(df_clean):,} records...", end='\r')

    cursor.close()

    print(f"\n✓ Imported {total_inserted:,} ZIP code records")

    # Verify import
    verify_query = "SELECT COUNT(*) FROM zip_county_reference"
    result = db.execute_query(verify_query)
    count = result.iloc[0][0]

    print(f"✓ Verified {count:,} records in database")


def test_lookups(db):
    """Test a few ZIP code lookups"""

    print("\nTesting ZIP lookups:")
    print("=" * 60)

    test_cases = [
        ('10001', 'NY'),  # Manhattan
        ('90210', 'CA'),  # Beverly Hills
        ('60601', 'IL'),  # Chicago
        ('33101', 'FL'),  # Miami
    ]

    for zip_code, state in test_cases:
        query = """
        SELECT zip_code, city, state_code, fips_code
        FROM zip_county_reference
        WHERE zip_code = %s AND state_code = %s
        """

        result = db.execute_query(query, (zip_code, state))

        if not result.empty:
            row = result.iloc[0]
            print(f"  {zip_code} ({state}): {row['city']}, FIPS: {row['fips_code']}")
        else:
            print(f"  {zip_code} ({state}): NOT FOUND")


if __name__ == "__main__":
    print("ZIP County Reference Data Import")
    print("=" * 60)

    # Get database connection
    db = get_database_connection()

    # Path to ZIP reference file
    xlsx_path = Path(__file__).parent.parent.parent / "ZIP_COUNTY_062025_.xlsx"

    if not xlsx_path.exists():
        print(f"ERROR: ZIP reference file not found: {xlsx_path}")
        sys.exit(1)

    try:
        # Create table
        create_zip_reference_table(db)

        # Import data
        import_zip_data(db, xlsx_path)

        # Test lookups
        test_lookups(db)

        print("\n✓ Import complete!")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        db.close()
