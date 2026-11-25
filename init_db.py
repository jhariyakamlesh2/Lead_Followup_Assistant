import argparse
from pathlib import Path

from lead_assistant.database import Database
from lead_assistant.config import settings


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Initialize the LeadPilot SQLite database.")
    parser.add_argument(
        "--sample-output",
        action="store_true",
        help="Create/update the reproducible synthetic database in sample_data.",
    )
    args = parser.parse_args()
    database_path = (
        Path("sample_data") / "lead_assistant_sample.db"
        if args.sample_output
        else settings.database_url or settings.database_path
    )
    db = Database(database_path)
    db.seed_sample_data()
    if str(database_path).startswith(("postgres://", "postgresql://")):
        print("Database initialized: configured PostgreSQL database")
    else:
        print(f"Database initialized: {database_path}")
