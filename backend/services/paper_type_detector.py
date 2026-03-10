"""
Paper Type Detector
====================
Classifies uploaded papers into types: review, experimental, meta_analysis,
case_report, protocol.

Uses LLM (Azure OpenAI) on the first ~5K characters for classification,
with a heuristic fallback when LLM is unavailable.

Returns: { paper_type, confidence, signals }
"""

import re
import json
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

PAPER_TYPES = {
    'experimental': 'Original research with methods, results, and discussion',
    'review': 'Systematic or narrative review of existing literature',
    'meta_analysis': 'Statistical synthesis of multiple study results',
    'case_report': 'Detailed report of a specific patient case or small series',
    'protocol': 'Step-by-step experimental or clinical procedure',
}

# Confidence levels (categorical, not fake percentages)
CONFIDENCE_LEVELS = ('high', 'moderate', 'low')


class PaperTypeDetector:
    """Detect paper type from text content."""

    def __init__(self, openai_client=None, chat_deployment: str = None):
        self._client = openai_client
        self._chat_deployment = chat_deployment

    @property
    def client(self):
        if self._client is None:
            try:
                from services.openai_client import get_openai_client
                self._client = get_openai_client()
            except Exception:
                pass
        return self._client

    @property
    def chat_deployment(self):
        if self._chat_deployment is None:
            import os
            self._chat_deployment = os.getenv("AZURE_CHAT_DEPLOYMENT", "gpt-5-chat")
        return self._chat_deployment

    def detect(self, text: str, title: str = '') -> Dict[str, Any]:
        """
        Detect paper type from text content.

        Args:
            text: Full text content of the paper (first 5K chars used for LLM)
            title: Optional title for additional context

        Returns:
            {
                paper_type: str,
                confidence: 'high' | 'moderate' | 'low',
                signals: [str],     # evidence strings
                all_scores: {type: score}  # relative weights
            }
        """
        if not text or len(text.strip()) < 50:
            return {
                'paper_type': 'experimental',
                'confidence': 'low',
                'signals': ['Text too short for reliable classification'],
                'all_scores': {},
            }

        # Try LLM classification first
        llm_result = self._classify_with_llm(text, title)
        if llm_result:
            return llm_result

        # Fallback to heuristic
        return self._classify_heuristic(text, title)

    def _classify_with_llm(self, text: str, title: str) -> Optional[Dict[str, Any]]:
        """Classify using LLM on the first ~5K characters."""
        if not self.client:
            return None

        sample = text[:5000]
        title_hint = f"Title: {title}\n\n" if title else ""

        prompt = f"""{title_hint}Classify this academic paper into exactly one type.

Types:
- experimental: Original research with methods, experiments, results
- review: Systematic or narrative review summarizing existing literature
- meta_analysis: Quantitative synthesis combining results from multiple studies
- case_report: Report of a specific clinical case or small patient series
- protocol: Step-by-step laboratory or clinical procedure

TEXT (first 5000 chars):
{sample}

Respond in JSON:
{{
    "paper_type": "experimental|review|meta_analysis|case_report|protocol",
    "confidence": "high|moderate|low",
    "signals": ["signal 1", "signal 2", "signal 3"]
}}

Rules:
- "signals" should list 2-4 specific textual evidence that led to classification
- If unclear, use "low" confidence
- Do not guess; base it on actual content"""

        try:
            if hasattr(self.client, 'chat_completion'):
                # OpenAIClientWrapper
                response = self.client.chat_completion(
                    messages=[
                        {"role": "system", "content": "You classify academic papers by type. Respond only with valid JSON."},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.1,
                    max_tokens=400,
                    response_format={"type": "json_object"},
                )
                content = response.choices[0].message.content
            else:
                # Raw AzureOpenAI client
                response = self.client.chat.completions.create(
                    model=self.chat_deployment,
                    messages=[
                        {"role": "system", "content": "You classify academic papers by type. Respond only with valid JSON."},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.1,
                    max_tokens=400,
                    response_format={"type": "json_object"},
                )
                content = response.choices[0].message.content

            result = json.loads(content)
            paper_type = result.get('paper_type', 'experimental')
            if paper_type not in PAPER_TYPES:
                paper_type = 'experimental'

            confidence = result.get('confidence', 'moderate')
            if confidence not in CONFIDENCE_LEVELS:
                confidence = 'moderate'

            signals = result.get('signals', [])
            if not isinstance(signals, list):
                signals = []

            return {
                'paper_type': paper_type,
                'confidence': confidence,
                'signals': signals[:5],
                'all_scores': {paper_type: 1.0},
                'detection_method': 'llm',
            }
        except Exception as e:
            logger.warning(f"[PaperTypeDetector] LLM classification failed: {e}")
            return None

    def _classify_heuristic(self, text: str, title: str = '') -> Dict[str, Any]:
        """Heuristic fallback classification based on section headers and keywords."""
        text_lower = text.lower()
        title_lower = title.lower() if title else ''
        combined = f"{title_lower} {text_lower}"
        scores = {t: 0.0 for t in PAPER_TYPES}
        signals = []

        # --- Protocol signals ---
        protocol_indicators = [
            (r'\b(step\s+\d+|protocol|procedure)\b', 2.0),
            (r'\d+\s*(?:mL|µL|µg|mg|mM|rpm|°C|min(?:utes?)?)\b', 1.5),
            (r'\b(pipette|incubate|centrifuge|vortex|wash|rinse|aspirate)\b', 1.5),
            (r'\b(reagent|buffer|solution|media)\b', 1.0),
        ]
        for pattern, weight in protocol_indicators:
            matches = re.findall(pattern, text_lower[:10000])
            if matches:
                scores['protocol'] += weight * min(len(matches), 5)
                if weight >= 1.5:
                    signals.append(f"Protocol indicator: found '{matches[0]}' ({len(matches)} occurrences)")

        # --- Review signals ---
        review_indicators = [
            (r'\b(systematic\s+review|literature\s+review|narrative\s+review|scoping\s+review)\b', 5.0),
            (r'\b(we\s+review|this\s+review|reviewed?\s+the\s+literature)\b', 3.0),
            (r'\b(search\s+strategy|inclusion\s+criteria|exclusion\s+criteria|prisma)\b', 3.0),
            (r'\b(databases?\s+(?:searched|were|included))\b', 2.0),
        ]
        for pattern, weight in review_indicators:
            matches = re.findall(pattern, combined)
            if matches:
                scores['review'] += weight
                signals.append(f"Review indicator: '{matches[0]}'")

        # --- Meta-analysis signals ---
        meta_indicators = [
            (r'\b(meta[\-\s]?analysis|pooled\s+analysis|forest\s+plot)\b', 5.0),
            (r'\b(heterogeneity|I[²2]\s*=|random[\-\s]?effects?\s+model)\b', 4.0),
            (r'\b(funnel\s+plot|publication\s+bias|egger)\b', 3.0),
            (r'\b(pooled\s+(?:estimate|effect|OR|RR|HR))\b', 3.0),
        ]
        for pattern, weight in meta_indicators:
            matches = re.findall(pattern, combined)
            if matches:
                scores['meta_analysis'] += weight
                signals.append(f"Meta-analysis indicator: '{matches[0]}'")

        # --- Case report signals ---
        case_indicators = [
            (r'\b(case\s+report|case\s+study|case\s+presentation)\b', 5.0),
            (r'\b(a\s+\d+[\-\s]?year[\-\s]?old)\b', 4.0),
            (r'\b(chief\s+complaint|present(?:ing|ed)\s+(?:with|to)|admitted\s+to)\b', 3.0),
            (r'\b(physical\s+exam(?:ination)?|past\s+medical\s+history)\b', 2.0),
        ]
        for pattern, weight in case_indicators:
            matches = re.findall(pattern, combined)
            if matches:
                scores['case_report'] += weight
                signals.append(f"Case report indicator: '{matches[0]}'")

        # --- Experimental signals ---
        exp_indicators = [
            (r'\b(materials?\s+and\s+methods?|methods?\s+and\s+materials?)\b', 3.0),
            (r'\b(we\s+(?:measured|tested|examined|investigated|analyzed|performed))\b', 2.0),
            (r'\b(results?\s+(?:showed?|demonstrated?|indicated?))\b', 2.0),
            (r'\b(figure\s+\d|table\s+\d|fig\.\s*\d|supplementary)\b', 1.5),
            (r'\b(p\s*[<>=]\s*0\.\d|statistically\s+significant)\b', 2.0),
            (r'\b(control\s+group|experimental\s+group|n\s*=\s*\d)\b', 2.0),
        ]
        for pattern, weight in exp_indicators:
            matches = re.findall(pattern, combined[:15000])
            if matches:
                scores['experimental'] += weight
                signals.append(f"Experimental indicator: '{matches[0]}'")

        # --- Reference density as review/meta_analysis boost ---
        ref_count = len(re.findall(r'\[\d+\]|\(\d{4}\)', text[:20000]))
        if ref_count > 80:
            scores['review'] += 2.0
            scores['meta_analysis'] += 1.0
            signals.append(f"High reference density: {ref_count} references")

        # Determine winner
        max_type = max(scores, key=scores.get)
        max_score = scores[max_type]

        if max_score == 0:
            # Default to experimental if nothing matched
            max_type = 'experimental'
            confidence = 'low'
            signals.append('No strong indicators found; defaulting to experimental')
        elif max_score < 5:
            confidence = 'low'
        elif max_score < 10:
            confidence = 'moderate'
        else:
            confidence = 'high'

        return {
            'paper_type': max_type,
            'confidence': confidence,
            'signals': signals[:5],
            'all_scores': {k: round(v, 2) for k, v in scores.items() if v > 0},
            'detection_method': 'heuristic',
        }
