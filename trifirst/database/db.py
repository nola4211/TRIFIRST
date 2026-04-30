"""Database connection helpers and initialization routines for SQLite.

SQLite is a lightweight database engine that stores all data in a single local file.
"""

import sqlite3
from pathlib import Path

from trifirst.config import DATABASE_PATH


# Return a database connection object we can use to run SQL queries.
def get_connection() -> sqlite3.Connection:
    """Return a SQLite connection for the configured database file."""
    # Open (or create) the SQLite database file configured for this app.
    connection = sqlite3.connect(DATABASE_PATH)
    # row_factory makes each row behave like a dictionary (column name -> value).
    connection.row_factory = sqlite3.Row
    return connection


# Create database tables from the schema file if they do not already exist.
def init_db() -> None:
    """Initialize the SQLite database using the SQL schema file."""
    # Build the path to schema.sql in this same folder.
    schema_path = Path(__file__).with_name("schema.sql")
    # Read the full SQL schema text from disk.
    schema_sql = schema_path.read_text(encoding="utf-8")

    # Open a connection, run schema SQL, and save changes.
    with get_connection() as connection:
        # executescript runs multiple SQL statements in one call.
        connection.executescript(schema_sql)
        connection.commit()
