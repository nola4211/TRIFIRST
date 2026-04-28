"""Database connection helpers and initialization routines for SQLite."""

import sqlite3
from pathlib import Path

from config import DATABASE_PATH


def get_connection() -> sqlite3.Connection:
    """Return a SQLite connection for the configured database file."""
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    """Initialize the SQLite database using the SQL schema file."""
    schema_path = Path(__file__).with_name("schema.sql")
    schema_sql = schema_path.read_text(encoding="utf-8")

    with get_connection() as connection:
        connection.executescript(schema_sql)
        connection.commit()
