"""
Seed the Reproducibility Archive with verified failed experiments
Run: python -m scripts.seed_reproducibility [--clear]
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from database.models import (
    SessionLocal, FailedExperiment, ExperimentCategory, ExperimentComment,
    generate_uuid, init_database
)
from scrapers.verified_experiments import get_all_verified_experiments
from scrapers.null_results_experiments import get_all_null_result_experiments
from scrapers.expanded_experiments import get_all_expanded_experiments
from scrapers.scraped_experiments import get_all_scraped_experiments


CATEGORIES = [
    ('Social Psychology', 'Interpersonal behavior, attitudes, social cognition'),
    ('Cognitive Psychology', 'Memory, attention, perception, decision-making'),
    ('Developmental Psychology', 'Human development across the lifespan'),
    ('Clinical Psychology', 'Mental health, psychopathology, treatment'),
    ('Personality Psychology', 'Individual differences, traits, assessment'),
    ('Neuroscience', 'Brain-behavior relationships'),
    ('Educational Psychology', 'Learning, instruction, academic achievement'),
    ('Industrial-Organizational', 'Workplace behavior, management, HR'),
    ('Health Psychology', 'Health behaviors, illness, medical settings'),
    ('Other', 'Experiments that don\'t fit other categories'),
]


def seed_categories(db):
    """Seed psychology categories"""
    for name, description in CATEGORIES:
        existing = db.query(ExperimentCategory).filter(ExperimentCategory.name == name).first()
        if not existing:
            db.add(ExperimentCategory(
                id=generate_uuid(),
                name=name,
                description=description,
                experiment_count=0
            ))
    db.commit()
    print(f"  Categories: {len(CATEGORIES)} ensured")


def seed_experiments(db):
    """Seed experiments from all scraper sources"""
    all_experiments = []
    sources = [
        ('Verified replications (OSF)', get_all_verified_experiments),
        ('JASNH null results', get_all_null_result_experiments),
        ('Expanded experiments', get_all_expanded_experiments),
        ('Scraped from journals', get_all_scraped_experiments),
    ]

    for label, getter in sources:
        try:
            exps = getter()
            all_experiments.extend(exps)
            print(f"  {label}: {len(exps)}")
        except Exception as e:
            print(f"  {label}: FAILED - {e}")

    added = 0
    skipped = 0

    for exp_data in all_experiments:
        source_url = exp_data.get('source_url', '')
        title = exp_data.get('title', '')

        # Deduplicate by source_url or title
        if source_url:
            existing = db.query(FailedExperiment).filter(
                FailedExperiment.source_url == source_url
            ).first()
            if existing:
                skipped += 1
                continue

        existing = db.query(FailedExperiment).filter(
            FailedExperiment.title == title
        ).first()
        if existing:
            skipped += 1
            continue

        db.add(FailedExperiment(
            id=generate_uuid(),
            anonymous_id='system',
            field='psychology',
            category=exp_data.get('category', 'Social Psychology'),
            title=title,
            hypothesis=exp_data.get('hypothesis', ''),
            sample_size=exp_data.get('sample_size'),
            design_type=exp_data.get('design_type', ''),
            methodology=exp_data.get('methodology', ''),
            what_failed=exp_data.get('what_failed', ''),
            why_failed=exp_data.get('why_failed', ''),
            lessons_learned=exp_data.get('lessons_learned', ''),
            original_study_doi=exp_data.get('original_study_doi', ''),
            original_study_citation=exp_data.get('original_study_citation', ''),
            source_url=source_url,
            is_seeded=True,
            status='published',
            upvotes=0,
            view_count=0,
        ))
        added += 1

    db.commit()

    # Update category counts
    categories = db.query(ExperimentCategory).all()
    for cat in categories:
        count = db.query(FailedExperiment).filter(
            FailedExperiment.category == cat.name,
            FailedExperiment.status == 'published'
        ).count()
        cat.experiment_count = count
    db.commit()

    print(f"\n  Added: {added} | Skipped: {skipped} duplicates")
    return added


def clear_seeded(db):
    """Clear only seeded experiments"""
    deleted = db.query(FailedExperiment).filter(
        FailedExperiment.is_seeded == True
    ).delete()
    db.commit()
    print(f"  Cleared {deleted} seeded experiments")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Seed Reproducibility Archive')
    parser.add_argument('--clear', action='store_true', help='Clear seeded experiments first')
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("  Reproducibility Archive - Database Seeder")
    print("=" * 60)

    init_database()

    db = SessionLocal()
    try:
        if args.clear:
            clear_seeded(db)

        seed_categories(db)
        seed_experiments(db)

        total = db.query(FailedExperiment).filter(
            FailedExperiment.status == 'published'
        ).count()
        print(f"\n  Total experiments: {total}")

        # Category breakdown
        categories = db.query(ExperimentCategory).all()
        for cat in categories:
            if cat.experiment_count > 0:
                print(f"    {cat.name}: {cat.experiment_count}")

    finally:
        db.close()

    print("=" * 60 + "\n")
