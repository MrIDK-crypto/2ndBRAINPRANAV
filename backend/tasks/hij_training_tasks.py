"""
Celery Tasks for HIJ (High Impact Journal) Model Training
==========================================================
Background tasks for generating training data from OpenAlex and training
the paper type classifier and journal tier predictor models.

Includes:
  - train_hij_models: Original 5K pipeline (single task)
  - fetch_hij_batch: Fetch one batch of papers → S3 (for 1M pipeline)
  - merge_hij_batches: Merge S3 batch files → train/val/test splits
  - train_hij_from_s3: Train models from merged S3 data → promote
  - build_hij_1m_chain(): Helper to build the full Celery chain
"""

import json
import os
import sys
import logging
import tempfile
import time
import uuid
from datetime import datetime, timezone

from celery_app import celery

logger = logging.getLogger(__name__)

S3_BUCKET = os.getenv("HIJ_MODEL_BUCKET", "secondbrain-models")
S3_REGION = os.getenv("AWS_S3_REGION", "us-east-2")
SNS_TOPIC_ARN = os.getenv("HIJ_SNS_TOPIC_ARN", "")
PROMOTION_THRESHOLD = 0.02

# Year ranges for each batch — non-overlapping to avoid duplicates
BATCH_CONFIGS = [
    {"index": 0, "year_range": "2024-2026", "target": 200000},
    {"index": 1, "year_range": "2022-2023", "target": 200000},
    {"index": 2, "year_range": "2020-2021", "target": 200000},
    {"index": 3, "year_range": "2019-2019", "target": 200000},
    {"index": 4, "year_range": "2018-2018", "target": 200000},
]


def _ensure_app_in_path():
    """Ensure /app is in sys.path — Celery prefork workers lose it after fork."""
    app_dir = '/app'
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)


def _s3_client():
    import boto3
    return boto3.client("s3", region_name=S3_REGION)


def _update_run_status(run_id, updates):
    """Read-modify-write status.json in S3 for a training run."""
    s3 = _s3_client()
    key = f"hij/training-runs/{run_id}/status.json"
    try:
        resp = s3.get_object(Bucket=S3_BUCKET, Key=key)
        status = json.loads(resp["Body"].read().decode())
    except Exception:
        status = {}
    status.update(updates)
    status["updated_at"] = datetime.now(timezone.utc).isoformat()
    s3.put_object(
        Bucket=S3_BUCKET, Key=key,
        Body=json.dumps(status, indent=2).encode(),
        ContentType="application/json",
    )
    return status


def _send_notification(subject, message):
    """Send SNS email notification."""
    if not SNS_TOPIC_ARN:
        logger.warning("[HIJ-1M] No SNS_TOPIC_ARN — skipping notification")
        return
    try:
        import boto3
        sns = boto3.client("sns", region_name=S3_REGION)
        sns.publish(TopicArn=SNS_TOPIC_ARN, Subject=subject[:100], Message=message)
        logger.info("[HIJ-1M] Sent notification: %s", subject)
    except Exception as e:
        logger.error("[HIJ-1M] Notification failed: %s", e)


@celery.task(
    bind=True,
    name='tasks.hij_training_tasks.train_hij_models',
    time_limit=10800,        # 3 hour hard limit
    soft_time_limit=10500,   # 2h55m soft limit (warning)
    max_retries=1,
)
def train_hij_models(self, target_papers=5000):
    """
    Full HIJ training pipeline: generate data from OpenAlex + train both models.

    Steps:
        1. Generate training data from OpenAlex (paper type + tier labels)
        2. Train Paper Type Classifier (TF-IDF + LogReg)
        3. Train Journal Tier Predictor (TF-IDF + LogReg)

    Args:
        target_papers: Target number of training papers to fetch (default 5000)

    Returns:
        dict with keys: data_generated, paper_type_metrics, tier_metrics, elapsed_seconds
    """
    _ensure_app_in_path()

    from pathlib import Path

    start_time = time.time()
    results = {
        'data_generated': False,
        'paper_type_metrics': None,
        'tier_metrics': None,
        'elapsed_seconds': 0,
    }

    # Resolve directories relative to backend/
    backend_dir = Path(__file__).resolve().parent.parent
    data_dir = backend_dir / 'data' / 'oncology_training'
    model_dir = backend_dir / 'models'

    # ── Step 1: Generate training data from OpenAlex ──────────────────
    logger.info('[HIJTask] Step 1/3: Generating training data from OpenAlex (target=%d)', target_papers)
    self.update_state(state='PROGRESS', meta={
        'current': 0, 'total': 3, 'percent': 0,
        'status': f'Generating training data ({target_papers} papers)...',
    })

    try:
        from scripts.generate_training_data import generate_training_data
        generate_training_data(data_dir, target_total=target_papers)
        results['data_generated'] = True
        logger.info('[HIJTask] Training data generated in %s', data_dir)
    except Exception as e:
        logger.error('[HIJTask] Data generation failed: %s', e, exc_info=True)
        results['data_generation_error'] = str(e)
        # If data already exists from a previous run, continue with training
        if not (data_dir / 'train.jsonl').exists():
            results['elapsed_seconds'] = round(time.time() - start_time, 1)
            return results

    # ── Step 2: Train Paper Type Classifier ───────────────────────────
    logger.info('[HIJTask] Step 2/3: Training Paper Type Classifier')
    self.update_state(state='PROGRESS', meta={
        'current': 1, 'total': 3, 'percent': 33,
        'status': 'Training paper type classifier...',
    })

    try:
        from scripts.train_hij_models import train_paper_type_classifier
        pt_metrics = train_paper_type_classifier(data_dir, model_dir)
        if pt_metrics:
            results['paper_type_metrics'] = {
                'test_accuracy': round(pt_metrics['test_acc'], 4),
                'test_f1_macro': round(pt_metrics['test_f1'], 4),
                'best_C': pt_metrics['best_c'],
            }
            logger.info(
                '[HIJTask] Paper type classifier: acc=%.4f, F1=%.4f',
                pt_metrics['test_acc'], pt_metrics['test_f1'],
            )
        else:
            logger.warning('[HIJTask] Paper type classifier returned no metrics (no data?)')
    except Exception as e:
        logger.error('[HIJTask] Paper type classifier training failed: %s', e, exc_info=True)
        results['paper_type_error'] = str(e)

    # ── Step 3: Train Tier Predictor ──────────────────────────────────
    logger.info('[HIJTask] Step 3/3: Training Journal Tier Predictor')
    self.update_state(state='PROGRESS', meta={
        'current': 2, 'total': 3, 'percent': 66,
        'status': 'Training tier predictor...',
    })

    try:
        from scripts.train_hij_models import train_tier_predictor
        tier_metrics = train_tier_predictor(data_dir, model_dir)
        if tier_metrics:
            results['tier_metrics'] = {
                'test_accuracy': round(tier_metrics['test_acc'], 4),
                'test_f1_macro': round(tier_metrics['test_f1'], 4),
                'best_C': tier_metrics['best_c'],
            }
            logger.info(
                '[HIJTask] Tier predictor: acc=%.4f, F1=%.4f',
                tier_metrics['test_acc'], tier_metrics['test_f1'],
            )
        else:
            logger.warning('[HIJTask] Tier predictor returned no metrics (no data?)')
    except Exception as e:
        logger.error('[HIJTask] Tier predictor training failed: %s', e, exc_info=True)
        results['tier_error'] = str(e)

    # ── Summary ───────────────────────────────────────────────────────
    elapsed = time.time() - start_time
    results['elapsed_seconds'] = round(elapsed, 1)

    logger.info(
        '[HIJTask] Pipeline complete in %.1fs (%.1f min). '
        'data=%s, paper_type=%s, tier=%s',
        elapsed, elapsed / 60,
        results['data_generated'],
        results['paper_type_metrics'] is not None,
        results['tier_metrics'] is not None,
    )

    return results


# ══════════════════════════════════════════════════════════════════════════════
# 1M BATCHED TRAINING PIPELINE (Celery chain + S3)
# ══════════════════════════════════════════════════════════════════════════════

@celery.task(
    bind=True,
    name='tasks.hij_training_tasks.fetch_hij_batch',
    time_limit=7200,         # 2 hour hard limit
    soft_time_limit=6900,    # 1h55m soft limit
    max_retries=1,
    autoretry_for=(),
)
def fetch_hij_batch(self, run_id, batch_index, batch_target, year_range):
    """
    Fetch one batch of papers from OpenAlex and upload to S3.

    Each batch uses a non-overlapping year range so no cross-batch dedup is needed.
    Output: s3://secondbrain-models/hij/training-runs/{run_id}/batch_{index}.jsonl
    """
    _ensure_app_in_path()
    from pathlib import Path

    logger.info("[HIJ-1M] Batch %d: Fetching %d papers (years %s)", batch_index, batch_target, year_range)
    self.update_state(state='PROGRESS', meta={
        'status': f'Fetching batch {batch_index} ({year_range}, target {batch_target})',
        'batch_index': batch_index,
        'run_id': run_id,
    })

    _update_run_status(run_id, {
        "status": "fetching",
        f"batch_{batch_index}": {"status": "in_progress", "started_at": datetime.now(timezone.utc).isoformat()},
    })

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)

        from scripts.parallel_openalex_fetcher import fetch_papers_parallel
        fetch_papers_parallel(
            output_dir=output_dir,
            target_total=batch_target,
            num_workers=8,
            year_range=year_range,
            split_output=False,
        )

        papers_file = output_dir / "papers.jsonl"
        if not papers_file.exists():
            raise RuntimeError(f"Batch {batch_index}: no papers.jsonl produced")

        paper_count = sum(1 for _ in open(papers_file))

        # Upload to S3
        s3 = _s3_client()
        s3_key = f"hij/training-runs/{run_id}/batch_{batch_index}.jsonl"
        s3.upload_file(str(papers_file), S3_BUCKET, s3_key)
        logger.info("[HIJ-1M] Batch %d: Uploaded %d papers → s3://%s/%s",
                     batch_index, paper_count, S3_BUCKET, s3_key)

        _update_run_status(run_id, {
            f"batch_{batch_index}": {
                "status": "complete",
                "papers": paper_count,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            },
        })

    return {"batch_index": batch_index, "papers": paper_count, "run_id": run_id}


@celery.task(
    bind=True,
    name='tasks.hij_training_tasks.merge_hij_batches',
    time_limit=3600,         # 1 hour hard limit
    soft_time_limit=3300,
    max_retries=1,
    autoretry_for=(),
)
def merge_hij_batches(self, run_id, num_batches=5):
    """
    Download all batch JSONL files from S3, merge with dedup, split 80/10/10,
    upload merged splits back to S3.
    """
    _ensure_app_in_path()
    from pathlib import Path
    import random
    from collections import Counter

    logger.info("[HIJ-1M] Merging %d batches for run %s", num_batches, run_id)
    self.update_state(state='PROGRESS', meta={
        'status': f'Merging {num_batches} batches',
        'run_id': run_id,
    })
    _update_run_status(run_id, {"status": "merging"})

    s3 = _s3_client()
    all_papers = []
    seen_titles = set()

    with tempfile.TemporaryDirectory() as tmpdir:
        for i in range(num_batches):
            s3_key = f"hij/training-runs/{run_id}/batch_{i}.jsonl"
            local_path = Path(tmpdir) / f"batch_{i}.jsonl"

            s3.download_file(S3_BUCKET, s3_key, str(local_path))

            batch_count = 0
            dupes = 0
            with open(local_path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    record = json.loads(line)
                    title = record.get("title", "").strip().lower()
                    if title in seen_titles:
                        dupes += 1
                        continue
                    seen_titles.add(title)
                    all_papers.append(record)
                    batch_count += 1

            logger.info("[HIJ-1M] Batch %d: %d papers loaded (%d dupes skipped)", i, batch_count, dupes)

        logger.info("[HIJ-1M] Total unique papers: %d", len(all_papers))

        # Shuffle and split 80/10/10
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
            local_path = Path(tmpdir) / filename
            with open(local_path, "w") as f:
                for r in records:
                    f.write(json.dumps(r) + "\n")

            s3_key = f"hij/training-runs/{run_id}/merged/{filename}"
            s3.upload_file(str(local_path), S3_BUCKET, s3_key)
            logger.info("[HIJ-1M] Uploaded %s: %d records", filename, len(records))

        # Summary
        summary = {
            "total_papers": len(all_papers),
            "splits": {k: len(v) for k, v in splits.items()},
            "paper_types": dict(Counter(p["paper_type"] for p in all_papers)),
            "tiers": dict(Counter(p["tier"] for p in all_papers)),
        }
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=f"hij/training-runs/{run_id}/merged/summary.json",
            Body=json.dumps(summary, indent=2).encode(),
            ContentType="application/json",
        )

        _update_run_status(run_id, {
            "status": "merged",
            "total_papers": len(all_papers),
            "merged_at": datetime.now(timezone.utc).isoformat(),
        })

    return {"total_papers": len(all_papers), "splits": {k: len(v) for k, v in splits.items()}, "run_id": run_id}


@celery.task(
    bind=True,
    name='tasks.hij_training_tasks.train_hij_from_s3',
    time_limit=7200,         # 2 hour hard limit
    soft_time_limit=6900,
    max_retries=1,
    autoretry_for=(),
)
def train_hij_from_s3(self, run_id):
    """
    Download merged training data from S3, train both models,
    validate against promotion gate, upload models to S3.
    """
    _ensure_app_in_path()
    from pathlib import Path

    logger.info("[HIJ-1M] Training models for run %s", run_id)
    self.update_state(state='PROGRESS', meta={
        'status': 'Training models from merged data',
        'run_id': run_id,
    })
    _update_run_status(run_id, {"status": "training"})

    s3 = _s3_client()

    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir) / "data"
        model_dir = Path(tmpdir) / "models"
        data_dir.mkdir()
        model_dir.mkdir()

        # Download merged splits
        for filename in ["train.jsonl", "val.jsonl", "test.jsonl"]:
            s3_key = f"hij/training-runs/{run_id}/merged/{filename}"
            s3.download_file(S3_BUCKET, s3_key, str(data_dir / filename))
            logger.info("[HIJ-1M] Downloaded %s", filename)

        # Train both models
        from scripts.train_hij_models import train_paper_type_classifier, train_tier_predictor

        pt_metrics = train_paper_type_classifier(data_dir, model_dir)
        tier_metrics = train_tier_predictor(data_dir, model_dir)

        if not pt_metrics or not tier_metrics:
            raise ValueError("Training returned no metrics")

        logger.info("[HIJ-1M] Paper type: acc=%.4f, F1=%.4f", pt_metrics["test_acc"], pt_metrics["test_f1"])
        logger.info("[HIJ-1M] Tier:       acc=%.4f, F1=%.4f", tier_metrics["test_acc"], tier_metrics["test_f1"])

        # Validate against promotion gate
        try:
            resp = s3.get_object(Bucket=S3_BUCKET, Key="hij/active/metadata.json")
            current = json.loads(resp["Body"].read().decode())
        except Exception:
            current = {"paper_type_f1": 0.0, "tier_f1_macro": 0.0}

        current_pt_f1 = current.get("paper_type_f1", 0.0)
        current_tier_f1 = current.get("tier_f1_macro", 0.0)
        new_pt_f1 = pt_metrics["test_f1"]
        new_tier_f1 = tier_metrics["test_f1"]

        pt_pass = new_pt_f1 >= current_pt_f1 + PROMOTION_THRESHOLD
        tier_pass = new_tier_f1 >= current_tier_f1 + PROMOTION_THRESHOLD
        promoted = pt_pass and tier_pass

        metadata = {
            "version": "v_1m_batched",
            "run_id": run_id,
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "paper_type_f1": round(new_pt_f1, 4),
            "paper_type_acc": round(pt_metrics["test_acc"], 4),
            "tier_f1_macro": round(new_tier_f1, 4),
            "tier_acc": round(tier_metrics["test_acc"], 4),
            "previous_paper_type_f1": round(current_pt_f1, 4),
            "previous_tier_f1_macro": round(current_tier_f1, 4),
            "promoted": promoted,
        }

        # Upload models
        model_files = [
            ("paper_type_classifier/tfidf_primary", ["tfidf_vectorizer.pkl", "logreg_model.pkl", "label_mappings.json"]),
            ("tier_predictor/tfidf", ["tfidf_vectorizer.pkl", "logreg_model.pkl", "label_mappings.json"]),
        ]

        if promoted:
            logger.info("[HIJ-1M] PROMOTED — new models beat current by +%.2f threshold", PROMOTION_THRESHOLD)

            # Archive current active → previous
            try:
                for subdir, files in model_files:
                    for f in files:
                        s3.copy_object(
                            Bucket=S3_BUCKET,
                            CopySource={"Bucket": S3_BUCKET, "Key": f"hij/active/{subdir}/{f}"},
                            Key=f"hij/previous/{subdir}/{f}",
                        )
                s3.copy_object(
                    Bucket=S3_BUCKET,
                    CopySource={"Bucket": S3_BUCKET, "Key": "hij/active/metadata.json"},
                    Key="hij/previous/metadata.json",
                )
                logger.info("[HIJ-1M] Archived current → hij/previous/")
            except Exception as e:
                logger.warning("[HIJ-1M] Archive failed (first run?): %s", e)

            prefix = "hij/active/"
            subject = f"HIJ 1M Training SUCCESS — Promoted (PT F1: {new_pt_f1:.3f}, Tier F1: {new_tier_f1:.3f})"
        else:
            logger.warning("[HIJ-1M] NOT promoted: pt_pass=%s, tier_pass=%s", pt_pass, tier_pass)
            metadata["rejection_reason"] = f"pt_pass={pt_pass}, tier_pass={tier_pass}"
            prefix = "hij/failed/"
            subject = f"HIJ 1M Training — NOT Promoted (PT F1: {new_pt_f1:.3f}, Tier F1: {new_tier_f1:.3f})"

        # Upload model files
        for subdir, files in model_files:
            for f in files:
                local_path = model_dir / subdir / f
                if local_path.exists():
                    s3.upload_file(str(local_path), S3_BUCKET, f"{prefix}{subdir}/{f}")

        # Upload metadata
        s3.put_object(
            Bucket=S3_BUCKET, Key=f"{prefix}metadata.json",
            Body=json.dumps(metadata, indent=2).encode(),
            ContentType="application/json",
        )

        _send_notification(subject, json.dumps(metadata, indent=2))

        _update_run_status(run_id, {
            "status": "complete" if promoted else "complete_not_promoted",
            "promoted": promoted,
            "metrics": metadata,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        })

    return metadata


# ── Chain builder ─────────────────────────────────────────────────────────────

def build_hij_1m_chain(run_id=None, resume_from_batch=0):
    """
    Build a Celery chain for the full 1M training pipeline.

    Args:
        run_id: Unique run identifier (auto-generated if None)
        resume_from_batch: Skip batches before this index (for resume)

    Returns:
        (run_id, chain) tuple — call chain.apply_async() to start
    """
    from celery import chain

    if not run_id:
        run_id = f"hij-1m-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"

    # Initialize status
    _update_run_status(run_id, {
        "run_id": run_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "status": "queued",
        "total_target": sum(b["target"] for b in BATCH_CONFIGS),
        "num_batches": len(BATCH_CONFIGS),
        "resume_from": resume_from_batch,
    })

    # Build chain: fetch batches → merge → train
    tasks = []
    for cfg in BATCH_CONFIGS:
        if cfg["index"] < resume_from_batch:
            continue
        tasks.append(
            fetch_hij_batch.si(run_id, cfg["index"], cfg["target"], cfg["year_range"])
        )

    tasks.append(merge_hij_batches.si(run_id, len(BATCH_CONFIGS)))
    tasks.append(train_hij_from_s3.si(run_id))

    return run_id, chain(*tasks)
