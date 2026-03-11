"""
Enrich OpenAlex papers with PubMed metadata (MeSH terms, publication types, dates).

Reads JSONL files produced by download_openalex.py, looks up PMIDs via DOI,
fetches structured metadata via NCBI E-utilities, and writes enriched JSONL.

Usage:
    python -m backend.oncology_model.download_pubmed \
        --input-dir /tmp/oncology_data/ \
        --output-dir /tmp/oncology_data_enriched/

Set NCBI_API_KEY env var for 10 req/s (otherwise 3 req/s).
"""

import argparse
import json
import logging
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
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

NCBI_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
NCBI_EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
NCBI_API_KEY = os.environ.get("NCBI_API_KEY")

# Rate limits: 3/s without key, 10/s with key
RATE_LIMIT = 0.10 if NCBI_API_KEY else 0.34  # seconds between requests

# Batch sizes
ESEARCH_BATCH = 200   # DOIs per esearch (one DOI per request actually, but we batch PMIDs)
EFETCH_BATCH = 500    # PMIDs per efetch call (NCBI allows up to 10K but 500 is safer for XML parsing)
DOI_LOOKUP_BATCH = 50  # DOIs to look up in one esearch call using OR

CHECKPOINT_FILE = "_pubmed_checkpoint.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def build_session() -> requests.Session:
    session = requests.Session()
    retries = Retry(
        total=8,
        backoff_factor=1.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def ncbi_params() -> dict[str, str]:
    """Base params for NCBI E-utilities."""
    params: dict[str, str] = {"db": "pubmed", "retmode": "xml"}
    if NCBI_API_KEY:
        params["api_key"] = NCBI_API_KEY
    return params


def clean_doi(doi: Optional[str]) -> Optional[str]:
    """Extract bare DOI from URL or string."""
    if not doi:
        return None
    doi = doi.strip()
    # Strip URL prefix
    if doi.startswith("https://doi.org/"):
        doi = doi[len("https://doi.org/"):]
    elif doi.startswith("http://doi.org/"):
        doi = doi[len("http://doi.org/"):]
    return doi if doi else None


# ---------------------------------------------------------------------------
# NCBI lookups
# ---------------------------------------------------------------------------

def lookup_pmids_by_dois(
    session: requests.Session,
    dois: list[str],
) -> dict[str, str]:
    """Look up PMIDs for a batch of DOIs using esearch.

    Returns mapping of DOI -> PMID.
    """
    doi_to_pmid: dict[str, str] = {}

    # NCBI esearch supports one DOI at a time most reliably
    for doi in dois:
        params = ncbi_params()
        params["term"] = f"{doi}[doi]"
        params["retmax"] = "1"

        try:
            resp = session.get(NCBI_ESEARCH, params=params, timeout=30)
            resp.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.warning("esearch failed for DOI %s: %s", doi, e)
            time.sleep(RATE_LIMIT)
            continue

        try:
            root = ET.fromstring(resp.content)
            id_list = root.find("IdList")
            if id_list is not None:
                ids = id_list.findall("Id")
                if ids:
                    doi_to_pmid[doi] = ids[0].text
        except ET.ParseError as e:
            logger.warning("XML parse error for DOI %s: %s", doi, e)

        time.sleep(RATE_LIMIT)

    return doi_to_pmid


def fetch_pubmed_metadata(
    session: requests.Session,
    pmids: list[str],
) -> dict[str, dict[str, Any]]:
    """Fetch structured PubMed metadata for a batch of PMIDs via efetch.

    Returns mapping of PMID -> metadata dict.
    """
    metadata: dict[str, dict[str, Any]] = {}

    for i in range(0, len(pmids), EFETCH_BATCH):
        batch = pmids[i:i + EFETCH_BATCH]
        params = ncbi_params()
        params["id"] = ",".join(batch)
        params["rettype"] = "xml"

        try:
            resp = session.post(NCBI_EFETCH, data=params, timeout=120)
            resp.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.warning("efetch failed for batch starting at %d: %s", i, e)
            time.sleep(RATE_LIMIT * 5)
            continue

        try:
            root = ET.fromstring(resp.content)
        except ET.ParseError as e:
            logger.warning("efetch XML parse error at batch %d: %s", i, e)
            continue

        for article in root.findall(".//PubmedArticle"):
            pmid_elem = article.find(".//PMID")
            if pmid_elem is None or not pmid_elem.text:
                continue
            pmid = pmid_elem.text

            # MeSH terms
            mesh_terms = []
            for mh in article.findall(".//MeshHeading"):
                descriptor = mh.find("DescriptorName")
                if descriptor is not None and descriptor.text:
                    qualifiers = []
                    for qual in mh.findall("QualifierName"):
                        if qual.text:
                            qualifiers.append({
                                "name": qual.text,
                                "major_topic": qual.get("MajorTopicYN", "N") == "Y",
                            })
                    mesh_terms.append({
                        "descriptor": descriptor.text,
                        "major_topic": descriptor.get("MajorTopicYN", "N") == "Y",
                        "qualifiers": qualifiers,
                    })

            # Publication types
            pub_types = []
            for pt in article.findall(".//PublicationType"):
                if pt.text:
                    pub_types.append(pt.text)

            # Dates
            dates: dict[str, Optional[str]] = {
                "received": None,
                "accepted": None,
                "published": None,
            }
            for ph in article.findall(".//PubMedPubDate"):
                status = ph.get("PubStatus", "")
                year = ph.findtext("Year")
                month = ph.findtext("Month", "01")
                day = ph.findtext("Day", "01")
                if year:
                    date_str = f"{year}-{int(month):02d}-{int(day):02d}"
                    if status == "received":
                        dates["received"] = date_str
                    elif status == "accepted":
                        dates["accepted"] = date_str
                    elif status in ("pubmed", "medline", "epublish"):
                        if dates["published"] is None:
                            dates["published"] = date_str

            metadata[pmid] = {
                "pmid": pmid,
                "pubmed_mesh_terms": mesh_terms,
                "pubmed_publication_types": pub_types,
                "date_received": dates["received"],
                "date_accepted": dates["accepted"],
                "date_published_pubmed": dates["published"],
            }

        time.sleep(RATE_LIMIT)

    return metadata


# ---------------------------------------------------------------------------
# Main enrichment pipeline
# ---------------------------------------------------------------------------

def load_checkpoint(output_dir: Path) -> dict[str, Any]:
    cp_path = output_dir / CHECKPOINT_FILE
    if cp_path.exists():
        with open(cp_path, "r") as f:
            return json.load(f)
    return {"completed_files": [], "doi_to_pmid_cache": {}}


def save_checkpoint(output_dir: Path, checkpoint: dict[str, Any]) -> None:
    cp_path = output_dir / CHECKPOINT_FILE
    with open(cp_path, "w") as f:
        json.dump(checkpoint, f)


def enrich_papers(input_dir: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    session = build_session()

    checkpoint = load_checkpoint(output_dir)
    completed_files: list[str] = checkpoint.get("completed_files", [])
    # Cache DOI -> PMID to avoid redundant lookups
    doi_to_pmid_cache: dict[str, str] = checkpoint.get("doi_to_pmid_cache", {})

    # Find all JSONL input files
    input_files = sorted(input_dir.glob("oncology_papers_*.jsonl"))
    if not input_files:
        logger.error("No oncology_papers_*.jsonl files found in %s", input_dir)
        return

    logger.info("Found %d input files, %d already completed", len(input_files), len(completed_files))

    total_enriched = 0
    total_skipped_no_doi = 0
    total_skipped_no_pmid = 0

    for input_file in input_files:
        if input_file.name in completed_files:
            logger.info("Skipping already-completed file: %s", input_file.name)
            continue

        logger.info("Processing %s ...", input_file.name)

        # Read all papers from this file
        papers: list[dict[str, Any]] = []
        with open(input_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    papers.append(json.loads(line))

        if not papers:
            logger.info("Empty file: %s", input_file.name)
            completed_files.append(input_file.name)
            save_checkpoint(output_dir, {"completed_files": completed_files, "doi_to_pmid_cache": doi_to_pmid_cache})
            continue

        # Phase 1: Collect DOIs that need PMID lookup
        dois_needing_lookup: list[str] = []
        doi_to_paper_indices: dict[str, list[int]] = {}

        for idx, paper in enumerate(papers):
            doi = clean_doi(paper.get("doi"))
            if not doi:
                total_skipped_no_doi += 1
                continue
            paper["_clean_doi"] = doi
            if doi not in doi_to_pmid_cache:
                dois_needing_lookup.append(doi)
            doi_to_paper_indices.setdefault(doi, []).append(idx)

        logger.info(
            "  %d papers, %d with DOIs, %d need PMID lookup (%d cached)",
            len(papers),
            len(doi_to_paper_indices),
            len(dois_needing_lookup),
            len(doi_to_paper_indices) - len(dois_needing_lookup),
        )

        # Phase 2: Look up PMIDs for DOIs not in cache
        if dois_needing_lookup:
            for batch_start in range(0, len(dois_needing_lookup), DOI_LOOKUP_BATCH):
                batch = dois_needing_lookup[batch_start:batch_start + DOI_LOOKUP_BATCH]
                new_mappings = lookup_pmids_by_dois(session, batch)
                doi_to_pmid_cache.update(new_mappings)

                if (batch_start + DOI_LOOKUP_BATCH) % 500 == 0:
                    logger.info(
                        "  DOI lookup progress: %d / %d",
                        min(batch_start + DOI_LOOKUP_BATCH, len(dois_needing_lookup)),
                        len(dois_needing_lookup),
                    )

        # Phase 3: Collect all PMIDs we have and fetch metadata
        pmids_to_fetch: list[str] = []
        doi_to_pmid_for_file: dict[str, str] = {}
        for doi in doi_to_paper_indices:
            pmid = doi_to_pmid_cache.get(doi)
            if pmid:
                pmids_to_fetch.append(pmid)
                doi_to_pmid_for_file[doi] = pmid
            else:
                total_skipped_no_pmid += 1

        logger.info("  Fetching PubMed metadata for %d PMIDs ...", len(pmids_to_fetch))
        pmid_metadata = fetch_pubmed_metadata(session, pmids_to_fetch)
        logger.info("  Got metadata for %d / %d PMIDs", len(pmid_metadata), len(pmids_to_fetch))

        # Phase 4: Merge and write enriched papers
        output_file = output_dir / input_file.name
        with open(output_file, "w", encoding="utf-8") as out_f:
            for paper in papers:
                doi = paper.pop("_clean_doi", None)
                if doi:
                    pmid = doi_to_pmid_for_file.get(doi)
                    if pmid and pmid in pmid_metadata:
                        paper.update(pmid_metadata[pmid])
                        total_enriched += 1
                    else:
                        # Add empty fields so schema is consistent
                        paper["pmid"] = None
                        paper["pubmed_mesh_terms"] = []
                        paper["pubmed_publication_types"] = []
                        paper["date_received"] = None
                        paper["date_accepted"] = None
                        paper["date_published_pubmed"] = None
                else:
                    paper["pmid"] = None
                    paper["pubmed_mesh_terms"] = []
                    paper["pubmed_publication_types"] = []
                    paper["date_received"] = None
                    paper["date_accepted"] = None
                    paper["date_published_pubmed"] = None

                out_f.write(json.dumps(paper, ensure_ascii=False) + "\n")

        completed_files.append(input_file.name)
        # Periodically trim cache to avoid memory bloat (keep last 500K entries)
        if len(doi_to_pmid_cache) > 600_000:
            keys = list(doi_to_pmid_cache.keys())
            doi_to_pmid_cache = {k: doi_to_pmid_cache[k] for k in keys[-500_000:]}

        save_checkpoint(output_dir, {"completed_files": completed_files, "doi_to_pmid_cache": doi_to_pmid_cache})
        logger.info("  Completed %s (%d enriched so far)", input_file.name, total_enriched)

    logger.info(
        "PubMed enrichment complete: %d enriched, %d no DOI, %d no PMID found",
        total_enriched, total_skipped_no_doi, total_skipped_no_pmid,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich OpenAlex papers with PubMed metadata")
    parser.add_argument(
        "--input-dir",
        type=str,
        default="/tmp/oncology_data/",
        help="Directory containing OpenAlex JSONL files",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="/tmp/oncology_data_enriched/",
        help="Directory for enriched JSONL output",
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)

    if not input_dir.exists():
        logger.error("Input directory does not exist: %s", input_dir)
        sys.exit(1)

    if NCBI_API_KEY:
        logger.info("NCBI API key detected — using 10 req/s rate limit")
    else:
        logger.info("No NCBI_API_KEY — using 3 req/s rate limit (set env var for faster)")

    logger.info("Enriching papers from %s → %s", input_dir, output_dir)
    enrich_papers(input_dir, output_dir)


if __name__ == "__main__":
    main()
