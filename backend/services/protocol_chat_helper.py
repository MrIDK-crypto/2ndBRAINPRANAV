"""
Protocol Chat Helper
=====================
Bridge between the chatbot's protocol_feasibility intent handler and the
trained ML protocol classifiers.

Takes a user query (+ optional document content), runs protocol classification,
completeness scoring, and missing-step detection, then returns a structured dict
ready for the chatbot to stream.

Usage (from app_v2.py protocol_feasibility handler):

    from services.protocol_chat_helper import analyze_protocol_for_chat

    result = analyze_protocol_for_chat(
        query="Can we do ChIP-seq on fixed tissue?",
        document_content=rag_chunk_text,   # optional
    )

    # result["formatted_response"]  → markdown string to stream
    # result["is_protocol"]         → bool
    # result["completeness_score"]  → float 0-1
    # result["missing_steps"]       → list of gap dicts
    # result["recommendations"]     → list of strings
"""

import re
import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


def analyze_protocol_for_chat(
    query: str,
    document_content: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run the full ML protocol analysis pipeline and return a chat-ready result.

    Args:
        query: The user's chat message (e.g. "Can we do ChIP-seq on fixed tissue?")
        document_content: Optional raw text from a retrieved document/protocol.
                          If provided, classification + completeness + missing-step
                          detection run against this content. If absent, only the
                          query text is classified.

    Returns:
        {
            "is_protocol": bool,
            "protocol_confidence": float,       # 0.0 - 1.0
            "completeness_score": float | None, # 0.0 - 1.0, None if not protocol
            "missing_steps": [                  # list of detected gaps
                {
                    "index": int,
                    "step_before": str,
                    "step_after": str,
                    "confidence": float,
                    "is_missing": bool,
                }
            ],
            "recommendations": [str, ...],      # improvement suggestions
            "formatted_response": str,           # markdown ready to stream
            "models_used": {
                "content_classifier": bool,
                "completeness_scorer": bool,
                "missing_step_detector": bool,
            },
        }
    """
    # Import the two service modules
    from services.ml_protocol_service import get_ml_protocol_service
    from services import protocol_classifier

    ml_service = get_ml_protocol_service()

    # Decide which text to analyze: document content if available, else the query
    analysis_text = document_content if document_content else query

    # -----------------------------------------------------------------
    # 1. Content classification
    # -----------------------------------------------------------------
    is_protocol, protocol_confidence = ml_service.classify_content(analysis_text)

    # -----------------------------------------------------------------
    # 2. Completeness scoring (only meaningful for protocol text)
    # -----------------------------------------------------------------
    completeness_score = None
    if is_protocol:
        # Use the ML service scorer (trained model with heuristic fallback)
        completeness_score = round(ml_service.score_completeness(analysis_text), 4)

    # -----------------------------------------------------------------
    # 3. Missing-step detection (only for protocol text)
    # -----------------------------------------------------------------
    missing_steps: List[Dict[str, Any]] = []
    missing_step_model_used = False

    if is_protocol and analysis_text:
        steps = _extract_steps(analysis_text)
        if len(steps) >= 2:
            missing_steps = protocol_classifier.detect_missing_steps_in_sequence(steps)
            # The function returns [] when the model isn't loaded, so we know:
            missing_step_model_used = len(missing_steps) > 0 or (
                protocol_classifier._load_missing_step_model() is not None
            )

    # -----------------------------------------------------------------
    # 4. Generate recommendations
    # -----------------------------------------------------------------
    recommendations = _generate_recommendations(
        is_protocol=is_protocol,
        completeness_score=completeness_score,
        missing_steps=missing_steps,
        text=analysis_text,
    )

    # -----------------------------------------------------------------
    # 5. Build formatted markdown response
    # -----------------------------------------------------------------
    formatted_response = _format_response(
        query=query,
        is_protocol=is_protocol,
        protocol_confidence=protocol_confidence,
        completeness_score=completeness_score,
        missing_steps=missing_steps,
        recommendations=recommendations,
        has_document=document_content is not None,
    )

    models_used = {
        "content_classifier": ml_service._content_classifier is not None,
        "completeness_scorer": ml_service._completeness_scorer is not None,
        "missing_step_detector": missing_step_model_used,
    }

    return {
        "is_protocol": is_protocol,
        "protocol_confidence": round(protocol_confidence, 4),
        "completeness_score": completeness_score,
        "missing_steps": missing_steps,
        "recommendations": recommendations,
        "formatted_response": formatted_response,
        "models_used": models_used,
    }


# =========================================================================
# INTERNAL HELPERS
# =========================================================================


def _extract_steps(text: str) -> List[str]:
    """
    Extract ordered steps from protocol text.

    Handles common step formats:
      - "1. Do this"  /  "1) Do this"
      - "Step 1: Do this"  /  "Step 1. Do this"
      - Markdown numbered lists ("1. ")
      - Bullet-prefixed numbered lines

    Returns a list of step text strings (in order).
    """
    lines = text.split("\n")
    steps: List[str] = []
    current_step = ""

    # Pattern: starts with a number, optionally preceded by "Step"
    step_pattern = re.compile(
        r"^\s*(?:step\s+)?(\d+)\s*[.):\-]\s*(.+)",
        re.IGNORECASE,
    )

    for line in lines:
        m = step_pattern.match(line)
        if m:
            # Save previous step
            if current_step.strip():
                steps.append(current_step.strip())
            current_step = m.group(2).strip()
        elif current_step:
            # Continuation line for the current step
            stripped = line.strip()
            if stripped:
                current_step += " " + stripped

    # Don't forget the last step
    if current_step.strip():
        steps.append(current_step.strip())

    # Fallback: if no numbered steps found, try splitting on action-verb sentences
    if len(steps) < 2:
        steps = _fallback_step_extraction(text)

    return steps


def _fallback_step_extraction(text: str) -> List[str]:
    """
    When no numbered steps are present, split on sentences that begin with
    imperative lab verbs (add, incubate, centrifuge, wash ...).
    """
    verb_pattern = re.compile(
        r"(?:^|(?<=\.\s))"                        # start of string or after ". "
        r"((?:Add|Pipette|Transfer|Incubate|Centrifuge|Wash|Rinse|Mix|Vortex|"
        r"Resuspend|Dissolve|Filter|Dilute|Heat|Cool|Remove|Discard|Aspirate|"
        r"Elute|Load|Apply|Measure|Record|Prepare|Store|Freeze|Thaw|"
        r"Pellet|Spin|Plate|Harvest|Stain|Label|Equilibrate|Run|Set)"
        r"\b.+?)(?=\.\s|$)",
        re.IGNORECASE | re.MULTILINE,
    )
    matches = verb_pattern.findall(text[:8000])
    return [m.strip() for m in matches if len(m.strip()) > 15]


def _generate_recommendations(
    is_protocol: bool,
    completeness_score: Optional[float],
    missing_steps: List[Dict[str, Any]],
    text: str,
) -> List[str]:
    """
    Produce a list of actionable improvement recommendations based on the
    ML analysis results and heuristic checks.
    """
    recs: List[str] = []

    if not is_protocol:
        recs.append(
            "The provided text does not appear to be a scientific protocol. "
            "If you intended to share a protocol, consider including numbered steps, "
            "reagent concentrations, and equipment settings."
        )
        return recs

    # --- Completeness-driven recommendations ---
    if completeness_score is not None:
        if completeness_score < 0.3:
            recs.append(
                "This protocol has low completeness. Consider adding: numbered steps, "
                "specific reagent concentrations, incubation times, temperatures, "
                "equipment settings, and expected results."
            )
        elif completeness_score < 0.6:
            recs.append(
                "Protocol completeness is moderate. Review the checklist below for "
                "missing elements."
            )

    # --- Missing-step recommendations ---
    high_conf_gaps = [g for g in missing_steps if g.get("confidence", 0) >= 0.6]
    if high_conf_gaps:
        for gap in high_conf_gaps[:3]:  # Top 3
            before_short = _truncate(gap.get("step_before", ""), 80)
            after_short = _truncate(gap.get("step_after", ""), 80)
            recs.append(
                f"A step may be missing between \"{before_short}\" and "
                f"\"{after_short}\" (confidence: {gap['confidence']:.0%}). "
                f"Consider adding an intermediate step."
            )

    # --- Heuristic checks on the raw text ---
    sample = text[:10000] if text else ""

    # Check for vague parameters
    vague_terms = re.findall(
        r"\b(briefly|gently|vigorously|some amount|a few|several)\b",
        sample,
        re.IGNORECASE,
    )
    if vague_terms:
        unique = list(set(t.lower() for t in vague_terms))[:4]
        recs.append(
            f"Replace vague terms ({', '.join(unique)}) with precise measurements "
            f"(e.g., exact times, volumes, speeds)."
        )

    # Check for missing safety info with hazardous reagents
    hazardous = re.findall(
        r"\b(phenol|chloroform|formaldehyde|acrylamide|ethidium bromide"
        r"|beta-?mercaptoethanol|sodium azide|trizol)\b",
        sample,
        re.IGNORECASE,
    )
    safety_present = bool(
        re.search(r"\b(fume hood|PPE|gloves|caution|warning|hazard|safety)\b", sample, re.IGNORECASE)
    )
    if hazardous and not safety_present:
        unique_haz = list(set(h.lower() for h in hazardous))[:3]
        recs.append(
            f"Hazardous reagent(s) mentioned ({', '.join(unique_haz)}) without "
            f"corresponding safety precautions. Add PPE requirements, fume hood "
            f"instructions, and disposal procedures."
        )

    # Check for missing expected results section
    if not re.search(
        r"\b(should\s+yield|expected\s+result|positive\s+control|negative\s+control)\b",
        sample,
        re.IGNORECASE,
    ):
        recs.append(
            "No expected results or controls section found. Add expected outcomes "
            "and positive/negative controls to aid troubleshooting."
        )

    # Cap at 6 recommendations
    return recs[:6]


def _format_response(
    query: str,
    is_protocol: bool,
    protocol_confidence: float,
    completeness_score: Optional[float],
    missing_steps: List[Dict[str, Any]],
    recommendations: List[str],
    has_document: bool,
) -> str:
    """
    Build a markdown-formatted response string ready for SSE streaming.
    """
    parts: List[str] = []

    # Header
    parts.append("### Protocol Analysis\n")

    # Classification result
    if is_protocol:
        conf_pct = f"{protocol_confidence:.0%}"
        parts.append(
            f"**Classification:** This content is identified as a scientific protocol "
            f"(confidence: {conf_pct}).\n"
        )
    else:
        if has_document:
            parts.append(
                "**Classification:** The retrieved document does not appear to be a "
                "scientific protocol. The analysis below is limited.\n"
            )
        else:
            parts.append(
                "**Classification:** No protocol document was found for this query. "
                "Results are based on the query text alone.\n"
            )

    # Completeness score
    if completeness_score is not None:
        bar = _completeness_bar(completeness_score)
        score_pct = f"{completeness_score:.0%}"
        parts.append(f"**Completeness:** {bar} {score_pct}\n")

        if completeness_score >= 0.8:
            parts.append("_This protocol is fairly complete._\n")
        elif completeness_score >= 0.5:
            parts.append("_This protocol has moderate completeness — see recommendations below._\n")
        else:
            parts.append("_This protocol has significant gaps — see recommendations below._\n")

    # Missing steps
    if missing_steps:
        parts.append("#### Potential Missing Steps\n")
        parts.append("| Gap | Between | Confidence |")
        parts.append("|-----|---------|------------|")
        for i, gap in enumerate(missing_steps[:5], 1):
            before = _truncate(gap.get("step_before", "?"), 50)
            after = _truncate(gap.get("step_after", "?"), 50)
            conf = gap.get("confidence", 0)
            flag = "**HIGH**" if conf >= 0.7 else "medium" if conf >= 0.5 else "low"
            parts.append(f"| {i} | \"{before}\" → \"{after}\" | {conf:.0%} ({flag}) |")
        parts.append("")

    # Recommendations
    if recommendations:
        parts.append("#### Recommendations\n")
        for rec in recommendations:
            parts.append(f"- {rec}")
        parts.append("")

    return "\n".join(parts)


def _completeness_bar(score: float) -> str:
    """Render a simple text progress bar for completeness."""
    filled = round(score * 10)
    empty = 10 - filled
    return "[" + "=" * filled + "-" * empty + "]"


def _truncate(text: str, max_len: int) -> str:
    """Truncate text with ellipsis."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."
