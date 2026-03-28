"""Adapter wrapping CoResearcherService for the orchestrator (one-shot, no persistent session)."""

import json
import logging
from typing import Dict, Any, Optional

from services.co_researcher_service import CoResearcherService
from . import make_result_envelope

logger = logging.getLogger(__name__)


def run_co_researcher(
    research_question: str,
    paper_text: Optional[str] = None,
    protocol_text: Optional[str] = None,
    context_package: Optional[Dict] = None,
    tenant_id: Optional[str] = None,
) -> Dict[str, Any]:
    try:
        service = CoResearcherService()
        enriched_message = research_question

        if context_package and context_package.get("research_profile"):
            profile = context_package["research_profile"]
            fields = ", ".join(profile.get("primary_fields", []))
            topics = ", ".join(profile.get("recent_topics", []))
            if fields or topics:
                enriched_message = (
                    f"[Research context: fields={fields}, recent topics={topics}]\n\n"
                    f"{research_question}"
                )

        if paper_text:
            enriched_message += f"\n\n[Paper excerpt]: {paper_text[:3000]}"
        if protocol_text:
            enriched_message += f"\n\n[Protocol excerpt]: {protocol_text[:3000]}"

        from azure_openai_config import get_azure_client, AZURE_CHAT_DEPLOYMENT
        client = get_azure_client()

        response = client.chat.completions.create(
            model=AZURE_CHAT_DEPLOYMENT,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a research co-pilot. Given the user's research question and context, "
                        "generate 3-5 structured research hypotheses. For each hypothesis provide:\n"
                        "1. Title\n2. Description\n3. Methodology approach\n"
                        "4. Expected outcome\n5. Risk assessment (low/medium/high)\n"
                        "6. Implementation steps (3-5 concrete steps)\n"
                        "Format as JSON array."
                    ),
                },
                {"role": "user", "content": enriched_message},
            ],
            temperature=0.8,
            max_tokens=3000,
        )

        raw_text = response.choices[0].message.content
        try:
            clean = raw_text.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1]
                clean = clean.rsplit("```", 1)[0]
            hypotheses = json.loads(clean)
        except json.JSONDecodeError:
            hypotheses = [{"title": "Research Analysis", "description": raw_text}]

        full_results = {
            "hypotheses": hypotheses,
            "research_question": research_question,
            "context_used": bool(context_package),
        }

        return make_result_envelope(
            service="co_researcher",
            status="success",
            full_results=full_results,
        )
    except Exception as e:
        logger.error(f"Co-researcher adapter error: {e}", exc_info=True)
        return make_result_envelope(
            service="co_researcher",
            status="error",
            error=f"Research analysis failed: {str(e)}",
        )
