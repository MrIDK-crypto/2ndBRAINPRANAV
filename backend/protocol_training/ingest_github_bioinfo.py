"""
GitHub Bioinformatics Protocols Ingester
=========================================
Scrapes GitHub repositories tagged with bioinformatics, neuroinformatics,
computational-oncology, rnaseq, etc.

Extracts protocols from:
- Markdown files (.md)
- Jupyter Notebooks (.ipynb)
- Workflow files (.nf Nextflow, .smk Snakemake)
- README files with protocol descriptions

Output: Structured dry lab protocol data
"""

import os
import re
import json
import logging
import requests
import base64
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from hashlib import md5

from . import REPOS_DIR, CORPUS_DIR

logger = logging.getLogger(__name__)

# GitHub API
GITHUB_API = "https://api.github.com"
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
# Fall back to OAuth app credentials for higher rate limits
GITHUB_CLIENT_ID = os.environ.get('GITHUB_CLIENT_ID', 'Ov23lihJHi0CxZ2uVM2u')
GITHUB_CLIENT_SECRET = os.environ.get('GITHUB_CLIENT_SECRET', '7d34d60e5e63f329a454f8f309afd009513f4e9e')

# Search topics by domain
DOMAIN_TOPICS = {
    'plant_biology': [
        'plant-biology', 'arabidopsis', 'plant-genomics', 'plant-science',
        'plant-bioinformatics', 'phytopathology', 'plant-phenotyping',
        'crop-genomics', 'plant-transcriptomics'
    ],
    'oncology': [
        'cancer-genomics', 'oncology', 'tumor-analysis', 'cancer-bioinformatics',
        'tcga', 'cancer-research', 'computational-oncology', 'cancer-transcriptomics',
        'mutation-analysis', 'somatic-variants'
    ],
    'neurology': [
        'neuroinformatics', 'neuroscience', 'brain-imaging', 'eeg-analysis',
        'fmri', 'neural-data-analysis', 'connectomics', 'neuroimaging',
        'electrophysiology', 'brain-research'
    ],
    'bioinformatics': [
        'bioinformatics', 'rnaseq', 'ngs', 'genomics', 'pipeline',
        'computational-biology', 'sequencing', 'variant-calling'
    ]
}

OUTPUT_FILE = os.path.join(CORPUS_DIR, 'github_bioinfo_protocols.jsonl')


def _github_request(endpoint: str, params: dict = None, max_retries: int = 10) -> Optional[dict]:
    """Make authenticated GitHub API request with persistent retries."""
    headers = {'Accept': 'application/vnd.github.v3+json'}

    # Use token if available, otherwise use OAuth app credentials for higher rate limits
    if GITHUB_TOKEN:
        headers['Authorization'] = f'token {GITHUB_TOKEN}'

    # Add OAuth app credentials as query params for higher rate limits (5000/hour vs 60/hour)
    if params is None:
        params = {}
    if GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET and not GITHUB_TOKEN:
        params['client_id'] = GITHUB_CLIENT_ID
        params['client_secret'] = GITHUB_CLIENT_SECRET

    for attempt in range(max_retries):
        try:
            resp = requests.get(
                f"{GITHUB_API}{endpoint}",
                headers=headers,
                params=params,
                timeout=30
            )

            if resp.status_code == 403:
                # Check rate limit reset time
                reset_time = resp.headers.get('X-RateLimit-Reset')
                remaining = resp.headers.get('X-RateLimit-Remaining', '0')

                if remaining == '0' and reset_time:
                    wait_seconds = max(int(reset_time) - int(time.time()) + 5, 60)
                    wait_seconds = min(wait_seconds, 3600)  # Cap at 1 hour
                    logger.info(f'[GitHub] Rate limited. Waiting {wait_seconds}s for reset (attempt {attempt+1}/{max_retries})...')
                    time.sleep(wait_seconds)
                    continue
                else:
                    # Short wait and retry
                    wait = min(60 * (2 ** attempt), 300)  # Exponential backoff, max 5 min
                    logger.info(f'[GitHub] Rate limited. Waiting {wait}s (attempt {attempt+1}/{max_retries})...')
                    time.sleep(wait)
                    continue

            if resp.status_code == 404:
                return None

            resp.raise_for_status()
            return resp.json()

        except requests.exceptions.Timeout:
            logger.warning(f'[GitHub] Timeout, retrying in {30 * (attempt + 1)}s...')
            time.sleep(30 * (attempt + 1))
        except Exception as e:
            logger.debug(f'[GitHub] Request failed: {e}, retrying...')
            time.sleep(10 * (attempt + 1))

    logger.warning(f'[GitHub] Failed after {max_retries} attempts: {endpoint}')
    return None


def _search_repos(topic: str, domain: str, max_repos: int = 50) -> List[Dict]:
    """Search GitHub repos by topic."""
    repos = []

    # Search query
    query = f'topic:{topic} in:topics stars:>5'

    params = {
        'q': query,
        'sort': 'stars',
        'order': 'desc',
        'per_page': min(max_repos, 100)
    }

    data = _github_request('/search/repositories', params)
    if not data:
        return repos

    for item in data.get('items', [])[:max_repos]:
        repos.append({
            'full_name': item['full_name'],
            'name': item['name'],
            'description': item.get('description', ''),
            'url': item['html_url'],
            'stars': item['stargazers_count'],
            'domain': domain,
            'topic': topic
        })

    logger.info(f'[GitHub] Found {len(repos)} repos for topic: {topic}')
    return repos


def _get_repo_contents(repo_full_name: str, path: str = '') -> List[Dict]:
    """Get repository contents listing."""
    endpoint = f'/repos/{repo_full_name}/contents/{path}'
    data = _github_request(endpoint)

    if isinstance(data, list):
        return data
    return []


def _get_file_content(repo_full_name: str, path: str) -> Optional[str]:
    """Get file content from GitHub."""
    endpoint = f'/repos/{repo_full_name}/contents/{path}'
    data = _github_request(endpoint)

    if not data or 'content' not in data:
        return None

    try:
        content = base64.b64decode(data['content']).decode('utf-8', errors='replace')
        return content
    except Exception:
        return None


def _find_protocol_files(repo_full_name: str, depth: int = 0, max_depth: int = 2) -> List[Dict]:
    """Recursively find protocol-related files in a repo."""
    protocol_files = []

    if depth > max_depth:
        return protocol_files

    contents = _get_repo_contents(repo_full_name)
    time.sleep(0.2)  # Rate limiting

    for item in contents:
        name = item.get('name', '').lower()
        item_type = item.get('type', '')
        path = item.get('path', '')

        # Check for protocol-related files
        if item_type == 'file':
            is_protocol_file = False

            # Markdown files
            if name.endswith('.md'):
                if any(kw in name for kw in ['protocol', 'method', 'pipeline', 'workflow',
                                               'tutorial', 'guide', 'readme', 'procedure',
                                               'analysis', 'sop', 'instruction']):
                    is_protocol_file = True
                elif name == 'readme.md':
                    is_protocol_file = True

            # Jupyter notebooks
            elif name.endswith('.ipynb'):
                if any(kw in name for kw in ['analysis', 'pipeline', 'workflow', 'tutorial',
                                               'protocol', 'processing', 'method']):
                    is_protocol_file = True

            # Workflow files
            elif name.endswith('.nf') or name.endswith('.smk'):
                is_protocol_file = True

            # Config files with protocol info
            elif name in ['nextflow.config', 'snakefile', 'workflow.yaml', 'pipeline.yaml']:
                is_protocol_file = True

            if is_protocol_file:
                protocol_files.append({
                    'path': path,
                    'name': name,
                    'type': _get_file_type(name)
                })

        # Recurse into relevant directories
        elif item_type == 'dir':
            if any(kw in name for kw in ['docs', 'protocol', 'workflow', 'pipeline',
                                          'analysis', 'tutorial', 'method', 'notebook']):
                sub_files = _find_protocol_files(repo_full_name, depth + 1, max_depth)
                protocol_files.extend(sub_files)

    return protocol_files


def _get_file_type(filename: str) -> str:
    """Determine file type."""
    if filename.endswith('.md'):
        return 'markdown'
    elif filename.endswith('.ipynb'):
        return 'notebook'
    elif filename.endswith('.nf'):
        return 'nextflow'
    elif filename.endswith('.smk') or 'snakefile' in filename.lower():
        return 'snakemake'
    elif filename.endswith('.yaml') or filename.endswith('.yml'):
        return 'yaml'
    return 'other'


def _parse_markdown_protocol(content: str, repo_info: Dict) -> Optional[Dict]:
    """Parse markdown file into protocol structure."""
    if len(content) < 100:
        return None

    # Extract title from first heading
    title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else repo_info['name']

    # Extract steps from numbered lists or headers
    steps = []

    # Try numbered lists
    numbered = re.findall(r'^\s*(\d+)[\.\)]\s+(.+?)(?=\n\s*\d+[\.\)]|\n\n|$)', content, re.MULTILINE | re.DOTALL)
    if numbered:
        for order, step_text in numbered:
            step_text = step_text.strip()
            if len(step_text) > 20:
                steps.append(_create_step(int(order), step_text[:1000]))

    # Try extracting from headers
    if not steps:
        headers = re.findall(r'^##\s+(?:Step\s*)?(\d+)?[:\.\s]*(.+?)$', content, re.MULTILINE)
        for i, (num, header_text) in enumerate(headers, 1):
            order = int(num) if num else i
            steps.append(_create_step(order, header_text.strip()))

    # Fall back to action verb sentences
    if not steps:
        action_verbs = r'\b(Run|Execute|Install|Configure|Download|Process|Analyze|Filter|Map|Align|Call|Annotate|Visualize|Export|Import|Load|Save|Generate|Create|Build|Compile|Test|Validate|Check|Verify)\b'
        sentences = re.split(r'(?<=[.!?])\s+', content)
        order = 1
        for sent in sentences:
            if re.match(action_verbs, sent.strip(), re.IGNORECASE):
                if 30 < len(sent.strip()) < 500:
                    steps.append(_create_step(order, sent.strip()))
                    order += 1
                    if order > 30:
                        break

    if not steps:
        return None

    # Collect all extracted entities
    all_reagents = []
    all_equipment = []
    all_params = []
    for step in steps:
        all_reagents.extend(step.get('reagents', []))
        all_equipment.extend(step.get('equipment', []))
        all_params.extend(step.get('parameters', []))

    protocol_id = md5(f"github:{repo_info['full_name']}:{title[:100]}".encode()).hexdigest()

    return {
        'id': protocol_id,
        'source': 'github_bioinfo',
        'source_id': repo_info['full_name'],
        'source_url': repo_info['url'],
        'title': title[:500],
        'domain': repo_info['domain'],
        'subdomain': 'computational',
        'protocol_type': 'dry_lab',
        'steps': steps,
        'reagents': list(set(all_reagents))[:30],
        'equipment': list(set(all_equipment))[:30],
        'parameters': list(set(all_params))[:30],
        'software_dependencies': _extract_software_deps(content),
        'safety_notes': [],
        'raw_text': content[:50000],
        'metadata': {
            'num_steps': len(steps),
            'file_type': 'markdown',
            'stars': repo_info.get('stars', 0),
            'topic': repo_info.get('topic', '')
        }
    }


def _parse_notebook_protocol(content: str, repo_info: Dict) -> Optional[Dict]:
    """Parse Jupyter notebook into protocol structure."""
    try:
        notebook = json.loads(content)
    except json.JSONDecodeError:
        return None

    cells = notebook.get('cells', [])
    if not cells:
        return None

    # Extract title from first markdown cell
    title = repo_info['name']
    for cell in cells:
        if cell.get('cell_type') == 'markdown':
            source = ''.join(cell.get('source', []))
            title_match = re.search(r'^#\s+(.+)$', source, re.MULTILINE)
            if title_match:
                title = title_match.group(1).strip()
                break

    # Extract steps from code cells with comments
    steps = []
    full_text = []

    for i, cell in enumerate(cells, 1):
        cell_type = cell.get('cell_type', '')
        source = ''.join(cell.get('source', []))

        if cell_type == 'code':
            # Use first comment or whole code as step
            comment_match = re.search(r'^#\s*(.+)$', source, re.MULTILINE)
            step_text = comment_match.group(1) if comment_match else source[:200]
            if len(step_text.strip()) > 10:
                steps.append(_create_step(len(steps) + 1, step_text.strip()))
                full_text.append(source)

        elif cell_type == 'markdown':
            full_text.append(source)

    if not steps:
        return None

    combined_text = '\n\n'.join(full_text)

    protocol_id = md5(f"github:{repo_info['full_name']}:nb:{title[:100]}".encode()).hexdigest()

    return {
        'id': protocol_id,
        'source': 'github_bioinfo',
        'source_id': repo_info['full_name'],
        'source_url': repo_info['url'],
        'title': title[:500],
        'domain': repo_info['domain'],
        'subdomain': 'computational',
        'protocol_type': 'dry_lab',
        'steps': steps[:50],
        'reagents': [],
        'equipment': [],
        'parameters': [],
        'software_dependencies': _extract_software_deps(combined_text),
        'safety_notes': [],
        'raw_text': combined_text[:50000],
        'metadata': {
            'num_steps': len(steps),
            'file_type': 'notebook',
            'num_cells': len(cells),
            'stars': repo_info.get('stars', 0)
        }
    }


def _parse_workflow_file(content: str, repo_info: Dict, file_type: str) -> Optional[Dict]:
    """Parse Nextflow/Snakemake workflow into protocol structure."""
    if len(content) < 100:
        return None

    steps = []

    if file_type == 'nextflow':
        # Extract process blocks
        processes = re.findall(r'process\s+(\w+)\s*\{([^}]+)\}', content, re.DOTALL)
        for i, (name, body) in enumerate(processes, 1):
            # Extract script section
            script_match = re.search(r'script:\s*["\'\n](.+?)["\']?\s*(?:}|$)', body, re.DOTALL)
            script = script_match.group(1) if script_match else body[:500]
            steps.append(_create_step(i, f"{name}: {script[:300]}"))

    elif file_type == 'snakemake':
        # Extract rule blocks
        rules = re.findall(r'rule\s+(\w+)\s*:\s*(.+?)(?=rule\s+\w+|$)', content, re.DOTALL)
        for i, (name, body) in enumerate(rules, 1):
            shell_match = re.search(r'shell:\s*["\'\n](.+?)["\']', body, re.DOTALL)
            shell = shell_match.group(1) if shell_match else body[:300]
            steps.append(_create_step(i, f"{name}: {shell[:300]}"))

    if not steps:
        return None

    title = f"{repo_info['name']} - {file_type.title()} Pipeline"
    protocol_id = md5(f"github:{repo_info['full_name']}:wf:{title[:100]}".encode()).hexdigest()

    return {
        'id': protocol_id,
        'source': 'github_bioinfo',
        'source_id': repo_info['full_name'],
        'source_url': repo_info['url'],
        'title': title[:500],
        'domain': repo_info['domain'],
        'subdomain': 'computational',
        'protocol_type': 'dry_lab',
        'steps': steps[:30],
        'reagents': [],
        'equipment': [],
        'parameters': _extract_workflow_params(content),
        'software_dependencies': _extract_software_deps(content),
        'safety_notes': [],
        'raw_text': content[:50000],
        'metadata': {
            'num_steps': len(steps),
            'file_type': file_type,
            'stars': repo_info.get('stars', 0)
        }
    }


def _create_step(order: int, text: str) -> Dict:
    """Create a structured step dict."""
    text = re.sub(r'\s+', ' ', text).strip()
    action_match = re.match(r'^(\w+)', text.lower())

    return {
        'order': order,
        'text': text[:1000],
        'action_verb': action_match.group(1) if action_match else None,
        'reagents': [],
        'equipment': _extract_software_tools(text),
        'parameters': _extract_parameters(text)
    }


def _extract_software_deps(text: str) -> List[str]:
    """Extract software dependencies."""
    deps = []
    patterns = [
        r'(?:pip install|conda install|apt install|brew install)\s+([a-zA-Z0-9\-_]+)',
        r'(?:import|from)\s+([a-zA-Z][a-zA-Z0-9_]+)',
        r'library\(([a-zA-Z][a-zA-Z0-9\.]+)\)',
        r'\b(samtools|bwa|bowtie|hisat|star|gatk|picard|bcftools|vcftools|bedtools|'
        r'fastqc|multiqc|trimmomatic|cutadapt|salmon|kallisto|rsem|deseq2|edger|'
        r'sleuth|stringtie|cufflinks|tophat|snpeff|annovar|vep|macs2|homer|'
        r'seurat|scanpy|cellranger|velocyto)\b'
    ]
    for pat in patterns:
        matches = re.findall(pat, text, re.IGNORECASE)
        deps.extend([m.lower() for m in matches])
    return list(set(deps))[:30]


def _extract_software_tools(text: str) -> List[str]:
    """Extract software tools mentioned."""
    tools = []
    patterns = [
        r'\b(samtools|bwa|bowtie|STAR|GATK|picard|bcftools|bedtools|FastQC|'
        r'trimmomatic|cutadapt|salmon|kallisto|RSEM|HTSeq|featureCounts|'
        r'DESeq2|edgeR|limma|Seurat|scanpy|MACS2|HOMER|ChIPseeker)\b'
    ]
    for pat in patterns:
        matches = re.findall(pat, text, re.IGNORECASE)
        tools.extend([m.lower() for m in matches])
    return list(set(tools))[:15]


def _extract_workflow_params(text: str) -> List[str]:
    """Extract workflow parameters."""
    params = []
    # Common parameter patterns in workflows
    param_patterns = [
        r'--(\w+)\s+(\d+)',
        r'-(\w)\s+(\d+)',
        r'params\.(\w+)\s*=\s*(\d+)',
        r'config\[[\'"]([\w]+)[\'"]\]'
    ]
    for pat in param_patterns:
        matches = re.findall(pat, text)
        for m in matches:
            if isinstance(m, tuple):
                params.append(f"{m[0]}={m[1]}" if len(m) > 1 else m[0])
            else:
                params.append(m)
    return params[:20]


def _extract_parameters(text: str) -> List[str]:
    """Extract numerical parameters."""
    params = re.findall(
        r'(\d+(?:\.\d+)?)\s*(threads?|cores?|gb|mb|kb|bp|reads?|samples?|%)',
        text, re.IGNORECASE
    )
    return [f"{val} {unit}" for val, unit in params][:15]


def ingest(max_per_topic: int = 20) -> Tuple[List[Dict], Dict[str, int]]:
    """
    Ingest protocols from GitHub bioinformatics repositories.

    Args:
        max_per_topic: Maximum repos to process per topic

    Returns:
        Tuple of (protocols list, stats dict)
    """
    protocols = []
    stats = {'repos_searched': 0, 'files_found': 0, 'protocols_extracted': 0}
    domain_stats = {}

    for domain, topics in DOMAIN_TOPICS.items():
        logger.info(f'[GitHub] Processing domain: {domain}')
        domain_protocols = []

        for topic in topics:
            repos = _search_repos(topic, domain, max_repos=max_per_topic)
            stats['repos_searched'] += len(repos)
            time.sleep(1)  # Rate limiting

            for repo_info in repos:
                # Find protocol files
                try:
                    protocol_files = _find_protocol_files(repo_info['full_name'])
                except Exception as e:
                    logger.debug(f"[GitHub] Error scanning {repo_info['full_name']}: {e}")
                    continue

                stats['files_found'] += len(protocol_files)

                # Process each file
                for pf in protocol_files[:5]:  # Limit files per repo
                    time.sleep(0.3)
                    content = _get_file_content(repo_info['full_name'], pf['path'])
                    if not content:
                        continue

                    protocol = None
                    if pf['type'] == 'markdown':
                        protocol = _parse_markdown_protocol(content, repo_info)
                    elif pf['type'] == 'notebook':
                        protocol = _parse_notebook_protocol(content, repo_info)
                    elif pf['type'] in ('nextflow', 'snakemake'):
                        protocol = _parse_workflow_file(content, repo_info, pf['type'])

                    if protocol and protocol.get('steps'):
                        domain_protocols.append(protocol)
                        stats['protocols_extracted'] += 1

        domain_stats[domain] = len(domain_protocols)
        protocols.extend(domain_protocols)
        logger.info(f'[GitHub] {domain}: extracted {len(domain_protocols)} protocols')

    # Save to file
    with open(OUTPUT_FILE, 'w') as f:
        for p in protocols:
            f.write(json.dumps(p) + '\n')

    logger.info(f'[GitHub] Total: {len(protocols)} protocols saved to {OUTPUT_FILE}')

    return protocols, {'stats': stats, 'by_domain': domain_stats}


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    protocols, stats = ingest(max_per_topic=20)
    print(f'\nIngested {len(protocols)} GitHub bioinformatics protocols')
    print(f'Stats: {stats}')
