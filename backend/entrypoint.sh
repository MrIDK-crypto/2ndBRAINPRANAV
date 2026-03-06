#!/bin/bash
set -e

echo "=== Starting 2ndBrain Backend ==="

# Seed Reproducibility Archive (handles deduplication internally)
echo "Seeding Reproducibility Archive..."
python -m scripts.seed_reproducibility --clear || echo "Seeding skipped or failed (non-critical)"

echo "Starting gunicorn..."
exec gunicorn --bind 0.0.0.0:$PORT --workers 4 --worker-class gevent --worker-connections 1000 --timeout 300 --graceful-timeout 30 --keep-alive 65 app_v2:app
