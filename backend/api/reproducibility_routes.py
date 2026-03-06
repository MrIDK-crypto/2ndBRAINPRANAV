"""
Reproducibility Archive API Routes
Public endpoints - no authentication required
"""

from flask import Blueprint, request, jsonify
from sqlalchemy import func
from database.models import (
    SessionLocal, FailedExperiment, ExperimentComment, ExperimentCategory, generate_uuid
)
from datetime import datetime
import hashlib

reproducibility_bp = Blueprint('reproducibility', __name__, url_prefix='/api/reproducibility')


def get_anonymous_id():
    """Generate anonymous ID from request headers (no IP logging)"""
    user_agent = request.headers.get('User-Agent', '')
    session_key = request.headers.get('X-Session-Key', str(datetime.now().date()))
    raw = f"{user_agent}:{session_key}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ============ Experiments ============

@reproducibility_bp.route('/experiments', methods=['GET'])
def list_experiments():
    """List published experiments with filters"""
    db = SessionLocal()
    try:
        query = db.query(FailedExperiment).filter(FailedExperiment.status == 'published')

        # Category filter
        category = request.args.get('category')
        if category:
            query = query.filter(FailedExperiment.category == category)

        # Search
        search = request.args.get('search')
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                (FailedExperiment.title.ilike(search_term)) |
                (FailedExperiment.what_failed.ilike(search_term)) |
                (FailedExperiment.hypothesis.ilike(search_term))
            )

        # Sort
        sort = request.args.get('sort', 'recent')
        if sort == 'recent':
            query = query.order_by(FailedExperiment.created_at.desc())
        elif sort == 'popular':
            query = query.order_by(FailedExperiment.upvotes.desc())
        elif sort == 'views':
            query = query.order_by(FailedExperiment.view_count.desc())

        # Pagination
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        offset = (page - 1) * per_page
        total = query.count()

        experiments = query.offset(offset).limit(per_page).all()

        return jsonify({
            'success': True,
            'experiments': [e.to_dict() for e in experiments],
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page,
            'has_contributed': True,
            'gated': False,
        })
    finally:
        db.close()


@reproducibility_bp.route('/experiments/<experiment_id>', methods=['GET'])
def get_experiment(experiment_id):
    """Get a single experiment with comments"""
    db = SessionLocal()
    try:
        experiment = db.query(FailedExperiment).filter(
            FailedExperiment.id == experiment_id
        ).first()

        if not experiment:
            return jsonify({'success': False, 'error': 'Experiment not found'}), 404

        experiment.view_count += 1
        db.commit()

        comments = db.query(ExperimentComment).filter(
            ExperimentComment.experiment_id == experiment_id,
            ExperimentComment.status == 'published'
        ).order_by(ExperimentComment.created_at.desc()).all()

        result = experiment.to_dict()
        result['comments'] = [c.to_dict() for c in comments]

        return jsonify({'success': True, 'experiment': result})
    finally:
        db.close()


@reproducibility_bp.route('/experiments', methods=['POST'])
def create_experiment():
    """Submit a new failed experiment (anonymous)"""
    db = SessionLocal()
    try:
        data = request.json
        anonymous_id = get_anonymous_id()

        experiment = FailedExperiment(
            id=generate_uuid(),
            anonymous_id=anonymous_id,
            field=data.get('field', 'psychology'),
            category=data.get('category'),
            title=data.get('title'),
            hypothesis=data.get('hypothesis'),
            sample_size=data.get('sample_size'),
            design_type=data.get('design_type'),
            methodology=data.get('methodology'),
            materials=data.get('materials'),
            what_failed=data.get('what_failed'),
            why_failed=data.get('why_failed'),
            lessons_learned=data.get('lessons_learned'),
            original_study_doi=data.get('original_study_doi'),
            original_study_citation=data.get('original_study_citation'),
            is_seeded=False,
            status='published'
        )

        db.add(experiment)

        if experiment.category:
            category = db.query(ExperimentCategory).filter(
                ExperimentCategory.name == experiment.category
            ).first()
            if category:
                category.experiment_count += 1

        db.commit()

        return jsonify({
            'success': True,
            'experiment': experiment.to_dict(),
        })
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400
    finally:
        db.close()


@reproducibility_bp.route('/experiments/<experiment_id>/upvote', methods=['POST'])
def upvote_experiment(experiment_id):
    """Upvote an experiment"""
    db = SessionLocal()
    try:
        experiment = db.query(FailedExperiment).filter(
            FailedExperiment.id == experiment_id
        ).first()

        if not experiment:
            return jsonify({'success': False, 'error': 'Experiment not found'}), 404

        experiment.upvotes += 1
        db.commit()

        return jsonify({'success': True, 'upvotes': experiment.upvotes})
    finally:
        db.close()


# ============ Comments ============

@reproducibility_bp.route('/experiments/<experiment_id>/comments', methods=['POST'])
def add_comment(experiment_id):
    """Add anonymous comment"""
    db = SessionLocal()
    try:
        data = request.json
        anonymous_id = get_anonymous_id()

        experiment = db.query(FailedExperiment).filter(
            FailedExperiment.id == experiment_id
        ).first()

        if not experiment:
            return jsonify({'success': False, 'error': 'Experiment not found'}), 404

        comment = ExperimentComment(
            id=generate_uuid(),
            experiment_id=experiment_id,
            anonymous_id=anonymous_id,
            content=data.get('content'),
            status='published'
        )

        db.add(comment)
        db.commit()

        return jsonify({'success': True, 'comment': comment.to_dict()})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400
    finally:
        db.close()


# ============ Categories ============

CATEGORY_DESCRIPTIONS = {
    'Social Psychology': 'Interpersonal behavior, attitudes, social cognition',
    'Cognitive Psychology': 'Memory, attention, perception, decision-making',
    'Developmental Psychology': 'Human development across the lifespan',
    'Clinical Psychology': 'Mental health, psychopathology, treatment',
    'Personality Psychology': 'Individual differences, traits, assessment',
    'Neuroscience': 'Brain-behavior relationships',
    'Educational Psychology': 'Learning, instruction, academic achievement',
    'Industrial-Organizational': 'Workplace behavior, management, HR',
    'Health Psychology': 'Health behaviors, illness, medical settings',
    'Other': "Experiments that don't fit other categories",
}


@reproducibility_bp.route('/categories', methods=['GET'])
def list_categories():
    """List categories with experiment counts"""
    db = SessionLocal()
    try:
        categories = db.query(ExperimentCategory).all()

        # Auto-seed categories if table is empty
        if not categories:
            for name, desc in CATEGORY_DESCRIPTIONS.items():
                db.add(ExperimentCategory(
                    id=generate_uuid(), name=name, description=desc, experiment_count=0
                ))
            db.commit()
            categories = db.query(ExperimentCategory).all()

        for cat in categories:
            count = db.query(FailedExperiment).filter(
                FailedExperiment.category == cat.name,
                FailedExperiment.status == 'published'
            ).count()
            cat.experiment_count = count

        return jsonify({
            'success': True,
            'categories': [c.to_dict() for c in categories]
        })
    finally:
        db.close()


# ============ Stats ============

@reproducibility_bp.route('/stats', methods=['GET'])
def get_stats():
    """Get platform statistics"""
    db = SessionLocal()
    try:
        total_experiments = db.query(FailedExperiment).filter(
            FailedExperiment.status == 'published'
        ).count()

        total_comments = db.query(ExperimentComment).filter(
            ExperimentComment.status == 'published'
        ).count()

        total_upvotes = db.query(func.sum(FailedExperiment.upvotes)).scalar() or 0

        return jsonify({
            'success': True,
            'stats': {
                'total_experiments': total_experiments,
                'total_comments': total_comments,
                'total_upvotes': total_upvotes,
            }
        })
    finally:
        db.close()


# ============ Admin/Debug ============

@reproducibility_bp.route('/admin/seed', methods=['POST'])
def trigger_seed():
    """Manually trigger database seeding (for debugging deployment issues)"""
    import sys
    import os
    from io import StringIO

    # Capture output
    output = StringIO()
    old_stdout = sys.stdout
    sys.stdout = output

    try:
        # Import and run seed functions
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
        from scripts.seed_reproducibility import (
            clear_seeded, seed_categories, seed_experiments
        )
        from database.models import SessionLocal, FailedExperiment

        db = SessionLocal()
        try:
            # Clear existing data
            print("Clearing existing data...")
            clear_seeded(db)

            # Seed categories and experiments
            print("Seeding categories...")
            seed_categories(db)

            print("Seeding experiments...")
            seed_experiments(db)

            # Verify
            total = db.query(FailedExperiment).count()
            with_url = db.query(FailedExperiment).filter(
                FailedExperiment.source_url.isnot(None),
                FailedExperiment.source_url != ''
            ).count()
            is_seeded_count = db.query(FailedExperiment).filter(
                FailedExperiment.is_seeded == True
            ).count()

            print(f"Total experiments: {total}")
            print(f"With source_url: {with_url}")
            print(f"With is_seeded=True: {is_seeded_count}")

        finally:
            db.close()

        sys.stdout = old_stdout
        return jsonify({
            'success': True,
            'output': output.getvalue()
        })

    except Exception as e:
        sys.stdout = old_stdout
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc(),
            'output': output.getvalue()
        }), 500


@reproducibility_bp.route('/admin/db-status', methods=['GET'])
def db_status():
    """Check database status for debugging"""
    db = SessionLocal()
    try:
        total = db.query(FailedExperiment).count()
        published = db.query(FailedExperiment).filter(
            FailedExperiment.status == 'published'
        ).count()
        is_seeded_true = db.query(FailedExperiment).filter(
            FailedExperiment.is_seeded == True
        ).count()
        is_seeded_false = db.query(FailedExperiment).filter(
            FailedExperiment.is_seeded == False
        ).count()
        with_source_url = db.query(FailedExperiment).filter(
            FailedExperiment.source_url.isnot(None),
            FailedExperiment.source_url != ''
        ).count()

        # Get a sample experiment
        sample = db.query(FailedExperiment).first()
        sample_data = None
        if sample:
            sample_data = {
                'id': sample.id,
                'title': sample.title[:50] if sample.title else None,
                'is_seeded': sample.is_seeded,
                'source_url': sample.source_url,
                'created_at': str(sample.created_at) if sample.created_at else None
            }

        return jsonify({
            'success': True,
            'db_status': {
                'total_experiments': total,
                'published': published,
                'is_seeded_true': is_seeded_true,
                'is_seeded_false': is_seeded_false,
                'with_source_url': with_source_url,
                'sample_experiment': sample_data
            }
        })
    finally:
        db.close()
