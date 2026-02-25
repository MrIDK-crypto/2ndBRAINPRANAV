"""
Knowledge Atom API Routes
CRUD for atoms + link management + extraction trigger.
"""

from flask import Blueprint, request, jsonify, g
from sqlalchemy.orm import joinedload

from database.models import (
    SessionLocal, KnowledgeAtom, AtomLink,
    AtomType, AtomLinkType,
    utc_now, generate_uuid,
)
from services.auth_service import require_auth

atom_bp = Blueprint('atoms', __name__, url_prefix='/api/atoms')


@atom_bp.route('', methods=['GET'])
@require_auth
def list_atoms():
    """
    List Knowledge Atoms with optional filters.

    Query params:
        type: atom type filter (concept, decision, process, fact, insight, definition)
        project_id: filter by project
        search: text search in title/content
        limit: max results (default 50)
        offset: pagination offset
    """
    tenant_id = g.tenant_id
    atom_type = request.args.get('type', '').lower().strip()
    project_id = request.args.get('project_id', '').strip()
    search = request.args.get('search', '').strip()
    limit = min(int(request.args.get('limit', 50)), 200)
    offset = int(request.args.get('offset', 0))

    db = SessionLocal()
    try:
        query = (
            db.query(KnowledgeAtom)
            .filter(
                KnowledgeAtom.tenant_id == tenant_id,
                KnowledgeAtom.is_deleted == False,
            )
        )

        if atom_type:
            try:
                at = AtomType(atom_type)
                query = query.filter(KnowledgeAtom.atom_type == at)
            except ValueError:
                pass

        if project_id:
            query = query.filter(KnowledgeAtom.project_id == project_id)

        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                KnowledgeAtom.title.ilike(search_pattern) |
                KnowledgeAtom.content.ilike(search_pattern)
            )

        total = query.count()
        atoms = (
            query
            .order_by(KnowledgeAtom.is_pinned.desc(), KnowledgeAtom.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        return jsonify({
            "success": True,
            "atoms": [a.to_dict() for a in atoms],
            "total": total,
            "limit": limit,
            "offset": offset,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@atom_bp.route('/<atom_id>', methods=['GET'])
@require_auth
def get_atom(atom_id):
    """Get a single atom with its bidirectional links."""
    tenant_id = g.tenant_id
    db = SessionLocal()
    try:
        atom = (
            db.query(KnowledgeAtom)
            .options(
                joinedload(KnowledgeAtom.outgoing_links).joinedload(AtomLink.target_atom),
                joinedload(KnowledgeAtom.incoming_links).joinedload(AtomLink.source_atom),
            )
            .filter(
                KnowledgeAtom.id == atom_id,
                KnowledgeAtom.tenant_id == tenant_id,
                KnowledgeAtom.is_deleted == False,
            )
            .first()
        )
        if not atom:
            return jsonify({"error": "Atom not found"}), 404

        # Increment view count
        atom.view_count = (atom.view_count or 0) + 1
        db.commit()

        return jsonify({
            "success": True,
            "atom": atom.to_dict(include_links=True),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@atom_bp.route('', methods=['POST'])
@require_auth
def create_atom():
    """
    Create a manual Knowledge Atom.

    Request body:
        title: str (required)
        content: str (required)
        atom_type: str (default "concept")
        project_id: str (optional)
    """
    tenant_id = g.tenant_id
    data = request.get_json()

    title = (data.get('title') or '').strip()
    content = (data.get('content') or '').strip()
    if not title or not content:
        return jsonify({"error": "Title and content are required"}), 400

    atom_type_str = (data.get('atom_type') or 'concept').lower()
    try:
        at = AtomType(atom_type_str)
    except ValueError:
        at = AtomType.CONCEPT

    db = SessionLocal()
    try:
        atom = KnowledgeAtom(
            id=generate_uuid(),
            tenant_id=tenant_id,
            title=title,
            content=content,
            atom_type=at,
            is_manual=True,
            project_id=data.get('project_id'),
            extraction_confidence=1.0,
        )
        db.add(atom)
        db.commit()

        return jsonify({"success": True, "atom": atom.to_dict()}), 201
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@atom_bp.route('/<atom_id>', methods=['PUT'])
@require_auth
def update_atom(atom_id):
    """Update an atom's title, content, type, or pin status."""
    tenant_id = g.tenant_id
    data = request.get_json()

    db = SessionLocal()
    try:
        atom = (
            db.query(KnowledgeAtom)
            .filter(
                KnowledgeAtom.id == atom_id,
                KnowledgeAtom.tenant_id == tenant_id,
                KnowledgeAtom.is_deleted == False,
            )
            .first()
        )
        if not atom:
            return jsonify({"error": "Atom not found"}), 404

        if 'title' in data:
            atom.title = data['title'].strip()
        if 'content' in data:
            atom.content = data['content'].strip()
        if 'atom_type' in data:
            try:
                atom.atom_type = AtomType(data['atom_type'].lower())
            except ValueError:
                pass
        if 'is_pinned' in data:
            atom.is_pinned = bool(data['is_pinned'])
        if 'project_id' in data:
            atom.project_id = data['project_id'] or None

        atom.updated_at = utc_now()
        db.commit()

        return jsonify({"success": True, "atom": atom.to_dict()})
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@atom_bp.route('/<atom_id>', methods=['DELETE'])
@require_auth
def delete_atom(atom_id):
    """Soft-delete an atom."""
    tenant_id = g.tenant_id
    db = SessionLocal()
    try:
        atom = (
            db.query(KnowledgeAtom)
            .filter(
                KnowledgeAtom.id == atom_id,
                KnowledgeAtom.tenant_id == tenant_id,
            )
            .first()
        )
        if not atom:
            return jsonify({"error": "Atom not found"}), 404

        atom.is_deleted = True
        atom.updated_at = utc_now()
        db.commit()

        return jsonify({"success": True})
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@atom_bp.route('/<atom_id>/links', methods=['POST'])
@require_auth
def create_link(atom_id):
    """
    Create a manual link from this atom to another.

    Request body:
        target_atom_id: str (required)
        link_type: str (default "related")
        reason: str (optional)
    """
    tenant_id = g.tenant_id
    data = request.get_json()
    target_id = (data.get('target_atom_id') or '').strip()

    if not target_id:
        return jsonify({"error": "target_atom_id is required"}), 400
    if target_id == atom_id:
        return jsonify({"error": "Cannot link atom to itself"}), 400

    link_type_str = (data.get('link_type') or 'related').lower()
    try:
        lt = AtomLinkType(link_type_str)
    except ValueError:
        lt = AtomLinkType.RELATED

    db = SessionLocal()
    try:
        # Verify both atoms exist and belong to tenant
        source = db.query(KnowledgeAtom).filter(KnowledgeAtom.id == atom_id, KnowledgeAtom.tenant_id == tenant_id).first()
        target = db.query(KnowledgeAtom).filter(KnowledgeAtom.id == target_id, KnowledgeAtom.tenant_id == tenant_id).first()

        if not source or not target:
            return jsonify({"error": "One or both atoms not found"}), 404

        # Check for existing link
        existing = (
            db.query(AtomLink)
            .filter(
                AtomLink.source_atom_id == atom_id,
                AtomLink.target_atom_id == target_id,
                AtomLink.link_type == lt,
            )
            .first()
        )
        if existing:
            return jsonify({"error": "Link already exists"}), 409

        link = AtomLink(
            id=generate_uuid(),
            tenant_id=tenant_id,
            source_atom_id=atom_id,
            target_atom_id=target_id,
            link_type=lt,
            is_manual=True,
            confidence=1.0,
            reason=data.get('reason', ''),
        )
        db.add(link)
        db.commit()

        return jsonify({"success": True, "link": link.to_dict()}), 201
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@atom_bp.route('/<atom_id>/links/<link_id>', methods=['DELETE'])
@require_auth
def delete_link(atom_id, link_id):
    """Delete a link."""
    tenant_id = g.tenant_id
    db = SessionLocal()
    try:
        link = (
            db.query(AtomLink)
            .filter(
                AtomLink.id == link_id,
                AtomLink.tenant_id == tenant_id,
            )
            .first()
        )
        if not link:
            return jsonify({"error": "Link not found"}), 404

        db.delete(link)
        db.commit()

        return jsonify({"success": True})
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@atom_bp.route('/extract', methods=['POST'])
@require_auth
def extract_atoms():
    """
    Trigger atom extraction for the current tenant.

    Request body (optional):
        force: bool - re-extract even if atoms already exist (default false)
        limit: int - max documents to process (default 100)
    """
    tenant_id = g.tenant_id
    data = request.get_json() or {}
    force = data.get('force', False)
    limit = min(data.get('limit', 100), 500)

    db = SessionLocal()
    try:
        from services.atom_extraction_service import AtomExtractionService
        service = AtomExtractionService()
        result = service.extract_for_tenant(
            tenant_id=tenant_id,
            db=db,
            force=force,
            limit=limit,
        )
        return jsonify({"success": True, **result})
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@atom_bp.route('/stats', methods=['GET'])
@require_auth
def atom_stats():
    """Get atom type distribution for the current tenant."""
    tenant_id = g.tenant_id
    db = SessionLocal()
    try:
        from sqlalchemy import func

        type_counts = (
            db.query(KnowledgeAtom.atom_type, func.count(KnowledgeAtom.id))
            .filter(
                KnowledgeAtom.tenant_id == tenant_id,
                KnowledgeAtom.is_deleted == False,
            )
            .group_by(KnowledgeAtom.atom_type)
            .all()
        )

        stats = {}
        total = 0
        for at, count in type_counts:
            key = at.value if hasattr(at, 'value') else str(at)
            stats[key] = count
            total += count

        link_count = (
            db.query(func.count(AtomLink.id))
            .filter(AtomLink.tenant_id == tenant_id)
            .scalar()
        )

        return jsonify({
            "success": True,
            "stats": stats,
            "total_atoms": total,
            "total_links": link_count or 0,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()
