#!/bin/bash
exec > /var/log/hij-training.log 2>&1
set -euxo pipefail

echo "=== HIJ Training Bootstrap ==="
date

# AL2023 ships python3.9; install 3.12 from extras
dnf install -y python3.12 python3.12-pip git

# Clone repo
cd /opt
git clone https://github.com/MrIDK-crypto/2ndBRAINPRANAV.git app
cd app/backend

# Install Python deps (only what's needed for training)
python3.12 -m pip install scikit-learn requests boto3 numpy

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
