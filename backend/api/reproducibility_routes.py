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

@reproducibility_bp.route('/categories', methods=['GET'])
def list_categories():
    """List categories with experiment counts"""
    db = SessionLocal()
    try:
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
