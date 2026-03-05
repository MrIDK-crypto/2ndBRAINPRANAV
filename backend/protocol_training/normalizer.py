"""
Protocol Corpus Normalizer
============================
Merges outputs from all 5 ingesters into a single unified corpus.
Deduplicates across sources and generates corpus-level statistics.

Unified schema:
  {
    "id": "md5 hash",
    "source": "chemh|bioprotocolbench|wlp|openwetware|protocolsio",
    "title": "Protocol Title",
    "domain": "biology|chemistry|...",
    "steps": [{"order": 1, "text": "...", "action_verb": "...", ...}],
    "reagents": ["..."],
    "equipment": ["..."],
    "safety_notes": ["..."],
    "raw_text": "...",
    "metadata": {...}
  }
"""

import os
import json
import logging
from typing import List, Dict, Any, Tuple
from collections import defaultdict
from hashlib import md5

from . import CORPUS_DIR

logger = logging.getLogger(__name__)

UNIFIED_FILE = os.path.join(CORPUS_DIR, 'unified_corpus.jsonl')
STATS_FILE = os.path.join(CORPUS_DIR, 'corpus_stats.json')


def _load_jsonl(filepath: str) -> List[Dict]:
    """Load a JSONL file."""
    if not os.path.exists(filepath):
        logger.warning(f'[Normalizer] File not found: {filepath}')
        return []
    protocols = []
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    protocols.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return protocols


def _deduplicate(protocols: List[Dict]) -> List[Dict]:
    """Deduplicate protocols by title similarity."""
    seen_titles = {}
    unique = []

    for p in protocols:
        # Normalize title for comparison
        title_key = p['title'].lower().strip()
        title_key = ''.join(c for c in title_key if c.isalnum() or c == ' ')
        title_key = ' '.join(title_key.split())

        if title_key in seen_titles:
            # Keep the one with more steps
            existing_idx = seen_titles[title_key]
            if len(p.get('steps', [])) > len(unique[existing_idx].get('steps', [])):
                unique[existing_idx] = p
        else:
            seen_titles[title_key] = len(unique)
            unique.append(p)

    return unique


def _compute_stats(protocols: List[Dict]) -> Dict[str, Any]:
    """Compute corpus-level statistics."""
    stats = {
        'total_protocols': len(protocols),
        'by_source': defaultdict(int),
        'by_domain': defaultdict(int),
        'total_steps': 0,
        'protocols_with_steps': 0,
        'protocols_with_reagents': 0,
        'protocols_with_equipment': 0,
        'protocols_with_safety': 0,
        'unique_action_verbs': set(),
        'unique_reagents': set(),
        'unique_equipment': set(),
        'avg_steps_per_protocol': 0,
    }

    for p in protocols:
        stats['by_source'][p['source']] += 1
        stats['by_domain'][p.get('domain', 'unknown')] += 1

        steps = p.get('steps', [])
        stats['total_steps'] += len(steps)
        if steps:
            stats['protocols_with_steps'] += 1
        if p.get('reagents'):
            stats['protocols_with_reagents'] += 1
        if p.get('equipment'):
            stats['protocols_with_equipment'] += 1
        if p.get('safety_notes'):
            stats['protocols_with_safety'] += 1

        for step in steps:
            if step.get('action_verb'):
                stats['unique_action_verbs'].add(step['action_verb'].lower())

        for r in p.get('reagents', []):
            stats['unique_reagents'].add(r.lower())
        for e in p.get('equipment', []):
            stats['unique_equipment'].add(e.lower())

    if protocols:
        stats['avg_steps_per_protocol'] = round(stats['total_steps'] / len(protocols), 1)

    # Convert sets to counts and sorted lists
    stats['num_unique_action_verbs'] = len(stats['unique_action_verbs'])
    stats['num_unique_reagents'] = len(stats['unique_reagents'])
    stats['num_unique_equipment'] = len(stats['unique_equipment'])
    stats['top_action_verbs'] = sorted(list(stats['unique_action_verbs']))[:100]
    stats['top_reagents'] = sorted(list(stats['unique_reagents']))[:100]
    stats['top_equipment'] = sorted(list(stats['unique_equipment']))[:100]

    # Clean up for JSON serialization
    stats['by_source'] = dict(stats['by_source'])
    stats['by_domain'] = dict(stats['by_domain'])
    del stats['unique_action_verbs']
    del stats['unique_reagents']
    del stats['unique_equipment']

    return stats


def normalize() -> Tuple[List[Dict], Dict[str, Any]]:
    """Load all source JSONL files, merge, deduplicate, compute stats."""

    source_files = [
        os.path.join(CORPUS_DIR, 'chemh_protocols.jsonl'),
        os.path.join(CORPUS_DIR, 'wlp_protocols.jsonl'),
        os.path.join(CORPUS_DIR, 'bioprotocolbench_protocols.jsonl'),
        os.path.join(CORPUS_DIR, 'protocolsio_protocols.jsonl'),
        os.path.join(CORPUS_DIR, 'openwetware_protocols.jsonl'),
    ]

    all_protocols = []
    for filepath in source_files:
        protocols = _load_jsonl(filepath)
        logger.info(f'[Normalizer] Loaded {len(protocols)} from {os.path.basename(filepath)}')
        all_protocols.extend(protocols)

    logger.info(f'[Normalizer] Total before dedup: {len(all_protocols)}')

    # Deduplicate
    unique = _deduplicate(all_protocols)
    logger.info(f'[Normalizer] Total after dedup: {len(unique)}')

    # Compute stats
    stats = _compute_stats(unique)

    # Save unified corpus
    with open(UNIFIED_FILE, 'w') as f:
        for p in unique:
            f.write(json.dumps(p) + '\n')

    # Save stats
    with open(STATS_FILE, 'w') as f:
        json.dump(stats, f, indent=2)

    logger.info(f'[Normalizer] Saved unified corpus to {UNIFIED_FILE}')
    logger.info(f'[Normalizer] Stats: {stats["total_protocols"]} protocols, '
                f'{stats["total_steps"]} steps, '
                f'{stats["num_unique_action_verbs"]} action verbs, '
                f'{stats["num_unique_reagents"]} reagents')

    return unique, stats


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    protocols, stats = normalize()
    print(f'\nUnified corpus: {stats["total_protocols"]} protocols')
    print(f'By source: {stats["by_source"]}')
    print(f'Steps: {stats["total_steps"]} total, {stats["avg_steps_per_protocol"]} avg')
    print(f'Action verbs: {stats["num_unique_action_verbs"]}')
    print(f'Reagents: {stats["num_unique_reagents"]}')
    print(f'Equipment: {stats["num_unique_equipment"]}')
