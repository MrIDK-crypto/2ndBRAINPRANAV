"""
Galaxy Training Network (GTN) Ingester
======================================
Extracts step-by-step tutorials from the Galaxy Training Network.

Galaxy Project is an open-source platform for FAIR data analysis.
GTN contains hundreds of structured dry lab protocols.
https://training.galaxyproject.org/

Output: Structured dry lab protocol data
"""

import os
import re
import json
import logging
import requests
import yaml
import time
from typing import List, Dict, Any, Optional, Tuple
from hashlib import md5

from . import CORPUS_DIR

logger = logging.getLogger(__name__)

# GitHub OAuth credentials for higher rate limits
GITHUB_CLIENT_ID = os.environ.get('GITHUB_CLIENT_ID', 'Ov23lihJHi0CxZ2uVM2u')
GITHUB_CLIENT_SECRET = os.environ.get('GITHUB_CLIENT_SECRET', '7d34d60e5e63f329a454f8f309afd009513f4e9e')

# GTN GitHub raw content base
GTN_GITHUB = "https://raw.githubusercontent.com/galaxyproject/training-material/main"
GTN_API = "https://api.github.com/repos/galaxyproject/training-material/contents/topics"

# Topics by domain
DOMAIN_TOPICS = {
    'plant_biology': [
        'transcriptomics', 'sequence-analysis', 'assembly'
    ],
    'oncology': [
        'variant-analysis', 'cancer-informatics', 'single-cell'
    ],
    'neurology': [
        'imaging', 'statistics'
    ],
    'general': [
        'introduction', 'galaxy-interface', 'data-science',
        'proteomics', 'metabolomics', 'epigenetics', 'metagenomics',
        'chip-seq', 'climate', 'computational-chemistry'
    ]
}

OUTPUT_FILE = os.path.join(CORPUS_DIR, 'galaxy_gtn_protocols.jsonl')


def _get_github_contents(path: str, max_retries: int = 10) -> Optional[List[Dict]]:
    """Get contents listing from GitHub API with persistent retries."""
    url = f"https://api.github.com/repos/galaxyproject/training-material/contents/{path}"

    # Add OAuth credentials for higher rate limits (5000/hour)
    params = {}
    if GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET:
        params['client_id'] = GITHUB_CLIENT_ID
        params['client_secret'] = GITHUB_CLIENT_SECRET

    for attempt in range(max_retries):
        try:
            resp = requests.get(url, params=params, timeout=30)

            if resp.status_code == 403:
                # Check rate limit reset time
                reset_time = resp.headers.get('X-RateLimit-Reset')
                remaining = resp.headers.get('X-RateLimit-Remaining', '0')

                if remaining == '0' and reset_time:
                    wait_seconds = max(int(reset_time) - int(time.time()) + 5, 60)
                    wait_seconds = min(wait_seconds, 3600)  # Cap at 1 hour
                    logger.info(f'[GTN] Rate limited. Waiting {wait_seconds}s for reset (attempt {attempt+1}/{max_retries})...')
                    time.sleep(wait_seconds)
                    continue
                else:
                    wait = min(60 * (2 ** attempt), 300)
                    logger.info(f'[GTN] Rate limited. Waiting {wait}s (attempt {attempt+1}/{max_retries})...')
                    time.sleep(wait)
                    continue

            if resp.status_code == 404:
                return None

            resp.raise_for_status()
            return resp.json()

        except requests.exceptions.Timeout:
            logger.warning(f'[GTN] Timeout, retrying in {30 * (attempt + 1)}s...')
            time.sleep(30 * (attempt + 1))
        except Exception as e:
            logger.debug(f'[GTN] Failed: {e}, retrying...')
            time.sleep(10 * (attempt + 1))

    logger.warning(f'[GTN] Failed after {max_retries} attempts: {path}')
    return None


def _get_topic_tutorials(topic: str) -> List[Dict]:
    """Get list of tutorials for a topic."""
    tutorials = []

    # Get topic contents
    contents = _get_github_contents(f"topics/{topic}/tutorials")
    if not contents or not isinstance(contents, list):
        return tutorials

    for item in contents:
        if item.get('type') != 'dir':
            continue

        tutorial_name = item['name']

        # Check for tutorial.md
        tutorial_path = f"topics/{topic}/tutorials/{tutorial_name}/tutorial.md"
        metadata_path = f"topics/{topic}/tutorials/{tutorial_name}/metadata.yaml"

        tutorials.append({
            'topic': topic,
            'name': tutorial_name,
            'tutorial_path': tutorial_path,
            'metadata_path': metadata_path,
            'url': f"https://training.galaxyproject.org/training-material/topics/{topic}/tutorials/{tutorial_name}/tutorial.html"
        })

    return tutorials


def _fetch_raw_file(path: str) -> Optional[str]:
    """Fetch raw file from GTN GitHub."""
    url = f"{GTN_GITHUB}/{path}"
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        logger.debug(f'[GTN] Failed to fetch {path}: {e}')
        return None


def _parse_tutorial_metadata(yaml_content: str) -> Dict:
    """Parse tutorial metadata YAML."""
    try:
        return yaml.safe_load(yaml_content) or {}
    except:
        return {}


def _parse_tutorial_markdown(md: str, tutorial: Dict, metadata: Dict, domain: str) -> Optional[Dict]:
    """Parse GTN tutorial markdown into protocol structure."""
    if len(md) < 500:
        return None

    # Get title from metadata or markdown
    title = metadata.get('title', '')
    if not title:
        title_match = re.search(r'^#\s+(.+)$', md, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else tutorial['name']

    # GTN tutorials use specific formatting
    # > <hands-on-title> Step Title </hands-on-title>
    # or ### Step N: Title

    steps = []

    # Look for hands-on blocks
    hands_on = re.findall(r'>\s*<hands-on-title>\s*(.+?)\s*</hands-on-title>(.*?)(?=>\s*<hands-on-title>|>\s*<question-title>|##|$)',
                          md, re.DOTALL)

    if hands_on:
        for i, (step_title, step_content) in enumerate(hands_on, 1):
            step_text = step_content.strip()
            # Extract numbered steps within hands-on
            numbered = re.findall(r'>\s*(\d+)\.\s+(.+)', step_text)
            if numbered:
                for num, text in numbered:
                    steps.append(_create_step(len(steps) + 1, text.strip()))
            else:
                steps.append(_create_step(i, f"{step_title}: {step_text[:300]}"))

    # Fall back to header-based steps
    if not steps:
        headers = re.findall(r'^###\s+(?:Step\s+)?(\d+)?:?\s*(.+)$', md, re.MULTILINE)
        for i, (num, header_text) in enumerate(headers, 1):
            steps.append(_create_step(int(num) if num else i, header_text.strip()))

    # Fall back to numbered lists
    if not steps:
        numbered = re.findall(r'^\s*(\d+)\.\s+(.+?)(?=\n\s*\d+\.|\n\n|$)', md, re.MULTILINE | re.DOTALL)
        for order, step_text in numbered[:30]:
            step_text = step_text.strip()
            if len(step_text) > 20:
                steps.append(_create_step(int(order), step_text[:500]))

    if not steps:
        return None

    # Extract tools mentioned
    tools = _extract_galaxy_tools(md)

    protocol_id = md5(f"gtn:{tutorial['topic']}:{tutorial['name']}".encode()).hexdigest()

    return {
        'id': protocol_id,
        'source': 'galaxy_gtn',
        'source_id': f"{tutorial['topic']}/{tutorial['name']}",
        'source_url': tutorial['url'],
        'title': f"GTN: {title}"[:500],
        'domain': domain,
        'subdomain': tutorial['topic'],
        'protocol_type': 'dry_lab',
        'steps': steps[:50],
        'reagents': [],
        'equipment': tools[:30],
        'parameters': [],
        'software_dependencies': ['galaxy'] + tools,
        'safety_notes': [],
        'raw_text': md[:50000],
        'metadata': {
            'num_steps': len(steps),
            'topic': tutorial['topic'],
            'tutorial': tutorial['name'],
            'level': metadata.get('level', 'unknown'),
            'time_estimation': metadata.get('time_estimation', 'unknown'),
            'platform': 'galaxy'
        }
    }


def _create_step(order: int, text: str) -> Dict:
    """Create a structured step dict."""
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'\{[^}]+\}', '', text)  # Remove GTN macros

    # Extract action from Galaxy tool format
    tool_match = re.search(r'\*\*([^*]+)\*\*', text)
    action = tool_match.group(1).lower() if tool_match else None

    if not action:
        action_match = re.match(r'^(\w+)', text.lower())
        action = action_match.group(1) if action_match else None

    return {
        'order': order,
        'text': text[:1000],
        'action_verb': action,
        'reagents': [],
        'equipment': _extract_galaxy_tools_from_step(text),
        'parameters': _extract_galaxy_params(text)
    }


def _extract_galaxy_tools(text: str) -> List[str]:
    """Extract Galaxy tool names from tutorial."""
    tools = []
    # Tool macros
    tool_macros = re.findall(r'%\s*tool\s*\[\s*([^\]]+)\s*\]', text)
    tools.extend(tool_macros)
    # Bold tool names
    bold_tools = re.findall(r'\*\*([A-Za-z][A-Za-z0-9_\s]+)\*\*(?:\s+tool)?', text)
    tools.extend([t.strip() for t in bold_tools if len(t.strip()) > 2])
    return list(set(tools))[:30]


def _extract_galaxy_tools_from_step(text: str) -> List[str]:
    """Extract Galaxy tools from a single step."""
    tools = []
    bold_tools = re.findall(r'\*\*([A-Za-z][A-Za-z0-9_\s]+)\*\*', text)
    tools.extend([t.strip().lower() for t in bold_tools if len(t.strip()) > 2])
    return list(set(tools))[:5]


def _extract_galaxy_params(text: str) -> List[str]:
    """Extract parameter values from Galaxy step."""
    params = []
    # Format: param_name: value
    param_matches = re.findall(r'"([^"]+)":\s*`([^`]+)`', text)
    for name, val in param_matches:
        params.append(f"{name}={val}")
    return params[:10]


def ingest(max_per_topic: int = 20) -> Tuple[List[Dict], Dict[str, int]]:
    """
    Ingest tutorials from Galaxy Training Network.

    Args:
        max_per_topic: Maximum tutorials to process per topic

    Returns:
        Tuple of (protocols list, stats dict)
    """
    protocols = []
    stats = {'topics_processed': 0, 'tutorials_found': 0, 'protocols_extracted': 0}
    domain_stats = {}

    for domain, topics in DOMAIN_TOPICS.items():
        logger.info(f'[GTN] Processing domain: {domain}')
        domain_protocols = []

        for topic in topics:
            stats['topics_processed'] += 1

            # Get tutorials for topic
            tutorials = _get_topic_tutorials(topic)
            stats['tutorials_found'] += len(tutorials)
            logger.info(f'[GTN] {topic}: found {len(tutorials)} tutorials')

            for tutorial in tutorials[:max_per_topic]:
                # Fetch metadata
                meta_content = _fetch_raw_file(tutorial['metadata_path'])
                metadata = _parse_tutorial_metadata(meta_content) if meta_content else {}

                # Fetch tutorial markdown
                md_content = _fetch_raw_file(tutorial['tutorial_path'])
                if not md_content:
                    continue

                protocol = _parse_tutorial_markdown(md_content, tutorial, metadata, domain)
                if protocol and protocol.get('steps'):
                    domain_protocols.append(protocol)
                    stats['protocols_extracted'] += 1

        domain_stats[domain] = len(domain_protocols)
        protocols.extend(domain_protocols)
        logger.info(f'[GTN] {domain}: extracted {len(domain_protocols)} protocols')

    # Save to file
    with open(OUTPUT_FILE, 'w') as f:
        for p in protocols:
            f.write(json.dumps(p) + '\n')

    logger.info(f'[GTN] Total: {len(protocols)} protocols saved to {OUTPUT_FILE}')

    return protocols, {'stats': stats, 'by_domain': domain_stats}


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    protocols, stats = ingest(max_per_topic=20)
    print(f'\nIngested {len(protocols)} Galaxy GTN protocols')
    print(f'Stats: {stats}')
