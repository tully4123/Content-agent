"""Initialise (or re-apply) the pubcam.db schema. Safe to re-run: uses CREATE TABLE IF NOT EXISTS."""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "pubcam.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def main() -> None:
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(schema_sql)
        conn.commit()
    finally:
        conn.close()
    print(f"Schema applied to {DB_PATH}")


if __name__ == "__main__":
    main()
