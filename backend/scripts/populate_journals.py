"""
Populate journal profiles from OpenAlex.
Run: python -m scripts.populate_journals [--field economics]
"""

import argparse
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.models import init_database
from services.journal_data_service import get_journal_data_service, FIELD_SEARCH_TERMS


def main():
    parser = argparse.ArgumentParser(description="Populate journal profiles from OpenAlex")
    parser.add_argument("--field", type=str, help="Single field to populate (default: all)")
    parser.add_argument("--list-fields", action="store_true", help="List available fields")
    args = parser.parse_args()

    if args.list_fields:
        print("Available fields:")
        for f in sorted(FIELD_SEARCH_TERMS.keys()):
            print(f"  - {f}")
        return

    # Ensure tables exist
    init_database()

    service = get_journal_data_service()

    if args.field:
        if args.field not in FIELD_SEARCH_TERMS:
            print(f"Unknown field: {args.field}")
            print(f"Available: {', '.join(sorted(FIELD_SEARCH_TERMS.keys()))}")
            sys.exit(1)
        print(f"Populating journals for: {args.field}")
    else:
        print(f"Populating journals for all {len(FIELD_SEARCH_TERMS)} fields...")

    service.populate_journals(field=args.field)

    # Print summary
    from database.models import SessionLocal, JournalProfile
    from sqlalchemy import func as sa_func
    db = SessionLocal()
    try:
        counts = db.query(
            JournalProfile.primary_field,
            JournalProfile.computed_tier,
            sa_func.count(JournalProfile.id)
        ).group_by(
            JournalProfile.primary_field,
            JournalProfile.computed_tier
        ).all()

        print("\n=== Journal Database Summary ===")
        field_totals = {}
        for field, tier, count in counts:
            if field not in field_totals:
                field_totals[field] = {1: 0, 2: 0, 3: 0}
            field_totals[field][tier] = count

        for field in sorted(field_totals.keys()):
            tiers = field_totals[field]
            total = sum(tiers.values())
            print(f"  {field}: {total} total (T1={tiers[1]}, T2={tiers[2]}, T3={tiers[3]})")

        grand_total = sum(sum(t.values()) for t in field_totals.values())
        print(f"\nGrand total: {grand_total} journals")
    finally:
        db.close()


if __name__ == "__main__":
    main()
