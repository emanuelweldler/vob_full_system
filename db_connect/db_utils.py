"""
Database utilities and shared functions
"""
import sqlite3

# Database path - update this to match your system
DB_PATH = r"C:\data\VOB_DB\vob.db"


def get_connection(timeout=10):
    """
    Create and return a database connection with Row factory
    
    Args:
        timeout: Connection timeout in seconds
        
    Returns:
        sqlite3.Connection with row_factory set
    """
    conn = sqlite3.connect(DB_PATH, timeout=timeout)
    conn.row_factory = sqlite3.Row
    return conn


def table_has_column(conn, table, col):
    """
    Check if a table has a specific column
    
    Args:
        conn: Database connection
        table: Table name to check
        col: Column name to look for
        
    Returns:
        bool: True if column exists, False otherwise
    """
    rows = conn.execute(f"PRAGMA table_info({table});").fetchall()
    return any(r[1] == col for r in rows)