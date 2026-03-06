"""
High-Impact Journal Predictor — Core Analysis Pipeline V2
10-step pipeline with 18 fields, 3× consistency scoring, real journal data,
landscape positioning, and CrossRef DOI verification.
"""

import json
import re
import time
import statistics
from typing import Generator, Dict, List, Optional

from parsers.document_parser import DocumentParser
from services.openai_client import get_openai_client


# ── 18 Field Configurations with Scoring Weights ────────────────────────────

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
    },
    "physics": {
        "label": "Physics",
        "features": {
            "theoretical_rigor": {"label": "Theoretical Rigor", "weight": 0.25},
            "experimental_design": {"label": "Experimental Design", "weight": 0.25},
            "novelty": {"label": "Novelty & Contribution", "weight": 0.20},
            "literature": {"label": "Literature Coverage", "weight": 0.15},
            "writing": {"label": "Writing Quality", "weight": 0.10},
            "data_quality": {"label": "Data Quality", "weight": 0.05},
        },
    },
    "chemistry": {
        "label": "Chemistry",
        "features": {
            "experimental_methodology": {"label": "Experimental Methodology", "weight": 0.25},
            "analytical_rigor": {"label": "Analytical Rigor", "weight": 0.20},
            "novelty": {"label": "Novelty & Contribution", "weight": 0.20},
            "literature": {"label": "Literature Coverage", "weight": 0.15},
            "writing": {"label": "Writing Quality", "weight": 0.10},
            "data_quality": {"label": "Data / Reproducibility", "weight": 0.10},
        },
    },
    "biology": {
        "label": "Biology",
        "features": {
            "experimental_design": {"label": "Experimental Design", "weight": 0.25},
            "statistical_rigor": {"label": "Statistical Rigor", "weight": 0.20},
            "novelty": {"label": "Novelty & Contribution", "weight": 0.20},
            "literature": {"label": "Literature Coverage", "weight": 0.15},
            "writing": {"label": "Writing Quality", "weight": 0.10},
            "data_quality": {"label": "Data Quality", "weight": 0.10},
        },
    },
    "psychology": {
        "label": "Psychology",
        "features": {
            "study_design": {"label": "Study Design", "weight": 0.25},
            "statistical_rigor": {"label": "Statistical Rigor", "weight": 0.25},
            "novelty": {"label": "Novelty & Contribution", "weight": 0.15},
            "literature": {"label": "Literature Coverage", "weight": 0.15},
            "writing": {"label": "Writing Quality", "weight": 0.10},
            "data_quality": {"label": "Data / Reproducibility", "weight": 0.10},
        },
    },
    "sociology": {
        "label": "Sociology",
        "features": {
            "theoretical_framework": {"label": "Theoretical Framework", "weight": 0.25},
            "methodology_evidence": {"label": "Methodology & Evidence", "weight": 0.25},
            "novelty": {"label": "Novelty & Contribution", "weight": 0.15},
            "literature": {"label": "Literature Coverage", "weight": 0.15},
            "writing": {"label": "Writing Quality", "weight": 0.10},
            "data_quality": {"label": "Data Quality", "weight": 0.10},
        },
    },
    "engineering": {
        "label": "Engineering",
        "features": {
            "technical_novelty": {"label": "Technical Novelty", "weight": 0.25},
            "experimental_validation": {"label": "Experimental Validation", "weight": 0.25},
            "practical_impact": {"label": "Practical Impact", "weight": 0.15},
            "literature": {"label": "Literature Coverage", "weight": 0.15},
            "writing": {"label": "Writing Quality", "weight": 0.10},
            "data_quality": {"label": "Data Quality", "weight": 0.10},
        },
    },
    "mathematics": {
        "label": "Mathematics",
        "features": {
            "theoretical_depth": {"label": "Theoretical Depth", "weight": 0.30},
            "proof_rigor": {"label": "Proof Rigor", "weight": 0.25},
            "novelty": {"label": "Novelty & Contribution", "weight": 0.20},
            "literature": {"label": "Literature Coverage", "weight": 0.15},
            "writing": {"label": "Writing Quality", "weight": 0.10},
        },
    },
    "environmental_science": {
        "label": "Environmental Science",
        "features": {
            "methodology": {"label": "Methodology", "weight": 0.25},
            "data_analysis": {"label": "Data Analysis", "weight": 0.20},
            "novelty": {"label": "Novelty & Contribution", "weight": 0.20},
            "literature": {"label": "Literature Coverage", "weight": 0.15},
            "writing": {"label": "Writing Quality", "weight": 0.10},
            "policy_relevance": {"label": "Policy Relevance", "weight": 0.10},
        },
    },
    "law": {
        "label": "Law",
        "features": {
            "legal_analysis": {"label": "Legal Analysis", "weight": 0.30},
            "argumentation": {"label": "Argumentation Quality", "weight": 0.25},
            "novelty": {"label": "Novelty & Contribution", "weight": 0.15},
            "literature": {"label": "Literature / Case Coverage", "weight": 0.15},
            "writing": {"label": "Writing Quality", "weight": 0.15},
        },
    },
    "education": {
        "label": "Education",
        "features": {
            "research_design": {"label": "Research Design", "weight": 0.25},
            "methodology": {"label": "Methodology & Analysis", "weight": 0.25},
            "novelty": {"label": "Novelty & Contribution", "weight": 0.15},
            "literature": {"label": "Literature Coverage", "weight": 0.15},
            "writing": {"label": "Writing Quality", "weight": 0.10},
            "practical_implications": {"label": "Practical Implications", "weight": 0.10},
        },
    },
    "business_management": {
        "label": "Business & Management",
        "features": {
            "theoretical_framework": {"label": "Theoretical Framework", "weight": 0.20},
            "methodology": {"label": "Methodology", "weight": 0.25},
            "novelty": {"label": "Novelty & Contribution", "weight": 0.20},
            "literature": {"label": "Literature Coverage", "weight": 0.15},
            "writing": {"label": "Writing Quality", "weight": 0.10},
            "practical_relevance": {"label": "Practical Relevance", "weight": 0.10},
        },
    },
    "history": {
        "label": "History",
        "features": {
            "primary_sources": {"label": "Primary Source Analysis", "weight": 0.30},
            "argumentation": {"label": "Argumentation & Interpretation", "weight": 0.25},
            "novelty": {"label": "Novelty & Contribution", "weight": 0.15},
            "historiography": {"label": "Historiographical Coverage", "weight": 0.15},
            "writing": {"label": "Writing Quality", "weight": 0.15},
        },
    },
    "philosophy": {
        "label": "Philosophy",
        "features": {
            "argumentation": {"label": "Argumentation Quality", "weight": 0.30},
            "conceptual_clarity": {"label": "Conceptual Clarity", "weight": 0.25},
            "novelty": {"label": "Novelty & Contribution", "weight": 0.15},
            "literature": {"label": "Literature Engagement", "weight": 0.15},
            "writing": {"label": "Writing Quality", "weight": 0.15},
        },
    },
    "linguistics": {
        "label": "Linguistics",
        "features": {
            "theoretical_framework": {"label": "Theoretical Framework", "weight": 0.25},
            "methodology": {"label": "Methodology & Analysis", "weight": 0.25},
            "novelty": {"label": "Novelty & Contribution", "weight": 0.20},
            "literature": {"label": "Literature Coverage", "weight": 0.15},
            "writing": {"label": "Writing Quality", "weight": 0.10},
            "data_quality": {"label": "Data Quality", "weight": 0.05},
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

MAX_FEATURE_CHARS = 100000  # max chars sent for feature extraction (~25K tokens)
CONSISTENCY_CHUNK = 12000   # chars sent for each consistency run (cheaper)
CONSISTENCY_RUNS = 3        # number of scoring runs for consistency


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


class JournalScorerService:
    def __init__(self):
        self.openai = get_openai_client()
        self.parser = DocumentParser()

    def analyze_manuscript(self, file_bytes: bytes, filename: str, manuscript_url: str = None) -> Generator[str, None, None]:
        """10-step pipeline — yields SSE events as analysis progresses."""
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

            yield _sse("progress", {"step": 1, "message": f"Parsed {word_count:,} words", "percent": 10})

            # ── Step 2: Detect Field ────────────────────────────────────
            yield _sse("progress", {"step": 2, "message": "Detecting academic field...", "percent": 12})

            field_result = self._detect_field(text[:8000])
            field = field_result["field"]
            field_config = FIELD_CONFIGS.get(field)

            if not field_config:
                # Fallback to closest match
                field = "economics"
                field_config = FIELD_CONFIGS["economics"]
                field_result["field"] = field
                field_result["reasoning"] = f"Field '{field_result.get('field', 'unknown')}' not recognized — defaulting to Economics"

            keywords = field_result.get("keywords", [])

            yield _sse("field_detected", {
                "field": field,
                "field_label": field_config["label"],
                "confidence": field_result["confidence"],
                "subfield": field_result["subfield"],
                "keywords": keywords,
                "reasoning": field_result["reasoning"],
            })

            # ── Step 3: Extract Features (full text) ─────────────────────
            yield _sse("progress", {"step": 3, "message": "Evaluating manuscript features...", "percent": 18})

            # Send full text (up to MAX_FEATURE_CHARS) for feature extraction
            analysis_text = text[:MAX_FEATURE_CHARS]
            char_info = f"{len(analysis_text):,} chars" + (" (full paper)" if len(analysis_text) == len(text) else f" of {len(text):,}")
            yield _sse("progress", {"step": 3, "message": f"Analyzing {char_info}...", "percent": 22})

            features = self._extract_features(analysis_text, field, field_config)

            yield _sse("features_extracted", {
                "features": features,
                "word_count": word_count,
                "reference_count": ref_count,
                "has_abstract": has_abstract,
                "has_tables": has_tables,
            })

            # ── Step 4: Consistency Check (3× scoring) ──────────────────
            yield _sse("progress", {"step": 4, "message": "Running consistency checks...", "percent": 32})

            consistency_result = self._run_consistency_check(analysis_text, field, field_config, features)

            yield _sse("consistency", consistency_result)

            # Use averaged scores from consistency check
            features = consistency_result["averaged_features"]

            # ── Step 5: Calculate Score ──────────────────────────────────
            yield _sse("progress", {"step": 5, "message": "Calculating overall score...", "percent": 50})

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

            # ── Step 6: Match Journals (keyword-based via OpenAlex) ──
            yield _sse("progress", {"step": 6, "message": "Finding relevant journals by keywords...", "percent": 58})

            journals = self._match_journals_by_keywords(keywords, field, tier)
            yield _sse("journals", journals)

            # ── Step 7: Landscape Position ──────────────────────────────
            yield _sse("progress", {"step": 7, "message": "Calculating landscape position...", "percent": 63})

            landscape = self._get_landscape_position(field, overall_score)
            yield _sse("landscape", landscape)

            # ── Step 8: Detect Red Flags ────────────────────────────────
            yield _sse("progress", {"step": 8, "message": "Checking for red flags...", "percent": 68})

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
                overall_score = adjusted_score
                tier = adjusted_tier

            # ── Step 9: Verify Citations (CrossRef) ─────────────────────
            yield _sse("progress", {"step": 9, "message": "Verifying citations...", "percent": 75})

            citation_result = self._verify_citations(text)
            yield _sse("citation_verification", citation_result)

            # ── Step 10: Generate Recommendations ───────────────────────
            yield _sse("progress", {"step": 10, "message": "Generating recommendations...", "percent": 82})

            rec_buffer = ""
            for chunk in self._generate_recommendations_stream(
                field_config["label"], overall_score, tier, features,
                flags_result["flags"], journals, landscape, citation_result,
                keywords=keywords, subfield=field_result.get("subfield", "")
            ):
                rec_buffer += chunk
                yield _sse("recommendations", {"content": chunk})

            yield _sse("recommendations_done", {"full_text": rec_buffer})

            # ── Done ────────────────────────────────────────────────────
            elapsed = round(time.time() - start_time, 1)
            done_data = {"success": True, "analysis_time_seconds": elapsed}
            if manuscript_url:
                done_data["manuscript_url"] = manuscript_url
            yield _sse("done", done_data)

        except Exception as e:
            import traceback
            traceback.print_exc()
            yield _sse("error", {"error": str(e)})

    # ── Private Methods ─────────────────────────────────────────────────────

    def _detect_field(self, text_excerpt: str) -> dict:
        field_list = "\n".join(f"- {key}" for key in FIELD_CONFIGS.keys())

        prompt = (
            "You are an academic field classifier and keyword extractor. "
            "Classify this manuscript excerpt into exactly one field AND extract specific research keywords.\n\n"
            f"FIELDS:\n{field_list}\n\n"
            "Respond ONLY in valid JSON:\n"
            '{"field": "...", "confidence": 0.0-1.0, "subfield": "specific subfield", '
            '"keywords": ["kw1", "kw2", "kw3", "...", "kw20"], '
            '"reasoning": "one sentence"}\n\n'
            "KEYWORD RULES:\n"
            "- Extract exactly 20 specific research keywords/phrases from the manuscript\n"
            "- Include a mix of: specific techniques (e.g. 'LC-MS/MS', 'CRISPR-Cas9', 'Western blot'), "
            "biological targets/pathways (e.g. 'iron metabolism', 'p53', 'mTOR signaling'), "
            "disease areas (e.g. 'pancreatic cancer', 'ferroptosis', 'glioblastoma'), "
            "methodologies (e.g. 'proteomics', 'single-cell RNA-seq', 'xenograft model'), "
            "and key molecules/genes/proteins studied in the paper\n"
            "- Do NOT use generic terms like 'biology', 'research', 'analysis' — be specific\n"
            "- These keywords will be used to find top professors and their publishing venues\n\n"
            f"MANUSCRIPT EXCERPT:\n{text_excerpt}"
        )

        resp = self.openai.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=600,
        )
        raw = resp.choices[0].message.content.strip()
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            # Validate the field is in our config
            if result.get("field") not in FIELD_CONFIGS:
                result["field"] = "economics"
                result["confidence"] = 0.5
            # Ensure keywords exist and have enough
            if not result.get("keywords") or not isinstance(result["keywords"], list):
                result["keywords"] = [result.get("subfield", "general")]
            return result
        return {"field": "economics", "confidence": 0.5, "subfield": "General", "keywords": ["general"], "reasoning": "Could not classify — defaulting to Economics"}

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
            f"MANUSCRIPT TEXT:\n{text_excerpt}"
        )

        resp = self.openai.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=3000,
        )
        raw = resp.choices[0].message.content.strip()
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group())
        else:
            parsed = {}

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

    def _run_consistency_check(self, text: str, field: str, field_config: dict, initial_features: dict) -> dict:
        """Run 2 additional scoring rounds and average with the initial to get consistent scores."""
        all_runs = [
            {k: v["score"] for k, v in initial_features.items()}
        ]

        # Run 2 more scoring rounds with slightly different temperature
        for run_idx in range(CONSISTENCY_RUNS - 1):
            try:
                feature_list = "\n".join(
                    f"- {key}: {info['label']}"
                    for key, info in field_config["features"].items()
                )
                prompt = (
                    f"You are a peer reviewer in {field_config['label']}. "
                    f"Score this manuscript on each feature (0-100). "
                    f"Respond ONLY in JSON: {{\"feature_key\": score_number, ...}}\n\n"
                    f"Features:\n{feature_list}\n\n"
                    f"MANUSCRIPT:\n{text[:CONSISTENCY_CHUNK]}"
                )
                resp = self.openai.chat_completion(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3 + (run_idx * 0.1),
                    max_tokens=500,
                )
                raw = resp.choices[0].message.content.strip()
                json_match = re.search(r'\{.*\}', raw, re.DOTALL)
                if json_match:
                    scores = json.loads(json_match.group())
                    run = {}
                    for key in field_config["features"]:
                        val = scores.get(key, 50)
                        if isinstance(val, dict):
                            val = val.get("score", 50)
                        run[key] = min(100, max(0, int(val)))
                    all_runs.append(run)
            except Exception as e:
                print(f"[Journal] Consistency run {run_idx + 1} failed: {e}")

        # Average scores across runs
        averaged_features = {}
        high_variance_features = []

        for key in field_config["features"]:
            scores_for_key = [run.get(key, 50) for run in all_runs]
            avg = round(statistics.mean(scores_for_key))
            std = round(statistics.stdev(scores_for_key), 1) if len(scores_for_key) > 1 else 0

            # Copy from initial features but update score
            averaged_features[key] = dict(initial_features.get(key, {
                "score": avg,
                "weight": field_config["features"][key]["weight"],
                "label": field_config["features"][key]["label"],
                "details": "",
                "citations": [],
                "suggested_references": [],
            }))
            averaged_features[key]["score"] = avg

            if std > 15:
                high_variance_features.append({
                    "feature": key,
                    "label": field_config["features"][key]["label"],
                    "std": std,
                    "scores": scores_for_key,
                })

        return {
            "scores_by_run": all_runs,
            "averaged_scores": {k: v["score"] for k, v in averaged_features.items()},
            "high_variance_features": high_variance_features,
            "num_runs": len(all_runs),
            "averaged_features": averaged_features,
        }

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

    # Mega-journals that publish everything — demote to Safe Options only
    MEGA_JOURNALS = {
        "plos one", "scientific reports", "frontiers in medicine",
        "biomed research international", "medicine", "cureus",
        "heliyon", "ieee access", "sage open", "peerj",
    }

    def _match_journals_by_keywords(self, keywords: list, field: str, tier: int) -> dict:
        """Professor-based journal discovery pipeline:
        1) Extract 20 keywords from paper (done upstream)
        2) Find top-cited papers matching keywords → extract top 100 authors
        3) Find where those top authors publish (recent 3 years)
        4) Rank journals by citedness, split into Target (5 top + 5 niche) / Stretch / Safe
        """
        import requests as req
        from collections import Counter

        OPENALEX_BASE = "https://api.openalex.org"
        OPENALEX_EMAIL = "prmogathala@gmail.com"
        HEADERS = {"User-Agent": f"2ndBrain/1.0 (mailto:{OPENALEX_EMAIL})", "Accept": "application/json"}

        def _api_get(url: str, timeout: int = 15):
            resp = req.get(url, headers=HEADERS, timeout=timeout)
            return resp.json() if resp.status_code == 200 else None

        def _is_mega(name: str) -> bool:
            return name.lower().strip() in self.MEGA_JOURNALS

        try:
            # ── Step 1: Find top-cited papers matching keywords ─────────
            # Use multiple keyword combinations for broad coverage
            all_author_ids = Counter()  # author_id -> total citations across matches

            search_queries = [
                " ".join(keywords[:8]),   # broad combined
                " ".join(keywords[:4]),   # tighter combo
                " ".join(keywords[4:10]), # middle keywords
            ]
            # Add 2-3 individual specific keywords
            for kw in keywords[:3]:
                search_queries.append(kw)

            for query in search_queries:
                url = (
                    f"{OPENALEX_BASE}/works"
                    f"?search={req.utils.quote(query)}"
                    f"&filter=type:article,publication_year:2020-2026"
                    f"&sort=cited_by_count:desc"
                    f"&per_page=50"
                    f"&select=id,authorships,cited_by_count"
                    f"&mailto={OPENALEX_EMAIL}"
                )
                data = _api_get(url)
                if not data:
                    continue
                for work in data.get("results", []):
                    cited = work.get("cited_by_count", 0)
                    for authorship in work.get("authorships", [])[:5]:  # top 5 authors per paper
                        author = authorship.get("author", {})
                        aid = author.get("id", "")
                        if aid:
                            all_author_ids[aid] += cited

            if not all_author_ids:
                print(f"[Journal] No authors found from keyword search, falling back")
                return self._match_journals_from_db(field, tier)

            # ── Step 2: Take top 100 authors by citation weight ─────────
            top_authors = [aid for aid, _ in all_author_ids.most_common(100)]
            print(f"[Journal] Found {len(all_author_ids)} unique authors, using top {len(top_authors)}")

            # ── Step 3: Find where these authors publish ────────────────
            # OpenAlex pipe filter supports ~50 IDs per call, so split into 2 batches
            journal_counts = Counter()  # source_id -> paper count
            journal_names = {}          # source_id -> display_name

            for batch_start in range(0, len(top_authors), 50):
                batch = top_authors[batch_start:batch_start + 50]
                author_filter = "|".join(batch)
                url = (
                    f"{OPENALEX_BASE}/works"
                    f"?filter=authorships.author.id:{author_filter},"
                    f"type:article,"
                    f"primary_location.source.type:journal,"
                    f"publication_year:2022-2026"
                    f"&group_by=primary_location.source.id"
                    f"&per_page=50"
                    f"&mailto={OPENALEX_EMAIL}"
                )
                data = _api_get(url)
                if not data:
                    continue
                for g in data.get("group_by", []):
                    sid = g.get("key", "")
                    name = g.get("key_display_name", "")
                    count = g.get("count", 0)
                    if sid and name:
                        journal_counts[sid] += count
                        journal_names[sid] = name

            if not journal_counts:
                print(f"[Journal] No journals found from author publications, falling back")
                return self._match_journals_from_db(field, tier)

            print(f"[Journal] Top authors publish in {len(journal_counts)} journals")

            # ── Step 4: Enrich top 40 journals with metadata ────────────
            top_journal_ids = [sid for sid, _ in journal_counts.most_common(40)]
            pipe_filter = "|".join(top_journal_ids[:30])
            meta_url = (
                f"{OPENALEX_BASE}/sources"
                f"?filter=ids.openalex:{pipe_filter}"
                f"&per_page=30"
                f"&mailto={OPENALEX_EMAIL}"
            )

            enriched = []
            data = _api_get(meta_url)
            if data:
                for src in data.get("results", []):
                    oa_id = src.get("id", "")
                    summary = src.get("summary_stats", {})
                    h_index = summary.get("h_index", 0) or 0
                    citedness = summary.get("2yr_mean_citedness", 0.0) or 0.0
                    works = src.get("works_count", 0) or 0
                    if works < 100 or h_index < 5:
                        continue
                    enriched.append({
                        "name": src.get("display_name", "Unknown"),
                        "h_index": h_index,
                        "citedness_2yr": round(citedness, 2),
                        "works_count": works,
                        "impact_factor": round(citedness, 1),
                        "sjr_quartile": None,
                        "composite_score": 0,
                        "homepage_url": src.get("homepage_url") or "",
                        "publisher": src.get("host_organization_name") or "",
                        "prof_papers": journal_counts.get(oa_id, 0),
                    })

            # Also enrich IDs 30-40 if we have them
            if len(top_journal_ids) > 30:
                pipe_filter2 = "|".join(top_journal_ids[30:40])
                meta_url2 = (
                    f"{OPENALEX_BASE}/sources"
                    f"?filter=ids.openalex:{pipe_filter2}"
                    f"&per_page=10"
                    f"&mailto={OPENALEX_EMAIL}"
                )
                data2 = _api_get(meta_url2)
                if data2:
                    for src in data2.get("results", []):
                        oa_id = src.get("id", "")
                        summary = src.get("summary_stats", {})
                        h_index = summary.get("h_index", 0) or 0
                        citedness = summary.get("2yr_mean_citedness", 0.0) or 0.0
                        works = src.get("works_count", 0) or 0
                        if works < 100 or h_index < 5:
                            continue
                        enriched.append({
                            "name": src.get("display_name", "Unknown"),
                            "h_index": h_index,
                            "citedness_2yr": round(citedness, 2),
                            "works_count": works,
                            "impact_factor": round(citedness, 1),
                            "sjr_quartile": None,
                            "composite_score": 0,
                            "homepage_url": src.get("homepage_url") or "",
                            "publisher": src.get("host_organization_name") or "",
                            "prof_papers": journal_counts.get(oa_id, 0),
                        })

            if not enriched:
                print(f"[Journal] No enriched journals, falling back")
                return self._match_journals_from_db(field, tier)

            # ── Step 5: Split into Stretch / Target / Safe ─────────────
            # Separate mega-journals
            quality = [j for j in enriched if not _is_mega(j["name"])]
            megas = [j for j in enriched if _is_mega(j["name"])]

            # Sort quality journals by citedness (quality indicator)
            quality.sort(key=lambda j: j["citedness_2yr"], reverse=True)

            # Stretch = top 5 most prestigious (aspirational — Nature, Cell, etc.)
            stretch = quality[:5]

            # Target = next 10 mid-range journals (realistic for the paper)
            target = quality[5:15]

            # Safe = mega-journals + lower-ranked quality (fallback options)
            safe = megas[:3]
            safe.extend(quality[15:17])

            return {
                "primary_matches": target,
                "stretch_matches": stretch,
                "safe_matches": safe[:5],
            }
        except Exception as e:
            print(f"[Journal] Professor-based journal matching failed: {e}")
            return self._match_journals_from_db(field, tier)

    def _match_journals_from_db(self, field: str, tier: int) -> dict:
        """Fallback: match journals from the pre-populated database by field."""
        try:
            from services.journal_data_service import get_journal_data_service
            svc = get_journal_data_service()

            primary = svc.get_journals_for_field(field, tier=tier)
            stretch = svc.get_journals_for_field(field, tier=max(1, tier - 1)) if tier > 1 else []
            safe = svc.get_journals_for_field(field, tier=min(3, tier + 1)) if tier < 3 else []

            return {
                "primary_matches": primary[:8],
                "stretch_matches": stretch[:5],
                "safe_matches": safe[:5],
            }
        except Exception as e:
            print(f"[Journal] DB journal matching also failed: {e}")
            return {"primary_matches": [], "stretch_matches": [], "safe_matches": []}

    def _get_landscape_position(self, field: str, score: float) -> dict:
        """Get the manuscript's position in the journal landscape."""
        try:
            from services.journal_data_service import get_journal_data_service
            svc = get_journal_data_service()
            landscape = svc.get_journal_landscape(field)
            percentile = svc.get_percentile_for_score(field, score)
            landscape["percentile"] = percentile
            return landscape
        except Exception as e:
            print(f"[Journal] Landscape position failed: {e}")
            return {
                "field": field,
                "total_journals": 0,
                "percentile": 50.0,
                "median_composite": 50,
                "tier1_threshold": 85,
                "tier2_threshold": 65,
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
                issue_text = check["issue"]
                fix_text = check["fix"]
                # Include actual counts in the message for clarity
                if check["id"] == "low_references":
                    issue_text = f"Only {ref_count} references detected (fewer than 15)"
                    fix_text = f"Expand your literature review — you have {ref_count} references, top journals expect 30-60"
                elif check["id"] == "too_short":
                    issue_text = f"Manuscript is {word_count:,} words (under 3,000)"

                flags.append({
                    "severity": check["severity"],
                    "issue": issue_text,
                    "penalty": check["penalty"],
                    "fix": fix_text,
                })
                total_penalty += check["penalty"]

        return {"flags": flags, "total_penalty": total_penalty, "reference_count": ref_count}

    def _verify_citations(self, text: str) -> dict:
        """Extract DOIs from text and verify them via CrossRef."""
        try:
            from services.crossref_service import get_crossref_service
            crossref = get_crossref_service()
            dois = crossref.extract_dois_from_text(text)

            if not dois:
                return {"verified": [], "unverified": [], "verification_rate": 0, "total_dois_found": 0}

            results = crossref.verify_dois(dois)

            verified = []
            unverified = []
            for doi, info in results.items():
                entry = {"doi": doi, **info}
                if info.get("valid"):
                    verified.append(entry)
                else:
                    unverified.append(entry)

            rate = round(len(verified) / len(results) * 100, 1) if results else 0

            return {
                "verified": verified,
                "unverified": unverified,
                "verification_rate": rate,
                "total_dois_found": len(dois),
            }
        except Exception as e:
            print(f"[Journal] Citation verification failed: {e}")
            return {"verified": [], "unverified": [], "verification_rate": 0, "total_dois_found": 0, "error": str(e)}

    def _extract_references_section(self, text: str) -> Optional[str]:
        """Extract references section — find the LAST occurrence of 'References'/'Bibliography'
        as a section header (not inline mentions like 'see references')."""
        # Look for References/Bibliography as a standalone heading (last occurrence)
        matches = list(re.finditer(
            r'(?:^|\n)\s*(?:#{1,3}\s*)?(?:REFERENCES|References|BIBLIOGRAPHY|Bibliography|WORKS\s+CITED|Works\s+Cited|LITERATURE\s+CITED)\s*\n',
            text
        ))
        if matches:
            return text[matches[-1].start():]

        # Fallback: last occurrence of the word as a heading-like line
        matches = list(re.finditer(
            r'(?:^|\n)\s*(?:references|bibliography)\s*$',
            text,
            re.IGNORECASE | re.MULTILINE
        ))
        if matches:
            return text[matches[-1].start():]

        return None

    def _count_references(self, ref_text: str) -> int:
        """Count references using multiple format detection strategies."""
        counts = []

        # Strategy 1: Numbered format [1], [2], ... or (1), (2), ...
        bracketed = re.findall(r'^\s*\[\d+\]', ref_text, re.MULTILINE)
        counts.append(len(bracketed))

        # Strategy 2: Numbered format 1. Author or 1 Author (Vancouver style)
        numbered_dot = re.findall(r'^\s*\d{1,3}[.\)]\s+[A-Z]', ref_text, re.MULTILINE)
        counts.append(len(numbered_dot))

        # Strategy 3: APA-style — Author, A. B. (2024) or Author et al. (2024)
        apa_style = re.findall(
            r'^\s*[A-Z][a-zà-ž\-]+[\s,].*?\(\d{4}[a-z]?\)',
            ref_text,
            re.MULTILINE
        )
        counts.append(len(apa_style))

        # Strategy 4: DOI-based — count unique DOIs in the references section
        dois = re.findall(r'10\.\d{4,9}/[^\s\]>]+', ref_text)
        counts.append(len(set(dois)))

        # Strategy 5: Blank-line-separated entries (each ref is a paragraph)
        # Split by blank lines and count entries that look like citations
        paragraphs = re.split(r'\n\s*\n', ref_text)
        citation_paras = [
            p for p in paragraphs
            if p.strip() and (
                re.search(r'\d{4}', p) and  # has a year
                len(p.strip()) > 30         # long enough to be a real citation
            )
        ]
        if len(citation_paras) >= 3:
            counts.append(len(citation_paras))

        best = max(counts) if counts else 0
        return best

    def _generate_recommendations_stream(self, field_label, score, tier, features, flags, journals, landscape, citations, keywords=None, subfield=""):
        feature_summary = "\n".join(
            f"- {f['label']}: {f['score']}/100 — {f.get('details', '')}"
            for f in features.values()
        )
        flag_summary = "\n".join(f"- [{f['severity']}] {f['issue']}" for f in flags) if flags else "None detected"

        # Get journal names from primary matches
        primary = journals.get("primary_matches", [])
        if primary and isinstance(primary[0], dict):
            journal_names = ", ".join(j.get("name", str(j)) for j in primary[:5])
        else:
            journal_names = "Various journals in the field"

        # Landscape context
        landscape_info = ""
        if landscape.get("total_journals", 0) > 0:
            landscape_info = (
                f"\n- Landscape: Your score places you at the {landscape.get('percentile', 50)}th percentile "
                f"among {landscape.get('total_journals', 0)} journals in {field_label}. "
                f"Tier 1 threshold: {landscape.get('tier1_threshold', 85)} composite score."
            )

        # Citation context
        citation_info = ""
        if citations.get("total_dois_found", 0) > 0:
            citation_info = (
                f"\n- Citations verified: {len(citations.get('verified', []))}/{citations.get('total_dois_found', 0)} DOIs confirmed valid."
            )

        # Keywords context
        keywords_info = ""
        if keywords:
            keywords_info = f"\n- Paper keywords: {', '.join(keywords)}"
        if subfield:
            keywords_info += f"\n- Specific subfield: {subfield}"

        prompt = (
            f"You are a senior research advisor specializing in {field_label}"
            f"{(' / ' + subfield) if subfield else ''}. "
            f"Given this manuscript analysis:\n"
            f"- Score: {score}/100 (Tier {tier})\n"
            f"- Feature breakdown:\n{feature_summary}\n"
            f"- Red flags:\n{flag_summary}\n"
            f"- Target journals: {journal_names}"
            f"{keywords_info}"
            f"{landscape_info}"
            f"{citation_info}\n\n"

            "## SECTION 1: Specific Experiments to Strengthen This Paper\n\n"
            "List exactly 3-5 specific experiments as a numbered list. For EACH experiment, you MUST include ALL of:\n"
            "- **Experiment name** — a clear, specific title\n"
            "- **Model system** — exact cell lines (e.g., 'HCT116 and SW480 colorectal cancer cells'), "
            "animal models (e.g., 'C57BL/6 xenograft mice'), databases (e.g., 'TCGA-COAD cohort'), "
            "or clinical datasets to use\n"
            "- **Technique/Protocol** — exact method (e.g., 'LC-MS/MS with TMT 16-plex labeling', "
            "'Western blot for cleaved caspase-3', 'ChIP-seq for H3K27ac')\n"
            "- **Controls** — what positive/negative controls to include\n"
            "- **Expected outcome** — what result would strengthen the paper and why\n"
            "- **Reference** — cite the seminal paper that established this method with DOI link\n\n"
            "CRITICAL: These must be experiments that are directly relevant to THIS paper's specific topic "
            f"({', '.join(keywords[:4]) if keywords else field_label}). "
            "Do NOT give generic advice like 'do dose-response studies'. "
            "Give the exact experiment a PI would assign to a grad student.\n\n"

            "## SECTION 2: Missing Key References\n\n"
            "List 5-8 specific papers that MUST be cited in this manuscript. For each:\n"
            "- Full citation: [Author et al. (Year) - Paper Title](https://doi.org/10.xxxx/xxxxx)\n"
            "- One sentence on why this specific paper is essential for this manuscript\n"
            "- Where in the manuscript it should be cited (Introduction, Methods, Discussion)\n\n"

            "## SECTION 3: Structural Improvements\n\n"
            "2-3 specific structural changes to improve acceptance chances.\n\n"

            "FORMATTING RULES:\n"
            "- Use markdown with numbered lists for experiments\n"
            "- Every paper citation MUST include a DOI link: [Author et al. (Year)](https://doi.org/...)\n"
            "- Be extremely specific — no vague advice\n"
        )

        for chunk in self.openai.chat_completion_stream(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=3000,
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
