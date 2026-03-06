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
    """Clear ALL experiments to allow fresh re-seeding with updated data"""
    # Clear comments first (foreign key)
    deleted_comments = db.query(ExperimentComment).delete()
    # Clear all experiments (not just is_seeded=True)
    deleted = db.query(FailedExperiment).delete()
    db.commit()
    print(f"  Cleared {deleted} experiments and {deleted_comments} comments")


# Realistic comments from researchers
SAMPLE_COMMENTS = [
    # General replication comments
    "We tried replicating this in our lab last semester and got similar null results. The effect size was basically zero even with n=400.",
    "This matches what we found. I think the original study had serious demand characteristics that inflated the effect.",
    "Ran this as part of a methods class - students were shocked when it didn't replicate. Great teaching moment about publication bias.",
    "The statistical power in the original was way too low. Not surprising this didn't hold up.",
    "We need more null results like this published. The file drawer problem is real.",

    # Methodological critiques
    "Looking at the original methods, the manipulation check was weak. No wonder it doesn't replicate.",
    "I wonder if this is a WEIRD sample problem - the original was all undergrads from one university.",
    "The effect might be real but much smaller than originally claimed. Classic winner's curse.",
    "Has anyone tried this with a pre-registered design? Would love to see a definitive test.",
    "The original p-value was .048 - classic p-hacking territory.",

    # Personal experiences
    "Spent 6 months on my thesis trying to replicate a version of this. Wish I'd seen this earlier.",
    "My advisor still cites the original. Sending them this link...",
    "This is why I switched to computational methods. At least the code either works or it doesn't.",
    "Failed to replicate this three times before finding this archive. Thank you for saving others the trouble.",
    "We actually found the opposite effect in our sample. Publication bias works both ways I guess.",

    # Constructive suggestions
    "Maybe worth trying with a more sensitive measure? The DV in most replications seems noisy.",
    "I think the boundary conditions are narrower than originally thought. Works in some contexts but not others.",
    "Would be interesting to see a meta-analysis of all these failed replications.",
    "The theory might still be salvageable even if this specific operationalization doesn't work.",
    "Has anyone contacted the original authors? Would be good to get their perspective.",

    # Humor/frustration
    "Another day, another failed replication. At least we're documenting it now.",
    "Psychology's greatest hits: things that don't replicate, volume 47.",
    "My PhD in three words: 'did not replicate'",
    "Plot twist: the replication crisis was the friends we made along the way.",
    "At this point I'm more surprised when something DOES replicate.",

    # Specific technical comments
    "The effect disappears completely when you control for participant attention.",
    "Tried online vs. in-lab - no difference, still null.",
    "Even with double the sample size, confidence interval still includes zero.",
    "Bayesian analysis strongly favors the null hypothesis here.",
    "Multi-site replication across 5 universities, all null. It's not a fluke.",
]

import random

def seed_comments(db):
    """Add realistic sample comments to some experiments"""
    experiments = db.query(FailedExperiment).filter(
        FailedExperiment.status == 'published'
    ).all()

    if not experiments:
        print("  No experiments to add comments to")
        return

    # Add comments to ~30% of experiments (random selection)
    num_to_comment = max(1, len(experiments) // 3)
    selected = random.sample(experiments, min(num_to_comment, len(experiments)))

    total_comments = 0
    for exp in selected:
        # Add 1-4 comments per experiment
        num_comments = random.randint(1, 4)
        chosen_comments = random.sample(SAMPLE_COMMENTS, min(num_comments, len(SAMPLE_COMMENTS)))

        for content in chosen_comments:
            db.add(ExperimentComment(
                id=generate_uuid(),
                experiment_id=exp.id,
                anonymous_id=f'anon_{random.randint(1000, 9999)}',
                content=content,
                upvotes=random.randint(0, 15),
                status='published'
            ))
            total_comments += 1

    db.commit()
    print(f"  Added {total_comments} comments to {len(selected)} experiments")


if __name__ == '__main__':
    import argparse
    import traceback

    parser = argparse.ArgumentParser(description='Seed Reproducibility Archive')
    parser.add_argument('--clear', action='store_true', help='Clear seeded experiments first')
    args = parser.parse_args()

    print("\n" + "=" * 60, flush=True)
    print("  Reproducibility Archive - Database Seeder", flush=True)
    print("=" * 60, flush=True)

    try:
        print("  Initializing database...", flush=True)
        init_database()
        print("  Database initialized.", flush=True)

        db = SessionLocal()
        try:
            if args.clear:
                print("  Clearing existing data...", flush=True)
                clear_seeded(db)

            print("  Seeding categories...", flush=True)
            seed_categories(db)

            print("  Seeding experiments...", flush=True)
            seed_experiments(db)

            total = db.query(FailedExperiment).filter(
                FailedExperiment.status == 'published'
            ).count()
            print(f"\n  Total experiments: {total}", flush=True)

            # Verify source_url values
            with_url = db.query(FailedExperiment).filter(
                FailedExperiment.source_url.isnot(None),
                FailedExperiment.source_url != ''
            ).count()
            print(f"  With source_url: {with_url}", flush=True)

            # Category breakdown
            categories = db.query(ExperimentCategory).all()
            for cat in categories:
                if cat.experiment_count > 0:
                    print(f"    {cat.name}: {cat.experiment_count}", flush=True)

        finally:
            db.close()

        print("=" * 60 + "\n", flush=True)
        print("  SEEDING COMPLETED SUCCESSFULLY", flush=True)

    except Exception as e:
        print(f"\n  ERROR: {e}", flush=True)
        traceback.print_exc()
        raise
