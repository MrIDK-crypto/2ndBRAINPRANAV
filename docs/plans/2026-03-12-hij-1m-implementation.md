# HIJ 1M-Paper Training Pipeline — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Scale HIJ model training from 5K to 1M papers via autonomous EC2 spot pipeline with zero-downtime model swap.

**Architecture:** EC2 spot instance fetches 1M papers from OpenAlex (parallel), trains TF-IDF+LogReg models, validates against accuracy floor, uploads to S3. ECS pulls from S3 on startup + admin hot-swap endpoint.

**Tech Stack:** boto3, OpenAlex API, scikit-learn, AWS (EC2, S3, Lambda, SNS, CloudWatch)

---

### Task 1: S3 Model Sync Script

**Files:**
- Create: `backend/scripts/sync_models_from_s3.py`

**Step 1: Write the sync script**

```python
"""
Download latest HIJ models from S3 if newer than local copy.
Run before Flask starts (from entrypoint.sh) or on-demand.
"""
import os
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

S3_BUCKET = os.getenv("HIJ_MODEL_BUCKET", "secondbrain-models")
S3_PREFIX = "hij/active/"
LOCAL_MODEL_DIR = Path(__file__).resolve().parent.parent / "models"

# Model subdirectories to sync
MODEL_DIRS = [
    "paper_type_classifier/tfidf_primary",
    "tier_predictor/tfidf",
]
METADATA_FILE = "metadata.json"


def _get_s3_client():
    import boto3
    return boto3.client(
        "s3",
        region_name=os.getenv("AWS_S3_REGION", "us-east-2"),
    )


def _local_metadata() -> dict:
    """Read local metadata.json if it exists."""
    path = LOCAL_MODEL_DIR / METADATA_FILE
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


def _s3_metadata(s3) -> dict:
    """Read metadata.json from S3."""
    try:
        resp = s3.get_object(Bucket=S3_BUCKET, Key=f"{S3_PREFIX}{METADATA_FILE}")
        return json.loads(resp["Body"].read().decode())
    except Exception:
        return {}


def sync_models(force: bool = False) -> dict:
    """
    Download models from S3 if they are newer than local.

    Returns dict with keys: synced (bool), reason (str), metadata (dict)
    """
    try:
        s3 = _get_s3_client()
    except Exception as e:
        logger.warning("[ModelSync] boto3/S3 unavailable: %s — using bundled models", e)
        return {"synced": False, "reason": f"S3 unavailable: {e}"}

    remote = _s3_metadata(s3)
    if not remote:
        logger.info("[ModelSync] No models in S3 — using bundled models")
        return {"synced": False, "reason": "No remote metadata"}

    local = _local_metadata()
    remote_ts = remote.get("trained_at", "")
    local_ts = local.get("trained_at", "")

    if not force and local_ts and local_ts >= remote_ts:
        logger.info("[ModelSync] Local models up-to-date (%s)", local_ts)
        return {"synced": False, "reason": "Already up-to-date", "metadata": local}

    logger.info("[ModelSync] Downloading newer models from S3 (remote=%s, local=%s)", remote_ts, local_ts)

    # Download all model files
    downloaded = 0
    for model_dir in MODEL_DIRS:
        local_dir = LOCAL_MODEL_DIR / model_dir
        local_dir.mkdir(parents=True, exist_ok=True)

        for filename in ["tfidf_vectorizer.pkl", "logreg_model.pkl", "label_mappings.json"]:
            s3_key = f"{S3_PREFIX}{model_dir}/{filename}"
            local_path = local_dir / filename
            try:
                s3.download_file(S3_BUCKET, s3_key, str(local_path))
                downloaded += 1
                logger.info("[ModelSync] Downloaded %s", s3_key)
            except Exception as e:
                logger.error("[ModelSync] Failed to download %s: %s", s3_key, e)

    # Save metadata locally
    meta_path = LOCAL_MODEL_DIR / METADATA_FILE
    with open(meta_path, "w") as f:
        json.dump(remote, f, indent=2)

    logger.info("[ModelSync] Synced %d files from S3", downloaded)
    return {"synced": True, "reason": f"Downloaded {downloaded} files", "metadata": remote}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    result = sync_models()
    print(json.dumps(result, indent=2))
```

**Step 2: Test locally**

Run: `cd /Users/pranavreddymogathala/2ndBRAINPRANAV-work/backend && python -m scripts.sync_models_from_s3`
Expected: `{"synced": false, "reason": "S3 unavailable: ..."}` or `{"synced": false, "reason": "No remote metadata"}` (no S3 bucket yet)

**Step 3: Commit**

```bash
git add backend/scripts/sync_models_from_s3.py
git commit -m "feat: add S3 model sync script for HIJ models"
```

---

### Task 2: Entrypoint.sh — Pull Models on Startup

**Files:**
- Modify: `backend/entrypoint.sh`

**Step 1: Add S3 sync before Flask starts**

Add this block after the seed step and before the gunicorn exec, around line 15:

```bash
# Sync HIJ models from S3 (non-blocking — falls back to bundled models)
echo "[Entrypoint] Syncing HIJ models from S3..."
python -m scripts.sync_models_from_s3 || echo "[Entrypoint] S3 model sync skipped (non-critical)"
```

**Step 2: Verify entrypoint still works**

Run: `cd /Users/pranavreddymogathala/2ndBRAINPRANAV-work/backend && bash entrypoint.sh` (ctrl+c after confirming it starts)

**Step 3: Commit**

```bash
git add backend/entrypoint.sh
git commit -m "feat: sync HIJ models from S3 on container startup"
```

---

### Task 3: Admin Refresh-Models Endpoint

**Files:**
- Modify: `backend/api/admin_routes.py` (add after train-hij-models endpoint, ~line 943)
- Modify: `backend/services/paper_type_detector.py` (add reload classmethod)
- Modify: `backend/services/ml_tier_predictor.py` (add reload function)

**Step 1: Add reload capability to PaperTypeDetector**

In `backend/services/paper_type_detector.py`, add a classmethod after `_ensure_ml_model_loaded` (~line 112):

```python
@classmethod
def reload_ml_model(cls):
    """Force reload ML model from disk (for hot-swap after S3 sync)."""
    cls._ml_tfidf = None
    cls._ml_logreg = None
    cls._ml_model_checked = False
    cls._ml_model_available = False
    cls._ensure_ml_model_loaded()
    return cls._ml_model_available
```

**Step 2: Add reload to MLTierPredictor**

In `backend/services/ml_tier_predictor.py`, add a function after `get_ml_tier_predictor` (~line 186):

```python
def reload_ml_tier_predictor():
    """Force reload tier predictor from disk (for hot-swap after S3 sync)."""
    global _instance
    _instance = None
    new = get_ml_tier_predictor()
    return new.is_available
```

**Step 3: Add admin endpoint**

In `backend/api/admin_routes.py`, add after the train-hij-models endpoint (~line 943):

```python
@admin_bp.route('/refresh-models', methods=['POST'])
@require_auth
def refresh_models():
    """
    Download latest models from S3 and hot-swap in memory.
    Super admin only. Zero downtime.

    POST /api/admin/refresh-models
    {"force": false}
    """
    db = get_db()
    try:
        user = db.query(User).filter(User.id == g.user_id).first()
        if not user or user.email not in SUPER_ADMIN_EMAILS:
            return jsonify({"success": False, "error": "Forbidden"}), 403

        data = request.get_json(silent=True) or {}
        force = data.get('force', False)

        # Step 1: Sync from S3
        from scripts.sync_models_from_s3 import sync_models
        sync_result = sync_models(force=force)

        # Step 2: Reload in-memory models
        from services.paper_type_detector import PaperTypeDetector
        from services.ml_tier_predictor import reload_ml_tier_predictor

        pt_available = PaperTypeDetector.reload_ml_model()
        tier_available = reload_ml_tier_predictor()

        return jsonify({
            "success": True,
            "s3_sync": sync_result,
            "models_reloaded": {
                "paper_type_detector": pt_available,
                "tier_predictor": tier_available,
            },
            "metadata": sync_result.get("metadata", {}),
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        db.close()
```

**Step 4: Test compilation**

Run: `cd /Users/pranavreddymogathala/2ndBRAINPRANAV-work/backend && python -c "from api.admin_routes import admin_bp; print('OK')"`

**Step 5: Commit**

```bash
git add backend/api/admin_routes.py backend/services/paper_type_detector.py backend/services/ml_tier_predictor.py
git commit -m "feat: add admin refresh-models endpoint for hot-swap from S3"
```

---

### Task 4: Parallel OpenAlex Fetcher

**Files:**
- Create: `backend/scripts/parallel_openalex_fetcher.py`

**Step 1: Write the parallel fetcher**

This replaces the single-threaded `generate_training_data` for large-scale runs. Key features:
- 8 worker threads with shared token-bucket rate limiter (10 req/s)
- Checkpointing every 10K papers (resume on restart)
- Deduplication via OpenAlex work ID set
- Progress logging every 1K papers

```python
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
```

**Step 2: Smoke test with small target**

Run: `cd /Users/pranavreddymogathala/2ndBRAINPRANAV-work/backend && python -m scripts.parallel_openalex_fetcher --target 100 --output /tmp/hij_test --workers 4`
Expected: Creates train.jsonl, val.jsonl, test.jsonl, summary.json in /tmp/hij_test

**Step 3: Commit**

```bash
git add backend/scripts/parallel_openalex_fetcher.py
git commit -m "feat: add parallel OpenAlex fetcher with checkpointing for 1M papers"
```

---

### Task 5: EC2 Training Script

**Files:**
- Create: `backend/scripts/ec2_train_and_upload.py`

**Step 1: Write the autonomous training script**

This is the script that runs on the EC2 spot instance. It:
1. Fetches 1M papers (parallel)
2. Trains both models
3. Validates against accuracy floor
4. Uploads to S3 (or marks as failed)
5. Sends SNS notification
6. Shuts down the instance

```python
"""
Autonomous HIJ training script for EC2 spot instances.

Run: python -m scripts.ec2_train_and_upload --target 1000000

Full pipeline: fetch → train → validate → upload → notify → shutdown
"""
import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

S3_BUCKET = os.getenv("HIJ_MODEL_BUCKET", "secondbrain-models")
S3_REGION = os.getenv("AWS_S3_REGION", "us-east-2")
SNS_TOPIC_ARN = os.getenv("HIJ_SNS_TOPIC_ARN", "")
PROMOTION_THRESHOLD = 0.02  # Must beat current F1 by this margin


def _get_s3_client():
    import boto3
    return boto3.client("s3", region_name=S3_REGION)


def _get_sns_client():
    import boto3
    return boto3.client("sns", region_name=S3_REGION)


def _send_notification(subject: str, message: str):
    """Send SNS email notification."""
    if not SNS_TOPIC_ARN:
        logger.warning("[Notify] No SNS_TOPIC_ARN set — skipping notification")
        return
    try:
        sns = _get_sns_client()
        sns.publish(TopicArn=SNS_TOPIC_ARN, Subject=subject[:100], Message=message)
        logger.info("[Notify] Sent: %s", subject)
    except Exception as e:
        logger.error("[Notify] Failed: %s", e)


def _get_current_metrics(s3) -> dict:
    """Read current active model metrics from S3."""
    try:
        resp = s3.get_object(Bucket=S3_BUCKET, Key="hij/active/metadata.json")
        return json.loads(resp["Body"].read().decode())
    except Exception:
        return {"paper_type_f1": 0.0, "tier_f1_macro": 0.0}


def _upload_models(s3, model_dir: Path, metadata: dict, prefix: str):
    """Upload model files and metadata to S3."""
    dirs = [
        ("paper_type_classifier/tfidf_primary", ["tfidf_vectorizer.pkl", "logreg_model.pkl", "label_mappings.json"]),
        ("tier_predictor/tfidf", ["tfidf_vectorizer.pkl", "logreg_model.pkl", "label_mappings.json"]),
    ]
    for subdir, files in dirs:
        for f in files:
            local_path = model_dir / subdir / f
            if local_path.exists():
                s3_key = f"{prefix}{subdir}/{f}"
                s3.upload_file(str(local_path), S3_BUCKET, s3_key)
                logger.info("[Upload] %s → s3://%s/%s", local_path.name, S3_BUCKET, s3_key)

    # Upload metadata
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=f"{prefix}metadata.json",
        Body=json.dumps(metadata, indent=2).encode(),
        ContentType="application/json",
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=int, default=1_000_000)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--no-shutdown", action="store_true", help="Don't shutdown after completion")
    args = parser.parse_args()

    start_time = time.time()
    backend_dir = Path(__file__).resolve().parent.parent
    data_dir = backend_dir / "data" / "hij_1m"
    model_dir = backend_dir / "models"
    model_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("HIJ 1M Training Pipeline — Starting")
    logger.info("Target: %d papers, Workers: %d", args.target, args.workers)
    logger.info("=" * 60)

    # ── Step 1: Fetch papers ─────────────────────────────────────
    logger.info("[Step 1/4] Fetching papers from OpenAlex...")
    try:
        from scripts.parallel_openalex_fetcher import fetch_papers_parallel
        fetch_papers_parallel(output_dir=data_dir, target_total=args.target, num_workers=args.workers)
    except Exception as e:
        msg = f"Data fetch failed: {e}"
        logger.error(msg)
        _send_notification("HIJ Training FAILED — Data Fetch", msg)
        sys.exit(1)

    # ── Step 2: Train models ─────────────────────────────────────
    logger.info("[Step 2/4] Training models...")
    try:
        from scripts.train_hij_models import train_paper_type_classifier, train_tier_predictor

        pt_metrics = train_paper_type_classifier(data_dir, model_dir)
        tier_metrics = train_tier_predictor(data_dir, model_dir)

        if not pt_metrics or not tier_metrics:
            raise ValueError("Training returned no metrics")

        logger.info("[Train] Paper type: acc=%.4f, F1=%.4f", pt_metrics["test_acc"], pt_metrics["test_f1"])
        logger.info("[Train] Tier:       acc=%.4f, F1=%.4f", tier_metrics["test_acc"], tier_metrics["test_f1"])
    except Exception as e:
        msg = f"Model training failed: {e}"
        logger.error(msg)
        _send_notification("HIJ Training FAILED — Training", msg)
        sys.exit(1)

    # ── Step 3: Validate against promotion gate ──────────────────
    logger.info("[Step 3/4] Validating against promotion gate...")
    s3 = _get_s3_client()
    current = _get_current_metrics(s3)
    current_pt_f1 = current.get("paper_type_f1", 0.0)
    current_tier_f1 = current.get("tier_f1_macro", 0.0)

    new_pt_f1 = pt_metrics["test_f1"]
    new_tier_f1 = tier_metrics["test_f1"]

    pt_pass = new_pt_f1 >= current_pt_f1 + PROMOTION_THRESHOLD
    tier_pass = new_tier_f1 >= current_tier_f1 + PROMOTION_THRESHOLD

    elapsed = round((time.time() - start_time) / 60, 1)

    metadata = {
        "version": f"v_{args.target}",
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "paper_count": args.target,
        "paper_type_f1": round(new_pt_f1, 4),
        "paper_type_acc": round(pt_metrics["test_acc"], 4),
        "tier_f1_macro": round(new_tier_f1, 4),
        "tier_acc": round(tier_metrics["test_acc"], 4),
        "previous_paper_type_f1": round(current_pt_f1, 4),
        "previous_tier_f1_macro": round(current_tier_f1, 4),
        "training_minutes": elapsed,
    }

    # ── Step 4: Upload to S3 ─────────────────────────────────────
    promoted = pt_pass and tier_pass

    if promoted:
        logger.info("[Promote] PASS — new models beat current by +%.2f threshold", PROMOTION_THRESHOLD)

        # Archive current active → previous
        try:
            for key_suffix in [
                "paper_type_classifier/tfidf_primary/tfidf_vectorizer.pkl",
                "paper_type_classifier/tfidf_primary/logreg_model.pkl",
                "paper_type_classifier/tfidf_primary/label_mappings.json",
                "tier_predictor/tfidf/tfidf_vectorizer.pkl",
                "tier_predictor/tfidf/logreg_model.pkl",
                "tier_predictor/tfidf/label_mappings.json",
                "metadata.json",
            ]:
                s3.copy_object(
                    Bucket=S3_BUCKET,
                    CopySource={"Bucket": S3_BUCKET, "Key": f"hij/active/{key_suffix}"},
                    Key=f"hij/previous/{key_suffix}",
                )
            logger.info("[Promote] Archived current models to hij/previous/")
        except Exception as e:
            logger.warning("[Promote] Archive failed (first run?): %s", e)

        metadata["promoted"] = True
        _upload_models(s3, model_dir, metadata, "hij/active/")
        subject = f"HIJ Training SUCCESS — Models Promoted (F1: {new_pt_f1:.3f}/{new_tier_f1:.3f})"
    else:
        logger.warning("[Promote] FAIL — did not beat threshold")
        logger.warning("  Paper type: %.4f vs %.4f (need +%.2f)", new_pt_f1, current_pt_f1, PROMOTION_THRESHOLD)
        logger.warning("  Tier:       %.4f vs %.4f (need +%.2f)", new_tier_f1, current_tier_f1, PROMOTION_THRESHOLD)
        metadata["promoted"] = False
        metadata["rejection_reason"] = f"pt_pass={pt_pass}, tier_pass={tier_pass}"
        _upload_models(s3, model_dir, metadata, "hij/failed/")
        subject = f"HIJ Training COMPLETE — Models NOT Promoted (F1: {new_pt_f1:.3f}/{new_tier_f1:.3f})"

    msg = json.dumps(metadata, indent=2)
    _send_notification(subject, msg)
    logger.info("[Done] Pipeline complete in %.1f minutes", elapsed)

    # Shutdown if on EC2 (not local dev)
    if not args.no_shutdown and os.path.exists("/sys/hypervisor/uuid"):
        logger.info("[Shutdown] EC2 detected — shutting down in 30 seconds...")
        os.system("sudo shutdown -h +1")


if __name__ == "__main__":
    main()
```

**Step 2: Test locally with tiny target**

Run: `cd /Users/pranavreddymogathala/2ndBRAINPRANAV-work/backend && python -m scripts.ec2_train_and_upload --target 100 --no-shutdown`
Expected: Fetches 100 papers, trains, prints metrics, skips S3/shutdown

**Step 3: Commit**

```bash
git add backend/scripts/ec2_train_and_upload.py
git commit -m "feat: add autonomous EC2 training script with S3 upload and SNS notifications"
```

---

### Task 6: EC2 User Data Bootstrap Script

**Files:**
- Create: `infra/hij-training-userdata.sh`

**Step 1: Write the EC2 user data script**

This is passed to EC2 `run-instances --user-data` and runs on boot.

```bash
#!/bin/bash
set -euo pipefail
exec > /var/log/hij-training.log 2>&1

echo "=== HIJ Training Bootstrap ==="
date

# Install system deps
yum update -y
yum install -y python3.12 python3.12-pip git

# Clone repo
cd /opt
git clone https://github.com/MrIDK-crypto/2ndBRAINPRANAV.git app
cd app/backend

# Install Python deps (only what's needed for training)
pip3.12 install scikit-learn requests boto3 numpy

# Set AWS credentials (passed via instance profile or env)
export HIJ_MODEL_BUCKET="${HIJ_MODEL_BUCKET:-secondbrain-models}"
export AWS_S3_REGION="${AWS_S3_REGION:-us-east-2}"
export HIJ_SNS_TOPIC_ARN="${HIJ_SNS_TOPIC_ARN}"

# Run training
echo "=== Starting HIJ Training ==="
python3.12 -m scripts.ec2_train_and_upload \
    --target "${HIJ_TARGET:-1000000}" \
    --workers 8

echo "=== Training Complete ==="
# Instance will self-terminate via the script
```

**Step 2: Commit**

```bash
mkdir -p infra
git add infra/hij-training-userdata.sh
git commit -m "feat: add EC2 user data bootstrap script for HIJ training"
```

---

### Task 7: Lambda Trigger Function

**Files:**
- Create: `infra/hij-training-lambda.py`

**Step 1: Write the Lambda function**

This Lambda launches an EC2 spot instance with the training user data script.

```python
"""
Lambda function to launch EC2 spot instance for HIJ model training.

Triggered by CloudWatch Events (weekly schedule) or manual invocation.
"""
import boto3
import json
import base64
import os

EC2_CLIENT = boto3.client("ec2", region_name="us-east-2")
SNS_CLIENT = boto3.client("sns", region_name="us-east-2")

# Configuration
INSTANCE_TYPE = "r5.xlarge"  # 16GB RAM, 4 vCPU
AMI_ID = os.environ.get("EC2_AMI_ID", "ami-0ea3405d2d2522162")  # Amazon Linux 2023 us-east-2
SUBNET_ID = os.environ.get("EC2_SUBNET_ID")
SECURITY_GROUP_ID = os.environ.get("EC2_SG_ID")
IAM_INSTANCE_PROFILE = os.environ.get("EC2_INSTANCE_PROFILE", "hij-training-role")
SNS_TOPIC_ARN = os.environ.get("HIJ_SNS_TOPIC_ARN", "")
S3_BUCKET = os.environ.get("HIJ_MODEL_BUCKET", "secondbrain-models")

USER_DATA_TEMPLATE = """#!/bin/bash
set -euo pipefail
exec > /var/log/hij-training.log 2>&1

echo "=== HIJ Training Bootstrap ==="
date

yum update -y
yum install -y python3.12 python3.12-pip git

cd /opt
git clone https://github.com/MrIDK-crypto/2ndBRAINPRANAV.git app
cd app/backend

pip3.12 install scikit-learn requests boto3 numpy

export HIJ_MODEL_BUCKET="{s3_bucket}"
export AWS_S3_REGION="us-east-2"
export HIJ_SNS_TOPIC_ARN="{sns_topic}"

python3.12 -m scripts.ec2_train_and_upload --target {target} --workers 8

echo "=== Training Complete ==="
"""


def handler(event, context):
    target = event.get("target_papers", 1_000_000)

    user_data = USER_DATA_TEMPLATE.format(
        s3_bucket=S3_BUCKET,
        sns_topic=SNS_TOPIC_ARN,
        target=target,
    )

    launch_spec = {
        "ImageId": AMI_ID,
        "InstanceType": INSTANCE_TYPE,
        "UserData": base64.b64encode(user_data.encode()).decode(),
        "InstanceMarketOptions": {
            "MarketType": "spot",
            "SpotOptions": {
                "SpotInstanceType": "one-time",
                "InstanceInterruptionBehavior": "terminate",
            },
        },
        "TagSpecifications": [{
            "ResourceType": "instance",
            "Tags": [
                {"Key": "Name", "Value": f"hij-training-{target}"},
                {"Key": "Project", "Value": "2ndBrain"},
                {"Key": "Purpose", "Value": "HIJ-model-training"},
            ],
        }],
        "MinCount": 1,
        "MaxCount": 1,
    }

    if SUBNET_ID:
        launch_spec["SubnetId"] = SUBNET_ID
    if SECURITY_GROUP_ID:
        launch_spec["SecurityGroupIds"] = [SECURITY_GROUP_ID]
    if IAM_INSTANCE_PROFILE:
        launch_spec["IamInstanceProfile"] = {"Name": IAM_INSTANCE_PROFILE}

    response = EC2_CLIENT.run_instances(**launch_spec)
    instance_id = response["Instances"][0]["InstanceId"]

    msg = f"Launched EC2 spot instance {instance_id} for HIJ training ({target} papers)"
    print(msg)

    if SNS_TOPIC_ARN:
        SNS_CLIENT.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject="HIJ Training Launched",
            Message=msg,
        )

    return {
        "statusCode": 200,
        "body": json.dumps({
            "instance_id": instance_id,
            "target_papers": target,
            "instance_type": INSTANCE_TYPE,
        }),
    }
```

**Step 2: Commit**

```bash
git add infra/hij-training-lambda.py
git commit -m "feat: add Lambda function to launch EC2 spot training instances"
```

---

### Task 8: AWS Infrastructure Setup (Manual Steps)

**This task is a checklist of AWS resources to create via console or CLI. Not code.**

**Step 1: Create S3 bucket**
```bash
aws s3 mb s3://secondbrain-models --region us-east-2
```

**Step 2: Upload current models as baseline**
```bash
cd /Users/pranavreddymogathala/2ndBRAINPRANAV-work/backend
# Upload current models
aws s3 sync models/paper_type_classifier/tfidf_primary/ s3://secondbrain-models/hij/active/paper_type_classifier/tfidf_primary/
aws s3 sync models/tier_predictor/tfidf/ s3://secondbrain-models/hij/active/tier_predictor/tfidf/

# Create metadata for current baseline
cat > /tmp/metadata.json << 'METAEOF'
{
  "version": "v_500",
  "trained_at": "2026-03-12T05:37:00Z",
  "paper_count": 500,
  "paper_type_f1": 0.80,
  "tier_f1_macro": 0.32,
  "promoted": true
}
METAEOF
aws s3 cp /tmp/metadata.json s3://secondbrain-models/hij/active/metadata.json
```

**Step 3: Create IAM role for EC2 training instance**
```bash
# Role needs: S3 read/write to secondbrain-models, SNS publish, EC2 terminate-self
aws iam create-role --role-name hij-training-role --assume-role-policy-document '{
  "Version": "2012-10-17",
  "Statement": [{"Effect": "Allow", "Principal": {"Service": "ec2.amazonaws.com"}, "Action": "sts:AssumeRole"}]
}'

# Attach policies (S3, SNS, EC2 self-terminate)
# Create inline policy with specific permissions
```

**Step 4: Create SNS topic + email subscription**
```bash
aws sns create-topic --name secondbrain-hij-training --region us-east-2
# Note the ARN
aws sns subscribe --topic-arn <ARN> --protocol email --notification-endpoint prmogathala@gmail.com
# Confirm email subscription
```

**Step 5: Create Lambda function**
```bash
cd /Users/pranavreddymogathala/2ndBRAINPRANAV-work
zip -j /tmp/hij-lambda.zip infra/hij-training-lambda.py

aws lambda create-function \
  --function-name hij-training-trigger \
  --runtime python3.12 \
  --handler hij-training-lambda.handler \
  --zip-file fileb:///tmp/hij-lambda.zip \
  --role <LAMBDA_ROLE_ARN> \
  --timeout 30 \
  --environment "Variables={HIJ_MODEL_BUCKET=secondbrain-models,HIJ_SNS_TOPIC_ARN=<SNS_ARN>,EC2_SUBNET_ID=<SUBNET>,EC2_SG_ID=<SG>,EC2_INSTANCE_PROFILE=hij-training-role}"
```

**Step 6: Create CloudWatch cron rule (weekly)**
```bash
aws events put-rule \
  --name hij-weekly-training \
  --schedule-expression "cron(0 2 ? * SUN *)" \
  --description "Weekly HIJ model retraining"

aws events put-targets \
  --rule hij-weekly-training \
  --targets "Id=hij-lambda,Arn=<LAMBDA_ARN>"
```

**Step 7: Add env vars to ECS task definition**

Add to the backend ECS task definition environment:
- `HIJ_MODEL_BUCKET=secondbrain-models`
- `AWS_S3_REGION=us-east-2`

**Step 8: Commit any remaining infra files**
```bash
git add -A && git commit -m "docs: add AWS infrastructure setup notes"
```

---

### Task 9: End-to-End Test

**Step 1: Test S3 sync locally**
```bash
cd /Users/pranavreddymogathala/2ndBRAINPRANAV-work/backend
python -m scripts.sync_models_from_s3
# Expected: Downloads models from S3 bucket
```

**Step 2: Test refresh-models endpoint on prod**
```bash
curl -X POST https://api.use2ndbrain.com/api/admin/refresh-models \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"force": true}'
# Expected: {"success": true, "s3_sync": {...}, "models_reloaded": {...}}
```

**Step 3: Test EC2 training script locally (tiny)**
```bash
python -m scripts.ec2_train_and_upload --target 200 --no-shutdown
# Expected: Fetches, trains, prints metrics, uploads to S3
```

**Step 4: Test Lambda trigger**
```bash
aws lambda invoke --function-name hij-training-trigger \
  --payload '{"target_papers": 500}' /tmp/lambda-output.json
cat /tmp/lambda-output.json
# Expected: instance_id in response, SNS email received
```

**Step 5: Monitor EC2 instance**
```bash
# Check instance status
aws ec2 describe-instances --filters "Name=tag:Purpose,Values=HIJ-model-training" \
  --query "Reservations[].Instances[].{Id:InstanceId,State:State.Name}"

# Check training log
aws ssm send-command --instance-ids <ID> \
  --document-name "AWS-RunShellScript" \
  --parameters commands="tail -50 /var/log/hij-training.log"
```

**Step 6: Verify models updated**
```bash
aws s3 ls s3://secondbrain-models/hij/active/metadata.json
aws s3 cp s3://secondbrain-models/hij/active/metadata.json - | python3 -m json.tool
```

**Step 7: Final commit**
```bash
git add -A && git commit -m "feat: HIJ 1M training pipeline complete"
```
