# backend/co_researcher/report_generator.py
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from azure_openai_config import get_azure_client, AZURE_CHAT_DEPLOYMENT


def generate_report(top_hypotheses: list, pinned_hypotheses: list, protocol_text: str, paper_text: str, debate_history: list) -> dict:
    """Generate a structured recommendations report from the top-ranked hypotheses."""
    client = get_azure_client()

    all_recommendations = top_hypotheses + [h for h in pinned_hypotheses if h not in top_hypotheses]

    hypotheses_text = ""
    for i, h in enumerate(all_recommendations):
        hypotheses_text += f"""
### Recommendation {i+1}: {h['title']}
- ELO Rating: {h.get('elo', 1200)}
- Agent: {h.get('agent_name', '?')} ({h.get('agent_personality', '?')})
- Type: {h.get('integration_type', '?')}
- Risk: {h.get('risk_level', '?')}
- Evidence: {h.get('evidence', '?')}
- Steps: {json.dumps(h.get('implementation_steps', []))}
- Tournament Record: {h.get('wins', 0)}W-{h.get('losses', 0)}L
"""

    response = client.chat.completions.create(
        model=AZURE_CHAT_DEPLOYMENT,
        messages=[
            {"role": "system", "content": """You are an expert research protocol consultant. Generate a comprehensive integration report based on the tournament results. Structure the report with:
1. Executive Summary (2-3 sentences)
2. Top Recommendations (numbered, with priority/risk/impact for each)
3. Implementation Roadmap (suggested order of integration)
4. Risk Assessment (what could go wrong, mitigation strategies)
5. Expected Outcomes (how the protocol improves)

Write in clear, professional academic language. Be specific and actionable."""},
            {"role": "user", "content": f"""Protocol (first 5000 chars):
{protocol_text[:5000]}

Paper (first 5000 chars):
{paper_text[:5000]}

Tournament-Ranked Recommendations:
{hypotheses_text}

Generate the integration report."""},
        ],
        temperature=0.4,
        max_tokens=3000,
    )

    return {
        "report_markdown": response.choices[0].message.content,
        "recommendations": all_recommendations,
    }


def generate_revised_protocol(top_hypotheses: list, protocol_text: str) -> str:
    """Generate a revised version of the protocol incorporating the top hypotheses."""
    client = get_azure_client()

    changes_text = "\n".join([
        f"- {h['title']}: {json.dumps(h.get('implementation_steps', []))}"
        for h in top_hypotheses
    ])

    response = client.chat.completions.create(
        model=AZURE_CHAT_DEPLOYMENT,
        messages=[
            {"role": "system", "content": """You are an expert protocol editor. Revise the given research protocol by integrating the recommended changes.

Mark ALL modifications with [ADDED] or [MODIFIED] tags so the researcher can see exactly what changed. Preserve the original structure and formatting as much as possible. Only change sections that are directly affected by the recommendations."""},
            {"role": "user", "content": f"""Original Protocol:
{protocol_text[:30000]}

Changes to integrate:
{changes_text}

Generate the revised protocol with tracked changes."""},
        ],
        temperature=0.3,
        max_tokens=6000,
    )

    return response.choices[0].message.content
