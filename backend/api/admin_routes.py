"""
Admin Routes
Administrative endpoints for tenant migration and maintenance
"""

import json
import os

from flask import Blueprint, jsonify, request, g
from sqlalchemy.orm import Session
from sqlalchemy import text, func
from datetime import datetime, timezone, timedelta

from database.models import SessionLocal, Document, KnowledgeGap, ChatConversation, ChatMessage, User, AuditLog, Connector, UserRole, Tenant, GapStatus, ConnectorStatus, ChannelTenantMapping
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
            KnowledgeGap.status == GapStatus.ANSWERED
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

        # Check if super admin (can view any tenant)
        user = db.query(User).filter(User.id == g.user_id).first()
        is_super_admin = user and user.email in SUPER_ADMIN_EMAILS

        # Super admin can override tenant_id; regular users can only see their own
        override_tenant = request.args.get('tenant_id')
        if override_tenant and is_super_admin:
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
            KnowledgeGap.status == GapStatus.ANSWERED
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

        # --- Slack Bot Metrics ---
        slack_total = db.query(AuditLog).filter(
            AuditLog.tenant_id == tenant_id,
            AuditLog.action == 'slack_bot:question',
            AuditLog.created_at >= since
        ).count()
        try:
            slack_answered = db.query(AuditLog).filter(
                AuditLog.tenant_id == tenant_id,
                AuditLog.action == 'slack_bot:question',
                AuditLog.created_at >= since,
                text("changes->>'result' = 'answered'")
            ).count()
        except Exception:
            db.rollback()
            slack_answered = 0
        slack_no_results = slack_total - slack_answered

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
            key = classification.value if hasattr(classification, 'value') else (str(classification) if classification else 'unclassified')
            classification_breakdown[key] = count

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
            key = category.value if hasattr(category, 'value') else (str(category) if category else 'uncategorized')
            gap_category_breakdown[key] = count

        # --- Integration Metrics ---
        integrations = []
        try:
            connector_rows = db.query(Connector).filter(
                Connector.tenant_id == tenant_id,
                Connector.status.notin_([ConnectorStatus.DISCONNECTED, ConnectorStatus.NOT_CONFIGURED])
            ).all()
            for c in connector_rows:
                integrations.append({
                    'type': c.connector_type.value if hasattr(c.connector_type, 'value') else str(c.connector_type),
                    'status': c.status.value if hasattr(c.status, 'value') else (str(c.status) if c.status else 'unknown'),
                    'last_synced': c.last_sync_at.isoformat() if c.last_sync_at else None,
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
                "slack_bot": {
                    "questions_asked": slack_total,
                    "answered": slack_answered,
                    "no_results": slack_no_results,
                    "answer_rate": round((slack_answered / slack_total * 100) if slack_total > 0 else 0, 1),
                },
                "integrations": integrations,
                "activity_timeline": activity_timeline,
                "period_days": days,
            }
        })

    except Exception as e:
        db.rollback()
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


@admin_bp.route('/embed-tenant', methods=['POST'])
@require_auth
def embed_tenant_docs():
    """Super admin: embed all unindexed documents for a specific tenant.
    Runs in background thread to avoid ALB timeout.

    POST /api/admin/embed-tenant
    {
        "tenant_id": "<target-tenant-uuid>",
        "force": false  // true = re-embed ALL docs, false = only unindexed
    }
    """
    import threading
    db = get_db()
    try:
        user = db.query(User).filter(User.id == g.user_id).first()
        if not user or user.email not in SUPER_ADMIN_EMAILS:
            return jsonify({"success": False, "error": "Forbidden"}), 403

        data = request.get_json() or {}
        target_tenant_id = data.get('tenant_id')
        force = data.get('force', False)

        if not target_tenant_id:
            return jsonify({"success": False, "error": "tenant_id required"}), 400

        tenant = db.query(Tenant).filter(Tenant.id == target_tenant_id).first()
        if not tenant:
            return jsonify({"success": False, "error": f"Tenant {target_tenant_id} not found"}), 404

        tenant_name = tenant.name

        # Count unembedded docs
        unembedded = db.query(Document).filter(
            Document.tenant_id == target_tenant_id,
            Document.embedded_at == None,
            Document.is_deleted == False,
            Document.content != None,
            Document.content != ''
        ).count()

        # Run embedding in background thread
        def _embed_bg(tid, force_flag):
            from database.models import SessionLocal as BgSession
            from services.embedding_service import get_embedding_service
            bg_db = BgSession()
            try:
                svc = get_embedding_service()
                result = svc.embed_tenant_documents(tenant_id=tid, db=bg_db, force_reembed=force_flag)
                print(f"[AdminEmbed] Tenant '{tenant_name}': embedded={result.get('embedded', 0)}, errors={len(result.get('errors', []))}", flush=True)
            except Exception as e:
                print(f"[AdminEmbed] Tenant '{tenant_name}' failed: {e}", flush=True)
            finally:
                bg_db.close()

        threading.Thread(target=_embed_bg, args=(target_tenant_id, force), daemon=True).start()

        return jsonify({
            "success": True,
            "tenant_name": tenant_name,
            "unembedded_docs": unembedded,
            "message": f"Embedding started in background for {unembedded} docs"
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        db.close()


@admin_bp.route('/embed-all-tenants', methods=['POST'])
@require_auth
def embed_all_tenants():
    """Super admin: embed unindexed documents across ALL tenants.
    Runs in background thread to avoid ALB timeout.

    POST /api/admin/embed-all-tenants
    """
    import threading
    db = get_db()
    try:
        user = db.query(User).filter(User.id == g.user_id).first()
        if not user or user.email not in SUPER_ADMIN_EMAILS:
            return jsonify({"success": False, "error": "Forbidden"}), 403

        # Collect summary of what needs embedding
        tenants = db.query(Tenant).filter(Tenant.is_active == True).all()
        pending = []
        for tenant in tenants:
            count = db.query(Document).filter(
                Document.tenant_id == tenant.id,
                Document.embedded_at == None,
                Document.is_deleted == False,
                Document.content != None,
                Document.content != ''
            ).count()
            if count > 0:
                pending.append({"tenant_name": tenant.name, "tenant_id": tenant.id, "unembedded": count})

        if not pending:
            return jsonify({"success": True, "message": "All tenants fully indexed", "tenants_processed": 0})

        # Run in background
        def _embed_all_bg(tenant_list):
            from database.models import SessionLocal as BgSession
            from services.embedding_service import get_embedding_service
            bg_db = BgSession()
            try:
                svc = get_embedding_service()
                for t in tenant_list:
                    try:
                        result = svc.embed_tenant_documents(tenant_id=t["tenant_id"], db=bg_db, force_reembed=False)
                        print(f"[AdminEmbed] {t['tenant_name']}: embedded={result.get('embedded', 0)}, errors={len(result.get('errors', []))}", flush=True)
                    except Exception as e:
                        print(f"[AdminEmbed] {t['tenant_name']} failed: {e}", flush=True)
                print("[AdminEmbed] All tenants complete", flush=True)
            finally:
                bg_db.close()

        threading.Thread(target=_embed_all_bg, args=(pending,), daemon=True).start()

        return jsonify({
            "success": True,
            "message": f"Embedding started in background for {len(pending)} tenants",
            "pending": pending
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        db.close()


@admin_bp.route('/train-hij-models', methods=['POST'])
@require_auth
def trigger_hij_training():
    """
    Trigger HIJ (High Impact Journal) model training pipeline.
    Super admin only. Runs data generation + both model trainers.

    POST /api/admin/train-hij-models
    {
        "target_papers": 5000   // optional, default 5000
    }

    Response:
    {
        "success": true,
        "task_id": "...",       // Celery task ID (if Celery available)
        "message": "HIJ model training started"
    }
    """
    db = get_db()
    try:
        # Super admin check
        user = db.query(User).filter(User.id == g.user_id).first()
        if not user or user.email not in SUPER_ADMIN_EMAILS:
            return jsonify({"success": False, "error": "Forbidden"}), 403

        data = request.get_json(silent=True) or {}
        target_papers = data.get('target_papers', 5000)

        # Try Celery first
        try:
            from tasks.hij_training_tasks import train_hij_models
            task = train_hij_models.delay(target_papers=target_papers)
            return jsonify({
                "success": True,
                "task_id": task.id,
                "message": f"HIJ model training started (target: {target_papers} papers)",
            })
        except Exception as celery_err:
            print(f"[Admin] Celery unavailable, falling back to background thread: {celery_err}", flush=True)

        # Fallback: run in background thread if Celery is not available
        import threading
        import uuid

        fake_task_id = f"bg-hij-{uuid.uuid4().hex[:12]}"

        def _train_bg(target):
            import sys
            import os
            from pathlib import Path

            backend_dir = Path(__file__).resolve().parent.parent
            if str(backend_dir) not in sys.path:
                sys.path.insert(0, str(backend_dir))

            try:
                from scripts.generate_training_data import generate_training_data
                from scripts.train_hij_models import train_paper_type_classifier, train_tier_predictor

                data_dir = backend_dir / 'data' / 'oncology_training'
                model_dir = backend_dir / 'models'

                print(f"[Admin] HIJ training started (thread, target={target})", flush=True)

                generate_training_data(data_dir, target_total=target)
                print("[Admin] HIJ data generation complete", flush=True)

                pt = train_paper_type_classifier(data_dir, model_dir)
                print(f"[Admin] Paper type classifier: {pt}", flush=True)

                tier = train_tier_predictor(data_dir, model_dir)
                print(f"[Admin] Tier predictor: {tier}", flush=True)

                print("[Admin] HIJ training pipeline complete", flush=True)
            except Exception as e:
                print(f"[Admin] HIJ training failed: {e}", flush=True)

        threading.Thread(target=_train_bg, args=(target_papers,), daemon=True).start()

        return jsonify({
            "success": True,
            "task_id": fake_task_id,
            "message": f"HIJ model training started in background thread (target: {target_papers} papers)",
            "note": "Celery unavailable — running in background thread. Check server logs for progress.",
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        db.close()


@admin_bp.route('/train-hij-1m', methods=['POST'])
@require_auth
def trigger_hij_1m_training():
    """
    Start batched 1M HIJ model training pipeline via Celery chain + S3.
    Super admin only.

    POST /api/admin/train-hij-1m
    {
        "resume_run_id": "hij-1m-...",   // optional — resume a failed run
        "resume_from_batch": 0           // optional — skip completed batches
    }
    """
    db = get_db()
    try:
        user = db.query(User).filter(User.id == g.user_id).first()
        if not user or user.email not in SUPER_ADMIN_EMAILS:
            return jsonify({"success": False, "error": "Forbidden"}), 403

        data = request.get_json(silent=True) or {}
        resume_run_id = data.get('resume_run_id')
        resume_from_batch = data.get('resume_from_batch', 0)

        from tasks.hij_training_tasks import build_hij_1m_chain

        run_id, pipeline = build_hij_1m_chain(
            run_id=resume_run_id,
            resume_from_batch=resume_from_batch,
        )

        result = pipeline.apply_async()

        return jsonify({
            "success": True,
            "run_id": run_id,
            "chain_task_id": result.id,
            "message": f"HIJ 1M training pipeline started (run: {run_id})",
            "resumed": resume_run_id is not None,
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        db.close()


@admin_bp.route('/train-hij-1m/merge-and-train', methods=['POST'])
@require_auth
def trigger_hij_merge_train():
    """
    Skip fetching — directly merge existing S3 batches and train.
    Use when some batches completed but remaining are blocked (e.g. rate limit).

    POST /api/admin/train-hij-1m/merge-and-train
    {
        "run_id": "hij-1m-...",
        "num_batches": 3
    }
    """
    db = get_db()
    try:
        user = db.query(User).filter(User.id == g.user_id).first()
        if not user or user.email not in SUPER_ADMIN_EMAILS:
            return jsonify({"success": False, "error": "Forbidden"}), 403

        data = request.get_json(silent=True) or {}
        run_id = data.get('run_id')
        num_batches = data.get('num_batches', 3)

        if not run_id:
            return jsonify({"success": False, "error": "run_id is required"}), 400

        from celery import chain
        from tasks.hij_training_tasks import merge_hij_batches, train_hij_from_s3

        pipeline = chain(
            merge_hij_batches.si(run_id, num_batches),
            train_hij_from_s3.si(run_id),
        )
        result = pipeline.apply_async()

        return jsonify({
            "success": True,
            "run_id": run_id,
            "chain_task_id": result.id,
            "message": f"Merge + train started for {num_batches} batches (run: {run_id})",
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        db.close()


@admin_bp.route('/train-hij-1m/status/<run_id>', methods=['GET'])
@require_auth
def get_hij_1m_status(run_id):
    """
    Get status of a batched HIJ 1M training run.
    Reads status.json from S3.

    GET /api/admin/train-hij-1m/status/<run_id>
    """
    db = get_db()
    try:
        user = db.query(User).filter(User.id == g.user_id).first()
        if not user or user.email not in SUPER_ADMIN_EMAILS:
            return jsonify({"success": False, "error": "Forbidden"}), 403

        import boto3
        s3 = boto3.client("s3", region_name=os.environ.get("AWS_S3_REGION", "us-east-2"))
        bucket = os.environ.get("HIJ_MODEL_BUCKET", "secondbrain-models")
        key = f"hij/training-runs/{run_id}/status.json"

        try:
            resp = s3.get_object(Bucket=bucket, Key=key)
            status = json.loads(resp["Body"].read().decode())
        except s3.exceptions.NoSuchKey:
            return jsonify({"success": False, "error": f"Run {run_id} not found"}), 404
        except Exception as e:
            return jsonify({"success": False, "error": f"S3 error: {e}"}), 500

        return jsonify({"success": True, "run_id": run_id, "status": status})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        db.close()


@admin_bp.route('/unembedded-docs', methods=['GET'])
@require_auth
def get_unembedded_docs():
    """
    Diagnostic: list unembedded documents for a tenant.
    Super admin only.

    GET /api/admin/unembedded-docs?tenant_id=...&limit=50
    """
    db = get_db()
    try:
        user = db.query(User).filter(User.id == g.user_id).first()
        if not user or user.email not in SUPER_ADMIN_EMAILS:
            return jsonify({"success": False, "error": "Forbidden"}), 403

        tenant_id = request.args.get('tenant_id', g.tenant_id)
        limit = int(request.args.get('limit', 50))

        from sqlalchemy import func

        docs = db.query(Document).filter(
            Document.tenant_id == tenant_id,
            Document.embedded_at == None,
            Document.is_deleted == False,
        ).limit(limit).all()

        results = []
        null_content = 0
        empty_content = 0
        has_content = 0

        for d in docs:
            content_status = 'null' if d.content is None else ('empty' if d.content.strip() == '' else 'has_content')
            if content_status == 'null':
                null_content += 1
            elif content_status == 'empty':
                empty_content += 1
            else:
                has_content += 1

            results.append({
                'id': d.id,
                'title': d.title[:100] if d.title else None,
                'source': d.source_type,
                'content_status': content_status,
                'content_length': len(d.content) if d.content else 0,
                'created_at': d.created_at.isoformat() if d.created_at else None,
            })

        total_unembedded = db.query(Document).filter(
            Document.tenant_id == tenant_id,
            Document.embedded_at == None,
            Document.is_deleted == False,
        ).count()

        return jsonify({
            "success": True,
            "tenant_id": tenant_id,
            "total_unembedded": total_unembedded,
            "showing": len(results),
            "summary": {
                "null_content": null_content,
                "empty_content": empty_content,
                "has_content": has_content,
            },
            "documents": results,
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        db.close()


@admin_bp.route('/refresh-models', methods=['POST'])
@require_auth
def refresh_models():
    """
    Download latest models from S3 and hot-swap in memory.
    Super admin only. Zero downtime.

    POST /api/admin/refresh-models
    {"force": false}
    """
    db = get_db()
    try:
        user = db.query(User).filter(User.id == g.user_id).first()
        if not user or user.email not in SUPER_ADMIN_EMAILS:
            return jsonify({"success": False, "error": "Forbidden"}), 403

        data = request.get_json(silent=True) or {}
        force = data.get('force', False)

        # Step 1: Sync from S3
        from scripts.sync_models_from_s3 import sync_models
        sync_result = sync_models(force=force)

        # Step 2: Reload in-memory models
        from services.paper_type_detector import PaperTypeDetector
        from services.ml_tier_predictor import reload_ml_tier_predictor

        pt_available = PaperTypeDetector.reload_ml_model()
        tier_available = reload_ml_tier_predictor()

        return jsonify({
            "success": True,
            "s3_sync": sync_result,
            "models_reloaded": {
                "paper_type_detector": pt_available,
                "tier_predictor": tier_available,
            },
            "metadata": sync_result.get("metadata", {}),
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        db.close()


@admin_bp.route('/slack-connect/channels', methods=['POST'])
@require_auth
def register_slack_connect_channel():
    """Register a Slack Connect shared channel → tenant mapping."""
    try:
        db = get_db()
        try:
            # Admin check
            user = db.query(User).filter(User.id == g.user_id).first()
            if not user or user.role != UserRole.ADMIN:
                return jsonify({'success': False, 'error': 'Admin access required'}), 403

            data = request.get_json()
            if not data:
                return jsonify({'success': False, 'error': 'JSON body required'}), 400

            channel_id = data.get('channel_id', '').strip()
            tenant_id = data.get('tenant_id', '').strip()
            channel_name = data.get('channel_name', '').strip()

            if not channel_id or not tenant_id:
                return jsonify({'success': False, 'error': 'channel_id and tenant_id are required'}), 400

            # Verify tenant exists
            tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
            if not tenant:
                return jsonify({'success': False, 'error': f'Tenant {tenant_id} not found'}), 404

            # Check for existing mapping
            existing = db.query(ChannelTenantMapping).filter(
                ChannelTenantMapping.channel_id == channel_id
            ).first()

            if existing:
                existing.tenant_id = tenant_id
                existing.channel_name = channel_name or existing.channel_name
                existing.is_active = True
                db.commit()
                mapping = existing
            else:
                mapping = ChannelTenantMapping(
                    channel_id=channel_id,
                    tenant_id=tenant_id,
                    channel_name=channel_name,
                )
                db.add(mapping)
                db.commit()

            # Invalidate cache
            from services.slack_bot_service import invalidate_channel_cache
            invalidate_channel_cache(channel_id)

            print(f"[Admin] Slack Connect channel registered: {channel_id} -> tenant {tenant_id[:8]}...", flush=True)

            return jsonify({
                'success': True,
                'mapping': mapping.to_dict(),
                'tenant_name': tenant.name,
            }), 201
        finally:
            db.close()
    except Exception as e:
        print(f"[Admin] Error registering channel: {e}", flush=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/slack-connect/channels', methods=['GET'])
@require_auth
def list_slack_connect_channels():
    """List all Slack Connect channel → tenant mappings."""
    try:
        db = get_db()
        try:
            user = db.query(User).filter(User.id == g.user_id).first()
            if not user or user.role != UserRole.ADMIN:
                return jsonify({'success': False, 'error': 'Admin access required'}), 403

            mappings = db.query(ChannelTenantMapping).all()

            result = []
            for m in mappings:
                d = m.to_dict()
                tenant = db.query(Tenant).filter(Tenant.id == m.tenant_id).first()
                d['tenant_name'] = tenant.name if tenant else 'Unknown'
                result.append(d)

            return jsonify({'success': True, 'channels': result})
        finally:
            db.close()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/slack-connect/channels/<channel_id>', methods=['DELETE'])
@require_auth
def delete_slack_connect_channel(channel_id):
    """Remove a Slack Connect channel mapping."""
    try:
        db = get_db()
        try:
            user = db.query(User).filter(User.id == g.user_id).first()
            if not user or user.role != UserRole.ADMIN:
                return jsonify({'success': False, 'error': 'Admin access required'}), 403

            mapping = db.query(ChannelTenantMapping).filter(
                ChannelTenantMapping.channel_id == channel_id
            ).first()

            if not mapping:
                return jsonify({'success': False, 'error': 'Channel mapping not found'}), 404

            db.delete(mapping)
            db.commit()

            from services.slack_bot_service import invalidate_channel_cache
            invalidate_channel_cache(channel_id)

            print(f"[Admin] Slack Connect channel removed: {channel_id}", flush=True)
            return jsonify({'success': True, 'message': f'Channel {channel_id} mapping removed'})
        finally:
            db.close()
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
