"""
chat.py — Phase 5 of the Research Translator pipeline.

Interactive refinement: the researcher provides constraints, asks questions,
or pushes back. The system refines translations based on their input.
"""

import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from azure_openai_config import get_azure_client, AZURE_CHAT_DEPLOYMENT


def build_chat_context(source_contexts: list, target_context: dict,
                       translations: list, adversarial_results: list) -> str:
    """Build a system prompt with full analysis context for the chat agent.

    Serializes all analysis results into a concise string that gives the chat
    agent enough context to answer researcher questions and refine translations.
    """
    parts = []

    # Target research
    parts.append("## YOUR RESEARCH")
    parts.append(f"Domain: {target_context.get('domain', 'Unknown')}")
    parts.append(f"Systems: {', '.join(target_context.get('experimental_systems', []))}")
    parts.append(f"Techniques: {', '.join(target_context.get('available_techniques', []))}")
    mechanisms = target_context.get("key_circuits_or_mechanisms", [])
    if mechanisms:
        for m in mechanisms[:3]:
            parts.append(f"Mechanism: {m.get('name', '?')} — {m.get('description', '')}")
    open_qs = target_context.get("open_questions", [])
    if open_qs:
        parts.append(f"Open questions: {'; '.join(open_qs[:5])}")

    # Source papers
    parts.append("\n## PAPERS ANALYZED")
    for i, sc in enumerate(source_contexts):
        parts.append(f"Paper {i+1}: {sc.get('domain', 'Unknown')}")

    # Translations
    parts.append("\n## TRANSLATION PROPOSALS")
    for i, (trans, adv) in enumerate(zip(translations, adversarial_results)):
        score = adv.get("survival_score", 0)
        has_fatal = adv.get("has_fatal", False)
        parts.append(f"\n### Translation {i+1}: {trans.get('title', 'Untitled')}")
        parts.append(f"Survival: {score}/4{' (HAS FATAL FLAW)' if has_fatal else ''}")
        parts.append(f"Source insight: {trans.get('source_insight', '')}")
        parts.append(f"Break point: {trans.get('overall_break_point', '')}")
        parts.append(f"Test first: {trans.get('what_to_test_first', '')}")

        for layer in trans.get("layers", []):
            conf = layer.get("confidence", 0)
            parts.append(f"  {layer.get('level', '?')} (conf {conf:.1f}): {layer.get('target', '')[:150]}")
            if layer.get("breaks_if"):
                parts.append(f"    Breaks if: {layer['breaks_if'][:150]}")

        for v in adv.get("verdicts", []):
            verdict = v.get("verdict", "?")
            parts.append(f"  [{v.get('agent_name', '?')}] {verdict}: {v.get('attack', '')[:200]}")

    return "\n".join(parts)


CHAT_SYSTEM_PROMPT = """You are a research translation advisor helping a researcher apply ideas from papers they've read to their own work.

You have access to the full analysis context below — translation proposals with abstraction layers, break-point analysis, and adversarial stress-test results.

RULES:
1. Do NOT ask probing questions. Respond directly and substantively to whatever the researcher says.
2. When the researcher provides a constraint ("we can't do X because Y"):
   - Identify which translation and which layer is affected
   - Explain how the constraint changes the assessment
   - Suggest alternative L2/L1 mappings that avoid the constraint
3. When the researcher asks about a new idea, evaluate it against the abstraction layers framework.
4. Be specific and practical — cite which layer (L1-L4) is affected by each point.
5. If a constraint kills a translation, say so honestly. Don't try to salvage dead translations.
6. Use markdown formatting for clarity.
7. Keep responses concise but substantive — 150-300 words typically.

{context}"""


def handle_chat_message(chat_context: str, chat_history: list, user_message: str) -> dict:
    """Process a researcher's message and return a response.

    Args:
        chat_context: The serialized analysis context (from build_chat_context).
        chat_history: List of prior messages [{"role": "user"|"assistant", "content": str}].
        user_message: The researcher's new message.

    Returns:
        dict with:
            response: str (markdown-formatted response)
            updated_translations: list | None (if the message contained constraints
                that change a translation's assessment)
    """
    client = get_azure_client()

    system_prompt = CHAT_SYSTEM_PROMPT.format(context=chat_context)

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(chat_history)
    messages.append({"role": "user", "content": user_message})

    response = client.chat.completions.create(
        model=AZURE_CHAT_DEPLOYMENT,
        messages=messages,
        temperature=0.4,
        max_tokens=1000,
    )

    return {
        "response": response.choices[0].message.content,
        "updated_translations": None,
    }
