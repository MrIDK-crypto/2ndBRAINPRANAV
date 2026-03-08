"""
Feasibility Scorer — Score experiment suggestions on multiple dimensions:
resource availability, timeline realism, statistical power, and novelty.
"""


class FeasibilityScorer:
    """Score experiment feasibility across multiple dimensions."""

    def score(self, suggestion: dict, available_resources: list = None,
              constraints: dict = None) -> dict:
        """Score experiment feasibility 0-1 across dimensions.

        Args:
            suggestion: Experiment suggestion dict with required_resources,
                       missing_resources, expected_duration_weeks, controls,
                       statistical_approach, novelty, risk_level
            available_resources: List of available resource dicts [{name, type, attributes}]
            constraints: {budget_usd, timeline_weeks, personnel_count}

        Returns:
            Dict with overall score, dimension scores, and feasibility tier
        """
        available_resources = available_resources or []
        constraints = constraints or {}

        # 1. Resource match (0-1): What fraction of required resources are available?
        required = [r.lower() for r in suggestion.get('required_resources', [])]
        available_names = set(r.get('name', '').lower() for r in available_resources)
        missing = [r.lower() for r in suggestion.get('missing_resources', [])]

        if required:
            matched = sum(1 for r in required
                         if any(a in r or r in a for a in available_names))
            resource_score = matched / len(required)
        else:
            resource_score = 0.5  # Unknown requirements

        # Penalize for explicitly missing resources
        if missing:
            resource_score *= max(0.3, 1 - len(missing) * 0.15)

        # 2. Timeline feasibility (0-1)
        duration = suggestion.get('expected_duration_weeks', 4)
        max_weeks = constraints.get('timeline_weeks', 52)
        if duration <= max_weeks:
            timeline_score = 1.0
        else:
            timeline_score = max(0.2, 1 - (duration - max_weeks) / max(max_weeks, 1))

        # 3. Statistical power (0-1): Based on presence of controls and statistical approach
        stat_score = 0.4  # Base
        controls = suggestion.get('controls', [])
        stat_approach = suggestion.get('statistical_approach', '')

        if controls:
            stat_score += min(0.3, len(controls) * 0.1)
        if stat_approach:
            stat_score += 0.2
            if any(term in stat_approach.lower() for term in ['power analysis', 'sample size', 'effect size']):
                stat_score += 0.1
        stat_score = min(1.0, stat_score)

        # 4. Novelty score (0-1)
        novelty_map = {'low': 0.2, 'incremental': 0.3, 'moderate': 0.6, 'high': 0.9}
        novelty_score = novelty_map.get(suggestion.get('novelty', 'moderate'), 0.5)

        # 5. Risk penalty
        risk_map = {'low': 0.0, 'medium': 0.1, 'high': 0.25}
        risk_penalty = risk_map.get(suggestion.get('risk_level', 'medium'), 0.1)

        # Overall: weighted average minus risk
        overall = round(
            resource_score * 0.35 +
            timeline_score * 0.25 +
            stat_score * 0.20 +
            novelty_score * 0.20 -
            risk_penalty, 2
        )
        overall = max(0.0, min(1.0, overall))

        # Determine tier
        if overall >= 0.7:
            tier = 'high'
        elif overall >= 0.4:
            tier = 'medium'
        else:
            tier = 'low'

        return {
            'overall': overall,
            'resource_match': round(resource_score, 2),
            'timeline': round(timeline_score, 2),
            'statistical_power': round(stat_score, 2),
            'novelty': round(novelty_score, 2),
            'risk_penalty': round(risk_penalty, 2),
            'feasibility_tier': tier,
        }
