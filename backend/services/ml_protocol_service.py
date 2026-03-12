"""
ML Protocol Service
====================
Service wrapper that loads trained scikit-learn models and provides inference:

  1. Content Classifier: determines if text is protocol vs business content
     - Model: backend/data/protocol_models/content_classifier.joblib
     - Input: raw text -> Output: (is_protocol: bool, confidence: float)

  2. Completeness Scorer: scores how complete a protocol document is (0-1)
     - Model: backend/data/protocol_models/completeness_scorer.joblib
     - Input: raw text -> Output: float (0.0 = very incomplete, 1.0 = fully complete)

Degrades gracefully: if model files don't exist or scikit-learn isn't installed,
falls back to heuristic methods from protocol_patterns.py.

Usage:
    from services.ml_protocol_service import get_ml_protocol_service

    service = get_ml_protocol_service()

    # Classify content
    is_protocol, confidence = service.classify_content(text)

    # Score completeness
    score = service.score_completeness(text)

    # Batch operations
    results = service.classify_batch(texts)
    scores = service.score_completeness_batch(texts)

    # Full analysis
    analysis = service.analyze_protocol(text)
"""

import os
import logging
from typing import Tuple, List, Dict, Any, Optional

logger = logging.getLogger(__name__)

MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'protocol_models')
CONTENT_CLASSIFIER_PATH = os.path.join(MODELS_DIR, 'content_classifier.joblib')
COMPLETENESS_SCORER_PATH = os.path.join(MODELS_DIR, 'completeness_scorer.joblib')

# Max text length to send to models (TF-IDF was trained on 5000 char truncated text)
MAX_TEXT_LENGTH = 5000


class MLProtocolService:
    """
    Unified service for ML-based protocol analysis.

    Wraps the two trained joblib models and provides graceful fallback
    to heuristic methods if models are unavailable.
    """

    def __init__(self):
        self._content_classifier = None
        self._completeness_scorer = None
        self._content_classifier_loaded = False
        self._completeness_scorer_loaded = False
        self._joblib_available = None

    def _check_joblib(self) -> bool:
        """Check if joblib is importable."""
        if self._joblib_available is None:
            try:
                import joblib  # noqa: F401
                self._joblib_available = True
            except ImportError:
                logger.warning('[MLProtocol] joblib not installed, ML models unavailable')
                self._joblib_available = False
        return self._joblib_available

    def _load_content_classifier(self):
        """Lazy-load the content classifier model."""
        if self._content_classifier_loaded:
            return self._content_classifier

        self._content_classifier_loaded = True

        if not self._check_joblib():
            return None

        if not os.path.exists(CONTENT_CLASSIFIER_PATH):
            logger.info('[MLProtocol] Content classifier model not found at %s, using heuristic fallback',
                        CONTENT_CLASSIFIER_PATH)
            return None

        try:
            import joblib
            self._content_classifier = joblib.load(CONTENT_CLASSIFIER_PATH)
            logger.info('[MLProtocol] Loaded content classifier from %s', CONTENT_CLASSIFIER_PATH)
            return self._content_classifier
        except Exception as e:
            logger.warning('[MLProtocol] Failed to load content classifier: %s', e)
            return None

    def _load_completeness_scorer(self):
        """Lazy-load the completeness scorer model."""
        if self._completeness_scorer_loaded:
            return self._completeness_scorer

        self._completeness_scorer_loaded = True

        if not self._check_joblib():
            return None

        if not os.path.exists(COMPLETENESS_SCORER_PATH):
            logger.info('[MLProtocol] Completeness scorer model not found at %s, using heuristic fallback',
                        COMPLETENESS_SCORER_PATH)
            return None

        try:
            import joblib
            self._completeness_scorer = joblib.load(COMPLETENESS_SCORER_PATH)
            logger.info('[MLProtocol] Loaded completeness scorer from %s', COMPLETENESS_SCORER_PATH)
            return self._completeness_scorer
        except Exception as e:
            logger.warning('[MLProtocol] Failed to load completeness scorer: %s', e)
            return None

    # ========================================================================
    # CONTENT CLASSIFICATION
    # ========================================================================

    def classify_content(self, text: str) -> Tuple[bool, float]:
        """
        Classify text as protocol vs business/general content.

        Uses the trained ML model if available, otherwise falls back to
        the heuristic pattern-based detection in protocol_patterns.py.

        Args:
            text: Raw document text

        Returns:
            (is_protocol, confidence) where confidence is 0.0 to 1.0
        """
        if not text or len(text) < 50:
            return False, 0.0

        model = self._load_content_classifier()

        if model is not None:
            try:
                truncated = text[:MAX_TEXT_LENGTH]
                proba = model.predict_proba([truncated])[0]
                # Class 1 = protocol content
                confidence = float(proba[1])
                is_protocol = confidence >= 0.5
                return is_protocol, confidence
            except Exception as e:
                logger.warning('[MLProtocol] Content classifier prediction failed: %s', e)

        # Fallback to heuristic
        return self._heuristic_classify(text)

    def classify_batch(self, texts: List[str]) -> List[Tuple[bool, float]]:
        """
        Classify a batch of texts.

        Args:
            texts: List of raw document texts

        Returns:
            List of (is_protocol, confidence) tuples
        """
        if not texts:
            return []

        model = self._load_content_classifier()

        if model is not None:
            try:
                truncated = [t[:MAX_TEXT_LENGTH] for t in texts]
                probas = model.predict_proba(truncated)
                return [(float(p[1]) >= 0.5, float(p[1])) for p in probas]
            except Exception as e:
                logger.warning('[MLProtocol] Batch classification failed: %s', e)

        # Fallback to heuristic for each text
        return [self._heuristic_classify(t) for t in texts]

    @staticmethod
    def _heuristic_classify(text: str) -> Tuple[bool, float]:
        """Fallback heuristic classification using regex patterns."""
        try:
            from services.protocol_patterns import is_protocol_content as heuristic_check
            return heuristic_check(text)
        except ImportError:
            return False, 0.0

    # ========================================================================
    # COMPLETENESS SCORING
    # ========================================================================

    def score_completeness(self, text: str) -> float:
        """
        Score how complete a protocol document is.

        Uses the trained ML regressor if available, otherwise falls back
        to a heuristic scoring based on structural indicators.

        Args:
            text: Raw protocol document text

        Returns:
            Completeness score from 0.0 (very incomplete) to 1.0 (fully complete)
        """
        if not text or len(text) < 50:
            return 0.0

        model = self._load_completeness_scorer()

        if model is not None:
            try:
                truncated = text[:MAX_TEXT_LENGTH]
                score = model.predict([truncated])[0]
                # Clamp to [0, 1]
                return max(0.0, min(1.0, float(score)))
            except Exception as e:
                logger.warning('[MLProtocol] Completeness scorer prediction failed: %s', e)

        # Fallback to heuristic
        return self._heuristic_completeness(text)

    def score_completeness_batch(self, texts: List[str]) -> List[float]:
        """
        Score completeness for a batch of texts.

        Args:
            texts: List of raw protocol document texts

        Returns:
            List of completeness scores (0.0 to 1.0)
        """
        if not texts:
            return []

        model = self._load_completeness_scorer()

        if model is not None:
            try:
                truncated = [t[:MAX_TEXT_LENGTH] for t in texts]
                scores = model.predict(truncated)
                return [max(0.0, min(1.0, float(s))) for s in scores]
            except Exception as e:
                logger.warning('[MLProtocol] Batch completeness scoring failed: %s', e)

        # Fallback to heuristic for each text
        return [self._heuristic_completeness(t) for t in texts]

    @staticmethod
    def _heuristic_completeness(text: str) -> float:
        """
        Fallback heuristic completeness scoring.

        Checks for structural indicators of a complete protocol:
        - Numbered/ordered steps
        - Reagent concentrations
        - Time/duration values
        - Temperature values
        - Equipment settings (rpm, voltage)
        - Safety notes
        - Expected results
        """
        import re

        if not text or len(text) < 50:
            return 0.0

        sample = text[:10000]
        checks = 0
        total = 7

        # Has numbered steps?
        if re.search(r'(?:^|\n)\s*(?:\d+[.)]\s|step\s+\d)', sample, re.IGNORECASE):
            checks += 1

        # Has reagent concentrations?
        if re.search(r'\d+\.?\d*\s*(?:mM|uM|mg/ml|ug/ml|ng/ml|%\s*(?:v/v|w/v))', sample):
            checks += 1

        # Has time/duration?
        if re.search(r'\d+\.?\d*\s*(?:min(?:utes?)?|sec(?:onds?)?|hrs?|hours?)', sample):
            checks += 1

        # Has temperature?
        if re.search(r'-?\d+\.?\d*\s*°?\s*[CF]\b', sample):
            checks += 1

        # Has equipment settings?
        if re.search(r'\d+[,.]?\d*\s*(?:rpm|RPM|rcf|xg|V\b|mA\b)', sample):
            checks += 1

        # Has safety info?
        if re.search(r'\b(?:caution|warning|hazard|PPE|fume\s+hood|gloves)\b', sample, re.IGNORECASE):
            checks += 1

        # Has expected results?
        if re.search(r'\b(?:should\s+(?:yield|produce|result|appear)|expected?\s+(?:result|output|yield))\b',
                     sample, re.IGNORECASE):
            checks += 1

        return round(checks / total, 3)

    # ========================================================================
    # COMBINED ANALYSIS
    # ========================================================================

    def analyze_protocol(self, text: str) -> Dict[str, Any]:
        """
        Full protocol analysis: classification + completeness scoring.

        Args:
            text: Raw document text

        Returns:
            Dict with is_protocol, protocol_confidence, completeness_score,
            and model metadata
        """
        is_protocol, protocol_confidence = self.classify_content(text)

        completeness_score = None
        # Only score completeness if content is actually a protocol
        if is_protocol:
            completeness_score = round(self.score_completeness(text), 4)

        result = {
            'is_protocol': is_protocol,
            'protocol_confidence': round(protocol_confidence, 4),
            'completeness_score': completeness_score,
            'models_used': {
                'content_classifier': self._content_classifier is not None,
                'completeness_scorer': self._completeness_scorer is not None,
            }
        }

        return result

    def analyze_document_protocol_metadata(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Analyze text and return protocol metadata suitable for storing
        in Document.doc_metadata.

        Returns None if text is not protocol content.
        Returns a dict with protocol details if it is.
        """
        is_protocol, confidence = self.classify_content(text)

        if not is_protocol:
            return None

        completeness = self.score_completeness(text)

        return {
            'is_protocol': True,
            'protocol_confidence': round(confidence, 4),
            'protocol_completeness_score': round(completeness, 4),
            'ml_content_classifier_used': self._content_classifier is not None,
            'ml_completeness_scorer_used': self._completeness_scorer is not None,
        }

    # ========================================================================
    # MODEL MANAGEMENT
    # ========================================================================

    def reload_models(self):
        """Force reload both models (e.g., after retraining)."""
        self._content_classifier = None
        self._content_classifier_loaded = False
        self._completeness_scorer = None
        self._completeness_scorer_loaded = False
        logger.info('[MLProtocol] Models cleared, will reload on next use')

    def get_model_status(self) -> Dict[str, Any]:
        """Get status of loaded models."""
        # Eagerly check joblib so status endpoint always returns a boolean
        self._check_joblib()
        return {
            'content_classifier': {
                'path': CONTENT_CLASSIFIER_PATH,
                'file_exists': os.path.exists(CONTENT_CLASSIFIER_PATH),
                'loaded': self._content_classifier is not None,
                'attempted': self._content_classifier_loaded,
            },
            'completeness_scorer': {
                'path': COMPLETENESS_SCORER_PATH,
                'file_exists': os.path.exists(COMPLETENESS_SCORER_PATH),
                'loaded': self._completeness_scorer is not None,
                'attempted': self._completeness_scorer_loaded,
            },
            'joblib_available': self._joblib_available,
        }


# ============================================================================
# SINGLETON
# ============================================================================

_service: Optional[MLProtocolService] = None


def get_ml_protocol_service() -> MLProtocolService:
    """Get or create the singleton MLProtocolService."""
    global _service
    if _service is None:
        _service = MLProtocolService()
    return _service


def reload_ml_protocol_service():
    """Force reload the ML protocol models."""
    global _service
    if _service:
        _service.reload_models()
    else:
        _service = MLProtocolService()
