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

# ── Field-to-OpenAlex Concept Mapping ─────────────────────────────────────────
# OpenAlex concepts for filtering journal searches by field of study
# This ensures 80% of journal recommendations come from field-appropriate sources
FIELD_TO_OPENALEX_CONCEPTS = {
    "biomedical": {
        "concepts": ["C71924100", "C86803240", "C126322002"],  # Medicine, Biology, Biochemistry
        "exclude_concepts": ["C39432304", "C127313418"],  # Environmental Science, Geology
        "field_keywords": ["clinical", "medical", "disease", "patient", "therapeutic", "cell", "molecular", "protein"],
    },
    "biology": {
        "concepts": ["C86803240", "C104317684", "C55493867"],  # Biology, Cell Biology, Molecular Biology
        "exclude_concepts": ["C39432304", "C127313418", "C33923547"],  # Environmental Science, Geology, Ecology (when not relevant)
        "field_keywords": ["cell", "molecular", "gene", "protein", "organism", "biological", "biochemistry", "bioenergetics"],
    },
    "chemistry": {
        "concepts": ["C185592680", "C178790620"],  # Chemistry, Organic Chemistry
        "exclude_concepts": ["C39432304"],  # Environmental Science
        "field_keywords": ["chemical", "synthesis", "compound", "reaction", "catalysis", "molecular"],
    },
    "physics": {
        "concepts": ["C121332964", "C62520636"],  # Physics, Condensed Matter Physics
        "exclude_concepts": [],
        "field_keywords": ["quantum", "particle", "energy", "wave", "field", "matter"],
    },
    "engineering": {
        "concepts": ["C127413603", "C199360897"],  # Engineering, Electrical Engineering
        "exclude_concepts": [],
        "field_keywords": ["design", "system", "control", "optimization", "device"],
    },
    "cs_data_science": {
        "concepts": ["C41008148", "C154945302"],  # Computer Science, AI
        "exclude_concepts": [],
        "field_keywords": ["algorithm", "machine learning", "data", "neural", "network", "computation"],
    },
    "economics": {
        "concepts": ["C162324750", "C175444787"],  # Economics, Microeconomics
        "exclude_concepts": [],
        "field_keywords": ["market", "price", "economic", "trade", "policy", "growth"],
    },
    "psychology": {
        "concepts": ["C15744967", "C169760540"],  # Psychology, Cognitive Science
        "exclude_concepts": [],
        "field_keywords": ["cognitive", "behavior", "mental", "perception", "emotion"],
    },
    "political_science": {
        "concepts": ["C17744445", "C199539241"],  # Political Science, International Relations
        "exclude_concepts": [],
        "field_keywords": ["policy", "government", "political", "democracy", "election"],
    },
    "sociology": {
        "concepts": ["C144024400", "C118552586"],  # Sociology, Demography
        "exclude_concepts": [],
        "field_keywords": ["social", "society", "community", "culture", "inequality"],
    },
    "environmental_science": {
        "concepts": ["C39432304", "C18903297"],  # Environmental Science, Ecology
        "exclude_concepts": [],
        "field_keywords": ["environment", "ecosystem", "climate", "pollution", "conservation"],
    },
    "neuroscience": {
        "concepts": ["C54355233", "C86803240"],  # Neuroscience, Biology
        "exclude_concepts": ["C39432304"],  # Environmental Science
        "field_keywords": ["brain", "neuron", "neural", "cognitive", "synaptic", "cortex"],
    },
    "materials_science": {
        "concepts": ["C192562407", "C185592680"],  # Materials Science, Chemistry
        "exclude_concepts": [],
        "field_keywords": ["material", "nanoparticle", "polymer", "semiconductor", "alloy"],
    },
    "public_health": {
        "concepts": ["C71924100", "C33923547"],  # Medicine, Epidemiology
        "exclude_concepts": [],
        "field_keywords": ["health", "epidemiology", "disease", "prevention", "population"],
    },
    "mathematics": {
        "concepts": ["C33923547", "C134306372"],  # Mathematics, Statistics
        "exclude_concepts": [],
        "field_keywords": ["theorem", "proof", "equation", "mathematical", "statistical"],
    },
    "law": {
        "concepts": ["C138885662"],  # Law
        "exclude_concepts": [],
        "field_keywords": ["legal", "law", "court", "regulation", "constitutional"],
    },
    "education": {
        "concepts": ["C95457728"],  # Education
        "exclude_concepts": [],
        "field_keywords": ["learning", "teaching", "student", "curriculum", "pedagogy"],
    },
    "business": {
        "concepts": ["C144133560", "C162324750"],  # Business, Economics
        "exclude_concepts": [],
        "field_keywords": ["management", "strategy", "organization", "market", "corporate"],
    },
}

# ── DISCIPLINE-SPECIFIC JOURNAL MAPPINGS ─────────────────────────────────────
# Maps core research disciplines/subfields to their natural-fit specialty journals.
# These are journals where researchers in that SPECIFIC discipline publish,
# NOT journals that just happen to publish papers mentioning the discipline.
#
# The key insight: A paper ABOUT mitochondrial bioenergetics should go to
# Mitochondrion, Autophagy, Free Radical Biology and Medicine — NOT to
# "Environmental Health Perspectives" just because it mentions cancer applications.

DISCIPLINE_JOURNAL_MAPPINGS = {
    # ══════════════════════════════════════════════════════════════════════════
    # DISCIPLINE JOURNAL MAPPINGS
    # ══════════════════════════════════════════════════════════════════════════
    # For each discipline, we define:
    # - core_journals: Specialty journals that are THE natural homes for this topic
    # - tier_2_journals: Good-fit journals that also publish in this area
    # - safe_journals: Lower-barrier, discipline-appropriate fallback options
    # - name_variants: Alternative names for journals (OpenAlex may use different names)
    # - avoid_keywords: Journal name patterns to EXCLUDE
    # ══════════════════════════════════════════════════════════════════════════
    "bioenergetics": {
        "core_journals": [
            "Mitochondrion", "Free Radical Biology and Medicine", "Autophagy",
            "Biochimica et Biophysica Acta - Bioenergetics", "Redox Biology",
            "Antioxidants and Redox Signaling", "Cell Metabolism",
            "Journal of Biological Chemistry", "Antioxidants",
            "Journal of Bioenergetics and Biomembranes"
        ],
        "tier_2_journals": [
            "Cell Death and Differentiation", "Cell Death and Disease",
            "EMBO Journal", "Molecular Cell", "eLife", "Cell Reports"
        ],
        # Safe options: lower-barrier journals that still fit the discipline
        "safe_journals": [
            "Cells", "International Journal of Molecular Sciences",
            "Oxidative Medicine and Cellular Longevity", "Biomolecules",
            "Antioxidants", "Life"
        ],
        # Name variants for matching (OpenAlex may use different names)
        "name_variants": {
            "Biochimica et Biophysica Acta - Bioenergetics": ["BBA Bioenergetics", "BBA - Bioenergetics", "Biochimica Biophysica Acta Bioenergetics"],
            "Free Radical Biology and Medicine": ["Free Radic Biol Med", "FRBM"],
            "Antioxidants and Redox Signaling": ["Antioxid Redox Signal", "ARS"],
        },
        "avoid_keywords": [
            "environmental", "ecology", "epidemiology", "public health",
            "oncology", "cancer research", "tumor", "leukemia",
            "immunology", "immune", "allergy",
            "pharmacology", "drug discovery", "therapeutics",
            "neurology", "lancet",
            "translational medicine", "frontiers in medicine",
        ],
    },
    "mitochondria": {
        "core_journals": [
            "Mitochondrion", "Free Radical Biology and Medicine", "Autophagy",
            "Biochimica et Biophysica Acta - Bioenergetics", "Redox Biology",
            "Journal of Bioenergetics and Biomembranes", "Cell Metabolism",
            "Antioxidants and Redox Signaling", "Antioxidants"
        ],
        "tier_2_journals": [
            "Cell Death and Disease", "Journal of Biological Chemistry",
            "EMBO Journal", "Aging Cell", "Cell Reports", "Molecular Cell"
        ],
        "safe_journals": [
            "Cells", "International Journal of Molecular Sciences",
            "Oxidative Medicine and Cellular Longevity", "Biomolecules", "Life"
        ],
        "name_variants": {
            "Biochimica et Biophysica Acta - Bioenergetics": ["BBA Bioenergetics", "BBA - Bioenergetics"],
        },
        "avoid_keywords": [
            "environmental", "ecology", "public health",
            "oncology", "cancer research", "tumor",
            "immunology", "immune",
            "pharmacology", "drug discovery",
            "lancet", "translational medicine", "frontiers in medicine",
        ],
    },
    "autophagy": {
        "core_journals": [
            "Autophagy", "Cell Death and Differentiation", "Cell Death and Disease",
            "EMBO Journal", "Molecular Cell", "Journal of Cell Biology",
            "Cell Reports", "eLife", "Nature Cell Biology"
        ],
        "tier_2_journals": [
            "Cellular and Molecular Life Sciences",
            "Journal of Biological Chemistry", "Aging Cell"
        ],
        "safe_journals": [
            "Cells", "International Journal of Molecular Sciences", "Biomolecules"
        ],
        "name_variants": {},
        "avoid_keywords": [
            "environmental", "ecology",
            "epidemiology", "public health",
            "lancet", "translational medicine", "frontiers in medicine",
        ],
    },
    "ferroptosis": {
        "core_journals": [
            "Cell Death and Differentiation", "Cell Death and Disease",
            "Free Radical Biology and Medicine", "Redox Biology",
            "Antioxidants and Redox Signaling", "Cell Chemical Biology",
            "Nature Chemical Biology", "Cell Metabolism"
        ],
        "tier_2_journals": [
            "Cell Reports", "eLife", "Journal of Biological Chemistry",
            "Molecular Cell", "EMBO Journal"
        ],
        "avoid_keywords": ["environmental", "ecology"],
    },
    "apoptosis": {
        "core_journals": [
            "Cell Death and Differentiation", "Cell Death and Disease", "Apoptosis",
            "Cell", "Molecular Cell", "Nature Cell Biology", "EMBO Journal"
        ],
        "tier_2_journals": [
            "Cell Reports", "Journal of Biological Chemistry", "eLife"
        ],
        "avoid_keywords": [],
    },
    "cell_signaling": {
        "core_journals": [
            "Cell", "Molecular Cell", "Nature Cell Biology", "Cell Reports",
            "EMBO Journal", "Journal of Cell Biology", "Science Signaling",
            "Journal of Biological Chemistry", "Cell Communication and Signaling"
        ],
        "tier_2_journals": [
            "Cellular and Molecular Life Sciences", "eLife", "PLOS Biology"
        ],
        "avoid_keywords": [],
    },
    "oxidative_stress": {
        "core_journals": [
            "Free Radical Biology and Medicine", "Redox Biology",
            "Antioxidants and Redox Signaling", "Oxidative Medicine and Cellular Longevity",
            "Antioxidants", "Free Radical Research"
        ],
        "tier_2_journals": [
            "Cell Death and Disease", "Journal of Biological Chemistry",
            "Aging Cell", "Biochimica et Biophysica Acta - Molecular Basis of Disease"
        ],
        "avoid_keywords": ["environmental toxicology"],
    },
    "metabolism": {
        "core_journals": [
            "Cell Metabolism", "Nature Metabolism", "Molecular Metabolism",
            "Diabetes", "Journal of Clinical Investigation", "Cell Reports",
            "Molecular Cell", "EMBO Journal"
        ],
        "tier_2_journals": [
            "Diabetologia", "Metabolism", "Journal of Lipid Research",
            "Biochimica et Biophysica Acta - Molecular Basis of Disease"
        ],
        "avoid_keywords": [],
    },
    "epigenetics": {
        "core_journals": [
            "Nature Genetics", "Molecular Cell", "Genes and Development",
            "Genome Research", "Cell", "Nature", "Nucleic Acids Research",
            "Epigenetics and Chromatin", "Genome Biology"
        ],
        "tier_2_journals": [
            "Cell Reports", "eLife", "EMBO Journal", "Nature Communications"
        ],
        "avoid_keywords": [],
    },
    "proteomics": {
        "core_journals": [
            "Molecular and Cellular Proteomics", "Journal of Proteome Research",
            "Proteomics", "Journal of Proteomics", "Nature Methods",
            "Analytical Chemistry", "Mass Spectrometry Reviews"
        ],
        "tier_2_journals": [
            "Molecular Cell", "Cell Reports", "EMBO Journal"
        ],
        "avoid_keywords": [],
    },
    "genomics": {
        "core_journals": [
            "Nature Genetics", "Genome Research", "Genome Biology",
            "Nucleic Acids Research", "Nature Methods", "Cell",
            "American Journal of Human Genetics"
        ],
        "tier_2_journals": [
            "PLOS Genetics", "Nature Communications", "Genetics"
        ],
        "avoid_keywords": [],
    },

    # ── Neuroscience ──────────────────────────────────────────────────────────
    "neurodegeneration": {
        "core_journals": [
            "Acta Neuropathologica", "Brain", "Annals of Neurology",
            "Neurobiology of Disease", "Neurobiology of Aging",
            "Journal of Neuroscience", "Molecular Neurodegeneration",
            "Alzheimer's and Dementia", "Movement Disorders"
        ],
        "tier_2_journals": [
            "Neurology", "JAMA Neurology", "Lancet Neurology",
            "Cell Death and Disease", "Autophagy"
        ],
        "avoid_keywords": ["environmental", "ecology"],
    },
    "synaptic_biology": {
        "core_journals": [
            "Neuron", "Nature Neuroscience", "Journal of Neuroscience",
            "eLife", "Cell Reports", "EMBO Journal", "Current Biology"
        ],
        "tier_2_journals": [
            "Journal of Neurophysiology", "Cerebral Cortex",
            "Brain Structure and Function"
        ],
        "avoid_keywords": [],
    },
    "glia": {
        "core_journals": [
            "Glia", "Nature Neuroscience", "Journal of Neuroscience",
            "Neuron", "Brain Behavior and Immunity", "Acta Neuropathologica"
        ],
        "tier_2_journals": [
            "Journal of Neuroinflammation", "Neurobiology of Disease"
        ],
        "avoid_keywords": [],
    },
    # ── Clinical Neurology ─────────────────────────────────────────────────────
    "clinical_neurology": {
        "core_journals": [
            "Neurology", "JAMA Neurology", "Lancet Neurology", "Brain",
            "Annals of Neurology", "Journal of Neurology Neurosurgery and Psychiatry",
            "European Journal of Neurology", "Journal of the Neurological Sciences",
            "Neurology Clinical Practice", "Frontiers in Neurology"
        ],
        "tier_2_journals": [
            "Journal of Neurology", "Neurological Sciences", "BMC Neurology",
            "Acta Neurologica Scandinavica", "Clinical Neurology and Neurosurgery"
        ],
        "safe_journals": [
            "Frontiers in Neurology", "Neurology Research", "Neurology International"
        ],
        "avoid_keywords": ["cancer", "oncology", "tumor", "hepatology", "liver"],
    },
    "autonomic_neurology": {
        "core_journals": [
            "Autonomic Neuroscience", "Clinical Autonomic Research",
            "Neurology", "Brain", "Annals of Neurology", "JAMA Neurology",
            "Journal of Neurology Neurosurgery and Psychiatry",
            "Movement Disorders", "Journal of the Neurological Sciences"
        ],
        "tier_2_journals": [
            "European Journal of Neurology", "Frontiers in Neurology",
            "Parkinsonism and Related Disorders", "Journal of Neurology"
        ],
        "safe_journals": [
            "Frontiers in Neurology", "Neurology Research", "BMC Neurology"
        ],
        "avoid_keywords": ["cancer", "oncology", "tumor", "hepatology", "liver", "Chinese medicine"],
    },
    "cerebrovascular": {
        "core_journals": [
            "Stroke", "Journal of Cerebral Blood Flow and Metabolism",
            "International Journal of Stroke", "Journal of Stroke",
            "Lancet Neurology", "Brain", "Annals of Neurology",
            "Journal of Stroke and Cerebrovascular Diseases", "Neurology"
        ],
        "tier_2_journals": [
            "European Stroke Journal", "Frontiers in Neurology",
            "Journal of the Neurological Sciences", "Cerebrovascular Diseases"
        ],
        "safe_journals": [
            "Frontiers in Neurology", "BMC Neurology", "Neurology Research"
        ],
        "avoid_keywords": ["cancer", "oncology", "tumor", "hepatology", "Chinese medicine"],
    },
    "multiple_sclerosis": {
        "core_journals": [
            "Multiple Sclerosis Journal", "Lancet Neurology", "Brain",
            "Annals of Neurology", "JAMA Neurology", "Neurology",
            "Journal of Neuroimmunology", "Multiple Sclerosis and Related Disorders"
        ],
        "tier_2_journals": [
            "Journal of Neurology Neurosurgery and Psychiatry",
            "European Journal of Neurology", "Frontiers in Neurology"
        ],
        "avoid_keywords": ["cancer", "oncology", "hepatology"],
    },

    # ── Immunology ────────────────────────────────────────────────────────────
    "immunology": {
        "core_journals": [
            "Immunity", "Nature Immunology", "Journal of Experimental Medicine",
            "Journal of Immunology", "Cell Host and Microbe", "Mucosal Immunology",
            "European Journal of Immunology", "Frontiers in Immunology"
        ],
        "tier_2_journals": [
            "Cell Reports", "eLife", "PLOS Pathogens"
        ],
        "avoid_keywords": [],
    },
    "inflammation": {
        "core_journals": [
            "Nature Immunology", "Immunity", "Journal of Clinical Investigation",
            "Journal of Experimental Medicine", "Cell Host and Microbe",
            "Inflammation", "Journal of Inflammation"
        ],
        "tier_2_journals": [
            "Frontiers in Immunology", "Journal of Immunology", "Cell Reports"
        ],
        "avoid_keywords": [],
    },

    # ── Cancer Biology ────────────────────────────────────────────────────────
    "cancer_biology": {
        "core_journals": [
            "Cancer Cell", "Nature Cancer", "Cancer Discovery", "Oncogene",
            "Cancer Research", "Molecular Cancer Research", "Clinical Cancer Research",
            "Cell", "Nature", "Science"
        ],
        "tier_2_journals": [
            "British Journal of Cancer", "International Journal of Cancer",
            "Carcinogenesis", "Neoplasia", "Molecular Cancer"
        ],
        "avoid_keywords": ["environmental epidemiology", "public health policy"],
    },
    "tumor_microenvironment": {
        "core_journals": [
            "Cancer Cell", "Cancer Discovery", "Cancer Research",
            "Cell", "Nature", "Immunity", "Journal of Clinical Investigation"
        ],
        "tier_2_journals": [
            "Molecular Cancer Research", "Clinical Cancer Research",
            "Journal of Experimental Medicine"
        ],
        "avoid_keywords": [],
    },

    # ── Structural Biology & Biochemistry ─────────────────────────────────────
    "structural_biology": {
        "core_journals": [
            "Nature Structural and Molecular Biology", "Structure",
            "Journal of Molecular Biology", "eLife", "Nature Communications",
            "PNAS", "Nucleic Acids Research"
        ],
        "tier_2_journals": [
            "Proteins", "Journal of Structural Biology", "Acta Crystallographica"
        ],
        "avoid_keywords": [],
    },
    "enzymology": {
        "core_journals": [
            "Biochemistry", "Journal of Biological Chemistry",
            "ACS Catalysis", "Nature Chemical Biology", "Biochemical Journal",
            "FEBS Journal", "FEBS Letters"
        ],
        "tier_2_journals": [
            "Archives of Biochemistry and Biophysics", "Biochimica et Biophysica Acta"
        ],
        "avoid_keywords": [],
    },

    # ── Microbiology ──────────────────────────────────────────────────────────
    "microbiology": {
        "core_journals": [
            "mBio", "Nature Microbiology", "Cell Host and Microbe",
            "ISME Journal", "Microbiome", "PLOS Pathogens",
            "Infection and Immunity", "Applied and Environmental Microbiology"
        ],
        "tier_2_journals": [
            "Microbiology Spectrum", "Journal of Bacteriology",
            "Frontiers in Microbiology"
        ],
        "avoid_keywords": [],
    },
    "virology": {
        "core_journals": [
            "Cell Host and Microbe", "PLOS Pathogens", "Nature Microbiology",
            "Journal of Virology", "Viruses", "mBio", "Antiviral Research"
        ],
        "tier_2_journals": [
            "Virology", "Archives of Virology", "Virus Research"
        ],
        "avoid_keywords": [],
    },
    "microbiome": {
        "core_journals": [
            "Microbiome", "Cell Host and Microbe", "Nature Microbiology",
            "ISME Journal", "Gut Microbes", "mBio"
        ],
        "tier_2_journals": [
            "Applied and Environmental Microbiology", "Frontiers in Microbiology",
            "FEMS Microbiology Reviews"
        ],
        "avoid_keywords": [],
    },

    # ── Cardiovascular ────────────────────────────────────────────────────────
    "cardiovascular": {
        "core_journals": [
            "Circulation", "Circulation Research", "European Heart Journal",
            "JACC", "Cardiovascular Research", "Arteriosclerosis Thrombosis and Vascular Biology",
            "Journal of Clinical Investigation"
        ],
        "tier_2_journals": [
            "Basic Research in Cardiology", "Journal of Molecular and Cellular Cardiology",
            "Heart Rhythm"
        ],
        "avoid_keywords": [],
    },

    # ── Developmental Biology ─────────────────────────────────────────────────
    "developmental_biology": {
        "core_journals": [
            "Development", "Developmental Cell", "Genes and Development",
            "eLife", "Nature Cell Biology", "Current Biology", "Cell Reports"
        ],
        "tier_2_journals": [
            "Developmental Biology", "Mechanisms of Development",
            "Genesis"
        ],
        "avoid_keywords": [],
    },
    "stem_cells": {
        "core_journals": [
            "Cell Stem Cell", "Stem Cell Reports", "Stem Cells",
            "Cell", "Nature Cell Biology", "Developmental Cell"
        ],
        "tier_2_journals": [
            "Stem Cells and Development", "Cell Proliferation",
            "Journal of Cell Science"
        ],
        "avoid_keywords": [],
    },

    # ── Plant Biology ─────────────────────────────────────────────────────────
    "plant_biology": {
        "core_journals": [
            "Plant Cell", "Nature Plants", "Plant Physiology",
            "New Phytologist", "Molecular Plant", "Current Biology",
            "Plant Journal", "PNAS"
        ],
        "tier_2_journals": [
            "Plant and Cell Physiology", "Journal of Experimental Botany",
            "Frontiers in Plant Science"
        ],
        "avoid_keywords": [],
    },

    # ── Aging ─────────────────────────────────────────────────────────────────
    "aging": {
        "core_journals": [
            "Aging Cell", "Nature Aging", "Journals of Gerontology",
            "Ageing Research Reviews", "GeroScience",
            "Cell Metabolism", "Cell"
        ],
        "tier_2_journals": [
            "Mechanisms of Ageing and Development", "Experimental Gerontology",
            "Biogerontology"
        ],
        "avoid_keywords": [],
    },

    # ── Drug Discovery ────────────────────────────────────────────────────────
    "drug_discovery": {
        "core_journals": [
            "Nature Reviews Drug Discovery", "Drug Discovery Today",
            "Journal of Medicinal Chemistry", "ACS Chemical Biology",
            "Cell Chemical Biology", "European Journal of Medicinal Chemistry"
        ],
        "tier_2_journals": [
            "Bioorganic and Medicinal Chemistry", "Molecular Pharmaceutics",
            "Journal of Pharmacology and Experimental Therapeutics"
        ],
        "avoid_keywords": [],
    },
}

# ── TIER 1 CORE DISCIPLINE IDENTIFIERS ───────────────────────────────────────
# Keywords that strongly indicate the paper's CORE discipline (what the paper IS about)
# These should drive journal selection above all else
TIER1_DISCIPLINE_MARKERS = {
    "bioenergetics": ["bioenergetics", "mitochondrial respiration", "oxidative phosphorylation", "electron transport chain", "ATP synthesis", "proton motive force", "mitochondrial membrane potential", "respiratory chain", "Complex I", "Complex II", "Complex III", "Complex IV", "cytochrome c"],
    "mitochondria": ["mitochondria", "mitochondrial", "mitophagy", "mitochondrial dynamics", "mitochondrial fission", "mitochondrial fusion", "mitochondrial DNA", "mtDNA", "mitochondrial biogenesis", "PGC-1alpha", "TFAM", "Drp1", "Mfn1", "Mfn2", "OPA1"],
    "autophagy": ["autophagy", "autophagosome", "LC3", "Atg", "AMPK", "mTOR", "mTORC1", "ULK1", "Beclin-1", "p62", "SQSTM1", "autophagic flux", "macroautophagy", "selective autophagy"],
    "ferroptosis": ["ferroptosis", "lipid peroxidation", "GPX4", "iron-dependent", "ferrostatin", "liproxstatin", "System Xc-", "glutathione peroxidase 4", "phospholipid hydroperoxide"],
    "apoptosis": ["apoptosis", "apoptotic", "caspase", "Bcl-2", "Bax", "Bak", "cytochrome c release", "MOMP", "extrinsic apoptosis", "intrinsic apoptosis", "TRAIL", "Fas"],
    "oxidative_stress": ["oxidative stress", "reactive oxygen species", "ROS", "antioxidant", "superoxide", "hydrogen peroxide", "glutathione", "redox", "Nrf2", "SOD", "catalase", "thioredoxin"],
    "cell_signaling": ["signal transduction", "kinase", "phosphorylation", "receptor", "MAPK", "ERK", "JNK", "p38", "Akt", "PI3K", "NF-kB", "JAK-STAT", "Wnt", "Notch", "Hedgehog"],
    "metabolism": ["metabolic", "glycolysis", "fatty acid oxidation", "lipid metabolism", "glucose metabolism", "metabolomics", "TCA cycle", "Krebs cycle", "insulin signaling", "AMPK"],
    "epigenetics": ["epigenetic", "histone modification", "DNA methylation", "chromatin", "histone acetylation", "histone methylation", "CpG", "DNMT", "HDAC", "HAT", "PRC2", "H3K4me3", "H3K27me3"],
    "proteomics": ["proteomics", "mass spectrometry", "LC-MS/MS", "protein identification", "phosphoproteomics", "interactome", "protein-protein interaction", "co-immunoprecipitation"],
    "genomics": ["genomics", "whole genome sequencing", "GWAS", "genome-wide", "RNA-seq", "ChIP-seq", "ATAC-seq", "single-cell RNA-seq", "scRNA-seq", "transcriptomics"],
    "neurodegeneration": ["neurodegeneration", "neurodegenerative", "Alzheimer", "Parkinson", "ALS", "Huntington", "tau", "amyloid", "alpha-synuclein", "TDP-43", "neuronal death"],
    "clinical_neurology": ["neurological disorder", "neurological disease", "clinical neurology", "neurological symptoms", "neurological examination", "brain disorder", "nervous system disorder", "dementia", "epilepsy", "migraine", "neuropathy"],
    "autonomic_neurology": ["autonomic dysfunction", "autonomic nervous system", "autonomic failure", "dysautonomia", "orthostatic hypotension", "heart rate variability", "sympathetic", "parasympathetic", "vagal", "baroreceptor", "sudomotor", "cardiovascular autonomic"],
    "cerebrovascular": ["stroke", "cerebrovascular", "ischemic stroke", "hemorrhagic stroke", "cerebral ischemia", "brain infarction", "cerebral blood flow", "reperfusion injury", "thrombolysis", "thrombectomy", "transient ischemic attack", "TIA"],
    "multiple_sclerosis": ["multiple sclerosis", "MS", "demyelination", "demyelinating", "myelin", "oligodendrocyte", "relapsing-remitting", "progressive MS", "neuroimmunology", "EAE", "experimental autoimmune encephalomyelitis"],
    "immunology": ["immune", "T cell", "B cell", "macrophage", "dendritic cell", "cytokine", "inflammation", "adaptive immunity", "innate immunity", "antigen", "MHC", "TCR"],
    "cancer_biology": ["cancer", "tumor", "oncogene", "tumor suppressor", "metastasis", "carcinogenesis", "oncogenic", "malignant", "p53", "Ras", "EGFR", "HER2"],
    "structural_biology": ["crystal structure", "cryo-EM", "NMR structure", "protein structure", "X-ray crystallography", "structural determination", "molecular dynamics"],
    "microbiology": ["bacterial", "microbial", "pathogen", "infection", "host-pathogen", "biofilm", "antibiotic resistance", "virulence"],
    "cardiovascular": ["cardiac", "heart", "cardiovascular", "cardiomyocyte", "vascular", "atherosclerosis", "myocardial", "arrhythmia", "hypertension"],
    "developmental_biology": ["embryonic", "developmental", "morphogenesis", "cell fate", "differentiation", "organogenesis", "gastrulation", "patterning"],
    "stem_cells": ["stem cell", "pluripotent", "iPSC", "ESC", "self-renewal", "differentiation potential", "stemness", "reprogramming"],
    "aging": ["aging", "senescence", "lifespan", "longevity", "cellular senescence", "SASP", "telomere", "age-related"],
}

# ══════════════════════════════════════════════════════════════════════════════
# PHASE 1A & 2B: JOURNAL ACCEPTANCE PROFILES (Paper Type Hard Constraints)
# ══════════════════════════════════════════════════════════════════════════════
# These define HARD FILTERS - journals that don't accept a paper type are
# eliminated BEFORE any scoring begins. This is critical for review papers.

# Journals that ONLY publish invited/commissioned reviews - HARD REJECT for unsolicited reviews
INVITED_ONLY_REVIEW_JOURNALS = {
    # Nature Reviews family - overwhelmingly commission reviews
    "nature reviews cancer",
    "nature reviews immunology",
    "nature reviews drug discovery",
    "nature reviews molecular cell biology",
    "nature reviews neuroscience",
    "nature reviews genetics",
    "nature reviews microbiology",
    "nature reviews clinical oncology",
    "nature reviews cardiology",
    "nature reviews nephrology",
    "nature reviews gastroenterology & hepatology",
    "nature reviews endocrinology",
    "nature reviews rheumatology",
    "nature reviews urology",
    "nature reviews disease primers",
    "nature reviews chemistry",
    "nature reviews physics",
    "nature reviews materials",
    "nature reviews methods primers",
    # Annual Reviews - all commissioned
    "annual review of biochemistry",
    "annual review of cell and developmental biology",
    "annual review of genetics",
    "annual review of immunology",
    "annual review of medicine",
    "annual review of microbiology",
    "annual review of neuroscience",
    "annual review of pathology",
    "annual review of pharmacology and toxicology",
    "annual review of physiology",
    "annual review of plant biology",
    # Other invite-only review journals
    "physiological reviews",
    "pharmacological reviews",
    "microbiology and molecular biology reviews",
    "clinical microbiology reviews",
    "endocrine reviews",
    "nutrition reviews",
    "epidemiologic reviews",
    "psychological review",
    "chemical reviews",
}

# Journals that DON'T accept editorials/commentaries/letters (research only)
NO_EDITORIALS_JOURNALS = {
    "cell", "nature", "science", "cell metabolism", "nature metabolism",
    "molecular cell", "developmental cell", "cell stem cell", "embo journal",
    "journal of biological chemistry", "journal of cell biology", "elife",
    # These high-impact journals have strict formats
}

# Journals that ACCEPT editorials/commentaries/perspectives
ACCEPTS_EDITORIALS = {
    "lancet", "lancet neurology", "lancet oncology", "lancet psychiatry",
    "jama", "jama neurology", "jama oncology", "jama internal medicine",
    "new england journal of medicine", "bmj", "annals of internal medicine",
    "neurology", "brain", "annals of neurology", "stroke",
    "frontiers in neurology", "frontiers in immunology", "frontiers in oncology",
    "frontiers in medicine", "frontiers in cell and developmental biology",
    # Most Frontiers journals accept various formats
}

# Maximum word count for editorials/commentaries by journal type
EDITORIAL_WORD_LIMITS = {
    "jama_family": 1200,  # JAMA viewpoints
    "lancet_family": 800,  # Lancet correspondence
    "frontiers": 3000,  # Frontiers perspectives
    "default": 2000,
}

# Journals that primarily publish EXPERIMENTAL/PRIMARY research (reviews rare or never)
PRIMARY_RESEARCH_ONLY_JOURNALS = {
    # High-impact primary research journals
    "cell",
    "nature",
    "science",
    "nature medicine",
    "nature genetics",
    "nature immunology",
    "nature neuroscience",
    "nature cell biology",
    "nature chemical biology",
    "nature structural & molecular biology",
    "nature metabolism",
    "nature microbiology",
    "nature communications",  # Some reviews but primarily research
    # Cell Press research journals
    "molecular cell",
    "developmental cell",
    "cell stem cell",
    "cell host & microbe",
    "cell metabolism",
    "cell reports",
    "cell chemical biology",
    "current biology",
    # EMBO journals
    "embo journal",
    "embo reports",
    "embo molecular medicine",
    # JBC and related
    "journal of biological chemistry",
    "journal of cell biology",
    "journal of experimental medicine",
    # PNAS
    "proceedings of the national academy of sciences",
    "pnas",
    # eLife
    "elife",
    # Science journals
    "science advances",
    "science signaling",
    "science immunology",
    "science translational medicine",
}

# Journals that ACCEPT unsolicited reviews
ACCEPTS_UNSOLICITED_REVIEWS = {
    # Specialty review journals that accept submissions
    "autophagy",
    "cell death and differentiation",
    "cell death and disease",
    "free radical biology and medicine",
    "redox biology",
    "antioxidants and redox signaling",
    "biochimica et biophysica acta",
    "biochimica et biophysica acta - bioenergetics",
    "biochimica et biophysica acta - molecular cell research",
    "biochimica et biophysica acta - molecular basis of disease",
    "mitochondrion",
    "trends in biochemical sciences",
    "trends in cell biology",
    "trends in molecular medicine",
    "trends in immunology",
    "trends in neurosciences",
    "trends in microbiology",
    "trends in genetics",
    "current opinion in cell biology",
    "current opinion in chemical biology",
    "current opinion in genetics & development",
    "current opinion in immunology",
    "current opinion in microbiology",
    "current opinion in neurobiology",
    "seminars in cell & developmental biology",
    "seminars in cancer biology",
    "seminars in immunology",
    "progress in neurobiology",
    "progress in lipid research",
    "ageing research reviews",
    "neuroscience and biobehavioral reviews",
    "molecular aspects of medicine",
    "frontiers in immunology",
    "frontiers in cell and developmental biology",
    "frontiers in molecular biosciences",
    "frontiers in microbiology",
    "international journal of molecular sciences",
    "cells",
    "biomolecules",
}

# Paper type compatibility matrix
# Format: journal_pattern -> set of accepted paper types
JOURNAL_PAPER_TYPE_COMPATIBILITY = {
    # Journals that accept ALL types
    "plos one": {"experimental", "review", "meta_analysis", "case_report", "protocol"},
    "scientific reports": {"experimental", "review", "meta_analysis", "case_report", "protocol"},
    "frontiers in": {"experimental", "review", "meta_analysis", "protocol"},

    # Review-focused journals (accept reviews + some experimental)
    "trends in": {"review", "experimental"},
    "current opinion in": {"review"},
    "seminars in": {"review", "experimental"},
    "progress in": {"review"},
    "ageing research reviews": {"review", "meta_analysis"},

    # Methods/protocol journals
    "nature protocols": {"protocol"},
    "star protocols": {"protocol"},
    "jove": {"protocol"},
    "bio-protocol": {"protocol"},
    "methods in molecular biology": {"protocol"},
    "current protocols": {"protocol"},
    "nature methods": {"protocol", "experimental"},

    # Meta-analysis friendly
    "cochrane database": {"meta_analysis", "review"},
    "systematic reviews": {"meta_analysis", "review"},
}

# ══════════════════════════════════════════════════════════════════════════════
# PHASE 1D: CONTRIBUTION LEVEL CALIBRATION
# ══════════════════════════════════════════════════════════════════════════════
# Maps contribution level to appropriate journal impact factor ranges
CONTRIBUTION_TO_IF_RANGE = {
    "paradigm_shifting": (20, 100),   # Cell, Nature, Science
    "substantial_synthesis": (8, 25),  # Strong specialty journals
    "competent_summary": (3, 12),      # Mid-tier journals
    "incremental_update": (1, 6),      # Specialty/lower-tier journals
}

# ══════════════════════════════════════════════════════════════════════════════
# PHASE 3A: DISCIPLINE OVERLAP THRESHOLDS
# ══════════════════════════════════════════════════════════════════════════════
# Minimum percentage of tier1 keyword overlap required to consider a journal
MIN_DISCIPLINE_OVERLAP_THRESHOLD = 0.15  # 15% of journal's papers must match tier1 keywords

# Journals that are NEVER appropriate for certain fields (hard exclusions)
FIELD_JOURNAL_EXCLUSIONS = {
    "biomedical": ["environmental", "ecology", "geological", "earth science", "marine biology"],
    "biology": ["environmental", "geology", "earth science", "atmospheric"],
    "chemistry": ["environmental", "ecology"],
    "neuroscience": ["environmental", "ecology", "botanical"],
}

# ══════════════════════════════════════════════════════════════════════════════
# DISCIPLINE-SPECIFIC JOURNAL EXCLUSIONS
# For basic science papers, exclude clinical/applied journals from wrong fields
# These exclusions are applied when the paper's CORE discipline doesn't match
# ══════════════════════════════════════════════════════════════════════════════
DISCIPLINE_JOURNAL_EXCLUSIONS = {
    "bioenergetics": [
        "oncology", "cancer", "tumor", "carcinoma", "leukemia",  # Cancer journals
        "immunology", "immune", "inflammation", "allergy",  # Immunology journals
        "pharmacology", "drug", "therapeutic", "clinical trial",  # Pharmacology
        "neurology", "neurological", "brain disorder",  # Clinical neurology
        "translational", "clinical medicine",  # Translational/clinical
    ],
    "mitochondria": [
        "oncology", "cancer", "tumor",  # Cancer journals (unless cancer IS the focus)
        "immunology", "immune", "inflammation",  # Immunology journals
        "pharmacology", "drug", "therapeutic",  # Pharmacology journals
        "clinical trial", "translational medicine",  # Clinical journals
    ],
    "autophagy": [
        "immunology", "immune",  # Unless autophagy-immune IS the focus
        "pharmacology", "drug discovery",  # Unless targeting autophagy
        "oncology", "cancer",  # Unless cancer-autophagy IS the focus
    ],
    "oxidative_stress": [
        "immunology", "inflammation",  # Unless ROS-immune IS the focus
        "clinical trial", "patient cohort",  # Clinical journals
    ],
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

            # Extract lab profile if present (from context-aware endpoint)
            lab_profile = self._extract_lab_profile_from_text(text)
            if lab_profile.get("has_context"):
                print(f"[JournalScorer] Context-aware mode: found lab profile with {len(lab_profile.get('research_focus_areas', []))} focus areas")

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

            # Extract tiered keywords (new system) — critical for proper journal matching
            tier1_keywords = field_result.get("tier1_keywords", keywords[:6] if keywords else [])
            tier2_keywords = field_result.get("tier2_keywords", keywords[6:14] if len(keywords) > 6 else [])
            tier3_keywords = field_result.get("tier3_keywords", keywords[14:] if len(keywords) > 14 else [])
            core_discipline = field_result.get("core_discipline", "general")

            # Phase 1D: Contribution/Novelty Assessment for prestige calibration
            contribution_level = field_result.get("contribution_level", "competent_summary")
            target_if_range = field_result.get("target_if_range", (3, 12))

            yield _sse("field_detected", {
                "field": field,
                "field_label": field_config["label"],
                "confidence": field_result["confidence"],
                "subfield": field_result.get("subfield", core_discipline),
                "core_discipline": core_discipline,
                "tier1_keywords": tier1_keywords,
                "tier2_keywords": tier2_keywords,
                "tier3_keywords": tier3_keywords,
                "keywords": keywords,  # backward compatibility
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

            # ── Step 5.9: Pre-extract citation network for journal matching boost (Phase 3C) ──
            citation_journal_counts = {}
            try:
                yield _sse("progress", {"step": 5, "message": "Analyzing citation network...", "percent": 56})

                # Extract DOIs from text
                doi_pattern = r'10\.\d{4,}/[^\s\)\]\}]+'
                dois = list(set(re.findall(doi_pattern, text)))[:20]  # Dedupe and cap

                if dois:
                    # Count journals cited by the manuscript
                    citation_journal_counts = self._count_citation_journals(dois)
                    if citation_journal_counts:
                        print(f"[JournalScorer] Citation network: found {len(citation_journal_counts)} journals, top cited: {list(citation_journal_counts.items())[:3]}")
            except Exception as e:
                print(f"[JournalScorer] Citation network pre-extraction failed (non-critical): {e}")

            # ── Step 6: Match Journals (TIERED keyword-based via OpenAlex) ──
            yield _sse("progress", {"step": 6, "message": "Finding relevant journals by core discipline...", "percent": 58})

            journals = self._match_journals_by_keywords(
                tier1_keywords=tier1_keywords,
                tier2_keywords=tier2_keywords,
                tier3_keywords=tier3_keywords,
                core_discipline=core_discipline,
                field=field,
                tier=tier,
                paper_type=paper_type,
                paper_score=overall_score,
                contribution_level=contribution_level,
                target_if_range=target_if_range,
                citation_journal_counts=citation_journal_counts,
            )

            # ── Step 6.5: Context-Aware Analysis (if lab profile present) ──
            context_analysis_result = None
            if lab_profile.get("has_context"):
                try:
                    yield _sse("progress", {"step": 6, "message": "Analyzing manuscript against your lab profile...", "percent": 60})

                    # Boost journals from lab's publication history
                    journals = self._boost_journals_from_profile(journals, lab_profile)

                    # Generate context-aware insights
                    context_analysis_result = self._generate_context_analysis(
                        lab_profile=lab_profile,
                        manuscript_text=text,
                        field=field,
                        score=overall_score,
                        tier=tier
                    )

                    yield _sse("context_analysis", context_analysis_result)
                    print(f"[JournalScorer] Context analysis complete: profile match = {context_analysis_result.get('profile_match', {}).get('score', 'N/A')}")

                except Exception as e:
                    print(f"[JournalScorer] Context analysis failed (non-critical): {e}")
                    yield _sse("context_analysis", {"has_context": False, "error": str(e)})

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
                "context_aware": lab_profile.get("has_context", False),
                "lab_profile_confidence": lab_profile.get("confidence", 0) if lab_profile.get("has_context") else None,
            }
            if manuscript_url:
                done_data["manuscript_url"] = manuscript_url
            yield _sse("done", done_data)

        except Exception as e:
            import traceback
            traceback.print_exc()
            yield _sse("error", {"error": str(e)})

    # ── Private Methods ─────────────────────────────────────────────────────

    def _extract_lab_profile_from_text(self, text: str) -> dict:
        """Extract lab profile data if present in the text (from context-aware endpoint)."""
        profile = {}

        # Check for lab profile section
        if "=== LAB PROFILE ===" not in text:
            return profile

        try:
            # Extract the profile section
            start = text.find("=== LAB PROFILE ===")
            end = text.find("=== END LAB PROFILE ===")
            if start == -1 or end == -1:
                return profile

            profile_text = text[start:end]

            # Parse key fields
            lines = profile_text.split('\n')
            for line in lines:
                if "Research Focus Areas:" in line:
                    areas = line.split(":", 1)[1].strip()
                    profile["research_focus_areas"] = [a.strip() for a in areas.split(",")]
                elif "Common Methodologies:" in line:
                    methods = line.split(":", 1)[1].strip()
                    profile["methodologies"] = [m.strip() for m in methods.split(",")]
                elif "Preferred Journals:" in line:
                    journals = line.split(":", 1)[1].strip()
                    profile["preferred_journals"] = [j.strip() for j in journals.split(",") if j.strip()]
                elif "Typical Publication Tier:" in line:
                    tier_match = re.search(r'Tier\s*(\d+)', line)
                    if tier_match:
                        profile["typical_tier"] = int(tier_match.group(1))
                elif "Confidence in Profile:" in line:
                    conf_match = re.search(r'(\d+)%', line)
                    if conf_match:
                        profile["confidence"] = int(conf_match.group(1)) / 100

            profile["has_context"] = bool(profile.get("research_focus_areas") or profile.get("preferred_journals"))

        except Exception as e:
            print(f"[JournalScorer] Error parsing lab profile: {e}")

        return profile

    def _generate_context_analysis(self, lab_profile: dict, manuscript_text: str, field: str, score: int, tier: int) -> dict:
        """Generate explicit context-aware analysis comparing manuscript to lab profile."""
        if not lab_profile.get("has_context"):
            return {"has_context": False}

        # Use LLM to generate insights
        profile_summary = json.dumps(lab_profile, indent=2)

        prompt = f"""You are analyzing a manuscript in the context of a researcher's lab profile.

LAB PROFILE:
{profile_summary}

MANUSCRIPT FIELD: {field}
MANUSCRIPT SCORE: {score}/100 (Tier {tier})

MANUSCRIPT (first 3000 chars):
{manuscript_text[manuscript_text.find("=== MANUSCRIPT/RESEARCH TO ANALYZE ==="):][40:3000]}

Provide a context-aware analysis. Be specific and actionable.

Return JSON:
{{
    "profile_match": {{
        "score": 0-100,
        "assessment": "How well does this manuscript fit the lab's research profile?",
        "consistency": "Is this consistent with their usual work or a new direction?"
    }},
    "publication_strategy": {{
        "recommendation": "Based on their publication history, what tier should they target?",
        "rationale": "Why this recommendation based on their track record",
        "preferred_journal_fit": ["List any of their preferred journals that fit this manuscript"]
    }},
    "leveraging_history": [
        "Specific suggestion 1 based on their past work",
        "Specific suggestion 2 based on their expertise"
    ],
    "potential_concerns": [
        "Any concerns based on comparing this to their profile"
    ],
    "competitive_advantage": "What unique advantage does this lab have for this specific manuscript?"
}}"""

        try:
            response = self.openai.chat_completion(
                messages=[
                    {"role": "system", "content": "You are a publication strategist helping researchers leverage their lab's track record. Be specific and evidence-based."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1500,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content)
            result["has_context"] = True
            result["lab_profile_summary"] = {
                "focus_areas": lab_profile.get("research_focus_areas", []),
                "methodologies": lab_profile.get("methodologies", []),
                "preferred_journals": lab_profile.get("preferred_journals", []),
                "typical_tier": lab_profile.get("typical_tier"),
                "confidence": lab_profile.get("confidence", 0)
            }
            return result

        except Exception as e:
            print(f"[JournalScorer] Context analysis generation failed: {e}")
            return {
                "has_context": True,
                "error": str(e),
                "lab_profile_summary": lab_profile
            }

    def _boost_journals_from_profile(self, journals: dict, lab_profile: dict) -> dict:
        """Boost journals that appear in the lab's preferred journals list."""
        if not lab_profile.get("preferred_journals"):
            return journals

        preferred = [j.lower().strip() for j in lab_profile.get("preferred_journals", [])]

        for category in ["primary_matches", "stretch_matches", "safe_matches"]:
            for journal in journals.get(category, []):
                journal_name = journal.get("name", "").lower().strip()
                # Check if this journal is in their preferred list
                for pref in preferred:
                    if pref in journal_name or journal_name in pref:
                        journal["from_lab_history"] = True
                        journal["lab_history_note"] = "Previously published here"
                        # Add a boost to existing scores if present
                        if "composite_score" in journal:
                            journal["composite_score"] = min(100, journal["composite_score"] + 10)
                        break

        return journals

    def _detect_field(self, text_excerpt: str) -> dict:
        """
        Detect field and extract TIERED keywords from manuscript using INVERSE POSITION WEIGHTING.

        PHASE 1B: INVERSE POSITION WEIGHTING
        =====================================
        Different parts of a paper carry different signals about its true discipline:
        - INTRODUCTION/MOTIVATION (first 1-2 sentences): LOW weight — disease names, clinical relevance
        - CORE CONTENT (middle sentences 3-8): HIGH weight — actual mechanistic content
        - CONCLUSION (last 1-2 sentences): LOW weight — mirrors intro's broad framing

        TIERED KEYWORD HIERARCHY (critical for proper journal matching):
        - Tier 1: Core discipline terms — what the paper IS fundamentally about
                  (e.g., "bioenergetics", "mitochondrial respiration", "autophagy")
                  These DRIVE journal selection.
        - Tier 2: Substantial secondary terms — topics the paper discusses in depth
                  (e.g., specific techniques, pathways, molecules)
                  These REFINE journal selection.
        - Tier 3: Contextual terms — mentioned only as motivation/application
                  (e.g., "cancer" in a bioenergetics paper about mitochondria)
                  These should NOT drive journal selection.

        PHASE 1D: CONTRIBUTION ASSESSMENT
        ==================================
        Also assesses the paper's contribution level to calibrate journal ambition:
        - paradigm_shifting: Fundamentally new framework (Cell, Nature, Science)
        - substantial_synthesis: Meaningful novel synthesis (IF 8-25)
        - competent_summary: Solid summary of established area (IF 3-12)
        - incremental_update: Incremental addition to known topic (IF 1-6)
        """
        field_list = "\n".join(f"- {key}" for key in FIELD_CONFIGS.keys())

        # List available disciplines for the LLM to identify
        discipline_list = ", ".join(DISCIPLINE_JOURNAL_MAPPINGS.keys())

        prompt = (
            "You are an academic field classifier specializing in distinguishing what a paper IS about "
            "versus what it merely MENTIONS. This distinction is CRITICAL for journal matching.\n\n"
            "=== INVERSE POSITION WEIGHTING ===\n"
            "When analyzing the text, apply INVERSE weighting based on position:\n"
            "- FIRST 1-2 sentences: LOW weight (motivation/framing - often mentions diseases, broad impact)\n"
            "- MIDDLE sentences (3-8): HIGH weight (actual core content - the real discipline)\n"
            "- LAST 1-2 sentences: LOW weight (conclusions - often mirrors intro's broad claims)\n"
            "Keywords from the MIDDLE are what the paper IS about. Keywords from the EDGES are context.\n\n"
            "=== CRITICAL FIELD DISAMBIGUATION ===\n"
            "DO NOT confuse these:\n"
            "- Proteomics, mass spectrometry, LC-MS/MS, TMT labeling = BIOLOGY or BIOMEDICAL, NOT cs_data_science\n"
            "- Cancer cell lines, iron metabolism, FAC/DFO treatment = BIOLOGY or BIOMEDICAL\n"
            "- 'Data analysis' in context of lab experiments = BIOLOGY, NOT data science\n"
            "- Only classify as cs_data_science if it's ACTUALLY about algorithms, machine learning models, neural networks, computational methods AS THE CORE TOPIC\n"
            "- A paper analyzing proteomics DATA is still a biology paper, not a data science paper\n\n"
            f"FIELDS:\n{field_list}\n\n"
            f"KNOWN RESEARCH DISCIPLINES:\n{discipline_list}\n\n"
            "Respond ONLY in valid JSON with this structure:\n"
            "{\n"
            '  "field": "one of the fields above",\n'
            '  "confidence": 0.0-1.0,\n'
            '  "core_discipline": "the specific subdiscipline this paper IS about (e.g., bioenergetics, autophagy, neurodegeneration)",\n'
            '  "paper_type": "experimental|review|meta_analysis|case_report|protocol|computational|theoretical|editorial|commentary|letter|perspective",\n'
            '  "contribution_level": "paradigm_shifting|substantial_synthesis|competent_summary|incremental_update",\n'
            '  "tier1_keywords": ["5-8 CORE terms from MIDDLE of text that define what this paper IS fundamentally about"],\n'
            '  "tier2_keywords": ["8-12 SUBSTANTIAL terms the paper discusses in depth — techniques, pathways, molecules"],\n'
            '  "tier3_keywords": ["5-8 CONTEXTUAL terms from INTRO/CONCLUSION mentioned only as motivation — do NOT let these drive journal selection"],\n'
            '  "motivation_keywords": ["terms from first 1-2 sentences — these are CONTEXT, not core"],\n'
            '  "conclusion_keywords": ["terms from last 1-2 sentences — these are FRAMING, not core"],\n'
            '  "topical_fingerprint": {\n'
            '    "primary_domain": "the broad field (e.g., neurology, cell biology, biochemistry)",\n'
            '    "subfield": "specific subfield (e.g., autonomic neurology, mitochondrial biology, autophagy)",\n'
            '    "clinical_focus": ["list of clinical conditions discussed, if any (e.g., stroke, Parkinson, diabetes)"],\n'
            '    "methodology": ["methods/techniques used (e.g., Ewing battery, Western blot, meta-analysis, cohort study)"],\n'
            '    "population": "study population if applicable (e.g., acute stroke patients, elderly, mice)"\n'
            '  },\n'
            '  "reasoning": "one sentence explaining why you classified it this way"\n'
            "}\n\n"
            "=== PAPER TYPE CLASSIFICATION (CRITICAL) ===\n"
            "- editorial: Short (<2000 words), no methods/results, opinion piece, invited commentary on field state\n"
            "- commentary: Brief response to recent paper or debate, typically <1500 words\n"
            "- letter: Very short (<1000 words), response to published article or brief case report\n"
            "- perspective: Opinion/viewpoint article, longer than editorial, may propose new frameworks\n"
            "- review: Comprehensive literature survey (>4000 words), synthesizes existing research, has systematic search\n"
            "- meta_analysis: Statistical synthesis of multiple studies, has forest plots, PRISMA-style methods\n"
            "- experimental: Original research with methods, results, and novel data\n"
            "- case_report: Clinical case(s) with patient data, typically 1-5 patients\n"
            "- protocol: Describes methodology for future/ongoing study\n"
            "- computational: In-silico analysis, modeling, simulations\n"
            "- theoretical: Mathematical models, theoretical frameworks without experimental data\n\n"
            "IMPORTANT: Word count and structure are key signals:\n"
            "- <1500 words + no methods = editorial/commentary/letter\n"
            "- 1500-3000 words + opinion focus = perspective\n"
            "- >4000 words + literature synthesis = review\n"
            "- Has methods + results + data = experimental\n\n"
            "=== CONTRIBUTION LEVEL GUIDELINES ===\n"
            "- paradigm_shifting: Proposes fundamentally new framework or paradigm. Rare. Cell/Nature/Science level.\n"
            "- substantial_synthesis: Provides substantial novel synthesis connecting previously separate fields. Good specialty journals.\n"
            "- competent_summary: Competent summary of an established area. Mid-tier journals.\n"
            "- incremental_update: Incremental update to a known topic. Specialty/lower-tier journals.\n\n"
            "CRITICAL RULES FOR TIERED KEYWORDS:\n"
            "1. TIER 1 (Core — DRIVES journal selection):\n"
            "   - Extract from MIDDLE of the abstract (sentences 3-8)\n"
            "   - What is this paper fundamentally ABOUT? What would experts call it?\n"
            "   - If it's about mitochondrial bioenergetics, tier 1 = ['bioenergetics', 'mitochondria', 'oxidative phosphorylation']\n"
            "   - If it's about autophagy mechanisms, tier 1 = ['autophagy', 'LC3', 'autophagosome']\n"
            "   - These terms should match the paper's core identity, not its applications\n\n"
            "2. TIER 2 (Substantial — REFINES journal selection):\n"
            "   - Specific techniques used (e.g., 'LC-MS/MS', 'Western blot', 'CRISPR')\n"
            "   - Specific pathways studied (e.g., 'mTOR signaling', 'p53 pathway')\n"
            "   - Specific molecules/genes/proteins (e.g., 'GPX4', 'Drp1', 'cytochrome c')\n\n"
            "3. TIER 3 (Contextual — mentioned but NOT core to paper's identity):\n"
            "   - Disease names IF the paper is not primarily a disease study\n"
            "     (e.g., 'cancer' in a bioenergetics paper studying mitochondrial metabolism)\n"
            "   - Application areas mentioned only in introduction/discussion\n"
            "   - Organisms/models used (e.g., 'mouse', 'HeLa cells') — context, not core topic\n"
            "   - THESE MUST NOT DRIVE JOURNAL SELECTION\n\n"
            "EXAMPLE - Review about mitochondrial bioenergetics mentioning cancer applications:\n"
            "  core_discipline: 'bioenergetics'\n"
            "  contribution_level: 'substantial_synthesis'\n"
            "  tier1_keywords: ['bioenergetics', 'mitochondrial respiration', 'oxidative phosphorylation', 'ATP synthesis', 'mitophagy']\n"
            "  tier2_keywords: ['electron transport chain', 'Complex I', 'mtDNA', 'PGC-1alpha', 'mitochondrial dynamics']\n"
            "  tier3_keywords: ['cancer', 'neurodegeneration', 'cardiovascular disease']  # These are CONTEXT from intro!\n"
            "  motivation_keywords: ['cardiovascular disease', 'diabetes', 'aging']  # From intro - LOW weight\n"
            "  conclusion_keywords: ['therapeutic potential', 'clinical implications']  # From conclusion - LOW weight\n\n"
            f"MANUSCRIPT EXCERPT:\n{text_excerpt}"
        )

        resp = self.openai.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=1200,
        )
        raw = resp.choices[0].message.content.strip()
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if json_match:
            try:
                result = json.loads(json_match.group())
            except json.JSONDecodeError:
                return self._default_field_result("JSON parse error in field detection")

            # Validate the field is in our config
            if result.get("field") not in FIELD_CONFIGS:
                result["field"] = "biology"  # Better default than economics for science papers
                result["confidence"] = 0.5

            # Ensure all tiers exist
            if not result.get("tier1_keywords") or not isinstance(result["tier1_keywords"], list):
                result["tier1_keywords"] = [result.get("core_discipline", "general")]
            if not result.get("tier2_keywords") or not isinstance(result["tier2_keywords"], list):
                result["tier2_keywords"] = []
            if not result.get("tier3_keywords") or not isinstance(result["tier3_keywords"], list):
                result["tier3_keywords"] = []

            # Ensure contribution_level exists and is valid
            valid_contribution_levels = {"paradigm_shifting", "substantial_synthesis", "competent_summary", "incremental_update"}
            if result.get("contribution_level") not in valid_contribution_levels:
                result["contribution_level"] = "competent_summary"  # Safe default

            # Store motivation and conclusion keywords for debugging/transparency
            result["motivation_keywords"] = result.get("motivation_keywords", [])
            result["conclusion_keywords"] = result.get("conclusion_keywords", [])

            # Also populate legacy 'keywords' field for backward compatibility (all tiers combined)
            result["keywords"] = result["tier1_keywords"] + result["tier2_keywords"] + result["tier3_keywords"]

            # ALWAYS normalize core_discipline to match our discipline mapping keys
            # The LLM might output "autonomic dysfunction" but we need "autonomic_neurology"
            llm_discipline = result.get("core_discipline", "")
            result["core_discipline"] = self._normalize_discipline(llm_discipline, result["tier1_keywords"])

            # Get appropriate IF range based on contribution level
            contribution_level = result.get("contribution_level", "competent_summary")
            result["target_if_range"] = CONTRIBUTION_TO_IF_RANGE.get(contribution_level, (3, 12))

            print(f"[Journal] === PAPER DECOMPOSITION COMPLETE ===")
            print(f"  Core discipline: {result.get('core_discipline', 'unknown')}")
            print(f"  Contribution level: {contribution_level} → target IF: {result['target_if_range']}")
            print(f"  Tier 1 (core, HIGH weight): {result.get('tier1_keywords', [])[:5]}")
            print(f"  Tier 2 (substantial, MED weight): {result.get('tier2_keywords', [])[:5]}")
            print(f"  Tier 3 (contextual, LOW weight): {result.get('tier3_keywords', [])[:5]}")
            print(f"  Motivation keywords (IGNORE): {result.get('motivation_keywords', [])[:3]}")

            return result
        return self._default_field_result("Could not classify — defaulting")

    def _default_field_result(self, reason: str) -> dict:
        """Return a safe default field detection result."""
        return {
            "field": "biology",
            "confidence": 0.5,
            "core_discipline": "general",
            "paper_type": "experimental",
            "tier1_keywords": ["general"],
            "tier2_keywords": [],
            "tier3_keywords": [],
            "keywords": ["general"],
            "reasoning": reason,
        }

    def _normalize_discipline(self, llm_discipline: str, tier1_keywords: list) -> str:
        """Normalize LLM-provided discipline to match our DISCIPLINE_JOURNAL_MAPPINGS keys.

        The LLM might output "autonomic dysfunction" but we need "autonomic_neurology".
        This function first tries exact match, then fuzzy match, then falls back to inference.
        """
        if not llm_discipline:
            return self._infer_core_discipline(tier1_keywords)

        llm_lower = llm_discipline.lower().strip().replace(" ", "_").replace("-", "_")

        # Direct match
        if llm_lower in DISCIPLINE_JOURNAL_MAPPINGS:
            return llm_lower

        # Alias mapping: LLM output -> our key
        DISCIPLINE_ALIASES = {
            "autonomic_dysfunction": "autonomic_neurology",
            "autonomic_nervous_system": "autonomic_neurology",
            "dysautonomia": "autonomic_neurology",
            "stroke": "cerebrovascular",
            "cerebral_ischemia": "cerebrovascular",
            "ischemic_stroke": "cerebrovascular",
            "ms": "multiple_sclerosis",
            "demyelination": "multiple_sclerosis",
            "neurology": "clinical_neurology",
            "neurological": "clinical_neurology",
            "clinical_neurology": "clinical_neurology",
            "mitochondrial": "mitochondria",
            "mitochondrial_biology": "mitochondria",
            "oxidative_phosphorylation": "bioenergetics",
            "cellular_bioenergetics": "bioenergetics",
            "energy_metabolism": "bioenergetics",
            "cell_death": "apoptosis",
            "programmed_cell_death": "apoptosis",
            "iron_dependent_cell_death": "ferroptosis",
            "lipid_peroxidation": "ferroptosis",
            "ros": "oxidative_stress",
            "reactive_oxygen_species": "oxidative_stress",
            "redox": "oxidative_stress",
            "alzheimers": "neurodegeneration",
            "alzheimer": "neurodegeneration",
            "parkinsons": "neurodegeneration",
            "parkinson": "neurodegeneration",
            "dementia": "neurodegeneration",
            "als": "neurodegeneration",
            "huntingtons": "neurodegeneration",
        }

        if llm_lower in DISCIPLINE_ALIASES:
            return DISCIPLINE_ALIASES[llm_lower]

        # Try partial matching
        for alias, mapped in DISCIPLINE_ALIASES.items():
            if alias in llm_lower or llm_lower in alias:
                return mapped

        # Fall back to inference from keywords
        inferred = self._infer_core_discipline(tier1_keywords)
        if inferred != "general":
            return inferred

        # Last resort: check if LLM output contains any known discipline keyword
        for discipline in DISCIPLINE_JOURNAL_MAPPINGS.keys():
            if discipline.replace("_", " ") in llm_discipline.lower():
                return discipline

        return "general"

    def _infer_core_discipline(self, tier1_keywords: list) -> str:
        """Infer the core discipline from tier 1 keywords by matching against known discipline markers."""
        tier1_lower = [kw.lower() for kw in tier1_keywords]
        tier1_text = " ".join(tier1_lower)

        best_match = None
        best_score = 0

        for discipline, markers in TIER1_DISCIPLINE_MARKERS.items():
            score = 0
            for marker in markers:
                if marker.lower() in tier1_text:
                    score += 3  # Strong match
                for kw in tier1_lower:
                    if marker.lower() in kw or kw in marker.lower():
                        score += 1  # Partial match
            if score > best_score:
                best_score = score
                best_match = discipline

        return best_match if best_match and best_score >= 2 else "general"

    def _discover_safe_journals_dynamically(self, core_discipline: str, broad_field: str, tier1_keywords: list) -> list:
        """
        Dynamically discover lower-prestige safe journals for ANY discipline using OpenAlex.

        This ensures the system works for disciplines without hardcoded safe_journals lists.
        We query OpenAlex for journals in the same field with citedness < 3.0 (lower barrier).

        Args:
            core_discipline: The detected core discipline (e.g., "bioenergetics", "proteomics")
            broad_field: The broad academic field (e.g., "biology", "biomedical")
            tier1_keywords: Keywords from the paper to help find relevant journals

        Returns:
            List of journal names that are topically appropriate but lower-prestige
        """
        import requests as req

        safe_journals = []

        # Get OpenAlex concepts for this field
        field_config = FIELD_TO_OPENALEX_CONCEPTS.get(broad_field, {})
        concepts = field_config.get("concepts", [])

        if not concepts:
            print(f"[Journal] No OpenAlex concepts for field '{broad_field}', skipping dynamic safe journal discovery")
            return []

        # Build search query combining concepts with discipline keywords
        concept_filter = "|".join(concepts)

        # Use top tier1 keywords to narrow down relevance
        search_terms = tier1_keywords[:3] if tier1_keywords else [core_discipline]
        search_query = " ".join(search_terms)

        try:
            # Query OpenAlex for journals (sources) in this field
            # Filter for:
            # - Active journals (has recent works)
            # - Lower citedness (< 3.0 for safe tier)
            # - Type: journal (not repository, conference, etc.)
            search_url = (
                f"{OPENALEX_BASE}/sources"
                f"?filter=type:journal,concepts.id:{concept_filter}"
                f"&search={req.utils.quote(search_query)}"
                f"&sort=cited_by_count:desc"
                f"&per_page=50"
                f"&mailto={OPENALEX_EMAIL}"
            )

            print(f"[Journal] Dynamically discovering safe journals for '{core_discipline}' in '{broad_field}'...")

            response = req.get(search_url, timeout=15)
            if response.status_code != 200:
                print(f"[Journal] OpenAlex query failed: {response.status_code}")
                return []

            data = response.json()
            results = data.get("results", [])

            for src in results:
                name = src.get("display_name", "")
                summary = src.get("summary_stats", {})
                citedness = summary.get("2yr_mean_citedness", 0.0) or 0.0
                h_index = summary.get("h_index", 0) or 0
                works_count = src.get("works_count", 0) or 0

                # Safe journals: citedness < 3.0, but still legitimate (h_index > 10, works > 500)
                # This ensures they're real journals, just lower prestige
                if citedness < 3.0 and citedness > 0.3 and h_index > 10 and works_count > 500:
                    # Exclude mega-journals and clearly off-topic
                    name_lower = name.lower()
                    skip = any(excl in name_lower for excl in [
                        "plos one", "scientific reports", "frontiers in",
                        "nature communications", "proceedings of the national academy",
                        "lancet", "jama", "bmj", "new england journal"
                    ])
                    if not skip:
                        safe_journals.append(name)
                        if len(safe_journals) >= 6:  # Cap at 6 safe options
                            break

            if safe_journals:
                print(f"[Journal] Dynamically discovered {len(safe_journals)} safe journals: {safe_journals[:3]}...")
            else:
                print(f"[Journal] No safe journals found dynamically for '{core_discipline}'")

        except Exception as e:
            print(f"[Journal] Dynamic safe journal discovery failed: {e}")

        return safe_journals

    def _get_journal_name_variants(self, journal_name: str) -> list:
        """
        Dynamically get name variants for a journal from OpenAlex metadata.

        OpenAlex stores alternate names for journals which helps with matching.
        This is essential for journals like "BBA - Bioenergetics" which may appear
        under different names in different contexts.

        Args:
            journal_name: The canonical journal name

        Returns:
            List of alternate names for this journal
        """
        import requests as req

        variants = [journal_name]  # Always include the original

        try:
            search_url = (
                f"{OPENALEX_BASE}/sources"
                f"?search={req.utils.quote(journal_name)}"
                f"&per_page=1"
                f"&mailto={OPENALEX_EMAIL}"
            )

            response = req.get(search_url, timeout=10)
            if response.status_code != 200:
                return variants

            data = response.json()
            results = data.get("results", [])

            if results:
                src = results[0]
                # Get alternate names from OpenAlex
                alt_names = src.get("alternate_titles", [])
                abbrev_title = src.get("abbreviated_title")
                display_name = src.get("display_name", "")

                if abbrev_title and abbrev_title not in variants:
                    variants.append(abbrev_title)
                if display_name and display_name not in variants:
                    variants.append(display_name)
                for alt in alt_names:
                    if alt and alt not in variants:
                        variants.append(alt)

        except Exception as e:
            pass  # Silently fail - variants are optional

        return variants

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

    def _match_journals_by_keywords(
        self,
        tier1_keywords: list = None,
        tier2_keywords: list = None,
        tier3_keywords: list = None,
        core_discipline: str = None,
        field: str = None,
        tier: int = 2,
        paper_type: str = 'experimental',
        paper_score: int = 50,
        contribution_level: str = 'competent_summary',
        target_if_range: tuple = None,
        keywords: list = None,  # Legacy fallback
        citation_journal_counts: dict = None,  # Phase 3C: {journal_name: citation_count}
    ) -> dict:
        """
        TIERED KEYWORD journal discovery pipeline with HARD FILTERS.

        PHASE 3A: HARD FILTERS (applied BEFORE any scoring)
        ====================================================
        1. Paper Type Compatibility — eliminates journals that don't accept this paper type
           - Reviews to invited-only journals → HARD REJECT
           - Experimental papers to review-only journals → HARD REJECT
        2. Discipline Overlap Threshold — 15% of journal's papers must match tier1 keywords

        The key insight: A paper's CORE DISCIPLINE (Tier 1 keywords) should DRIVE journal selection,
        not peripheral disease mentions (Tier 3 keywords).

        KEYWORD WEIGHTING (Phase 3B):
        - Tier 1 (Core): 10x weight — what the paper IS fundamentally about (60% of score)
        - Tier 2 (Substantial): 3x weight — topics discussed in depth (30% of score)
        - Tier 3 (Contextual): 0.5x weight — mentioned as motivation (10% of score, should NOT drive selection)

        PRESTIGE AS TIEBREAKER (Phase 3D):
        - Impact factor/prestige is applied LAST, not first
        - Only used to rank among topically well-matched journals

        DISCIPLINE BOOST:
        - If core_discipline matches a known discipline in DISCIPLINE_JOURNAL_MAPPINGS,
          journals in that mapping get a significant boost.

        Pipeline:
        1) Search by Tier 1 keywords (HEAVILY weighted) → find core discipline authors
        2) Search by Tier 2 keywords (moderate weight) → refine author pool
        3) Apply discipline-specific journal boost from DISCIPLINE_JOURNAL_MAPPINGS
        4) Find where these authors publish → rank journals
        5) Filter out journals that ONLY match Tier 3 keywords
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

        # Handle legacy calls with just 'keywords' parameter
        if tier1_keywords is None and keywords:
            tier1_keywords = keywords[:6]
            tier2_keywords = keywords[6:14] if len(keywords) > 6 else []
            tier3_keywords = keywords[14:] if len(keywords) > 14 else []
        tier1_keywords = tier1_keywords or []
        tier2_keywords = tier2_keywords or []
        tier3_keywords = tier3_keywords or []
        core_discipline = core_discipline or "general"

        # Combine keywords for legacy compatibility
        all_keywords = tier1_keywords + tier2_keywords + tier3_keywords

        try:
            print(f"[Journal] === TIERED KEYWORD MATCHING ===")
            print(f"[Journal] Core discipline: {core_discipline}")
            print(f"[Journal] Tier 1 (CORE, 10x): {tier1_keywords[:5]}")
            print(f"[Journal] Tier 2 (Substantial, 3x): {tier2_keywords[:5]}")
            print(f"[Journal] Tier 3 (Contextual, 0.5x): {tier3_keywords[:5]}")

            # ── Get discipline-specific journal mappings ─────────────────────
            discipline_mapping = DISCIPLINE_JOURNAL_MAPPINGS.get(core_discipline, {})
            core_journals = discipline_mapping.get("core_journals", [])
            tier2_discipline_journals = discipline_mapping.get("tier_2_journals", [])
            avoid_keywords = discipline_mapping.get("avoid_keywords", [])

            if core_journals:
                print(f"[Journal] Discipline '{core_discipline}' maps to core journals: {core_journals[:5]}")
            else:
                # ══════════════════════════════════════════════════════════════
                # DYNAMIC CORE JOURNAL DISCOVERY for unmapped disciplines
                # ══════════════════════════════════════════════════════════════
                # If no hardcoded core_journals exist, we dynamically discover them
                # by querying OpenAlex for high-prestige journals in this field.
                # This ensures the system works for ANY discipline, not just mapped ones.
                print(f"[Journal] No hardcoded core_journals for '{core_discipline}', will rely on author search + dynamic discovery")

            # ── Step 1: Find authors using TIERED keyword approach ───────────
            tier1_author_ids = Counter()   # Authors from Tier 1 (core) search
            tier2_author_ids = Counter()   # Authors from Tier 2 (substantial) search
            tier3_author_ids = Counter()   # Authors from Tier 3 (contextual) - penalized

            # Use paper-type-aware filter from JOURNAL_TARGETS_BY_TYPE
            type_target = JOURNAL_TARGETS_BY_TYPE.get(paper_type, JOURNAL_TARGETS_BY_TYPE["experimental"])
            type_filter = type_target["filter"]

            # Get field-specific concepts
            field_config = FIELD_TO_OPENALEX_CONCEPTS.get(field, {})
            field_concepts = field_config.get("concepts", [])
            exclude_concepts = field_config.get("exclude_concepts", [])

            exclude_filter = ""
            if exclude_concepts:
                exclude_filter = "," + ",".join(f"concepts.id:!{c}" for c in exclude_concepts)

            concept_filter_clause = ""
            if field_concepts:
                concept_filter_clause = f",concepts.id:{('|'.join(field_concepts))}"

            # ── Step 1a: TIER 1 SEARCH (Core discipline) - 10x weight ─────────
            # This is THE MOST IMPORTANT search — defines what the paper IS about
            if tier1_keywords:
                tier1_queries = [
                    " ".join(tier1_keywords),  # All core terms together
                    " ".join(tier1_keywords[:4]),  # Top 4 core terms
                ]
                # Add individual important terms for precision
                for kw in tier1_keywords[:3]:
                    if len(kw) > 5:  # Skip very short terms
                        tier1_queries.append(kw)

                for query in tier1_queries[:5]:
                    url = (
                        f"{OPENALEX_BASE}/works"
                        f"?search={req.utils.quote(query)}"
                        f"&filter={type_filter},publication_year:2020-2026{concept_filter_clause}{exclude_filter}"
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
                        for authorship in work.get("authorships", [])[:5]:
                            author = authorship.get("author", {})
                            aid = author.get("id", "")
                            if aid:
                                tier1_author_ids[aid] += cited * 10  # 10x weight for CORE discipline

            print(f"[Journal] Tier 1 (core) search found {len(tier1_author_ids)} authors")

            # ── Step 1b: TIER 2 SEARCH (Substantial topics) - 3x weight ───────
            if tier2_keywords:
                tier2_queries = [
                    " ".join(tier2_keywords[:6]),
                    " ".join(tier2_keywords[:3]),
                ]

                for query in tier2_queries[:3]:
                    url = (
                        f"{OPENALEX_BASE}/works"
                        f"?search={req.utils.quote(query)}"
                        f"&filter={type_filter},publication_year:2020-2026{concept_filter_clause}{exclude_filter}"
                        f"&sort=cited_by_count:desc"
                        f"&per_page=30"
                        f"&select=id,authorships,cited_by_count"
                        f"&mailto={OPENALEX_EMAIL}"
                    )
                    data = _api_get(url)
                    if not data:
                        continue
                    for work in data.get("results", []):
                        cited = work.get("cited_by_count", 0)
                        for authorship in work.get("authorships", [])[:5]:
                            author = authorship.get("author", {})
                            aid = author.get("id", "")
                            if aid:
                                tier2_author_ids[aid] += cited * 3  # 3x weight for substantial topics

            print(f"[Journal] Tier 2 (substantial) search found {len(tier2_author_ids)} authors")

            # ── Step 1c: TIER 3 SEARCH (Contextual) - 0.5x weight (penalized) ─
            # IMPORTANT: Tier 3 keywords should NOT drive journal selection
            # We still search to understand the landscape, but heavily discount these
            if tier3_keywords:
                tier3_query = " ".join(tier3_keywords[:4])
                url = (
                    f"{OPENALEX_BASE}/works"
                    f"?search={req.utils.quote(tier3_query)}"
                    f"&filter={type_filter},publication_year:2020-2026"
                    f"&sort=cited_by_count:desc"
                    f"&per_page=20"
                    f"&select=id,authorships,cited_by_count"
                    f"&mailto={OPENALEX_EMAIL}"
                )
                data = _api_get(url)
                if data:
                    for work in data.get("results", []):
                        cited = work.get("cited_by_count", 0)
                        for authorship in work.get("authorships", [])[:3]:
                            author = authorship.get("author", {})
                            aid = author.get("id", "")
                            if aid:
                                tier3_author_ids[aid] += cited * 0.5  # 0.5x weight - minimal contribution

            print(f"[Journal] Tier 3 (contextual) search found {len(tier3_author_ids)} authors")

            # ── Combine authors with weighted tiers ──────────────────────────
            all_author_ids = Counter()
            all_author_ids.update(tier1_author_ids)  # Already weighted 10x
            all_author_ids.update(tier2_author_ids)  # Already weighted 3x
            all_author_ids.update(tier3_author_ids)  # Already weighted 0.5x

            if not all_author_ids:
                print(f"[Journal] No authors found, falling back to DB")
                return self._match_journals_from_db(field, tier, keywords=all_keywords, paper_type=paper_type)

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
                return self._match_journals_from_db(field, tier, keywords=all_keywords, paper_type=paper_type)

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
                return self._match_journals_from_db(field, tier, keywords=all_keywords, paper_type=paper_type)

            # ══════════════════════════════════════════════════════════════════
            # CRITICAL FIX: INJECT CORE DISCIPLINE JOURNALS DIRECTLY
            # ══════════════════════════════════════════════════════════════════
            # These specialty journals (Mitochondrion, Autophagy, Free Radical Biology
            # and Medicine, etc.) may not appear in the OpenAlex author-publication
            # search because:
            # 1. Authors who study bioenergetics ALSO publish in broad journals (Cancer, Immunology)
            # 2. The author search inherits ALL their publications, not topic-specific ones
            #
            # We MUST inject these journals directly to ensure they enter the candidate pool.
            # This is the fix for the "disease keyword trap" - ensuring specialty journals
            # appear even when authors publish broadly across many fields.
            # ══════════════════════════════════════════════════════════════════
            existing_names = {j["name"].lower() for j in enriched}
            injected_count = 0

            # Get safe journals for this discipline (hardcoded OR dynamically discovered)
            safe_journals_list = discipline_mapping.get("safe_journals", [])

            # ══════════════════════════════════════════════════════════════════
            # DYNAMIC SAFE JOURNAL DISCOVERY (works for ANY discipline)
            # ══════════════════════════════════════════════════════════════════
            # If no hardcoded safe_journals exist, dynamically discover them
            # This ensures the system works equally well for ALL disciplines,
            # not just the ones we've manually curated.
            if not safe_journals_list:
                print(f"[Journal] No hardcoded safe_journals for '{core_discipline}', discovering dynamically...")
                safe_journals_list = self._discover_safe_journals_dynamically(
                    core_discipline=core_discipline,
                    broad_field=field,
                    tier1_keywords=tier1_keywords
                )

            # Include core, tier2, AND safe journals for injection
            all_discipline_journals = (core_journals or []) + (tier2_discipline_journals or []) + safe_journals_list
            if all_discipline_journals:
                print(f"[Journal] Checking {len(all_discipline_journals)} discipline-specific journals for injection (including {len(safe_journals_list)} safe options)...")

                for journal_name in all_discipline_journals:
                    # Skip if already in pool
                    if any(journal_name.lower() in existing.lower() or existing.lower() in journal_name.lower()
                           for existing in existing_names):
                        continue

                    # Look up journal in OpenAlex by name
                    search_url = (
                        f"{OPENALEX_BASE}/sources"
                        f"?search={req.utils.quote(journal_name)}"
                        f"&per_page=1"
                        f"&mailto={OPENALEX_EMAIL}"
                    )
                    data = _api_get(search_url)
                    if not data or not data.get("results"):
                        print(f"[Journal] Could not find '{journal_name}' in OpenAlex")
                        continue

                    src = data["results"][0]
                    found_name = src.get("display_name", "").lower()

                    # Verify name matches reasonably (fuzzy match)
                    if not (journal_name.lower() in found_name or found_name in journal_name.lower()):
                        # Try partial match for complex names
                        name_words = set(journal_name.lower().split())
                        found_words = set(found_name.split())
                        overlap = len(name_words & found_words)
                        if overlap < 2:
                            print(f"[Journal] Name mismatch: searched '{journal_name}', found '{found_name}'")
                            continue

                    oa_id = src.get("id", "")
                    summary = src.get("summary_stats", {})
                    h_index = summary.get("h_index", 0) or 0
                    citedness = summary.get("2yr_mean_citedness", 0.0) or 0.0
                    works = src.get("works_count", 0) or 0

                    # Add to enriched list - DO NOT apply h_index/works filters for core journals
                    # These are specialty journals that may be smaller but are the RIGHT venue
                    enriched.append({
                        "name": src.get("display_name", journal_name),
                        "openalex_id": oa_id,
                        "h_index": h_index,
                        "citedness_2yr": round(citedness, 2),
                        "works_count": works,
                        "impact_factor": round(citedness, 1),
                        "sjr_quartile": None,
                        "composite_score": 0,
                        "homepage_url": src.get("homepage_url") or "",
                        "publisher": src.get("host_organization_name") or "",
                        "prof_papers": 0,
                        "injected_core_journal": True,  # Mark as directly injected
                    })
                    existing_names.add(found_name)
                    injected_count += 1
                    print(f"[Journal] ✓ INJECTED core journal: {src.get('display_name', journal_name)} (citedness={citedness:.1f})")

                print(f"[Journal] Injected {injected_count} discipline-specific journals into candidate pool")

            # ══════════════════════════════════════════════════════════════════
            # PHASE 3A: HARD FILTERS (applied BEFORE any scoring)
            # These eliminate journals that are categorically inappropriate
            # ══════════════════════════════════════════════════════════════════

            # Track anti-recommendations (journals that seem relevant but aren't)
            anti_recommendations = []

            # ── HARD FILTER 1: Paper Type Compatibility ───────────────────────
            # For REVIEW papers: eliminate invited-only review journals
            # This is THE MOST CRITICAL filter - Nature Reviews, Annual Reviews, etc.
            # overwhelmingly commission their reviews, you can't submit unsolicited
            if paper_type in ('review', 'meta_analysis'):
                paper_type_filtered = []
                for j in enriched:
                    name_lower = j["name"].lower()

                    # Check if journal is in invited-only list
                    is_invited_only = any(invited_j in name_lower for invited_j in INVITED_ONLY_REVIEW_JOURNALS)

                    if is_invited_only:
                        anti_recommendations.append({
                            "name": j["name"],
                            "reason": f"This journal only publishes INVITED/COMMISSIONED reviews. You cannot submit unsolicited reviews here.",
                            "filter_type": "paper_type_incompatibility",
                        })
                        print(f"[Journal] HARD FILTER (invited-only): '{j['name']}' rejected - only publishes commissioned reviews")
                    else:
                        paper_type_filtered.append(j)

                print(f"[Journal] After paper type filter: {len(paper_type_filtered)} journals remain ({len(enriched) - len(paper_type_filtered)} invited-only rejected)")
                enriched = paper_type_filtered

            # For EXPERIMENTAL papers: warn about review-only journals (soft filter)
            elif paper_type == 'experimental':
                paper_type_filtered = []
                for j in enriched:
                    name_lower = j["name"].lower()

                    # Check if journal primarily publishes reviews (Trends, Current Opinion, etc.)
                    is_review_focused = any(
                        pattern in name_lower
                        for pattern in ['trends in', 'current opinion', 'annual review', 'nature reviews', 'reviews in']
                    )

                    if is_review_focused:
                        anti_recommendations.append({
                            "name": j["name"],
                            "reason": f"This journal primarily publishes reviews, not primary research. Your experimental paper may not be appropriate here.",
                            "filter_type": "paper_type_mismatch",
                        })
                        print(f"[Journal] HARD FILTER (review-focused): '{j['name']}' rejected for experimental paper")
                    else:
                        paper_type_filtered.append(j)

                enriched = paper_type_filtered

            # For EDITORIALS/COMMENTARIES/LETTERS: filter journals that don't accept these
            elif paper_type in ('editorial', 'commentary', 'letter', 'perspective'):
                paper_type_filtered = []
                for j in enriched:
                    name_lower = j["name"].lower()

                    # Check if journal accepts editorials (clinical/general journals usually do)
                    is_no_editorials = any(no_ed in name_lower for no_ed in NO_EDITORIALS_JOURNALS)

                    # Also reject basic science journals for clinical editorials
                    is_basic_science = any(
                        pattern in name_lower
                        for pattern in ['journal of biological chemistry', 'embo', 'molecular cell',
                                       'developmental cell', 'cell reports', 'elife']
                    )

                    if is_no_editorials or is_basic_science:
                        anti_recommendations.append({
                            "name": j["name"],
                            "reason": f"This journal doesn't typically accept unsolicited editorials/commentaries. Target clinical or specialty journals that have viewpoint sections.",
                            "filter_type": "paper_type_incompatibility",
                        })
                        print(f"[Journal] HARD FILTER (no-editorials): '{j['name']}' rejected for editorial/commentary")
                    else:
                        paper_type_filtered.append(j)

                print(f"[Journal] After editorial filter: {len(paper_type_filtered)} journals remain")
                enriched = paper_type_filtered

            # ── HARD FILTER 2: Primary Research Only Journals ─────────────────
            # For REVIEW papers: eliminate journals that only publish primary research
            if paper_type in ('review', 'meta_analysis'):
                research_only_filtered = []
                for j in enriched:
                    name_lower = j["name"].lower()

                    # Check if journal is in primary-research-only list
                    is_research_only = any(rj in name_lower for rj in PRIMARY_RESEARCH_ONLY_JOURNALS)

                    if is_research_only:
                        anti_recommendations.append({
                            "name": j["name"],
                            "reason": f"This journal primarily publishes original research, not reviews. Consider submitting your review elsewhere.",
                            "filter_type": "paper_type_incompatibility",
                        })
                        print(f"[Journal] HARD FILTER (research-only): '{j['name']}' rejected - primarily publishes original research")
                    else:
                        research_only_filtered.append(j)

                print(f"[Journal] After research-only filter: {len(research_only_filtered)} remain")
                enriched = research_only_filtered

            # ── HARD FILTER 3: Contribution Level / IF Range ──────────────────
            # Apply prestige calibration based on contribution level
            # A "competent_summary" review shouldn't target Cell/Nature/Science
            if target_if_range:
                min_if, max_if = target_if_range
                prestige_filtered = []
                aspirational = []  # Keep a few aspirational options

                for j in enriched:
                    journal_if = j.get("citedness_2yr", 0) or j.get("impact_factor", 0) or 0

                    if journal_if > max_if * 2:  # Way above target range
                        anti_recommendations.append({
                            "name": j["name"],
                            "reason": f"Journal IF ({journal_if:.1f}) is significantly above your paper's target range ({min_if}-{max_if}). Based on contribution level '{contribution_level}', this would likely be a desk rejection.",
                            "filter_type": "prestige_mismatch",
                        })
                        # Keep top 2 as aspirational stretch goals
                        if len(aspirational) < 2:
                            aspirational.append(j)
                            j["is_aspirational"] = True
                        else:
                            print(f"[Journal] PRESTIGE FILTER: '{j['name']}' (IF={journal_if:.1f}) above target range ({min_if}-{max_if})")
                    else:
                        prestige_filtered.append(j)

                # Add aspirational journals back but mark them
                enriched = prestige_filtered + aspirational
                print(f"[Journal] After prestige filter: {len(prestige_filtered)} in range, {len(aspirational)} aspirational")

            if not enriched:
                print(f"[Journal] All journals filtered out, falling back")
                return self._match_journals_from_db(field, tier, keywords=all_keywords, paper_type=paper_type)

            # ══════════════════════════════════════════════════════════════════
            # END HARD FILTERS - Now apply soft scoring and boosting
            # ══════════════════════════════════════════════════════════════════

            # ── Step 4a: DISCIPLINE-BASED JOURNAL BOOSTING ───────────────────
            # This is the KEY NEW FEATURE: boost journals that are natural fits for the core discipline
            # A bioenergetics paper should get Mitochondrion, Autophagy, etc. boosted to the top

            # Get name variants from hardcoded mapping OR dynamically fetch them
            name_variants = discipline_mapping.get("name_variants", {})

            # Use the safe_journals_list we computed earlier (may be dynamic or hardcoded)
            # This ensures consistency between injection and boosting
            safe_journals = safe_journals_list  # Use the list from injection phase (may be dynamic)

            if core_journals or tier2_discipline_journals or safe_journals:
                print(f"[Journal] Applying discipline boost for '{core_discipline}'")

                # Build a list of all core journal names including variants
                # For hardcoded variants, use the mapping
                # For any core journal without variants, dynamically fetch them
                all_core_names = list(core_journals) if core_journals else []
                for canonical, variants in name_variants.items():
                    all_core_names.extend(variants)

                # Dynamically add variants for core journals not in the hardcoded mapping
                for core_j in (core_journals or []):
                    if core_j not in name_variants:
                        # Dynamically get variants from OpenAlex
                        dynamic_variants = self._get_journal_name_variants(core_j)
                        for v in dynamic_variants:
                            if v not in all_core_names:
                                all_core_names.append(v)

                for j in enriched:
                    name_lower = j["name"].lower()

                    # Check if journal matches core journals (including name variants)
                    core_match = any(
                        cj.lower() in name_lower or name_lower in cj.lower()
                        for cj in all_core_names
                    )
                    tier2_match = any(
                        t2j.lower() in name_lower or name_lower in t2j.lower()
                        for t2j in (tier2_discipline_journals or [])
                    )
                    safe_match = any(
                        sj.lower() in name_lower or name_lower in sj.lower()
                        for sj in safe_journals
                    )

                    if core_match:
                        j["discipline_boost"] = 100  # Massive boost for core discipline journals
                        j["discipline_match"] = "core"
                        print(f"[Journal] DISCIPLINE BOOST (core): '{j['name']}' matches '{core_discipline}' core journals")
                    elif tier2_match:
                        j["discipline_boost"] = 50   # Good boost for tier 2 discipline journals
                        j["discipline_match"] = "tier2"
                        print(f"[Journal] DISCIPLINE BOOST (tier2): '{j['name']}' matches '{core_discipline}' tier2 journals")
                    elif safe_match:
                        j["discipline_boost"] = 25   # Modest boost for safe discipline journals
                        j["discipline_match"] = "safe"
                        print(f"[Journal] DISCIPLINE BOOST (safe): '{j['name']}' matches '{core_discipline}' safe journals")
                    else:
                        j["discipline_boost"] = 0
                        j["discipline_match"] = None

            # ── Step 4a.4: CITATION NETWORK BOOST (Phase 3C) ─────────────────
            # Boost journals that appear frequently in the manuscript's references
            # This signals that the author already views these journals as relevant
            if citation_journal_counts:
                CITATION_BOOST_THRESHOLD = 3  # Must appear at least 3 times
                CITATION_BOOST_VALUE = 15     # +15 points for citation network match

                for j in enriched:
                    name_lower = j["name"].lower()
                    # Check for fuzzy match against citation journals
                    for cited_journal, count in citation_journal_counts.items():
                        cited_lower = cited_journal.lower()
                        if count >= CITATION_BOOST_THRESHOLD:
                            if cited_lower in name_lower or name_lower in cited_lower:
                                j["citation_boost"] = CITATION_BOOST_VALUE
                                j["citation_count"] = count
                                print(f"[Journal] CITATION BOOST: '{j['name']}' cited {count}x in references (+{CITATION_BOOST_VALUE})")
                                break
                    else:
                        j["citation_boost"] = 0
                        j["citation_count"] = 0

            # ── Step 4a.5: AVOID KEYWORD FILTERING ───────────────────────────
            # Remove journals that contain keywords we should avoid for this discipline
            if avoid_keywords:
                avoid_filtered = []
                for j in enriched:
                    name_lower = j["name"].lower()
                    avoided = False
                    for avoid_kw in avoid_keywords:
                        if avoid_kw.lower() in name_lower:
                            print(f"[Journal] DISCIPLINE AVOID: '{j['name']}' excluded (contains '{avoid_kw}' but discipline is '{core_discipline}')")
                            avoided = True
                            break
                    if not avoided:
                        avoid_filtered.append(j)
                enriched = avoid_filtered
                print(f"[Journal] After avoid keyword filtering: {len(enriched)} journals remain")

            # ── Step 4a.6: FIELD EXCLUSION - Remove journals from wrong fields ──
            field_exclusions = FIELD_JOURNAL_EXCLUSIONS.get(field, [])
            if field_exclusions:
                field_filtered = []
                for j in enriched:
                    name_lower = j["name"].lower()
                    excluded = False
                    for exc in field_exclusions:
                        if exc.lower() in name_lower:
                            print(f"[Journal] FIELD EXCLUSION: '{j['name']}' excluded (contains '{exc}' but field is '{field}')")
                            excluded = True
                            break
                    if not excluded:
                        field_filtered.append(j)
                enriched = field_filtered
                print(f"[Journal] After field exclusion: {len(enriched)} journals remain")

            # ── Step 4a.7: DISCIPLINE-SPECIFIC EXCLUSIONS ─────────────────────
            # For basic science papers (bioenergetics, mitochondria, autophagy),
            # exclude clinical/applied journals from unrelated fields.
            # This prevents cancer/immunology/pharmacology journals appearing for
            # a basic science review just because it mentions disease applications.
            discipline_exclusions = DISCIPLINE_JOURNAL_EXCLUSIONS.get(core_discipline, [])
            if discipline_exclusions:
                discipline_filtered = []
                for j in enriched:
                    name_lower = j["name"].lower()
                    # Skip exclusion check for core discipline journals (they're definitionally appropriate)
                    if j.get("discipline_boost", 0) >= 100 or j.get("injected_core_journal"):
                        discipline_filtered.append(j)
                        continue

                    excluded = False
                    for exc in discipline_exclusions:
                        if exc.lower() in name_lower:
                            anti_recommendations.append({
                                "name": j["name"],
                                "reason": f"This {exc}-focused journal is not appropriate for a {core_discipline} paper. Your paper mentions {exc} topics peripherally but is fundamentally about {core_discipline}.",
                                "filter_type": "discipline_mismatch",
                            })
                            print(f"[Journal] DISCIPLINE EXCLUSION: '{j['name']}' excluded (contains '{exc}' but core discipline is '{core_discipline}')")
                            excluded = True
                            break
                    if not excluded:
                        discipline_filtered.append(j)
                enriched = discipline_filtered
                print(f"[Journal] After discipline exclusion: {len(enriched)} journals remain")

            # ── Step 4b: Validate top journals against recent publications ──
            # Verify each journal actually publishes papers of this type
            # in this subject area (prevents subfield mismatches)
            #
            # CRITICAL FIX: Use ONLY tier1_keywords for validation
            # Using broader keywords (tier2) creates false positives because terms
            # like "ROS" or "oxidative stress" appear in hundreds of journals.
            # We need the CORE discipline terms to validate true fit.
            validated_enriched = []
            for j in enriched[:25]:  # Validate top 25 to keep API calls reasonable
                # Discipline-matched journals get automatic validation (they're definitionally appropriate)
                if j.get("discipline_boost", 0) >= 100 or j.get("injected_core_journal"):
                    j["validation"] = {
                        "validated": True,
                        "confidence": "high",
                        "reason": "Core discipline journal for this paper's topic",
                    }
                    validated_enriched.append(j)
                    continue

                validation = self._validate_journal_fit(
                    journal_name=j["name"],
                    journal_oa_id=j.get("openalex_id", ""),
                    paper_type=paper_type,
                    keywords=tier1_keywords[:6],  # Use ONLY top tier1 keywords (core discipline)
                    field=field,
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

            # Boost journals matching include keywords AND discipline + citation network
            for j in quality:
                name_lower = j["name"].lower()
                boost = sum(1 for kw in include_kws if kw.lower() in name_lower)
                demote = sum(1 for kw in exclude_kws if kw.lower() in name_lower)
                # Combine all boosts: discipline + citation network + paper type relevance
                j["type_relevance_boost"] = (
                    boost - demote +
                    j.get("discipline_boost", 0) +
                    j.get("citation_boost", 0)  # Phase 3C: Citation network boost
                )

            # Sort quality journals by DISCIPLINE BOOST FIRST, then citation network, then type relevance, then citedness
            # This ensures core discipline journals rise to the top, with citation network as secondary signal
            quality.sort(key=lambda j: (
                j.get("discipline_boost", 0),      # 1. Discipline match (most important!)
                j.get("citation_boost", 0),        # 2. Citation network match (Phase 3C)
                j.get("type_relevance_boost", 0),  # 3. Paper type match
                j.get("citedness_2yr", 0)          # 4. Quality indicator (prestige as tiebreaker per Phase 3D)
            ), reverse=True)

            # ══════════════════════════════════════════════════════════════════
            # FIT-FIRST TIER ASSIGNMENT (Phase 4A) - REVISED
            # ══════════════════════════════════════════════════════════════════
            # The correct tiering for academic journal recommendations:
            #
            # STRETCH = High fit + HIGH prestige (aspirational but appropriate)
            #   Example: Cell Metabolism for a bioenergetics review
            #   These are journals where the paper COULD be published if it's excellent
            #
            # PRIMARY = High fit + MODERATE prestige (realistic primary targets)
            #   Example: Autophagy, Redox Biology for a mitophagy review
            #   These are the natural homes for this paper
            #
            # SAFE = High fit + LOWER prestige (accessible fallbacks)
            #   Example: Cells, IJMS for broad molecular biology coverage
            #   These are backup options with lower acceptance barriers
            #
            # KEY INSIGHT: ALL tiers should be discipline-appropriate!
            # Non-matched journals should generally be EXCLUDED, not promoted.
            # ══════════════════════════════════════════════════════════════════

            # Split discipline-matched journals by prestige tier
            discipline_matched = [j for j in quality if j.get("discipline_boost", 0) > 0]
            non_matched = [j for j in quality if j.get("discipline_boost", 0) == 0]

            print(f"[Journal] Tier assignment: {len(discipline_matched)} discipline-matched, {len(non_matched)} non-matched")

            # ══════════════════════════════════════════════════════════════════
            # CONTENT-FIRST RANKING: Prioritize discipline match over metrics
            # ══════════════════════════════════════════════════════════════════
            #
            # Step 1: Group by CONTENT FIT (discipline_match quality)
            # Step 2: Within each group, sort by citedness as secondary factor
            # Step 3: Core matches go to PRIMARY (they're the best fit!)
            # Step 4: High-citedness within core = stretch (aspirational)
            # ══════════════════════════════════════════════════════════════════

            HIGH_PRESTIGE_THRESHOLD = 8.0    # Aspirational threshold

            # Group by discipline match quality (CONTENT FIRST)
            core_matches = []      # discipline_match == "core" -> BEST FIT
            tier2_matches = []     # discipline_match == "tier2" -> GOOD FIT
            weak_matches = []      # discipline_match == "safe" or None -> FALLBACK

            for j in discipline_matched:
                dm = j.get("discipline_match")
                if dm == "core":
                    core_matches.append(j)
                elif dm == "tier2":
                    tier2_matches.append(j)
                else:
                    weak_matches.append(j)

            # Sort within each group by citedness (secondary ranking factor)
            core_matches.sort(key=lambda j: j.get("citedness_2yr", 0), reverse=True)
            tier2_matches.sort(key=lambda j: j.get("citedness_2yr", 0), reverse=True)
            weak_matches.sort(key=lambda j: j.get("citedness_2yr", 0), reverse=True)

            print(f"[Journal] Content-first grouping: {len(core_matches)} core, {len(tier2_matches)} tier2, {len(weak_matches)} weak")

            # Stretch = ONLY high-citedness journals from core matches (aspirational)
            stretch_pool = [j for j in core_matches if j.get("citedness_2yr", 0) >= HIGH_PRESTIGE_THRESHOLD]

            # Primary = remaining core matches + tier2 matches (BEST FITS regardless of citedness)
            primary_pool = [j for j in core_matches if j.get("citedness_2yr", 0) < HIGH_PRESTIGE_THRESHOLD] + tier2_matches

            # Safe = weak matches only (journals with lower content fit)
            safe_pool = weak_matches

            print(f"[Journal] Pools: {len(stretch_pool)} stretch, {len(primary_pool)} primary, {len(safe_pool)} safe")

            # If stretch pool is empty, promote top primary journals
            if not stretch_pool and primary_pool:
                # Take top 2 from primary as aspirational
                stretch_pool = primary_pool[:2]
                primary_pool = primary_pool[2:]

            # If primary pool is small, fill from safe pool
            if len(primary_pool) < 5 and safe_pool:
                needed = 5 - len(primary_pool)
                primary_pool.extend(safe_pool[:needed])
                safe_pool = safe_pool[needed:]

            # Final tier assignment
            stretch = stretch_pool[:5]
            target = primary_pool[:10]

            # Safe = discipline-appropriate lower-prestige + mega-journals as last resort
            safe = safe_pool[:3]
            if len(safe) < 3:
                safe.extend(megas[:2])  # Add mega-journals only if needed

            # Add remaining non-matched only if we still need more (unlikely)
            all_used = set(j["name"].lower() for j in stretch + target + safe)
            if len(target) < 5:
                remaining_non_matched = [j for j in non_matched if j["name"].lower() not in all_used]
                remaining_non_matched.sort(key=lambda j: j.get("citedness_2yr", 0), reverse=True)
                target.extend(remaining_non_matched[:5 - len(target)])

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

            # Add quality-aware reasoning to each journal with discipline matching info
            score_label = "high-scoring" if paper_score >= 75 else "mid-range" if paper_score >= 50 else "developing"

            def _build_reason(j, base_reason: str) -> str:
                """Build journal reason with discipline and citation network match info.

                Phase 4B: Fit Justifications
                - Include WHY this journal fits based on discipline match
                - Include citation network evidence if applicable
                """
                parts = []

                # Discipline match indicator
                discipline_match = j.get("discipline_match")
                if discipline_match == "core":
                    parts.append(f"🎯 Core {core_discipline} journal")
                elif discipline_match == "tier2":
                    parts.append(f"✓ Natural fit for {core_discipline} research")

                # Citation network match indicator (Phase 3C)
                citation_count = j.get("citation_count", 0)
                if citation_count >= 3:
                    parts.append(f"📚 Cited {citation_count}x in your references")

                # Build prefix from parts
                if parts:
                    prefix = " — ".join(parts) + " — "
                else:
                    prefix = ""

                return prefix + base_reason

            for j in stretch:
                pp = j.get("prof_papers", 0)
                cite = j.get("citedness_2yr", 0)
                validation = j.get("validation", {})
                evidence = validation.get("evidence", "")
                base_reason = (
                    f"Top-cited researchers in your field publish here — "
                    f"{pp} recent papers by leading authors. "
                    f"Citedness ({cite}) is aspirational for a {score_label} manuscript."
                )
                j["reason"] = _build_reason(j, base_reason)
                if evidence:
                    j["reason"] += f" Verified: {evidence}"
                j["verified"] = validation.get("validated", False)
                j["core_discipline"] = core_discipline
                j["fit_tier"] = "stretch"  # Phase 4A: Explicit fit tier label

            for j in target:
                pp = j.get("prof_papers", 0)
                cite = j.get("citedness_2yr", 0)
                validation = j.get("validation", {})
                evidence = validation.get("evidence", "")
                base_reason = (
                    f"Frequently chosen by experts in your area — "
                    f"{pp} recent papers by top authors. "
                    f"Citedness of {cite} suggests a realistic match for your paper."
                )
                j["reason"] = _build_reason(j, base_reason)
                if evidence:
                    j["reason"] += f" Verified: {evidence}"
                j["verified"] = validation.get("validated", False)
                j["core_discipline"] = core_discipline
                j["fit_tier"] = "best_fit"  # Phase 4A: These are the primary recommended

            for j in safe:
                pp = j.get("prof_papers", 0)
                cite = j.get("citedness_2yr", 0)
                validation = j.get("validation", {})
                evidence = validation.get("evidence", "")
                if _is_mega(j["name"]):
                    base_reason = (
                        f"High-volume journal that publishes broadly. "
                        f"Good fallback with {pp} papers from authors in your area."
                    )
                else:
                    base_reason = (
                        f"Accessible venue where researchers in your area publish. "
                        f"Citedness {cite} with {pp} recent papers from top authors."
                    )
                j["reason"] = _build_reason(j, base_reason)
                if evidence:
                    j["reason"] += f" Verified: {evidence}"
                j["verified"] = validation.get("validated", False)
                j["core_discipline"] = core_discipline
                j["fit_tier"] = "safe"  # Phase 4A: Fallback/safe options

            return {
                "primary_matches": target,
                "stretch_matches": stretch,
                "safe_matches": safe[:5],
                # Phase 4C: Anti-recommendations (journals that SEEM relevant but aren't)
                "anti_recommendations": anti_recommendations[:5] if anti_recommendations else [],
                # Phase 1D/3D: Include contribution level for prestige calibration context
                "contribution_level": contribution_level,
                "target_if_range": target_if_range,
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[Journal] Tiered journal matching failed: {e}")
            return self._match_journals_from_db(field, tier, keywords=all_keywords, paper_type=paper_type)

    def _validate_journal_fit(self, journal_name: str, journal_oa_id: str,
                               paper_type: str, keywords: list, field: str = None) -> dict:
        """Validate that a journal actually publishes papers of this type in this area.

        Phase 5A: Table of Contents Validation Test
        ============================================
        1. Sample 5-10 recent papers from the journal's TOC
        2. Calculate keyword overlap with user's paper
        3. Flag if overlap < 25% threshold

        This prevents recommending journals that exist but don't publish in the
        user's specific subfield or paper type.
        """
        TOC_OVERLAP_THRESHOLD = 0.25  # 25% minimum keyword overlap required
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

        # ── Field exclusion check (quick, no API call) ──────────────────────
        if field:
            field_exclusions = FIELD_JOURNAL_EXCLUSIONS.get(field, [])
            name_lower = journal_name.lower()
            for exc in field_exclusions:
                if exc.lower() in name_lower:
                    return {
                        "validated": False,
                        "confidence": "high",
                        "reason": f"Journal '{journal_name}' is {exc}-focused but paper field is {field}",
                    }

        try:
            # ── Search for recent papers in this journal matching keywords + field ──
            kw_query = " ".join(keywords[:5]) if keywords else ""

            # Add field-specific keywords to search to ensure field relevance
            if field:
                field_config = FIELD_TO_OPENALEX_CONCEPTS.get(field, {})
                field_keywords = field_config.get("field_keywords", [])
                if field_keywords:
                    # Add top field keyword to search for better field specificity
                    kw_query = f"{kw_query} {field_keywords[0]}"

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
                    "keyword_overlap": 0.0,
                    "reason": f"No recent {paper_type} papers matching your keywords in {field or 'your field'} found in {journal_name}",
                }

            # ── Phase 5A: Calculate keyword overlap from TOC samples ──────────
            # CRITICAL FIX: More stringent validation to prevent false positives
            # The previous logic allowed validation if total >= 5 papers matched,
            # but those papers might only match on broad terms like "ROS".
            # We now require MULTIPLE core keywords to match in the TOC.
            keywords_lower = [kw.lower() for kw in keywords[:6]] if keywords else []
            matched_keywords = set()

            # Count papers that match MULTIPLE keywords (not just one)
            papers_with_strong_match = 0
            for paper in results[:10]:  # Sample up to 10 papers
                title = (paper.get("title") or "").lower()
                paper_matches = [kw for kw in keywords_lower if kw in title]
                for kw in paper_matches:
                    matched_keywords.add(kw)
                if len(paper_matches) >= 2:  # Require 2+ keywords per paper for "strong match"
                    papers_with_strong_match += 1

            keyword_overlap = len(matched_keywords) / len(keywords_lower) if keywords_lower else 0.0

            # More stringent validation criteria:
            # 1. At least 33% keyword overlap (was 25%)
            # 2. OR at least 3 papers with strong matches (2+ keywords each)
            # 3. Remove the "total >= 5 papers" escape hatch
            MIN_OVERLAP = 0.33  # 33% of keywords must match
            MIN_STRONG_MATCHES = 3  # Need 3+ papers with 2+ keyword matches

            if keyword_overlap < MIN_OVERLAP and papers_with_strong_match < MIN_STRONG_MATCHES:
                return {
                    "validated": False,
                    "confidence": "moderate",
                    "keyword_overlap": keyword_overlap,
                    "total_similar_papers": total,
                    "papers_with_strong_match": papers_with_strong_match,
                    "reason": f"Weak content alignment with {journal_name}: only {keyword_overlap:.0%} keyword overlap and {papers_with_strong_match} papers with strong matches. This journal may publish broadly on related topics but is not focused on your paper's core discipline.",
                    "matched_keywords": list(matched_keywords),
                }

            # Build evidence from top match
            top = results[0]
            return {
                "validated": True,
                "confidence": "high" if papers_with_strong_match >= 5 else "moderate",
                "keyword_overlap": keyword_overlap,
                "total_similar_papers": total,
                "papers_with_strong_match": papers_with_strong_match,
                "evidence": f"Published {total} similar papers (2022-2026), e.g. \"{top.get('title', '')}\" ({top.get('cited_by_count', 0)} citations)",
                "example_paper": {
                    "title": top.get("title", ""),
                    "year": top.get("publication_year"),
                    "citations": top.get("cited_by_count", 0),
                },
                "matched_keywords": list(matched_keywords),
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

    def _count_citation_journals(self, dois: list) -> dict:
        """Count which journals appear most frequently in the manuscript's references.

        Phase 3C: Citation Network Analysis
        - Extract DOIs from references section
        - Lookup in OpenAlex to find source journals
        - Returns dict of {journal_name: citation_count}

        Journals cited ≥3 times get a citation network boost in journal matching.
        """
        import requests as req
        OPENALEX_EMAIL = "prmogathala@gmail.com"
        HEADERS = {"User-Agent": f"2ndBrain/1.0 (mailto:{OPENALEX_EMAIL})", "Accept": "application/json"}

        journal_counts = {}

        for doi in dois[:20]:  # Cap at 20 DOIs for speed
            try:
                # Clean DOI
                doi = doi.strip().rstrip('.,;')
                if not doi.startswith('10.'):
                    continue

                # Look up this DOI in OpenAlex
                url = f"https://api.openalex.org/works/doi:{doi}?mailto={OPENALEX_EMAIL}"
                resp = req.get(url, headers=HEADERS, timeout=5)
                if resp.status_code != 200:
                    continue

                data = resp.json()
                source = data.get("primary_location", {}).get("source", {})
                journal_name = source.get("display_name", "")

                if journal_name and len(journal_name) > 2:
                    journal_counts[journal_name] = journal_counts.get(journal_name, 0) + 1
            except Exception:
                continue

        return journal_counts

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
