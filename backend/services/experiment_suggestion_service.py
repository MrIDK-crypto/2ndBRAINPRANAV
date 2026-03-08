"""
Experiment Suggestion Service — Generate experiment suggestions based on
research questions and available lab resources from the protocol knowledge graph.
"""

import json


class ExperimentSuggestionService:
    """Suggest experiments based on research questions and available resources."""

    def __init__(self, llm_client, chat_deployment: str):
        self.llm_client = llm_client
        self.chat_deployment = chat_deployment

    def suggest_experiments(self, research_question: str,
                           available_resources: list = None,
                           existing_results: list = None,
                           constraints: dict = None) -> list:
        """Suggest experiments based on research question and available resources.

        Args:
            research_question: The question to investigate
            available_resources: From protocol graph [{type, name, attributes}]
            existing_results: Previous experiment results to build on
            constraints: {budget_usd, timeline_weeks, personnel_count}

        Returns:
            List of experiment suggestion dicts
        """
        available_resources = available_resources or []
        existing_results = existing_results or []
        constraints = constraints or {}

        resource_text = ''
        if available_resources:
            resource_lines = []
            for r in available_resources[:30]:
                attrs = r.get('attributes', {})
                attr_str = ', '.join(f'{k}: {v}' for k, v in attrs.items()) if attrs else ''
                if attr_str:
                    resource_lines.append(f"- {r.get('entity_type', r.get('type', 'item'))}: {r.get('name', '')} ({attr_str})")
                else:
                    resource_lines.append(f"- {r.get('entity_type', r.get('type', 'item'))}: {r.get('name', '')}")
            resource_text = '\n\nAvailable lab resources:\n' + '\n'.join(resource_lines)

        existing_text = ''
        if existing_results:
            existing_text = '\n\nPrevious results:\n' + '\n'.join(
                f"- {r.get('title', 'Experiment')}: {r.get('summary', 'No summary')}"
                for r in existing_results[:10]
            )

        constraint_text = ''
        if constraints:
            parts = []
            if constraints.get('budget_usd'):
                parts.append(f"Budget: ${constraints['budget_usd']}")
            if constraints.get('timeline_weeks'):
                parts.append(f"Timeline: {constraints['timeline_weeks']} weeks")
            if constraints.get('personnel_count'):
                parts.append(f"Personnel: {constraints['personnel_count']} people")
            if parts:
                constraint_text = f"\n\nConstraints: {', '.join(parts)}"

        try:
            response = self.llm_client.chat.completions.create(
                model=self.chat_deployment,
                messages=[{
                    'role': 'system',
                    'content': f'''You are a research methodology expert. Given a research question and available lab resources, suggest 2-4 experiments.
{resource_text}
{existing_text}
{constraint_text}

Return JSON:
{{
  "suggestions": [
    {{
      "title": "Experiment title",
      "hypothesis": "What this tests",
      "methodology": "Step-by-step approach (3-5 steps)",
      "required_resources": ["list of needed resources"],
      "missing_resources": ["resources needed but not available"],
      "expected_duration_weeks": 2,
      "expected_outcome": "What success looks like",
      "controls": ["Required controls"],
      "statistical_approach": "How to analyze results",
      "risk_level": "low|medium|high",
      "novelty": "incremental|moderate|high",
      "builds_on": "Which previous result this extends (if any)"
    }}
  ]
}}

Prioritize experiments that use available resources. Flag missing resources clearly.
Keep suggestions practical and actionable.'''
                }, {
                    'role': 'user',
                    'content': research_question
                }],
                temperature=0.3,
                max_tokens=3000,
                response_format={"type": "json_object"},
            )

            result = json.loads(response.choices[0].message.content)
            return result.get('suggestions', [])
        except Exception as e:
            print(f"[ExperimentSuggestion] LLM call failed: {e}")
            return []
