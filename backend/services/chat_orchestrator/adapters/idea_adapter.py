"""Adapter wrapping IdeaRealityService for the orchestrator."""

import logging
from typing import Dict, Any, Optional

from services.idea_reality_service import IdeaRealityService
from . import make_result_envelope

logger = logging.getLogger(__name__)


def run_idea_reality(
    idea_description: str,
    context_package: Optional[Dict] = None,
) -> Dict[str, Any]:
    try:
        service = IdeaRealityService()
        result = service.check_idea(idea_description)

        if context_package and context_package.get("research_profile"):
            profile = context_package["research_profile"]
            institution = profile.get("institution", "").lower()
            if institution and result.get("competitors"):
                result["competitors"] = [
                    c for c in result["competitors"]
                    if institution not in (c.get("owner", "") or "").lower()
                ]

        return make_result_envelope(
            service="idea_reality",
            status="success",
            full_results=result,
        )
    except Exception as e:
        logger.error(f"Idea reality adapter error: {e}", exc_info=True)
        return make_result_envelope(
            service="idea_reality",
            status="error",
            error=f"Idea validation failed: {str(e)}",
        )
