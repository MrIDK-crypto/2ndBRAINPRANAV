"""
Daily Grant Scraper
Fetches grants from NIH RePORTER and Grants.gov, saves as Documents, embeds into Pinecone.

Usage:
    cd backend
    python -m scripts.scrape_grants_daily              # Default tenant
    python -m scripts.scrape_grants_daily --tenant-id abc123  # Specific tenant
    python -m scripts.scrape_grants_daily --dry-run     # Preview without saving

Schedule via cron (daily at 6 AM):
    0 6 * * * cd /path/to/backend && ./venv/bin/python -m scripts.scrape_grants_daily >> /var/log/grant_scraper.log 2>&1
"""

import os
import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime, timezone

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / '.env')

from database.models import (
    SessionLocal, init_database,
    Document, DocumentStatus, DocumentClassification, Tenant
)
from services.grant_finder_service import GrantFinderService
from services.embedding_service import get_embedding_service

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [GrantScraper] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Broad research topics (always searched)
BASE_SEARCH_QUERIES = [
    "biomedical research",
    "clinical trial",
    "health sciences",
    "technology innovation",
    "environmental science",
    "data science machine learning",
    "public health",
    "neuroscience",
]


def get_lab_profile_keywords(db, tenant_id: str) -> list:
    """Pull additional keywords from tenant's lab profile if it exists."""
    try:
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if tenant and tenant.settings:
            profile = tenant.settings.get('grant_profile', {})
            keywords = profile.get('keywords', [])
            areas = profile.get('research_areas', [])
            return list(set(keywords + areas))
    except Exception as e:
        logger.warning(f"Could not load lab profile: {e}")
    return []


def grant_to_document_content(grant: dict) -> str:
    """Format a grant result as structured text for embedding."""
    parts = [
        f"Grant: {grant['title']}",
        f"Source: {grant['source'].replace('_', ' ').title()}",
        f"Agency: {grant['agency_full']} ({grant['agency']})",
    ]

    if grant.get('pi_name') and grant['pi_name'] != 'Unknown PI':
        parts.append(f"Principal Investigator: {grant['pi_name']}")
    if grant.get('organization'):
        loc = f" ({grant['org_location']})" if grant.get('org_location') else ""
        parts.append(f"Organization: {grant['organization']}{loc}")
    if grant.get('award_amount'):
        parts.append(f"Award Amount: ${grant['award_amount']:,}")
    if grant.get('activity_code'):
        parts.append(f"Activity Code: {grant['activity_code']}")
    if grant.get('start_date'):
        parts.append(f"Start Date: {grant['start_date']}")
    if grant.get('end_date'):
        parts.append(f"End Date: {grant['end_date']}")
    if grant.get('deadline'):
        parts.append(f"Application Deadline: {grant['deadline']}")
    if grant.get('status'):
        parts.append(f"Status: {grant['status']}")
    if grant.get('project_num'):
        parts.append(f"Project Number: {grant['project_num']}")
    if grant.get('url'):
        parts.append(f"URL: {grant['url']}")

    if grant.get('abstract'):
        parts.append(f"\nAbstract:\n{grant['abstract']}")

    return "\n".join(parts)


def scrape_and_ingest(tenant_id: str = None, dry_run: bool = False, limit_per_query: int = 20):
    """Main scraper logic. If tenant_id is None, scrape for all tenants."""
    init_database()
    db = SessionLocal()

    try:
        # Auto-detect tenants if none specified
        if not tenant_id:
            tenants = db.query(Tenant).all()
            if not tenants:
                logger.warning("No tenants found in database. Nothing to scrape for.")
                return
            tenant_ids = [t.id for t in tenants]
            logger.info(f"Auto-detected {len(tenant_ids)} tenant(s): {tenant_ids}")
        else:
            # Verify tenant exists
            tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
            if not tenant:
                logger.warning(f"Tenant '{tenant_id}' not found. Falling back to all tenants.")
                tenants = db.query(Tenant).all()
                if not tenants:
                    logger.warning("No tenants found in database. Nothing to scrape for.")
                    return
                tenant_ids = [t.id for t in tenants]
            else:
                tenant_ids = [tenant_id]

        for tid in tenant_ids:
            logger.info(f"--- Scraping grants for tenant: {tid} ---")
            _scrape_for_tenant(db, tid, dry_run, limit_per_query)

    except Exception as e:
        db.rollback()
        logger.error(f"Scraper failed: {e}", exc_info=True)
    finally:
        db.close()


def _scrape_for_tenant(db, tenant_id: str, dry_run: bool = False, limit_per_query: int = 20):
    """Scrape and ingest grants for a single tenant."""
    try:
        finder = GrantFinderService()

        # Build search queries: base terms + lab profile keywords
        queries = list(BASE_SEARCH_QUERIES)
        profile_keywords = get_lab_profile_keywords(db, tenant_id)
        if profile_keywords:
            logger.info(f"Adding {len(profile_keywords)} lab profile keywords: {profile_keywords[:5]}...")
            queries.extend(profile_keywords)

        # Deduplicate queries
        queries = list(dict.fromkeys(q.lower().strip() for q in queries))
        logger.info(f"Searching {len(queries)} queries across NIH RePORTER + Grants.gov")

        # Collect all grant results
        all_grants = {}  # keyed by external_id for dedup
        for query in queries:
            try:
                nih_results = finder.search_nih_reporter(query=query, limit=limit_per_query)
                for g in nih_results:
                    all_grants[g['id']] = g

                gov_results = finder.search_grants_gov(query=query, limit=limit_per_query)
                for g in gov_results:
                    all_grants[g['id']] = g
            except Exception as e:
                logger.warning(f"Error searching '{query}': {e}")

        logger.info(f"Found {len(all_grants)} unique grants across all queries")

        if not all_grants:
            logger.info("No grants found. Exiting.")
            return

        # Check which grants already exist in DB
        existing_ids = set()
        ext_ids = list(all_grants.keys())
        # Query in batches of 100
        for i in range(0, len(ext_ids), 100):
            batch = ext_ids[i:i+100]
            rows = db.query(Document.external_id).filter(
                Document.tenant_id == tenant_id,
                Document.external_id.in_(batch)
            ).all()
            existing_ids.update(r[0] for r in rows)

        new_grants = {k: v for k, v in all_grants.items() if k not in existing_ids}
        logger.info(f"New grants to ingest: {len(new_grants)} (skipping {len(existing_ids)} existing)")

        if not new_grants:
            logger.info("All grants already in database. Nothing to do.")
            return

        if dry_run:
            logger.info("[DRY RUN] Would ingest these grants:")
            for ext_id, grant in list(new_grants.items())[:10]:
                logger.info(f"  - [{grant['source']}] {grant['title'][:80]}...")
            if len(new_grants) > 10:
                logger.info(f"  ... and {len(new_grants) - 10} more")
            return

        # Create Document records
        now = datetime.now(timezone.utc)
        new_docs = []
        for ext_id, grant in new_grants.items():
            content = grant_to_document_content(grant)
            doc = Document(
                tenant_id=tenant_id,
                external_id=ext_id,
                source_type='grant',
                source_url=grant.get('url', ''),
                title=grant['title'][:500],
                content=content,
                doc_metadata={
                    'grant_source': grant['source'],
                    'agency': grant['agency'],
                    'agency_full': grant['agency_full'],
                    'pi_name': grant.get('pi_name', ''),
                    'organization': grant.get('organization', ''),
                    'award_amount': grant.get('award_amount', 0),
                    'activity_code': grant.get('activity_code', ''),
                    'project_num': grant.get('project_num', ''),
                    'deadline': grant.get('deadline'),
                    'status': grant.get('status', ''),
                },
                sender=grant.get('pi_name', ''),
                source_created_at=now,
                status=DocumentStatus.CONFIRMED,
                classification=DocumentClassification.WORK,
                classification_confidence=1.0,
                created_at=now,
                updated_at=now,
            )
            db.add(doc)
            new_docs.append(doc)

        db.commit()
        logger.info(f"Saved {len(new_docs)} new grant documents to database")

        # Embed into Pinecone
        try:
            embedding_service = get_embedding_service()
            result = embedding_service.embed_documents(
                documents=new_docs,
                tenant_id=tenant_id,
                db=db,
                force_reembed=False,
                batch_size=20
            )
            embedded = result.get('embedded', 0)
            errors = result.get('errors', [])
            logger.info(f"Embedded {embedded}/{len(new_docs)} grants into Pinecone")
            if errors:
                logger.warning(f"Embedding errors: {errors[:3]}")
        except Exception as e:
            logger.error(f"Embedding failed (grants saved to DB but not yet searchable): {e}")

        logger.info(f"Done! {len(new_docs)} new grants ingested and embedded.")

    except Exception as e:
        db.rollback()
        logger.error(f"Scraper failed for tenant {tenant_id}: {e}", exc_info=True)


def main():
    parser = argparse.ArgumentParser(description='Daily grant scraper for 2nd Brain')
    parser.add_argument('--tenant-id', default=None,
                        help='Tenant ID to ingest grants for (default: auto-detect all tenants)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Preview what would be ingested without saving')
    parser.add_argument('--limit', type=int, default=20,
                        help='Max results per query per source (default: 20)')
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("2nd Brain - Daily Grant Scraper")
    logger.info(f"Tenant: {args.tenant_id}")
    logger.info(f"Dry run: {args.dry_run}")
    logger.info("=" * 60)

    scrape_and_ingest(
        tenant_id=args.tenant_id,
        dry_run=args.dry_run,
        limit_per_query=args.limit
    )


if __name__ == '__main__':
    main()
