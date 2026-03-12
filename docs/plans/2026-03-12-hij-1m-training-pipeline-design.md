# HIJ 1M-Paper Training Pipeline — Design Document

**Date:** 2026-03-12
**Status:** Approved

---

## Problem

Current HIJ models are trained on 500 papers (locally) and 5K papers (server). The tier predictor has poor macro F1 (0.32) due to class imbalance — almost all training data is Tier1. Scaling to 1M papers will fix class balance and significantly improve both models.

**Constraints:**
- Zero downtime — existing models must keep serving during training
- Fully autonomous — user won't be around to monitor
- No architecture change — keep TF-IDF + LogReg (scales linearly)

---

## Architecture

```
CloudWatch Cron (weekly or manual trigger)
    → Lambda trigger
        → Launch EC2 spot instance (r5.xlarge, 16GB, 4 vCPU)
            → Fetch 1M papers from OpenAlex (8 parallel threads, ~3-4 hrs)
            → Train paper_type + tier models (~1-2 hrs)
            → Validate against accuracy floor (must beat current F1 by +2%)
            → If pass: upload to S3 active/, archive old to previous/
            → If fail: upload to S3 failed/, keep old active
            → SNS notification (success/fail + metrics)
            → Self-terminate

ECS Web Server:
    → On startup: pull latest models from S3 if newer
    → Admin endpoint: POST /api/admin/refresh-models (hot-swap without restart)
```

---

## Components

### 1. EC2 Spot Training Job

- **Instance:** r5.xlarge (16GB RAM, 4 vCPU, ~$0.03/hr spot)
- **AMI:** Amazon Linux 2023 with Python 3.12
- **User data script** bootstraps: clone repo, install deps, run training
- **Parallelized OpenAlex fetching:** 8 worker threads with shared rate limiter (10 req/s total)
- **Checkpointing:** Every 10K papers, save progress to local disk. On resume, skip already-fetched papers by tracking OpenAlex cursor positions per query
- **Total runtime:** ~5-6 hours (fetch + train + upload)
- **Auto-terminates:** `shutdown -h now` at end of script
- **Spot interruption handling:** Checkpoint saved, can resume from last checkpoint on new instance

### 2. Blue-Green Model Swap

- Train new models to `/tmp/hij_new/` on EC2 instance
- Run evaluation on held-out test set (10% of data = 100K papers)
- **Promotion gates:**
  - Paper type macro F1 >= current F1 + 0.02
  - Tier macro F1 >= current F1 + 0.02
- **If pass:** Upload to `s3://secondbrain-models/hij/active/`, copy current active to `previous/`
- **If fail:** Upload to `s3://secondbrain-models/hij/failed/`, keep old active
- **Either way:** SNS email with full metrics comparison

### 3. S3 Model Storage Layout

```
s3://secondbrain-models/hij/
├── active/
│   ├── paper_type_classifier/
│   │   ├── tfidf_vectorizer.pkl
│   │   ├── logreg_model.pkl
│   │   └── label_mappings.json
│   ├── tier_predictor/
│   │   ├── tfidf_vectorizer.pkl
│   │   ├── logreg_model.pkl
│   │   └── label_mappings.json
│   └── metadata.json              # version, date, metrics, paper_count
├── previous/                       # rollback copy
└── failed/                         # failed attempts for inspection
```

**metadata.json example:**
```json
{
  "version": "v2_1m",
  "trained_at": "2026-03-15T04:30:00Z",
  "paper_count": 1000000,
  "paper_type_f1": 0.93,
  "tier_f1_macro": 0.82,
  "previous_paper_type_f1": 0.80,
  "previous_tier_f1_macro": 0.32,
  "promoted": true
}
```

### 4. ECS Integration

**On startup (entrypoint.sh):**
- Run `python -m scripts.sync_models_from_s3` before starting Flask
- Checks S3 `metadata.json` timestamp vs local `metadata.json`
- Downloads if S3 is newer
- Falls back to bundled models if S3 unreachable

**Admin endpoint:**
- `POST /api/admin/refresh-models` — downloads from S3, validates files, reloads in-memory singletons
- Clears class-level caches on `PaperTypeDetector._ml_tfidf/logreg` and `MLTierPredictor._instance`
- Returns old vs new metrics comparison
- Zero downtime: old model serves until new one is fully loaded, then atomic swap

### 5. Monitoring & Alerts

- **SNS topic:** `secondbrain-hij-training`
- **Email to:** prmogathala@gmail.com
- **Alerts on:**
  - Training complete (with accuracy metrics + old vs new comparison)
  - Training failed (with error details)
  - Spot interruption (checkpoint saved, needs manual re-trigger)
  - Model promotion decision (promoted or rejected with reasons)

### 6. Data Generation — Parallel OpenAlex Fetcher

**Current:** Single-threaded, 0.11s delay, ~30 hrs for 1M papers
**New:** 8 worker threads, shared token-bucket rate limiter (10 req/s), ~3-4 hrs

Each thread handles a different field/type combination:
- 8 fields × 5 paper types = 40 query combinations
- Thread pool dispatches queries, each fetches via cursor pagination
- Rate limiter ensures total requests stay under 10/s (OpenAlex polite pool)
- Results written to per-thread temp files, merged at end

**Checkpointing:**
- Progress file tracks: query_key → last_cursor, papers_fetched
- On restart, each query resumes from its last cursor
- Deduplication via OpenAlex work ID set (in-memory, ~40MB for 1M IDs)

---

## Time Estimates

| Step | Duration |
|------|----------|
| EC2 launch + bootstrap | ~5 min |
| OpenAlex fetch (1M papers, 8 threads) | ~3-4 hrs |
| Data validation + train/val/test split | ~10 min |
| TF-IDF vectorization (1M docs) | ~30 min |
| Paper type classifier training (grid search) | ~30-45 min |
| Tier predictor training (grid search) | ~30-45 min |
| Evaluation + S3 upload | ~5 min |
| **Total** | **~5-6 hours** |

## Cost Estimate

| Resource | Cost |
|----------|------|
| EC2 spot r5.xlarge × 6 hrs | ~$0.18 |
| S3 storage (few MB) | < $0.01/month |
| SNS emails | Free tier |
| Lambda invocations | Free tier |
| **Per run total** | **~$0.20** |
| **Monthly (weekly schedule)** | **~$0.80** |

## Expected Accuracy

| Metric | 500 papers | 1M papers (projected) |
|--------|-----------|----------------------|
| Paper type macro F1 | 0.80 | 0.92-0.95 |
| Tier accuracy | 0.93 (imbalanced) | 0.88-0.92 |
| Tier macro F1 | 0.32 | 0.80-0.85 |

---

## What Stays The Same

- TF-IDF + LogReg architecture (no model change)
- Same .pkl + label_mappings.json file format
- Same inference code in paper_type_detector.py and ml_tier_predictor.py
- Same Celery task for quick small retrains still works
- Existing models serve until 1M model passes validation gate

## Implementation Order

1. S3 bucket + model sync script (ECS can pull models)
2. Entrypoint.sh modification (pull on startup)
3. Admin refresh-models endpoint (hot-swap)
4. Parallel OpenAlex fetcher with checkpointing
5. EC2 training script (fetch → train → validate → upload → notify)
6. Lambda + CloudWatch cron trigger
7. SNS topic + email subscription
8. Test full pipeline end-to-end
