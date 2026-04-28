"""Application entry point for starting TriFirst and initializing resources."""

from database.db import init_db


def main() -> None:
    """Initialize the database and start the TriFirst application."""
    init_db()
    print("TriFirst is running")


if __name__ == "__main__":
    main()
