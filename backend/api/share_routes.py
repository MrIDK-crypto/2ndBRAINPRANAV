"""
Share Link API Routes
REST endpoints for managing tenant share links and providing public
shared access to a tenant's knowledge portal.
"""

import os
import secrets
import hashlib
from functools import wraps
from flask import Blueprint, request, jsonify, g

from database.models import (
    SessionLocal, TenantShareLink, Tenant, Document, KnowledgeGap,
    GapAnswer, GapStatus, GapCategory, DocumentStatus, DocumentClassification,
    generate_uuid, utc_now
)
from services.auth_service import require_auth
from services.knowledge_service import KnowledgeService
from services.embedding_service import get_embedding_service


# Create blueprint
share_bp = Blueprint('shared', __name__, url_prefix='/api/shared')


def get_db():
    """Get database session"""
    return SessionLocal()


# ============================================================================
# SHARE TOKEN AUTHENTICATION DECORATOR
# ============================================================================

def require_share_token(f):
    """
    Decorator that authenticates via share token instead of JWT.
    Sets g.tenant_id, g.share_link_id, g.share_permissions, g.is_shared_access.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        # Token from header or query param
        token = request.headers.get('X-Share-Token') or request.args.get('token')

        if not token:
            return jsonify({"success": False, "error": "Share token required"}), 401

        token_hash = hashlib.sha256(token.encode()).hexdigest()

        db = get_db()
        try:
            link = db.query(TenantShareLink).filter(
                TenantShareLink.token_hash == token_hash,
                TenantShareLink.is_active == True
            ).first()

            if not link:
                return jsonify({"success": False, "error": "Invalid or revoked share link"}), 401

            # Check expiry
            if not link.is_valid:
                return jsonify({"success": False, "error": "Share link has expired"}), 401

            # Check tenant is active
            tenant = db.query(Tenant).filter(Tenant.id == link.tenant_id).first()
            if not tenant or not tenant.is_active:
                return jsonify({"success": False, "error": "Organization is inactive"}), 403

            # Set context on Flask g
            g.tenant_id = link.tenant_id
            g.share_link_id = link.id
            g.share_permissions = link.permissions or {}
            g.is_shared_access = True
            g.user_id = f"shared-{link.id[:8]}"

            # Update access tracking
            link.access_count = (link.access_count or 0) + 1
            link.last_accessed_at = utc_now()
            db.commit()

        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

        return f(*args, **kwargs)
    return decorated


# ============================================================================
# TOKEN VALIDATION (no auth - entry point for shared access)
# ============================================================================

@share_bp.route('/validate', methods=['GET'])
def validate_share_token_endpoint():
    """
    Validate a share token and return tenant info.
    Used by the frontend landing page before redirecting into the main app.
    Query param: ?token=<raw_token>
    """
    token = request.args.get('token')
    if not token:
        return jsonify({"success": False, "error": "Token required"}), 400

    token_hash = hashlib.sha256(token.encode()).hexdigest()

    db = get_db()
    try:
        link = db.query(TenantShareLink).filter(
            TenantShareLink.token_hash == token_hash,
            TenantShareLink.is_active == True
        ).first()

        if not link or not link.is_valid:
            return jsonify({"success": False, "error": "Invalid or expired share link"}), 401

        tenant = db.query(Tenant).filter(Tenant.id == link.tenant_id).first()
        if not tenant or not tenant.is_active:
            return jsonify({"success": False, "error": "Organization is inactive"}), 403

        return jsonify({
            "success": True,
            "tenant": {
                "id": tenant.id,
                "name": tenant.name,
                "slug": tenant.slug if hasattr(tenant, 'slug') else "",
            },
            "permissions": link.permissions or {},
            "share_link_id": link.id,
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        db.close()


# ============================================================================
# MANAGEMENT ENDPOINTS (JWT auth required)
# ============================================================================

@share_bp.route('/links', methods=['POST'])
@require_auth
def create_share_link():
    """
    Generate a new share link for the tenant.

    Request body:
    {
        "label": "External reviewers"  // optional
    }

    Response:
    {
        "success": true,
        "share_url": "https://app.example.com/shared/{token}",
        "token": "raw_token",
        "link": { ... }
    }
    """
    try:
        data = request.get_json() or {}
        label = data.get('label', '').strip() or None

        # Generate secure token
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        db = get_db()
        try:
            share_link = TenantShareLink(
                tenant_id=g.tenant_id,
                created_by_user_id=g.user_id,
                token_hash=token_hash,
                label=label,
            )
            db.add(share_link)
            db.commit()

            # Build share URL
            frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:3000')
            share_url = f"{frontend_url}/shared/{token}"

            return jsonify({
                "success": True,
                "share_url": share_url,
                "token": token,
                "link": share_link.to_dict()
            })

        finally:
            db.close()

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@share_bp.route('/links', methods=['GET'])
@require_auth
def list_share_links():
    """List all share links for the current tenant."""
    try:
        db = get_db()
        try:
            links = db.query(TenantShareLink).filter(
                TenantShareLink.tenant_id == g.tenant_id,
                TenantShareLink.is_active == True
            ).order_by(TenantShareLink.created_at.desc()).all()

            return jsonify({
                "success": True,
                "links": [link.to_dict() for link in links]
            })

        finally:
            db.close()

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@share_bp.route('/links/<link_id>', methods=['DELETE'])
@require_auth
def revoke_share_link(link_id: str):
    """Revoke a share link."""
    try:
        db = get_db()
        try:
            link = db.query(TenantShareLink).filter(
                TenantShareLink.id == link_id,
                TenantShareLink.tenant_id == g.tenant_id
            ).first()

            if not link:
                return jsonify({"success": False, "error": "Share link not found"}), 404

            link.is_active = False
            link.revoked_at = utc_now()
            link.revoked_by_user_id = g.user_id
            db.commit()

            return jsonify({"success": True, "message": "Share link revoked"})

        finally:
            db.close()

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ============================================================================
# PUBLIC ENDPOINTS (share token auth)
# ============================================================================

@share_bp.route('/portal', methods=['GET'])
@require_share_token
def get_portal_info():
    """Get tenant portal metadata for shared access."""
    try:
        db = get_db()
        try:
            tenant = db.query(Tenant).filter(Tenant.id == g.tenant_id).first()

            doc_count = db.query(Document).filter(
                Document.tenant_id == g.tenant_id,
                Document.is_deleted == False,
                Document.classification == DocumentClassification.WORK,
                Document.status.in_([DocumentStatus.CONFIRMED, DocumentStatus.CLASSIFIED])
            ).count()

            gap_count = db.query(KnowledgeGap).filter(
                KnowledgeGap.tenant_id == g.tenant_id,
                KnowledgeGap.status.in_([GapStatus.OPEN, GapStatus.IN_PROGRESS])
            ).count()

            return jsonify({
                "success": True,
                "portal": {
                    "organization_name": tenant.name if tenant else "Knowledge Portal",
                    "permissions": g.share_permissions,
                    "document_count": doc_count,
                    "gap_count": gap_count,
                }
            })

        finally:
            db.close()

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@share_bp.route('/documents', methods=['GET'])
@require_share_token
def list_shared_documents():
    """List tenant documents for shared access (confirmed/work only)."""
    if not g.share_permissions.get('documents', True):
        return jsonify({"success": False, "error": "Document access not permitted"}), 403

    try:
        limit = min(int(request.args.get('limit', 50)), 200)
        offset = int(request.args.get('offset', 0))

        db = get_db()
        try:
            query = db.query(Document).filter(
                Document.tenant_id == g.tenant_id,
                Document.is_deleted == False,
                Document.classification == DocumentClassification.WORK,
                Document.status.in_([DocumentStatus.CONFIRMED, DocumentStatus.CLASSIFIED])
            ).order_by(Document.created_at.desc())

            total = query.count()
            docs = query.offset(offset).limit(limit).all()

            documents = []
            for doc in docs:
                documents.append({
                    "id": doc.id,
                    "title": doc.title or "Untitled",
                    "summary": doc.summary,
                    "source_type": doc.source_type,
                    "created_at": doc.created_at.isoformat() if doc.created_at else None,
                })

            return jsonify({
                "success": True,
                "documents": documents,
                "pagination": {
                    "total": total,
                    "limit": limit,
                    "offset": offset,
                    "has_more": offset + limit < total
                }
            })

        finally:
            db.close()

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@share_bp.route('/documents/<doc_id>', methods=['GET'])
@require_share_token
def get_shared_document(doc_id: str):
    """Get a single document content for shared access."""
    if not g.share_permissions.get('documents', True):
        return jsonify({"success": False, "error": "Document access not permitted"}), 403

    try:
        db = get_db()
        try:
            doc = db.query(Document).filter(
                Document.id == doc_id,
                Document.tenant_id == g.tenant_id,
                Document.is_deleted == False,
                Document.classification == DocumentClassification.WORK
            ).first()

            if not doc:
                return jsonify({"success": False, "error": "Document not found"}), 404

            return jsonify({
                "success": True,
                "document": {
                    "id": doc.id,
                    "title": doc.title or "Untitled",
                    "content": doc.content,
                    "summary": doc.summary,
                    "source_type": doc.source_type,
                    "created_at": doc.created_at.isoformat() if doc.created_at else None,
                }
            })

        finally:
            db.close()

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@share_bp.route('/search', methods=['POST'])
@require_share_token
def shared_search():
    """RAG search for shared access (no conversation persistence)."""
    if not g.share_permissions.get('chatbot', True):
        return jsonify({"success": False, "error": "Chatbot access not permitted"}), 403

    try:
        data = request.get_json() or {}
        query = data.get('query', '').strip()

        if not query:
            return jsonify({"success": False, "error": "Query required"}), 400

        if len(query) > 2000:
            return jsonify({"success": False, "error": "Query too long (max 2000 chars)"}), 400

        tenant_id = g.tenant_id

        # Reuse the same search logic from app_v2.py
        from vector_stores.pinecone_store import get_hybrid_store
        from services.enhanced_search_service import get_enhanced_search_service

        vector_store = None
        if os.getenv("PINECONE_API_KEY"):
            try:
                vector_store = get_hybrid_store()
            except Exception:
                pass

        if not vector_store:
            return jsonify({
                "success": True,
                "query": query,
                "answer": "Search service is temporarily unavailable.",
                "sources": [],
                "source_count": 0
            })

        # Check if knowledge base has content
        stats = vector_store.get_stats(tenant_id)
        if stats.get('vector_count', 0) == 0:
            return jsonify({
                "success": True,
                "query": query,
                "answer": "This knowledge base doesn't have any searchable content yet.",
                "sources": [],
                "source_count": 0
            })

        enhanced_service = get_enhanced_search_service()
        result = enhanced_service.search_and_answer(
            query=query,
            tenant_id=tenant_id,
            vector_store=vector_store,
            top_k=10,
            validate=True,
            conversation_history=[],
            boost_doc_ids=[]
        )

        sources = []
        for src in result.get('sources', []):
            sources.append({
                "title": src.get('title', 'Untitled'),
                "content_preview": (src.get('content', '') or src.get('content_preview', ''))[:300],
                "score": src.get('rerank_score', src.get('score', 0)),
            })

        return jsonify({
            "success": True,
            "query": query,
            "answer": result.get('answer', ''),
            "confidence": result.get('confidence', 0),
            "sources": sources,
            "source_count": len(sources),
        })

    except Exception as e:
        import traceback
        print(f"[SHARED SEARCH] Error: {e}", flush=True)
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@share_bp.route('/knowledge/gaps', methods=['GET'])
@require_share_token
def list_shared_gaps():
    """List knowledge gaps for shared access."""
    if not g.share_permissions.get('knowledge_gaps', True):
        return jsonify({"success": False, "error": "Knowledge gaps access not permitted"}), 403

    try:
        limit = min(int(request.args.get('limit', 50)), 200)
        offset = int(request.args.get('offset', 0))

        db = get_db()
        try:
            service = KnowledgeService(db)
            gaps, total = service.get_gaps(
                tenant_id=g.tenant_id,
                status=None,
                category=None,
                limit=limit,
                offset=offset
            )

            return jsonify({
                "success": True,
                "gaps": [gap.to_dict(include_answers=True) for gap in gaps],
                "pagination": {
                    "total": total,
                    "limit": limit,
                    "offset": offset,
                    "has_more": offset + limit < total
                }
            })

        finally:
            db.close()

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@share_bp.route('/knowledge/gaps/<gap_id>', methods=['GET'])
@require_share_token
def get_shared_gap(gap_id: str):
    """Get a single knowledge gap with answers for shared access."""
    if not g.share_permissions.get('knowledge_gaps', True):
        return jsonify({"success": False, "error": "Knowledge gaps access not permitted"}), 403

    try:
        db = get_db()
        try:
            gap = db.query(KnowledgeGap).filter(
                KnowledgeGap.id == gap_id,
                KnowledgeGap.tenant_id == g.tenant_id
            ).first()

            if not gap:
                return jsonify({"success": False, "error": "Knowledge gap not found"}), 404

            return jsonify({
                "success": True,
                "gap": gap.to_dict(include_answers=True)
            })

        finally:
            db.close()

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@share_bp.route('/knowledge/gaps/<gap_id>/answers', methods=['POST'])
@require_share_token
def submit_shared_answer(gap_id: str):
    """Submit an answer to a knowledge gap from shared access."""
    if not g.share_permissions.get('knowledge_gaps', True):
        return jsonify({"success": False, "error": "Knowledge gaps access not permitted"}), 403

    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Request body required"}), 400

        question_index = data.get('question_index')
        answer_text = data.get('answer_text', '').strip()

        if question_index is None:
            return jsonify({"success": False, "error": "question_index required"}), 400
        if not answer_text:
            return jsonify({"success": False, "error": "answer_text required"}), 400
        if len(answer_text) > 10000:
            return jsonify({"success": False, "error": "Answer too long (max 10000 chars)"}), 400

        db = get_db()
        try:
            service = KnowledgeService(db)
            answer, error = service.submit_answer(
                gap_id=gap_id,
                question_index=question_index,
                answer_text=answer_text,
                user_id=g.user_id,
                tenant_id=g.tenant_id
            )

            if error:
                return jsonify({"success": False, "error": error}), 400

            # Auto-embed the answer
            from api.knowledge_routes import embed_gap_answer
            embed_result = embed_gap_answer(answer, g.tenant_id, db)

            return jsonify({
                "success": True,
                "answer": answer.to_dict(),
                "embedded": embed_result.get('success', False),
            })

        finally:
            db.close()

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
