"""
Generate Training Data for HIJ ML Models
==========================================
Fetches real paper metadata from OpenAlex API and labels them for:
  1. Paper Type Classifier (5 classes: experimental, review, meta_analysis, case_report, protocol)
  2. Journal Tier Predictor (3 classes: Tier1, Tier2, Tier3)

Outputs JSONL files (train/val/test splits) to backend/data/oncology_training/

Usage:
    python -m scripts.generate_training_data
    python -m scripts.generate_training_data --target 5000 --output-dir data/oncology_training
    python -m scripts.generate_training_data --target 10000 --fields biomedical,cs_data_science

OpenAlex API is free, no key needed. Uses polite pool (mailto header) for faster rates.
"""

import argparse
import collections
import json
import logging
import os
import random
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OPENALEX_API = "https://api.openalex.org"
MAILTO = "prmogathala@gmail.com"
PER_PAGE = 200  # OpenAlex max per request
RATE_LIMIT_S = 0.11  # 100ms+ between requests (polite pool)
MIN_ABSTRACT_LENGTH = 80

TRAIN_RATIO = 0.80
VAL_RATIO = 0.10
TEST_RATIO = 0.10
RANDOM_SEED = 42

# Paper type classification: OpenAlex type -> our 5-class label
# OpenAlex "type" field values: article, review, book-chapter, editorial, letter, etc.
PAPER_TYPE_MAP = {
    "article": "experimental",
    "review": "review",
    "editorial": None,  # skip
    "letter": None,
    "book-chapter": None,
    "erratum": None,
    "paratext": None,
    "dataset": None,
    "preprint": "experimental",
}

# Concept-based overrides for meta_analysis, case_report, protocol
# These OpenAlex concept IDs help identify specific paper types
META_ANALYSIS_CONCEPTS = {
    "c183658997",  # Meta-analysis
    "c125863259",  # Systematic review (often co-occurs)
}

CASE_REPORT_CONCEPTS = {
    "c68597994",   # Case report
    "c126792064",  # Case study
}

PROTOCOL_CONCEPTS = {
    "c24667770",   # Protocol
    "c187412552",  # Clinical protocol
}

# Keywords in title/abstract that override type classification
META_ANALYSIS_KEYWORDS = [
    "meta-analysis", "meta analysis", "metaanalysis",
    "systematic review and meta", "pooled analysis",
    "forest plot", "random-effects model", "fixed-effects model",
]

CASE_REPORT_KEYWORDS = [
    "case report", "case presentation", "case study",
    "a rare case", "unusual case", "an unusual presentation",
]

PROTOCOL_KEYWORDS = [
    "study protocol", "trial protocol", "protocol for",
    "protocol paper", "protocol:",
]

# Journal tier assignment based on OpenAlex journal-level metrics
# We use cited_by_count percentile + h-index from the source (venue) data
TIER1_JOURNALS_LOWER = {
    # Nature family
    "nature", "nature medicine", "nature genetics", "nature reviews cancer",
    "nature biotechnology", "nature methods", "nature cell biology",
    "nature neuroscience", "nature communications",
    # Science family
    "science", "science translational medicine",
    # Cell family
    "cell", "cancer cell", "cell reports",
    # Lancet family
    "the lancet", "the lancet oncology", "lancet oncology",
    # NEJM / JAMA
    "the new england journal of medicine", "jama",
    "jama oncology", "jama internal medicine",
    # Top field journals
    "journal of clinical oncology", "annals of oncology",
    "journal of the national cancer institute",
    "cancer research", "clinical cancer research",
    "cancer discovery", "blood", "journal of clinical investigation",
    "circulation", "european heart journal",
    "annals of internal medicine", "the bmj", "bmj",
    "proceedings of the national academy of sciences",
    "nucleic acids research", "genome research",
    "physical review letters", "the astrophysical journal",
    "ieee transactions on pattern analysis and machine intelligence",
    "acm computing surveys",
    "annual review of biochemistry", "annual review of immunology",
    "chemical reviews", "angewandte chemie international edition",
    "journal of the american chemical society",
    "the american economic review", "quarterly journal of economics",
    "econometrica", "journal of political economy",
    "review of economic studies", "journal of finance",
    "american political science review", "american journal of political science",
    "psychological bulletin", "psychological review",
    "american sociological review",
    "cochrane database of systematic reviews",
}

TIER2_JOURNALS_LOWER = {
    "plos medicine", "elife", "embo journal",
    "cancer letters", "oncogene", "neoplasia",
    "molecular cancer", "breast cancer research",
    "lung cancer", "european journal of cancer",
    "international journal of cancer",
    "bmc medicine", "bmc cancer",
    "journal of experimental medicine",
    "journal of biological chemistry",
    "bioinformatics", "genome biology",
    "ieee transactions on medical imaging",
    "medical image analysis",
    "journal of machine learning research",
    "artificial intelligence",
    "journal of development economics",
    "journal of monetary economics",
    "journal of public economics",
    "journal of health economics",
    "health affairs",
    "systematic reviews",
    "research synthesis methods",
    "international journal of epidemiology",
    "american journal of epidemiology",
    "epidemiology",
    "journal of epidemiology and community health",
    "journal of clinical epidemiology",
}

# Academic fields and their OpenAlex concept filters for diverse data
FIELD_CONCEPTS = {
    "biomedical": {
        "concept_ids": ["C71924100", "C86803240", "C143998085"],  # Medicine, Biology, Oncology
        "description": "Biomedical sciences",
    },
    "cs_data_science": {
        "concept_ids": ["C41008148", "C154945302"],  # Computer Science, AI
        "description": "Computer Science / Data Science",
    },
    "economics": {
        "concept_ids": ["C162324750"],  # Economics
        "description": "Economics",
    },
    "psychology": {
        "concept_ids": ["C15744967"],  # Psychology
        "description": "Psychology",
    },
    "physics": {
        "concept_ids": ["C121332964"],  # Physics
        "description": "Physics",
    },
    "chemistry": {
        "concept_ids": ["C185592680"],  # Chemistry
        "description": "Chemistry",
    },
    "engineering": {
        "concept_ids": ["C127413603"],  # Engineering
        "description": "Engineering",
    },
    "environmental_science": {
        "concept_ids": ["C39432304"],  # Environmental Science
        "description": "Environmental Science",
    },
}


# ---------------------------------------------------------------------------
# HTTP session with retries
# ---------------------------------------------------------------------------

def create_session() -> requests.Session:
    session = requests.Session()
    retries = Retry(
        total=5,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({
        "User-Agent": f"2ndBrain/1.0 (mailto:{MAILTO})",
        "Accept": "application/json",
    })
    return session


# ---------------------------------------------------------------------------
# OpenAlex data fetching
# ---------------------------------------------------------------------------

def reconstruct_abstract(inverted_index: dict) -> str:
    """Reconstruct abstract from OpenAlex inverted index format."""
    if not inverted_index:
        return ""
    # Build (position, word) pairs
    word_positions = []
    for word, positions in inverted_index.items():
        for pos in positions:
            word_positions.append((pos, word))
    word_positions.sort(key=lambda x: x[0])
    return " ".join(w for _, w in word_positions)


def determine_paper_type(work: dict) -> Optional[str]:
    """Determine paper type from OpenAlex work metadata.

    Uses a combination of:
    1. OpenAlex type field
    2. Concept-based detection (meta-analysis, case report, protocol)
    3. Keyword-based detection in title
    """
    title = (work.get("title") or "").lower()
    oa_type = (work.get("type") or "article").lower()

    # Check title keywords first (highest confidence)
    for kw in META_ANALYSIS_KEYWORDS:
        if kw in title:
            return "meta_analysis"

    for kw in CASE_REPORT_KEYWORDS:
        if kw in title:
            return "case_report"

    for kw in PROTOCOL_KEYWORDS:
        if kw in title:
            return "protocol"

    # Check concepts
    concept_ids = set()
    for concept in work.get("concepts", []):
        cid = (concept.get("id") or "").lower().split("/")[-1]
        concept_ids.add(cid)

    if concept_ids & META_ANALYSIS_CONCEPTS:
        return "meta_analysis"
    if concept_ids & CASE_REPORT_CONCEPTS:
        return "case_report"
    if concept_ids & PROTOCOL_CONCEPTS:
        return "protocol"

    # Fall back to OpenAlex type mapping
    mapped = PAPER_TYPE_MAP.get(oa_type)
    return mapped


def determine_tier(work: dict) -> str:
    """Determine journal tier from source/venue data.

    Uses journal name matching + cited_by_count as a proxy.
    """
    # Get journal/source name
    source = work.get("primary_location", {}) or {}
    source_obj = source.get("source", {}) or {}
    journal_name = (source_obj.get("display_name") or "").lower().strip()

    if not journal_name:
        return "Tier3"

    # Direct name matching
    if journal_name in TIER1_JOURNALS_LOWER:
        return "Tier1"
    # Partial match for Tier1
    for t1 in TIER1_JOURNALS_LOWER:
        if t1 in journal_name or journal_name in t1:
            return "Tier1"

    if journal_name in TIER2_JOURNALS_LOWER:
        return "Tier2"
    for t2 in TIER2_JOURNALS_LOWER:
        if t2 in journal_name or journal_name in t2:
            return "Tier2"

    # Use cited_by_count as proxy for tier
    cited_by = work.get("cited_by_count", 0)
    if cited_by >= 200:
        # Highly cited papers tend to be in better journals
        return "Tier1"
    elif cited_by >= 50:
        return "Tier2"

    return "Tier3"


def extract_metadata(work: dict) -> Dict[str, Any]:
    """Extract metadata features needed for tier predictor training."""
    authorships = work.get("authorships", []) or []
    author_count = len(authorships)

    # Count unique institutions
    institutions = set()
    for auth in authorships:
        for inst in (auth.get("institutions") or []):
            iname = inst.get("display_name", "")
            if iname:
                institutions.add(iname.lower())
    institution_count = len(institutions)

    # Reference count
    ref_count = work.get("referenced_works_count", 0) or 0

    # Funding: heuristic from institution count + author count
    # Papers with many institutions and authors are more likely to have funding
    has_funding = (institution_count >= 2 and author_count >= 3)

    # Multicenter: heuristic based on institution count
    is_multicenter = institution_count >= 3

    # Journal name
    source = work.get("primary_location", {}) or {}
    source_obj = source.get("source", {}) or {}
    journal_name = source_obj.get("display_name", "")

    return {
        "author_count": author_count,
        "ref_count": ref_count,
        "has_funding": has_funding,
        "institution_count": institution_count,
        "is_multicenter": is_multicenter,
        "journal": journal_name,
        "year": work.get("publication_year"),
        "cited_by_count": work.get("cited_by_count", 0),
    }


def fetch_papers_for_type(
    session: requests.Session,
    concept_ids: List[str],
    work_type: str,
    target_count: int,
    extra_filter: str = "",
) -> List[Dict]:
    """Fetch papers of a specific type from OpenAlex.

    Args:
        session: requests session
        concept_ids: OpenAlex concept IDs to filter by
        work_type: OpenAlex work type filter (article, review, etc.)
        target_count: number of papers to fetch
        extra_filter: additional filter string
    """
    papers = []
    cursor = "*"

    # Build concept filter
    concept_filter = "|".join(concept_ids)
    base_filter = f"concepts.id:{concept_filter},type:{work_type},has_abstract:true"
    if extra_filter:
        base_filter += f",{extra_filter}"

    select_fields = ",".join([
        "id", "doi", "title", "type", "publication_year",
        "cited_by_count", "referenced_works_count",
        "primary_location", "authorships", "abstract_inverted_index",
        "concepts", "fwci",
    ])

    while len(papers) < target_count and cursor:
        params = {
            "filter": base_filter,
            "per_page": PER_PAGE,
            "cursor": cursor,
            "select": select_fields,
            "sort": "cited_by_count:desc",
            "mailto": MAILTO,
        }

        try:
            resp = session.get(f"{OPENALEX_API}/works", params=params, timeout=30)
            if resp.status_code == 429:
                logger.warning("Rate limited, waiting 5s...")
                time.sleep(5)
                continue
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.warning(f"API error: {e}, retrying in 3s...")
            time.sleep(3)
            continue

        results = data.get("results", [])
        if not results:
            break

        for work in results:
            abstract = reconstruct_abstract(work.get("abstract_inverted_index"))
            if len(abstract) < MIN_ABSTRACT_LENGTH:
                continue

            paper_type = determine_paper_type(work)
            if paper_type is None:
                continue

            tier = determine_tier(work)
            metadata = extract_metadata(work)

            record = {
                "title": work.get("title", ""),
                "abstract": abstract,
                "paper_type": paper_type,
                "tier": tier,
                **metadata,
            }
            papers.append(record)

            if len(papers) >= target_count:
                break

        # Get next cursor
        meta = data.get("meta", {})
        cursor = meta.get("next_cursor")

        time.sleep(RATE_LIMIT_S)

        if len(papers) % 500 == 0 and len(papers) > 0:
            logger.info(f"  Fetched {len(papers)}/{target_count} papers...")

    return papers


def fetch_papers_by_title_search(
    session: requests.Session,
    search_terms: List[str],
    target_count: int,
    expected_type: str,
) -> List[Dict]:
    """Fetch papers using title search for specific paper types.

    This is used for meta-analyses, case reports, and protocols
    which are harder to find via OpenAlex type filters alone.
    """
    papers = []

    select_fields = ",".join([
        "id", "doi", "title", "type", "publication_year",
        "cited_by_count", "referenced_works_count",
        "primary_location", "authorships", "abstract_inverted_index",
        "concepts", "fwci",
    ])

    per_term = max(target_count // len(search_terms) + 50, 100)

    for term in search_terms:
        cursor = "*"
        term_count = 0

        while term_count < per_term and cursor and len(papers) < target_count:
            params = {
                "filter": f"title.search:{term},has_abstract:true",
                "per_page": PER_PAGE,
                "cursor": cursor,
                "select": select_fields,
                "sort": "cited_by_count:desc",
                "mailto": MAILTO,
            }

            try:
                resp = session.get(f"{OPENALEX_API}/works", params=params, timeout=30)
                if resp.status_code == 429:
                    logger.warning("Rate limited, waiting 5s...")
                    time.sleep(5)
                    continue
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.warning(f"API error for term '{term}': {e}")
                time.sleep(3)
                break

            results = data.get("results", [])
            if not results:
                break

            for work in results:
                abstract = reconstruct_abstract(work.get("abstract_inverted_index"))
                if len(abstract) < MIN_ABSTRACT_LENGTH:
                    continue

                tier = determine_tier(work)
                metadata = extract_metadata(work)

                record = {
                    "title": work.get("title", ""),
                    "abstract": abstract,
                    "paper_type": expected_type,
                    "tier": tier,
                    **metadata,
                }
                papers.append(record)
                term_count += 1

                if len(papers) >= target_count:
                    break

            meta = data.get("meta", {})
            cursor = meta.get("next_cursor")
            time.sleep(RATE_LIMIT_S)

        if len(papers) >= target_count:
            break

    return papers


# ---------------------------------------------------------------------------
# Main data generation pipeline
# ---------------------------------------------------------------------------

def generate_training_data(
    output_dir: Path,
    target_total: int = 5000,
    fields: Optional[List[str]] = None,
) -> None:
    """Generate training data from OpenAlex.

    Strategy:
    - Fetch articles (-> experimental) from multiple academic fields
    - Fetch reviews from the same fields
    - Use title search for meta-analyses, case reports, protocols
    - Ensure class balance across paper types and tiers

    Target distribution:
    - experimental: ~40% of total
    - review: ~25% of total
    - meta_analysis: ~15% of total
    - case_report: ~12% of total
    - protocol: ~8% of total
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    session = create_session()

    if fields is None:
        fields = list(FIELD_CONCEPTS.keys())

    # Target counts per paper type
    target_experimental = int(target_total * 0.40)
    target_review = int(target_total * 0.25)
    target_meta = int(target_total * 0.15)
    target_case = int(target_total * 0.12)
    target_protocol = int(target_total * 0.08)

    all_papers = []

    # ── Fetch experimental papers (articles) ──────────────────────────
    logger.info("=" * 60)
    logger.info(f"Fetching ~{target_experimental} experimental papers...")
    logger.info("=" * 60)

    per_field = target_experimental // len(fields) + 20
    for field_name in fields:
        field_cfg = FIELD_CONCEPTS.get(field_name)
        if not field_cfg:
            logger.warning(f"Unknown field: {field_name}, skipping")
            continue

        logger.info(f"  Field: {field_cfg['description']} (target: {per_field})")
        papers = fetch_papers_for_type(
            session,
            concept_ids=field_cfg["concept_ids"],
            work_type="article",
            target_count=per_field,
            extra_filter="publication_year:2018-2026",
        )
        logger.info(f"  Got {len(papers)} experimental papers from {field_name}")
        all_papers.extend(papers)

    # ── Fetch review papers ───────────────────────────────────────────
    logger.info("=" * 60)
    logger.info(f"Fetching ~{target_review} review papers...")
    logger.info("=" * 60)

    per_field_review = target_review // len(fields) + 20
    for field_name in fields:
        field_cfg = FIELD_CONCEPTS.get(field_name)
        if not field_cfg:
            continue

        logger.info(f"  Field: {field_cfg['description']} (target: {per_field_review})")
        papers = fetch_papers_for_type(
            session,
            concept_ids=field_cfg["concept_ids"],
            work_type="review",
            target_count=per_field_review,
            extra_filter="publication_year:2018-2026",
        )
        # Ensure these are labeled as review
        for p in papers:
            p["paper_type"] = "review"
        logger.info(f"  Got {len(papers)} review papers from {field_name}")
        all_papers.extend(papers)

    # ── Fetch meta-analyses (title search) ────────────────────────────
    logger.info("=" * 60)
    logger.info(f"Fetching ~{target_meta} meta-analysis papers...")
    logger.info("=" * 60)

    meta_papers = fetch_papers_by_title_search(
        session,
        search_terms=[
            "meta-analysis", "meta analysis",
            "systematic review and meta-analysis",
            "pooled analysis",
        ],
        target_count=target_meta,
        expected_type="meta_analysis",
    )
    logger.info(f"  Got {len(meta_papers)} meta-analysis papers")
    all_papers.extend(meta_papers)

    # ── Fetch case reports (title search) ─────────────────────────────
    logger.info("=" * 60)
    logger.info(f"Fetching ~{target_case} case report papers...")
    logger.info("=" * 60)

    case_papers = fetch_papers_by_title_search(
        session,
        search_terms=[
            "case report", "case presentation",
            "a rare case of", "unusual case",
        ],
        target_count=target_case,
        expected_type="case_report",
    )
    logger.info(f"  Got {len(case_papers)} case report papers")
    all_papers.extend(case_papers)

    # ── Fetch protocol papers (title search) ──────────────────────────
    logger.info("=" * 60)
    logger.info(f"Fetching ~{target_protocol} protocol papers...")
    logger.info("=" * 60)

    protocol_papers = fetch_papers_by_title_search(
        session,
        search_terms=[
            "study protocol", "trial protocol",
            "protocol for a randomized", "protocol paper",
        ],
        target_count=target_protocol,
        expected_type="protocol",
    )
    logger.info(f"  Got {len(protocol_papers)} protocol papers")
    all_papers.extend(protocol_papers)

    # ── Deduplicate by title ──────────────────────────────────────────
    seen_titles = set()
    unique_papers = []
    for p in all_papers:
        title_key = (p.get("title") or "").lower().strip()
        if title_key and title_key not in seen_titles:
            seen_titles.add(title_key)
            unique_papers.append(p)
    logger.info(f"After deduplication: {len(unique_papers)} papers (was {len(all_papers)})")
    all_papers = unique_papers

    # ── Validate and clean ────────────────────────────────────────────
    valid_papers = []
    for p in all_papers:
        if not p.get("title") or not p.get("abstract"):
            continue
        if len(p["abstract"]) < MIN_ABSTRACT_LENGTH:
            continue
        if p.get("paper_type") not in ("experimental", "review", "meta_analysis", "case_report", "protocol"):
            continue
        if p.get("tier") not in ("Tier1", "Tier2", "Tier3"):
            continue
        valid_papers.append(p)

    logger.info(f"Valid papers after cleaning: {len(valid_papers)}")

    if not valid_papers:
        logger.error("No valid papers. Exiting.")
        sys.exit(1)

    # ── Stratified split by paper_type ────────────────────────────────
    random.seed(RANDOM_SEED)

    type_groups: Dict[str, List[dict]] = collections.defaultdict(list)
    for p in valid_papers:
        type_groups[p["paper_type"]].append(p)

    train_papers: List[dict] = []
    val_papers: List[dict] = []
    test_papers: List[dict] = []

    for ptype, group in type_groups.items():
        random.shuffle(group)
        n = len(group)
        n_train = int(n * TRAIN_RATIO)
        n_val = int(n * VAL_RATIO)
        train_papers.extend(group[:n_train])
        val_papers.extend(group[n_train:n_train + n_val])
        test_papers.extend(group[n_train + n_val:])

    random.shuffle(train_papers)
    random.shuffle(val_papers)
    random.shuffle(test_papers)

    logger.info(f"Split sizes: train={len(train_papers)}, val={len(val_papers)}, test={len(test_papers)}")

    # ── Write JSONL files ─────────────────────────────────────────────
    def write_jsonl(filepath: Path, data: List[dict]) -> None:
        with open(filepath, "w", encoding="utf-8") as f:
            for item in data:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

    write_jsonl(output_dir / "train.jsonl", train_papers)
    write_jsonl(output_dir / "val.jsonl", val_papers)
    write_jsonl(output_dir / "test.jsonl", test_papers)

    # ── Write label mappings ──────────────────────────────────────────
    paper_types = ["experimental", "review", "meta_analysis", "case_report", "protocol"]
    tiers = ["Tier1", "Tier2", "Tier3"]

    label_mappings = {
        "paper_type": {
            "classes": paper_types,
            "label2id": {label: idx for idx, label in enumerate(paper_types)},
            "id2label": {str(idx): label for idx, label in enumerate(paper_types)},
        },
        "tier": {
            "classes": tiers,
            "label2id": {label: idx for idx, label in enumerate(tiers)},
            "id2label": {str(idx): label for idx, label in enumerate(tiers)},
        },
    }
    with open(output_dir / "label_mappings.json", "w") as f:
        json.dump(label_mappings, f, indent=2)

    # ── Print statistics ──────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("TRAINING DATA STATISTICS")
    print("=" * 70)
    print(f"\nTotal papers: {len(valid_papers):,}")
    print(f"  Train: {len(train_papers):,} ({100 * len(train_papers) / len(valid_papers):.1f}%)")
    print(f"  Val:   {len(val_papers):,} ({100 * len(val_papers) / len(valid_papers):.1f}%)")
    print(f"  Test:  {len(test_papers):,} ({100 * len(test_papers) / len(valid_papers):.1f}%)")

    print("\n--- Paper Type Distribution ---")
    type_counts = collections.Counter(p["paper_type"] for p in valid_papers)
    for ptype in paper_types:
        count = type_counts.get(ptype, 0)
        print(f"  {ptype:20s}: {count:>6,} ({100 * count / len(valid_papers):5.1f}%)")

    print("\n--- Tier Distribution ---")
    tier_counts = collections.Counter(p["tier"] for p in valid_papers)
    for tier in tiers:
        count = tier_counts.get(tier, 0)
        print(f"  {tier:20s}: {count:>6,} ({100 * count / len(valid_papers):5.1f}%)")

    # Cross-tabulation
    print("\n--- Paper Type x Tier Cross-Tab ---")
    header = f"{'':20s}" + "".join(f"{t:>10s}" for t in tiers)
    print(header)
    for ptype in paper_types:
        row = f"{ptype:20s}"
        for tier in tiers:
            count = sum(1 for p in valid_papers if p["paper_type"] == ptype and p["tier"] == tier)
            row += f"{count:>10,}"
        print(row)

    # Abstract length stats
    lengths = sorted(len(p["abstract"]) for p in valid_papers)
    print(f"\n--- Abstract Length ---")
    print(f"  Min:    {lengths[0]:,} chars")
    print(f"  Median: {lengths[len(lengths) // 2]:,} chars")
    print(f"  Max:    {lengths[-1]:,} chars")

    print(f"\nOutput directory: {output_dir}")
    print("=" * 70 + "\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate HIJ ML training data from OpenAlex")
    parser.add_argument(
        "--output-dir", type=str,
        default="data/oncology_training",
        help="Output directory for JSONL files (default: data/oncology_training)",
    )
    parser.add_argument(
        "--target", type=int, default=5000,
        help="Target total number of papers (default: 5000)",
    )
    parser.add_argument(
        "--fields", type=str, default=None,
        help="Comma-separated fields to fetch from (default: all). "
             "Options: biomedical,cs_data_science,economics,psychology,physics,chemistry,engineering,environmental_science",
    )
    args = parser.parse_args()

    # Resolve output dir relative to backend/
    script_dir = Path(__file__).resolve().parent.parent
    output_dir = script_dir / args.output_dir

    fields = None
    if args.fields:
        fields = [f.strip() for f in args.fields.split(",")]

    logger.info(f"Generating training data: target={args.target}, output={output_dir}")
    if fields:
        logger.info(f"Fields: {fields}")

    generate_training_data(output_dir, target_total=args.target, fields=fields)


if __name__ == "__main__":
    main()
