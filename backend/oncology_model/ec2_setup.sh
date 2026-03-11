#!/bin/bash
# EC2 Setup Script for Oncology Model Training
# Run this on the g4dn.xlarge Deep Learning AMI instance
# Usage: bash ec2_setup.sh

set -e

echo "========================================="
echo "Oncology Model Training Pipeline Setup"
echo "========================================="

# 1. Install system deps
echo "[1/7] Installing system dependencies..."
sudo apt-get update -qq
sudo apt-get install -y -qq git python3-pip python3-venv

# 2. Clone the repo
echo "[2/7] Cloning repository..."
cd /home/ubuntu
if [ -d "2ndBRAINPRANAV-work" ]; then
    cd 2ndBRAINPRANAV-work && git pull
else
    git clone https://github.com/MrIDK-crypto/2ndBRAINPRANAV.git 2ndBRAINPRANAV-work
    cd 2ndBRAINPRANAV-work
fi

# 3. Create venv and install dependencies
echo "[3/7] Setting up Python environment..."
python3 -m venv /home/ubuntu/onco_venv
source /home/ubuntu/onco_venv/bin/activate

pip install --upgrade pip
pip install requests transformers torch scikit-learn numpy pandas tqdm boto3 joblib

# 4. Download oncology papers from OpenAlex (~19hrs for 1M)
echo "[4/7] Starting OpenAlex data download..."
echo "This will download ~1M oncology papers. ETA: ~19 hours."
mkdir -p /tmp/oncology_data
python3 -m backend.oncology_model.download_openalex \
    --output-dir /tmp/oncology_data \
    --target 1000000 \
    2>&1 | tee /tmp/oncology_download.log

# 5. Enrich with PubMed data
echo "[5/7] Enriching with PubMed data..."
python3 -m backend.oncology_model.download_pubmed \
    --input_dir /tmp/oncology_data \
    --output_dir /tmp/oncology_data/enriched \
    2>&1 | tee /tmp/pubmed_enrich.log

# 6. Prepare training data
echo "[6/7] Preparing training data..."
python3 -m backend.oncology_model.prepare_training_data \
    --input_dir /tmp/oncology_data/enriched \
    --output_dir /tmp/oncology_data/training \
    2>&1 | tee /tmp/prepare_data.log

# 7. Train all models
echo "[7/7] Training models..."

echo "--- Training sub-field classifier ---"
python3 -m backend.oncology_model.train_subfield_classifier \
    --data_dir /tmp/oncology_data/training \
    --output_dir /tmp/oncology_models/subfield \
    --epochs 3 --batch_size 32 \
    2>&1 | tee /tmp/train_subfield.log

echo "--- Training tier predictor ---"
python3 -m backend.oncology_model.train_tier_predictor \
    --data_dir /tmp/oncology_data/training \
    --output_dir /tmp/oncology_models/tier \
    --epochs 3 --batch_size 32 \
    2>&1 | tee /tmp/train_tier.log

echo "--- Training paper type classifier ---"
python3 -m backend.oncology_model.train_paper_type \
    --data_dir /tmp/oncology_data/training \
    --output_dir /tmp/oncology_models/paper_type \
    2>&1 | tee /tmp/train_paper_type.log

# 8. Upload models to S3
echo "Uploading models to S3..."
python3 -m backend.oncology_model.upload_models_to_s3 \
    --model_dir /tmp/oncology_models \
    --bucket secondbrain-oncology-models \
    2>&1 | tee /tmp/upload_s3.log

echo "========================================="
echo "DONE! Models uploaded to S3."
echo "========================================="
echo "Check s3://secondbrain-oncology-models/"
echo "Logs in /tmp/*.log"
