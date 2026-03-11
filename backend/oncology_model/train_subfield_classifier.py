"""
Train Oncology Sub-Field Classifier (Model 1)
Fine-tunes DistilBERT for 15-class oncology sub-field classification.
Also trains a TF-IDF + LogisticRegression baseline for comparison.

Usage:
    python -m oncology_model.train_subfield_classifier \
        --data_dir data/oncology_training \
        --output_dir models/subfield_classifier \
        --epochs 3 --batch_size 32 --lr 2e-5

Expected data format (JSONL):
    {"title": "...", "abstract": "...", "subfield": "breast", ...}
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
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
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

SUBFIELD_CLASSES = [
    "breast",
    "lung",
    "colorectal",
    "prostate",
    "hematologic",
    "melanoma",
    "brain",
    "pancreatic",
    "ovarian",
    "head_neck",
    "liver",
    "kidney",
    "sarcoma",
    "pediatric",
    "general_oncology",
]

NUM_CLASSES = len(SUBFIELD_CLASSES)
MAX_SEQ_LEN = 512
DISTILBERT_HIDDEN = 768


# ── Dataset ──────────────────────────────────────────────────────────────────

class OncologySubfieldDataset(Dataset):
    """Dataset for oncology sub-field classification."""

    def __init__(self, filepath: str, tokenizer: DistilBertTokenizer, label2id: dict):
        self.samples = []
        self.tokenizer = tokenizer
        self.label2id = label2id

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

                title = record.get("title", "")
                abstract = record.get("abstract", "")
                subfield = record.get("subfield", "")

                if subfield not in self.label2id:
                    logger.warning(
                        f"Unknown subfield '{subfield}' at line {line_num}, skipping"
                    )
                    continue

                text = f"{title} [SEP] {abstract}"
                self.samples.append((text, self.label2id[subfield]))

        logger.info(
            f"Loaded {len(self.samples)} samples from {filepath}"
        )

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        text, label = self.samples[idx]
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
            "label": torch.tensor(label, dtype=torch.long),
        }


# ── Model ────────────────────────────────────────────────────────────────────

class SubfieldClassifier(nn.Module):
    """DistilBERT + classification head for oncology sub-field prediction."""

    def __init__(self, num_classes: int = NUM_CLASSES, dropout: float = 0.3):
        super().__init__()
        self.distilbert = DistilBertModel.from_pretrained("distilbert-base-uncased")
        self.classifier = nn.Sequential(
            nn.Linear(DISTILBERT_HIDDEN, 256),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(256, num_classes),
        )

    def forward(self, input_ids, attention_mask):
        outputs = self.distilbert(input_ids=input_ids, attention_mask=attention_mask)
        # Use [CLS] token representation (first token)
        cls_output = outputs.last_hidden_state[:, 0, :]
        logits = self.classifier(cls_output)
        return logits


# ── Utility Functions ────────────────────────────────────────────────────────

def get_device():
    """Auto-detect best available device: CUDA > MPS > CPU."""
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


def compute_class_weights(dataset: OncologySubfieldDataset, num_classes: int, device):
    """Compute inverse-frequency class weights for imbalanced data."""
    label_counts = Counter()
    for _, label in dataset.samples:
        label_counts[label] += 1

    total = len(dataset.samples)
    weights = []
    for i in range(num_classes):
        count = label_counts.get(i, 1)
        weights.append(total / (num_classes * count))

    weights_tensor = torch.tensor(weights, dtype=torch.float32).to(device)
    logger.info(f"Class weights: {dict(zip(SUBFIELD_CLASSES, [f'{w:.3f}' for w in weights]))}")
    return weights_tensor


def load_raw_texts(filepath: str):
    """Load raw text + labels from JSONL for TF-IDF baseline."""
    texts, labels = [], []
    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            title = record.get("title", "")
            abstract = record.get("abstract", "")
            subfield = record.get("subfield", "")
            if subfield in SUBFIELD_CLASSES:
                texts.append(f"{title} {abstract}")
                labels.append(subfield)
    return texts, labels


# ── Training Loop ────────────────────────────────────────────────────────────

def train_epoch(model, dataloader, optimizer, scheduler, criterion, device, epoch, log_every=100):
    """Train for one epoch, logging every `log_every` steps."""
    model.train()
    total_loss = 0.0
    correct = 0
    total = 0
    step_loss = 0.0

    for step, batch in enumerate(dataloader, 1):
        input_ids = batch["input_ids"].to(device)
        attention_mask = batch["attention_mask"].to(device)
        labels = batch["label"].to(device)

        optimizer.zero_grad()
        logits = model(input_ids, attention_mask)
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


def evaluate(model, dataloader, criterion, device, id2label):
    """Evaluate model on a dataset, return metrics."""
    model.eval()
    total_loss = 0.0
    all_preds = []
    all_labels = []

    with torch.no_grad():
        for batch in dataloader:
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["label"].to(device)

            logits = model(input_ids, attention_mask)
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


# ── Baseline Model ───────────────────────────────────────────────────────────

def train_baseline(data_dir: str, output_dir: str):
    """Train TF-IDF + LogisticRegression baseline for comparison."""
    logger.info("=" * 60)
    logger.info("Training TF-IDF + LogisticRegression Baseline")
    logger.info("=" * 60)

    train_texts, train_labels = load_raw_texts(os.path.join(data_dir, "train.jsonl"))
    val_texts, val_labels = load_raw_texts(os.path.join(data_dir, "val.jsonl"))
    test_texts, test_labels = load_raw_texts(os.path.join(data_dir, "test.jsonl"))

    logger.info(f"Baseline data: train={len(train_texts)}, val={len(val_texts)}, test={len(test_texts)}")

    # Fit TF-IDF
    tfidf = TfidfVectorizer(
        max_features=50000,
        ngram_range=(1, 2),
        sublinear_tf=True,
        strip_accents="unicode",
    )
    X_train = tfidf.fit_transform(train_texts)
    X_val = tfidf.transform(val_texts)
    X_test = tfidf.transform(test_texts)

    # Train LogisticRegression with class weight balancing
    clf = LogisticRegression(
        max_iter=1000,
        class_weight="balanced",
        C=1.0,
        solver="lbfgs",
        multi_class="multinomial",
        n_jobs=-1,
    )
    clf.fit(X_train, train_labels)

    # Evaluate
    val_preds = clf.predict(X_val)
    test_preds = clf.predict(X_test)

    val_acc = accuracy_score(val_labels, val_preds)
    val_f1 = f1_score(val_labels, val_preds, average="macro", zero_division=0)
    test_acc = accuracy_score(test_labels, test_preds)
    test_f1 = f1_score(test_labels, test_preds, average="macro", zero_division=0)

    logger.info(f"Baseline Val  — Acc: {val_acc:.4f}, F1 (macro): {val_f1:.4f}")
    logger.info(f"Baseline Test — Acc: {test_acc:.4f}, F1 (macro): {test_f1:.4f}")

    logger.info("\nBaseline Test Classification Report:")
    print(classification_report(test_labels, test_preds, zero_division=0))

    # Save baseline
    import pickle

    baseline_dir = os.path.join(output_dir, "baseline")
    os.makedirs(baseline_dir, exist_ok=True)
    with open(os.path.join(baseline_dir, "tfidf_vectorizer.pkl"), "wb") as f:
        pickle.dump(tfidf, f)
    with open(os.path.join(baseline_dir, "logreg_model.pkl"), "wb") as f:
        pickle.dump(clf, f)

    logger.info(f"Baseline model saved to {baseline_dir}")

    return {"val_acc": val_acc, "val_f1": val_f1, "test_acc": test_acc, "test_f1": test_f1}


# ── Main Training ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Train Oncology Sub-Field Classifier")
    parser.add_argument("--data_dir", type=str, required=True, help="Directory with train/val/test JSONL files")
    parser.add_argument("--output_dir", type=str, required=True, help="Directory to save trained model")
    parser.add_argument("--epochs", type=int, default=3, help="Number of training epochs")
    parser.add_argument("--batch_size", type=int, default=32, help="Training batch size")
    parser.add_argument("--lr", type=float, default=2e-5, help="Learning rate")
    parser.add_argument("--warmup_ratio", type=float, default=0.1, help="Warmup ratio of total steps")
    parser.add_argument("--weight_decay", type=float, default=0.01, help="Weight decay")
    parser.add_argument("--dropout", type=float, default=0.3, help="Classifier dropout")
    parser.add_argument("--log_every", type=int, default=100, help="Log every N steps")
    parser.add_argument("--skip_baseline", action="store_true", help="Skip TF-IDF baseline training")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    # Seed
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)

    # Device
    device = get_device()

    # Output directory
    os.makedirs(args.output_dir, exist_ok=True)

    # Label mappings
    label2id = {label: idx for idx, label in enumerate(SUBFIELD_CLASSES)}
    id2label = {idx: label for idx, label in enumerate(SUBFIELD_CLASSES)}

    # Save label mappings
    label_mappings = {
        "label2id": label2id,
        "id2label": {str(k): v for k, v in id2label.items()},
        "classes": SUBFIELD_CLASSES,
        "num_classes": NUM_CLASSES,
    }
    with open(os.path.join(args.output_dir, "label_mappings.json"), "w") as f:
        json.dump(label_mappings, f, indent=2)

    # Tokenizer
    logger.info("Loading DistilBERT tokenizer...")
    tokenizer = DistilBertTokenizer.from_pretrained("distilbert-base-uncased")

    # Datasets
    logger.info("Loading datasets...")
    train_dataset = OncologySubfieldDataset(
        os.path.join(args.data_dir, "train.jsonl"), tokenizer, label2id
    )
    val_dataset = OncologySubfieldDataset(
        os.path.join(args.data_dir, "val.jsonl"), tokenizer, label2id
    )
    test_dataset = OncologySubfieldDataset(
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
    label_dist = Counter(label for _, label in train_dataset.samples)
    logger.info("Training class distribution:")
    for cls_name in SUBFIELD_CLASSES:
        cls_id = label2id[cls_name]
        count = label_dist.get(cls_id, 0)
        logger.info(f"  {cls_name}: {count}")

    # Model
    logger.info("Initializing SubfieldClassifier...")
    model = SubfieldClassifier(num_classes=NUM_CLASSES, dropout=args.dropout).to(device)

    # Class weights
    class_weights = compute_class_weights(train_dataset, NUM_CLASSES, device)
    criterion = nn.CrossEntropyLoss(weight=class_weights)

    # Optimizer
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=args.lr, weight_decay=args.weight_decay
    )

    # Scheduler with warmup
    total_steps = len(train_loader) * args.epochs
    warmup_steps = int(total_steps * args.warmup_ratio)
    scheduler = get_linear_schedule_with_warmup(
        optimizer, num_warmup_steps=warmup_steps, num_training_steps=total_steps
    )

    logger.info(f"Total steps: {total_steps}, Warmup steps: {warmup_steps}")
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

        # Train
        train_loss, train_acc = train_epoch(
            model, train_loader, optimizer, scheduler, criterion, device, epoch, args.log_every
        )

        # Validate
        val_metrics = evaluate(model, val_loader, criterion, device, id2label)

        epoch_time = time.time() - epoch_start
        logger.info(
            f"Epoch {epoch} complete in {epoch_time:.1f}s | "
            f"Train Loss: {train_loss:.4f}, Acc: {train_acc:.4f} | "
            f"Val Loss: {val_metrics['loss']:.4f}, Acc: {val_metrics['accuracy']:.4f}, "
            f"F1 (macro): {val_metrics['f1_macro']:.4f}, F1 (weighted): {val_metrics['f1_weighted']:.4f}"
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

        # Save best model by macro F1
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

    # Load best model
    model.load_state_dict(torch.load(os.path.join(args.output_dir, "best_model.pt"), map_location=device))
    test_metrics = evaluate(model, test_loader, criterion, device, id2label)

    logger.info(f"Test Accuracy:    {test_metrics['accuracy']:.4f}")
    logger.info(f"Test F1 (macro):  {test_metrics['f1_macro']:.4f}")
    logger.info(f"Test F1 (weighted): {test_metrics['f1_weighted']:.4f}")

    # Per-class report
    target_names = [id2label[i] for i in range(NUM_CLASSES)]
    report = classification_report(
        test_metrics["labels"],
        test_metrics["predictions"],
        target_names=target_names,
        zero_division=0,
    )
    logger.info("\nPer-Class Classification Report:")
    print(report)

    # Confusion matrix
    cm = confusion_matrix(test_metrics["labels"], test_metrics["predictions"])
    logger.info("Confusion Matrix:")
    # Print header
    header = "".join(f"{name[:8]:>10}" for name in SUBFIELD_CLASSES)
    print(f"{'':>15}{header}")
    for i, row in enumerate(cm):
        row_str = "".join(f"{val:>10}" for val in row)
        print(f"{SUBFIELD_CLASSES[i]:>15}{row_str}")

    # Save training metrics
    metrics = {
        "model": "subfield_classifier",
        "architecture": "DistilBERT + Linear(768,256) + ReLU + Dropout(0.3) + Linear(256,15)",
        "best_epoch": best_epoch,
        "best_val_f1": best_f1,
        "test_accuracy": test_metrics["accuracy"],
        "test_f1_macro": test_metrics["f1_macro"],
        "test_f1_weighted": test_metrics["f1_weighted"],
        "hyperparameters": {
            "epochs": args.epochs,
            "batch_size": args.batch_size,
            "learning_rate": args.lr,
            "warmup_ratio": args.warmup_ratio,
            "weight_decay": args.weight_decay,
            "dropout": args.dropout,
            "max_seq_len": MAX_SEQ_LEN,
        },
        "training_history": training_history,
        "classification_report": classification_report(
            test_metrics["labels"],
            test_metrics["predictions"],
            target_names=target_names,
            output_dict=True,
            zero_division=0,
        ),
    }

    with open(os.path.join(args.output_dir, "training_metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)

    logger.info(f"\nModel saved to {args.output_dir}")

    # ── Baseline Comparison ──────────────────────────────────────────────────

    if not args.skip_baseline:
        baseline_metrics = train_baseline(args.data_dir, args.output_dir)
        logger.info("\n" + "=" * 60)
        logger.info("Model Comparison")
        logger.info("=" * 60)
        logger.info(f"  DistilBERT — Test Acc: {test_metrics['accuracy']:.4f}, F1: {test_metrics['f1_macro']:.4f}")
        logger.info(f"  TF-IDF+LR  — Test Acc: {baseline_metrics['test_acc']:.4f}, F1: {baseline_metrics['test_f1']:.4f}")

    logger.info("\nTraining complete.")


if __name__ == "__main__":
    main()
