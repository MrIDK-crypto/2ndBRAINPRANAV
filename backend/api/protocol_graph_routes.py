"""
Protocol Knowledge Graph & ML Analysis API Routes
Endpoints for:
- Extracting entities from protocol documents and querying the knowledge graph
- ML-based protocol classification and completeness scoring
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


# ---- ML Protocol Analysis ----

@protocol_graph_bp.route('/analyze', methods=['POST'])
@require_auth
def analyze_protocol_document():
    """
    Run ML protocol analysis on a specific document.

    Uses trained content_classifier.joblib and completeness_scorer.joblib
    to classify content and score completeness. Falls back to heuristic
    analysis if models are not available.

    Request body:
        { "document_id": "<uuid>" }

    Response:
        {
            "success": true,
            "document_id": "...",
            "analysis": {
                "is_protocol": true,
                "protocol_confidence": 0.92,
                "completeness_score": 0.71,
                "models_used": {
                    "content_classifier": true,
                    "completeness_scorer": true
                }
            },
            "metadata_updated": true
        }
    """
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

        if not doc.content:
            return jsonify({'error': 'Document has no content to analyze'}), 400

        from services.ml_protocol_service import get_ml_protocol_service
        service = get_ml_protocol_service()

        analysis = service.analyze_protocol(doc.content)

        # Update doc_metadata with protocol analysis results
        metadata_updated = False
        if analysis.get('is_protocol'):
            protocol_meta = service.analyze_document_protocol_metadata(doc.content)
            if protocol_meta:
                existing_meta = doc.doc_metadata or {}
                if not isinstance(existing_meta, dict):
                    existing_meta = {}
                existing_meta.update(protocol_meta)
                doc.doc_metadata = existing_meta
                db.commit()
                metadata_updated = True

        return jsonify({
            'success': True,
            'document_id': doc_id,
            'analysis': analysis,
            'metadata_updated': metadata_updated,
        })

    except Exception as e:
        return jsonify({'error': f'Analysis failed: {str(e)}'}), 500
    finally:
        db.close()


@protocol_graph_bp.route('/analyze/batch', methods=['POST'])
@require_auth
def analyze_protocol_documents_batch():
    """
    Run ML protocol analysis on all documents for the tenant, or a subset.

    Classifies all documents as protocol/non-protocol and scores completeness
    for protocol documents. Updates doc_metadata for protocol documents.

    Request body:
        {
            "limit": 100,           // optional, max documents to process
            "force": false,         // optional, re-analyze already-tagged docs
            "document_ids": [...]   // optional, specific doc IDs to analyze
        }

    Response:
        {
            "success": true,
            "total_analyzed": 85,
            "protocols_found": 12,
            "avg_completeness": 0.64,
            "model_status": { ... }
        }
    """
    data = request.get_json() or {}
    limit = data.get('limit', 100)
    force = data.get('force', False)
    doc_ids = data.get('document_ids')

    tenant_id = g.tenant_id
    db = SessionLocal()
    try:
        # Build query
        query = db.query(Document).filter(
            Document.tenant_id == tenant_id,
            Document.is_deleted == False,
            Document.content != None,
            Document.content != ''
        )

        if doc_ids:
            query = query.filter(Document.id.in_(doc_ids))

        if not force:
            # Skip documents that already have protocol metadata
            from sqlalchemy import or_
            # Include docs that don't have doc_metadata or don't have is_protocol key
            # This is tricky with JSON columns, so we just process all and skip in-code
            pass

        documents = query.limit(limit).all()

        from services.ml_protocol_service import get_ml_protocol_service
        service = get_ml_protocol_service()

        total_analyzed = 0
        protocols_found = 0
        completeness_scores = []

        for doc in documents:
            if not doc.content or len(doc.content) < 50:
                continue

            # Skip already-tagged unless force
            existing_meta = doc.doc_metadata or {}
            if not force and isinstance(existing_meta, dict) and existing_meta.get('is_protocol') is not None:
                continue

            total_analyzed += 1
            protocol_meta = service.analyze_document_protocol_metadata(doc.content)

            if protocol_meta:
                protocols_found += 1
                completeness_scores.append(protocol_meta['protocol_completeness_score'])

                if not isinstance(existing_meta, dict):
                    existing_meta = {}
                existing_meta.update(protocol_meta)
                doc.doc_metadata = existing_meta
            else:
                # Mark as non-protocol so we don't re-check
                if not isinstance(existing_meta, dict):
                    existing_meta = {}
                existing_meta['is_protocol'] = False
                doc.doc_metadata = existing_meta

        db.commit()

        avg_completeness = (
            round(sum(completeness_scores) / len(completeness_scores), 3)
            if completeness_scores else None
        )

        return jsonify({
            'success': True,
            'total_analyzed': total_analyzed,
            'protocols_found': protocols_found,
            'avg_completeness': avg_completeness,
            'completeness_scores': {
                'min': round(min(completeness_scores), 3) if completeness_scores else None,
                'max': round(max(completeness_scores), 3) if completeness_scores else None,
                'avg': avg_completeness,
            },
            'model_status': service.get_model_status(),
        })

    except Exception as e:
        db.rollback()
        return jsonify({'error': f'Batch analysis failed: {str(e)}'}), 500
    finally:
        db.close()


@protocol_graph_bp.route('/ml-status', methods=['GET'])
@require_auth
def get_protocol_ml_status():
    """
    Get the status of ML protocol models (loaded, available, paths).

    Response:
        {
            "success": true,
            "models": {
                "content_classifier": {
                    "path": "...",
                    "file_exists": true,
                    "loaded": true,
                    "attempted": true
                },
                "completeness_scorer": { ... }
            },
            "joblib_available": true
        }
    """
    try:
        from services.ml_protocol_service import get_ml_protocol_service
        service = get_ml_protocol_service()
        status = service.get_model_status()
        return jsonify({'success': True, **status})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@protocol_graph_bp.route('/analyze/text', methods=['POST'])
@require_auth
def analyze_protocol_text():
    """
    Analyze raw text for protocol content (no document required).

    Useful for testing the ML models or classifying pasted text.

    Request body:
        { "text": "Add 10 uL of sample to the tube..." }

    Response:
        {
            "success": true,
            "analysis": {
                "is_protocol": true,
                "protocol_confidence": 0.95,
                "completeness_score": 0.43,
                "models_used": { ... }
            }
        }
    """
    data = request.get_json() or {}
    text = data.get('text', '')
    if not text or len(text) < 10:
        return jsonify({'error': 'text must be at least 10 characters'}), 400

    try:
        from services.ml_protocol_service import get_ml_protocol_service
        service = get_ml_protocol_service()
        analysis = service.analyze_protocol(text)
        return jsonify({'success': True, 'analysis': analysis})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@protocol_graph_bp.route('/reload-models', methods=['POST'])
@require_auth
def reload_protocol_models():
    """
    Force reload ML protocol models (e.g., after retraining).

    Response:
        { "success": true, "model_status": { ... } }
    """
    try:
        from services.ml_protocol_service import reload_ml_protocol_service, get_ml_protocol_service
        reload_ml_protocol_service()
        service = get_ml_protocol_service()
        # Trigger lazy load so status reflects reality
        _ = service.classify_content("test text for model loading")
        return jsonify({'success': True, 'model_status': service.get_model_status()})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
