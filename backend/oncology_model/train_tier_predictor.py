"""
Train Journal Tier Predictor (Model 2)
Fine-tunes DistilBERT with metadata features for 3-class journal tier prediction.

Tiers:
    Tier1 — Top-tier journals (Nature, NEJM, Lancet, Cell, etc.)
    Tier2 — Mid-tier specialty journals
    Tier3 — Lower-tier / regional journals

Architecture:
    DistilBERT [CLS] (768-dim) concat metadata (10-dim)
    -> Linear(778, 256) -> ReLU -> Dropout(0.3) -> Linear(256, 3)

Metadata features (10-dim):
    - author_count (1, normalized)
    - ref_count (1, normalized)
    - paper_type one-hot (5-dim: experimental, review, meta_analysis, case_report, protocol)
    - has_funding (1, binary)
    - institution_count (1, normalized)
    - is_multicenter (1, binary)

Usage:
    python -m oncology_model.train_tier_predictor \
        --data_dir data/oncology_training \
        --output_dir models/tier_predictor \
        --epochs 3 --batch_size 32 --lr 2e-5
"""

import argparse
import json
import logging
import os
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)
from transformers import (
    DistilBertTokenizer,
    DistilBertModel,
    get_linear_schedule_with_warmup,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

TIER_CLASSES = ["Tier1", "Tier2", "Tier3"]
NUM_CLASSES = len(TIER_CLASSES)
MAX_SEQ_LEN = 512
DISTILBERT_HIDDEN = 768

PAPER_TYPES = ["experimental", "review", "meta_analysis", "case_report", "protocol"]
METADATA_DIM = 10  # author_count(1) + ref_count(1) + paper_type(5) + has_funding(1) + institution_count(1) + is_multicenter(1)


# ── Dataset ──────────────────────────────────────────────────────────────────

class TierPredictionDataset(Dataset):
    """Dataset for journal tier prediction with metadata features."""

    def __init__(self, filepath: str, tokenizer: DistilBertTokenizer, label2id: dict):
        self.samples = []
        self.tokenizer = tokenizer
        self.label2id = label2id

        # For normalization: collect stats first pass
        author_counts = []
        ref_counts = []
        institution_counts = []

        raw_records = []
        with open(filepath, "r") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    logger.warning(f"Skipping malformed JSON at line {line_num}")
                    continue

                tier = record.get("tier", "")
                if tier not in self.label2id:
                    logger.warning(f"Unknown tier '{tier}' at line {line_num}, skipping")
                    continue

                raw_records.append(record)
                author_counts.append(record.get("author_count", 1))
                ref_counts.append(record.get("ref_count", 20))
                institution_counts.append(record.get("institution_count", 1))

        # Compute normalization stats (min-max style, clipped)
        self.author_max = max(author_counts) if author_counts else 1
        self.ref_max = max(ref_counts) if ref_counts else 1
        self.inst_max = max(institution_counts) if institution_counts else 1

        # Build samples
        for record in raw_records:
            title = record.get("title", "")
            abstract = record.get("abstract", "")
            tier = record.get("tier", "")
            text = f"{title} [SEP] {abstract}"

            metadata = self._encode_metadata(record)
            self.samples.append((text, metadata, self.label2id[tier]))

        logger.info(f"Loaded {len(self.samples)} samples from {filepath}")

    def _encode_metadata(self, record: dict) -> np.ndarray:
        """Encode metadata into a fixed-size feature vector."""
        features = np.zeros(METADATA_DIM, dtype=np.float32)

        # Normalized author count [0, 1]
        features[0] = min(record.get("author_count", 1) / max(self.author_max, 1), 1.0)

        # Normalized reference count [0, 1]
        features[1] = min(record.get("ref_count", 20) / max(self.ref_max, 1), 1.0)

        # Paper type one-hot (indices 2-6)
        paper_type = record.get("paper_type", "experimental")
        if paper_type in PAPER_TYPES:
            features[2 + PAPER_TYPES.index(paper_type)] = 1.0

        # Binary features
        features[7] = 1.0 if record.get("has_funding", False) else 0.0
        features[8] = min(record.get("institution_count", 1) / max(self.inst_max, 1), 1.0)
        features[9] = 1.0 if record.get("is_multicenter", False) else 0.0

        return features

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        text, metadata, label = self.samples[idx]
        encoding = self.tokenizer(
            text,
            max_length=MAX_SEQ_LEN,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )
        return {
            "input_ids": encoding["input_ids"].squeeze(0),
            "attention_mask": encoding["attention_mask"].squeeze(0),
            "metadata": torch.tensor(metadata, dtype=torch.float32),
            "label": torch.tensor(label, dtype=torch.long),
        }


# ── Model ────────────────────────────────────────────────────────────────────

class TierPredictor(nn.Module):
    """DistilBERT + metadata -> journal tier prediction."""

    def __init__(
        self,
        num_classes: int = NUM_CLASSES,
        metadata_dim: int = METADATA_DIM,
        dropout: float = 0.3,
    ):
        super().__init__()
        self.distilbert = DistilBertModel.from_pretrained("distilbert-base-uncased")
        combined_dim = DISTILBERT_HIDDEN + metadata_dim  # 768 + 10 = 778

        self.classifier = nn.Sequential(
            nn.Linear(combined_dim, 256),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(256, num_classes),
        )

    def forward(self, input_ids, attention_mask, metadata):
        outputs = self.distilbert(input_ids=input_ids, attention_mask=attention_mask)
        cls_output = outputs.last_hidden_state[:, 0, :]  # [CLS] token
        # Concatenate text representation with metadata
        combined = torch.cat([cls_output, metadata], dim=-1)  # (batch, 778)
        logits = self.classifier(combined)
        return logits


# ── Utility Functions ────────────────────────────────────────────────────────

def get_device():
    """Auto-detect best available device."""
    if torch.cuda.is_available():
        device = torch.device("cuda")
        logger.info(f"Using CUDA: {torch.cuda.get_device_name(0)}")
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        device = torch.device("mps")
        logger.info("Using Apple Silicon MPS")
    else:
        device = torch.device("cpu")
        logger.info("Using CPU")
    return device


def compute_class_weights(dataset: TierPredictionDataset, num_classes: int, device):
    """Compute inverse-frequency class weights."""
    label_counts = Counter()
    for _, _, label in dataset.samples:
        label_counts[label] += 1

    total = len(dataset.samples)
    weights = []
    for i in range(num_classes):
        count = label_counts.get(i, 1)
        weights.append(total / (num_classes * count))

    weights_tensor = torch.tensor(weights, dtype=torch.float32).to(device)
    logger.info(f"Class weights: {dict(zip(TIER_CLASSES, [f'{w:.3f}' for w in weights]))}")
    return weights_tensor


def compute_topk_journal_accuracy(
    predictions: list,
    labels: list,
    records: list,
    journal_to_tier: dict,
    k_values: list = [5, 10],
):
    """
    Compute top-K journal accuracy: for each paper, given the predicted tier,
    check if the actual journal is within the top-K journals of that tier.

    This measures whether the model's tier prediction would lead to correct
    journal suggestions from a journal recommendation system.
    """
    results = {}
    for k in k_values:
        correct = 0
        total = 0
        for pred, record in zip(predictions, records):
            actual_journal = record.get("journal", "")
            if not actual_journal:
                continue
            total += 1
            # Get journals in predicted tier, ranked by impact
            tier_name = TIER_CLASSES[pred] if isinstance(pred, int) else pred
            tier_journals = [
                j for j, t in journal_to_tier.items() if t == tier_name
            ]
            if actual_journal in tier_journals[:k]:
                correct += 1
        accuracy = correct / total if total > 0 else 0.0
        results[f"top_{k}_accuracy"] = accuracy
        logger.info(f"  Top-{k} Journal Accuracy: {accuracy:.4f} ({correct}/{total})")
    return results


# ── Training Loop ────────────────────────────────────────────────────────────

def train_epoch(model, dataloader, optimizer, scheduler, criterion, device, epoch, log_every=100):
    """Train for one epoch."""
    model.train()
    total_loss = 0.0
    correct = 0
    total = 0
    step_loss = 0.0

    for step, batch in enumerate(dataloader, 1):
        input_ids = batch["input_ids"].to(device)
        attention_mask = batch["attention_mask"].to(device)
        metadata = batch["metadata"].to(device)
        labels = batch["label"].to(device)

        optimizer.zero_grad()
        logits = model(input_ids, attention_mask, metadata)
        loss = criterion(logits, labels)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()
        scheduler.step()

        total_loss += loss.item()
        step_loss += loss.item()
        preds = torch.argmax(logits, dim=-1)
        correct += (preds == labels).sum().item()
        total += labels.size(0)

        if step % log_every == 0:
            avg_step_loss = step_loss / log_every
            lr = scheduler.get_last_lr()[0]
            logger.info(
                f"  Epoch {epoch} | Step {step}/{len(dataloader)} | "
                f"Loss: {avg_step_loss:.4f} | Acc: {correct/total:.4f} | LR: {lr:.2e}"
            )
            step_loss = 0.0

    avg_loss = total_loss / len(dataloader)
    accuracy = correct / total if total > 0 else 0.0
    return avg_loss, accuracy


def evaluate(model, dataloader, criterion, device):
    """Evaluate model, return metrics."""
    model.eval()
    total_loss = 0.0
    all_preds = []
    all_labels = []

    with torch.no_grad():
        for batch in dataloader:
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            metadata = batch["metadata"].to(device)
            labels = batch["label"].to(device)

            logits = model(input_ids, attention_mask, metadata)
            loss = criterion(logits, labels)
            total_loss += loss.item()

            preds = torch.argmax(logits, dim=-1)
            all_preds.extend(preds.cpu().numpy())
            all_labels.extend(labels.cpu().numpy())

    avg_loss = total_loss / len(dataloader) if len(dataloader) > 0 else 0.0
    accuracy = accuracy_score(all_labels, all_preds)
    f1_macro = f1_score(all_labels, all_preds, average="macro", zero_division=0)
    f1_weighted = f1_score(all_labels, all_preds, average="weighted", zero_division=0)

    return {
        "loss": avg_loss,
        "accuracy": accuracy,
        "f1_macro": f1_macro,
        "f1_weighted": f1_weighted,
        "predictions": all_preds,
        "labels": all_labels,
    }


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Train Journal Tier Predictor")
    parser.add_argument("--data_dir", type=str, required=True, help="Directory with train/val/test JSONL files")
    parser.add_argument("--output_dir", type=str, required=True, help="Directory to save trained model")
    parser.add_argument("--journal_mapping", type=str, default=None, help="JSON file mapping journal names to tiers")
    parser.add_argument("--epochs", type=int, default=3, help="Number of training epochs")
    parser.add_argument("--batch_size", type=int, default=32, help="Training batch size")
    parser.add_argument("--lr", type=float, default=2e-5, help="Learning rate")
    parser.add_argument("--warmup_ratio", type=float, default=0.1, help="Warmup ratio")
    parser.add_argument("--weight_decay", type=float, default=0.01, help="Weight decay")
    parser.add_argument("--dropout", type=float, default=0.3, help="Classifier dropout")
    parser.add_argument("--log_every", type=int, default=100, help="Log every N steps")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    # Seed
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)

    device = get_device()
    os.makedirs(args.output_dir, exist_ok=True)

    # Label mappings
    label2id = {label: idx for idx, label in enumerate(TIER_CLASSES)}
    id2label = {idx: label for idx, label in enumerate(TIER_CLASSES)}

    label_mappings = {
        "label2id": label2id,
        "id2label": {str(k): v for k, v in id2label.items()},
        "classes": TIER_CLASSES,
        "num_classes": NUM_CLASSES,
        "metadata_dim": METADATA_DIM,
        "paper_types": PAPER_TYPES,
    }
    with open(os.path.join(args.output_dir, "label_mappings.json"), "w") as f:
        json.dump(label_mappings, f, indent=2)

    # Load journal-to-tier mapping for top-K evaluation
    journal_to_tier = {}
    if args.journal_mapping and os.path.exists(args.journal_mapping):
        with open(args.journal_mapping, "r") as f:
            journal_to_tier = json.load(f)
        logger.info(f"Loaded journal-to-tier mapping with {len(journal_to_tier)} journals")

    # Tokenizer
    logger.info("Loading DistilBERT tokenizer...")
    tokenizer = DistilBertTokenizer.from_pretrained("distilbert-base-uncased")

    # Datasets
    logger.info("Loading datasets...")
    train_dataset = TierPredictionDataset(
        os.path.join(args.data_dir, "train.jsonl"), tokenizer, label2id
    )
    val_dataset = TierPredictionDataset(
        os.path.join(args.data_dir, "val.jsonl"), tokenizer, label2id
    )
    test_dataset = TierPredictionDataset(
        os.path.join(args.data_dir, "test.jsonl"), tokenizer, label2id
    )

    # DataLoaders
    train_loader = DataLoader(
        train_dataset, batch_size=args.batch_size, shuffle=True, num_workers=2, pin_memory=True
    )
    val_loader = DataLoader(
        val_dataset, batch_size=args.batch_size, shuffle=False, num_workers=2, pin_memory=True
    )
    test_loader = DataLoader(
        test_dataset, batch_size=args.batch_size, shuffle=False, num_workers=2, pin_memory=True
    )

    # Class distribution
    label_dist = Counter(label for _, _, label in train_dataset.samples)
    logger.info("Training class distribution:")
    for cls_name in TIER_CLASSES:
        cls_id = label2id[cls_name]
        count = label_dist.get(cls_id, 0)
        logger.info(f"  {cls_name}: {count}")

    # Model
    logger.info("Initializing TierPredictor...")
    model = TierPredictor(
        num_classes=NUM_CLASSES, metadata_dim=METADATA_DIM, dropout=args.dropout
    ).to(device)

    # Class weights
    class_weights = compute_class_weights(train_dataset, NUM_CLASSES, device)
    criterion = nn.CrossEntropyLoss(weight=class_weights)

    # Optimizer + scheduler
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=args.lr, weight_decay=args.weight_decay
    )
    total_steps = len(train_loader) * args.epochs
    warmup_steps = int(total_steps * args.warmup_ratio)
    scheduler = get_linear_schedule_with_warmup(
        optimizer, num_warmup_steps=warmup_steps, num_training_steps=total_steps
    )

    logger.info(f"Total steps: {total_steps}, Warmup: {warmup_steps}")
    logger.info(f"Train: {len(train_dataset)}, Val: {len(val_dataset)}, Test: {len(test_dataset)}")
    logger.info("=" * 60)
    logger.info("Starting Training")
    logger.info("=" * 60)

    # Training loop
    best_f1 = 0.0
    best_epoch = -1
    training_history = []

    for epoch in range(1, args.epochs + 1):
        epoch_start = time.time()
        logger.info(f"\n--- Epoch {epoch}/{args.epochs} ---")

        train_loss, train_acc = train_epoch(
            model, train_loader, optimizer, scheduler, criterion, device, epoch, args.log_every
        )

        val_metrics = evaluate(model, val_loader, criterion, device)

        epoch_time = time.time() - epoch_start
        logger.info(
            f"Epoch {epoch} complete in {epoch_time:.1f}s | "
            f"Train Loss: {train_loss:.4f}, Acc: {train_acc:.4f} | "
            f"Val Loss: {val_metrics['loss']:.4f}, Acc: {val_metrics['accuracy']:.4f}, "
            f"F1 (macro): {val_metrics['f1_macro']:.4f}"
        )

        training_history.append({
            "epoch": epoch,
            "train_loss": train_loss,
            "train_accuracy": train_acc,
            "val_loss": val_metrics["loss"],
            "val_accuracy": val_metrics["accuracy"],
            "val_f1_macro": val_metrics["f1_macro"],
            "val_f1_weighted": val_metrics["f1_weighted"],
            "epoch_time_s": epoch_time,
        })

        if val_metrics["f1_macro"] > best_f1:
            best_f1 = val_metrics["f1_macro"]
            best_epoch = epoch
            logger.info(f"  New best F1: {best_f1:.4f} — saving model")
            torch.save(model.state_dict(), os.path.join(args.output_dir, "best_model.pt"))
            tokenizer.save_pretrained(os.path.join(args.output_dir, "tokenizer"))

    logger.info(f"\nBest model from epoch {best_epoch} with val F1: {best_f1:.4f}")

    # ── Test Set Evaluation ──────────────────────────────────────────────────

    logger.info("=" * 60)
    logger.info("Test Set Evaluation (Best Model)")
    logger.info("=" * 60)

    model.load_state_dict(
        torch.load(os.path.join(args.output_dir, "best_model.pt"), map_location=device)
    )
    test_metrics = evaluate(model, test_loader, criterion, device)

    logger.info(f"Test Accuracy:    {test_metrics['accuracy']:.4f}")
    logger.info(f"Test F1 (macro):  {test_metrics['f1_macro']:.4f}")
    logger.info(f"Test F1 (weighted): {test_metrics['f1_weighted']:.4f}")

    # Per-class report
    report = classification_report(
        test_metrics["labels"],
        test_metrics["predictions"],
        target_names=TIER_CLASSES,
        zero_division=0,
    )
    logger.info("\nPer-Class Classification Report:")
    print(report)

    # Confusion matrix
    cm = confusion_matrix(test_metrics["labels"], test_metrics["predictions"])
    logger.info("Confusion Matrix:")
    header = "".join(f"{name:>10}" for name in TIER_CLASSES)
    print(f"{'':>10}{header}")
    for i, row in enumerate(cm):
        row_str = "".join(f"{val:>10}" for val in row)
        print(f"{TIER_CLASSES[i]:>10}{row_str}")

    # ── Top-K Journal Accuracy ───────────────────────────────────────────────

    if journal_to_tier:
        logger.info("\nTop-K Journal Accuracy:")
        # Re-load raw test records for journal names
        test_records = []
        with open(os.path.join(args.data_dir, "test.jsonl"), "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        test_records.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass

        topk_results = compute_topk_journal_accuracy(
            test_metrics["predictions"],
            test_metrics["labels"],
            test_records,
            journal_to_tier,
            k_values=[5, 10],
        )
    else:
        topk_results = {}
        logger.info("\nSkipping top-K journal accuracy (no --journal_mapping provided)")

    # Save metrics
    metrics = {
        "model": "tier_predictor",
        "architecture": "DistilBERT [CLS](768) + metadata(10) -> Linear(778,256) -> ReLU -> Dropout -> Linear(256,3)",
        "best_epoch": best_epoch,
        "best_val_f1": best_f1,
        "test_accuracy": test_metrics["accuracy"],
        "test_f1_macro": test_metrics["f1_macro"],
        "test_f1_weighted": test_metrics["f1_weighted"],
        "topk_journal_accuracy": topk_results,
        "hyperparameters": {
            "epochs": args.epochs,
            "batch_size": args.batch_size,
            "learning_rate": args.lr,
            "warmup_ratio": args.warmup_ratio,
            "weight_decay": args.weight_decay,
            "dropout": args.dropout,
            "max_seq_len": MAX_SEQ_LEN,
            "metadata_dim": METADATA_DIM,
        },
        "training_history": training_history,
        "classification_report": classification_report(
            test_metrics["labels"],
            test_metrics["predictions"],
            target_names=TIER_CLASSES,
            output_dict=True,
            zero_division=0,
        ),
    }

    with open(os.path.join(args.output_dir, "training_metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)

    logger.info(f"\nModel saved to {args.output_dir}")
    logger.info("Training complete.")


if __name__ == "__main__":
    main()
