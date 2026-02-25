"""
Knowledge Graph API Routes
Endpoints for graph exploration, building, and stats.
"""

from flask import Blueprint, request, jsonify, g
from sqlalchemy.orm import joinedload

from database.models import (
    SessionLocal, GraphEntity, GraphRelation, GraphCommunity,
    GraphEntityType,
)
from services.auth_service import require_auth

graph_bp = Blueprint('graph', __name__, url_prefix='/api/graph')


@graph_bp.route('/entities', methods=['GET'])
@require_auth
def list_entities():
    """
    List graph entities with optional filters.

    Query params:
        type: entity type (person, system, process, decision, topic, org)
        search: text search in canonical_name
        community_id: filter by community
        limit: max results (default 50)
        offset: pagination offset
    """
    tenant_id = g.tenant_id
    entity_type = request.args.get('type', '').lower().strip()
    search = request.args.get('search', '').strip()
    community_id = request.args.get('community_id', '').strip()
    limit = min(int(request.args.get('limit', 50)), 200)
    offset = int(request.args.get('offset', 0))

    db = SessionLocal()
    try:
        query = db.query(GraphEntity).filter(GraphEntity.tenant_id == tenant_id)

        if entity_type:
            try:
                et = GraphEntityType(entity_type)
                query = query.filter(GraphEntity.entity_type == et)
            except ValueError:
                pass

        if search:
            query = query.filter(GraphEntity.canonical_name.ilike(f"%{search}%"))

        if community_id:
            query = query.filter(GraphEntity.community_id == community_id)

        total = query.count()
        entities = (
            query
            .order_by(GraphEntity.mention_count.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        return jsonify({
            "success": True,
            "entities": [e.to_dict() for e in entities],
            "total": total,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@graph_bp.route('/entities/<entity_id>', methods=['GET'])
@require_auth
def get_entity(entity_id):
    """Get entity detail with its relations."""
    tenant_id = g.tenant_id
    db = SessionLocal()
    try:
        entity = (
            db.query(GraphEntity)
            .filter(GraphEntity.id == entity_id, GraphEntity.tenant_id == tenant_id)
            .first()
        )
        if not entity:
            return jsonify({"error": "Entity not found"}), 404

        # Get relations
        relations = (
            db.query(GraphRelation)
            .filter(
                GraphRelation.tenant_id == tenant_id,
                (
                    (GraphRelation.source_entity_id == entity_id) |
                    (GraphRelation.target_entity_id == entity_id)
                ),
            )
            .options(
                joinedload(GraphRelation.source_entity),
                joinedload(GraphRelation.target_entity),
            )
            .all()
        )

        return jsonify({
            "success": True,
            "entity": entity.to_dict(),
            "relations": [r.to_dict() for r in relations],
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@graph_bp.route('/entities/<entity_id>/neighborhood', methods=['GET'])
@require_auth
def entity_neighborhood(entity_id):
    """Get BFS neighborhood of an entity (1-2 hops)."""
    tenant_id = g.tenant_id
    max_depth = min(int(request.args.get('depth', 2)), 3)
    db = SessionLocal()
    try:
        from services.graphrag_search_service import GraphRAGSearchService
        service = GraphRAGSearchService()
        result = service._traverse_graph([entity_id], tenant_id, db, max_depth)

        return jsonify({
            "success": True,
            "entities": result["entities"],
            "relations": result["relations"],
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@graph_bp.route('/communities', methods=['GET'])
@require_auth
def list_communities():
    """List all graph communities."""
    tenant_id = g.tenant_id
    db = SessionLocal()
    try:
        communities = (
            db.query(GraphCommunity)
            .filter(GraphCommunity.tenant_id == tenant_id)
            .order_by(GraphCommunity.entity_count.desc())
            .all()
        )
        return jsonify({
            "success": True,
            "communities": [c.to_dict() for c in communities],
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@graph_bp.route('/communities/<community_id>', methods=['GET'])
@require_auth
def get_community(community_id):
    """Get community detail with its entities."""
    tenant_id = g.tenant_id
    db = SessionLocal()
    try:
        community = (
            db.query(GraphCommunity)
            .filter(GraphCommunity.id == community_id, GraphCommunity.tenant_id == tenant_id)
            .first()
        )
        if not community:
            return jsonify({"error": "Community not found"}), 404

        entities = (
            db.query(GraphEntity)
            .filter(
                GraphEntity.tenant_id == tenant_id,
                GraphEntity.community_id == community_id,
            )
            .order_by(GraphEntity.mention_count.desc())
            .all()
        )

        return jsonify({
            "success": True,
            "community": community.to_dict(),
            "entities": [e.to_dict() for e in entities],
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@graph_bp.route('/build', methods=['POST'])
@require_auth
def build_graph():
    """
    Trigger a full graph build for the current tenant.

    Request body (optional):
        force: bool - rebuild from scratch (default false)
    """
    tenant_id = g.tenant_id
    data = request.get_json() or {}
    force = data.get('force', False)

    db = SessionLocal()
    try:
        from services.graph_builder_service import GraphBuilderService
        service = GraphBuilderService()
        result = service.build_graph(tenant_id=tenant_id, db=db, force=force)
        return jsonify({"success": True, **result})
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@graph_bp.route('/stats', methods=['GET'])
@require_auth
def graph_stats():
    """Get graph statistics for the current tenant."""
    tenant_id = g.tenant_id
    db = SessionLocal()
    try:
        from services.graph_builder_service import GraphBuilderService
        service = GraphBuilderService()
        stats = service.get_graph_stats(tenant_id, db)
        return jsonify({"success": True, **stats})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()
