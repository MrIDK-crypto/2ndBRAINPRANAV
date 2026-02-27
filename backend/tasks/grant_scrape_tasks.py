"""
Grant Scraping Tasks
Background task for daily grant ingestion from NIH RePORTER and Grants.gov.
"""

import logging
from celery_app import celery

logger = logging.getLogger(__name__)


@celery.task(bind=True, name='tasks.grant_scrape_tasks.scrape_grants_daily')
def scrape_grants_daily_task(self, tenant_id: str = 'local-tenant', limit_per_query: int = 20):
    """
    Daily background task to scrape grants and ingest into knowledge base.

    Args:
        tenant_id: Tenant ID to ingest grants for
        limit_per_query: Max results per query per source

    Returns:
        dict: Scraping results
    """
    from scripts.scrape_grants_daily import scrape_and_ingest

    try:
        self.update_progress(0, 100, 'Starting daily grant scrape...')
        logger.info(f"[GrantScrapeTask] Starting for tenant={tenant_id}")

        scrape_and_ingest(
            tenant_id=tenant_id,
            dry_run=False,
            limit_per_query=limit_per_query
        )

        self.update_progress(100, 100, 'Grant scrape completed')
        logger.info(f"[GrantScrapeTask] Completed for tenant={tenant_id}")

        return {
            'success': True,
            'tenant_id': tenant_id,
        }

    except Exception as e:
        logger.error(f"[GrantScrapeTask] Error: {e}", exc_info=True)
        self.update_state(state='FAILURE', meta={'error': str(e)})
        raise
