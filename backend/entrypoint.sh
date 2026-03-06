#!/bin/bash
set -e

echo "=== Starting 2ndBrain Backend ==="
echo "Timestamp: $(date)"
echo "DATABASE_URL set: ${DATABASE_URL:+yes}"
echo "JWT_SECRET_KEY set: ${JWT_SECRET_KEY:+yes}"

# Seed Reproducibility Archive (handles deduplication internally)
echo "=== Seeding Reproducibility Archive ==="
if python -m scripts.seed_reproducibility --clear 2>&1; then
    echo "=== Seeding completed successfully ==="
else
    echo "=== Seeding FAILED with exit code $? ==="
    echo "Continuing anyway (non-critical for app startup)..."
fi

echo "=== Starting gunicorn ==="
exec gunicorn --bind 0.0.0.0:$PORT --workers 4 --worker-class gevent --worker-connections 1000 --timeout 300 --graceful-timeout 30 --keep-alive 65 app_v2:app
