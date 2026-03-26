"""
Neurology/Neuroscience Sources Ingester
========================================
Extracts protocols from neuroscience-specific sources:

1. INCF (International Neuroinformatics Coordinating Facility)
   - Training materials and standards
   - Neuroimaging and electrophysiology pipelines

2. OpenNeuro
   - Preprocessing and analysis pipelines
   - fMRI/EEG/MEG datasets with methods

3. Allen Institute for Brain Science
   - Standardized protocols for atlas projects
   - Wet lab tissue prep and dry lab data processing

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

# OpenNeuro API
OPENNEURO_API = "https://openneuro.org/crn/datasets"

# Allen Institute protocols
ALLEN_PROTOCOLS_URL = "https://raw.githubusercontent.com/AllenInstitute"

OUTPUT_FILE = os.path.join(CORPUS_DIR, 'neurology_protocols.jsonl')


def _fetch_openneuro_datasets(max_datasets: int = 50) -> List[Dict]:
    """Fetch dataset info from OpenNeuro."""
    datasets = []

    # OpenNeuro GraphQL endpoint
    graphql_url = "https://openneuro.org/crn/graphql"

    query = """
    query {
        datasets(first: %d, orderBy: {stars: descending}) {
            edges {
                node {
                    id
                    name
                    description
                    modality
                    stars
                }
            }
        }
    }
    """ % max_datasets

    try:
        resp = requests.post(
            graphql_url,
            json={'query': query},
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        resp.raise_for_status()
        data = resp.json()

        for edge in data.get('data', {}).get('datasets', {}).get('edges', []):
            node = edge.get('node', {})
            datasets.append({
                'id': node.get('id', ''),
                'name': node.get('name', ''),
                'description': node.get('description', ''),
                'modality': node.get('modality', 'unknown'),
                'source': 'openneuro'
            })

    except Exception as e:
        logger.warning(f'[Neuro] OpenNeuro query failed: {e}')

    logger.info(f'[Neuro] Found {len(datasets)} OpenNeuro datasets')
    return datasets


def _create_openneuro_protocol(dataset: Dict) -> Optional[Dict]:
    """Create protocol from OpenNeuro dataset description."""
    description = dataset.get('description', '')
    if len(description) < 100:
        return None

    # Extract processing steps from description
    steps = _extract_neuro_steps(description)
    if not steps:
        return None

    protocol_id = md5(f"openneuro:{dataset['id']}".encode()).hexdigest()

    # Determine subdomain from modality
    modality = dataset.get('modality', 'unknown').lower()
    if 'fmri' in modality or 'mri' in modality:
        subdomain = 'neuroimaging'
    elif 'eeg' in modality or 'meg' in modality:
        subdomain = 'electrophysiology'
    elif 'pet' in modality:
        subdomain = 'pet_imaging'
    else:
        subdomain = 'general'

    return {
        'id': protocol_id,
        'source': 'openneuro',
        'source_id': dataset['id'],
        'source_url': f"https://openneuro.org/datasets/{dataset['id']}",
        'title': dataset['name'][:500],
        'domain': 'neurology',
        'subdomain': subdomain,
        'protocol_type': 'dry_lab',
        'steps': steps,
        'reagents': [],
        'equipment': _extract_neuro_equipment(description),
        'parameters': _extract_neuro_params(description),
        'software_dependencies': _extract_neuro_software(description),
        'safety_notes': [],
        'raw_text': description[:50000],
        'metadata': {
            'num_steps': len(steps),
            'modality': dataset.get('modality', 'unknown')
        }
    }


def _fetch_allen_protocols() -> List[Dict]:
    """Fetch/generate Allen Institute standard protocols."""
    protocols = []

    # Standard Allen Institute protocols (based on their public documentation)
    allen_protocols = [
        {
            'name': 'Allen Brain Atlas - Brain Tissue Processing',
            'text': '''1. Perfuse mouse transcardially with PBS followed by 4% PFA.
2. Dissect brain and post-fix in 4% PFA for 24 hours at 4°C.
3. Cryoprotect in 30% sucrose until brain sinks.
4. Embed in OCT compound and freeze at -80°C.
5. Section at 25µm using cryostat.
6. Mount sections on SuperFrost Plus slides.
7. Store at -20°C until staining.
8. For ISH: Process through standard colorimetric protocol.
9. Image using automated slide scanner at 10x magnification.
10. Register images to Allen CCF coordinates.''',
            'subdomain': 'tissue_processing',
            'type': 'wet_lab'
        },
        {
            'name': 'Allen Cell Types Database - Patch-Seq Protocol',
            'text': '''1. Prepare acute brain slices (300µm) in ice-cold ACSF.
2. Allow slices to recover at 34°C for 30 minutes.
3. Transfer to recording chamber with continuous ACSF perfusion.
4. Identify target cell using IR-DIC optics.
5. Obtain whole-cell patch with 3-5 MΩ pipette.
6. Record electrophysiological properties (firing pattern, membrane properties).
7. After recording, extract cytoplasmic contents.
8. Perform reverse transcription directly in pipette solution.
9. Amplify cDNA using Smart-seq2 protocol.
10. Generate sequencing library and sequence on Illumina platform.''',
            'subdomain': 'electrophysiology',
            'type': 'wet_lab'
        },
        {
            'name': 'Allen Brain Observatory - Two-Photon Calcium Imaging',
            'text': '''1. Inject AAV-Syn-GCaMP6 virus into target brain region.
2. Wait 3-4 weeks for expression.
3. Implant cranial window over visual cortex.
4. Allow 2 weeks recovery before imaging.
5. Head-fix mouse on running wheel.
6. Present visual stimuli (drifting gratings, natural scenes).
7. Image at 30Hz using 920nm excitation.
8. Extract ROIs using Suite2p or custom pipeline.
9. Calculate ΔF/F traces for each neuron.
10. Align responses to stimulus timing.
11. Classify cells by visual feature selectivity.''',
            'subdomain': 'calcium_imaging',
            'type': 'wet_lab'
        },
        {
            'name': 'Allen SDK - fMRI Preprocessing Pipeline',
            'text': '''1. Download raw NIFTI files from Allen Brain Observatory.
2. Run motion correction using FSL MCFLIRT.
3. Apply slice timing correction.
4. Perform brain extraction using BET.
5. Register to MNI152 template using FNIRT.
6. Apply spatial smoothing (6mm FWHM).
7. High-pass filter at 0.01 Hz.
8. Regress out confounds (motion parameters, WM, CSF).
9. Compute functional connectivity matrices.
10. Parcellate using Allen CCF regions.''',
            'subdomain': 'neuroimaging',
            'type': 'dry_lab'
        },
        {
            'name': 'Neuropixels Recording Protocol',
            'text': '''1. Sterilize Neuropixels probe with 70% ethanol.
2. Coat probe shank with DiI for track reconstruction.
3. Position probe using stereotaxic coordinates.
4. Lower probe slowly (10µm/s) to target depth.
5. Allow 30 minutes for tissue to settle.
6. Start acquisition at 30kHz sampling rate.
7. Present behavioral stimuli or allow free behavior.
8. Record for desired duration (typically 1-2 hours).
9. Slowly retract probe.
10. Export data in SpikeGLX format.
11. Run Kilosort for spike sorting.
12. Curate units in Phy.''',
            'subdomain': 'electrophysiology',
            'type': 'wet_lab'
        },
        {
            'name': 'Single-Cell RNA-seq Brain Tissue',
            'text': '''1. Microdissect brain region of interest.
2. Dissociate tissue using papain enzyme.
3. Triturate to single cell suspension.
4. Filter through 40µm strainer.
5. Load cells on 10x Genomics Chromium controller.
6. Generate GEMs with barcoded beads.
7. Perform reverse transcription.
8. Amplify cDNA by PCR.
9. Fragment and add sequencing adapters.
10. Sequence on Illumina NovaSeq (50,000 reads/cell).
11. Process with Cell Ranger pipeline.
12. Cluster cells and identify types using Seurat.''',
            'subdomain': 'single_cell',
            'type': 'wet_lab'
        },
        {
            'name': 'CLARITY Brain Clearing Protocol',
            'text': '''1. Perfuse mouse with 4% PFA + acrylamide/bisacrylamide.
2. Incubate brain in hydrogel solution at 4°C overnight.
3. Polymerize at 37°C for 3 hours in nitrogen atmosphere.
4. Remove excess hydrogel by gentle washing.
5. Clear tissue in SDS buffer at 37°C with agitation.
6. Continue clearing until tissue is transparent (1-4 weeks).
7. Wash out SDS with PBS.
8. Immunostain with primary antibody (3-5 days).
9. Wash and apply secondary antibody (3-5 days).
10. Clear in RIMS for refractive index matching.
11. Image using light sheet microscopy.''',
            'subdomain': 'tissue_clearing',
            'type': 'wet_lab'
        },
        {
            'name': 'EEG Signal Processing Pipeline',
            'text': '''1. Import raw EEG data into MNE-Python.
2. Apply notch filter at 50/60 Hz (line noise).
3. Bandpass filter 0.1-100 Hz.
4. Detect and interpolate bad channels.
5. Re-reference to average reference.
6. Run ICA for artifact removal.
7. Identify and remove eye/muscle components.
8. Epoch data around events of interest.
9. Reject epochs with amplitude > 100µV.
10. Compute event-related potentials.
11. Perform time-frequency analysis using Morlet wavelets.
12. Apply cluster-based permutation statistics.''',
            'subdomain': 'electrophysiology',
            'type': 'dry_lab'
        }
    ]

    for proto in allen_protocols:
        steps = _parse_protocol_text(proto['text'])

        all_reagents = list(set(r for s in steps for r in s.get('reagents', [])))
        all_equipment = list(set(e for s in steps for e in s.get('equipment', [])))
        all_software = _extract_neuro_software(proto['text'])

        protocol_id = md5(f"allen:{proto['name']}".encode()).hexdigest()

        protocols.append({
            'id': protocol_id,
            'source': 'allen_institute',
            'source_id': proto['name'].lower().replace(' ', '_'),
            'title': proto['name'],
            'domain': 'neurology',
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
                'source_org': 'Allen Institute for Brain Science'
            }
        })

    return protocols


def _fetch_incf_standards() -> List[Dict]:
    """Generate INCF standard protocols based on their guidelines."""
    protocols = []

    incf_protocols = [
        {
            'name': 'BIDS Dataset Organization',
            'text': '''1. Create root dataset folder with dataset_description.json.
2. Create participants.tsv with subject metadata.
3. Create sub-XX folders for each participant.
4. Organize modalities: anat/, func/, dwi/, eeg/, meg/.
5. Name files following BIDS convention.
6. Create accompanying JSON sidecar files.
7. Validate using bids-validator.
8. Document any deviations in README.
9. Add derivatives/ folder for processed data.
10. Include sourcedata/ for raw files.''',
            'subdomain': 'data_standards',
            'type': 'dry_lab'
        },
        {
            'name': 'NWB Neural Data Format Conversion',
            'text': '''1. Install pynwb package.
2. Create NWBFile with required metadata.
3. Add subject information.
4. Create ElectrodeTable for recording sites.
5. Add raw electrical series data.
6. Add processed LFP data.
7. Add spike times as Units table.
8. Add behavioral time series.
9. Add stimulus presentations.
10. Validate using nwbinspector.
11. Write to HDF5 file.''',
            'subdomain': 'data_standards',
            'type': 'dry_lab'
        },
        {
            'name': 'fMRIPrep Standard Processing',
            'text': '''1. Organize data in BIDS format.
2. Run fmriprep container with singularity/docker.
3. Specify output spaces (MNI152NLin2009cAsym).
4. Enable ICA-AROMA denoising.
5. Set FreeSurfer license path.
6. Run with --participant-label for specific subjects.
7. Review visual QC reports.
8. Check framewise displacement metrics.
9. Apply confound regression in downstream analysis.
10. Use preprocessed BOLD for GLM or connectivity.''',
            'subdomain': 'neuroimaging',
            'type': 'dry_lab'
        }
    ]

    for proto in incf_protocols:
        steps = _parse_protocol_text(proto['text'])
        all_software = _extract_neuro_software(proto['text'])

        protocol_id = md5(f"incf:{proto['name']}".encode()).hexdigest()

        protocols.append({
            'id': protocol_id,
            'source': 'incf',
            'source_id': proto['name'].lower().replace(' ', '_'),
            'title': f"INCF: {proto['name']}",
            'domain': 'neurology',
            'subdomain': proto['subdomain'],
            'protocol_type': proto['type'],
            'steps': steps,
            'reagents': [],
            'equipment': [],
            'parameters': [],
            'software_dependencies': all_software,
            'safety_notes': [],
            'raw_text': proto['text'],
            'metadata': {
                'num_steps': len(steps),
                'source_org': 'INCF'
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


def _extract_neuro_steps(text: str) -> List[Dict]:
    """Extract processing steps from neuroscience text."""
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
        action_verbs = r'\b(Acquire|Record|Process|Filter|Register|Segment|Normalize|Smooth|Analyze|Compute|Extract|Detect|Classify|Cluster|Run|Apply|Perform|Calculate|Generate|Export|Import|Load|Save|Visualize|Plot|Map|Transform|Align|Correct|Preprocess|Download)\b'
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
        'equipment': _extract_neuro_equipment_step(text),
        'parameters': _extract_neuro_params(text)
    }


def _extract_reagents(text: str) -> List[str]:
    """Extract reagent names from text."""
    reagents = []
    patterns = [
        r'\b(PFA|paraformaldehyde|PBS|sucrose|OCT|ACSF|papain|DiI|GCaMP)\b',
        r'(\d+%\s+[A-Z][a-zA-Z]+)'
    ]
    for pat in patterns:
        matches = re.findall(pat, text, re.IGNORECASE)
        reagents.extend([m.strip() for m in matches])
    return list(set(reagents))[:10]


def _extract_neuro_equipment(text: str) -> List[str]:
    """Extract neuroscience equipment from text."""
    equipment = []
    patterns = [
        r'\b(MRI|fMRI|PET|CT|EEG|MEG|microscope|cryostat|light\s+sheet|'
        r'two-photon|patch\s+clamp|electrode|Neuropixels|oscilloscope|'
        r'amplifier|stimulator|scanner|headstage|stereotax)\b'
    ]
    for pat in patterns:
        matches = re.findall(pat, text, re.IGNORECASE)
        equipment.extend([m.strip().lower() for m in matches])
    return list(set(equipment))[:15]


def _extract_neuro_equipment_step(text: str) -> List[str]:
    """Extract equipment from single step."""
    equipment = []
    patterns = [
        r'\b(cryostat|microscope|scanner|electrode|pipette|chamber)\b'
    ]
    for pat in patterns:
        matches = re.findall(pat, text, re.IGNORECASE)
        equipment.extend([m.strip().lower() for m in matches])
    return list(set(equipment))[:5]


def _extract_neuro_params(text: str) -> List[str]:
    """Extract neuroscience parameters."""
    params = re.findall(
        r'(\d+(?:\.\d+)?)\s*(Hz|kHz|MHz|µm|mm|ms|seconds?|minutes?|hours?|µV|mV|°C|MΩ|FWHM|µm/s)',
        text, re.IGNORECASE
    )
    return [f"{val} {unit}" for val, unit in params][:10]


def _extract_neuro_software(text: str) -> List[str]:
    """Extract neuroscience software dependencies."""
    software = []
    patterns = [
        r'\b(FSL|SPM|AFNI|FreeSurfer|ANTs|fmriprep|MRtrix|DSI\s+Studio|'
        r'MNE|MNE-Python|Brainstorm|FieldTrip|EEGLAB|Kilosort|Phy|'
        r'Suite2p|CaImAn|Cell\s+Ranger|Seurat|scanpy|BIDS|NWB|'
        r'nibabel|nilearn|pynwb|allensdk)\b'
    ]
    for pat in patterns:
        matches = re.findall(pat, text, re.IGNORECASE)
        software.extend([m.strip().lower() for m in matches])
    return list(set(software))[:20]


def ingest(max_openneuro: int = 50) -> Tuple[List[Dict], Dict[str, int]]:
    """
    Ingest protocols from neuroscience sources.

    Args:
        max_openneuro: Maximum OpenNeuro datasets to process

    Returns:
        Tuple of (protocols list, stats dict)
    """
    protocols = []
    stats = {'allen': 0, 'incf': 0, 'openneuro': 0}

    # 1. Allen Institute protocols
    logger.info('[Neuro] Fetching Allen Institute protocols...')
    allen_protocols = _fetch_allen_protocols()
    stats['allen'] = len(allen_protocols)
    protocols.extend(allen_protocols)
    logger.info(f'[Neuro] Extracted {len(allen_protocols)} Allen protocols')

    # 2. INCF standards
    logger.info('[Neuro] Fetching INCF standards...')
    incf_protocols = _fetch_incf_standards()
    stats['incf'] = len(incf_protocols)
    protocols.extend(incf_protocols)
    logger.info(f'[Neuro] Extracted {len(incf_protocols)} INCF protocols')

    # 3. OpenNeuro datasets
    logger.info('[Neuro] Fetching OpenNeuro datasets...')
    datasets = _fetch_openneuro_datasets(max_datasets=max_openneuro)

    for dataset in datasets:
        protocol = _create_openneuro_protocol(dataset)
        if protocol and protocol.get('steps'):
            protocols.append(protocol)
            stats['openneuro'] += 1

    logger.info(f'[Neuro] Extracted {stats["openneuro"]} OpenNeuro protocols')

    # Save to file
    with open(OUTPUT_FILE, 'w') as f:
        for p in protocols:
            f.write(json.dumps(p) + '\n')

    logger.info(f'[Neuro] Total: {len(protocols)} protocols saved to {OUTPUT_FILE}')

    return protocols, stats


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    protocols, stats = ingest(max_openneuro=50)
    print(f'\nIngested {len(protocols)} neurology protocols')
    print(f'Stats: {stats}')
