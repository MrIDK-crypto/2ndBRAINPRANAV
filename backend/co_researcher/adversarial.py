"""
adversarial.py — Phase 4 of the Research Translator pipeline.

Four role-based agents stress-test each translation proposal in parallel.
Each agent tries to break the translation from a different angle.
"""

import json
import sys
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from azure_openai_config import get_azure_client, AZURE_CHAT_DEPLOYMENT


ADVERSARIAL_AGENTS = [
    {
        "id": "skeptic",
        "name": "Skeptic",
        "color": "#EF4444",
        "role": "Break the translation",
        "system_prompt": """You are a harsh scientific critic. Your ONLY job is to BREAK this cross-domain translation proposal.

Look for:
- Assumptions that probably don't hold in the target domain
- Forced analogies where the mapping is superficial (structural similarity without mechanistic equivalence)
- Cases where the principle transfers at L4 but the implementation can't work at L2/L1
- Biochemical, physical, or practical reasons the lower-layer mapping would fail
- Logical gaps: does the target mapping actually test what the source insight claims?

Do NOT be encouraging. Do NOT say "this is interesting but..." — your job is to find the fatal flaw.

Output ONLY valid JSON:
{
  "verdict": "survives" | "vulnerable" | "fatal",
  "attack": "2-3 sentences describing your specific critique",
  "weakest_layer": "L1" | "L2" | "L3" | "L4",
  "what_would_change_my_mind": "what evidence or argument would make you reconsider"
}"""
    },
    {
        "id": "prior_art",
        "name": "Prior Art",
        "color": "#3B82F6",
        "role": "Check novelty and precedent",
        "system_prompt": """You are a literature expert evaluating whether this cross-domain translation has precedent.

Consider:
- Has anyone applied this source methodology to the target field before?
- Are there "bridge" papers that connect these two domains?
- If similar cross-domain work exists, did it succeed or fail? Why?
- If no precedent exists, is that because (a) no one thought of it, (b) it's technically infeasible, or (c) it was tried and didn't work?
- Is the proposed translation genuinely novel, or is it standard practice in the target field dressed up as a cross-domain insight?

Output ONLY valid JSON:
{
  "verdict": "survives" | "vulnerable" | "fatal",
  "attack": "2-3 sentences about what you found or didn't find",
  "precedent_exists": true | false,
  "bridge_papers_hint": "describe what to search for in PubMed/Google Scholar, or cite known examples",
  "what_would_change_my_mind": "what evidence would make you reconsider"
}"""
    },
    {
        "id": "feasibility",
        "name": "Feasibility",
        "color": "#10B981",
        "role": "Check practical constraints",
        "system_prompt": """You are a practical experimentalist evaluating whether this translation can actually be DONE.

Consider:
- Do the required reagents, constructs, cell lines, or datasets exist?
- Based on the target paper's methods section, does this lab have the necessary techniques?
- What's the experimental bottleneck — time, cost, technical difficulty, or equipment?
- Is the dynamic range of the target system sufficient to see the predicted effect?
- Are there regulatory, ethical, or safety barriers?

Output ONLY valid JSON:
{
  "verdict": "survives" | "vulnerable" | "fatal",
  "attack": "2-3 sentences about the specific practical concern",
  "bottleneck": "the single biggest practical obstacle",
  "estimated_difficulty": "straightforward" | "challenging" | "heroic",
  "what_would_change_my_mind": "what evidence would make you reconsider"
}"""
    },
    {
        "id": "impact",
        "name": "Impact",
        "color": "#F59E0B",
        "role": "Assess payoff and novelty",
        "system_prompt": """You are a grant reviewer evaluating the potential impact of this cross-domain translation.

Consider:
- If this translation works perfectly, what does it actually reveal about the target system?
- Is this a genuinely NEW insight, or does the target field already know/assume this?
- Would this open a new research direction, or just confirm existing knowledge?
- Is the juice worth the squeeze — does the effort justify the expected insight?
- Would reviewers/editors find this interesting, or would they shrug?

Output ONLY valid JSON:
{
  "verdict": "survives" | "vulnerable" | "fatal",
  "attack": "2-3 sentences with honest assessment",
  "novelty": "high" | "moderate" | "low",
  "potential_impact": "what this could lead to if it works",
  "what_would_change_my_mind": "what evidence would make you reconsider"
}"""
    },
]


def run_single_agent(agent: dict, translation: dict, source_context: dict, target_context: dict) -> dict:
    """Run a single adversarial agent against one translation."""
    client = get_azure_client()

    user_prompt = f"""## Translation Proposal
Title: {translation.get('title', 'Untitled')}
Source insight: {translation.get('source_insight', '')}

## Layer-by-Layer Mapping
"""
    for layer in translation.get("layers", []):
        user_prompt += f"""
{layer.get('level', '?')}:
  Source: {layer.get('source', '')}
  Target: {layer.get('target', '')}
  Confidence: {layer.get('confidence', '?')}
  Assumption: {layer.get('assumption', '')}
  Breaks if: {layer.get('breaks_if', '')}
"""

    user_prompt += f"""
Overall break point: {translation.get('overall_break_point', '')}
What to test first: {translation.get('what_to_test_first', '')}

## Source Paper Context
Domain: {source_context.get('domain', 'Unknown')}

## Target Paper Context
Domain: {target_context.get('domain', 'Unknown')}
Experimental systems: {', '.join(target_context.get('experimental_systems', []))}
Available techniques: {', '.join(target_context.get('available_techniques', []))}

Evaluate this translation from your perspective."""

    response = client.chat.completions.create(
        model=AZURE_CHAT_DEPLOYMENT,
        messages=[
            {"role": "system", "content": agent["system_prompt"]},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
        max_tokens=600,
        response_format={"type": "json_object"},
    )

    result = json.loads(response.choices[0].message.content)

    # Attach agent metadata
    result["agent_id"] = agent["id"]
    result["agent_name"] = agent["name"]
    result["agent_color"] = agent["color"]
    result["agent_role"] = agent["role"]

    # Ensure required fields
    result.setdefault("verdict", "vulnerable")
    result.setdefault("attack", "")
    result.setdefault("what_would_change_my_mind", "")

    return result


def run_adversarial(translation: dict, source_context: dict, target_context: dict) -> dict:
    """Run all 4 adversarial agents in parallel against a single translation.

    Returns:
        dict with:
            translation_title: str
            verdicts: list of 4 agent result dicts
            survival_score: int (count of "survives" verdicts, 0-4)
            has_fatal: bool (any agent returned "fatal")
    """
    verdicts = []

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(
                run_single_agent, agent, translation, source_context, target_context
            ): agent
            for agent in ADVERSARIAL_AGENTS
        }

        for future in as_completed(futures):
            agent = futures[future]
            try:
                result = future.result()
                verdicts.append(result)
            except Exception as e:
                verdicts.append({
                    "agent_id": agent["id"],
                    "agent_name": agent["name"],
                    "agent_color": agent["color"],
                    "agent_role": agent["role"],
                    "verdict": "vulnerable",
                    "attack": f"Evaluation failed: {str(e)}",
                    "what_would_change_my_mind": "",
                })

    survival_score = sum(1 for v in verdicts if v.get("verdict") == "survives")
    has_fatal = any(v.get("verdict") == "fatal" for v in verdicts)

    return {
        "translation_title": translation.get("title", "Untitled"),
        "verdicts": verdicts,
        "survival_score": survival_score,
        "has_fatal": has_fatal,
    }
