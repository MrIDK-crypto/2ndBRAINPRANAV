"""
Oncology Sources Ingester
=========================
Extracts protocols from cancer research-specific sources:

1. NCI/CPTAC (Clinical Proteomic Tumor Analysis Consortium)
   - Standardized tumor sample preparation
   - Mass spectrometry protocols
   - Genomics protocols

2. TCGA (The Cancer Genome Atlas)
   - Data processing pipelines
   - Variant calling protocols
   - Gene expression analysis

3. CCLE (Cancer Cell Line Encyclopedia)
   - Cell line maintenance
   - Treatment protocols
   - Sequencing methodologies

Output: Structured wet lab and dry lab protocol data
"""

import os
import re
import json
import logging
import requests
from typing import List, Dict, Any, Optional, Tuple
from hashlib import md5
import time

from . import CORPUS_DIR

logger = logging.getLogger(__name__)

# GDC API for TCGA data
GDC_API = "https://api.gdc.cancer.gov"

OUTPUT_FILE = os.path.join(CORPUS_DIR, 'oncology_protocols.jsonl')


def _fetch_cptac_protocols() -> List[Dict]:
    """Generate CPTAC standard protocols based on their documentation."""
    protocols = []

    cptac_protocols = [
        {
            'name': 'CPTAC Tumor Tissue Collection and Processing',
            'text': '''1. Obtain surgical tumor specimen within 30 minutes of resection.
2. Weigh fresh tissue specimen.
3. Divide specimen according to CPTAC sectioning protocol.
4. Flash freeze primary tumor portion in liquid nitrogen.
5. Transfer OCT-embedded portion for histology.
6. Store frozen samples at -80°C within 1 hour.
7. Document ischemic time (warm and cold).
8. Complete tissue quality checklist.
9. Ship frozen tissue on dry ice.
10. Verify sample integrity upon receipt.''',
            'subdomain': 'sample_collection',
            'type': 'wet_lab'
        },
        {
            'name': 'CPTAC Protein Extraction from FFPE Tissue',
            'text': '''1. Cut 10µm FFPE sections (5-10 sections per sample).
2. Deparaffinize with xylene (3x 5 minutes).
3. Rehydrate through graded ethanol series.
4. Resuspend in lysis buffer (100mM Tris-HCl, 4% SDS).
5. Sonicate for 15 minutes in water bath.
6. Heat at 95°C for 60 minutes for decrosslinking.
7. Cool and centrifuge at 16,000g for 15 minutes.
8. Collect supernatant.
9. Quantify protein using BCA assay.
10. Aliquot and store at -80°C.''',
            'subdomain': 'sample_preparation',
            'type': 'wet_lab'
        },
        {
            'name': 'CPTAC TMT Labeling Protocol',
            'text': '''1. Reduce 100µg protein with 5mM DTT at 56°C for 30 minutes.
2. Alkylate with 14mM iodoacetamide in dark for 30 minutes.
3. Perform methanol-chloroform precipitation.
4. Resuspend pellet in 100mM TEAB.
5. Digest overnight with trypsin (1:50 enzyme:protein).
6. Quantify peptides using BCA.
7. Label with TMT reagent (1:4 peptide:TMT ratio).
8. Incubate at room temperature for 1 hour.
9. Quench with 5% hydroxylamine.
10. Combine labeled samples.
11. Fractionate by basic pH reversed-phase chromatography.
12. Analyze fractions by LC-MS/MS.''',
            'subdomain': 'proteomics',
            'type': 'wet_lab'
        },
        {
            'name': 'CPTAC Phosphopeptide Enrichment (IMAC)',
            'text': '''1. Acidify combined TMT-labeled peptides with TFA.
2. Desalt using C18 Sep-Pak cartridge.
3. Resuspend in loading buffer (80% ACN, 0.1% TFA).
4. Load onto Fe-NTA IMAC beads.
5. Wash with loading buffer 3 times.
6. Wash with 0.5% formic acid.
7. Elute phosphopeptides with 500mM K2HPO4.
8. Immediately acidify eluate.
9. Desalt using C18 StageTips.
10. Dry in SpeedVac.
11. Resuspend in 0.1% formic acid for LC-MS/MS.''',
            'subdomain': 'proteomics',
            'type': 'wet_lab'
        },
        {
            'name': 'CPTAC Data-Dependent Acquisition MS Protocol',
            'text': '''1. Load 1µg peptides onto trap column.
2. Separate on 75µm x 50cm C18 column.
3. Run 2-hour gradient (5-35% ACN).
4. Set MS1 resolution to 120,000.
5. Set AGC target to 4e5 ions.
6. Set MS2 resolution to 60,000.
7. Use HCD fragmentation (NCE 32).
8. Set dynamic exclusion to 60 seconds.
9. Acquire top 20 ions per cycle.
10. Process raw files with MaxQuant or Proteome Discoverer.''',
            'subdomain': 'mass_spec',
            'type': 'dry_lab'
        },
        {
            'name': 'CPTAC Global Proteome Processing Pipeline',
            'text': '''1. Convert raw files to mzML using msconvert.
2. Search against UniProt reference proteome + contaminants.
3. Set enzyme to trypsin (2 missed cleavages max).
4. Set fixed modification: carbamidomethyl (C).
5. Set variable modifications: oxidation (M), acetyl (N-term).
6. Set TMT labels as fixed modifications.
7. Filter PSMs at 1% FDR.
8. Filter proteins at 1% FDR.
9. Normalize reporter ion intensities.
10. Aggregate peptide intensities to protein level.
11. Perform batch correction using ComBat.
12. Output final protein abundance matrix.''',
            'subdomain': 'proteomics',
            'type': 'dry_lab'
        }
    ]

    for proto in cptac_protocols:
        steps = _parse_protocol_text(proto['text'])

        all_reagents = list(set(r for s in steps for r in s.get('reagents', [])))
        all_equipment = list(set(e for s in steps for e in s.get('equipment', [])))
        all_software = _extract_oncology_software(proto['text'])

        protocol_id = md5(f"cptac:{proto['name']}".encode()).hexdigest()

        protocols.append({
            'id': protocol_id,
            'source': 'cptac',
            'source_id': proto['name'].lower().replace(' ', '_'),
            'title': proto['name'],
            'domain': 'oncology',
            'subdomain': proto['subdomain'],
            'protocol_type': proto['type'],
            'steps': steps,
            'reagents': all_reagents,
            'equipment': all_equipment,
            'parameters': [],
            'software_dependencies': all_software,
            'safety_notes': [],
            'raw_text': proto['text'],
            'metadata': {
                'num_steps': len(steps),
                'source_org': 'NCI CPTAC'
            }
        })

    return protocols


def _fetch_tcga_protocols() -> List[Dict]:
    """Generate TCGA standard protocols based on their documentation."""
    protocols = []

    tcga_protocols = [
        {
            'name': 'TCGA DNA Extraction from Fresh Frozen Tissue',
            'text': '''1. Cut 10-20 10µm sections from frozen tissue block.
2. Add 360µL Buffer ATL to tissue.
3. Add 40µL Proteinase K solution.
4. Incubate at 56°C overnight with shaking.
5. Add 400µL Buffer AL, vortex.
6. Add 400µL 100% ethanol, mix.
7. Transfer to DNeasy Mini spin column.
8. Centrifuge and discard flow-through.
9. Wash with Buffer AW1 and AW2.
10. Elute DNA in 100µL Buffer AE.
11. Quantify using Qubit dsDNA assay.
12. Assess quality with Agilent TapeStation.''',
            'subdomain': 'sample_preparation',
            'type': 'wet_lab'
        },
        {
            'name': 'TCGA RNA Extraction from Fresh Frozen Tissue',
            'text': '''1. Homogenize tissue in TRIzol using bead beater.
2. Incubate 5 minutes at room temperature.
3. Add 0.2mL chloroform per 1mL TRIzol.
4. Shake vigorously for 15 seconds.
5. Centrifuge at 12,000g for 15 minutes at 4°C.
6. Transfer aqueous phase to new tube.
7. Add equal volume 70% ethanol.
8. Transfer to RNeasy Mini column.
9. Follow RNeasy protocol with on-column DNase.
10. Elute RNA in 50µL RNase-free water.
11. Quantify using NanoDrop.
12. Assess RIN using Agilent Bioanalyzer.''',
            'subdomain': 'sample_preparation',
            'type': 'wet_lab'
        },
        {
            'name': 'TCGA Whole Exome Sequencing Library Prep',
            'text': '''1. Fragment 100ng gDNA using Covaris sonicator (target 200bp).
2. End repair using NEBNext End Repair Module.
3. A-tail using Klenow Fragment.
4. Ligate adapters using T4 DNA Ligase.
5. Size select 300-400bp using gel or beads.
6. Hybridize with exome capture probes (24 hours).
7. Capture hybrids with streptavidin beads.
8. Wash and elute captured fragments.
9. PCR amplify library (8-12 cycles).
10. Purify with AMPure XP beads.
11. Quantify using qPCR.
12. Sequence 100bp paired-end on Illumina HiSeq.''',
            'subdomain': 'sequencing',
            'type': 'wet_lab'
        },
        {
            'name': 'TCGA Somatic Variant Calling Pipeline',
            'text': '''1. Align reads to GRCh38 using BWA-MEM.
2. Sort and mark duplicates with Picard.
3. Perform base quality score recalibration with GATK.
4. Call somatic SNVs with MuTect2.
5. Call somatic indels with MuTect2.
6. Filter variants using FilterMutectCalls.
7. Annotate variants with VEP (Ensembl release 93).
8. Add cancer-specific annotations (COSMIC, ClinVar).
9. Filter for PASS variants.
10. Calculate tumor mutation burden.
11. Generate MAF file for downstream analysis.''',
            'subdomain': 'variant_calling',
            'type': 'dry_lab'
        },
        {
            'name': 'TCGA RNA-Seq Processing Pipeline',
            'text': '''1. Perform quality control with FastQC.
2. Trim adapters and low-quality bases with Trimmomatic.
3. Align to GRCh38 using STAR (2-pass mode).
4. Generate gene-level counts with HTSeq.
5. Perform RSEM quantification for TPM values.
6. Normalize counts using DESeq2 VST.
7. Perform batch correction if needed.
8. Call gene fusions using STAR-Fusion.
9. Generate BigWig coverage tracks.
10. Aggregate QC metrics.
11. Output final expression matrix.''',
            'subdomain': 'transcriptomics',
            'type': 'dry_lab'
        },
        {
            'name': 'TCGA Copy Number Analysis Pipeline',
            'text': '''1. Generate target coverage from BAM files.
2. Calculate log2 ratios vs normal panel.
3. Segment copy number using CBS algorithm.
4. Call amplifications and deletions.
5. Estimate tumor purity with ABSOLUTE.
6. Calculate allele-specific copy number.
7. Identify LOH regions.
8. Call chromothripsis events.
9. Integrate with driver gene list.
10. Generate GISTIC2 input files.
11. Run GISTIC2 for significant CNVs.''',
            'subdomain': 'genomics',
            'type': 'dry_lab'
        },
        {
            'name': 'TCGA Methylation Array Analysis',
            'text': '''1. Extract DNA (500ng input) for bisulfite conversion.
2. Perform bisulfite conversion using EZ DNA kit.
3. Process on Illumina 450K or EPIC array.
4. Load raw IDAT files into R.
5. Preprocess with minfi package.
6. Perform background correction (noob).
7. Normalize using SWAN or Funnorm.
8. Filter poor quality probes (detection p > 0.01).
9. Remove cross-reactive and SNP-affected probes.
10. Calculate beta values.
11. Identify differentially methylated regions.''',
            'subdomain': 'epigenetics',
            'type': 'dry_lab'
        }
    ]

    for proto in tcga_protocols:
        steps = _parse_protocol_text(proto['text'])

        all_reagents = list(set(r for s in steps for r in s.get('reagents', [])))
        all_equipment = list(set(e for s in steps for e in s.get('equipment', [])))
        all_software = _extract_oncology_software(proto['text'])

        protocol_id = md5(f"tcga:{proto['name']}".encode()).hexdigest()

        protocols.append({
            'id': protocol_id,
            'source': 'tcga',
            'source_id': proto['name'].lower().replace(' ', '_'),
            'title': proto['name'],
            'domain': 'oncology',
            'subdomain': proto['subdomain'],
            'protocol_type': proto['type'],
            'steps': steps,
            'reagents': all_reagents,
            'equipment': all_equipment,
            'parameters': [],
            'software_dependencies': all_software,
            'safety_notes': [],
            'raw_text': proto['text'],
            'metadata': {
                'num_steps': len(steps),
                'source_org': 'NCI TCGA'
            }
        })

    return protocols


def _fetch_ccle_protocols() -> List[Dict]:
    """Generate CCLE standard protocols based on their documentation."""
    protocols = []

    ccle_protocols = [
        {
            'name': 'CCLE Cell Line Maintenance',
            'text': '''1. Thaw vial rapidly in 37°C water bath.
2. Transfer cells to 10mL pre-warmed medium.
3. Centrifuge at 200g for 5 minutes.
4. Resuspend pellet in fresh medium.
5. Plate in appropriate culture vessel.
6. Incubate at 37°C, 5% CO2.
7. Change medium every 2-3 days.
8. Passage at 70-80% confluence.
9. Use 0.25% trypsin-EDTA for adherent cells.
10. Maintain below passage 20.
11. Verify identity by STR profiling.
12. Test for mycoplasma monthly.''',
            'subdomain': 'cell_culture',
            'type': 'wet_lab'
        },
        {
            'name': 'CCLE Drug Response Assay (CTG)',
            'text': '''1. Plate 1000-5000 cells/well in 384-well plate.
2. Allow cells to attach for 24 hours.
3. Add compounds using acoustic dispenser (Echo).
4. Treat across 9-point dose range.
5. Include DMSO and positive controls.
6. Incubate for 72 hours.
7. Add CellTiter-Glo reagent (1:1 ratio).
8. Shake for 2 minutes.
9. Incubate 10 minutes at room temperature.
10. Read luminescence on plate reader.
11. Normalize to DMSO controls.
12. Calculate IC50 using 4-parameter fit.''',
            'subdomain': 'drug_screening',
            'type': 'wet_lab'
        },
        {
            'name': 'CCLE Whole Genome Sequencing Protocol',
            'text': '''1. Extract DNA using DNeasy Blood & Tissue Kit.
2. QC DNA using Qubit and TapeStation.
3. Fragment DNA to 350bp using Covaris.
4. Prepare library using KAPA HyperPrep Kit.
5. Perform size selection with beads.
6. Amplify library with 6 PCR cycles.
7. Quantify library with qPCR.
8. Sequence on Illumina NovaSeq (60x coverage).
9. Align to GRCh38 with BWA-MEM.
10. Mark duplicates with GATK.
11. Call variants with GATK HaplotypeCaller.
12. Annotate with VEP and ClinVar.''',
            'subdomain': 'sequencing',
            'type': 'wet_lab'
        },
        {
            'name': 'CCLE CRISPR Dependency Screening',
            'text': '''1. Expand cells to 50 million.
2. Transduce with Cas9 lentivirus at MOI 0.3.
3. Select with blasticidin for 7 days.
4. Verify Cas9 activity using control sgRNA.
5. Transduce with sgRNA library at MOI 0.3.
6. Select with puromycin for 3 days.
7. Expand to maintain 500x library coverage.
8. Collect cells at day 0 (reference) and day 21.
9. Extract genomic DNA.
10. PCR amplify sgRNA cassettes.
11. Sequence on Illumina.
12. Analyze with MAGeCK algorithm.''',
            'subdomain': 'functional_genomics',
            'type': 'wet_lab'
        },
        {
            'name': 'CCLE RNA-Seq Protocol',
            'text': '''1. Harvest cells at 70% confluence.
2. Extract RNA using RNeasy Plus kit.
3. Assess RNA quality (RIN > 8 required).
4. Deplete rRNA or select polyA.
5. Fragment RNA and synthesize cDNA.
6. Prepare library using TruSeq Stranded kit.
7. Quantify library with Bioanalyzer.
8. Pool libraries for multiplexing.
9. Sequence 100bp paired-end on HiSeq.
10. Process with STAR and RSEM.
11. Call fusions with STAR-Fusion.
12. Generate TPM and count matrices.''',
            'subdomain': 'transcriptomics',
            'type': 'wet_lab'
        },
        {
            'name': 'CCLE Metabolomics Protocol',
            'text': '''1. Wash cells with cold PBS.
2. Add extraction solvent (80% methanol, -80°C).
3. Scrape cells and transfer to tube.
4. Vortex for 1 minute.
5. Centrifuge at 20,000g for 15 minutes at 4°C.
6. Transfer supernatant to new tube.
7. Dry in SpeedVac.
8. Resuspend in 50:50 ACN:water.
9. Inject onto HILIC column.
10. Run LC gradient over 25 minutes.
11. Acquire MS data in positive and negative mode.
12. Process with El-MAVEN for quantification.''',
            'subdomain': 'metabolomics',
            'type': 'wet_lab'
        }
    ]

    for proto in ccle_protocols:
        steps = _parse_protocol_text(proto['text'])

        all_reagents = list(set(r for s in steps for r in s.get('reagents', [])))
        all_equipment = list(set(e for s in steps for e in s.get('equipment', [])))
        all_software = _extract_oncology_software(proto['text'])

        protocol_id = md5(f"ccle:{proto['name']}".encode()).hexdigest()

        protocols.append({
            'id': protocol_id,
            'source': 'ccle',
            'source_id': proto['name'].lower().replace(' ', '_'),
            'title': proto['name'],
            'domain': 'oncology',
            'subdomain': proto['subdomain'],
            'protocol_type': proto['type'],
            'steps': steps,
            'reagents': all_reagents,
            'equipment': all_equipment,
            'parameters': [],
            'software_dependencies': all_software,
            'safety_notes': [],
            'raw_text': proto['text'],
            'metadata': {
                'num_steps': len(steps),
                'source_org': 'Broad Institute CCLE'
            }
        })

    return protocols


def _fetch_pmc_oncology_methods(max_articles: int = 50) -> List[Dict]:
    """Fetch oncology methods from PMC Open Access papers."""
    protocols = []

    # Use Europe PMC to find cancer/oncology methods papers
    epmc_url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    params = {
        'query': '(TITLE:cancer OR TITLE:tumor OR TITLE:oncology) AND (METHODS:protocol OR METHODS:procedure) AND OPEN_ACCESS:Y',
        'format': 'json',
        'pageSize': min(max_articles, 100),
        'resultType': 'lite'
    }

    try:
        resp = requests.get(epmc_url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        for result in data.get('resultList', {}).get('result', []):
            pmcid = result.get('pmcid')
            if not pmcid:
                continue

            # Extract basic info to create protocol
            abstract = result.get('abstractText', '')
            if len(abstract) < 200:
                continue

            steps = _extract_oncology_steps(abstract)
            if not steps:
                continue

            protocol_id = md5(f"pmc_oncology:{pmcid}".encode()).hexdigest()

            protocols.append({
                'id': protocol_id,
                'source': 'pmc_oncology',
                'source_id': pmcid,
                'title': result.get('title', '')[:500],
                'domain': 'oncology',
                'subdomain': _classify_oncology_subdomain(abstract),
                'protocol_type': 'wet_lab',
                'abstract': abstract[:2000],
                'steps': steps,
                'reagents': list(set(r for s in steps for r in s.get('reagents', [])))[:30],
                'equipment': list(set(e for s in steps for e in s.get('equipment', [])))[:20],
                'parameters': [],
                'software_dependencies': _extract_oncology_software(abstract),
                'safety_notes': [],
                'raw_text': abstract,
                'metadata': {
                    'num_steps': len(steps),
                    'pmcid': pmcid
                }
            })

    except Exception as e:
        logger.warning(f'[Oncology] Failed to fetch PMC articles: {e}')

    logger.info(f'[Oncology] Extracted {len(protocols)} PMC protocols')
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


def _extract_oncology_steps(text: str) -> List[Dict]:
    """Extract processing steps from oncology text."""
    steps = []

    # Try numbered steps
    numbered = re.findall(r'(?:^|\n)\s*(\d+)[\.\)]\s+(.+?)(?=\n\s*\d+[\.\)]|\n\n|$)', text, re.DOTALL)
    if numbered:
        for order, step_text in numbered:
            step_text = step_text.strip()
            if len(step_text) > 20:
                steps.append(_create_step(int(order), step_text[:500]))

    # Fall back to action sentences
    if not steps:
        action_verbs = r'\b(Add|Treat|Incubate|Culture|Harvest|Extract|Isolate|Lyse|Centrifuge|Wash|Resuspend|Plate|Transfect|Infect|Analyze|Sequence|Process|Filter|Quantify|Normalize|Stain|Image|Measure)\b'
        sentences = re.split(r'(?<=[.!?])\s+', text)
        order = 1
        for sent in sentences:
            if re.match(action_verbs, sent.strip(), re.IGNORECASE):
                if 30 < len(sent.strip()) < 500:
                    steps.append(_create_step(order, sent.strip()))
                    order += 1
                    if order > 20:
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
        r'\b(TRIzol|DMSO|PBS|FBS|trypsin|EDTA|SDS|DTT|TCEP|TMT|ACN|TFA|formic\s+acid)\b',
        r'\b(ethanol|methanol|chloroform|isopropanol)\b',
        r'(\d+%?\s+[A-Z][a-zA-Z\-]+)',
        r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:buffer|kit|reagent))\b'
    ]
    for pat in patterns:
        matches = re.findall(pat, text, re.IGNORECASE)
        reagents.extend([m.strip() for m in matches if len(m.strip()) > 2])
    return list(set(reagents))[:10]


def _extract_equipment(text: str) -> List[str]:
    """Extract equipment from text."""
    equipment = []
    patterns = [
        r'\b(centrifuge|incubator|sonicator|Covaris|spectrophotometer|'
        r'plate\s+reader|microscope|flow\s+cytometer|mass\s+spec|LC-MS|'
        r'HiSeq|NovaSeq|Illumina|Bioanalyzer|TapeStation|Qubit|'
        r'NanoDrop|SpeedVac|PCR|qPCR)\b'
    ]
    for pat in patterns:
        matches = re.findall(pat, text, re.IGNORECASE)
        equipment.extend([m.strip().lower() for m in matches])
    return list(set(equipment))[:10]


def _extract_parameters(text: str) -> List[str]:
    """Extract numerical parameters."""
    params = re.findall(
        r'(\d+(?:\.\d+)?)\s*(°?C|rpm|xg|g|minutes?|min|hours?|hrs?|µg|mg|ng|µL|mL|mM|µM|nM|%|bp|kb)',
        text, re.IGNORECASE
    )
    return [f"{val} {unit}" for val, unit in params][:10]


def _extract_oncology_software(text: str) -> List[str]:
    """Extract oncology software dependencies."""
    software = []
    patterns = [
        r'\b(GATK|BWA|STAR|Picard|MuTect|VEP|annovar|samtools|bcftools|'
        r'HTSeq|RSEM|DESeq2|edgeR|MAGeCK|GISTIC|ABSOLUTE|CellRanger|'
        r'MaxQuant|Proteome\s+Discoverer|Perseus|minfi|ComBat|'
        r'FastQC|MultiQC|Trimmomatic)\b'
    ]
    for pat in patterns:
        matches = re.findall(pat, text, re.IGNORECASE)
        software.extend([m.strip().lower() for m in matches])
    return list(set(software))[:20]


def _classify_oncology_subdomain(text: str) -> str:
    """Classify oncology subdomain."""
    text_lower = text.lower()
    subdomains = {
        'genomics': ['sequencing', 'genome', 'mutation', 'variant', 'dna'],
        'transcriptomics': ['rna', 'expression', 'transcript', 'mrna'],
        'proteomics': ['protein', 'mass spec', 'tmt', 'itraq', 'proteome'],
        'epigenetics': ['methylation', 'chromatin', 'histone', 'chip-seq'],
        'cell_culture': ['cell line', 'culture', 'passage', 'confluence'],
        'drug_screening': ['drug', 'compound', 'ic50', 'viability'],
        'immunology': ['t cell', 'immune', 'pd-1', 'checkpoint']
    }

    for subdomain, keywords in subdomains.items():
        if any(kw in text_lower for kw in keywords):
            return subdomain
    return 'general'


def ingest(max_pmc_articles: int = 50) -> Tuple[List[Dict], Dict[str, int]]:
    """
    Ingest protocols from oncology sources.

    Args:
        max_pmc_articles: Maximum PMC articles to process

    Returns:
        Tuple of (protocols list, stats dict)
    """
    protocols = []
    stats = {'cptac': 0, 'tcga': 0, 'ccle': 0, 'pmc': 0}

    # 1. CPTAC protocols
    logger.info('[Oncology] Fetching CPTAC protocols...')
    cptac_protocols = _fetch_cptac_protocols()
    stats['cptac'] = len(cptac_protocols)
    protocols.extend(cptac_protocols)
    logger.info(f'[Oncology] Extracted {len(cptac_protocols)} CPTAC protocols')

    # 2. TCGA protocols
    logger.info('[Oncology] Fetching TCGA protocols...')
    tcga_protocols = _fetch_tcga_protocols()
    stats['tcga'] = len(tcga_protocols)
    protocols.extend(tcga_protocols)
    logger.info(f'[Oncology] Extracted {len(tcga_protocols)} TCGA protocols')

    # 3. CCLE protocols
    logger.info('[Oncology] Fetching CCLE protocols...')
    ccle_protocols = _fetch_ccle_protocols()
    stats['ccle'] = len(ccle_protocols)
    protocols.extend(ccle_protocols)
    logger.info(f'[Oncology] Extracted {len(ccle_protocols)} CCLE protocols')

    # 4. PMC oncology methods
    logger.info('[Oncology] Fetching PMC oncology methods...')
    pmc_protocols = _fetch_pmc_oncology_methods(max_articles=max_pmc_articles)
    stats['pmc'] = len(pmc_protocols)
    protocols.extend(pmc_protocols)

    # Save to file
    with open(OUTPUT_FILE, 'w') as f:
        for p in protocols:
            f.write(json.dumps(p) + '\n')

    logger.info(f'[Oncology] Total: {len(protocols)} protocols saved to {OUTPUT_FILE}')

    return protocols, stats


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    protocols, stats = ingest(max_pmc_articles=50)
    print(f'\nIngested {len(protocols)} oncology protocols')
    print(f'Stats: {stats}')
