"""
tools/db/apply_migrations.py
Applies the IPMI-OS 2.0 database schema to your Neon PostgreSQL instance.

Usage (run from the project root):
    python tools/db/apply_migrations.py

Requires DATABASE_URL to be set in .env
"""

import os
import sys
from pathlib import Path

# Ensure project root is on the Python path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import psycopg2
from dotenv import load_dotenv

# Load .env from project root
load_dotenv(ROOT / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")
MIGRATIONS_DIR = ROOT / "tools" / "db" / "migrations"

EXPECTED_TABLES = [
    "predictions",
    "actual_outcomes",
    "strategy_weights",
    "anomaly_log",
]


def get_connection():
    if not DATABASE_URL:
        print("❌  DATABASE_URL is not set in your .env file.")
        print("    Add a line like:")
        print("    DATABASE_URL=postgresql://user:pass@host/dbname?sslmode=require")
        sys.exit(1)
    try:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = False
        return conn
    except psycopg2.OperationalError as e:
        print(f"❌  Cannot connect to PostgreSQL.\n    Error: {e}")
        print("\n    Check your DATABASE_URL in .env and ensure the Neon instance is active.")
        sys.exit(1)


def verify_tables(conn) -> list[str]:
    """Returns list of EXPECTED_TABLES that are missing."""
    cur = conn.cursor()
    cur.execute("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_type = 'BASE TABLE';
    """)
    existing = {row[0] for row in cur.fetchall()}
    cur.close()
    return [t for t in EXPECTED_TABLES if t not in existing]


def apply_migration(conn, sql_path: Path):
    sql = sql_path.read_text(encoding="utf-8")
    cur = conn.cursor()
    try:
        cur.execute(sql)
        conn.commit()
        cur.close()
        print(f"  ✅  Applied: {sql_path.name}")
    except Exception as e:
        conn.rollback()
        cur.close()
        print(f"  ❌  Failed to apply {sql_path.name}: {e}")
        raise


def main():
    print("=" * 60)
    print("  IPMI-OS 2.0 — Database Migration Runner")
    print("=" * 60)
    print(f"\n  Connecting to: {DATABASE_URL[:40]}...\n")

    conn = get_connection()
    print("  ✅  Connected to PostgreSQL successfully.\n")

    # Check which tables exist before applying
    missing_before = verify_tables(conn)
    if not missing_before:
        print("  ✅  All tables already exist. Nothing to migrate.\n")
        print("  Tables verified:", ", ".join(EXPECTED_TABLES))
        conn.close()
        return

    print(f"  ⚠   Missing tables: {', '.join(missing_before)}")
    print("  Applying migrations...\n")

    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not migration_files:
        print(f"❌  No .sql files found in {MIGRATIONS_DIR}")
        sys.exit(1)

    for sql_file in migration_files:
        apply_migration(conn, sql_file)

    # Verify all tables now exist
    missing_after = verify_tables(conn)
    if missing_after:
        print(f"\n❌  Migration incomplete. Still missing: {', '.join(missing_after)}")
        sys.exit(1)

    print("\n  ✅  All migrations applied successfully!")
    print("  Tables created:", ", ".join(EXPECTED_TABLES))
    conn.close()
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
