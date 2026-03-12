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
