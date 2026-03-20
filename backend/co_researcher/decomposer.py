"""
decomposer.py — Phase 1-2 of the Research Translator pipeline.

Phase 1: Extract structured context from source and target papers.
Phase 2: Decompose each method/finding into 4 abstraction layers (L1-L4).
"""

import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from azure_openai_config import get_azure_client, AZURE_CHAT_DEPLOYMENT
from co_researcher.json_utils import robust_json_parse, retry_api_call


# ---------------------------------------------------------------------------
# Phase 1 — Structured context extraction
# ---------------------------------------------------------------------------

_SOURCE_EXTRACTION_PROMPT = """\
You are a scientific analysis engine. Given the text of a research paper, extract structured context.

Return a JSON object with EXACTLY these keys:

{
  "domain": "<field of research, one sentence>",
  "key_methods": [
    {
      "name": "<method name>",
      "what_it_does": "<concise description of the method's function>",
      "why_it_matters": "<why this method is important for the paper's goals>",
      "specific_implementation": "<exact parameters, reagents, model variants, datasets, or conditions used>"
    }
  ],
  "key_findings": [
    {
      "finding": "<one-sentence statement of the finding>",
      "evidence_type": "<e.g. quantitative measurement, statistical test, qualitative observation, computational simulation>",
      "supporting_data": "<specific numbers, p-values, effect sizes, or figures cited>"
    }
  ],
  "analytical_approaches": ["<each entry is a distinct analytical or computational technique used>"],
  "conceptual_principles": ["<each entry is a FIELD-AGNOSTIC conceptual principle underlying the work>"]
}

CRITICAL RULES for conceptual_principles:
- These MUST be field-agnostic. They should make sense to a scientist in ANY discipline.
- Do NOT restate domain-specific findings. Instead, identify the abstract reasoning pattern.
- BAD example: "Hox genes modulate anterior-posterior patterning in vertebrates"
- GOOD example: "Self-organizing systems can be characterized by smoothly tuning their control parameters"
- BAD example: "CRISPR-Cas9 enables precise genome editing"
- GOOD example: "Programmable molecular recognition can be repurposed for targeted modification of information-carrying polymers"

Be thorough — capture ALL significant methods and findings, not just the most prominent ones.
Return ONLY valid JSON. No markdown fences, no commentary."""

_TARGET_EXTRACTION_PROMPT = """\
You are a scientific analysis engine. Given the text of a researcher's OWN paper (or research description), extract structured context about their work.

Return a JSON object with EXACTLY these keys:

{
  "domain": "<field of research, one sentence>",
  "experimental_systems": ["<cell lines, model organisms, computational platforms, clinical cohorts, etc.>"],
  "available_techniques": ["<techniques the researcher uses or has access to, inferred from the methods section>"],
  "key_circuits_or_mechanisms": [
    {
      "name": "<name of the circuit, pathway, mechanism, or system under study>",
      "description": "<what it does and why it matters>",
      "components": ["<list of key molecular, computational, or conceptual components>"]
    }
  ],
  "open_questions": ["<questions the paper explicitly or implicitly leaves unanswered>"],
  "limitations_acknowledged": ["<limitations the authors acknowledge or that are apparent from the methods>"]
}

Be thorough — extract ALL experimental systems, techniques, and mechanisms mentioned.
For open_questions, include both explicit statements ("future work should...") and implicit gaps.
Return ONLY valid JSON. No markdown fences, no commentary."""


@retry_api_call(max_retries=3, base_delay=2.0)
def extract_context(text: str, role: str) -> dict:
    """
    Extract structured context from a paper.

    Args:
        text: The full text of the paper.
        role: Either "source" (paper they read) or "target" (their own research).

    Returns:
        A dict with structured fields appropriate to the role.
    """
    if role not in ("source", "target"):
        raise ValueError(f"role must be 'source' or 'target', got '{role}'")

    system_prompt = _SOURCE_EXTRACTION_PROMPT if role == "source" else _TARGET_EXTRACTION_PROMPT

    # Truncate to first 40 000 characters to stay within token limits
    truncated_text = text[:40000]

    client = get_azure_client()
    response = client.chat.completions.create(
        model=AZURE_CHAT_DEPLOYMENT,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": truncated_text},
        ],
        temperature=0.2,
        max_tokens=2000,
        response_format={"type": "json_object"},
        timeout=90,  # 90 second timeout
    )

    raw = response.choices[0].message.content
    fallback = {
        "domain": "Unknown",
        "key_methods": [],
        "key_findings": [],
        "analytical_approaches": [],
        "conceptual_principles": [],
        "experimental_systems": [],
        "available_techniques": [],
        "key_circuits_or_mechanisms": [],
        "open_questions": [],
        "limitations_acknowledged": [],
    }
    return robust_json_parse(raw, fallback)


# ---------------------------------------------------------------------------
# Phase 2 — Four-layer abstraction decomposition
# ---------------------------------------------------------------------------

_DECOMPOSE_SYSTEM_PROMPT = """\
You are an abstraction-layer decomposer for scientific methods and findings.

Given a method or finding from a research paper along with the paper's domain context, \
decompose it into exactly four abstraction layers. Each layer must capture a GENUINELY \
DIFFERENT level of abstraction — not the same idea rephrased at different verbosity levels.

The four layers are:

L4 — Conceptual Principle
  The deepest abstraction. A statement that would make sense to ANY scientist regardless \
  of field. This is the universal reasoning pattern, mathematical relationship, or \
  epistemological insight that underpins the work.
  Example: "Measuring how a system's output changes when you systematically vary one \
  input while holding others constant reveals the functional contribution of that input."

L3 — Analytical Logic
  The experimental or analytical reasoning pattern. Makes sense to any experimentalist \
  or computational scientist, even outside the specific field. Describes the type of \
  measurement, comparison, or inference strategy without field-specific jargon.
  Example: "Compare system behavior with and without a specific component to quantify \
  that component's contribution to the overall output."

L2 — Design Pattern
  A concrete experimental or computational design recognizable to someone working in the \
  broad area (e.g., biology, physics, computer science) but not necessarily in the exact \
  sub-field. Uses some domain vocabulary but remains transferable.
  Example: "Use a loss-of-function perturbation (knockout, knockdown, or inhibitor) and \
  measure a phenotypic readout to determine gene necessity for a process."

L1 — Specific Implementation
  The exact details as executed in THIS paper. Includes specific reagents, model organisms, \
  parameter values, software versions, cell lines, statistical thresholds, etc.
  Example: "CRISPR-Cas9 knockout of FGF8 in E9.5 mouse embryos, followed by whole-mount \
  in situ hybridization for Pax2, scored as present/absent in the midbrain-hindbrain boundary."

CRITICAL: Each layer MUST be substantively different from the others.
- L4 should be so abstract it could apply to economics, ecology, or engineering.
- L3 should describe a strategy, not a specific tool.
- L2 should name a recognizable experimental pattern within a broad discipline.
- L1 should read like a methods section excerpt.

If the layers start to sound similar, you are not abstracting enough at the higher levels \
or not being specific enough at L1. Push harder.

Return a JSON object:
{
  "layers": [
    {"level": "L4", "name": "Conceptual Principle", "content": "..."},
    {"level": "L3", "name": "Analytical Logic", "content": "..."},
    {"level": "L2", "name": "Design Pattern", "content": "..."},
    {"level": "L1", "name": "Specific Implementation", "content": "..."}
  ]
}

Return ONLY valid JSON. No markdown fences, no commentary."""


@retry_api_call(max_retries=3, base_delay=2.0)
def decompose_layers(source_context: dict, method_or_finding: dict) -> dict:
    """
    Decompose a single method or finding into 4 abstraction layers.

    Args:
        source_context: The full context dict returned by extract_context(..., role="source").
        method_or_finding: A single item from source_context["key_methods"] or
                           source_context["key_findings"].

    Returns:
        A dict with a "layers" key containing the four abstraction layers (L4 -> L1).
    """
    user_message = json.dumps(
        {
            "domain": source_context.get("domain", ""),
            "item_to_decompose": method_or_finding,
            "paper_conceptual_principles": source_context.get("conceptual_principles", []),
        },
        indent=2,
    )

    client = get_azure_client()
    response = client.chat.completions.create(
        model=AZURE_CHAT_DEPLOYMENT,
        messages=[
            {"role": "system", "content": _DECOMPOSE_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0.3,
        max_tokens=800,
        response_format={"type": "json_object"},
        timeout=60,  # 60 second timeout
    )

    raw = response.choices[0].message.content
    fallback = {
        "layers": [
            {"level": "L4", "name": "Conceptual Principle", "content": "Unable to extract"},
            {"level": "L3", "name": "Analytical Logic", "content": "Unable to extract"},
            {"level": "L2", "name": "Design Pattern", "content": "Unable to extract"},
            {"level": "L1", "name": "Specific Implementation", "content": "Unable to extract"},
        ]
    }
    return robust_json_parse(raw, fallback)
