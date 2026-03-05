import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from azure_openai_config import get_azure_client, AZURE_CHAT_DEPLOYMENT


def consolidate_themes(final_by_category: dict, relevance_assessment: dict, rejected_hypotheses: list = None) -> list:
    """Merge semantically identical ideas across categories into 3-5 distinct themes.

    This is the key step that prevents the report from repeating the same idea
    6 times in different category wrappers.
    """
    client = get_azure_client()

    # Collect all hypotheses across categories
    all_hyps_text = ""
    for cat, hyps in final_by_category.items():
        for h in hyps:
            verified = "VERIFIED" if h.get("evidence_verified") else "UNVERIFIED"
            all_hyps_text += f"\n- [{cat}] \"{h['title']}\" (ELO: {h.get('elo', 1200)}, Evidence: {verified}, Applicability: {h.get('applicability_score', '?')})"
            if h.get("evidence"):
                all_hyps_text += f"\n  Evidence: {h['evidence']}"
            if h.get("evidence_quote"):
                all_hyps_text += f"\n  Quote: \"{h['evidence_quote'][:150]}\""
            if h.get("critique"):
                all_hyps_text += f"\n  Review: {h['critique']}"
            if h.get("risks_identified") and h["risks_identified"] not in ("none identified", "None identified"):
                all_hyps_text += f"\n  Risks: {h['risks_identified']}"
            if h.get("implementation_steps"):
                all_hyps_text += f"\n  Steps: {'; '.join(h['implementation_steps'])}"

    rejected_text = ""
    if rejected_hypotheses:
        rejected_text = "\n\nREJECTED (not applicable or fabricated evidence):\n"
        for h in rejected_hypotheses:
            rejected_text += f"- {h.get('title', h.get('id', '?'))}: {h.get('critique', '')}\n"

    transferable = relevance_assessment.get("transferable_concepts", [])
    not_applicable = relevance_assessment.get("not_applicable", [])

    # Scale theme count to relevance -- don't inflate output for low-relevance papers
    rel_score = relevance_assessment.get("relevance_score", 0.5)
    if rel_score >= 0.6:
        theme_range = "3-5"
    elif rel_score >= 0.3:
        theme_range = "2-3"
    else:
        theme_range = "1-2"

    response = client.chat.completions.create(
        model=AZURE_CHAT_DEPLOYMENT,
        messages=[
            {"role": "system", "content": f"""You are synthesizing tournament-ranked research integration hypotheses into DISTINCT, actionable themes.

CRITICAL RULES:

1. Many hypotheses across different categories are variations of the SAME underlying idea. Collapse duplicates ruthlessly.
2. Every theme MUST be grounded in specific evidence FROM THE UPLOADED PAPER. If a theme is generic statistical/operational advice that doesn't come from the paper (e.g., "use bootstrap CIs", "write better consent forms"), do NOT include it — the researcher didn't need AI to suggest textbook practices.
3. A theme rated "high" MUST have a direct quote from the paper supporting it AND be directly applicable without major adaptation. If it requires significant adaptation, it is "moderate" at best.
4. If the paper has low relevance (score < 0.3), it is BETTER to return 1 genuine theme than 4 padded ones. Quality over quantity. Returning an empty themes array is acceptable if nothing genuinely transfers.
5. Never claim evidence "while not present in the paper" — if the paper doesn't support it, the theme doesn't belong.

The paper-protocol relevance score is {rel_score}. Generate {theme_range} themes MAX. Fewer is fine if the paper genuinely doesn't offer more.

Output ONLY valid JSON with a "themes" array. Each theme has:
- "theme_title": string (the core transferable idea, not a specific technique name)
- "relevance": "high" | "moderate" | "low"
- "description": string (2-3 sentences: what the idea is, how to adapt it to THIS protocol)
- "supporting_categories": array of category label strings
- "evidence_summary": string (MUST contain a direct quote from the paper — no generic claims)
- "risks": string (key risks)
- "first_step": string (one concrete next action)
- "avg_elo": number (average ELO of supporting hypotheses)

Sort themes by relevance (high first), then by avg_elo."""},
            {"role": "user", "content": f"""## Paper-Protocol Relevance
Paper domain: {relevance_assessment.get('paper_domain', 'Unknown')}
Protocol domain: {relevance_assessment.get('protocol_domain', 'Unknown')}
Relevance score: {rel_score}
Transferable concepts: {', '.join(transferable) if transferable else 'None identified'}
Not applicable: {', '.join(not_applicable) if not_applicable else 'None'}

## All Tournament-Ranked Hypotheses (across all categories)
{all_hyps_text}
{rejected_text}
Consolidate into {theme_range} distinct themes. Only include themes grounded in paper evidence."""},
        ],
        temperature=0.3,
        max_tokens=1500,
        response_format={"type": "json_object"},
    )

    result = json.loads(response.choices[0].message.content)
    if isinstance(result, dict):
        themes = result.get("themes", result.get("results", []))
    elif isinstance(result, list):
        themes = result
    else:
        themes = []

    return themes


def generate_report(consolidated_themes: list, relevance_assessment: dict, rejected_hypotheses: list = None, protocol_text: str = "", paper_text: str = "") -> dict:
    """Generate an integration report based on consolidated themes (not per-category repetition)."""
    client = get_azure_client()

    themes_text = ""
    for i, t in enumerate(consolidated_themes):
        themes_text += f"\n{i+1}. **{t['theme_title']}** (Relevance: {t.get('relevance', '?')})"
        themes_text += f"\n   {t.get('description', '')}"
        themes_text += f"\n   Evidence: {t.get('evidence_summary', 'N/A')}"
        themes_text += f"\n   Risks: {t.get('risks', 'N/A')}"
        themes_text += f"\n   First step: {t.get('first_step', 'N/A')}"
        themes_text += f"\n   Categories: {', '.join(t.get('supporting_categories', []))}"

    rejected_text = ""
    if rejected_hypotheses:
        rejected_text = "\n\nNot Recommended:\n"
        for h in rejected_hypotheses[:5]:
            rejected_text += f"- {h.get('title', h.get('id', '?'))}: {h.get('critique', '')}\n"

    relevance_score = relevance_assessment.get("relevance_score", "?")
    paper_domain = relevance_assessment.get("paper_domain", "Unknown")
    protocol_domain = relevance_assessment.get("protocol_domain", "Unknown")

    response = client.chat.completions.create(
        model=AZURE_CHAT_DEPLOYMENT,
        messages=[
            {"role": "system", "content": f"""You are a research integration consultant writing a report for a principal investigator.

IMPORTANT RULES:
1. Start with the paper-protocol relevance assessment — be brutally honest about fit
2. If overall relevance is below 0.3, LEAD with: "This paper has limited applicability to your protocol." and explain why. Recommend the researcher consider a more relevant paper.
3. Present each consolidated theme with a concrete, protocol-specific recommendation
4. Distinguish between "directly applicable" and "requires adaptation" recommendations
5. Do NOT recommend techniques that don't match the protocol's data types
6. Do NOT include generic best practices (bootstrap CIs, consent language, etc.) unless they are specifically supported by findings in the uploaded paper
7. If a theme has low relevance, say so explicitly and explain what adaptation would be needed
8. End with a prioritized implementation order
9. The number of recommendations should match the relevance: low-relevance papers should have SHORT reports with fewer recommendations, not padded reports

Overall relevance score: {relevance_score}. Keep it under 500 words. Use markdown. Be specific and honest."""},
            {"role": "user", "content": f"""## Relevance Assessment
Paper: {paper_domain}
Protocol: {protocol_domain}
Overall relevance: {relevance_score}

## Protocol Summary
{protocol_text[:3000]}

## Consolidated Themes
{themes_text}
{rejected_text}

Write the integration report."""},
        ],
        temperature=0.4,
        max_tokens=1200,
    )

    return {
        "report_markdown": response.choices[0].message.content,
        "recommendations": consolidated_themes,
    }


def generate_revised_protocol(consolidated_themes: list, relevance_assessment: dict, protocol_text: str) -> str:
    """Generate specific protocol modifications based on consolidated themes."""
    client = get_azure_client()

    # Only include themes with moderate+ relevance
    relevant_themes = [t for t in consolidated_themes if t.get("relevance") in ("high", "moderate")]

    if not relevant_themes:
        return "No protocol modifications recommended. The paper's methods are not directly applicable to this protocol's data types and methodology. Consider the transferable architectural concepts noted in the report, but specific protocol changes would require further feasibility assessment."

    changes = ""
    for t in relevant_themes:
        changes += f"\n- {t['theme_title']} (Relevance: {t.get('relevance', '?')})"
        changes += f"\n  Description: {t.get('description', '')}"
        changes += f"\n  First step: {t.get('first_step', '')}"
        changes += f"\n  Risks: {t.get('risks', '')}"

    response = client.chat.completions.create(
        model=AZURE_CHAT_DEPLOYMENT,
        messages=[
            {"role": "system", "content": """List specific changes to make to the protocol based on the recommended themes.

CRITICAL: Only recommend changes that match the protocol's actual data types and methods. If a theme requires adapting an imaging technique to non-imaging data, say EXACTLY how to adapt it — don't just transplant the original technique.

For each change:
- Which section of the protocol to modify
- What exactly to add, change, or remove
- Why (cite the evidence)
- Any prerequisites or dependencies
- What adaptation is needed if the paper's method doesn't directly apply

Use bullet points. Keep it under 400 words. Be specific enough that a research coordinator could implement each change."""},
            {"role": "user", "content": f"""## Current Protocol
{protocol_text[:8000]}

## Recommended Changes (only themes with moderate+ relevance)
{changes}

List the specific protocol modifications needed. Do NOT recommend changes for techniques that don't match the protocol's data types."""},
        ],
        temperature=0.3,
        max_tokens=800,
    )

    return response.choices[0].message.content


def cross_paper_consolidation(paper_results: list, protocol_text: str) -> list:
    """Merge themes across multiple papers. Themes supported by multiple papers rank higher."""
    client = get_azure_client()

    # Build per-paper theme summaries
    all_themes_text = ""
    for r in paper_results:
        paper_name = r.get("paper_name", "Unknown")
        rel_score = r.get("relevance", {}).get("relevance_score", 0)
        themes = r.get("themes", [])
        all_themes_text += f"\n\n### Paper: \"{paper_name}\" (Relevance: {rel_score})\n"
        if not themes:
            all_themes_text += "No actionable themes found.\n"
            continue
        for t in themes:
            all_themes_text += f"- **{t['theme_title']}** (Relevance: {t.get('relevance', '?')}, ELO: {t.get('avg_elo', '?')})\n"
            all_themes_text += f"  Description: {t.get('description', '')}\n"
            all_themes_text += f"  Evidence: {t.get('evidence_summary', '')}\n"
            if t.get('risks'):
                all_themes_text += f"  Risks: {t['risks']}\n"
            if t.get('first_step'):
                all_themes_text += f"  First step: {t['first_step']}\n"

    num_papers = len(paper_results)
    max_themes = min(num_papers * 2, 8)

    response = client.chat.completions.create(
        model=AZURE_CHAT_DEPLOYMENT,
        messages=[
            {"role": "system", "content": f"""You are synthesizing research integration themes from {num_papers} papers into a unified set of cross-paper recommendations for a protocol.

CRITICAL RULES:

1. If MULTIPLE papers independently support the same idea, that is STRONG evidence. Merge them into one theme and list all supporting papers.
2. Themes supported by 2+ papers should be ranked HIGHER than single-paper themes.
3. Do NOT inflate — if a theme only appears in one paper, keep its original relevance rating. Don't upgrade it.
4. If papers contradict each other on a recommendation, note the disagreement explicitly.
5. Maximum {max_themes} themes. Quality over quantity.
6. Every theme must be grounded in specific paper evidence.

Output ONLY valid JSON with a "themes" array. Each theme has:
- "theme_title": string
- "relevance": "high" | "moderate" | "low"
- "description": string (2-3 sentences)
- "supporting_papers": array of paper name strings that support this theme
- "paper_count": number (how many papers support this)
- "evidence_summary": string (cite specific papers and evidence)
- "risks": string
- "first_step": string
- "avg_elo": number (average across papers)
- "convergence_note": string (if multiple papers agree, explain what that means; if only one, say so)

Sort by: paper_count DESC, then relevance (high > moderate > low), then avg_elo DESC."""},
            {"role": "user", "content": f"""## Protocol Summary
{protocol_text[:3000]}

## Per-Paper Themes
{all_themes_text}

Consolidate into {max_themes} or fewer cross-paper themes. Highlight where multiple papers converge."""},
        ],
        temperature=0.3,
        max_tokens=2000,
        response_format={"type": "json_object"},
    )

    result = json.loads(response.choices[0].message.content)
    if isinstance(result, dict):
        themes = result.get("themes", result.get("results", []))
    elif isinstance(result, list):
        themes = result
    else:
        themes = []

    return themes


def generate_multi_paper_report(cross_paper_themes: list, paper_results: list, protocol_text: str) -> dict:
    """Generate a unified integration report from cross-paper consolidated themes."""
    client = get_azure_client()

    themes_text = ""
    for i, t in enumerate(cross_paper_themes):
        papers_str = ", ".join(t.get("supporting_papers", []))
        themes_text += f"\n{i+1}. **{t['theme_title']}** (Relevance: {t.get('relevance', '?')}, Papers: {t.get('paper_count', 1)})"
        themes_text += f"\n   Supported by: {papers_str}"
        themes_text += f"\n   {t.get('description', '')}"
        themes_text += f"\n   Evidence: {t.get('evidence_summary', 'N/A')}"
        themes_text += f"\n   Convergence: {t.get('convergence_note', 'N/A')}"
        themes_text += f"\n   Risks: {t.get('risks', 'N/A')}"
        themes_text += f"\n   First step: {t.get('first_step', 'N/A')}"

    paper_summary = ""
    for r in paper_results:
        rel = r.get("relevance", {})
        paper_summary += f"\n- **{r['paper_name']}**: {rel.get('paper_domain', '?')} (Relevance: {rel.get('relevance_score', '?')}, Themes: {len(r.get('themes', []))})"

    num_papers = len(paper_results)
    avg_relevance = sum(r.get("relevance", {}).get("relevance_score", 0) for r in paper_results) / max(num_papers, 1)

    response = client.chat.completions.create(
        model=AZURE_CHAT_DEPLOYMENT,
        messages=[
            {"role": "system", "content": f"""You are a research integration consultant writing a multi-paper synthesis report for a principal investigator.

This report synthesizes findings from {num_papers} papers. Average relevance: {avg_relevance:.2f}.

IMPORTANT RULES:
1. Start with a brief overview of all papers analyzed and their relevance to the protocol
2. Highlight CONVERGENT findings — themes supported by multiple papers carry more weight than single-paper themes. Explicitly state "Supported by N papers" for each recommendation.
3. For single-paper themes, note that independent replication would strengthen the recommendation
4. If papers disagree, present both sides
5. End with a prioritized implementation order that factors in paper convergence
6. Be honest about gaps — if key protocol areas have no paper coverage, say so

Keep it under 700 words. Use markdown. Be specific and honest."""},
            {"role": "user", "content": f"""## Protocol Summary
{protocol_text[:3000]}

## Papers Analyzed
{paper_summary}

## Cross-Paper Consolidated Themes
{themes_text}

Write the multi-paper integration report."""},
        ],
        temperature=0.4,
        max_tokens=1500,
    )

    return {
        "report_markdown": response.choices[0].message.content,
        "recommendations": cross_paper_themes,
    }
