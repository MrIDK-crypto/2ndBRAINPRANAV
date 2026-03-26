"""
Master Domain Ingester
======================
Runs all domain-specific ingesters to build a comprehensive
protocol corpus for plant biology, oncology, and neurology.

This script:
1. Runs each domain ingester
2. Merges all protocols into unified corpus
3. Generates domain-specific statistics
4. Retrains classifiers

Usage:
    python -m protocol_training.ingest_all_domains
"""

import os
import json
import logging
from typing import Dict, List, Any
from collections import defaultdict
import time

from . import CORPUS_DIR

logger = logging.getLogger(__name__)

OUTPUT_UNIFIED = os.path.join(CORPUS_DIR, 'unified_protocols.jsonl')
OUTPUT_STATS = os.path.join(CORPUS_DIR, 'corpus_stats.json')


def run_all_ingesters() -> Dict[str, Any]:
    """Run all domain ingesters and collect results."""
    results = {}

    # 1. PMC Open Access Methods
    logger.info('=' * 60)
    logger.info('[Master] Running PMC Open Access ingester...')
    try:
        from .ingest_pmc_methods import ingest as ingest_pmc
        protocols, stats = ingest_pmc(max_per_domain=100)
        results['pmc_methods'] = {'count': len(protocols), 'stats': stats}
        logger.info(f'[Master] PMC: {len(protocols)} protocols')
    except Exception as e:
        logger.error(f'[Master] PMC ingester failed: {e}')
        results['pmc_methods'] = {'count': 0, 'error': str(e)}

    # 2. GitHub Bioinformatics
    logger.info('=' * 60)
    logger.info('[Master] Running GitHub Bioinformatics ingester...')
    try:
        from .ingest_github_bioinfo import ingest as ingest_github
        protocols, stats = ingest_github(max_per_topic=15)
        results['github_bioinfo'] = {'count': len(protocols), 'stats': stats}
        logger.info(f'[Master] GitHub: {len(protocols)} protocols')
    except Exception as e:
        logger.error(f'[Master] GitHub ingester failed: {e}')
        results['github_bioinfo'] = {'count': 0, 'error': str(e)}

    # 3. Bioconductor Vignettes
    logger.info('=' * 60)
    logger.info('[Master] Running Bioconductor ingester...')
    try:
        from .ingest_bioconductor import ingest as ingest_bioc
        protocols, stats = ingest_bioc(max_per_domain=20)
        results['bioconductor'] = {'count': len(protocols), 'stats': stats}
        logger.info(f'[Master] Bioconductor: {len(protocols)} protocols')
    except Exception as e:
        logger.error(f'[Master] Bioconductor ingester failed: {e}')
        results['bioconductor'] = {'count': 0, 'error': str(e)}

    # 4. Galaxy Training Network
    logger.info('=' * 60)
    logger.info('[Master] Running Galaxy GTN ingester...')
    try:
        from .ingest_galaxy_gtn import ingest as ingest_gtn
        protocols, stats = ingest_gtn(max_per_topic=15)
        results['galaxy_gtn'] = {'count': len(protocols), 'stats': stats}
        logger.info(f'[Master] Galaxy GTN: {len(protocols)} protocols')
    except Exception as e:
        logger.error(f'[Master] Galaxy GTN ingester failed: {e}')
        results['galaxy_gtn'] = {'count': 0, 'error': str(e)}

    # 5. Plant Biology Sources (TAIR, Plant Methods)
    logger.info('=' * 60)
    logger.info('[Master] Running Plant Biology ingester...')
    try:
        from .ingest_plant_sources import ingest as ingest_plant
        protocols, stats = ingest_plant(max_plant_methods=30)
        results['plant_biology'] = {'count': len(protocols), 'stats': stats}
        logger.info(f'[Master] Plant Biology: {len(protocols)} protocols')
    except Exception as e:
        logger.error(f'[Master] Plant Biology ingester failed: {e}')
        results['plant_biology'] = {'count': 0, 'error': str(e)}

    # 6. Neurology Sources (Allen, INCF, OpenNeuro)
    logger.info('=' * 60)
    logger.info('[Master] Running Neurology ingester...')
    try:
        from .ingest_neuro_sources import ingest as ingest_neuro
        protocols, stats = ingest_neuro(max_openneuro=30)
        results['neurology'] = {'count': len(protocols), 'stats': stats}
        logger.info(f'[Master] Neurology: {len(protocols)} protocols')
    except Exception as e:
        logger.error(f'[Master] Neurology ingester failed: {e}')
        results['neurology'] = {'count': 0, 'error': str(e)}

    # 7. Oncology Sources (CPTAC, TCGA, CCLE)
    logger.info('=' * 60)
    logger.info('[Master] Running Oncology ingester...')
    try:
        from .ingest_oncology_sources import ingest as ingest_oncology
        protocols, stats = ingest_oncology(max_pmc_articles=30)
        results['oncology'] = {'count': len(protocols), 'stats': stats}
        logger.info(f'[Master] Oncology: {len(protocols)} protocols')
    except Exception as e:
        logger.error(f'[Master] Oncology ingester failed: {e}')
        results['oncology'] = {'count': 0, 'error': str(e)}

    # 8. Existing BioProtocolBench
    logger.info('=' * 60)
    logger.info('[Master] Running BioProtocolBench ingester...')
    try:
        from .ingest_bioprotocolbench import ingest as ingest_bpb
        protocols, training_data = ingest_bpb()
        results['bioprotocolbench'] = {'count': len(protocols)}
        logger.info(f'[Master] BioProtocolBench: {len(protocols)} protocols')
    except Exception as e:
        logger.error(f'[Master] BioProtocolBench ingester failed: {e}')
        results['bioprotocolbench'] = {'count': 0, 'error': str(e)}

    return results


def merge_all_protocols() -> Dict[str, Any]:
    """Merge all protocol files into unified corpus."""
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

    # Aggregate stats
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
            logger.warning(f'[Master] File not found: {pf}')
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

                    # Deduplicate by ID
                    pid = protocol.get('id', '')
                    if pid in seen_ids:
                        continue
                    seen_ids.add(pid)

                    # Track stats
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
            logger.error(f'[Master] Error processing {pf}: {e}')

    # Write unified corpus
    with open(OUTPUT_UNIFIED, 'w') as f:
        for p in all_protocols:
            f.write(json.dumps(p) + '\n')

    logger.info(f'[Master] Unified corpus: {len(all_protocols)} protocols')

    # Compute stats
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
        'top_action_verbs': sorted(list(action_verbs))[:100],
        'top_reagents': sorted(list(all_reagents))[:100],
        'top_equipment': sorted(list(all_equipment))[:50]
    }

    # Write stats
    with open(OUTPUT_STATS, 'w') as f:
        json.dump(stats, f, indent=2)

    return stats


def main():
    """Main entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    start_time = time.time()

    logger.info('=' * 60)
    logger.info('[Master] Starting domain-specific protocol ingestion')
    logger.info('=' * 60)

    # Run all ingesters
    ingester_results = run_all_ingesters()

    # Merge into unified corpus
    logger.info('=' * 60)
    logger.info('[Master] Merging all protocols...')
    stats = merge_all_protocols()

    elapsed = time.time() - start_time

    # Print summary
    print('\n' + '=' * 60)
    print('INGESTION COMPLETE')
    print('=' * 60)
    print(f'\nTime elapsed: {elapsed:.1f} seconds')
    print(f'\nTotal protocols: {stats["total_protocols"]}')
    print(f'\nBy Domain:')
    for domain, count in sorted(stats['by_domain'].items(), key=lambda x: -x[1]):
        print(f'  {domain}: {count}')

    print(f'\nBy Source:')
    for source, count in sorted(stats['by_source'].items(), key=lambda x: -x[1]):
        print(f'  {source}: {count}')

    print(f'\nBy Protocol Type:')
    for ptype, count in stats.get('by_protocol_type', {}).items():
        print(f'  {ptype}: {count}')

    print(f'\nStep Statistics:')
    print(f'  Total steps: {stats["total_steps"]}')
    print(f'  Protocols with steps: {stats["protocols_with_steps"]}')
    print(f'  Average steps/protocol: {stats["avg_steps_per_protocol"]}')

    print(f'\nExtraction Statistics:')
    print(f'  Unique action verbs: {stats["num_unique_action_verbs"]}')
    print(f'  Unique reagents: {stats["num_unique_reagents"]}')
    print(f'  Unique equipment: {stats["num_unique_equipment"]}')

    print(f'\nSubdomain breakdown:')
    for domain, subdomains in stats.get('by_subdomain', {}).items():
        print(f'  {domain}:')
        for subdomain, count in sorted(subdomains.items(), key=lambda x: -x[1])[:5]:
            print(f'    - {subdomain}: {count}')

    print(f'\nOutput files:')
    print(f'  Unified corpus: {OUTPUT_UNIFIED}')
    print(f'  Stats: {OUTPUT_STATS}')

    return stats


if __name__ == '__main__':
    main()
