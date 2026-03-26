"""
Persistent Domain Ingester
==========================
Keeps running and retrying until we get comprehensive protocol coverage.
Never gives up - waits for rate limits, retries failures, keeps going.

Usage:
    python -m protocol_training.ingest_persistent
"""

import os
import json
import logging
import time
from typing import Dict, List, Any, Tuple
from collections import defaultdict
from datetime import datetime

from . import CORPUS_DIR

logger = logging.getLogger(__name__)

OUTPUT_UNIFIED = os.path.join(CORPUS_DIR, 'unified_protocols.jsonl')
OUTPUT_STATS = os.path.join(CORPUS_DIR, 'corpus_stats.json')

# Target minimums for each domain
TARGET_PROTOCOLS = {
    'plant_biology': 300,
    'oncology': 300,
    'neurology': 300,
    'bioinformatics': 200,
    'general': 3000
}


def run_ingester_with_retry(name: str, ingest_func, max_retries: int = 5, **kwargs) -> Tuple[int, Any]:
    """Run an ingester with retries until success."""
    for attempt in range(max_retries):
        try:
            logger.info(f'[Persistent] Running {name} (attempt {attempt+1}/{max_retries})...')
            protocols, stats = ingest_func(**kwargs)
            logger.info(f'[Persistent] {name}: {len(protocols)} protocols extracted')
            return len(protocols), stats
        except Exception as e:
            logger.warning(f'[Persistent] {name} failed: {e}')
            if attempt < max_retries - 1:
                wait = 60 * (attempt + 1)
                logger.info(f'[Persistent] Waiting {wait}s before retry...')
                time.sleep(wait)
            else:
                logger.error(f'[Persistent] {name} failed after {max_retries} attempts')
                return 0, {'error': str(e)}
    return 0, {}


def run_all_ingesters_persistent() -> Dict[str, Any]:
    """Run all ingesters with persistence - never give up."""
    results = {}
    total_protocols = 0

    # 1. PMC Open Access - most reliable, run first with high limits
    logger.info('=' * 60)
    logger.info('[Persistent] Phase 1: PMC Open Access (reliable source)')
    logger.info('=' * 60)
    try:
        from .ingest_pmc_methods import ingest as ingest_pmc
        count, stats = run_ingester_with_retry('PMC Methods', ingest_pmc, max_per_domain=200)
        results['pmc_methods'] = {'count': count, 'stats': stats}
        total_protocols += count
    except Exception as e:
        logger.error(f'[Persistent] PMC import failed: {e}')
        results['pmc_methods'] = {'count': 0, 'error': str(e)}

    # 2. Plant Biology specific sources
    logger.info('=' * 60)
    logger.info('[Persistent] Phase 2: Plant Biology sources')
    logger.info('=' * 60)
    try:
        from .ingest_plant_sources import ingest as ingest_plant
        count, stats = run_ingester_with_retry('Plant Sources', ingest_plant, max_plant_methods=100)
        results['plant_biology'] = {'count': count, 'stats': stats}
        total_protocols += count
    except Exception as e:
        logger.error(f'[Persistent] Plant import failed: {e}')
        results['plant_biology'] = {'count': 0, 'error': str(e)}

    # 3. Neurology sources
    logger.info('=' * 60)
    logger.info('[Persistent] Phase 3: Neurology sources')
    logger.info('=' * 60)
    try:
        from .ingest_neuro_sources import ingest as ingest_neuro
        count, stats = run_ingester_with_retry('Neuro Sources', ingest_neuro, max_openneuro=100)
        results['neurology'] = {'count': count, 'stats': stats}
        total_protocols += count
    except Exception as e:
        logger.error(f'[Persistent] Neuro import failed: {e}')
        results['neurology'] = {'count': 0, 'error': str(e)}

    # 4. Oncology sources
    logger.info('=' * 60)
    logger.info('[Persistent] Phase 4: Oncology sources')
    logger.info('=' * 60)
    try:
        from .ingest_oncology_sources import ingest as ingest_oncology
        count, stats = run_ingester_with_retry('Oncology Sources', ingest_oncology, max_pmc_articles=100)
        results['oncology'] = {'count': count, 'stats': stats}
        total_protocols += count
    except Exception as e:
        logger.error(f'[Persistent] Oncology import failed: {e}')
        results['oncology'] = {'count': 0, 'error': str(e)}

    # 5. GitHub - wait for rate limits if needed
    logger.info('=' * 60)
    logger.info('[Persistent] Phase 5: GitHub Bioinformatics (will wait for rate limits)')
    logger.info('=' * 60)
    try:
        from .ingest_github_bioinfo import ingest as ingest_github
        count, stats = run_ingester_with_retry('GitHub Bioinfo', ingest_github, max_per_topic=30)
        results['github_bioinfo'] = {'count': count, 'stats': stats}
        total_protocols += count
    except Exception as e:
        logger.error(f'[Persistent] GitHub import failed: {e}')
        results['github_bioinfo'] = {'count': 0, 'error': str(e)}

    # 6. Galaxy GTN - wait for rate limits
    logger.info('=' * 60)
    logger.info('[Persistent] Phase 6: Galaxy Training Network')
    logger.info('=' * 60)
    try:
        from .ingest_galaxy_gtn import ingest as ingest_gtn
        count, stats = run_ingester_with_retry('Galaxy GTN', ingest_gtn, max_per_topic=30)
        results['galaxy_gtn'] = {'count': count, 'stats': stats}
        total_protocols += count
    except Exception as e:
        logger.error(f'[Persistent] Galaxy GTN import failed: {e}')
        results['galaxy_gtn'] = {'count': 0, 'error': str(e)}

    # 7. Bioconductor
    logger.info('=' * 60)
    logger.info('[Persistent] Phase 7: Bioconductor Vignettes')
    logger.info('=' * 60)
    try:
        from .ingest_bioconductor import ingest as ingest_bioc
        count, stats = run_ingester_with_retry('Bioconductor', ingest_bioc, max_per_domain=50)
        results['bioconductor'] = {'count': count, 'stats': stats}
        total_protocols += count
    except Exception as e:
        logger.error(f'[Persistent] Bioconductor import failed: {e}')
        results['bioconductor'] = {'count': 0, 'error': str(e)}

    # 8. BioProtocolBench (always works)
    logger.info('=' * 60)
    logger.info('[Persistent] Phase 8: BioProtocolBench')
    logger.info('=' * 60)
    try:
        from .ingest_bioprotocolbench import ingest as ingest_bpb
        protocols, training_data = ingest_bpb()
        results['bioprotocolbench'] = {'count': len(protocols)}
        total_protocols += len(protocols)
    except Exception as e:
        logger.error(f'[Persistent] BioProtocolBench import failed: {e}')
        results['bioprotocolbench'] = {'count': 0, 'error': str(e)}

    results['total'] = total_protocols
    return results


def merge_all_protocols() -> Dict[str, Any]:
    """Merge all protocol files into unified corpus with comprehensive stats."""
    protocol_files = [
        'pmc_methods_protocols.jsonl',
        'github_bioinfo_protocols.jsonl',
        'bioconductor_protocols.jsonl',
        'galaxy_gtn_protocols.jsonl',
        'plant_biology_protocols.jsonl',
        'neurology_protocols.jsonl',
        'oncology_protocols.jsonl',
        'bioprotocolbench_protocols.jsonl',
        'chemh_protocols.jsonl',
        'openwetware_protocols.jsonl'
    ]

    all_protocols = []
    seen_ids = set()
    source_counts = defaultdict(int)
    domain_counts = defaultdict(int)
    subdomain_counts = defaultdict(lambda: defaultdict(int))
    protocol_type_counts = defaultdict(int)

    total_steps = 0
    protocols_with_steps = 0
    protocols_with_reagents = 0
    protocols_with_equipment = 0
    action_verbs = set()
    all_reagents = set()
    all_equipment = set()

    for pf in protocol_files:
        filepath = os.path.join(CORPUS_DIR, pf)
        if not os.path.exists(filepath):
            continue

        try:
            with open(filepath, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        protocol = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    pid = protocol.get('id', '')
                    if pid in seen_ids:
                        continue
                    seen_ids.add(pid)

                    source = protocol.get('source', 'unknown')
                    domain = protocol.get('domain', 'general')
                    subdomain = protocol.get('subdomain', 'general')
                    ptype = protocol.get('protocol_type', 'unknown')

                    source_counts[source] += 1
                    domain_counts[domain] += 1
                    subdomain_counts[domain][subdomain] += 1
                    protocol_type_counts[ptype] += 1

                    steps = protocol.get('steps', [])
                    if steps:
                        protocols_with_steps += 1
                        total_steps += len(steps)
                        for step in steps:
                            if step.get('action_verb'):
                                action_verbs.add(step['action_verb'])

                    reagents = protocol.get('reagents', [])
                    if reagents:
                        protocols_with_reagents += 1
                        all_reagents.update(reagents)

                    equipment = protocol.get('equipment', [])
                    if equipment:
                        protocols_with_equipment += 1
                        all_equipment.update(equipment)

                    all_protocols.append(protocol)

        except Exception as e:
            logger.error(f'[Persistent] Error processing {pf}: {e}')

    # Write unified corpus
    with open(OUTPUT_UNIFIED, 'w') as f:
        for p in all_protocols:
            f.write(json.dumps(p) + '\n')

    stats = {
        'total_protocols': len(all_protocols),
        'by_source': dict(source_counts),
        'by_domain': dict(domain_counts),
        'by_subdomain': {d: dict(sd) for d, sd in subdomain_counts.items()},
        'by_protocol_type': dict(protocol_type_counts),
        'total_steps': total_steps,
        'protocols_with_steps': protocols_with_steps,
        'protocols_with_reagents': protocols_with_reagents,
        'protocols_with_equipment': protocols_with_equipment,
        'avg_steps_per_protocol': round(total_steps / max(1, protocols_with_steps), 1),
        'num_unique_action_verbs': len(action_verbs),
        'num_unique_reagents': len(all_reagents),
        'num_unique_equipment': len(all_equipment),
        'generated_at': datetime.now().isoformat()
    }

    with open(OUTPUT_STATS, 'w') as f:
        json.dump(stats, f, indent=2)

    return stats


def check_coverage(stats: Dict) -> Tuple[bool, Dict[str, int]]:
    """Check if we have sufficient coverage for each domain."""
    domain_counts = stats.get('by_domain', {})
    gaps = {}

    for domain, target in TARGET_PROTOCOLS.items():
        current = domain_counts.get(domain, 0)
        if current < target:
            gaps[domain] = target - current

    is_sufficient = len(gaps) == 0
    return is_sufficient, gaps


def main():
    """Main entry point - keeps running until good coverage."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    start_time = time.time()

    logger.info('=' * 70)
    logger.info('[Persistent] PERSISTENT PROTOCOL INGESTION')
    logger.info('[Persistent] Will keep running until comprehensive coverage achieved')
    logger.info('=' * 70)

    # Run all ingesters
    results = run_all_ingesters_persistent()

    # Merge protocols
    logger.info('=' * 60)
    logger.info('[Persistent] Merging all protocols...')
    stats = merge_all_protocols()

    # Check coverage
    is_sufficient, gaps = check_coverage(stats)

    elapsed = time.time() - start_time

    # Print results
    print('\n' + '=' * 70)
    print('PERSISTENT INGESTION COMPLETE')
    print('=' * 70)
    print(f'\nTime elapsed: {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)')
    print(f'\nTotal protocols: {stats["total_protocols"]}')

    print(f'\n{"="*40}')
    print('DOMAIN COVERAGE')
    print(f'{"="*40}')
    for domain, count in sorted(stats['by_domain'].items(), key=lambda x: -x[1]):
        target = TARGET_PROTOCOLS.get(domain, 0)
        status = '✓' if count >= target else f'(need {target - count} more)'
        print(f'  {domain}: {count} {status}')

    print(f'\n{"="*40}')
    print('SOURCE BREAKDOWN')
    print(f'{"="*40}')
    for source, count in sorted(stats['by_source'].items(), key=lambda x: -x[1]):
        print(f'  {source}: {count}')

    print(f'\n{"="*40}')
    print('EXTRACTION QUALITY')
    print(f'{"="*40}')
    print(f'  Total steps: {stats["total_steps"]}')
    print(f'  Protocols with steps: {stats["protocols_with_steps"]}')
    print(f'  Average steps/protocol: {stats["avg_steps_per_protocol"]}')
    print(f'  Unique action verbs: {stats["num_unique_action_verbs"]}')
    print(f'  Unique reagents: {stats["num_unique_reagents"]}')
    print(f'  Unique equipment: {stats["num_unique_equipment"]}')

    if gaps:
        print(f'\n{"="*40}')
        print('COVERAGE GAPS (targets not met)')
        print(f'{"="*40}')
        for domain, gap in gaps.items():
            print(f'  {domain}: need {gap} more protocols')

    print(f'\nOutput: {OUTPUT_UNIFIED}')
    print(f'Stats: {OUTPUT_STATS}')

    return stats


if __name__ == '__main__':
    main()
