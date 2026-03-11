"""
Oncology Model Suite — Runtime Inference Module

Loads all 3 trained oncology models and provides unified prediction interface
for use in the journal scorer service.

Models:
    1. Subfield Classifier — 15-class oncology sub-field prediction
    2. Tier Predictor — 3-class journal tier prediction (with metadata)
    3. Paper Type Classifier — 5-class paper type (TF-IDF primary, DistilBERT fallback)

Usage:
    from oncology_model.inference import OncologyModelSuite

    suite = OncologyModelSuite(model_dir="models/oncology")
    # or from S3:
    suite = OncologyModelSuite(s3_bucket="secondbrain-oncology-models")

    subfield, confidence, probs = suite.predict_subfield("Title", "Abstract...")
    tier, confidence, probs = suite.predict_tier("Title", "Abstract...", author_count=5, ref_count=40)
    paper_type, confidence = suite.predict_paper_type("Title", "Abstract...")

    # Batch prediction
    results = suite.predict_subfield_batch([("Title1", "Abstract1"), ("Title2", "Abstract2")])
"""

import json
import logging
import os
import pickle
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import torch
import torch.nn as nn
from transformers import DistilBertTokenizer, DistilBertModel

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

MAX_SEQ_LEN = 512
DISTILBERT_HIDDEN = 768


# ── Model Definitions (must match training scripts) ─────────────────────────

class SubfieldClassifier(nn.Module):
    """DistilBERT + classification head for 15-class sub-field prediction."""

    def __init__(self, num_classes: int = 15, dropout: float = 0.3):
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


class TierPredictor(nn.Module):
    """DistilBERT + metadata -> 3-class journal tier prediction."""

    def __init__(self, num_classes: int = 3, metadata_dim: int = 10, dropout: float = 0.3):
        super().__init__()
        self.distilbert = DistilBertModel.from_pretrained("distilbert-base-uncased")
        combined_dim = DISTILBERT_HIDDEN + metadata_dim
        self.classifier = nn.Sequential(
            nn.Linear(combined_dim, 256),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(256, num_classes),
        )

    def forward(self, input_ids, attention_mask, metadata):
        outputs = self.distilbert(input_ids=input_ids, attention_mask=attention_mask)
        cls_output = outputs.last_hidden_state[:, 0, :]
        combined = torch.cat([cls_output, metadata], dim=-1)
        logits = self.classifier(combined)
        return logits


class PaperTypeClassifier(nn.Module):
    """DistilBERT + classification head for 5-class paper type."""

    def __init__(self, num_classes: int = 5, dropout: float = 0.3):
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


# ── Oncology Model Suite ─────────────────────────────────────────────────────

PAPER_TYPES_LIST = ["experimental", "review", "meta_analysis", "case_report", "protocol"]


class OncologyModelSuite:
    """
    Unified inference class that lazily loads all 3 oncology models.

    Supports loading from:
        - Local directory
        - S3 bucket (downloads to temp dir on first use)
    """

    def __init__(
        self,
        model_dir: Optional[str] = None,
        s3_bucket: Optional[str] = None,
        s3_prefix: str = "",
        device: Optional[str] = None,
    ):
        """
        Initialize the model suite.

        Args:
            model_dir: Local path containing model subdirectories
                       (subfield_classifier/, tier_predictor/, paper_type_classifier/)
            s3_bucket: S3 bucket name (alternative to model_dir)
            s3_prefix: Prefix within the S3 bucket
            device: Force device ('cuda', 'mps', 'cpu'). Auto-detects if None.
        """
        if model_dir is None and s3_bucket is None:
            raise ValueError("Must provide either model_dir or s3_bucket")

        self.model_dir = model_dir
        self.s3_bucket = s3_bucket
        self.s3_prefix = s3_prefix.rstrip("/")

        # Device auto-detection
        if device:
            self.device = torch.device(device)
        elif torch.cuda.is_available():
            self.device = torch.device("cuda")
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            self.device = torch.device("mps")
        else:
            self.device = torch.device("cpu")

        logger.info(f"OncologyModelSuite initialized on device: {self.device}")

        # Lazy-loaded model state
        self._subfield_model = None
        self._subfield_tokenizer = None
        self._subfield_mappings = None

        self._tier_model = None
        self._tier_tokenizer = None
        self._tier_mappings = None

        self._paper_type_tfidf = None
        self._paper_type_logreg = None
        self._paper_type_bert_model = None
        self._paper_type_bert_tokenizer = None
        self._paper_type_mappings = None
        self._paper_type_use_bert = False  # default to TF-IDF

        self._s3_local_cache = None  # temp dir for S3 downloads

    # ── S3 Download ──────────────────────────────────────────────────────────

    def _ensure_local_dir(self) -> str:
        """Ensure models are available locally (download from S3 if needed)."""
        if self.model_dir and os.path.isdir(self.model_dir):
            return self.model_dir

        if self.s3_bucket:
            if self._s3_local_cache and os.path.isdir(self._s3_local_cache):
                return self._s3_local_cache
            return self._download_from_s3()

        raise FileNotFoundError(
            f"Model directory not found: {self.model_dir}"
        )

    def _download_from_s3(self) -> str:
        """Download model files from S3 to a temporary directory."""
        try:
            import boto3
        except ImportError:
            raise ImportError("boto3 is required for S3 model loading: pip install boto3")

        logger.info(f"Downloading models from s3://{self.s3_bucket}/{self.s3_prefix}")
        s3 = boto3.client("s3")

        temp_dir = tempfile.mkdtemp(prefix="oncology_models_")
        self._s3_local_cache = temp_dir

        # List all objects under prefix
        paginator = s3.get_paginator("list_objects_v2")
        prefix = f"{self.s3_prefix}/" if self.s3_prefix else ""

        for page in paginator.paginate(Bucket=self.s3_bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                # Strip the prefix to get relative path
                rel_path = key[len(prefix):] if prefix else key
                if not rel_path:
                    continue

                local_path = os.path.join(temp_dir, rel_path)
                os.makedirs(os.path.dirname(local_path), exist_ok=True)

                logger.debug(f"  Downloading {key} -> {local_path}")
                s3.download_file(self.s3_bucket, key, local_path)

        logger.info(f"Models downloaded to {temp_dir}")
        return temp_dir

    # ── Subfield Classifier (Model 1) ────────────────────────────────────────

    def _load_subfield_model(self):
        """Load subfield classifier on first use."""
        if self._subfield_model is not None:
            return

        base_dir = self._ensure_local_dir()
        model_path = os.path.join(base_dir, "subfield_classifier")

        logger.info(f"Loading subfield classifier from {model_path}")

        # Load label mappings
        with open(os.path.join(model_path, "label_mappings.json"), "r") as f:
            self._subfield_mappings = json.load(f)

        num_classes = self._subfield_mappings["num_classes"]

        # Load tokenizer
        self._subfield_tokenizer = DistilBertTokenizer.from_pretrained(
            os.path.join(model_path, "tokenizer")
        )

        # Load model
        self._subfield_model = SubfieldClassifier(num_classes=num_classes)
        state_dict = torch.load(
            os.path.join(model_path, "best_model.pt"),
            map_location=self.device,
            weights_only=True,
        )
        self._subfield_model.load_state_dict(state_dict)
        self._subfield_model.to(self.device)
        self._subfield_model.eval()

        logger.info(f"Subfield classifier loaded ({num_classes} classes)")

    def predict_subfield(
        self, title: str, abstract: str
    ) -> Tuple[str, float, Dict[str, float]]:
        """
        Predict the oncology sub-field for a paper.

        Args:
            title: Paper title
            abstract: Paper abstract

        Returns:
            (predicted_label, confidence, all_probabilities)
        """
        self._load_subfield_model()

        text = f"{title} [SEP] {abstract}"
        encoding = self._subfield_tokenizer(
            text,
            max_length=MAX_SEQ_LEN,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )

        input_ids = encoding["input_ids"].to(self.device)
        attention_mask = encoding["attention_mask"].to(self.device)

        with torch.no_grad():
            logits = self._subfield_model(input_ids, attention_mask)
            probs = torch.softmax(logits, dim=-1).squeeze(0).cpu().numpy()

        id2label = self._subfield_mappings["id2label"]
        pred_idx = int(np.argmax(probs))
        pred_label = id2label[str(pred_idx)]
        confidence = float(probs[pred_idx])

        all_probs = {id2label[str(i)]: float(p) for i, p in enumerate(probs)}

        return pred_label, confidence, all_probs

    def predict_subfield_batch(
        self, papers: List[Tuple[str, str]], batch_size: int = 32
    ) -> List[Tuple[str, float, Dict[str, float]]]:
        """
        Batch prediction for sub-field classification.

        Args:
            papers: List of (title, abstract) tuples
            batch_size: Batch size for inference

        Returns:
            List of (predicted_label, confidence, all_probabilities)
        """
        self._load_subfield_model()

        results = []
        id2label = self._subfield_mappings["id2label"]

        for i in range(0, len(papers), batch_size):
            batch_papers = papers[i : i + batch_size]
            texts = [f"{title} [SEP] {abstract}" for title, abstract in batch_papers]

            encodings = self._subfield_tokenizer(
                texts,
                max_length=MAX_SEQ_LEN,
                padding="max_length",
                truncation=True,
                return_tensors="pt",
            )

            input_ids = encodings["input_ids"].to(self.device)
            attention_mask = encodings["attention_mask"].to(self.device)

            with torch.no_grad():
                logits = self._subfield_model(input_ids, attention_mask)
                probs = torch.softmax(logits, dim=-1).cpu().numpy()

            for j in range(len(batch_papers)):
                pred_idx = int(np.argmax(probs[j]))
                pred_label = id2label[str(pred_idx)]
                confidence = float(probs[j][pred_idx])
                all_probs = {id2label[str(k)]: float(p) for k, p in enumerate(probs[j])}
                results.append((pred_label, confidence, all_probs))

        return results

    # ── Tier Predictor (Model 2) ─────────────────────────────────────────────

    def _load_tier_model(self):
        """Load tier predictor on first use."""
        if self._tier_model is not None:
            return

        base_dir = self._ensure_local_dir()
        model_path = os.path.join(base_dir, "tier_predictor")

        logger.info(f"Loading tier predictor from {model_path}")

        with open(os.path.join(model_path, "label_mappings.json"), "r") as f:
            self._tier_mappings = json.load(f)

        num_classes = self._tier_mappings["num_classes"]
        metadata_dim = self._tier_mappings.get("metadata_dim", 10)

        self._tier_tokenizer = DistilBertTokenizer.from_pretrained(
            os.path.join(model_path, "tokenizer")
        )

        self._tier_model = TierPredictor(
            num_classes=num_classes, metadata_dim=metadata_dim
        )
        state_dict = torch.load(
            os.path.join(model_path, "best_model.pt"),
            map_location=self.device,
            weights_only=True,
        )
        self._tier_model.load_state_dict(state_dict)
        self._tier_model.to(self.device)
        self._tier_model.eval()

        logger.info(f"Tier predictor loaded ({num_classes} classes, metadata_dim={metadata_dim})")

    def _encode_tier_metadata(
        self,
        author_count: int = 1,
        ref_count: int = 20,
        paper_type: str = "experimental",
        has_funding: bool = False,
        institution_count: int = 1,
        is_multicenter: bool = False,
    ) -> np.ndarray:
        """Encode metadata features for the tier predictor."""
        features = np.zeros(10, dtype=np.float32)

        # Normalize with reasonable max values (same as training)
        features[0] = min(author_count / 50.0, 1.0)  # author_count
        features[1] = min(ref_count / 200.0, 1.0)  # ref_count

        # Paper type one-hot
        if paper_type in PAPER_TYPES_LIST:
            features[2 + PAPER_TYPES_LIST.index(paper_type)] = 1.0

        features[7] = 1.0 if has_funding else 0.0
        features[8] = min(institution_count / 20.0, 1.0)
        features[9] = 1.0 if is_multicenter else 0.0

        return features

    def predict_tier(
        self,
        title: str,
        abstract: str,
        author_count: int = 1,
        ref_count: int = 20,
        paper_type: str = "experimental",
        has_funding: bool = False,
        institution_count: int = 1,
        is_multicenter: bool = False,
    ) -> Tuple[str, float, Dict[str, float]]:
        """
        Predict journal tier for a paper.

        Args:
            title: Paper title
            abstract: Paper abstract
            author_count: Number of authors
            ref_count: Number of references
            paper_type: Type of paper (experimental, review, etc.)
            has_funding: Whether the paper has funding disclosure
            institution_count: Number of institutions
            is_multicenter: Whether it's a multicenter study

        Returns:
            (predicted_tier, confidence, all_probabilities)
        """
        self._load_tier_model()

        text = f"{title} [SEP] {abstract}"
        encoding = self._tier_tokenizer(
            text,
            max_length=MAX_SEQ_LEN,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )

        input_ids = encoding["input_ids"].to(self.device)
        attention_mask = encoding["attention_mask"].to(self.device)

        metadata = self._encode_tier_metadata(
            author_count, ref_count, paper_type, has_funding, institution_count, is_multicenter
        )
        metadata_tensor = torch.tensor(metadata, dtype=torch.float32).unsqueeze(0).to(self.device)

        with torch.no_grad():
            logits = self._tier_model(input_ids, attention_mask, metadata_tensor)
            probs = torch.softmax(logits, dim=-1).squeeze(0).cpu().numpy()

        id2label = self._tier_mappings["id2label"]
        pred_idx = int(np.argmax(probs))
        pred_label = id2label[str(pred_idx)]
        confidence = float(probs[pred_idx])

        all_probs = {id2label[str(i)]: float(p) for i, p in enumerate(probs)}

        return pred_label, confidence, all_probs

    def predict_tier_batch(
        self,
        papers: List[Dict],
        batch_size: int = 32,
    ) -> List[Tuple[str, float, Dict[str, float]]]:
        """
        Batch prediction for tier classification.

        Args:
            papers: List of dicts with keys: title, abstract, author_count, ref_count,
                    paper_type, has_funding, institution_count, is_multicenter
            batch_size: Batch size for inference

        Returns:
            List of (predicted_tier, confidence, all_probabilities)
        """
        self._load_tier_model()

        results = []
        id2label = self._tier_mappings["id2label"]

        for i in range(0, len(papers), batch_size):
            batch_papers = papers[i : i + batch_size]
            texts = [
                f"{p.get('title', '')} [SEP] {p.get('abstract', '')}"
                for p in batch_papers
            ]

            encodings = self._tier_tokenizer(
                texts,
                max_length=MAX_SEQ_LEN,
                padding="max_length",
                truncation=True,
                return_tensors="pt",
            )

            input_ids = encodings["input_ids"].to(self.device)
            attention_mask = encodings["attention_mask"].to(self.device)

            # Build metadata batch
            metadata_batch = []
            for p in batch_papers:
                meta = self._encode_tier_metadata(
                    author_count=p.get("author_count", 1),
                    ref_count=p.get("ref_count", 20),
                    paper_type=p.get("paper_type", "experimental"),
                    has_funding=p.get("has_funding", False),
                    institution_count=p.get("institution_count", 1),
                    is_multicenter=p.get("is_multicenter", False),
                )
                metadata_batch.append(meta)
            metadata_tensor = torch.tensor(
                np.array(metadata_batch), dtype=torch.float32
            ).to(self.device)

            with torch.no_grad():
                logits = self._tier_model(input_ids, attention_mask, metadata_tensor)
                probs = torch.softmax(logits, dim=-1).cpu().numpy()

            for j in range(len(batch_papers)):
                pred_idx = int(np.argmax(probs[j]))
                pred_label = id2label[str(pred_idx)]
                confidence = float(probs[j][pred_idx])
                all_probs = {id2label[str(k)]: float(p) for k, p in enumerate(probs[j])}
                results.append((pred_label, confidence, all_probs))

        return results

    # ── Paper Type Classifier (Model 3) ──────────────────────────────────────

    def _load_paper_type_model(self):
        """Load paper type classifier on first use. Prefers TF-IDF model."""
        if self._paper_type_tfidf is not None or self._paper_type_bert_model is not None:
            return

        base_dir = self._ensure_local_dir()
        model_path = os.path.join(base_dir, "paper_type_classifier")

        logger.info(f"Loading paper type classifier from {model_path}")

        # Load label mappings
        mappings_path = os.path.join(model_path, "label_mappings.json")
        if os.path.exists(mappings_path):
            with open(mappings_path, "r") as f:
                self._paper_type_mappings = json.load(f)
        else:
            self._paper_type_mappings = {
                "classes": PAPER_TYPES_LIST,
                "num_classes": 5,
            }

        # Try TF-IDF model first (primary, faster)
        tfidf_dir = os.path.join(model_path, "tfidf_primary")
        if os.path.isdir(tfidf_dir):
            tfidf_path = os.path.join(tfidf_dir, "tfidf_vectorizer.pkl")
            logreg_path = os.path.join(tfidf_dir, "logreg_model.pkl")

            if os.path.exists(tfidf_path) and os.path.exists(logreg_path):
                with open(tfidf_path, "rb") as f:
                    self._paper_type_tfidf = pickle.load(f)
                with open(logreg_path, "rb") as f:
                    self._paper_type_logreg = pickle.load(f)
                self._paper_type_use_bert = False
                logger.info("Paper type classifier loaded (TF-IDF + LogisticRegression)")
                return

        # Fallback to DistilBERT
        bert_dir = os.path.join(model_path, "distilbert_comparison")
        if os.path.isdir(bert_dir):
            num_classes = self._paper_type_mappings.get("num_classes", 5)
            self._paper_type_bert_tokenizer = DistilBertTokenizer.from_pretrained(
                os.path.join(bert_dir, "tokenizer")
            )
            self._paper_type_bert_model = PaperTypeClassifier(num_classes=num_classes)
            state_dict = torch.load(
                os.path.join(bert_dir, "best_model.pt"),
                map_location=self.device,
                weights_only=True,
            )
            self._paper_type_bert_model.load_state_dict(state_dict)
            self._paper_type_bert_model.to(self.device)
            self._paper_type_bert_model.eval()
            self._paper_type_use_bert = True
            logger.info("Paper type classifier loaded (DistilBERT fallback)")
            return

        raise FileNotFoundError(
            f"No paper type model found in {model_path}. "
            "Expected tfidf_primary/ or distilbert_comparison/ subdirectory."
        )

    def predict_paper_type(
        self, title: str, abstract: str
    ) -> Tuple[str, float]:
        """
        Predict paper type.

        Args:
            title: Paper title
            abstract: Paper abstract

        Returns:
            (predicted_type, confidence)
        """
        self._load_paper_type_model()

        text = f"{title} {abstract}"

        if not self._paper_type_use_bert:
            # TF-IDF + LogReg
            X = self._paper_type_tfidf.transform([text])
            probs = self._paper_type_logreg.predict_proba(X)[0]
            pred_idx = int(np.argmax(probs))
            pred_label = self._paper_type_logreg.classes_[pred_idx]
            confidence = float(probs[pred_idx])
            return pred_label, confidence
        else:
            # DistilBERT
            encoding = self._paper_type_bert_tokenizer(
                f"{title} [SEP] {abstract}",
                max_length=MAX_SEQ_LEN,
                padding="max_length",
                truncation=True,
                return_tensors="pt",
            )
            input_ids = encoding["input_ids"].to(self.device)
            attention_mask = encoding["attention_mask"].to(self.device)

            with torch.no_grad():
                logits = self._paper_type_bert_model(input_ids, attention_mask)
                probs = torch.softmax(logits, dim=-1).squeeze(0).cpu().numpy()

            classes = self._paper_type_mappings.get("classes", PAPER_TYPES_LIST)
            pred_idx = int(np.argmax(probs))
            pred_label = classes[pred_idx]
            confidence = float(probs[pred_idx])
            return pred_label, confidence

    def predict_paper_type_batch(
        self, papers: List[Tuple[str, str]], batch_size: int = 64
    ) -> List[Tuple[str, float]]:
        """
        Batch prediction for paper type classification.

        Args:
            papers: List of (title, abstract) tuples
            batch_size: Batch size

        Returns:
            List of (predicted_type, confidence)
        """
        self._load_paper_type_model()

        results = []

        if not self._paper_type_use_bert:
            # TF-IDF is fast enough to process all at once
            texts = [f"{title} {abstract}" for title, abstract in papers]
            X = self._paper_type_tfidf.transform(texts)
            probs_all = self._paper_type_logreg.predict_proba(X)
            for probs in probs_all:
                pred_idx = int(np.argmax(probs))
                pred_label = self._paper_type_logreg.classes_[pred_idx]
                confidence = float(probs[pred_idx])
                results.append((pred_label, confidence))
        else:
            classes = self._paper_type_mappings.get("classes", PAPER_TYPES_LIST)
            for i in range(0, len(papers), batch_size):
                batch = papers[i : i + batch_size]
                texts = [f"{title} [SEP] {abstract}" for title, abstract in batch]

                encodings = self._paper_type_bert_tokenizer(
                    texts,
                    max_length=MAX_SEQ_LEN,
                    padding="max_length",
                    truncation=True,
                    return_tensors="pt",
                )
                input_ids = encodings["input_ids"].to(self.device)
                attention_mask = encodings["attention_mask"].to(self.device)

                with torch.no_grad():
                    logits = self._paper_type_bert_model(input_ids, attention_mask)
                    probs = torch.softmax(logits, dim=-1).cpu().numpy()

                for j in range(len(batch)):
                    pred_idx = int(np.argmax(probs[j]))
                    pred_label = classes[pred_idx]
                    confidence = float(probs[j][pred_idx])
                    results.append((pred_label, confidence))

        return results

    # ── Combined Prediction ──────────────────────────────────────────────────

    def predict_all(
        self,
        title: str,
        abstract: str,
        author_count: int = 1,
        ref_count: int = 20,
        has_funding: bool = False,
        institution_count: int = 1,
        is_multicenter: bool = False,
    ) -> Dict:
        """
        Run all 3 models on a single paper.

        Returns:
            {
                "subfield": {"label": str, "confidence": float, "probabilities": dict},
                "tier": {"label": str, "confidence": float, "probabilities": dict},
                "paper_type": {"label": str, "confidence": float},
            }
        """
        # Predict paper type first (needed for tier prediction)
        paper_type, pt_confidence = self.predict_paper_type(title, abstract)

        # Sub-field
        sf_label, sf_conf, sf_probs = self.predict_subfield(title, abstract)

        # Tier (uses paper_type from model 3)
        tier_label, tier_conf, tier_probs = self.predict_tier(
            title,
            abstract,
            author_count=author_count,
            ref_count=ref_count,
            paper_type=paper_type,
            has_funding=has_funding,
            institution_count=institution_count,
            is_multicenter=is_multicenter,
        )

        return {
            "subfield": {
                "label": sf_label,
                "confidence": sf_conf,
                "probabilities": sf_probs,
            },
            "tier": {
                "label": tier_label,
                "confidence": tier_conf,
                "probabilities": tier_probs,
            },
            "paper_type": {
                "label": paper_type,
                "confidence": pt_confidence,
            },
        }

    # ── Cleanup ──────────────────────────────────────────────────────────────

    def cleanup(self):
        """Clean up temporary S3 download directory if created."""
        if self._s3_local_cache and os.path.isdir(self._s3_local_cache):
            import shutil
            shutil.rmtree(self._s3_local_cache, ignore_errors=True)
            logger.info(f"Cleaned up temp dir: {self._s3_local_cache}")
            self._s3_local_cache = None

    def __del__(self):
        """Cleanup on garbage collection."""
        try:
            self.cleanup()
        except Exception:
            pass
