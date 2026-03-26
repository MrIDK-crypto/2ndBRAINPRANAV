"""
Azure OpenAI Fine-tuning for Protocol Domain Classification
============================================================
Uses Azure OpenAI's fine-tuning API to train a custom GPT model
for protocol domain classification (plant_biology, oncology, neurology).

This runs on Azure's infrastructure (no local GPU needed).
"""

import os
import json
import time
import logging
from typing import List, Dict, Tuple
from collections import Counter
from dotenv import load_dotenv
from openai import AzureOpenAI

from . import CORPUS_DIR, MODELS_DIR

# Load environment
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Azure OpenAI Configuration
AZURE_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "https://secondbrain-resource.openai.azure.com/")
AZURE_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_API_VERSION = os.getenv("AZURE_API_VERSION", "2024-05-01-preview")

# Domains
TARGET_DOMAINS = ['plant_biology', 'oncology', 'neurology', 'biology']


def load_protocol_data() -> List[Dict]:
    """Load all protocols from unified corpus."""
    protocols = []
    corpus_file = os.path.join(CORPUS_DIR, 'unified_protocols.jsonl')

    if not os.path.exists(corpus_file):
        logger.error(f"Corpus file not found: {corpus_file}")
        return protocols

    with open(corpus_file, 'r') as f:
        for line in f:
            if line.strip():
                try:
                    protocols.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    logger.info(f"Loaded {len(protocols)} protocols")
    return protocols


def prepare_training_data(protocols: List[Dict]) -> Tuple[str, str]:
    """
    Prepare data in Azure OpenAI fine-tuning format.
    Returns paths to training and validation JSONL files.
    """
    training_examples = []

    for p in protocols:
        domain = p.get('domain', 'biology')
        if domain not in TARGET_DOMAINS:
            domain = 'biology'

        # Get text content (limited to avoid token issues)
        text = ""
        if p.get('title'):
            text += p['title'] + "\n"
        if p.get('abstract'):
            text += p['abstract'][:500] + "\n"
        if p.get('raw_text'):
            text += p['raw_text'][:1000]

        text = text.strip()
        if len(text) < 50:
            continue

        # Azure OpenAI fine-tuning format (chat completion style)
        example = {
            "messages": [
                {
                    "role": "system",
                    "content": "You are a scientific protocol classifier. Classify protocols into: plant_biology, oncology, neurology, or biology (general)."
                },
                {
                    "role": "user",
                    "content": f"Classify this protocol:\n\n{text[:1500]}"
                },
                {
                    "role": "assistant",
                    "content": domain
                }
            ]
        }
        training_examples.append(example)

    # Shuffle and split
    import random
    random.shuffle(training_examples)

    split_idx = int(len(training_examples) * 0.9)
    train_data = training_examples[:split_idx]
    val_data = training_examples[split_idx:]

    logger.info(f"Training examples: {len(train_data)}")
    logger.info(f"Validation examples: {len(val_data)}")

    # Save to files
    train_file = os.path.join(MODELS_DIR, 'azure_train.jsonl')
    val_file = os.path.join(MODELS_DIR, 'azure_val.jsonl')

    os.makedirs(MODELS_DIR, exist_ok=True)

    with open(train_file, 'w') as f:
        for ex in train_data:
            f.write(json.dumps(ex) + '\n')

    with open(val_file, 'w') as f:
        for ex in val_data:
            f.write(json.dumps(ex) + '\n')

    logger.info(f"Saved training data to {train_file}")
    logger.info(f"Saved validation data to {val_file}")

    return train_file, val_file


def upload_training_files(client: AzureOpenAI, train_file: str, val_file: str) -> Tuple[str, str]:
    """Upload training files to Azure OpenAI."""
    logger.info("Uploading training file...")
    with open(train_file, 'rb') as f:
        train_response = client.files.create(file=f, purpose="fine-tune")
    train_file_id = train_response.id
    logger.info(f"Training file ID: {train_file_id}")

    logger.info("Uploading validation file...")
    with open(val_file, 'rb') as f:
        val_response = client.files.create(file=f, purpose="fine-tune")
    val_file_id = val_response.id
    logger.info(f"Validation file ID: {val_file_id}")

    # Wait for files to be processed
    logger.info("Waiting for files to be processed...")
    for file_id in [train_file_id, val_file_id]:
        while True:
            file_status = client.files.retrieve(file_id)
            if file_status.status == "processed":
                break
            elif file_status.status == "error":
                raise Exception(f"File {file_id} processing failed")
            time.sleep(5)

    logger.info("Files processed successfully")
    return train_file_id, val_file_id


def create_fine_tuning_job(client: AzureOpenAI, train_file_id: str, val_file_id: str) -> str:
    """Create a fine-tuning job on Azure OpenAI."""
    logger.info("Creating fine-tuning job...")

    response = client.fine_tuning.jobs.create(
        training_file=train_file_id,
        validation_file=val_file_id,
        model="gpt-4o-mini-2024-07-18",  # Base model to fine-tune
        hyperparameters={
            "n_epochs": 3,
            "batch_size": 4,
            "learning_rate_multiplier": 1.0
        },
        suffix="protocol-classifier"
    )

    job_id = response.id
    logger.info(f"Fine-tuning job created: {job_id}")
    return job_id


def monitor_fine_tuning_job(client: AzureOpenAI, job_id: str) -> str:
    """Monitor fine-tuning job until completion."""
    logger.info(f"Monitoring job {job_id}...")

    while True:
        job = client.fine_tuning.jobs.retrieve(job_id)
        status = job.status

        logger.info(f"Status: {status}")

        if status == "succeeded":
            model_id = job.fine_tuned_model
            logger.info(f"Fine-tuning complete! Model ID: {model_id}")
            return model_id
        elif status == "failed":
            raise Exception(f"Fine-tuning failed: {job.error}")
        elif status == "cancelled":
            raise Exception("Fine-tuning was cancelled")

        # Print events
        events = client.fine_tuning.jobs.list_events(job_id, limit=5)
        for event in events.data:
            logger.info(f"  Event: {event.message}")

        time.sleep(60)  # Check every minute


def test_fine_tuned_model(client: AzureOpenAI, model_id: str):
    """Test the fine-tuned model with sample protocols."""
    logger.info("\n" + "=" * 60)
    logger.info("Testing Fine-tuned Model")
    logger.info("=" * 60)

    test_protocols = [
        "Arabidopsis thaliana seedling transformation using floral dip method with Agrobacterium",
        "CRISPR-Cas9 knockout of tumor suppressor genes in HeLa cell lines for cancer research",
        "Whole-cell patch clamp recording from cortical pyramidal neurons in mouse brain slices",
        "Standard PCR protocol for DNA amplification using Taq polymerase"
    ]

    expected = ['plant_biology', 'oncology', 'neurology', 'biology']

    for text, exp in zip(test_protocols, expected):
        response = client.chat.completions.create(
            model=model_id,
            messages=[
                {
                    "role": "system",
                    "content": "You are a scientific protocol classifier. Classify protocols into: plant_biology, oncology, neurology, or biology (general)."
                },
                {
                    "role": "user",
                    "content": f"Classify this protocol:\n\n{text}"
                }
            ],
            max_tokens=20
        )

        prediction = response.choices[0].message.content.strip().lower()
        correct = "✓" if prediction == exp else "✗"
        logger.info(f"{correct} '{text[:50]}...' -> {prediction} (expected: {exp})")


def main():
    """Main training function."""
    logger.info("=" * 70)
    logger.info("AZURE OPENAI FINE-TUNING FOR PROTOCOL CLASSIFIER")
    logger.info("=" * 70)

    # Check credentials
    if not AZURE_API_KEY:
        logger.error("AZURE_OPENAI_API_KEY not set")
        return

    logger.info(f"Azure Endpoint: {AZURE_ENDPOINT}")

    # Initialize client
    client = AzureOpenAI(
        azure_endpoint=AZURE_ENDPOINT,
        api_key=AZURE_API_KEY,
        api_version=AZURE_API_VERSION
    )

    # Load data
    protocols = load_protocol_data()
    if not protocols:
        logger.error("No protocols loaded")
        return

    # Domain distribution
    domain_counts = Counter(p.get('domain', 'unknown') for p in protocols)
    logger.info("Protocol domain distribution:")
    for domain, count in domain_counts.most_common(10):
        logger.info(f"  {domain}: {count}")

    # Prepare training data
    train_file, val_file = prepare_training_data(protocols)

    # Upload files
    train_file_id, val_file_id = upload_training_files(client, train_file, val_file)

    # Create fine-tuning job
    job_id = create_fine_tuning_job(client, train_file_id, val_file_id)

    # Monitor until completion
    model_id = monitor_fine_tuning_job(client, job_id)

    # Save model info
    model_info = {
        "model_id": model_id,
        "job_id": job_id,
        "train_file_id": train_file_id,
        "val_file_id": val_file_id,
        "domains": TARGET_DOMAINS,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }

    info_file = os.path.join(MODELS_DIR, 'azure_model_info.json')
    with open(info_file, 'w') as f:
        json.dump(model_info, f, indent=2)
    logger.info(f"Model info saved to {info_file}")

    # Test model
    test_fine_tuned_model(client, model_id)

    logger.info("\n" + "=" * 70)
    logger.info("FINE-TUNING COMPLETE")
    logger.info("=" * 70)
    logger.info(f"Model ID: {model_id}")
    logger.info(f"Use this model in your code with: model='{model_id}'")


if __name__ == '__main__':
    main()
