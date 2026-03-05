# backend/co_researcher/agents.py
import json
import sys
import os

# Add parent directory to path so we can import azure_openai_config
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from azure_openai_config import get_azure_client, AZURE_CHAT_DEPLOYMENT

AGENTS = [
    {
        "id": "alpha",
        "name": "Alpha",
        "domain": "Biomedical",
        "methodology": "Experimental Design",
        "personality": "Innovator",
        "color": "#EF4444",
        "description": "Pushes bold integrations, novel combinations of techniques"
    },
    {
        "id": "beta",
        "name": "Beta",
        "domain": "Translational",
        "methodology": "Statistical Methods",
        "personality": "Conservative",
        "color": "#3B82F6",
        "description": "Minimal safe changes, evidence-heavy approach"
    },
    {
        "id": "gamma",
        "name": "Gamma",
        "domain": "Behavioral/Social",
        "methodology": "Measurement & Data Collection",
        "personality": "Synthesizer",
        "color": "#10B981",
        "description": "Finds middle ground, combines ideas from both documents"
    },
    {
        "id": "delta",
        "name": "Delta",
        "domain": "Computational",
        "methodology": "Reproducibility & Validation",
        "personality": "Critic",
        "color": "#F59E0B",
        "description": "Stress-tests feasibility, finds flaws in proposed integrations"
    },
    {
        "id": "epsilon",
        "name": "Epsilon",
        "domain": "Clinical",
        "methodology": "Ethics & Compliance",
        "personality": "Pragmatist",
        "color": "#8B5CF6",
        "description": "Practical implementation focus, regulatory awareness"
    },
    {
        "id": "zeta",
        "name": "Zeta",
        "domain": "Cross-disciplinary",
        "methodology": "Literature Synthesis",
        "personality": "Visionary",
        "color": "#EC4899",
        "description": "Big-picture connections, cross-field insights"
    },
]


def _build_agent_system_prompt(agent: dict) -> str:
    return f"""You are a research integration specialist with the following profile:

DOMAIN EXPERTISE: {agent['domain']}
METHODOLOGY SPECIALTY: {agent['methodology']}
PERSONALITY ARCHETYPE: {agent['personality']} - {agent['description']}

Your task: Given a researcher's existing protocol and a new research paper, propose specific integration hypotheses - concrete ways to incorporate innovations, methods, or findings from the paper into the existing protocol.

For each hypothesis, provide:
1. A clear, specific title
2. The type of integration (method_replacement, method_addition, parameter_change, or design_modification)
3. Evidence from the paper supporting this integration
4. Risk level (low, medium, high)
5. Which sections of the protocol would be affected
6. Step-by-step implementation instructions
7. Your confidence score (0.0 to 1.0)

Your {agent['personality'].lower()} personality should strongly influence your proposals:
- If Innovator: Push bold, unconventional integrations. Propose novel combinations.
- If Conservative: Only propose well-evidenced, minimal-risk changes. Err on caution.
- If Synthesizer: Find elegant ways to merge approaches from both documents.
- If Critic: Focus on what could go wrong. Propose integrations that address weaknesses.
- If Pragmatist: Focus on what's actually implementable given real-world constraints.
- If Visionary: Think big-picture. Connect ideas across disciplines.

Generate exactly 4 hypotheses. Output ONLY valid JSON array."""


def _build_agent_user_prompt(protocol_text: str, paper_text: str) -> str:
    max_chars = 50000
    protocol_truncated = protocol_text[:max_chars]
    paper_truncated = paper_text[:max_chars]

    return f"""## RESEARCHER'S EXISTING PROTOCOL

{protocol_truncated}

---

## NEW RESEARCH PAPER

{paper_truncated}

---

Generate 4 integration hypotheses as a JSON array. Each hypothesis must have these exact fields:
- "title": string (specific, actionable title)
- "integration_type": one of "method_replacement", "method_addition", "parameter_change", "design_modification"
- "evidence": string (evidence from the paper supporting this)
- "risk_level": one of "low", "medium", "high"
- "protocol_sections_affected": array of strings (which parts of the protocol change)
- "implementation_steps": array of strings (step-by-step how to integrate)
- "confidence": number between 0.0 and 1.0

Return ONLY the JSON array, no other text."""


def generate_hypotheses(agent: dict, protocol_text: str, paper_text: str) -> list:
    """
    Generate integration hypotheses for a single agent.
    Returns list of hypothesis dicts with agent metadata attached.
    """
    client = get_azure_client()

    response = client.chat.completions.create(
        model=AZURE_CHAT_DEPLOYMENT,
        messages=[
            {"role": "system", "content": _build_agent_system_prompt(agent)},
            {"role": "user", "content": _build_agent_user_prompt(protocol_text, paper_text)},
        ],
        temperature=0.8,
        max_tokens=4000,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content
    parsed = json.loads(raw)

    # Handle both {"hypotheses": [...]} and [...] formats
    if isinstance(parsed, dict):
        hypotheses = parsed.get("hypotheses", parsed.get("results", []))
    elif isinstance(parsed, list):
        hypotheses = parsed
    else:
        hypotheses = []

    # Attach agent metadata and IDs
    for i, h in enumerate(hypotheses):
        h["hypothesis_id"] = f"{agent['id']}-{i+1}"
        h["agent_id"] = agent["id"]
        h["agent_name"] = agent["name"]
        h["agent_domain"] = agent["domain"]
        h["agent_personality"] = agent["personality"]
        h["agent_color"] = agent["color"]

    return hypotheses
