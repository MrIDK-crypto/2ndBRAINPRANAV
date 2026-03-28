"""
Research Translator — Phase 3 of the Research Translator pipeline.

Takes a decomposed insight (4 abstraction layers from a source paper) and
attempts to re-instantiate each layer in the target researcher's domain.

For each layer (L4 abstract principle -> L1 concrete protocol), the translator:
  - Maps the source concept to the target domain
  - States the specific assumption required for the mapping to hold
  - States the condition that would invalidate it ("breaks_if")
  - Assigns a confidence score

It also identifies the overall weakest layer (overall_break_point) and the
single most informative experiment to resolve that uncertainty (what_to_test_first).
"""

import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from azure_openai_config import get_azure_client, AZURE_CHAT_DEPLOYMENT
from co_researcher.json_utils import robust_json_parse, retry_api_call


TRANSLATOR_SYSTEM_PROMPT = """You are a research translation specialist. Your job is to take an insight that has been decomposed into 4 abstraction layers from a SOURCE paper and attempt to re-instantiate each layer in a TARGET researcher's domain.

The 4 layers are:
- L4 (Abstract Principle): The universal principle behind the insight
- L3 (Mechanism): The causal mechanism or theoretical framework
- L2 (Method): The specific methodology or experimental approach
- L1 (Protocol): The concrete implementation details

=== CRITICAL: USE THE LAB PROFILE ===
The TARGET PAPER CONTEXT may include the researcher's lab profile with:
- "available_equipment": Equipment they have access to — USE THIS for L1/L2 translations
- "established_methods": Methods they already know — REFERENCE THESE in your translations
- "model_systems": Cell lines, organisms they work with — USE THESE in implementation
- "expertise_areas": What they're good at — LEVERAGE THIS for confidence scoring
- "known_constraints": Past issues to avoid

When generating translations, you MUST:
1. At L2 (Method) and L1 (Protocol): Explicitly reference their available equipment and methods
2. Use their model systems (cell lines, organisms) in concrete implementations
3. Flag if a translation requires equipment/methods they DON'T have
4. Increase confidence if translation uses their established expertise
5. Decrease confidence if translation requires techniques outside their profile

For EACH layer, you must provide:
1. "source": What this layer says in the source paper's domain
2. "target": How this layer would map to the target researcher's domain
3. "confidence": 0.0-1.0 how likely this mapping holds
4. "assumption": The specific assumption required for this mapping to work
5. "breaks_if": The specific condition that would invalidate this mapping

CRITICAL RULES:
- Be HONEST about where the mapping breaks. A translation that acknowledges weak points is far more valuable than one that pretends everything maps cleanly.
- Higher layers (L4, L3) usually transfer more easily than lower layers (L2, L1). If L1 doesn't map, SAY SO — that's useful information.
- The "breaks_if" field is the most important part. A researcher reading this needs to know exactly what could go wrong.
- Identify the overall_break_point: which single layer is weakest and most likely to fail.
- Identify what_to_test_first: a single concrete experiment or analysis that would resolve the biggest uncertainty before committing resources.
- The "title" should be a clear 1-sentence name for this translation proposal.
- If lab profile is available, the title and implementations MUST reference their specific capabilities.

Output ONLY valid JSON with this structure:
{
  "title": "string — 1-sentence name for this translation proposal",
  "source_insight": "string — 1-sentence summary of what the source paper's insight is",
  "layers": [
    {
      "level": "L4",
      "source": "string",
      "target": "string",
      "confidence": float,
      "assumption": "string",
      "breaks_if": "string"
    },
    {
      "level": "L3",
      "source": "string",
      "target": "string",
      "confidence": float,
      "assumption": "string",
      "breaks_if": "string"
    },
    {
      "level": "L2",
      "source": "string",
      "target": "string",
      "confidence": float,
      "assumption": "string",
      "breaks_if": "string"
    },
    {
      "level": "L1",
      "source": "string",
      "target": "string",
      "confidence": float,
      "assumption": "string",
      "breaks_if": "string"
    }
  ],
  "overall_break_point": "string — identify the weakest layer (e.g. 'L2') and explain WHY it is the most likely point of failure",
  "what_to_test_first": "string — a single concrete experiment or check to resolve the biggest uncertainty"
}"""


@retry_api_call(max_retries=3, base_delay=2.0)
def translate_insight(source_context: dict, target_context: dict, layers: dict) -> dict:
    """Translate a decomposed insight from source domain to target domain.

    Takes the 4 abstraction layers extracted from a source paper and attempts
    to map each one into the target researcher's domain, honestly flagging
    where the mapping is strong vs where it breaks.

    Args:
        source_context: Structured context from the source paper
                        (output of decomposer.extract_context).
        target_context: Structured context from the target paper
                        (same structure as source_context).
        layers:         Decomposed layers from decomposer.decompose_layers.
                        Expected to have a "layers" key containing an array
                        with L4, L3, L2, L1 entries.

    Returns:
        dict with keys:
            - title: 1-sentence name for the translation proposal
            - source_insight: summary of the source insight
            - layers: list of layer translation dicts (L4, L3, L2, L1),
              each with source, target, confidence, assumption, breaks_if
            - overall_break_point: weakest layer and why
            - what_to_test_first: single experiment to resolve biggest uncertainty
    """
    client = get_azure_client()

    # Truncate contexts to first 8000 chars each to stay within token budget
    source_context_str = json.dumps(source_context, indent=2)[:8000]
    target_context_str = json.dumps(target_context, indent=2)[:8000]
    layers_str = json.dumps(layers, indent=2)

    # Check if lab profile info is present in target context
    has_lab_profile = any(k in target_context for k in ['available_equipment', 'established_methods', 'model_systems', 'expertise_areas'])

    lab_profile_instruction = ""
    if has_lab_profile:
        lab_profile_instruction = """
IMPORTANT: The target context includes the researcher's LAB PROFILE with their equipment, methods, and expertise.
You MUST use this information when generating translations:
- Reference their specific equipment in L1/L2 implementations
- Leverage their established methods
- Use their model systems (cell lines, etc.) in protocols
- Explain HOW their expertise helps or where gaps exist
"""

    user_prompt = f"""## SOURCE PAPER CONTEXT (the paper the insight comes from)
{source_context_str}

## TARGET PAPER CONTEXT (the researcher's domain to translate INTO)
{target_context_str}
{lab_profile_instruction}
## DECOMPOSED INSIGHT LAYERS (from source paper)
{layers_str}

Translate each layer from the source domain into the target domain. Be honest about where the mapping is strong and where it breaks.{' USE THE LAB PROFILE to make translations specific to their capabilities.' if has_lab_profile else ''}"""

    response = client.chat.completions.create(
        model=AZURE_CHAT_DEPLOYMENT,
        messages=[
            {"role": "system", "content": TRANSLATOR_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.4,
        max_tokens=1500,
        response_format={"type": "json_object"},
        timeout=90,  # 90 second timeout
    )

    fallback = {
        "title": "Translation failed",
        "source_insight": "",
        "layers": [],
        "overall_break_point": "",
        "what_to_test_first": "",
    }
    result = robust_json_parse(response.choices[0].message.content, fallback)

    # Ensure the expected structure is present with sensible defaults
    if "title" not in result:
        result["title"] = "Untitled translation"
    if "source_insight" not in result:
        result["source_insight"] = ""
    if "layers" not in result:
        result["layers"] = []
    if "overall_break_point" not in result:
        result["overall_break_point"] = ""
    if "what_to_test_first" not in result:
        result["what_to_test_first"] = ""

    # Validate each layer has the required fields
    for layer in result["layers"]:
        layer.setdefault("level", "")
        layer.setdefault("source", "")
        layer.setdefault("target", "")
        layer.setdefault("confidence", 0.0)
        layer.setdefault("assumption", "")
        layer.setdefault("breaks_if", "")

    return result
