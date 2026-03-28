"""Adapter wrapping JournalScorerService for the orchestrator."""

import logging
from typing import Dict, Any, Optional

from services.journal_scorer_service import JournalScorerService
from . import parse_sse_stream, make_result_envelope

logger = logging.getLogger(__name__)


def run_hij(
    file_bytes: Optional[bytes] = None,
    filename: Optional[str] = None,
    raw_text: Optional[str] = None,
    context_package: Optional[Dict] = None,
) -> Dict[str, Any]:
    try:
        service = JournalScorerService()
        publication_year = None
        if context_package and context_package.get("research_profile"):
            profile = context_package["research_profile"]

        generator = service.analyze_manuscript(
            file_bytes=file_bytes,
            filename=filename or "manuscript.pdf",
            raw_text=raw_text,
            user_publication_year=publication_year,
        )

        events = parse_sse_stream(generator)
        full_results = _extract_hij_results(events)

        return make_result_envelope(
            service="hij",
            status="success",
            full_results=full_results,
        )
    except Exception as e:
        logger.error(f"HIJ adapter error: {e}", exc_info=True)
        return make_result_envelope(
            service="hij",
            status="error",
            error=f"Manuscript analysis failed: {str(e)}",
        )


def _extract_hij_results(events: list) -> Dict[str, Any]:
    results = {
        "scores": None,
        "journal_matches": None,
        "red_flags": None,
        "field_detection": None,
        "citations": None,
        "recommendations": None,
        "raw_events": [],
    }
    for event in events:
        event_type = event.get("event", "")
        data = event.get("data", {})
        if isinstance(data, dict):
            results["raw_events"].append(event)
            if event_type == "scores" or "score" in str(data.get("type", "")):
                results["scores"] = data
            elif event_type == "journals" or "journal" in str(data.get("type", "")):
                results["journal_matches"] = data
            elif event_type == "red_flags" or "red_flag" in str(data.get("type", "")):
                results["red_flags"] = data
            elif event_type == "field" or "field" in str(data.get("type", "")):
                results["field_detection"] = data
            elif event_type == "citations":
                results["citations"] = data
            elif event_type == "recommendations" or event_type == "final":
                results["recommendations"] = data
    return results
