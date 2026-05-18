"""Database connection helpers and initialization routines for SQLite.

SQLite is a lightweight database engine that stores all data in a single local file.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from trifirst.config import DATABASE_PATH

logger = logging.getLogger(__name__)

# Tables that must exist for the TriFirst application to run correctly.
EXPECTED_TABLES = (
    "users",
    "race_goals",
    "fitness_background",
    "activities",
    "strava_tokens",
    "weekly_summaries",
    "coach_messages",
    "athlete_profile",
    "scheduled_workouts",
    "pending_workouts",
)


def get_connection() -> sqlite3.Connection:
    """Return a SQLite connection for the configured database file.

    Args:
        None.

    Returns:
        A SQLite connection configured with row dictionaries, a connection timeout,
        and cross-thread access enabled for web-server stability.
    """
    # Open or create the configured SQLite database with a timeout for busy writes.
    connection = sqlite3.connect(DATABASE_PATH, timeout=30.0, check_same_thread=False)
    # Return rows as dictionary-like sqlite3.Row objects for readable column access.
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    """Initialize the SQLite database using the SQL schema file.

    Args:
        None.

    Returns:
        None.
    """
    # Load and execute the schema file that defines all application tables.
    schema_path = Path(__file__).with_name("schema.sql")
    schema_sql = schema_path.read_text(encoding="utf-8")

    with get_connection() as connection:
        connection.executescript(schema_sql)
        connection.commit()

    migrate_add_auth_columns()


def migrate_add_auth_columns() -> None:
    """Add legacy authentication columns to existing user tables when missing.

    Args:
        None.

    Returns:
        None.
    """
    with get_connection() as connection:
        # Check current user columns before applying idempotent migrations.
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(users)").fetchall()}
        if "username" not in columns:
            connection.execute("ALTER TABLE users ADD COLUMN username TEXT")
        if "password_hash" not in columns:
            connection.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
        connection.commit()


def check_db_health() -> dict[str, bool]:
    """Verify that every expected application table exists.

    Args:
        None.

    Returns:
        A dictionary mapping expected table names to whether they exist in SQLite.
    """
    with get_connection() as connection:
        # Fetch all user-defined table names from SQLite metadata.
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()

    existing_tables = {row["name"] for row in rows}
    health = {table_name: table_name in existing_tables for table_name in EXPECTED_TABLES}
    missing_tables = [table_name for table_name, exists in health.items() if not exists]
    if missing_tables:
        logger.warning("Missing database tables: %s", ", ".join(missing_tables))
    else:
        logger.info("Database health check passed for %s tables", len(EXPECTED_TABLES))
    return health
