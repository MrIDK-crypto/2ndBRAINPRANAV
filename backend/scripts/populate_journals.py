"""
Populate journal profiles from OpenAlex + SCImago SJR.

Usage:
  python -m scripts.populate_journals                    # full refresh (OpenAlex + SJR)
  python -m scripts.populate_journals --field economics  # single field
  python -m scripts.populate_journals --openalex-only    # skip SJR scraping
  python -m scripts.populate_journals --sjr-only         # only enrich SJR (assumes OpenAlex data exists)
  python -m scripts.populate_journals --list-fields      # list available fields
  python -m scripts.populate_journals --summary          # show current DB state
"""

import argparse
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.models import init_database
from services.journal_data_service import get_journal_data_service, FIELD_SEARCH_TERMS


def print_summary():
    """Print current journal database summary."""
    service = get_journal_data_service()
    summary = service.get_data_summary()

    print("\n╔══════════════════════════════════════════════════════════════╗")
    print("║              Journal Database Summary                       ║")
    print("╠══════════════════════════════════════════════════════════════╣")

    if not summary.get("fields"):
        print("║  No journal data found. Run populate first.                ║")
        print("╚══════════════════════════════════════════════════════════════╝")
        return

    header = f"{'Field':<25} {'Total':>6} {'T1':>4} {'T2':>4} {'T3':>4} {'SJR':>5}"
    print(f"║  {header}  ║")
    print("╠══════════════════════════════════════════════════════════════╣")

    for field in sorted(summary["fields"].keys()):
        data = summary["fields"][field]
        row = f"{field:<25} {data['total']:>6} {data['tier1']:>4} {data['tier2']:>4} {data['tier3']:>4} {data['has_sjr']:>5}"
        print(f"║  {row}  ║")

    print("╠══════════════════════════════════════════════════════════════╣")
    total_line = f"Total: {summary['total_journals']} journals across {summary['total_fields']} fields"
    updated_line = f"Last updated: {summary.get('last_updated', 'never')}"
    print(f"║  {total_line:<58}║")
    print(f"║  {updated_line:<58}║")
    print("╚══════════════════════════════════════════════════════════════╝")


def main():
    parser = argparse.ArgumentParser(description="Populate journal profiles from OpenAlex + SCImago SJR")
    parser.add_argument("--field", type=str, help="Single field to populate (default: all)")
    parser.add_argument("--list-fields", action="store_true", help="List available fields")
    parser.add_argument("--summary", action="store_true", help="Show current database summary")
    parser.add_argument("--openalex-only", action="store_true", help="Only fetch from OpenAlex (skip SJR)")
    parser.add_argument("--sjr-only", action="store_true", help="Only enrich with SJR data (assumes OpenAlex data exists)")
    args = parser.parse_args()

    if args.list_fields:
        print("Available fields:")
        for f in sorted(FIELD_SEARCH_TERMS.keys()):
            print(f"  - {f}")
        return

    # Ensure tables exist
    init_database()

    if args.summary:
        print_summary()
        return

    service = get_journal_data_service()

    if args.field and args.field not in FIELD_SEARCH_TERMS:
        print(f"Unknown field: {args.field}")
        print(f"Available: {', '.join(sorted(FIELD_SEARCH_TERMS.keys()))}")
        sys.exit(1)

    if args.sjr_only:
        print(f"Enriching SJR data for {'all fields' if not args.field else args.field}...")
        service.enrich_with_sjr(field=args.field)
        service._recompute_tiers_with_sjr(field=args.field)
    elif args.openalex_only:
        print(f"Populating from OpenAlex for {'all fields' if not args.field else args.field}...")
        service.populate_journals(field=args.field)
    else:
        print(f"Full refresh for {'all fields' if not args.field else args.field}...")
        service.full_refresh(field=args.field)

    print_summary()


if __name__ == "__main__":
    main()
