# backend/co_researcher/tournament.py
import json
import random
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from azure_openai_config import get_azure_client, AZURE_CHAT_DEPLOYMENT


def calculate_elo(winner_elo: float, loser_elo: float, k: int = 32, draw: bool = False) -> tuple:
    """Standard ELO calculation. Returns (new_winner_elo, new_loser_elo)."""
    expected_winner = 1.0 / (1.0 + 10 ** ((loser_elo - winner_elo) / 400))
    expected_loser = 1.0 - expected_winner

    if draw:
        new_winner = winner_elo + k * (0.5 - expected_winner)
        new_loser = loser_elo + k * (0.5 - expected_loser)
    else:
        new_winner = winner_elo + k * (1.0 - expected_winner)
        new_loser = loser_elo + k * (0.0 - expected_loser)

    return round(new_winner), round(new_loser)


def generate_matchups(hypothesis_ids: list, rounds_per_hypothesis: int = 4) -> list:
    """Generate tournament matchups. Each hypothesis faces ~rounds_per_hypothesis opponents."""
    matchups = []
    n = len(hypothesis_ids)
    if n < 2:
        return []

    all_pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            all_pairs.append((hypothesis_ids[i], hypothesis_ids[j]))

    random.shuffle(all_pairs)
    target_total = (n * rounds_per_hypothesis) // 2
    matchups = all_pairs[:target_total]
    return matchups


EVALUATOR_SYSTEM_PROMPT = """You are an expert research evaluator. Your job is to compare two integration hypotheses and determine which one is stronger.

Consider these criteria:
1. SCIENTIFIC RIGOR: Is the evidence from the paper strong? Is the reasoning sound?
2. FEASIBILITY: Can this actually be implemented in the protocol?
3. IMPACT: How much would this improve the protocol?
4. RISK/BENEFIT: Does the benefit outweigh the risk?
5. SPECIFICITY: Is the hypothesis concrete and actionable?

You must output a JSON object with:
- "winner": "a" or "b" or "draw"
- "score": "decisive" (clear winner) or "narrow" (close) or "draw"
- "reasoning": A 2-3 sentence explanation of your judgment
- "criteria_scores": {"a": {"rigor": 1-5, "feasibility": 1-5, "impact": 1-5}, "b": {"rigor": 1-5, "feasibility": 1-5, "impact": 1-5}}

Output ONLY valid JSON."""


def evaluate_matchup(hypothesis_a: dict, hypothesis_b: dict, protocol_summary: str, paper_summary: str) -> dict:
    """Run a head-to-head evaluation of two hypotheses."""
    client = get_azure_client()

    user_prompt = f"""## Context
Protocol summary: {protocol_summary[:3000]}
Paper summary: {paper_summary[:3000]}

## Hypothesis A: "{hypothesis_a['title']}"
Agent: {hypothesis_a.get('agent_name', '?')} ({hypothesis_a.get('agent_personality', '?')})
Type: {hypothesis_a.get('integration_type', '?')}
Evidence: {hypothesis_a.get('evidence', '?')}
Risk: {hypothesis_a.get('risk_level', '?')}
Steps: {json.dumps(hypothesis_a.get('implementation_steps', []))}
Confidence: {hypothesis_a.get('confidence', '?')}

## Hypothesis B: "{hypothesis_b['title']}"
Agent: {hypothesis_b.get('agent_name', '?')} ({hypothesis_b.get('agent_personality', '?')})
Type: {hypothesis_b.get('integration_type', '?')}
Evidence: {hypothesis_b.get('evidence', '?')}
Risk: {hypothesis_b.get('risk_level', '?')}
Steps: {json.dumps(hypothesis_b.get('implementation_steps', []))}
Confidence: {hypothesis_b.get('confidence', '?')}

Compare these two hypotheses. Which is a stronger integration recommendation?"""

    response = client.chat.completions.create(
        model=AZURE_CHAT_DEPLOYMENT,
        messages=[
            {"role": "system", "content": EVALUATOR_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
        max_tokens=500,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content
    result = json.loads(raw)
    return result
