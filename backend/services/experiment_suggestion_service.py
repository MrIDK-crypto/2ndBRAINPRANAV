"""
Experiment Suggestion Service — Generate experiment suggestions based on
research questions and available lab resources from the protocol knowledge graph.
"""

import json
import logging

from services.feasibility_checker import FeasibilityChecker, protocol_reasoning

logger = logging.getLogger(__name__)


class ExperimentSuggestionService:
    """Suggest experiments based on research questions and available resources."""

    def __init__(self, llm_client, chat_deployment: str):
        self.llm_client = llm_client
        self.chat_deployment = chat_deployment

    def suggest_experiments(self, research_question: str,
                           available_resources: list = None,
                           existing_results: list = None,
                           constraints: dict = None,
                           paper_context: str = None,
                           protocol_context: str = None) -> list:
        """Suggest experiments grounded in the user's paper content and protocol corpus.

        Args:
            research_question: The question to investigate
            available_resources: From protocol graph [{type, name, attributes}]
            existing_results: Documents/references the user has uploaded
            constraints: {budget_usd, timeline_weeks, personnel_count}
            paper_context: Actual content from the user's uploaded papers (RAG results)
            protocol_context: Related protocols from the trained corpus (Pinecone)

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
            existing_text = '\n\nReferences from user\'s documents:\n' + '\n'.join(
                f"- {r.get('title', 'Document')}"
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

        # Build paper context section (the actual grounding data)
        paper_section = ''
        if paper_context:
            paper_section = f'\n\n--- USER\'S PAPER CONTENT (ground your suggestions in this) ---\n{paper_context[:8000]}\n--- END PAPER CONTENT ---'

        # Build protocol corpus section (validated lab protocols)
        protocol_section = ''
        if protocol_context:
            protocol_section = f'\n\n--- RELATED PROTOCOLS FROM CORPUS (use as methodology references) ---\n{protocol_context[:4000]}\n--- END PROTOCOLS ---'

        try:
            response = self.llm_client.chat.completions.create(
                model=self.chat_deployment,
                messages=[{
                    'role': 'system',
                    'content': f'''You are a research methodology expert. Given a research question, the user's paper content, and related lab protocols, suggest 2-4 follow-up experiments.

CRITICAL RULES:
1. Base your suggestions on the ACTUAL FINDINGS and METHODOLOGY described in the user's paper content below
2. Reference specific results, techniques, and data from the paper
3. Each suggestion must logically extend from what the paper already demonstrates
4. Use the related protocols from the corpus as methodology templates where applicable
5. Do NOT hallucinate techniques or results not present in the provided context
6. In "grounding", cite the specific paper content that supports each suggestion
{resource_text}
{existing_text}
{constraint_text}
{paper_section}
{protocol_section}

Return JSON:
{{
  "suggestions": [
    {{
      "title": "Experiment title",
      "hypothesis": "What this tests — reference specific findings from the paper",
      "methodology": "Step-by-step approach (3-5 steps) — cite protocol references where applicable",
      "grounding": "Which specific findings/data from the paper support this experiment",
      "references_used": ["titles of papers/protocols that inform this suggestion"],
      "required_resources": ["list of needed resources"],
      "missing_resources": ["resources needed but not available"],
      "expected_duration_weeks": 2,
      "expected_outcome": "What success looks like",
      "controls": ["Required controls"],
      "statistical_approach": "How to analyze results",
      "risk_level": "low|medium|high",
      "novelty": "incremental|moderate|high",
      "builds_on": "Which specific result from the paper this extends"
    }}
  ]
}}

If no paper content or protocol references are provided, respond with:
{{"suggestions": [], "note": "Insufficient data — please upload a research paper or specify a topic so I can search the corpus."}}

Do NOT invent experiments without evidence. Every suggestion MUST cite specific text from the provided paper or protocol context.'''
                }, {
                    'role': 'user',
                    'content': research_question
                }],
                temperature=0.3,
                max_tokens=4000,
                response_format={"type": "json_object"},
            )

            result = json.loads(response.choices[0].message.content)
            suggestions = result.get('suggestions', [])

            # Add corpus metadata to each suggestion
            corpus_papers_used = 0
            if protocol_context:
                corpus_papers_used = protocol_context.count("[Protocol:")
            user_papers_used = 0
            if paper_context:
                user_papers_used = len(set(
                    line.split("]:")[0].replace("[", "")
                    for line in paper_context.split("\n\n")
                    if line.startswith("[")
                ))

            for s in suggestions:
                s["evidence_sources"] = {
                    "user_papers": user_papers_used,
                    "corpus_protocols": corpus_papers_used,
                    "grounded": bool(paper_context or protocol_context),
                }

            return suggestions
        except Exception as e:
            print(f"[ExperimentSuggestion] LLM call failed: {e}")
            return []

    def suggest_experiments_with_feasibility(self, research_question: str,
                                             available_resources: list = None,
                                             existing_results: list = None,
                                             constraints: dict = None,
                                             paper_context: str = None,
                                             protocol_context: str = None) -> list:
        """Suggest experiments and score each for feasibility.

        Returns suggestions sorted by feasibility (highest first).
        """
        suggestions = self.suggest_experiments(
            research_question, available_resources, existing_results, constraints,
            paper_context=paper_context, protocol_context=protocol_context,
        )

        try:
            from services.feasibility_scorer import FeasibilityScorer
        except ImportError:
            print("[ExperimentSuggestion] FeasibilityScorer not available, returning unscored")
            return suggestions
        scorer = FeasibilityScorer()

        for suggestion in suggestions:
            suggestion['feasibility'] = scorer.score(
                suggestion, available_resources or [], constraints or {}
            )

        # Sort by feasibility (highest first)
        suggestions.sort(key=lambda s: s.get('feasibility', {}).get('overall', 0), reverse=True)
        return suggestions

    def suggest_with_deep_feasibility(self, research_question: str,
                                       available_resources: list = None,
                                       existing_results: list = None,
                                       constraints: dict = None,
                                       biological_context: dict = None,
                                       tenant_id: str = None,
                                       vector_store=None,
                                       paper_context: str = None,
                                       protocol_context: str = None) -> list:
        """
        Full pipeline: Generate suggestions -> Basic scoring -> Deep feasibility check.
        Model A (creative) -> Model B (experienced lab manager validation).
        """
        # Step 1: Generate and score suggestions
        suggestions = self.suggest_experiments_with_feasibility(
            research_question, available_resources, existing_results, constraints,
            paper_context=paper_context, protocol_context=protocol_context,
        )

        # Step 2: Deep feasibility check on top suggestions
        checker = FeasibilityChecker(
            llm_client=self.llm_client,
            vector_store=vector_store,
        )

        for suggestion in suggestions:
            basic_score = suggestion.get("feasibility", {}).get("overall", 0)

            # Only deep-check suggestions that pass basic threshold
            if basic_score >= 0.3:
                try:
                    deep_result = checker.check(
                        experiment=suggestion,
                        tenant_id=tenant_id,
                        biological_context=biological_context,
                    )
                    suggestion["deep_feasibility"] = deep_result

                    # Combine scores: weighted average of basic and deep
                    deep_score = deep_result.get("score", 0.5)
                    suggestion["combined_feasibility_score"] = (basic_score * 0.3) + (deep_score * 0.7)
                except Exception as e:
                    logger.warning(f"Deep feasibility check failed for '{suggestion.get('title', '')}': {e}")
                    suggestion["combined_feasibility_score"] = basic_score
            else:
                suggestion["combined_feasibility_score"] = basic_score

        # Re-sort by combined score
        suggestions.sort(key=lambda s: s.get("combined_feasibility_score", 0), reverse=True)

        return suggestions
