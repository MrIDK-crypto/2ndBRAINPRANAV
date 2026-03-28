"""Layer 1: Intent Gate — fast triage for power service routing."""

import os
import re
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

POWER_PATTERNS: Dict[str, List[str]] = {
    "hij": [
        r"\bscore\b.*\b(paper|manuscript|article)\b",
        r"\bmanuscript\b",
        r"\bjournal\s+match",
        r"\bimpact\s+factor\b",
        r"\bred\s+flags?\b.*\b(paper|manuscript)\b",
        r"\breview\s+my\s+paper\b",
        r"\bpublish\b",
        r"\bwhere\s+should\s+I\s+submit\b",
        r"\bscore\s+(my|this|the)\b",
        r"\bjournal\s+recommend",
        r"\bmanuscript\s+(scor|analys|evaluat)",
    ],
    "competitor_finder": [
        r"\bcompetitor",
        r"\bcompeting\s+lab",
        r"\bwho\s+else\s+(is|are)\s+working",
        r"\bgrants?\s+in\s+my\s+area\b",
        r"\bpreprints?\b.*\b(similar|competing|related)\b",
        r"\bsimilar\s+research\b",
        r"\bcompetition\b.*\bresearch\b",
        r"\bwho\s+(is|are)\s+researching\b",
        r"\bcompeting\s+(groups?|teams?|labs?)\b",
    ],
    "idea_reality": [
        r"\bvalidate\s+(my\s+)?(idea|concept|research)\b",
        r"\bis\s+this\s+(idea\s+)?novel\b",
        r"\bdoes\s+this\s+exist\b",
        r"\breality\s+check\b",
        r"\bfeasib(le|ility)\b.*\b(idea|concept|research)\b",
        r"\bhas\s+anyone\s+done\b",
        r"\bnovel(ty)?\b.*\b(check|assess|evaluat)\b",
        r"\balready\s+(been\s+)?done\b",
        r"\boriginal(ity)?\b.*\b(check|research)\b",
        r"\b(idea|concept)\s+(novel|unique|original)\b",
        r"\bnovel\b.*\b(idea|concept)\b",
    ],
    "co_researcher": [
        r"\bhypothes[ie]s\b",
        r"\bbrainstorm\s+research\b",
        r"\bagent\s+debate\b",
        r"\bco[\-\s]?research",
        r"\bresearch\s+direction",
        r"\bresearch\s+idea",
        r"\bgenerate\s+(research\s+)?hypothes",
        r"\bexplore\s+research\b",
    ],
}

_COMPILED_PATTERNS: Dict[str, List[re.Pattern]] = {
    power: [re.compile(p, re.IGNORECASE) for p in patterns]
    for power, patterns in POWER_PATTERNS.items()
}


class IntentGate:
    def __init__(self):
        self._embedding_client = None
        self._power_embeddings = None
        self.similarity_threshold = float(
            os.getenv("POWER_INTENT_THRESHOLD", "0.75")
        )

    def classify(
        self,
        message: str,
        power_hint: Optional[str] = None,
    ) -> Dict[str, Any]:
        if power_hint:
            valid_powers = {"hij", "competitor_finder", "idea_reality", "co_researcher"}
            if power_hint in valid_powers:
                return {
                    "needs_powers": True,
                    "powers": [power_hint],
                    "skip_router": True,
                }

        detected = self._keyword_scan(message)
        if detected:
            return {
                "needs_powers": True,
                "powers": detected,
                "skip_router": len(detected) == 1,
            }

        detected = self._embedding_scan(message)
        if detected:
            return {
                "needs_powers": True,
                "powers": detected,
                "skip_router": False,
            }

        return {
            "needs_powers": False,
            "powers": [],
            "skip_router": False,
        }

    def _keyword_scan(self, message: str) -> List[str]:
        detected = []
        for power, patterns in _COMPILED_PATTERNS.items():
            for pattern in patterns:
                if pattern.search(message):
                    detected.append(power)
                    break
        return detected

    def _embedding_scan(self, message: str) -> List[str]:
        try:
            self._ensure_embeddings_loaded()
            if not self._embedding_client or not self._power_embeddings:
                return []

            from azure_openai_config import get_embedding
            msg_embedding = get_embedding(message)

            detected = []
            for power, power_emb in self._power_embeddings.items():
                similarity = self._cosine_similarity(msg_embedding, power_emb)
                if similarity >= self.similarity_threshold:
                    detected.append(power)
            return detected
        except Exception as e:
            logger.warning(f"Embedding scan failed, falling back to no powers: {e}")
            return []

    def _ensure_embeddings_loaded(self):
        if self._power_embeddings is not None:
            return
        try:
            from azure_openai_config import get_embedding
            power_descriptions = {
                "hij": "Score and evaluate a research manuscript or paper for journal publication. Analyze methodology, impact, citations, and match to journals.",
                "competitor_finder": "Find competing research labs, recent preprints, and active grants in a research area or field.",
                "idea_reality": "Validate a research idea for novelty. Check if similar implementations or projects already exist.",
                "co_researcher": "Generate research hypotheses and brainstorm new research directions. Explore potential experiments.",
            }
            self._power_embeddings = {}
            for power, desc in power_descriptions.items():
                self._power_embeddings[power] = get_embedding(desc)
            self._embedding_client = True
        except Exception as e:
            logger.warning(f"Failed to load power embeddings: {e}")
            self._embedding_client = False
            self._power_embeddings = {}

    @staticmethod
    def _cosine_similarity(vec_a: list, vec_b: list) -> float:
        dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = sum(a * a for a in vec_a) ** 0.5
        norm_b = sum(b * b for b in vec_b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot_product / (norm_a * norm_b)
