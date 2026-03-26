"""
CPU-Optimized Neural Network Training for Protocol Models
===========================================================
Uses DistilBERT (faster) and optimized settings for CPU training.
Trains in ~20-30 minutes on Apple M2.
"""

import os
import json
import logging
import random
from typing import List, Dict, Tuple
from collections import Counter
import torch
from torch.utils.data import DataLoader
from sentence_transformers import SentenceTransformer, InputExample, losses, evaluation
from transformers import AutoTokenizer, AutoModelForSequenceClassification, TrainingArguments, Trainer
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
import numpy as np

from . import CORPUS_DIR, MODELS_DIR

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Domains we care about
TARGET_DOMAINS = ['plant_biology', 'oncology', 'neurology', 'biology']
DOMAIN_TO_ID = {d: i for i, d in enumerate(TARGET_DOMAINS)}
ID_TO_DOMAIN = {i: d for d, i in DOMAIN_TO_ID.items()}


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


def prepare_classification_data(protocols: List[Dict]) -> Tuple[List[str], List[int]]:
    """Prepare data for domain classification."""
    texts = []
    labels = []

    for p in protocols:
        domain = p.get('domain', 'biology')
        if domain not in TARGET_DOMAINS:
            domain = 'biology'

        # Get text content (shorter for faster training)
        text = ""
        if p.get('title'):
            text += p['title'] + " "
        if p.get('abstract'):
            text += p['abstract'][:500] + " "
        if p.get('raw_text'):
            text += p['raw_text'][:1000]

        text = text.strip()
        if len(text) > 50:
            texts.append(text[:1500])  # Shorter for CPU
            labels.append(DOMAIN_TO_ID[domain])

    logger.info(f"Prepared {len(texts)} samples for classification")
    logger.info(f"Label distribution: {Counter(labels)}")

    return texts, labels


def prepare_similarity_data(protocols: List[Dict]) -> List[InputExample]:
    """Prepare data for protocol similarity training (reduced for CPU)."""
    examples = []

    # Group protocols by domain
    domain_protocols = {}
    for p in protocols:
        domain = p.get('domain', 'biology')
        if domain not in domain_protocols:
            domain_protocols[domain] = []

        text = ""
        if p.get('title'):
            text += p['title'] + " "
        if p.get('raw_text'):
            text += p['raw_text'][:800]

        if len(text) > 50:
            domain_protocols[domain].append(text[:1000])

    # Create pairs (fewer for CPU)
    domains = list(domain_protocols.keys())

    for domain in domains:
        protos = domain_protocols[domain]
        if len(protos) < 2:
            continue

        # Positive pairs (same domain)
        for i in range(min(len(protos) - 1, 100)):  # Reduced from 500
            idx1, idx2 = random.sample(range(len(protos)), 2)
            examples.append(InputExample(
                texts=[protos[idx1], protos[idx2]],
                label=0.8
            ))

        # Negative pairs
        other_domains = [d for d in domains if d != domain]
        for other in other_domains:
            other_protos = domain_protocols[other]
            for i in range(min(20, len(protos), len(other_protos))):
                examples.append(InputExample(
                    texts=[random.choice(protos), random.choice(other_protos)],
                    label=0.3
                ))

    random.shuffle(examples)
    logger.info(f"Created {len(examples)} similarity training examples")

    return examples


class ProtocolDataset(torch.utils.data.Dataset):
    """Dataset for protocol classification."""

    def __init__(self, texts, labels, tokenizer, max_length=256):  # Shorter for CPU
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        encoding = self.tokenizer(
            self.texts[idx],
            truncation=True,
            padding='max_length',
            max_length=self.max_length,
            return_tensors='pt'
        )
        return {
            'input_ids': encoding['input_ids'].squeeze(),
            'attention_mask': encoding['attention_mask'].squeeze(),
            'labels': torch.tensor(self.labels[idx])
        }


def compute_metrics(eval_pred):
    """Compute metrics for evaluation."""
    predictions, labels = eval_pred
    predictions = np.argmax(predictions, axis=1)
    return {'accuracy': accuracy_score(labels, predictions)}


def train_domain_classifier(protocols: List[Dict], output_dir: str):
    """Train DistilBERT-based domain classifier (CPU optimized)."""
    logger.info("=" * 60)
    logger.info("Training Domain Classifier (DistilBERT - CPU Optimized)")
    logger.info("=" * 60)

    # Prepare data
    texts, labels = prepare_classification_data(protocols)

    if len(texts) < 50:
        logger.error("Not enough data for training")
        return None

    # Split data
    train_texts, val_texts, train_labels, val_labels = train_test_split(
        texts, labels, test_size=0.2, stratify=labels, random_state=42
    )

    logger.info(f"Train: {len(train_texts)}, Val: {len(val_texts)}")

    # Use DistilBERT (6x faster than BERT)
    model_name = "distilbert-base-uncased"
    logger.info(f"Loading model: {model_name}")

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_name,
        num_labels=len(TARGET_DOMAINS),
        id2label=ID_TO_DOMAIN,
        label2id=DOMAIN_TO_ID
    )

    # Create datasets
    train_dataset = ProtocolDataset(train_texts, train_labels, tokenizer)
    val_dataset = ProtocolDataset(val_texts, val_labels, tokenizer)

    # CPU-optimized training arguments
    training_args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=2,  # Fewer epochs for CPU
        per_device_train_batch_size=16,  # Larger batch for efficiency
        per_device_eval_batch_size=32,
        warmup_steps=50,
        weight_decay=0.01,
        logging_dir=os.path.join(output_dir, 'logs'),
        logging_steps=100,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="accuracy",
        report_to="none",
        dataloader_num_workers=4,  # Parallel data loading
        gradient_accumulation_steps=2,  # Simulate larger batch
    )

    # Trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        compute_metrics=compute_metrics,
    )

    # Train
    logger.info("Starting training (this takes ~15-20 min on CPU)...")
    trainer.train()

    # Evaluate
    eval_results = trainer.evaluate()
    logger.info(f"Evaluation results: {eval_results}")

    # Save model
    model_path = os.path.join(MODELS_DIR, 'domain_classifier_distilbert')
    model.save_pretrained(model_path)
    tokenizer.save_pretrained(model_path)

    logger.info(f"Model saved to {model_path}")

    # Test predictions
    logger.info("\nSample predictions:")
    test_texts = [
        "Arabidopsis thaliana transformation using floral dip method",
        "Tumor cell line culture and chemotherapy drug screening",
        "Neuroimaging fMRI preprocessing with FSL and FreeSurfer",
        "General PCR protocol for DNA amplification"
    ]
    expected = ['plant_biology', 'oncology', 'neurology', 'biology']

    model.eval()
    correct = 0
    for text, exp in zip(test_texts, expected):
        inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=256)
        with torch.no_grad():
            outputs = model(**inputs)
        pred_id = torch.argmax(outputs.logits, dim=1).item()
        pred_domain = ID_TO_DOMAIN[pred_id]
        status = "✓" if pred_domain == exp else "✗"
        correct += 1 if pred_domain == exp else 0
        logger.info(f"  {status} '{text[:50]}...' -> {pred_domain} (expected: {exp})")

    logger.info(f"\nTest accuracy: {correct}/{len(test_texts)}")

    return model_path


def train_protocol_embeddings(protocols: List[Dict], output_dir: str):
    """Fine-tune sentence embeddings (CPU optimized)."""
    logger.info("=" * 60)
    logger.info("Training Protocol Embeddings (CPU Optimized)")
    logger.info("=" * 60)

    # Prepare similarity data (reduced for CPU)
    examples = prepare_similarity_data(protocols)

    if len(examples) < 50:
        logger.error("Not enough examples for embedding training")
        return None

    # Split
    train_examples = examples[:int(len(examples) * 0.9)]
    val_examples = examples[int(len(examples) * 0.9):]

    logger.info(f"Train: {len(train_examples)}, Val: {len(val_examples)}")

    # Load base model (MiniLM is very fast)
    model_name = "all-MiniLM-L6-v2"
    logger.info(f"Loading model: {model_name}")
    model = SentenceTransformer(model_name)

    # DataLoader
    train_dataloader = DataLoader(train_examples, shuffle=True, batch_size=32)

    # Loss
    train_loss = losses.CosineSimilarityLoss(model)

    # Evaluator
    val_sentences1 = [ex.texts[0] for ex in val_examples]
    val_sentences2 = [ex.texts[1] for ex in val_examples]
    val_scores = [ex.label for ex in val_examples]

    evaluator = evaluation.EmbeddingSimilarityEvaluator(
        val_sentences1, val_sentences2, val_scores,
        name='protocol-similarity'
    )

    # Train (just 1 epoch for CPU)
    logger.info("Starting embedding training (this takes ~5-10 min on CPU)...")
    model.fit(
        train_objectives=[(train_dataloader, train_loss)],
        evaluator=evaluator,
        epochs=1,
        warmup_steps=50,
        output_path=os.path.join(MODELS_DIR, 'protocol_embeddings_minilm'),
        show_progress_bar=True
    )

    model_path = os.path.join(MODELS_DIR, 'protocol_embeddings_minilm')
    logger.info(f"Embeddings model saved to {model_path}")

    # Test embeddings
    logger.info("\nTesting embedding similarity:")
    test_pairs = [
        ("Arabidopsis transformation protocol", "Plant cell transformation method"),
        ("Cancer cell line drug screening", "Tumor chemotherapy assay"),
        ("Plant DNA extraction", "Neuroimaging MRI analysis"),
    ]

    for text1, text2 in test_pairs:
        emb1 = model.encode(text1)
        emb2 = model.encode(text2)
        similarity = np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))
        logger.info(f"  '{text1}' <-> '{text2}': {similarity:.3f}")

    return model_path


def main():
    """Main training function."""
    logger.info("=" * 70)
    logger.info("CPU-OPTIMIZED NEURAL NETWORK TRAINING")
    logger.info("=" * 70)

    # Check device
    device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
    logger.info(f"Using device: {device}")
    logger.info(f"PyTorch version: {torch.__version__}")

    # Ensure output directory exists
    os.makedirs(MODELS_DIR, exist_ok=True)

    # Load data
    protocols = load_protocol_data()
    if not protocols:
        logger.error("No protocols loaded, exiting")
        return

    # Domain distribution
    domain_counts = Counter(p.get('domain', 'unknown') for p in protocols)
    logger.info("Protocol domain distribution:")
    for domain, count in domain_counts.most_common(10):
        logger.info(f"  {domain}: {count}")

    # Train domain classifier
    logger.info("\n" + "=" * 60)
    logger.info("PHASE 1: Domain Classifier")
    logger.info("=" * 60)
    classifier_path = train_domain_classifier(
        protocols,
        output_dir=os.path.join(MODELS_DIR, 'domain_classifier_training')
    )

    # Train embeddings
    logger.info("\n" + "=" * 60)
    logger.info("PHASE 2: Protocol Embeddings")
    logger.info("=" * 60)
    embeddings_path = train_protocol_embeddings(
        protocols,
        output_dir=MODELS_DIR
    )

    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("TRAINING COMPLETE")
    logger.info("=" * 70)
    logger.info(f"Domain Classifier: {classifier_path}")
    logger.info(f"Protocol Embeddings: {embeddings_path}")
    logger.info(f"\nModels saved to: {MODELS_DIR}")


if __name__ == '__main__':
    main()
