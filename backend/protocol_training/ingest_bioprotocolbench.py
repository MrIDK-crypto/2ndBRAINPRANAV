"""
BioProtocolBench Ingester
==========================
Downloads and parses the BioProtocolBench dataset from:
  https://github.com/YuyangSunshine/bioprotocolbench

27,000 biological protocols with 556K+ structured instances across
5 ML tasks: Protocol QA, Step Ordering, Error Correction,
Protocol Generation, Protocol Reasoning.

Output:
  - Raw protocol corpus (for pattern mining + reference store)
  - Structured ML training instances (for sklearn classifiers)
"""

import os
import re
import json
import logging
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from hashlib import md5
from collections import defaultdict

from . import REPOS_DIR, CORPUS_DIR

logger = logging.getLogger(__name__)

REPO_URL = 'https://github.com/YuyangSunshine/bioprotocolbench.git'
REPO_DIR = os.path.join(REPOS_DIR, 'bioprotocolbench')
OUTPUT_PROTOCOLS = os.path.join(CORPUS_DIR, 'bioprotocolbench_protocols.jsonl')
OUTPUT_TRAINING = os.path.join(CORPUS_DIR, 'bioprotocolbench_training.json')


def download() -> str:
    """Clone or pull the BioProtocolBench repository."""
    if os.path.exists(os.path.join(REPO_DIR, '.git')):
        logger.info('[BPB] Pulling latest changes...')
        subprocess.run(['git', '-C', REPO_DIR, 'pull', '--quiet'], check=True)
    else:
        logger.info('[BPB] Cloning repository...')
        os.makedirs(REPO_DIR, exist_ok=True)
        subprocess.run(['git', 'clone', '--depth=1', REPO_URL, REPO_DIR], check=True)
    return REPO_DIR


def _find_json_data(repo_dir: str) -> Dict[str, List[str]]:
    """Find JSON data files organized by task type."""
    task_files = defaultdict(list)
    for json_file in Path(repo_dir).rglob('*.json'):
        name = json_file.stem.lower()
        rel_path = str(json_file.relative_to(repo_dir)).lower()

        # Categorize by task type based on path/filename
        if 'ord' in name or 'order' in rel_path:
            task_files['step_ordering'].append(str(json_file))
        elif 'err' in name or 'error' in rel_path or 'correct' in rel_path:
            task_files['error_correction'].append(str(json_file))
        elif 'qa' in name or 'question' in rel_path:
            task_files['protocol_qa'].append(str(json_file))
        elif 'gen' in name or 'generat' in rel_path:
            task_files['protocol_generation'].append(str(json_file))
        elif 'rea' in name or 'reason' in rel_path:
            task_files['protocol_reasoning'].append(str(json_file))
        elif 'corpus' in rel_path or 'raw' in rel_path or 'protocol' in rel_path:
            task_files['raw_protocols'].append(str(json_file))
        else:
            task_files['other'].append(str(json_file))

    # Also check for JSONL files
    for jsonl_file in Path(repo_dir).rglob('*.jsonl'):
        task_files['other'].append(str(jsonl_file))

    return dict(task_files)


def _load_json_safe(filepath: str) -> Optional[Any]:
    """Load a JSON or JSONL file safely."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read().strip()
            if not content:
                return None
            # Try as regular JSON first
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                # Try as JSONL
                lines = []
                for line in content.split('\n'):
                    line = line.strip()
                    if line:
                        try:
                            lines.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
                return lines if lines else None
    except Exception as e:
        logger.warning(f'[BPB] Failed to load {filepath}: {e}')
        return None


def _extract_protocol_from_instance(instance: Dict) -> Optional[Dict]:
    """Extract a protocol dict from a training instance."""
    # BioProtocolBench instances vary by task but typically have:
    # - protocol/text/input: the protocol text
    # - steps: list of steps
    # - title/name: protocol name
    text = (instance.get('protocol') or instance.get('text') or
            instance.get('input') or instance.get('context') or '')

    if isinstance(text, list):
        text = '\n'.join(str(t) for t in text)
    text = str(text)

    if len(text) < 30:
        return None

    title = (instance.get('title') or instance.get('name') or
             instance.get('protocol_title') or text[:80].split('\n')[0])

    # Try to extract steps
    steps_raw = instance.get('steps', [])
    if isinstance(steps_raw, str):
        steps_raw = [s.strip() for s in re.split(r'\d+\.\s+|\n', steps_raw) if s.strip()]
    elif not isinstance(steps_raw, list):
        steps_raw = []

    steps = []
    for i, step_text in enumerate(steps_raw, 1):
        if isinstance(step_text, dict):
            step_text = step_text.get('text', step_text.get('step', str(step_text)))
        step_text = str(step_text).strip()
        if step_text:
            action_match = re.match(r'^(\w+)', step_text.lower())
            steps.append({
                'order': i,
                'text': step_text,
                'action_verb': action_match.group(1) if action_match else None,
                'reagents': [],
                'equipment': [],
                'parameters': [],
            })

    # If no explicit steps, try splitting text into numbered steps
    if not steps:
        numbered = re.findall(r'^\s*(\d+)\.\s+(.+)$', text, re.MULTILINE)
        for order, step_text in numbered:
            action_match = re.match(r'^(\w+)', step_text.lower())
            steps.append({
                'order': int(order),
                'text': step_text.strip(),
                'action_verb': action_match.group(1) if action_match else None,
                'reagents': [],
                'equipment': [],
                'parameters': [],
            })

    # Determine domain from metadata
    domain = (instance.get('domain') or instance.get('category') or
              instance.get('subdomain') or 'biology')
    if isinstance(domain, list):
        domain = domain[0] if domain else 'biology'

    protocol_id = md5(f'bpb:{title[:100]}:{text[:200]}'.encode()).hexdigest()

    return {
        'id': protocol_id,
        'source': 'bioprotocolbench',
        'title': str(title)[:500],
        'domain': str(domain).lower(),
        'steps': steps,
        'reagents': [],
        'equipment': [],
        'safety_notes': [],
        'raw_text': text[:50000],
        'metadata': {
            'num_steps': len(steps),
            'task_origin': instance.get('_task_type', 'unknown'),
        }
    }


def _extract_training_data(task_files: Dict[str, List[str]]) -> Dict[str, List[Dict]]:
    """Extract ML training instances organized by task type."""
    training = {
        'step_ordering': [],
        'error_correction': [],
        'protocol_qa': [],
        'protocol_reasoning': [],
    }

    for task_type, files in task_files.items():
        if task_type in ('raw_protocols', 'other', 'protocol_generation'):
            continue

        for filepath in files:
            data = _load_json_safe(filepath)
            if not data:
                continue

            instances = data if isinstance(data, list) else [data]
            for inst in instances:
                if not isinstance(inst, dict):
                    continue
                inst['_task_type'] = task_type
                inst['_source_file'] = os.path.basename(filepath)

                if task_type in training:
                    training[task_type].append(inst)

    return training


def ingest() -> Tuple[List[Dict], Dict[str, List[Dict]]]:
    """Download, parse protocols and training data, and save."""
    repo_dir = download()

    # Find and categorize data files
    task_files = _find_json_data(repo_dir)
    logger.info(f'[BPB] Found data files by task:')
    for task, files in task_files.items():
        logger.info(f'  - {task}: {len(files)} files')

    # Extract protocols from all JSON files
    protocols = []
    seen_ids = set()
    all_files = [f for files in task_files.values() for f in files]

    for filepath in all_files:
        data = _load_json_safe(filepath)
        if not data:
            continue

        instances = data if isinstance(data, list) else [data]
        for inst in instances:
            if not isinstance(inst, dict):
                continue
            protocol = _extract_protocol_from_instance(inst)
            if protocol and protocol['id'] not in seen_ids:
                seen_ids.add(protocol['id'])
                protocols.append(protocol)

    logger.info(f'[BPB] Extracted {len(protocols)} unique protocols')

    # Extract structured training data
    training_data = _extract_training_data(task_files)
    logger.info(f'[BPB] Training data:')
    for task, instances in training_data.items():
        logger.info(f'  - {task}: {len(instances)} instances')

    # Save protocols
    with open(OUTPUT_PROTOCOLS, 'w') as f:
        for p in protocols:
            f.write(json.dumps(p) + '\n')

    # Save training data
    with open(OUTPUT_TRAINING, 'w') as f:
        json.dump({
            'metadata': {
                'total_protocols': len(protocols),
                'training_instances': {k: len(v) for k, v in training_data.items()},
            },
            'training': {k: v[:10000] for k, v in training_data.items()},  # Cap at 10K per task for storage
        }, f)

    logger.info(f'[BPB] Saved to {OUTPUT_PROTOCOLS} and {OUTPUT_TRAINING}')

    return protocols, training_data


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    protocols, training = ingest()
    print(f'\nIngested {len(protocols)} BioProtocolBench protocols')
    print(f'Training instances:')
    for task, instances in training.items():
        print(f'  {task}: {len(instances)}')
