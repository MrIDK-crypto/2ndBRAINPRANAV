"""Layer 2: LLM Tool-Use Router — uses GPT function-calling to select tools and extract params."""

import json
import logging
from typing import Dict, Any, List, Optional

from azure_openai_config import get_azure_client, AZURE_CHAT_DEPLOYMENT

logger = logging.getLogger(__name__)

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "score_manuscript",
            "description": "Score and evaluate a research manuscript for journal publication. Analyzes methodology, impact, citations, red flags, and recommends journals.",
            "parameters": {
                "type": "object",
                "properties": {
                    "paper_text": {"type": "string", "description": "The text content of the paper/manuscript to score"},
                    "focus_areas": {"type": "array", "items": {"type": "string"}, "description": "Optional specific areas to focus the analysis on"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_competitors",
            "description": "Find competing research labs, recent preprints, and active grants in a research area. Searches OpenAlex, arXiv, and NIH Reporter.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topics": {"type": "array", "items": {"type": "string"}, "description": "Research topics to search for competitors"},
                    "field": {"type": "string", "description": "Broad research field (e.g., 'molecular biology')"},
                },
                "required": ["topics"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "validate_idea",
            "description": "Validate a research idea for novelty by checking GitHub, PyPI, and web sources for existing implementations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "idea_description": {"type": "string", "description": "Description of the research idea to validate"},
                    "domain": {"type": "string", "description": "Research domain for context"},
                },
                "required": ["idea_description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_co_researcher",
            "description": "Generate research hypotheses and brainstorm new research directions based on a question, paper, or protocol.",
            "parameters": {
                "type": "object",
                "properties": {
                    "research_question": {"type": "string", "description": "The research question to explore"},
                    "paper_text": {"type": "string", "description": "Optional paper text for context"},
                    "protocol_text": {"type": "string", "description": "Optional protocol text for context"},
                },
                "required": ["research_question"],
            },
        },
    },
]

TOOL_TO_SERVICE = {
    "score_manuscript": "hij",
    "find_competitors": "competitor_finder",
    "validate_idea": "idea_reality",
    "run_co_researcher": "co_researcher",
}


def route(
    message: str,
    context_package: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Use LLM function-calling to decide which tools to invoke and extract parameters.
    Returns: [{"service": "hij", "args": {...}}, ...]
    """
    try:
        client = get_azure_client()

        context_str = ""
        if context_package and context_package.get("research_profile"):
            profile = context_package["research_profile"]
            fields = ", ".join(profile.get("primary_fields", []))
            topics = ", ".join(profile.get("recent_topics", []))
            context_str = f"\nUser's research context: fields={fields}, topics={topics}"

        response = client.chat.completions.create(
            model=AZURE_CHAT_DEPLOYMENT,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a research assistant router. Analyze the user's message "
                        "and decide which research tools to invoke. You may call multiple "
                        "tools if the user's request spans multiple tasks. Extract the "
                        "relevant parameters from their message for each tool call."
                        f"{context_str}"
                    ),
                },
                {"role": "user", "content": message},
            ],
            tools=TOOL_DEFINITIONS,
            tool_choice="auto",
            temperature=0,
            max_tokens=500,
        )

        tool_calls = []
        msg = response.choices[0].message

        if msg.tool_calls:
            for tc in msg.tool_calls:
                service = TOOL_TO_SERVICE.get(tc.function.name)
                if service:
                    try:
                        args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        args = {}
                    tool_calls.append({
                        "service": service,
                        "tool_name": tc.function.name,
                        "args": args,
                    })

        if not tool_calls:
            logger.info(f"Tool router found no tools for message: {message[:100]}")

        return tool_calls

    except Exception as e:
        logger.error(f"Tool router error: {e}", exc_info=True)
        return []


def extract_params_simple(
    message: str,
    power: str,
    context_package: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Lightweight parameter extraction for explicit triggers (skips full tool-use router).
    Used when power_hint is set and we know the target service.
    """
    args = {}

    if power == "hij":
        args = {"paper_text": message if len(message) > 200 else None}

    elif power == "competitor_finder":
        topics = [t.strip() for t in message.split(",") if len(t.strip()) > 3]
        if not topics:
            topics = [message[:200]]
        field = None
        if context_package and context_package.get("research_profile"):
            fields = context_package["research_profile"].get("primary_fields", [])
            field = fields[0] if fields else None
        args = {"topics": topics, "field": field}

    elif power == "idea_reality":
        args = {"idea_description": message}

    elif power == "co_researcher":
        args = {"research_question": message}

    return args
