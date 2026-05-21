"""Configuration utilities for loading environment variables and app settings."""

from __future__ import annotations

import logging
import os

from dotenv import load_dotenv

# Load environment variables from a local .env file before reading settings.
load_dotenv()

logger = logging.getLogger(__name__)

# Core application settings used by both API and Streamlit processes.
APP_NAME = os.getenv("APP_NAME", "TriFirst")
ENV = os.getenv("ENV", "development")
DATABASE_PATH = os.getenv("DATABASE_PATH", "trifirst.db")
DATABASE_URL = os.getenv("DATABASE_URL", "")
STRAVA_CLIENT_ID = os.getenv("STRAVA_CLIENT_ID", "")
STRAVA_CLIENT_SECRET = os.getenv("STRAVA_CLIENT_SECRET", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# Critical settings that should be present for production features to work.
CRITICAL_ENV_VARS = {
    "DATABASE_URL": DATABASE_URL or DATABASE_PATH,
    "DATABASE_PATH": DATABASE_PATH,
    "STRAVA_CLIENT_ID": STRAVA_CLIENT_ID,
    "STRAVA_CLIENT_SECRET": STRAVA_CLIENT_SECRET,
    "GROQ_API_KEY": GROQ_API_KEY,
}


def validate_environment() -> dict[str, bool]:
    """Report which critical environment variables are configured.

    Args:
        None.

    Returns:
        A dictionary mapping each critical environment variable name to ``True`` when
        it has a non-empty value and ``False`` when it is missing or blank.
    """
    status = {name: bool(value) for name, value in CRITICAL_ENV_VARS.items()}
    loaded = [name for name, present in status.items() if present]
    missing = [name for name, present in status.items() if not present]
    logger.info("Environment variables loaded: %s", ", ".join(loaded) or "none")
    if missing:
        logger.warning("Critical environment variables missing: %s", ", ".join(missing))
    return status


# Validate configuration as soon as the module is imported during startup.
ENV_STATUS = validate_environment()
