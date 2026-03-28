"""Response Merger — generates personalized tabbed summaries from service results."""

import json
import logging
from typing import Dict, Any, List, Optional

from azure_openai_config import get_azure_client, AZURE_CHAT_DEPLOYMENT

logger = logging.getLogger(__name__)

SERVICE_LABELS = {
    "hij": {"label": "Manuscript Score", "icon": "file-text"},
    "competitor_finder": {"label": "Competitors", "icon": "search"},
    "idea_reality": {"label": "Idea Check", "icon": "lightbulb"},
    "co_researcher": {"label": "Co-Researcher", "icon": "flask-conical"},
}


def merge(
    results: List[Dict[str, Any]],
    research_profile: Optional[Dict] = None,
    user_message: str = "",
) -> Dict[str, Any]:
    if not results:
        return {"type": "power_result", "tabs": [], "followup_suggestions": []}

    tabs = []
    successful_results = []

    for result in results:
        service = result["service"]
        meta = SERVICE_LABELS.get(service, {"label": service, "icon": "zap"})

        if result["status"] != "success":
            tabs.append({
                "label": meta["label"],
                "icon": meta["icon"],
                "status": result["status"],
                "summary": result.get("error", "Service unavailable. Try the standalone version."),
                "full_results": None,
            })
        else:
            successful_results.append(result)
            tabs.append({
                "label": meta["label"],
                "icon": meta["icon"],
                "status": "success",
                "summary": None,
                "full_results": result.get("full_results"),
            })

    if successful_results:
        summaries = _generate_summaries(successful_results, research_profile, user_message)
        summary_idx = 0
        for tab in tabs:
            if tab["status"] == "success" and summary_idx < len(summaries):
                tab["summary"] = summaries[summary_idx]
                summary_idx += 1

    followup_suggestions = _generate_followups(results, research_profile)

    return {
        "type": "power_result",
        "tabs": tabs,
        "followup_suggestions": followup_suggestions,
    }


def _generate_summaries(
    results: List[Dict],
    research_profile: Optional[Dict],
    user_message: str,
) -> List[str]:
    try:
        client = get_azure_client()

        profile_context = ""
        if research_profile:
            fields = ", ".join(research_profile.get("primary_fields", []))
            topics = ", ".join(research_profile.get("recent_topics", []))
            profile_context = f"Researcher's fields: {fields}. Recent topics: {topics}."

        results_text = []
        for r in results:
            service = r["service"]
            full = r.get("full_results", {})
            results_text.append(f"Service: {service}\nResults: {json.dumps(full, default=str)[:3000]}")

        response = client.chat.completions.create(
            model=AZURE_CHAT_DEPLOYMENT,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Generate concise, personalized summaries for research analysis results. "
                        "Each summary should be 2-4 sentences, use markdown formatting, and reference "
                        "the researcher's context when relevant. "
                        "Return a JSON array of strings, one summary per result.\n"
                        f"Researcher context: {profile_context}\n"
                        f"User's question: {user_message}"
                    ),
                },
                {
                    "role": "user",
                    "content": "\n\n---\n\n".join(results_text),
                },
            ],
            temperature=0.5,
            max_tokens=1500,
        )

        raw = response.choices[0].message.content.strip()
        try:
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
            summaries = json.loads(raw)
            if isinstance(summaries, list):
                return [str(s) for s in summaries]
        except json.JSONDecodeError:
            pass

        return [raw] * len(results)

    except Exception as e:
        logger.error(f"Summary generation failed: {e}")
        return ["Analysis complete. Click 'View full analysis' for details."] * len(results)


def _generate_followups(
    results: List[Dict],
    research_profile: Optional[Dict],
) -> List[str]:
    ran_services = {r["service"] for r in results if r["status"] == "success"}
    all_services = {"hij", "competitor_finder", "idea_reality", "co_researcher"}
    not_run = all_services - ran_services

    suggestions = []
    if "competitor_finder" in not_run and "hij" in ran_services:
        suggestions.append("Want me to find competitors in this research area?")
    if "idea_reality" in not_run:
        suggestions.append("Should I check if your research idea is novel?")
    if "co_researcher" in not_run:
        suggestions.append("Want me to brainstorm research hypotheses?")
    if "hij" in not_run:
        suggestions.append("Would you like me to score a manuscript?")

    return suggestions[:3]
