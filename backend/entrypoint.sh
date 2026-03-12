#!/bin/bash
set -e

echo "=== Starting 2ndBrain Backend ==="
echo "Timestamp: $(date)"
echo "DATABASE_URL set: ${DATABASE_URL:+yes}"
echo "JWT_SECRET_KEY set: ${JWT_SECRET_KEY:+yes}"

# Seed Reproducibility Archive
# NOTE: Removed --clear flag to preserve user-submitted experiments
# Deduplication handles skipping existing experiments
# Use /api/reproducibility/admin/seed endpoint to force a full re-seed if needed
echo "=== Ensuring Reproducibility Archive categories ==="
if python -m scripts.seed_reproducibility 2>&1; then
    echo "=== Seeding completed successfully ==="
else
    echo "=== Seeding FAILED with exit code $? ==="
    echo "Continuing anyway (non-critical for app startup)..."
fi

# Sync HIJ models from S3 (non-blocking — falls back to bundled models)
echo "=== Syncing HIJ models from S3 ==="
if python -m scripts.sync_models_from_s3 2>&1; then
    echo "=== Model sync completed ==="
else
    echo "=== Model sync skipped (non-critical) ==="
fi

echo "=== Starting gunicorn ==="
exec gunicorn --bind 0.0.0.0:$PORT --workers 4 --worker-class gevent --worker-connections 1000 --timeout 300 --graceful-timeout 30 --keep-alive 65 app_v2:app
