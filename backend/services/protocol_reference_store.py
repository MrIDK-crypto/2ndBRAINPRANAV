"""
Protocol Reference Store
=========================
In-memory TF-IDF index of protocol corpus for gap comparison.

Provides:
  - find_similar_protocols(text, top_k) → matched protocols
  - find_missing_steps(protocol_steps, domain) → expected steps not found
  - get_domain_stats(domain) → typical step count, common reagents, etc.
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from collections import Counter, defaultdict

logger = logging.getLogger(__name__)

CORPUS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'protocol_corpus')
UNIFIED_CORPUS = os.path.join(CORPUS_DIR, 'unified_corpus.jsonl')

_store = None
_store_loaded = False


class ProtocolReferenceStore:
    """In-memory TF-IDF index over protocol corpus."""

    def __init__(self):
        self.protocols: List[Dict] = []
        self.vectorizer = None
        self.tfidf_matrix = None
        self.domain_stats: Dict[str, Dict] = {}
        self.domain_protocols: Dict[str, List[int]] = defaultdict(list)

    def load(self, max_protocols: int = 30000) -> bool:
        """Load corpus and build TF-IDF index."""
        if not os.path.exists(UNIFIED_CORPUS):
            logger.warning('[RefStore] Unified corpus not found')
            return False

        # Load protocols
        self.protocols = []
        with open(UNIFIED_CORPUS, 'r') as f:
            for line in f:
                line = line.strip()
                if line and len(self.protocols) < max_protocols:
                    try:
                        self.protocols.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

        if not self.protocols:
            logger.warning('[RefStore] No protocols loaded')
            return False

        logger.info(f'[RefStore] Loaded {len(self.protocols)} protocols')

        # Index by domain
        for i, p in enumerate(self.protocols):
            domain = p.get('domain', 'unknown')
            self.domain_protocols[domain].append(i)

        # Build TF-IDF index
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer

            texts = []
            for p in self.protocols:
                # Combine title + steps for matching
                step_texts = ' '.join(s.get('text', '') for s in p.get('steps', []))
                texts.append(f"{p.get('title', '')} {step_texts}"[:5000])

            self.vectorizer = TfidfVectorizer(
                max_features=10000,
                ngram_range=(1, 2),
                min_df=2,
                max_df=0.95,
                sublinear_tf=True,
            )
            self.tfidf_matrix = self.vectorizer.fit_transform(texts)
            logger.info(f'[RefStore] Built TF-IDF index: {self.tfidf_matrix.shape}')

        except ImportError:
            logger.warning('[RefStore] scikit-learn not installed, search disabled')
            self.vectorizer = None

        # Compute domain stats
        self._compute_domain_stats()

        return True

    def _compute_domain_stats(self):
        """Compute per-domain statistics."""
        for domain, indices in self.domain_protocols.items():
            step_counts = []
            action_verbs = Counter()
            reagent_counts = Counter()
            equipment_counts = Counter()

            for idx in indices:
                p = self.protocols[idx]
                steps = p.get('steps', [])
                step_counts.append(len(steps))

                for step in steps:
                    v = step.get('action_verb')
                    if v:
                        action_verbs[v.lower()] += 1

                for r in p.get('reagents', []):
                    reagent_counts[r.lower()] += 1

                for e in p.get('equipment', []):
                    equipment_counts[e.lower()] += 1

            self.domain_stats[domain] = {
                'count': len(indices),
                'avg_steps': round(sum(step_counts) / max(len(step_counts), 1), 1),
                'median_steps': sorted(step_counts)[len(step_counts) // 2] if step_counts else 0,
                'top_verbs': [v for v, _ in action_verbs.most_common(20)],
                'top_reagents': [r for r, _ in reagent_counts.most_common(20)],
                'top_equipment': [e for e, _ in equipment_counts.most_common(20)],
            }

    def find_similar_protocols(self, text: str, top_k: int = 5,
                                domain: Optional[str] = None) -> List[Dict]:
        """Find protocols most similar to the given text."""
        if self.vectorizer is None or self.tfidf_matrix is None:
            return []

        try:
            from sklearn.metrics.pairwise import cosine_similarity
            import numpy as np

            query_vec = self.vectorizer.transform([text[:5000]])
            similarities = cosine_similarity(query_vec, self.tfidf_matrix).flatten()

            # Filter by domain if specified
            if domain and domain in self.domain_protocols:
                mask = set(self.domain_protocols[domain])
                for i in range(len(similarities)):
                    if i not in mask:
                        similarities[i] = 0.0

            top_indices = np.argsort(similarities)[-top_k:][::-1]

            results = []
            for idx in top_indices:
                if similarities[idx] > 0.05:  # Minimum similarity threshold
                    p = self.protocols[idx]
                    results.append({
                        'title': p.get('title', ''),
                        'domain': p.get('domain', ''),
                        'source': p.get('source', ''),
                        'num_steps': len(p.get('steps', [])),
                        'similarity': round(float(similarities[idx]), 3),
                        'step_verbs': [s.get('action_verb', '') for s in p.get('steps', []) if s.get('action_verb')],
                        'reagents': p.get('reagents', [])[:10],
                        'equipment': p.get('equipment', [])[:10],
                    })

            return results

        except Exception as e:
            logger.warning(f'[RefStore] Search failed: {e}')
            return []

    def find_missing_steps(self, protocol_steps: List[str],
                            domain: Optional[str] = None) -> List[Dict]:
        """
        Compare protocol steps against reference corpus to find potentially missing steps.

        Returns list of suggested missing steps with evidence.
        """
        if not protocol_steps:
            return []

        # Find similar protocols
        combined_text = ' '.join(protocol_steps)
        similar = self.find_similar_protocols(combined_text, top_k=10, domain=domain)

        if not similar:
            return []

        # Collect common action verbs from similar protocols
        ref_verbs = Counter()
        for s in similar:
            for v in s.get('step_verbs', []):
                ref_verbs[v.lower()] += 1

        # Identify action verbs in current protocol
        import re
        current_verbs = set()
        for step in protocol_steps:
            match = re.match(r'^(\w+)', step.lower())
            if match:
                current_verbs.add(match.group(1))

        # Find verbs common in references but missing in current protocol
        missing = []
        for verb, count in ref_verbs.most_common(20):
            if verb not in current_verbs and count >= 3:
                missing.append({
                    'verb': verb,
                    'frequency': count,
                    'message': f'Step "{verb}" found in {count}/{len(similar)} similar protocols but missing here',
                    'similar_protocols': [s['title'] for s in similar if verb in [v.lower() for v in s.get('step_verbs', [])]],
                })

        return missing

    def get_domain_stats(self, domain: str) -> Optional[Dict]:
        """Get statistics for a specific protocol domain."""
        return self.domain_stats.get(domain)

    def get_all_domains(self) -> List[str]:
        """Get all available domains."""
        return sorted(self.domain_stats.keys())


def get_store() -> ProtocolReferenceStore:
    """Get or create the singleton reference store."""
    global _store, _store_loaded

    if _store_loaded:
        return _store

    _store_loaded = True
    _store = ProtocolReferenceStore()
    if not _store.load():
        logger.info('[RefStore] Reference store not available (corpus not ingested yet)')

    return _store


def reload_store():
    """Force reload the reference store."""
    global _store, _store_loaded
    _store = None
    _store_loaded = False
    get_store()
