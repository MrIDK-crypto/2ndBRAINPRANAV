"""
Train Paper Type Classifier (Model 3)
Classifies oncology papers into 5 types:
    experimental, review, meta_analysis, case_report, protocol

Trains two models:
    1. TF-IDF + LogisticRegression (primary — research showed similar accuracy to BERT)
    2. DistilBERT variant (for comparison)

Usage:
    python -m oncology_model.train_paper_type \
        --data_dir data/oncology_training \
        --output_dir models/paper_type_classifier \
        --epochs 3 --batch_size 32 --lr 2e-5
"""

import argparse
import json
import logging
import os
import pickle
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

PAPER_TYPE_CLASSES = [
    "experimental",
    "review",
    "meta_analysis",
    "case_report",
    "protocol",
]

NUM_CLASSES = len(PAPER_TYPE_CLASSES)
MAX_SEQ_LEN = 512
DISTILBERT_HIDDEN = 768


# ── Dataset ──────────────────────────────────────────────────────────────────

class PaperTypeDataset(Dataset):
    """Dataset for paper type classification."""

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
                paper_type = record.get("paper_type", "")

                if paper_type not in self.label2id:
                    logger.warning(
                        f"Unknown paper_type '{paper_type}' at line {line_num}, skipping"
                    )
                    continue

                text = f"{title} [SEP] {abstract}"
                self.samples.append((text, self.label2id[paper_type]))

        logger.info(f"Loaded {len(self.samples)} samples from {filepath}")

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


# ── DistilBERT Model ────────────────────────────────────────────────────────

class PaperTypeClassifier(nn.Module):
    """DistilBERT + classification head for paper type prediction."""

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
        cls_output = outputs.last_hidden_state[:, 0, :]
        logits = self.classifier(cls_output)
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


def load_raw_texts(filepath: str):
    """Load raw text + labels from JSONL for TF-IDF model."""
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
            paper_type = record.get("paper_type", "")
            if paper_type in PAPER_TYPE_CLASSES:
                texts.append(f"{title} {abstract}")
                labels.append(paper_type)
    return texts, labels


def compute_class_weights(dataset: PaperTypeDataset, num_classes: int, device):
    """Compute inverse-frequency class weights."""
    label_counts = Counter()
    for _, label in dataset.samples:
        label_counts[label] += 1

    total = len(dataset.samples)
    weights = []
    for i in range(num_classes):
        count = label_counts.get(i, 1)
        weights.append(total / (num_classes * count))

    weights_tensor = torch.tensor(weights, dtype=torch.float32).to(device)
    logger.info(
        f"Class weights: {dict(zip(PAPER_TYPE_CLASSES, [f'{w:.3f}' for w in weights]))}"
    )
    return weights_tensor


# ── TF-IDF Baseline (Primary Model) ─────────────────────────────────────────

def train_tfidf_model(data_dir: str, output_dir: str):
    """Train TF-IDF + LogisticRegression (primary model for paper type)."""
    logger.info("=" * 60)
    logger.info("Training TF-IDF + LogisticRegression (Primary Model)")
    logger.info("=" * 60)

    train_texts, train_labels = load_raw_texts(os.path.join(data_dir, "train.jsonl"))
    val_texts, val_labels = load_raw_texts(os.path.join(data_dir, "val.jsonl"))
    test_texts, test_labels = load_raw_texts(os.path.join(data_dir, "test.jsonl"))

    logger.info(
        f"TF-IDF data: train={len(train_texts)}, val={len(val_texts)}, test={len(test_texts)}"
    )

    # Class distribution
    train_dist = Counter(train_labels)
    logger.info("Training class distribution:")
    for cls in PAPER_TYPE_CLASSES:
        logger.info(f"  {cls}: {train_dist.get(cls, 0)}")

    # TF-IDF with bigrams
    tfidf = TfidfVectorizer(
        max_features=30000,
        ngram_range=(1, 2),
        sublinear_tf=True,
        strip_accents="unicode",
        min_df=2,
        max_df=0.95,
    )
    X_train = tfidf.fit_transform(train_texts)
    X_val = tfidf.transform(val_texts)
    X_test = tfidf.transform(test_texts)

    logger.info(f"TF-IDF vocabulary size: {len(tfidf.vocabulary_)}")
    logger.info(f"Feature matrix shape: {X_train.shape}")

    # Grid search over C values
    best_c = 1.0
    best_val_f1 = 0.0
    for c_val in [0.1, 0.5, 1.0, 5.0, 10.0]:
        clf = LogisticRegression(
            max_iter=1000,
            class_weight="balanced",
            C=c_val,
            solver="lbfgs",
            multi_class="multinomial",
            n_jobs=-1,
        )
        clf.fit(X_train, train_labels)
        val_preds = clf.predict(X_val)
        val_f1 = f1_score(val_labels, val_preds, average="macro", zero_division=0)
        logger.info(f"  C={c_val}: Val F1={val_f1:.4f}")
        if val_f1 > best_val_f1:
            best_val_f1 = val_f1
            best_c = c_val

    logger.info(f"Best C={best_c} with Val F1={best_val_f1:.4f}")

    # Retrain with best C
    clf = LogisticRegression(
        max_iter=1000,
        class_weight="balanced",
        C=best_c,
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

    logger.info(f"\nTF-IDF+LR Val  — Acc: {val_acc:.4f}, F1 (macro): {val_f1:.4f}")
    logger.info(f"TF-IDF+LR Test — Acc: {test_acc:.4f}, F1 (macro): {test_f1:.4f}")

    logger.info("\nTF-IDF Test Classification Report:")
    print(
        classification_report(
            test_labels, test_preds, target_names=PAPER_TYPE_CLASSES, zero_division=0
        )
    )

    # Confusion matrix
    cm = confusion_matrix(test_labels, test_preds, labels=PAPER_TYPE_CLASSES)
    logger.info("Confusion Matrix:")
    header = "".join(f"{name[:12]:>14}" for name in PAPER_TYPE_CLASSES)
    print(f"{'':>14}{header}")
    for i, row in enumerate(cm):
        row_str = "".join(f"{val:>14}" for val in row)
        print(f"{PAPER_TYPE_CLASSES[i]:>14}{row_str}")

    # Save TF-IDF model (primary)
    tfidf_dir = os.path.join(output_dir, "tfidf_primary")
    os.makedirs(tfidf_dir, exist_ok=True)
    with open(os.path.join(tfidf_dir, "tfidf_vectorizer.pkl"), "wb") as f:
        pickle.dump(tfidf, f)
    with open(os.path.join(tfidf_dir, "logreg_model.pkl"), "wb") as f:
        pickle.dump(clf, f)

    # Save label mappings for TF-IDF model
    with open(os.path.join(tfidf_dir, "label_mappings.json"), "w") as f:
        json.dump({"classes": PAPER_TYPE_CLASSES, "best_C": best_c}, f, indent=2)

    logger.info(f"TF-IDF model saved to {tfidf_dir}")

    # Top features per class
    logger.info("\nTop-10 TF-IDF features per class:")
    feature_names = np.array(tfidf.get_feature_names_out())
    for i, cls in enumerate(clf.classes_):
        top_indices = np.argsort(clf.coef_[i])[-10:][::-1]
        top_features = feature_names[top_indices]
        logger.info(f"  {cls}: {', '.join(top_features)}")

    return {
        "val_acc": val_acc,
        "val_f1": val_f1,
        "test_acc": test_acc,
        "test_f1": test_f1,
        "best_c": best_c,
    }


# ── DistilBERT Training ─────────────────────────────────────────────────────

def train_distilbert_model(args, device):
    """Train DistilBERT variant for comparison."""
    logger.info("=" * 60)
    logger.info("Training DistilBERT Variant (Comparison)")
    logger.info("=" * 60)

    label2id = {label: idx for idx, label in enumerate(PAPER_TYPE_CLASSES)}
    id2label = {idx: label for idx, label in enumerate(PAPER_TYPE_CLASSES)}

    tokenizer = DistilBertTokenizer.from_pretrained("distilbert-base-uncased")

    train_dataset = PaperTypeDataset(
        os.path.join(args.data_dir, "train.jsonl"), tokenizer, label2id
    )
    val_dataset = PaperTypeDataset(
        os.path.join(args.data_dir, "val.jsonl"), tokenizer, label2id
    )
    test_dataset = PaperTypeDataset(
        os.path.join(args.data_dir, "test.jsonl"), tokenizer, label2id
    )

    train_loader = DataLoader(
        train_dataset, batch_size=args.batch_size, shuffle=True, num_workers=2, pin_memory=True
    )
    val_loader = DataLoader(
        val_dataset, batch_size=args.batch_size, shuffle=False, num_workers=2, pin_memory=True
    )
    test_loader = DataLoader(
        test_dataset, batch_size=args.batch_size, shuffle=False, num_workers=2, pin_memory=True
    )

    model = PaperTypeClassifier(num_classes=NUM_CLASSES, dropout=args.dropout).to(device)

    class_weights = compute_class_weights(train_dataset, NUM_CLASSES, device)
    criterion = nn.CrossEntropyLoss(weight=class_weights)

    optimizer = torch.optim.AdamW(
        model.parameters(), lr=args.lr, weight_decay=args.weight_decay
    )
    total_steps = len(train_loader) * args.epochs
    warmup_steps = int(total_steps * args.warmup_ratio)
    scheduler = get_linear_schedule_with_warmup(
        optimizer, num_warmup_steps=warmup_steps, num_training_steps=total_steps
    )

    best_f1 = 0.0
    best_epoch = -1

    for epoch in range(1, args.epochs + 1):
        epoch_start = time.time()
        logger.info(f"\n--- Epoch {epoch}/{args.epochs} ---")

        # Train
        model.train()
        total_loss = 0.0
        correct = 0
        total = 0

        for step, batch in enumerate(train_loader, 1):
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
            preds = torch.argmax(logits, dim=-1)
            correct += (preds == labels).sum().item()
            total += labels.size(0)

            if step % args.log_every == 0:
                logger.info(
                    f"  Step {step}/{len(train_loader)} | "
                    f"Loss: {total_loss/step:.4f} | Acc: {correct/total:.4f}"
                )

        train_loss = total_loss / len(train_loader)
        train_acc = correct / total if total > 0 else 0.0

        # Validate
        model.eval()
        val_loss = 0.0
        val_preds_list = []
        val_labels_list = []
        with torch.no_grad():
            for batch in val_loader:
                input_ids = batch["input_ids"].to(device)
                attention_mask = batch["attention_mask"].to(device)
                labels = batch["label"].to(device)
                logits = model(input_ids, attention_mask)
                loss = criterion(logits, labels)
                val_loss += loss.item()
                preds = torch.argmax(logits, dim=-1)
                val_preds_list.extend(preds.cpu().numpy())
                val_labels_list.extend(labels.cpu().numpy())

        val_loss /= len(val_loader) if len(val_loader) > 0 else 1
        val_acc = accuracy_score(val_labels_list, val_preds_list)
        val_f1 = f1_score(val_labels_list, val_preds_list, average="macro", zero_division=0)

        epoch_time = time.time() - epoch_start
        logger.info(
            f"Epoch {epoch} ({epoch_time:.1f}s) | Train: loss={train_loss:.4f} acc={train_acc:.4f} | "
            f"Val: loss={val_loss:.4f} acc={val_acc:.4f} F1={val_f1:.4f}"
        )

        if val_f1 > best_f1:
            best_f1 = val_f1
            best_epoch = epoch
            logger.info(f"  New best F1: {best_f1:.4f} — saving model")
            bert_dir = os.path.join(args.output_dir, "distilbert_comparison")
            os.makedirs(bert_dir, exist_ok=True)
            torch.save(model.state_dict(), os.path.join(bert_dir, "best_model.pt"))
            tokenizer.save_pretrained(os.path.join(bert_dir, "tokenizer"))

    # Test set evaluation
    model.load_state_dict(
        torch.load(
            os.path.join(args.output_dir, "distilbert_comparison", "best_model.pt"),
            map_location=device,
        )
    )
    model.eval()
    test_preds_list = []
    test_labels_list = []
    with torch.no_grad():
        for batch in test_loader:
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["label"].to(device)
            logits = model(input_ids, attention_mask)
            preds = torch.argmax(logits, dim=-1)
            test_preds_list.extend(preds.cpu().numpy())
            test_labels_list.extend(labels.cpu().numpy())

    test_acc = accuracy_score(test_labels_list, test_preds_list)
    test_f1 = f1_score(test_labels_list, test_preds_list, average="macro", zero_division=0)

    target_names = [id2label[i] for i in range(NUM_CLASSES)]
    logger.info(f"\nDistilBERT Test — Acc: {test_acc:.4f}, F1 (macro): {test_f1:.4f}")
    logger.info("\nDistilBERT Test Classification Report:")
    print(
        classification_report(
            test_labels_list, test_preds_list, target_names=target_names, zero_division=0
        )
    )

    return {
        "val_f1": best_f1,
        "test_acc": test_acc,
        "test_f1": test_f1,
        "best_epoch": best_epoch,
    }


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Train Paper Type Classifier")
    parser.add_argument("--data_dir", type=str, required=True, help="Directory with train/val/test JSONL files")
    parser.add_argument("--output_dir", type=str, required=True, help="Directory to save trained models")
    parser.add_argument("--epochs", type=int, default=3, help="DistilBERT training epochs")
    parser.add_argument("--batch_size", type=int, default=32, help="Batch size")
    parser.add_argument("--lr", type=float, default=2e-5, help="Learning rate")
    parser.add_argument("--warmup_ratio", type=float, default=0.1, help="Warmup ratio")
    parser.add_argument("--weight_decay", type=float, default=0.01, help="Weight decay")
    parser.add_argument("--dropout", type=float, default=0.3, help="Dropout")
    parser.add_argument("--log_every", type=int, default=100, help="Log every N steps")
    parser.add_argument("--skip_distilbert", action="store_true", help="Skip DistilBERT comparison")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)

    device = get_device()
    os.makedirs(args.output_dir, exist_ok=True)

    # Save label mappings
    label2id = {label: idx for idx, label in enumerate(PAPER_TYPE_CLASSES)}
    label_mappings = {
        "label2id": label2id,
        "id2label": {str(idx): label for idx, label in enumerate(PAPER_TYPE_CLASSES)},
        "classes": PAPER_TYPE_CLASSES,
        "num_classes": NUM_CLASSES,
        "primary_model": "tfidf",
    }
    with open(os.path.join(args.output_dir, "label_mappings.json"), "w") as f:
        json.dump(label_mappings, f, indent=2)

    # Train TF-IDF model (primary)
    tfidf_metrics = train_tfidf_model(args.data_dir, args.output_dir)

    # Train DistilBERT model (comparison)
    bert_metrics = None
    if not args.skip_distilbert:
        bert_metrics = train_distilbert_model(args, device)

    # ── Final Comparison ─────────────────────────────────────────────────────

    logger.info("\n" + "=" * 60)
    logger.info("Final Model Comparison")
    logger.info("=" * 60)
    logger.info(
        f"  TF-IDF+LR   — Test Acc: {tfidf_metrics['test_acc']:.4f}, F1: {tfidf_metrics['test_f1']:.4f}"
    )
    if bert_metrics:
        logger.info(
            f"  DistilBERT   — Test Acc: {bert_metrics['test_acc']:.4f}, F1: {bert_metrics['test_f1']:.4f}"
        )
        if tfidf_metrics["test_f1"] >= bert_metrics["test_f1"] * 0.95:
            logger.info(
                "  -> TF-IDF+LR is recommended (similar accuracy, much faster inference)"
            )
        else:
            logger.info(
                "  -> DistilBERT is recommended (significantly better accuracy)"
            )

    # Save combined metrics
    combined_metrics = {
        "model": "paper_type_classifier",
        "primary_model": "tfidf",
        "tfidf_metrics": tfidf_metrics,
        "distilbert_metrics": bert_metrics,
    }
    with open(os.path.join(args.output_dir, "training_metrics.json"), "w") as f:
        json.dump(combined_metrics, f, indent=2, default=str)

    logger.info(f"\nModels saved to {args.output_dir}")
    logger.info("Training complete.")


if __name__ == "__main__":
    main()
