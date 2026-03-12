"""
ML-Based Journal Tier Predictor
================================
Provides ML-based tier prediction using the trained TF-IDF + LogReg model
(lightweight, no GPU needed) with fallback to the LLM-based scoring.

This module is used by the journal_scorer_service to optionally supplement
or pre-screen tier predictions before running the full LLM pipeline.

Usage:
    from services.ml_tier_predictor import get_ml_tier_predictor

    predictor = get_ml_tier_predictor()
    if predictor.is_available:
        result = predictor.predict_tier(title, abstract, metadata)
        # result = {'tier': 'Tier1', 'confidence': 0.87, 'probabilities': {...}}
"""

import json
import logging
import os
import pickle
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Tier classes expected by the training scripts
TIER_CLASSES = ["Tier1", "Tier2", "Tier3"]
PAPER_TYPES = ["experimental", "review", "meta_analysis", "case_report", "protocol"]
METADATA_DIM = 10


class MLTierPredictor:
    """Lightweight ML-based journal tier predictor.

    Uses TF-IDF + LogisticRegression on title+abstract text combined with
    structured metadata features. This avoids the need for DistilBERT/GPU
    while maintaining reasonable accuracy for pre-screening.

    Falls back gracefully if no trained model exists.
    """

    def __init__(self):
        self._tfidf = None
        self._model = None
        self._label_mappings = None
        self._is_available = False
        self._checked = False

    @property
    def is_available(self) -> bool:
        """Whether a trained model is loaded and ready."""
        if not self._checked:
            self._try_load()
        return self._is_available

    def _try_load(self):
        """Attempt to load the trained tier prediction model."""
        self._checked = True

        backend_dir = Path(__file__).resolve().parent.parent
        possible_paths = [
            backend_dir / "models" / "tier_predictor" / "tfidf",
            backend_dir / "oncology_model" / "models" / "tier_predictor" / "tfidf",
        ]

        for model_dir in possible_paths:
            tfidf_path = model_dir / "tfidf_vectorizer.pkl"
            model_path = model_dir / "logreg_model.pkl"
            mappings_path = model_dir / "label_mappings.json"

            if tfidf_path.exists() and model_path.exists():
                try:
                    with open(tfidf_path, "rb") as f:
                        self._tfidf = pickle.load(f)
                    with open(model_path, "rb") as f:
                        self._model = pickle.load(f)
                    if mappings_path.exists():
                        with open(mappings_path, "r") as f:
                            self._label_mappings = json.load(f)

                    self._is_available = True
                    logger.info(f"[MLTierPredictor] Model loaded from {model_dir}")
                    return
                except Exception as e:
                    logger.warning(f"[MLTierPredictor] Failed to load from {model_dir}: {e}")
                    self._tfidf = None
                    self._model = None

        logger.info("[MLTierPredictor] No trained model found")

    def predict_tier(
        self,
        title: str,
        abstract: str,
        paper_type: str = "experimental",
        author_count: int = 1,
        ref_count: int = 20,
        has_funding: bool = False,
        institution_count: int = 1,
        is_multicenter: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Predict journal tier from paper text and metadata.

        Args:
            title: Paper title
            abstract: Paper abstract (or full text excerpt)
            paper_type: Detected paper type
            author_count: Number of authors
            ref_count: Number of references
            has_funding: Whether funding is mentioned
            institution_count: Number of institutions
            is_multicenter: Whether it is a multicenter study

        Returns:
            Dict with tier, confidence, probabilities, or None if model unavailable
        """
        if not self.is_available:
            return None

        try:
            # Build text input (title + first 2K of abstract for TF-IDF)
            text = f"{title} {abstract[:2000]}" if title else abstract[:2000]

            # Encode metadata as text features appended to input
            # This is a simple approach: append structured info as text
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

            full_text = text + meta_text

            X = self._tfidf.transform([full_text])
            probs = self._model.predict_proba(X)[0]
            pred_idx = int(probs.argmax())
            pred_label = self._model.classes_[pred_idx]
            confidence = float(probs[pred_idx])

            probabilities = {
                cls: round(float(p), 4)
                for cls, p in zip(self._model.classes_, probs)
            }

            return {
                "tier": pred_label,
                "confidence": confidence,
                "probabilities": probabilities,
                "method": "ml_tfidf",
            }

        except Exception as e:
            logger.warning(f"[MLTierPredictor] Prediction failed: {e}")
            return None

    def predict_tier_from_score(self, overall_score: int) -> Dict[str, Any]:
        """Simple rule-based tier prediction from overall quality score.

        This mirrors the existing _get_tier() logic from journal_scorer_service.
        Used as a baseline comparison for the ML model.
        """
        if overall_score >= 85:
            return {"tier": "Tier1", "confidence": 0.9, "method": "score_rule"}
        elif overall_score >= 65:
            return {"tier": "Tier2", "confidence": 0.8, "method": "score_rule"}
        else:
            return {"tier": "Tier3", "confidence": 0.7, "method": "score_rule"}


# Singleton
_instance = None


def get_ml_tier_predictor() -> MLTierPredictor:
    """Get or create the singleton ML tier predictor."""
    global _instance
    if _instance is None:
        _instance = MLTierPredictor()
    return _instance


def reload_ml_tier_predictor():
    """Force reload tier predictor from disk (for hot-swap after S3 sync)."""
    global _instance
    _instance = None
    new = get_ml_tier_predictor()
    return new.is_available
