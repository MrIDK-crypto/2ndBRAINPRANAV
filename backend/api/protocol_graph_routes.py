"""
Protocol Knowledge Graph API Routes
Endpoints for extracting entities from protocol documents and querying the knowledge graph.
"""

from flask import Blueprint, request, jsonify, g
from database.models import SessionLocal, Document
from services.auth_service import require_auth
from azure_openai_config import get_azure_client, AZURE_CHAT_DEPLOYMENT

protocol_graph_bp = Blueprint('protocol_graph', __name__, url_prefix='/api/protocols')


# ---- Protocol Knowledge Graph ----

@protocol_graph_bp.route('/graph', methods=['GET'])
@require_auth
def get_protocol_graph():
    """Query the protocol knowledge graph for this tenant."""
    tenant_id = g.tenant_id
    entity_name = request.args.get('entity')
    entity_type = request.args.get('type')

    db = SessionLocal()
    try:
        from services.protocol_graph_service import ProtocolGraphService
        client = get_azure_client()
        service = ProtocolGraphService(client, AZURE_CHAT_DEPLOYMENT)
        graph = service.query_graph(tenant_id, db, entity_name, entity_type)
        return jsonify(graph)
    finally:
        db.close()


@protocol_graph_bp.route('/extract', methods=['POST'])
@require_auth
def extract_protocol_entities():
    """Extract entities from a specific document into the protocol graph."""
    data = request.get_json() or {}
    doc_id = data.get('document_id')
    if not doc_id:
        return jsonify({'error': 'document_id required'}), 400

    tenant_id = g.tenant_id
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(
            Document.id == doc_id,
            Document.tenant_id == tenant_id
        ).first()
        if not doc:
            return jsonify({'error': 'Document not found'}), 404

        from services.protocol_graph_service import ProtocolGraphService
        client = get_azure_client()
        service = ProtocolGraphService(client, AZURE_CHAT_DEPLOYMENT)
        entities = service.extract_entities_from_document(doc, tenant_id, db)
        return jsonify({'entities_extracted': len(entities), 'entities': entities})
    finally:
        db.close()
