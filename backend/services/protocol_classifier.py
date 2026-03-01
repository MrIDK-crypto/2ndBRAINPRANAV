"""
Protocol Content Classifier (Runtime)
=======================================
Loads trained scikit-learn model and provides:
  - is_protocol_content(text) → (bool, confidence)
  - classify_batch(texts) → List[(bool, confidence)]

Falls back to heuristic detection if model isn't trained yet.
"""

import os
import logging
from typing import Tuple, List, Optional

logger = logging.getLogger(__name__)

MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'protocol_models')
CONTENT_CLASSIFIER_PATH = os.path.join(MODELS_DIR, 'content_classifier.joblib')

_model = None
_model_loaded = False


def _load_model():
    """Lazy-load the trained classifier model."""
    global _model, _model_loaded

    if _model_loaded:
        return _model

    _model_loaded = True

    if not os.path.exists(CONTENT_CLASSIFIER_PATH):
        logger.info('[ProtocolClassifier] No trained model found, using heuristic fallback')
        return None

    try:
        import joblib
        _model = joblib.load(CONTENT_CLASSIFIER_PATH)
        logger.info('[ProtocolClassifier] Loaded trained content classifier')
        return _model
    except Exception as e:
        logger.warning(f'[ProtocolClassifier] Failed to load model: {e}')
        return None


def is_protocol_content(text: str) -> Tuple[bool, float]:
    """
    Determine if text is scientific protocol content.

    Returns:
        (is_protocol, confidence) where confidence is 0.0 to 1.0
    """
    if not text or len(text) < 50:
        return False, 0.0

    model = _load_model()

    if model is not None:
        try:
            proba = model.predict_proba([text[:5000]])[0]
            # Class 1 = protocol
            confidence = float(proba[1])
            return confidence >= 0.5, confidence
        except Exception as e:
            logger.warning(f'[ProtocolClassifier] Model prediction failed: {e}')

    # Fallback to heuristic
    from services.protocol_patterns import is_protocol_content as heuristic_check
    return heuristic_check(text)


def classify_batch(texts: List[str]) -> List[Tuple[bool, float]]:
    """Classify a batch of texts."""
    model = _load_model()

    if model is not None:
        try:
            truncated = [t[:5000] for t in texts]
            probas = model.predict_proba(truncated)
            return [(float(p[1]) >= 0.5, float(p[1])) for p in probas]
        except Exception as e:
            logger.warning(f'[ProtocolClassifier] Batch prediction failed: {e}')

    # Fallback to heuristic
    from services.protocol_patterns import is_protocol_content as heuristic_check
    return [heuristic_check(t) for t in texts]


def reload_model():
    """Force reload the model (after retraining)."""
    global _model, _model_loaded
    _model = None
    _model_loaded = False
    _load_model()
