"""Adapter wrapping CompetitorFinderService for the orchestrator."""

import logging
from typing import Dict, Any, Optional, List

from services.competitor_finder_service import CompetitorFinderService
from . import make_result_envelope

logger = logging.getLogger(__name__)


def run_competitor_finder(
    topics: Optional[List[str]] = None,
    field: Optional[str] = None,
    paper_text: Optional[str] = None,
    context_package: Optional[Dict] = None,
) -> Dict[str, Any]:
    try:
        service = CompetitorFinderService()

        # Use context to enhance search
        if context_package and context_package.get("research_profile"):
            profile = context_package["research_profile"]
            if not field and profile.get("primary_fields"):
                field = profile["primary_fields"][0]
            if not topics and profile.get("recent_topics"):
                topics = profile["recent_topics"][:3]

        # Extract research focus from paper text if provided
        if paper_text:
            focus = service.extract_research_focus(paper_text)
            keywords = focus.get("search_keywords", topics or [])
            domain = focus.get("domain", field or "")
            arxiv_cats = focus.get("arxiv_categories", [])
        elif topics:
            keywords = topics
            domain = field or ""
            arxiv_cats = []
        else:
            return make_result_envelope(
                service="competitor_finder",
                status="error",
                error="No topics or paper text provided for competitor search.",
            )

        # Call the actual service methods with correct signatures
        openalex_results = service.search_openalex_competitors(keywords, domain)
        arxiv_results = service.search_arxiv_preprints(keywords, arxiv_cats)
        nih_results = service.search_nih_grants(keywords, domain)

        total_competitors = len(openalex_results) + len(arxiv_results) + len(nih_results)
        if total_competitors > 15:
            urgency = "HIGH"
        elif total_competitors > 8:
            urgency = "MEDIUM-HIGH"
        elif total_competitors > 4:
            urgency = "MEDIUM"
        else:
            urgency = "LOW"

        full_results = {
            "domain": domain,
            "keywords": keywords,
            "competing_labs": openalex_results,
            "preprints": arxiv_results,
            "active_grants": nih_results,
            "urgency": urgency,
            "total_competitors": total_competitors,
        }

        return make_result_envelope(
            service="competitor_finder",
            status="success",
            full_results=full_results,
        )
    except Exception as e:
        logger.error(f"Competitor finder adapter error: {e}", exc_info=True)
        return make_result_envelope(
            service="competitor_finder",
            status="error",
            error=f"Competitor search failed: {str(e)}",
        )
