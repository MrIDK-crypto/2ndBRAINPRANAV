"""
High-Impact Journal Predictor — Core Analysis Pipeline V2
10-step pipeline with 18 fields, 3× consistency scoring, real journal data,
landscape positioning, and CrossRef DOI verification.
"""

import json
import os
import re
import time
import statistics
import httpx
from datetime import datetime
from typing import Generator, Dict, List, Optional
from openai import AzureOpenAI, OpenAI

from parsers.document_parser import DocumentParser
from services.openai_client import get_openai_client
from services.openalex_search_service import OpenAlexSearchService

# HIJ-specific timeout: 5 minutes total, 60s connect (longer for complex analyses)
_HIJ_TIMEOUT = httpx.Timeout(300.0, connect=60.0)


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

# ── Paper-Type-Aware Feature Overrides ─────────────────────────────────────
# When a paper is detected as a non-experimental type, these features REPLACE
# the field-specific experimental features. This prevents review papers from
# being scored on "Experimental Rigor" or "Statistical Methods".

PAPER_TYPE_FEATURE_OVERRIDES = {
    "review": {
        "label_suffix": " (Review)",
        "features": {
            "literature_scope": {"label": "Literature Scope & Comprehensiveness", "weight": 0.25, "criteria": "Does it cover the breadth of the field? Recent + foundational papers?"},
            "synthesis_quality": {"label": "Synthesis & Integration", "weight": 0.25, "criteria": "Does it connect disparate findings into coherent narrative?"},
            "critical_analysis": {"label": "Critical Analysis", "weight": 0.20, "criteria": "Does it critique methodologies, identify contradictions, evaluate evidence?"},
            "gap_identification": {"label": "Gap Identification & Future Directions", "weight": 0.15, "criteria": "Does it identify unstudied areas and propose research directions?"},
            "writing": {"label": "Writing Quality & Organization", "weight": 0.10, "criteria": "Clear structure, logical flow, accessible to target audience?"},
            "practical_applicability": {"label": "Practical Applicability", "weight": 0.05, "criteria": "Is the perspective actionable for researchers/practitioners?"},
        },
    },
    "meta_analysis": {
        "label_suffix": " (Meta-Analysis)",
        "features": {
            "search_methodology": {"label": "Search Strategy & Methodology", "weight": 0.25, "criteria": "PRISMA compliance, databases searched, inclusion/exclusion criteria"},
            "statistical_synthesis": {"label": "Statistical Synthesis Quality", "weight": 0.25, "criteria": "Effect size calculations, heterogeneity assessment (I²), forest plots"},
            "bias_assessment": {"label": "Bias & Quality Assessment", "weight": 0.20, "criteria": "Risk of bias tools used, publication bias tested (funnel plot, Egger's)"},
            "study_selection": {"label": "Study Selection & Inclusion", "weight": 0.15, "criteria": "Appropriate inclusion criteria, sufficient studies included"},
            "interpretation": {"label": "Interpretation & Clinical Significance", "weight": 0.10, "criteria": "Meaningful conclusions, limitations acknowledged"},
            "writing": {"label": "Writing Quality", "weight": 0.05},
        },
    },
    "case_report": {
        "label_suffix": " (Case Report)",
        "features": {
            "clinical_presentation": {"label": "Clinical Presentation Completeness", "weight": 0.25, "criteria": "History, symptoms, exam findings, timeline clearly documented"},
            "diagnostic_workup": {"label": "Diagnostic Workup", "weight": 0.20, "criteria": "Appropriate tests ordered, results interpreted correctly"},
            "management_rationale": {"label": "Management & Rationale", "weight": 0.20, "criteria": "Treatment choices justified, alternatives discussed"},
            "educational_value": {"label": "Educational Value & Novelty", "weight": 0.20, "criteria": "Does this case teach something new or rare?"},
            "literature_context": {"label": "Literature Context", "weight": 0.10, "criteria": "Similar cases referenced, placed in clinical context"},
            "writing": {"label": "Writing Quality", "weight": 0.05},
        },
    },
    "protocol": {
        "label_suffix": " (Protocol)",
        "features": {
            "reproducibility": {"label": "Reproducibility & Detail", "weight": 0.30, "criteria": "Can another lab replicate this exactly? All steps, quantities, timing?"},
            "validation": {"label": "Validation & Controls", "weight": 0.25, "criteria": "Positive/negative controls, validation experiments, troubleshooting"},
            "applicability": {"label": "Broad Applicability", "weight": 0.20, "criteria": "Useful to multiple labs/contexts? Equipment commonly available?"},
            "optimization": {"label": "Optimization Evidence", "weight": 0.15, "criteria": "Were conditions optimized? Data shown?"},
            "safety_ethics": {"label": "Safety & Ethics", "weight": 0.10, "criteria": "Safety considerations, ethical approvals mentioned"},
        },
    },
}


# ── Type-Specific Red Flag Checks ──────────────────────────────────────────
# Supplements the generic RED_FLAG_CHECKS with paper-type-aware regex checks.

RED_FLAGS_BY_TYPE = {
    "experimental": [
        {"id": "no_methods", "pattern": r"\b(methods?|methodology|materials?\s+and\s+methods?)\b", "check": "missing", "issue": "No methods section", "penalty": -10, "fix": "Add a detailed methods section"},
        {"id": "no_stats", "pattern": r"\b(p\s*[<>=]|statistical|significance|ANOVA|t-test|chi-square|regression|confidence interval)\b", "check": "missing", "issue": "No statistical analysis", "penalty": -8, "fix": "Add statistical analysis of your results"},
        {"id": "small_n", "pattern": r"\bn\s*=\s*[1-9]\b", "check": "present", "issue": "Very small sample size (n < 10)", "penalty": -5, "fix": "Increase sample size or justify small N"},
    ],
    "review": [
        {"id": "no_synthesis", "pattern": r"\b(synthesiz|integrat|taken together|collectively|overall|in summary)\b", "check": "missing", "issue": "Lists papers without synthesis", "penalty": -10, "fix": "Add synthesis paragraphs connecting findings across studies"},
        {"id": "outdated_refs", "pattern": None, "check": "recency_dynamic", "issue": "No references from last 2 years", "penalty": -5, "fix": "Include recent publications from the last 2 years"},
        {"id": "no_gaps", "pattern": r"\b(future\s+(research|direction|stud)|gap|remain|unanswered|unexplored)\b", "check": "missing", "issue": "No future directions identified", "penalty": -2, "fix": "Consider adding a brief section on research gaps and future directions"},
    ],
    "meta_analysis": [
        {"id": "no_prisma", "pattern": r"\b(PRISMA|flow\s+diagram|study\s+selection)\b", "check": "missing", "issue": "No PRISMA flow diagram", "penalty": -8, "fix": "Add PRISMA flow diagram showing study selection"},
        {"id": "no_heterogeneity", "pattern": r"\b(heterogeneity|I²|I-squared|Q\s+statistic|random.effects)\b", "check": "missing", "issue": "No heterogeneity assessment", "penalty": -10, "fix": "Assess and report heterogeneity (I², Q statistic)"},
        {"id": "few_studies", "pattern": r"\b(\d+)\s+stud(y|ies)\s+(included|met|selected)\b", "check": "count_low", "issue": "Fewer than 5 studies included", "penalty": -8, "fix": "Consider broadening inclusion criteria"},
    ],
    "case_report": [
        {"id": "no_consent", "pattern": r"\b(consent|permission|IRB|ethics)\b", "check": "missing", "issue": "No patient consent mentioned", "penalty": -5, "fix": "Add statement about patient consent"},
        {"id": "no_differential", "pattern": r"\b(differential|rule\s+out|alternative\s+diagnos)\b", "check": "missing", "issue": "No differential diagnosis discussed", "penalty": -5, "fix": "Discuss differential diagnoses considered"},
    ],
    "protocol": [
        {"id": "no_reagents", "pattern": r"\b(catalog|supplier|vendor|manufacturer|concentration|dilut)\b", "check": "missing", "issue": "Missing reagent details", "penalty": -5, "fix": "Add supplier, catalog numbers, and concentrations for all reagents"},
        {"id": "no_troubleshooting", "pattern": r"\b(troubleshoot|common\s+error|pitfall|tip|caution|warning|note)\b", "check": "missing", "issue": "No troubleshooting section", "penalty": -5, "fix": "Add troubleshooting tips for common issues"},
    ],
}

# ── Red Flag Checks ────────────────────────────────────────────────────────
# Note: paper_type_exclude lists paper types for which this flag should NOT apply

RED_FLAG_CHECKS = [
    {"id": "no_abstract", "pattern": r"\babstract\b", "check": "missing", "severity": "critical", "issue": "No abstract detected", "penalty": -8, "fix": "Add a structured abstract (150-300 words)", "paper_type_exclude": []},
    {"id": "no_references", "pattern": r"\breferences?\b|\bbibliography\b", "check": "missing", "severity": "critical", "issue": "No references section detected", "penalty": -10, "fix": "Add a properly formatted references section", "paper_type_exclude": []},
    {"id": "low_references", "pattern": None, "check": "ref_count_low", "severity": "warning", "issue": "Fewer than 15 references", "penalty": -3, "fix": "Expand your literature review — top journals expect 30-60 references", "paper_type_exclude": ["review", "meta_analysis"]},
    {"id": "too_short", "pattern": None, "check": "word_count_low", "severity": "warning", "issue": "Manuscript under 3,000 words", "penalty": -5, "fix": "Expand methodology and results sections for journal-length depth", "paper_type_exclude": ["case_report"]},
    {"id": "no_tables", "pattern": r"\btable\s+\d+\b|\btable\s+[ivx]+\b", "check": "missing", "severity": "info", "issue": "No tables detected", "penalty": -2, "fix": "Add summary statistics, regression results, or comparison tables", "paper_type_exclude": ["review", "protocol"]},
]

JOURNAL_TARGETS_BY_TYPE = {
    "experimental": {
        "filter": "type:article",
        "hint": "journals accepting original research",
        "include_keywords": [],
        "exclude_keywords": ["review", "survey"],
        "example_journals": [],
    },
    "review": {
        "filter": "type:review",
        "hint": "journals with review sections",
        "include_keywords": ["review", "reviews", "trends", "current opinion", "annual review", "progress in", "advances in"],
        "exclude_keywords": [],
        "example_journals": ["Nature Reviews", "Annual Review of", "Trends in", "Current Opinion in", "Progress in", "Advances in"],
    },
    "meta_analysis": {
        "filter": "type:review",
        "hint": "journals accepting systematic reviews and meta-analyses",
        "include_keywords": ["systematic", "evidence", "cochrane", "meta"],
        "exclude_keywords": [],
        "example_journals": ["Cochrane Database of Systematic Reviews", "JAMA", "BMJ", "Annals of Internal Medicine", "Lancet", "Systematic Reviews"],
    },
    "case_report": {
        "filter": "type:article",
        "hint": "journals accepting case reports",
        "include_keywords": ["case", "clinical", "report"],
        "exclude_keywords": [],
        "example_journals": ["BMJ Case Reports", "Journal of Medical Case Reports", "Cureus", "American Journal of Case Reports", "Case Reports in Medicine"],
    },
    "protocol": {
        "filter": "type:article",
        "hint": "journals publishing protocols and methods",
        "include_keywords": ["protocol", "method", "technique", "procedure", "jove", "bio-protocol"],
        "exclude_keywords": [],
        "example_journals": ["Nature Protocols", "STAR Protocols", "JoVE", "Bio-protocol", "Methods in Molecular Biology", "Current Protocols"],
    },
}

MAX_FEATURE_CHARS = 100000  # max chars sent for feature extraction (~25K tokens)
CONSISTENCY_CHUNK = 12000   # chars sent for each consistency run (cheaper)
CONSISTENCY_RUNS = 3        # number of scoring runs for consistency


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


class JournalScorerService:
    def __init__(self):
        # Use HIJ-specific OpenAI client with longer timeout for complex analyses
        self.openai = self._create_hij_openai_client()
        self.parser = DocumentParser()
        self.openalex = OpenAlexSearchService()

        # Lazy-load ML tier predictor (supplements LLM-based scoring)
        self._ml_tier_predictor = None

    def _create_hij_openai_client(self):
        """Create OpenAI client with HIJ-specific timeout (5 min) and retry logic."""
        use_azure = os.getenv("USE_AZURE_OPENAI", "false").lower() == "true"

        if use_azure:
            endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
            client = AzureOpenAI(
                api_key=os.getenv("AZURE_OPENAI_API_KEY"),
                api_version=os.getenv("AZURE_API_VERSION", "2024-12-01-preview"),
                azure_endpoint=endpoint,
                timeout=_HIJ_TIMEOUT,
                max_retries=3,  # Built-in retry for transient errors
            )
            chat_model = os.getenv("AZURE_CHAT_DEPLOYMENT", "gpt-4")
        else:
            client = OpenAI(
                api_key=os.getenv("OPENAI_API_KEY"),
                timeout=_HIJ_TIMEOUT,
                max_retries=3,
            )
            chat_model = "gpt-4o-mini"

        # Return a simple wrapper that mimics the shared client interface
        class HIJOpenAIClient:
            def __init__(self, client, model):
                self.client = client
                self.chat_model = model

            def chat_completion(self, messages, temperature=0.7, max_tokens=None, **kwargs):
                params = {"model": self.chat_model, "messages": messages, "temperature": temperature}
                if max_tokens:
                    params["max_tokens"] = max_tokens
                params.update(kwargs)
                return self.client.chat.completions.create(**params)

            def chat_completion_stream(self, messages, temperature=0.7, max_tokens=None, **kwargs):
                params = {"model": self.chat_model, "messages": messages, "temperature": temperature, "stream": True}
                if max_tokens:
                    params["max_tokens"] = max_tokens
                params.update(kwargs)
                return self.client.chat.completions.create(**params)

        return HIJOpenAIClient(client, chat_model)

    @property
    def ml_tier_predictor(self):
        """Lazy-load the ML tier predictor (returns None if unavailable)."""
        if self._ml_tier_predictor is None:
            try:
                from services.ml_tier_predictor import get_ml_tier_predictor
                self._ml_tier_predictor = get_ml_tier_predictor()
            except Exception as e:
                print(f"[JournalScorer] ML tier predictor unavailable: {e}")
        return self._ml_tier_predictor

    # ── Publication Year Extraction ────────────────────────────────────────

    @staticmethod
    def _extract_publication_year(text: str) -> Optional[int]:
        """Extract the paper's own publication year from header, copyright, or date lines.

        Searches for common patterns like:
        - "Published: March 2022", "Received: Jan 2021, Accepted: May 2022"
        - "Copyright (c) 2022", "(c) 2023"
        - "Volume 12, Issue 3, 2022"
        - Year in first few lines (title page)

        Returns the publication year as int, or None if not determinable.
        """
        current_year = datetime.now().year
        # Only consider the first ~3000 chars (header/title page area)
        # and the last ~1500 chars (copyright/footer area)
        header = text[:3000]
        footer = text[-1500:] if len(text) > 1500 else text

        candidates = []

        # Pattern 1: Explicit publication/accepted/received dates
        date_patterns = [
            r'(?:published|accepted|received|available\s+online|epub)\s*(?:date)?[:\s]+\w*\s*(\d{4})',
            r'(?:published|accepted|received)\s*:\s*\d{1,2}\s+\w+\s+(\d{4})',
            r'(?:published|accepted|received)\s*:\s*\w+\s+\d{1,2},?\s+(\d{4})',
        ]
        for pat in date_patterns:
            for m in re.finditer(pat, header + '\n' + footer, re.IGNORECASE):
                yr = int(m.group(1))
                if 1990 <= yr <= current_year:
                    candidates.append(('explicit_date', yr))

        # Pattern 2: Copyright lines
        copyright_patterns = [
            r'(?:copyright|©|\(c\))\s*(?:\d{4}\s*[-–]\s*)?(\d{4})',
            r'(\d{4})\s*(?:copyright|©)',
        ]
        for pat in copyright_patterns:
            for m in re.finditer(pat, header + '\n' + footer, re.IGNORECASE):
                yr = int(m.group(1))
                if 1990 <= yr <= current_year:
                    candidates.append(('copyright', yr))

        # Pattern 3: Volume/issue lines (e.g., "Volume 12, No. 3, 2022")
        vol_patterns = [
            r'(?:vol(?:ume)?|v)\.?\s*\d+.*?(\d{4})',
        ]
        for pat in vol_patterns:
            for m in re.finditer(pat, header, re.IGNORECASE):
                yr = int(m.group(1))
                if 1990 <= yr <= current_year:
                    candidates.append(('volume', yr))

        # Pattern 4: Year in the first 5 non-empty lines (title page)
        first_lines = [l.strip() for l in header.split('\n') if l.strip()][:8]
        for line in first_lines:
            for m in re.finditer(r'\b(20\d{2})\b', line):
                yr = int(m.group(1))
                if 1990 <= yr <= current_year:
                    candidates.append(('header_line', yr))

        if not candidates:
            return None

        # Prefer explicit dates > copyright > volume > header lines
        priority = {'explicit_date': 0, 'copyright': 1, 'volume': 2, 'header_line': 3}
        candidates.sort(key=lambda x: (priority.get(x[0], 99), -x[1]))
        # For explicit dates, prefer the latest (published > accepted > received)
        return candidates[0][1]

    # ── Self-Reference Detection ──────────────────────────────────────────

    @staticmethod
    def _is_self_reference(paper_title: str, candidate_title: str, paper_authors: list = None, candidate_authors: list = None) -> bool:
        """Check if a candidate reference is the same paper as the uploaded manuscript.

        Uses normalized title similarity. If titles are very similar (>80% overlap),
        considers it a self-reference. Also checks author overlap if available.
        """
        if not paper_title or not candidate_title:
            return False

        # Normalize titles: lowercase, strip punctuation, collapse whitespace
        def normalize(t):
            t = t.lower().strip()
            t = re.sub(r'[^\w\s]', '', t)
            t = re.sub(r'\s+', ' ', t)
            return t

        norm_paper = normalize(paper_title)
        norm_candidate = normalize(candidate_title)

        if not norm_paper or not norm_candidate:
            return False

        # Exact match
        if norm_paper == norm_candidate:
            return True

        # Check if one title is a substantial substring of the other
        shorter = norm_paper if len(norm_paper) <= len(norm_candidate) else norm_candidate
        longer = norm_candidate if len(norm_paper) <= len(norm_candidate) else norm_paper

        if len(shorter) > 15 and shorter in longer:
            return True

        # Word-level overlap check (Jaccard similarity)
        words_paper = set(norm_paper.split())
        words_candidate = set(norm_candidate.split())
        # Remove very common words
        stopwords = {'the', 'a', 'an', 'of', 'in', 'on', 'for', 'and', 'or', 'to', 'with', 'by', 'is', 'are', 'was', 'were', 'from', 'at', 'as', 'its', 'this', 'that'}
        words_paper -= stopwords
        words_candidate -= stopwords

        if not words_paper or not words_candidate:
            return False

        overlap = words_paper & words_candidate
        union = words_paper | words_candidate
        jaccard = len(overlap) / len(union) if union else 0

        if jaccard > 0.75:
            return True

        # Check first N significant words match (handles subtitle differences)
        paper_sig = [w for w in norm_paper.split() if w not in stopwords][:6]
        cand_sig = [w for w in norm_candidate.split() if w not in stopwords][:6]
        if len(paper_sig) >= 4 and paper_sig == cand_sig:
            return True

        return False

    def analyze_manuscript(self, file_bytes: bytes, filename: str, manuscript_url: str = None, raw_text: str = None, user_publication_year: int = None) -> Generator[str, None, None]:
        """10-step pipeline — yields SSE events as analysis progresses.

        IMPORTANT: Paper type detection runs BEFORE feature extraction so that
        scoring criteria are appropriate for the paper type (review papers get
        review criteria, not experimental criteria).

        If raw_text is provided, skip file parsing and use it directly.
        """
        start_time = time.time()

        try:
            # ── Step 1: Parse Document ──────────────────────────────────
            yield _sse("progress", {"step": 1, "message": "Parsing document...", "percent": 5})

            if raw_text:
                text = raw_text
            else:
                text = self.parser.parse_file_bytes(file_bytes, filename)
            if not text or len(text.strip()) < 100:
                yield _sse("error", {"error": "Could not extract enough text. Please provide more detail about your research or upload a valid PDF/DOCX file."})
                return

            word_count = len(text.split())
            ref_section = self._extract_references_section(text)
            ref_count = self._count_references(ref_section) if ref_section else 0
            has_abstract = bool(re.search(r'\babstract\b', text[:3000], re.IGNORECASE))
            has_tables = bool(re.search(r'\btable\s+\d+\b|\btable\s+[ivx]+\b', text, re.IGNORECASE))

            # Extract the paper's own publication year (for date-relative checks)
            # User-provided year takes priority over auto-detected
            if user_publication_year:
                publication_year = user_publication_year
                print(f"[JournalScorer] Using user-provided publication year: {publication_year}")
            else:
                publication_year = self._extract_publication_year(text)
                if publication_year:
                    print(f"[JournalScorer] Detected paper publication year: {publication_year}")
                else:
                    print("[JournalScorer] Could not detect publication year, using current year as baseline")

            # Extract the paper's title (first non-empty line) for self-reference filtering
            manuscript_title = ''
            for line in text[:500].split('\n'):
                line = line.strip()
                if len(line) > 10 and not line.lower().startswith(('abstract', 'keywords', 'doi', 'http')):
                    manuscript_title = line
                    break
            print(f"[JournalScorer] Manuscript title guess: {manuscript_title[:80]}...")

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

            # ── Step 2.5: Detect Paper Type (BEFORE feature extraction) ──
            # This is critical: paper type determines which scoring criteria
            # are used. A review paper must NOT be scored on experimental criteria.
            paper_type_result = None
            paper_type = 'experimental'  # default

            try:
                yield _sse("progress", {"step": 2, "message": "Detecting paper type...", "percent": 14})

                from services.paper_type_detector import PaperTypeDetector
                detector = PaperTypeDetector(openai_client=self.openai)
                paper_type_result = detector.detect(text, title=text[:200].split('\n')[0] if text else '')
                paper_type = paper_type_result.get('paper_type', 'experimental')

                yield _sse("paper_type", paper_type_result)
            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"[JournalScorer] Paper type detection failed (defaulting to experimental): {e}")
                paper_type_result = {"paper_type": "experimental", "confidence": "low", "signals": ["Detection failed"], "all_scores": {}}
                yield _sse("paper_type", paper_type_result)

            # ── Step 2.7: Apply Paper-Type Feature Overrides ─────────────
            # If the paper is a review, meta-analysis, case report, or protocol,
            # replace the field-specific experimental features with type-appropriate ones.
            scoring_field_config = dict(field_config)  # shallow copy
            if paper_type in PAPER_TYPE_FEATURE_OVERRIDES:
                override = PAPER_TYPE_FEATURE_OVERRIDES[paper_type]
                scoring_field_config = {
                    "label": field_config["label"] + override["label_suffix"],
                    "features": override["features"],
                }
                print(f"[JournalScorer] Overriding features for paper type '{paper_type}': "
                      f"{list(override['features'].keys())}")

            # ── Step 3: Extract Features (full text, type-aware) ──────────
            yield _sse("progress", {"step": 3, "message": "Evaluating manuscript features...", "percent": 18})

            # Send full text (up to MAX_FEATURE_CHARS) for feature extraction
            analysis_text = text[:MAX_FEATURE_CHARS]
            char_info = f"{len(analysis_text):,} chars" + (" (full paper)" if len(analysis_text) == len(text) else f" of {len(text):,}")
            yield _sse("progress", {"step": 3, "message": f"Analyzing {char_info}...", "percent": 22})

            features = self._extract_features(analysis_text, field, scoring_field_config, paper_type=paper_type, manuscript_title=manuscript_title)

            yield _sse("features_extracted", {
                "features": features,
                "word_count": word_count,
                "reference_count": ref_count,
                "has_abstract": has_abstract,
                "has_tables": has_tables,
            })

            # ── Step 4: Consistency Check (3× scoring) ──────────────────
            yield _sse("progress", {"step": 4, "message": "Running consistency checks...", "percent": 32})

            consistency_result = self._run_consistency_check(analysis_text, field, scoring_field_config, features, paper_type=paper_type)

            yield _sse("consistency", consistency_result)

            # Use averaged scores from consistency check
            features = consistency_result["averaged_features"]

            # ── Step 5: Calculate Score ──────────────────────────────────
            yield _sse("progress", {"step": 5, "message": "Calculating overall score...", "percent": 50})

            score_result = self._calculate_score(features, scoring_field_config)
            overall_score = score_result["overall_score"]
            tier = score_result["tier"]
            tier_label = score_result["tier_label"]

            # ── ML Tier Cross-Check (if model available) ──────────────
            ml_tier_result = None
            if self.ml_tier_predictor and self.ml_tier_predictor.is_available:
                try:
                    ml_tier_result = self.ml_tier_predictor.predict_tier(
                        title=manuscript_title,
                        abstract=text[:3000],
                        paper_type=paper_type,
                        author_count=0,  # not extracted yet
                        ref_count=ref_count,
                    )
                    if ml_tier_result:
                        print(f"[JournalScorer] ML tier prediction: {ml_tier_result['tier']} "
                              f"(confidence: {ml_tier_result['confidence']:.2f})")
                except Exception as e:
                    print(f"[JournalScorer] ML tier prediction failed (non-critical): {e}")

            yield _sse("score", {
                "overall_score": overall_score,
                "tier": tier,
                "tier_label": tier_label,
                "score_breakdown": score_result["breakdown"],
                "ml_tier_prediction": ml_tier_result,
            })

            # ── Step 5.5: Methodology Gap Detection (type-aware) ─────────
            yield _sse("progress", {"step": 5, "message": "Checking for methodology gaps...", "percent": 54})

            methodology_gaps = self._detect_methodology_gaps(text, field, paper_type=paper_type)

            yield _sse("methodology_gaps", {
                "gaps": methodology_gaps,
                "gaps_found": len(methodology_gaps),
            })

            # ── Step 5.7: Deep Paper Analysis ──────────────────────
            # Type-specific deep analysis, research gap detection, and
            # paper-type-aware experiment suggestions (paper type already detected above)
            deep_analysis_result = None
            experiment_suggestions = []
            research_gaps_result = []
            review_methodology_result = None
            related_literature = []
            related_protocols = []
            novelty_result = None

            try:
                # Type-specific deep analysis via PaperAnalysisService
                yield _sse("progress", {"step": 5, "message": f"Running {paper_type} deep analysis...", "percent": 56})

                from services.paper_analysis_service import PaperAnalysisService
                paper_svc = PaperAnalysisService()
                title_guess = text[:200].split('\n')[0].strip() if text else ''

                if paper_type == 'experimental':
                    deep_analysis_result = paper_svc._analyze_experimental(text, title_guess)
                elif paper_type == 'review':
                    deep_analysis_result = paper_svc._analyze_review(text, title_guess)
                elif paper_type == 'meta_analysis':
                    deep_analysis_result = paper_svc._analyze_meta_analysis(text, title_guess)
                elif paper_type == 'case_report':
                    deep_analysis_result = paper_svc._analyze_case_report(text, title_guess)
                elif paper_type == 'protocol':
                    deep_analysis_result = paper_svc._analyze_protocol(text, title_guess)
                else:
                    deep_analysis_result = paper_svc._analyze_experimental(text, title_guess)

                yield _sse("deep_analysis", {
                    "paper_type": paper_type,
                    "analysis": deep_analysis_result or {},
                })

                # ── OpenAlex related literature search ──
                try:
                    yield _sse("progress", {"step": 5, "message": "Searching related literature...", "percent": 56})
                    related_literature = paper_svc._search_related_literature(text, title_guess)
                    # ── Self-reference filter (ISSUE 6 fix) ──
                    if related_literature and manuscript_title:
                        related_literature = [
                            p for p in related_literature
                            if not self._is_self_reference(manuscript_title, p.get('title', ''))
                        ]
                    if related_literature:
                        yield _sse("related_literature", {
                            "papers": related_literature,
                            "count": len(related_literature),
                        })
                except Exception as e:
                    print(f"[JournalScorer] Related literature search failed (non-critical): {e}")

                # ── Related protocols search ──
                try:
                    related_protocols = paper_svc._search_related_protocols(text)
                    if related_protocols:
                        yield _sse("related_protocols", {
                            "protocols": related_protocols,
                            "count": len(related_protocols),
                        })
                except Exception as e:
                    print(f"[JournalScorer] Related protocols search failed (non-critical): {e}")

                # Paper-type-aware experiment/follow-up suggestions
                yield _sse("progress", {"step": 5, "message": "Generating follow-up suggestions...", "percent": 57})

                experiment_suggestions = self._generate_paper_type_aware_suggestions(
                    text, title_guess, paper_type, deep_analysis_result
                )

                # ── Feasibility check for experimental paper suggestions ──
                if paper_type in ('experimental', 'protocol') and experiment_suggestions:
                    try:
                        from services.feasibility_checker import FeasibilityChecker
                        feasibility_checker = FeasibilityChecker(
                            llm_client=self.openai.client if self.openai else None,
                        )
                        # Extract biological context from deep analysis if available
                        bio_context = None
                        if deep_analysis_result and isinstance(deep_analysis_result, dict):
                            bio_context = deep_analysis_result.get('biological_context') or {}

                        for suggestion in experiment_suggestions:
                            try:
                                feasibility = feasibility_checker.check(
                                    experiment={
                                        'title': suggestion.get('title', ''),
                                        'methodology': suggestion.get('methodology', ''),
                                        'hypothesis': suggestion.get('hypothesis', ''),
                                        'required_resources': suggestion.get('controls', []),
                                    },
                                    biological_context=bio_context if bio_context else None,
                                )
                                suggestion['feasibility'] = {
                                    'score': feasibility.get('score', 0.5),
                                    'tier': feasibility.get('tier', 'medium'),
                                    'issues': feasibility.get('issues', [])[:3],
                                    'modifications': feasibility.get('modifications', [])[:2],
                                    'reasoning': feasibility.get('reasoning', ''),
                                }
                            except Exception:
                                # Skip feasibility for this suggestion silently
                                pass
                    except Exception as e:
                        print(f"[JournalScorer] Feasibility check failed (non-critical): {e}")

                # ── Novelty verification ──
                try:
                    yield _sse("progress", {"step": 5, "message": "Verifying novelty claims...", "percent": 57})

                    from services.novelty_verifier import NoveltyVerifier
                    nv = NoveltyVerifier(openai_client=self.openai)

                    # Get the LLM novelty score from features (look for 'novelty' key or similar)
                    llm_novelty = 50
                    for key, feat in features.items():
                        if 'novelty' in key.lower() or 'contribution' in key.lower():
                            llm_novelty = feat.get('score', 50)
                            break

                    title_guess = text[:200].split('\n')[0].strip() if text else ''
                    novelty_result = nv.verify(
                        text=text,
                        title=title_guess,
                        llm_novelty_score=llm_novelty,
                        paper_type=paper_type,
                    )

                    yield _sse("novelty_verification", novelty_result)

                    # If novelty was verified as lower, adjust the features score
                    if novelty_result and novelty_result.get('verified_score') is not None:
                        verified = novelty_result['verified_score']
                        for key in features:
                            if 'novelty' in key.lower() or 'contribution' in key.lower():
                                old_score = features[key]['score']
                                # Blend: keep 30% of original LLM score, 70% of verified score
                                features[key]['score'] = round(old_score * 0.3 + verified * 0.7)
                                if old_score != features[key]['score']:
                                    features[key]['details'] = (
                                        features[key].get('details', '') +
                                        f" [Novelty verified: {verified}/100 via literature check]"
                                    )
                                break
                except Exception as e:
                    print(f"[JournalScorer] Novelty verification failed (non-critical): {e}")

                yield _sse("experiment_suggestions", {
                    "paper_type": paper_type,
                    "suggestions": experiment_suggestions,
                })

                # Research gap detection OR review methodology assessment
                review_methodology_result = None
                if paper_type in ('review', 'meta_analysis'):
                    # For review papers, run a Review Methodology Assessment instead of research gaps
                    yield _sse("progress", {"step": 5, "message": "Assessing review methodology & synthesis quality...", "percent": 58})

                    review_methodology_result = self._assess_review_methodology(text, title_guess, paper_type, publication_year=publication_year)
                    yield _sse("review_methodology", review_methodology_result)

                    # Emit empty research_gaps so frontend doesn't hang waiting
                    yield _sse("research_gaps", {"gaps": [], "stats": {}})
                else:
                    yield _sse("progress", {"step": 5, "message": "Detecting research gaps...", "percent": 58})

                    from services.research_gap_detector import ResearchGapDetector
                    gap_detector = ResearchGapDetector()
                    gap_detector.add_document(
                        doc_id='manuscript',
                        title=title_guess or 'Uploaded Manuscript',
                        content=text,
                        doc_type='paper' if paper_type in ('experimental', 'review', 'meta_analysis') else paper_type,
                    )
                    gap_result = gap_detector.analyze()
                    research_gaps_result = gap_result.get('gaps', [])[:10]

                    yield _sse("research_gaps", {
                        "gaps": research_gaps_result,
                        "stats": gap_result.get('stats', {}),
                    })

            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"[JournalScorer] Deep paper analysis failed (non-critical): {e}")
                # Emit empty results so frontend doesn't hang
                # paper_type_result is already emitted above (Step 2.5)
                if not deep_analysis_result:
                    yield _sse("deep_analysis", {"paper_type": paper_type, "analysis": {}})
                if not experiment_suggestions:
                    yield _sse("experiment_suggestions", {"paper_type": paper_type, "suggestions": []})
                if not research_gaps_result:
                    yield _sse("research_gaps", {"gaps": [], "stats": {}})
                if paper_type in ('review', 'meta_analysis') and not review_methodology_result:
                    yield _sse("review_methodology", {"search_strategy": {}, "synthesis_quality": {}, "coverage_analysis": {}, "overall_rigor_score": 0, "paper_type": paper_type})

            # ── Step 5.8: Figure/Graph Analysis (Vision API) ──────────────
            figure_analysis_result = None
            if file_bytes and filename and filename.lower().endswith('.pdf'):
                try:
                    yield _sse("progress", {"step": 5, "message": "Analyzing figures and graphs...", "percent": 62})
                    from services.figure_analyzer import FigureAnalyzer
                    fig_analyzer = FigureAnalyzer()
                    figure_analysis_result = fig_analyzer.analyze_all_figures(file_bytes, text[:5000])
                    if figure_analysis_result and figure_analysis_result["total_figures"] > 0:
                        yield _sse("figure_analysis", figure_analysis_result)
                    else:
                        yield _sse("figure_analysis", {"figures": [], "summary": "No figures extracted from PDF.", "total_figures": 0})
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    print(f"[JournalScorer] Figure analysis failed (non-critical): {e}")
                    yield _sse("figure_analysis", {"figures": [], "summary": f"Figure analysis unavailable: {e}", "total_figures": 0})

            # ── Step 6: Match Journals (keyword-based via OpenAlex) ──
            yield _sse("progress", {"step": 6, "message": "Finding relevant journals by keywords...", "percent": 58})

            journals = self._match_journals_by_keywords(keywords, field, tier, paper_type=paper_type, paper_score=overall_score)
            yield _sse("journals", journals)

            # ── Step 7: Landscape Position ──────────────────────────────
            yield _sse("progress", {"step": 7, "message": "Calculating landscape position...", "percent": 63})

            landscape = self._get_landscape_position(field, overall_score)
            yield _sse("landscape", landscape)

            # ── Step 8: Detect Red Flags ────────────────────────────────
            yield _sse("progress", {"step": 8, "message": "Checking for red flags...", "percent": 68})

            flags_result = self._detect_red_flags(text, word_count, ref_count, paper_type=paper_type, publication_year=publication_year)
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

            # ── Citation Neighborhood Matching (additive, between Steps 9 & 10) ──
            citation_neighbor_journals = []
            try:
                yield _sse("progress", {"step": 9, "message": "Analyzing citation neighborhood...", "percent": 78})

                # Extract reference-like strings from manuscript
                doi_pattern = r'10\.\d{4,}/[^\s]+'
                dois = re.findall(doi_pattern, text)

                # Also try to extract reference titles (lines that look like citations)
                ref_section_text = ''
                for marker in ['References', 'Bibliography', 'Works Cited', 'Literature Cited']:
                    idx = text.lower().rfind(marker.lower())
                    if idx > 0:
                        ref_section_text = text[idx:idx+5000]
                        break

                ref_queries = dois[:10]
                if ref_section_text and len(ref_queries) < 5:
                    # Extract lines that look like references
                    ref_lines = [l.strip() for l in ref_section_text.split('\n')
                                 if len(l.strip()) > 30 and any(c.isdigit() for c in l[:20])]
                    ref_queries.extend(ref_lines[:10])

                if ref_queries:
                    citation_neighbor_journals = self._find_citation_neighbor_journals(ref_queries, field)
                    if citation_neighbor_journals:
                        # Deduplicate against existing journal matches
                        existing_names = set()
                        for category in ['primary_matches', 'stretch_matches', 'safe_matches']:
                            for j in journals.get(category, []):
                                existing_names.add(j.get('name', '').lower().strip())

                        citation_neighbor_journals = [
                            j for j in citation_neighbor_journals
                            if j['journal_name'].lower().strip() not in existing_names
                        ]

                        yield _sse("citation_neighbor_journals", {
                            "journals": citation_neighbor_journals,
                            "total_references_analyzed": len(ref_queries),
                        })
            except Exception as e:
                print(f"[JournalScorer] Citation neighborhood matching failed (non-critical): {e}")

            # ── Step 10: Generate Recommendations ───────────────────────
            yield _sse("progress", {"step": 10, "message": "Fetching verified references & generating recommendations...", "percent": 82})

            # Part A: Pre-fetch real references from OpenAlex
            # CRITICAL: Filter by publication_year so we only suggest papers that existed when the manuscript was written
            reference_bank = []
            try:
                reference_bank = self._fetch_reference_bank(
                    keywords, field,
                    manuscript_title=manuscript_title,
                    publication_year=publication_year
                )
                print(f"[JournalScorer] Reference bank: fetched {len(reference_bank)} verified papers from OpenAlex (up to year {publication_year or 'current'})")
            except Exception as e:
                print(f"[JournalScorer] Reference bank fetch failed (non-critical): {e}")

            rec_buffer = ""
            for chunk in self._generate_recommendations_stream(
                scoring_field_config["label"], overall_score, tier, features,
                flags_result["flags"], journals, landscape, citation_result,
                keywords=keywords, subfield=field_result.get("subfield", ""),
                paper_type=paper_type,
                research_gaps=research_gaps_result if research_gaps_result else None,
                reference_bank=reference_bank,
                publication_year=publication_year,
                manuscript_title=manuscript_title,
            ):
                rec_buffer += chunk
                yield _sse("recommendations", {"content": chunk})

            # Part C: Post-process to strip any remaining hallucinated DOIs
            if reference_bank:
                rec_buffer = self._sanitize_doi_links(rec_buffer, reference_bank)

            yield _sse("recommendations_done", {"full_text": rec_buffer})

            # ── Done ────────────────────────────────────────────────────
            elapsed = round(time.time() - start_time, 1)
            done_data = {
                "success": True,
                "analysis_time_seconds": elapsed,
                "methodology_gaps": methodology_gaps,
                "citation_neighbor_journals": citation_neighbor_journals,
                "paper_type": paper_type,
                "novelty_verified": bool(novelty_result),
                "research_gaps_count": len(research_gaps_result) if research_gaps_result else 0,
                "experiment_suggestions_count": len(experiment_suggestions) if experiment_suggestions else 0,
                "related_literature_count": len(related_literature) if related_literature else 0,
                "related_protocols_count": len(related_protocols) if related_protocols else 0,
            }
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
            try:
                result = json.loads(json_match.group())
            except json.JSONDecodeError:
                return {"field": "economics", "confidence": 0.5, "subfield": "General", "keywords": ["general"], "reasoning": "JSON parse error in field detection"}
            # Validate the field is in our config
            if result.get("field") not in FIELD_CONFIGS:
                result["field"] = "economics"
                result["confidence"] = 0.5
            # Ensure keywords exist and have enough
            if not result.get("keywords") or not isinstance(result["keywords"], list):
                result["keywords"] = [result.get("subfield", "general")]
            return result
        return {"field": "economics", "confidence": 0.5, "subfield": "General", "keywords": ["general"], "reasoning": "Could not classify — defaulting to Economics"}

    def _extract_features(self, text_excerpt: str, field: str, field_config: dict, paper_type: str = 'experimental', manuscript_title: str = '') -> dict:
        feature_list = "\n".join(
            f"- {key}: {info['label']} (weight: {info['weight']*100:.0f}%)"
            for key, info in field_config["features"].items()
        )

        # Build paper-type-aware context for the reviewer prompt
        paper_type_context = ""
        if paper_type == 'review':
            paper_type_context = (
                "\nIMPORTANT: This is a REVIEW paper. Score it on review-specific criteria "
                "(comprehensiveness, synthesis quality, literature coverage, narrative clarity). "
                "Do NOT penalize it for lacking original experiments, statistical methods, or raw data. "
                "Reviews synthesize existing literature — evaluate whether that synthesis is done well.\n"
            )
        elif paper_type == 'meta_analysis':
            paper_type_context = (
                "\nIMPORTANT: This is a META-ANALYSIS. Score it on meta-analytic criteria "
                "(search strategy, study selection, statistical pooling, heterogeneity assessment). "
                "This paper combines data from multiple studies — evaluate the quality of that combination.\n"
            )
        elif paper_type == 'case_report':
            paper_type_context = (
                "\nIMPORTANT: This is a CASE REPORT. Score it on case report criteria "
                "(clinical detail, diagnostic reasoning, literature context, educational value). "
                "Do NOT penalize it for small sample size or lack of controlled experiments.\n"
            )
        elif paper_type == 'protocol':
            paper_type_context = (
                "\nIMPORTANT: This is a PROTOCOL paper. Score it on protocol criteria "
                "(procedural completeness, reproducibility, validation, safety documentation). "
                "Evaluate whether someone could reproduce the procedure from this description alone.\n"
            )

        prompt = (
            f"You are a peer reviewer in {field_config['label']}. Score this manuscript on each feature below.\n"
            f"{paper_type_context}\n"
            f"FEATURES TO SCORE (each 0-100):\n{feature_list}\n\n"
            "Respond ONLY in valid JSON — a dict where each key is the feature name and value is:\n"
            '{"score": 0-100, "details": "justification (2-3 sentences)", "citations": [{"text": "quoted or paraphrased evidence from the manuscript", "section": "which section it appears in"}], "suggested_references": [{"title": "Seminal paper title", "authors": "Author et al.", "year": "YYYY", "relevance": "why this reference matters"}]}\n\n'
            "IMPORTANT:\n"
            "- In 'citations', quote specific passages from the manuscript that support your score.\n"
            "- In 'suggested_references', list 1-2 key papers the authors should cite or benchmark against. Do NOT include DOI URLs — just the paper title, authors, and year.\n"
            "- If the manuscript already cites important works, mention that positively in 'details'.\n\n"
            f"MANUSCRIPT TEXT:\n{text_excerpt}"
        )

        resp = self.openai.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=4500,
        )
        raw = resp.choices[0].message.content.strip()
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if json_match:
            try:
                parsed = json.loads(json_match.group())
            except json.JSONDecodeError as je:
                print(f"[JournalScorer] Feature scoring JSON truncated (max_tokens hit?): {je}")
                # Try to repair by closing open strings/braces
                truncated = json_match.group()
                # Close any open string and braces
                if truncated.count('"') % 2 == 1:
                    truncated += '"'
                open_braces = truncated.count('{') - truncated.count('}')
                truncated += '}' * max(0, open_braces)
                try:
                    parsed = json.loads(truncated)
                except json.JSONDecodeError:
                    parsed = {}
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
                    "suggested_references": self._enrich_suggested_references(
                        parsed[key].get("suggested_references", []),
                        manuscript_title=manuscript_title,
                    ),
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

    def _run_consistency_check(self, text: str, field: str, field_config: dict, initial_features: dict, paper_type: str = 'experimental') -> dict:
        """Run 2 additional scoring rounds and average with the initial to get consistent scores."""
        all_runs = [
            {k: v["score"] for k, v in initial_features.items()}
        ]

        # Build paper-type context for consistency runs
        type_hint = ""
        if paper_type == 'review':
            type_hint = " This is a REVIEW paper — score on review quality (synthesis, coverage, clarity), NOT experimental rigor."
        elif paper_type == 'meta_analysis':
            type_hint = " This is a META-ANALYSIS — score on meta-analytic quality (search strategy, pooling, heterogeneity)."
        elif paper_type == 'case_report':
            type_hint = " This is a CASE REPORT — score on clinical completeness, diagnostic reasoning, educational value."
        elif paper_type == 'protocol':
            type_hint = " This is a PROTOCOL — score on procedural completeness, reproducibility, detail level."

        # Run 2 more scoring rounds with slightly different temperature
        for run_idx in range(CONSISTENCY_RUNS - 1):
            try:
                feature_list = "\n".join(
                    f"- {key}: {info['label']}"
                    for key, info in field_config["features"].items()
                )
                prompt = (
                    f"You are a peer reviewer in {field_config['label']}. "
                    f"Score this manuscript on each feature (0-100).{type_hint} "
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
                    try:
                        scores = json.loads(json_match.group())
                    except json.JSONDecodeError:
                        continue  # Skip this consistency run
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

    def _match_journals_by_keywords(self, keywords: list, field: str, tier: int, paper_type: str = 'experimental', paper_score: int = 50) -> dict:
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

            # Use paper-type-aware filter from JOURNAL_TARGETS_BY_TYPE
            type_target = JOURNAL_TARGETS_BY_TYPE.get(paper_type, JOURNAL_TARGETS_BY_TYPE["experimental"])
            type_filter = type_target["filter"]

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
                    f"&filter={type_filter},publication_year:2020-2026"
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
                return self._match_journals_from_db(field, tier, keywords=keywords, paper_type=paper_type)

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
                    f"{type_filter},"
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
                return self._match_journals_from_db(field, tier, keywords=keywords, paper_type=paper_type)

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
                        "openalex_id": oa_id,
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
                            "openalex_id": oa_id,
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
                return self._match_journals_from_db(field, tier, keywords=keywords, paper_type=paper_type)

            # ── Step 4b: Validate top journals against recent publications ──
            # Verify each journal actually publishes papers of this type
            # in this subject area (prevents subfield mismatches)
            validated_enriched = []
            for j in enriched[:25]:  # Validate top 25 to keep API calls reasonable
                validation = self._validate_journal_fit(
                    journal_name=j["name"],
                    journal_oa_id=j.get("openalex_id", ""),
                    paper_type=paper_type,
                    keywords=keywords,
                )
                j["validation"] = validation
                if validation.get("validated", True):
                    validated_enriched.append(j)
                else:
                    print(f"[Journal] Excluded {j['name']}: {validation.get('reason', 'no fit')}")

            # Keep unvalidated journals at the end as backup
            unvalidated = [j for j in enriched[25:]]
            enriched = validated_enriched + unvalidated
            print(f"[Journal] {len(validated_enriched)} journals validated, {len(unvalidated)} unvalidated backup")

            # ── Step 5: Split into Stretch / Target / Safe ─────────────
            # Separate mega-journals
            quality = [j for j in enriched if not _is_mega(j["name"])]
            megas = [j for j in enriched if _is_mega(j["name"])]

            # Apply paper-type-aware journal filtering
            type_target = JOURNAL_TARGETS_BY_TYPE.get(paper_type, JOURNAL_TARGETS_BY_TYPE["experimental"])
            include_kws = type_target.get("include_keywords", [])
            exclude_kws = type_target.get("exclude_keywords", [])

            # Boost journals matching include keywords
            for j in quality:
                name_lower = j["name"].lower()
                boost = sum(1 for kw in include_kws if kw.lower() in name_lower)
                demote = sum(1 for kw in exclude_kws if kw.lower() in name_lower)
                j["type_relevance_boost"] = boost - demote

            # Sort quality journals by type relevance then citedness (quality indicator)
            quality.sort(key=lambda j: (j.get("type_relevance_boost", 0), j["citedness_2yr"]), reverse=True)

            # Quality-aware tier split based on paper score
            # High-scoring papers get more ambitious stretch targets
            if paper_score >= 80:
                stretch_count, target_count = 5, 10
            elif paper_score >= 60:
                stretch_count, target_count = 3, 10
            else:
                stretch_count, target_count = 2, 8

            stretch = quality[:stretch_count]
            target = quality[stretch_count:stretch_count + target_count]

            # Safe = capped mega-journals (max 2) + lower-ranked quality
            safe = megas[:2]
            remaining = quality[stretch_count + target_count:]
            safe.extend(remaining[:3])

            # Deduplicate across tiers
            seen_names = set()
            def _dedup(journals):
                deduped = []
                for j in journals:
                    name = j["name"].lower().strip()
                    if name not in seen_names:
                        seen_names.add(name)
                        deduped.append(j)
                return deduped

            stretch = _dedup(stretch)
            target = _dedup(target)
            safe = _dedup(safe)

            # Add quality-aware reasoning to each journal
            score_label = "high-scoring" if paper_score >= 75 else "mid-range" if paper_score >= 50 else "developing"

            for j in stretch:
                pp = j.get("prof_papers", 0)
                cite = j.get("citedness_2yr", 0)
                validation = j.get("validation", {})
                evidence = validation.get("evidence", "")
                j["reason"] = (
                    f"Top-cited researchers in your field publish here — "
                    f"{pp} recent papers by leading authors. "
                    f"Citedness ({cite}) is aspirational for a {score_label} manuscript."
                )
                if evidence:
                    j["reason"] += f" Verified: {evidence}"
                j["verified"] = validation.get("validated", False)

            for j in target:
                pp = j.get("prof_papers", 0)
                cite = j.get("citedness_2yr", 0)
                validation = j.get("validation", {})
                evidence = validation.get("evidence", "")
                j["reason"] = (
                    f"Frequently chosen by experts in your area — "
                    f"{pp} recent papers by top authors. "
                    f"Citedness of {cite} suggests a realistic match for your paper."
                )
                if evidence:
                    j["reason"] += f" Verified: {evidence}"
                j["verified"] = validation.get("validated", False)

            for j in safe:
                pp = j.get("prof_papers", 0)
                cite = j.get("citedness_2yr", 0)
                validation = j.get("validation", {})
                evidence = validation.get("evidence", "")
                if _is_mega(j["name"]):
                    j["reason"] = (
                        f"High-volume journal that publishes broadly. "
                        f"Good fallback with {pp} papers from authors in your area."
                    )
                else:
                    j["reason"] = (
                        f"Accessible venue where researchers in your area publish. "
                        f"Citedness {cite} with {pp} recent papers from top authors."
                    )
                if evidence:
                    j["reason"] += f" Verified: {evidence}"
                j["verified"] = validation.get("validated", False)

            return {
                "primary_matches": target,
                "stretch_matches": stretch,
                "safe_matches": safe[:5],
            }
        except Exception as e:
            print(f"[Journal] Professor-based journal matching failed: {e}")
            return self._match_journals_from_db(field, tier, keywords=keywords, paper_type=paper_type)

    def _validate_journal_fit(self, journal_name: str, journal_oa_id: str,
                               paper_type: str, keywords: list) -> dict:
        """Validate that a journal actually publishes papers of this type in this area.

        Searches OpenAlex for recent papers in this journal matching the paper's
        keywords and type. Returns concrete evidence of fit.

        This prevents recommending journals that exist but don't publish in the
        user's specific subfield or paper type.
        """
        import requests as req
        OPENALEX_EMAIL = "prmogathala@gmail.com"
        HEADERS = {"User-Agent": f"2ndBrain/1.0 (mailto:{OPENALEX_EMAIL})", "Accept": "application/json"}

        type_map = {
            "experimental": "article",
            "review": "review",
            "meta_analysis": "article",
            "case_report": "article",
            "protocol": "article",
        }
        work_type = type_map.get(paper_type, "article")

        try:
            # Search for recent papers in this journal matching keywords
            kw_query = " ".join(keywords[:5]) if keywords else ""
            source_filter = f"primary_location.source.id:{journal_oa_id}" if journal_oa_id else f"primary_location.source.display_name.search:{req.utils.quote(journal_name)}"

            url = (
                f"https://api.openalex.org/works"
                f"?filter={source_filter},"
                f"type:{work_type},"
                f"publication_year:2022-2026"
                f"&search={req.utils.quote(kw_query)}"
                f"&per_page=5"
                f"&sort=cited_by_count:desc"
                f"&select=id,title,publication_year,cited_by_count"
                f"&mailto={OPENALEX_EMAIL}"
            )
            resp = req.get(url, headers=HEADERS, timeout=10)
            if resp.status_code != 200:
                return {"validated": True, "confidence": "unknown", "reason": "Could not verify"}

            data = resp.json()
            results = data.get("results", [])
            total = data.get("meta", {}).get("count", 0)

            if total == 0:
                return {
                    "validated": False,
                    "confidence": "low",
                    "reason": f"No recent {paper_type} papers matching your keywords found in {journal_name}",
                }

            # Build evidence from top match
            top = results[0]
            return {
                "validated": True,
                "confidence": "high" if total >= 5 else "moderate",
                "total_similar_papers": total,
                "evidence": f"Published {total} similar papers (2022-2026), e.g. \"{top.get('title', '')}\" ({top.get('cited_by_count', 0)} citations)",
                "example_paper": {
                    "title": top.get("title", ""),
                    "year": top.get("publication_year"),
                    "citations": top.get("cited_by_count", 0),
                },
            }
        except Exception as e:
            print(f"[Journal] Validation error for {journal_name}: {e}")
            return {"validated": True, "confidence": "unknown", "reason": "Validation skipped"}

    def _match_journals_from_db(self, field: str, tier: int, keywords: list = None, paper_type: str = 'experimental') -> dict:
        """Fallback: match journals from the pre-populated database by field.

        If keywords are provided, validates each journal against the keywords
        to filter out journals that don't publish in the paper's specific subfield.
        """
        try:
            from services.journal_data_service import get_journal_data_service
            svc = get_journal_data_service()

            primary = svc.get_journals_for_field(field, tier=tier)
            stretch = svc.get_journals_for_field(field, tier=max(1, tier - 1)) if tier > 1 else []
            safe = svc.get_journals_for_field(field, tier=min(3, tier + 1)) if tier < 3 else []

            # If keywords provided, validate journals against the specific topic
            if keywords:
                def validate_and_filter(journals, max_count):
                    validated = []
                    for j in journals:
                        if len(validated) >= max_count:
                            break
                        # Try to validate against keywords
                        journal_name = j.get("name", "") if isinstance(j, dict) else str(j)
                        validation = self._validate_journal_fit(
                            journal_name=journal_name,
                            journal_oa_id=j.get("openalex_id", "") if isinstance(j, dict) else "",
                            paper_type=paper_type,
                            keywords=keywords,
                        )
                        if validation.get("validated", False):
                            if isinstance(j, dict):
                                j["validation"] = validation
                                j["verified"] = True
                            validated.append(j)
                    return validated

                primary = validate_and_filter(primary, 8)
                stretch = validate_and_filter(stretch, 5)
                safe = validate_and_filter(safe, 5)

                print(f"[Journal] DB fallback: validated {len(primary)} primary, {len(stretch)} stretch, {len(safe)} safe journals against keywords")
            else:
                primary = primary[:8]
                stretch = stretch[:5]
                safe = safe[:5]

            return {
                "primary_matches": primary,
                "stretch_matches": stretch,
                "safe_matches": safe,
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

    def _detect_red_flags(self, text: str, word_count: int, ref_count: int, paper_type: str = 'experimental', publication_year: int = None) -> dict:
        flags = []
        total_penalty = 0

        for check in RED_FLAG_CHECKS:
            # Skip flags that don't apply to this paper type
            excluded_types = check.get("paper_type_exclude", [])
            if paper_type in excluded_types:
                continue

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

        # Type-specific red flags
        type_flags = RED_FLAGS_BY_TYPE.get(paper_type, [])
        for flag in type_flags:
            pattern = flag.get("pattern")
            check_type = flag.get("check", "missing")

            # ── Dynamic recency check (ISSUE 4 fix) ──
            # Instead of hardcoding "202[3-6]", compute the recency window
            # relative to the paper's own publication year.
            if check_type == "recency_dynamic":
                baseline_year = publication_year or datetime.now().year
                # "Recent" = within 2 years before the paper's publication
                recent_start = baseline_year - 2
                recent_end = baseline_year

                # Build a regex that matches any year in [recent_start, recent_end]
                recent_years = list(range(recent_start, recent_end + 1))
                year_alts = "|".join(str(y) for y in recent_years)
                recency_pattern = rf'\b({year_alts})\b'

                found = bool(re.search(recency_pattern, text))
                if not found:
                    issue_text = flag["issue"]
                    fix_text = flag["fix"]
                    if publication_year:
                        issue_text = f"No references from {recent_start}-{recent_end} (relative to paper's {baseline_year} publication)"
                        fix_text = f"Include recent publications from {recent_start}-{recent_end} (the 2 years around your paper's publication date)"
                    flags.append({"id": flag["id"], "issue": issue_text, "penalty": flag["penalty"], "fix": fix_text, "severity": "warning"})
                    total_penalty += flag["penalty"]
                continue

            if pattern:
                found = bool(re.search(pattern, text, re.IGNORECASE))
                if check_type == "missing" and not found:
                    flags.append({"id": flag["id"], "issue": flag["issue"], "penalty": flag["penalty"], "fix": flag.get("fix", ""), "severity": "warning"})
                    total_penalty += flag["penalty"]
                elif check_type == "present" and found:
                    flags.append({"id": flag["id"], "issue": flag["issue"], "penalty": flag["penalty"], "fix": flag.get("fix", ""), "severity": "warning"})
                    total_penalty += flag["penalty"]

        # Cap total red-flag penalty at -25 to prevent red flags from dominating
        total_penalty = max(total_penalty, -25)

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

    def _detect_methodology_gaps(self, text: str, field: str, paper_type: str = 'experimental') -> list:
        """Detect common methodology gaps that journal reviewers will flag.

        Paper-type-aware: review papers get review-specific checks, experimental
        papers get experimental checks, etc.

        Args:
            text: Full manuscript text
            field: Academic field (e.g., 'biomedical', 'psychology', 'economics')
            paper_type: Detected paper type

        Returns:
            List of gap dicts with name, severity, recommendation, detected status
        """
        text_lower = text.lower()

        # ── Review-specific checks ───────────────────────────────────────
        if paper_type == 'review':
            checks = [
                {
                    'name': 'Search Strategy',
                    'keywords': ['search strategy', 'databases searched', 'pubmed', 'web of science', 'scopus',
                                'search terms', 'search string', 'systematic search', 'literature search'],
                    'severity': 'high',
                    'recommendation': 'Describe the literature search strategy: databases, search terms, date range, inclusion/exclusion criteria.',
                },
                {
                    'name': 'Scope Definition',
                    'keywords': ['scope', 'aim of this review', 'this review focuses', 'we review', 'purpose of this review',
                                'objective', 'in this review we'],
                    'severity': 'medium',
                    'recommendation': 'Clearly define the scope and objectives of the review in the introduction.',
                },
                {
                    'name': 'Critical Analysis',
                    'keywords': ['limitation', 'however', 'in contrast', 'conflicting', 'debate', 'controversy',
                                'drawback', 'caveat', 'shortcoming', 'critique', 'critically'],
                    'severity': 'medium',
                    'recommendation': 'Go beyond summarizing -- include critical analysis of conflicting findings, methodological limitations of reviewed studies.',
                },
                {
                    'name': 'Future Directions',
                    'keywords': ['future', 'remain to be', 'further research', 'unanswered', 'open question',
                                'future directions', 'future studies', 'warrant further'],
                    'severity': 'medium',
                    'recommendation': 'Include a section on future research directions and unanswered questions.',
                },
                {
                    'name': 'Conflict of Interest',
                    'keywords': ['conflict of interest', 'competing interest', 'disclosure', 'no conflict', 'declare no'],
                    'severity': 'medium',
                    'recommendation': 'Include a Conflict of Interest / Competing Interests declaration.',
                },
                {
                    'name': 'PRISMA / Reporting Guidelines',
                    'keywords': ['prisma', 'reporting guideline', 'preferred reporting', 'moose', 'prospero',
                                'registration'],
                    'severity': 'low',
                    'recommendation': 'For systematic reviews, follow PRISMA guidelines. Consider registering the review protocol in PROSPERO.',
                },
            ]

        # ── Meta-analysis-specific checks ────────────────────────────────
        elif paper_type == 'meta_analysis':
            checks = [
                {
                    'name': 'Search Strategy',
                    'keywords': ['search strategy', 'databases searched', 'pubmed', 'web of science', 'scopus',
                                'search terms', 'systematic search'],
                    'severity': 'high',
                    'recommendation': 'Describe the comprehensive literature search strategy.',
                },
                {
                    'name': 'Heterogeneity Assessment',
                    'keywords': ['heterogeneity', 'i-squared', 'i2', 'q statistic', 'tau-squared', 'cochran'],
                    'severity': 'high',
                    'recommendation': 'Report heterogeneity metrics (I-squared, Q statistic, tau-squared).',
                },
                {
                    'name': 'Publication Bias',
                    'keywords': ['publication bias', 'funnel plot', 'egger', 'begg', 'trim and fill', 'asymmetry'],
                    'severity': 'high',
                    'recommendation': 'Assess publication bias using funnel plots and statistical tests (Egger, Begg).',
                },
                {
                    'name': 'Quality Assessment',
                    'keywords': ['quality assessment', 'risk of bias', 'newcastle-ottawa', 'nos', 'cochrane',
                                'jadad', 'rob 2', 'robins'],
                    'severity': 'high',
                    'recommendation': 'Use a validated tool (Cochrane RoB, Newcastle-Ottawa) to assess study quality.',
                },
                {
                    'name': 'PRISMA Adherence',
                    'keywords': ['prisma', 'preferred reporting', 'prospero', 'registration'],
                    'severity': 'medium',
                    'recommendation': 'Follow PRISMA guidelines for reporting. Register the protocol in PROSPERO.',
                },
                {
                    'name': 'Sensitivity Analysis',
                    'keywords': ['sensitivity analysis', 'leave-one-out', 'subgroup analysis', 'sensitivity'],
                    'severity': 'medium',
                    'recommendation': 'Perform sensitivity analyses to test robustness of pooled results.',
                },
                {
                    'name': 'Conflict of Interest',
                    'keywords': ['conflict of interest', 'competing interest', 'disclosure', 'no conflict', 'declare no'],
                    'severity': 'medium',
                    'recommendation': 'Include a Conflict of Interest / Competing Interests declaration.',
                },
            ]

        # ── Case report-specific checks ──────────────────────────────────
        elif paper_type == 'case_report':
            checks = [
                {
                    'name': 'Patient Consent',
                    'keywords': ['informed consent', 'patient consent', 'written consent', 'verbal consent',
                                'consent obtained', 'approved by'],
                    'severity': 'high',
                    'recommendation': 'Include a statement about informed patient consent for publication.',
                },
                {
                    'name': 'Clinical Timeline',
                    'keywords': ['timeline', 'day 1', 'on admission', 'hospital day', 'week', 'month',
                                'follow-up', 'at presentation'],
                    'severity': 'medium',
                    'recommendation': 'Provide a clear clinical timeline of events.',
                },
                {
                    'name': 'Differential Diagnosis',
                    'keywords': ['differential diagnosis', 'differential', 'ruled out', 'excluded',
                                'considered', 'alternative diagnosis'],
                    'severity': 'medium',
                    'recommendation': 'Discuss the differential diagnosis and why alternatives were excluded.',
                },
                {
                    'name': 'CARE Guidelines',
                    'keywords': ['care guideline', 'care checklist', 'case report guidelines'],
                    'severity': 'low',
                    'recommendation': 'Follow the CARE (CAse REport) guidelines for structured case reporting.',
                },
                {
                    'name': 'Literature Comparison',
                    'keywords': ['similar case', 'previously reported', 'literature', 'published case',
                                'in the literature', 'our case differs'],
                    'severity': 'medium',
                    'recommendation': 'Compare this case with similar cases in the literature.',
                },
            ]

        # ── Protocol-specific checks ─────────────────────────────────────
        elif paper_type == 'protocol':
            checks = [
                {
                    'name': 'Reagent Details',
                    'keywords': ['catalog', 'vendor', 'supplier', 'manufacturer', 'cat#', 'cat. no',
                                'purchased from', 'obtained from'],
                    'severity': 'high',
                    'recommendation': 'Provide vendor names and catalog numbers for all reagents.',
                },
                {
                    'name': 'Equipment Settings',
                    'keywords': ['rpm', 'temperature', 'voltage', 'watt', 'settings', 'parameters',
                                'conditions'],
                    'severity': 'high',
                    'recommendation': 'Specify exact equipment settings (RPM, temperature, voltage, etc.).',
                },
                {
                    'name': 'Timing Details',
                    'keywords': ['minutes', 'hours', 'seconds', 'overnight', 'incubat'],
                    'severity': 'medium',
                    'recommendation': 'Provide exact durations for all incubation and processing steps.',
                },
                {
                    'name': 'Troubleshooting Section',
                    'keywords': ['troubleshoot', 'common problem', 'if this fails', 'tips', 'notes',
                                'caution', 'warning', 'critical step'],
                    'severity': 'medium',
                    'recommendation': 'Add a troubleshooting section with common problems and solutions.',
                },
                {
                    'name': 'Safety Information',
                    'keywords': ['safety', 'hazard', 'ppe', 'fume hood', 'gloves', 'goggles',
                                'biohazard', 'waste disposal'],
                    'severity': 'medium',
                    'recommendation': 'Include safety precautions and waste disposal instructions.',
                },
            ]

        # ── Experimental paper checks (default) ──────────────────────────
        else:
            checks = [
                {
                    'name': 'Sample Size Justification',
                    'keywords': ['sample size', 'power analysis', 'power calculation', 'n =', 'participants were', 'sample of'],
                    'severity': 'high',
                    'recommendation': 'Add a power analysis or sample size justification in the Methods section.',
                },
                {
                    'name': 'Blinding/Randomization',
                    'keywords': ['blind', 'randomiz', 'double-blind', 'single-blind', 'allocation conceal', 'random assignment'],
                    'severity': 'high' if field in ('biomedical', 'psychology', 'biology') else 'medium',
                    'recommendation': 'Describe blinding and randomization procedures, or explain why they were not applicable.',
                },
                {
                    'name': 'Ethics Statement',
                    'keywords': ['ethics', 'irb', 'institutional review', 'informed consent', 'ethics committee', 'iacuc', 'ethical approval'],
                    'severity': 'high' if field in ('biomedical', 'psychology', 'biology') else 'low',
                    'recommendation': 'Include IRB/ethics committee approval number and informed consent details.',
                },
                {
                    'name': 'Data Availability',
                    'keywords': ['data availab', 'data sharing', 'openly available', 'repository', 'supplementary data', 'upon request', 'data access'],
                    'severity': 'medium',
                    'recommendation': 'Add a Data Availability Statement specifying where data can be accessed.',
                },
                {
                    'name': 'Conflict of Interest',
                    'keywords': ['conflict of interest', 'competing interest', 'disclosure', 'no conflict', 'declare no'],
                    'severity': 'medium',
                    'recommendation': 'Include a Conflict of Interest / Competing Interests declaration.',
                },
                {
                    'name': 'Statistical Methods',
                    'keywords': ['t-test', 'anova', 'regression', 'chi-square', 'p-value', 'confidence interval',
                                'mann-whitney', 'statistical analys', 'significance level', 'alpha ='],
                    'severity': 'high',
                    'recommendation': 'Describe statistical tests used, significance thresholds, and software/versions.',
                },
                {
                    'name': 'Limitations',
                    'keywords': ['limitation', 'caveat', 'shortcoming', 'weakness', 'future work should address',
                                'acknowledge that', 'despite these'],
                    'severity': 'medium',
                    'recommendation': 'Add a Limitations section discussing study constraints and their impact.',
                },
                {
                    'name': 'Reproducibility Details',
                    'keywords': ['protocol', 'code availab', 'software version', 'package version', 'reproducib',
                                'materials and methods', 'detailed in supplementa'],
                    'severity': 'medium' if field in ('biomedical', 'biology', 'cs_data_science') else 'low',
                    'recommendation': 'Provide sufficient detail for independent replication: software versions, parameter settings, protocol steps.',
                },
            ]

        gaps = []
        for check in checks:
            found = any(kw in text_lower for kw in check['keywords'])
            if not found:
                gaps.append({
                    'gap': check['name'],
                    'severity': check['severity'],
                    'recommendation': check['recommendation'],
                    'detected': False,
                })

        return gaps

    def _assess_review_methodology(self, text: str, title: str, paper_type: str = 'review', publication_year: int = None) -> dict:
        """Assess methodology and synthesis quality for review/meta-analysis papers.

        Instead of generic research gap detection (which doesn't apply to reviews,
        since reviews ARE about identifying gaps), this evaluates:
        1. Search Strategy & Inclusion Criteria - PRISMA compliance, databases searched
        2. Synthesis Quality - how well findings are integrated vs. just listed
        3. Coverage Analysis - topics/areas the review may have missed

        Returns a structured assessment dict emitted as the 'review_methodology' SSE event.
        """
        type_label = "systematic review" if paper_type == "review" else "meta-analysis"
        meta_specific = ""
        if paper_type == "meta_analysis":
            meta_specific = (
                "\n\nMETA-ANALYSIS SPECIFIC — also evaluate:\n"
                "- Effect size measure used (OR, RR, HR, SMD, etc.) and appropriateness\n"
                "- Heterogeneity assessment (I-squared, Q-statistic, tau-squared)\n"
                "- Publication bias tests (funnel plot, Egger test, trim-and-fill)\n"
                "- Sensitivity/subgroup analysis adequacy\n"
                "- Forest plot clarity and completeness\n"
                "- Random vs. fixed effects model justification\n"
            )

        meta_json_block = ""
        if paper_type == "meta_analysis":
            meta_json_block = (
                ',\n    "meta_analysis_rigor": {\n'
                '        "effect_size_appropriate": true,\n'
                '        "heterogeneity_assessed": true,\n'
                '        "publication_bias_tested": true,\n'
                '        "sensitivity_analysis_done": true,\n'
                '        "subgroup_analysis_done": true,\n'
                '        "model_justified": true,\n'
                '        "strengths": ["1-2 statistical strengths"],\n'
                '        "weaknesses": ["1-3 statistical issues"],\n'
                '        "recommendations": ["1-3 statistical improvements"]\n'
                '    }'
            )

        # Year-awareness: evaluate coverage ONLY relative to literature available at publication time
        year_context = ""
        year_instruction = ""
        if publication_year:
            year_context = f"\nPUBLICATION YEAR: {publication_year}\n"
            year_instruction = (
                f"\n\nCRITICAL YEAR-AWARENESS RULE: This paper was published in {publication_year}. "
                f"You MUST evaluate its literature coverage ONLY against studies available up to {publication_year}. "
                f"Do NOT penalize for missing studies published AFTER {publication_year} — those did not exist when this paper was written. "
                f"'Recency' means: did the review include the latest studies available AT THE TIME of writing (up to {publication_year})? "
                f"A 2013 review that covers literature through 2012-2013 is 'up-to-date', NOT 'outdated'. "
                f"Only flag recency issues if the review missed studies that were already published BEFORE {publication_year}.\n"
            )
        else:
            year_instruction = (
                "\n\nNote: If you can detect the paper's publication year from its content, evaluate "
                "recency RELATIVE to that year, not the current year.\n"
            )

        prompt = f"""You are a senior methodologist evaluating a {type_label} paper for journal submission.

TITLE: {title}
{year_context}
MANUSCRIPT (first 18,000 chars):
{text[:18000]}

Evaluate this {type_label} across three dimensions. For each, provide a score (0-100) and specific evidence-based findings.
{year_instruction}{meta_specific}
Respond in JSON format:
{{{{
    "search_strategy": {{{{
        "score": 65,
        "databases_mentioned": ["list of databases mentioned, e.g. PubMed, Scopus, Web of Science"],
        "date_range_specified": true,
        "search_terms_described": true,
        "prisma_compliant": false,
        "inclusion_criteria_clear": true,
        "exclusion_criteria_clear": false,
        "screening_process_described": true,
        "strengths": ["1-3 specific strengths with quoted evidence"],
        "weaknesses": ["1-4 specific weaknesses — what is missing or vague"],
        "recommendations": ["1-3 actionable fixes"]
    }}}},
    "synthesis_quality": {{{{
        "score": 55,
        "approach": "narrative or thematic or chronological or methodological or framework-based",
        "critical_comparison": true,
        "themes_identified": true,
        "contradictions_addressed": false,
        "theoretical_framework_used": false,
        "strengths": ["1-3 specific strengths — where synthesis is genuinely insightful"],
        "weaknesses": ["1-4 specific issues — e.g. Section 3.2 lists 12 studies sequentially without comparing their findings"],
        "recommendations": ["1-3 actionable improvements, e.g. Add a comparison table for the 8 RCTs in Section 4"]
    }}}},
    "coverage_analysis": {{{{
        "score": 60,
        "total_studies_included": 45,
        "date_range_of_studies": "e.g. 2010-2012 or unclear",
        "geographic_diversity": "global or regional or single-country or unclear",
        "study_type_diversity": "mixed methods or RCTs only or observational only or etc.",
        "potential_gaps": ["1-4 specific topic areas or perspectives the review appears to miss — ONLY flag gaps in literature that existed BEFORE the paper's publication year"],
        "recency_assessment": "up-to-date or slightly outdated or significantly outdated — RELATIVE TO THE PAPER'S OWN PUBLICATION YEAR, not today",
        "strengths": ["1-2 coverage strengths"],
        "recommendations": ["1-3 ways to improve coverage — ONLY suggest adding studies that were available before the publication year"]
    }}}}{meta_json_block}
}}}}
"""

        try:
            response = self.openai.chat_completion(
                messages=[
                    {"role": "system", "content": f"You are a senior peer reviewer and methodologist specializing in {type_label} papers. Evaluate rigorously but fairly. Always cite specific evidence from the manuscript. CRITICAL: When evaluating literature coverage and recency, you MUST judge relative to the paper's own publication year — never penalize a paper for not citing studies that were published AFTER it."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=4000,
                response_format={"type": "json_object"}
            )
            result = json.loads(response.choices[0].message.content)

            # Compute overall rigor score as weighted average
            search_score = result.get('search_strategy', {}).get('score', 50)
            synthesis_score = result.get('synthesis_quality', {}).get('score', 50)
            coverage_score = result.get('coverage_analysis', {}).get('score', 50)

            if paper_type == 'meta_analysis':
                meta_rigor = result.get('meta_analysis_rigor', {})
                meta_checks = [
                    meta_rigor.get('effect_size_appropriate', False),
                    meta_rigor.get('heterogeneity_assessed', False),
                    meta_rigor.get('publication_bias_tested', False),
                    meta_rigor.get('sensitivity_analysis_done', False),
                    meta_rigor.get('subgroup_analysis_done', False),
                    meta_rigor.get('model_justified', False),
                ]
                meta_score = round(sum(1 for c in meta_checks if c) / max(len(meta_checks), 1) * 100)
                result['meta_analysis_rigor']['score'] = meta_score
                overall = round(search_score * 0.25 + synthesis_score * 0.20 + coverage_score * 0.20 + meta_score * 0.35)
            else:
                overall = round(search_score * 0.35 + synthesis_score * 0.40 + coverage_score * 0.25)

            result['overall_rigor_score'] = overall
            result['paper_type'] = paper_type

            print(f"[JournalScorer] Review methodology assessment: overall={overall}, "
                  f"search={search_score}, synthesis={synthesis_score}, coverage={coverage_score}")

            return result

        except Exception as e:
            print(f"[JournalScorer] Review methodology assessment failed: {e}")
            return {
                "search_strategy": {"score": 0, "strengths": [], "weaknesses": ["Assessment failed"], "recommendations": []},
                "synthesis_quality": {"score": 0, "strengths": [], "weaknesses": ["Assessment failed"], "recommendations": []},
                "coverage_analysis": {"score": 0, "strengths": [], "weaknesses": ["Assessment failed"], "recommendations": []},
                "overall_rigor_score": 0,
                "paper_type": paper_type,
                "error": str(e),
            }

    def _generate_paper_type_aware_suggestions(self, text: str, title: str,
                                                paper_type: str,
                                                deep_analysis: dict = None) -> list:
        """Generate follow-up suggestions that are appropriate for the paper type.

        CRITICAL: Review/meta-analysis papers get editorial/analytical suggestions,
        NOT wet-lab experiment suggestions. This prevents hallucinations where a
        review paper is told to run Western blots.

        Args:
            text: Full manuscript text
            title: Manuscript title
            paper_type: Detected type (experimental, review, meta_analysis, case_report, protocol)
            deep_analysis: Type-specific analysis results from PaperAnalysisService

        Returns:
            List of suggestion dicts
        """
        sample = text[:10000]
        analysis_context = ""
        if deep_analysis and not deep_analysis.get('error'):
            analysis_context = f"\nDeep analysis findings: {json.dumps(deep_analysis, default=str)[:3000]}"

        # Build the prompt based on paper type
        if paper_type in ('review', 'meta_analysis'):
            # EDITORIAL/ANALYTICAL suggestions — NOT lab experiments
            type_label = "review" if paper_type == "review" else "meta-analysis"
            prompt = (
                f"You are a research methodology expert. This is a {type_label} paper.\n\n"
                f"PAPER: {title or 'Untitled'}\n"
                f"TEXT:\n{sample}\n"
                f"{analysis_context}\n\n"
                "Since this is a REVIEW or META-ANALYSIS paper, suggest 3-4 EDITORIAL/ANALYTICAL follow-up "
                "opportunities. Do NOT suggest wet-lab experiments — that would be nonsensical for a review paper.\n\n"
                "Suggest from these categories:\n"
                "1. SYSTEMATIC REVIEW EXTENSION: Expand the review scope (new databases, updated time range, "
                "additional inclusion criteria)\n"
                "2. META-ANALYSIS OPPORTUNITY: If this is a narrative review, suggest converting specific "
                "sections into a quantitative meta-analysis\n"
                "3. EDITORIAL PERSPECTIVE: Write a focused commentary or editorial on the most impactful "
                "finding from this review\n"
                "4. GAP-FILLING PRIMARY STUDY: Identify the most critical research gap found in this review "
                "and suggest a specific primary study design to address it\n"
                "5. METHODOLOGICAL CRITIQUE: Suggest a methodological quality assessment of the studies reviewed\n\n"
                "Return JSON:\n"
                '{"suggestions": [\n'
                '  {\n'
                '    "title": "Suggestion title",\n'
                '    "type": "systematic_review_extension|meta_analysis_opportunity|editorial_perspective|gap_filling_study|methodological_critique",\n'
                '    "description": "What to do and why",\n'
                '    "methodology": "Step-by-step approach (3-5 steps)",\n'
                '    "expected_outcome": "What this would produce",\n'
                '    "effort_level": "low|medium|high",\n'
                '    "impact": "How this advances the field"\n'
                '  }\n'
                ']}'
            )
        elif paper_type == 'case_report':
            prompt = (
                f"You are a clinical research advisor. This is a case report.\n\n"
                f"PAPER: {title or 'Untitled'}\n"
                f"TEXT:\n{sample}\n"
                f"{analysis_context}\n\n"
                "Suggest 3-4 follow-up studies that build on this case report. Categories:\n"
                "1. CASE SERIES: Expand to a multi-patient retrospective case series\n"
                "2. COMPARATIVE STUDY: Design a controlled study comparing treatments/approaches\n"
                "3. LITERATURE SEARCH: Systematic search for similar reported cases\n"
                "4. MECHANISTIC INVESTIGATION: Lab study to investigate the mechanism behind the clinical observation\n"
                "5. REGISTRY PROPOSAL: Propose a patient registry for this condition\n\n"
                "Return JSON:\n"
                '{"suggestions": [\n'
                '  {\n'
                '    "title": "Study title",\n'
                '    "type": "case_series|comparative_study|literature_search|mechanistic_investigation|registry_proposal",\n'
                '    "description": "What to do and why",\n'
                '    "methodology": "Step-by-step approach",\n'
                '    "expected_outcome": "What this would produce",\n'
                '    "effort_level": "low|medium|high",\n'
                '    "impact": "How this advances clinical knowledge"\n'
                '  }\n'
                ']}'
            )
        elif paper_type == 'protocol':
            prompt = (
                f"You are a lab methods expert. This is a protocol paper.\n\n"
                f"PAPER: {title or 'Untitled'}\n"
                f"TEXT:\n{sample}\n"
                f"{analysis_context}\n\n"
                "Suggest 3-4 validation/optimization experiments for this protocol:\n"
                "1. VALIDATION EXPERIMENT: Test protocol reproducibility across labs/conditions\n"
                "2. OPTIMIZATION: Identify parameters to optimize (temperature, concentration, timing)\n"
                "3. COMPARISON: Compare this protocol against the current gold standard\n"
                "4. ADAPTATION: Adapt the protocol for a different model system or application\n"
                "5. TROUBLESHOOTING GUIDE: Systematic testing of failure modes\n\n"
                "Return JSON:\n"
                '{"suggestions": [\n'
                '  {\n'
                '    "title": "Experiment title",\n'
                '    "type": "validation|optimization|comparison|adaptation|troubleshooting",\n'
                '    "description": "What to do and why",\n'
                '    "methodology": "Step-by-step approach with specific parameters",\n'
                '    "expected_outcome": "What success looks like",\n'
                '    "effort_level": "low|medium|high",\n'
                '    "impact": "How this improves the protocol"\n'
                '  }\n'
                ']}'
            )
        else:
            # experimental or unknown — standard lab experiment suggestions
            prompt = (
                f"You are a research methodology expert. This is an experimental paper.\n\n"
                f"PAPER: {title or 'Untitled'}\n"
                f"TEXT:\n{sample}\n"
                f"{analysis_context}\n\n"
                "Suggest 3-4 specific follow-up experiments that build on this paper's findings:\n"
                "1. Reference specific results/data from the paper\n"
                "2. Include exact model systems, techniques, and controls\n"
                "3. Explain how each experiment extends the current findings\n\n"
                "Return JSON:\n"
                '{"suggestions": [\n'
                '  {\n'
                '    "title": "Experiment title",\n'
                '    "type": "validation|extension|mechanistic|translational|methodology",\n'
                '    "hypothesis": "What this tests — reference specific paper findings",\n'
                '    "methodology": "Step-by-step approach (3-5 steps) with specific techniques",\n'
                '    "controls": ["Required controls"],\n'
                '    "expected_outcome": "What success looks like",\n'
                '    "effort_level": "low|medium|high",\n'
                '    "impact": "How this strengthens or extends the paper"\n'
                '  }\n'
                ']}'
            )

        try:
            resp = self.openai.chat_completion(
                messages=[
                    {"role": "system", "content": "You are a research advisor. Respond only with valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=3000,
                response_format={"type": "json_object"},
            )
            raw = resp.choices[0].message.content.strip()
            result = json.loads(raw)
            suggestions = result.get('suggestions', [])
            # Tag each suggestion with the paper type for frontend awareness
            for s in suggestions:
                s['paper_type'] = paper_type
            return suggestions
        except Exception as e:
            print(f"[JournalScorer] Paper-type-aware suggestions failed: {e}")
            return []

    def _find_citation_neighbor_journals(self, references: list, field: str) -> list:
        """Find journals that frequently publish papers in the same citation neighborhood.

        Analyzes the manuscript's references via OpenAlex to find journals
        where related papers are frequently published.

        Args:
            references: List of reference strings (DOIs, titles, or citation text)
            field: Academic field for context

        Returns:
            List of journal suggestion dicts sorted by citation overlap
        """
        try:
            from services.openalex_search_service import OpenAlexSearchService
        except ImportError:
            print("[JournalScorer] OpenAlex service not available")
            return []

        openalex = OpenAlexSearchService()
        journal_counts = {}

        for ref in references[:15]:  # Cap at 15 references for speed
            try:
                # Search OpenAlex for this reference
                works = openalex.search_works(ref, max_results=3)
                for work in works:
                    journal = work.get('journal', '')
                    if journal and len(journal) > 2:
                        journal_counts[journal] = journal_counts.get(journal, 0) + 1
            except Exception:
                continue

        # Sort by frequency — journals appearing most often in citation neighborhood
        neighbor_journals = sorted(journal_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        return [{
            'journal_name': name,
            'citation_overlap': count,
            'match_reason': f'Found in {count} of your references\' citation neighborhoods',
            'source': 'citation_neighborhood',
        } for name, count in neighbor_journals]

    # ── Enrich suggested references with real DOIs from OpenAlex ─────────────

    def _enrich_suggested_references(self, refs: list, manuscript_title: str = '') -> list:
        """Strip hallucinated URLs from LLM-suggested references and look up real DOIs.

        For each reference, search OpenAlex by title to find the real paper and DOI.
        Filters out any reference that matches the uploaded manuscript (self-reference).
        Returns cleaned references with verified DOI URLs where found.
        """
        if not refs:
            return []

        enriched = []
        for ref in refs:
            if not isinstance(ref, dict):
                continue
            # Only keep safe fields
            clean = {k: v for k, v in ref.items() if k in ("title", "authors", "year", "relevance")}
            title = clean.get("title", "")
            if not title:
                enriched.append(clean)
                continue

            # ── Self-reference filter (ISSUE 6 fix) ──
            # Skip references that match the uploaded paper's own title
            if manuscript_title and self._is_self_reference(manuscript_title, title):
                print(f"[JournalScorer] Filtered self-reference from suggested refs: {title[:60]}...")
                continue

            # Search OpenAlex for this paper by title
            try:
                results = self.openalex.search_works(title, max_results=1, min_citations=0)
                if results:
                    paper = results[0]
                    paper_title = paper.get("title", "")
                    # Basic fuzzy match — first 40 chars of title should overlap
                    if paper_title and title[:40].lower().strip() in paper_title.lower() or paper_title[:40].lower().strip() in title.lower():
                        # Also check that the OpenAlex result is not the manuscript itself
                        if manuscript_title and self._is_self_reference(manuscript_title, paper_title):
                            print(f"[JournalScorer] Filtered self-reference (OpenAlex match): {paper_title[:60]}...")
                            continue
                        doi = paper.get("doi", "")
                        if doi:
                            if not doi.startswith("http"):
                                doi = f"https://doi.org/{doi}"
                            clean["url"] = doi
            except Exception:
                pass  # Non-critical — just won't have a link

            enriched.append(clean)

        return enriched

    # ── Reference Bank: pre-fetch real papers from OpenAlex ─────────────────

    def _fetch_reference_bank(self, keywords: list, field: str, manuscript_title: str = '', publication_year: int = None) -> list:
        """Fetch real papers from OpenAlex to use as a verified reference bank.

        Returns up to 15 papers with real DOIs that the LLM can cite,
        preventing DOI hallucination. Filters out the user's own paper
        to avoid self-referencing.

        CRITICAL: If publication_year is provided, only fetch papers published
        BEFORE that year. A 2013 paper cannot cite a 2022 paper!
        """
        if not keywords:
            keywords = [field]

        all_papers = []
        seen_dois = set()

        # Determine year range for references
        # For a paper from 2013, we want refs from ~2003-2013 (last 10 years before publication)
        to_year = publication_year if publication_year else None
        from_year = (publication_year - 10) if publication_year else None

        if publication_year:
            print(f"[JournalScorer] Reference bank: filtering to papers from {from_year}-{to_year}")

        # Search with top keywords (combine first 3-4 for relevance)
        primary_query = " ".join(keywords[:4])
        try:
            results = self.openalex.search_works(
                query=primary_query,
                max_results=10,
                min_citations=5,
                from_year=from_year,
                to_year=to_year,
            )
            for paper in results:
                doi = paper.get("doi", "")
                paper_title = paper.get("title", "")
                # ── Self-reference filter (ISSUE 6 fix) ──
                if manuscript_title and self._is_self_reference(manuscript_title, paper_title):
                    print(f"[JournalScorer] Filtered self-reference from reference bank: {paper_title[:60]}...")
                    continue
                if doi and doi not in seen_dois:
                    seen_dois.add(doi)
                    all_papers.append({
                        "title": paper_title,
                        "authors": paper.get("authors", []),
                        "year": paper.get("year"),
                        "doi": doi,
                        "journal": paper.get("journal", ""),
                        "cited_by_count": paper.get("cited_by_count", 0),
                    })
        except Exception as e:
            print(f"[JournalScorer] OpenAlex primary search failed: {e}")

        # If we have fewer than 10, do a secondary search with different keyword combos
        if len(all_papers) < 10 and len(keywords) > 2:
            secondary_query = " ".join(keywords[1:5]) if len(keywords) > 4 else " ".join(keywords[:3])
            try:
                results2 = self.openalex.search_works(
                    query=secondary_query,
                    max_results=8,
                    min_citations=3,
                    from_year=from_year,
                    to_year=to_year,
                )
                for paper in results2:
                    doi = paper.get("doi", "")
                    paper_title = paper.get("title", "")
                    # ── Self-reference filter (ISSUE 6 fix) ──
                    if manuscript_title and self._is_self_reference(manuscript_title, paper_title):
                        print(f"[JournalScorer] Filtered self-reference from reference bank (secondary): {paper_title[:60]}...")
                        continue
                    if doi and doi not in seen_dois:
                        seen_dois.add(doi)
                        all_papers.append({
                            "title": paper_title,
                            "authors": paper.get("authors", []),
                            "year": paper.get("year"),
                            "doi": doi,
                            "journal": paper.get("journal", ""),
                            "cited_by_count": paper.get("cited_by_count", 0),
                        })
            except Exception as e:
                print(f"[JournalScorer] OpenAlex secondary search failed: {e}")

        # Sort by citation count (most-cited first) and cap at 15
        all_papers.sort(key=lambda p: p.get("cited_by_count", 0), reverse=True)
        return all_papers[:15]

    def _format_reference_bank(self, reference_bank: list) -> str:
        """Format the reference bank as a numbered list for prompt injection."""
        if not reference_bank:
            return "(No verified references available — do NOT cite any papers by name or DOI.)\n"

        lines = ["REFERENCE BANK (verified real papers with real DOIs):\n"]
        for i, ref in enumerate(reference_bank, 1):
            authors_str = ", ".join(ref["authors"][:3]) if ref["authors"] else "Unknown"
            if len(ref.get("authors", [])) > 3:
                authors_str += " et al."
            doi = ref["doi"]
            # Normalize DOI to URL form
            if doi and not doi.startswith("http"):
                doi = f"https://doi.org/{doi}"
            lines.append(
                f"{i}. {authors_str} ({ref.get('year', 'n.d.')}). "
                f"\"{ref['title']}\". {ref.get('journal', '')}. "
                f"DOI: {doi}"
            )
        lines.append("")
        return "\n".join(lines)

    # ── DOI sanitization: strip hallucinated DOIs from output ───────────────

    def _sanitize_doi_links(self, text: str, reference_bank: list) -> str:
        """Strip any DOI links that were NOT in the verified reference bank.

        Finds markdown links like [text](https://doi.org/...) and plain DOI URLs.
        If the DOI was not in our reference bank, strips the link but keeps the text.
        """
        # Build set of known-good DOIs (normalized to full URL form)
        valid_dois = set()
        for ref in reference_bank:
            doi = ref.get("doi", "")
            if doi:
                # Normalize: ensure both forms are covered
                if doi.startswith("https://doi.org/"):
                    valid_dois.add(doi)
                    valid_dois.add(doi.replace("https://doi.org/", ""))
                elif doi.startswith("http://doi.org/"):
                    valid_dois.add(doi)
                    valid_dois.add(doi.replace("http://doi.org/", ""))
                    valid_dois.add(doi.replace("http://", "https://"))
                else:
                    valid_dois.add(doi)
                    valid_dois.add(f"https://doi.org/{doi}")

        def _is_valid_doi(doi_url: str) -> bool:
            """Check if a DOI URL matches any paper in the reference bank."""
            if doi_url in valid_dois:
                return True
            # Also check the bare DOI portion
            bare = doi_url.replace("https://doi.org/", "").replace("http://doi.org/", "")
            return bare in valid_dois

        # Pattern 1: Markdown links with DOI URLs — [text](https://doi.org/...)
        def replace_md_doi(match):
            link_text = match.group(1)
            doi_url = match.group(2)
            if _is_valid_doi(doi_url):
                return match.group(0)  # Keep valid DOI links
            return link_text  # Strip fake DOI, keep text

        text = re.sub(
            r'\[([^\]]+)\]\((https?://doi\.org/[^\)]+)\)',
            replace_md_doi,
            text,
        )

        # Pattern 2: Bare DOI URLs not inside markdown links
        def replace_bare_doi(match):
            doi_url = match.group(0)
            if _is_valid_doi(doi_url):
                return doi_url  # Keep valid
            return ""  # Strip fake bare DOIs

        text = re.sub(
            r'(?<!\()(https?://doi\.org/10\.\S+?)(?=[\s,;\)\]\n]|$)',
            replace_bare_doi,
            text,
        )

        return text

    def _generate_recommendations_stream(self, field_label, score, tier, features, flags, journals, landscape, citations, keywords=None, subfield="", paper_type=None, research_gaps=None, reference_bank=None, publication_year=None, manuscript_title=None):
        feature_summary = "\n".join(
            f"- {f['label']}: {f['score']}/100 — {f.get('details', '')}"
            for f in features.values()
        )
        flag_summary = "\n".join(f"- [{f['severity']}] {f['issue']}" for f in flags) if flags else "None detected"

        # Get journal names from primary matches — ONLY these verified journals
        primary = journals.get("primary_matches", [])
        stretch = journals.get("stretch_matches", [])
        safe = journals.get("safe_matches", [])
        if primary and isinstance(primary[0], dict):
            journal_names = ", ".join(j.get("name", str(j)) for j in primary[:5])
        else:
            journal_names = "Various journals in the field"

        # Build verified journal list for the LLM (prevents hallucination)
        all_verified = []
        for tier_label, tier_journals in [("Stretch", stretch), ("Target", primary), ("Safe", safe)]:
            for j in tier_journals:
                if isinstance(j, dict):
                    name = j.get("name", "")
                    verified = j.get("verified", False)
                    evidence = j.get("validation", {}).get("evidence", "") if isinstance(j.get("validation"), dict) else ""
                    all_verified.append(f"  - {name} ({tier_label}){' [VERIFIED]' if verified else ''}")

        verified_journal_list = "\n".join(all_verified) if all_verified else "  (No journals matched)"

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

        # Paper type context
        paper_type_info = ""
        if paper_type:
            paper_type_info = f"\n- Paper type: {paper_type}"

        # Manuscript title context — CRITICAL to prevent self-citation suggestions
        manuscript_info = ""
        if manuscript_title:
            manuscript_info = f"\n- THIS MANUSCRIPT'S TITLE: \"{manuscript_title}\" — DO NOT suggest citing this paper as a missing reference"

        # Publication year context — CRITICAL for appropriate recommendations
        year_context = ""
        year_warning = ""
        if publication_year:
            year_context = f"\n- Publication year: {publication_year}"
            year_warning = (
                f"\n\n⚠️ CRITICAL YEAR CONSTRAINT: This manuscript was written in {publication_year}. "
                f"You MUST ONLY recommend citing papers published BEFORE {publication_year}. "
                f"Do NOT suggest adding references from {publication_year + 1} or later — those papers did not exist when this manuscript was written. "
                f"The Reference Bank below contains ONLY papers published up to {publication_year}. "
                f"If a topic emerged after {publication_year}, acknowledge that it was not yet established at the time of writing, rather than suggesting the author cite future papers."
            )

        # Research gaps context
        gaps_info = ""
        if research_gaps:
            gap_summaries = []
            for g in research_gaps[:5]:
                gap_title = g.get('title', '') if isinstance(g, dict) else str(g)
                gap_summaries.append(f"  - {gap_title}")
            if gap_summaries:
                gaps_info = f"\n- Research gaps detected:\n" + "\n".join(gap_summaries)

        # ── Build paper-type-specific Section 1 ──────────────────────────
        if paper_type in ('review', 'meta_analysis'):
            section1 = (
                "## SECTION 1: Specific Improvements to Strengthen This Review\n\n"
                "List exactly 3-5 specific improvements as a numbered list. "
                "This is a REVIEW/META-ANALYSIS — do NOT suggest wet-lab experiments.\n\n"
                "For EACH improvement, include:\n"
                "- **Improvement title** — clear, specific\n"
                "- **Type** — one of: coverage gap, synthesis improvement, methodological addition, "
                "visualization/figure suggestion, updated analysis\n"
                "- **What to do** — specific action (e.g., 'Add a section on emerging ferroptosis-iron interactions "
                "covering the 15+ papers published since 2022', NOT 'expand the review')\n"
                "- **Why this matters** — how this strengthens the review for journal acceptance\n"
                "- **Key references to add** — select 2-3 papers from the Reference Bank below that should be incorporated\n\n"
                "Types of improvements to suggest:\n"
                "- Missing subtopics or recent developments not covered\n"
                "- Sections where synthesis is weak (just listing studies vs. critically comparing them)\n"
                "- Summary tables or figures that would improve clarity\n"
                "- If a narrative review: sections that could become a quantitative meta-analysis\n"
                "- Updated literature searches (papers published after the review's search date)\n\n"
                "CRITICAL: These must be specific to THIS review's topic "
                f"({', '.join(keywords[:4]) if keywords else field_label}). "
                "Do NOT suggest running Western blots, doing cell culture, or any bench experiments.\n\n"
            )
        elif paper_type == 'case_report':
            section1 = (
                "## SECTION 1: Specific Improvements to Strengthen This Case Report\n\n"
                "List exactly 3-5 specific improvements as a numbered list. For EACH:\n"
                "- **Improvement title**\n"
                "- **Type** — clinical detail, differential diagnosis, literature comparison, "
                "follow-up data, educational value\n"
                "- **What to do** — specific action\n"
                "- **Why this matters** — how this improves the case report\n"
                "- **Reference** — select a relevant paper from the Reference Bank below, if applicable\n\n"
            )
        elif paper_type == 'protocol':
            section1 = (
                "## SECTION 1: Specific Validation Experiments for This Protocol\n\n"
                "List exactly 3-5 specific validation/optimization experiments. For EACH:\n"
                "- **Experiment name**\n"
                "- **What to test** — specific parameter or condition\n"
                "- **Methodology** — exact approach\n"
                "- **Controls** — positive and negative controls\n"
                "- **Expected outcome** — what success looks like\n"
                "- **Reference** — select the closest matching method paper from the Reference Bank below\n\n"
            )
        else:
            # Experimental papers — original experiment suggestions
            section1 = (
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
                "- **Reference** — select the most relevant paper from the Reference Bank below\n\n"
                "CRITICAL: These must be experiments that are directly relevant to THIS paper's specific topic "
                f"({', '.join(keywords[:4]) if keywords else field_label}). "
                "Do NOT give generic advice like 'do dose-response studies'. "
                "Give the exact experiment a PI would assign to a grad student.\n\n"
            )

        prompt = (
            f"You are a senior research advisor specializing in {field_label}"
            f"{(' / ' + subfield) if subfield else ''}. "
            f"Given this manuscript analysis:\n"
            f"- Score: {score}/100 (Tier {tier})\n"
            f"- Feature breakdown:\n{feature_summary}\n"
            f"- Red flags:\n{flag_summary}\n"
            f"- Target journals: {journal_names}"
            f"{keywords_info}"
            f"{paper_type_info}"
            f"{manuscript_info}"
            f"{year_context}"
            f"{gaps_info}"
            f"{landscape_info}"
            f"{citation_info}"
            f"{year_warning}\n\n"

            f"{section1}"

            "## SECTION 2: Missing Key References\n\n"
            "⚠️ STRICT RULES FOR THIS SECTION:\n"
            f"{'1. This paper was written in ' + str(publication_year) + '. ONLY suggest references published BEFORE ' + str(publication_year) + '.' if publication_year else ''}\n"
            "2. You MUST ONLY select papers from the REFERENCE BANK below. Do NOT cite any paper not in the reference bank.\n"
            "3. Do NOT suggest the manuscript itself as a reference — that would be self-citation.\n"
            "4. If the reference bank is empty or has no relevant papers, write: 'No additional references needed from the available literature.'\n\n"
            "Select 3-5 papers from the Reference Bank below. For each:\n"
            "- Full citation using the EXACT title and DOI from the Reference Bank: [Author et al. (Year) - Paper Title](DOI)\n"
            "- One sentence on why this specific paper is essential\n"
            "- Where in the manuscript it should be cited (Introduction, Methods, Discussion)\n\n"

            "## SECTION 3: Structural Improvements\n\n"
            "2-3 specific structural changes to improve acceptance chances.\n\n"

            f"{self._format_reference_bank(reference_bank or [])}\n\n"

            "## VERIFIED JOURNAL LIST\n"
            "The following journals have been verified against OpenAlex data as publishing in this paper's area:\n"
            f"{verified_journal_list}\n\n"
            "FORMATTING RULES:\n"
            "- Use markdown with numbered lists\n"
            "- CITATIONS: You MUST ONLY cite papers that appear in the REFERENCE BANK above. Copy the exact title and DOI.\n"
            "- ABSOLUTELY DO NOT cite papers from your training data that are not in the Reference Bank.\n"
            "- ABSOLUTELY DO NOT suggest citing the manuscript itself — that is the paper being analyzed.\n"
            "- If the Reference Bank is empty or has no suitable papers, say so explicitly instead of inventing citations.\n"
            "- JOURNALS: ONLY mention journals from the VERIFIED JOURNAL LIST above.\n"
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
