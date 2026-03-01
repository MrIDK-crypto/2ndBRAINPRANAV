"""
protocols.io Public API Ingester
==================================
Fetches public protocols from protocols.io's free public API.

API docs: https://apidoc.protocols.io/
Public endpoint returns protocol metadata + steps in JSON format.

Output: List of normalized protocol dicts.
"""

import os
import re
import json
import logging
import time
from typing import List, Dict, Any, Optional
from hashlib import md5

try:
    import requests
except ImportError:
    requests = None

from . import CORPUS_DIR

logger = logging.getLogger(__name__)

API_BASE = 'https://www.protocols.io/api/v3'
OUTPUT_FILE = os.path.join(CORPUS_DIR, 'protocolsio_protocols.jsonl')

# Rate limit: be respectful
RATE_LIMIT_SECONDS = 1.0
MAX_PROTOCOLS = 5000  # Cap to avoid excessive API calls


def _fetch_page(page: int, page_size: int = 50) -> Optional[Dict]:
    """Fetch a single page of public protocols."""
    if not requests:
        raise ImportError('requests library required for protocols.io ingestion')

    url = f'{API_BASE}/protocols'
    params = {
        'page_size': page_size,
        'page_id': page,
        'order_field': 'activity',
        'order_dir': 'desc',
        'filter': 'public',
        'fields': 'id,title,description,steps,materials,created_on,categories',
    }

    try:
        resp = requests.get(url, params=params, timeout=30)
        if resp.status_code == 200:
            return resp.json()
        elif resp.status_code == 429:
            logger.warning('[PIO] Rate limited, waiting 10s...')
            time.sleep(10)
            return _fetch_page(page, page_size)
        else:
            logger.warning(f'[PIO] API returned {resp.status_code} for page {page}')
            return None
    except Exception as e:
        logger.warning(f'[PIO] Request failed for page {page}: {e}')
        return None


def _parse_protocol(raw: Dict) -> Optional[Dict]:
    """Parse a protocols.io API response into our normalized format."""
    title = raw.get('title', '')
    if not title:
        return None

    # Parse steps
    steps_raw = raw.get('steps', [])
    steps = []
    if isinstance(steps_raw, list):
        for i, step in enumerate(steps_raw, 1):
            if isinstance(step, dict):
                step_text = step.get('description', step.get('text', ''))
            else:
                step_text = str(step)

            # Strip HTML tags
            step_text = re.sub(r'<[^>]+>', '', str(step_text)).strip()
            if not step_text:
                continue

            action_match = re.match(r'^(\w+)', step_text.lower())
            steps.append({
                'order': i,
                'text': step_text[:2000],
                'action_verb': action_match.group(1) if action_match else None,
                'reagents': [],
                'equipment': [],
                'parameters': [],
            })

    # Parse materials
    materials_raw = raw.get('materials', [])
    reagents = []
    equipment = []
    if isinstance(materials_raw, list):
        for mat in materials_raw:
            if isinstance(mat, dict):
                name = mat.get('name', '')
                mat_type = mat.get('type', '').lower()
                if mat_type in ('reagent', 'chemical', 'solution', 'buffer'):
                    reagents.append(name)
                elif mat_type in ('equipment', 'device', 'instrument'):
                    equipment.append(name)
                else:
                    reagents.append(name)  # Default to reagent
            elif isinstance(mat, str):
                reagents.append(mat)

    # Parse categories
    categories = raw.get('categories', [])
    domain = 'biology'
    if isinstance(categories, list) and categories:
        cat = categories[0]
        if isinstance(cat, dict):
            domain = cat.get('name', 'biology').lower()
        elif isinstance(cat, str):
            domain = cat.lower()

    description = raw.get('description', '')
    if isinstance(description, str):
        description = re.sub(r'<[^>]+>', '', description).strip()

    raw_text = f"{title}\n\n{description}\n\n" + "\n".join(
        f"{s['order']}. {s['text']}" for s in steps
    )

    protocol_id = md5(f"pio:{raw.get('id', title)}".encode()).hexdigest()

    return {
        'id': protocol_id,
        'source': 'protocolsio',
        'title': str(title)[:500],
        'domain': domain,
        'steps': steps,
        'reagents': list(set(reagents)),
        'equipment': list(set(equipment)),
        'safety_notes': [],
        'raw_text': raw_text[:50000],
        'metadata': {
            'pio_id': raw.get('id'),
            'num_steps': len(steps),
            'num_materials': len(reagents) + len(equipment),
            'created_on': raw.get('created_on'),
        }
    }


def ingest(max_protocols: int = MAX_PROTOCOLS) -> List[Dict]:
    """Fetch public protocols from protocols.io API and save."""
    if not requests:
        logger.error('[PIO] requests library not installed, skipping protocols.io ingestion')
        return []

    protocols = []
    page = 1
    page_size = 50
    total_fetched = 0

    logger.info(f'[PIO] Starting ingestion (max {max_protocols} protocols)...')

    while total_fetched < max_protocols:
        result = _fetch_page(page, page_size)
        if not result:
            break

        items = result.get('items', result.get('protocols', []))
        if not items:
            break

        for raw in items:
            if not isinstance(raw, dict):
                continue
            protocol = _parse_protocol(raw)
            if protocol:
                protocols.append(protocol)
                total_fetched += 1
                if total_fetched >= max_protocols:
                    break

        pagination = result.get('pagination', {})
        total_pages = pagination.get('total_pages', page)
        if page >= total_pages:
            break

        page += 1
        time.sleep(RATE_LIMIT_SECONDS)

        if page % 10 == 0:
            logger.info(f'[PIO] Fetched {total_fetched} protocols ({page} pages)...')

    logger.info(f'[PIO] Fetched {len(protocols)} protocols total')

    # Save to JSONL
    with open(OUTPUT_FILE, 'w') as f:
        for p in protocols:
            f.write(json.dumps(p) + '\n')

    logger.info(f'[PIO] Saved to {OUTPUT_FILE}')
    return protocols


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    results = ingest(max_protocols=100)  # Small test run
    print(f'\nIngested {len(results)} protocols.io protocols')
    for p in results[:3]:
        print(f'  - {p["title"][:60]} ({p["metadata"]["num_steps"]} steps, domain: {p["domain"]})')
