"""
Protocol ML Classifiers (Runtime)
===================================
Loads trained scikit-learn models and provides:
  - is_protocol_content(text) → (bool, confidence)
  - classify_batch(texts) → List[(bool, confidence)]
  - detect_missing_step(step_before, step_after) → (bool, confidence)
  - score_completeness(text) → float  (0.0 to 1.0)

Falls back to heuristic detection if models aren't trained yet.
"""

import os
import logging
from typing import Tuple, List, Optional, Dict, Any

logger = logging.getLogger(__name__)

MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'protocol_models')
CONTENT_CLASSIFIER_PATH = os.path.join(MODELS_DIR, 'content_classifier.joblib')
MISSING_STEP_PATH = os.path.join(MODELS_DIR, 'missing_step_detector.joblib')
COMPLETENESS_PATH = os.path.join(MODELS_DIR, 'completeness_scorer.joblib')

_model = None
_model_loaded = False

_missing_step_model = None
_missing_step_loaded = False

_completeness_model = None
_completeness_loaded = False


def _load_model():
    """Lazy-load the trained content classifier model."""
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


def _load_missing_step_model():
    """Lazy-load the trained missing step detector model."""
    global _missing_step_model, _missing_step_loaded

    if _missing_step_loaded:
        return _missing_step_model

    _missing_step_loaded = True

    if not os.path.exists(MISSING_STEP_PATH):
        logger.info('[ProtocolClassifier] No missing step detector model found')
        return None

    try:
        import joblib
        _missing_step_model = joblib.load(MISSING_STEP_PATH)
        logger.info('[ProtocolClassifier] Loaded missing step detector')
        return _missing_step_model
    except Exception as e:
        logger.warning(f'[ProtocolClassifier] Failed to load missing step model: {e}')
        return None


def _load_completeness_model():
    """Lazy-load the trained completeness scorer model."""
    global _completeness_model, _completeness_loaded

    if _completeness_loaded:
        return _completeness_model

    _completeness_loaded = True

    if not os.path.exists(COMPLETENESS_PATH):
        logger.info('[ProtocolClassifier] No completeness scorer model found')
        return None

    try:
        import joblib
        _completeness_model = joblib.load(COMPLETENESS_PATH)
        logger.info('[ProtocolClassifier] Loaded completeness scorer')
        return _completeness_model
    except Exception as e:
        logger.warning(f'[ProtocolClassifier] Failed to load completeness model: {e}')
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


def detect_missing_step(step_before: str, step_after: str) -> Tuple[bool, float]:
    """
    Predict if a step is missing between two consecutive protocol steps.

    Args:
        step_before: Text of the earlier step
        step_after: Text of the later step

    Returns:
        (is_missing, confidence) where confidence is 0.0 to 1.0
    """
    if not step_before or not step_after:
        return False, 0.0

    model = _load_missing_step_model()

    if model is not None:
        try:
            pair_text = f"{step_before[:500]} [SEP] {step_after[:500]}"
            proba = model.predict_proba([pair_text])[0]
            # Class 1 = missing step
            confidence = float(proba[1])
            return confidence >= 0.5, confidence
        except Exception as e:
            logger.warning(f'[ProtocolClassifier] Missing step prediction failed: {e}')

    return False, 0.0


def detect_missing_steps_in_sequence(steps: List[str]) -> List[Dict[str, Any]]:
    """
    Scan a sequence of protocol steps for potential gaps.

    Args:
        steps: Ordered list of step texts

    Returns:
        List of dicts with keys: index, step_before, step_after, confidence, is_missing
    """
    if len(steps) < 2:
        return []

    model = _load_missing_step_model()
    if model is None:
        return []

    results = []
    try:
        pairs = []
        for i in range(len(steps) - 1):
            pair_text = f"{steps[i][:500]} [SEP] {steps[i + 1][:500]}"
            pairs.append(pair_text)

        probas = model.predict_proba(pairs)
        for i, proba in enumerate(probas):
            confidence = float(proba[1])
            if confidence >= 0.4:  # Lower threshold for surfacing potential gaps
                results.append({
                    'index': i,
                    'step_before': steps[i],
                    'step_after': steps[i + 1],
                    'confidence': round(confidence, 3),
                    'is_missing': confidence >= 0.5,
                })
    except Exception as e:
        logger.warning(f'[ProtocolClassifier] Batch missing step detection failed: {e}')

    return results


def score_completeness(text: str) -> float:
    """
    Score the completeness of a protocol text.

    Args:
        text: Full protocol text

    Returns:
        Completeness score from 0.0 (very incomplete) to 1.0 (fully complete)
    """
    if not text or len(text) < 50:
        return 0.0

    model = _load_completeness_model()

    if model is not None:
        try:
            score = float(model.predict([text[:5000]])[0])
            return max(0.0, min(1.0, round(score, 3)))
        except Exception as e:
            logger.warning(f'[ProtocolClassifier] Completeness scoring failed: {e}')

    # Heuristic fallback: basic checks
    import re
    score = 0.0
    checks = 0
    total = 6

    # Has numbered steps?
    checks += 1 if re.search(r'^\s*\d+[\.\)]\s', text, re.MULTILINE) else 0
    # Has measurements/quantities?
    checks += 1 if re.search(r'\d+\s*(?:mM|µM|uM|mg|ml|µl|min|sec|°C|rpm|mol|mg/ml)', text, re.I) else 0
    # Has action verbs?
    checks += 1 if re.search(r'\b(?:add|pipette|incubate|centrifuge|wash|mix|transfer|dissolve|filter)\b', text, re.I) else 0
    # Has timing?
    checks += 1 if re.search(r'\b(?:\d+\s*(?:min|minutes?|hours?|seconds?|overnight))\b', text, re.I) else 0
    # Has equipment/tools?
    checks += 1 if re.search(r'\b(?:tube|plate|flask|pipette|centrifuge|incubator|microscope|vortex)\b', text, re.I) else 0
    # Has safety/caution?
    checks += 1 if re.search(r'\b(?:caution|warning|safety|fume hood|gloves|hazard|avoid)\b', text, re.I) else 0

    return round(checks / total, 3)


def reload_model():
    """Force reload all models (after retraining)."""
    global _model, _model_loaded
    global _missing_step_model, _missing_step_loaded
    global _completeness_model, _completeness_loaded
    _model = None
    _model_loaded = False
    _missing_step_model = None
    _missing_step_loaded = False
    _completeness_model = None
    _completeness_loaded = False
    _load_model()
    _load_missing_step_model()
    _load_completeness_model()
