"""
Download ~1M oncology papers from OpenAlex API.

Uses cursor-based pagination with concept filter C143998085 (Oncology).
Designed to run unattended on AWS EC2/ECS for ~19 hours.

Usage:
    python -m backend.oncology_model.download_openalex \
        --output-dir /tmp/oncology_data/ \
        --target 1000000
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Optional

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

OPENALEX_API = "https://api.openalex.org/works"
CONCEPT_ONCOLOGY = "C143998085"
MAILTO = "prmogathala@gmail.com"
PER_PAGE = 200  # OpenAlex max
RATE_LIMIT_SECONDS = 0.10  # 100 ms between requests
BATCH_SIZE = 10_000  # papers per JSONL file

SELECT_FIELDS = ",".join([
    "id",
    "doi",
    "title",
    "publication_year",
    "cited_by_count",
    "type",
    "primary_location",
    "authorships",
    "abstract_inverted_index",
    "concepts",
    "topics",
    "mesh",
    "referenced_works_count",
    "fwci",
    "citation_normalized_percentile",
])

# Cancer-type keywords mapped to canonical labels (matched against concept names)
CANCER_TYPE_KEYWORDS: dict[str, list[str]] = {
    "breast": ["breast cancer", "breast neoplasm", "breast carcinoma", "mammary"],
    "lung": ["lung cancer", "lung neoplasm", "lung carcinoma", "non-small cell lung", "small cell lung", "nsclc", "sclc", "pulmonary neoplasm"],
    "colorectal": ["colorectal cancer", "colorectal neoplasm", "colon cancer", "rectal cancer", "colorectal carcinoma"],
    "prostate": ["prostate cancer", "prostate neoplasm", "prostate carcinoma", "prostatic"],
    "hematologic": ["leukemia", "lymphoma", "myeloma", "hematologic", "haematologic", "blood cancer", "hodgkin", "non-hodgkin"],
    "melanoma": ["melanoma", "skin cancer", "cutaneous melanoma"],
    "brain": ["glioma", "glioblastoma", "brain cancer", "brain tumor", "brain tumour", "brain neoplasm", "meningioma", "astrocytoma", "medulloblastoma", "neuroblastoma"],
    "pancreatic": ["pancreatic cancer", "pancreatic neoplasm", "pancreatic carcinoma", "pancreatic ductal"],
    "ovarian": ["ovarian cancer", "ovarian neoplasm", "ovarian carcinoma"],
    "head_neck": ["head and neck cancer", "head and neck neoplasm", "head neck", "oral cancer", "nasopharyngeal", "pharyngeal cancer", "laryngeal cancer", "thyroid cancer"],
    "liver": ["liver cancer", "hepatocellular carcinoma", "hepatocellular", "hepatoblastoma", "liver neoplasm", "hepatic cancer"],
    "kidney": ["kidney cancer", "renal cell carcinoma", "renal cancer", "renal neoplasm", "kidney neoplasm", "nephroblastoma", "wilms"],
    "sarcoma": ["sarcoma", "osteosarcoma", "ewing", "rhabdomyosarcoma", "liposarcoma", "leiomyosarcoma"],
    "pediatric": ["pediatric oncology", "pediatric cancer", "childhood cancer", "childhood leukemia", "retinoblastoma"],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def build_session() -> requests.Session:
    """Build a requests session with retry logic."""
    session = requests.Session()
    retries = Retry(
        total=10,
        backoff_factor=1.0,  # 1, 2, 4, 8, 16 … seconds
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def reconstruct_abstract(inverted_index: Optional[dict]) -> Optional[str]:
    """Reconstruct plain-text abstract from OpenAlex inverted index."""
    if not inverted_index:
        return None
    word_positions: list[tuple[int, str]] = []
    for word, positions in inverted_index.items():
        for pos in positions:
            word_positions.append((pos, word))
    if not word_positions:
        return None
    word_positions.sort(key=lambda x: x[0])
    return " ".join(w for _, w in word_positions)


def extract_cancer_type(concepts: list[dict], mesh_terms: list[dict]) -> Optional[str]:
    """Extract cancer type from concepts and MeSH terms."""
    # Collect all concept/mesh display names in lowercase
    names_lower: list[str] = []
    for c in concepts:
        name = (c.get("display_name") or "").lower()
        if name:
            names_lower.append(name)
    for m in mesh_terms:
        name = (m.get("descriptor_name") or "").lower()
        if name:
            names_lower.append(name)

    joined = " | ".join(names_lower)
    for cancer_type, keywords in CANCER_TYPE_KEYWORDS.items():
        for kw in keywords:
            if kw in joined:
                return cancer_type
    return None


def parse_paper(raw: dict) -> Optional[dict]:
    """Parse a single OpenAlex work record into our schema.

    Returns None if the paper has no usable abstract.
    """
    abstract = reconstruct_abstract(raw.get("abstract_inverted_index"))
    if not abstract:
        return None

    # Primary location -> journal info
    primary_loc = raw.get("primary_location") or {}
    source = primary_loc.get("source") or {}
    journal_name = source.get("display_name")
    journal_issn = None
    issn_list = source.get("issn") or []
    if issn_list:
        journal_issn = issn_list[0]

    # Concepts
    concepts_raw = raw.get("concepts") or []
    concepts = [
        {"name": c.get("display_name"), "score": c.get("score")}
        for c in concepts_raw
        if c.get("display_name")
    ]

    # Topics
    topics_raw = raw.get("topics") or []
    topics = [
        t.get("display_name")
        for t in topics_raw
        if t.get("display_name")
    ]

    # MeSH
    mesh_raw = raw.get("mesh") or []
    mesh_terms = [
        {
            "descriptor_name": m.get("descriptor_name"),
            "qualifier_name": m.get("qualifier_name"),
            "is_major_topic": m.get("is_major_topic", False),
        }
        for m in mesh_raw
        if m.get("descriptor_name")
    ]

    # Author count
    authorships = raw.get("authorships") or []
    author_count = len(authorships)

    # Citation normalized percentile
    cnp = raw.get("citation_normalized_percentile")
    cnp_value = None
    if isinstance(cnp, dict):
        cnp_value = cnp.get("value")
    elif isinstance(cnp, (int, float)):
        cnp_value = cnp

    # Cancer type
    cancer_type = extract_cancer_type(concepts_raw, mesh_raw)

    # OpenAlex ID (strip URL prefix)
    openalex_id = raw.get("id", "")
    if openalex_id.startswith("https://openalex.org/"):
        openalex_id = openalex_id.replace("https://openalex.org/", "")

    return {
        "openalex_id": openalex_id,
        "doi": raw.get("doi"),
        "title": raw.get("title"),
        "abstract": abstract,
        "journal_name": journal_name,
        "journal_issn": journal_issn,
        "year": raw.get("publication_year"),
        "cited_by_count": raw.get("cited_by_count", 0),
        "fwci": raw.get("fwci"),
        "citation_normalized_percentile": cnp_value,
        "type": raw.get("type"),
        "author_count": author_count,
        "ref_count": raw.get("referenced_works_count", 0),
        "concepts": concepts,
        "topics": topics,
        "mesh_terms": mesh_terms,
        "cancer_type": cancer_type,
    }


def get_checkpoint_path(output_dir: Path) -> Path:
    return output_dir / "_checkpoint.json"


def load_checkpoint(output_dir: Path) -> dict[str, Any]:
    """Load resume checkpoint (cursor, total collected, batch index)."""
    cp_path = get_checkpoint_path(output_dir)
    if cp_path.exists():
        with open(cp_path, "r") as f:
            return json.load(f)
    return {"cursor": "*", "total_collected": 0, "batch_index": 0, "batch_buffer_count": 0}


def save_checkpoint(output_dir: Path, cursor: str, total_collected: int,
                    batch_index: int, batch_buffer_count: int) -> None:
    cp_path = get_checkpoint_path(output_dir)
    with open(cp_path, "w") as f:
        json.dump({
            "cursor": cursor,
            "total_collected": total_collected,
            "batch_index": batch_index,
            "batch_buffer_count": batch_buffer_count,
        }, f)


def get_batch_filepath(output_dir: Path, batch_index: int) -> Path:
    return output_dir / f"oncology_papers_{batch_index:05d}.jsonl"


# ---------------------------------------------------------------------------
# Main download loop
# ---------------------------------------------------------------------------

def download_papers(output_dir: Path, target: int) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    session = build_session()

    # Resume from checkpoint
    checkpoint = load_checkpoint(output_dir)
    cursor = checkpoint["cursor"]
    total_collected = checkpoint["total_collected"]
    batch_index = checkpoint["batch_index"]
    batch_buffer_count = checkpoint["batch_buffer_count"]

    if total_collected > 0:
        logger.info(
            "Resuming from checkpoint: %d papers collected, batch %d, cursor=%s",
            total_collected, batch_index, cursor[:30] + "...",
        )

    # Open the current batch file in append mode if we're resuming mid-batch
    batch_file_path = get_batch_filepath(output_dir, batch_index)
    batch_fp = open(batch_file_path, "a", encoding="utf-8")

    pages_fetched = 0
    start_time = time.time()

    try:
        while total_collected < target:
            params: dict[str, Any] = {
                "filter": f"concepts.id:{CONCEPT_ONCOLOGY}",
                "select": SELECT_FIELDS,
                "per_page": PER_PAGE,
                "cursor": cursor,
                "mailto": MAILTO,
            }

            try:
                resp = session.get(OPENALEX_API, params=params, timeout=60)
                resp.raise_for_status()
            except requests.exceptions.RequestException as e:
                logger.error("Request failed after retries: %s", e)
                # Save checkpoint and exit so we can resume
                save_checkpoint(output_dir, cursor, total_collected, batch_index, batch_buffer_count)
                batch_fp.close()
                raise

            data = resp.json()
            results = data.get("results", [])
            next_cursor = data.get("meta", {}).get("next_cursor")

            if not results:
                logger.info("No more results from API. Ending.")
                break

            for raw_paper in results:
                if total_collected >= target:
                    break

                paper = parse_paper(raw_paper)
                if paper is None:
                    continue

                batch_fp.write(json.dumps(paper, ensure_ascii=False) + "\n")
                total_collected += 1
                batch_buffer_count += 1

                # Progress logging every 1000 papers
                if total_collected % 1000 == 0:
                    elapsed = time.time() - start_time
                    rate = total_collected / elapsed if elapsed > 0 else 0
                    eta_hours = (target - total_collected) / rate / 3600 if rate > 0 else 0
                    logger.info(
                        "Progress: %d / %d papers (%.1f%%) | %.1f papers/s | ETA: %.1f hrs",
                        total_collected, target,
                        100 * total_collected / target,
                        rate, eta_hours,
                    )

                # Rotate batch file every BATCH_SIZE papers
                if batch_buffer_count >= BATCH_SIZE:
                    batch_fp.close()
                    logger.info(
                        "Batch %d complete: %s (%d papers in this batch)",
                        batch_index, batch_file_path.name, batch_buffer_count,
                    )
                    batch_index += 1
                    batch_buffer_count = 0
                    batch_file_path = get_batch_filepath(output_dir, batch_index)
                    batch_fp = open(batch_file_path, "a", encoding="utf-8")

            # Move to next cursor
            if next_cursor is None:
                logger.info("API returned no next_cursor. Ending.")
                break
            cursor = next_cursor
            pages_fetched += 1

            # Checkpoint every 10 pages (~2000 papers)
            if pages_fetched % 10 == 0:
                save_checkpoint(output_dir, cursor, total_collected, batch_index, batch_buffer_count)

            # Rate limiting
            time.sleep(RATE_LIMIT_SECONDS)

    finally:
        batch_fp.close()
        save_checkpoint(output_dir, cursor, total_collected, batch_index, batch_buffer_count)

    elapsed_total = time.time() - start_time
    logger.info(
        "Download complete: %d papers in %.1f hours (%d batch files)",
        total_collected, elapsed_total / 3600, batch_index + 1,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Download oncology papers from OpenAlex")
    parser.add_argument(
        "--output-dir",
        type=str,
        default="/tmp/oncology_data/",
        help="Directory to save JSONL files (default: /tmp/oncology_data/)",
    )
    parser.add_argument(
        "--target",
        type=int,
        default=1_000_000,
        help="Target number of papers to download (default: 1,000,000)",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    logger.info("Starting OpenAlex oncology download → %s (target: %d)", output_dir, args.target)
    download_papers(output_dir, args.target)


if __name__ == "__main__":
    main()
