"""
WLP-Parser Corpus Ingester
============================
Downloads and parses the annotated wet lab protocol corpus from:
  https://github.com/chaitanya2334/WLP-Parser

BRAT annotation format (.txt + .ann files):
  - T# annotations: entities (Action, Reagent, Location, Device, etc.)
  - R# annotations: relations between entities

Output:
  - Entity vocabulary lists (action verbs, materials, equipment, conditions)
  - Annotated protocol instances for NER training data
"""

import os
import re
import json
import logging
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Tuple
from collections import defaultdict
from hashlib import md5

from . import REPOS_DIR, CORPUS_DIR

logger = logging.getLogger(__name__)

REPO_URL = 'https://github.com/chaitanya2334/WLP-Parser.git'
REPO_DIR = os.path.join(REPOS_DIR, 'wlp-parser')
OUTPUT_PROTOCOLS = os.path.join(CORPUS_DIR, 'wlp_protocols.jsonl')
OUTPUT_VOCAB = os.path.join(CORPUS_DIR, 'wlp_vocabulary.json')


def download() -> str:
    """Clone or pull the WLP-Parser repository."""
    if os.path.exists(os.path.join(REPO_DIR, '.git')):
        logger.info('[WLP] Pulling latest changes...')
        subprocess.run(['git', '-C', REPO_DIR, 'pull', '--quiet'], check=True)
    else:
        logger.info('[WLP] Cloning repository...')
        os.makedirs(REPO_DIR, exist_ok=True)
        subprocess.run(['git', 'clone', '--depth=1', REPO_URL, REPO_DIR], check=True)
    return REPO_DIR


def _find_data_dirs(repo_dir: str) -> List[str]:
    """Find directories containing BRAT annotation files."""
    data_dirs = []
    for root, dirs, files in os.walk(repo_dir):
        ann_files = [f for f in files if f.endswith('.ann')]
        if ann_files:
            data_dirs.append(root)
    return data_dirs


def _parse_ann_file(ann_path: str) -> Tuple[List[Dict], List[Dict]]:
    """Parse a BRAT .ann file into entities and relations."""
    entities = []
    relations = []

    try:
        with open(ann_path, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                if line.startswith('T'):
                    # Entity annotation: T1\tAction 0 10\tPipette
                    parts = line.split('\t')
                    if len(parts) >= 3:
                        ann_id = parts[0]
                        type_span = parts[1].split(' ')
                        entity_type = type_span[0]
                        text = parts[2] if len(parts) > 2 else ''
                        try:
                            start = int(type_span[1])
                            end = int(type_span[-1])
                        except (ValueError, IndexError):
                            start, end = 0, 0
                        entities.append({
                            'id': ann_id,
                            'type': entity_type,
                            'start': start,
                            'end': end,
                            'text': text,
                        })

                elif line.startswith('R'):
                    # Relation annotation: R1\tActs-on Arg1:T1 Arg2:T2
                    parts = line.split('\t')
                    if len(parts) >= 2:
                        ann_id = parts[0]
                        rel_parts = parts[1].split(' ')
                        rel_type = rel_parts[0]
                        args = {}
                        for rp in rel_parts[1:]:
                            if ':' in rp:
                                key, val = rp.split(':', 1)
                                args[key] = val
                        relations.append({
                            'id': ann_id,
                            'type': rel_type,
                            'args': args,
                        })
    except Exception as e:
        logger.warning(f'[WLP] Failed to parse {ann_path}: {e}')

    return entities, relations


def _parse_protocol_pair(txt_path: str, ann_path: str) -> Dict[str, Any]:
    """Parse a .txt + .ann file pair into a structured protocol."""
    try:
        with open(txt_path, 'r', encoding='utf-8', errors='replace') as f:
            text = f.read()
    except Exception as e:
        logger.warning(f'[WLP] Failed to read {txt_path}: {e}')
        return None

    entities, relations = _parse_ann_file(ann_path)

    filename = os.path.basename(txt_path)
    protocol_id = md5(f'wlp:{filename}'.encode()).hexdigest()

    # Group entities by type
    entities_by_type = defaultdict(list)
    for ent in entities:
        entities_by_type[ent['type']].append(ent['text'])

    # Extract steps from text (sentences containing action entities)
    action_texts = set(e['text'].lower() for e in entities if e['type'] in ('Action', 'action'))
    sentences = re.split(r'[.!?]\s+|\n+', text)
    steps = []
    for i, sent in enumerate(sentences, 1):
        sent = sent.strip()
        if not sent or len(sent) < 10:
            continue
        is_step = any(act in sent.lower() for act in action_texts) if action_texts else True
        if is_step:
            steps.append({
                'order': len(steps) + 1,
                'text': sent,
                'action_verb': None,
                'reagents': [e['text'] for e in entities
                            if e['type'] in ('Reagent', 'reagent', 'Material')
                            and e['start'] >= text.find(sent)
                            and e['end'] <= text.find(sent) + len(sent)],
                'equipment': [e['text'] for e in entities
                             if e['type'] in ('Device', 'device', 'Equipment', 'Location', 'location')
                             and e['start'] >= text.find(sent)
                             and e['end'] <= text.find(sent) + len(sent)],
                'parameters': [],
            })

    # Extract action verb from first entity match
    for step in steps:
        action_match = re.match(r'^(\w+)', step['text'].lower())
        if action_match:
            step['action_verb'] = action_match.group(1)

    return {
        'id': protocol_id,
        'source': 'wlp',
        'title': filename.replace('.txt', '').replace('_', ' '),
        'domain': 'wet_lab',
        'steps': steps,
        'reagents': list(set(entities_by_type.get('Reagent', []) + entities_by_type.get('reagent', []) + entities_by_type.get('Material', []))),
        'equipment': list(set(entities_by_type.get('Device', []) + entities_by_type.get('device', []) + entities_by_type.get('Equipment', []))),
        'safety_notes': [],
        'raw_text': text[:50000],
        'annotations': {
            'entities': entities,
            'relations': relations,
            'entity_types': dict(entities_by_type),
        },
        'metadata': {
            'filename': filename,
            'num_steps': len(steps),
            'num_entities': len(entities),
            'num_relations': len(relations),
            'entity_types': list(entities_by_type.keys()),
        }
    }


def _build_vocabulary(protocols: List[Dict]) -> Dict[str, List[str]]:
    """Build vocabulary lists from all parsed protocols."""
    vocab = defaultdict(set)

    for p in protocols:
        anns = p.get('annotations', {})
        entity_types = anns.get('entity_types', {})

        for ent_type, texts in entity_types.items():
            normalized_type = ent_type.lower()
            if normalized_type in ('action', 'method'):
                for t in texts:
                    vocab['action_verbs'].add(t.lower().strip())
            elif normalized_type in ('reagent', 'material'):
                for t in texts:
                    vocab['reagents'].add(t.strip())
            elif normalized_type in ('device', 'equipment', 'location'):
                for t in texts:
                    vocab['equipment'].add(t.strip())
            elif normalized_type in ('modifier', 'measure-type', 'numerical', 'amount', 'concentration', 'size'):
                for t in texts:
                    vocab['parameters'].add(t.strip())
            elif normalized_type in ('temperature', 'time', 'speed', 'ph'):
                for t in texts:
                    vocab['conditions'].add(t.strip())
            else:
                for t in texts:
                    vocab[f'other_{normalized_type}'].add(t.strip())

        # Also collect action verbs from steps
        for step in p.get('steps', []):
            if step.get('action_verb'):
                vocab['action_verbs'].add(step['action_verb'])

    # Convert sets to sorted lists
    return {k: sorted(list(v)) for k, v in vocab.items()}


def ingest() -> Tuple[List[Dict], Dict[str, List[str]]]:
    """Download, parse all protocols, build vocabulary, and save."""
    repo_dir = download()

    # Find data directories with annotations
    data_dirs = _find_data_dirs(repo_dir)
    logger.info(f'[WLP] Found {len(data_dirs)} directories with annotations')

    protocols = []
    for data_dir in data_dirs:
        txt_files = list(Path(data_dir).glob('*.txt'))
        for txt_file in txt_files:
            ann_file = txt_file.with_suffix('.ann')
            if ann_file.exists():
                protocol = _parse_protocol_pair(str(txt_file), str(ann_file))
                if protocol:
                    protocols.append(protocol)

    logger.info(f'[WLP] Parsed {len(protocols)} annotated protocols')

    # Build vocabulary
    vocabulary = _build_vocabulary(protocols)

    # Save protocols
    with open(OUTPUT_PROTOCOLS, 'w') as f:
        for p in protocols:
            f.write(json.dumps(p) + '\n')

    # Save vocabulary
    with open(OUTPUT_VOCAB, 'w') as f:
        json.dump(vocabulary, f, indent=2)

    # Summary
    logger.info(f'[WLP] Vocabulary: {sum(len(v) for v in vocabulary.values())} total terms')
    for k, v in vocabulary.items():
        logger.info(f'  - {k}: {len(v)} terms')

    return protocols, vocabulary


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    protocols, vocab = ingest()
    print(f'\nIngested {len(protocols)} WLP protocols')
    print(f'Vocabulary:')
    for k, v in vocab.items():
        print(f'  {k}: {len(v)} terms ({", ".join(v[:5])}...)')
