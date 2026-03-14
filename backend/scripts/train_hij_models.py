"""
HIJ ML Model Training Pipeline
================================
End-to-end script to generate training data and train both ML models:
  1. Paper Type Classifier (TF-IDF + LogReg)
  2. Journal Tier Predictor (TF-IDF + LogReg)

This is a simpler, lightweight alternative to the DistilBERT-based training
scripts in oncology_model/. It produces models that are fast to load,
require no GPU, and integrate directly with the HIJ services.

Usage:
    # Full pipeline: generate data + train both models
    python -m scripts.train_hij_models

    # Generate data only
    python -m scripts.train_hij_models --data-only --target 3000

    # Train only (assumes data already exists)
    python -m scripts.train_hij_models --train-only

    # Quick test with small dataset
    python -m scripts.train_hij_models --target 500 --skip-tier

Options:
    --target N          Target number of training papers (default: 5000)
    --data-dir DIR      Data directory (default: data/oncology_training)
    --model-dir DIR     Model output directory (default: models)
    --data-only         Only generate training data, skip training
    --train-only        Only train models, skip data generation
    --skip-paper-type   Skip paper type classifier training
    --skip-tier         Skip tier predictor training
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
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    f1_score,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Paper Type Classifier Training
# ---------------------------------------------------------------------------

PAPER_TYPE_CLASSES = ["experimental", "review", "meta_analysis", "case_report", "protocol"]


MAX_TRAIN_SAMPLES = 100000  # TF-IDF+LogReg has diminishing returns above ~50K


def load_paper_type_data(filepath: str, max_samples: int = 0):
    """Load texts and paper_type labels from JSONL."""
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
                if max_samples and len(texts) >= max_samples:
                    break
    return texts, labels


def train_paper_type_classifier(data_dir: Path, output_dir: Path):
    """Train TF-IDF + LogReg paper type classifier."""
    logger.info("=" * 60)
    logger.info("Training Paper Type Classifier (TF-IDF + LogReg)")
    logger.info("=" * 60)

    train_texts, train_labels = load_paper_type_data(str(data_dir / "train.jsonl"), max_samples=MAX_TRAIN_SAMPLES)
    val_texts, val_labels = load_paper_type_data(str(data_dir / "val.jsonl"))
    test_texts, test_labels = load_paper_type_data(str(data_dir / "test.jsonl"))

    logger.info(f"Data: train={len(train_texts)}, val={len(val_texts)}, test={len(test_texts)}")

    if not train_texts:
        logger.error("No training data found for paper type classifier")
        return None

    # Class distribution
    train_dist = Counter(train_labels)
    logger.info("Training class distribution:")
    for cls in PAPER_TYPE_CLASSES:
        logger.info(f"  {cls}: {train_dist.get(cls, 0)}")

    # TF-IDF with unigrams + bigrams (max_features=20000 for memory safety)
    tfidf = TfidfVectorizer(
        max_features=20000,
        ngram_range=(1, 2),
        sublinear_tf=True,
        strip_accents="unicode",
        min_df=3,
        max_df=0.95,
    )
    X_train = tfidf.fit_transform(train_texts)
    # Free raw texts after vectorization to save memory
    del train_texts
    X_val = tfidf.transform(val_texts)
    del val_texts
    X_test = tfidf.transform(test_texts)
    del test_texts

    logger.info(f"TF-IDF vocabulary: {len(tfidf.vocabulary_)}, features: {X_train.shape}")

    # Grid search over regularization strength
    # n_jobs=1 to avoid forking (memory-safe for 2GB ECS containers)
    best_c = 1.0
    best_val_f1 = 0.0
    for c_val in [0.1, 1.0, 10.0]:
        clf = LogisticRegression(
            max_iter=500,
            class_weight="balanced",
            C=c_val,
            solver="saga",
            n_jobs=1,
        )
        clf.fit(X_train, train_labels)
        val_preds = clf.predict(X_val)
        val_f1 = f1_score(val_labels, val_preds, average="macro", zero_division=0)
        logger.info(f"  C={c_val}: Val F1={val_f1:.4f}")
        if val_f1 > best_val_f1:
            best_val_f1 = val_f1
            best_c = c_val

    logger.info(f"Best C={best_c}, Val F1={best_val_f1:.4f}")

    # Retrain with best C
    clf = LogisticRegression(
        max_iter=500,
        class_weight="balanced",
        C=best_c,
        solver="saga",
        n_jobs=1,
    )
    clf.fit(X_train, train_labels)

    # Evaluate on test set
    test_preds = clf.predict(X_test)
    test_acc = accuracy_score(test_labels, test_preds)
    test_f1 = f1_score(test_labels, test_preds, average="macro", zero_division=0)

    logger.info(f"\nTest Accuracy: {test_acc:.4f}")
    logger.info(f"Test F1 (macro): {test_f1:.4f}")
    logger.info("\nClassification Report:")
    print(classification_report(test_labels, test_preds, target_names=PAPER_TYPE_CLASSES, zero_division=0))

    # Save model
    model_dir = output_dir / "paper_type_classifier" / "tfidf_primary"
    model_dir.mkdir(parents=True, exist_ok=True)

    with open(model_dir / "tfidf_vectorizer.pkl", "wb") as f:
        pickle.dump(tfidf, f)
    with open(model_dir / "logreg_model.pkl", "wb") as f:
        pickle.dump(clf, f)

    # Save label mappings
    label_info = {
        "classes": PAPER_TYPE_CLASSES,
        "best_C": best_c,
        "test_accuracy": test_acc,
        "test_f1_macro": test_f1,
    }
    with open(model_dir / "label_mappings.json", "w") as f:
        json.dump(label_info, f, indent=2)

    logger.info(f"Paper type model saved to {model_dir}")

    # Top features per class
    feature_names = np.array(tfidf.get_feature_names_out())
    logger.info("\nTop-10 features per class:")
    for i, cls in enumerate(clf.classes_):
        top_indices = np.argsort(clf.coef_[i])[-10:][::-1]
        top_features = feature_names[top_indices]
        logger.info(f"  {cls}: {', '.join(top_features)}")

    return {"test_acc": test_acc, "test_f1": test_f1, "best_c": best_c}


# ---------------------------------------------------------------------------
# Tier Predictor Training
# ---------------------------------------------------------------------------

TIER_CLASSES = ["Tier1", "Tier2", "Tier3"]


def load_tier_data(filepath: str, max_samples: int = 0):
    """Load texts, metadata features, and tier labels from JSONL."""
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
            tier = record.get("tier", "")
            if tier not in TIER_CLASSES:
                continue

            # Build text with metadata appended as pseudo-tokens
            paper_type = record.get("paper_type", "experimental")
            author_count = record.get("author_count", 1)
            ref_count = record.get("ref_count", 20)
            has_funding = record.get("has_funding", False)
            institution_count = record.get("institution_count", 1)
            is_multicenter = record.get("is_multicenter", False)

            meta_text = (
                f" __AUTHORS_{min(author_count, 50)}__"
                f" __REFS_{min(ref_count, 200)}__"
                f" __TYPE_{paper_type}__"
                f" __INSTITUTIONS_{min(institution_count, 20)}__"
            )
            if has_funding:
                meta_text += " __FUNDED__"
            if is_multicenter:
                meta_text += " __MULTICENTER__"

            text = f"{title} {abstract[:2000]}{meta_text}"
            texts.append(text)
            labels.append(tier)
            if max_samples and len(texts) >= max_samples:
                break

    return texts, labels


def train_tier_predictor(data_dir: Path, output_dir: Path):
    """Train TF-IDF + LogReg tier predictor."""
    logger.info("=" * 60)
    logger.info("Training Journal Tier Predictor (TF-IDF + LogReg)")
    logger.info("=" * 60)

    train_texts, train_labels = load_tier_data(str(data_dir / "train.jsonl"), max_samples=MAX_TRAIN_SAMPLES)
    val_texts, val_labels = load_tier_data(str(data_dir / "val.jsonl"))
    test_texts, test_labels = load_tier_data(str(data_dir / "test.jsonl"))

    logger.info(f"Data: train={len(train_texts)}, val={len(val_texts)}, test={len(test_texts)}")

    if not train_texts:
        logger.error("No training data found for tier predictor")
        return None

    # Class distribution
    train_dist = Counter(train_labels)
    logger.info("Training class distribution:")
    for cls in TIER_CLASSES:
        logger.info(f"  {cls}: {train_dist.get(cls, 0)}")

    # TF-IDF (max_features=20000 for memory safety)
    tfidf = TfidfVectorizer(
        max_features=20000,
        ngram_range=(1, 2),
        sublinear_tf=True,
        strip_accents="unicode",
        min_df=3,
        max_df=0.95,
    )
    X_train = tfidf.fit_transform(train_texts)
    del train_texts
    X_val = tfidf.transform(val_texts)
    del val_texts
    X_test = tfidf.transform(test_texts)
    del test_texts

    logger.info(f"TF-IDF vocabulary: {len(tfidf.vocabulary_)}, features: {X_train.shape}")

    # Grid search
    # n_jobs=1 to avoid forking (memory-safe for 2GB ECS containers)
    best_c = 1.0
    best_val_f1 = 0.0
    for c_val in [0.1, 1.0, 10.0]:
        clf = LogisticRegression(
            max_iter=500,
            class_weight="balanced",
            C=c_val,
            solver="saga",
            n_jobs=1,
        )
        clf.fit(X_train, train_labels)
        val_preds = clf.predict(X_val)
        val_f1 = f1_score(val_labels, val_preds, average="macro", zero_division=0)
        logger.info(f"  C={c_val}: Val F1={val_f1:.4f}")
        if val_f1 > best_val_f1:
            best_val_f1 = val_f1
            best_c = c_val

    logger.info(f"Best C={best_c}, Val F1={best_val_f1:.4f}")

    # Retrain with best C
    clf = LogisticRegression(
        max_iter=500,
        class_weight="balanced",
        C=best_c,
        solver="saga",
        n_jobs=1,
    )
    clf.fit(X_train, train_labels)

    # Evaluate
    test_preds = clf.predict(X_test)
    test_acc = accuracy_score(test_labels, test_preds)
    test_f1 = f1_score(test_labels, test_preds, average="macro", zero_division=0)

    logger.info(f"\nTest Accuracy: {test_acc:.4f}")
    logger.info(f"Test F1 (macro): {test_f1:.4f}")
    logger.info("\nClassification Report:")
    # Use labels param to handle cases where not all classes appear in test set
    present_labels = sorted(set(test_labels) | set(test_preds))
    present_names = [t for t in TIER_CLASSES if t in present_labels]
    print(classification_report(
        test_labels, test_preds,
        labels=present_labels,
        target_names=present_names,
        zero_division=0,
    ))

    # Save model
    model_dir = output_dir / "tier_predictor" / "tfidf"
    model_dir.mkdir(parents=True, exist_ok=True)

    with open(model_dir / "tfidf_vectorizer.pkl", "wb") as f:
        pickle.dump(tfidf, f)
    with open(model_dir / "logreg_model.pkl", "wb") as f:
        pickle.dump(clf, f)

    label_info = {
        "classes": TIER_CLASSES,
        "best_C": best_c,
        "test_accuracy": test_acc,
        "test_f1_macro": test_f1,
    }
    with open(model_dir / "label_mappings.json", "w") as f:
        json.dump(label_info, f, indent=2)

    logger.info(f"Tier predictor model saved to {model_dir}")

    # Top features per class
    feature_names = np.array(tfidf.get_feature_names_out())
    logger.info("\nTop-10 features per class:")
    for i, cls in enumerate(clf.classes_):
        top_indices = np.argsort(clf.coef_[i])[-10:][::-1]
        top_features = feature_names[top_indices]
        logger.info(f"  {cls}: {', '.join(top_features)}")

    return {"test_acc": test_acc, "test_f1": test_f1, "best_c": best_c}


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="HIJ ML Model Training Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m scripts.train_hij_models                     # Full pipeline
  python -m scripts.train_hij_models --target 500        # Quick test
  python -m scripts.train_hij_models --data-only         # Generate data only
  python -m scripts.train_hij_models --train-only        # Train from existing data
        """,
    )
    parser.add_argument("--target", type=int, default=5000, help="Target papers for data generation")
    parser.add_argument("--data-dir", type=str, default="data/oncology_training", help="Training data directory")
    parser.add_argument("--model-dir", type=str, default="models", help="Model output directory")
    parser.add_argument("--data-only", action="store_true", help="Only generate data")
    parser.add_argument("--train-only", action="store_true", help="Only train models")
    parser.add_argument("--skip-paper-type", action="store_true", help="Skip paper type training")
    parser.add_argument("--skip-tier", action="store_true", help="Skip tier predictor training")
    parser.add_argument(
        "--fields", type=str, default=None,
        help="Comma-separated fields for data generation (default: all)",
    )
    args = parser.parse_args()

    backend_dir = Path(__file__).resolve().parent.parent
    data_dir = backend_dir / args.data_dir
    model_dir = backend_dir / args.model_dir

    start_time = time.time()

    # ── Step 1: Generate training data ────────────────────────────────
    if not args.train_only:
        logger.info("=" * 70)
        logger.info("STEP 1: Generating Training Data from OpenAlex")
        logger.info("=" * 70)

        from scripts.generate_training_data import generate_training_data

        fields = None
        if args.fields:
            fields = [f.strip() for f in args.fields.split(",")]

        generate_training_data(data_dir, target_total=args.target, fields=fields)
        logger.info(f"Training data generated in {data_dir}")

    if args.data_only:
        logger.info("Data-only mode. Exiting.")
        return

    # Verify data exists
    if not (data_dir / "train.jsonl").exists():
        logger.error(f"Training data not found at {data_dir / 'train.jsonl'}")
        logger.error("Run with --data-only first or without --train-only")
        sys.exit(1)

    # ── Step 2: Train Paper Type Classifier ───────────────────────────
    pt_metrics = None
    if not args.skip_paper_type:
        logger.info("\n" + "=" * 70)
        logger.info("STEP 2: Training Paper Type Classifier")
        logger.info("=" * 70)
        pt_metrics = train_paper_type_classifier(data_dir, model_dir)

    # ── Step 3: Train Tier Predictor ──────────────────────────────────
    tier_metrics = None
    if not args.skip_tier:
        logger.info("\n" + "=" * 70)
        logger.info("STEP 3: Training Journal Tier Predictor")
        logger.info("=" * 70)
        tier_metrics = train_tier_predictor(data_dir, model_dir)

    # ── Summary ───────────────────────────────────────────────────────
    elapsed = time.time() - start_time
    logger.info("\n" + "=" * 70)
    logger.info("TRAINING PIPELINE COMPLETE")
    logger.info("=" * 70)
    logger.info(f"Total time: {elapsed:.1f}s ({elapsed / 60:.1f} minutes)")
    logger.info(f"Data directory: {data_dir}")
    logger.info(f"Model directory: {model_dir}")

    if pt_metrics:
        logger.info(f"\nPaper Type Classifier:")
        logger.info(f"  Test Accuracy: {pt_metrics['test_acc']:.4f}")
        logger.info(f"  Test F1 (macro): {pt_metrics['test_f1']:.4f}")
        logger.info(f"  Best C: {pt_metrics['best_c']}")
        logger.info(f"  Model: {model_dir / 'paper_type_classifier' / 'tfidf_primary'}")

    if tier_metrics:
        logger.info(f"\nJournal Tier Predictor:")
        logger.info(f"  Test Accuracy: {tier_metrics['test_acc']:.4f}")
        logger.info(f"  Test F1 (macro): {tier_metrics['test_f1']:.4f}")
        logger.info(f"  Best C: {tier_metrics['best_c']}")
        logger.info(f"  Model: {model_dir / 'tier_predictor' / 'tfidf'}")

    logger.info("\nThe trained models will be automatically used by:")
    logger.info("  - PaperTypeDetector (services/paper_type_detector.py)")
    logger.info("  - MLTierPredictor (services/ml_tier_predictor.py)")
    logger.info("  - JournalScorerService (services/journal_scorer_service.py)")
    logger.info("\nModels are loaded lazily on first use. No restart needed,")
    logger.info("but restarting the backend will pick up fresh models.")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
