"""
OpenAlex Methods Section Extractor (Tier 1)
=============================================
Downloads full-text from OpenAlex for top journals, extracts Methods sections,
and adds to protocol corpus for knowledge graph building.

Target: 30 journals (20 cancer + 10 general bio/methods)
Period: 2015-2024
"""

import os
import json
import time
import logging
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from xml.etree import ElementTree as ET

from . import CORPUS_DIR

logger = logging.getLogger(__name__)

OUTPUT_FILE = os.path.join(CORPUS_DIR, 'openalex_methods.jsonl')

# Top 30 journals — OpenAlex source IDs
# 20 cancer + 10 general bio/methods
TOP_JOURNALS = {
    # Cancer journals
    "CA: A Cancer Journal for Clinicians": "S125754415",
    "Nature Reviews Cancer": "S49861241",
    "Cancer Cell": "S160590955",
    "Cancer Discovery": "S2764556561",
    "Journal of Clinical Oncology": "S108542453",
    "The Lancet Oncology": "S151497755",
    "Nature Cancer": "S4210168932",
    "Annals of Oncology": "S196278807",
    "JAMA Oncology": "S2764844088",
    "Journal of the National Cancer Institute": "S167601637",
    "Clinical Cancer Research": "S188861966",
    "Molecular Cancer": "S163011645",
    "British Journal of Cancer": "S40576303",
    "Cancer Research": "S60697047",
    "Leukemia": "S174746622",
    "Neuro-Oncology": "S134288513",
    "International Journal of Cancer": "S151668105",
    "Oncogene": "S62491907",
    "European Journal of Cancer": "S4310234394",
    "Cell Reports Medicine": "S4210204685",
    # General biology / methods
    "Nature Methods": "S69568664",
    "Nature Protocols": "S82168767",
    "Cell": "S10637544",
    "Science": "S3880285",
    "PNAS": "S125754415",
    "Nature": "S137773608",
    "Nature Biotechnology": "S47756892",
    "Nucleic Acids Research": "S107023602",
    "PLOS ONE": "S202381698",
    "eLife": "S76438547",
}

OPENALEX_API = "https://api.openalex.org"
USER_EMAIL = os.getenv("OPENALEX_EMAIL", "prmogathala@gmail.com")

# Rate limit: be respectful
RATE_LIMIT_SECONDS = 0.1


def _fetch_works(source_id: str, per_page: int = 50, max_works: int = 500,
                 from_year: int = 2015, to_year: int = 2024) -> list:
    """Fetch works from OpenAlex for a given source."""
    try:
        import httpx
    except ImportError:
        raise ImportError('httpx library required for OpenAlex ingestion')

    works = []
    cursor = "*"

    while len(works) < max_works:
        url = (
            f"{OPENALEX_API}/works"
            f"?filter=primary_location.source.id:{source_id},"
            f"publication_year:{from_year}-{to_year},"
            f"has_fulltext:true"
            f"&per_page={per_page}"
            f"&cursor={cursor}"
            f"&mailto={USER_EMAIL}"
            f"&select=id,doi,title,publication_year,primary_location,open_access"
        )

        try:
            resp = httpx.get(url, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            page_results = data.get("results", [])
            if not page_results:
                break

            works.extend(page_results)

            cursor = data.get("meta", {}).get("next_cursor")
            if not cursor:
                break

            time.sleep(RATE_LIMIT_SECONDS)

        except Exception as e:
            logger.warning(f'[OpenAlex] Fetch error: {e}')
            break

    return works[:max_works]


def _extract_methods_from_tei(xml_content: str) -> str:
    """Extract Methods/Materials section from TEI XML."""
    try:
        root = ET.fromstring(xml_content)
        ns = {"tei": "http://www.tei-c.org/ns/1.0"}

        methods_text = []

        # Look for methods sections
        for div in root.findall(".//tei:body/tei:div", ns):
            head = div.find("tei:head", ns)
            if head is not None and head.text:
                head_lower = head.text.lower()
                if any(kw in head_lower for kw in [
                    "method", "material", "experimental", "procedure",
                    "protocol", "technique", "assay", "reagent",
                    "cell culture", "animal", "statistical", "data analysis"
                ]):
                    # Extract all text from this section
                    texts = []
                    for p in div.findall(".//tei:p", ns):
                        text = "".join(p.itertext()).strip()
                        if text:
                            texts.append(text)
                    if texts:
                        methods_text.append(f"## {head.text}\n" + "\n".join(texts))

        # Fallback: look for any div with type="methods"
        if not methods_text:
            for div in root.findall(".//tei:body/tei:div[@type]", ns):
                div_type = div.get("type", "").lower()
                if "method" in div_type or "material" in div_type:
                    texts = []
                    for p in div.findall(".//tei:p", ns):
                        text = "".join(p.itertext()).strip()
                        if text:
                            texts.append(text)
                    if texts:
                        methods_text.append("\n".join(texts))

        return "\n\n".join(methods_text)

    except ET.ParseError as e:
        logger.debug(f'[OpenAlex] TEI XML parse error: {e}')
        return ""


def _extract_methods_from_fulltext(fulltext: str) -> str:
    """Extract Methods section from plain full text using section headers."""
    if not fulltext:
        return ""

    methods_start = None
    for marker in ["Methods", "Materials and Methods", "Experimental Procedures",
                    "METHODS", "MATERIALS AND METHODS", "Experimental Section",
                    "Material and Methods", "MATERIAL AND METHODS",
                    "Experimental Design", "EXPERIMENTAL DESIGN",
                    "Study Design", "STUDY DESIGN"]:
        idx = fulltext.find(marker)
        if idx >= 0:
            methods_start = idx
            break

    if methods_start is None:
        return ""

    remaining = fulltext[methods_start:]
    end_markers = ["Results", "RESULTS", "Discussion", "DISCUSSION",
                    "Acknowledgment", "ACKNOWLEDGMENT", "References", "REFERENCES",
                    "Supplementary", "SUPPLEMENTARY", "Data Availability",
                    "Author Contributions", "Competing Interests", "Funding"]
    methods_end = len(remaining)
    for end_marker in end_markers:
        idx = remaining.find(end_marker, 100)  # Skip past the header
        if 0 < idx < methods_end:
            methods_end = idx

    return remaining[:methods_end].strip()


def _fetch_fulltext_from_oa_url(url: str, client) -> str:
    """Download and extract text from an open access URL (HTML or PDF landing page)."""
    if not url:
        return ""
    try:
        resp = client.get(url, timeout=30, follow_redirects=True,
                          headers={"User-Agent": "SecondBrain/1.0 (mailto:prmogathala@gmail.com)"})
        if resp.status_code != 200:
            return ""
        content_type = resp.headers.get("content-type", "")
        if "html" not in content_type:
            return ""  # Skip PDFs and other binary formats

        html = resp.text
        # Strip HTML tags to get plain text
        # Remove script and style blocks first
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<nav[^>]*>.*?</nav>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<header[^>]*>.*?</header>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<footer[^>]*>.*?</footer>', '', html, flags=re.DOTALL | re.IGNORECASE)
        # Convert common block elements to newlines
        html = re.sub(r'<(?:p|div|h[1-6]|br|li|tr)[^>]*>', '\n', html, flags=re.IGNORECASE)
        # Remove remaining tags
        text = re.sub(r'<[^>]+>', ' ', html)
        # Clean up whitespace
        text = re.sub(r'\n\s*\n', '\n\n', text)
        text = re.sub(r' +', ' ', text)
        # Decode HTML entities
        import html as html_mod
        text = html_mod.unescape(text)
        return text.strip()[:100000]  # Cap at 100K chars
    except Exception:
        return ""


def _extract_protocol_steps(methods_text: str) -> List[Dict]:
    """Extract structured steps from methods text."""
    steps = []

    # Split into sentences
    sentences = re.split(r'(?<=[.!?])\s+', methods_text)

    # Action verb patterns for protocol steps
    action_verbs = [
        "add", "incubate", "centrifuge", "wash", "mix", "pipette", "transfer",
        "resuspend", "dilute", "prepare", "harvest", "lyse", "extract",
        "amplify", "sequence", "stain", "fix", "mount", "image", "analyze",
        "measure", "quantify", "culture", "transfect", "treat", "collect",
        "separate", "elute", "block", "probe", "blot", "run", "load",
    ]

    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) < 20:
            continue

        # Check if sentence contains action verb
        words = sentence.lower().split()
        action = None
        for verb in action_verbs:
            if verb in words[:5]:  # Check first 5 words
                action = verb
                break

        if action or any(kw in sentence.lower() for kw in ["were ", "was ", "using "]):
            steps.append({
                "text": sentence,
                "action_verb": action or "process",
            })

    return steps


def _extract_reagents_equipment(text: str) -> Tuple[List[str], List[str]]:
    """Extract reagents and equipment from methods text."""
    reagents = set()
    equipment = set()

    # Common reagent patterns
    reagent_patterns = [
        r'\b(?:PBS|DMEM|RPMI|FBS|BSA|EDTA|SDS|Tris|HEPES)\b',
        r'\b(?:anti-\w+(?:\s+\w+)?)\b',
        r'\b\d+\s*(?:mM|µM|nM|mg/mL|µg/mL|ng/mL)\s+\w+',
        r'\b(?:antibody|enzyme|buffer|reagent|substrate|inhibitor)\b',
    ]

    equipment_patterns = [
        r'\b(?:centrifuge|microscope|spectrophotometer|incubator|thermocycler)\b',
        r'\b(?:PCR|HPLC|FACS|flow cytometer|plate reader|sequencer)\b',
        r'\b(?:vortex|sonicator|homogenizer|electroporator|cryostat)\b',
    ]

    for pattern in reagent_patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            reagents.add(match.group().strip())

    for pattern in equipment_patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            equipment.add(match.group().strip())

    return list(reagents)[:30], list(equipment)[:20]


def _detect_domain(journal_name: str) -> str:
    """Detect domain from journal name."""
    if journal_name in ["Nature Methods", "Nature Protocols"]:
        return "methods"
    elif journal_name in ["Cell", "Science", "Nature", "PNAS", "eLife"]:
        return "general_biology"
    elif journal_name in ["Nature Biotechnology"]:
        return "biotechnology"
    elif journal_name in ["Nucleic Acids Research"]:
        return "molecular_biology"
    elif journal_name in ["PLOS ONE"]:
        return "general_biology"
    else:
        return "cancer_biology"


def ingest(max_per_journal: int = 500, from_year: int = 2015, to_year: int = 2024) -> dict:
    """
    Download and process methods sections from top journals via OpenAlex.

    Args:
        max_per_journal: Max works to fetch per journal
        from_year: Start year for publications
        to_year: End year for publications

    Returns:
        dict with stats about ingested methods
    """
    os.makedirs(CORPUS_DIR, exist_ok=True)

    stats = {
        "journals_processed": 0,
        "works_fetched": 0,
        "methods_extracted": 0,
        "methods_with_steps": 0,
        "errors": 0,
    }

    try:
        import httpx
    except ImportError:
        logger.error('[OpenAlex] httpx library required for ingestion')
        return stats

    logger.info(f'[OpenAlex] Starting methods ingestion (max {max_per_journal}/journal, {from_year}-{to_year})...')

    with open(OUTPUT_FILE, "w") as out_f:
        for journal_name, source_id in TOP_JOURNALS.items():
            logger.info(f'[OpenAlex] Processing: {journal_name} ({source_id})')

            try:
                works = _fetch_works(source_id, max_works=max_per_journal,
                                     from_year=from_year, to_year=to_year)
                stats["works_fetched"] += len(works)

                for work in works:
                    work_id = work.get("id", "").split("/")[-1]
                    title = work.get("title", "")
                    doi = work.get("doi", "")
                    year = work.get("publication_year", 0)

                    # Try to get full text via OpenAlex
                    try:
                        full_text_url = (
                            f"{OPENALEX_API}/works/{work_id}"
                            f"?mailto={USER_EMAIL}"
                        )
                        resp = httpx.get(full_text_url, timeout=30)
                        if resp.status_code != 200:
                            continue

                        work_data = resp.json()

                        # Strategy 1: Try OA URL to download HTML full text
                        fulltext = ""
                        oa_url = (work_data.get("open_access", {}) or {}).get("oa_url", "")
                        if not oa_url:
                            best_loc = work_data.get("best_oa_location", {}) or {}
                            oa_url = best_loc.get("landing_page_url", "") or best_loc.get("pdf_url", "")

                        if oa_url and not oa_url.endswith(".pdf"):
                            fulltext = _fetch_fulltext_from_oa_url(oa_url, httpx)

                        # Strategy 2: Fallback to abstract (may contain some methods info)
                        if not fulltext:
                            abstract_inv = work_data.get("abstract_inverted_index", {})
                            if abstract_inv:
                                positions = {}
                                for word, pos_list in abstract_inv.items():
                                    for pos in pos_list:
                                        positions[pos] = word
                                if positions:
                                    fulltext = " ".join(positions.get(i, "") for i in range(max(positions.keys()) + 1))

                        if not fulltext:
                            continue

                        # Extract methods section from full text
                        methods = _extract_methods_from_fulltext(fulltext)

                        if not methods or len(methods) < 200:
                            continue

                        # Extract structured data
                        steps = _extract_protocol_steps(methods)
                        reagents, equipment = _extract_reagents_equipment(methods)
                        domain = _detect_domain(journal_name)

                        record = {
                            "title": title,
                            "source": f"openalex_{journal_name.lower().replace(' ', '_')}",
                            "domain": domain,
                            "steps": steps,
                            "reagents": reagents,
                            "equipment": equipment,
                            "metadata": {
                                "openalex_id": work_id,
                                "doi": doi,
                                "year": year,
                                "journal": journal_name,
                                "methods_length": len(methods),
                            },
                            "methods_text": methods[:10000],  # Cap at 10K chars
                        }

                        out_f.write(json.dumps(record) + "\n")
                        stats["methods_extracted"] += 1
                        if steps:
                            stats["methods_with_steps"] += 1

                    except Exception as e:
                        logger.debug(f'[OpenAlex] Work {work_id} failed: {e}')
                        stats["errors"] += 1

                    time.sleep(RATE_LIMIT_SECONDS)

                stats["journals_processed"] += 1
                logger.info(f'[OpenAlex]   {journal_name}: {stats["methods_extracted"]} methods so far')

            except Exception as e:
                logger.error(f'[OpenAlex] Journal {journal_name} failed: {e}')
                stats["errors"] += 1

    logger.info(f'[OpenAlex] Methods ingestion complete: {stats}')
    logger.info(f'[OpenAlex] Saved to {OUTPUT_FILE}')
    return stats


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    results = ingest(max_per_journal=10)  # Small test run
    print(f'\nOpenAlex methods ingestion results:')
    for k, v in results.items():
        print(f'  {k}: {v}')
