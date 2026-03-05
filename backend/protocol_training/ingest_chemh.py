"""
Stanford ChEMH MCAC Protocols Ingester
=======================================
Downloads and parses ~65 markdown protocols from:
  https://github.com/Stanford-ChEMH-MCAC/protocols

Covers: mass spectrometry operations, instrument maintenance,
sample preparation, ion source management, hardware installation,
software configuration.

Output: List of normalized protocol dicts.
"""

import os
import re
import json
import logging
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional
from hashlib import md5

from . import REPOS_DIR, CORPUS_DIR

logger = logging.getLogger(__name__)

REPO_URL = 'https://github.com/Stanford-ChEMH-MCAC/protocols.git'
REPO_DIR = os.path.join(REPOS_DIR, 'chemh-protocols')
OUTPUT_FILE = os.path.join(CORPUS_DIR, 'chemh_protocols.jsonl')


def download() -> str:
    """Clone or pull the Stanford ChEMH protocols repository."""
    if os.path.exists(os.path.join(REPO_DIR, '.git')):
        logger.info('[ChEMH] Pulling latest changes...')
        subprocess.run(['git', '-C', REPO_DIR, 'pull', '--quiet'], check=True)
    else:
        logger.info('[ChEMH] Cloning repository...')
        os.makedirs(REPO_DIR, exist_ok=True)
        subprocess.run(['git', 'clone', '--depth=1', REPO_URL, REPO_DIR], check=True)
    return REPO_DIR


def _extract_steps(content: str) -> List[Dict[str, Any]]:
    """Extract ordered steps from markdown content."""
    steps = []
    # Match numbered list items (1. Step text) or bullet items (- Step text)
    # Numbered lists are stronger protocol indicators
    numbered = re.findall(r'^\s*(\d+)\.\s+(.+)$', content, re.MULTILINE)
    if numbered:
        for order, text in numbered:
            steps.append(_parse_step(int(order), text.strip()))
    else:
        # Fall back to bullet points
        bullets = re.findall(r'^\s*[-*]\s+(.+)$', content, re.MULTILINE)
        for i, text in enumerate(bullets, 1):
            steps.append(_parse_step(i, text.strip()))
    return steps


def _parse_step(order: int, text: str) -> Dict[str, Any]:
    """Parse a single step to extract action verb, reagents, equipment, parameters."""
    step = {
        'order': order,
        'text': text,
        'action_verb': None,
        'reagents': [],
        'equipment': [],
        'parameters': [],
    }

    # Extract leading action verb
    action_match = re.match(r'^(\w+)', text.lower())
    if action_match:
        step['action_verb'] = action_match.group(1)

    # Extract parameters: numbers with units
    params = re.findall(
        r'(\d+(?:\.\d+)?)\s*(°?C|°?F|mL|µL|uL|mM|µM|uM|nM|mg|µg|ug|ng|rpm|xg|rcf|'
        r'min|minutes?|hrs?|hours?|sec|seconds?|psi|mbar|kV|V|Hz|mm|cm|nm|%|v/v|w/v|mg/mL|µg/mL)',
        text, re.IGNORECASE
    )
    step['parameters'] = [f"{val} {unit}" for val, unit in params]

    # Extract equipment keywords
    equipment_patterns = [
        r'(centrifuge|incubator|spectrometer|mass spec|HPLC|LC-MS|GC-MS|'
        r'autosampler|column|syringe|pipette|vortex|sonicator|'
        r'fume hood|biosafety cabinet|PCR|thermocycler|gel electrophoresis|'
        r'spectrophotometer|NMR|balance|pH meter|water bath|oven|freezer)',
    ]
    for pat in equipment_patterns:
        matches = re.findall(pat, text, re.IGNORECASE)
        step['equipment'].extend([m.lower() for m in matches])

    # Extract reagent-like terms (capitalized multi-word or with concentrations)
    reagent_matches = re.findall(
        r'(?:with|using|add|of)\s+([A-Z][a-zA-Z\s-]+?)(?:\s+(?:at|to|in|for)|\s*[,.]|$)',
        text
    )
    step['reagents'] = [r.strip() for r in reagent_matches if len(r.strip()) > 2]

    return step


def _extract_sections(content: str) -> Dict[str, str]:
    """Split markdown into sections by headers."""
    sections = {}
    current_header = 'introduction'
    current_content = []

    for line in content.split('\n'):
        header_match = re.match(r'^#{1,4}\s+(.+)$', line)
        if header_match:
            if current_content:
                sections[current_header] = '\n'.join(current_content).strip()
            current_header = header_match.group(1).strip().lower()
            current_content = []
        else:
            current_content.append(line)

    if current_content:
        sections[current_header] = '\n'.join(current_content).strip()

    return sections


def _extract_safety_notes(content: str) -> List[str]:
    """Extract safety-related sentences."""
    safety_keywords = re.compile(
        r'(caution|warning|danger|hazard|safety|PPE|gloves|goggles|'
        r'fume hood|toxic|corrosive|flammable|biohazard|waste|disposal|'
        r'eye protection|lab coat|ventilat)',
        re.IGNORECASE
    )
    notes = []
    for sentence in re.split(r'[.!]\s+', content):
        if safety_keywords.search(sentence):
            notes.append(sentence.strip())
    return notes


def parse_protocol(filepath: str) -> Optional[Dict[str, Any]]:
    """Parse a single markdown protocol file into structured format."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
    except Exception as e:
        logger.warning(f'[ChEMH] Failed to read {filepath}: {e}')
        return None

    if len(content.strip()) < 50:
        return None

    filename = os.path.basename(filepath)
    # Extract title from first H1 or filename
    title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else filename.replace('.md', '').replace('-', ' ').replace('_', ' ')

    sections = _extract_sections(content)
    steps = _extract_steps(content)
    safety_notes = _extract_safety_notes(content)

    # Collect all reagents and equipment across steps
    all_reagents = list(set(r for s in steps for r in s.get('reagents', [])))
    all_equipment = list(set(e for s in steps for e in s.get('equipment', [])))

    # Determine domain based on content keywords
    domain = 'mass_spectrometry'  # Default for ChEMH
    if re.search(r'sample\s+prep|extraction|purification', content, re.IGNORECASE):
        domain = 'sample_preparation'
    elif re.search(r'maintenance|cleaning|tuning', content, re.IGNORECASE):
        domain = 'instrument_maintenance'
    elif re.search(r'software|install|config', content, re.IGNORECASE):
        domain = 'software_configuration'

    protocol = {
        'id': md5(f'chemh:{filename}'.encode()).hexdigest(),
        'source': 'chemh',
        'title': title,
        'domain': domain,
        'steps': steps,
        'reagents': all_reagents,
        'equipment': all_equipment,
        'safety_notes': safety_notes,
        'sections': list(sections.keys()),
        'raw_text': content[:50000],
        'metadata': {
            'filename': filename,
            'num_steps': len(steps),
            'num_sections': len(sections),
            'has_safety': len(safety_notes) > 0,
        }
    }
    return protocol


def ingest() -> List[Dict[str, Any]]:
    """Download, parse all protocols, and save to JSONL."""
    repo_dir = download()

    protocols = []
    md_files = list(Path(repo_dir).rglob('*.md'))
    logger.info(f'[ChEMH] Found {len(md_files)} markdown files')

    for md_file in md_files:
        # Skip README and non-protocol files
        if md_file.name.lower() in ('readme.md', 'license.md', 'contributing.md'):
            continue
        protocol = parse_protocol(str(md_file))
        if protocol:
            protocols.append(protocol)

    logger.info(f'[ChEMH] Parsed {len(protocols)} protocols')

    # Save to JSONL
    with open(OUTPUT_FILE, 'w') as f:
        for p in protocols:
            f.write(json.dumps(p) + '\n')

    logger.info(f'[ChEMH] Saved to {OUTPUT_FILE}')

    # Print summary
    total_steps = sum(p['metadata']['num_steps'] for p in protocols)
    total_reagents = len(set(r for p in protocols for r in p['reagents']))
    total_equipment = len(set(e for p in protocols for e in p['equipment']))
    logger.info(f'[ChEMH] Summary: {len(protocols)} protocols, {total_steps} steps, '
                f'{total_reagents} unique reagents, {total_equipment} unique equipment')

    return protocols


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    results = ingest()
    print(f'\nIngested {len(results)} ChEMH protocols')
    for p in results[:3]:
        print(f'  - {p["title"]} ({p["metadata"]["num_steps"]} steps, domain: {p["domain"]})')
