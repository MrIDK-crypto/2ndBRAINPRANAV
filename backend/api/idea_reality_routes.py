"""
Idea Reality API Routes
Validates research ideas against GitHub, PyPI, and web sources.
Returns JSON (not SSE) with reality signal, competitors, and verdict.
"""

from flask import Blueprint, request, jsonify

from services.auth_service import require_auth
from services.idea_reality_service import get_idea_reality_service

idea_reality_bp = Blueprint('idea_reality', __name__, url_prefix='/api/idea-reality')


@idea_reality_bp.route('/check', methods=['POST'])
@require_auth
def check_idea():
    """Check if similar implementations of a research idea already exist."""
    data = request.get_json() or {}
    idea = (data.get('idea') or '').strip()
    depth = (data.get('depth') or 'standard').strip()

    if len(idea) < 10:
        return jsonify({
            'success': False,
            'error': f'Idea description must be at least 10 characters (currently {len(idea)}).',
        }), 400

    try:
        service = get_idea_reality_service()
        result = service.check_idea(idea)
        return jsonify({
            'success': True,
            **result,
        })
    except Exception as e:
        print(f"[IdeaReality] Check error: {e}", flush=True)
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500
