"""
Admin Routes
Administrative endpoints for tenant migration and maintenance
"""

from flask import Blueprint, jsonify, request, g
from sqlalchemy.orm import Session
from sqlalchemy import text

from database.models import SessionLocal, Document, KnowledgeGap
from services.auth_service import require_auth

# Create blueprint
admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')


def get_db():
    """Get database session"""
    return SessionLocal()


@admin_bp.route('/migrate-tenant', methods=['POST'])
@require_auth
def migrate_tenant():
    """
    Migrate documents and gaps from 'local-tenant' to the current user's tenant_id.

    This fixes the common issue where data was created before proper auth was enabled.

    Response:
    {
        "success": true,
        "documents_migrated": 50,
        "gaps_migrated": 10,
        "target_tenant": "5349595e-e2c7-4cd9-a6eb-4f4727e5f061"
    }
    """
    db = get_db()
    try:
        # Get the user's actual tenant_id from JWT
        target_tenant = g.tenant_id
        source_tenant = 'local-tenant'

        if not target_tenant:
            return jsonify({
                "success": False,
                "error": "No tenant_id found in JWT token"
            }), 400

        # Count items to migrate
        docs_to_migrate = db.query(Document).filter(
            Document.tenant_id == source_tenant
        ).count()

        gaps_to_migrate = db.query(KnowledgeGap).filter(
            KnowledgeGap.tenant_id == source_tenant
        ).count()

        if docs_to_migrate == 0 and gaps_to_migrate == 0:
            return jsonify({
                "success": True,
                "message": "No data to migrate from local-tenant",
                "documents_migrated": 0,
                "gaps_migrated": 0,
                "target_tenant": target_tenant
            })

        # Migrate documents
        db.query(Document).filter(
            Document.tenant_id == source_tenant
        ).update({Document.tenant_id: target_tenant})

        # Migrate knowledge gaps
        db.query(KnowledgeGap).filter(
            KnowledgeGap.tenant_id == source_tenant
        ).update({KnowledgeGap.tenant_id: target_tenant})

        db.commit()

        return jsonify({
            "success": True,
            "message": f"Migrated {docs_to_migrate} documents and {gaps_to_migrate} gaps to your tenant",
            "documents_migrated": docs_to_migrate,
            "gaps_migrated": gaps_to_migrate,
            "target_tenant": target_tenant,
            "note": "You should re-embed documents to update Pinecone namespace"
        })

    except Exception as e:
        db.rollback()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
    finally:
        db.close()


@admin_bp.route('/reembed-all', methods=['POST'])
@require_auth
def reembed_all_documents():
    """
    Mark all documents for re-embedding and trigger embedding.

    This clears embedding flags so documents get re-embedded to the correct
    Pinecone namespace based on tenant_id.

    Response:
    {
        "success": true,
        "documents_marked": 50,
        "message": "Documents marked for re-embedding"
    }
    """
    db = get_db()
    try:
        tenant_id = g.tenant_id

        # Clear embedding flags for all tenant documents
        result = db.query(Document).filter(
            Document.tenant_id == tenant_id
        ).update({
            Document.embedded_at: None,
            Document.embedding_generated: False
        })

        db.commit()

        # Now trigger embedding
        from services.embedding_service import get_embedding_service
        embedding_service = get_embedding_service()

        # Get documents to embed
        docs_to_embed = db.query(Document).filter(
            Document.tenant_id == tenant_id,
            Document.embedded_at == None
        ).all()

        if docs_to_embed:
            embed_result = embedding_service.embed_documents(
                documents=docs_to_embed,
                tenant_id=tenant_id,
                db=db,
                force_reembed=True
            )

            return jsonify({
                "success": True,
                "documents_marked": result,
                "documents_embedded": embed_result.get('embedded', 0),
                "message": "Documents re-embedded successfully"
            })

        return jsonify({
            "success": True,
            "documents_marked": result,
            "documents_embedded": 0,
            "message": "No documents to embed"
        })

    except Exception as e:
        db.rollback()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
    finally:
        db.close()


@admin_bp.route('/delete-local-tenant', methods=['DELETE'])
@require_auth
def delete_local_tenant_data():
    """
    Delete ALL data created with 'local-tenant' tenant_id.

    This removes orphaned data from before proper auth was enabled.

    Response:
    {
        "success": true,
        "documents_deleted": 50,
        "gaps_deleted": 10
    }
    """
    db = get_db()
    try:
        source_tenant = 'local-tenant'

        # Count before deleting
        docs_count = db.query(Document).filter(
            Document.tenant_id == source_tenant
        ).count()

        gaps_count = db.query(KnowledgeGap).filter(
            KnowledgeGap.tenant_id == source_tenant
        ).count()

        if docs_count == 0 and gaps_count == 0:
            return jsonify({
                "success": True,
                "message": "No local-tenant data found",
                "documents_deleted": 0,
                "gaps_deleted": 0
            })

        # Delete from Pinecone first (if any embeddings exist)
        try:
            from vector_stores.pinecone_store import get_hybrid_store
            vector_store = get_hybrid_store()
            vector_store.delete_tenant_data(source_tenant)
            print(f"[Admin] Deleted Pinecone namespace for {source_tenant}")
        except Exception as e:
            print(f"[Admin] Warning: Could not delete Pinecone data: {e}")

        # Delete gaps
        db.query(KnowledgeGap).filter(
            KnowledgeGap.tenant_id == source_tenant
        ).delete()

        # Delete documents
        db.query(Document).filter(
            Document.tenant_id == source_tenant
        ).delete()

        db.commit()

        return jsonify({
            "success": True,
            "message": f"Deleted all local-tenant data",
            "documents_deleted": docs_count,
            "gaps_deleted": gaps_count
        })

    except Exception as e:
        db.rollback()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
    finally:
        db.close()


@admin_bp.route('/tenant-stats', methods=['GET'])
@require_auth
def get_tenant_stats():
    """
    Get statistics about the current tenant's data.

    Response:
    {
        "success": true,
        "tenant_id": "...",
        "documents": {"total": 50, "embedded": 45, "pending": 5},
        "gaps": {"total": 10, "answered": 3}
    }
    """
    db = get_db()
    try:
        tenant_id = g.tenant_id

        # Document stats
        total_docs = db.query(Document).filter(
            Document.tenant_id == tenant_id
        ).count()

        embedded_docs = db.query(Document).filter(
            Document.tenant_id == tenant_id,
            Document.embedded_at != None
        ).count()

        # Gap stats
        total_gaps = db.query(KnowledgeGap).filter(
            KnowledgeGap.tenant_id == tenant_id
        ).count()

        answered_gaps = db.query(KnowledgeGap).filter(
            KnowledgeGap.tenant_id == tenant_id,
            KnowledgeGap.status == 'answered'
        ).count()

        # Also check local-tenant for migration needs
        local_docs = db.query(Document).filter(
            Document.tenant_id == 'local-tenant'
        ).count()

        local_gaps = db.query(KnowledgeGap).filter(
            KnowledgeGap.tenant_id == 'local-tenant'
        ).count()

        return jsonify({
            "success": True,
            "tenant_id": tenant_id,
            "documents": {
                "total": total_docs,
                "embedded": embedded_docs,
                "pending_embed": total_docs - embedded_docs
            },
            "gaps": {
                "total": total_gaps,
                "answered": answered_gaps
            },
            "migration_needed": {
                "local_tenant_documents": local_docs,
                "local_tenant_gaps": local_gaps,
                "action_required": local_docs > 0 or local_gaps > 0
            }
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
    finally:
        db.close()
