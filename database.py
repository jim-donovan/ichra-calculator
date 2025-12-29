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
                 database: str = "ichra_data", user: Optional[str] = None,
                 password: Optional[str] = None, sslmode: Optional[str] = None):
        """
        Initialize database connection parameters

        Args:
            host: Database host
            port: Database port
            database: Database name
            user: Database user
            password: Database password (required for remote connections)
            sslmode: SSL mode ('require', 'prefer', 'disable', etc.)
        """
        self.host = host
        self.port = port
        self.database = database
        # Get user from parameter, environment, or current OS user
        import os
        import getpass
        self.user = user or os.environ.get('DB_USER') or getpass.getuser()
        self.password = password or os.environ.get('DB_PASSWORD')
        self.sslmode = sslmode or os.environ.get('DB_SSLMODE')
        self._conn = None
        self._engine = None

    def connect(self) -> psycopg2.extensions.connection:
        """
        Establish database connection (psycopg2)

        Returns:
            Database connection object
        """
        import logging
        import time

        if self._conn is None or self._conn.closed:
            try:
                logging.info(f"DB CONNECT: Connecting to {self.database}@{self.host}:{self.port}...")
                connect_start = time.time()
                connect_params = {
                    'host': self.host,
                    'port': self.port,
                    'database': self.database,
                    'user': self.user
                }
                if self.password:
                    connect_params['password'] = self.password
                if self.sslmode:
                    connect_params['sslmode'] = self.sslmode
                self._conn = psycopg2.connect(**connect_params)
                logging.info(f"DB CONNECT: Connected in {time.time() - connect_start:.2f}s")
            except psycopg2.Error as e:
                import logging
                import os
                # Only log detailed errors in debug mode to prevent info leakage
                if os.environ.get('DEBUG', '').lower() == 'true':
                    logging.error(f"Database connection error: {e}")
                else:
                    logging.error(f"Database connection error: {type(e).__name__}")
                st.error("Database connection error. Please check your configuration.")
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
            from urllib.parse import quote_plus
            if self.password:
                # URL-encode password to handle special characters
                encoded_password = quote_plus(self.password)
                connection_string = f"postgresql+psycopg2://{self.user}:{encoded_password}@{self.host}:{self.port}/{self.database}"
            else:
                connection_string = f"postgresql+psycopg2://{self.user}@{self.host}:{self.port}/{self.database}"
            # Add SSL mode as query parameter if specified
            if self.sslmode:
                connection_string += f"?sslmode={self.sslmode}"
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
        import logging
        import time

        # Log first 100 chars of query for debugging
        query_preview = query.strip()[:100].replace('\n', ' ')
        logging.debug(f"DB QUERY: {query_preview}...")

        connect_start = time.time()
        conn = self.connect()
        connect_time = time.time() - connect_start
        if connect_time > 0.1:
            logging.info(f"DB QUERY: Connection took {connect_time:.2f}s (slow)")

        try:
            exec_start = time.time()
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, params)
                exec_time = time.time() - exec_start
                if exec_time > 1.0:
                    logging.warning(f"DB QUERY: Slow query took {exec_time:.2f}s: {query_preview}...")

                if cursor.description:  # Query returns data
                    columns = [desc[0] for desc in cursor.description]
                    data = cursor.fetchall()
                    return pd.DataFrame(data, columns=columns)
                else:  # Query doesn't return data (INSERT, UPDATE, etc.)
                    conn.commit()
                    return pd.DataFrame()
        except psycopg2.Error as e:
            import logging
            import os
            # Always log detailed errors for debugging
            logging.error(f"Query execution error: {e}")
            logging.error(f"Query: {query[:200]}...")
            logging.error(f"Params: {params}")
            st.error(f"Database query error: {e}")
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
    import os

    # Option 1: Check Railway/environment variables first
    if os.environ.get('DATABASE_URL') or os.environ.get('DB_HOST'):
        # Railway provides DATABASE_URL, or use individual env vars
        if os.environ.get('DATABASE_URL'):
            # Parse DATABASE_URL (postgres://user:pass@host:port/dbname)
            import urllib.parse
            url = urllib.parse.urlparse(os.environ['DATABASE_URL'])
            return DatabaseConnection(
                host=url.hostname,
                port=url.port or 5432,
                database=url.path[1:],  # Remove leading /
                user=url.username,
                password=url.password,
                sslmode=os.environ.get('DB_SSLMODE', 'prefer')
            )
        else:
            # Individual environment variables
            return DatabaseConnection(
                host=os.environ.get('DB_HOST', 'localhost'),
                port=int(os.environ.get('DB_PORT', 5432)),
                database=os.environ.get('DB_NAME', 'ichra_data'),
                user=os.environ.get('DB_USER'),
                password=os.environ.get('DB_PASSWORD'),
                sslmode=os.environ.get('DB_SSLMODE', 'prefer')
            )

    # Option 2: Check Streamlit secrets (for Streamlit Cloud)
    # Wrap in try/except because st.secrets throws if no secrets file exists
    try:
        if hasattr(st, 'secrets') and 'database' in st.secrets:
            db_secrets = st.secrets['database']
            return DatabaseConnection(
                host=db_secrets['host'],
                port=db_secrets['port'],
                database=db_secrets['name'],
                user=db_secrets['user'],
                password=db_secrets.get('password'),
                sslmode=db_secrets.get('sslmode', 'prefer')
            )
    except Exception:
        pass

    # Option 3: Use local defaults for development
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
