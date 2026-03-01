"""
Celery Tasks for Protocol Training Pipeline
=============================================
Background tasks for corpus ingestion, pattern mining, and model training.
"""

import os
import sys
import logging

# Ensure /app is in Python path (Celery workers may fork with different cwd)
_app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _app_dir not in sys.path:
    sys.path.insert(0, _app_dir)

from celery_app import celery

logger = logging.getLogger(__name__)


@celery.task(bind=True, name='tasks.protocol_training_tasks.ingest_protocol_corpus')
def ingest_protocol_corpus(self, sources=None, max_protocols=5000):
    """
    Ingest protocols from external sources, normalize, and mine patterns.

    Args:
        sources: List of sources to ingest. None = all sources.
                 Options: ['chemh', 'wlp', 'bioprotocolbench', 'protocolsio', 'openwetware']
        max_protocols: Max protocols per source (for API-based sources)
    """
    # Debug: log filesystem state to diagnose ModuleNotFoundError
    logger.warning(f'[ProtocolTask] cwd={os.getcwd()}')
    logger.warning(f'[ProtocolTask] sys.path={sys.path[:5]}')
    logger.warning(f'[ProtocolTask] /app contents={os.listdir("/app") if os.path.isdir("/app") else "NOT_FOUND"}')
    logger.warning(f'[ProtocolTask] /app/protocol_training exists={os.path.isdir("/app/protocol_training")}')
    if os.path.isdir('/app/protocol_training'):
        logger.warning(f'[ProtocolTask] protocol_training contents={os.listdir("/app/protocol_training")}')

    from protocol_training import ingest_chemh, ingest_wlp, ingest_bioprotocolbench
    from protocol_training import ingest_protocolsio, ingest_openwetware
    from protocol_training.normalizer import normalize
    from protocol_training.pattern_miner import mine

    all_sources = sources or ['chemh', 'wlp', 'bioprotocolbench', 'protocolsio', 'openwetware']
    results = {}

    for source in all_sources:
        try:
            if source == 'chemh':
                protocols = ingest_chemh.ingest()
                results['chemh'] = len(protocols)
            elif source == 'wlp':
                protocols, vocab = ingest_wlp.ingest()
                results['wlp'] = len(protocols)
            elif source == 'bioprotocolbench':
                protocols, training = ingest_bioprotocolbench.ingest()
                results['bioprotocolbench'] = len(protocols)
            elif source == 'protocolsio':
                protocols = ingest_protocolsio.ingest(max_protocols=max_protocols)
                results['protocolsio'] = len(protocols)
            elif source == 'openwetware':
                protocols = ingest_openwetware.ingest(max_pages=max_protocols)
                results['openwetware'] = len(protocols)
        except Exception as e:
            logger.error(f'[ProtocolTask] Failed to ingest {source}: {e}')
            results[source] = f'error: {str(e)}'

    # Normalize
    try:
        unified, stats = normalize()
        results['unified_count'] = stats['total_protocols']
    except Exception as e:
        logger.error(f'[ProtocolTask] Normalization failed: {e}')
        results['normalize'] = f'error: {str(e)}'

    # Mine patterns
    try:
        patterns = mine(save_runtime=True)
        results['patterns_mined'] = True
    except Exception as e:
        logger.error(f'[ProtocolTask] Pattern mining failed: {e}')
        results['patterns'] = f'error: {str(e)}'

    return results


@celery.task(bind=True, name='tasks.protocol_training_tasks.train_protocol_models')
def train_protocol_models(self):
    """Train ML classifiers using the ingested protocol corpus."""
    from protocol_training.train_classifier import train_all

    try:
        results = train_all()
        return {
            name: (path is not None)
            for name, path in results.items()
        }
    except Exception as e:
        logger.error(f'[ProtocolTask] Model training failed: {e}')
        return {'error': str(e)}


@celery.task(bind=True, name='tasks.protocol_training_tasks.update_reference_store')
def update_reference_store(self):
    """Reload the protocol reference store with latest corpus data."""
    from services.protocol_reference_store import reload_store

    try:
        reload_store()
        return {'success': True}
    except Exception as e:
        logger.error(f'[ProtocolTask] Reference store update failed: {e}')
        return {'error': str(e)}
