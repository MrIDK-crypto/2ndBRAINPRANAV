"""
Process downloaded and enriched oncology paper JSONL files into training-ready splits.

Creates labelled train/val/test JSONL files with stratified splitting.

Usage:
    python -m backend.oncology_model.prepare_training_data \
        --input-dir /tmp/oncology_data_enriched/ \
        --output-dir /tmp/oncology_training/

If PubMed enrichment was skipped, can also read directly from OpenAlex JSONL:
    python -m backend.oncology_model.prepare_training_data \
        --input-dir /tmp/oncology_data/ \
        --output-dir /tmp/oncology_training/
"""

import argparse
import collections
import json
import logging
import os
import random
import sys
from pathlib import Path
from typing import Any, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MIN_ABSTRACT_LENGTH = 100
TRAIN_RATIO = 0.80
VAL_RATIO = 0.10
TEST_RATIO = 0.10
RANDOM_SEED = 42

SUB_FIELD_LABELS = [
    "breast", "lung", "colorectal", "prostate", "hematologic",
    "melanoma", "brain", "pancreatic", "ovarian", "head_neck",
    "liver", "kidney", "sarcoma", "pediatric", "general_oncology",
]

# Cancer-type keyword mapping (mirrors download_openalex.py but also uses PubMed MeSH)
CANCER_TYPE_KEYWORDS: dict[str, list[str]] = {
    "breast": ["breast cancer", "breast neoplasm", "breast carcinoma", "mammary", "breast neoplasms"],
    "lung": ["lung cancer", "lung neoplasm", "lung carcinoma", "non-small cell lung",
             "small cell lung", "nsclc", "sclc", "pulmonary neoplasm", "lung neoplasms"],
    "colorectal": ["colorectal cancer", "colorectal neoplasm", "colon cancer", "rectal cancer",
                   "colorectal carcinoma", "colorectal neoplasms", "colonic neoplasms"],
    "prostate": ["prostate cancer", "prostate neoplasm", "prostate carcinoma", "prostatic",
                 "prostatic neoplasms"],
    "hematologic": ["leukemia", "lymphoma", "myeloma", "hematologic", "haematologic",
                    "blood cancer", "hodgkin", "non-hodgkin", "multiple myeloma",
                    "hematologic neoplasms"],
    "melanoma": ["melanoma", "skin cancer", "cutaneous melanoma", "skin neoplasms"],
    "brain": ["glioma", "glioblastoma", "brain cancer", "brain tumor", "brain tumour",
              "brain neoplasm", "meningioma", "astrocytoma", "medulloblastoma",
              "neuroblastoma", "brain neoplasms", "central nervous system neoplasms"],
    "pancreatic": ["pancreatic cancer", "pancreatic neoplasm", "pancreatic carcinoma",
                   "pancreatic ductal", "pancreatic neoplasms"],
    "ovarian": ["ovarian cancer", "ovarian neoplasm", "ovarian carcinoma", "ovarian neoplasms"],
    "head_neck": ["head and neck cancer", "head and neck neoplasm", "head neck",
                  "oral cancer", "nasopharyngeal", "pharyngeal cancer", "laryngeal cancer",
                  "thyroid cancer", "head and neck neoplasms", "thyroid neoplasms"],
    "liver": ["liver cancer", "hepatocellular carcinoma", "hepatocellular",
              "hepatoblastoma", "liver neoplasm", "hepatic cancer", "liver neoplasms",
              "carcinoma, hepatocellular"],
    "kidney": ["kidney cancer", "renal cell carcinoma", "renal cancer", "renal neoplasm",
               "kidney neoplasm", "nephroblastoma", "wilms", "kidney neoplasms"],
    "sarcoma": ["sarcoma", "osteosarcoma", "ewing", "rhabdomyosarcoma",
                "liposarcoma", "leiomyosarcoma"],
    "pediatric": ["pediatric oncology", "pediatric cancer", "childhood cancer",
                  "childhood leukemia", "retinoblastoma"],
}

# Paper type mapping from OpenAlex type + PubMed publication types
PAPER_TYPE_MAP: dict[str, str] = {
    # OpenAlex types
    "article": "research_article",
    "review": "review",
    "letter": "letter",
    "editorial": "editorial",
    "erratum": "erratum",
    "book-chapter": "book_chapter",
    "dataset": "dataset",
    "preprint": "preprint",
    "paratext": "other",
    # PubMed publication types (common ones)
    "randomized controlled trial": "rct",
    "clinical trial": "clinical_trial",
    "clinical trial, phase i": "clinical_trial",
    "clinical trial, phase ii": "clinical_trial",
    "clinical trial, phase iii": "clinical_trial",
    "clinical trial, phase iv": "clinical_trial",
    "meta-analysis": "meta_analysis",
    "systematic review": "systematic_review",
    "case reports": "case_report",
    "observational study": "observational_study",
    "comparative study": "comparative_study",
    "multicenter study": "multicenter_study",
    "practice guideline": "guideline",
    "guideline": "guideline",
    "comment": "comment",
    "review": "review",
    "journal article": "research_article",
    "research support, n.i.h., extramural": None,  # skip funding labels
    "research support, non-u.s. gov't": None,
    "research support, u.s. gov't, p.h.s.": None,
    "research support, u.s. gov't, non-p.h.s.": None,
}


# ---------------------------------------------------------------------------
# Journal tier lookup
# ---------------------------------------------------------------------------

def load_journal_tiers(script_dir: Path) -> dict[str, int]:
    """Load journal_tiers.json and build a name->tier lookup (including aliases)."""
    tiers_path = script_dir / "journal_tiers.json"
    if not tiers_path.exists():
        logger.warning("journal_tiers.json not found at %s — all journals will be tier 3", tiers_path)
        return {}

    with open(tiers_path, "r") as f:
        data = json.load(f)

    lookup: dict[str, int] = {}
    for entry in data.get("journals", []):
        tier = entry["tier"]
        # Normalize: lowercase for matching
        name_lower = entry["name"].lower().strip()
        lookup[name_lower] = tier
        for alias in entry.get("aliases", []):
            lookup[alias.lower().strip()] = tier

    return lookup


def get_journal_tier(journal_name: Optional[str], tier_lookup: dict[str, int]) -> int:
    """Return tier (1, 2, or 3) for a journal name."""
    if not journal_name or not tier_lookup:
        return 3
    normalized = journal_name.lower().strip()
    if normalized in tier_lookup:
        return tier_lookup[normalized]
    # Fuzzy: check if any key is a substring of the journal name or vice versa
    for key, tier in tier_lookup.items():
        if key in normalized or normalized in key:
            return tier
    return 3


# ---------------------------------------------------------------------------
# Label extraction
# ---------------------------------------------------------------------------

def extract_sub_field(paper: dict) -> str:
    """Determine cancer sub-field from concepts, MeSH, and PubMed MeSH."""
    names_lower: list[str] = []

    # OpenAlex concepts
    for c in paper.get("concepts", []):
        name = (c.get("name") or "").lower()
        if name:
            names_lower.append(name)

    # OpenAlex MeSH
    for m in paper.get("mesh_terms", []):
        name = (m.get("descriptor_name") or "").lower()
        if name:
            names_lower.append(name)

    # PubMed MeSH (enriched)
    for m in paper.get("pubmed_mesh_terms", []):
        name = (m.get("descriptor") or "").lower()
        if name:
            names_lower.append(name)
        for q in m.get("qualifiers", []):
            qname = (q.get("name") or "").lower()
            if qname:
                names_lower.append(qname)

    # Also check title
    title = (paper.get("title") or "").lower()
    names_lower.append(title)

    joined = " | ".join(names_lower)

    for cancer_type, keywords in CANCER_TYPE_KEYWORDS.items():
        for kw in keywords:
            if kw in joined:
                return cancer_type

    return "general_oncology"


def extract_paper_type(paper: dict) -> str:
    """Determine paper type from OpenAlex type and PubMed publication types.

    PubMed types take priority for specific categories (RCT, clinical trial, etc.).
    """
    # Check PubMed publication types first (more specific)
    pubmed_types = paper.get("pubmed_publication_types", [])
    best_type = None

    # Priority order: RCT > clinical_trial > meta_analysis > systematic_review >
    # guideline > case_report > observational > review > research_article
    priority = {
        "rct": 10,
        "clinical_trial": 9,
        "meta_analysis": 8,
        "systematic_review": 7,
        "guideline": 6,
        "case_report": 5,
        "observational_study": 4,
        "comparative_study": 3,
        "multicenter_study": 2,
    }

    for pt in pubmed_types:
        mapped = PAPER_TYPE_MAP.get(pt.lower().strip())
        if mapped is None:
            continue
        if best_type is None or priority.get(mapped, 0) > priority.get(best_type, 0):
            best_type = mapped

    if best_type:
        return best_type

    # Fall back to OpenAlex type
    oa_type = (paper.get("type") or "article").lower().strip()
    return PAPER_TYPE_MAP.get(oa_type, "other")


# ---------------------------------------------------------------------------
# Main processing pipeline
# ---------------------------------------------------------------------------

def process_papers(input_dir: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load journal tier lookup
    script_dir = Path(__file__).parent
    tier_lookup = load_journal_tiers(script_dir)
    logger.info("Loaded %d journal name -> tier mappings", len(tier_lookup))

    # Find input files
    input_files = sorted(input_dir.glob("oncology_papers_*.jsonl"))
    if not input_files:
        logger.error("No oncology_papers_*.jsonl files found in %s", input_dir)
        sys.exit(1)
    logger.info("Found %d input files", len(input_files))

    # Process all papers
    papers: list[dict[str, Any]] = []
    total_read = 0
    skipped_short_abstract = 0

    for input_file in input_files:
        with open(input_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                total_read += 1
                try:
                    paper = json.loads(line)
                except json.JSONDecodeError:
                    continue

                # Filter: abstract must be >= MIN_ABSTRACT_LENGTH chars
                abstract = paper.get("abstract", "")
                if not abstract or len(abstract) < MIN_ABSTRACT_LENGTH:
                    skipped_short_abstract += 1
                    continue

                # Add labels
                paper["sub_field_label"] = extract_sub_field(paper)
                paper["tier_label"] = get_journal_tier(paper.get("journal_name"), tier_lookup)
                paper["paper_type_label"] = extract_paper_type(paper)

                papers.append(paper)

        if total_read % 100_000 == 0:
            logger.info("  Read %d papers so far, %d passed filters", total_read, len(papers))

    logger.info(
        "Total read: %d | Passed filters: %d | Skipped (short abstract): %d",
        total_read, len(papers), skipped_short_abstract,
    )

    if not papers:
        logger.error("No papers passed filters. Exiting.")
        sys.exit(1)

    # ---------------------------------------------------------------------------
    # Stratified split by sub_field_label
    # ---------------------------------------------------------------------------
    random.seed(RANDOM_SEED)

    # Group papers by sub_field_label
    label_groups: dict[str, list[dict]] = collections.defaultdict(list)
    for p in papers:
        label_groups[p["sub_field_label"]].append(p)

    train_papers: list[dict] = []
    val_papers: list[dict] = []
    test_papers: list[dict] = []

    for label, group in label_groups.items():
        random.shuffle(group)
        n = len(group)
        n_train = int(n * TRAIN_RATIO)
        n_val = int(n * VAL_RATIO)
        # Rest goes to test
        train_papers.extend(group[:n_train])
        val_papers.extend(group[n_train:n_train + n_val])
        test_papers.extend(group[n_train + n_val:])

    # Shuffle within each split
    random.shuffle(train_papers)
    random.shuffle(val_papers)
    random.shuffle(test_papers)

    logger.info("Split sizes: train=%d, val=%d, test=%d", len(train_papers), len(val_papers), len(test_papers))

    # ---------------------------------------------------------------------------
    # Write output files
    # ---------------------------------------------------------------------------

    def write_jsonl(filepath: Path, data: list[dict]) -> None:
        with open(filepath, "w", encoding="utf-8") as f:
            for item in data:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

    write_jsonl(output_dir / "train.jsonl", train_papers)
    write_jsonl(output_dir / "val.jsonl", val_papers)
    write_jsonl(output_dir / "test.jsonl", test_papers)
    logger.info("Wrote train.jsonl, val.jsonl, test.jsonl to %s", output_dir)

    # ---------------------------------------------------------------------------
    # Label mappings
    # ---------------------------------------------------------------------------

    # Collect all unique values for each label
    sub_fields = sorted(set(p["sub_field_label"] for p in papers))
    tiers = sorted(set(p["tier_label"] for p in papers))
    paper_types = sorted(set(p["paper_type_label"] for p in papers))

    label_mappings = {
        "sub_field_labels": {label: idx for idx, label in enumerate(sub_fields)},
        "tier_labels": {str(t): idx for idx, t in enumerate(tiers)},
        "paper_type_labels": {label: idx for idx, label in enumerate(paper_types)},
    }

    with open(output_dir / "label_mappings.json", "w") as f:
        json.dump(label_mappings, f, indent=2)
    logger.info("Wrote label_mappings.json")

    # ---------------------------------------------------------------------------
    # Print statistics
    # ---------------------------------------------------------------------------

    print("\n" + "=" * 70)
    print("DATASET STATISTICS")
    print("=" * 70)

    print(f"\nTotal papers (after filtering): {len(papers):,}")
    print(f"  Train: {len(train_papers):,} ({100 * len(train_papers) / len(papers):.1f}%)")
    print(f"  Val:   {len(val_papers):,} ({100 * len(val_papers) / len(papers):.1f}%)")
    print(f"  Test:  {len(test_papers):,} ({100 * len(test_papers) / len(papers):.1f}%)")

    print(f"\nSkipped (abstract < {MIN_ABSTRACT_LENGTH} chars): {skipped_short_abstract:,}")

    # Sub-field distribution
    print("\n--- Sub-field Distribution ---")
    sub_field_counts = collections.Counter(p["sub_field_label"] for p in papers)
    for label, count in sub_field_counts.most_common():
        print(f"  {label:25s}: {count:>8,} ({100 * count / len(papers):5.1f}%)")

    # Tier distribution
    print("\n--- Journal Tier Distribution ---")
    tier_counts = collections.Counter(p["tier_label"] for p in papers)
    for tier in sorted(tier_counts.keys()):
        count = tier_counts[tier]
        print(f"  Tier {tier}: {count:>8,} ({100 * count / len(papers):5.1f}%)")

    # Paper type distribution
    print("\n--- Paper Type Distribution ---")
    type_counts = collections.Counter(p["paper_type_label"] for p in papers)
    for label, count in type_counts.most_common():
        print(f"  {label:25s}: {count:>8,} ({100 * count / len(papers):5.1f}%)")

    # Year distribution (summary)
    print("\n--- Publication Year Distribution (last 10 years) ---")
    year_counts = collections.Counter(p.get("year") for p in papers)
    for year in sorted(year_counts.keys(), reverse=True):
        if year and year >= 2016:
            count = year_counts[year]
            print(f"  {year}: {count:>8,} ({100 * count / len(papers):5.1f}%)")
    older = sum(c for y, c in year_counts.items() if y and y < 2016)
    none_year = year_counts.get(None, 0)
    if older:
        print(f"  <2016: {older:>8,} ({100 * older / len(papers):5.1f}%)")
    if none_year:
        print(f"  Unknown: {none_year:>6,}")

    # Abstract length stats
    lengths = [len(p["abstract"]) for p in papers]
    lengths.sort()
    print(f"\n--- Abstract Length ---")
    print(f"  Min:    {lengths[0]:,} chars")
    print(f"  Median: {lengths[len(lengths) // 2]:,} chars")
    print(f"  Mean:   {sum(lengths) / len(lengths):,.0f} chars")
    print(f"  Max:    {lengths[-1]:,} chars")

    # Citation stats
    cites = [p.get("cited_by_count", 0) for p in papers]
    cites.sort()
    print(f"\n--- Citation Counts ---")
    print(f"  Min:    {cites[0]:,}")
    print(f"  Median: {cites[len(cites) // 2]:,}")
    print(f"  Mean:   {sum(cites) / len(cites):,.1f}")
    print(f"  Max:    {cites[-1]:,}")
    print(f"  Zero citations: {sum(1 for c in cites if c == 0):,}")

    # FWCI stats
    fwci_vals = [p["fwci"] for p in papers if p.get("fwci") is not None]
    if fwci_vals:
        fwci_vals.sort()
        print(f"\n--- FWCI (Field-Weighted Citation Impact) ---")
        print(f"  Available: {len(fwci_vals):,} / {len(papers):,}")
        print(f"  Median: {fwci_vals[len(fwci_vals) // 2]:.2f}")
        print(f"  Mean:   {sum(fwci_vals) / len(fwci_vals):.2f}")

    # Label mappings summary
    print(f"\n--- Label Mappings ---")
    print(f"  Sub-fields:  {len(label_mappings['sub_field_labels'])} classes")
    print(f"  Tiers:       {len(label_mappings['tier_labels'])} classes")
    print(f"  Paper types: {len(label_mappings['paper_type_labels'])} classes")

    print("\n" + "=" * 70)
    print(f"Output directory: {output_dir}")
    print("=" * 70 + "\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare oncology training data")
    parser.add_argument(
        "--input-dir",
        type=str,
        default="/tmp/oncology_data_enriched/",
        help="Directory containing (enriched) JSONL files",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="/tmp/oncology_training/",
        help="Directory for training split output",
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)

    if not input_dir.exists():
        logger.error("Input directory does not exist: %s", input_dir)
        sys.exit(1)

    logger.info("Preparing training data from %s → %s", input_dir, output_dir)
    process_papers(input_dir, output_dir)


if __name__ == "__main__":
    main()
