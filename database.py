"""
Database connection module for ICHRA Calculator
Connects to PostgreSQL database 'pricing-proposal'
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import streamlit as st
from typing import Optional
import pandas as pd
from sqlalchemy import create_engine


class DatabaseConnection:
    """Manages PostgreSQL database connections"""

    def __init__(self, host: str = "localhost", port: int = 5432,
                 database: str = "pricing-proposal", user: str = "jimdonovan"):
        """
        Initialize database connection parameters

        Args:
            host: Database host
            port: Database port
            database: Database name
            user: Database user
        """
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self._conn = None
        self._engine = None

    def connect(self) -> psycopg2.extensions.connection:
        """
        Establish database connection (psycopg2)

        Returns:
            Database connection object
        """
        if self._conn is None or self._conn.closed:
            try:
                self._conn = psycopg2.connect(
                    host=self.host,
                    port=self.port,
                    database=self.database,
                    user=self.user
                )
            except psycopg2.Error as e:
                st.error(f"Database connection error: {e}")
                raise
        return self._conn

    @property
    def engine(self):
        """
        Get SQLAlchemy engine for pandas operations.
        Use this with pd.read_sql() to avoid deprecation warnings.

        Returns:
            SQLAlchemy engine
        """
        if self._engine is None:
            # Explicitly use psycopg2 driver for compatibility
            connection_string = f"postgresql+psycopg2://{self.user}@{self.host}:{self.port}/{self.database}"
            self._engine = create_engine(connection_string)
        return self._engine

    def execute_query(self, query: str, params: Optional[tuple] = None) -> pd.DataFrame:
        """
        Execute a SQL query and return results as DataFrame

        Args:
            query: SQL query string
            params: Query parameters (optional)

        Returns:
            Pandas DataFrame with query results
        """
        conn = self.connect()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, params)
                if cursor.description:  # Query returns data
                    columns = [desc[0] for desc in cursor.description]
                    data = cursor.fetchall()
                    return pd.DataFrame(data, columns=columns)
                else:  # Query doesn't return data (INSERT, UPDATE, etc.)
                    conn.commit()
                    return pd.DataFrame()
        except psycopg2.Error as e:
            st.error(f"Query execution error: {e}")
            conn.rollback()
            raise

    def close(self):
        """Close database connection"""
        if self._conn and not self._conn.closed:
            self._conn.close()


@st.cache_resource
def get_database_connection():
    """
    Get cached database connection for Streamlit app

    Returns:
        DatabaseConnection instance
    """
    # Check if running on Streamlit Cloud or Railway
    if hasattr(st, 'secrets') and 'database' in st.secrets:
        # Use secrets for deployed environment
        return DatabaseConnection(
            host=st.secrets['database']['host'],
            port=st.secrets['database']['port'],
            database=st.secrets['database']['name'],
            user=st.secrets['database']['user']
        )
    else:
        # Use local defaults for development
        return DatabaseConnection()


def test_connection():
    """Test database connection"""
    try:
        db = get_database_connection()
        result = db.execute_query("SELECT 1 as test")
        if not result.empty:
            print("✓ Database connection successful!")
            return True
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        return False


if __name__ == "__main__":
    # Test connection when run directly
    test_connection()
