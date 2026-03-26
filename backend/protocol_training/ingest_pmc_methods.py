"""
PMC Open Access Methods Section Ingester
=========================================
Downloads and extracts methods sections from PMC Open Access papers
filtered by domain: plant biology, oncology, neurology.

Uses the PMC OAI-PMH service and FTP bulk downloads.
https://pmc.ncbi.nlm.nih.gov/tools/openftlist/

Output: Structured protocol data with domain tags
"""

import os
import re
import json
import logging
import requests
import gzip
import tarfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from hashlib import md5
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

from . import REPOS_DIR, CORPUS_DIR

logger = logging.getLogger(__name__)

# PMC OAI-PMH endpoint
PMC_OAI_BASE = "https://www.ncbi.nlm.nih.gov/pmc/oai/oai.cgi"
PMC_FTP_BASE = "https://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_bulk/"

# Search terms for each domain
DOMAIN_QUERIES = {
    'plant_biology': [
        'Arabidopsis', 'plant transformation', 'chloroplast', 'photosynthesis',
        'plant cell culture', 'plant DNA extraction', 'plant RNA extraction',
        'protoplast', 'plant tissue culture', 'seed germination', 'plant phenotyping',
        'phytohormone', 'plant pathogen', 'root development', 'leaf senescence',
        'stomata', 'xylem', 'phloem', 'meristem', 'plant breeding'
    ],
    'oncology': [
        'tumor', 'cancer cell line', 'chemotherapy', 'immunotherapy',
        'tumor microenvironment', 'metastasis', 'oncogene', 'tumor suppressor',
        'cancer genomics', 'TCGA', 'cancer proteomics', 'cancer immunology',
        'xenograft', 'organoid cancer', 'liquid biopsy', 'circulating tumor',
        'cancer stem cell', 'apoptosis cancer', 'angiogenesis tumor'
    ],
    'neurology': [
        'neuroimaging', 'electrophysiology', 'patch clamp', 'neuron culture',
        'brain slice', 'optogenetics', 'calcium imaging', 'EEG', 'fMRI',
        'neural network', 'synaptic plasticity', 'action potential',
        'neurotransmitter', 'axon', 'dendrite', 'microglia', 'astrocyte',
        'blood brain barrier', 'neurodegeneration', 'Alzheimer', 'Parkinson'
    ]
}

OUTPUT_FILE = os.path.join(CORPUS_DIR, 'pmc_methods_protocols.jsonl')
CACHE_DIR = os.path.join(REPOS_DIR, 'pmc_cache')


def _search_pmc_esearch(query: str, domain: str, max_results: int = 500) -> List[str]:
    """Search PMC using NCBI E-utilities to get PMCIDs."""
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"

    # Add open access filter
    full_query = f'({query}) AND "open access"[filter]'

    params = {
        'db': 'pmc',
        'term': full_query,
        'retmax': max_results,
        'retmode': 'json',
        'usehistory': 'y'
    }

    try:
        resp = requests.get(base_url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        id_list = data.get('esearchresult', {}).get('idlist', [])
        logger.info(f'[PMC] Found {len(id_list)} papers for query: {query[:50]}...')
        return id_list
    except Exception as e:
        logger.warning(f'[PMC] Search failed for {query}: {e}')
        return []


def _fetch_pmc_article(pmcid: str) -> Optional[str]:
    """Fetch full XML for a PMC article."""
    url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    params = {
        'db': 'pmc',
        'id': pmcid,
        'rettype': 'xml'
    }

    try:
        resp = requests.get(url, params=params, timeout=60)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        logger.debug(f'[PMC] Failed to fetch {pmcid}: {e}')
        return None


def _extract_methods_from_xml(xml_content: str, domain: str) -> Optional[Dict]:
    """Extract methods section from PMC XML."""
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError:
        return None

    # Find article metadata
    title = ''
    abstract = ''
    methods_text = ''

    # Get title
    title_elem = root.find('.//article-title')
    if title_elem is not None:
        title = ''.join(title_elem.itertext()).strip()

    # Get abstract
    abstract_elem = root.find('.//abstract')
    if abstract_elem is not None:
        abstract = ''.join(abstract_elem.itertext()).strip()

    # Find methods section (various naming conventions)
    methods_sections = []
    for sec in root.findall('.//sec'):
        sec_type = sec.get('sec-type', '').lower()
        title_elem = sec.find('title')
        sec_title = ''
        if title_elem is not None:
            sec_title = ''.join(title_elem.itertext()).lower()

        # Check if this is a methods section
        if any(kw in sec_type or kw in sec_title for kw in
               ['method', 'material', 'procedure', 'protocol', 'experimental']):
            sec_text = ''.join(sec.itertext())
            methods_sections.append(sec_text)

    methods_text = '\n\n'.join(methods_sections)

    if len(methods_text) < 200:  # Too short to be useful
        return None

    # Extract structured steps from methods
    steps = _parse_methods_to_steps(methods_text)

    # Get PMCID
    pmcid = ''
    for article_id in root.findall('.//article-id'):
        if article_id.get('pub-id-type') == 'pmc':
            pmcid = article_id.text
            break

    # Extract reagents and equipment
    all_reagents = []
    all_equipment = []
    all_params = []

    for step in steps:
        all_reagents.extend(step.get('reagents', []))
        all_equipment.extend(step.get('equipment', []))
        all_params.extend(step.get('parameters', []))

    protocol_id = md5(f'pmc:{pmcid}:{title[:100]}'.encode()).hexdigest()

    return {
        'id': protocol_id,
        'source': 'pmc_open_access',
        'source_id': f'PMC{pmcid}',
        'title': title[:500],
        'domain': domain,
        'subdomain': _classify_subdomain(methods_text, domain),
        'abstract': abstract[:2000],
        'steps': steps,
        'reagents': list(set(all_reagents))[:50],
        'equipment': list(set(all_equipment))[:30],
        'parameters': list(set(all_params))[:50],
        'safety_notes': _extract_safety_notes(methods_text),
        'raw_text': methods_text[:100000],
        'metadata': {
            'num_steps': len(steps),
            'methods_length': len(methods_text),
            'has_abstract': len(abstract) > 0
        }
    }


def _parse_methods_to_steps(text: str) -> List[Dict]:
    """Parse methods text into structured steps."""
    steps = []

    # Try to find numbered steps first
    numbered = re.findall(r'(?:^|\n)\s*(\d+)[\.\)]\s+(.+?)(?=\n\s*\d+[\.\)]|\n\n|$)', text, re.DOTALL)

    if numbered:
        for order, step_text in numbered:
            step_text = step_text.strip()
            if len(step_text) > 20:
                steps.append(_create_step(int(order), step_text))
    else:
        # Split by sentences that start with action verbs
        action_verbs = r'\b(Add|Mix|Incubate|Centrifuge|Wash|Transfer|Remove|Apply|Prepare|Dissolve|Heat|Cool|Filter|Measure|Record|Analyze|Culture|Harvest|Extract|Dilute|Suspend|Pipette|Vortex|Sonicate|Lyse|Stain|Fix|Mount|Image|Collect|Store|Freeze|Thaw|Sterilize|Autoclave|Inject|Administer|Perform|Run|Load|Separate|Elute|Precipitate|Resuspend|Aliquot|Label|Weigh|Calculate|Adjust|Monitor|Observe|Document)\b'

        sentences = re.split(r'(?<=[.!?])\s+', text)
        order = 1
        for sent in sentences:
            if re.match(action_verbs, sent.strip(), re.IGNORECASE):
                if len(sent.strip()) > 30:
                    steps.append(_create_step(order, sent.strip()))
                    order += 1

        # If still no steps, just chunk by paragraphs
        if not steps:
            paragraphs = text.split('\n\n')
            for i, para in enumerate(paragraphs[:20], 1):
                para = para.strip()
                if len(para) > 50:
                    steps.append(_create_step(i, para[:1000]))

    return steps[:50]  # Limit to 50 steps


def _create_step(order: int, text: str) -> Dict:
    """Create a structured step dict."""
    action_match = re.match(r'^(\w+)', text.lower())

    return {
        'order': order,
        'text': text,
        'action_verb': action_match.group(1) if action_match else None,
        'reagents': _extract_reagents(text),
        'equipment': _extract_equipment(text),
        'parameters': _extract_parameters(text)
    }


def _extract_reagents(text: str) -> List[str]:
    """Extract reagent names from text."""
    reagents = []
    patterns = [
        r'(\d+(?:\.\d+)?\s*(?:mM|µM|uM|nM|M|mg/ml|µg/ml|ng/ml|%)\s+[A-Z][a-zA-Z\s\-]{2,30})',
        r'\b(PBS|DMEM|RPMI|FBS|EDTA|DMSO|BSA|DTT|SDS|Tris|HEPES|NaCl|KCl|MgCl2|CaCl2)\b',
        r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:buffer|medium|media|solution|reagent|antibody|enzyme))\b',
        r'\b(anti-[A-Za-z0-9\-]+\s+antibody)\b',
        r'\b(formaldehyde|paraformaldehyde|glutaraldehyde|methanol|ethanol|acetone|chloroform|phenol)\b'
    ]
    for pat in patterns:
        matches = re.findall(pat, text, re.IGNORECASE)
        reagents.extend([m.strip() for m in matches if len(m.strip()) > 2])
    return list(set(reagents))[:15]


def _extract_equipment(text: str) -> List[str]:
    """Extract equipment names from text."""
    equipment = []
    patterns = [
        r'\b(centrifuge|incubator|microscope|spectrophotometer|PCR|thermocycler|'
        r'vortex|sonicator|autoclave|pipette|micropipette|plate\s+reader|'
        r'flow\s+cytometer|HPLC|LC-MS|mass\s+spec|NMR|gel\s+electrophoresis|'
        r'water\s+bath|hot\s+plate|shaker|rocker|hood|biosafety\s+cabinet|'
        r'freezer|refrigerator|balance|pH\s+meter|stirrer|nanodrop|'
        r'confocal|fluorescence\s+microscope|western\s+blot|electroporator|'
        r'cryostat|microtome|tissue\s+culture|laminar\s+flow|sequencer|'
        r'real-time\s+PCR|qPCR|RT-PCR|thermal\s+cycler)\b',
    ]
    for pat in patterns:
        matches = re.findall(pat, text, re.IGNORECASE)
        equipment.extend([m.strip().lower() for m in matches])
    return list(set(equipment))[:15]


def _extract_parameters(text: str) -> List[str]:
    """Extract numerical parameters with units."""
    params = re.findall(
        r'(\d+(?:\.\d+)?)\s*(°?C|°?F|mL|µL|uL|mM|µM|uM|nM|mg|µg|ug|ng|rpm|xg|rcf|g|'
        r'min|minutes?|hrs?|hours?|sec|seconds?|psi|mbar|kV|V|Hz|mm|cm|nm|µm|%|v/v|w/v|kDa)',
        text, re.IGNORECASE
    )
    return [f"{val} {unit}" for val, unit in params][:20]


def _extract_safety_notes(text: str) -> List[str]:
    """Extract safety-related notes."""
    safety = []
    patterns = [
        r'(?:caution|warning|danger|hazard|toxic|corrosive|flammable|carcinogen)[:\s]+([^.]+\.)',
        r'(?:handle\s+with\s+care|wear\s+gloves|use\s+fume\s+hood|avoid\s+contact)[^.]*\.',
        r'(?:BSL-\d|biosafety\s+level)[^.]*\.'
    ]
    for pat in patterns:
        matches = re.findall(pat, text, re.IGNORECASE)
        safety.extend([m.strip() for m in matches])
    return safety[:10]


def _classify_subdomain(text: str, domain: str) -> str:
    """Classify subdomain within the main domain."""
    text_lower = text.lower()

    subdomains = {
        'plant_biology': {
            'arabidopsis': ['arabidopsis', 'thaliana', 'col-0'],
            'crop_science': ['rice', 'wheat', 'maize', 'corn', 'soybean', 'crop'],
            'photosynthesis': ['photosynthesis', 'chloroplast', 'chlorophyll'],
            'plant_development': ['meristem', 'root', 'shoot', 'flower', 'seed'],
            'plant_stress': ['drought', 'salt stress', 'pathogen', 'defense']
        },
        'oncology': {
            'genomics': ['sequencing', 'genome', 'mutation', 'variant', 'tcga'],
            'immunotherapy': ['immunotherapy', 't cell', 'checkpoint', 'car-t'],
            'proteomics': ['proteomics', 'mass spec', 'protein expression'],
            'cell_biology': ['cell line', 'culture', 'proliferation', 'apoptosis'],
            'clinical': ['patient', 'clinical', 'treatment', 'therapy']
        },
        'neurology': {
            'neuroimaging': ['mri', 'fmri', 'pet', 'ct scan', 'imaging'],
            'electrophysiology': ['patch clamp', 'eeg', 'electrode', 'recording'],
            'molecular': ['neurotransmitter', 'receptor', 'synaptic', 'signaling'],
            'behavior': ['behavior', 'cognition', 'memory', 'learning'],
            'disease': ['alzheimer', 'parkinson', 'stroke', 'neurodegeneration']
        }
    }

    if domain in subdomains:
        for subdomain, keywords in subdomains[domain].items():
            if any(kw in text_lower for kw in keywords):
                return subdomain

    return 'general'


def ingest(max_per_domain: int = 200) -> Tuple[List[Dict], Dict[str, int]]:
    """
    Ingest methods sections from PMC Open Access papers.

    Args:
        max_per_domain: Maximum papers to fetch per domain

    Returns:
        Tuple of (protocols list, stats dict)
    """
    os.makedirs(CACHE_DIR, exist_ok=True)

    protocols = []
    stats = {'total_searched': 0, 'total_fetched': 0, 'total_extracted': 0}
    domain_stats = {}

    for domain, queries in DOMAIN_QUERIES.items():
        logger.info(f'[PMC] Processing domain: {domain}')
        domain_protocols = []
        pmcids_seen = set()

        for query in queries:
            if len(domain_protocols) >= max_per_domain:
                break

            # Search for papers
            pmcids = _search_pmc_esearch(query, domain, max_results=100)
            stats['total_searched'] += len(pmcids)

            # Fetch and extract methods
            for pmcid in pmcids:
                if pmcid in pmcids_seen:
                    continue
                pmcids_seen.add(pmcid)

                if len(domain_protocols) >= max_per_domain:
                    break

                # Rate limiting
                time.sleep(0.4)

                xml = _fetch_pmc_article(pmcid)
                if not xml:
                    continue
                stats['total_fetched'] += 1

                protocol = _extract_methods_from_xml(xml, domain)
                if protocol and protocol.get('steps'):
                    domain_protocols.append(protocol)
                    stats['total_extracted'] += 1

        domain_stats[domain] = len(domain_protocols)
        protocols.extend(domain_protocols)
        logger.info(f'[PMC] {domain}: extracted {len(domain_protocols)} protocols')

    # Save to file
    with open(OUTPUT_FILE, 'w') as f:
        for p in protocols:
            f.write(json.dumps(p) + '\n')

    logger.info(f'[PMC] Total: {len(protocols)} protocols saved to {OUTPUT_FILE}')
    logger.info(f'[PMC] By domain: {domain_stats}')

    return protocols, {'stats': stats, 'by_domain': domain_stats}


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    protocols, stats = ingest(max_per_domain=200)
    print(f'\nIngested {len(protocols)} PMC methods protocols')
    print(f'Stats: {stats}')
