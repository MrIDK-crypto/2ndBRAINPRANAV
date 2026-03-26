"""
Bioconductor Vignettes Ingester
===============================
Extracts protocols from Bioconductor R package vignettes.

Bioconductor is the standard for:
- Oncology sequencing analysis (DESeq2, edgeR, etc.)
- Plant biology RNA-seq (tximport, etc.)
- Single-cell analysis (Seurat, SingleCellExperiment)

Vignettes are structured tutorials with step-by-step workflows.

Output: Structured dry lab protocol data
"""

import os
import re
import json
import logging
import requests
from typing import List, Dict, Any, Optional, Tuple
from hashlib import md5

from . import CORPUS_DIR

logger = logging.getLogger(__name__)

# Bioconductor package categories by domain
DOMAIN_PACKAGES = {
    'oncology': [
        'TCGAbiolinks', 'DESeq2', 'edgeR', 'limma', 'maftools', 'RTCGA',
        'GenomicDataCommons', 'curatedTCGAData', 'RTCGAToolbox', 'cBioPortalData',
        'oncoscanR', 'CNVtools', 'CopyNumberPlots', 'sequenza', 'ABSOLUTE',
        'varscan2', 'mutSignatures', 'deconstructSigs', 'SigMA'
    ],
    'plant_biology': [
        'tximport', 'clusterProfiler', 'topGO', 'GOstats', 'KEGGREST',
        'biomaRt', 'AnnotationHub', 'GenomicFeatures', 'BSgenome',
        'Rsubread', 'Rhisat2', 'RBowtie2', 'systemPipeR', 'systemPipeRdata'
    ],
    'neurology': [
        'fmri', 'neuRosim', 'brainR', 'BrainStars', 'RBGL',
        'EBImage', 'flowCore', 'cytofast', 'CATALYST'
    ],
    'general': [
        'Biostrings', 'GenomicRanges', 'SummarizedExperiment', 'SingleCellExperiment',
        'Seurat', 'scran', 'scater', 'Rsamtools', 'rtracklayer',
        'VariantAnnotation', 'ensembldb', 'org.Hs.eg.db'
    ]
}

BIOC_BASE = "https://bioconductor.org"
OUTPUT_FILE = os.path.join(CORPUS_DIR, 'bioconductor_protocols.jsonl')


def _get_package_vignettes(package_name: str) -> List[Dict]:
    """Get list of vignettes for a Bioconductor package."""
    vignettes = []

    # Try release and devel versions
    for version in ['release', 'devel']:
        url = f"{BIOC_BASE}/packages/{version}/bioc/vignettes/{package_name}/inst/doc/"

        try:
            resp = requests.get(url, timeout=15)
            if resp.status_code != 200:
                continue

            # Parse HTML for vignette links
            html = resp.text
            # Find .html and .pdf vignette files
            links = re.findall(rf'href=["\']([^"\']+\.(?:html|Rmd))["\']', html)

            for link in links:
                if not link.startswith('http'):
                    vignette_url = f"{url}{link}"
                else:
                    vignette_url = link

                vignettes.append({
                    'name': link,
                    'url': vignette_url,
                    'package': package_name,
                    'version': version
                })

            if vignettes:
                break  # Got vignettes from release, don't need devel

        except Exception as e:
            logger.debug(f'[Bioc] Failed to get vignettes for {package_name}: {e}')

    return vignettes


def _fetch_vignette_content(vignette: Dict) -> Optional[str]:
    """Fetch vignette content."""
    try:
        resp = requests.get(vignette['url'], timeout=30)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        logger.debug(f'[Bioc] Failed to fetch {vignette["url"]}: {e}')
        return None


def _parse_html_vignette(html: str, vignette: Dict, domain: str) -> Optional[Dict]:
    """Parse HTML vignette into protocol structure."""
    if len(html) < 500:
        return None

    # Extract title
    title_match = re.search(r'<title>([^<]+)</title>', html, re.IGNORECASE)
    title = title_match.group(1).strip() if title_match else vignette['package']

    # Remove HTML tags for text processing
    text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text)

    # Extract code blocks (these are the actual steps)
    code_blocks = re.findall(r'<pre[^>]*><code[^>]*>([^<]+)</code></pre>', html, re.DOTALL)
    if not code_blocks:
        code_blocks = re.findall(r'<pre[^>]*>([^<]+)</pre>', html, re.DOTALL)

    steps = []
    for i, code in enumerate(code_blocks, 1):
        code = code.strip()
        if len(code) > 20 and not code.startswith('#'):
            # Get first comment or first line as description
            lines = code.split('\n')
            description = ''
            for line in lines:
                if line.strip().startswith('#'):
                    description = line.strip().lstrip('#').strip()
                    break
                elif line.strip():
                    description = line.strip()[:100]
                    break

            steps.append({
                'order': i,
                'text': description or code[:200],
                'action_verb': _extract_r_function(code),
                'code': code[:500],
                'reagents': [],
                'equipment': _extract_r_packages(code),
                'parameters': _extract_r_params(code)
            })

    if not steps:
        return None

    protocol_id = md5(f"bioc:{vignette['package']}:{vignette['name']}".encode()).hexdigest()

    return {
        'id': protocol_id,
        'source': 'bioconductor',
        'source_id': vignette['package'],
        'source_url': vignette['url'],
        'title': f"{vignette['package']}: {title}"[:500],
        'domain': domain,
        'subdomain': 'bioinformatics',
        'protocol_type': 'dry_lab',
        'steps': steps[:50],
        'reagents': [],
        'equipment': list(set(pkg for s in steps for pkg in s.get('equipment', [])))[:30],
        'parameters': list(set(p for s in steps for p in s.get('parameters', [])))[:30],
        'software_dependencies': [vignette['package']] + _extract_dependencies(text),
        'safety_notes': [],
        'raw_text': text[:50000],
        'metadata': {
            'num_steps': len(steps),
            'package': vignette['package'],
            'bioc_version': vignette['version'],
            'language': 'R'
        }
    }


def _parse_rmd_vignette(rmd: str, vignette: Dict, domain: str) -> Optional[Dict]:
    """Parse Rmd vignette into protocol structure."""
    if len(rmd) < 500:
        return None

    # Extract title from YAML header
    yaml_match = re.search(r'^---\s*\n(.*?)\n---', rmd, re.DOTALL)
    title = vignette['package']
    if yaml_match:
        yaml_content = yaml_match.group(1)
        title_match = re.search(r'title:\s*["\']?([^"\'\n]+)', yaml_content)
        if title_match:
            title = title_match.group(1).strip()

    # Extract R code chunks
    code_chunks = re.findall(r'```\{r[^}]*\}(.*?)```', rmd, re.DOTALL)

    steps = []
    for i, code in enumerate(code_chunks, 1):
        code = code.strip()
        if len(code) > 20:
            # Get description from preceding markdown
            description = code.split('\n')[0][:100]

            steps.append({
                'order': i,
                'text': description,
                'action_verb': _extract_r_function(code),
                'code': code[:500],
                'reagents': [],
                'equipment': _extract_r_packages(code),
                'parameters': _extract_r_params(code)
            })

    if not steps:
        return None

    protocol_id = md5(f"bioc:{vignette['package']}:rmd:{vignette['name']}".encode()).hexdigest()

    return {
        'id': protocol_id,
        'source': 'bioconductor',
        'source_id': vignette['package'],
        'source_url': vignette['url'],
        'title': f"{vignette['package']}: {title}"[:500],
        'domain': domain,
        'subdomain': 'bioinformatics',
        'protocol_type': 'dry_lab',
        'steps': steps[:50],
        'reagents': [],
        'equipment': list(set(pkg for s in steps for pkg in s.get('equipment', [])))[:30],
        'parameters': list(set(p for s in steps for p in s.get('parameters', [])))[:30],
        'software_dependencies': [vignette['package']] + _extract_dependencies(rmd),
        'safety_notes': [],
        'raw_text': rmd[:50000],
        'metadata': {
            'num_steps': len(steps),
            'package': vignette['package'],
            'bioc_version': vignette['version'],
            'language': 'R'
        }
    }


def _extract_r_function(code: str) -> Optional[str]:
    """Extract main R function from code."""
    # Find first function call
    func_match = re.search(r'\b([a-zA-Z_][a-zA-Z0-9_.]*)\s*\(', code)
    if func_match:
        return func_match.group(1).lower()
    return None


def _extract_r_packages(code: str) -> List[str]:
    """Extract R packages used in code."""
    packages = []
    # library() and require() calls
    pkg_calls = re.findall(r'(?:library|require)\s*\(\s*["\']?([a-zA-Z][a-zA-Z0-9.]+)["\']?\s*\)', code)
    packages.extend(pkg_calls)
    # Package::function calls
    ns_calls = re.findall(r'([a-zA-Z][a-zA-Z0-9.]+)::', code)
    packages.extend(ns_calls)
    return list(set(packages))[:15]


def _extract_r_params(code: str) -> List[str]:
    """Extract parameter values from R code."""
    params = []
    # Named arguments with numeric values
    named_params = re.findall(r'(\w+)\s*=\s*(\d+(?:\.\d+)?)', code)
    for name, val in named_params:
        params.append(f"{name}={val}")
    return params[:15]


def _extract_dependencies(text: str) -> List[str]:
    """Extract software dependencies mentioned."""
    deps = []
    # BiocManager packages
    bioc_deps = re.findall(r'BiocManager::install\s*\(\s*["\']([^"\']+)["\']', text)
    deps.extend(bioc_deps)
    # CRAN packages
    cran_deps = re.findall(r'install\.packages\s*\(\s*["\']([^"\']+)["\']', text)
    deps.extend(cran_deps)
    return list(set(deps))[:20]


def ingest(max_per_domain: int = 30) -> Tuple[List[Dict], Dict[str, int]]:
    """
    Ingest protocols from Bioconductor vignettes.

    Args:
        max_per_domain: Maximum packages to process per domain

    Returns:
        Tuple of (protocols list, stats dict)
    """
    protocols = []
    stats = {'packages_processed': 0, 'vignettes_found': 0, 'protocols_extracted': 0}
    domain_stats = {}

    for domain, packages in DOMAIN_PACKAGES.items():
        logger.info(f'[Bioc] Processing domain: {domain}')
        domain_protocols = []

        for package in packages[:max_per_domain]:
            stats['packages_processed'] += 1

            # Get vignettes for package
            vignettes = _get_package_vignettes(package)
            stats['vignettes_found'] += len(vignettes)

            for vignette in vignettes[:3]:  # Max 3 vignettes per package
                content = _fetch_vignette_content(vignette)
                if not content:
                    continue

                protocol = None
                if vignette['name'].endswith('.html'):
                    protocol = _parse_html_vignette(content, vignette, domain)
                elif vignette['name'].endswith('.Rmd'):
                    protocol = _parse_rmd_vignette(content, vignette, domain)

                if protocol and protocol.get('steps'):
                    domain_protocols.append(protocol)
                    stats['protocols_extracted'] += 1

        domain_stats[domain] = len(domain_protocols)
        protocols.extend(domain_protocols)
        logger.info(f'[Bioc] {domain}: extracted {len(domain_protocols)} protocols')

    # Save to file
    with open(OUTPUT_FILE, 'w') as f:
        for p in protocols:
            f.write(json.dumps(p) + '\n')

    logger.info(f'[Bioc] Total: {len(protocols)} protocols saved to {OUTPUT_FILE}')

    return protocols, {'stats': stats, 'by_domain': domain_stats}


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    protocols, stats = ingest(max_per_domain=30)
    print(f'\nIngested {len(protocols)} Bioconductor protocols')
    print(f'Stats: {stats}')
