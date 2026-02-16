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
import secrets
from pathlib import Path
from datetime import datetime, timezone

from flask import Flask, jsonify, request, g
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

# CORS configuration - use CORS_ORIGINS env var or defaults
_cors_origins = os.getenv("CORS_ORIGINS", "").split(",") if os.getenv("CORS_ORIGINS") else []
_cors_origins.extend([
    "http://localhost:3000",
    "http://localhost:3006",
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
             "allow_headers": ["Content-Type", "Authorization", "X-Share-Token"]
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

@app.errorhandler(404)
def handle_404(e):
    return jsonify({"error": "Not found", "path": request.path}), 404

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
from api.email_forwarding_routes import email_forwarding_bp
from api.admin_routes import admin_bp, ensure_admins, fix_untitled_conversations
from api.website_routes import website_bp
from api.share_routes import share_bp

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
app.register_blueprint(email_forwarding_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(website_bp)
app.register_blueprint(share_bp)

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
    print(f"[SEARCH] Tenant: {tenant_id} (shared={getattr(g, 'is_shared_access', False)})", flush=True)

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

        # Use Enhanced Search Service
        if use_enhanced:
            from services.enhanced_search_service import get_enhanced_search_service

            print(f"[SEARCH] Using ENHANCED search for tenant {tenant_id}: '{query}'", flush=True)

            enhanced_service = get_enhanced_search_service()
            result = enhanced_service.search_and_answer(
                query=query,
                tenant_id=tenant_id,
                vector_store=vector_store,
                top_k=top_k,
                validate=True,
                conversation_history=conversation_history,  # Pass conversation history
                boost_doc_ids=boost_doc_ids  # Boost newly uploaded docs
            )

            # Format sources for response
            sources = []
            if include_sources:
                for src in result.get('sources', []):
                    sources.append({
                        "doc_id": src.get('doc_id', ''),
                        "title": src.get('title', 'Untitled'),
                        "content_preview": (src.get('content', '') or src.get('content_preview', ''))[:300],
                        "score": src.get('rerank_score', src.get('score', 0)),
                        "metadata": src.get('metadata', {})
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

    app.run(host='0.0.0.0', port=port, debug=debug)
