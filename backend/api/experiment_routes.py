"""
Experiment Suggestion API Routes
Endpoints for suggesting experiments based on research questions and available lab resources.
"""

from flask import Blueprint, request, jsonify, g
from database.models import SessionLocal
from services.auth_service import require_auth
from azure_openai_config import get_azure_client, AZURE_CHAT_DEPLOYMENT

experiment_bp = Blueprint('experiments', __name__, url_prefix='/api/experiments')


@experiment_bp.route('/suggest', methods=['POST'])
@require_auth
def suggest_experiments():
    """Suggest experiments based on research question and available resources."""
    data = request.get_json() or {}
    question = data.get('research_question', '')
    if not question:
        return jsonify({'error': 'research_question required'}), 400

    constraints = data.get('constraints', {})

    tenant_id = g.tenant_id

    # Get available resources from protocol graph
    resources = []
    db = SessionLocal()
    try:
        from services.protocol_graph_service import ProtocolGraphService
        client = get_azure_client()
        graph_service = ProtocolGraphService(client, AZURE_CHAT_DEPLOYMENT)
        graph = graph_service.query_graph(tenant_id, db)
        resources = graph.get('entities', [])
    except Exception as e:
        print(f"[ExperimentSuggest] Protocol graph query failed (continuing without): {e}")
    finally:
        db.close()

    from services.experiment_suggestion_service import ExperimentSuggestionService
    client = get_azure_client()
    service = ExperimentSuggestionService(client, AZURE_CHAT_DEPLOYMENT)
    suggestions = service.suggest_experiments(question, resources, constraints=constraints)

    return jsonify({
        'suggestions': suggestions,
        'resources_available': len(resources),
        'research_question': question,
    })
