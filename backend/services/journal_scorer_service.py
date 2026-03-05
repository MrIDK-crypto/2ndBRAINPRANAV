"""
High-Impact Journal Predictor — Core Analysis Pipeline
Stateless service that analyzes manuscripts and predicts journal tier placement.
"""

import json
import re
import time
from typing import Generator

from parsers.document_parser import DocumentParser
from services.openai_client import get_openai_client


# ── Field-Specific Scoring Configurations ──────────────────────────────────

FIELD_CONFIGS = {
    "economics": {
        "label": "Economics",
        "features": {
            "methodology": {"label": "Methodology / Study Design", "weight": 0.25},
            "statistical_rigor": {"label": "Statistical Rigor", "weight": 0.20},
            "novelty": {"label": "Novelty & Contribution", "weight": 0.20},
            "literature": {"label": "Literature Coverage", "weight": 0.15},
            "writing": {"label": "Writing Quality", "weight": 0.10},
            "data_quality": {"label": "Data / Impact Quality", "weight": 0.10},
        },
        "journals": {
            1: [
                {"name": "American Economic Review (AER)", "url": "https://www.aeaweb.org/journals/aer"},
                {"name": "Quarterly Journal of Economics (QJE)", "url": "https://academic.oup.com/qje"},
                {"name": "Econometrica", "url": "https://www.econometricsociety.org/econometrica"},
                {"name": "Journal of Political Economy (JPE)", "url": "https://www.journals.uchicago.edu/toc/jpe/current"},
                {"name": "Review of Economic Studies (RES)", "url": "https://academic.oup.com/restud"},
            ],
            2: [
                {"name": "Journal of Development Economics", "url": "https://www.sciencedirect.com/journal/journal-of-development-economics"},
                {"name": "Journal of Public Economics", "url": "https://www.sciencedirect.com/journal/journal-of-public-economics"},
                {"name": "Journal of Labor Economics", "url": "https://www.journals.uchicago.edu/toc/jole/current"},
                {"name": "Review of Economics and Statistics", "url": "https://direct.mit.edu/rest"},
            ],
            3: [
                {"name": "Economics Letters", "url": "https://www.sciencedirect.com/journal/economics-letters"},
                {"name": "Applied Economics", "url": "https://www.tandfonline.com/toc/raec20/current"},
                {"name": "Journal of Economic Behavior & Organization", "url": "https://www.sciencedirect.com/journal/journal-of-economic-behavior-and-organization"},
            ],
        },
    },
    "cs_data_science": {
        "label": "Computer Science / Data Science",
        "features": {
            "technical_novelty": {"label": "Technical Novelty", "weight": 0.25},
            "experimental_rigor": {"label": "Experimental Rigor", "weight": 0.25},
            "results_quality": {"label": "Results Quality", "weight": 0.15},
            "literature": {"label": "Literature Coverage", "weight": 0.15},
            "writing": {"label": "Writing Quality", "weight": 0.10},
            "data_quality": {"label": "Data / Impact Quality", "weight": 0.10},
        },
        "journals": {
            1: [
                {"name": "NeurIPS", "url": "https://neurips.cc/"},
                {"name": "ICML", "url": "https://icml.cc/"},
                {"name": "ICLR", "url": "https://iclr.cc/"},
                {"name": "JMLR", "url": "https://jmlr.org/"},
                {"name": "IEEE TPAMI", "url": "https://ieeexplore.ieee.org/xpl/RecentIssue.jsp?punumber=34"},
            ],
            2: [
                {"name": "AAAI", "url": "https://aaai.org/"},
                {"name": "KDD", "url": "https://kdd.org/"},
                {"name": "EMNLP", "url": "https://aclanthology.org/venues/emnlp/"},
                {"name": "Neural Networks", "url": "https://www.sciencedirect.com/journal/neural-networks"},
            ],
            3: [
                {"name": "IEEE Access", "url": "https://ieeeaccess.ieee.org/"},
                {"name": "Applied Intelligence", "url": "https://www.springer.com/journal/10489"},
                {"name": "Information Sciences", "url": "https://www.sciencedirect.com/journal/information-sciences"},
            ],
        },
    },
    "biomedical": {
        "label": "Biomedical Sciences",
        "features": {
            "study_design": {"label": "Study Design / Methodology", "weight": 0.25},
            "statistical_rigor": {"label": "Statistical Rigor", "weight": 0.20},
            "clinical_significance": {"label": "Clinical Significance", "weight": 0.20},
            "literature": {"label": "Literature Coverage", "weight": 0.15},
            "writing": {"label": "Writing Quality", "weight": 0.10},
            "data_quality": {"label": "Data / Impact Quality", "weight": 0.10},
        },
        "journals": {
            1: [
                {"name": "New England Journal of Medicine (NEJM)", "url": "https://www.nejm.org/"},
                {"name": "The Lancet", "url": "https://www.thelancet.com/"},
                {"name": "JAMA", "url": "https://jamanetwork.com/journals/jama"},
                {"name": "Nature Medicine", "url": "https://www.nature.com/nm/"},
            ],
            2: [
                {"name": "BMJ", "url": "https://www.bmj.com/"},
                {"name": "PLOS Medicine", "url": "https://journals.plos.org/plosmedicine/"},
                {"name": "Circulation", "url": "https://www.ahajournals.org/journal/circ"},
                {"name": "The Lancet Global Health", "url": "https://www.thelancet.com/journals/langlo/home"},
            ],
            3: [
                {"name": "PLOS ONE", "url": "https://journals.plos.org/plosone/"},
                {"name": "BMC Medicine", "url": "https://bmcmedicine.biomedcentral.com/"},
                {"name": "Scientific Reports", "url": "https://www.nature.com/srep/"},
            ],
        },
    },
    "political_science": {
        "label": "Political Science",
        "features": {
            "theoretical_framework": {"label": "Theoretical Framework", "weight": 0.25},
            "methodology_evidence": {"label": "Methodology & Evidence", "weight": 0.25},
            "novelty": {"label": "Novelty & Contribution", "weight": 0.15},
            "literature": {"label": "Literature Coverage", "weight": 0.15},
            "writing": {"label": "Writing Quality", "weight": 0.10},
            "data_quality": {"label": "Data / Impact Quality", "weight": 0.10},
        },
        "journals": {
            1: [
                {"name": "American Political Science Review (APSR)", "url": "https://www.cambridge.org/core/journals/american-political-science-review"},
                {"name": "American Journal of Political Science (AJPS)", "url": "https://ajps.org/"},
                {"name": "Journal of Politics (JOP)", "url": "https://www.journals.uchicago.edu/toc/jop/current"},
                {"name": "International Organization (IO)", "url": "https://www.cambridge.org/core/journals/international-organization"},
            ],
            2: [
                {"name": "Comparative Political Studies", "url": "https://journals.sagepub.com/home/cps"},
                {"name": "World Politics", "url": "https://www.cambridge.org/core/journals/world-politics"},
                {"name": "British Journal of Political Science", "url": "https://www.cambridge.org/core/journals/british-journal-of-political-science"},
            ],
            3: [
                {"name": "Political Research Quarterly", "url": "https://journals.sagepub.com/home/prq"},
                {"name": "Democratization", "url": "https://www.tandfonline.com/toc/fdem20/current"},
                {"name": "Journal of Elections, Public Opinion and Parties", "url": "https://www.tandfonline.com/toc/fbep20/current"},
            ],
        },
    },
}

# ── Red Flag Checks ────────────────────────────────────────────────────────

RED_FLAG_CHECKS = [
    {"id": "no_abstract", "pattern": r"\babstract\b", "check": "missing", "severity": "critical", "issue": "No abstract detected", "penalty": -15, "fix": "Add a structured abstract (150-300 words)"},
    {"id": "no_references", "pattern": r"\breferences?\b|\bbibliography\b", "check": "missing", "severity": "critical", "issue": "No references section detected", "penalty": -20, "fix": "Add a properly formatted references section"},
    {"id": "low_references", "pattern": None, "check": "ref_count_low", "severity": "warning", "issue": "Fewer than 15 references", "penalty": -5, "fix": "Expand your literature review — top journals expect 30-60 references"},
    {"id": "too_short", "pattern": None, "check": "word_count_low", "severity": "warning", "issue": "Manuscript under 3,000 words", "penalty": -10, "fix": "Expand methodology and results sections for journal-length depth"},
    {"id": "no_tables", "pattern": r"\btable\s+\d+\b|\btable\s+[ivx]+\b", "check": "missing", "severity": "info", "issue": "No tables detected", "penalty": -3, "fix": "Add summary statistics, regression results, or comparison tables"},
]


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


class JournalScorerService:
    def __init__(self):
        self.openai = get_openai_client()
        self.parser = DocumentParser()

    def analyze_manuscript(self, file_bytes: bytes, filename: str) -> Generator[str, None, None]:
        """Main pipeline — yields SSE events as analysis progresses."""
        start_time = time.time()

        try:
            # ── Step 1: Parse Document ──────────────────────────────────
            yield _sse("progress", {"step": 1, "message": "Parsing document...", "percent": 5})

            text = self.parser.parse_file_bytes(file_bytes, filename)
            if not text or len(text.strip()) < 100:
                yield _sse("error", {"error": "Could not extract text from the document. Please ensure it's a valid PDF or DOCX file with readable text."})
                return

            word_count = len(text.split())
            ref_section = self._extract_references_section(text)
            ref_count = self._count_references(ref_section) if ref_section else 0
            has_abstract = bool(re.search(r'\babstract\b', text[:3000], re.IGNORECASE))
            has_tables = bool(re.search(r'\btable\s+\d+\b|\btable\s+[ivx]+\b', text, re.IGNORECASE))

            yield _sse("progress", {"step": 1, "message": f"Parsed {word_count:,} words", "percent": 15})

            # ── Step 2: Detect Field ────────────────────────────────────
            yield _sse("progress", {"step": 2, "message": "Detecting academic field...", "percent": 20})

            field_result = self._detect_field(text[:6000])
            field = field_result["field"]
            field_config = FIELD_CONFIGS.get(field)

            if not field_config:
                yield _sse("error", {"error": f"Unsupported field detected: {field}. Supported fields: Economics, CS/Data Science, Biomedical, Political Science."})
                return

            yield _sse("field_detected", {
                "field": field,
                "field_label": field_config["label"],
                "confidence": field_result["confidence"],
                "subfield": field_result["subfield"],
                "reasoning": field_result["reasoning"],
            })

            # ── Step 3: Extract Features ────────────────────────────────
            yield _sse("progress", {"step": 3, "message": "Evaluating manuscript features...", "percent": 35})

            # Send up to ~12K chars for feature extraction (balance detail vs cost)
            excerpt = text[:12000]
            features = self._extract_features(excerpt, field, field_config)

            yield _sse("features_extracted", {
                "features": features,
                "word_count": word_count,
                "reference_count": ref_count,
                "has_abstract": has_abstract,
                "has_tables": has_tables,
            })

            # ── Step 4: Calculate Score ─────────────────────────────────
            yield _sse("progress", {"step": 4, "message": "Calculating overall score...", "percent": 55})

            score_result = self._calculate_score(features, field_config)
            overall_score = score_result["overall_score"]
            tier = score_result["tier"]
            tier_label = score_result["tier_label"]

            yield _sse("score", {
                "overall_score": overall_score,
                "tier": tier,
                "tier_label": tier_label,
                "score_breakdown": score_result["breakdown"],
            })

            # ── Step 5: Match Journals ──────────────────────────────────
            yield _sse("progress", {"step": 5, "message": "Matching to journals...", "percent": 65})

            journals = self._match_journals(field_config, tier)
            yield _sse("journals", journals)

            # ── Step 6: Detect Red Flags ────────────────────────────────
            yield _sse("progress", {"step": 6, "message": "Checking for red flags...", "percent": 75})

            flags_result = self._detect_red_flags(text, word_count, ref_count)
            yield _sse("red_flags", flags_result)

            # Adjust score for penalties
            if flags_result["total_penalty"] < 0:
                adjusted_score = max(0, overall_score + flags_result["total_penalty"])
                adjusted_tier, adjusted_label = self._get_tier(adjusted_score)
                yield _sse("score", {
                    "overall_score": adjusted_score,
                    "tier": adjusted_tier,
                    "tier_label": adjusted_label,
                    "score_breakdown": score_result["breakdown"],
                    "penalty_applied": flags_result["total_penalty"],
                    "original_score": overall_score,
                })

            # ── Step 7: Generate Recommendations ────────────────────────
            yield _sse("progress", {"step": 7, "message": "Generating recommendations...", "percent": 85})

            rec_buffer = ""
            for chunk in self._generate_recommendations_stream(
                field_config["label"], overall_score, tier, features, flags_result["flags"], journals
            ):
                rec_buffer += chunk
                yield _sse("recommendations", {"content": chunk})

            yield _sse("recommendations_done", {"full_text": rec_buffer})

            # ── Done ────────────────────────────────────────────────────
            elapsed = round(time.time() - start_time, 1)
            yield _sse("done", {"success": True, "analysis_time_seconds": elapsed})

        except Exception as e:
            import traceback
            traceback.print_exc()
            yield _sse("error", {"error": str(e)})

    # ── Private Methods ─────────────────────────────────────────────────────

    def _detect_field(self, text_excerpt: str) -> dict:
        prompt = (
            "You are an academic field classifier. Classify this manuscript excerpt into exactly one field.\n\n"
            "FIELDS:\n"
            "- economics\n"
            "- cs_data_science\n"
            "- biomedical\n"
            "- political_science\n\n"
            "Respond ONLY in valid JSON:\n"
            '{"field": "...", "confidence": 0.0-1.0, "subfield": "specific subfield", "reasoning": "one sentence"}\n\n'
            f"MANUSCRIPT EXCERPT:\n{text_excerpt}"
        )

        resp = self.openai.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=200,
        )
        raw = resp.choices[0].message.content.strip()
        # Extract JSON from potential markdown code blocks
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        return {"field": "economics", "confidence": 0.5, "subfield": "General", "reasoning": "Could not classify — defaulting to Economics"}

    def _extract_features(self, text_excerpt: str, field: str, field_config: dict) -> dict:
        feature_list = "\n".join(
            f"- {key}: {info['label']} (weight: {info['weight']*100:.0f}%)"
            for key, info in field_config["features"].items()
        )

        prompt = (
            f"You are a peer reviewer in {field_config['label']}. Score this manuscript on each feature below.\n\n"
            f"FEATURES TO SCORE (each 0-100):\n{feature_list}\n\n"
            "Respond ONLY in valid JSON — a dict where each key is the feature name and value is:\n"
            '{"score": 0-100, "details": "justification (2-3 sentences)", "citations": [{"text": "quoted or paraphrased evidence from the manuscript", "section": "which section it appears in"}], "suggested_references": [{"title": "Seminal paper title", "authors": "Author et al.", "year": "YYYY", "url": "DOI or URL if known", "relevance": "why this reference matters"}]}\n\n'
            "IMPORTANT:\n"
            "- In 'citations', quote specific passages from the manuscript that support your score.\n"
            "- In 'suggested_references', list 1-2 key papers the authors should cite or benchmark against. Include DOI URLs (https://doi.org/...) when possible.\n"
            "- If the manuscript already cites important works, mention that positively in 'details'.\n\n"
            "Example format:\n"
            '{"methodology": {"score": 72, "details": "Uses diff-in-diff with state-level variation, but lacks robustness checks like placebo tests or synthetic control comparison.", "citations": [{"text": "We exploit the staggered adoption of minimum wage laws across states", "section": "Methodology"}], "suggested_references": [{"title": "Difference-in-Differences with Variation in Treatment Timing", "authors": "Goodman-Bacon, A.", "year": "2021", "url": "https://doi.org/10.1016/j.jeconom.2021.03.014", "relevance": "Standard reference for staggered DiD designs"}]}}\n\n'
            f"MANUSCRIPT EXCERPT:\n{text_excerpt}"
        )

        resp = self.openai.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=2000,
        )
        raw = resp.choices[0].message.content.strip()
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group())
        else:
            parsed = {}

        # Ensure all features present with defaults
        result = {}
        for key, info in field_config["features"].items():
            if key in parsed and isinstance(parsed[key], dict):
                result[key] = {
                    "score": min(100, max(0, int(parsed[key].get("score", 50)))),
                    "weight": info["weight"],
                    "label": info["label"],
                    "details": parsed[key].get("details", ""),
                    "citations": parsed[key].get("citations", []),
                    "suggested_references": parsed[key].get("suggested_references", []),
                }
            else:
                result[key] = {
                    "score": 50,
                    "weight": info["weight"],
                    "label": info["label"],
                    "details": "Could not evaluate this feature.",
                    "citations": [],
                    "suggested_references": [],
                }
        return result

    def _calculate_score(self, features: dict, field_config: dict) -> dict:
        breakdown = []
        total = 0.0
        for key, feat in features.items():
            weighted = feat["score"] * feat["weight"]
            total += weighted
            breakdown.append({
                "feature": feat["label"],
                "score": feat["score"],
                "weight": feat["weight"],
                "weighted": round(weighted, 1),
            })

        overall = round(total)
        tier, tier_label = self._get_tier(overall)

        return {
            "overall_score": overall,
            "tier": tier,
            "tier_label": tier_label,
            "breakdown": breakdown,
        }

    def _get_tier(self, score: int) -> tuple:
        if score >= 85:
            return 1, "Tier 1 — Top Journal"
        elif score >= 65:
            return 2, "Tier 2 — Strong Journal"
        else:
            return 3, "Tier 3 — Solid Journal"

    def _match_journals(self, field_config: dict, tier: int) -> dict:
        journals = field_config["journals"]
        primary = journals.get(tier, [])
        stretch = journals.get(max(1, tier - 1), []) if tier > 1 else []
        safe = journals.get(min(3, tier + 1), []) if tier < 3 else []

        return {
            "primary_matches": primary,
            "stretch_matches": stretch,
            "safe_matches": safe,
        }

    def _detect_red_flags(self, text: str, word_count: int, ref_count: int) -> dict:
        flags = []
        total_penalty = 0

        for check in RED_FLAG_CHECKS:
            triggered = False

            if check["check"] == "missing" and check["pattern"]:
                if not re.search(check["pattern"], text, re.IGNORECASE):
                    triggered = True
            elif check["check"] == "ref_count_low":
                if 0 < ref_count < 15:
                    triggered = True
            elif check["check"] == "word_count_low":
                if word_count < 3000:
                    triggered = True

            if triggered:
                flags.append({
                    "severity": check["severity"],
                    "issue": check["issue"],
                    "penalty": check["penalty"],
                    "fix": check["fix"],
                })
                total_penalty += check["penalty"]

        return {"flags": flags, "total_penalty": total_penalty}

    def _extract_references_section(self, text: str) -> str | None:
        match = re.search(r'\b(references|bibliography)\b', text, re.IGNORECASE)
        if match:
            return text[match.start():]
        return None

    def _count_references(self, ref_text: str) -> int:
        # Count numbered references like [1], [2] or 1. Author...
        numbered = re.findall(r'^\s*\[?\d+[\].]', ref_text, re.MULTILINE)
        if len(numbered) >= 3:
            return len(numbered)
        # Count lines that look like references (Author, Year pattern)
        author_lines = re.findall(r'^\s*[A-Z][a-z]+.*\(\d{4}\)', ref_text, re.MULTILINE)
        return max(len(author_lines), len(numbered))

    def _generate_recommendations_stream(self, field_label, score, tier, features, flags, journals):
        feature_summary = "\n".join(
            f"- {f['label']}: {f['score']}/100 — {f.get('details', '')}"
            for f in features.values()
        )
        flag_summary = "\n".join(f"- [{f['severity']}] {f['issue']}" for f in flags) if flags else "None detected"
        journal_names = ", ".join(j["name"] for j in journals.get("primary_matches", []))

        prompt = (
            f"You are a journal submission advisor in {field_label}. Given the manuscript analysis:\n"
            f"- Score: {score}/100 (Tier {tier})\n"
            f"- Feature breakdown:\n{feature_summary}\n"
            f"- Red flags:\n{flag_summary}\n"
            f"- Target journals: {journal_names}\n\n"
            "Provide 2-3 actionable recommendations per category:\n"
            "1. **Methodological Upgrades** — what experiments/analyses to add\n"
            "2. **Literature Gaps** — specific missing citations or bodies of work\n"
            "3. **Structural & Formatting** — what to restructure\n\n"
            "IMPORTANT FORMATTING RULES:\n"
            "- Be specific, reference actual manuscript content.\n"
            "- For every recommended paper/reference, include a clickable markdown link with the DOI URL.\n"
            "  Format: [Author et al. (Year) - Paper Title](https://doi.org/10.xxxx/xxxxx)\n"
            "- For methodology suggestions, link to the seminal paper describing the method.\n"
            "- Include at least 2-3 specific paper citations with DOI links per category.\n"
            "- Use markdown formatting throughout.\n"
        )

        for chunk in self.openai.chat_completion_stream(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=1500,
        ):
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content


# ── Singleton ───────────────────────────────────────────────────────────────

_journal_scorer_service = None


def get_journal_scorer_service() -> JournalScorerService:
    global _journal_scorer_service
    if _journal_scorer_service is None:
        _journal_scorer_service = JournalScorerService()
    return _journal_scorer_service
