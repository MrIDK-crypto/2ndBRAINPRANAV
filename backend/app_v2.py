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
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max upload size

# CORS configuration - use CORS_ORIGINS env var or defaults
_cors_origins = os.getenv("CORS_ORIGINS", "").split(",") if os.getenv("CORS_ORIGINS") else []
_cors_origins.extend([
    "http://localhost:3000",
    "http://localhost:3006",
    "http://localhost:3007",
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
    return jsonify({"error": "Internal server error", "message": str(e)}), 500

@app.errorhandler(413)
def handle_413(e):
    return jsonify({"error": "File too large. Maximum upload size is 100MB."}), 413

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
# share_bp removed - invitation system lives in auth_bp

print("✓ API blueprints registered")

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
            "knowledge_gaps": "GET /api/knowledge/gaps",
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
            "knowledge_gaps": True,
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

    if not query:
        return jsonify({
            "success": False,
            "error": "Query required"
        }), 400

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

            enhanced_service = get_enhanced_search_service()
            result = enhanced_service.search_and_answer(
                query=query,
                tenant_id=tenant_id,
                vector_store=vector_store,
                top_k=top_k,
                validate=True,
                conversation_history=conversation_history,  # Pass conversation history
                boost_doc_ids=boost_doc_ids,  # Boost newly uploaded docs
                response_mode=response_mode
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

                for src in raw_sources:
                    doc_id = src.get('doc_id', '')
                    sources.append({
                        "doc_id": doc_id,
                        "title": src.get('title', 'Untitled'),
                        "content_preview": (src.get('content', '') or src.get('content_preview', ''))[:300],
                        "score": src.get('rerank_score', src.get('score', 0)),
                        "metadata": src.get('metadata', {}),
                        "source_url": source_url_map.get(doc_id, '')
                    })

            # Build response
            response_data = {
                "success": True,
                "query": query,
                "expanded_query": result.get('expanded_query'),
                "answer": result.get('answer', ''),
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
    from database.models import SessionLocal, Document, Tenant

    tenant_id = g.tenant_id
    print(f"[SEARCH-STREAM] Tenant: {tenant_id}", flush=True)

    data = request.get_json() or {}
    query = data.get('query', '')
    conversation_history = data.get('conversation_history', [])
    top_k = data.get('top_k', 10)
    boost_doc_ids = data.get('boost_doc_ids', [])

    if not query:
        def error_gen():
            yield f"event: error\ndata: {json.dumps({'error': 'Query required'})}\n\n"
        return Response(error_gen(), mimetype='text/event-stream')

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
                yield f"event: chunk\ndata: {json.dumps({'content': 'Your knowledge base is empty. Please add some documents first.'})}\n\n"
                yield f"event: done\ndata: {json.dumps({'confidence': 1.0, 'sources': []})}\n\n"
                return

            from services.enhanced_search_service import get_enhanced_search_service
            enhanced_service = get_enhanced_search_service()

            print(f"[SEARCH-STREAM] Starting (mode={response_mode}): '{query}'", flush=True)

            sources_for_response = []
            for event in enhanced_service.search_and_answer_stream(
                query=query,
                tenant_id=tenant_id,
                vector_store=vector_store,
                top_k=top_k,
                conversation_history=conversation_history,
                boost_doc_ids=boost_doc_ids,
                response_mode=response_mode
            ):
                event_type = event.get('type')

                if event_type == 'search_complete':
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

                    for src in raw_sources:
                        doc_id = src.get('doc_id', '')
                        sources_for_response.append({
                            "doc_id": doc_id,
                            "title": src.get('title', 'Untitled'),
                            "content_preview": (src.get('content', '') or '')[:300],
                            "score": src.get('rerank_score', src.get('score', 0)),
                            "source_url": source_url_map.get(doc_id, '')
                        })

                    yield f"event: search_complete\ndata: {json.dumps({'expanded_query': event.get('expanded_query', query), 'num_sources': event.get('num_sources', 0), 'sources': sources_for_response})}\n\n"

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
