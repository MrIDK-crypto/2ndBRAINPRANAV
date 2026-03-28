#!/usr/bin/env python3
"""
Add research_summary columns to tenants table.

Usage:
    DATABASE_URL=your_postgres_url python add_research_summary_columns.py

Or set the DATABASE_URL environment variable first.
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError


def get_database_url():
    """Get database URL from environment."""
    url = os.getenv('DATABASE_URL')
    if not url:
        print("ERROR: DATABASE_URL environment variable not set")
        print("\nSet it like this:")
        print("  export DATABASE_URL='postgresql://user:pass@host:5432/dbname'")
        sys.exit(1)
    return url


def run_migration(engine):
    """Add research_summary columns to tenants table."""

    migration_sql = """
    -- Add research_summary columns to tenants table
    ALTER TABLE tenants ADD COLUMN IF NOT EXISTS research_summary JSON;
    ALTER TABLE tenants ADD COLUMN IF NOT EXISTS research_summary_updated_at TIMESTAMP WITH TIME ZONE;
    """

    # Split into individual statements and execute
    statements = [s.strip() for s in migration_sql.split(';') if s.strip() and not s.strip().startswith('--')]

    with engine.connect() as conn:
        for i, stmt in enumerate(statements, 1):
            try:
                conn.execute(text(stmt))
                print(f"  [{i}/{len(statements)}] OK: {stmt[:60]}...")
            except SQLAlchemyError as e:
                if 'already exists' in str(e).lower():
                    print(f"  [{i}/{len(statements)}] SKIP (exists): {stmt[:60]}...")
                else:
                    print(f"  [{i}/{len(statements)}] ERROR: {e}")
                    raise
        conn.commit()


def verify_columns(engine):
    """Verify all columns were added."""
    expected_columns = ['research_summary', 'research_summary_updated_at']

    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'tenants'
            AND column_name = ANY(:columns)
        """), {"columns": expected_columns})

        found_columns = {row[0] for row in result}

    missing = set(expected_columns) - found_columns
    if missing:
        print(f"\nWARNING: Missing columns: {missing}")
        return False
    else:
        print(f"\nSUCCESS: All {len(expected_columns)} columns verified!")
        return True


def main():
    print("=" * 60)
    print("TENANT RESEARCH SUMMARY MIGRATION")
    print("=" * 60)

    db_url = get_database_url()
    print(f"\nConnecting to database...")
    print(f"  URL: {db_url[:30]}...{db_url[-20:]}")

    engine = create_engine(db_url)

    # Test connection
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print("  Connection: OK")
    except Exception as e:
        print(f"  Connection: FAILED - {e}")
        sys.exit(1)

    print("\nRunning migration...")
    try:
        run_migration(engine)
        print("\nMigration completed!")
    except Exception as e:
        print(f"\nMigration FAILED: {e}")
        sys.exit(1)

    print("\nVerifying columns...")
    if verify_columns(engine):
        print("\n" + "=" * 60)
        print("MIGRATION SUCCESSFUL!")
        print("=" * 60)
    else:
        print("\nMigration may have partially failed. Check logs above.")
        sys.exit(1)


if __name__ == '__main__':
    main()
