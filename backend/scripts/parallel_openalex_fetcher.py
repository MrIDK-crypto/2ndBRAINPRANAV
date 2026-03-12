"""
Parallel OpenAlex fetcher for large-scale HIJ training data.

Usage:
    python -m scripts.parallel_openalex_fetcher --target 1000000 --output data/hij_1m
"""
import argparse
import json
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Set

import requests
from requests.adapters import HTTPAdapter, Retry

logger = logging.getLogger(__name__)

MAILTO = os.getenv("OPENALEX_MAILTO", "prmogathala@gmail.com")
BASE_URL = "https://api.openalex.org/works"
PER_PAGE = 200

# Fields and paper types to query
FIELDS = {
    "biomedical": "C71924100",
    "cs_data_science": "C41008148",
    "economics": "C162324750",
    "psychology": "C15744967",
    "physics": "C121332964",
    "chemistry": "C185592680",
    "engineering": "C127413603",
    "environmental_science": "C39432304",
}

PAPER_TYPES = {
    "experimental": {"work_type": "article", "title_filter": None},
    "review": {"work_type": "review", "title_filter": None},
    "meta_analysis": {"work_type": "article", "title_filter": "meta-analysis|systematic review"},
    "case_report": {"work_type": "article", "title_filter": "case report|case study|case series"},
    "protocol": {"work_type": "article", "title_filter": "protocol|methodology|standard operating"},
}


class RateLimiter:
    """Thread-safe token bucket rate limiter."""

    def __init__(self, rate: float = 10.0):
        self._rate = rate
        self._lock = threading.Lock()
        self._last = time.monotonic()

    def acquire(self):
        with self._lock:
            now = time.monotonic()
            wait = max(0, (1.0 / self._rate) - (now - self._last))
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()


class CheckpointManager:
    """Save/restore fetch progress for resumability."""

    def __init__(self, checkpoint_path: Path):
        self._path = checkpoint_path
        self._lock = threading.Lock()
        self._state: Dict = {}
        self._load()

    def _load(self):
        if self._path.exists():
            with open(self._path) as f:
                self._state = json.load(f)
            logger.info("[Checkpoint] Restored: %d queries tracked", len(self._state.get("cursors", {})))

    def save(self):
        with self._lock:
            with open(self._path, "w") as f:
                json.dump(self._state, f, indent=2)

    def get_cursor(self, query_key: str) -> Optional[str]:
        return self._state.get("cursors", {}).get(query_key)

    def set_cursor(self, query_key: str, cursor: str, count: int):
        with self._lock:
            self._state.setdefault("cursors", {})[query_key] = cursor
            self._state.setdefault("counts", {})[query_key] = count

    @property
    def total_fetched(self) -> int:
        return sum(self._state.get("counts", {}).values())


def _create_session() -> requests.Session:
    session = requests.Session()
    retries = Retry(total=5, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retries))
    session.headers.update({
        "User-Agent": f"2ndBrain/1.0 (mailto:{MAILTO})",
        "Accept": "application/json",
    })
    return session


def _reconstruct_abstract(inverted_index: dict) -> str:
    """Rebuild abstract from OpenAlex inverted index format."""
    if not inverted_index:
        return ""
    word_positions = []
    for word, positions in inverted_index.items():
        for pos in positions:
            word_positions.append((pos, word))
    word_positions.sort()
    return " ".join(w for _, w in word_positions)


def _determine_tier(cited_by_count: int, journal_name: str) -> str:
    """Assign tier based on citation count as proxy for journal quality."""
    top_journals = {
        "nature", "science", "cell", "the lancet", "new england journal of medicine",
        "jama", "bmj", "nature medicine", "nature genetics", "nature biotechnology",
        "proceedings of the national academy of sciences", "plos medicine",
    }
    if journal_name and journal_name.lower() in top_journals:
        return "Tier1"
    if cited_by_count >= 50:
        return "Tier1"
    elif cited_by_count >= 10:
        return "Tier2"
    return "Tier3"


def _fetch_query(
    field_name: str,
    field_concept: str,
    paper_type: str,
    type_config: dict,
    target_per_query: int,
    rate_limiter: RateLimiter,
    checkpoint: CheckpointManager,
    seen_ids: Set[str],
    seen_lock: threading.Lock,
) -> List[dict]:
    """Fetch papers for one field+type combination."""
    query_key = f"{field_name}_{paper_type}"
    session = _create_session()
    results = []
    cursor = checkpoint.get_cursor(query_key) or "*"
    fetched = 0

    params = {
        "filter": f"concepts.id:{field_concept},type:{type_config['work_type']},has_abstract:true,publication_year:2018-2026",
        "select": "id,doi,title,type,cited_by_count,referenced_works_count,primary_location,authorships,abstract_inverted_index,concepts,fwci",
        "per_page": PER_PAGE,
        "cursor": cursor,
        "mailto": MAILTO,
    }

    if type_config.get("title_filter"):
        params["filter"] += f",title.search:{type_config['title_filter']}"

    while fetched < target_per_query:
        rate_limiter.acquire()

        try:
            resp = session.get(BASE_URL, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.warning("[%s] API error: %s — stopping this query", query_key, e)
            break

        works = data.get("results", [])
        if not works:
            break

        for work in works:
            work_id = work.get("id", "")
            with seen_lock:
                if work_id in seen_ids:
                    continue
                seen_ids.add(work_id)

            abstract = _reconstruct_abstract(work.get("abstract_inverted_index", {}))
            if len(abstract) < 80:
                continue

            title = work.get("title", "")
            if not title:
                continue

            journal = ""
            loc = work.get("primary_location", {})
            if loc and loc.get("source"):
                journal = loc["source"].get("display_name", "")

            authors = work.get("authorships", [])
            institutions = set()
            for a in authors:
                for inst in a.get("institutions", []):
                    if inst.get("display_name"):
                        institutions.add(inst["display_name"])

            has_funding = work.get("fwci") is not None and work.get("fwci", 0) > 0

            record = {
                "title": title,
                "abstract": abstract,
                "paper_type": paper_type,
                "tier": _determine_tier(work.get("cited_by_count", 0), journal),
                "author_count": len(authors),
                "ref_count": work.get("referenced_works_count", 0),
                "has_funding": has_funding,
                "institution_count": len(institutions),
                "is_multicenter": len(institutions) > 1,
                "journal": journal,
                "year": work.get("publication_year", 0),
                "cited_by_count": work.get("cited_by_count", 0),
            }
            results.append(record)
            fetched += 1

        next_cursor = data.get("meta", {}).get("next_cursor")
        if not next_cursor:
            break

        params["cursor"] = next_cursor
        checkpoint.set_cursor(query_key, next_cursor, fetched)

        if fetched % 1000 == 0:
            checkpoint.save()
            logger.info("[%s] %d papers fetched", query_key, fetched)

    checkpoint.set_cursor(query_key, params.get("cursor", "*"), fetched)
    checkpoint.save()
    logger.info("[%s] Done: %d papers", query_key, fetched)
    return results


def fetch_papers_parallel(
    output_dir: Path,
    target_total: int = 1_000_000,
    num_workers: int = 8,
) -> Path:
    """
    Fetch papers from OpenAlex in parallel and write train/val/test JSONL splits.

    Returns path to output directory containing train.jsonl, val.jsonl, test.jsonl.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint = CheckpointManager(output_dir / "checkpoint.json")
    rate_limiter = RateLimiter(rate=10.0)
    seen_ids: Set[str] = set()
    seen_lock = threading.Lock()

    # Build query combinations
    queries = []
    num_queries = len(FIELDS) * len(PAPER_TYPES)
    per_query = target_total // num_queries + 1

    # Weight experimental papers higher (40% of total)
    type_weights = {
        "experimental": 0.40,
        "review": 0.25,
        "meta_analysis": 0.15,
        "case_report": 0.10,
        "protocol": 0.10,
    }

    for field_name, concept_id in FIELDS.items():
        for ptype, config in PAPER_TYPES.items():
            target = int(target_total * type_weights[ptype] / len(FIELDS))
            queries.append((field_name, concept_id, ptype, config, target))

    logger.info("[Fetcher] %d queries, target %d papers total, %d workers", len(queries), target_total, num_workers)

    all_papers = []
    with ThreadPoolExecutor(max_workers=num_workers) as pool:
        futures = {
            pool.submit(
                _fetch_query, fn, cid, pt, cfg, tgt,
                rate_limiter, checkpoint, seen_ids, seen_lock,
            ): f"{fn}_{pt}"
            for fn, cid, pt, cfg, tgt in queries
        }

        for future in as_completed(futures):
            query_key = futures[future]
            try:
                papers = future.result()
                all_papers.extend(papers)
                logger.info("[Fetcher] %s returned %d papers (total: %d)", query_key, len(papers), len(all_papers))
            except Exception as e:
                logger.error("[Fetcher] %s failed: %s", query_key, e)

    logger.info("[Fetcher] Total papers collected: %d", len(all_papers))

    # Shuffle and split: 80/10/10
    import random
    random.shuffle(all_papers)
    n = len(all_papers)
    train_end = int(n * 0.8)
    val_end = int(n * 0.9)

    splits = {
        "train.jsonl": all_papers[:train_end],
        "val.jsonl": all_papers[train_end:val_end],
        "test.jsonl": all_papers[val_end:],
    }

    for filename, records in splits.items():
        path = output_dir / filename
        with open(path, "w") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")
        logger.info("[Fetcher] Wrote %s: %d records", filename, len(records))

    # Write summary
    from collections import Counter
    type_counts = Counter(p["paper_type"] for p in all_papers)
    tier_counts = Counter(p["tier"] for p in all_papers)
    summary = {
        "total_papers": len(all_papers),
        "splits": {k: len(v) for k, v in splits.items()},
        "paper_types": dict(type_counts),
        "tiers": dict(tier_counts),
    }
    with open(output_dir / "summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    logger.info("[Fetcher] Summary: %s", json.dumps(summary, indent=2))
    return output_dir


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=int, default=1_000_000)
    parser.add_argument("--output", type=str, default="data/hij_1m")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    fetch_papers_parallel(
        output_dir=Path(args.output),
        target_total=args.target,
        num_workers=args.workers,
    )
