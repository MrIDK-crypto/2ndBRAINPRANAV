"""
LLM-based Intent Classifier for Co-Work Chatbot
Replaces keyword pattern matching with a single gpt-4o-mini call.
Returns structured intent + source weights for query routing.
"""

import os
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# All possible intents the chatbot can route to
INTENTS = [
    "rag_search",           # Standard KB search + RAG answer
    "experiment_suggestion", # Suggest experiments with feasibility scoring
    "protocol_feasibility",  # Check if a technique/experiment is feasible
    "journal_analysis",      # Recommend journals for publishing
    "methodology_analysis",  # Detect methodology gaps in a paper/protocol
    "knowledge_gap",         # Analyze KB for missing knowledge
    "literature_search",     # Search PubMed/OpenAlex for papers
    "general",               # General conversation, greetings, meta-questions
]

# Source weight presets per intent
SOURCE_WEIGHTS = {
    "rag_search":            {"user_kb": 0.7, "pubmed": 0.1, "journals": 0.05, "protocols": 0.1, "openalex": 0.05},
    "experiment_suggestion": {"user_kb": 0.3, "pubmed": 0.2, "journals": 0.05, "protocols": 0.4, "openalex": 0.05},
    "protocol_feasibility":  {"user_kb": 0.2, "pubmed": 0.1, "journals": 0.05, "protocols": 0.6, "openalex": 0.05},
    "journal_analysis":      {"user_kb": 0.3, "pubmed": 0.1, "journals": 0.4, "protocols": 0.0, "openalex": 0.2},
    "methodology_analysis":  {"user_kb": 0.4, "pubmed": 0.2, "journals": 0.1, "protocols": 0.2, "openalex": 0.1},
    "knowledge_gap":         {"user_kb": 0.8, "pubmed": 0.05, "journals": 0.05, "protocols": 0.05, "openalex": 0.05},
    "literature_search":     {"user_kb": 0.1, "pubmed": 0.4, "journals": 0.1, "protocols": 0.0, "openalex": 0.4},
    "general":               {"user_kb": 0.5, "pubmed": 0.0, "journals": 0.0, "protocols": 0.0, "openalex": 0.0},
}


class IntentClassifier:
    """Classifies user queries into intents using a single LLM call."""

    def __init__(self, llm_client=None, deployment: str = None):
        self.client = llm_client
        self.deployment = deployment or os.getenv("AZURE_MINI_DEPLOYMENT", "gpt-4o-mini")
        # Fallback deployment name
        if not self.deployment:
            self.deployment = os.getenv("AZURE_CHAT_DEPLOYMENT", "gpt-5-chat")

    def classify(self, query: str, conversation_history: list = None) -> dict:
        """
        Classify a query into an intent.

        Returns:
            {
                "intent": str,           # Primary intent
                "confidence": float,     # 0-1 confidence
                "sub_intents": list,     # Secondary intents to also trigger
                "source_weights": dict,  # Source weighting for retrieval
                "special_mode": str|None # For backwards compat with existing code
            }
        """
        if not self.client:
            # Fallback to keyword-based classification
            return self._keyword_fallback(query)

        try:
            # Build conversation context (last 3 messages)
            history_context = ""
            if conversation_history:
                recent = conversation_history[-6:]  # Last 3 exchanges
                history_lines = []
                for msg in recent:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")[:200]
                    history_lines.append(f"{role}: {content}")
                history_context = "\n".join(history_lines)

            system_prompt = """You classify research assistant queries into intents. Return JSON only.

Intents:
- rag_search: Questions about the user's own documents/knowledge base. "What does my protocol say about X?" "Summarize the document about Y"
- experiment_suggestion: User wants ideas for experiments, next steps, what to try. "What experiments should we run?" "How can we test this hypothesis?"
- protocol_feasibility: User asks if a specific technique/method/experiment is possible or compatible. "Can we do ChIP-seq on fixed tissue?" "Will this antibody work in mouse?"
- journal_analysis: User wants journal recommendations for publishing. "Where should we publish this?" "What journals fit this paper?"
- methodology_analysis: User wants to find weaknesses in methods, improve a paper. "What's wrong with our methodology?" "How can we strengthen this paper?"
- knowledge_gap: User wants to know what's missing from their knowledge base. "What gaps exist in our documentation?" "What knowledge are we missing?"
- literature_search: User wants to find published papers/studies. "What studies exist on X?" "Find recent papers about Y"
- general: Greetings, meta-questions, non-research queries. "Hello" "How does this tool work?"

Rules:
- If the query mentions the user's own files/docs/data specifically → rag_search
- If it asks "can I/we do X" about a lab technique → protocol_feasibility
- If it asks "what should we try/test" → experiment_suggestion
- Ambiguous research questions default to rag_search with literature_search as sub_intent
- Return sub_intents array for queries that span multiple intents (max 2)
- Confidence 0.0-1.0 based on how clearly the query matches one intent"""

            user_prompt = f"""Classify this query:

Query: "{query}"
{f'Recent conversation:{chr(10)}{history_context}' if history_context else ''}

Return JSON: {{"intent": "...", "confidence": 0.0-1.0, "sub_intents": []}}"""

            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=100,
                temperature=0,
                response_format={"type": "json_object"},
            )

            result = json.loads(response.choices[0].message.content)
            intent = result.get("intent", "rag_search")
            if intent not in INTENTS:
                intent = "rag_search"

            confidence = min(1.0, max(0.0, float(result.get("confidence", 0.5))))
            sub_intents = [s for s in result.get("sub_intents", []) if s in INTENTS and s != intent]

            # Map to special_mode for backwards compat
            special_mode = None
            if intent == "journal_analysis":
                special_mode = "journal_analysis"
            elif intent == "methodology_analysis":
                special_mode = "methodology_analysis"

            return {
                "intent": intent,
                "confidence": confidence,
                "sub_intents": sub_intents,
                "source_weights": SOURCE_WEIGHTS.get(intent, SOURCE_WEIGHTS["rag_search"]),
                "special_mode": special_mode,
            }

        except Exception as e:
            logger.warning(f"Intent classification failed, falling back to keywords: {e}")
            return self._keyword_fallback(query)

    def _keyword_fallback(self, query: str) -> dict:
        """Fallback keyword-based classification when LLM is unavailable."""
        q = query.lower()

        # Check patterns in priority order
        if any(w in q for w in ["experiment", "try next", "what should we test", "suggest experiment", "what can we do"]):
            intent = "experiment_suggestion"
        elif any(w in q for w in ["feasib", "can we do", "will this work", "compatible", "can i use", "does this work on", "can you do"]):
            intent = "protocol_feasibility"
        elif any(w in q for w in ["journal", "publish", "where should", "impact factor", "submit to"]):
            intent = "journal_analysis"
        elif any(w in q for w in ["methodolog", "improve paper", "weakness", "strengthen", "reviewer"]):
            intent = "methodology_analysis"
        elif any(w in q for w in ["knowledge gap", "what's missing", "gaps in", "missing knowledge"]):
            intent = "knowledge_gap"
        elif any(w in q for w in ["literature", "published", "papers about", "studies on", "find papers", "pubmed", "research on"]):
            intent = "literature_search"
        elif any(w in q for w in ["hello", "hi ", "hey", "how are", "what can you", "help me"]):
            intent = "general"
        elif any(w in q for w in ["my doc", "my file", "our data", "my protocol", "uploaded", "in my"]):
            intent = "rag_search"
        else:
            intent = "rag_search"

        special_mode = None
        if intent == "journal_analysis":
            special_mode = "journal_analysis"
        elif intent == "methodology_analysis":
            special_mode = "methodology_analysis"

        return {
            "intent": intent,
            "confidence": 0.6,
            "sub_intents": [],
            "source_weights": SOURCE_WEIGHTS.get(intent, SOURCE_WEIGHTS["rag_search"]),
            "special_mode": special_mode,
        }


# Singleton
_classifier = None


def get_intent_classifier(llm_client=None) -> IntentClassifier:
    global _classifier
    if _classifier is None:
        deployment = os.getenv("AZURE_MINI_DEPLOYMENT", "gpt-4o-mini")
        if not deployment:
            deployment = os.getenv("AZURE_CHAT_DEPLOYMENT", "gpt-5-chat")
        _classifier = IntentClassifier(llm_client=llm_client, deployment=deployment)
    elif llm_client and not _classifier.client:
        _classifier.client = llm_client
    return _classifier
