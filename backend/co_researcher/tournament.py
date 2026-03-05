import json
import random
import sys
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

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
    """Generate tournament matchups (legacy, cross-category)."""
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


def generate_category_matchups(hypothesis_ids_by_category: dict) -> list:
    """Generate round-robin matchups within each category.

    Returns list of (id_a, id_b, category) tuples.
    Within each category, every hypothesis faces every other (exhaustive).
    """
    matchups = []
    for category, ids in hypothesis_ids_by_category.items():
        n = len(ids)
        if n < 2:
            continue
        category_pairs = []
        for i in range(n):
            for j in range(i + 1, n):
                category_pairs.append((ids[i], ids[j], category))
        random.shuffle(category_pairs)
        matchups.extend(category_pairs)
    return matchups


EVALUATOR_SYSTEM_PROMPT = """You are an expert research evaluator comparing two integration hypotheses within the SAME category.

Both hypotheses propose changes in the same domain. Compare them on:

1. EVIDENCE QUALITY: Is the cited evidence from the paper accurate and relevant? Has it been verified? Does a direct quote from the paper support the claim?
2. SCIENTIFIC RIGOR: Is the reasoning sound? Are there logical gaps or unsupported leaps?
3. FEASIBILITY: Can this realistically be implemented in this protocol without derailing the study?
4. IMPACT: How much would this genuinely improve the protocol's outcomes or methodology?
5. SPECIFICITY: Is this concrete and actionable, or vague and hand-wavy?

IMPORTANT: A hypothesis with verified evidence (evidence_verified=true, with a supporting quote) should be weighted higher than one with unverified claims. Do NOT favor an idea just because it sounds impressive — groundedness matters more than ambition.

Output ONLY valid JSON:
- "winner": "a" or "b" or "draw"
- "score": "decisive" (clear winner) or "narrow" (close) or "draw"
- "reasoning": 2-3 sentence explanation citing specific strengths/weaknesses
- "criteria_scores": {"a": {"evidence": 1-5, "rigor": 1-5, "feasibility": 1-5, "impact": 1-5, "specificity": 1-5}, "b": {"evidence": 1-5, "rigor": 1-5, "feasibility": 1-5, "impact": 1-5, "specificity": 1-5}}"""


def evaluate_matchup(hypothesis_a: dict, hypothesis_b: dict, protocol_summary: str, paper_summary: str) -> dict:
    """Run a head-to-head evaluation of two hypotheses."""
    client = get_azure_client()

    user_prompt = f"""## Protocol Context
{protocol_summary}

## Paper Context
{paper_summary}

## Hypothesis A: "{hypothesis_a['title']}"
Type: {hypothesis_a.get('integration_type', '?')}
Evidence claimed: {hypothesis_a.get('evidence', '?')}
Evidence verified: {hypothesis_a.get('evidence_verified', 'unknown')}
Supporting quote: {hypothesis_a.get('evidence_quote', 'none')[:300]}
Risk: {hypothesis_a.get('risk_level', '?')}
Steps: {json.dumps(hypothesis_a.get('implementation_steps', []))}
Critical review: {hypothesis_a.get('critique', 'none')}
Viability: {hypothesis_a.get('viability_score', '?')}

## Hypothesis B: "{hypothesis_b['title']}"
Type: {hypothesis_b.get('integration_type', '?')}
Evidence claimed: {hypothesis_b.get('evidence', '?')}
Evidence verified: {hypothesis_b.get('evidence_verified', 'unknown')}
Supporting quote: {hypothesis_b.get('evidence_quote', 'none')[:300]}
Risk: {hypothesis_b.get('risk_level', '?')}
Steps: {json.dumps(hypothesis_b.get('implementation_steps', []))}
Critical review: {hypothesis_b.get('critique', 'none')}
Viability: {hypothesis_b.get('viability_score', '?')}

Compare these hypotheses. Which is a stronger, more well-grounded recommendation?"""

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


def evaluate_matchup_debiased(hypothesis_a: dict, hypothesis_b: dict, protocol_summary: str, paper_summary: str) -> dict:
    """Run matchup twice with swapped presentation order.

    Evaluates A-vs-B and B-vs-A in parallel.
    Only counts as decisive if both evaluations agree on the winner.
    If they disagree, position bias is detected and the result is a draw.
    """
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_ab = executor.submit(
            evaluate_matchup, hypothesis_a, hypothesis_b, protocol_summary, paper_summary
        )
        future_ba = executor.submit(
            evaluate_matchup, hypothesis_b, hypothesis_a, protocol_summary, paper_summary
        )
        result_ab = future_ab.result()
        result_ba = future_ba.result()

    winner_ab = result_ab.get("winner")
    winner_ba = result_ba.get("winner")

    # Translate BA result back to AB frame
    if winner_ba == "a":
        winner_ba_translated = "b"
    elif winner_ba == "b":
        winner_ba_translated = "a"
    else:
        winner_ba_translated = "draw"

    if winner_ab == winner_ba_translated:
        # Both evaluations agree
        result_ab["debiased"] = True
        result_ab["agreement"] = True
        return result_ab
    else:
        # Disagreement = position bias detected, treat as draw
        return {
            "winner": "draw",
            "score": "draw",
            "reasoning": f"Position bias detected: forward evaluation chose '{winner_ab}', reverse chose '{winner_ba_translated}'. Treating as draw to ensure fairness.",
            "criteria_scores": result_ab.get("criteria_scores", {}),
            "debiased": True,
            "agreement": False,
        }
