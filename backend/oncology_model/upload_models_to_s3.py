"""
Upload Trained Oncology Models to S3

Uploads model weights, tokenizers, label mappings, and training metrics
to an S3 bucket for deployment.

Usage:
    python -m oncology_model.upload_models_to_s3 \
        --model_dir models/oncology \
        --bucket secondbrain-oncology-models

    # With custom prefix:
    python -m oncology_model.upload_models_to_s3 \
        --model_dir models/oncology \
        --bucket secondbrain-oncology-models \
        --prefix v2.0

    # Dry run:
    python -m oncology_model.upload_models_to_s3 \
        --model_dir models/oncology \
        --bucket secondbrain-oncology-models \
        --dry_run
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Files that should be uploaded for each model
EXPECTED_FILES = {
    "subfield_classifier": [
        "best_model.pt",
        "label_mappings.json",
        "training_metrics.json",
        "tokenizer/tokenizer_config.json",
        "tokenizer/vocab.txt",
        "tokenizer/special_tokens_map.json",
    ],
    "tier_predictor": [
        "best_model.pt",
        "label_mappings.json",
        "training_metrics.json",
        "tokenizer/tokenizer_config.json",
        "tokenizer/vocab.txt",
        "tokenizer/special_tokens_map.json",
    ],
    "paper_type_classifier": [
        "label_mappings.json",
        "training_metrics.json",
        "tfidf_primary/tfidf_vectorizer.pkl",
        "tfidf_primary/logreg_model.pkl",
        "tfidf_primary/label_mappings.json",
    ],
}

# Optional files (uploaded if present)
OPTIONAL_PATTERNS = [
    "baseline/",
    "distilbert_comparison/",
    "*.log",
]


def get_s3_client():
    """Create and return an S3 client."""
    try:
        import boto3
    except ImportError:
        logger.error("boto3 is required: pip install boto3")
        sys.exit(1)
    return boto3.client("s3")


def verify_model_dir(model_dir: str) -> dict:
    """
    Verify the model directory structure and return found files.

    Returns dict of {model_name: [found_files]}
    """
    found = {}
    missing = {}

    for model_name, expected in EXPECTED_FILES.items():
        model_path = os.path.join(model_dir, model_name)
        found_files = []
        missing_files = []

        for rel_file in expected:
            full_path = os.path.join(model_path, rel_file)
            if os.path.exists(full_path):
                found_files.append(rel_file)
            else:
                missing_files.append(rel_file)

        found[model_name] = found_files
        if missing_files:
            missing[model_name] = missing_files

    return found, missing


def collect_all_files(model_dir: str) -> list:
    """
    Collect all files in the model directory for upload.

    Returns list of (local_path, s3_key_suffix) tuples.
    """
    files = []
    model_dir = os.path.abspath(model_dir)

    for root, dirs, filenames in os.walk(model_dir):
        # Skip __pycache__ and hidden directories
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]

        for filename in filenames:
            if filename.startswith("."):
                continue

            local_path = os.path.join(root, filename)
            # Relative path from model_dir
            rel_path = os.path.relpath(local_path, model_dir)
            files.append((local_path, rel_path))

    return files


def format_size(size_bytes: int) -> str:
    """Format bytes into human-readable size."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def upload_to_s3(
    model_dir: str,
    bucket: str,
    prefix: str = "",
    dry_run: bool = False,
    skip_verification: bool = False,
):
    """
    Upload all model files to S3.

    Args:
        model_dir: Local directory containing trained models
        bucket: S3 bucket name
        prefix: Optional prefix/version within the bucket
        dry_run: If True, list files without uploading
        skip_verification: If True, skip checking for expected files
    """
    model_dir = os.path.abspath(model_dir)
    logger.info(f"Model directory: {model_dir}")
    logger.info(f"S3 destination: s3://{bucket}/{prefix}")

    # Verify directory exists
    if not os.path.isdir(model_dir):
        logger.error(f"Model directory not found: {model_dir}")
        sys.exit(1)

    # Verify model structure
    if not skip_verification:
        logger.info("\nVerifying model directory structure...")
        found, missing = verify_model_dir(model_dir)

        for model_name, files in found.items():
            if files:
                logger.info(f"  {model_name}: {len(files)} expected files found")

        has_critical_missing = False
        for model_name, files in missing.items():
            for f in files:
                logger.warning(f"  {model_name}: MISSING {f}")
                has_critical_missing = True

        if has_critical_missing:
            logger.warning(
                "\nSome expected files are missing. Use --skip_verification to upload anyway."
            )
            if not dry_run:
                response = input("Continue with upload? (y/N): ").strip().lower()
                if response != "y":
                    logger.info("Upload cancelled.")
                    return

    # Collect all files
    files = collect_all_files(model_dir)
    total_size = sum(os.path.getsize(f[0]) for f in files)

    logger.info(f"\nFiles to upload: {len(files)}")
    logger.info(f"Total size: {format_size(total_size)}")

    if dry_run:
        logger.info("\n--- DRY RUN (no files will be uploaded) ---")
        for local_path, rel_path in sorted(files, key=lambda x: x[1]):
            size = format_size(os.path.getsize(local_path))
            s3_key = f"{prefix}/{rel_path}" if prefix else rel_path
            logger.info(f"  {s3_key} ({size})")
        logger.info(f"\nTotal: {len(files)} files, {format_size(total_size)}")
        return

    # Upload
    s3 = get_s3_client()
    uploaded = 0
    failed = 0
    start_time = time.time()

    logger.info("\nUploading...")
    for i, (local_path, rel_path) in enumerate(files, 1):
        s3_key = f"{prefix}/{rel_path}" if prefix else rel_path
        size = os.path.getsize(local_path)

        # Determine content type
        content_type = "application/octet-stream"
        if rel_path.endswith(".json"):
            content_type = "application/json"
        elif rel_path.endswith(".txt"):
            content_type = "text/plain"
        elif rel_path.endswith(".pkl"):
            content_type = "application/x-pickle"

        try:
            extra_args = {"ContentType": content_type}
            s3.upload_file(local_path, bucket, s3_key, ExtraArgs=extra_args)
            uploaded += 1
            logger.info(f"  [{i}/{len(files)}] Uploaded {s3_key} ({format_size(size)})")
        except Exception as e:
            failed += 1
            logger.error(f"  [{i}/{len(files)}] FAILED {s3_key}: {e}")

    elapsed = time.time() - start_time
    logger.info(f"\nUpload complete in {elapsed:.1f}s")
    logger.info(f"  Uploaded: {uploaded}")
    logger.info(f"  Failed:   {failed}")
    logger.info(f"  Total:    {format_size(total_size)}")

    # Create/update manifest
    manifest = {
        "upload_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "bucket": bucket,
        "prefix": prefix,
        "total_files": uploaded,
        "total_size_bytes": total_size,
        "models": {},
    }

    for model_name in EXPECTED_FILES:
        metrics_path = os.path.join(model_dir, model_name, "training_metrics.json")
        if os.path.exists(metrics_path):
            with open(metrics_path, "r") as f:
                metrics = json.load(f)
            manifest["models"][model_name] = {
                "test_accuracy": metrics.get("test_accuracy"),
                "test_f1_macro": metrics.get("test_f1_macro"),
                "best_epoch": metrics.get("best_epoch"),
            }

    # Upload manifest
    manifest_key = f"{prefix}/manifest.json" if prefix else "manifest.json"
    try:
        s3.put_object(
            Bucket=bucket,
            Key=manifest_key,
            Body=json.dumps(manifest, indent=2),
            ContentType="application/json",
        )
        logger.info(f"\nManifest uploaded: s3://{bucket}/{manifest_key}")
    except Exception as e:
        logger.error(f"Failed to upload manifest: {e}")

    logger.info(f"\nModels available at: s3://{bucket}/{prefix}")


def main():
    parser = argparse.ArgumentParser(description="Upload Oncology Models to S3")
    parser.add_argument(
        "--model_dir",
        type=str,
        required=True,
        help="Local directory containing trained model subdirectories",
    )
    parser.add_argument(
        "--bucket",
        type=str,
        default="secondbrain-oncology-models",
        help="S3 bucket name (default: secondbrain-oncology-models)",
    )
    parser.add_argument(
        "--prefix",
        type=str,
        default="",
        help="Optional prefix/version within the bucket (e.g., 'v1.0', '2026-03-10')",
    )
    parser.add_argument(
        "--dry_run",
        action="store_true",
        help="List files without uploading",
    )
    parser.add_argument(
        "--skip_verification",
        action="store_true",
        help="Skip verification of expected model files",
    )
    args = parser.parse_args()

    upload_to_s3(
        model_dir=args.model_dir,
        bucket=args.bucket,
        prefix=args.prefix,
        dry_run=args.dry_run,
        skip_verification=args.skip_verification,
    )


if __name__ == "__main__":
    main()
