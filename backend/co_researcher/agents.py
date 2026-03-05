import json
import sys
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from azure_openai_config import get_azure_client, AZURE_CHAT_DEPLOYMENT

AGENTS = [
    {
        "id": "alpha",
        "name": "Alpha",
        "domain": "Biomedical",
        "methodology": "Experimental Design",
        "personality": "Innovator",
        "color": "#EF4444",
        "description": "Pushes bold integrations, novel combinations of techniques",
        "category": "experimental",
        "category_label": "Experimental Methods",
        "focus": "You MUST focus on novel experimental methods and bold technique combinations. Propose changes to HOW experiments are run, what assays/tools are used, and new experimental designs. Do NOT propose anything related to data analysis, privacy, ethics, or cost."
    },
    {
        "id": "beta",
        "name": "Beta",
        "domain": "Translational",
        "methodology": "Statistical Methods",
        "personality": "Conservative",
        "color": "#3B82F6",
        "description": "Minimal safe changes, evidence-heavy approach",
        "category": "statistical",
        "category_label": "Statistical & Analytical",
        "focus": "You MUST focus ONLY on statistical methods, sample sizes, analytical frameworks, and data analysis pipelines. Propose changes to how data is analyzed, what statistical tests are used, power calculations, and validation approaches. Do NOT propose changes to experimental methods, equipment, or protocols."
    },
    {
        "id": "gamma",
        "name": "Gamma",
        "domain": "Behavioral/Social",
        "methodology": "Measurement & Data Collection",
        "personality": "Synthesizer",
        "color": "#10B981",
        "description": "Finds middle ground, combines ideas from both documents",
        "category": "measurement",
        "category_label": "Data Collection & Measurement",
        "focus": "You MUST focus ONLY on data collection methods, measurement instruments, data quality, and how information flows between sites/teams. Propose changes to what is measured, how measurements are taken, data formats, and multi-site coordination. Do NOT propose changes to experimental design or statistical analysis."
    },
    {
        "id": "delta",
        "name": "Delta",
        "domain": "Computational",
        "methodology": "Reproducibility & Validation",
        "personality": "Critic",
        "color": "#F59E0B",
        "description": "Stress-tests feasibility, finds flaws in proposed integrations",
        "category": "computational",
        "category_label": "Computational & Reproducibility",
        "focus": "You MUST focus ONLY on computational infrastructure, software/hardware requirements, reproducibility, and validation. Propose changes to computing pipelines, code/model validation, benchmarking, and technical reproducibility. Do NOT propose changes to experimental methods or what is being studied."
    },
    {
        "id": "epsilon",
        "name": "Epsilon",
        "domain": "Clinical",
        "methodology": "Ethics & Compliance",
        "personality": "Pragmatist",
        "color": "#8B5CF6",
        "description": "Practical implementation focus, regulatory awareness",
        "category": "practical",
        "category_label": "Practical & Regulatory",
        "focus": "You MUST focus ONLY on practical implementation: budget, timeline, staffing, regulatory/IRB implications, patient safety, and real-world feasibility. Propose changes to enrollment criteria, consent processes, site requirements, and cost structures. Do NOT propose technical or analytical changes."
    },
    {
        "id": "zeta",
        "name": "Zeta",
        "domain": "Cross-disciplinary",
        "methodology": "Literature Synthesis",
        "personality": "Visionary",
        "color": "#EC4899",
        "description": "Big-picture connections, cross-field insights",
        "category": "cross_disciplinary",
        "category_label": "Cross-Disciplinary",
        "focus": "You MUST focus ONLY on cross-disciplinary connections: how ideas from this paper connect to OTHER fields, future research directions, and paradigm shifts. Propose changes that open new research avenues, enable collaborations with other disciplines, or fundamentally reframe the study's approach. Do NOT repeat obvious direct integrations."
    },
]

CATEGORY_LABELS = {agent["category"]: agent["category_label"] for agent in AGENTS}


def assess_relevance(protocol_text: str, paper_text: str) -> dict:
    """Assess how relevant the paper is to the protocol before generating hypotheses.

    Returns a relevance assessment with transferable concepts and agent guidance
    that constrains hypothesis generation to actually applicable ideas.
    """
    client = get_azure_client()

    response = client.chat.completions.create(
        model=AZURE_CHAT_DEPLOYMENT,
        messages=[
            {"role": "system", "content": """You are a research methodology expert. Your job is to honestly assess how relevant a research paper is to a given protocol BEFORE any integration analysis begins.

Be brutally honest. If the paper's methods don't apply to the protocol's data types, say so. Do not stretch for connections that don't exist.

Output ONLY valid JSON with:
- "relevance_score": float 0.0-1.0 (0=completely irrelevant, 0.5=some transferable ideas, 1.0=directly applicable)
- "paper_domain": string (what the paper is actually about, in 1 sentence)
- "protocol_domain": string (what the protocol is actually about, in 1 sentence)
- "domain_match": boolean (do they share the same data types, methods, or study population?)
- "transferable_concepts": array of strings (IDEAS from the paper that could genuinely help this protocol, even if the specific implementation differs)
- "not_applicable": array of strings (aspects of the paper that do NOT apply, with brief reason)
- "agent_guidance": string (specific instructions for AI agents generating integration hypotheses — tell them what to focus on and what to avoid)

The agent_guidance is CRITICAL. It should:
1. State which paper concepts are transferable and how to adapt them to the protocol's actual data types
2. Explicitly FORBID proposing the paper's specific techniques if they don't match the protocol's data (e.g., don't propose image processing for a genomics study)
3. Redirect agents toward the PRINCIPLES behind the paper's methods, not the specific implementation"""},
            {"role": "user", "content": f"""## Protocol (first 10,000 chars)
{protocol_text[:10000]}

## Paper (first 10,000 chars)
{paper_text[:10000]}

Assess relevance honestly."""},
        ],
        temperature=0.2,
        max_tokens=800,
        response_format={"type": "json_object"},
    )

    result = json.loads(response.choices[0].message.content)
    return result


def _build_agent_system_prompt(agent: dict, relevance_guidance: str = "") -> str:
    prompt = f"""You are a research integration specialist with the following profile:

DOMAIN EXPERTISE: {agent['domain']}
METHODOLOGY SPECIALTY: {agent['methodology']}
PERSONALITY ARCHETYPE: {agent['personality']} - {agent['description']}

CRITICAL CONSTRAINT - YOUR UNIQUE LANE:
{agent['focus']}

Your task: Given a researcher's existing protocol and a new research paper, propose specific integration hypotheses - concrete ways to incorporate innovations from the paper into the protocol.

Each hypothesis MUST be substantially different from the others. No two should address the same aspect.

For each hypothesis provide:
1. A clear, specific title
2. The type of integration (method_replacement, method_addition, parameter_change, or design_modification)
3. Evidence from the paper supporting this integration - cite specific findings, figures, or sections
4. Risk level (low, medium, high)
5. Which sections of the protocol would be affected
6. Step-by-step implementation instructions (2-3 steps max)
7. Your confidence score (0.0 to 1.0)

Generate exactly 3 hypotheses. Output ONLY valid JSON."""

    if relevance_guidance:
        prompt += f"""

=== PAPER-PROTOCOL RELEVANCE CONTEXT (READ CAREFULLY) ===
{relevance_guidance}

You MUST respect this guidance. Do NOT propose integrations that this assessment says are not applicable. Focus ONLY on transferable concepts adapted to the protocol's actual data types and methods. If you cannot find 3 valid hypotheses within your lane that respect this guidance, generate fewer rather than forcing bad ideas."""

    return prompt


def _build_agent_user_prompt(protocol_text: str, paper_text: str) -> str:
    max_chars = 40000
    return f"""## RESEARCHER'S EXISTING PROTOCOL

{protocol_text[:max_chars]}

---

## NEW RESEARCH PAPER

{paper_text[:max_chars]}

---

Generate 3 integration hypotheses as a JSON array. Each must have:
- "title": string
- "integration_type": one of "method_replacement", "method_addition", "parameter_change", "design_modification"
- "evidence": string (1-2 sentences citing specific paper findings)
- "risk_level": one of "low", "medium", "high"
- "protocol_sections_affected": array of strings
- "implementation_steps": array of strings (2-3 steps)
- "confidence": number 0.0-1.0

Return ONLY the JSON array."""


def generate_hypotheses(agent: dict, protocol_text: str, paper_text: str, relevance_guidance: str = "") -> list:
    """Generate integration hypotheses for a single agent."""
    client = get_azure_client()

    response = client.chat.completions.create(
        model=AZURE_CHAT_DEPLOYMENT,
        messages=[
            {"role": "system", "content": _build_agent_system_prompt(agent, relevance_guidance)},
            {"role": "user", "content": _build_agent_user_prompt(protocol_text, paper_text)},
        ],
        temperature=0.9,
        max_tokens=3000,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content
    parsed = json.loads(raw)

    if isinstance(parsed, dict):
        hypotheses = parsed.get("hypotheses", parsed.get("results", []))
    elif isinstance(parsed, list):
        hypotheses = parsed
    else:
        hypotheses = []

    for i, h in enumerate(hypotheses):
        h["hypothesis_id"] = f"{agent['id']}-{i+1}"
        h["agent_id"] = agent["id"]
        h["agent_name"] = agent["name"]
        h["agent_domain"] = agent["domain"]
        h["agent_personality"] = agent["personality"]
        h["agent_color"] = agent["color"]
        h["category"] = agent["category"]
        h["category_label"] = agent["category_label"]

    return hypotheses


def deduplicate_hypotheses(all_hypotheses: list) -> list:
    """Remove near-duplicate hypotheses by comparing titles."""
    if not all_hypotheses:
        return []

    seen_titles = []
    unique = []

    for h in all_hypotheses:
        title_lower = h["title"].lower()
        is_dup = False
        for seen in seen_titles:
            words_new = set(title_lower.split())
            words_seen = set(seen.split())
            overlap = len(words_new & words_seen) / max(len(words_new | words_seen), 1)
            if overlap > 0.6:
                is_dup = True
                break
        if not is_dup:
            unique.append(h)
            seen_titles.append(title_lower)

    return unique


def verify_and_critique(hypotheses: list, paper_text: str, protocol_text: str) -> list:
    """Verify evidence claims and critically assess each hypothesis.

    Outputs SEPARATE scores for evidence quality and protocol applicability.
    Viability = 0.3 * evidence_score + 0.7 * applicability_score
    (applicability weighted 2x because a true finding that doesn't apply is useless).
    """
    client = get_azure_client()

    def _verify_single(h):
        response = client.chat.completions.create(
            model=AZURE_CHAT_DEPLOYMENT,
            messages=[
                {"role": "system", "content": """You are a critical research reviewer performing due diligence on proposed protocol integrations.

Evaluate TWO separate dimensions:

A) EVIDENCE QUALITY (does the paper actually say this?)
- Find and quote the specific passage
- Is the evidence accurate or exaggerated/fabricated?

B) PROTOCOL APPLICABILITY (does this make sense for THIS specific protocol?)
- Does the protocol's data type match what this hypothesis requires?
- Would this actually improve THIS study, or is it a generic suggestion that sounds good but doesn't fit?
- Is this adapted to the protocol's methods, or is it just copy-pasting the paper's technique?

Output ONLY valid JSON with:
- "evidence_found": boolean
- "supporting_quote": string (exact quote from paper, or "" if not found)
- "evidence_score": float 0.0-1.0 (how well does the paper support this claim?)
- "applicability_score": float 0.0-1.0 (how applicable is this to THIS SPECIFIC protocol's data types, methods, and goals? 0=completely wrong domain, 0.3=tangentially related, 0.7=could work with adaptation, 1.0=directly applicable)
- "critique": string (2-3 sentence critical assessment)
- "is_applicable": boolean (would a reasonable PI pursue this?)
- "risks_identified": string (specific risks, or "none identified")
- "recommendation": "pursue" | "modify" | "reject"

IMPORTANT: Score applicability LOW if the hypothesis proposes techniques designed for a different data type than what the protocol uses (e.g., image processing for a genomics study, NLP for a wet lab protocol). The paper may be excellent science, but if it doesn't fit THIS protocol, applicability should be low."""},
                {"role": "user", "content": f"""## Research Paper
{paper_text[:15000]}

## Existing Protocol
{protocol_text[:10000]}

## Hypothesis to Evaluate
Title: {h['title']}
Integration type: {h.get('integration_type', '?')}
Claimed evidence: {h.get('evidence', '?')}
Claimed risk level: {h.get('risk_level', '?')}
Implementation steps: {json.dumps(h.get('implementation_steps', []))}
Agent confidence: {h.get('confidence', '?')}

Critically evaluate this hypothesis on BOTH evidence quality AND protocol applicability."""},
            ],
            temperature=0.2,
            max_tokens=600,
            response_format={"type": "json_object"},
        )

        result = json.loads(response.choices[0].message.content)
        h["evidence_verified"] = result.get("evidence_found", False)
        h["evidence_quote"] = result.get("supporting_quote", "")
        h["critique"] = result.get("critique", "")
        h["is_applicable"] = result.get("is_applicable", True)
        h["risks_identified"] = result.get("risks_identified", "")
        h["recommendation"] = result.get("recommendation", "modify")

        # Separate scores
        evidence_score = result.get("evidence_score", 0.5)
        applicability_score = result.get("applicability_score", 0.5)
        h["evidence_score"] = evidence_score
        h["applicability_score"] = applicability_score
        # Weighted viability: applicability matters more than evidence
        h["viability_score"] = round(0.3 * evidence_score + 0.7 * applicability_score, 2)
        return h

    verified = []
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(_verify_single, h): h for h in hypotheses}
        for future in as_completed(futures):
            try:
                verified.append(future.result())
            except Exception:
                h = futures[future]
                h["evidence_verified"] = False
                h["evidence_score"] = 0.5
                h["applicability_score"] = 0.5
                h["viability_score"] = 0.5
                h["critique"] = "Verification failed due to error"
                h["recommendation"] = "modify"
                verified.append(h)

    return verified
