"""
Email Forwarding API Routes
Endpoints for email forwarding integration
"""

from flask import Blueprint, jsonify, g
from sqlalchemy.orm import Session

from database.models import SessionLocal, Document
from services.auth_service import require_auth
from services.email_forwarding_service import poll_forwarded_emails
from services.embedding_service import get_embedding_service

# Import config
try:
    from config.config import Config
    HAS_CONFIG = True
except ImportError:
    HAS_CONFIG = False
    Config = None


# Create blueprint
email_forwarding_bp = Blueprint('email_forwarding', __name__, url_prefix='/api/email-forwarding')


def get_db():
    """Get database session"""
    return SessionLocal()


# ============================================================================
# FETCH FORWARDED EMAILS
# ============================================================================

@email_forwarding_bp.route('/fetch', methods=['POST'])
@require_auth
def fetch_emails():
    """
    Fetch forwarded emails from beatatucla@gmail.com inbox

    Response:
    {
        "success": true,
        "processed": 5,
        "total": 5,
        "errors": []
    }
    """
    try:
        db = get_db()
        try:
            # Get config
            config = Config if HAS_CONFIG else None

            # Use tenant_id from authenticated user (set by @require_auth)
            tenant_id = g.tenant_id

            # Poll emails
            result = poll_forwarded_emails(
                tenant_id=tenant_id,
                db=db,
                config=config,
                max_emails=50
            )

            # Embed newly created documents to Pinecone
            if result.get('success') and result.get('processed', 0) > 0:
                try:
                    # Get documents that were just created (not yet embedded)
                    new_docs = db.query(Document).filter(
                        Document.tenant_id == tenant_id,
                        Document.source_type.in_(['email', 'email_attachment']),
                        Document.embedded_at == None,
                        Document.content != None,
                        Document.content != ''
                    ).all()

                    if new_docs:
                        embedding_service = get_embedding_service()
                        embed_result = embedding_service.embed_documents(
                            documents=new_docs,
                            tenant_id=tenant_id,
                            db=db
                        )
                        result['embedded'] = embed_result.get('embedded', 0)
                        print(f"[EmailForwarding] Embedded {embed_result.get('embedded', 0)} documents to Pinecone")
                except Exception as embed_err:
                    print(f"[EmailForwarding] Warning: Failed to embed documents: {embed_err}")
                    result['embed_warning'] = str(embed_err)

            return jsonify(result)

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# GET STATUS
# ============================================================================

@email_forwarding_bp.route('/status', methods=['GET'])
@require_auth
def get_status():
    """
    Get email forwarding status and instructions (requires auth)

    Response:
    {
        "success": true,
        "forwarding_address": "beatatucla+tenant123@gmail.com",
        "instructions": "Forward emails to...",
        "configured": true
    }
    """
    import os
    from services.email_forwarding_service import EmailForwardingService

    base_email = os.getenv("FORWARD_EMAIL_ADDRESS", "beatatucla@gmail.com")
    email_password = os.getenv("FORWARD_EMAIL_PASSWORD")

    # Generate tenant-specific email address using plus addressing
    tenant_email = EmailForwardingService.get_tenant_email(base_email, g.tenant_id)

    return jsonify({
        "success": True,
        "forwarding_address": tenant_email,
        "configured": bool(email_password),
        "instructions": f"""
To add emails to your knowledge base:

1. Forward any email to: {tenant_email}
2. Click the "Fetch Emails" button or we'll check automatically every hour
3. Your forwarded emails will appear in the Documents page
4. Review and classify them as Work or Personal

You control what goes into your knowledge base - only forward what you want to save!
        """.strip()
    })


@email_forwarding_bp.route('/status-public', methods=['GET'])
def get_status_public():
    """
    Get email forwarding status (PUBLIC - no auth required for testing)
    """
    import os

    email_address = os.getenv("FORWARD_EMAIL_ADDRESS", "beatatucla@gmail.com")
    email_password = os.getenv("FORWARD_EMAIL_PASSWORD")

    return jsonify({
        "success": True,
        "forwarding_address": email_address,
        "configured": bool(email_password),
        "instructions": f"Forward emails to {email_address}"
    })


@email_forwarding_bp.route('/fetch-public', methods=['POST'])
def fetch_emails_public():
    """
    Fetch forwarded emails (PUBLIC - no auth required for testing)
    Creates documents with local-tenant for testing

    NOTE: This can take 30-60 seconds if there are many emails.
    For production, use a background task queue (Celery/RQ).
    """
    db = get_db()
    try:
        # Get config
        config = Config if HAS_CONFIG else None

        # Use local-tenant for testing (consistent with other routes)
        tenant_id = "local-tenant"

        # Poll emails - this is SYNCHRONOUS and can take time
        # For production: move this to a background job queue
        result = poll_forwarded_emails(
            tenant_id=tenant_id,
            db=db,
            config=config,
            max_emails=10  # Reduced from 50 to make it faster for testing
        )

        # Embed newly created documents to Pinecone
        if result.get('success') and result.get('processed', 0) > 0:
            try:
                # Get documents that were just created (not yet embedded)
                new_docs = db.query(Document).filter(
                    Document.tenant_id == tenant_id,
                    Document.source_type.in_(['email', 'email_attachment']),
                    Document.embedded_at == None,
                    Document.content != None,
                    Document.content != ''
                ).all()

                if new_docs:
                    embedding_service = get_embedding_service()
                    embed_result = embedding_service.embed_documents(
                        documents=new_docs,
                        tenant_id=tenant_id,
                        db=db
                    )
                    result['embedded'] = embed_result.get('embedded', 0)
                    print(f"[EmailForwarding] Embedded {embed_result.get('embedded', 0)} documents to Pinecone")
            except Exception as embed_err:
                print(f"[EmailForwarding] Warning: Failed to embed documents: {embed_err}")
                result['embed_warning'] = str(embed_err)

        return jsonify(result)

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
    finally:
        db.close()
