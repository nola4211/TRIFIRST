"""Configuration utilities for loading environment variables and app settings."""

from dotenv import load_dotenv
import os

load_dotenv()

APP_NAME = os.getenv("APP_NAME", "TriFirst")
ENV = os.getenv("ENV", "development")
DATABASE_PATH = os.getenv("DATABASE_PATH", "trifirst.db")
