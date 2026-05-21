"""Database connection helpers and initialization routines for PostgreSQL."""

from __future__ import annotations

import logging
from pathlib import Path

import psycopg2
import psycopg2.extras

from trifirst.config import DATABASE_PATH, DATABASE_URL

logger = logging.getLogger(__name__)

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


def get_connection():
    """Return a PostgreSQL connection using DATABASE_URL when configured."""
    dsn = DATABASE_URL or DATABASE_PATH
    return psycopg2.connect(dsn, cursor_factory=psycopg2.extras.RealDictCursor)


def init_db() -> None:
    """Initialize the PostgreSQL database using the SQL schema file."""
    schema_path = Path(__file__).with_name("schema.sql")
    schema_sql = schema_path.read_text(encoding="utf-8")

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(schema_sql)
        connection.commit()

    migrate_add_auth_columns()


def migrate_add_auth_columns() -> None:
    """Add legacy authentication columns to existing user tables when missing."""
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS username TEXT")
            cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash TEXT")
        connection.commit()


def check_db_health() -> dict[str, bool]:
    """Verify that every expected application table exists."""
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT table_name AS name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                """
            )
            rows = cursor.fetchall()

    existing_tables = {row["name"] for row in rows}
    health = {table_name: table_name in existing_tables for table_name in EXPECTED_TABLES}
    missing_tables = [table_name for table_name, exists in health.items() if not exists]
    if missing_tables:
        logger.warning("Missing database tables: %s", ", ".join(missing_tables))
    else:
        logger.info("Database health check passed for %s tables", len(EXPECTED_TABLES))
    return health
