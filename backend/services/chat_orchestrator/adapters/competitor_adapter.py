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
        keywords = None
        if context_package and context_package.get("research_profile"):
            profile = context_package["research_profile"]
            if not field and profile.get("primary_fields"):
                field = profile["primary_fields"][0]
            if not topics and profile.get("recent_topics"):
                topics = profile["recent_topics"][:3]

        if paper_text:
            topic_info = service._extract_topic(paper_text, field or "", keywords)
        elif topics:
            topic_info = {
                "topic": topics[0] if topics else "",
                "search_queries": topics,
                "key_terms": topics,
                "field": field or "",
                "arxiv_categories": [],
            }
        else:
            return make_result_envelope(
                service="competitor_finder",
                status="error",
                error="No topics or paper text provided for competitor search.",
            )

        openalex_results = service._search_openalex(topic_info)
        arxiv_results = service._search_arxiv(topic_info)
        nih_results = service._search_nih(topic_info)

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
            "topic_info": topic_info,
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
