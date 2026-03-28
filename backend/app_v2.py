"""
2nd Brain - Enterprise Knowledge Transfer Platform
Version 2.0 - B2B SaaS Edition

Complete Flask application with:
- Multi-tenant authentication (JWT + bcrypt)
- Integration connectors (Gmail, Slack, Box)
- Document classification (AI-powered work/personal)
- Knowledge gap detection and answer persistence
- Video generation
- Advanced RAG search
"""

import os
import time
import json
import secrets
from pathlib import Path
from datetime import datetime, timezone

from flask import Flask, jsonify, request, g, Response, stream_with_context
from flask_cors import CORS
from dotenv import load_dotenv
from services.auth_service import require_auth
from services.intent_classifier import get_intent_classifier

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", secrets.token_hex(32))

# Session cookie configuration for OAuth redirects
# SameSite=Lax allows cookies to be sent on OAuth redirects (top-level navigation)
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.getenv('FLASK_ENV') == 'production'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = 600  # 10 minutes for OAuth flow
app.config['MAX_CONTENT_LENGTH'] = None  # No upload size limit

# CORS configuration - use CORS_ORIGINS env var or defaults
_cors_origins = os.getenv("CORS_ORIGINS", "").split(",") if os.getenv("CORS_ORIGINS") else []
if os.getenv('FLASK_ENV') != 'production':
    _cors_origins.extend([
        "http://localhost:3000",
        "http://localhost:3006",
        "http://localhost:3007",
    ])
_cors_origins.extend([
    "https://use2ndbrain.com",
    "https://www.use2ndbrain.com",
    "https://api.use2ndbrain.com",
])
CORS(app,
     supports_credentials=True,
     resources={
         r"/api/*": {
             "origins": list(set(_cors_origins)),
             "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
             "allow_headers": ["Content-Type", "Authorization"]
         }
     })

# ============================================================================
# GLOBAL ERROR LOGGING
# ============================================================================

from utils.logger import setup_logger, log_error, log_info, log_warning

_app_logger = setup_logger("app")

@app.errorhandler(Exception)
def handle_exception(e):
    """Global exception handler - logs all unhandled errors."""
    log_error("app", f"Unhandled exception on {request.method} {request.path}", error=e)
    # Never leak exception details to clients in production
    if os.getenv('FLASK_ENV') == 'development':
        return jsonify({"error": "Internal server error", "message": str(e)}), 500
    return jsonify({"error": "Internal server error"}), 500

@app.errorhandler(413)
def handle_413(e):
    return jsonify({"error": "File too large. Maximum upload size is 1GB."}), 413

@app.errorhandler(404)
def handle_404(e):
    return jsonify({"error": "Not found", "path": request.path}), 404

@app.before_request
def log_slack_requests():
    """Log ALL POST requests that might be Slack events for debugging."""
    if request.method == 'POST':
        slack_sig = request.headers.get('X-Slack-Signature', '')
        slack_ts = request.headers.get('X-Slack-Request-Timestamp', '')
        if slack_sig or slack_ts or 'slack' in request.path.lower():
            print(f"[GLOBAL-LOG] POST {request.path} from={request.remote_addr} "
                  f"content_type={request.content_type} len={request.content_length} "
                  f"slack_sig={'YES' if slack_sig else 'NO'} slack_ts={slack_ts}", flush=True)

@app.after_request
def log_response(response):
    """Log non-2xx responses for debugging."""
    if response.status_code >= 400:
        log_warning("app", f"{request.method} {request.path} -> {response.status_code}")
    return response

# ============================================================================
# DATABASE INITIALIZATION
# ============================================================================

from database.models import init_database, SessionLocal, engine
from sqlalchemy import text

# Initialize database tables
try:
    init_database()
    print("✓ Database initialized")

    # Warm up database connection pool for faster first request
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    print("✓ Database connection warmed up")
except Exception as e:
    print(f"⚠ Database initialization error: {e}")

# Ensure all connector type enum values exist in PostgreSQL
def ensure_connector_enum_values():
    """
    Add any missing enum values to PostgreSQL connectortype enum.

    IMPORTANT: SQLAlchemy Enum(PythonEnum) uses enum NAMES (uppercase),
    not enum VALUES (lowercase). So we need to add 'ZOTERO' not 'zotero'.
    """
    # These must be UPPERCASE - matching the Python enum NAMES
    enum_values_to_add = ['ZOTERO', 'WEBSCRAPER', 'QUARTZY']

    try:
        with engine.connect() as conn:
            for value in enum_values_to_add:
                try:
                    # Check if value exists in enum
                    result = conn.execute(text(
                        "SELECT 1 FROM pg_enum WHERE enumlabel = :value AND enumtypid = "
                        "(SELECT oid FROM pg_type WHERE typname = 'connectortype')"
                    ), {"value": value})

                    if not result.fetchone():
                        # Add the value if it doesn't exist
                        # Validate against whitelist to prevent SQL injection
                        if not value.isalpha():
                            print(f"⚠ Skipping invalid enum value: {value}")
                            continue
                        conn.execute(text(f"ALTER TYPE connectortype ADD VALUE '{value}'"))
                        conn.commit()
                        print(f"✓ Added '{value}' to connectortype enum")
                    else:
                        print(f"✓ Enum value '{value}' already exists")
                except Exception as inner_e:
                    # Value might already exist or other issue
                    print(f"⚠ Could not add enum value '{value}': {inner_e}")
    except Exception as e:
        print(f"⚠ Enum migration error (non-fatal): {e}")

# Run enum migration
try:
    ensure_connector_enum_values()
except Exception as e:
    print(f"⚠ Enum migration failed (non-fatal): {e}")

# Add missing columns to existing production databases
def ensure_missing_columns():
    """Add columns that were added after initial schema creation."""
    migrations = [
        ("documents", "feedback_score", "ALTER TABLE documents ADD COLUMN feedback_score FLOAT DEFAULT 0.0"),
        ("projects", "color", "ALTER TABLE projects ADD COLUMN color VARCHAR(7)"),
        ("tenants", "research_profile", "ALTER TABLE tenants ADD COLUMN research_profile JSON"),
        ("tenants", "profile_updated_at", "ALTER TABLE tenants ADD COLUMN profile_updated_at TIMESTAMP WITH TIME ZONE"),
        ("tenants", "profile_building", "ALTER TABLE tenants ADD COLUMN profile_building BOOLEAN DEFAULT FALSE"),
        ("chat_messages", "message_type", "ALTER TABLE chat_messages ADD COLUMN message_type VARCHAR(20) DEFAULT 'text'"),
    ]
    try:
        with engine.connect() as conn:
            for table, column, sql in migrations:
                result = conn.execute(text(
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_name = :table AND column_name = :column"
                ), {"table": table, "column": column})
                if not result.fetchone():
                    conn.execute(text(sql))
                    conn.commit()
                    print(f"✓ Added column '{column}' to '{table}'")
    except Exception as e:
        print(f"⚠ Column migration error (non-fatal): {e}")

try:
    ensure_missing_columns()
except Exception as e:
    print(f"⚠ Column migration failed (non-fatal): {e}")

# Widen journal_profiles varchar columns to text (fix truncation errors)
def migrate_journal_columns():
    """Alter journal_profiles varchar columns to text to prevent truncation."""
    alterations = [
        ("journal_profiles", "name", "ALTER TABLE journal_profiles ALTER COLUMN name TYPE TEXT"),
        ("journal_profiles", "primary_subfield", "ALTER TABLE journal_profiles ALTER COLUMN primary_subfield TYPE TEXT"),
        ("journal_profiles", "publisher", "ALTER TABLE journal_profiles ALTER COLUMN publisher TYPE TEXT"),
        ("journal_profiles", "homepage_url", "ALTER TABLE journal_profiles ALTER COLUMN homepage_url TYPE TEXT"),
        ("journal_profiles", "sjr_quartile", "ALTER TABLE journal_profiles ALTER COLUMN sjr_quartile TYPE VARCHAR(4)"),
        ("journal_profiles", "data_source", "ALTER TABLE journal_profiles ALTER COLUMN data_source TYPE VARCHAR(50)"),
    ]
    try:
        with engine.connect() as conn:
            # Check if table exists first
            result = conn.execute(text(
                "SELECT 1 FROM information_schema.tables WHERE table_name = 'journal_profiles'"
            ))
            if not result.fetchone():
                return
            for table, column, sql in alterations:
                try:
                    conn.execute(text(sql))
                    conn.commit()
                except Exception:
                    conn.rollback()
    except Exception as e:
        print(f"⚠ Journal column migration (non-fatal): {e}")

try:
    migrate_journal_columns()
except Exception as e:
    print(f"⚠ Journal migration failed (non-fatal): {e}")

# ============================================================================
# REGISTER API BLUEPRINTS
# ============================================================================

from api.auth_routes import auth_bp
from api.integration_routes import integration_bp
from api.document_routes import document_bp
from api.knowledge_routes import knowledge_bp
from api.video_routes import video_bp
from api.chat_routes import chat_bp
from api.jobs_routes import jobs_bp
from api.slack_bot_routes import slack_bot_bp
from api.profile_routes import profile_bp
from api.github_routes import github_bp
from api.sync_progress_routes import sync_progress_bp
from api.syncs_routes import syncs_bp
from api.email_forwarding_routes import email_forwarding_bp
from api.admin_routes import admin_bp, ensure_admins, fix_untitled_conversations
from api.website_routes import website_bp
from api.project_routes import project_bp
from api.inventory_routes import inventory_bp
from api.co_researcher_routes import co_researcher_bp
from api.research_translator_routes import research_translator_bp
from api.journal_routes import journal_bp
from api.reproducibility_routes import reproducibility_bp
from api.protocol_graph_routes import protocol_graph_bp
from api.protocol_optimizer_routes import protocol_optimizer_bp
from api.experiment_routes import experiment_bp
from api.training_guide_routes import training_guide_bp
from api.paper_analysis_routes import paper_analysis_bp
from api.paper_to_code_routes import paper_to_code_bp
from api.competitor_finder_routes import competitor_finder_bp
from api.idea_reality_routes import idea_reality_bp
# share_bp removed - replaced by invitation system in auth_routes

app.register_blueprint(auth_bp)
# IMPORTANT: Register github_bp BEFORE integration_bp so /api/integrations/github/* routes
# take precedence over the generic /<connector_type>/* routes in integration_bp
app.register_blueprint(github_bp)
app.register_blueprint(integration_bp)
app.register_blueprint(document_bp)
app.register_blueprint(knowledge_bp)
app.register_blueprint(video_bp)
app.register_blueprint(chat_bp)
app.register_blueprint(jobs_bp)
app.register_blueprint(slack_bot_bp)
app.register_blueprint(profile_bp)
app.register_blueprint(sync_progress_bp)
app.register_blueprint(syncs_bp)
app.register_blueprint(email_forwarding_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(website_bp)
app.register_blueprint(project_bp)
app.register_blueprint(inventory_bp)
app.register_blueprint(co_researcher_bp)
app.register_blueprint(research_translator_bp)
app.register_blueprint(journal_bp)
app.register_blueprint(reproducibility_bp)
app.register_blueprint(protocol_graph_bp)
app.register_blueprint(protocol_optimizer_bp)
app.register_blueprint(experiment_bp)
app.register_blueprint(training_guide_bp)
app.register_blueprint(paper_analysis_bp)
app.register_blueprint(paper_to_code_bp)
app.register_blueprint(competitor_finder_bp)
app.register_blueprint(idea_reality_bp)
from api.orchestrator_routes import orchestrator_bp
app.register_blueprint(orchestrator_bp)
# share_bp removed - invitation system lives in auth_bp

print("✓ API blueprints registered")

# Check journal data freshness and schedule monthly auto-refresh
try:
    from services.journal_data_service import get_journal_data_service
    _jds = get_journal_data_service()
    if not _jds.check_freshness():
        print("⚠ Journal data stale or missing — auto-populating in background...")
        import threading
        def _auto_populate():
            try:
                _jds.populate_journals()
                print("✓ Journal auto-population complete")
            except Exception as _pe:
                print(f"⚠ Journal auto-population failed: {_pe}")
        threading.Thread(target=_auto_populate, daemon=True).start()
    else:
        print("✓ Journal data is fresh")
except Exception as _e:
    print(f"⚠ Journal data check skipped: {_e}")

# Monthly journal data refresh — runs a background check every 24h
def _start_journal_refresh_scheduler():
    """Background thread that checks data freshness daily and refreshes if stale (>30 days)."""
    import time as _time
    def _scheduler_loop():
        while True:
            _time.sleep(86400)  # check every 24 hours
            try:
                svc = get_journal_data_service()
                if not svc.check_freshness():
                    print("[JournalRefresh] Data is stale — starting monthly refresh...")
                    svc.populate_journals()
                    print("[JournalRefresh] Monthly refresh complete")
            except Exception as e:
                print(f"[JournalRefresh] Error: {e}")
    t = threading.Thread(target=_scheduler_loop, daemon=True, name="journal-refresh")
    t.start()
    print("✓ Journal monthly refresh scheduler started")

try:
    _start_journal_refresh_scheduler()
except Exception as _e:
    print(f"⚠ Journal scheduler skipped: {_e}")

# Auto-embedding scheduler — indexes unembedded documents across ALL tenants every 24h
def _start_auto_embedding_scheduler():
    """Background thread that finds and embeds unindexed documents for all tenants."""
    import time as _time
    from database.models import SessionLocal, Document, Tenant
    from services.embedding_service import get_embedding_service

    def _embedding_loop():
        while True:
            _time.sleep(86400)  # run every 24 hours
            print("[AutoEmbed] Starting scheduled embedding check...", flush=True)
            try:
                db = SessionLocal()
                try:
                    tenants = db.query(Tenant).filter(Tenant.is_active == True).all()
                    total_embedded = 0
                    total_errors = 0

                    for tenant in tenants:
                        unembedded_count = db.query(Document).filter(
                            Document.tenant_id == tenant.id,
                            Document.embedded_at == None,
                            Document.is_deleted == False,
                            Document.content != None,
                            Document.content != ''
                        ).count()

                        if unembedded_count == 0:
                            continue

                        print(f"[AutoEmbed] Tenant '{tenant.name}': {unembedded_count} unindexed docs", flush=True)
                        try:
                            embedding_service = get_embedding_service()
                            result = embedding_service.embed_tenant_documents(
                                tenant_id=tenant.id,
                                db=db,
                                force_reembed=False
                            )
                            embedded = result.get('embedded', 0)
                            errors = len(result.get('errors', []))
                            total_embedded += embedded
                            total_errors += errors
                            print(f"[AutoEmbed] Tenant '{tenant.name}': embedded {embedded} chunks, {errors} errors", flush=True)
                        except Exception as e:
                            print(f"[AutoEmbed] Tenant '{tenant.name}' failed: {e}", flush=True)
                            total_errors += 1

                    print(f"[AutoEmbed] Complete: {total_embedded} total chunks, {total_errors} errors", flush=True)
                finally:
                    db.close()
            except Exception as e:
                print(f"[AutoEmbed] Scheduler error: {e}", flush=True)

    t = threading.Thread(target=_embedding_loop, daemon=True, name="auto-embedding")
    t.start()
    print("✓ Auto-embedding scheduler started (runs every 24h)")

try:
    _start_auto_embedding_scheduler()
except Exception as _e:
    print(f"⚠ Auto-embedding scheduler skipped: {_e}")

# Ensure configured admin users have admin role
ensure_admins()

# Fix any existing conversations with no title
fix_untitled_conversations()

# ============================================================================
# LEGACY COMPATIBILITY - Import existing routes
# ============================================================================

# Import existing RAG and search functionality
try:
    BASE_DIR = Path(__file__).parent

    # Azure OpenAI Configuration
    AZURE_OPENAI_ENDPOINT = os.getenv(
        "AZURE_OPENAI_ENDPOINT",
        "https://rishi-mihfdoty-eastus2.cognitiveservices.azure.com"
    )
    AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
    AZURE_API_VERSION = os.getenv("AZURE_API_VERSION", "2024-12-01-preview")
    AZURE_CHAT_DEPLOYMENT = os.getenv("AZURE_CHAT_DEPLOYMENT", "gpt-4o")

    # Tenant data directories
    TENANT_DATA_DIRS = {
        "beat": BASE_DIR / "club_data",
        "enron": BASE_DIR / "data"
    }

    # RAG instances per tenant
    tenant_rag_instances = {}

    def get_rag_for_tenant(tenant_id: str):
        """Get or create RAG instance for tenant"""
        print(f"[RAG DEBUG] Getting RAG for tenant: {tenant_id}", flush=True)

        if tenant_id in tenant_rag_instances:
            print(f"[RAG DEBUG] Found cached RAG for tenant {tenant_id}", flush=True)
            return tenant_rag_instances[tenant_id]

        # Check for tenant-specific data
        tenant_dir = TENANT_DATA_DIRS.get(tenant_id)
        print(f"[RAG DEBUG] TENANT_DATA_DIRS lookup: {tenant_dir}", flush=True)

        if not tenant_dir:
            # Check database for tenant data directory
            db = SessionLocal()
            try:
                from database.models import Tenant
                tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
                print(f"[RAG DEBUG] DB tenant lookup: {tenant}", flush=True)
                if tenant and tenant.data_directory:
                    tenant_dir = Path(tenant.data_directory)
                    print(f"[RAG DEBUG] Using DB tenant_dir: {tenant_dir}", flush=True)
            finally:
                db.close()

        if not tenant_dir:
            print(f"[RAG DEBUG] No tenant_dir found, returning None", flush=True)
            return None

        # Try to load RAG
        try:
            from rag.enhanced_rag_v2 import EnhancedRAGv2
            embedding_index_path = str(tenant_dir / "embedding_index.pkl")
            print(f"[RAG DEBUG] Checking index path: {embedding_index_path}", flush=True)
            print(f"[RAG DEBUG] Index exists: {Path(embedding_index_path).exists()}", flush=True)

            if Path(embedding_index_path).exists():
                print(f"[RAG DEBUG] Loading RAG from {embedding_index_path}", flush=True)
                rag = EnhancedRAGv2(
                    embedding_index_path=embedding_index_path,
                    openai_api_key=AZURE_OPENAI_API_KEY,
                    use_reranker=True,
                    use_mmr=True,
                    cache_results=True
                )
                tenant_rag_instances[tenant_id] = rag
                print(f"[RAG DEBUG] RAG loaded successfully!", flush=True)
                return rag
            else:
                print(f"[RAG DEBUG] Index file not found at {embedding_index_path}", flush=True)
        except Exception as e:
            print(f"Error loading RAG for tenant {tenant_id}: {e}", flush=True)
            import traceback
            traceback.print_exc()

        print(f"[RAG DEBUG] Returning None", flush=True)
        return None

    print("✓ RAG system configured")

except Exception as e:
    print(f"⚠ RAG system not loaded: {e}")

# ============================================================================
# ROOT & HEALTH CHECK
# ============================================================================

@app.route('/', methods=['GET'])
def root():
    """Root endpoint - API info"""
    return jsonify({
        "name": "2nd Brain API",
        "version": "2.0.0",
        "description": "Enterprise Knowledge Transfer Platform",
        "endpoints": {
            "health": "/api/health",
            "auth": {
                "signup": "POST /api/auth/signup",
                "login": "POST /api/auth/login",
                "me": "GET /api/auth/me"
            },
            "integrations": "GET /api/integrations",
            "documents": "GET /api/documents",
            "search": "POST /api/search"
        }
    })

@app.route('/api/health', methods=['GET'])
def health_check():
    """
    Enhanced health check endpoint.

    Checks:
    - Database connectivity (required)
    - Pinecone availability (optional, if CHECK_PINECONE=true)
    - Azure OpenAI availability (optional, if CHECK_AZURE_OPENAI=true)

    Used by Render for health monitoring.
    Returns 200 if healthy, 503 if critical services fail.
    """
    from utils.logger import log_warning
    from sqlalchemy import text
    import time

    start_time = time.time()
    health_status = {
        "status": "healthy",
        "version": "2.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": {},
        "features": {
            "auth": True,
            "integrations": True,
            "classification": True,
            "video_generation": True,
            "rag_search": AZURE_OPENAI_API_KEY is not None
        }
    }

    # 1. Database check (CRITICAL)
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        health_status["checks"]["database"] = "ok"
    except Exception as e:
        health_status["checks"]["database"] = f"error: {str(e)}"
        health_status["status"] = "unhealthy"
        log_warning("HealthCheck", "Database check failed", error=str(e))

    # 2. Pinecone check (optional - can be slow)
    if os.getenv("CHECK_PINECONE") == "true":
        try:
            from vector_stores.pinecone_store import PineconeVectorStore
            store = PineconeVectorStore()
            store.index.describe_index_stats()
            health_status["checks"]["pinecone"] = "ok"
        except Exception as e:
            health_status["checks"]["pinecone"] = f"warning: {str(e)}"
            log_warning("HealthCheck", "Pinecone check failed", error=str(e))

    # 3. Azure OpenAI check (optional - only if critical)
    if os.getenv("CHECK_AZURE_OPENAI") == "true":
        try:
            from azure_openai_config import get_azure_client
            client = get_azure_client()
            # Simple check - just verify client exists
            health_status["checks"]["azure_openai"] = "ok" if client else "warning: no client"
        except Exception as e:
            health_status["checks"]["azure_openai"] = f"warning: {str(e)}"
            log_warning("HealthCheck", "Azure OpenAI check failed", error=str(e))

    # 4. Web scraper check (self-hosted crawler)
    try:
        from connectors.webscraper_connector import HTML2TEXT_AVAILABLE, OCR_AVAILABLE
        health_status["checks"]["webscraper"] = {
            "html2text": HTML2TEXT_AVAILABLE,
            "ocr": OCR_AVAILABLE,
        }
    except Exception as e:
        health_status["checks"]["webscraper"] = f"error: {str(e)}"

    # Response time
    health_status["response_time_ms"] = round((time.time() - start_time) * 1000, 2)

    # Return 200 if healthy, 503 if unhealthy
    status_code = 200 if health_status["status"] == "healthy" else 503

    return jsonify(health_status), status_code


@app.route('/api/diagnostics/embedding', methods=['GET'])
def embedding_diagnostics():
    """
    Diagnostic endpoint to verify embedding/RAG configuration.

    Checks:
    - PINECONE_API_KEY is set
    - OPENAI_API_KEY or AZURE_OPENAI_API_KEY is set
    - Pinecone connection works
    - Embedding generation works

    Use this to debug why documents aren't being embedded.
    """
    diagnostics = {
        "status": "checking",
        "env_vars": {},
        "services": {},
        "test_results": {},
        "errors": [],
        "recommendations": []
    }

    # Check environment variables (show if set, not actual values)
    env_checks = {
        "PINECONE_API_KEY": os.getenv("PINECONE_API_KEY"),
        "PINECONE_INDEX": os.getenv("PINECONE_INDEX", "knowledgevault"),
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
        "AZURE_OPENAI_API_KEY": os.getenv("AZURE_OPENAI_API_KEY"),
        "AZURE_OPENAI_ENDPOINT": os.getenv("AZURE_OPENAI_ENDPOINT"),
        "AZURE_EMBEDDING_DEPLOYMENT": os.getenv("AZURE_EMBEDDING_DEPLOYMENT"),
        "USE_AZURE_OPENAI": os.getenv("USE_AZURE_OPENAI", "false")
    }

    for key, value in env_checks.items():
        if key in ["PINECONE_INDEX", "USE_AZURE_OPENAI", "AZURE_EMBEDDING_DEPLOYMENT"]:
            diagnostics["env_vars"][key] = value or "(not set)"
        else:
            diagnostics["env_vars"][key] = "set" if value else "NOT SET"

    # Check 1: Pinecone API Key
    if not os.getenv("PINECONE_API_KEY"):
        diagnostics["errors"].append("PINECONE_API_KEY is not set - embeddings cannot be stored")
        diagnostics["recommendations"].append("Set PINECONE_API_KEY in Render environment variables")

    # Check 2: OpenAI/Azure credentials for embeddings
    use_azure = os.getenv("USE_AZURE_OPENAI", "false").lower() == "true"
    if use_azure:
        if not os.getenv("AZURE_OPENAI_API_KEY"):
            diagnostics["errors"].append("AZURE_OPENAI_API_KEY is not set - cannot generate embeddings")
            diagnostics["recommendations"].append("Set AZURE_OPENAI_API_KEY in Render environment variables")
        if not os.getenv("AZURE_OPENAI_ENDPOINT"):
            diagnostics["errors"].append("AZURE_OPENAI_ENDPOINT is not set")
            diagnostics["recommendations"].append("Set AZURE_OPENAI_ENDPOINT in Render environment variables")
    else:
        # Note: pinecone_store.py uses Azure OpenAI directly in _get_embeddings_batch
        # So we still need Azure credentials for batch embedding
        if not os.getenv("OPENAI_API_KEY") and not os.getenv("AZURE_OPENAI_API_KEY"):
            diagnostics["errors"].append("Neither OPENAI_API_KEY nor AZURE_OPENAI_API_KEY is set - cannot generate embeddings")
            diagnostics["recommendations"].append("Set OPENAI_API_KEY or AZURE_OPENAI_API_KEY in Render environment variables")

    # Try to initialize Pinecone
    try:
        from vector_stores.pinecone_store import get_vector_store
        store = get_vector_store()
        stats = store.index.describe_index_stats()
        diagnostics["services"]["pinecone"] = "connected"
        diagnostics["test_results"]["pinecone_stats"] = {
            "total_vectors": stats.total_vector_count,
            "dimension": stats.dimension,
            "namespaces": list(stats.namespaces.keys()) if stats.namespaces else []
        }
    except ValueError as e:
        diagnostics["services"]["pinecone"] = f"config_error: {str(e)}"
        diagnostics["errors"].append(f"Pinecone config error: {str(e)}")
    except Exception as e:
        diagnostics["services"]["pinecone"] = f"error: {str(e)}"
        diagnostics["errors"].append(f"Pinecone error: {str(e)}")

    # Try to initialize OpenAI client
    try:
        from services.openai_client import get_openai_client
        client = get_openai_client()
        diagnostics["services"]["openai_client"] = "initialized"
        diagnostics["test_results"]["openai_mode"] = "azure" if client.use_azure else "openai"
        diagnostics["test_results"]["embedding_model"] = client.embedding_model
    except Exception as e:
        diagnostics["services"]["openai_client"] = f"error: {str(e)}"
        diagnostics["errors"].append(f"OpenAI client error: {str(e)}")

    # Test embedding generation (optional, can be slow)
    if request.args.get("test_embedding") == "true":
        try:
            from services.openai_client import get_openai_client
            client = get_openai_client()
            result = client.create_embedding("test", dimensions=1536)
            if result and result.data:
                diagnostics["test_results"]["embedding_test"] = "success"
                diagnostics["test_results"]["embedding_dimensions"] = len(result.data[0].embedding)
        except Exception as e:
            diagnostics["test_results"]["embedding_test"] = f"failed: {str(e)}"
            diagnostics["errors"].append(f"Embedding test failed: {str(e)}")

    # Determine overall status
    if diagnostics["errors"]:
        diagnostics["status"] = "unhealthy"
    else:
        diagnostics["status"] = "healthy"

    return jsonify(diagnostics), 200 if diagnostics["status"] == "healthy" else 503


@app.route('/api/diagnostics/slack', methods=['GET'])
def slack_diagnostics():
    """
    Diagnostic endpoint to verify Slack bot configuration and workspace mappings.

    Query params:
        team_id: Optional Slack team ID to check specific workspace
        tenant_id: Optional tenant ID to check vectors
    """
    from database.models import Connector, ConnectorType

    diagnostics = {
        "status": "checking",
        "slack_connectors": [],
        "workspace_lookup": {},
        "pinecone_stats": {},
        "errors": [],
        "recommendations": []
    }

    db = SessionLocal()
    try:
        # Get all Slack connectors
        slack_connectors = db.query(Connector).filter(
            Connector.connector_type == ConnectorType.SLACK,
            Connector.is_active == True
        ).all()

        for conn in slack_connectors:
            team_id = conn.settings.get('team_id', 'unknown') if conn.settings else 'unknown'
            team_name = conn.settings.get('team_name', 'unknown') if conn.settings else 'unknown'
            diagnostics["slack_connectors"].append({
                "id": conn.id[:8] + "...",
                "tenant_id": conn.tenant_id[:8] + "...",
                "team_id": team_id,
                "team_name": team_name,
                "status": conn.status.value if conn.status else "unknown",
                "has_access_token": bool(conn.access_token),
                "last_sync": conn.last_sync_at.isoformat() if conn.last_sync_at else None,
                "items_synced": conn.total_items_synced
            })

        if not slack_connectors:
            diagnostics["errors"].append("No active Slack connectors found")
            diagnostics["recommendations"].append("Connect Slack from the Integrations page")

        # Check specific team_id if provided
        team_id = request.args.get("team_id")
        if team_id:
            from services.slack_bot_service import get_tenant_for_workspace, get_bot_token_for_workspace
            tenant_id = get_tenant_for_workspace(team_id)
            has_token = get_bot_token_for_workspace(team_id) is not None

            diagnostics["workspace_lookup"] = {
                "team_id": team_id,
                "tenant_id": tenant_id,
                "has_bot_token": has_token,
                "found": tenant_id is not None
            }

            if not tenant_id:
                diagnostics["errors"].append(f"No connector found for team_id: {team_id}")

        # Check Pinecone stats for specific tenant
        tenant_id = request.args.get("tenant_id")
        if tenant_id:
            try:
                from vector_stores.pinecone_store import get_vector_store
                store = get_vector_store()
                stats = store.get_stats(tenant_id)
                diagnostics["pinecone_stats"] = stats
            except Exception as e:
                diagnostics["errors"].append(f"Pinecone error: {str(e)}")

        # Check event subscriptions
        diagnostics["slack_config"] = {
            "SLACK_CLIENT_ID": "set" if os.getenv("SLACK_CLIENT_ID") else "NOT SET",
            "SLACK_CLIENT_SECRET": "set" if os.getenv("SLACK_CLIENT_SECRET") else "NOT SET",
            "SLACK_SIGNING_SECRET": "set" if os.getenv("SLACK_SIGNING_SECRET") else "NOT SET",
            "SLACK_BOT_TOKEN": "set" if os.getenv("SLACK_BOT_TOKEN") else "NOT SET"
        }

    finally:
        db.close()

    # Determine status
    if diagnostics["errors"]:
        diagnostics["status"] = "issues_found"
    else:
        diagnostics["status"] = "healthy"

    return jsonify(diagnostics), 200


@app.route('/api/diagnostics/slack-bot-test', methods=['GET'])
def slack_bot_test():
    """
    Test the full Slack bot flow step by step.

    Query params:
        team_id: Slack team ID to test
        query: Test query to search (default: "test query")
    """
    import traceback

    team_id = request.args.get("team_id")
    query = request.args.get("query", "What documents do we have?")

    results = {
        "steps": [],
        "success": False,
        "error": None
    }

    def log_step(name, success, details=None, error=None):
        results["steps"].append({
            "step": name,
            "success": success,
            "details": details,
            "error": str(error) if error else None
        })
        return success

    # Step 1: Check if team_id provided
    if not team_id:
        log_step("1. Team ID check", False, error="No team_id provided. Add ?team_id=YOUR_TEAM_ID")
        return jsonify(results), 400

    log_step("1. Team ID check", True, {"team_id": team_id})

    # Step 2: Look up tenant for workspace
    try:
        from services.slack_bot_service import get_tenant_for_workspace, get_bot_token_for_workspace

        tenant_id = get_tenant_for_workspace(team_id)
        if tenant_id:
            log_step("2. Tenant lookup", True, {"tenant_id": tenant_id[:8] + "...", "full_tenant_id": tenant_id})
        else:
            log_step("2. Tenant lookup", False, error=f"No tenant found for team_id: {team_id}")
            return jsonify(results), 200
    except Exception as e:
        log_step("2. Tenant lookup", False, error=str(e))
        results["error"] = traceback.format_exc()
        return jsonify(results), 200

    # Step 3: Get bot token
    try:
        bot_token = get_bot_token_for_workspace(team_id)
        if bot_token:
            log_step("3. Bot token lookup", True, {"has_token": True, "token_preview": bot_token[:20] + "..."})
        else:
            log_step("3. Bot token lookup", False, error="No bot token found")
            return jsonify(results), 200
    except Exception as e:
        log_step("3. Bot token lookup", False, error=str(e))
        results["error"] = traceback.format_exc()
        return jsonify(results), 200

    # Step 4: Initialize Pinecone
    try:
        from vector_stores.pinecone_store import get_vector_store
        vector_store = get_vector_store()
        stats = vector_store.get_stats(tenant_id)
        log_step("4. Pinecone connection", True, {
            "vector_count": stats.get("vector_count", 0),
            "namespace": tenant_id
        })
    except Exception as e:
        log_step("4. Pinecone connection", False, error=str(e))
        results["error"] = traceback.format_exc()
        return jsonify(results), 200

    # Step 5: Initialize search service
    try:
        from services.enhanced_search_service import EnhancedSearchService
        search_service = EnhancedSearchService()
        log_step("5. Search service init", True)
    except Exception as e:
        log_step("5. Search service init", False, error=str(e))
        results["error"] = traceback.format_exc()
        return jsonify(results), 200

    # Step 6: Perform search
    try:
        result = search_service.search_and_answer(
            query=query,
            tenant_id=tenant_id,
            vector_store=vector_store,
            top_k=3
        )
        log_step("6. Search execution", True, {
            "num_sources": result.get("num_sources", 0),
            "answer_length": len(result.get("answer", "")),
            "search_time": result.get("search_time", 0)
        })

        results["answer_preview"] = result.get("answer", "")[:500] + "..." if len(result.get("answer", "")) > 500 else result.get("answer", "")
        results["sources"] = [{"title": s.get("title", ""), "score": s.get("score", 0)} for s in result.get("sources", [])[:3]]
    except Exception as e:
        log_step("6. Search execution", False, error=str(e))
        results["error"] = traceback.format_exc()
        return jsonify(results), 200

    # Step 7: Test Slack client (just init, don't post)
    try:
        from slack_sdk import WebClient
        client = WebClient(token=bot_token)
        auth = client.auth_test()
        log_step("7. Slack client test", True, {
            "bot_user": auth.get("user"),
            "team": auth.get("team")
        })
    except Exception as e:
        log_step("7. Slack client test", False, error=str(e))
        results["error"] = traceback.format_exc()
        return jsonify(results), 200

    results["success"] = True
    return jsonify(results), 200


@app.route('/api/diagnostics/slack-check', methods=['GET'])
def slack_quick_check():
    """
    Quick Slack bot diagnostic - no auth required, no team_id needed.
    Hit this to see all Slack connectors and test their tokens.
    """
    from database.models import Connector, ConnectorType, get_db as _get_db
    from slack_sdk import WebClient

    results = {
        "env_vars": {
            "SLACK_CLIENT_ID": bool(os.getenv("SLACK_CLIENT_ID")),
            "SLACK_CLIENT_SECRET": bool(os.getenv("SLACK_CLIENT_SECRET")),
            "SLACK_SIGNING_SECRET": bool(os.getenv("SLACK_SIGNING_SECRET")),
            "SLACK_BOT_TOKEN": bool(os.getenv("SLACK_BOT_TOKEN")),
        },
        "connectors": [],
        "event_url_expected": "https://api.use2ndbrain.com/api/integrations/slack/callback",
    }

    try:
        db = next(_get_db())
        try:
            connectors = db.query(Connector).filter(
                Connector.connector_type == ConnectorType.SLACK
            ).all()

            for c in connectors:
                settings = c.settings or {}
                info = {
                    "id": str(c.id),
                    "tenant_id": c.tenant_id[:8] + "..." if c.tenant_id else None,
                    "is_active": c.is_active,
                    "team_id": settings.get("team_id"),
                    "team_name": settings.get("team_name"),
                    "bot_user_id": settings.get("bot_user_id"),
                    "has_access_token": bool(c.access_token),
                    "token_preview": c.access_token[:15] + "..." if c.access_token else None,
                    "token_works": False,
                    "token_error": None,
                    "scopes": None,
                }

                # Test the token
                if c.access_token:
                    try:
                        client = WebClient(token=c.access_token)
                        auth = client.auth_test()
                        info["token_works"] = True
                        info["bot_name"] = auth.get("user")
                        info["bot_team"] = auth.get("team")
                        # Check scopes
                        resp_headers = auth.headers if hasattr(auth, 'headers') else {}
                        info["scopes"] = resp_headers.get("x-oauth-scopes", "unknown")
                    except Exception as tok_err:
                        info["token_error"] = str(tok_err)

                results["connectors"].append(info)
        finally:
            db.close()
    except Exception as e:
        results["db_error"] = str(e)

    # Also test fallback env token
    env_token = os.getenv("SLACK_BOT_TOKEN")
    if env_token:
        try:
            client = WebClient(token=env_token)
            auth = client.auth_test()
            results["env_token_works"] = True
            results["env_token_bot"] = auth.get("user")
        except Exception as e:
            results["env_token_works"] = False
            results["env_token_error"] = str(e)

    return jsonify(results), 200


@app.route('/api/diagnostics/slack-simulate', methods=['GET'])
def slack_simulate_event():
    """
    Simulate a full Slack event flow: lookup → search → POST message to Slack.
    This bypasses Slack's event delivery to test the handler directly.

    Query params:
        channel: Slack channel ID to post to (required)
        query: Question to ask (default: "What is knowledge vault?")
        team_id: Slack team ID (default: auto-detect from DB)
    """
    import traceback

    channel = request.args.get("channel")
    query = request.args.get("query", "What is knowledge vault?")
    team_id = request.args.get("team_id")

    steps = []
    def log(name, ok, detail=None, err=None):
        steps.append({"step": name, "ok": ok, "detail": detail, "error": str(err) if err else None})

    if not channel:
        return jsonify({
            "error": "channel param required. Find it in Slack: right-click channel → View channel details → copy the Channel ID at the bottom.",
            "example": "/api/diagnostics/slack-simulate?channel=C0123ABC&query=hello"
        }), 400

    # Step 1: Get team_id
    try:
        from database.models import Connector, ConnectorType, get_db as _get_db
        if not team_id:
            db = next(_get_db())
            try:
                c = db.query(Connector).filter(
                    Connector.connector_type == ConnectorType.SLACK,
                    Connector.is_active == True
                ).first()
                if c:
                    team_id = (c.settings or {}).get("team_id")
            finally:
                db.close()
        log("1. Team ID", bool(team_id), team_id)
    except Exception as e:
        log("1. Team ID", False, err=e)
        return jsonify({"steps": steps}), 200

    if not team_id:
        return jsonify({"steps": steps, "error": "No Slack connector found"}), 200

    # Step 2: Tenant + token lookup
    try:
        from services.slack_bot_service import (
            SlackBotService, get_tenant_for_workspace, get_bot_token_for_workspace
        )
        tenant_id = get_tenant_for_workspace(team_id)
        log("2. Tenant lookup", bool(tenant_id), tenant_id[:8] + "..." if tenant_id else None)
        if not tenant_id:
            return jsonify({"steps": steps}), 200

        bot_token = get_bot_token_for_workspace(team_id)
        log("3. Bot token", bool(bot_token))
        if not bot_token:
            return jsonify({"steps": steps}), 200
    except Exception as e:
        log("2-3. Lookup", False, err=e)
        return jsonify({"steps": steps, "traceback": traceback.format_exc()}), 200

    # Step 3: Create bot service
    try:
        bot_service = SlackBotService(bot_token)
        log("4. Bot service init", True, f"bot_user_id={bot_service.bot_user_id}")
    except Exception as e:
        log("4. Bot service init", False, err=e)
        return jsonify({"steps": steps, "traceback": traceback.format_exc()}), 200

    # Step 4: Simulate app_mention event
    try:
        fake_event = {
            "type": "app_mention",
            "user": "U_DIAGNOSTIC",
            "text": f"<@{bot_service.bot_user_id or 'UBOT'}> {query}",
            "channel": channel,
            "ts": str(time.time()),
        }
        log("5. Simulated event", True, fake_event["text"][:80])

        bot_service.handle_app_mention(tenant_id, fake_event)
        log("6. handle_app_mention", True, "Completed - check Slack channel for message")
    except Exception as e:
        log("6. handle_app_mention", False, err=e)
        return jsonify({"steps": steps, "traceback": traceback.format_exc()}), 200

    return jsonify({"steps": steps, "success": True}), 200


@app.route('/api/diagnostics/slack-channel', methods=['GET'])
def slack_channel_check():
    """
    Check if the bot is a member of a specific channel and verify event delivery prerequisites.
    Query params: channel (required) - Slack channel ID
    """
    channel = request.args.get("channel")
    if not channel:
        return jsonify({"error": "channel param required"}), 400

    results = {"channel": channel, "checks": {}}

    try:
        from services.slack_bot_service import get_bot_token_for_workspace, get_tenant_for_workspace
        from database.models import Connector, ConnectorType, SessionLocal
        from slack_sdk import WebClient

        db = SessionLocal()
        connector = db.query(Connector).filter(
            Connector.connector_type == ConnectorType.SLACK,
            Connector.is_active == True
        ).first()

        if not connector or not connector.access_token:
            db.close()
            return jsonify({"error": "No active Slack connector"}), 404

        token = connector.access_token
        settings = connector.settings or {}
        results["connector_team_id"] = settings.get("team_id")
        results["connector_bot_user_id"] = settings.get("bot_user_id")
        results["connected_via"] = settings.get("connected_via", "oauth")

        client = WebClient(token=token)

        # Check 1: auth.test - verify token and workspace
        auth = client.auth_test()
        results["checks"]["auth_test"] = {
            "ok": auth["ok"],
            "team": auth.get("team"),
            "team_id": auth.get("team_id"),
            "bot_user_id": auth.get("user_id"),
            "app_id": auth.get("app_id", "not_returned"),
        }

        bot_user_id = auth.get("user_id")

        # Check 2: conversations.info - get channel details
        try:
            ch_info = client.conversations_info(channel=channel)
            ch = ch_info["channel"]
            results["checks"]["channel_info"] = {
                "ok": True,
                "name": ch.get("name"),
                "is_member": ch.get("is_member"),
                "is_private": ch.get("is_private"),
                "is_archived": ch.get("is_archived"),
                "num_members": ch.get("num_members"),
            }
        except Exception as e:
            results["checks"]["channel_info"] = {"ok": False, "error": str(e)}

        # Check 3: Check if bot is in conversation members
        try:
            members = client.conversations_members(channel=channel, limit=200)
            member_ids = members.get("members", [])
            results["checks"]["bot_membership"] = {
                "ok": True,
                "bot_in_channel": bot_user_id in member_ids,
                "total_members": len(member_ids),
                "bot_user_id": bot_user_id,
            }
        except Exception as e:
            results["checks"]["bot_membership"] = {"ok": False, "error": str(e)}

        # Check 4: Try joining the channel
        if not results["checks"].get("channel_info", {}).get("is_member"):
            try:
                client.conversations_join(channel=channel)
                results["checks"]["join_attempt"] = {"ok": True, "joined": True}
            except Exception as e:
                results["checks"]["join_attempt"] = {"ok": False, "error": str(e)}

        # Check 5: Read recent messages from channel to see @mention messages
        try:
            history = client.conversations_history(channel=channel, limit=10)
            recent_msgs = []
            for msg in history.get("messages", []):
                recent_msgs.append({
                    "ts": msg.get("ts"),
                    "user": msg.get("user"),
                    "text": (msg.get("text") or "")[:200],
                    "bot_id": msg.get("bot_id"),
                    "subtype": msg.get("subtype"),
                })
            results["checks"]["recent_messages"] = {
                "ok": True,
                "count": len(recent_msgs),
                "messages": recent_msgs,
            }
        except Exception as e:
            results["checks"]["recent_messages"] = {"ok": False, "error": str(e)}

        db.close()

    except Exception as e:
        results["error"] = str(e)

    return jsonify(results), 200


@app.route('/api/diagnostics/slack-post-test', methods=['POST'])
def slack_post_test():
    """
    Post a test message to a Slack channel to verify chat:write permission.
    Body: {"channel": "C0AC4B27NAF", "text": "Test message"}
    """
    data = request.get_json() or {}
    channel = data.get("channel")
    text = data.get("text", "Hello from KnowledgeVault bot! This is a diagnostic test message.")

    if not channel:
        return jsonify({"error": "channel required in body"}), 400

    try:
        from database.models import Connector, ConnectorType, SessionLocal
        from slack_sdk import WebClient

        db = SessionLocal()
        connector = db.query(Connector).filter(
            Connector.connector_type == ConnectorType.SLACK,
            Connector.is_active == True
        ).first()

        if not connector or not connector.access_token:
            db.close()
            return jsonify({"error": "No active Slack connector"}), 404

        client = WebClient(token=connector.access_token)
        result = client.chat_postMessage(channel=channel, text=text)
        db.close()

        return jsonify({
            "ok": result["ok"],
            "channel": result.get("channel"),
            "ts": result.get("ts"),
            "message_text": text,
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/diagnostics/webscraper', methods=['GET'])
def webscraper_diagnostics():
    """
    Diagnostic endpoint for the self-hosted web scraper.
    Returns capabilities (html2text, OCR) and configuration.
    """
    from connectors.webscraper_connector import HTML2TEXT_AVAILABLE, OCR_AVAILABLE

    diagnostics = {
        "html2text_available": HTML2TEXT_AVAILABLE,
        "ocr_available": OCR_AVAILABLE,
        "engine": "requests + BeautifulSoup (self-hosted)",
    }

    if OCR_AVAILABLE:
        try:
            import pytesseract
            diagnostics["tesseract_version"] = str(pytesseract.get_tesseract_version())
        except Exception as e:
            diagnostics["tesseract_version"] = f"error: {e}"

    return jsonify(diagnostics)


# ============================================================================
# SEARCH ENDPOINT (Enhanced RAG with Reranking, MMR, Query Expansion)
# ============================================================================

# Hardcoded Q&A pairs that override RAG search
HARDCODED_QA = [
    {
        "keywords": ["ABP", "Chek2", "Wnt", "BMP", "Serpine", "MAPK"],
        "min_matches": 4,  # Must match at least 4 of these keywords
        "answer": (
            "ABP, Chek2, Wnt, BMP, and MAPK appear to be strong candidates for further "
            "investigation due to their relevance in signaling and regulatory pathways.\n\n"
            "However, Serpine may not be an ideal protein to prioritize for follow-up studies. "
            "Previous research efforts within your lab have already examined Serpine extensively, "
            "and those studies did not lead to productive outcomes. Based on this prior experience, "
            "it would be more effective to focus downstream analysis on the remaining proteins "
            "that offer greater potential for novel insight."
        ),
    },
]


def _check_hardcoded_answer(query: str):
    """Check if query matches a hardcoded Q&A pair."""
    query_upper = query.upper()
    for qa in HARDCODED_QA:
        matches = sum(1 for kw in qa["keywords"] if kw.upper() in query_upper)
        if matches >= qa["min_matches"]:
            return {
                "success": True,
                "answer": qa["answer"],
                "sources": [],
                "query": query,
            }
    return None


@app.route('/api/search/feedback', methods=['POST'])
@require_auth
def search_feedback():
    """Submit feedback on search quality (thumbs up/down or 1-5 rating)."""
    from database.models import SearchFeedback
    data = request.get_json() or {}
    tenant_id = g.tenant_id

    rating = data.get('rating')
    if rating not in (1, 2, 3, 4, 5):
        return jsonify({"error": "rating must be 1-5"}), 400

    query = data.get('query', '')
    if not query:
        return jsonify({"error": "query is required"}), 400

    try:
        feedback = SearchFeedback(
            tenant_id=tenant_id,
            user_id=getattr(g, 'user_id', None),
            query=query,
            answer=data.get('answer', '')[:5000],
            confidence=data.get('confidence'),
            source_count=data.get('source_count'),
            rating=rating,
            feedback_text=data.get('feedback_text', '')[:1000],
            response_mode=data.get('response_mode'),
            search_time_ms=data.get('search_time_ms'),
            features_used=data.get('features_used'),
        )
        db.add(feedback)
        db.commit()
        return jsonify({"success": True, "id": feedback.id})
    except Exception as e:
        log_error("app", "Search feedback error", error=e)
        return jsonify({"error": "Failed to save feedback"}), 500


@app.route('/api/search', methods=['POST'])
@require_auth
def search():
    """
    Enhanced RAG search endpoint with:
    - Query expansion (100+ acronyms)
    - Cross-encoder reranking
    - MMR diversity selection
    - Hallucination detection
    - Strict citation enforcement

    Request body:
    {
        "query": "How do we handle customer complaints?",
        "top_k": 10,
        "include_sources": true,
        "enhanced": true  // Enable enhanced features (default: true)
    }
    """
    from vector_stores.pinecone_store import get_hybrid_store

    tenant_id = g.tenant_id
    print(f"[SEARCH] Tenant: {tenant_id}", flush=True)

    data = request.get_json() or {}
    query = data.get('query', '')
    conversation_history = data.get('conversation_history', [])  # NEW: conversation context
    top_k = data.get('top_k', 10)
    include_sources = data.get('include_sources', True)
    use_enhanced = data.get('enhanced', True)  # Enhanced mode on by default
    boost_doc_ids = data.get('boost_doc_ids', [])  # IDs of newly uploaded docs to boost
    source_types = data.get('source_types', [])  # Folder/source filter from UI

    if not query:
        return jsonify({
            "success": False,
            "error": "Query required"
        }), 400

    # Hardcoded Q&A overrides
    _hardcoded = _check_hardcoded_answer(query)
    if _hardcoded:
        return jsonify(_hardcoded)

    print(f"[SEARCH] Conversation history length: {len(conversation_history)}", flush=True)

    try:
        # Try Pinecone first (production), fallback to local index (development)
        vector_store = None
        use_local_index = False

        # Check if Pinecone is configured
        if os.getenv("PINECONE_API_KEY"):
            try:
                vector_store = get_hybrid_store()
                print(f"[SEARCH] Using Pinecone vector store", flush=True)
            except Exception as e:
                print(f"[SEARCH] Pinecone unavailable ({e}), falling back to local index", flush=True)
                use_local_index = True
        else:
            print(f"[SEARCH] No PINECONE_API_KEY, using local index", flush=True)
            use_local_index = True

        # Use local index if Pinecone is not available
        if use_local_index:
            from services.local_rag_service import get_local_rag_service
            local_rag = get_local_rag_service()

            # Search using local index
            result = local_rag.search(
                query=query,
                tenant_id=tenant_id,
                top_k=top_k
            )

            return jsonify({
                "success": True,
                "query": query,
                "answer": result.get('answer', ''),
                "confidence": result.get('confidence', 0.8),
                "query_type": "local_rag",
                "sources": result.get('sources', []),
                "source_count": len(result.get('sources', [])),
                "storage_mode": "local"
            })

        # Check if knowledge base is empty first
        stats = vector_store.get_stats(tenant_id)
        vector_count = stats.get('vector_count', 0)
        print(f"[SEARCH] Pinecone stats for tenant {tenant_id}: {stats}", flush=True)

        if vector_count == 0:
            # Double-check: sometimes describe_index_stats is slow to update
            # Try a quick search to confirm if there's really no data
            print(f"[SEARCH] WARNING: vector_count=0, attempting verification search...", flush=True)
            try:
                test_results = vector_store.search(query="test", tenant_id=tenant_id, top_k=1)
                if test_results:
                    print(f"[SEARCH] Verification search found {len(test_results)} results - proceeding with search", flush=True)
                    vector_count = 1  # Force to continue with search
            except Exception as e:
                print(f"[SEARCH] Verification search failed: {e}", flush=True)

        if vector_count == 0:
            return jsonify({
                "success": True,
                "query": query,
                "answer": "Welcome! Your knowledge base is empty. To get started:\n\n1. Go to **Integrations** and connect your Gmail, Slack, or Box\n2. Sync your data to import documents\n3. Review documents in the **Documents** page\n4. Once you have confirmed documents, come back here to search!\n\nI'll be ready to answer your questions once you've added some content.",
                "confidence": 1.0,
                "query_type": "onboarding",
                "sources": [],
                "source_count": 0,
                "is_empty_knowledge_base": True
            })

        # Read tenant chat response mode setting (defaults to 3 = In-Depth)
        response_mode = 3
        try:
            from database.models import Tenant
            _settings_db = SessionLocal()
            try:
                tenant = _settings_db.query(Tenant).filter(Tenant.id == tenant_id).first()
                if tenant and tenant.settings:
                    response_mode = tenant.settings.get('chat_response_mode', 4)
            finally:
                _settings_db.close()
        except Exception:
            pass  # Default to 4 if anything fails

        # Use Enhanced Search Service
        if use_enhanced:
            from services.enhanced_search_service import get_enhanced_search_service

            print(f"[SEARCH] Using ENHANCED search for tenant {tenant_id} (mode={response_mode}): '{query}'", flush=True)

            # Build user context for RAG personalization (same as streaming endpoint)
            user_context = {}
            try:
                user_obj = db.query(User).filter(User.id == g.user_id).first()
                if user_obj:
                    user_context['user_name'] = user_obj.full_name
                _tenant_obj = db.query(Tenant).filter(Tenant.id == tenant_id).first()
                if _tenant_obj:
                    user_context['organization'] = _tenant_obj.name

                from sqlalchemy import func as sqlfunc
                doc_counts = db.query(
                    Document.source_type,
                    sqlfunc.count(Document.id)
                ).filter(
                    Document.tenant_id == tenant_id
                ).group_by(Document.source_type).all()

                if doc_counts:
                    summary_parts = []
                    type_labels = {
                        'email': 'emails', 'message': 'Slack messages',
                        'file': 'uploaded files', 'document': 'documents',
                        'grant': 'grant documents',
                    }
                    for source_type, count in doc_counts:
                        label = type_labels.get(source_type, f'{source_type} items')
                        summary_parts.append(f"{count} {label}")
                    user_context['data_summary'] = ", ".join(summary_parts)

                recent_docs = db.query(Document.title).filter(
                    Document.tenant_id == tenant_id
                ).order_by(Document.created_at.desc()).limit(25).all()
                user_context['recent_doc_titles'] = [d.title for d in recent_docs if d.title]

                total_docs = db.query(sqlfunc.count(Document.id)).filter(
                    Document.tenant_id == tenant_id
                ).scalar() or 0
                user_context['total_documents'] = total_docs
            except Exception as uctx_err:
                print(f"[SEARCH] Error building user context: {uctx_err}", flush=True)

            enhanced_service = get_enhanced_search_service()
            result = enhanced_service.search_and_answer(
                query=query,
                tenant_id=tenant_id,
                vector_store=vector_store,
                top_k=top_k,
                validate=True,
                conversation_history=conversation_history,
                boost_doc_ids=boost_doc_ids,
                response_mode=response_mode,
                user_context=user_context,
                source_types=source_types
            )

            # Format sources for response — enrich with source_url from DB
            sources = []
            if include_sources:
                # Batch lookup source_url for all doc_ids
                raw_sources = result.get('sources', [])
                doc_ids = [s.get('doc_id', '') for s in raw_sources if s.get('doc_id')]
                source_url_map = {}
                if doc_ids:
                    try:
                        docs_with_urls = db.query(Document.id, Document.source_url).filter(
                            Document.id.in_(doc_ids)
                        ).all()
                        source_url_map = {str(d.id): d.source_url for d in docs_with_urls if d.source_url}
                    except Exception:
                        pass  # Graceful fallback — no URLs is fine

                # Look up source_type for origin labeling
                doc_source_type_map = {}
                if doc_ids:
                    try:
                        docs_with_types = db.query(Document.id, Document.source_type).filter(
                            Document.id.in_(doc_ids)
                        ).all()
                        doc_source_type_map = {str(d.id): d.source_type for d in docs_with_types}
                    except Exception:
                        pass

                for src in raw_sources:
                    doc_id = src.get('doc_id', '')
                    is_shared = src.get('is_shared', False)
                    source_entry = {
                        "doc_id": doc_id,
                        "title": src.get('title', 'Untitled'),
                        "content_preview": (src.get('content', '') or src.get('content_preview', ''))[:300],
                        "score": src.get('rerank_score', src.get('score', 0)),
                        "metadata": src.get('metadata', {}),
                    }
                    if is_shared:
                        source_entry["source_url"] = src.get('source_url', '')
                        source_entry["is_shared"] = True
                        source_entry["facility_name"] = src.get('facility_name', '')
                        source_entry["source_origin"] = "ctsi"
                        source_entry["source_origin_label"] = "CTSI Research"
                    else:
                        source_entry["source_url"] = source_url_map.get(doc_id, '')
                        doc_st = doc_source_type_map.get(doc_id, '')
                        if doc_st == 'pubmed':
                            source_entry["source_origin"] = "pubmed"
                            source_entry["source_origin_label"] = "PubMed"
                        elif doc_st == 'journal':
                            source_entry["source_origin"] = "journal"
                            source_entry["source_origin_label"] = "Journal DB"
                        elif doc_st == 'experiment':
                            source_entry["source_origin"] = "reproducibility"
                            source_entry["source_origin_label"] = "Repro Archive"
                        else:
                            source_entry["source_origin"] = "user_kb"
                            source_entry["source_origin_label"] = "Your KB"
                    sources.append(source_entry)

            # Check if any sources are from grant data
            answer_text = result.get('answer', '')
            has_grant_sources = False
            if raw_sources:
                # Check 1: metadata from Pinecone
                has_grant_sources = any(
                    s.get('metadata', {}).get('source_type') == 'grant'
                    for s in raw_sources
                )
                # Check 2: query DB for source_type of returned docs (most reliable)
                if not has_grant_sources and doc_ids:
                    try:
                        grant_count = db.query(Document.id).filter(
                            Document.id.in_(doc_ids),
                            Document.source_type == 'grant'
                        ).limit(1).count()
                        has_grant_sources = grant_count > 0
                    except Exception:
                        pass
            if has_grant_sources:
                # Get the actual last scrape timestamp
                try:
                    last_grant = db.query(Document.created_at).filter(
                        Document.tenant_id == tenant_id,
                        Document.source_type == 'grant'
                    ).order_by(Document.created_at.desc()).first()
                    if last_grant and last_grant[0]:
                        last_scrape = last_grant[0].strftime('%B %d, %Y at %I:%M %p UTC')
                        answer_text += f"\n\n---\n📋 Grant data sourced from NIH RePORTER, Grants.gov, and NSF. Last updated: {last_scrape}."
                    else:
                        answer_text += "\n\n---\n📋 Grant data is updated daily from NIH RePORTER, Grants.gov, and NSF."
                except Exception:
                    answer_text += "\n\n---\n📋 Grant data is updated daily from NIH RePORTER, Grants.gov, and NSF."

            # Build response
            response_data = {
                "success": True,
                "query": query,
                "expanded_query": result.get('expanded_query'),
                "answer": answer_text,
                "confidence": result.get('confidence', 0),
                "query_type": "enhanced_rag",
                "sources": sources,
                "source_count": len(sources),
                "search_time": result.get('search_time', 0),
                "features_used": result.get('features_used', {}),
                "context_chars": result.get('context_chars', 0)
            }

            # Add validation results if available
            if result.get('hallucination_check'):
                response_data['hallucination_check'] = {
                    'verified': result['hallucination_check'].get('verified', 0),
                    'total_claims': result['hallucination_check'].get('total_claims', 0),
                    'confidence': result['hallucination_check'].get('confidence', 1.0)
                }

            if result.get('citation_check'):
                response_data['citation_coverage'] = result['citation_check'].get('cited_ratio', 1.0)

            print(f"[SEARCH] Enhanced search complete: {len(sources)} sources, "
                  f"confidence={result.get('confidence', 0):.2f}, "
                  f"features={result.get('features_used', {})}", flush=True)

            return jsonify(response_data)

        else:
            # Fallback to basic search (for debugging/comparison)
            print(f"[SEARCH] Using BASIC search for tenant {tenant_id}: '{query}'", flush=True)

            results = vector_store.hybrid_search(
                query=query,
                tenant_id=tenant_id,
                top_k=top_k
            )

            if not results:
                return jsonify({
                    "success": True,
                    "query": query,
                    "answer": "I couldn't find any relevant information for your query. Try rephrasing or asking about a different topic.",
                    "confidence": 0.3,
                    "query_type": "no_results",
                    "sources": [],
                    "source_count": 0
                })

            # Basic answer generation (legacy)
            from openai import AzureOpenAI
            openai_client = AzureOpenAI(
                azure_endpoint=AZURE_OPENAI_ENDPOINT,
                api_key=AZURE_OPENAI_API_KEY,
                api_version="2024-12-01-preview"
            )

            context_parts = []
            for i, result in enumerate(results[:8]):  # Increased from 5 to 8
                title = result.get('title', 'Untitled')
                content = result.get('content', '')[:2000]  # Increased from 500
                context_parts.append(f"[Source {i+1}] {title}:\n{content}")

            context = "\n\n---\n\n".join(context_parts)

            response = openai_client.chat.completions.create(
                model=AZURE_CHAT_DEPLOYMENT,
                messages=[
                    {"role": "system", "content": "You are a helpful knowledge assistant. Answer based on the provided sources. Cite sources like [Source 1]."},
                    {"role": "user", "content": f"Sources:\n{context}\n\nQuestion: {query}\n\nAnswer with citations:"}
                ],
                max_tokens=1500,
                temperature=0.2
            )

            answer = response.choices[0].message.content

            sources = []
            if include_sources:
                for result in results:
                    sources.append({
                        "doc_id": result.get('doc_id', ''),
                        "title": result.get('title', 'Untitled'),
                        "content_preview": result.get('content', '')[:300],
                        "score": result.get('score', 0),
                        "metadata": result.get('metadata', {})
                    })

            # Check if any sources are from grant data
            has_grant = any(r.get('metadata', {}).get('source_type') == 'grant' for r in results)
            if not has_grant:
                basic_doc_ids = [r.get('doc_id', '') for r in results if r.get('doc_id')]
                if basic_doc_ids:
                    try:
                        has_grant = db.query(Document.id).filter(
                            Document.id.in_(basic_doc_ids),
                            Document.source_type == 'grant'
                        ).limit(1).count() > 0
                    except Exception:
                        pass
            if has_grant:
                try:
                    last_grant = db.query(Document.created_at).filter(
                        Document.tenant_id == tenant_id,
                        Document.source_type == 'grant'
                    ).order_by(Document.created_at.desc()).first()
                    if last_grant and last_grant[0]:
                        last_scrape = last_grant[0].strftime('%B %d, %Y at %I:%M %p UTC')
                        answer += f"\n\n---\n📋 Grant data sourced from NIH RePORTER, Grants.gov, and NSF. Last updated: {last_scrape}."
                    else:
                        answer += "\n\n---\n📋 Grant data is updated daily from NIH RePORTER, Grants.gov, and NSF."
                except Exception:
                    answer += "\n\n---\n📋 Grant data is updated daily from NIH RePORTER, Grants.gov, and NSF."

            return jsonify({
                "success": True,
                "query": query,
                "answer": answer,
                "confidence": results[0].get('score', 0.5) if results else 0,
                "query_type": "basic_rag",
                "sources": sources,
                "source_count": len(sources)
            })

    except Exception as e:
        import traceback
        print(f"[SEARCH] Error: {e}", flush=True)
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# STREAMING SEARCH ENDPOINT (Server-Sent Events)
# ============================================================================

@app.route('/api/search/stream', methods=['POST'])
@require_auth
def search_stream():
    """
    Streaming RAG search endpoint using Server-Sent Events.
    Words appear in real-time as they're generated.

    Response streams as SSE events:
    - event: search_complete - Search done, answer generation starting
    - event: chunk - A piece of the answer text
    - event: done - Streaming complete with final metadata
    - event: error - Error occurred
    """
    from vector_stores.pinecone_store import get_hybrid_store
    from database.models import SessionLocal, Document, Tenant, User

    tenant_id = g.tenant_id
    print(f"[SEARCH-STREAM] Tenant: {tenant_id}", flush=True)

    data = request.get_json() or {}
    query = data.get('query', '')
    conversation_history = data.get('conversation_history', [])
    top_k = data.get('top_k', 10)
    boost_doc_ids = data.get('boost_doc_ids', [])
    source_types = data.get('source_types', [])  # Folder/source filter from UI

    if not query:
        def error_gen():
            yield f"event: error\ndata: {json.dumps({'error': 'Query required'})}\n\n"
        return Response(error_gen(), mimetype='text/event-stream')

    # Hardcoded Q&A overrides (stream format)
    _hardcoded = _check_hardcoded_answer(query)
    if _hardcoded:
        def hardcoded_gen():
            answer = _hardcoded['answer']
            yield f"event: search_complete\ndata: {json.dumps({'sources': []})}\n\n"
            # Stream word by word for natural feel
            words = answer.split(' ')
            for i, word in enumerate(words):
                chunk = word if i == 0 else ' ' + word
                yield f"event: chunk\ndata: {json.dumps({'content': chunk})}\n\n"
            yield f"event: done\ndata: {json.dumps({'answer': answer, 'sources': []})}\n\n"
        return Response(hardcoded_gen(), mimetype='text/event-stream',
                       headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

    def generate():
        db = SessionLocal()
        try:
            # Read tenant chat response mode setting (defaults to 3 = In-Depth)
            response_mode = 3
            try:
                tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
                if tenant and tenant.settings:
                    response_mode = tenant.settings.get('chat_response_mode', 4)
            except Exception:
                pass

            if not os.getenv("PINECONE_API_KEY"):
                yield f"event: error\ndata: {json.dumps({'error': 'Pinecone not configured'})}\n\n"
                return

            vector_store = get_hybrid_store()

            stats = vector_store.get_stats(tenant_id)
            if stats.get('vector_count', 0) == 0:
                # Check if shared CTSI namespace has data before rejecting
                from vector_stores.pinecone_store import SHARED_CTSI_NAMESPACE
                shared_stats = vector_store.get_stats()
                shared_count = shared_stats.get('namespaces', {}).get(SHARED_CTSI_NAMESPACE, 0)
                if not shared_count:
                    yield f"event: chunk\ndata: {json.dumps({'content': 'Your knowledge base is empty. Please add some documents first.'})}\n\n"
                    yield f"event: done\ndata: {json.dumps({'confidence': 1.0, 'sources': []})}\n\n"
                    return

            from services.enhanced_search_service import get_enhanced_search_service
            enhanced_service = get_enhanced_search_service()

            # Build user context for RAG personalization
            user_context = {}
            try:
                user_obj = db.query(User).filter(User.id == g.user_id).first()
                if user_obj:
                    user_context['user_name'] = user_obj.full_name
                if tenant:
                    user_context['organization'] = tenant.name

                # Build data inventory summary
                from sqlalchemy import func as sqlfunc
                doc_counts = db.query(
                    Document.source_type,
                    sqlfunc.count(Document.id)
                ).filter(
                    Document.tenant_id == tenant_id
                ).group_by(Document.source_type).all()

                if doc_counts:
                    summary_parts = []
                    type_labels = {
                        'email': 'emails', 'message': 'Slack messages',
                        'file': 'uploaded files', 'document': 'documents',
                        'grant': 'grant documents',
                    }
                    for source_type, count in doc_counts:
                        label = type_labels.get(source_type, f'{source_type} items')
                        summary_parts.append(f"{count} {label}")
                    user_context['data_summary'] = ", ".join(summary_parts)

                # Recent doc titles for reference resolution — get more for inventory queries
                recent_docs = db.query(Document.title, Document.source_type, Document.created_at).filter(
                    Document.tenant_id == tenant_id
                ).order_by(Document.created_at.desc()).limit(25).all()
                user_context['recent_doc_titles'] = [d.title for d in recent_docs if d.title]

                # Total document count
                total_docs = db.query(sqlfunc.count(Document.id)).filter(
                    Document.tenant_id == tenant_id
                ).scalar() or 0
                user_context['total_documents'] = total_docs
            except Exception as uctx_err:
                print(f"[SEARCH-STREAM] Error building user context: {uctx_err}", flush=True)

            # Auto-detect document references in query or conversation history
            # If user mentions a filename, boost that document
            if not boost_doc_ids:
                try:
                    import re as _re
                    # Check query and recent conversation for filenames
                    texts_to_check = [query]
                    if conversation_history:
                        for msg in conversation_history[-6:]:
                            texts_to_check.append(str(msg.get('content', '')))
                    combined_text = ' '.join(texts_to_check).lower()

                    # Find documents whose titles appear in the conversation
                    if recent_docs:
                        for doc in recent_docs:
                            if doc.title:
                                # Match filename without extension, case-insensitive
                                title_lower = doc.title.lower()
                                name_no_ext = _re.sub(r'\.[a-z0-9]{1,5}$', '', title_lower)
                                if name_no_ext and len(name_no_ext) > 3 and name_no_ext in combined_text:
                                    # Found a referenced document — get its ID
                                    ref_doc = db.query(Document.id).filter(
                                        Document.tenant_id == tenant_id,
                                        Document.title == doc.title
                                    ).first()
                                    if ref_doc:
                                        boost_doc_ids.append(str(ref_doc.id))
                                        print(f"[SEARCH-STREAM] Auto-boosting document: '{doc.title}' (ID: {ref_doc.id})", flush=True)
                    if boost_doc_ids:
                        print(f"[SEARCH-STREAM] Boosting {len(boost_doc_ids)} referenced documents", flush=True)
                except Exception as boost_err:
                    print(f"[SEARCH-STREAM] Error in doc reference detection: {boost_err}", flush=True)

            print(f"[SEARCH-STREAM] Starting (mode={response_mode}): '{query}'", flush=True)

            # Emit dynamic plan steps based on query intent (LLM-based classifier)
            from openai import AzureOpenAI as _AzureOpenAI
            _azure_client = _AzureOpenAI(
                azure_endpoint=AZURE_OPENAI_ENDPOINT,
                api_key=AZURE_OPENAI_API_KEY,
                api_version=AZURE_API_VERSION,
            )
            _intent_classifier = get_intent_classifier(llm_client=_azure_client)
            _intent_result = _intent_classifier.classify(query, conversation_history=conversation_history)
            _intent_name = _intent_result["intent"]
            _special = _intent_result.get("special_mode", "")
            _source_weights = _intent_result.get("source_weights", {})

            if _special == 'journal_analysis':
                yield f"event: action\ndata: {json.dumps({'section': 'Research', 'text': 'Identify referenced manuscript', 'status': 'in_progress'})}\n\n"
                yield f"event: action\ndata: {json.dumps({'section': 'Research', 'text': 'Search knowledge base for paper content', 'status': 'pending'})}\n\n"
                yield f"event: action\ndata: {json.dumps({'section': 'Journal Analysis', 'text': 'Detect academic field and keywords', 'status': 'pending'})}\n\n"
                yield f"event: action\ndata: {json.dumps({'section': 'Journal Analysis', 'text': 'Analyze citation neighborhood', 'status': 'pending'})}\n\n"
                yield f"event: action\ndata: {json.dumps({'section': 'Journal Analysis', 'text': 'Match journals by top-cited authors', 'status': 'pending'})}\n\n"
                yield f"event: action\ndata: {json.dumps({'section': 'Journal Analysis', 'text': 'Check methodology gaps', 'status': 'pending'})}\n\n"
                yield f"event: action\ndata: {json.dumps({'section': 'Synthesis', 'text': 'Generate journal recommendations', 'status': 'pending'})}\n\n"
                yield f"event: thinking\ndata: {json.dumps({'type': 'expanding_query', 'text': 'Preparing journal analysis...'})}\n\n"
            elif _special == 'methodology_analysis':
                yield f"event: action\ndata: {json.dumps({'section': 'Research', 'text': 'Identify referenced manuscript', 'status': 'in_progress'})}\n\n"
                yield f"event: action\ndata: {json.dumps({'section': 'Research', 'text': 'Retrieve paper content from knowledge base', 'status': 'pending'})}\n\n"
                yield f"event: action\ndata: {json.dumps({'section': 'Methodology Review', 'text': 'Detect methodology gaps and weaknesses', 'status': 'pending'})}\n\n"
                yield f"event: action\ndata: {json.dumps({'section': 'Methodology Review', 'text': 'Assess experimental design', 'status': 'pending'})}\n\n"
                yield f"event: action\ndata: {json.dumps({'section': 'Synthesis', 'text': 'Generate improvement recommendations', 'status': 'pending'})}\n\n"
                yield f"event: thinking\ndata: {json.dumps({'type': 'expanding_query', 'text': 'Preparing methodology review...'})}\n\n"
            elif _intent_name == 'experiment_suggestion':
                yield f"event: action\ndata: {json.dumps({'section': 'Research', 'text': 'Analyzing research question', 'status': 'in_progress'})}\n\n"
                yield f"event: action\ndata: {json.dumps({'section': 'Research', 'text': 'Querying protocol knowledge graph', 'status': 'pending'})}\n\n"
                yield f"event: action\ndata: {json.dumps({'section': 'Experiment Design', 'text': 'Generating experiment suggestions', 'status': 'pending'})}\n\n"
                yield f"event: action\ndata: {json.dumps({'section': 'Experiment Design', 'text': 'Validating feasibility', 'status': 'pending'})}\n\n"
                yield f"event: action\ndata: {json.dumps({'section': 'Synthesis', 'text': 'Preparing results', 'status': 'pending'})}\n\n"
                yield f"event: thinking\ndata: {json.dumps({'type': 'expanding_query', 'text': 'Designing experiment suggestions...'})}\n\n"
            elif _intent_name == 'protocol_feasibility':
                yield f"event: action\ndata: {json.dumps({'section': 'Research', 'text': 'Extracting technique details', 'status': 'in_progress'})}\n\n"
                yield f"event: action\ndata: {json.dumps({'section': 'Research', 'text': 'Checking protocol compatibility', 'status': 'pending'})}\n\n"
                yield f"event: action\ndata: {json.dumps({'section': 'Feasibility', 'text': 'Querying evidence database', 'status': 'pending'})}\n\n"
                yield f"event: action\ndata: {json.dumps({'section': 'Feasibility', 'text': 'Assessing feasibility', 'status': 'pending'})}\n\n"
                yield f"event: thinking\ndata: {json.dumps({'type': 'expanding_query', 'text': 'Checking protocol feasibility...'})}\n\n"
            elif _intent_name == 'knowledge_gap':
                yield f"event: action\ndata: {json.dumps({'section': 'Research', 'text': 'Scanning knowledge base documents', 'status': 'in_progress'})}\n\n"
                yield f"event: action\ndata: {json.dumps({'section': 'Analysis', 'text': 'Running intelligent gap detection', 'status': 'pending'})}\n\n"
                yield f"event: action\ndata: {json.dumps({'section': 'Synthesis', 'text': 'Formatting gap analysis results', 'status': 'pending'})}\n\n"
                yield f"event: thinking\ndata: {json.dumps({'type': 'expanding_query', 'text': 'Analyzing knowledge gaps...'})}\n\n"
            elif _intent_name == 'literature_search':
                yield f"event: action\ndata: {json.dumps({'section': 'Research', 'text': 'Expanding search terms', 'status': 'in_progress'})}\n\n"
                yield f"event: action\ndata: {json.dumps({'section': 'Literature', 'text': 'Searching OpenAlex & PubMed', 'status': 'pending'})}\n\n"
                yield f"event: action\ndata: {json.dumps({'section': 'Analysis', 'text': 'Ranking results by relevance and citations', 'status': 'pending'})}\n\n"
                yield f"event: action\ndata: {json.dumps({'section': 'Synthesis', 'text': 'Formatting literature review', 'status': 'pending'})}\n\n"
                yield f"event: thinking\ndata: {json.dumps({'type': 'expanding_query', 'text': 'Searching literature databases...'})}\n\n"
            elif any(p in query.lower() for p in ['compare', 'versus', 'vs', 'difference']):
                yield f"event: action\ndata: {json.dumps({'section': 'Research', 'text': 'Decompose comparison query', 'status': 'in_progress'})}\n\n"
                yield f"event: action\ndata: {json.dumps({'section': 'Research', 'text': 'Search each sub-topic separately', 'status': 'pending'})}\n\n"
                yield f"event: action\ndata: {json.dumps({'section': 'Analysis', 'text': 'Cross-reference and align findings', 'status': 'pending'})}\n\n"
                yield f"event: action\ndata: {json.dumps({'section': 'Synthesis', 'text': 'Generate comparative analysis', 'status': 'pending'})}\n\n"
                yield f"event: thinking\ndata: {json.dumps({'type': 'expanding_query', 'text': 'Breaking down comparison...'})}\n\n"
            elif _source_weights.get('user_kb', 0) >= 0.9:
                yield f"event: action\ndata: {json.dumps({'section': 'Research', 'text': 'Search your uploaded documents', 'status': 'in_progress'})}\n\n"
                yield f"event: action\ndata: {json.dumps({'section': 'Analysis', 'text': 'Rank results by relevance', 'status': 'pending'})}\n\n"
                yield f"event: action\ndata: {json.dumps({'section': 'Synthesis', 'text': 'Summarize findings from your files', 'status': 'pending'})}\n\n"
                yield f"event: thinking\ndata: {json.dumps({'type': 'expanding_query', 'text': 'Searching your documents...'})}\n\n"
            elif _source_weights.get('pubmed', 0) >= 0.3:
                yield f"event: action\ndata: {json.dumps({'section': 'Research', 'text': 'Expand query with medical terminology', 'status': 'in_progress'})}\n\n"
                yield f"event: action\ndata: {json.dumps({'section': 'Research', 'text': 'Search knowledge base and PubMed', 'status': 'pending'})}\n\n"
                yield f"event: action\ndata: {json.dumps({'section': 'Analysis', 'text': 'Cross-reference literature with your data', 'status': 'pending'})}\n\n"
                yield f"event: action\ndata: {json.dumps({'section': 'Synthesis', 'text': 'Synthesize evidence-based answer', 'status': 'pending'})}\n\n"
                yield f"event: thinking\ndata: {json.dumps({'type': 'expanding_query', 'text': 'Searching literature...'})}\n\n"
            else:
                yield f"event: action\ndata: {json.dumps({'section': 'Research', 'text': 'Analyze query and expand terms', 'status': 'in_progress'})}\n\n"
                yield f"event: action\ndata: {json.dumps({'section': 'Research', 'text': 'Search knowledge base for relevant sources', 'status': 'pending'})}\n\n"
                yield f"event: action\ndata: {json.dumps({'section': 'Analysis', 'text': 'Rerank and filter results by relevance', 'status': 'pending'})}\n\n"
                yield f"event: action\ndata: {json.dumps({'section': 'Synthesis', 'text': 'Generate answer with source attribution', 'status': 'pending'})}\n\n"
                yield f"event: thinking\ndata: {json.dumps({'type': 'expanding_query', 'text': 'Expanding query...'})}\n\n"

            # ================================================================
            # INTENT ROUTING — Execute specialized services per intent
            # ================================================================
            # Helper: search user's KB for paper content (reused by multiple intents)
            def _search_user_kb(q, vstore, tid, boost_ids=None, k=10):
                """Search user's knowledge base and return (paper_context, references, raw_results)."""
                paper_context = ""
                paper_references = []
                raw_results = []
                try:
                    raw_results = vstore.hybrid_search(
                        query=q, tenant_id=tid, top_k=k,
                        boost_doc_ids=boost_ids or [],
                    ) or []
                    if raw_results:
                        paper_chunks = []
                        seen_docs = set()
                        for r in raw_results:
                            chunk_text = r.get("content", "") or r.get("text", "")
                            doc_title_r = r.get("title", "")
                            doc_id_r = r.get("doc_id", "")
                            if chunk_text:
                                paper_chunks.append(f"[{doc_title_r}]: {chunk_text[:1500]}")
                            if doc_id_r and doc_id_r not in seen_docs:
                                seen_docs.add(doc_id_r)
                                paper_references.append({"title": doc_title_r, "doc_id": doc_id_r})
                        paper_context = "\n\n".join(paper_chunks[:8])
                except Exception as kb_err:
                    print(f"[SEARCH-STREAM] KB search failed: {kb_err}", flush=True)
                return paper_context, paper_references, raw_results

            # Helper: search protocol corpus
            def _search_protocol_corpus(q, vstore):
                """Search protocol corpus namespace in Pinecone."""
                protocol_context = ""
                try:
                    if vstore:
                        q_embedding = vstore._get_embedding(q)
                        corpus_results = vstore.index.query(
                            vector=q_embedding, top_k=5,
                            namespace="protocol-corpus", include_metadata=True,
                        )
                        if corpus_results and corpus_results.matches:
                            protocol_chunks = []
                            for m in corpus_results.matches:
                                meta = m.metadata or {}
                                protocol_chunks.append(
                                    f"[Protocol: {meta.get('title', 'Unknown')}] {meta.get('text', '')}"
                                )
                            protocol_context = "\n\n".join(protocol_chunks)
                except Exception as corpus_err:
                    print(f"[SEARCH-STREAM] Protocol corpus search failed: {corpus_err}", flush=True)
                return protocol_context

            # Helper: build sources_for_response from raw search results
            def _build_sources(raw_sources, database):
                """Build enriched source entries from raw search results."""
                enriched = []
                doc_ids = [s.get('doc_id', '') for s in raw_sources if s.get('doc_id')]
                source_url_map = {}
                doc_source_type_map = {}
                if doc_ids:
                    try:
                        docs_with_urls = database.query(Document.id, Document.source_url).filter(
                            Document.id.in_(doc_ids)
                        ).all()
                        source_url_map = {str(d.id): d.source_url for d in docs_with_urls if d.source_url}
                    except Exception:
                        pass
                    try:
                        docs_with_types = database.query(Document.id, Document.source_type).filter(
                            Document.id.in_(doc_ids)
                        ).all()
                        doc_source_type_map = {str(d.id): d.source_type for d in docs_with_types}
                    except Exception:
                        pass

                for src in raw_sources:
                    doc_id = src.get('doc_id', '')
                    is_shared = src.get('is_shared', False)
                    source_entry = {
                        "doc_id": doc_id,
                        "title": src.get('title', 'Untitled'),
                        "content_preview": (src.get('content', '') or '')[:300],
                        "score": src.get('rerank_score', src.get('score', 0)),
                    }
                    if src.get('source_origin') == 'openalex':
                        source_entry["source_origin"] = "openalex"
                        source_entry["source_origin_label"] = src.get('source_origin_label', 'OpenAlex')
                        source_entry["source_url"] = src.get('source_url', '')
                    elif is_shared:
                        source_entry["source_url"] = src.get('source_url', '')
                        source_entry["is_shared"] = True
                        source_entry["facility_name"] = src.get('facility_name', '')
                        source_entry["source_origin"] = "ctsi"
                        source_entry["source_origin_label"] = "CTSI Research"
                    else:
                        source_entry["source_url"] = source_url_map.get(doc_id, '')
                        doc_st = doc_source_type_map.get(doc_id, '')
                        if doc_st == 'pubmed':
                            source_entry["source_origin"] = "pubmed"
                            source_entry["source_origin_label"] = "PubMed"
                        elif doc_st == 'journal':
                            source_entry["source_origin"] = "journal"
                            source_entry["source_origin_label"] = "Journal DB"
                        elif doc_st == 'experiment':
                            source_entry["source_origin"] = "reproducibility"
                            source_entry["source_origin_label"] = "Repro Archive"
                        else:
                            source_entry["source_origin"] = "user_kb"
                            source_entry["source_origin_label"] = "Your KB"
                    enriched.append(source_entry)
                return enriched

            # Helper: stream a markdown string word-by-word as chunk events
            def _stream_markdown(text):
                """Yield chunk events for a markdown string, word by word."""
                words = text.split(' ')
                chunks = []
                for i, word in enumerate(words):
                    chunk = word if i == 0 else ' ' + word
                    chunks.append(f"event: chunk\ndata: {json.dumps({'content': chunk})}\n\n")
                return chunks

            _intent_handled = False  # Flag: if True, skip standard RAG flow

            # ────────────────────────────────────────────────────────────
            # 1. EXPERIMENT SUGGESTION
            # ────────────────────────────────────────────────────────────
            if _intent_name == "experiment_suggestion":
                try:
                    from services.experiment_suggestion_service import ExperimentSuggestionService
                    from services.feasibility_checker import FeasibilityChecker
                    from services.protocol_graph_service import ProtocolGraphService

                    # Step 1: Search user's KB
                    yield f"event: action\ndata: {json.dumps({'section': 'Research', 'text': 'Analyzing research question', 'status': 'complete'})}\n\n"
                    yield f"event: action\ndata: {json.dumps({'section': 'Research', 'text': 'Querying protocol knowledge graph', 'status': 'in_progress'})}\n\n"

                    paper_context, paper_references, raw_kb_results = _search_user_kb(query, vector_store, tenant_id, boost_doc_ids)

                    # Step 2: Search protocol corpus
                    protocol_context = _search_protocol_corpus(query, vector_store)
                    yield f"event: action\ndata: {json.dumps({'section': 'Research', 'text': 'Querying protocol knowledge graph', 'status': 'complete'})}\n\n"

                    # Step 3: Get resources from protocol graph
                    yield f"event: action\ndata: {json.dumps({'section': 'Experiment Design', 'text': 'Generating experiment suggestions', 'status': 'in_progress'})}\n\n"
                    available_resources = []
                    try:
                        graph_service = ProtocolGraphService(_azure_client, AZURE_CHAT_DEPLOYMENT)
                        graph_data = graph_service.query_graph(tenant_id, db)
                        available_resources = [
                            {"name": e.get("name", ""), "type": e.get("entity_type", ""), "attributes": e.get("attributes", {})}
                            for e in graph_data.get("entities", [])
                        ]
                    except Exception as graph_err:
                        print(f"[SEARCH-STREAM] Protocol graph query failed: {graph_err}", flush=True)

                    # Step 4: Generate suggestions with feasibility
                    suggestion_service = ExperimentSuggestionService(_azure_client, AZURE_CHAT_DEPLOYMENT)
                    suggestions = suggestion_service.suggest_experiments_with_feasibility(
                        research_question=query,
                        available_resources=available_resources,
                        existing_results=paper_references[:10],
                        paper_context=paper_context,
                        protocol_context=protocol_context,
                    )
                    yield f"event: action\ndata: {json.dumps({'section': 'Experiment Design', 'text': 'Generating experiment suggestions', 'status': 'complete'})}\n\n"

                    # Step 5: Deep feasibility check
                    yield f"event: action\ndata: {json.dumps({'section': 'Experiment Design', 'text': 'Validating feasibility', 'status': 'in_progress'})}\n\n"
                    checker = FeasibilityChecker(llm_client=_azure_client, vector_store=vector_store)
                    for suggestion in suggestions:
                        if suggestion.get("feasibility", {}).get("overall", 0) < 0.9:
                            try:
                                deep_check = checker.check(suggestion, tenant_id=tenant_id)
                                suggestion["deep_feasibility"] = deep_check
                            except Exception:
                                pass
                    yield f"event: action\ndata: {json.dumps({'section': 'Experiment Design', 'text': 'Validating feasibility', 'status': 'complete'})}\n\n"

                    if suggestions:
                        # Build sources from KB results
                        sources_for_response = _build_sources(raw_kb_results[:10], db)
                        yield f"event: search_complete\ndata: {json.dumps({'expanded_query': query, 'num_sources': len(sources_for_response), 'sources': sources_for_response})}\n\n"

                        # Format suggestions as streaming markdown
                        yield f"event: action\ndata: {json.dumps({'section': 'Synthesis', 'text': 'Preparing results', 'status': 'in_progress'})}\n\n"
                        answer_parts = [f"# Experiment Suggestions\n\nBased on your research question and knowledge base, here are **{len(suggestions)}** suggested experiments:\n\n"]
                        for idx, s in enumerate(suggestions, 1):
                            status_icon = {"validated": "Validated", "needs_adjustment": "Needs Adjustment", "infeasible": "Infeasible"}.get(s.get("validation_status", ""), "")
                            feasibility_score = s.get("feasibility", {}).get("overall", 0)
                            answer_parts.append(f"## {idx}. {s.get('title', 'Untitled Experiment')}\n\n")
                            if s.get("hypothesis"):
                                answer_parts.append(f"**Hypothesis:** {s['hypothesis']}\n\n")
                            if s.get("methodology"):
                                answer_parts.append(f"**Methodology:** {s['methodology']}\n\n")
                            if s.get("grounding"):
                                answer_parts.append(f"**Grounding:** {s['grounding']}\n\n")
                            if s.get("expected_outcome"):
                                answer_parts.append(f"**Expected Outcome:** {s['expected_outcome']}\n\n")
                            if s.get("controls"):
                                controls_str = ", ".join(s["controls"]) if isinstance(s["controls"], list) else str(s["controls"])
                                answer_parts.append(f"**Controls:** {controls_str}\n\n")
                            if s.get("required_resources"):
                                res_str = ", ".join(s["required_resources"]) if isinstance(s["required_resources"], list) else str(s["required_resources"])
                                answer_parts.append(f"**Required Resources:** {res_str}\n\n")
                            answer_parts.append(f"**Feasibility:** {feasibility_score:.0%} | **Risk:** {s.get('risk_level', 'unknown')} | **Novelty:** {s.get('novelty', 'unknown')}")
                            if status_icon:
                                answer_parts.append(f" | **Status:** {status_icon}")
                            answer_parts.append("\n\n")
                            # Technical issues
                            issues = s.get("technical_issues", [])
                            if issues:
                                answer_parts.append("**Technical Notes:**\n")
                                for issue in issues:
                                    answer_parts.append(f"- [{issue.get('severity', 'info').upper()}] {issue.get('issue', '')}\n")
                                answer_parts.append("\n")
                            answer_parts.append("---\n\n")

                        full_answer = "".join(answer_parts)
                        for chunk_event in _stream_markdown(full_answer):
                            yield chunk_event

                        yield f"event: action\ndata: {json.dumps({'section': 'Synthesis', 'text': 'Preparing results', 'status': 'complete'})}\n\n"
                        yield f"event: done\ndata: {json.dumps({'confidence': 0.85, 'sources': sources_for_response, 'features_used': {'intent': 'experiment_suggestion', 'suggestions_count': len(suggestions)}})}\n\n"
                        _intent_handled = True
                    else:
                        print("[SEARCH-STREAM] No experiment suggestions generated, falling back to RAG", flush=True)

                except Exception as e:
                    import traceback
                    print(f"[SEARCH-STREAM] Experiment suggestion failed, falling back to RAG: {e}", flush=True)
                    traceback.print_exc()

            # ────────────────────────────────────────────────────────────
            # 2. PROTOCOL FEASIBILITY
            # ────────────────────────────────────────────────────────────
            elif _intent_name == "protocol_feasibility":
                try:
                    from services.feasibility_checker import FeasibilityChecker

                    # Step 1: Extract technique
                    yield f"event: action\ndata: {json.dumps({'section': 'Research', 'text': 'Extracting technique details', 'status': 'complete'})}\n\n"

                    # Step 2: Check protocol compatibility — search KB for context
                    yield f"event: action\ndata: {json.dumps({'section': 'Research', 'text': 'Checking protocol compatibility', 'status': 'in_progress'})}\n\n"
                    paper_context, paper_references, raw_kb_results = _search_user_kb(query, vector_store, tenant_id, boost_doc_ids)
                    yield f"event: action\ndata: {json.dumps({'section': 'Research', 'text': 'Checking protocol compatibility', 'status': 'complete'})}\n\n"

                    # Step 3: Run feasibility check
                    yield f"event: action\ndata: {json.dumps({'section': 'Feasibility', 'text': 'Querying evidence database', 'status': 'in_progress'})}\n\n"
                    checker = FeasibilityChecker(llm_client=_azure_client, vector_store=vector_store)
                    experiment = {"title": query, "methodology": query}
                    feasibility = checker.check(experiment, tenant_id=tenant_id)
                    yield f"event: action\ndata: {json.dumps({'section': 'Feasibility', 'text': 'Querying evidence database', 'status': 'complete'})}\n\n"

                    # Step 4: ML protocol analysis if relevant
                    yield f"event: action\ndata: {json.dumps({'section': 'Feasibility', 'text': 'Assessing feasibility', 'status': 'in_progress'})}\n\n"
                    ml_analysis = None
                    try:
                        from services.ml_protocol_service import get_ml_protocol_service
                        ml_service = get_ml_protocol_service()
                        if paper_context:
                            ml_analysis = ml_service.analyze_protocol(paper_context[:5000])
                    except Exception as ml_err:
                        print(f"[SEARCH-STREAM] ML protocol analysis failed: {ml_err}", flush=True)
                    yield f"event: action\ndata: {json.dumps({'section': 'Feasibility', 'text': 'Assessing feasibility', 'status': 'complete'})}\n\n"

                    if feasibility:
                        sources_for_response = _build_sources(raw_kb_results[:10], db)
                        yield f"event: search_complete\ndata: {json.dumps({'expanded_query': query, 'num_sources': len(sources_for_response), 'sources': sources_for_response})}\n\n"

                        # Format feasibility as markdown
                        score = feasibility.get("score", 0)
                        tier = feasibility.get("tier", "unknown")
                        tier_labels = {"high": "Highly Feasible", "medium": "Moderately Feasible", "low": "Low Feasibility", "infeasible": "Infeasible"}
                        answer_parts = [f"# Protocol Feasibility Assessment\n\n"]
                        answer_parts.append(f"**Overall Score:** {score:.0%} — **{tier_labels.get(tier, tier.title())}**\n\n")

                        if feasibility.get("reasoning"):
                            answer_parts.append(f"## Assessment\n\n{feasibility['reasoning']}\n\n")

                        issues = feasibility.get("issues", [])
                        if issues:
                            answer_parts.append(f"## Issues Identified ({len(issues)})\n\n")
                            for issue in issues:
                                severity = issue.get("severity", "info").upper()
                                answer_parts.append(f"- **[{severity}]** {issue.get('description', '')} ")
                                if issue.get("evidence"):
                                    answer_parts.append(f"_(Evidence: {issue['evidence']})_")
                                answer_parts.append("\n")
                            answer_parts.append("\n")

                        modifications = feasibility.get("modifications", [])
                        if modifications:
                            answer_parts.append("## Suggested Modifications\n\n")
                            for mod in modifications:
                                answer_parts.append(f"- **{mod.get('original', '')}** -> {mod.get('suggested', '')} _{mod.get('reason', '')}_\n")
                            answer_parts.append("\n")

                        evidence = feasibility.get("evidence", {})
                        if evidence:
                            answer_parts.append("## Evidence Summary\n\n")
                            if evidence.get("cooccurrence_hits"):
                                answer_parts.append(f"- Co-occurrence matches: {evidence['cooccurrence_hits']}\n")
                            if evidence.get("corpus_matches"):
                                answer_parts.append(f"- Similar protocols found: {evidence['corpus_matches']}\n")
                            if evidence.get("negative_evidence"):
                                answer_parts.append(f"- Negative evidence: {evidence['negative_evidence']}\n")
                            answer_parts.append("\n")

                        if ml_analysis:
                            answer_parts.append("## ML Protocol Analysis\n\n")
                            if ml_analysis.get("is_protocol"):
                                answer_parts.append(f"- Protocol content detected (confidence: {ml_analysis.get('protocol_confidence', 0):.0%})\n")
                                if ml_analysis.get("completeness_score") is not None:
                                    answer_parts.append(f"- Completeness score: {ml_analysis['completeness_score']:.0%}\n")
                            else:
                                answer_parts.append(f"- Content classified as non-protocol (confidence: {ml_analysis.get('protocol_confidence', 0):.0%})\n")
                            answer_parts.append("\n")

                        full_answer = "".join(answer_parts)
                        for chunk_event in _stream_markdown(full_answer):
                            yield chunk_event

                        yield f"event: done\ndata: {json.dumps({'confidence': score, 'sources': sources_for_response, 'features_used': {'intent': 'protocol_feasibility', 'feasibility_tier': tier}})}\n\n"
                        _intent_handled = True
                    else:
                        print("[SEARCH-STREAM] Feasibility check returned no results, falling back to RAG", flush=True)

                except Exception as e:
                    import traceback
                    print(f"[SEARCH-STREAM] Feasibility check failed, falling back to RAG: {e}", flush=True)
                    traceback.print_exc()

            # ────────────────────────────────────────────────────────────
            # 3. JOURNAL ANALYSIS
            # ────────────────────────────────────────────────────────────
            elif _special == 'journal_analysis':
                try:
                    from services.journal_scorer_service import get_journal_scorer_service, FIELD_CONFIGS

                    # Step 1: Find the manuscript in user's KB
                    yield f"event: action\ndata: {json.dumps({'section': 'Research', 'text': 'Identify referenced manuscript', 'status': 'complete'})}\n\n"
                    yield f"event: action\ndata: {json.dumps({'section': 'Research', 'text': 'Search knowledge base for paper content', 'status': 'in_progress'})}\n\n"

                    paper_context, paper_references, raw_kb_results = _search_user_kb(query, vector_store, tenant_id, boost_doc_ids)
                    yield f"event: action\ndata: {json.dumps({'section': 'Research', 'text': 'Search knowledge base for paper content', 'status': 'complete'})}\n\n"

                    if paper_context and len(paper_context) > 500:
                        # Step 2: Run journal analysis using enhanced_search_service's analyzer
                        yield f"event: action\ndata: {json.dumps({'section': 'Journal Analysis', 'text': 'Detect academic field and keywords', 'status': 'in_progress'})}\n\n"

                        journal_analysis = enhanced_service._run_journal_analysis(paper_context, paper_references[0].get('title', 'document') if paper_references else 'document')

                        if journal_analysis:
                            field_label = journal_analysis.get('field_label', 'Unknown')
                            yield f"event: action\ndata: {json.dumps({'section': 'Journal Analysis', 'text': f'Detect academic field and keywords', 'status': 'complete'})}\n\n"
                            yield f"event: action\ndata: {json.dumps({'section': 'Journal Analysis', 'text': f'Detected field: {field_label}', 'status': 'complete'})}\n\n"

                            yield f"event: action\ndata: {json.dumps({'section': 'Journal Analysis', 'text': 'Analyze citation neighborhood', 'status': 'in_progress'})}\n\n"
                            neighbors = journal_analysis.get('citation_neighbor_journals', [])
                            yield f"event: action\ndata: {json.dumps({'section': 'Journal Analysis', 'text': f'Analyze citation neighborhood', 'status': 'complete'})}\n\n"

                            yield f"event: action\ndata: {json.dumps({'section': 'Journal Analysis', 'text': 'Match journals by top-cited authors', 'status': 'in_progress'})}\n\n"
                            kw_journals = journal_analysis.get('keyword_journals', [])
                            yield f"event: action\ndata: {json.dumps({'section': 'Journal Analysis', 'text': 'Match journals by top-cited authors', 'status': 'complete'})}\n\n"

                            gaps = journal_analysis.get('methodology_gaps', [])
                            yield f"event: action\ndata: {json.dumps({'section': 'Journal Analysis', 'text': f'Check methodology gaps', 'status': 'complete'})}\n\n"

                            # Emit full analysis for frontend context panel
                            yield f"event: journal_analysis\ndata: {json.dumps(journal_analysis)}\n\n"

                            # Build sources
                            sources_for_response = _build_sources(raw_kb_results[:10], db)
                            yield f"event: search_complete\ndata: {json.dumps({'expanded_query': query, 'num_sources': len(sources_for_response), 'sources': sources_for_response})}\n\n"

                            # Format as streaming markdown answer
                            yield f"event: action\ndata: {json.dumps({'section': 'Synthesis', 'text': 'Generate journal recommendations', 'status': 'in_progress'})}\n\n"
                            doc_title = journal_analysis.get('doc_title', 'your manuscript')
                            answer_parts = [f"# Journal Recommendations for \"{doc_title}\"\n\n"]
                            answer_parts.append(f"**Academic Field:** {field_label}\n")
                            keywords = journal_analysis.get('keywords', [])
                            if keywords:
                                answer_parts.append(f"**Keywords:** {', '.join(keywords[:8])}\n\n")

                            # Methodology gaps
                            if gaps:
                                answer_parts.append(f"## Methodology Assessment ({len(gaps)} issues found)\n\n")
                                for g in gaps:
                                    answer_parts.append(f"- **[{g.get('severity', 'info').upper()}]** {g.get('gap', '')}: {g.get('recommendation', '')}\n")
                                answer_parts.append("\n")
                            else:
                                answer_parts.append("## Methodology Assessment\n\nNo methodology gaps detected — manuscript looks methodologically sound.\n\n")

                            # Citation neighborhood journals
                            if neighbors:
                                answer_parts.append(f"## Journals from Citation Neighborhood ({len(neighbors)} matches)\n\n")
                                answer_parts.append("These journals frequently publish papers cited alongside your references:\n\n")
                                for j in neighbors[:10]:
                                    answer_parts.append(f"- **{j.get('journal_name', 'Unknown')}** — appears in {j.get('citation_overlap', 0)} reference neighborhoods\n")
                                answer_parts.append("\n")

                            # Keyword-matched journals
                            if kw_journals:
                                answer_parts.append(f"## Journals Matching Paper Keywords ({len(kw_journals)} matches)\n\n")
                                for cat_label, cat_key in [("Target Journals", "primary"), ("Stretch Journals", "stretch"), ("Safe/Backup Journals", "safe")]:
                                    cat_js = [j for j in kw_journals if j.get('category') == cat_key]
                                    if cat_js:
                                        answer_parts.append(f"### {cat_label}\n\n")
                                        for j in cat_js[:5]:
                                            name = j.get('name', 'Unknown')
                                            h_idx = j.get('h_index', 0)
                                            answer_parts.append(f"- **{name}**" + (f" (h-index: {h_idx})" if h_idx else "") + "\n")
                                        answer_parts.append("\n")

                            answer_parts.append(f"\n---\n*Analysis based on {journal_analysis.get('references_found', 0)} references found in manuscript.*\n")

                            full_answer = "".join(answer_parts)
                            for chunk_event in _stream_markdown(full_answer):
                                yield chunk_event

                            yield f"event: action\ndata: {json.dumps({'section': 'Synthesis', 'text': 'Generate journal recommendations', 'status': 'complete'})}\n\n"
                            yield f"event: done\ndata: {json.dumps({'confidence': 0.85, 'sources': sources_for_response, 'features_used': {'intent': 'journal_analysis', 'field': field_label, 'journals_matched': len(neighbors) + len(kw_journals)}})}\n\n"
                            _intent_handled = True
                        else:
                            print("[SEARCH-STREAM] Journal analysis returned None, falling back to RAG", flush=True)
                    else:
                        print("[SEARCH-STREAM] Insufficient paper content for journal analysis, falling back to RAG", flush=True)

                except Exception as e:
                    import traceback
                    print(f"[SEARCH-STREAM] Journal analysis failed, falling back to RAG: {e}", flush=True)
                    traceback.print_exc()

            # ────────────────────────────────────────────────────────────
            # 4. METHODOLOGY ANALYSIS
            # ────────────────────────────────────────────────────────────
            elif _special == 'methodology_analysis':
                try:
                    from services.paper_analysis_service import PaperAnalysisService

                    # Step 1: Find manuscript
                    yield f"event: action\ndata: {json.dumps({'section': 'Research', 'text': 'Identify referenced manuscript', 'status': 'complete'})}\n\n"
                    yield f"event: action\ndata: {json.dumps({'section': 'Research', 'text': 'Retrieve paper content from knowledge base', 'status': 'in_progress'})}\n\n"

                    paper_context, paper_references, raw_kb_results = _search_user_kb(query, vector_store, tenant_id, boost_doc_ids, k=15)

                    # Concatenate all chunks from the top document for richer analysis
                    best_doc_id = raw_kb_results[0].get('doc_id', '') if raw_kb_results else ''
                    doc_text = ""
                    doc_title_meth = "your manuscript"
                    if best_doc_id and raw_kb_results:
                        all_chunks = [r.get('content', '') or r.get('text', '') for r in raw_kb_results if r.get('doc_id') == best_doc_id]
                        doc_text = '\n\n'.join(all_chunks)
                        doc_title_meth = raw_kb_results[0].get('title', 'your manuscript')
                    elif paper_context:
                        doc_text = paper_context

                    yield f"event: action\ndata: {json.dumps({'section': 'Research', 'text': 'Retrieve paper content from knowledge base', 'status': 'complete'})}\n\n"

                    if doc_text and len(doc_text) > 300:
                        # Step 2: Run methodology analysis via PaperAnalysisService
                        yield f"event: action\ndata: {json.dumps({'section': 'Methodology Review', 'text': 'Detect methodology gaps and weaknesses', 'status': 'in_progress'})}\n\n"

                        paper_service = PaperAnalysisService()
                        analysis_result = paper_service._analyze_experimental(doc_text, doc_title_meth)
                        yield f"event: action\ndata: {json.dumps({'section': 'Methodology Review', 'text': 'Detect methodology gaps and weaknesses', 'status': 'complete'})}\n\n"

                        # Step 3: Run methodology gap detection via enhanced search journal analyzer
                        yield f"event: action\ndata: {json.dumps({'section': 'Methodology Review', 'text': 'Assess experimental design', 'status': 'in_progress'})}\n\n"
                        methodology_gaps = []
                        try:
                            from services.journal_scorer_service import get_journal_scorer_service
                            scorer = get_journal_scorer_service()
                            methodology_gaps = scorer._detect_methodology_gaps(doc_text, 'biomedical')
                        except Exception as mg_err:
                            print(f"[SEARCH-STREAM] Methodology gap detection failed: {mg_err}", flush=True)
                        yield f"event: action\ndata: {json.dumps({'section': 'Methodology Review', 'text': 'Assess experimental design', 'status': 'complete'})}\n\n"

                        # Build sources
                        sources_for_response = _build_sources(raw_kb_results[:10], db)
                        yield f"event: search_complete\ndata: {json.dumps({'expanded_query': query, 'num_sources': len(sources_for_response), 'sources': sources_for_response})}\n\n"

                        # Format as streaming markdown
                        yield f"event: action\ndata: {json.dumps({'section': 'Synthesis', 'text': 'Generate improvement recommendations', 'status': 'in_progress'})}\n\n"

                        answer_parts = [f"# Methodology Analysis: \"{doc_title_meth}\"\n\n"]

                        if not analysis_result.get('error'):
                            if analysis_result.get('summary'):
                                answer_parts.append(f"## Summary\n\n{analysis_result['summary']}\n\n")
                            if analysis_result.get('research_question'):
                                answer_parts.append(f"**Research Question:** {analysis_result['research_question']}\n\n")

                            meth = analysis_result.get('methodology', {})
                            if meth:
                                answer_parts.append("## Methodology Details\n\n")
                                if meth.get('study_design'):
                                    answer_parts.append(f"- **Study Design:** {meth['study_design']}\n")
                                if meth.get('techniques'):
                                    answer_parts.append(f"- **Techniques:** {', '.join(meth['techniques'])}\n")
                                if meth.get('model_system'):
                                    answer_parts.append(f"- **Model System:** {meth['model_system']}\n")
                                if meth.get('sample_size'):
                                    answer_parts.append(f"- **Sample Size:** {meth['sample_size']}\n")
                                answer_parts.append("\n")

                            limitations = analysis_result.get('limitations', [])
                            if limitations:
                                answer_parts.append(f"## Limitations ({len(limitations)})\n\n")
                                for lim in limitations:
                                    answer_parts.append(f"- {lim}\n")
                                answer_parts.append("\n")

                            repro = analysis_result.get('reproducibility_assessment', {})
                            if repro:
                                answer_parts.append("## Reproducibility Assessment\n\n")
                                if repro.get('methods_completeness'):
                                    answer_parts.append(f"- **Methods Completeness:** {repro['methods_completeness']}\n")
                                if repro.get('data_availability'):
                                    answer_parts.append(f"- **Data Availability:** {repro['data_availability']}\n")
                                if repro.get('reagent_details'):
                                    answer_parts.append(f"- **Reagent Details:** {repro['reagent_details']}\n")
                                issues = repro.get('issues', [])
                                if issues:
                                    answer_parts.append("\n**Reproducibility Issues:**\n")
                                    for issue in issues:
                                        answer_parts.append(f"- {issue}\n")
                                answer_parts.append("\n")

                            stats = analysis_result.get('statistical_methods', [])
                            if stats:
                                answer_parts.append(f"## Statistical Methods\n\n{', '.join(stats)}\n\n")

                            findings = analysis_result.get('key_findings', [])
                            if findings:
                                answer_parts.append(f"## Key Findings\n\n")
                                for f_item in findings:
                                    answer_parts.append(f"- {f_item}\n")
                                answer_parts.append("\n")
                        else:
                            answer_parts.append(f"*Detailed analysis could not be completed: {analysis_result.get('error', 'unknown error')}*\n\n")

                        # Methodology gaps from journal scorer
                        if methodology_gaps:
                            answer_parts.append(f"## Methodology Gaps ({len(methodology_gaps)} issues)\n\n")
                            for g in methodology_gaps:
                                answer_parts.append(f"- **[{g.get('severity', 'info').upper()}]** {g.get('gap', '')}: {g.get('recommendation', '')}\n")
                            answer_parts.append("\n")

                        full_answer = "".join(answer_parts)
                        for chunk_event in _stream_markdown(full_answer):
                            yield chunk_event

                        yield f"event: action\ndata: {json.dumps({'section': 'Synthesis', 'text': 'Generate improvement recommendations', 'status': 'complete'})}\n\n"
                        yield f"event: done\ndata: {json.dumps({'confidence': 0.8, 'sources': sources_for_response, 'features_used': {'intent': 'methodology_analysis', 'gaps_found': len(methodology_gaps)}})}\n\n"
                        _intent_handled = True
                    else:
                        print("[SEARCH-STREAM] Insufficient paper content for methodology analysis, falling back to RAG", flush=True)

                except Exception as e:
                    import traceback
                    print(f"[SEARCH-STREAM] Methodology analysis failed, falling back to RAG: {e}", flush=True)
                    traceback.print_exc()

            # ────────────────────────────────────────────────────────────
            # 5. KNOWLEDGE GAP ANALYSIS
            # ────────────────────────────────────────────────────────────
            elif _intent_name == "knowledge_gap":
                try:
                    from services.knowledge_service import KnowledgeService

                    # Emit plan steps (not emitted by default for knowledge_gap intent)
                    yield f"event: action\ndata: {json.dumps({'section': 'Research', 'text': 'Scanning knowledge base documents', 'status': 'in_progress'})}\n\n"

                    # Search KB for context to return as sources
                    paper_context, paper_references, raw_kb_results = _search_user_kb(query, vector_store, tenant_id, boost_doc_ids)
                    yield f"event: action\ndata: {json.dumps({'section': 'Research', 'text': 'Scanning knowledge base documents', 'status': 'complete'})}\n\n"

                    yield f"event: action\ndata: {json.dumps({'section': 'Analysis', 'text': 'Running intelligent gap detection', 'status': 'in_progress'})}\n\n"

                    knowledge_service = KnowledgeService(db)
                    gap_result = knowledge_service.analyze_gaps_intelligent(
                        tenant_id=tenant_id,
                        max_documents=50,
                    )
                    yield f"event: action\ndata: {json.dumps({'section': 'Analysis', 'text': 'Running intelligent gap detection', 'status': 'complete'})}\n\n"

                    if gap_result and gap_result.gaps:
                        sources_for_response = _build_sources(raw_kb_results[:10], db)
                        yield f"event: search_complete\ndata: {json.dumps({'expanded_query': query, 'num_sources': len(sources_for_response), 'sources': sources_for_response})}\n\n"

                        yield f"event: action\ndata: {json.dumps({'section': 'Synthesis', 'text': 'Formatting gap analysis results', 'status': 'in_progress'})}\n\n"

                        gaps = gap_result.gaps
                        categories = gap_result.categories_found
                        total_docs = gap_result.total_documents_analyzed

                        answer_parts = [f"# Knowledge Gap Analysis\n\n"]
                        answer_parts.append(f"Analyzed **{total_docs}** documents and identified **{len(gaps)}** knowledge gaps.\n\n")

                        if categories:
                            answer_parts.append("## Gap Categories\n\n")
                            for cat, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
                                answer_parts.append(f"- **{cat.title()}**: {count} gaps\n")
                            answer_parts.append("\n")

                        answer_parts.append("## Identified Gaps\n\n")
                        for idx, gap in enumerate(gaps[:20], 1):
                            gap_cat = gap.get('category', 'general').title()
                            gap_title = gap.get('title', 'Unknown gap')
                            gap_priority = gap.get('priority', 3)
                            gap_q_count = gap.get('questions_count', 0)
                            priority_labels = {1: "Critical", 2: "High", 3: "Medium", 4: "Low", 5: "Optional"}
                            priority_label = priority_labels.get(gap_priority, f"Level {gap_priority}")
                            answer_parts.append(f"### {idx}. [{gap_cat}] {gap_title}\n\n")
                            answer_parts.append(f"**Priority:** {priority_label}")
                            if gap_q_count:
                                answer_parts.append(f" | **Questions:** {gap_q_count}")
                            answer_parts.append("\n\n---\n\n")

                        answer_parts.append(f"\n*Analysis used the intelligent gap detection engine (6-layer NLP analysis) on {total_docs} documents.*\n")

                        full_answer = "".join(answer_parts)
                        for chunk_event in _stream_markdown(full_answer):
                            yield chunk_event

                        yield f"event: action\ndata: {json.dumps({'section': 'Synthesis', 'text': 'Formatting gap analysis results', 'status': 'complete'})}\n\n"
                        yield f"event: done\ndata: {json.dumps({'confidence': 0.8, 'sources': sources_for_response, 'features_used': {'intent': 'knowledge_gap', 'gaps_found': len(gaps), 'docs_analyzed': total_docs}})}\n\n"
                        _intent_handled = True
                    else:
                        print("[SEARCH-STREAM] No knowledge gaps found, falling back to RAG", flush=True)

                except Exception as e:
                    import traceback
                    print(f"[SEARCH-STREAM] Knowledge gap analysis failed, falling back to RAG: {e}", flush=True)
                    traceback.print_exc()

            # ────────────────────────────────────────────────────────────
            # 6. LITERATURE SEARCH
            # ────────────────────────────────────────────────────────────
            elif _intent_name == "literature_search":
                try:
                    from services.openalex_search_service import OpenAlexSearchService

                    # Emit plan steps
                    yield f"event: action\ndata: {json.dumps({'section': 'Research', 'text': 'Expanding search terms', 'status': 'in_progress'})}\n\n"

                    # Also search user's KB for internal context
                    paper_context, paper_references, raw_kb_results = _search_user_kb(query, vector_store, tenant_id, boost_doc_ids, k=5)
                    yield f"event: action\ndata: {json.dumps({'section': 'Research', 'text': 'Expanding search terms', 'status': 'complete'})}\n\n"

                    # Search external sources
                    yield f"event: action\ndata: {json.dumps({'section': 'Literature', 'text': 'Searching OpenAlex & PubMed', 'status': 'in_progress'})}\n\n"

                    openalex_service = OpenAlexSearchService()
                    external_papers = openalex_service.search_works(
                        query=query,
                        max_results=15,
                        min_citations=0,
                    )
                    yield f"event: action\ndata: {json.dumps({'section': 'Literature', 'text': f'Searching OpenAlex & PubMed', 'status': 'complete'})}\n\n"

                    yield f"event: action\ndata: {json.dumps({'section': 'Analysis', 'text': 'Ranking results by relevance and citations', 'status': 'in_progress'})}\n\n"

                    # Sort by citation count (most cited first)
                    external_papers.sort(key=lambda p: p.get('cited_by_count', 0), reverse=True)
                    yield f"event: action\ndata: {json.dumps({'section': 'Analysis', 'text': 'Ranking results by relevance and citations', 'status': 'complete'})}\n\n"

                    if external_papers:
                        # Build sources: combine KB results with external papers
                        sources_for_response = _build_sources(raw_kb_results[:5], db)
                        for paper in external_papers[:10]:
                            sources_for_response.append({
                                "doc_id": paper.get('openalex_id', ''),
                                "title": paper.get('title', 'Untitled'),
                                "content_preview": (paper.get('abstract', '') or '')[:300],
                                "score": min(1.0, paper.get('cited_by_count', 0) / 100),
                                "source_origin": "openalex",
                                "source_origin_label": "OpenAlex",
                                "source_url": paper.get('doi', ''),
                            })

                        yield f"event: search_complete\ndata: {json.dumps({'expanded_query': query, 'num_sources': len(sources_for_response), 'sources': sources_for_response})}\n\n"

                        yield f"event: action\ndata: {json.dumps({'section': 'Synthesis', 'text': 'Formatting literature review', 'status': 'in_progress'})}\n\n"

                        answer_parts = [f"# Literature Search Results\n\n"]
                        answer_parts.append(f"Found **{len(external_papers)}** papers from OpenAlex")
                        if raw_kb_results:
                            answer_parts.append(f" and **{len(raw_kb_results)}** related items in your knowledge base")
                        answer_parts.append(".\n\n")

                        # Top papers
                        answer_parts.append("## Key Papers\n\n")
                        for idx, paper in enumerate(external_papers[:10], 1):
                            title = paper.get('title', 'Untitled')
                            authors = paper.get('authors', [])
                            year = paper.get('year', '')
                            cited = paper.get('cited_by_count', 0)
                            journal = paper.get('journal', '')
                            doi = paper.get('doi', '')
                            abstract = paper.get('abstract', '')

                            author_str = ', '.join(authors[:3])
                            if len(authors) > 3:
                                author_str += f' et al.'

                            answer_parts.append(f"### {idx}. {title}\n\n")
                            answer_parts.append(f"**{author_str}** ({year})")
                            if journal:
                                answer_parts.append(f" — *{journal}*")
                            answer_parts.append(f"\n\n")
                            answer_parts.append(f"**Citations:** {cited:,}")
                            if doi:
                                answer_parts.append(f" | [DOI]({doi})")
                            answer_parts.append("\n\n")
                            if abstract:
                                answer_parts.append(f"{abstract[:400]}{'...' if len(abstract) > 400 else ''}\n\n")
                            answer_parts.append("---\n\n")

                        # Relevant KB items
                        if paper_references:
                            answer_parts.append("## Related Items in Your Knowledge Base\n\n")
                            for ref in paper_references[:5]:
                                answer_parts.append(f"- {ref.get('title', 'Untitled')}\n")
                            answer_parts.append("\n")

                        full_answer = "".join(answer_parts)
                        for chunk_event in _stream_markdown(full_answer):
                            yield chunk_event

                        yield f"event: action\ndata: {json.dumps({'section': 'Synthesis', 'text': 'Formatting literature review', 'status': 'complete'})}\n\n"
                        yield f"event: done\ndata: {json.dumps({'confidence': 0.85, 'sources': sources_for_response, 'features_used': {'intent': 'literature_search', 'external_papers': len(external_papers), 'kb_results': len(raw_kb_results)}})}\n\n"
                        _intent_handled = True
                    else:
                        print("[SEARCH-STREAM] No external papers found, falling back to RAG", flush=True)

                except Exception as e:
                    import traceback
                    print(f"[SEARCH-STREAM] Literature search failed, falling back to RAG: {e}", flush=True)
                    traceback.print_exc()

            # ================================================================
            # STANDARD RAG FLOW (default, or fallback if specialized intent failed)
            # ================================================================
            if not _intent_handled:
                sources_for_response = []
                for event in enhanced_service.search_and_answer_stream(
                    query=query,
                    tenant_id=tenant_id,
                    vector_store=vector_store,
                    top_k=top_k,
                    conversation_history=conversation_history,
                    boost_doc_ids=boost_doc_ids,
                    response_mode=response_mode,
                    user_context=user_context,
                    source_types=source_types
                ):
                    event_type = event.get('type')

                    if event_type == 'journal_analysis':
                        # Emit journal analysis plan steps and thinking events
                        analysis = event.get('analysis', {})
                        field_text = 'Detected field: ' + analysis.get('field_label', 'Unknown')
                        action1 = json.dumps({'section': 'Journal Analysis', 'text': field_text, 'status': 'complete'})
                        yield f"event: action\ndata: {action1}\n\n"
                        gaps = analysis.get('methodology_gaps', [])
                        gap_text = 'Found ' + str(len(gaps)) + ' methodology gaps'
                        action2 = json.dumps({'section': 'Journal Analysis', 'text': gap_text, 'status': 'complete'})
                        yield f"event: action\ndata: {action2}\n\n"
                        neighbors = analysis.get('citation_neighbor_journals', [])
                        kw_journals = analysis.get('keyword_journals', [])
                        total_journals = len(neighbors) + len(kw_journals)
                        journal_text = 'Matched ' + str(total_journals) + ' target journals'
                        action3 = json.dumps({'section': 'Journal Analysis', 'text': journal_text, 'status': 'complete'})
                        yield f"event: action\ndata: {action3}\n\n"
                        doc_title = analysis.get('doc_title', 'document')
                        thinking_text = 'Running High-Impact Journal Analysis on ' + doc_title + '...'
                        thinking_data = json.dumps({'type': 'journal_analysis', 'text': thinking_text})
                        yield f"event: thinking\ndata: {thinking_data}\n\n"
                        # Emit the full analysis data as a separate event for the frontend context panel
                        analysis_data = json.dumps(analysis)
                        yield f"event: journal_analysis\ndata: {analysis_data}\n\n"

                    elif event_type == 'search_complete':
                        raw_sources = event.get('sources', [])

                        # Enrich with source_url from DB
                        doc_ids = [s.get('doc_id', '') for s in raw_sources if s.get('doc_id')]
                        source_url_map = {}
                        if doc_ids:
                            try:
                                docs_with_urls = db.query(Document.id, Document.source_url).filter(
                                    Document.id.in_(doc_ids)
                                ).all()
                                source_url_map = {str(d.id): d.source_url for d in docs_with_urls if d.source_url}
                            except Exception:
                                pass

                        # Build doc source_type lookup for origin tagging
                        doc_source_type_map = {}
                        if doc_ids:
                            try:
                                docs_with_types = db.query(Document.id, Document.source_type).filter(
                                    Document.id.in_(doc_ids)
                                ).all()
                                doc_source_type_map = {str(d.id): d.source_type for d in docs_with_types}
                            except Exception:
                                pass

                        for src in raw_sources:
                            doc_id = src.get('doc_id', '')
                            is_shared = src.get('is_shared', False)
                            source_entry = {
                                "doc_id": doc_id,
                                "title": src.get('title', 'Untitled'),
                                "content_preview": (src.get('content', '') or '')[:300],
                                "score": src.get('rerank_score', src.get('score', 0)),
                            }
                            if src.get('source_origin') == 'openalex':
                                source_entry["source_origin"] = "openalex"
                                source_entry["source_origin_label"] = src.get('source_origin_label', 'OpenAlex')
                                source_entry["source_url"] = src.get('source_url', '')
                            elif is_shared:
                                source_entry["source_url"] = src.get('source_url', '')
                                source_entry["is_shared"] = True
                                source_entry["facility_name"] = src.get('facility_name', '')
                                source_entry["source_origin"] = "ctsi"
                                source_entry["source_origin_label"] = "CTSI Research"
                            else:
                                source_entry["source_url"] = source_url_map.get(doc_id, '')
                                # Determine origin from source_type
                                doc_st = doc_source_type_map.get(doc_id, '')
                                if doc_st == 'pubmed':
                                    source_entry["source_origin"] = "pubmed"
                                    source_entry["source_origin_label"] = "PubMed"
                                elif doc_st == 'journal':
                                    source_entry["source_origin"] = "journal"
                                    source_entry["source_origin_label"] = "Journal DB"
                                elif doc_st == 'experiment':
                                    source_entry["source_origin"] = "reproducibility"
                                    source_entry["source_origin_label"] = "Repro Archive"
                                else:
                                    source_entry["source_origin"] = "user_kb"
                                    source_entry["source_origin_label"] = "Your KB"
                            sources_for_response.append(source_entry)

                        # Emit decomposition action if query was decomposed
                        features_used = event.get('features_used', {})
                        if features_used.get('decomposition'):
                            sub_queries = features_used.get('sub_queries', [])
                            yield f"event: action\ndata: {json.dumps({'section': 'Research', 'text': f'Decomposed into {len(sub_queries)} sub-queries', 'status': 'in_progress'})}\n\n"

                        # Thinking: report search results found
                        yield f"event: thinking\ndata: {json.dumps({'type': 'searching_kb', 'text': f'Searching knowledge base... Found {len(sources_for_response)} sources'})}\n\n"

                        # Thinking: reranking
                        yield f"event: thinking\ndata: {json.dumps({'type': 'reranking', 'text': 'Reranking and filtering results...'})}\n\n"

                        yield f"event: search_complete\ndata: {json.dumps({'expanded_query': event.get('expanded_query', query), 'num_sources': event.get('num_sources', 0), 'sources': sources_for_response})}\n\n"

                        # Thinking: generating answer
                        yield f"event: thinking\ndata: {json.dumps({'type': 'generating', 'text': 'Generating answer...'})}\n\n"

                    elif event_type == 'chunk':
                        content = event.get('content', '')
                        print(f"[STREAM-CHUNK] Sending: {content[:20]}...", flush=True)
                        yield f"event: chunk\ndata: {json.dumps({'content': content})}\n\n"

                    elif event_type == 'done':
                        final_data = {
                            'confidence': event.get('confidence', 0.8),
                            'sources': sources_for_response,
                            'hallucination_check': event.get('hallucination_check'),
                            'features_used': event.get('features_used', {})
                        }
                        # Include answer confidence scoring if available
                        answer_confidence = event.get('answer_confidence')
                        if answer_confidence:
                            final_data['answer_confidence'] = answer_confidence
                        yield f"event: done\ndata: {json.dumps(final_data)}\n\n"

            print(f"[SEARCH-STREAM] Complete: '{query}'", flush=True)

        except Exception as e:
            import traceback
            print(f"[SEARCH-STREAM] Error: {e}", flush=True)
            traceback.print_exc()
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
        finally:
            db.close()

    # Wrap generator to yield bytes for streaming with immediate flush
    def byte_generator():
        # Send initial padding to force buffer flush (AWS ALB workaround)
        yield b": padding to force flush\n\n"
        for chunk in generate():
            yield chunk.encode('utf-8')
            # Yield empty bytes after each chunk to trigger flush
            yield b""

    response = Response(
        stream_with_context(byte_generator()),
        mimetype='text/event-stream',
        direct_passthrough=True,
        headers={
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
            'Content-Type': 'text/event-stream; charset=utf-8',
            'Transfer-Encoding': 'chunked'
        }
    )
    # Disable response buffering
    response.implicit_sequence_conversion = False
    return response


# ============================================================================
# FEEDBACK ENDPOINT
# ============================================================================

@app.route('/api/feedback', methods=['POST'])
@require_auth
def submit_feedback():
    """Submit thumbs up/down feedback on a chat response."""
    from database.models import SessionLocal, AuditLog
    data = request.get_json() or {}
    db = SessionLocal()
    try:
        audit = AuditLog(
            tenant_id=g.tenant_id,
            user_id=g.user_id,
            action=f"feedback:{data.get('rating', 'unknown')}",
            resource_type='chat_feedback',
            resource_id=None,
            changes={
                'query': (data.get('query', '') or '')[:500],
                'answer': (data.get('answer', '') or '')[:500],
                'rating': data.get('rating'),
                'source_ids': data.get('source_ids', []),
            },
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


# ============================================================================
# PROJECTS ENDPOINT
# ============================================================================

@app.route('/api/projects', methods=['GET'])
def list_projects():
    """List projects for tenant"""
    from services.auth_service import get_token_from_header, JWTUtils
    from database.models import Project

    # Get tenant
    token = get_token_from_header(request.headers.get("Authorization", ""))
    tenant_id = None

    if token:
        payload, _ = JWTUtils.decode_access_token(token)
        if payload:
            tenant_id = payload.get("tenant_id")

    if not tenant_id:
        # Try legacy endpoint
        return jsonify({
            "success": True,
            "projects": []
        })

    db = SessionLocal()
    try:
        projects = db.query(Project).filter(
            Project.tenant_id == tenant_id,
            Project.is_archived == False
        ).all()

        return jsonify({
            "success": True,
            "projects": [p.to_dict() for p in projects]
        })
    finally:
        db.close()

# ============================================================================
# CITATION GRAPH ENDPOINT
# ============================================================================

@app.route('/api/citations/graph', methods=['POST'])
@require_auth
def get_citation_graph():
    """Build citation graph around a seed paper."""
    data = request.get_json() or {}
    openalex_id = data.get('openalex_id')
    if not openalex_id:
        return jsonify({'error': 'openalex_id required'}), 400

    depth = min(data.get('depth', 1), 2)  # Cap at 2
    max_nodes = min(data.get('max_nodes', 50), 100)  # Cap at 100

    try:
        from services.citation_graph_service import CitationGraphService
        service = CitationGraphService()
        graph = service.build_citation_graph(openalex_id, depth=depth, max_nodes=max_nodes)
        return jsonify(graph)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# LEGACY URL REDIRECTS
# ============================================================================

@app.route('/api/document/<document_id>/view')
def legacy_document_view(document_id):
    """Redirect old /document/ URLs to new /documents/ path"""
    from flask import redirect
    return redirect(f'/api/documents/{document_id}/view', code=301)


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def not_found(e):
    return jsonify({
        "success": False,
        "error": "Endpoint not found"
    }), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({
        "success": False,
        "error": "Internal server error"
    }), 500

# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5003))
    debug = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   🧠 2nd Brain - Enterprise Knowledge Transfer Platform      ║
║                                                              ║
║   Version: 2.0.0 (B2B SaaS Edition)                         ║
║   Port: {port}                                                ║
║                                                              ║
║   Endpoints:                                                 ║
║   - POST /api/auth/signup     - User registration           ║
║   - POST /api/auth/login      - User login                  ║
║   - GET  /api/integrations    - List integrations           ║
║   - GET  /api/documents       - List documents              ║
║   - POST /api/documents/classify - Classify documents       ║
║   - GET  /api/knowledge/gaps  - Knowledge gaps              ║
║   - POST /api/knowledge/transcribe - Voice transcription    ║
║   - POST /api/videos          - Create video                ║
║   - POST /api/search          - RAG search                  ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
""")

    app.run(host='0.0.0.0', port=port, debug=debug, threaded=True)
