"""
Celery Tasks for HIJ (High Impact Journal) Model Training
==========================================================
Background tasks for generating training data from OpenAlex and training
the paper type classifier and journal tier predictor models.
"""

import os
import sys
import logging
import time

from celery_app import celery

logger = logging.getLogger(__name__)


def _ensure_app_in_path():
    """Ensure /app is in sys.path — Celery prefork workers lose it after fork."""
    app_dir = '/app'
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)


@celery.task(
    bind=True,
    name='tasks.hij_training_tasks.train_hij_models',
    time_limit=10800,        # 3 hour hard limit
    soft_time_limit=10500,   # 2h55m soft limit (warning)
    max_retries=1,
)
def train_hij_models(self, target_papers=5000):
    """
    Full HIJ training pipeline: generate data from OpenAlex + train both models.

    Steps:
        1. Generate training data from OpenAlex (paper type + tier labels)
        2. Train Paper Type Classifier (TF-IDF + LogReg)
        3. Train Journal Tier Predictor (TF-IDF + LogReg)

    Args:
        target_papers: Target number of training papers to fetch (default 5000)

    Returns:
        dict with keys: data_generated, paper_type_metrics, tier_metrics, elapsed_seconds
    """
    _ensure_app_in_path()

    from pathlib import Path

    start_time = time.time()
    results = {
        'data_generated': False,
        'paper_type_metrics': None,
        'tier_metrics': None,
        'elapsed_seconds': 0,
    }

    # Resolve directories relative to backend/
    backend_dir = Path(__file__).resolve().parent.parent
    data_dir = backend_dir / 'data' / 'oncology_training'
    model_dir = backend_dir / 'models'

    # ── Step 1: Generate training data from OpenAlex ──────────────────
    logger.info('[HIJTask] Step 1/3: Generating training data from OpenAlex (target=%d)', target_papers)
    self.update_state(state='PROGRESS', meta={
        'current': 0, 'total': 3, 'percent': 0,
        'status': f'Generating training data ({target_papers} papers)...',
    })

    try:
        from scripts.generate_training_data import generate_training_data
        generate_training_data(data_dir, target_total=target_papers)
        results['data_generated'] = True
        logger.info('[HIJTask] Training data generated in %s', data_dir)
    except Exception as e:
        logger.error('[HIJTask] Data generation failed: %s', e, exc_info=True)
        results['data_generation_error'] = str(e)
        # If data already exists from a previous run, continue with training
        if not (data_dir / 'train.jsonl').exists():
            results['elapsed_seconds'] = round(time.time() - start_time, 1)
            return results

    # ── Step 2: Train Paper Type Classifier ───────────────────────────
    logger.info('[HIJTask] Step 2/3: Training Paper Type Classifier')
    self.update_state(state='PROGRESS', meta={
        'current': 1, 'total': 3, 'percent': 33,
        'status': 'Training paper type classifier...',
    })

    try:
        from scripts.train_hij_models import train_paper_type_classifier
        pt_metrics = train_paper_type_classifier(data_dir, model_dir)
        if pt_metrics:
            results['paper_type_metrics'] = {
                'test_accuracy': round(pt_metrics['test_acc'], 4),
                'test_f1_macro': round(pt_metrics['test_f1'], 4),
                'best_C': pt_metrics['best_c'],
            }
            logger.info(
                '[HIJTask] Paper type classifier: acc=%.4f, F1=%.4f',
                pt_metrics['test_acc'], pt_metrics['test_f1'],
            )
        else:
            logger.warning('[HIJTask] Paper type classifier returned no metrics (no data?)')
    except Exception as e:
        logger.error('[HIJTask] Paper type classifier training failed: %s', e, exc_info=True)
        results['paper_type_error'] = str(e)

    # ── Step 3: Train Tier Predictor ──────────────────────────────────
    logger.info('[HIJTask] Step 3/3: Training Journal Tier Predictor')
    self.update_state(state='PROGRESS', meta={
        'current': 2, 'total': 3, 'percent': 66,
        'status': 'Training tier predictor...',
    })

    try:
        from scripts.train_hij_models import train_tier_predictor
        tier_metrics = train_tier_predictor(data_dir, model_dir)
        if tier_metrics:
            results['tier_metrics'] = {
                'test_accuracy': round(tier_metrics['test_acc'], 4),
                'test_f1_macro': round(tier_metrics['test_f1'], 4),
                'best_C': tier_metrics['best_c'],
            }
            logger.info(
                '[HIJTask] Tier predictor: acc=%.4f, F1=%.4f',
                tier_metrics['test_acc'], tier_metrics['test_f1'],
            )
        else:
            logger.warning('[HIJTask] Tier predictor returned no metrics (no data?)')
    except Exception as e:
        logger.error('[HIJTask] Tier predictor training failed: %s', e, exc_info=True)
        results['tier_error'] = str(e)

    # ── Summary ───────────────────────────────────────────────────────
    elapsed = time.time() - start_time
    results['elapsed_seconds'] = round(elapsed, 1)

    logger.info(
        '[HIJTask] Pipeline complete in %.1fs (%.1f min). '
        'data=%s, paper_type=%s, tier=%s',
        elapsed, elapsed / 60,
        results['data_generated'],
        results['paper_type_metrics'] is not None,
        results['tier_metrics'] is not None,
    )

    return results
