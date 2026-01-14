#!/usr/bin/env python3
"""
Migration script to create and populate HAS and Sedera rate tables.
These tables are required for the ICHRA Dashboard plan comparisons.

Safe to run multiple times (drops and recreates tables).

Usage:
    # Local (uses your OS user):
    python scripts/create_has_sedera_tables.py

    # Railway (set DATABASE_URL first):
    export DATABASE_URL="postgresql://user:pass@host:port/dbname"
    python scripts/create_has_sedera_tables.py
"""

import sys
import os
import psycopg2
import getpass


def get_direct_connection():
    """Get database connection directly (bypassing Streamlit caching)."""
    # Check for DATABASE_URL (Railway/Heroku style)
    if os.environ.get('DATABASE_URL'):
        import urllib.parse
        url = urllib.parse.urlparse(os.environ['DATABASE_URL'])
        return psycopg2.connect(
            host=url.hostname,
            port=url.port or 5432,
            database=url.path[1:],
            user=url.username,
            password=url.password,
            sslmode=os.environ.get('DB_SSLMODE', 'prefer')
        )

    # Local development: use current OS user (likely has admin privileges)
    return psycopg2.connect(
        host='localhost',
        port=5432,
        database='ichra_data',
        user=getpass.getuser()  # Use current OS user, not ichra_reader
    )


# HAS (Health Access Solutions) Cooperative Rates
# Columns: age_band, family_status, deductible_1k, deductible_2_5k
HAS_DATA = [
    ("18-29", "EC", 565.00, 465.00),
    ("18-29", "EE", 303.00, 253.00),
    ("18-29", "ES", 565.00, 465.00),
    ("18-29", "F", 890.00, 790.00),
    ("30-39", "EC", 623.00, 503.00),
    ("30-39", "EE", 332.00, 272.00),
    ("30-39", "ES", 623.00, 503.00),
    ("30-39", "F", 948.00, 828.00),
    ("40-49", "EC", 691.00, 547.00),
    ("40-49", "EE", 366.00, 294.00),
    ("40-49", "ES", 691.00, 547.00),
    ("40-49", "F", 1016.00, 872.00),
    ("50-59", "EC", 899.00, 679.00),
    ("50-59", "EE", 470.00, 360.00),
    ("50-59", "ES", 899.00, 679.00),
    ("50-59", "F", 1224.00, 1004.00),
    ("60-64", "EC", 1089.00, 801.00),
    ("60-64", "EE", 565.00, 421.00),
    ("60-64", "ES", 1089.00, 801.00),
    ("60-64", "F", 1414.00, 1126.00),
]

# Sedera Prime+ with DPC Rates
# Columns: Plan, IUA, age_band, family_status, family_status_sedera, sedera_monthly_rate
SEDERA_DATA = [
    ("Sedera Prime+ with DPC", "1000", "18-29", "EC", "MC", 391.44),
    ("Sedera Prime+ with DPC", "1000", "18-29", "EE", "MO", 182.24),
    ("Sedera Prime+ with DPC", "1000", "18-29", "ES", "MS", 388.86),
    ("Sedera Prime+ with DPC", "1000", "18-29", "F", "MF", 577.2),
    ("Sedera Prime+ with DPC", "1000", "30-39", "EC", "MC", 419.82),
    ("Sedera Prime+ with DPC", "1000", "30-39", "EE", "MO", 209.76),
    ("Sedera Prime+ with DPC", "1000", "30-39", "ES", "MS", 417.24),
    ("Sedera Prime+ with DPC", "1000", "30-39", "F", "MF", 587.52),
    ("Sedera Prime+ with DPC", "1000", "40-49", "EC", "MC", 426.7),
    ("Sedera Prime+ with DPC", "1000", "40-49", "EE", "MO", 214.06),
    ("Sedera Prime+ with DPC", "1000", "40-49", "ES", "MS", 424.12),
    ("Sedera Prime+ with DPC", "1000", "40-49", "F", "MF", 597.84),
    ("Sedera Prime+ with DPC", "1000", "50-59", "EC", "MC", 590.1),
    ("Sedera Prime+ with DPC", "1000", "50-59", "EE", "MO", 300.06),
    ("Sedera Prime+ with DPC", "1000", "50-59", "ES", "MS", 584.94),
    ("Sedera Prime+ with DPC", "1000", "50-59", "F", "MF", 847.24),
    ("Sedera Prime+ with DPC", "1000", "60+", "EC", "MC", 599.56),
    ("Sedera Prime+ with DPC", "1000", "60+", "EE", "MO", 307.8),
    ("Sedera Prime+ with DPC", "1000", "60+", "ES", "MS", 595.26),
    ("Sedera Prime+ with DPC", "1000", "60+", "F", "MF", 861),
    ("Sedera Prime+ with DPC", "1500", "18-29", "EC", "MC", 256.84),
    ("Sedera Prime+ with DPC", "1500", "18-29", "EE", "MO", 116.66),
    ("Sedera Prime+ with DPC", "1500", "18-29", "ES", "MS", 255.12),
    ("Sedera Prime+ with DPC", "1500", "18-29", "F", "MF", 458.08),
    ("Sedera Prime+ with DPC", "1500", "30-39", "EC", "MC", 311.88),
    ("Sedera Prime+ with DPC", "1500", "30-39", "EE", "MO", 142.46),
    ("Sedera Prime+ with DPC", "1500", "30-39", "ES", "MS", 310.16),
    ("Sedera Prime+ with DPC", "1500", "30-39", "F", "MF", 478.72),
    ("Sedera Prime+ with DPC", "1500", "40-49", "EC", "MC", 326.5),
    ("Sedera Prime+ with DPC", "1500", "40-49", "EE", "MO", 150.2),
    ("Sedera Prime+ with DPC", "1500", "40-49", "ES", "MS", 323.92),
    ("Sedera Prime+ with DPC", "1500", "40-49", "F", "MF", 501.08),
    ("Sedera Prime+ with DPC", "1500", "50-59", "EC", "MC", 502.8),
    ("Sedera Prime+ with DPC", "1500", "50-59", "EE", "MO", 238.78),
    ("Sedera Prime+ with DPC", "1500", "50-59", "ES", "MS", 497.64),
    ("Sedera Prime+ with DPC", "1500", "50-59", "F", "MF", 710.06),
    ("Sedera Prime+ with DPC", "1500", "60+", "EC", "MC", 520.86),
    ("Sedera Prime+ with DPC", "1500", "60+", "EE", "MO", 274.04),
    ("Sedera Prime+ with DPC", "1500", "60+", "ES", "MS", 515.7),
    ("Sedera Prime+ with DPC", "1500", "60+", "F", "MF", 735),
    ("Sedera Prime+ with DPC", "2500", "18-29", "EC", "MC", 232.76),
    ("Sedera Prime+ with DPC", "2500", "18-29", "EE", "MO", 105.48),
    ("Sedera Prime+ with DPC", "2500", "18-29", "ES", "MS", 231.04),
    ("Sedera Prime+ with DPC", "2500", "18-29", "F", "MF", 415.94),
    ("Sedera Prime+ with DPC", "2500", "30-39", "EC", "MC", 279.2),
    ("Sedera Prime+ with DPC", "2500", "30-39", "EE", "MO", 126.98),
    ("Sedera Prime+ with DPC", "2500", "30-39", "ES", "MS", 275.76),
    ("Sedera Prime+ with DPC", "2500", "30-39", "F", "MF", 427.12),
    ("Sedera Prime+ with DPC", "2500", "40-49", "EC", "MC", 283.5),
    ("Sedera Prime+ with DPC", "2500", "40-49", "EE", "MO", 129.56),
    ("Sedera Prime+ with DPC", "2500", "40-49", "ES", "MS", 280.92),
    ("Sedera Prime+ with DPC", "2500", "40-49", "F", "MF", 434.86),
    ("Sedera Prime+ with DPC", "2500", "50-59", "EC", "MC", 436.58),
    ("Sedera Prime+ with DPC", "2500", "50-59", "EE", "MO", 226.74),
    ("Sedera Prime+ with DPC", "2500", "50-59", "ES", "MS", 433.14),
    ("Sedera Prime+ with DPC", "2500", "50-59", "F", "MF", 617.18),
    ("Sedera Prime+ with DPC", "2500", "60+", "EC", "MC", 445.18),
    ("Sedera Prime+ with DPC", "2500", "60+", "EE", "MO", 233.62),
    ("Sedera Prime+ with DPC", "2500", "60+", "ES", "MS", 440.88),
    ("Sedera Prime+ with DPC", "2500", "60+", "F", "MF", 627.5),
    ("Sedera Prime+ with DPC", "500", "18-29", "EC", "MC", 462.82),
    ("Sedera Prime+ with DPC", "500", "18-29", "EE", "MO", 214.06),
    ("Sedera Prime+ with DPC", "500", "18-29", "ES", "MS", 457.66),
    ("Sedera Prime+ with DPC", "500", "18-29", "F", "MF", 684.7),
    ("Sedera Prime+ with DPC", "500", "30-39", "EC", "MC", 497.22),
    ("Sedera Prime+ with DPC", "500", "30-39", "EE", "MO", 248.46),
    ("Sedera Prime+ with DPC", "500", "30-39", "ES", "MS", 492.06),
    ("Sedera Prime+ with DPC", "500", "30-39", "F", "MF", 697.6),
    ("Sedera Prime+ with DPC", "500", "40-49", "EC", "MC", 524.74),
    ("Sedera Prime+ with DPC", "500", "40-49", "EE", "MO", 263.08),
    ("Sedera Prime+ with DPC", "500", "40-49", "ES", "MS", 519.58),
    ("Sedera Prime+ with DPC", "500", "40-49", "F", "MF", 738.02),
    ("Sedera Prime+ with DPC", "500", "50-59", "EC", "MC", 756.08),
    ("Sedera Prime+ with DPC", "500", "50-59", "EE", "MO", 385.2),
    ("Sedera Prime+ with DPC", "500", "50-59", "ES", "MS", 749.2),
    ("Sedera Prime+ with DPC", "500", "50-59", "F", "MF", 1089.76),
    ("Sedera Prime+ with DPC", "500", "60+", "EC", "MC", 768.98),
    ("Sedera Prime+ with DPC", "500", "60+", "EE", "MO", 394.66),
    ("Sedera Prime+ with DPC", "500", "60+", "ES", "MS", 762.1),
    ("Sedera Prime+ with DPC", "500", "60+", "F", "MF", 1107.82),
    ("Sedera Prime+ with DPC", "5000", "18-29", "EC", "MC", 170.84),
    ("Sedera Prime+ with DPC", "5000", "18-29", "EE", "MO", 79.68),
    ("Sedera Prime+ with DPC", "5000", "18-29", "ES", "MS", 169.98),
    ("Sedera Prime+ with DPC", "5000", "18-29", "F", "MF", 294.68),
    ("Sedera Prime+ with DPC", "5000", "30-39", "EC", "MC", 232.76),
    ("Sedera Prime+ with DPC", "5000", "30-39", "EE", "MO", 105.48),
    ("Sedera Prime+ with DPC", "5000", "30-39", "ES", "MS", 231.04),
    ("Sedera Prime+ with DPC", "5000", "30-39", "F", "MF", 357.46),
    ("Sedera Prime+ with DPC", "5000", "40-49", "EC", "MC", 237.92),
    ("Sedera Prime+ with DPC", "5000", "40-49", "EE", "MO", 108.06),
    ("Sedera Prime+ with DPC", "5000", "40-49", "ES", "MS", 234.48),
    ("Sedera Prime+ with DPC", "5000", "40-49", "F", "MF", 365.2),
    ("Sedera Prime+ with DPC", "5000", "50-59", "EC", "MC", 341.12),
    ("Sedera Prime+ with DPC", "5000", "50-59", "EE", "MO", 158.8),
    ("Sedera Prime+ with DPC", "5000", "50-59", "ES", "MS", 337.68),
    ("Sedera Prime+ with DPC", "5000", "50-59", "F", "MF", 513.98),
    ("Sedera Prime+ with DPC", "5000", "60+", "EC", "MC", 347.14),
    ("Sedera Prime+ with DPC", "5000", "60+", "EE", "MO", 163.1),
    ("Sedera Prime+ with DPC", "5000", "60+", "ES", "MS", 343.7),
    ("Sedera Prime+ with DPC", "5000", "60+", "F", "MF", 522.58),
]


def create_has_sedera_tables():
    """Create and populate HAS and Sedera rate tables."""

    try:
        conn = get_direct_connection()
        cursor = conn.cursor()
        print(f"Connected to database as user: {getpass.getuser()}")

        # =====================================================================
        # HAS Cooperative Rates Table
        # =====================================================================
        print("Creating hap_cooperative_rates table...")
        # Drop and recreate to ensure current user owns the table
        cursor.execute("DROP TABLE IF EXISTS hap_cooperative_rates CASCADE")
        cursor.execute("""
            CREATE TABLE hap_cooperative_rates (
                id SERIAL PRIMARY KEY,
                age_band VARCHAR(10) NOT NULL,
                family_status VARCHAR(5) NOT NULL,
                deductible_1k NUMERIC(10,2),
                deductible_2_5k NUMERIC(10,2)
            )
        """)
        conn.commit()
        print("  Table created")

        # Insert HAS data
        print(f"  Inserting {len(HAS_DATA)} HAS rate rows...")
        for row in HAS_DATA:
            cursor.execute("""
                INSERT INTO hap_cooperative_rates (age_band, family_status, deductible_1k, deductible_2_5k)
                VALUES (%s, %s, %s, %s)
            """, row)
        conn.commit()
        print(f"  Inserted {len(HAS_DATA)} rows")

        # =====================================================================
        # Sedera Rates Table
        # =====================================================================
        print("\nCreating sedera_rates_with_dpc table...")
        # Drop and recreate to ensure current user owns the table
        cursor.execute("DROP TABLE IF EXISTS sedera_rates_with_dpc CASCADE")
        cursor.execute("""
            CREATE TABLE sedera_rates_with_dpc (
                "Plan" TEXT NOT NULL,
                "IUA" TEXT NOT NULL,
                age_band TEXT NOT NULL,
                family_status TEXT NOT NULL,
                family_status_sedera TEXT NOT NULL,
                sedera_monthly_rate NUMERIC(10,2)
            )
        """)
        conn.commit()
        print("  Table created")

        # Insert Sedera data
        print(f"  Inserting {len(SEDERA_DATA)} Sedera rate rows...")
        for row in SEDERA_DATA:
            cursor.execute("""
                INSERT INTO sedera_rates_with_dpc ("Plan", "IUA", age_band, family_status, family_status_sedera, sedera_monthly_rate)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, row)
        conn.commit()
        print(f"  Inserted {len(SEDERA_DATA)} rows")

        # =====================================================================
        # Verify
        # =====================================================================
        print("\nVerifying...")
        cursor.execute("SELECT COUNT(*) FROM hap_cooperative_rates")
        has_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM sedera_rates_with_dpc")
        sedera_count = cursor.fetchone()[0]

        print(f"  hap_cooperative_rates: {has_count} rows")
        print(f"  sedera_rates_with_dpc: {sedera_count} rows")

        cursor.close()
        conn.close()

        print("\n✓ Migration completed successfully!")
        return True

    except Exception as e:
        print(f"ERROR: Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = create_has_sedera_tables()
    sys.exit(0 if success else 1)
