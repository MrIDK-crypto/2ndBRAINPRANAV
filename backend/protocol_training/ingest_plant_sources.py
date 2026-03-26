"""
Plant Biology Sources Ingester
==============================
Extracts protocols from plant biology-specific sources:

1. TAIR (The Arabidopsis Information Resource)
   - Arabidopsis-specific protocols
   - DNA extraction, plant transformation, etc.

2. Plant Methods Journal (BioMed Central)
   - Open access methods papers
   - Technological innovations in plant science

Output: Structured wet lab and dry lab protocol data
"""

import os
import re
import json
import logging
import requests
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional, Tuple
from hashlib import md5
import time

from . import CORPUS_DIR

logger = logging.getLogger(__name__)

# Plant Methods uses BioMed Central's OAI-PMH or RSS
PLANT_METHODS_OAI = "https://plantmethods.biomedcentral.com/oai/oai"
PLANT_METHODS_SEARCH = "https://plantmethods.biomedcentral.com/articles/json"

# TAIR protocols page (would need scraping)
TAIR_PROTOCOLS = "https://www.arabidopsis.org/portals/education/protocols.jsp"

OUTPUT_FILE = os.path.join(CORPUS_DIR, 'plant_biology_protocols.jsonl')


def _fetch_plant_methods_articles(max_articles: int = 100) -> List[Dict]:
    """Fetch article metadata from Plant Methods journal."""
    articles = []

    # Use Europe PMC to find Plant Methods papers with methods sections
    epmc_url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    params = {
        'query': '(JOURNAL:"Plant Methods") AND (METHODS:*protocol* OR METHODS:*procedure*)',
        'format': 'json',
        'pageSize': min(max_articles, 100),
        'resultType': 'lite'
    }

    try:
        resp = requests.get(epmc_url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        for result in data.get('resultList', {}).get('result', []):
            articles.append({
                'pmid': result.get('pmid'),
                'pmcid': result.get('pmcid'),
                'doi': result.get('doi'),
                'title': result.get('title', ''),
                'abstract': result.get('abstractText', ''),
                'source': 'plant_methods'
            })

    except Exception as e:
        logger.warning(f'[PlantMethods] Failed to fetch articles: {e}')

    logger.info(f'[PlantMethods] Found {len(articles)} articles')
    return articles


def _fetch_pmc_methods(pmcid: str) -> Optional[str]:
    """Fetch methods section from PMC."""
    if not pmcid:
        return None

    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    params = {
        'db': 'pmc',
        'id': pmcid.replace('PMC', ''),
        'rettype': 'xml'
    }

    try:
        resp = requests.get(url, params=params, timeout=60)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        logger.debug(f'[PlantMethods] Failed to fetch {pmcid}: {e}')
        return None


def _parse_pmc_xml_methods(xml_content: str, article: Dict) -> Optional[Dict]:
    """Parse PMC XML to extract methods section."""
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError:
        return None

    # Find methods section
    methods_text = ''
    for sec in root.findall('.//sec'):
        sec_type = sec.get('sec-type', '').lower()
        title_elem = sec.find('title')
        sec_title = ''
        if title_elem is not None:
            sec_title = ''.join(title_elem.itertext()).lower()

        if any(kw in sec_type or kw in sec_title for kw in
               ['method', 'material', 'procedure', 'protocol', 'experimental']):
            methods_text += ''.join(sec.itertext()) + '\n\n'

    if len(methods_text) < 200:
        return None

    steps = _parse_methods_to_steps(methods_text)
    if not steps:
        return None

    # Collect extracted entities
    all_reagents = list(set(r for s in steps for r in s.get('reagents', [])))
    all_equipment = list(set(e for s in steps for e in s.get('equipment', [])))

    protocol_id = md5(f"plantmethods:{article.get('pmcid', '')}:{article['title'][:50]}".encode()).hexdigest()

    return {
        'id': protocol_id,
        'source': 'plant_methods',
        'source_id': article.get('pmcid', article.get('doi', '')),
        'title': article['title'][:500],
        'domain': 'plant_biology',
        'subdomain': _classify_plant_subdomain(methods_text),
        'protocol_type': 'wet_lab',
        'abstract': article.get('abstract', '')[:2000],
        'steps': steps,
        'reagents': all_reagents[:50],
        'equipment': all_equipment[:30],
        'parameters': [],
        'safety_notes': _extract_safety_notes(methods_text),
        'raw_text': methods_text[:50000],
        'metadata': {
            'num_steps': len(steps),
            'pmcid': article.get('pmcid'),
            'doi': article.get('doi')
        }
    }


def _fetch_arabidopsis_protocols() -> List[Dict]:
    """Fetch protocols from TAIR and related Arabidopsis resources."""
    protocols = []

    # Common Arabidopsis protocol sources (from various open resources)
    protocol_sources = [
        {
            'name': 'Arabidopsis Transformation (Floral Dip)',
            'text': '''1. Grow Arabidopsis plants until they begin to flower.
2. Prepare Agrobacterium culture with transformation vector.
3. Grow Agrobacterium to OD600 of 0.8-1.0.
4. Resuspend cells in 5% sucrose solution with 0.05% Silwet L-77.
5. Dip floral buds in Agrobacterium solution for 30 seconds.
6. Cover plants with plastic dome overnight.
7. Allow plants to set seed.
8. Screen T1 seeds on selection media.''',
            'subdomain': 'plant_transformation'
        },
        {
            'name': 'Arabidopsis Genomic DNA Extraction (CTAB)',
            'text': '''1. Collect 100mg fresh leaf tissue.
2. Grind tissue in liquid nitrogen.
3. Add 500µL CTAB buffer (2% CTAB, 100mM Tris-HCl, 20mM EDTA, 1.4M NaCl).
4. Incubate at 65°C for 30 minutes.
5. Add equal volume chloroform:isoamyl alcohol (24:1).
6. Centrifuge at 12,000g for 10 minutes.
7. Transfer aqueous phase to new tube.
8. Add 2/3 volume isopropanol, incubate at -20°C.
9. Centrifuge, wash pellet with 70% ethanol.
10. Air dry and resuspend in TE buffer.''',
            'subdomain': 'dna_extraction'
        },
        {
            'name': 'Arabidopsis Protoplast Isolation',
            'text': '''1. Collect young rosette leaves (4-week old plants).
2. Cut leaves into 0.5mm strips with razor blade.
3. Incubate strips in enzyme solution (1% Cellulase, 0.25% Macerozyme) for 3 hours.
4. Filter through 75µm nylon mesh.
5. Centrifuge at 100g for 2 minutes.
6. Wash protoplasts with W5 solution.
7. Resuspend in MMg solution for transformation.
8. Add DNA and PEG solution.
9. Incubate 15 minutes.
10. Wash and culture in W5 solution.''',
            'subdomain': 'cell_culture'
        },
        {
            'name': 'Arabidopsis Seed Sterilization',
            'text': '''1. Place seeds in 1.5mL microcentrifuge tube.
2. Add 1mL 70% ethanol, vortex 30 seconds.
3. Remove ethanol, add 1mL 50% bleach with 0.1% Tween-20.
4. Incubate 10 minutes with occasional mixing.
5. Remove bleach solution.
6. Wash 5 times with sterile water.
7. Stratify seeds at 4°C for 2-4 days.
8. Plate on MS media.''',
            'subdomain': 'seed_handling'
        },
        {
            'name': 'Arabidopsis RNA Extraction (TRIzol)',
            'text': '''1. Grind 100mg leaf tissue in liquid nitrogen.
2. Add 1mL TRIzol reagent immediately.
3. Incubate at room temperature 5 minutes.
4. Add 200µL chloroform, shake vigorously.
5. Centrifuge at 12,000g, 4°C for 15 minutes.
6. Transfer aqueous phase to new tube.
7. Add 500µL isopropanol.
8. Incubate 10 minutes, centrifuge 10 minutes.
9. Wash pellet with 75% ethanol.
10. Dissolve RNA in RNase-free water.''',
            'subdomain': 'rna_extraction'
        },
        {
            'name': 'Plant Hormone Treatment (ABA)',
            'text': '''1. Prepare 100mM ABA stock in ethanol.
2. Dilute to working concentration (10-100µM) in sterile water.
3. For seedling treatment: transfer to liquid MS + ABA.
4. For foliar spray: add 0.02% Tween-20.
5. Spray entire plant surface until runoff.
6. Collect tissue at indicated time points.
7. Flash freeze in liquid nitrogen.
8. Store at -80°C until analysis.''',
            'subdomain': 'plant_stress'
        },
        {
            'name': 'Chlorophyll Fluorescence Measurement',
            'text': '''1. Dark adapt plants for 30 minutes.
2. Set fluorometer parameters (measuring beam, actinic light).
3. Position leaf clip on dark-adapted leaf.
4. Measure Fo (minimal fluorescence).
5. Apply saturating pulse, measure Fm.
6. Calculate Fv/Fm ratio.
7. Apply actinic light for steady-state measurements.
8. Record Fs, then saturating pulse for Fm'.
9. Calculate quantum yield and ETR.
10. Export data for analysis.''',
            'subdomain': 'photosynthesis'
        }
    ]

    for source in protocol_sources:
        steps = _parse_protocol_text(source['text'])

        all_reagents = list(set(r for s in steps for r in s.get('reagents', [])))
        all_equipment = list(set(e for s in steps for e in s.get('equipment', [])))

        protocol_id = md5(f"arabidopsis:{source['name']}".encode()).hexdigest()

        protocols.append({
            'id': protocol_id,
            'source': 'arabidopsis_tair',
            'source_id': source['name'].lower().replace(' ', '_'),
            'title': source['name'],
            'domain': 'plant_biology',
            'subdomain': source['subdomain'],
            'protocol_type': 'wet_lab',
            'steps': steps,
            'reagents': all_reagents,
            'equipment': all_equipment,
            'parameters': [],
            'safety_notes': [],
            'raw_text': source['text'],
            'metadata': {
                'num_steps': len(steps),
                'organism': 'arabidopsis_thaliana'
            }
        })

    return protocols


def _parse_protocol_text(text: str) -> List[Dict]:
    """Parse numbered protocol text into steps."""
    steps = []
    lines = text.strip().split('\n')

    for line in lines:
        match = re.match(r'^\s*(\d+)\.\s+(.+)$', line)
        if match:
            order, step_text = int(match.group(1)), match.group(2).strip()
            steps.append(_create_step(order, step_text))

    return steps


def _parse_methods_to_steps(text: str) -> List[Dict]:
    """Parse methods text into structured steps."""
    steps = []

    # Try numbered steps
    numbered = re.findall(r'(?:^|\n)\s*(\d+)[\.\)]\s+(.+?)(?=\n\s*\d+[\.\)]|\n\n|$)', text, re.DOTALL)
    if numbered:
        for order, step_text in numbered:
            step_text = step_text.strip()
            if len(step_text) > 20:
                steps.append(_create_step(int(order), step_text[:500]))

    # Fall back to action verb sentences
    if not steps:
        action_verbs = r'\b(Add|Mix|Incubate|Centrifuge|Wash|Transfer|Remove|Prepare|Dissolve|Heat|Cool|Filter|Grind|Harvest|Plant|Sow|Spray|Inoculate|Infect|Cross|Pollinate|Score|Measure|Collect|Extract|Purify|Amplify|Clone|Transform|Select)\b'
        sentences = re.split(r'(?<=[.!?])\s+', text)
        order = 1
        for sent in sentences:
            if re.match(action_verbs, sent.strip(), re.IGNORECASE):
                if 30 < len(sent.strip()) < 500:
                    steps.append(_create_step(order, sent.strip()))
                    order += 1
                    if order > 30:
                        break

    return steps[:50]


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
        r'(\d+(?:\.\d+)?\s*(?:mM|µM|µL|mL|mg|µg|ng|%)\s+[A-Z][a-zA-Z\s\-]+)',
        r'\b(CTAB|TRIzol|Tris|EDTA|SDS|PEG|MS|ABA|IAA|GA3|BAP|sucrose|ethanol|chloroform|isopropanol)\b',
        r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:buffer|solution|medium|media|reagent))\b'
    ]
    for pat in patterns:
        matches = re.findall(pat, text, re.IGNORECASE)
        reagents.extend([m.strip() for m in matches if len(m.strip()) > 2])
    return list(set(reagents))[:10]


def _extract_equipment(text: str) -> List[str]:
    """Extract equipment names from text."""
    equipment = []
    patterns = [
        r'\b(centrifuge|incubator|growth\s+chamber|fluorometer|microscope|'
        r'autoclave|razor|mortar|pestle|vortex|shaker|freezer|PCR|'
        r'spectrophotometer|plate\s+reader|water\s+bath|hot\s+plate)\b'
    ]
    for pat in patterns:
        matches = re.findall(pat, text, re.IGNORECASE)
        equipment.extend([m.strip().lower() for m in matches])
    return list(set(equipment))[:10]


def _extract_parameters(text: str) -> List[str]:
    """Extract numerical parameters."""
    params = re.findall(
        r'(\d+(?:\.\d+)?)\s*(°?C|rpm|xg|g|minutes?|min|hours?|hrs?|days?|weeks?|µL|mL|µM|mM|mg|µg|%)',
        text, re.IGNORECASE
    )
    return [f"{val} {unit}" for val, unit in params][:10]


def _extract_safety_notes(text: str) -> List[str]:
    """Extract safety notes."""
    safety = []
    patterns = [
        r'(?:caution|warning|danger|hazard|toxic)[:\s]+([^.]+\.)',
        r'(?:wear\s+gloves|fume\s+hood|liquid\s+nitrogen)[^.]*\.'
    ]
    for pat in patterns:
        matches = re.findall(pat, text, re.IGNORECASE)
        safety.extend([m.strip() for m in matches])
    return safety[:5]


def _classify_plant_subdomain(text: str) -> str:
    """Classify plant biology subdomain."""
    text_lower = text.lower()
    subdomains = {
        'genomics': ['dna', 'genome', 'sequencing', 'pcr', 'cloning'],
        'transcriptomics': ['rna', 'expression', 'qpcr', 'transcriptome'],
        'transformation': ['transform', 'agrobacterium', 'floral dip', 'transgenic'],
        'phenotyping': ['phenotype', 'measurement', 'growth', 'morphology'],
        'stress': ['stress', 'drought', 'salt', 'pathogen', 'disease'],
        'photosynthesis': ['chlorophyll', 'photosynthesis', 'fluorescence'],
        'cell_culture': ['protoplast', 'cell culture', 'callus', 'suspension']
    }

    for subdomain, keywords in subdomains.items():
        if any(kw in text_lower for kw in keywords):
            return subdomain
    return 'general'


def ingest(max_plant_methods: int = 50) -> Tuple[List[Dict], Dict[str, int]]:
    """
    Ingest protocols from plant biology sources.

    Args:
        max_plant_methods: Maximum Plant Methods articles to process

    Returns:
        Tuple of (protocols list, stats dict)
    """
    protocols = []
    stats = {'arabidopsis': 0, 'plant_methods': 0}

    # 1. Fetch Arabidopsis protocols
    logger.info('[Plant] Fetching Arabidopsis protocols...')
    arab_protocols = _fetch_arabidopsis_protocols()
    stats['arabidopsis'] = len(arab_protocols)
    protocols.extend(arab_protocols)
    logger.info(f'[Plant] Extracted {len(arab_protocols)} Arabidopsis protocols')

    # 2. Fetch Plant Methods journal articles
    logger.info('[Plant] Fetching Plant Methods articles...')
    articles = _fetch_plant_methods_articles(max_articles=max_plant_methods)

    for article in articles:
        if not article.get('pmcid'):
            continue

        time.sleep(0.4)  # Rate limiting

        xml = _fetch_pmc_methods(article['pmcid'])
        if not xml:
            continue

        protocol = _parse_pmc_xml_methods(xml, article)
        if protocol and protocol.get('steps'):
            protocols.append(protocol)
            stats['plant_methods'] += 1

    logger.info(f'[Plant] Extracted {stats["plant_methods"]} Plant Methods protocols')

    # Save to file
    with open(OUTPUT_FILE, 'w') as f:
        for p in protocols:
            f.write(json.dumps(p) + '\n')

    logger.info(f'[Plant] Total: {len(protocols)} protocols saved to {OUTPUT_FILE}')

    return protocols, stats


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    protocols, stats = ingest(max_plant_methods=50)
    print(f'\nIngested {len(protocols)} plant biology protocols')
    print(f'Stats: {stats}')
