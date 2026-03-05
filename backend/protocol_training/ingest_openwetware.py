"""
OpenWetWare MediaWiki Ingester
================================
Downloads and parses the OpenWetWare wiki using MediaWiki API.
  https://openwetware.org/wiki/Main_Page

Uses Special:Export or the MediaWiki API to bulk-download pages
in the Protocols namespace and linked sub-pages.

Output: List of normalized protocol dicts.
"""

import os
import re
import json
import logging
import time
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional
from hashlib import md5

try:
    import requests
except ImportError:
    requests = None

try:
    import mwparserfromhell
except ImportError:
    mwparserfromhell = None

from . import CORPUS_DIR

logger = logging.getLogger(__name__)

API_URL = 'https://openwetware.org/mediawiki/api.php'
OUTPUT_FILE = os.path.join(CORPUS_DIR, 'openwetware_protocols.jsonl')

RATE_LIMIT_SECONDS = 0.5
MAX_PAGES = 10000


def _api_request(params: Dict) -> Optional[Dict]:
    """Make a MediaWiki API request."""
    if not requests:
        raise ImportError('requests library required for OpenWetWare ingestion')

    params['format'] = 'json'
    try:
        resp = requests.get(API_URL, params=params, timeout=30)
        if resp.status_code == 200:
            return resp.json()
        else:
            logger.warning(f'[OWW] API returned {resp.status_code}')
            return None
    except Exception as e:
        logger.warning(f'[OWW] Request failed: {e}')
        return None


def _get_protocol_page_titles() -> List[str]:
    """Get titles of pages in the Protocols category and namespace."""
    titles = set()

    # Method 1: Search for pages in Protocol categories
    categories_to_search = [
        'Category:Protocols',
        'Category:Methods',
        'Category:Techniques',
        'Category:Procedures',
    ]

    for category in categories_to_search:
        cont = None
        while True:
            params = {
                'action': 'query',
                'list': 'categorymembers',
                'cmtitle': category,
                'cmlimit': 500,
                'cmtype': 'page|subcat',
            }
            if cont:
                params['cmcontinue'] = cont

            result = _api_request(params)
            if not result:
                break

            members = result.get('query', {}).get('categorymembers', [])
            for member in members:
                titles.add(member['title'])

            cont = result.get('continue', {}).get('cmcontinue')
            if not cont:
                break
            time.sleep(RATE_LIMIT_SECONDS)

    # Method 2: Search for pages with "Protocol" in title
    search_terms = ['protocol', 'method', 'procedure', 'assay']
    for term in search_terms:
        params = {
            'action': 'query',
            'list': 'search',
            'srsearch': term,
            'srlimit': 500,
            'srnamespace': 0,
        }
        result = _api_request(params)
        if result:
            for item in result.get('query', {}).get('search', []):
                titles.add(item['title'])
        time.sleep(RATE_LIMIT_SECONDS)

    # Method 3: Get all pages starting with "Protocols/"
    params = {
        'action': 'query',
        'list': 'allpages',
        'apprefix': 'Protocols/',
        'aplimit': 500,
    }
    result = _api_request(params)
    if result:
        for page in result.get('query', {}).get('allpages', []):
            titles.add(page['title'])

    logger.info(f'[OWW] Found {len(titles)} protocol-related page titles')
    return sorted(list(titles))[:MAX_PAGES]


def _fetch_page_content(titles: List[str]) -> List[Dict]:
    """Fetch page content in batches of 50 (MediaWiki API limit)."""
    pages = []
    batch_size = 50

    for i in range(0, len(titles), batch_size):
        batch = titles[i:i + batch_size]
        params = {
            'action': 'query',
            'titles': '|'.join(batch),
            'prop': 'revisions|categories',
            'rvprop': 'content',
            'rvslots': 'main',
        }

        result = _api_request(params)
        if not result:
            continue

        query_pages = result.get('query', {}).get('pages', {})
        for page_id, page_data in query_pages.items():
            if int(page_id) < 0:  # Missing page
                continue

            revisions = page_data.get('revisions', [])
            if not revisions:
                continue

            slots = revisions[0].get('slots', {})
            content = slots.get('main', {}).get('*', '')
            if not content:
                # Fallback to old API format
                content = revisions[0].get('*', '')

            if content and len(content) > 50:
                pages.append({
                    'title': page_data.get('title', ''),
                    'page_id': page_id,
                    'wikitext': content,
                    'categories': [c.get('title', '') for c in page_data.get('categories', [])],
                })

        if i % 200 == 0 and i > 0:
            logger.info(f'[OWW] Fetched {i}/{len(titles)} pages...')
        time.sleep(RATE_LIMIT_SECONDS)

    return pages


def _parse_wikitext(wikitext: str) -> str:
    """Convert MediaWiki markup to plain text."""
    if mwparserfromhell:
        try:
            parsed = mwparserfromhell.parse(wikitext)
            return parsed.strip_code()
        except Exception:
            pass

    # Fallback: basic regex cleanup
    text = wikitext
    text = re.sub(r'\[\[(?:[^|\]]*\|)?([^\]]+)\]\]', r'\1', text)  # [[Link|Text]] → Text
    text = re.sub(r'\{\{[^}]+\}\}', '', text)  # Remove templates
    text = re.sub(r"'{2,}", '', text)  # Remove bold/italic markup
    text = re.sub(r'<ref[^>]*>.*?</ref>', '', text, flags=re.DOTALL)  # Remove references
    text = re.sub(r'<[^>]+>', '', text)  # Remove HTML tags
    text = re.sub(r'\n{3,}', '\n\n', text)  # Collapse blank lines
    return text.strip()


def _extract_steps_from_text(text: str) -> List[Dict]:
    """Extract protocol steps from plain text."""
    steps = []

    # Try numbered lists first
    numbered = re.findall(r'^\s*(\d+)\.\s+(.+)$', text, re.MULTILINE)
    if numbered:
        for order, step_text in numbered:
            step_text = step_text.strip()
            if len(step_text) > 10:
                action_match = re.match(r'^(\w+)', step_text.lower())
                steps.append({
                    'order': int(order),
                    'text': step_text,
                    'action_verb': action_match.group(1) if action_match else None,
                    'reagents': [],
                    'equipment': [],
                    'parameters': [],
                })
    else:
        # Try bullet points
        bullets = re.findall(r'^\s*[*#]\s+(.+)$', text, re.MULTILINE)
        for i, step_text in enumerate(bullets, 1):
            step_text = step_text.strip()
            if len(step_text) > 10:
                action_match = re.match(r'^(\w+)', step_text.lower())
                steps.append({
                    'order': i,
                    'text': step_text,
                    'action_verb': action_match.group(1) if action_match else None,
                    'reagents': [],
                    'equipment': [],
                    'parameters': [],
                })

    return steps


def _parse_page(page: Dict) -> Optional[Dict]:
    """Parse a wiki page into a normalized protocol."""
    title = page['title']
    wikitext = page['wikitext']

    plain_text = _parse_wikitext(wikitext)
    if len(plain_text) < 100:
        return None

    steps = _extract_steps_from_text(plain_text)

    # Determine domain from categories
    domain = 'biology'
    categories = ' '.join(page.get('categories', [])).lower()
    if 'molecular' in categories or 'cloning' in categories:
        domain = 'molecular_biology'
    elif 'cell' in categories:
        domain = 'cell_biology'
    elif 'protein' in categories:
        domain = 'biochemistry'
    elif 'genetic' in categories or 'dna' in categories or 'rna' in categories:
        domain = 'genetics'
    elif 'micro' in categories:
        domain = 'microbiology'
    elif 'neuro' in categories:
        domain = 'neuroscience'

    protocol_id = md5(f"oww:{title}".encode()).hexdigest()

    return {
        'id': protocol_id,
        'source': 'openwetware',
        'title': title[:500],
        'domain': domain,
        'steps': steps,
        'reagents': [],
        'equipment': [],
        'safety_notes': [],
        'raw_text': plain_text[:50000],
        'metadata': {
            'page_id': page['page_id'],
            'num_steps': len(steps),
            'categories': page.get('categories', []),
            'text_length': len(plain_text),
        }
    }


def ingest(max_pages: int = MAX_PAGES) -> List[Dict]:
    """Fetch protocol pages from OpenWetWare and parse them."""
    if not requests:
        logger.error('[OWW] requests library not installed, skipping OpenWetWare ingestion')
        return []

    # Step 1: Get page titles
    titles = _get_protocol_page_titles()
    titles = titles[:max_pages]
    logger.info(f'[OWW] Will fetch {len(titles)} pages')

    # Step 2: Fetch content
    pages = _fetch_page_content(titles)
    logger.info(f'[OWW] Fetched content for {len(pages)} pages')

    # Step 3: Parse into protocols
    protocols = []
    for page in pages:
        protocol = _parse_page(page)
        if protocol:
            protocols.append(protocol)

    logger.info(f'[OWW] Parsed {len(protocols)} protocols')

    # Save
    with open(OUTPUT_FILE, 'w') as f:
        for p in protocols:
            f.write(json.dumps(p) + '\n')

    logger.info(f'[OWW] Saved to {OUTPUT_FILE}')

    # Summary
    domains = {}
    for p in protocols:
        d = p['domain']
        domains[d] = domains.get(d, 0) + 1
    logger.info(f'[OWW] Domains: {domains}')

    return protocols


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    results = ingest(max_pages=200)  # Small test run
    print(f'\nIngested {len(results)} OpenWetWare protocols')
    for p in results[:5]:
        print(f'  - {p["title"][:60]} ({p["metadata"]["num_steps"]} steps, domain: {p["domain"]})')
