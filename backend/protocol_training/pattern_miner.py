"""
Protocol Pattern Miner
========================
Extracts protocol-specific patterns from the unified corpus to generate:
  - Action verb vocabulary (pipette, incubate, centrifuge, etc.)
  - Transition markers (then, next, after, following)
  - Safety patterns (fume hood, PPE, caution, hazardous)
  - Reagent patterns (mM, uM, mg/ml, stock solution)
  - Equipment patterns (rpm, xg, °C, PCR thermocycler)
  - Parameter patterns (for X minutes, at X degrees)
  - Vague parameter patterns (briefly, gently, overnight)

Outputs:
  - protocol_patterns.json  (raw mined data)
  - Generates backend/services/protocol_patterns.py (runtime module)
"""

import os
import re
import json
import logging
from typing import List, Dict, Any, Set, Tuple
from collections import Counter, defaultdict

from . import CORPUS_DIR

logger = logging.getLogger(__name__)

OUTPUT_PATTERNS = os.path.join(CORPUS_DIR, 'protocol_patterns.json')
RUNTIME_MODULE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    'services', 'protocol_patterns.py'
)

# ─── Known protocol action verbs (seed set, expanded by corpus mining) ───

SEED_ACTION_VERBS = {
    'add', 'adjust', 'agitate', 'aliquot', 'analyze', 'apply', 'aspirate',
    'assay', 'autoclave', 'blot', 'boil', 'buffer', 'calibrate', 'cap',
    'centrifuge', 'clamp', 'clean', 'collect', 'combine', 'cool', 'count',
    'culture', 'cut', 'decant', 'denature', 'detect', 'dialyze', 'digest',
    'dilute', 'discard', 'disconnect', 'dispense', 'dissolve', 'drain',
    'dry', 'elute', 'equilibrate', 'evaporate', 'examine', 'extract',
    'filter', 'fix', 'flash', 'flush', 'freeze', 'grind', 'grow', 'harvest',
    'heat', 'homogenize', 'hybridize', 'image', 'immerse', 'inoculate',
    'incubate', 'inject', 'insert', 'invert', 'isolate', 'label', 'layer',
    'ligate', 'load', 'lyse', 'measure', 'melt', 'microcentrifuge', 'mix',
    'mount', 'neutralize', 'observe', 'open', 'overlay', 'passage', 'pcr',
    'pellet', 'perfuse', 'photograph', 'pipette', 'plate', 'pool',
    'pour', 'precipitate', 'prepare', 'press', 'prime', 'probe', 'pulse',
    'purify', 'quantify', 'quench', 'read', 'reconstitute', 'record',
    'recover', 'reduce', 'remove', 'repeat', 'replace', 'resuspend',
    'rinse', 'rotate', 'run', 'seal', 'seed', 'separate', 'sequence',
    'shake', 'slice', 'sonicate', 'sort', 'spin', 'stain', 'sterilize',
    'stir', 'store', 'strain', 'streak', 'subculture', 'suspend', 'swirl',
    'thaw', 'tilt', 'titrate', 'transfer', 'transfect', 'transform',
    'treat', 'trypsinize', 'uncap', 'vacuum', 'visualize', 'vortex',
    'wash', 'weigh',
}

# ─── Known vague/imprecise parameter terms ───

VAGUE_TERMS = {
    'briefly', 'gently', 'vigorously', 'thoroughly', 'carefully',
    'overnight', 'room temperature', 'ambient temperature',
    'some', 'several', 'a few', 'adequate', 'sufficient', 'enough',
    'approximately', 'about', 'around', 'roughly', 'nearly',
    'small amount', 'large volume', 'appropriate amount',
    'as needed', 'until done', 'until ready', 'as required',
    'generous amount', 'trace amount', 'a little', 'a lot',
    'warm', 'cold', 'hot', 'cool', 'lukewarm',
    'fast', 'slow', 'quick', 'rapid',
    'short time', 'long time', 'extended period',
    'low speed', 'high speed', 'medium speed',
    'gentle heat', 'mild conditions', 'harsh conditions',
}

# ─── Hazardous reagents that require safety context ───

HAZARDOUS_REAGENTS = {
    'phenol', 'chloroform', 'trizol', 'tri reagent', 'formaldehyde',
    'paraformaldehyde', 'pfa', 'glutaraldehyde', 'acrylamide',
    'bis-acrylamide', 'ethidium bromide', 'etbr', 'sybr',
    'beta-mercaptoethanol', 'b-mercaptoethanol', 'bme', 'dtt',
    'dithiothreitol', 'sodium azide', 'diethyl pyrocarbonate', 'depc',
    'dimethyl sulfoxide', 'dmso', 'methanol', 'acetone', 'xylene',
    'toluene', 'benzene', 'hydrochloric acid', 'hcl', 'sulfuric acid',
    'nitric acid', 'sodium hydroxide', 'naoh', 'potassium hydroxide',
    'hydrofluoric acid', 'perchloric acid', 'acetic anhydride',
    'liquid nitrogen', 'dry ice', 'uv', 'ultraviolet',
    'radioactive', 'isotope', 'p32', 'p-32', 's35', 'c14',
    'cyanide', 'azide', 'osmium tetroxide', 'picric acid',
    'diaminobenzidine', 'dab', 'hydrogen peroxide', 'h2o2',
}


def _load_unified_corpus() -> List[Dict]:
    """Load the unified corpus JSONL file."""
    filepath = os.path.join(CORPUS_DIR, 'unified_corpus.jsonl')
    if not os.path.exists(filepath):
        logger.warning('[PatternMiner] Unified corpus not found, run normalizer first')
        return []

    protocols = []
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    protocols.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return protocols


def mine_action_verbs(protocols: List[Dict]) -> Dict[str, Any]:
    """Mine action verbs from protocol steps."""
    verb_counts = Counter()
    verb_contexts = defaultdict(list)

    for p in protocols:
        for step in p.get('steps', []):
            verb = step.get('action_verb', '')
            if verb and len(verb) > 1:
                verb = verb.lower().strip()
                verb_counts[verb] += 1
                # Store a context example (up to 3)
                if len(verb_contexts[verb]) < 3:
                    verb_contexts[verb].append(step['text'][:120])

    # Combine with seed set
    all_verbs = set(SEED_ACTION_VERBS)
    # Add corpus-mined verbs that appear at least 3 times
    for verb, count in verb_counts.items():
        if count >= 3 and len(verb) > 2:
            all_verbs.add(verb)

    # Categorize verbs
    categories = {
        'transfer': {'pipette', 'transfer', 'pour', 'decant', 'aliquot', 'dispense', 'aspirate', 'load', 'elute'},
        'mixing': {'mix', 'vortex', 'stir', 'shake', 'agitate', 'swirl', 'invert', 'homogenize'},
        'separation': {'centrifuge', 'spin', 'filter', 'separate', 'pellet', 'precipitate', 'extract', 'purify', 'isolate'},
        'temperature': {'incubate', 'heat', 'boil', 'cool', 'freeze', 'thaw', 'autoclave', 'denature', 'melt'},
        'preparation': {'prepare', 'dilute', 'dissolve', 'reconstitute', 'resuspend', 'buffer', 'neutralize', 'equilibrate'},
        'measurement': {'measure', 'weigh', 'count', 'quantify', 'read', 'record', 'calibrate', 'titrate', 'analyze'},
        'visualization': {'stain', 'image', 'visualize', 'photograph', 'observe', 'examine', 'blot', 'detect'},
        'cell_culture': {'culture', 'passage', 'seed', 'plate', 'harvest', 'trypsinize', 'transfect', 'transform', 'inoculate'},
        'molecular': {'pcr', 'ligate', 'digest', 'hybridize', 'sequence', 'probe', 'label', 'lyse'},
        'cleaning': {'wash', 'rinse', 'clean', 'flush', 'sterilize', 'dry', 'drain', 'discard', 'remove'},
    }

    return {
        'all_verbs': sorted(all_verbs),
        'verb_counts': dict(verb_counts.most_common(200)),
        'categories': {k: sorted(v) for k, v in categories.items()},
        'total_unique': len(all_verbs),
        'corpus_mined': len(verb_counts),
    }


def mine_transition_markers(protocols: List[Dict]) -> List[str]:
    """Mine transition markers between protocol steps."""
    markers = Counter()
    transition_patterns = [
        r'\b(then|next|after(?:wards?)?|following|subsequently|finally|lastly)\b',
        r'\b(meanwhile|simultaneously|concurrently|in parallel)\b',
        r'\b(immediately|quickly|slowly|carefully|gently)\b',
        r'\b(repeat|continue|proceed|resume)\b',
        r'\b(once .+? is (?:done|complete|ready|finished))\b',
        r'\b(before|prior to|ahead of)\b',
        r'\b(during|while|as)\b',
        r'\b(until|unless|if)\b',
        r'\b(note:|caution:|warning:|important:)\b',
        r'\b(optional(?:ly)?:?|alternatively)\b',
    ]

    for p in protocols:
        text = p.get('raw_text', '')
        for pattern in transition_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                markers[match.group(0).lower().strip()] += 1

    return [m for m, c in markers.most_common(100) if c >= 5]


def mine_parameter_patterns(protocols: List[Dict]) -> Dict[str, List[str]]:
    """Mine parameter patterns (concentrations, durations, temperatures, etc.)."""
    patterns = {
        'concentration': [],
        'duration': [],
        'temperature': [],
        'speed': [],
        'volume': [],
        'mass': [],
        'ph': [],
        'pressure': [],
    }

    # Regex patterns for parameter extraction
    param_regexes = {
        'concentration': [
            r'\d+\.?\d*\s*(?:mM|µM|uM|nM|pM|M|mg/ml|mg/mL|µg/ml|µg/mL|ug/ml|ng/ml|ng/µl|ng/uL|%\s*(?:v/v|w/v|w/w))',
            r'\d+\.?\d*\s*(?:x|X)\s*(?:concentration|conc\.?|stock)',
            r'(?:final|working|stock)\s+concentration\s+(?:of\s+)?\d+',
        ],
        'duration': [
            r'\d+\.?\d*\s*(?:min(?:utes?)?|sec(?:onds?)?|hr?s?|hours?|days?|weeks?|months?)',
            r'(?:for|approximately|about|~)\s*\d+\s*(?:min|sec|hr|hours?|days?)',
        ],
        'temperature': [
            r'-?\d+\.?\d*\s*°?\s*[CF]\b',
            r'-?\d+\.?\d*\s*degrees?\s*(?:Celsius|Fahrenheit|centigrade)',
            r'(?:room\s+temp(?:erature)?|RT|4\s*°?\s*C|37\s*°?\s*C|-[278]0\s*°?\s*C)',
        ],
        'speed': [
            r'\d+[,.]?\d*\s*(?:rpm|RPM|rcf|RCF|xg|×g|x\s*g)\b',
            r'(?:max(?:imum)?\s+)?speed',
        ],
        'volume': [
            r'\d+\.?\d*\s*(?:ml|mL|µl|µL|ul|uL|nl|nL|L|liters?|litres?)',
        ],
        'mass': [
            r'\d+\.?\d*\s*(?:mg|µg|ug|ng|pg|g|kg|grams?)',
        ],
        'ph': [
            r'pH\s*(?:of\s*)?\d+\.?\d*',
            r'pH\s*\d+\.?\d*\s*[-–]\s*\d+\.?\d*',
        ],
        'pressure': [
            r'\d+\.?\d*\s*(?:psi|PSI|bar|atm|Pa|kPa|mbar|torr|mmHg)',
        ],
    }

    examples = defaultdict(set)
    for p in protocols:
        text = p.get('raw_text', '')
        for param_type, regexes in param_regexes.items():
            for regex in regexes:
                for match in re.finditer(regex, text):
                    examples[param_type].add(match.group(0).strip())

    return {k: sorted(list(v))[:50] for k, v in examples.items()}


def mine_safety_patterns(protocols: List[Dict]) -> Dict[str, Any]:
    """Mine safety-related patterns from protocols."""
    safety_triggers = Counter()
    safety_contexts = []

    safety_regexes = [
        r'\b(?:caution|warning|danger|hazard(?:ous)?|toxic|corrosive|flammable|irritant)\b',
        r'\b(?:fume\s+hood|laminar\s+flow|biosafety\s+cabinet|BSC|chemical\s+hood)\b',
        r'\b(?:PPE|gloves?|goggles?|lab\s+coat|face\s+(?:mask|shield)|respirator)\b',
        r'\b(?:biohazard|biosafety\s+level|BSL-?\d|radioactive|carcinogen(?:ic)?)\b',
        r'\b(?:waste\s+disposal|sharps?\s+container|decontaminat(?:e|ion)|spill\s+kit)\b',
        r'\b(?:eye\s+wash|safety\s+shower|first\s+aid|emergency)\b',
        r'\b(?:do\s+not\s+(?:inhale|ingest|touch)|avoid\s+(?:contact|exposure|inhalation))\b',
        r'\b(?:ventilat(?:e|ion|ed)|well-?ventilated|open\s+flame|ignition\s+source)\b',
        r'\b(?:MSDS|SDS|safety\s+data\s+sheet|material\s+safety)\b',
    ]

    for p in protocols:
        text = p.get('raw_text', '')
        for regex in safety_regexes:
            for match in re.finditer(regex, text, re.IGNORECASE):
                safety_triggers[match.group(0).lower()] += 1

        # Also collect safety_notes from structured data
        for note in p.get('safety_notes', []):
            if note and len(note) > 10:
                safety_contexts.append(note[:200])

    return {
        'triggers': dict(safety_triggers.most_common(100)),
        'contexts': safety_contexts[:50],
        'hazardous_reagents': sorted(HAZARDOUS_REAGENTS),
    }


def mine_equipment_patterns(protocols: List[Dict]) -> Dict[str, Any]:
    """Mine equipment-related patterns."""
    equipment_counts = Counter()

    equipment_regexes = [
        r'\b(?:centrifuge|microcentrifuge|ultracentrifuge)\b',
        r'\b(?:PCR\s+(?:machine|thermocycler|cycler)|thermal\s*cycler)\b',
        r'\b(?:spectrophotometer|nanodrop|plate\s+reader|fluorometer)\b',
        r'\b(?:gel\s+(?:electrophoresis|box|apparatus)|SDS-?PAGE)\b',
        r'\b(?:microscope|confocal|fluorescence\s+microscop(?:e|y))\b',
        r'\b(?:incubator|shaking\s+incubator|CO2\s+incubator)\b',
        r'\b(?:autoclave|sterilizer)\b',
        r'\b(?:water\s+bath|heat(?:ing)?\s+block|hot\s+plate)\b',
        r'\b(?:vortex(?:er)?|sonicator|homogenizer)\b',
        r'\b(?:fume\s+hood|laminar\s+flow\s+hood|biosafety\s+cabinet)\b',
        r'\b(?:balance|scale|analytical\s+balance)\b',
        r'\b(?:pH\s+meter|conductivity\s+meter)\b',
        r'\b(?:pipett?e?|micropipett?e?|serological\s+pipett?e?|multichannel)\b',
        r'\b(?:HPLC|LC-?MS|GC-?MS|mass\s+spec(?:trometer|trometry)?)\b',
        r'\b(?:flow\s+cytometer|FACS|cell\s+sorter)\b',
        r'\b(?:western\s+blot(?:ting)?|transfer\s+apparatus)\b',
        r'\b(?:magnetic\s+stir(?:rer)?|orbital\s+shaker|rocker|rotator)\b',
        r'\b(?:cryostat|microtome|tissue\s+processor)\b',
        r'\b(?:electrophorator|electroporator|nucleofector)\b',
        r'\b(?:vacuum\s+(?:pump|manifold|flask)|aspirator)\b',
    ]

    for p in protocols:
        text = p.get('raw_text', '')
        for regex in equipment_regexes:
            for match in re.finditer(regex, text, re.IGNORECASE):
                equipment_counts[match.group(0).lower().strip()] += 1

        # Also count from structured equipment lists
        for eq in p.get('equipment', []):
            if eq:
                equipment_counts[eq.lower().strip()] += 1

    return {
        'equipment_counts': dict(equipment_counts.most_common(200)),
        'total_unique': len(equipment_counts),
    }


def mine_reagent_patterns(protocols: List[Dict]) -> Dict[str, Any]:
    """Mine reagent-related patterns."""
    reagent_counts = Counter()

    for p in protocols:
        for r in p.get('reagents', []):
            if r and len(r) > 1:
                reagent_counts[r.lower().strip()] += 1

    return {
        'reagent_counts': dict(reagent_counts.most_common(500)),
        'total_unique': len(reagent_counts),
    }


def generate_runtime_module(patterns: Dict[str, Any]) -> str:
    """Generate the backend/services/protocol_patterns.py runtime module."""

    action_verbs = patterns.get('action_verbs', {}).get('all_verbs', sorted(SEED_ACTION_VERBS))
    # Build trigger regex alternatives for action verbs (top 80)
    top_verbs = action_verbs[:80]
    verb_pattern = '|'.join(re.escape(v) for v in top_verbs)

    module = f'''"""
Protocol-Specific Patterns for IntelligentGapDetector
======================================================
AUTO-GENERATED by backend/protocol_training/pattern_miner.py
Do not edit manually — re-run the pattern miner to regenerate.

Provides:
  - PROTOCOL_FRAME_TEMPLATES: New frame types for protocol content
  - PROTOCOL_MISSING_PATTERNS: Missing info patterns for protocols
  - PROTOCOL_CONTENT_INDICATORS: Regex patterns to detect protocol text
  - is_protocol_content(): Quick heuristic check
"""

import re
from typing import Dict, List, Any, Tuple


# =============================================================================
# PROTOCOL CONTENT DETECTION
# =============================================================================

PROTOCOL_CONTENT_INDICATORS = [
    # Action verbs typical of lab protocols
    r"\\b(?:{verb_pattern})\\b",
    # Parameter patterns
    r"\\d+\\.?\\d*\\s*(?:mM|µM|uM|nM|mg/ml|µg/ml|ng/ml|%\\s*(?:v/v|w/v))",
    r"\\d+\\.?\\d*\\s*(?:min(?:utes?)?|sec(?:onds?)?|hrs?|hours?)",
    r"-?\\d+\\.?\\d*\\s*°?\\s*[CF]\\b",
    r"\\d+[,.]?\\d*\\s*(?:rpm|RPM|rcf|xg|×g)",
    r"\\d+\\.?\\d*\\s*(?:ml|mL|µl|µL|ul|uL|nl|L)",
    r"\\d+\\.?\\d*\\s*(?:mg|µg|ug|ng|pg|g|kg)",
    r"pH\\s*\\d+\\.?\\d*",
    # Equipment mentions
    r"\\b(?:centrifuge|PCR|thermocycler|incubator|spectrophotometer|nanodrop)\\b",
    r"\\b(?:vortex|sonicator|autoclave|microscope|plate\\s+reader)\\b",
    r"\\b(?:gel\\s+electrophoresis|western\\s+blot|HPLC|mass\\s+spec)\\b",
    r"\\b(?:fume\\s+hood|biosafety\\s+cabinet|laminar\\s+flow)\\b",
    # Reagent/material mentions
    r"\\b(?:buffer|solution|reagent|substrate|enzyme|antibody|primer|probe)\\b",
    r"\\b(?:PBS|DMEM|RPMI|FBS|BSA|EDTA|Tris|HEPES|SDS|TEMED)\\b",
    r"\\b(?:ethanol|methanol|isopropanol|chloroform|phenol|DMSO)\\b",
]

PROTOCOL_CONTENT_COMPILED = [re.compile(p, re.IGNORECASE) for p in PROTOCOL_CONTENT_INDICATORS]


def is_protocol_content(text: str, threshold: int = 5) -> Tuple[bool, float]:
    """
    Heuristic check: does this text look like a scientific protocol?

    Returns (is_protocol, confidence) where confidence is 0.0 to 1.0.
    A text needs at least `threshold` indicator matches to be considered protocol content.
    """
    if not text or len(text) < 50:
        return False, 0.0

    sample = text[:10000]  # Check first 10K chars for speed
    matches = 0
    max_possible = len(PROTOCOL_CONTENT_COMPILED)

    for pattern in PROTOCOL_CONTENT_COMPILED:
        if pattern.search(sample):
            matches += 1

    confidence = min(1.0, matches / max(1, max_possible * 0.6))
    return matches >= threshold, confidence


# =============================================================================
# PROTOCOL FRAME TEMPLATES (merge into FRAME_TEMPLATES)
# =============================================================================

PROTOCOL_FRAME_TEMPLATES = {{
    "PROTOCOL_STEP": {{
        "required": ["action", "parameters"],
        "optional": ["reagents", "equipment", "duration", "temperature", "expected_result", "notes"],
        "triggers": [
            # Core lab action patterns
            r"(?:pipette|transfer|add|dispense)\\s+\\d+",
            r"incubate\\s+(?:at|for|in)",
            r"centrifuge\\s+(?:at|for)",
            r"(?:wash|rinse)\\s+(?:with|in|using|\\d+\\s*(?:times|x))",
            r"elute\\s+(?:with|in|into)",
            r"(?:heat|cool|warm)\\s+(?:to|at|for)",
            r"vortex\\s+(?:for|briefly|vigorously)",
            r"(?:mix|combine|pool)\\s+(?:with|together|the)",
            r"(?:resuspend|dissolve|reconstitute)\\s+(?:in|with|the)",
            r"(?:filter|strain)\\s+(?:through|using|with)",
            r"(?:dilute|concentrate)\\s+(?:to|with|the|\\d+)",
            r"(?:spin|pellet)\\s+(?:at|for|down)",
            r"(?:load|apply|pour)\\s+(?:onto|into|the)",
            r"(?:stain|label|probe)\\s+(?:with|for|using)",
            r"(?:prepare|make|set up)\\s+(?:a|the|fresh)",
            r"(?:store|keep|freeze|thaw)\\s+(?:at|in|until)",
            r"(?:remove|discard|aspirate)\\s+(?:the|supernatant|media|medium)",
            r"(?:measure|record|note)\\s+(?:the|absorbance|concentration|volume)",
            r"(?:dry|air-dry|vacuum-dry|lyophilize)\\s+",
            r"(?:sterilize|autoclave|UV-treat)\\s+",
            r"run\\s+(?:the|a)?\\s*(?:gel|PCR|reaction|assay|column)",
            r"set\\s+(?:the)?\\s*(?:temperature|speed|timer|voltage)",
            r"equilibrate\\s+(?:to|at|for|the)",
            r"(?:cut|digest|ligate)\\s+(?:with|the|using)",
            r"plate\\s+(?:cells?|bacteria|the)",
            r"harvest\\s+(?:cells?|the|media)",
        ]
    }},
    "REAGENT_USAGE": {{
        "required": ["reagent_name", "concentration"],
        "optional": ["volume", "preparation", "storage", "vendor", "catalog_number"],
        "triggers": [
            r"\\d+\\.?\\d*\\s*(?:mM|µM|uM|nM|pM|M)\\s+",
            r"\\d+\\.?\\d*\\s*(?:mg/ml|mg/mL|µg/ml|µg/mL|ug/ml|ng/ml|ng/µl)",
            r"\\d+\\.?\\d*\\s*%\\s*(?:v/v|w/v|w/w)",
            r"(?:stock|working)\\s+(?:solution|concentration)",
            r"(?:final|initial)\\s+concentration",
            r"(?:freshly|newly)\\s+(?:prepared|made|dissolved)",
            r"(?:dilute|diluted)\\s+(?:\\d+[:-]\\d+|to\\s+\\d+)",
            r"(?:add|use|prepare)\\s+\\d+\\.?\\d*\\s*(?:ml|µl|ul|mL|µL|uL|L)",
        ]
    }},
    "EQUIPMENT_SETUP": {{
        "required": ["equipment", "settings"],
        "optional": ["calibration", "maintenance", "alternatives"],
        "triggers": [
            r"set\\s+(?:to|at)\\s+\\d+",
            r"preheat\\s+(?:to|at)\\s+\\d+",
            r"\\d+[,.]?\\d*\\s*(?:rpm|RPM|rcf|RCF|xg|×g)",
            r"(?:PCR|thermal)\\s*cycl(?:er|ing)",
            r"(?:HPLC|GC|LC)[- ](?:MS)?",
            r"(?:plate\\s+reader|spectrophotometer|nanodrop)",
            r"(?:flow\\s+cytometer|FACS|cell\\s+sorter)",
            r"(?:gel\\s+(?:box|apparatus)|electrophoresis)",
            r"(?:column|cartridge|membrane|filter)\\s+(?:equilibrat|condition|prime|wash)",
        ]
    }},
    "SAFETY_PRECAUTION": {{
        "required": ["hazard", "precaution"],
        "optional": ["ppe_required", "disposal", "first_aid", "regulatory"],
        "triggers": [
            r"(?:caution|warning|danger|hazard)",
            r"(?:fume\\s+hood|chemical\\s+hood|laminar\\s+flow)",
            r"(?:PPE|personal\\s+protective|gloves|goggles|lab\\s+coat|face\\s+(?:mask|shield))",
            r"(?:toxic|corrosive|flammable|irritant|carcinogen)",
            r"(?:biohazard|biosafety|BSL-?\\d|radioactive)",
            r"(?:waste\\s+disposal|sharps?\\s+container|decontaminat)",
            r"(?:avoid\\s+(?:contact|exposure|inhalation|ingestion))",
            r"(?:MSDS|SDS|safety\\s+data\\s+sheet)",
            r"(?:eye\\s+wash|safety\\s+shower|first\\s+aid)",
            r"(?:do\\s+not\\s+(?:inhale|ingest|pipette\\s+by\\s+mouth))",
        ]
    }},
    "EXPECTED_RESULT": {{
        "required": ["observation", "criteria"],
        "optional": ["troubleshooting", "alternatives", "quantitative_range"],
        "triggers": [
            r"should\\s+(?:yield|produce|result|appear|show|give|be)",
            r"(?:expect|expected)\\s+(?:to|result|output|yield|band|peak)",
            r"(?:positive|negative)\\s+control",
            r"(?:expected|typical|normal)\\s+(?:range|value|result|output|yield)",
            r"band\\s+(?:at|of|around)\\s+\\d+",
            r"(?:peak|signal)\\s+(?:at|around)\\s+\\d+",
            r"(?:OD|A)\\d{{3}}\\s*(?:=|of|around|~)\\s*\\d+",
            r"(?:confluence|confluency|density)\\s+(?:of|at|~)\\s*\\d+",
            r"(?:purity|yield|recovery|efficiency)\\s+(?:of|>|<|~|around)\\s*\\d+",
        ]
    }},
}}


# =============================================================================
# PROTOCOL-SPECIFIC MISSING PATTERNS (merge into MISSING_PATTERNS)
# =============================================================================

PROTOCOL_MISSING_PATTERNS = {{
    "VAGUE_PARAMETER": [
        r"\\b(?:briefly|gently|vigorously|thoroughly|carefully)\\b",
        r"\\b(?:overnight|room\\s+temperature|ambient\\s+temperature|RT)\\b",
        r"\\b(?:some|several|a\\s+few|adequate|sufficient|enough|appropriate)\\s+(?:amount|volume|quantity)",
        r"\\b(?:small|large|generous|trace)\\s+(?:amount|volume|quantity)",
        r"\\b(?:warm|cold|hot|cool|lukewarm)\\b(?!\\s*(?:to|at)\\s*\\d)",
        r"\\b(?:fast|slow|quick|rapid)(?:ly)?\\b(?!\\s*(?:at|to)\\s*\\d)",
        r"\\b(?:short|long|extended)\\s+(?:time|period|incubation|centrifugation)",
        r"\\b(?:low|high|medium|moderate)\\s+(?:speed|power|voltage|temperature)(?!\\s*(?:\\(|of|=|:)\\s*\\d)",
    ],
    "MISSING_CONCENTRATION": [
        r"(?:add|use|prepare|dissolve|dilute)\\s+(?:the\\s+)?(?:buffer|solution|reagent|antibody|enzyme|substrate|primer|probe)(?!\\s*(?:at|to|\\(|\\d+\\s*(?:mM|µM|uM|mg|µg|ng|%)))",
    ],
    "MISSING_DURATION": [
        r"\\b(?:incubate|centrifuge|spin|vortex|shake|heat|cool|boil|sonicate|digest|ligate|dry|equilibrate|block|stain|wash)\\b(?!.*?(?:\\d+\\s*(?:min|sec|hr|hour|day|week|s\\b|m\\b|h\\b)))",
    ],
    "MISSING_TEMPERATURE": [
        r"\\b(?:incubate|heat|warm|cool|store|freeze|thaw)\\b(?!.*?(?:\\d+\\s*°|\\d+\\s*degrees|room\\s+temp|RT\\b|on\\s+ice|4\\s*°?C|37\\s*°?C|-[278]0\\s*°?C))",
    ],
    "MISSING_EQUIPMENT_SETTING": [
        r"\\b(?:centrifuge|spin)\\b(?!.*?(?:\\d+\\s*(?:rpm|RPM|rcf|RCF|xg|×g)))",
        r"\\b(?:run|load)\\s+(?:the\\s+)?gel\\b(?!.*?(?:\\d+\\s*(?:V|mA|W|volts?|milliamps?|watts?)))",
    ],
    "MISSING_SAFETY_INFO": [
        # Hazardous reagent mentioned without safety context nearby
        r"\\b(?:phenol|chloroform|trizol|formaldehyde|paraformaldehyde|acrylamide|ethidium\\s+bromide|beta-?mercaptoethanol|sodium\\s+azide)\\b(?!.*?(?:hood|PPE|gloves|caution|warning|hazard|safety|careful|avoid))",
    ],
    "MISSING_VENDOR_INFO": [
        r"\\b(?:antibody|antibodies|primer|primers|enzyme|kit|plasmid|vector|cell\\s+line)\\b(?!.*?(?:catalog|cat\\.?\\s*#|cat\\.?\\s*no|from\\s+\\w+|purchased|obtained|supplied|provided|\\w+®|Thermo|Sigma|Invitrogen|Qiagen|NEB|Promega|Bio-?Rad|Abcam|Santa\\s+Cruz|Cell\\s+Signaling))",
    ],
}}


# =============================================================================
# PROTOCOL QUESTION TEMPLATES (for GroundedQuestionGenerator)
# =============================================================================

PROTOCOL_QUESTION_TEMPLATES = {{
    "PROTOCOL_STEP": [
        "What specific {{parameters}} should be used when performing {{action}}?",
        "What is the expected result after completing the {{action}} step?",
        "Are there any critical parameters missing from the {{action}} procedure?",
        "What equipment settings are needed for {{action}}?",
    ],
    "REAGENT_USAGE": [
        "What is the exact concentration of {{reagent_name}} to use?",
        "How should the {{reagent_name}} solution be prepared and stored?",
        "What is the vendor and catalog number for {{reagent_name}}?",
        "Are there any substitutes for {{reagent_name}}?",
    ],
    "EQUIPMENT_SETUP": [
        "What specific settings should {{equipment}} be configured to?",
        "Does {{equipment}} need calibration before use? If so, how?",
        "What maintenance is required for {{equipment}}?",
    ],
    "SAFETY_PRECAUTION": [
        "What PPE is required when handling {{hazard}}?",
        "What is the proper disposal procedure for {{hazard}}?",
        "What are the first aid measures if exposed to {{hazard}}?",
        "Is a fume hood or biosafety cabinet required for this step?",
    ],
    "EXPECTED_RESULT": [
        "What is the expected quantitative range for {{observation}}?",
        "What troubleshooting steps should be taken if {{criteria}} is not met?",
        "What does a failed result look like, and what are the likely causes?",
    ],
}}
'''

    return module


def mine(save_runtime: bool = True) -> Dict[str, Any]:
    """Run the full pattern mining pipeline."""
    protocols = _load_unified_corpus()

    if not protocols:
        logger.warning('[PatternMiner] No protocols found, using seed patterns only')
        # Generate with seed data even without corpus
        patterns = {
            'action_verbs': {
                'all_verbs': sorted(SEED_ACTION_VERBS),
                'verb_counts': {},
                'categories': {},
                'total_unique': len(SEED_ACTION_VERBS),
                'corpus_mined': 0,
            },
            'transition_markers': [],
            'parameter_patterns': {},
            'safety_patterns': {
                'triggers': {},
                'contexts': [],
                'hazardous_reagents': sorted(HAZARDOUS_REAGENTS),
            },
            'equipment_patterns': {'equipment_counts': {}, 'total_unique': 0},
            'reagent_patterns': {'reagent_counts': {}, 'total_unique': 0},
            'vague_terms': sorted(VAGUE_TERMS),
            'corpus_size': 0,
        }
    else:
        logger.info(f'[PatternMiner] Mining patterns from {len(protocols)} protocols...')

        patterns = {
            'action_verbs': mine_action_verbs(protocols),
            'transition_markers': mine_transition_markers(protocols),
            'parameter_patterns': mine_parameter_patterns(protocols),
            'safety_patterns': mine_safety_patterns(protocols),
            'equipment_patterns': mine_equipment_patterns(protocols),
            'reagent_patterns': mine_reagent_patterns(protocols),
            'vague_terms': sorted(VAGUE_TERMS),
            'corpus_size': len(protocols),
        }

    # Save raw patterns
    with open(OUTPUT_PATTERNS, 'w') as f:
        json.dump(patterns, f, indent=2)
    logger.info(f'[PatternMiner] Saved raw patterns to {OUTPUT_PATTERNS}')

    # Generate runtime module
    if save_runtime:
        runtime_code = generate_runtime_module(patterns)
        os.makedirs(os.path.dirname(RUNTIME_MODULE), exist_ok=True)
        with open(RUNTIME_MODULE, 'w') as f:
            f.write(runtime_code)
        logger.info(f'[PatternMiner] Generated runtime module at {RUNTIME_MODULE}')

    # Summary
    logger.info(f'[PatternMiner] Summary:')
    logger.info(f'  Action verbs: {patterns["action_verbs"]["total_unique"]}')
    logger.info(f'  Transition markers: {len(patterns["transition_markers"])}')
    logger.info(f'  Safety triggers: {len(patterns["safety_patterns"]["triggers"])}')
    logger.info(f'  Equipment types: {patterns["equipment_patterns"]["total_unique"]}')
    logger.info(f'  Reagent types: {patterns["reagent_patterns"]["total_unique"]}')
    logger.info(f'  Vague terms: {len(patterns["vague_terms"])}')

    return patterns


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    results = mine()
    print(f'\nPattern mining complete:')
    print(f'  Action verbs: {results["action_verbs"]["total_unique"]}')
    print(f'  Corpus size: {results["corpus_size"]} protocols')
