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
