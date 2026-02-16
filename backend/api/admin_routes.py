"""
Admin Routes
Administrative endpoints for tenant migration and maintenance
"""

from flask import Blueprint, jsonify, request, g
from sqlalchemy.orm import Session
from sqlalchemy import text, func
from datetime import datetime, timezone, timedelta

from database.models import SessionLocal, Document, KnowledgeGap, ChatConversation, ChatMessage, User, AuditLog, Connector, UserRole, Tenant
from services.auth_service import require_auth

# Create blueprint
admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')

# Admin emails - these users are always promoted to admin on startup
ADMIN_EMAILS = [
    'pranav@use2ndbrain.com',
]

# Super admin emails - can view analytics for all tenants
SUPER_ADMIN_EMAILS = [
    'pranav@use2ndbrain.com',
]


def get_db():
    """Get database session"""
    return SessionLocal()


def ensure_admins():
    """Promote configured admin emails to admin role on startup."""
    db = get_db()
    try:
        for email in ADMIN_EMAILS:
            user = db.query(User).filter(User.email == email).first()
            if user and user.role != UserRole.ADMIN:
                user.role = UserRole.ADMIN
                db.commit()
                print(f"[Admin] Promoted {email} to admin")
            elif user:
                print(f"[Admin] {email} is already admin")
    except Exception as e:
        db.rollback()
        print(f"[Admin] Error ensuring admins: {e}")
    finally:
        db.close()


def fix_untitled_conversations():
    """Retroactively generate titles for conversations that have messages but no title."""
    import re
    db = get_db()
    try:
        untitled = db.query(ChatConversation).filter(
            ChatConversation.title == None
        ).all()

        fixed = 0
        for conv in untitled:
            # Find the first user message in this conversation
            first_msg = db.query(ChatMessage).filter(
                ChatMessage.conversation_id == conv.id,
                ChatMessage.role == 'user'
            ).order_by(ChatMessage.created_at.asc()).first()

            if first_msg and first_msg.content:
                cleaned = first_msg.content.strip()
                cleaned = re.sub(r'https?://\S+', '', cleaned)
                cleaned = re.sub(r'\s+', ' ', cleaned).strip()
                if cleaned and len(cleaned) >= 3:
                    if len(cleaned) <= 50:
                        conv.title = cleaned
                    else:
                        truncated = cleaned[:50]
                        last_space = truncated.rfind(' ')
                        conv.title = (truncated[:last_space] + "...") if last_space > 20 else (truncated + "...")
                    fixed += 1

        if fixed > 0:
            db.commit()
            print(f"[Admin] Fixed {fixed} untitled conversations")
    except Exception as e:
        db.rollback()
        print(f"[Admin] Error fixing untitled conversations: {e}")
    finally:
        db.close()


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


@admin_bp.route('/tenants', methods=['GET'])
@require_auth
def list_tenants():
    """
    List all tenants. Only accessible to super admins.
    """
    db = get_db()
    try:
        # Check super admin
        user = db.query(User).filter(User.id == g.user_id).first()
        if not user or user.email not in SUPER_ADMIN_EMAILS:
            return jsonify({"success": False, "error": "Forbidden"}), 403

        tenants = db.query(Tenant).filter(Tenant.is_active == True).all()
        result = []
        for t in tenants:
            user_count = db.query(User).filter(User.tenant_id == t.id, User.is_active == True).count()
            result.append({
                "id": t.id,
                "name": t.name,
                "slug": t.slug,
                "plan": t.plan.value if t.plan else "free",
                "user_count": user_count,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            })

        return jsonify({"success": True, "tenants": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        db.close()


@admin_bp.route('/analytics', methods=['GET'])
@require_auth
def get_analytics():
    """
    Get observability metrics for the tenant.

    Query params:
        days: Number of days to look back (default 30)
        tenant_id: Override tenant (super admin only)

    Response:
    {
        "success": true,
        "metrics": {
            "overview": { ... },
            "chat": { ... },
            "documents": { ... },
            "knowledge_gaps": { ... },
            "integrations": { ... },
            "activity_timeline": [ ... ]
        }
    }
    """
    db = get_db()
    try:
        tenant_id = g.tenant_id
        days = int(request.args.get('days', 30))

        # Check analytics access - only super admins
        user = db.query(User).filter(User.id == g.user_id).first()
        if not user or user.email not in SUPER_ADMIN_EMAILS:
            return jsonify({"success": False, "error": "Analytics access restricted"}), 403

        # Super admin can override tenant_id
        override_tenant = request.args.get('tenant_id')
        if override_tenant:
            tenant_id = override_tenant

        since = datetime.now(timezone.utc) - timedelta(days=days)

        # --- Overview Metrics ---
        total_users = db.query(User).filter(User.tenant_id == tenant_id, User.is_active == True).count()
        total_docs = db.query(Document).filter(Document.tenant_id == tenant_id).count()
        embedded_docs = db.query(Document).filter(
            Document.tenant_id == tenant_id, Document.embedded_at != None
        ).count()
        total_conversations = db.query(ChatConversation).filter(
            ChatConversation.tenant_id == tenant_id
        ).count()
        total_messages = db.query(ChatMessage).filter(
            ChatMessage.tenant_id == tenant_id
        ).count()
        total_gaps = db.query(KnowledgeGap).filter(
            KnowledgeGap.tenant_id == tenant_id
        ).count()
        answered_gaps = db.query(KnowledgeGap).filter(
            KnowledgeGap.tenant_id == tenant_id,
            KnowledgeGap.status == 'answered'
        ).count()

        # --- Chat Metrics (last N days) ---
        recent_conversations = db.query(ChatConversation).filter(
            ChatConversation.tenant_id == tenant_id,
            ChatConversation.created_at >= since
        ).count()
        recent_messages = db.query(ChatMessage).filter(
            ChatMessage.tenant_id == tenant_id,
            ChatMessage.created_at >= since
        ).count()
        user_messages = db.query(ChatMessage).filter(
            ChatMessage.tenant_id == tenant_id,
            ChatMessage.role == 'user',
            ChatMessage.created_at >= since
        ).count()

        # Average messages per conversation
        avg_messages = 0
        if recent_conversations > 0:
            avg_messages = round(recent_messages / recent_conversations, 1)

        # --- Document Metrics (last N days) ---
        recent_docs = db.query(Document).filter(
            Document.tenant_id == tenant_id,
            Document.created_at >= since
        ).count()

        # Document source breakdown
        source_breakdown = {}
        source_rows = db.query(
            Document.source_type,
            func.count(Document.id)
        ).filter(
            Document.tenant_id == tenant_id
        ).group_by(Document.source_type).all()
        for source_type, count in source_rows:
            source_breakdown[source_type or 'upload'] = count

        # Document classification breakdown
        classification_breakdown = {}
        class_rows = db.query(
            Document.classification,
            func.count(Document.id)
        ).filter(
            Document.tenant_id == tenant_id
        ).group_by(Document.classification).all()
        for classification, count in class_rows:
            classification_breakdown[classification or 'unclassified'] = count

        # --- Knowledge Gap Metrics ---
        recent_gaps = db.query(KnowledgeGap).filter(
            KnowledgeGap.tenant_id == tenant_id,
            KnowledgeGap.created_at >= since
        ).count()

        gap_category_breakdown = {}
        gap_rows = db.query(
            KnowledgeGap.category,
            func.count(KnowledgeGap.id)
        ).filter(
            KnowledgeGap.tenant_id == tenant_id
        ).group_by(KnowledgeGap.category).all()
        for category, count in gap_rows:
            gap_category_breakdown[str(category) if category else 'uncategorized'] = count

        # --- Integration Metrics ---
        integrations = []
        try:
            connector_rows = db.query(Connector).filter(
                Connector.tenant_id == tenant_id
            ).all()
            for c in connector_rows:
                integrations.append({
                    'type': c.connector_type,
                    'status': str(c.status) if c.status else 'unknown',
                    'last_synced': c.last_synced_at.isoformat() if c.last_synced_at else None,
                    'documents_synced': c.total_items_synced or 0,
                })
        except Exception:
            pass  # Connector model might not have all fields

        # --- Activity Timeline (daily counts for last N days) ---
        activity_timeline = []
        for i in range(min(days, 30)):
            day_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=i)
            day_end = day_start + timedelta(days=1)

            day_messages = db.query(ChatMessage).filter(
                ChatMessage.tenant_id == tenant_id,
                ChatMessage.role == 'user',
                ChatMessage.created_at >= day_start,
                ChatMessage.created_at < day_end
            ).count()

            day_docs = db.query(Document).filter(
                Document.tenant_id == tenant_id,
                Document.created_at >= day_start,
                Document.created_at < day_end
            ).count()

            activity_timeline.append({
                'date': day_start.strftime('%Y-%m-%d'),
                'questions_asked': day_messages,
                'documents_added': day_docs,
            })

        activity_timeline.reverse()  # chronological order

        return jsonify({
            "success": True,
            "metrics": {
                "overview": {
                    "total_users": total_users,
                    "total_documents": total_docs,
                    "embedded_documents": embedded_docs,
                    "total_conversations": total_conversations,
                    "total_messages": total_messages,
                    "total_gaps": total_gaps,
                    "answered_gaps": answered_gaps,
                    "embedding_coverage": round((embedded_docs / total_docs * 100) if total_docs > 0 else 0, 1),
                    "gap_resolution_rate": round((answered_gaps / total_gaps * 100) if total_gaps > 0 else 0, 1),
                },
                "chat": {
                    "conversations_last_period": recent_conversations,
                    "messages_last_period": recent_messages,
                    "questions_asked": user_messages,
                    "avg_messages_per_conversation": avg_messages,
                },
                "documents": {
                    "added_last_period": recent_docs,
                    "by_source": source_breakdown,
                    "by_classification": classification_breakdown,
                },
                "knowledge_gaps": {
                    "detected_last_period": recent_gaps,
                    "by_category": gap_category_breakdown,
                },
                "integrations": integrations,
                "activity_timeline": activity_timeline,
                "period_days": days,
            }
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
    finally:
        db.close()


@admin_bp.route('/track-event', methods=['POST'])
@require_auth
def track_event():
    """
    Track a frontend analytics event.

    POST /api/admin/track-event
    {
        "event": "page_view",
        "properties": {
            "page": "/documents",
            "action": "click_document",
            "label": "doc_id_123"
        }
    }
    """
    db = get_db()
    try:
        data = request.get_json() or {}
        event_name = data.get('event', 'unknown')
        properties = data.get('properties', {})

        # Store as audit log entry
        audit = AuditLog(
            tenant_id=g.tenant_id,
            user_id=g.user_id,
            action=f"analytics:{event_name}",
            resource_type='analytics',
            resource_id=None,
            changes=properties,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent', '')[:255],
        )
        db.add(audit)
        db.commit()

        return jsonify({"success": True})

    except Exception as e:
        db.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        db.close()
